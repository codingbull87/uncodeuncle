#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class InjectionResult:
    chart_id: str
    anchor: str
    status: str
    message: str


@dataclass
class PlannedInsertion:
    pos: int
    rec: dict[str, Any]
    fragment: str
    anchor: str
    match_count: int


@dataclass
class LayoutBlock:
    block_id: str
    kind: str
    anchor: str
    layout: str
    size: str
    page_role: str
    keep_with_next: bool
    can_shrink: bool
    max_shrink_ratio: float
    group: str = ""
    row_layout: str = ""
    equal_height: bool = False
