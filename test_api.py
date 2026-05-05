import gradio as gr
import requests
import json
import time
import re
import os
import tempfile
from pathlib import Path
import html as html_lib

# ==================== استخراج خودکار API از سایت ====================
def extract_api_config_from_website():
    """استخراج API key و endpoint از صفحه اصلی downloaderto"""
    try:
        print("\n" + "=" * 60)
        print("🔍 استخراج تنظیمات API از سایت downloaderto...")
        print("=" * 60)

        site_url = "https://downloaderto.com/enHF/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        }
        response = requests.get(site_url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"❌ خطا در دریافت صفحه: {response.status_code}")
            return None

        html_content = response.text

        # استخراج API Key (۳۲ کاراکتر hex)
        api_key = None
        matches = re.findall(r'["\']([a-f0-9]{32})["\']', html_content, re.IGNORECASE)
        for match in matches:
            if len(match) == 32 and all(c in '0123456789abcdef' for c in match):
                api_key = match
                print(f"✅ API Key: {api_key}")
                break

        # استخراج API URL
        api_url = None
        url_match = re.search(r'(https?://[a-z0-9\.-]+/ajax/download\.php)', html_content, re.IGNORECASE)
        if url_match:
            api_url = url_match.group(1)
            print(f"✅ API URL: {api_url}")

        if api_key and api_url:
            print("✅ تنظیمات API با موفقیت استخراج شد!")
            return {
                'api_key': api_key,
                'api_url': api_url,
                'timestamp': time.time()
            }
        else:
            print("⚠️ استخراج ناقص")
            return None

    except Exception as e:
        print(f"❌ خطا در استخراج API: {str(e)}")
        return None


def get_api_config(force_refresh=False):
    """دریافت تنظیمات API با cache یک روزه"""
    cache_file = Path(tempfile.gettempdir()) / "downloaderto_api_cache.json"

    if not force_refresh and cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            age = time.time() - cached.get('timestamp', 0)
            if age < 24 * 3600:
                print(f"📦 استفاده از API cache (سن: {age/3600:.1f} ساعت)")
                return cached
        except:
            pass

    config = extract_api_config_from_website()
    if config:
        try:
            with open(cache_file, 'w') as f:
                json.dump(config, f)
            print("💾 تنظیمات در cache ذخیره شد")
        except:
            pass
        return config

    # fallback
    print("⚠️ استفاده از API پیش‌فرض")
    return {
        'api_key': 'e1f31df4f6424efab5eb606004289ced',
        'api_url': 'https://p.savenow.to/ajax/download.php',
        'timestamp': time.time()
    }


# ==================== استخراج عنوان ویدیو ====================
def get_video_title(youtube_url):
    """دریافت عنوان ویدیو از YouTube oEmbed"""
    print("🎬 دریافت عنوان ویدیو...")
    video_id = None
    patterns = [
        r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed/)([0-9A-Za-z_-]{11})',
        r'youtu\.be/([0-9A-Za-z_-]{11})',
        r'shorts/([0-9A-Za-z_-]{11})',
    ]
    for pat in patterns:
        match = re.search(pat, youtube_url)
        if match:
            video_id = match.group(1)
            break

    if not video_id:
        return f"Video_{int(time.time())}"

    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        resp = requests.get(oembed_url, timeout=10)
        if resp.status_code == 200:
            title = resp.json().get('title', '')
            if title:
                title = html_lib.unescape(title)
                title = re.sub(r'\s*-\s*YouTube\s*$', '', title, flags=re.IGNORECASE)
                title = re.sub(r'[<>:"/\\|?*]', ' ', title)
                title = re.sub(r'\s+', ' ', title).strip()[:200]
                print(f"✅ عنوان: {title}")
                return title
    except:
        pass

    return f"YouTube_{video_id}"


