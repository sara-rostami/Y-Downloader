#!/usr/bin/env python3
import subprocess
import sys
import re
import os
from pathlib import Path

def sanitize_title(title):
    """تمیز کردن عنوان برای نام فایل"""
    title = re.sub(r'[<>:"/\\|?*]', '_', title)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 100:
        title = title[:97] + "..."
    return title

def download_youtube(url, quality, output_dir):
    """
    دانلود ویدیو با yt-dlp
    کیفیت: 360p, 480p, 720p, 1080p, best
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

    # دریافت عنوان ویدیو (قبل از دانلود)
    cmd_title = [
        "yt-dlp",
        "--get-title",
        "--no-warnings",
        url
    ]
    try:
        title = subprocess.check_output(cmd_title, text=True).strip()
        safe_title = sanitize_title(title)
    except Exception as e:
        print(f"⚠️ ناتوان در دریافت عنوان: {e}")
        safe_title = f"video_{int(time.time())}"

    output_template = output_dir / f"{safe_title}_{quality}.mp4"

    # دستور دانلود
    cmd = [
        "yt-dlp",
        "-f", format_selector,
        "-o", str(output_template),
        "--no-playlist",
        "--no-warnings",
        "--restrict-filenames",  # کاراکترهای مجاز
        url
    ]

    print(f"📥 دانلود ویدیو با کیفیت {quality}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        # تلاش مجدد با کیفیت پایین‌تر در صورت خطا
        print("⚠️ خطا در دانلود، تلاش با بهترین کیفیت موجود...")
        cmd_fallback = [
            "yt-dlp",
            "-f", "best",
            "-o", str(output_template),
            "--no-playlist",
            url
        ]
        result = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ خروجی خطای yt-dlp:")
            print(result.stderr)
            raise Exception("دانلود ناموفق")

    # بررسی اینکه فایل واقعاً ساخته شده
    if not output_template.exists():
        # ممکن است yt-dlp نام فایل را تغییر داده باشد (مثلاً اضافه کردن .mp4)
        files = list(output_dir.glob(f"{safe_title}*.mp4"))
        if files:
            output_template = files[0]
        else:
            raise Exception("فایل خروجی پیدا نشد")

    # محاسبه حجم
    size_mb = output_template.stat().st_size / (1024*1024)
    print(f"✅ دانلود شد: {output_template.name} ({size_mb:.2f} MB)")

    # خروجی برای GitHub Actions
    print(f"::set-output name=video_file::{output_template}")
    print(f"::set-output name=video_title::{title}")

if __name__ == "__main__":
    import argparse
    import time
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--quality", default="720p")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    download_youtube(args.url, args.quality, args.output_dir)
