import requests,urllib.parse
hcno='6E44399C5BD3EB6034B9159EA7D71334'
std_no='GB/T 3667.2-2016'
title='交流电动机电容器 第2部分：电动机起动电容器'
base='https://std.samr.gov.cn:8080/publicServiceManager/o/pdfPreview'

for key in [std_no, title, std_no + ' ' + title]:
    k=urllib.parse.quote(key)
    url=f"{base}?fileMd5=&kpi={k}"
    print('Trying',url)
    try:
        r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=15)
        print('Status',r.status_code,'CT',r.headers.get('content-type'))
        if r.status_code==200:
            data=r.content
            if data[:4]==b'%PDF' or 'application/pdf' in (r.headers.get('content-type') or '').lower():
                open('downloads/preview.pdf','wb').write(data)
                print('Saved preview.pdf')
            else:
                print('Body length',len(data))
    except Exception as e:
        print('Error',e)
