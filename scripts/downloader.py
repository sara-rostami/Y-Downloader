#!/usr/bin/env python3
import argparse
import json
import time
import re
import html
import tempfile
import requests
from pathlib import Path

# ------------------------------------------------------------
# استخراج API از سایت (دقیقاً همان کد شما)
# ------------------------------------------------------------
def extract_api_config_from_website():
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

        # اگر پیدا نشد، در فایل‌های JS جستجو کن
        if not api_key or not api_url:
            js_files = re.findall(r'<script[^>]*src=["\']([^"\']+\.js[^"\']*)["\']', html_content)
            for js_file in js_files[:5]:
                try:
                    if not js_file.startswith('http'):
                        js_url = "https://downloaderto.com" + (js_file if js_file.startswith('/') else '/'+js_file)
                    else:
                        js_url = js_file
                    js_resp = requests.get(js_url, headers=headers, timeout=10)
                    if js_resp.status_code == 200:
                        js_content = js_resp.text
                        if not api_key:
                            for pattern in api_key_patterns:
                                matches = re.findall(pattern, js_content, re.IGNORECASE)
                                for match in matches:
                                    if len(match) == 32 and all(c in '0123456789abcdef' for c in match):
                                        api_key = match
                                        break
                                if api_key:
                                    break
                        if not api_url:
                            for pattern in api_url_patterns:
                                matches = re.findall(pattern, js_content, re.IGNORECASE)
                                for match in matches:
                                    if 'download' in match.lower() and match.startswith('http'):
                                        api_url = match
                                        break
                                if api_url:
                                    break
                    if api_key and api_url:
                        break
                except:
                    continue

        if api_key and api_url:
            return {'api_key': api_key, 'api_url': api_url, 'timestamp': time.time()}
        return None
    except Exception:
        return None

def get_api_config(force_refresh=False):
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
    if config:
        try:
            with open(cache_file, 'w') as f:
                json.dump(config, f)
        except:
            pass
        return config
    # fallback
    return {
        'api_key': '2e716c3914a4f931fdad91ad9e14c6b1',
        'api_url': 'https://p.lbserver.xyz/ajax/download.php',
        'timestamp': time.time()
    }

# ------------------------------------------------------------
# دریافت عنوان ویدیو (همان کد شما)
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
# Polling و دانلود (همان کد شما)
# ------------------------------------------------------------
def wait_for_download_link(download_id, max_attempts=25, wait_time=2):
    possible_urls = [
        f"https://p.savenow.to/download/{download_id}",
        f"https://p.savenow.to/api/download/{download_id}",
        f"https://p.lbserver.xyz/download/{download_id}",
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'video/mp4,video/*,*/*;q=0.8',
        'Referer': 'https://downloaderto.com/',
    }
    for attempt in range(1, max_attempts+1):
        for url in possible_urls:
            try:
                resp = requests.head(url, headers=headers, timeout=8, allow_redirects=True)
                if resp.status_code in [200,302,307]:
                    final_url = resp.url if resp.history else url
                    size = resp.headers.get('content-length', 0)
                    if size and int(size) > 500*1024:
                        size_str = f"{int(size)/(1024*1024):.1f} MB" if int(size) > 1024*1024 else f"{int(size)/1024:.1f} KB"
                        return {'url': final_url, 'size': size_str, 'size_bytes': int(size)}
            except:
                continue
        time.sleep(wait_time)
    return None

def download_file(download_url, filename, output_dir):
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://downloaderto.com/',
    }
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
    return {'success': True, 'filepath': str(filepath), 'size': f"{size_mb:.1f} MB"}

# ------------------------------------------------------------
# تابع اصلی (همان منطق دانلود شما)
# ------------------------------------------------------------
def download_youtube_video(youtube_url, quality, output_dir):
    quality_map = {"360p":"360", "480p":"480", "720p":"720", "1080p":"1080", "بهترین":"best"}
    format_code = quality_map.get(quality, "720")

    api_config = get_api_config(force_refresh=False)
    api_key = api_config['api_key']
    api_url = api_config['api_url']

    # دریافت عنوان
    video_title = get_video_title(youtube_url)
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)
    filename = f"{safe_title}_{quality}.mp4"

    # درخواست به API
    params = {'copyright':'0', 'format':format_code, 'url':youtube_url, 'api':api_key}
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Referer': 'https://downloaderto.com/'}
    resp = requests.get(api_url, params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"API خطا: {resp.status_code}")
    data = resp.json()
    if not data.get('success'):
        raise Exception(f"API خطا: {data.get('error', 'نامشخص')}")
    download_id = data.get('id')
    print(f"✅ Download ID: {download_id}")

    # Polling
    link_info = wait_for_download_link(download_id)
    if not link_info:
        raise Exception("زمان انتظار برای لینک دانلود تمام شد")

    # دانلود
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

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        file_path, title = download_youtube_video(args.url, args.quality, output_dir)
        # خروجی برای GitHub Actions
        with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
            f.write(f"video_file={file_path}\n")
            f.write(f"video_title={title}\n")
        print(f"✅ موفق: {file_path}")
    except Exception as e:
        print(f"❌ خطا: {e}")
        exit(1)
