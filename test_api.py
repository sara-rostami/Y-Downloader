import requests, re, tempfile, time, json, sys  # sys اضافه شد
from pathlib import Path

# ====================== ۱. استخراج از صفحه اصلی ======================
def extract_from_main_page():
    print("=" * 60)
    print("مرحله ۱-الف: استخراج از صفحه اصلی downloaderto.com")
    print("=" * 60)
    try:
        site_url = "https://downloaderto.com/enHF/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(site_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"❌ دریافت صفحه اصلی شکست خورد: {resp.status_code}")
            return None, None
        html = resp.text

        # ذخیره HTML برای بررسی
        debug_file = Path("/tmp/downloaderto_main.html")
        debug_file.write_text(html, encoding='utf-8')
        print(f"📄 صفحه اصلی در {debug_file} ذخیره شد")

        # جستجوی API Key
        api_key = None
        patterns_key = [
            r'api["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'apiKey["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'key["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'["\']([a-f0-9]{32})["\']',  # عمومی
        ]
        for pat in patterns_key:
            matches = re.findall(pat, html, re.IGNORECASE)
            for m in matches:
                if len(m) == 32 and all(c in '0123456789abcdef' for c in m):
                    api_key = m
                    print(f"✅ API Key پیدا شد: {api_key}")
                    break
            if api_key:
                break
        if not api_key:
            print("❌ API Key در HTML اصلی پیدا نشد")
            # چاپ چند اسکریپت که ممکن است کلید را پنهان کرده باشند
            scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
            interesting_scripts = []
            for s in scripts:
                if 'api' in s.lower() or 'key' in s.lower() or len(s) > 200:
                    interesting_scripts.append(s[:300])
            if interesting_scripts:
                print("\n🔎 بخش‌هایی از اسکریپت‌های مرتبط:")
                for i, sc in enumerate(interesting_scripts[:3]):
                    print(f"--- اسکریپت {i+1} ---")
                    print(sc)
                    print("-------------------")

        # جستجوی API URL
        api_url = None
        patterns_url = [
            r'(https?://[a-z0-9\.-]+/ajax/download\.php)',
            r'(https?://[a-z0-9\.-]+/api/download\.php)',
            r'apiUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        ]
        for pat in patterns_url:
            matches = re.findall(pat, html, re.IGNORECASE)
            for m in matches:
                if 'download' in m.lower() and m.startswith('http'):
                    api_url = m
                    print(f"✅ API URL پیدا شد: {api_url}")
                    break
            if api_url:
                break
        if not api_url:
            print("❌ API URL در HTML اصلی پیدا نشد")

        return api_key, api_url
    except Exception as e:
        print(f"❌ خطا: {e}")
        return None, None

# ====================== ۲. تلاش برای دریافت کلید از endpoint‌های اختصاصی ======================
def try_get_api_key_from_endpoints():
    print("\n" + "=" * 60)
    print("مرحله ۱-ب: جستجوی کلید در endpoint‌های احتمالی")
    print("=" * 60)
    candidates = [
        "https://downloaderto.com/api/key",
        "https://downloaderto.com/ajax/key.php",
        "https://p.savenow.to/api/key",
        "https://p.savenow.to/ajax/key.php",
        "https://downloaderto.com/enHF/api/key",
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for url in candidates:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                content_type = r.headers.get('content-type', '')
                print(f"🔍 بررسی {url} -> status={r.status_code}, content-type={content_type}")
                if 'json' in content_type:
                    data = r.json()
                    print(f"   📦 پاسخ جیسون: {json.dumps(data)[:200]}")
                    for key_name in ['api_key', 'key', 'apikey', 'token']:
                        if key_name in data:
                            print(f"   ✅ کلید با نام '{key_name}' پیدا شد: {data[key_name]}")
                            return data[key_name]
                else:
                    text = r.text
                    print(f"   📄 پاسخ متنی (200 کاراکتر اول): {text[:200]}")
                    m = re.search(r'["\']?([a-f0-9]{32})["\']?', text)
                    if m and len(m.group(1)) == 32:
                        key = m.group(1)
                        print(f"   ✅ کلید ۳۲ کاراکتری هگز پیدا شد: {key}")
                        return key
            else:
                print(f"   {url} -> status {r.status_code}")
        except Exception as e:
            print(f"   ❌ خطا در {url}: {e}")
    print("❌ هیچ کلیدی از endpoint‌ها دریافت نشد")
    return None

# ====================== ۳. درخواست به API دانلود ======================
def test_api_request(api_key, api_url):
    print("\n" + "=" * 60)
    print("مرحله ۲: درخواست آزمایشی به API")
    print("=" * 60)
    if not api_key or not api_url:
        print("⚠️ کلید یا آدرس موجود نیست، نمی‌توان درخواست داد")
        return None

    youtube_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # ویدیو تست
    params = {
        'copyright': '0',
        'format': '360',
        'url': youtube_url,
        'api': api_key
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': 'https://downloaderto.com/'
    }
    try:
        r = requests.get(api_url, params=params, headers=headers, timeout=30)
        print(f"Status: {r.status_code}")
        print("Response text:", r.text[:500])
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

# ====================== ۴. Polling لینک نهایی ======================
def test_polling(download_id):
    print("\n" + "=" * 60)
    print("مرحله ۳: آزمایش Polling لینک دانلود")
    print("=" * 60)
    if not download_id:
        print("⚠️ شناسه دانلود موجود نیست")
        return

    urls = [
        f"https://p.savenow.to/download/{download_id}",
        f"https://p.savenow.to/api/download/{download_id}",
        f"https://p.lbserver.xyz/download/{download_id}",
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'video/mp4,video/*,*/*;q=0.8',
        'Referer': 'https://downloaderto.com/'
    }
    for attempt in range(1, 15):
        print(f"\n🔄 تلاش {attempt}:")
        for url in urls:
            try:
                resp = requests.head(url, headers=headers, timeout=8, allow_redirects=True)
                size = resp.headers.get('content-length', '0')
                final_url = resp.url
                print(f"   {url} -> {resp.status_code}, size={size}, final={final_url}")
                if resp.status_code in [200, 302] and int(size) > 500000:
                    print(f"   ✅ لینک آماده: {final_url}")
                    return final_url
            except Exception as e:
                print(f"   {url} -> خطا: {e}")
        time.sleep(2)
    print("❌ لینک بعد از ۱۵ تلاش آماده نشد")

# ====================== اجرای اصلی ======================
if __name__ == "__main__":
    # مرحله ۱: استخراج از صفحه اصلی
    api_key, api_url = extract_from_main_page()

    # اگر کلید پیدا نشد، endpoint‌ها را بگرد
    if not api_key:
        api_key = try_get_api_key_from_endpoints()

    # اگر همچنان کلید نیست، پیام نهایی و خروج
    if not api_key:
        print("\n⚠️ کلید API پیدا نشد. ادامه ممکن نیست. فایل HTML ذخیره شده را از Artifacts دانلود کنید و بررسی دستی نمایید.")
        sys.exit(1)

    # اگر api_url نیست، از آدرس پیدا شده قبلی استفاده کن
    if not api_url:
        api_url = "https://p.savenow.to/ajax/download.php"
        print(f"⚠️ از API URL پیش‌فرض استفاده می‌شود: {api_url}")

    # مرحله ۲: درخواست به API
    download_id = test_api_request(api_key, api_url)

    # مرحله ۳: polling
    if download_id:
        final_link = test_polling(download_id)
        if final_link:
            print(f"\n🎉 لینک نهایی: {final_link}")
        else:
            print("\n⚠️ Polling انجام شد اما لینکی پیدا نشد")
    else:
        print("\n❌ در مرحله API شکست خوردیم")

    print("\n🏁 پایان تست")
