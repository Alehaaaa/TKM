from dataclasses import dataclass, field
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class SliderMode:
    """Declarative identity and presentation for one slider calculation mode."""

    key: str
    label: str
    text: str = ""
    shortcut: Tuple[Any, ...] = field(default_factory=tuple)
    icon: Optional[str] = None
    description: str = ""
    tooltip: Any = None
    world_space: bool = False
    frame_buttons: bool = False

    def __post_init__(self):
        if not self.description and isinstance(self.tooltip, (list, tuple)) and self.tooltip:
            first_line = self.tooltip[0]
            if isinstance(first_line, str):
                object.__setattr__(self, "description", first_line)

    def widget_data(self):
        icon = self.resolved_icon()
        return {
            "key": self.key,
            "label": self.label,
            "text": self.text,
            "icon": icon,
            "shortcut": list(self.shortcut),
            "description": self.description,
            "tooltip": self.tooltip,
            "worldSpace": self.world_space,
            "frameButtons": self.frame_buttons,
        }

    def resolved_icon(self):
        if not self.icon:
            return None
        from TheKeyMachine.data import icons

        return icons.get(self.icon) or self.icon

    def display_value(self):
        return self.resolved_icon() or self.text

    @property
    def worldSpace(self):
        return self.world_space

    @property
    def frameButtons(self):
        return self.frame_buttons
