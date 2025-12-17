import time
import requests

from sources.http_search import call_api, _SIMPLE_CACHE


class DummyResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, seq):
        # seq: list of (status, payload) responses to return on consecutive calls
        self.seq = list(seq)

    def post(self, url, **kwargs):
        if not self.seq:
            return DummyResp(500, {})
        status, payload = self.seq.pop(0)
        return DummyResp(status, payload)

    def get(self, url, **kwargs):
        return self.post(url, **kwargs)


def test_call_api_retries(monkeypatch):
    # first two attempts fail (500), third succeeds
    seq = [(500, {}), (500, {}), (200, {'ok': True})]
    s = FakeSession(seq)
    start = time.time()
    res = call_api(s, 'POST', 'https://example.invalid', json_body={'a':1}, timeout=1, retries=2, backoff=0.01)
    assert res == {'ok': True}


def test_call_api_cache():
    # clear cache
    _SIMPLE_CACHE.clear()
    seq = [(200, {'x': 1})]
    s = FakeSession(seq)
    res1 = call_api(s, 'GET', 'https://example.invalid/path', params={'q':'a'}, use_cache=True)
    assert res1 == {'x': 1}
    # second call with same args should hit cache and not consume session responses
    res2 = call_api(s, 'GET', 'https://example.invalid/path', params={'q':'a'}, use_cache=True)
    assert res2 == {'x': 1}