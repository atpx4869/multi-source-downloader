from playwright.sync_api import sync_playwright
from pathlib import Path
import re

hcno = '6E44399C5BD3EB6034B9159EA7D71334'
openstd = f'http://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno={hcno}'

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        found = []

        def handle_request(req):
            url = req.url
            if url.lower().endswith('.pdf') or 'download' in url.lower() or 'immdoc' in url.lower():
                print('Captured request:', url)
                found.append(url)

        def handle_response(resp):
            try:
                url = resp.url
                ct = resp.headers.get('content-type','')
                if 'application/pdf' in ct.lower():
                    print('Captured PDF response:', url)
                    body = resp.body()
                    out = Path('downloads') / Path(url.split('/')[-1] or 'gbw.pdf')
                    out.parent.mkdir(exist_ok=True)
                    out.write_bytes(body)
                    found.append(url)
                else:
                    # small heuristic: check start of body
                    body = resp.body()
                    if body[:4]==b'%PDF':
                        print('Captured PDF body:', url)
                        out = Path('downloads') / f'gbw_{len(found)}.pdf'
                        out.parent.mkdir(exist_ok=True)
                        out.write_bytes(body)
                        found.append(url)
            except Exception:
                pass

        page.on('request', handle_request)
        page.on('response', handle_response)
        print('Opening', openstd)
        page.goto(openstd)
        page.wait_for_load_state('networkidle')

        # Try clicking download buttons
        try:
            btns = page.query_selector_all('.xz_btn, .ck_btn, a[onclick]')
            print('Found', len(btns), 'potential buttons')
            for b in btns[:3]:
                try:
                    b.click()
                except Exception as e:
                    pass
        except Exception as e:
            print('Click error', e)

        page.wait_for_timeout(3000)
        browser.close()
        print('Found URLs:', found)

if __name__ == '__main__':
    run()
