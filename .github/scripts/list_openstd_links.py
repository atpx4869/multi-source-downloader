import requests, re
url='http://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=6E44399C5BD3EB6034B9159EA7D71334'
text=requests.get(url,headers={'User-Agent':'Mozilla/5.0'}).text
links=re.findall(r'href=["\']([^"\']+)["\']', text)
print('Total links:', len(links))
for l in sorted(set(links)):
    if 'pdf' in l.lower() or 'download' in l.lower() or 'bzgk' in l.lower() or 'doc' in l.lower():
        print(l)
