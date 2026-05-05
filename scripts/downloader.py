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
# استخراج API از سایت downloaderto (همان کد قبلی)
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
    fallback_apis = [
        'https://p.lbserver.xyz/ajax/download.php',
        'https://p.savenow.to/ajax/download.php',
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
        if config['api_url'] not in fallback_apis:
            fallback_apis.insert(0, config['api_url'])
        config['api_url'] = fallback_apis[0]
        try:
            with open(cache_file, 'w') as f:
                json.dump(config, f)
        except:
            pass
        return config
    return {
        'api_key': '2e716c3914a4f931fdad91ad9e14c6b1',
        'api_url': fallback_apis[0],
        'timestamp': time.time()
    }

# ------------------------------------------------------------
# توابع دریافت عنوان ویدیو (بدون تغییر)
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
# استخراج لینک دانلود از صفحه (تقویت شده)
# ------------------------------------------------------------
def extract_download_link_from_page(download_id, save_debug=True):
    """
    با درخواست به https://downloaderto.com/download/{id}
    لینک نهایی دانلود را از HTML استخراج می‌کند.
    در صورت save_debug=True، HTML را در پوشه debug_html ذخیره می‌کند.
    """
    page_url = f"https://downloaderto.com/download/{download_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://downloaderto.com/',
    }
    try:
        resp = requests.get(page_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"   ⚠️ درخواست صفحه ناموفق: {resp.status_code}")
            return None
        html_content = resp.text

        # ذخیره HTML برای دیباگ
        if save_debug:
            debug_dir = Path("debug_html")
            debug_dir.mkdir(exist_ok=True)
            debug_file = debug_dir / f"download_page_{download_id}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   💾 HTML صفحه ذخیره شد: {debug_file}")

        # الگوهای مختلف برای یافتن لینک دانلود (مرتب‌سازی شده از محتمل‌ترین)
        patterns = [
            # لینک‌های مستقیم mp4
            r'href=["\'](https?://[^"\']+\.mp4)["\']',
            r'href=["\'](https?://[^"\']+\.zip)["\']',
            # لینک‌های حاوی download
            r'href=["\'](https?://[^"\']+/download/[^"\']+)["\']',
            r'data-url=["\'](https?://[^"\']+)["\']',
            # کلیدهای رایج در JSON
            r'downloadUrl["\']\s*:\s*["\']([^"\']+)["\']',
            r'videoUrl["\']\s*:\s*["\']([^"\']+)["\']',
            r'fileUrl["\']\s*:\s*["\']([^"\']+)["\']',
            r'source["\']\s*:\s*["\']([^"\']+\.mp4)["\']',
            # جاوااسکریپت window.location
            r'window\.location\.href\s*=\s*["\']([^"\']+)["\']',
            # لینک در تگ‌های a با کلاس download-btn
            r'<a[^>]+class=["\'][^"\']*download[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                candidate = match.group(1)
                if candidate.startswith('http'):
                    print(f"   ✅ لینک دانلود با الگو پیدا شد: {candidate[:80]}...")
                    return candidate

        # اگر هیچ لینکی پیدا نشد، عنوان صفحه را به عنوان fallback برمی‌گردانیم
        title_match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
        if title_match:
            page_title = title_match.group(1)
            page_title = re.sub(r'\s*[-|]\s*downloaderto\.com.*$', '', page_title, flags=re.IGNORECASE)
            if page_title and len(page_title) > 3:
                print(f"   ℹ️ لینکی یافت نشد، اما عنوان صفحه استخراج شد: {page_title}")
                return page_title   # این عنوان نیست، ولی برای نام فایل بعداً استفاده می‌شود
        return None
    except Exception as e:
        print(f"   ⚠️ خطا در دریافت صفحه: {e}")
        return None

# ------------------------------------------------------------
# Polling هوشمند
# ------------------------------------------------------------
def wait_for_download_link(download_id, max_attempts=20, wait_time=3):
    """
    منتظر می‌ماند تا لینک نهایی در صفحه دانلود ظاهر شود.
    هر wait_time ثانیه یکبار صفحه را چک می‌کند.
    """
    print(f"⏳ شروع هوشمند polling برای Download ID: {download_id}")
    print(f"📊 حداکثر {max_attempts} تلاش، هر {wait_time} ثانیه")
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 تلاش {attempt}/{max_attempts}...")
        download_url = extract_download_link_from_page(download_id)
        if download_url and download_url.startswith('http'):
            # بررسی حجم فایل
            try:
                head_resp = requests.head(download_url, timeout=8, allow_redirects=True)
                size = head_resp.headers.get('content-length', 0)
                if size and int(size) > 500 * 1024:
                    size_str = f"{int(size)/(1024*1024):.1f} MB" if int(size) > 1024*1024 else f"{int(size)/1024:.1f} KB"
                    print(f"✅ لینک آماده شد! حجم: {size_str}")
                    return {
                        'url': download_url,
                        'size': size_str,
                        'size_bytes': int(size),
                        'attempts': attempt
                    }
                else:
                    print(f"✅ لینک پیدا شد (حجم نامشخص یا کمتر از 500KB)")
                    return {
                        'url': download_url,
                        'size': 'نامشخص',
                        'size_bytes': 0,
                        'attempts': attempt
                    }
            except Exception as e:
                print(f"✅ لینک پیدا شد (خطا در دریافت حجم: {e})")
                return {
                    'url': download_url,
                    'size': 'نامشخص',
                    'size_bytes': 0,
                    'attempts': attempt
                }
        elif download_url and not download_url.startswith('http'):
            # ممکن است عنوان صفحه باشد – کاری نمی‌کنیم، فقط چاپ می‌کنیم
            print(f"   ℹ️ عنوان صفحه: {download_url}")
        time.sleep(wait_time)
    
    print(f"❌ پس از {max_attempts} تلاش، لینک پیدا نشد")
    return None

# ------------------------------------------------------------
# دانلود فایل
# ------------------------------------------------------------
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
# فراخوانی API با fallback (برای لینک یوتیوب)
# ------------------------------------------------------------
def call_api_with_fallback(youtube_url, format_code, api_key, api_url_list):
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

# ------------------------------------------------------------
# دانلود مستقیم از لینک downloaderto (بدون نیاز به API)
# ------------------------------------------------------------
def download_from_direct_link(direct_url, output_dir):
    """
    دریافت لینک مانند https://downloaderto.com/download/xyz
    و دانلود ویدیو با polling هوشمند
    """
    match = re.search(r'/download/([A-Za-z0-9]+)', direct_url)
    if not match:
        raise Exception("لینک دانلود معتبر نیست (عدم وجود ID)")
    download_id = match.group(1)
    print(f"🔍 استخراج Download ID: {download_id}")

    # تلاش برای دریافت عنوان از صفحه (برای نام فایل)
    page_content = extract_download_link_from_page(download_id, save_debug=True)
    video_title = None
    if page_content and not page_content.startswith('http'):
        # در این حالت page_content ممکن است عنوان صفحه باشد
        video_title = sanitize_title(page_content)
    if not video_title:
        video_title = f"video_{download_id}"
    print(f"🎬 عنوان ویدیو (پیش‌فرض): {video_title}")

    # منتظر لینک نهایی
    link_info = wait_for_download_link(download_id, max_attempts=20, wait_time=3)
    if not link_info:
        manual_url = f"https://downloaderto.com/download/{download_id}"
        raise Exception(f"زمان انتظار تمام شد. لینک دستی: {manual_url}")

    # دانلود
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)
    filename = f"{safe_title}_direct.mp4"
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    result = download_file(link_info['url'], filename, output_path)
    if not result['success']:
        raise Exception("دانلود ناموفق")
    return result['filepath'], video_title

