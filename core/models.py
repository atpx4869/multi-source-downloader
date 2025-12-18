# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict
import re


def natural_key(s: str):
    parts = re.split(r"(\d+)", s or "")
    return [int(p) if p.isdigit() else p for p in parts]


def sanitize_filename(name: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|]', "_", name or "")
    safe = safe.strip() or "download"
    return safe


@dataclass
class Standard:
    std_no: str
    name: str
    publish: str = ""
    implement: str = ""
    status: str = ""
    has_pdf: bool = False
    source_meta: Dict = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)

    def display_label(self) -> str:
        return f"{self.std_no or '-'} {self.name or ''}".strip()

    def filename(self) -> str:
        return f"{sanitize_filename(self.display_label())}.pdf"
