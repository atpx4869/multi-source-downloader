# -*- coding: utf-8 -*-
import json
from core.aggregated_downloader import AggregatedDownloader

if __name__ == '__main__':
    client = AggregatedDownloader(enable_sources=["ZBY"])
    print('Loaded sources:', [s.name for s in client.sources])
    results = client.search('标准')
    out = []
    for r in results[:10]:
        out.append({'std_no': r.std_no, 'name': r.name, 'has_pdf': r.has_pdf, 'sources': r.sources})
    print(json.dumps(out, ensure_ascii=False, indent=2))
