"""Download ZBY JS assets and search for status mappings/snippets.

Prints all matched snippets around likely keywords so we can infer mapping.
"""
import requests
import re

BASE = 'https://bz.zhenggui.vip'
ASSETS = [
    '/assets/index.0214bd45.js',
    '/assets/index-legacy.35e4c9d8.js',
    '/assets/polyfills-legacy.0d3d6c0f.js',
]

KEYWORDS = [
    'status', 'STATUS_MAP', 'statusMap', 'statusList', 'standardStatus', 'statusCodes',
    'stateMap', '状态', '现行', '废止', '即将实施', '草案', '被替代', '已发布', '实施'
]

# additional regex patterns to find numeric->label mappings or arrays
PATTERNS = [
    re.compile(r"['\"]?\d+['\"]?\s*[:=]\s*['\"][^'\"]{1,20}['\"]"),
    re.compile(r"\[[^\]]{0,200}\]")  # arrays
]


def snippet(text, i, width=120):
    s = max(0, i - width//2)
    e = min(len(text), i + width//2)
    return text[s:e].replace('\n', ' ')


def search_text(txt):
    found = []
    for kw in KEYWORDS:
        for m in re.finditer(re.escape(kw), txt):
            found.append((m.start(), kw))
    # sort and dedupe nearby
    found_sorted = sorted(found, key=lambda x: x[0])
    groups = []
    last = None
    for pos, kw in found_sorted:
        if last is None or pos - last > 200:
            groups.append(pos)
            last = pos
    for pos in groups:
        print('--- SNIPPET at', pos)
        print(snippet(txt, pos, width=300))
        print()
    # search for numeric->label object entries
    for pat in PATTERNS:
        for m in pat.finditer(txt[:2000000]):
            i = m.start()
            print('--- PATTERN MATCH ---')
            print(snippet(txt, i, width=240))
            print()


def main():
    for p in ASSETS:
        url = BASE + p
        try:
            r = requests.get(url, timeout=15)
            txt = r.text
            print('=== Asset', p, 'len', len(txt))
            search_text(txt)
        except Exception as e:
            print('ERR fetching', p, e)


if __name__ == '__main__':
    main()