# ------------------------------------------------------------
# تابع اصلی (تشخیص خودکار نوع لینک)
# ------------------------------------------------------------
def download_youtube_video(youtube_url, quality, output_dir):
    # تشخیص لینک مستقیم downloaderto
    if 'downloaderto.com/download/' in youtube_url or re.match(r'https?://[^/]+/download/[A-Za-z0-9]+', youtube_url):
        print("🔗 لینک از نوع downloaderto.com تشخیص داده شد. دانلود مستقیم...")
        return download_from_direct_link(youtube_url, output_dir)

    # در غیر این صورت، لینک یوتیوب
    quality_map = {"360p": "360", "480p": "480", "720p": "720", "1080p": "1080", "بهترین": "best"}
    format_code = quality_map.get(quality, "720")

    api_config = get_api_config(force_refresh=False)
    api_key = api_config['api_key']
    api_url_list = [
        'https://p.lbserver.xyz/ajax/download.php',
        'https://p.savenow.to/ajax/download.php',
    ]
    extracted_url = api_config.get('api_url')
    if extracted_url and extracted_url not in api_url_list:
        api_url_list.insert(0, extracted_url)

    print(f"🔑 API Key: {api_key[:16]}...")
    video_title = get_video_title(youtube_url)
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)
    filename = f"{safe_title}_{quality}.mp4"

    data = call_api_with_fallback(youtube_url, format_code, api_key, api_url_list)
    if not data:
        raise Exception("تمامی API endpoint‌ها پاسخگو نبودند. لطفاً بعداً تلاش کنید.")

    download_id = data.get('id')
    print(f"✅ Download ID از API: {download_id}")

    link_info = wait_for_download_link(download_id, max_attempts=20, wait_time=3)
    if not link_info:
        manual_url = f"https://downloaderto.com/download/{download_id}"
        text_file = Path(output_dir) / "download_link.txt"
        with open(text_file, 'w') as f:
            f.write(f"ویدیو آماده نشد. لطفاً به صورت دستی از لینک زیر دانلود کنید:\n{manual_url}")
        raise Exception(f"زمان انتظار تمام شد. لینک دستی در فایل {text_file} ذخیره شد.")

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
    parser = argparse.ArgumentParser(description="دانلود از یوتیوب یا لینک مستقیم downloaderto")
    parser.add_argument("--url", required=True, help="لینک یوتیوب یا لینک downloaderto.com/download/...")
    parser.add_argument("--quality", default="720p", help="کیفیت (فقط برای یوتیوب معنی دارد)")
    parser.add_argument("--output-dir", default=".", help="پوشه خروجی")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        file_path, title = download_youtube_video(args.url, args.quality, out_dir)
        # خروجی برای GitHub Actions (از GITHUB_OUTPUT استفاده می‌کند)
        github_output = os.getenv("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write(f"video_file={file_path}\n")
                f.write(f"video_title={title}\n")
        else:
            # حالت محلی
            print(f"::set-output name=video_file::{file_path}")
            print(f"::set-output name=video_title::{title}")
        print(f"✅ موفق: {file_path}")
    except Exception as e:
        print(f"❌ خطا: {e}")
        # در صورت وجود فایل لینک دستی، آن را نمایش می‌دهیم
        link_file = out_dir / "download_link.txt"
        if link_file.exists():
            print(f"📄 لینک دستی در فایل {link_file} ذخیره شده است.")
        exit(1)
