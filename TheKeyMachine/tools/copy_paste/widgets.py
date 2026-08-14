"""Copy/paste-specific widgets.

The group uses standard registry buttons and declarative menus. ``PasteToDialog``
and its namespace-resolution helpers own the paste-target UI: they are only
consumed by ``tools.copy_paste.controller`` and resolve Maya namespaces
directly, so they live with the feature instead of in the shared
``widgets`` package.
"""

from TheKeyMachine.core.Qt import QtCore, QtWidgets
from TheKeyMachine.data import icons
from TheKeyMachine.ui.widgets import customDialogs
from TheKeyMachine.ui.widgets.util import DPI


def _paste_to_node_leaf(node):
    return str(node or "").split("|")[-1]


def _paste_to_node_namespace(node):
    leaf = _paste_to_node_leaf(node)
    if ":" not in leaf:
        return ""
    return leaf.rsplit(":", 1)[0]


def _paste_to_node_base_name(node):
    return _paste_to_node_leaf(node).rsplit(":", 1)[-1]


def _paste_to_node_with_namespace(base_name, namespace):
    namespace = str(namespace or "").strip().strip(":")
    return f"{namespace}:{base_name}" if namespace else base_name


def _paste_to_scene_namespaces():
    from maya import cmds

    namespaces = set()
    try:
        namespaces.update(cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or [])
    except Exception:
        pass
    namespaces.discard("UI")
    namespaces.discard("shared")
    namespaces.discard(":")
    return [""] + sorted(ns.strip(":") for ns in namespaces if ns is not None)


def _paste_to_namespace_display(namespace):
    return namespace or ""


def _paste_to_resolve_node(source_node, namespace):
    from maya import cmds

    candidate = _paste_to_node_with_namespace(_paste_to_node_base_name(source_node), namespace)
    if cmds.objExists(candidate):
        return candidate
    matches = cmds.ls(candidate, long=False) or []
    return matches[0] if matches else None


def _paste_to_asset_key(source_node):
    namespace = _paste_to_node_namespace(source_node)
    return namespace or "<root>"


def _paste_to_asset_display(asset_key):
    return "" if asset_key == "<root>" else asset_key


