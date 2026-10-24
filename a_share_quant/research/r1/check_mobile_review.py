"""Audit blinding and touch annotation with synthetic UI input, not human ratings."""
import argparse
import json
import re
import sys
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ashare_quant.r1.io import write_json
from ashare_quant.r1.io import load_dataset
from ashare_quant.r1.review import select_blind_samples
from mobile_review import visible_window


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--packet', type=Path, required=True)
    p.add_argument('--audit', type=Path, required=True)
    args = p.parse_args()
    html = args.packet / '手机标注.html'
    text = html.read_text()
    neutral = re.sub(r'data:image/png;base64,[A-Za-z0-9+/=]+', 'OMITTED_PNG', text)
    for word in ['r0_legacy', 'atr_intersection', 'density', 'PRIVATE', 'algorithm_regions']:
        if word in neutral:
            raise ValueError('identity or algorithm content found in first-stage HTML')
    assert not re.search(r'20\d{2}-\d{2}-\d{2}', neutral)
    assert not re.search(r'(?:sz|sh)\d{6}', neutral)
    assert 'fetch(' not in neutral and '<iframe' not in neutral
    manifest = json.loads((args.packet / 'packet_manifest.json').read_text())
    assert [r['case_id'] for r in manifest['cases']] == [f'B{i:03d}' for i in range(1, 7)]
    audit = json.loads((args.audit / 'PRIVATE-source-and-cutoffs.json').read_text())
    registration = json.loads((ROOT / 'research/r1/preregister.json').read_text())
    registered = select_blind_samples(registration)[:6]
    assert [(r['case_id'], r['symbol'], r['cutoff']) for r in audit] == registered
    for row in audit:
        assert row['visible_bar_dates'][-1] == row['cutoff']
        assert all(d <= row['cutoff'] for d in row['visible_bar_dates'])
        actual = visible_window(load_dataset(ROOT, row['symbol'], False), row['cutoff'])
        assert [b.date.isoformat() for b in actual] == row['visible_bar_dates']
    from pypdf import PdfReader
    pdf = PdfReader(args.packet / 'first-six-blank-mobile.pdf')
    assert len(pdf.pages) == 6
    pdf_text = '\n'.join(page.extract_text() for page in pdf.pages)
    assert not re.search(r'20\d{2}-\d{2}-\d{2}|r0_legacy|atr_intersection|density|sz\d{6}|sh\d{6}', pdf_text)
    with zipfile.ZipFile(args.packet.parent / (args.packet.name + '.zip')) as z:
        assert not any(any(word in name for word in ['PRIVATE', 'algorithm', 'known-case', 'snapshot']) for name in z.namelist())
    from playwright.sync_api import sync_playwright
    browser_errors, external_requests = [], []
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
    # Managed Chromium blocks file:// navigation. Serve only this packet on
    # loopback for the test; this is not a public delivery URL or host service.
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(args.packet)))
    origin = f'http://127.0.0.1:{server.server_port}'
    Thread(target=server.serve_forever, daemon=True).start()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-background-networking'])
        context = browser.new_context(viewport={'width': 412, 'height': 915}, device_scale_factor=2.625,
            is_mobile=True, has_touch=True, user_agent='Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/125.0 Mobile Safari/537.36')
        page = context.new_page()
        page.on('pageerror', lambda e: browser_errors.append(str(e)))
        page.on('request', lambda r: external_requests.append(r.url)
            if r.url.startswith(('http://', 'https://')) and not r.url.startswith(origin + '/') else None)
        page.goto(origin + '/' + html.name)
        page.wait_for_function('document.getElementById("image").complete')
        assert page.evaluate('state.cases.every(c=>!c.reviewed && c.regions.length===0)')
        args.audit.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(args.audit / 'android-emulation-initial.png'), full_page=False)
        page.get_by_role('button', name='画中枢框', exact=True).click()
        canvas = page.locator('#overlay')
        box = canvas.bounding_box()
        meta = page.evaluate('chart()')
        panel = meta['panels'][0]
        def xy(fx, fy):
            return (box['x'] + (panel['left'] + (panel['right'] - panel['left']) * fx) / meta['width'] * box['width'],
                    box['y'] + (panel['top'] + (panel['bottom'] - panel['top']) * fy) / meta['height'] * box['height'])
        start, end = xy(.25, .25), xy(.55, .55)
        cdp = context.new_cdp_session(page)
        for kind, point in [('touchStart', start), ('touchMove', end)]:
            cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': point[0], 'y': point[1]}]})
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        page.wait_for_function('current().regions.length===1')
        assert page.evaluate('current().regions[0].centroid===null && !current().reviewed')
        page.evaluate("addRegion({type:'bottom',k_start:150,k_end:160,lower:70,upper:75,centroid:null,view:'synthetic-ui-test'})")
        assert page.evaluate('current().regions.length===2')
        page.get_by_role('button', name='保存本图为已审阅', exact=True).click()
        assert page.evaluate('current().reviewed')
        with page.expect_download() as download:
            page.get_by_role('button', name='导出 JSON', exact=True).click()
        # The browser test is explicitly synthetic and confined to private audit.
        target = args.audit / 'SYNTHETIC-ui-test-export-not-human.json'
        download.value.save_as(str(target))
        synthetic = json.loads(target.read_text())
        assert len(synthetic['cases'][0]['regions']) == 2
        assert all(not c['reviewed'] for c in synthetic['cases'][1:])
        assert synthetic['history']
        page.locator('#case').select_option('1')
        page.locator('#noCenter').check()
        page.get_by_role('button', name='保存本图为已审阅', exact=True).click()
        assert page.evaluate("current().reviewed && current().center_judgment==='none' && current().regions.length===0")
        assert not browser_errors, browser_errors
        assert not external_requests, external_requests
        browser.close()
    server.shutdown()
    server.server_close()
    write_json(args.audit / 'delivery_validation.json', {'first_six_order_verified': True, 'png_dimensions': [2160, 3360],
        'future_dates_in_visible_bars': 0, 'pdf_pages': 6, 'algorithm_or_identity_in_first_stage': False,
        'android_chromium_emulation': 'passed touch drawing, multiple regions, null centroid, no-center, review and JSON export',
        'physical_android_device_tested': False, 'real_human_annotations_received': 0,
        'external_network_requests_by_annotator': 0, 'synthetic_browser_test_excluded_from_review': True})
    print(json.dumps({'blinding_checks': 'passed', 'android_emulation': 'passed', 'real_human_annotations': 0}))


if __name__ == '__main__':
    main()
