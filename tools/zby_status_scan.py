import requests

URL = "https://login.bz.zhenggui.vip/bzy-api/org/std/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://bz.zhenggui.vip",
    "Referer": "https://bz.zhenggui.vip/",
}

def scan(keyword=''):
    # First request to discover total pages
    body_template = {
      "params":{
        "pageNo":1,
        "pageSize":50,
        "model":{
          "standardNum":None,
          "standardName":None,
          "standardType":None,
          "standardCls":None,
          "keyword":keyword,
          "forceEffective":"0",
          "standardStatus":None,
          "searchType":"1",
          "standardPubTimeType":"0"
        }
      },
      "token":"",
      "userId":"",
      "orgId":"",
      "time":""
    }

    statuses = {}
    page = 1
    page_size = 50
    while True:
        body = body_template.copy()
        body['params'] = body_template['params'].copy()
        body['params']['pageNo'] = page
        body['params']['pageSize'] = page_size
        body['params']['model'] = body_template['params']['model'].copy()
        body['params']['model']['keyword'] = keyword

        r = requests.post(URL, headers=HEADERS, json=body, timeout=15)
        try:
            j = r.json()
        except Exception:
            print('invalid json on page', page)
            break

        data = j.get('data') if isinstance(j, dict) else None
        if not data:
            break
        rows = data.get('rows', [])
        for row in rows:
            st = row.get('standardStatus')
            statuses.setdefault(st, 0)
            statuses[st] += 1

        # paging
        pages = data.get('pages') or data.get('lastPage') or 1
        if page >= pages:
            break
        page += 1

    print('Found statuses:', statuses)

if __name__ == '__main__':
    scan('')
