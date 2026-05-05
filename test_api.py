import requests, re, time, base64, json, sys
from pathlib import Path

# ====================== استخراج API ======================
def extract_api_config():
    print("="*60)
    print("مرحله ۱: استخراج API از سایت")
    print("="*60)
    try:
        url = "https://downloaderto.com/enHF/"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"❌ status {resp.status_code}")
            return None, None
        html = resp.text

        api_key = re.search(r'["\']([a-f0-9]{32})["\']', html)
        api_key = api_key.group(1) if api_key else None
        api_url = re.search(r'(https?://[a-z0-9\.-]+/ajax/download\.php)', html)
        api_url = api_url.group(1) if api_url else None

        print(f"API Key: {api_key}")
        print(f"API URL: {api_url}")
        return api_key, api_url
    except Exception as e:
        print(f"❌ {e}")
        return None, None

# ====================== درخواست API و استخراج لینک ======================
def get_download_info(api_key, api_url):
    print("\n"+"="*60)
    print("مرحله ۲: درخواست به API و تحلیل پاسخ")
    print("="*60)
    if not api_key or not api_url:
        return None

    params = {
        'copyright': '0',
        'format': '360',
        'url': 'https://www.youtube.com/watch?v=jNQXAC9IVRw',
        'api': api_key
    }
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://downloaderto.com/'
    }
    try:
        r = requests.get(api_url, params=params, headers=headers, timeout=30)
        data = r.json()
        print("JSON keys:", list(data.keys()))
        if data.get('success'):
            download_id = data.get('id')
            content_b64 = data.get('content', '')
            print(f"Download ID: {download_id}")
            print(f"Content (first 100 chars): {content_b64[:100]}...")

            # کدگشایی base64
            try:
                decoded_bytes = base64.b64decode(content_b64)
                decoded_html = decoded_bytes.decode('utf-8', errors='ignore')
                print("\n✅ محتوای دیکد شده (اول ۲۰۰۰ کاراکتر):")
                print(decoded_html[:2000])

                # جستجوی لینک های mp4 یا لینک دانلود
                # الگوهای مختلف
                patterns = [
                    r'href=["\'](https?://[^"\']+\.mp4[^"\']*)',
                    r'(https?://[^"\']+/download/[^"\']+)',
                    r'(https?://[^"\']+/file/[^"\']+)',
                    r'(https?://[^"\']+\.mp4[^"\']*)',
                    r'data-url=["\']([^"\']+)["\']',
                    r'download-url=["\']([^"\']+)["\']',
                ]
                found_links = []
                for pat in patterns:
                    matches = re.findall(pat, decoded_html, re.IGNORECASE)
                    for link in matches:
                        if link not in found_links:
                            found_links.append(link)
                            print(f"🔗 لینک احتمالی پیدا شد: {link}")

                if found_links:
                    # برمی‌گردانیم اولین لینک mp4 یا اولین لینک
                    mp4_links = [l for l in found_links if '.mp4' in l.lower()]
                    return mp4_links[0] if mp4_links else found_links[0]
                else:
                    print("⚠️ هیچ لینک دانلودی در content پیدا نشد")
                    # شاید content فقط کارت نمایش باشد و لینک با یک درخواست دیگر بیاید
                    # پس به عنوان fallback، ID را برمی‌گردانیم و بعداً تست می‌کنیم
                    return {'id': download_id, 'content': decoded_html}

            except Exception as e:
                print(f"❌ خطا در دیکد base64: {e}")
                return {'id': download_id}
        else:
            print("❌ API success=false:", data.get('error'))
            return None
    except Exception as e:
        print(f"❌ {e}")
        return None

# ====================== تست لینک ======================
def test_direct_link(link):
    if isinstance(link, dict):  # هنوز لینک کامل نداریم
        print("\n❌ لینک مستقیم یافت نشد. اطلاعات:", link)
        # اینجا می‌توانیم endpointهای جدید را تست کنیم
        return

    print("\n"+"="*60)
    print("مرحله ۳: تست لینک دانلود مستقیم")
    print("="*60)
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://downloaderto.com/'}
        r = requests.head(link, headers=headers, timeout=10, allow_redirects=True)
        size = r.headers.get('content-length', '0')
        final_url = r.url
        print(f"Status: {r.status_code}, Size: {size}")
        if r.status_code in [200, 302] and int(size) > 100000:
            print(f"✅ لینک فعال: {final_url}")
            return final_url
        else:
            print("⚠️ لینک معتبر نیست یا حجم کم است")
            return None
    except Exception as e:
        print(f"❌ {e}")
        return None

# ====================== اجرا ======================
if __name__ == "__main__":
    api_key, api_url = extract_api_config()
    if not api_key or not api_url:
        sys.exit(1)

    result = get_download_info(api_key, api_url)
    if result:
        if isinstance(result, str):
            # لینک مستقیم
            direct = test_direct_link(result)
            if direct:
                print(f"\n🎉 موفقیت! لینک دانلود: {direct}")
            else:
                print("\n⚠️ لینک پیدا شده در content قابل دانلود نبود.")
        else:
            # لینک پیدا نشد، دوباره polling را با ID امتحان می‌کنیم اما با تاخیر بیشتر و endpoint جدید
            download_id = result.get('id')
            if download_id:
                print(f"\n🔄 تلاش دوباره برای polling با ID {download_id}")
                # ممکن است لینک در آدرس دیگری ساخته شود
                test_urls = [
                    f"https://p.savenow.to/dl/{download_id}",
                    f"https://downloaderto.com/download/{download_id}",
                    f"https://downloaderto.com/file/{download_id}",
                    f"https://p.savenow.to/file/{download_id}",
                ]
                for url in test_urls:
                    try:
                        r = requests.head(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
                        if r.status_code == 200:
                            print(f"✅ {url} در دسترس است")
                    except:
                        pass
    else:
        print("❌ دریافت اطلاعات دانلود ناموفق.")
    print("\n🏁 پایان")
