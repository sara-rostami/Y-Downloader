import requests, re, tempfile, time, json, sys
from pathlib import Path

# ====================== ۱. استخراج از صفحه اصلی + فایل‌های JS ======================
def extract_from_main_page():
    print("=" * 60)
    print("مرحله ۱: استخراج API از سایت downloaderto.com")
    print("=" * 60)
    try:
        site_url = "https://downloaderto.com/enHF/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                   'Accept': 'text/html,application/xhtml+xml'}
        resp = requests.get(site_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"❌ دریافت صفحه اصلی شکست خورد: {resp.status_code}")
            return None, None
        html = resp.text

        # ذخیره HTML
        debug_file = Path("/tmp/downloaderto_main.html")
        debug_file.write_text(html, encoding='utf-8')
        print(f"📄 صفحه اصلی ذخیره شد: {debug_file}")

        # جستجوی API Key در خود HTML
        api_key = None
        patterns_key = [
            r'api["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'apiKey["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'key["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'["\']([a-f0-9]{32})["\']',
        ]
        for pat in patterns_key:
            matches = re.findall(pat, html, re.IGNORECASE)
            for m in matches:
                if len(m) == 32 and all(c in '0123456789abcdef' for c in m):
                    api_key = m
                    print(f"✅ API Key در HTML اصلی: {api_key}")
                    break
            if api_key:
                break

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
                    print(f"✅ API URL در HTML اصلی: {api_url}")
                    break
            if api_url:
                break

        # اگر کلید یا URL پیدا نشد، فایل‌های JS خارجی را بررسی کن
        if not api_key or not api_url:
            print("\n🔍 جستجو در فایل‌های JavaScript خارجی...")
            js_files = re.findall(r'<script[^>]*src=["\']([^"\']+\.js[^"\']*)["\']', html)
            # حذف تکراری‌ها و محدود به ۱۰ فایل اول
            js_files = list(dict.fromkeys(js_files))[:10]
            print(f"   {len(js_files)} فایل JS پیدا شد.")

            for js_file in js_files:
                # ساخت URL کامل
                if js_file.startswith('http'):
                    js_url = js_file
                elif js_file.startswith('/'):
                    js_url = f"https://downloaderto.com{js_file}"
                else:
                    js_url = f"https://downloaderto.com/{js_file}"

                try:
                    print(f"   دریافت: {js_url[:80]}...")
                    js_resp = requests.get(js_url, headers=headers, timeout=10)
                    if js_resp.status_code == 200:
                        js_content = js_resp.text

                        # جستجوی کلید در فایل JS
                        if not api_key:
                            for pat in patterns_key:
                                matches = re.findall(pat, js_content, re.IGNORECASE)
                                for m in matches:
                                    if len(m) == 32 and all(c in '0123456789abcdef' for c in m):
                                        api_key = m
                                        print(f"   ✅ API Key در JS پیدا شد: {api_key}")
                                        break
                                if api_key:
                                    break

                        # جستجوی URL در فایل JS
                        if not api_url:
                            for pat in patterns_url:
                                matches = re.findall(pat, js_content, re.IGNORECASE)
                                for m in matches:
                                    if 'download' in m.lower() and m.startswith('http'):
                                        api_url = m
                                        print(f"   ✅ API URL در JS پیدا شد: {api_url}")
                                        break
                                if api_url:
                                    break

                        if api_key and api_url:
                            break
                except Exception as e:
                    print(f"   ⚠️ خطا در دریافت {js_url[:50]}: {e}")

        # خلاصه
        if api_key:
            print(f"\n✅ API Key نهایی: {api_key}")
        else:
            print("\n❌ API Key پیدا نشد")
        if api_url:
            print(f"✅ API URL نهایی: {api_url}")
        else:
            print("❌ API URL پیدا نشد")

        return api_key, api_url

    except Exception as e:
        print(f"❌ خطای کلی: {e}")
        return None, None

# ====================== ۲. درخواست به API دانلود ======================
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

# ====================== ۳. Polling لینک نهایی ======================
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
    # مرحله ۱: استخراج کامل (HTML + JS)
    api_key, api_url = extract_from_main_page()

    # اگر api_url نداریم، از URL پیدا شده قبلی (پیش‌فرض امن) استفاده کن
    if not api_url:
        api_url = "https://p.savenow.to/ajax/download.php"
        print(f"⚠️ از API URL پیش‌فرض استفاده می‌شود: {api_url}")

    # اگر کلید پیدا نشد، نمی‌توان ادامه داد
    if not api_key:
        print("\n⚠️ کلید API پیدا نشد. ادامه ممکن نیست.")
        print("لطفاً فایل HTML ذخیره شده را از Artifacts دانلود کنید و بررسی دستی نمایید.")
        sys.exit(1)

    # مرحله ۲: درخواست API
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
