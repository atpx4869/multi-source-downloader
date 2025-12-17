import requests
from sources.zby_http import search_via_api


class DummyResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def fake_post(url, headers=None, json=None, timeout=None):
    return DummyResp(200, {"code": 1, "data": {"rows": [{"standardNum": "GB/T 123", "standardName": "测试", "hasPdf": 1}]}})


def main():
    sess = requests.Session()
    sess.post = fake_post
    # sanity-check fake_post behavior
    print('FAKE_POST DIRECT JSON:', fake_post('u').json())
    print('SESS.POST IS FAKE?', sess.post is fake_post)
    # call lower-level call_api / find_rows via zby wrapper
    from sources.http_search import call_api, find_rows
    j = call_api(sess, 'POST', 'https://example.invalid', json_body={})
    print('LOW-LEVEL CALL_API RESULT:', j)
    rows = search_via_api('测试', page=1, page_size=10, session=sess)
    print('DEBUG ROWS:', rows)


if __name__ == '__main__':
    main()
