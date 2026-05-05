import requests
import re
import time
import sys
import json
import os
from pathlib import Path

# ==================== استخراج API ====================
def extract_api_config():
    print("🔍 استخراج API از سایت downloaderto...")
    try:
        resp = requests.get(
            "https://downloaderto.com/enHF/",
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=15
        )
        if resp.status_code != 200:
            return None
        html = resp.text

        api_key = re.search(r'["\']([a-f0-9]{32})["\']', html)
        api_key = api_key.group(1) if api_key else None

        api_url = re.search(r'(https?://p\.savenow\.to/ajax/download\.php)', html)
        api_url = api_url.group(1) if api_url else None

        if api_key and api_url:
            return {'api_key': api_key, 'api_url': api_url}
        return None
    except Exception as e:
        print(f"❌ خطا: {e}")
        return None

def get_api_config(force_refresh=False):
    """کش تنظیمات API برای ۲۴ ساعت"""
    cache_file = Path.home() / ".downloaderto_cache.json"
    if not force_refresh and cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            if time.time() - cached.get('timestamp', 0) < 86400:
                print("📦 استفاده از API کش شده")
                return cached
        except:
            pass

    config = extract_api_config()
    if config:
        config['timestamp'] = time.time()
        try:
            with open(cache_file, 'w') as f:
                json.dump(config, f)
        except:
            pass
        return config
    raise Exception("❌ استخراج API ناموفق بود!")

# ==================== دریافت لینک نهایی ====================
def get_download_url(api_key, api_url, youtube_url, quality='720'):
    quality_map = {"360p": "360", "480p": "480", "720p": "720", "1080p": "1080", "best": "best"}
    fmt = quality_map.get(quality, "720")

    params = {
        'copyright': '0',
        'format': fmt,
        'url': youtube_url,
        'api': api_key
    }
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://downloaderto.com/'
    }

    print(f"📤 درخواست به API برای {youtube_url} (کیفیت: {fmt})")
    r = requests.get(api_url, params=params, headers=headers, timeout=30)
    data = r.json()
    if not data.get('success'):
        raise Exception(f"API خطا: {data.get('error')}")

    progress_url = data.get('progress_url')
    if not progress_url:
        raise Exception("progress_url یافت نشد")

    print(f"⏳ Polling روی {progress_url}")
    for attempt in range(1, 15):
        print(f"   تلاش {attempt}...")
        pr = requests.get(progress_url, headers=headers, timeout=10)
        if pr.status_code == 200:
            pdata = pr.json()
            if pdata.get('download_url'):
                durl = pdata['download_url']
                print(f"✅ لینک مستقیم: {durl}")
                return durl
        time.sleep(2)
    raise Exception("دریافت download_url بعد از ۱۵ تلاش ناموفق ماند")

# ==================== دانلود فایل ====================
def download_file(download_url, output_dir, filename=None):
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://downloaderto.com/',
        'Accept': 'video/mp4,video/*'
    }
    print("📥 شروع دانلود فایل...")
    response = requests.get(download_url, headers=headers, stream=True, timeout=60, allow_redirects=True)
    response.raise_for_status()

    if not filename:
        # استخراج نام از URL یا عنوان (در تابع اصلی جایگزین می‌شود)
        filename = "downloaded_video.mp4"

    filepath = Path(output_dir) / filename
    total_size = int(response.headers.get('content-length', 0))

    with open(filepath, 'wb') as f:
        downloaded = 0
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    percent = downloaded / total_size * 100
                    print(f"📥 {percent:.1f}%", end='\r')
    print(f"\n✅ دانلود کامل شد: {filepath} ({downloaded} بایت)")
    return str(filepath)

# ==================== تابع اصلی ====================
def download_youtube_video(youtube_url, quality, output_dir="."):
    """
    دانلود ویدیو یوتیوب با کیفیت مشخص شده.
    پارامترها:
        youtube_url: لینک ویدیو
        quality: یکی از '360p', '480p', '720p', '1080p', 'best'
        output_dir: مسیر ذخیره‌سازی (پیش‌فرض دایرکتوری جاری)
    بازگشت: مسیر فایل دانلود شده
    """
    # دریافت API
    config = get_api_config()
    api_key = config['api_key']
    api_url = config['api_url']

    # دریافت عنوان ویدیو (برای نام فایل)
    try:
        # استخراج شناسه
        video_id = re.search(r'(?:v=|/)([0-9A-Za-z_-]{11})', youtube_url)
        if video_id:
            video_id = video_id.group(1)
            oembed = requests.get(
                f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            ).json()
            title = oembed.get('title', f'video_{video_id}')
            # پاکسازی کاراکترهای نامناسب برای فایل
            title = re.sub(r'[<>:"/\\|?*]', ' ', title)
            title = re.sub(r'\s+', ' ', title).strip()[:100]
        else:
            title = "downloaded_video"
    except:
        title = "downloaded_video"

    filename = f"{title}_{quality}.mp4".replace(' ', '_')

    # دریافت لینک مستقیم
    download_url = get_download_url(api_key, api_url, youtube_url, quality)

    # دانلود
    file_path = download_file(download_url, output_dir, filename)
    return file_path

# ==================== استفاده نمونه ====================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("استفاده:")
        print("  python youtube_downloader.py <YouTube_URL> [کیفیت]")
        print("کیفیت‌ها: 360p, 480p, 720p (پیش‌فرض), 1080p, best")
        print()
        # تست پیش‌فرض
        test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        print(f"اجرای تست با {test_url} (کیفیت 360p)")
        try:
            path = download_youtube_video(test_url, "360p")
            print(f"✅ فایل نهایی: {path}")
        except Exception as e:
            print(f"❌ خطا: {e}")
    else:
        url = sys.argv[1]
        quality = sys.argv[2] if len(sys.argv) > 2 else "720p"
        try:
            path = download_youtube_video(url, quality)
            print(f"✅ دانلود کامل شد: {path}")
        except Exception as e:
            print(f"❌ خطا: {e}")
