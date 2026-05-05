import requests
import re
import time
import sys

# ====================== ۱. استخراج API ======================
def extract_api_config():
    print("=" * 60)
    print("مرحله ۱: استخراج API")
    print("=" * 60)
    try:
        resp = requests.get(
            "https://downloaderto.com/enHF/",
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=15
        )
        html = resp.text
        api_key = re.search(r'["\']([a-f0-9]{32})["\']', html)
        api_key = api_key.group(1) if api_key else None
        api_url = re.search(r'(https?://p\.savenow\.to/ajax/download\.php)', html)
        api_url = api_url.group(1) if api_url else None
        print(f"✅ Key: {api_key}")
        print(f"✅ URL: {api_url}")
        return api_key, api_url
    except Exception as e:
        print(f"❌ {e}")
        return None, None

# ====================== ۲. دریافت download_url ======================
def get_download_url(api_key, api_url):
    print("\n" + "=" * 60)
    print("مرحله ۲: دریافت download_url از progress")
    print("=" * 60)
    params = {
        'copyright': '0',
        'format': '360',
        'url': 'https://www.youtube.com/watch?v=jNQXAC9IVRw',
        'api': api_key
    }
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://downloaderto.com/'
    }
    try:
        r = requests.get(api_url, params=params, headers=headers, timeout=30)
        data = r.json()
        if not data.get('success'):
            print("❌ API:", data.get('error'))
            return None

        progress_url = data.get('progress_url')
        print(f"🔗 Progress URL: {progress_url}")

        for attempt in range(1, 10):
            print(f"🔄 تلاش {attempt}...")
            pr = requests.get(progress_url, headers=headers, timeout=10)
            if pr.status_code == 200:
                pdata = pr.json()
                if pdata.get('download_url'):
                    durl = pdata['download_url']
                    print(f"✅ download_url: {durl}")
                    return durl
            time.sleep(1)
        print("❌ download_url دریافت نشد")
        return None
    except Exception as e:
        print(f"❌ {e}")
        return None

# ====================== ۳. تست دانلود واقعی ======================
def test_real_download(download_url):
    print("\n" + "=" * 60)
    print("مرحله ۳: تست GET واقعی و بررسی امضای فایل")
    print("=" * 60)
    if not download_url:
        return None

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://downloaderto.com/',
        'Accept': 'video/mp4,video/*,*/*;q=0.8'
    }
    try:
        print(f"📡 درخواست GET به {download_url}")
        # دریافت فقط ۸۱۹۲ بایت اول
        response = requests.get(
            download_url,
            headers=headers,
            stream=True,
            timeout=30,
            allow_redirects=True
        )
        response.raise_for_status()
        final_url = response.url
        content_type = response.headers.get('content-type', '')
        total_size = response.headers.get('content-length', '0')

        print(f"   Final URL: {final_url}")
        print(f"   Content-Type: {content_type}")
        print(f"   Content-Length: {total_size}")

        # خواندن ۵۱۲۰ بایت اول
        chunk = response.iter_content(chunk_size=5120).__next__()
        print(f"   حجم خوانده شده: {len(chunk)} بایت")
        print(f"   امضای اولیه: {chunk[:12].hex()} - {chunk[:12]}")

        # بررسی امضای mp4 معمول (ftyp)
        if b'ftyp' in chunk[:100]:
            print("   ✅ امضای MP4 پیدا شد! فایل معتبر است.")
            return final_url
        elif chunk[:4] == b'RIFF':
            print("   ℹ️ امضای RIFF (WebM یا AVI). احتمالاً قابل قبول.")
            return final_url
        elif chunk[:4] == b'\x1a\x45\xdf\xa3':
            print("   ℹ️ امضای WebM/MKV. قابل قبول.")
            return final_url
        else:
            # شاید HTML برگرداده باشه
            if b'<!DOCTYPE html>' in chunk or b'<html' in chunk:
                print("   ❌ پاسخ HTML است نه فایل ویدیویی! محتوا:")
                print("   ", chunk[:200])
                return None
            else:
                print("   ⚠️ امضای ناشناخته. شاید فایل درست باشه، ادامه بررسی دستی.")
                # با این وجود شاید بشه دانلود کرد
                return final_url

    except Exception as e:
        print(f"❌ خطا: {e}")
        return None

# ====================== اجرا ======================
if __name__ == "__main__":
    api_key, api_url = extract_api_config()
    if not api_key or not api_url:
        sys.exit(1)

    download_url = get_download_url(api_key, api_url)
    if not download_url:
        print("❌ download_url به دست نیامد.")
        sys.exit(1)

    final_link = test_real_download(download_url)
    if final_link:
        print(f"\n🎉 لینک نهایی معتبر: {final_link}")
        print("✅ می‌توان از این روش در برنامه نهایی استفاده کرد.")
    else:
        print("\n⚠️ لینک نهایی معتبر نیست. نیاز به بررسی بیشتر.")

    print("\n🏁 پایان تست")
