import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi
from TheKeyMachine.tools.attribute_switcher.custom_widgets import AttributeSwitcherWidget


class AttributeSwitcherWindow(AttributeSwitcherWidget):
    def __init__(self, parent=None, popup=False):
        super().__init__(popup=popup, parent=parent)
        self.setObjectName("attribute_switcher_window")
        self.setWindowTitle("Attribute Switcher")

    def closeEvent(self, event):
        attributeSwitcherApi._emit_attribute_switcher_window_state(False)
        super().closeEvent(event)
