from typing import Any, Dict, Optional, List
import requests
import logging
import time
import json
import urllib3

# 抑制 urllib3 的 SSL 验证警告（我们故意禁用 SSL 验证以兼容国内网站）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_LOGGER = logging.getLogger(__name__)
# Simple in-memory cache keyed by (method,url,params,json) -> response JSON
_SIMPLE_CACHE: Dict[str, Any] = {}


def _cache_key(method: str, url: str, params: Optional[Dict[str, Any]], json_body: Optional[Dict[str, Any]]) -> str:
    try:
        p_str = json.dumps(params, sort_keys=True) if params else "None"
        j_str = json.dumps(json_body, sort_keys=True) if json_body else "None"
    except (TypeError, ValueError):
        # Fallback to repr if not JSON serializable
        p_str = repr(params)
        j_str = repr(json_body)
    return f"{method.upper()} {url} | params:{p_str} | json:{j_str}"


def call_api(session: Optional[requests.Session], method: str, url: str, *, params: Optional[Dict[str, Any]] = None,
             json_body: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
             timeout: int = 10, retries: int = 2, backoff: float = 0.3, use_cache: bool = False, verify_ssl: bool = False) -> Optional[Any]:
    """Call an HTTP API and return parsed JSON or None on failure.

    Adds retry with exponential backoff and a very small simple cache when `use_cache` is True.
    """
    sess = session or requests.Session()
    # 默认禁用系统代理：避免用户机器上配置的代理/抓包环境干扰请求。
    # 注意：这里不通过 request(..., proxies=...) 传参，以兼容 tests 中 monkeypatch 的简化签名。
    sess.trust_env = False
    try:
        sess.proxies = {"http": None, "https": None}
    except Exception:
        pass
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
            kwargs['verify'] = verify_ssl  # 添加 SSL 验证控制参数（国内站点可能需要禁用）

            _LOGGER.debug('http_search calling %s %s attempt=%d kwargs_keys=%s', method, url, attempt, list(kwargs.keys()))
            # 禁用系统代理：优先使用 Session.trust_env=False。
            # 某些测试会 monkeypatch session.get/post 为简化签名的假函数，
            # 若强行传 proxies= 会导致 TypeError，因此这里采用“可选回退”。
            if method.upper() == 'GET':
                try:
                    resp = sess.get(url, **kwargs)
                except TypeError:
                    # Some test doubles don't accept unexpected kwargs.
                    retry_kwargs = {}
                    if params is not None:
                        retry_kwargs['params'] = params
                    if headers is not None:
                        retry_kwargs['headers'] = headers
                    retry_kwargs['timeout'] = timeout
                    resp = sess.get(url, **retry_kwargs)
            else:
                try:
                    resp = sess.post(url, **kwargs)
                except TypeError:
                    retry_kwargs = {}
                    if headers is not None:
                        retry_kwargs['headers'] = headers
                    if json_body is not None:
                        retry_kwargs['json'] = json_body
                    retry_kwargs['timeout'] = timeout
                    resp = sess.post(url, **retry_kwargs)

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
