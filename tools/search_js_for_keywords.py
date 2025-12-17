#!/usr/bin/env python3
import re
import requests
from urllib.parse import urljoin

BASE = "https://bz.zhenggui.vip"
KEYWORDS = ["现行", "草案", "废止", "即将实施", "被替代", "实施", "替代", "废止/终止", "已实施"]

def fetch(url):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.text

def find_assets(html):
    # find /assets/*.js occurrences
    return list({m.group(0) for m in re.finditer(r"/assets/[\w\-\.]+\.js", html)})

def snippet(s, idx, pad=60):
    start = max(0, idx - pad)
    end = min(len(s), idx + pad)
    return s[start:end].replace('\n','\\n')

def main():
    print("Fetching standardList page...")
    html = fetch(urljoin(BASE, "/standardList"))
    assets = find_assets(html)
    if not assets:
        print("No /assets/*.js URLs found on page.")
        return
    for a in assets:
        url = urljoin(BASE, a)
        try:
            print(f"=== Asset {a} ===")
            data = requests.get(url, timeout=30).text
            print(f"length={len(data)}")
            found = False
            for kw in KEYWORDS:
                for m in re.finditer(re.escape(kw), data):
                    found = True
                    idx = m.start()
                    print(f"-- match '{kw}' at {idx}: ...{snippet(data, idx)}...")
            if not found:
                print("(no keyword matches)")
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")

if __name__ == '__main__':
    main()
