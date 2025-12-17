import requests, re
url = 'https://std.samr.gov.cn/gb/search/gbDetailed?id=71F772D80E23D3A7E05397BE0A0AB82A'
resp = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=15)
text = resp.text
vals = re.findall(r'data-value=["\']([^"\']+)["\']', text)
print('data-value count:', len(vals))
for v in set(vals):
    print(' -', v[:120])

# also extract clickable texts which may be used as KPI
texts = re.findall(r'>([^<>]{3,80})<', text)
cand = [t.strip() for t in texts if ' ' not in t and len(t.strip())>3]
print('\nCandidate KPI-like texts (sample 20):')
print('\n'.join(cand[:20]))
