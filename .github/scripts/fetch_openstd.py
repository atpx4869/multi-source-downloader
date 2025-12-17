import requests
from pathlib import Path

hcno = '6E44399C5BD3EB6034B9159EA7D71334'
url = f'http://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno={hcno}'
print('Fetching', url)
resp = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=15)
print('Status', resp.status_code)
text = resp.text
if resp.status_code==200:
    # look for .pdf links
    import re
    links = re.findall(r'href=["\']([^"\']+\.pdf)["\']', text, flags=re.IGNORECASE)
    print('Found pdf links:', links[:5])
    # look for resource ids or download patterns
    patterns = ['pdf', 'attachment', 'download', 'downloadUrl', 'fileMd5']
    for p in patterns:
        if p in text.lower():
            idx = text.lower().find(p)
            start = max(0, idx-120)
            end = min(len(text), idx+120)
            print('\ncontext for', p)
            print(text[start:end])
