#!/usr/bin/env python3
import json
import sys
import os

HAR_PATH = os.path.expanduser(r"c:\Users\jzrm\Downloads\bz.zhenggui.vip.har")

def trunc(s, n=1000):
    if s is None:
        return ''
    s = str(s)
    return s if len(s) <= n else s[:n] + '...(truncated)'

def main():
    if not os.path.exists(HAR_PATH):
        print(f"HAR not found: {HAR_PATH}")
        sys.exit(2)
    with open(HAR_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entries = data.get('log', {}).get('entries', [])
    print(f"Total entries: {len(entries)}")

    matches = []
    for e in entries:
        req = e.get('request', {})
        res = e.get('response', {})
        url = req.get('url','')
        rtype = e.get('_resourceType') or e.get('resourceType') or ''
        if rtype.lower() == 'xhr' or '/bzy-api/' in url or '/org/std/search' in url or 'search' in url:
            match = {
                'url': url,
                'method': req.get('method'),
                'status': res.get('status'),
                'request': None,
                'response': None,
            }
            # request postData
            post = req.get('postData') or {}
            text = post.get('text') if isinstance(post, dict) else None
            match['request'] = trunc(text, 2000)

            # response content
            cont = res.get('content') or {}
            resp_text = cont.get('text') if isinstance(cont, dict) else None
            match['response'] = trunc(resp_text, 4000)

            matches.append(match)

    if not matches:
        print('No XHR / API-like entries matched.')
        return

    for i, m in enumerate(matches, 1):
        print('---')
        print(f"[{i}] {m['method']} {m['url']}  status={m['status']}")
        print('Request body:')
        print(m['request'] or '(empty)')
        print('Response snippet:')
        print(m['response'] or '(empty)')

if __name__ == '__main__':
    main()
