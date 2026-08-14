"""Drag-start value snapshots used only by Slider Tween modes."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TweenFrameData:
    needsCalculation: bool
    use_direct_attribute: bool = False
    previousValue: Optional[float] = None
    nextValue: Optional[float] = None
    currentValue: Optional[float] = None
    prev_f: Optional[float] = None
    next_f: Optional[float] = None
    curve: Optional[str] = None
    keyIndex: Optional[int] = None


@dataclass
class BlendFrameData:
    original_value: Optional[float] = None
    use_direct_attribute: bool = False
    previousValue: Optional[float] = None
    nextValue: Optional[float] = None
    prevTanType: Optional[str] = None
    prev_f: Optional[float] = None
    next_f: Optional[float] = None
    defaultValue: Optional[float] = None
    leftValue: Optional[float] = None
    rightValue: Optional[float] = None
    leftFrame: Optional[float] = None
    rightFrame: Optional[float] = None
    bufferValue: Optional[float] = None
    curve: Optional[str] = None
    keyIndex: Optional[int] = None
