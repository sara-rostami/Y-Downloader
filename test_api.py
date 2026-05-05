import requests
import re
import time
import sys

# ====================== ۱. استخراج API (خلاصه‌شده) ======================
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
        print(f"Key: {api_key}, URL: {api_url}")
        return api_key, api_url
    except Exception as e:
        print(f"❌ {e}")
        return None, None

# ====================== ۲. دریافت download_url ======================
def get_download_url(api_key, api_url):
    print("\n" + "=" * 60)
    print("مرحله ۲: دریافت download_url از progress endpoint")
    print("=" * 60)
    params = {
        'copyright': '0', 'format': '360',
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
            print("❌ API شکست:", data.get('error'))
            return None

        progress_url = data.get('progress_url')
        print(f"Progress URL: {progress_url}")

        # چند بار تلاش تا download_url برگردد
        for attempt in range(1, 10):
            print(f"🔄 تلاش {attempt}...")
            pr = requests.get(progress_url, headers=headers, timeout=10)
            if pr.status_code == 200:
                pdata = pr.json()
                if pdata.get('download_url'):
                    print(f"✅ download_url: {pdata['download_url']}")
                    return pdata['download_url']
            time.sleep(1)
        print("❌ download_url پیدا نشد")
        return None
    except Exception as e:
        print(f"❌ {e}")
        return None

# ====================== ۳. تست دانلود واقعی ======================
def test_real_download(download_url):
    print("\n" + "=" * 60)
    print("مرحله ۳: تست دانلود واقعی (GET چند کیلوبایت اول)")
    print("=" * 60)
    if not download_url:
        return

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://downloaderto.com/',
        'Accept': 'video/mp4,video/*,*/*;q=0.8'
    }
    try:
        # ابتدا HEAD برای دیدن ریدایرکت و سایز
        print("📡 HEAD request...")
        head_resp = requests.head(
            download_url,
            headers=headers,
            timeout=10,
            allow_redirects=True
        )
        final_url = head_resp.url
        size = head_resp.headers.get('content-length', '0')
        print(f"   Final URL after redirect: {final_url}")
        print(f"   Content-Length: {size}")

        # حالا GET واقعی و خواندن ۵ کیلوبایت اول
        print("\n📥 دریافت ۵۱۲۰ بایت اول فایل...")
        get_resp = requests.get(
            download_url,
            headers=headers,
            stream=True,
            timeout=15,
            allow_redirects=True
        )
        get_resp.raise_for_status()
        chunk = get_resp.read(5120)
        print(f"   وضعیت: {get_resp.status_code}")
        print(f"   حجم دریافتی: {len(chunk)} بایت")
        print(f"   Content-Type: {get_resp.headers.get('content-type')}")
        print(f"   Final URL: {get_resp.url}")

        # بررسی امضای فایل mp4 (ftyp)
        if b'ftyp' in chunk[:100]:
            print("   ✅ امضای MP4 پیدا شد! لینک معتبر است.")
            # اگر همه چیز خوب بود، لینک نهایی را برگردان
            return get_resp.url
        elif b'RIFF' in chunk[:4]:
            print("   ℹ️ شاید فایل AVI/WAV باشد.")
            return get_resp.url
        else:
            print("   ⚠️ امضای فایل شناسایی نشد. محتوای اولیه:")
            print("   ", chunk[:100])
            # شاید ریدایرکت به یک صفحه HTML باشد
            return None

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
        print("❌ نتوانستیم download_url بگیریم.")
        sys.exit(1)

    final_link = test_real_download(download_url)
    if final_link:
        print(f"\n🎉 لینک نهایی معتبر: {final_link}")
        print("✅ کد آماده استفاده در برنامه اصلی است!")
    else:
        print("\n⚠️ لینک نهایی هنوز نیاز به بررسی دارد.")

    print("\n🏁 پایان تست")
