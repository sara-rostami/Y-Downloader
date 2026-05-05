#!/usr/bin/env python3
import subprocess
import sys
import re
import os
import time
from pathlib import Path

def sanitize_title(title):
    """پاک‌سازی عنوان برای استفاده در نام فایل"""
    title = re.sub(r'[<>:"/\\|?*]', '_', title)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 100:
        title = title[:97] + "..."
    return title

def download_youtube(url, quality, output_dir):
    """
    دانلود ویدیو با استفاده از yt-dlp و احراز هویت OAuth
    """
    quality_map = {
        "360p": "best[height<=360]",
        "480p": "best[height<=480]",
        "720p": "best[height<=720]",
        "1080p": "best[height<=1080]",
        "best": "best"
    }
    format_selector = quality_map.get(quality, "best[height<=720]")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # دریافت عنوان ویدیو (بدون نیاز به احراز هویت)
    try:
        title = subprocess.check_output([
            "yt-dlp", "--get-title", "--no-warnings", url
        ], text=True).strip()
        safe_title = sanitize_title(title)
    except Exception as e:
        print(f"⚠️ خطا در دریافت عنوان: {e}")
        safe_title = f"video_{int(time.time())}"
        title = safe_title

    output_template = output_dir / f"{safe_title}_{quality}.mp4"

    # دستور اصلی با OAuth
    cmd = [
        "yt-dlp",
        "-f", format_selector,
        "-o", str(output_template),
        "--no-playlist",
        "--restrict-filenames",
        "--username", "oauth",          # استفاده از OAuth
        "--netrc",                      # استفاده از فایل netrc
        url
    ]
    
    print(f"📥 دانلود با کیفیت {quality} و احراز هویت OAuth...")
    print("ℹ️  در اولین اجرا، ممکن است نیاز به تأیید دستگاه باشد. راهنما در لاگ نمایش داده می‌شود.")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # اگر خطا خورد، پیغام خطا را چاپ کن
    if result.returncode != 0:
        print("❌ خروجی خطا:")
        print(result.stderr)
        raise Exception("دانلود ناموفق. (ممکن است نیاز به تأیید دستگاه OAuth باشد)")

    # بررسی وجود فایل خروجی
    if not output_template.exists():
        files = list(output_dir.glob(f"{safe_title}*.mp4"))
        if files:
            output_template = files[0]
        else:
            raise Exception("فایل خروجی پیدا نشد")

    # محاسبه حجم
    size_mb = output_template.stat().st_size / (1024*1024)
    print(f"✅ دانلود شد: {output_template.name} ({size_mb:.2f} MB)")

    # خروجی برای GitHub Actions
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"video_file={output_template}\n")
            f.write(f"video_title={title}\n")
    else:
        # برای اجرای محلی
        print(f"::set-output name=video_file::{output_template}")
        print(f"::set-output name=video_title::{title}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Downloader with OAuth")
    parser.add_argument("--url", required=True, help="YouTube URL")
    parser.add_argument("--quality", default="720p", help="Quality: 360p,480p,720p,1080p,best")
    parser.add_argument("--output-dir", default=".", help="Output directory")
    args = parser.parse_args()
    
    download_youtube(args.url, args.quality, args.output_dir)
