# -*- coding: utf-8 -*-
"""入口文件（精简版）。

原先的 UI/线程/业务实现已迁移到 `app/desktop_app_impl.py`。
此文件仅负责作为稳定入口，便于维护与后续继续拆分模块。
"""

from __future__ import annotations

import sys
import io
from pathlib import Path

# 设置 UTF-8 编码以支持 emoji 和其他 Unicode 字符
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def _bootstrap_sys_path():
    project_root = Path(__file__).parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Add ppllocr path for development mode
    ppllocr_path = project_root / "ppllocr" / "ppllocr-main"
    if ppllocr_path.exists() and str(ppllocr_path) not in sys.path:
        sys.path.insert(0, str(ppllocr_path))


def main():
    _bootstrap_sys_path()
    from app.desktop_app_impl import main as _impl_main

    return _impl_main()


if __name__ == "__main__":
    main()