class PasteToDialog:
    def __init__(self, saved_data, apply_callback, data_label="animation", parent=None):
        self.saved_data = saved_data or {}
        self.apply_callback = apply_callback
        self.data_label = data_label
        self._asset_rows = {}
        self._asset_sources = {}

        title = f"Paste {data_label.title()} To..."
        buttons = []
        if data_label == "animation":
            buttons.append(
                customDialogs.QFlatDialogButton(
                    "Paste Insert Animation",
                    callback=lambda: self._apply(insert=True),
                    icon=icons.paste_insert_animation,
                    highlight=True,
                )
            )
        buttons.extend(
            [
                customDialogs.QFlatDialogButton(
                    f"Paste Replace {data_label.title()}",
                    callback=lambda: self._apply(insert=False),
                    icon=icons.paste_animation if data_label == "animation" else icons.paste_pose,
                    highlight=True,
                ),
                customDialogs.QFlatDialogButton("Close", callback=self.close, icon=icons.close),
            ]
        )

        self.dialog = customDialogs.QFlatDialog(parent=parent, buttons=buttons, closeButton=False)
        self.dialog.setWindowTitle(title)
        self.dialog.addWindowHeader(
            self.dialog.root_layout,
            text=title,
            icon=icons.paste_animation if data_label == "animation" else icons.paste_pose,
        )
        self._build_content()
        self.dialog.setBottomBar(buttons=buttons)
        self.dialog.resize(DPI(590), DPI(390))

    def show(self):
        self.dialog.show()
        self.dialog.raise_()

    def close(self):
        self.dialog.close()

    def _build_content(self):
        content = QtWidgets.QWidget(self.dialog)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(DPI(10), 0, DPI(10), DPI(10))
        layout.setSpacing(DPI(6))

        self.tree = QtWidgets.QTreeWidget(content)
        self.tree.setObjectName("pasteToAssetsTree")
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Assets", "Scene Namespace", "Custom Namespace"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setAllColumnsShowFocus(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tree.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.tree.header().setStretchLastSection(True)
        self.tree.setStyleSheet(
            """
            QTreeWidget#pasteToAssetsTree {
                background-color: #282828;
                alternate-background-color: #303030;
                border: 1px solid #3b3b3b;
                color: #bdbdbd;
                outline: none;
            }
            QTreeWidget#pasteToAssetsTree::item:selected {
                background-color: #4a4a4a;
                color: #ffffff;
            }
            QTreeWidget#pasteToAssetsTree QLineEdit#pasteToCustomNamespace {
                background-color: #bdbdbd;
                border: none;
                border-radius: 5px;
                color: #202020;
                padding: 2px 7px;
                font-size: 11px;
            }
            QTreeWidget#pasteToAssetsTree QHeaderView::section {
                background-color: #444444;
                color: #c7c7c7;
                border: none;
                padding: 4px;
                font-weight: bold;
            }
            """
        )
        layout.addWidget(self.tree, 1)
        self.dialog.root_layout.addWidget(content)
        self._populate_tree()

    def _populate_tree(self):
        scene_namespaces = _paste_to_scene_namespaces()
        for source_node in sorted((self.saved_data or {}).keys()):
            asset_key = _paste_to_asset_key(source_node)
            self._asset_sources.setdefault(asset_key, []).append(source_node)

        for asset_key in sorted(self._asset_sources.keys(), key=lambda value: _paste_to_asset_display(value).lower()):
            source_namespace = _paste_to_asset_display(asset_key)
            preview_text = self._asset_preview(asset_key, source_namespace)
            item = QtWidgets.QTreeWidgetItem([source_namespace or "<root>", preview_text, ""])
            item.setData(0, QtCore.Qt.UserRole, asset_key)
            self.tree.addTopLevelItem(item)

            combo = QtWidgets.QComboBox(self.tree)
            combo.setObjectName("pasteToNamespaceCombo")
            for scene_namespace in scene_namespaces:
                combo.addItem(_paste_to_namespace_display(scene_namespace), scene_namespace)
            if source_namespace in scene_namespaces:
                combo.setCurrentIndex(scene_namespaces.index(source_namespace))
            elif scene_namespaces:
                combo.setCurrentIndex(0)

            custom = QtWidgets.QLineEdit(self.tree)
            custom.setObjectName("pasteToCustomNamespace")
            custom.textChanged.connect(lambda _text, source=asset_key: self._refresh_asset_preview(source))
            combo.currentIndexChanged.connect(lambda _idx, source=asset_key: self._refresh_asset_preview(source))

            self.tree.setItemWidget(item, 1, combo)
            self.tree.setItemWidget(item, 2, custom)
            self._asset_rows[asset_key] = {"combo": combo, "custom": custom, "item": item}

        QtCore.QTimer.singleShot(0, self._resize_columns)

    def _resize_columns(self):
        viewport_width = max(0, self.tree.viewport().width())
        if viewport_width <= 0:
            return
        first_width = int(viewport_width * 0.25)
        second_width = int(viewport_width * 0.25)
        self.tree.setColumnWidth(0, first_width)
        self.tree.setColumnWidth(1, second_width)
        self.tree.setColumnWidth(2, max(DPI(120), viewport_width - first_width - second_width))

    def _selected_namespace(self, asset_key):
        widgets = self._asset_rows.get(asset_key)
        if not widgets:
            return _paste_to_asset_display(asset_key)
        custom_text = widgets["custom"].text().strip().strip(":")
        if custom_text:
            return custom_text
        combo = widgets["combo"]
        return combo.currentData() if combo.currentIndex() >= 0 else ""

    def _asset_preview(self, asset_key, target_namespace):
        sources = self._asset_sources.get(asset_key) or []
        resolved = 0
        for source_node in sources:
            if _paste_to_resolve_node(source_node, target_namespace):
                resolved += 1
        return f"{resolved}/{len(sources)} controls" if sources else ""

    def _refresh_asset_preview(self, asset_key):
        widgets = self._asset_rows.get(asset_key)
        if not widgets:
            return
        widgets["item"].setText(1, self._asset_preview(asset_key, self._selected_namespace(asset_key)))

    def mappings(self):
        resolved = []
        missing = []
        items = self.tree.selectedItems() or [self.tree.topLevelItem(index) for index in range(self.tree.topLevelItemCount())]
        for item in items:
            asset_key = item.data(0, QtCore.Qt.UserRole)
            target_namespace = self._selected_namespace(asset_key)
            for source_node in self._asset_sources.get(asset_key, []):
                target_node = _paste_to_resolve_node(source_node, target_namespace)
                if target_node:
                    resolved.append((source_node, target_node))
                else:
                    missing.append(_paste_to_node_with_namespace(_paste_to_node_base_name(source_node), target_namespace))
        return resolved, missing

    def _apply(self, insert=False):
        from maya import cmds

        mappings, _missing = self.mappings()
        if not mappings:
            cmds.warning(f"No matching {self.data_label} targets found")
            return
        if self.apply_callback(mappings, insert=insert):
            self.close()
