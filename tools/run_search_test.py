import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.enhanced_search import EnhancedSmartSearcher
from core.aggregated_downloader import AggregatedDownloader

def on_result(src, rows):
    print(f"[ON_RESULT] source={src} count={len(rows)}")
    for r in rows:
        print(f"  std_no={r.get('std_no')} sources={r.get('sources')} has_pdf={r.get('has_pdf')}")

if __name__ == '__main__':
    dl = AggregatedDownloader()
    metadata = EnhancedSmartSearcher.search_with_callback('6675.1-', dl, output_dir='downloads', on_result=on_result)
    print('[METADATA]', metadata)
