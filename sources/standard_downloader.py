# -*- coding: utf-8 -*-
"""
A lightweight shim named `StandardDownloader` so projects that expect
an external `standard_downloader` package can work out-of-the-box.

This shim delegates to the local `zby_playwright.ZBYSource` when available.
It is intentionally small and self-contained so the packaged exe will
have a usable ZBY implementation without extra external packages.
"""
from pathlib import Path
from typing import Any, List, Union, Optional

try:
    from core.models import Standard
except Exception:  # pragma: no cover - runtime import may fail in some contexts
    Standard = None  # type: ignore


class StandardDownloader:
    """Minimal compatibility shim implementing the expected interface.

    Methods:
    - is_available() -> bool
    - search(keyword, **kwargs) -> List[Standard]
    - download_standard(meta) -> Path | None
    """

    def __init__(self, output_dir: Union[Path, str] = "downloads"):
        self.output_dir = Path(output_dir)
        self._impl = None

    def is_available(self, timeout: int = 6) -> bool:
        if self._impl and hasattr(self._impl, 'is_available'):
            try:
                return bool(self._impl.is_available(timeout=timeout))
            except Exception:
                return False
        return False

    def search(self, keyword: str, **kwargs) -> List[Any]:
        """Return a list of `Standard` objects (or empty list)."""
        # Lazy-import playwright-backed implementation only when needed
        if self._impl is None:
            try:
                from .zby_playwright import ZBYSource
                self._impl = ZBYSource(self.output_dir)
            except Exception:
                self._impl = None

        if self._impl and hasattr(self._impl, 'search'):
            try:
                return self._impl.search(keyword, **kwargs)
            except Exception:
                return []
        return []

    def download_standard(self, meta: Any) -> Optional[Path]:
        """Download given meta (Standard or dict) and return Path or None."""
        if self._impl is None:
            try:
                from .zby_playwright import ZBYSource
                self._impl = ZBYSource(self.output_dir)
            except Exception:
                self._impl = None

        if not self._impl:
            return None
        try:
            item = None
            if Standard is not None and isinstance(meta, Standard):
                item = meta
            elif isinstance(meta, dict):
                # Try to construct a minimal Standard if available
                if Standard is not None:
                    # compute mapped status before constructing Standard
                    try:
                        from .status_map import map_status
                        mapped_status = map_status(meta.get('standardStatus') if 'standardStatus' in meta else meta.get('status'))
                    except Exception:
                        mapped_status = str(meta.get('standardStatus') or meta.get('status') or '')

                    item = Standard(
                        std_no=(meta.get('standardNum') or meta.get('std_no') or '').strip(),
                        name=(meta.get('standardName') or meta.get('name') or '').strip(),
                        publish_date=(meta.get('standardPubTime') or meta.get('publish') or '')[:10],
                        implement_date=(meta.get('standardUsefulDate') or meta.get('implement') or '')[:10],
                        status=mapped_status,
                        has_pdf=bool(meta.get('hasPdf') or meta.get('has_pdf') or False),
                        source_meta=meta,
                        sources=["ZBY"],
                    )
            if item is None:
                return None
            result = self._impl.download(item, self.output_dir)
            if isinstance(result, tuple):
                path, _logs = result
                return Path(path) if path else None
            return Path(result) if result else None
        except Exception:
            return None
