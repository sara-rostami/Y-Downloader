import requests, re, tempfile, time, json, sys
from pathlib import Path

def extract_api_config():
    print("="*60)
    print("مرحله ۱: استخراج API از سایت downloaderto.com")
    print("="*60)
    try:
        site_url = "https://downloaderto.com/enHF/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(site_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"❌ دریافت صفحه شکست خورد: {resp.status_code}")
            return None
        html = resp.text

        # ذخیره صفحه برای بررسی (در گیتهاب اکشن قابل دانلود است)
        debug_file = Path("/tmp/downloaderto_main.html")
        debug_file.write_text(html, encoding='utf-8')
        print(f"📄 صفحه اصلی در {debug_file} ذخیره شد")

        api_key = None
        for pat in [r'api["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
                    r'apiKey["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
                    r'["\']([a-f0-9]{32})["\']']:
            matches = re.findall(pat, html, re.IGNORECASE)
            for m in matches:
                if len(m) == 32 and all(c in '0123456789abcdef' for c in m):
                    api_key = m
                    print(f"✅ API Key پیدا شد: {api_key}")
                    break
            if api_key:
                break
        if not api_key:
            print("❌ API Key پیدا نشد")

        api_url = None
        for pat in [r'(https?://[a-z0-9\.-]+/ajax/download\.php)',
                    r'(https?://[a-z0-9\.-]+/api/download\.php)',
                    r'apiUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']']:
            matches = re.findall(pat, html, re.IGNORECASE)
            for m in matches:
                if 'download' in m.lower() and m.startswith('http'):
                    api_url = m
                    print(f"✅ API URL پیدا شد: {api_url}")
                    break
            if api_url:
                break
        if not api_url:
            print("❌ API URL پیدا نشد")

        return dict(api_key=api_key, api_url=api_url)
    except Exception as e:
        print(f"❌ خطای استخراج: {e}")
        return None

def test_api_request(api_key, api_url):
    print("\n" + "="*60)
    print("مرحله ۲: درخواست آزمایشی به API")
    print("="*60)
    if not api_key or not api_url:
        print("⚠️ کلید یا آدرس موجود نیست، نمی‌توان درخواست داد")
        return None

    youtube_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"   # اولین ویدیو
    params = {'copyright':'0', 'format':'360', 'url':youtube_url, 'api':api_key}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
               'Referer': 'https://downloaderto.com/'}
    try:
        r = requests.get(api_url, params=params, headers=headers, timeout=30)
        print(f"Status: {r.status_code}")
        print("Response:", r.text[:500])
        data = r.json()
        print("JSON:", data)
        if data.get('success'):
            download_id = data.get('id')
            print(f"✅ Download ID دریافت شد: {download_id}")
            return download_id
        else:
            print(f"❌ API گفت ناموفق: {data.get('error', 'نامشخص')}")
            return None
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def test_polling(download_id):
    print("\n" + "="*60)
    print("مرحله ۳: آزمایش Polling لینک دانلود")
    print("="*60)
    if not download_id:
        print("⚠️ شناسه دانلود موجود نیست، polling رد می‌شود")
        return

    urls = [
        f"https://p.savenow.to/download/{download_id}",
        f"https://p.savenow.to/api/download/{download_id}",
        f"https://p.lbserver.xyz/download/{download_id}",
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
               'Accept': 'video/mp4,video/*,*/*;q=0.8',
               'Referer': 'https://downloaderto.com/'}
    for attempt in range(1, 15):
        print(f"\n🔄 تلاش {attempt}:")
        for url in urls:
            try:
                resp = requests.head(url, headers=headers, timeout=8, allow_redirects=True)
                size = resp.headers.get('content-length', '0')
                final = resp.url
                print(f"   {url} -> {resp.status_code}, size={size}, final={final}")
                if resp.status_code in [200, 302] and int(size) > 500000:
                    print(f"   ✅ لینک آماده: {final}")
                    return final
            except Exception as e:
                print(f"   {url} -> خطا: {e}")
        time.sleep(2)
    print("❌ لینک بعد از ۱۵ تلاش آماده نشد")

if __name__ == "__main__":
    config = extract_api_config()
    if config:
        download_id = test_api_request(config['api_key'], config['api_url'])
        if download_id:
            final_link = test_polling(download_id)
            if final_link:
                print(f"\n🎉 لینک نهایی: {final_link}")
            else:
                print("\n⚠️ به لینک دانلود نرسیدیم، اما polling انجام شد")
        else:
            print("\n❌ در مرحله درخواست API شکست خوردیم")
    else:
        print("\n❌ در مرحله استخراج API شکست خوردیم")
    
    # چاپ خلاصه برای لاگ گیتهاب
    print("\n🏁 پایان تست")
