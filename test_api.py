import requests
import re
import time
import base64
import json
import sys
from pathlib import Path

# ====================== استخراج API از سایت ======================
def extract_api_config():
    print("=" * 60)
    print("مرحله ۱: استخراج API از سایت downloaderto.com")
    print("=" * 60)
    try:
        site_url = "https://downloaderto.com/enHF/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml'
        }
        resp = requests.get(site_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"❌ دریافت صفحه اصلی شکست خورد: {resp.status_code}")
            return None, None
        html = resp.text

        # ذخیره HTML برای بررسی دستی (اختیاری)
        debug_file = Path("/tmp/downloaderto_main.html")
        debug_file.write_text(html, encoding='utf-8')
        print(f"📄 صفحه اصلی ذخیره شد: {debug_file}")

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
        print(f"❌ خطای کلی: {e}")
        return None, None

# ====================== درخواست API و استخراج لینک ======================
def fetch_and_decode(api_key, api_url):
    print("\n" + "=" * 60)
    print("مرحله ۲: درخواست به API و تحلیل پاسخ")
    print("=" * 60)
    if not api_key or not api_url:
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
        print("Response (first 500 chars):", r.text[:500])
        data = r.json()
        print("JSON keys:", list(data.keys()))
        if data.get('success'):
            download_id = data.get('id')
            content_b64 = data.get('content', '')
            print(f"✅ Download ID: {download_id}")
            print(f"Content base64 (first 80 chars): {content_b64[:80]}...")

            # دیکد base64
            try:
                decoded_bytes = base64.b64decode(content_b64)
                decoded_html = decoded_bytes.decode('utf-8', errors='ignore')
                print("\n✅ محتوای دیکد شده (۲۰۰۰ کاراکتر اول):")
                print(decoded_html[:2000])

                # الگوهای مختلف برای یافتن لینک mp4 یا لینک دانلود
                patterns = [
                    r'href=["\'](https?://[^"\']+\.mp4[^"\']*)',
                    r'(https?://[^"\']+/download/[^"\']+)',
                    r'(https?://[^"\']+/file/[^"\']+)',
                    r'(https?://[^"\']+\.mp4[^"\']*)',
                    r'data-url=["\']([^"\']+)["\']',
                    r'download-url=["\']([^"\']+)["\']',
                    r'(https?://[^"\']+/dl/[^"\']+)',
                ]
                found_links = []
                for pat in patterns:
                    matches = re.findall(pat, decoded_html, re.IGNORECASE)
                    for link in matches:
                        if link not in found_links:
                            found_links.append(link)
                            print(f"🔗 لینک احتمالی: {link}")

                if found_links:
                    # اولویت با mp4
                    mp4_links = [l for l in found_links if '.mp4' in l.lower()]
                    final_link = mp4_links[0] if mp4_links else found_links[0]
                    print(f"\n🎯 لینک انتخاب شده: {final_link}")
                    return final_link
                else:
                    print("\n⚠️ هیچ لینکی در content پیدا نشد.")
                    # برگرداندن ID + content برای بررسی بیشتر
                    return {'id': download_id, 'content': decoded_html}

            except Exception as e:
                print(f"❌ خطا در دیکد base64: {e}")
                return {'id': download_id}
        else:
            print("❌ API شکست:", data.get('error'))
            return None
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

# ====================== تست لینک مستقیم ======================
def test_direct_link(link):
    if isinstance(link, dict):
        # لینک پیدا نشد، از ID استفاده می‌کنیم
        download_id = link.get('id')
        if not download_id:
            print("❌ شناسه دانلود هم موجود نیست.")
            return None
        print(f"\n🔄 لینک در content نبود، آزمایش مسیرهای جایگزین با ID {download_id}...")
        alternative_urls = [
            f"https://p.savenow.to/dl/{download_id}",
            f"https://p.savenow.to/file/{download_id}",
            f"https://downloaderto.com/download/{download_id}",
            f"https://downloaderto.com/dl/{download_id}",
            f"https://downloaderto.com/file/{download_id}",
            f"https://p.lbserver.xyz/dl/{download_id}",
            f"https://p.lbserver.xyz/file/{download_id}",
        ]
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://downloaderto.com/'
        }
        for alt_url in alternative_urls:
            try:
                resp = requests.head(alt_url, headers=headers, timeout=8, allow_redirects=True)
                size = resp.headers.get('content-length', '0')
                if resp.status_code in [200, 302] and int(size) > 500000:
                    print(f"✅ لینک فعال پیدا شد: {alt_url} (size={size})")
                    return alt_url
                else:
                    print(f"   {alt_url} -> {resp.status_code}, size={size}")
            except Exception as e:
                print(f"   {alt_url} -> خطا: {e}")
        return None
    else:
        # لینک مستقیم از content
        print("\n" + "=" * 60)
        print("مرحله ۳: تست لینک دانلود مستقیم")
        print("=" * 60)
        try:
            headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://downloaderto.com/'}
            r = requests.head(link, headers=headers, timeout=10, allow_redirects=True)
            size = r.headers.get('content-length', '0')
            final_url = r.url
            print(f"Status: {r.status_code}, Size: {size}")
            if r.status_code in [200, 302] and int(size) > 100000:
                print(f"✅ لینک فعال: {final_url}")
                return final_url
            else:
                print("⚠️ لینک قابل استفاده نیست یا حجم کم است.")
                return None
        except Exception as e:
            print(f"❌ {e}")
            return None

# ====================== اجرای اصلی ======================
if __name__ == "__main__":
    api_key, api_url = extract_api_config()
    if not api_key or not api_url:
        print("❌ استخراج API ناموفق. پایان.")
        sys.exit(1)

    result = fetch_and_decode(api_key, api_url)
    if not result:
        print("❌ دریافت اطلاعات از API ناموفق.")
        sys.exit(1)

    final_link = test_direct_link(result)
    if final_link:
        print(f"\n🎉 لینک نهایی دانلود: {final_link}")
    else:
        print("\n⚠️ نتوانستیم لینک مستقیم پیدا کنیم. شاید نیاز به بررسی بیشتر باشد.")

    print("\n🏁 پایان تست")
