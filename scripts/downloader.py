#!/usr/bin/env python3
import argparse
import json
import time
import re
import html
import tempfile
import requests
import os
from pathlib import Path

# ------------------------------------------------------------
# استخراج API از سایت downloaderto (با چندین آدرس پیش‌فرض)
# ------------------------------------------------------------
EXTRACTED_API_CACHE = None

def extract_api_config_from_website():
    global EXTRACTED_API_CACHE
    if EXTRACTED_API_CACHE:
        return EXTRACTED_API_CACHE
    try:
        site_url = "https://downloaderto.com/enHF/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        response = requests.get(site_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        html_content = response.text

        # الگوهای API key (32 کاراکتر hex)
        api_key_patterns = [
            r'api["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'apiKey["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'API_KEY["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'key["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']',
            r'["\']([a-f0-9]{32})["\']',
        ]
        api_key = None
        for pattern in api_key_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                if len(match) == 32 and all(c in '0123456789abcdef' for c in match):
                    api_key = match
                    break
            if api_key:
                break

        # الگوهای API URL
        api_url_patterns = [
            r'(https?://[a-z0-9\.-]+/ajax/download\.php)',
            r'(https?://[a-z0-9\.-]+/api/download\.php)',
            r'apiUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'API_URL["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        ]
        api_url = None
        for pattern in api_url_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                if 'download' in match.lower() and match.startswith('http'):
                    api_url = match
                    break
            if api_url:
                break

        if api_key and api_url:
            EXTRACTED_API_CACHE = {'api_key': api_key, 'api_url': api_url, 'timestamp': time.time()}
            return EXTRACTED_API_CACHE
        return None
    except Exception:
        return None

def get_api_config(force_refresh=False):
    # لیست fallback آدرس‌های API (در صورت عدم استخراج یا خطا)
    fallback_apis = [
        'https://p.lbserver.xyz/ajax/download.php',
        'https://p.savenow.to/ajax/download.php',
        'https://api.downloaderto.com/ajax/download.php',
    ]
    cache_file = Path(tempfile.gettempdir()) / "downloaderto_api_cache.json"
    if not force_refresh and cache_file.exists():
        try:
            with open(cache_file) as f:
                cached = json.load(f)
                if time.time() - cached.get('timestamp', 0) < 24*3600:
                    return cached
        except:
            pass
    config = extract_api_config_from_website()
    if config and config.get('api_url'):
        # اگر آدرس استخراج شده در لیست fallback نبود، آن را اول قرار بده
        if config['api_url'] not in fallback_apis:
            fallback_apis.insert(0, config['api_url'])
        config['api_url'] = fallback_apis[0]  # اولویت با آدرس استخراج شده
        try:
            with open(cache_file, 'w') as f:
                json.dump(config, f)
        except:
            pass
        return config
    # برگرداندن اولین fallback
    return {
        'api_key': '2e716c3914a4f931fdad91ad9e14c6b1',
        'api_url': fallback_apis[0],
        'timestamp': time.time()
    }

# ------------------------------------------------------------
# دریافت عنوان ویدیو (بدون تغییر)
# ------------------------------------------------------------
def extract_youtube_video_id(url):
    patterns = [
        r'(?:v=|/)([0-9A-Za-z_-]{11})',
        r'(?:embed/)([0-9A-Za-z_-]{11})',
        r'youtu\.be/([0-9A-Za-z_-]{11})',
        r'shorts/([0-9A-Za-z_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def get_video_title(youtube_url):
    video_id = extract_youtube_video_id(youtube_url)
    if not video_id:
        return f"Video_{int(time.time())}"
    try:
        resp = requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json", timeout=10)
        if resp.status_code == 200:
            title = resp.json().get('title', '')
            if title:
                title = html.unescape(title)
                return sanitize_title(title)
    except:
        pass
    try:
        resp = requests.get(f"https://noembed.com/embed?url=https://www.youtube.com/watch?v={video_id}", timeout=10)
        if resp.status_code == 200:
            title = resp.json().get('title', '')
            if title:
                title = html.unescape(title)
                return sanitize_title(title)
    except:
        pass
    return f"YouTube_{video_id}"

def sanitize_title(title):
    title = re.sub(r'\s*-\s*YouTube\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'[<>:"/\\|?*]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 100:
        title = title[:97] + "..."
    return title

# ------------------------------------------------------------
# Polling با پشتیبانی از چندین لینک
# ------------------------------------------------------------
def wait_for_download_link(download_id, max_attempts=5, wait_time=30):
    possible_urls = [
        f"https://p.savenow.to/download/{download_id}",
        f"https://p.savenow.to/api/download/{download_id}",
        f"https://p.lbserver.xyz/download/{download_id}",
        f"https://downloaderto.com/download/{download_id}",
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'video/mp4,video/*,*/*;q=0.8',
        'Referer': 'https://downloaderto.com/',
    }
    print(f"⏳ شروع polling برای Download ID: {download_id}")
    print(f"📊 حداکثر {max_attempts} تلاش، هر {wait_time} ثانیه یک بار")
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 تلاش {attempt}/{max_attempts}...")
        for url in possible_urls:
            try:
                resp = requests.head(url, headers=headers, timeout=8, allow_redirects=True)
                print(f"   🔍 بررسی {url} => وضعیت {resp.status_code}")
                if resp.status_code in [200, 302, 307]:
                    final_url = resp.url if resp.history else url
                    size = resp.headers.get('content-length', 0)
                    if size and int(size) > 500 * 1024:
                        if int(size) < 1024*1024:
                            size_str = f"{int(size)/1024:.1f} KB"
                        else:
                            size_str = f"{int(size)/(1024*1024):.1f} MB"
                        print(f"✅ لینک آماده شد! حجم: {size_str}")
                        return {
                            'url': final_url,
                            'size': size_str,
                            'size_bytes': int(size),
                            'attempts': attempt
                        }
            except Exception as e:
                print(f"   ⚠️ خطا در بررسی {url}: {str(e)[:50]}")
                continue
        time.sleep(wait_time)
    
    print(f"❌ پس از {max_attempts} تلاش، لینک پیدا نشد")
    return None

def download_file(download_url, filename, output_dir):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://downloaderto.com/',
    }
    print(f"📥 شروع دانلود: {filename}")
    resp = requests.get(download_url, headers=headers, stream=True, timeout=60)
    resp.raise_for_status()
    filepath = output_dir / filename
    total = int(resp.headers.get('content-length', 0))
    with open(filepath, 'wb') as f:
        downloaded = 0
        for chunk in resp.iter_content(8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                print(f"\r📥 {downloaded/total*100:.1f}%", end='')
    print()
    size_mb = filepath.stat().st_size / (1024*1024)
    return {
        'success': True,
        'filepath': str(filepath),
        'size': f"{size_mb:.1f} MB"
    }

# ------------------------------------------------------------
# تابع اصلی با پشتیبانی از چندین API endpoint (fallback)
# ------------------------------------------------------------
def call_api_with_fallback(youtube_url, format_code, api_key, api_url_list):
    """تلاش برای فراخوانی API با لیستی از آدرس‌ها"""
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Referer': 'https://downloaderto.com/'}
    for api_url in api_url_list:
        params = {'copyright': '0', 'format': format_code, 'url': youtube_url, 'api': api_key}
        try:
            print(f"🌐 تلاش به آدرس: {api_url}")
            resp = requests.get(api_url, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success'):
                    return data
                else:
                    print(f"⚠️ API {api_url} خطا: {data.get('error', 'نامشخص')}")
            else:
                print(f"⚠️ API {api_url} پاسخ نامعتبر: {resp.status_code}")
        except Exception as e:
            print(f"⚠️ خطا در ارتباط با {api_url}: {str(e)[:50]}")
            continue
    return None

def download_youtube_video(youtube_url, quality, output_dir):
    quality_map = {"360p": "360", "480p": "480", "720p": "720", "1080p": "1080", "بهترین": "best"}
    format_code = quality_map.get(quality, "720")

    # دریافت کلید API (بدون آدرس خاص)
    api_config = get_api_config(force_refresh=False)
    api_key = api_config['api_key']
    # لیست آدرس‌های API برای fallback
    api_url_list = [
        'https://p.lbserver.xyz/ajax/download.php',
        'https://p.savenow.to/ajax/download.php',
        'https://api.downloaderto.com/ajax/download.php',
    ]
    # اگر آدرسی از سایت استخراج شده و در لیست نیست، اول اضافه کن
    extracted_url = api_config.get('api_url')
    if extracted_url and extracted_url not in api_url_list:
        api_url_list.insert(0, extracted_url)

    print(f"🔑 API Key: {api_key[:16]}...")
    
    # عنوان ویدیو
    video_title = get_video_title(youtube_url)
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)
    filename = f"{safe_title}_{quality}.mp4"

    # فراخوانی API با fallback
    data = call_api_with_fallback(youtube_url, format_code, api_key, api_url_list)
    if not data:
        raise Exception("تمامی API endpoint‌ها پاسخگو نبودند. لطفاً بعداً تلاش کنید.")
    
    download_id = data.get('id')
    print(f"✅ Download ID: {download_id}")

    # Polling برای دریافت لینک دانلود
    link_info = wait_for_download_link(download_id, max_attempts=40, wait_time=3)
    if not link_info:
        manual_url = f"https://downloaderto.com/download/{download_id}"
        raise Exception(f"زمان انتظار تمام شد. لطفاً ویدیو را به صورت دستی از این لینک دانلود کنید: {manual_url}")

    # دانلود فایل
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    result = download_file(link_info['url'], filename, output_path)
    if not result['success']:
        raise Exception("دانلود ناموفق")
    return result['filepath'], video_title

# ------------------------------------------------------------
# اجرای خط فرمان و خروجی برای GitHub Actions
# ------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--quality", default="720p")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        file_path, title = download_youtube_video(args.url, args.quality, out_dir)
        github_output = os.getenv("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write(f"video_file={file_path}\n")
                f.write(f"video_title={title}\n")
        else:
            print(f"::set-output name=video_file::{file_path}")
            print(f"::set-output name=video_title::{title}")
        print(f"✅ موفق: {file_path}")
    except Exception as e:
        print(f"❌ خطا: {e}")
        exit(1)
