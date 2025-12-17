import requests
import re

BASE = 'https://bz.zhenggui.vip'
FILES = ['/assets/index.0214bd45.js','/assets/index-legacy.35e4c9d8.js','/assets/polyfills-legacy.0d3d6c0f.js']

def main():
    for p in FILES:
        url = BASE + p
        try:
            r = requests.get(url, timeout=10)
            txt = r.text
            print('---', p, 'len', len(txt))
            for kw in ['standardStatus','statusMap','status','现行','废止','即将实施','草案','实施']:
                if kw in txt:
                    print('FOUND', kw)
            # print small snippets around 'standardStatus'
            for m in re.finditer(r"standardStatus[^\w\u4e00-\u9fff]{0,20}", txt):
                i = max(0, m.start()-40)
                print('SNIPPET:', txt[i:m.start()+80].replace('\n',' ')[:200])
        except Exception as e:
            print('ERR', p, e)

if __name__ == '__main__':
    main()
