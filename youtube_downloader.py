import requests
import re
import time
import sys
import os
import json
import tempfile
from pathlib import Path

# ==================== استخراج API ====================
def extract_api_config():
    print("🔍 استخراج API از سایت downloaderto...")
    try:
        resp = requests.get(
            "https://downloaderto.com/enHF/",
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
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
            print(f"✅ API Key: {api_key}")
            print(f"✅ API URL: {api_url}")
            return {'api_key': api_key, 'api_url': api_url}
        return None
    except Exception as e:
        print(f"❌ خطا در استخراج: {e}")
        return None

def get_api_config(force_refresh=False):
    """دریافت تنظیمات API با cache و fallback"""
    cache_file = Path(tempfile.gettempdir()) / "downloaderto_cache.json"
    if not force_refresh and cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            if time.time() - cached.get('timestamp', 0) < 86400:
                print("📦 استفاده از API کش شده")
                return cached
        except:
            pass

    # تلاش برای استخراج خودکار
    config = extract_api_config()
    if config:
        config['timestamp'] = time.time()
        try:
            with open(cache_file, 'w') as f:
                json.dump(config, f)
        except:
            pass
        return config

    # Fallback به مقادیر ثابت (آخرین test موفق)
    print("⚠️ استخراج خودکار ناموفق – استفاده از API پیش‌فرض.")
    fallback_config = {
        'api_key': 'e1f31df4f6424efab5eb606004289ced',
        'api_url': 'https://p.savenow.to/ajax/download.php',
        'timestamp': time.time()
    }
    return fallback_config

# ==================== دریافت لینک مستقیم دانلود ====================
def get_download_url(api_key, api_url, youtube_url, quality='720'):
    quality_map = {
        "360p": "360",
        "480p": "480",
        "720p": "720",
        "1080p": "1080",
        "best": "best"
    }
    fmt = quality_map.get(quality, "720")

    params = {
        'copyright': '0',
        'format': fmt,
        'url': youtube_url,
        'api': api_key
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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
    # حداکثر ۶۰ ثانیه انتظار
    for attempt in range(1, 31):
        print(f"   تلاش {attempt}...")
        try:
            pr = requests.get(progress_url, headers=headers, timeout=10)
            if pr.status_code == 200:
                pdata = pr.json()
                if pdata.get('download_url'):
                    durl = pdata['download_url']
                    print(f"✅ لینک مستقیم: {durl}")
                    return durl
        except Exception as e:
            print(f"⚠️ خطا در تلاش {attempt}: {e}")
        time.sleep(2)

    raise Exception("دریافت download_url بعد از 60 ثانیه ناموفق ماند")

# ==================== استخراج عنوان ویدیو ====================
def get_video_title(youtube_url):
    try:
        video_id = re.search(r'(?:v=|/)([0-9A-Za-z_-]{11})', youtube_url)
        if video_id:
            video_id = video_id.group(1)
            oembed = requests.get(
                f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            ).json()
            title = oembed.get('title', f'video_{video_id}')
            # پاکسازی کاراکترهای نامناسب برای نام فایل
            title = re.sub(r'[<>:"/\\|?*]', ' ', title)
            title = re.sub(r'\s+', ' ', title).strip()[:100]
            return title
    except:
        pass
    return "downloaded_video"

# ==================== دانلود فایل ====================
def download_file(download_url, filename, output_dir="."):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://downloaderto.com/',
        'Accept': 'video/mp4,video/*,*/*;q=0.8'
    }

    print(f"📥 شروع دانلود: {filename}")
    response = requests.get(download_url, headers=headers, stream=True, timeout=60, allow_redirects=True)
    response.raise_for_status()

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
                    print(f"   {percent:.1f}%", end='\r')
    print(f"\n✅ دانلود کامل شد: {filepath} ({downloaded} بایت)")
    return str(filepath)

# ==================== روند اصلی ====================
def download_youtube_video(youtube_url, quality="720p", output_dir="."):
    print(f"🎬 شروع دانلود: {youtube_url}")
    # 1. تنظیمات API (با fallback)
    config = get_api_config()
    api_key = config['api_key']
    api_url = config['api_url']

    # 2. عنوان ویدیو
    title = get_video_title(youtube_url)
    safe_title = re.sub(r'[^\w\-_\. ]', '', title).replace(' ', '_')
    filename = f"{safe_title}_{quality}.mp4"

    # 3. دریافت لینک مستقیم
    download_url = get_download_url(api_key, api_url, youtube_url, quality)

    # 4. دانلود فایل
    file_path = download_file(download_url, filename, output_dir)
    return file_path

# ==================== ورودی برنامه ====================
if __name__ == "__main__":
    # خواندن لینک از environment variable (مناسب GitHub Actions) یا آرگومان
    url = os.environ.get("YOUTUBE_URL") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not url:
        print("❌ لینک یوتیوب مشخص نشده است.")
        print("میتوانید از متغیر محیطی YOUTUBE_URL یا آرگومان خط فرمان استفاده کنید.")
        sys.exit(1)

    quality = os.environ.get("QUALITY", "720p")
    output_dir = os.environ.get("OUTPUT_DIR", ".")

    try:
        file_path = download_youtube_video(url, quality, output_dir)
        print(f"🎉 فایل نهایی: {file_path}")
        # خروجی مسیر فایل برای استفاده در مراحل بعدی GitHub Actions
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"downloaded_file={file_path}\n")
    except Exception as e:
        print(f"❌ خطا: {e}")
        sys.exit(1)
