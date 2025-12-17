from typing import Any, Dict, Optional, List
import requests
import logging
import time

_LOGGER = logging.getLogger(__name__)
# Simple in-memory cache keyed by (method,url,params,json) -> response JSON
_SIMPLE_CACHE: Dict[str, Any] = {}


def _cache_key(method: str, url: str, params: Optional[Dict[str, Any]], json_body: Optional[Dict[str, Any]]) -> str:
    return f"{method.upper()} {url} | params:{repr(params)} | json:{repr(json_body)}"


def call_api(session: Optional[requests.Session], method: str, url: str, *, params: Optional[Dict[str, Any]] = None,
             json_body: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
             timeout: int = 10, retries: int = 2, backoff: float = 0.3, use_cache: bool = False) -> Optional[Any]:
    """Call an HTTP API and return parsed JSON or None on failure.

    Adds retry with exponential backoff and a very small simple cache when `use_cache` is True.
    """
    sess = session or requests.Session()
    key = None
    if use_cache:
        key = _cache_key(method, url, params, json_body)
        if key in _SIMPLE_CACHE:
            _LOGGER.debug('http_search cache HIT %s', key)
            return _SIMPLE_CACHE[key]

    attempt = 0
    while attempt <= retries:
        try:
            # Build kwargs only for provided arguments to remain compatible with
            # test doubles that may not accept unexpected keyword args.
            kwargs: Dict[str, Any] = {}
            if params is not None:
                kwargs['params'] = params
            if headers is not None:
                kwargs['headers'] = headers
            if json_body is not None and method.upper() != 'GET':
                kwargs['json'] = json_body
            kwargs['timeout'] = timeout

            _LOGGER.debug('http_search calling %s %s attempt=%d kwargs_keys=%s', method, url, attempt, list(kwargs.keys()))
            if method.upper() == 'GET':
                resp = sess.get(url, **kwargs)
            else:
                resp = sess.post(url, **kwargs)

            if resp is None:
                raise RuntimeError('no response')
            status = getattr(resp, 'status_code', 0)
            if status != 200:
                _LOGGER.warning('http_search non-200 status %s for %s %s', status, method, url)
                raise RuntimeError(f'status {status}')

            j = resp.json()
            if use_cache and key is not None:
                _SIMPLE_CACHE[key] = j
            return j

        except Exception as exc:
            _LOGGER.debug('http_search attempt %d failed for %s %s: %s', attempt, method, url, exc)
            if attempt == retries:
                _LOGGER.error('http_search all attempts failed for %s %s', method, url)
                return None
            # exponential backoff
            sleep_time = backoff * (2 ** attempt)
            time.sleep(sleep_time)
            attempt += 1
            continue


def find_rows(obj: Any) -> List[Dict[str, Any]]:
    """Try common locations for list-of-rows in an API JSON response.

    Common shapes:
    - {"data": {"rows": [...]}}
    - {"result": {"rows": [...]}}
    - {"rows": [...]}
    - {"data": [...]}
    - [...] (top-level list)
    """
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if not isinstance(obj, dict):
        return []

    # Prefer data.rows, result.rows
    for container_key in ('data', 'result'):
        container = obj.get(container_key)
        if isinstance(container, dict):
            rows = container.get('rows')
            if isinstance(rows, list):
                return rows
            if isinstance(container, list):
                return container
        if isinstance(container, list):
            return container

    # Top-level rows
    rows = obj.get('rows')
    if isinstance(rows, list):
        return rows

    # data might itself be a list
    data = obj.get('data')
    if isinstance(data, list):
        return data

    return []
