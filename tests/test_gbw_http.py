import requests

from sources.gbw import GBWSource


class DummyResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def test_gbw_search_success(monkeypatch):
    sample = {"code": 1, "data": {"rows": [{"C_STD_CODE": "GB/T <sacinfo>123-2018</sacinfo>", "C_C_NAME": "测试名称", "ISSUE_DATE": "2018-01-01", "ACT_DATE": "2019-01-01", "STATE": "现行", "id": "abc", "HCNO": "DEADBEEFDEADBEEFDEADBEEFDEADBEEF"}]}}

    def fake_get(url, params=None, timeout=None, headers=None):
        return DummyResp(200, sample)

    s = GBWSource()
    monkeypatch.setattr(s.session, 'get', fake_get)
    results = s.search('测试', page=1, page_size=10)
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].name == '测试名称'


def test_gbw_search_failure(monkeypatch):
    def fake_get(url, params=None, timeout=None, headers=None):
        return DummyResp(500, {})

    s = GBWSource()
    monkeypatch.setattr(s.session, 'get', fake_get)
    results = s.search('nope')
    assert results == []
