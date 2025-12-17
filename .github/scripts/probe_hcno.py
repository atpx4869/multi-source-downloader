import requests
from pathlib import Path

hcno = '6E44399C5BD3EB6034B9159EA7D71334'
base = 'https://std.samr.gov.cn'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}
candidates = [
    f"{base}/servlet/Download?HCNO={hcno}",
    f"{base}/hcno/download?hcno={hcno}",
    f"{base}/attachment/download?hcno={hcno}",
    f"{base}/download?hcno={hcno}",
    f"{base}/gb/search/gcDown?hcno={hcno}",
]

out_dir = Path('downloads')
out_dir.mkdir(exist_ok=True)

for url in candidates:
    try:
        print('Trying', url)
        r = requests.get(url, headers=headers, timeout=15)
        print('Status', r.status_code, 'Content-Type:', r.headers.get('content-type'))
        if r.status_code == 200:
            data = r.content
            if data[:4] == b'%PDF' or 'application/pdf' in (r.headers.get('content-type') or '').lower():
                out_path = out_dir / f'GBW_{hcno}.pdf'
                with open(out_path, 'wb') as f:
                    f.write(data)
                print('Saved PDF to', out_path)
                break
            else:
                print('Not PDF, length', len(data))
    except Exception as e:
        print('Error', e)
