import requests
import re

def main():
    u = 'https://bz.zhenggui.vip/standardList'
    r = requests.get(u, timeout=10)
    t = r.text
    print('len', len(t))
    for kw in ['status','standardStatus','现行','废止','即将实施','状态','标准状态']:
        if kw in t:
            print('FOUND', kw)
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', t)
    print('scripts', len(scripts))
    for s in scripts[:20]:
        print(' -', s)

if __name__ == '__main__':
    main()
