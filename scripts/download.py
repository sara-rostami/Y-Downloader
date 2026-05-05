#!/usr/bin/env python3
import subprocess
import sys
import re
import os
import time
from pathlib import Path

def sanitize_title(title):
    title = re.sub(r'[<>:"/\\|?*]', '_', title)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 100:
        title = title[:97] + "..."
    return title

def download_youtube(url, quality, output_dir):
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

    # دریافت عنوان
    try:
        title = subprocess.check_output([
            "yt-dlp", "--get-title", "--no-warnings", url
        ], text=True).strip()
        safe_title = sanitize_title(title)
    except:
        safe_title = f"video_{int(time.time())}"
        title = safe_title

    output_template = output_dir / f"{safe_title}_{quality}.mp4"

    cmd = [
        "yt-dlp",
        "-f", format_selector,
        "-o", str(output_template),
        "--no-playlist",
        "--restrict-filenames",
        url
    ]
    print(f"📥 دانلود با کیفیت {quality}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        # fallback به best
        print("⚠️ تلاش با best کیفیت...")
        cmd_fallback = [
            "yt-dlp", "-f", "best",
            "-o", str(output_template),
            "--no-playlist", url
        ]
        result = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ خطا:", result.stderr)
            raise Exception("دانلود ناموفق")

    if not output_template.exists():
        files = list(output_dir.glob(f"{safe_title}*.mp4"))
        if files:
            output_template = files[0]
        else:
            raise Exception("فایل پیدا نشد")

    size_mb = output_template.stat().st_size / (1024*1024)
    print(f"✅ دانلود شد: {output_template.name} ({size_mb:.2f} MB)")

    # ==================== خروجی برای GitHub Actions ====================
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"video_file={output_template}\n")
            f.write(f"video_title={title}\n")
    else:
        # Fallback برای اجرای محلی
        print(f"::set-output name=video_file::{output_template}")
        print(f"::set-output name=video_title::{title}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--quality", default="720p")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    download_youtube(args.url, args.quality, args.output_dir)
