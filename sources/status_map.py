"""Centralized mapping for numeric status codes returned by some APIs.

NOTE: The mapping below was inferred from observed API responses (HAR: bz.zhenggui.vip.har)
and common conventions. Static frontend bundles did not contain an obvious authoritative
numeric->text mapping object, so these labels are applied as a best-effort, user-friendly
representation. If an authoritative mapping is discovered in site JS or documentation,
prefer that source and update this file accordingly.

Provides a small helper to map backend status codes to human-readable labels.
"""
from typing import Optional

STATUS_MAP = {
    '0': '现行',
    '1': '草案',
    '2': '废止',
    '3': '即将实施',
    '4': '被替代',
}


def map_status(code: Optional[object]) -> str:
    if code is None:
        return ''
    try:
        return STATUS_MAP.get(str(code), str(code))
    except Exception:
        return str(code)
