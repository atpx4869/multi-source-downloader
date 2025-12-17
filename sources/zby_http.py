from typing import Any, Dict, List, Optional
import requests

from .http_search import call_api, find_rows

API_URL_DEFAULT = "https://login.bz.zhenggui.vip/bzy-api/org/std/search"


def search_via_api(keyword: str, page: int = 1, page_size: int = 20, session: Optional[requests.Session] = None, api_url: str = API_URL_DEFAULT) -> List[Dict[str, Any]]:
    """Query ZBY JSON API and return list of rows (dicts).

    Returns empty list on failure.
    """
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://bz.zhenggui.vip", "Origin": "https://bz.zhenggui.vip", "Content-Type": "application/json;charset=UTF-8"}
    body = {
        "params": {
            "pageNo": int(page),
            "pageSize": int(page_size),
            "model": {
                "standardNum": None,
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

    j = call_api(session, 'POST', api_url, json_body=body, headers=headers, timeout=10)
    if j is None:
        return []
    rows = find_rows(j)
    return rows or []
