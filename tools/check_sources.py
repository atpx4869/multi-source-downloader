# -*- coding: utf-8 -*-
import json
from core.aggregated_downloader import AggregatedDownloader

if __name__ == '__main__':
    client = AggregatedDownloader(enable_sources=["GBW","BY","ZBY"])
    health = client.check_source_health(force=True)
    out = {}
    for k, v in health.items():
        out[k] = {
            'available': bool(v.available),
            'error': v.error,
            'response_time': round(float(v.response_time or 0.0), 3),
            'last_check': v.last_check
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))
