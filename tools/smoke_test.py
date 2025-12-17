import sys
from pathlib import Path
import tempfile

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.aggregated_downloader import AggregatedDownloader
from core.models import Standard


def make_fake_standard():
    s = Standard(std_no='GB/T 000-2025', name='测试标准 SmokeTest', publish='2025-01-01')
    s.has_pdf = True
    s.sources = ['ZBY']
    s.source_meta = {'ZBY': {'fake': True}}
    return s


def main():
    # Monkeypatch ZBYSource in-place to avoid network calls
    try:
        import sources.zby as zby_mod

        def fake_search(self, keyword, **kwargs):
            return [make_fake_standard()]

        def fake_download(self, item, outdir):
            outdir = Path(outdir)
            outdir.mkdir(parents=True, exist_ok=True)
            f = outdir / item.filename()
            f.write_bytes(b'%PDF-1.4\n%mock pdf\n')
            return f

        zby_mod.ZBYSource.search = fake_search
        zby_mod.ZBYSource.download = fake_download
    except Exception as e:
        print('failed to patch ZBYSource:', e)

    print('Instantiating AggregatedDownloader with ZBY only')
    ad = AggregatedDownloader(output_dir='downloads_smoke', enable_sources=['ZBY'])
    print('Searching for "测试"')
    results = ad.search('测试')
    print('Search returned', len(results), 'items')
    if results:
        item = results[0]
        print('Attempting download for', item.std_no)
        path, logs = ad.download(item)
        print('Download result path:', path)
        print('Logs:')
        for l in logs:
            print('  ', l)


if __name__ == '__main__':
    main()
