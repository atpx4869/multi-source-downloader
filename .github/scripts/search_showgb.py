import requests,re
url='https://std.samr.gov.cn/gb/search/gbDetailed?id=71F772D80E23D3A7E05397BE0A0AB82A'
text=requests.get(url,headers={'User-Agent':'Mozilla/5.0'}).text
matches=re.findall(r'showGb\(([^\)]+)\)',text)
print('showGb matches:',matches)
for m in matches:
    print(m)
