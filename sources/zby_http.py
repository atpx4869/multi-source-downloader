from typing import Any, Dict, List, Optional
import requests

from .http_search import call_api, find_rows

API_URL_DEFAULT = "https://login.bz.zhenggui.vip/bzy-api/org/std/search"


def search_via_api(keyword: str, page: int = 1, page_size: int = 20, session: Optional[requests.Session] = None, api_url: str = API_URL_DEFAULT, timeout: int = 10) -> List[Dict[str, Any]]:
    """Query ZBY JSON API and return list of rows (dicts).

    Returns empty list on failure.
    """
    print(f"[ZBY HTTP] 调用API，关键词: {keyword}, page: {page}, size: {page_size}")
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://bz.zhenggui.vip", "Origin": "https://bz.zhenggui.vip", "Content-Type": "application/json;charset=UTF-8"}
    body = {
        "params": {
            "pageNo": int(page),
            "pageSize": int(page_size),
            "model": {
                "standardNum": keyword if '-' in keyword or '/' in keyword else None,
                "standardName": None,
                "standardType": None,
                "standardCls": None,
                "keyword": keyword,
                "forceEffective": "0",
                "standardStatus": None,
                "searchType": "1",
                "standardPubTimeType": "0",
            },
        },
        "token": "",
        "userId": "",
        "orgId": "",
        "time": "",
    }

    # 搜索时允许 1 次重试（防止网络抖动导致的间歇性失败）
    j = call_api(session, 'POST', api_url, json_body=body, headers=headers, timeout=timeout, retries=1, verify_ssl=False)
    if j is None:
        print(f"[ZBY HTTP] API返回为空")
        return []
    print(f"[ZBY HTTP] API返回JSON: {str(j)[:200]}...")
    rows = find_rows(j)
    print(f"[ZBY HTTP] 解析到 {len(rows)} 条数据")
    
    # 修正状态逻辑：如果状态为废止(2)但实施日期在未来，则修正为即将实施(3)
    import time
    current_date = time.strftime("%Y-%m-%d")
    for row in rows:
        try:
            status = str(row.get('standardStatus', ''))
            impl_date = str(row.get('standardUsefulDate') or row.get('standardUsefulTime') or row.get('standardUseDate') or row.get('implement') or '')[:10]
            
            # 如果状态是废止(2)且有实施日期且实施日期大于当前日期
            if status == '2' and impl_date and impl_date > current_date:
                row['standardStatus'] = '3'  # 修正为即将实施
        except Exception:
            pass
            
    return rows or []
