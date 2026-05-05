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

        api_key = None
        for pat in [
            r'api["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'apiKey["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'key["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'["\']([a-f0-9]{32})["\']',
        ]:
            matches = re.findall(pat, html, re.IGNORECASE)
            for m in matches:
                if len(m) == 32 and all(c in '0123456789abcdef' for c in m):
                    api_key = m
                    print(f"✅ API Key پیدا شد: {api_key}")
                    break
            if api_key:
                break

        api_url = None
        for pat in [
            r'(https?://[a-z0-9\.-]+/ajax/download\.php)',
            r'(https?://[a-z0-9\.-]+/api/download\.php)',
            r'apiUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        ]:
            matches = re.findall(pat, html, re.IGNORECASE)
            for m in matches:
                if 'download' in m.lower() and m.startswith('http'):
                    api_url = m
                    print(f"✅ API URL پیدا شد: {api_url}")
                    break
            if api_url:
                break

        return api_key, api_url
    except Exception as e:
        print(f"❌ خطای کلی: {e}")
        return None, None

# ====================== تابع اصلی بررسی progress_url ======================
def test_progress_url(api_key, api_url):
    print("\n" + "=" * 60)
    print("مرحله ۲: درخواست API و بررسی progress_url")
    print("=" * 60)

    youtube_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
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
        data = r.json()

        if not data.get('success'):
            print(f"❌ API شکست: {data.get('error')}")
            return None

        download_id = data.get('id')
        progress_url = data.get('progress_url')
        title = data.get('title', '')
        info = data.get('info', {})

        print(f"✅ Download ID: {download_id}")
        print(f"📝 Title: {title}")
        print(f"📊 Info: {info}")
        print(f"🔗 Progress URL: {progress_url}")

        if progress_url:
            # مرحله ۳: بررسی progress_url
            print("\n" + "=" * 60)
            print("مرحله ۳: Polling progress_url تا آماده شدن فایل")
            print("=" * 60)

            # ساخت URL کامل اگر نسبی باشد
            if progress_url.startswith('/'):
                progress_url = f"https://p.savenow.to{progress_url}"
            elif not progress_url.startswith('http'):
                progress_url = f"https://p.savenow.to/{progress_url}"

            print(f"🌐 آدرس polling: {progress_url}")

            for attempt in range(1, 15):
                print(f"\n🔄 تلاش {attempt}:")

                try:
                    pr = requests.get(
                        progress_url,
                        headers={
                            'User-Agent': 'Mozilla/5.0',
                            'Referer': 'https://downloaderto.com/',
                            'Accept': 'application/json, text/plain, */*'
                        },
                        timeout=10
                    )
                    print(f"   Status: {pr.status_code}")
                    print(f"   Response: {pr.text[:300]}")

                    # ممکن است JSON باشد
                    try:
                        progress_data = pr.json()
                        print(f"   JSON keys: {list(progress_data.keys())}")

                        # دنبال لینک دانلود بگردیم
                        if progress_data.get('download_url'):
                            print(f"   ✅ لینک دانلود پیدا شد: {progress_data['download_url']}")
                            return progress_data['download_url']

                        if progress_data.get('url'):
                            print(f"   ✅ لینک در فیلد url: {progress_data['url']}")
                            return progress_data['url']

                        # چاپ همه کلیدها برای بررسی
                        for k, v in progress_data.items():
                            if isinstance(v, str) and ('http' in v or 'mp4' in v):
                                print(f"   🔗 کلید {k} حاوی لینک است: {v[:200]}")
                    except:
                        pass

                    # جستجوی لینک در متن پاسخ
                    links = re.findall(r'https?://[^"\'\s]+', pr.text)
                    mp4_links = [l for l in links if '.mp4' in l]
                    if mp4_links:
                        print(f"   ✅ لینک mp4 در پاسخ: {mp4_links[0]}")
                        return mp4_links[0]
                    elif links:
                        print(f"   🔗 لینک‌های یافت شده: {links[:3]}")

                except Exception as e:
                    print(f"   ❌ خطا: {e}")

                time.sleep(2)

            print("\n❌ بعد از ۱۴ تلاش لینکی پیدا نشد")

            # یک بار دیگر با POST امتحان کن
            print("\n🔄 تلاش با متد POST...")
            try:
                pr_post = requests.post(
                    progress_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0',
                        'Referer': 'https://downloaderto.com/',
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    data={'id': download_id},
                    timeout=10
                )
                print(f"   POST Status: {pr_post.status_code}")
                print(f"   POST Response: {pr_post.text[:300]}")
            except Exception as e:
                print(f"   ❌ POST خطا: {e}")

    except Exception as e:
        print(f"❌ خطا: {e}")

    return None

# ====================== اجرا ======================
if __name__ == "__main__":
    api_key, api_url = extract_api_config()
    if not api_key or not api_url:
        print("❌ استخراج API ناموفق.")
        sys.exit(1)

    final_link = test_progress_url(api_key, api_url)

    if final_link:
        print(f"\n🎉 لینک نهایی دانلود: {final_link}")

        # تست HEAD روی لینک
        print("\n" + "=" * 60)
        print("تست لینک دانلود")
        print("=" * 60)
        try:
            hr = requests.head(
                final_link,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10,
                allow_redirects=True
            )
            size = int(hr.headers.get('content-length', '0'))
            print(f"Status: {hr.status_code}, Size: {size}")
            if size > 100000:
                print(f"✅ لینک معتبر است! حجم: {size/(1024*1024):.1f} MB")
            else:
                print("⚠️ حجم فایل کم است یا لینک مستقیم نیست")
        except Exception as e:
            print(f"❌ خطا در تست: {e}")
    else:
        print("\n⚠️ نتوانستیم لینک مستقیم پیدا کنیم.")

    print("\n🏁 پایان تست")
