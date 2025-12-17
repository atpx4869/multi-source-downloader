#!/usr/bin/env python3
import re
import requests
from urllib.parse import urljoin

BASE = "https://bz.zhenggui.vip"

CHINESE_KEYWORDS = ["现行", "草案", "废止", "即将实施", "被替代", "实施", "替代", "已实施"]
EN_KEYWORDS = ["status", "standardStatus", "STATE", "draft", "implemented", "obsolete", "replaced", "superseded", "effective"]

PATTERNS = [
    # numeric key mapping like '0': '现行' or 0: '现行'
    re.compile(r"([\"']?)(0|1|2|3|4)\1\s*[:=]\s*[\"']([^\"']{1,80})[\"']"),
    # object literal containing numeric->string pairs
    re.compile(r"\{[^}]{0,600}(?:[\"']?(?:0|1|2|3|4)[\"']?\s*:\s*[\"'][^\"']{1,80}[\"']).{0,600}\}", re.S),
    # array containing Chinese status words
    re.compile(r"\[[^\]]{0,600}(?:"+"|".join(CHINESE_KEYWORDS)+r")[^\]]{0,600}\]", re.S),
    # switch case patterns mapping numbers to strings
    re.compile(r"switch\s*\([^)]*\)\s*\{[^}]{0,1200}case\s*(?:0|1|2|3|4)[:\s][^}]{0,300}\}", re.S),
]

def fetch(url):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.text

def find_assets(html):
    return list({m.group(0) for m in re.finditer(r"/assets/[\w\-\.]+\.js", html)})

def snippet(s, idx, pad=80):
    start = max(0, idx - pad)
    end = min(len(s), idx + pad)
    return s[start:end].replace('\n','\\n')

def search_in_asset(url, data):
    hits = []
    # keyword search
    for kw in CHINESE_KEYWORDS + EN_KEYWORDS:
        for m in re.finditer(re.escape(kw), data, re.I):
            hits.append((f"KW:{kw}", m.start(), snippet(data, m.start())))

    # pattern searches
    for pat in PATTERNS:
        for m in pat.finditer(data):
            start = m.start()
            txt = m.group(0)
            hits.append((f"PAT:{pat.pattern[:40]}", start, txt.replace('\n','\\n')[:800]))

    # some heuristics: look for 'standardStatus' nearby strings
    for m in re.finditer(r"standardStatus|standard_status|standard-status|hasPdf", data, re.I):
        hits.append(("FIELD:standardStatus", m.start(), snippet(data, m.start())))

    # deduplicate by (tag, start)
    seen = set()
    uniq = []
    for t, pos, txt in hits:
        key = (t, pos)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((t, pos, txt))
    return uniq

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
            results = search_in_asset(url, data)
            if not results:
                print("(no broad-pattern matches)")
            else:
                for tag, pos, txt in results:
                    print(f"-- {tag} at {pos}: {txt}")
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")

if __name__ == '__main__':
    main()
