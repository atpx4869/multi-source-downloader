#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sources.gbw import GBWSource
from core.models import Standard

def log_cb(msg: str):
    print(msg)

def main():
    s = GBWSource()
    print('Searching GBW for keyword "电动机"...')
    items = s.search('电动机', page=1, page_size=5)
    print(f'Found {len(items)} items')
    if not items:
        return
    item = items[0]
    print('Testing download for first item:', item.display_label())
    out_dir = Path('downloads')
    out_dir.mkdir(exist_ok=True)
    path, logs = s.download(item, out_dir, log_cb=log_cb)
    print('Download result path:', path)
    print('Logs:')
    for l in logs:
        print(' -', l)

if __name__ == '__main__':
    main()