# ==================== دریافت لینک نهایی از Progress API ====================
def wait_for_download_url(progress_url, max_attempts=15, wait_time=2):
    """Polling روی progress_url تا دریافت download_url"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://downloaderto.com/',
        'Accept': 'application/json, text/plain, */*'
    }

    print(f"⏳ Polling روی {progress_url}")
    for attempt in range(1, max_attempts + 1):
        print(f"🔄 تلاش {attempt}/{max_attempts}...")
        try:
            resp = requests.get(progress_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('download_url'):
                    durl = data['download_url']
                    print(f"✅ لینک دانلود دریافت شد: {durl}")
                    return durl
                # گاهی progress کامل است ولی download_url نیست
                if data.get('progress', 0) >= 1000:
                    print(f"⚠️ Progress کامل است اما download_url خالی. پاسخ: {data}")
        except Exception as e:
            print(f"⚠️ خطا: {e}")
        time.sleep(wait_time)
    print("❌ بعد از چند تلاش download_url دریافت نشد")
    return None


def download_file(download_url, filename, output_dir):
    """دانلود فایل ویدیو"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://downloaderto.com/',
        'Accept': 'video/mp4,video/*,*/*;q=0.8'
    }

    try:
        print(f"📥 دانلود: {filename}")
        response = requests.get(download_url, headers=headers, stream=True, timeout=60, allow_redirects=True)
        response.raise_for_status()

        filepath = output_dir / filename
        total = int(response.headers.get('content-length', 0))

        with open(filepath, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        print(f"📥 {downloaded/total*100:.1f}%", end='\r')

        actual_size = filepath.stat().st_size
        if actual_size < 1024*1024:
            size_str = f"{actual_size/1024:.1f} KB"
        elif actual_size < 1024*1024*1024:
            size_str = f"{actual_size/(1024*1024):.1f} MB"
        else:
            size_str = f"{actual_size/(1024*1024*1024):.2f} GB"

        print(f"\n✅ دانلود کامل: {filepath.name} ({size_str})")
        return {'success': True, 'filepath': str(filepath), 'filename': filepath.name, 'size': size_str}
    except Exception as e:
        print(f"❌ خطای دانلود: {e}")
        return {'success': False, 'error': str(e)}


def cleanup_old_files(download_dir, max_files=5):
    """حذف فایل‌های قدیمی"""
    try:
        files = sorted(download_dir.glob("*.mp4"), key=lambda x: x.stat().st_ctime, reverse=True)
        for f in files[max_files:]:
            f.unlink()
            print(f"🧹 حذف {f.name}")
    except:
        pass


# ==================== تابع اصلی دانلود ====================
def download_youtube_video(youtube_url, quality, enable_preview):
    quality_map = {"360p": "360", "480p": "480", "720p": "720", "1080p": "1080", "بهترین": "best"}
    format_code = quality_map.get(quality, "720")

    api_config = get_api_config()
    api_key = api_config['api_key']
    api_url = api_config['api_url']

    video_title = get_video_title(youtube_url)

    print("📤 درخواست به API اصلی...")
    params = {'copyright': '0', 'format': format_code, 'url': youtube_url, 'api': api_key}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://downloaderto.com/',
        'Accept': 'application/json'
    }

    try:
        resp = requests.get(api_url, params=params, headers=headers, timeout=30)
        if resp.status_code != 200:
            # تلاش برای به‌روزرسانی
            new_cfg = get_api_config(force_refresh=True)
            if new_cfg:
                api_key = new_cfg['api_key']
                api_url = new_cfg['api_url']
                params['api'] = api_key
                resp = requests.get(api_url, params=params, headers=headers, timeout=30)
                if resp.status_code != 200:
                    return None, f"❌ خطای API: {resp.status_code}", None
            else:
                return None, f"❌ خطای API: {resp.status_code}", None

        data = resp.json()
        if not data.get('success'):
            return None, f"❌ API: {data.get('error', 'نامشخص')}", None

        progress_url = data.get('progress_url')
        if not progress_url:
            return None, "❌ progress_url یافت نشد", None

        print(f"🔗 Progress URL: {progress_url}")
        download_url = wait_for_download_url(progress_url)

        if not download_url:
            return None, f"⏱️ زمان دریافت لینک تمام شد. عنوان: {video_title}", None

        # دانلود فایل
        download_dir = Path(tempfile.gettempdir()) / "youtube_downloads"
        download_dir.mkdir(exist_ok=True)
        cleanup_old_files(download_dir, max_files=3)

        safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)
        filename = f"{safe_title}_{quality}.mp4"
        result = download_file(download_url, filename, download_dir)

        preview = None
        if enable_preview and result.get('success') and os.path.exists(result['filepath']):
            preview = result['filepath']

        if result.get('success'):
            info = f"""✅ دانلود موفق!
📝 عنوان: {video_title}
📊 کیفیت: {quality}
💾 حجم: {result['size']}
📂 فایل: {result['filename']}"""
            return {'title': video_title, 'file': result['filepath'], 'filename': result['filename'],
                    'size': result['size'], 'url': download_url}, info, preview
        else:
            info = f"""⚠️ دانلود خودکار ناموفق بود
📝 عنوان: {video_title}
🔗 لینک مستقیم: {download_url}
💡 می‌توانید با مرورگر و Referer دانلود کنید."""
            return {'title': video_title, 'url': download_url}, info, preview

    except Exception as e:
        return None, f"❌ خطا: {str(e)}", None


