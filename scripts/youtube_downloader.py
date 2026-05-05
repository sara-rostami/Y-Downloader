#!/usr/bin/env python3
# scripts/youtube_downloader.py

import argparse
import json
import re
import time
import html
import tempfile
import requests
from pathlib import Path
from urllib.parse import quote_plus

# ------------------- استخراج API از سایت -------------------
def extract_api_config():
    try:
        site_url = "https://downloaderto.com/enHF/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(site_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        html_content = resp.text

        # الگوهای API Key (32 کاراکتر hex)
        pattern_key = r'["\']([a-f0-9]{32})["\']'
        api_key = None
        for m in re.finditer(pattern_key, html_content, re.IGNORECASE):
            candidate = m.group(1)
            if len(candidate) == 32:
                api_key = candidate
                break

        # الگوهای API URL
        pattern_url = r'(https?://[a-z0-9\.-]+/(?:ajax/)?download\.php)'
        api_url = None
        for m in re.finditer(pattern_url, html_content, re.IGNORECASE):
            if 'download' in m.group(1):
                api_url = m.group(1)
                break

        # اگر پیدا نشد، در فایل‌های JS جستجو کن
        if not api_key or not api_url:
            js_files = re.findall(r'<script[^>]*src=["\']([^"\']+\.js[^"\']*)["\']', html_content)
            for js_file in js_files[:3]:
                if not js_file.startswith('http'):
                    js_file = "https://downloaderto.com" + (js_file if js_file.startswith('/') else '/'+js_file)
                try:
                    js_resp = requests.get(js_file, headers=headers, timeout=10)
                    if js_resp.status_code == 200:
                        js_content = js_resp.text
                        if not api_key:
                            for m in re.finditer(pattern_key, js_content, re.IGNORECASE):
                                if len(m.group(1)) == 32:
                                    api_key = m.group(1)
                                    break
                        if not api_url:
                            for m in re.finditer(pattern_url, js_content, re.IGNORECASE):
                                if 'download' in m.group(1):
                                    api_url = m.group(1)
                                    break
                except:
                    continue

        if api_key and api_url:
            return {'api_key': api_key, 'api_url': api_url}
    except Exception as e:
        print(f"⚠️ خطا در استخراج API: {e}")
    return None

# ------------------- دریافت عنوان ویدیو -------------------
def get_video_title(youtube_url):
    video_id = None
    patterns = [
        r'(?:v=|/)([0-9A-Za-z_-]{11})', r'(?:embed/)([0-9A-Za-z_-]{11})',
        r'youtu\.be/([0-9A-Za-z_-]{11})', r'shorts/([0-9A-Za-z_-]{11})'
    ]
    for p in patterns:
        m = re.search(p, youtube_url)
        if m:
            video_id = m.group(1)
            break
    if not video_id:
        return f"Video_{int(time.time())}"

    # oEmbed
    try:
        r = requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json", timeout=10)
        if r.status_code == 200:
            title = r.json().get('title', '')
            if title:
                title = html.unescape(title)
                return sanitize_title(title)
    except:
        pass
    # Fallback noembed
    try:
        r = requests.get(f"https://noembed.com/embed?url=https://www.youtube.com/watch?v={video_id}", timeout=10)
        if r.status_code == 200:
            title = r.json().get('title', '')
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

# ------------------- Polling برای لینک دانلود -------------------
def wait_for_download_link(download_id, max_attempts=25, wait_time=2):
    possible_urls = [
        f"https://p.savenow.to/download/{download_id}",
        f"https://p.lbserver.xyz/download/{download_id}",
    ]
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://downloaderto.com/'}
    for attempt in range(1, max_attempts+1):
        for url in possible_urls:
            try:
                resp = requests.head(url, headers=headers, timeout=8, allow_redirects=True)
                if resp.status_code in [200,302,307]:
                    final_url = resp.url if resp.history else url
                    size = resp.headers.get('content-length', 0)
                    if size and int(size) > 500*1024:
                        return {'url': final_url, 'size_bytes': int(size)}
            except:
                continue
        time.sleep(wait_time)
    return None

# ------------------- دانلود فایل -------------------
def download_file(url, output_path):
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://downloaderto.com/'}
    resp = requests.get(url, headers=headers, stream=True, timeout=60)
    resp.raise_for_status()
    total = int(resp.headers.get('content-length', 0))
    with open(output_path, 'wb') as f:
        downloaded = 0
        for chunk in resp.iter_content(8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                print(f"\r📥 {downloaded/total*100:.1f}%", end='')
    print()
    return output_path

# ------------------- تابع اصلی -------------------
def download_youtube(youtube_url, quality, output_dir):
    quality_map = {"360p":"360","480p":"480","720p":"720","1080p":"1080","best":"best"}
    fmt = quality_map.get(quality, "720")

    # 1. دریافت تنظیمات API (با کش ساده)
    cache_file = Path(tempfile.gettempdir()) / "yt_api_cache.json"
    api_config = None
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                cached = json.load(f)
                if time.time() - cached.get('ts',0) < 86400:
                    api_config = cached
        except:
            pass
    if not api_config:
        api_config = extract_api_config()
        if api_config:
            api_config['ts'] = time.time()
            with open(cache_file, 'w') as f:
                json.dump(api_config, f)
    if not api_config:
        raise Exception("❌ ناتوان در استخراج API از سایت")

    # 2. دریافت عنوان
    title = get_video_title(youtube_url)
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
    filename = f"{safe_title}_{quality}.mp4"
    output_path = Path(output_dir) / filename

    # 3. درخواست به API
    params = {'copyright':'0','format':fmt,'url':youtube_url,'api':api_config['api_key']}
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Referer': 'https://downloaderto.com/'}
    resp = requests.get(api_config['api_url'], params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"API خطا: {resp.status_code}")
    data = resp.json()
    if not data.get('success'):
        raise Exception(f"API خطا: {data.get('error','نامشخص')}")

    download_id = data.get('id')
    print(f"✅ Download ID: {download_id}")

    # 4. Polling
    link_info = wait_for_download_link(download_id)
    if not link_info:
        raise Exception("زمان انتظار برای لینک دانلود تمام شد")

    # 5. دانلود
    print(f"📥 دانلود فایل {filename} ...")
    download_file(link_info['url'], output_path)
    size_mb = output_path.stat().st_size / (1024*1024)
    print(f"✅ ذخیره شد: {output_path} ({size_mb:.2f} MB)")
    return str(output_path), title

# ------------------- اجرای خط فرمان -------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Downloader for GitHub Actions")
    parser.add_argument("--url", required=True, help="YouTube URL")
    parser.add_argument("--quality", default="720p", choices=["360p","480p","720p","1080p","best"])
    parser.add_argument("--output-dir", default=".", help="Directory to save video")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        file_path, video_title = download_youtube(args.url, args.quality, output_dir)
        # خروجی برای استفاده در workflow (فقط مسیر فایل)
        print(f"::set-output name=video_file::{file_path}")
        print(f"::set-output name=video_title::{video_title}")
    except Exception as e:
        print(f"❌ خطا: {e}")
        exit(1)
