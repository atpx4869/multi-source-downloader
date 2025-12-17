from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sources.gbw import GBWSource

def main():
    s = GBWSource()
    items = s.search('电动机', page=1, page_size=5)
    if not items:
        print('no items')
        return
    item = items[0]
    meta = item.source_meta
    # meta stored as { 'GBW': {...} } in AggregatedDownloader context, but here item.source_meta likely original dict
    print('item id (meta):', meta)
    # Try _get_hcno
    hcno = s._get_hcno(meta.get('id') if isinstance(meta, dict) else '')
    print('hcno:', hcno)

if __name__ == '__main__':
    main()