# ==================== رابط کاربری Gradio ====================
with gr.Blocks(title="YouTube Downloader - Progress API", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎬 YouTube Video Downloader")
    gr.Markdown("### روش جدید Progress API – استخراج خودکار و لینک مستقیم")

    with gr.Row():
        with gr.Column(scale=1):
            url_input = gr.Textbox(label="🔗 لینک یوتیوب", placeholder="https://www.youtube.com/watch?v=...")
            quality_select = gr.Dropdown(label="📊 کیفیت", choices=["360p", "480p", "720p", "1080p", "بهترین"], value="720p")
            preview_checkbox = gr.Checkbox(label="🎥 نمایش پیش‌نمایش", value=False)
            download_btn = gr.Button("⬇️ دانلود", variant="primary")
            refresh_api_btn = gr.Button("🔄 به‌روزرسانی API", variant="secondary")
            gr.Markdown("""
            ### ✨ ویژگی‌ها
            - استخراج خودکار API از سایت
            - استفاده از progress_url
            - دانلود با Referer صحیح
            - Cache ۲۴ ساعته
            """)

        with gr.Column(scale=2):
            info_output = gr.Textbox(label="📋 اطلاعات", lines=12, interactive=False)
            with gr.Row():
                size_output = gr.Textbox(label="💾 حجم", scale=1)
                status_output = gr.Textbox(label="✅ وضعیت", scale=1)
            link_output = gr.Textbox(label="🔗 لینک مستقیم", interactive=False)
            file_output = gr.File(label="📁 فایل دانلود شده")
            video_output = gr.Video(label="🎥 پیش‌نمایش", height=400)

    # دکمه‌های تست سریع
    with gr.Row():
        test1_btn = gr.Button("تست ویدیو Me at the zoo")
        test2_btn = gr.Button("تست YouTube Short")

    @download_btn.click(inputs=[url_input, quality_select, preview_checkbox],
                        outputs=[info_output, size_output, status_output, link_output, file_output, video_output])
    def handle_download(url, quality, enable_preview):
        if not url:
            return "❌ لینک را وارد کنید", "", "❌", "", None, None
        yield "🚀 شروع...", "", "⏳ در حال پردازش", "", None, None
        result, info, preview = download_youtube_video(url, quality, enable_preview)
        if not result:
            yield info, "", "❌ خطا", "", None, None
            return
        size = result.get('size', '')
        link = result.get('url', '')
        file = result.get('file')
        status = "✅ موفق" if file and os.path.exists(file) else "⚠️ فقط لینک"
        yield info, size, status, link, file, preview

    @refresh_api_btn.click(outputs=[info_output])
    def refresh_api():
        config = get_api_config(force_refresh=True)
        if config:
            return f"✅ API به‌روزرسانی شد!\nKey: {config['api_key'][:16]}...\nURL: {config['api_url']}"
        return "❌ خطا در به‌روزرسانی"

    test1_btn.click(outputs=[url_input, quality_select, preview_checkbox],
                    fn=lambda: ("https://www.youtube.com/watch?v=jNQXAC9IVRw", "360p", False))
    test2_btn.click(outputs=[url_input, quality_select, preview_checkbox],
                    fn=lambda: ("https://www.youtube.com/shorts/cPuS6WPZjWI", "720p", False))

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
