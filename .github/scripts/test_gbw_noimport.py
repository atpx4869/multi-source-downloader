#!/usr/bin/env python3
from pathlib import Path
import sys
import re

ROOT = Path(__file__).resolve().parents[2]
src_file = ROOT / 'sources' / 'gbw.py'
code = src_file.read_text(encoding='utf-8')

# Remove the problematic import of core.models to avoid circular import during testing
code = re.sub(r"from core\.models import Standard\n", "", code)

# Execute the modified module in an isolated namespace
ns = {}
# Provide a dummy Standard type for annotations to avoid NameError
class _DummyStandard: pass
ns['Standard'] = _DummyStandard
exec(code, ns)

GBWSource = ns.get('GBWSource')
if GBWSource is None:
    print('Failed to load GBWSource')
    sys.exit(1)

class DummyItem:
    def __init__(self, item_id):
        self.std_no = 'TEST'
        self.name = '测试标准'
        self.source_meta = {'id': item_id}
    def display_label(self):
        return f"{self.std_no} {self.name}"
    def filename(self):
        return f"{self.std_no}_{self.name}.pdf"

def log_cb(msg: str):
    print(msg)

def main():
    s = GBWSource()
    print('Testing GBW download with dummy item id...')
    item = DummyItem('dummy-id')
    out_dir = ROOT / 'downloads'
    out_dir.mkdir(exist_ok=True)
    path, logs = s.download(item, out_dir, log_cb=log_cb)
    print('Result path:', path)
    print('Logs:')
    for l in logs:
        print(' -', l)

if __name__ == '__main__':
    main()
