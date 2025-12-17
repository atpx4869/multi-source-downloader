import requests
from pathlib import Path

item_id = '71F772D80E23D3A7E05397BE0A0AB82A'
detail_url = f'https://std.samr.gov.cn/gb/search/gbDetailed?id={item_id}'
print('Fetching', detail_url)
resp = requests.get(detail_url, headers={'User-Agent':'Mozilla/5.0'}, timeout=15)
text = resp.text
print('Status', resp.status_code)

keys = ['hcno', '.pdf', 'immdoc', '/doc/I/', 'aliyunPreview', 'aliyun', 'download', 'servlet', 'attachment', 'pdf']
for k in keys:
    idx = text.lower().find(k)
    if idx!=-1:
        start = max(0, idx-120)
        end = min(len(text), idx+120)
        print('\n--- context for', k, '---')
        print(text[start:end])
