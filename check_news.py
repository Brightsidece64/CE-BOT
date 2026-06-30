"""
สคริปต์เช็คข่าวสารใหม่จากเว็บ ce.kmitl.ac.th แล้วส่งแจ้งเตือนเข้า LINE
ออกแบบให้รันผ่าน GitHub Actions (ใช้ Playwright เพราะเว็บเป็น React SPA)
"""

import os
import sys
import json
import hashlib
from playwright.sync_api import sync_playwright

# ---------- ตั้งค่า ----------
TARGET_URL = "https://www.ce.kmitl.ac.th/"
STATE_FILE = "last_news.json"

# CSS selector ของส่วนที่แสดงหัวข้อข่าว - ต้องปรับตามโครงสร้างจริงของเว็บ
# ถ้าไม่แน่ใจ ให้ปล่อยเป็นค่า default นี้ก่อน สคริปต์จะดึงข้อความทั้งหน้ามาเทียบแทน
NEWS_SELECTOR = None  # เช่น "div.news-item h3" ถ้ารู้ selector ที่แน่นอน

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")


def fetch_news_text():
    """เปิดเว็บด้วย headless browser แล้วดึงข้อความข่าวสารออกมา"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
        # รอให้ JS render เนื้อหาเสร็จ (ปรับเวลาได้ถ้าเว็บโหลดช้า)
        page.wait_for_timeout(3000)

        if NEWS_SELECTOR:
            elements = page.query_selector_all(NEWS_SELECTOR)
            text = "\n".join(el.inner_text().strip() for el in elements)
        else:
            # ถ้ายังไม่รู้ selector ที่แน่ชัด ใช้ข้อความทั้งหน้าแทนไปก่อน
            text = page.inner_text("body")

        browser.close()
        return text


def load_last_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"hash": None, "snippet": ""}


def save_state(hash_value, snippet):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"hash": hash_value, "snippet": snippet}, f, ensure_ascii=False, indent=2)


def send_line_message(message):
    import urllib.request

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message[:1000]}],  # LINE จำกัดความยาวข้อความ
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print("LINE notify status:", resp.status)
    except Exception as e:
        print("ส่ง LINE ไม่สำเร็จ:", e)
        sys.exit(1)


def main():
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print("ขาดตัวแปร LINE_CHANNEL_ACCESS_TOKEN หรือ LINE_USER_ID")
        sys.exit(1)

    current_text = fetch_news_text()
    current_hash = hashlib.sha256(current_text.encode("utf-8")).hexdigest()

    last_state = load_last_state()

    if last_state["hash"] is None:
        # รันครั้งแรก แค่บันทึก state ไว้ ยังไม่ส่งแจ้งเตือน (กันเด้งครั้งแรกตอนตั้งระบบ)
        print("รันครั้งแรก บันทึกสถานะเริ่มต้น ยังไม่ส่งแจ้งเตือน")
        save_state(current_hash, current_text[:300])
        return

    if current_hash != last_state["hash"]:
        print("ตรวจพบการเปลี่ยนแปลง ส่งแจ้งเตือน LINE")
        message = f"📢 เว็บ ce.kmitl.ac.th มีการอัปเดตใหม่!\nเข้าไปดูที่: {TARGET_URL}"
        send_line_message(message)
        save_state(current_hash, current_text[:300])
    else:
        print("ไม่มีการเปลี่ยนแปลง")


if __name__ == "__main__":
    main()
