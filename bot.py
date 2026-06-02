import os
import json
import requests
import gspread
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from google.oauth2.service_account import Credentials

LINE_ACCESS_TOKEN = os.environ.get("LINE_TOKEN")
SHEET_URL = os.environ.get("SHEET_URL")


def calculate_due_date(start_date_str, period, freq_type, freq_val):
    base_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    steps = (period - 1) * freq_val
    if freq_type == "รายวัน": return base_date + relativedelta(days=steps)
    elif freq_type == "รายสัปดาห์": return base_date + relativedelta(weeks=steps)
    elif freq_type == "รายเดือน": return base_date + relativedelta(months=steps)
    return base_date


def get_period_date(s, period):
    """คืนวันที่ของงวดที่ระบุ โดยใช้ 'วันจ่ายจริงรายงวด' (period_dates) ก่อน
    ถ้าไม่มี (วงเก่า) ค่อยถอยไปคำนวณจากความถี่ — ต้องตรงกับ get_period_date ในแอป v9"""
    pdates = s.get("period_dates")
    if pdates and 1 <= period <= len(pdates):
        try:
            return datetime.strptime(pdates[period - 1], "%Y-%m-%d").date()
        except:
            pass
    try:
        return calculate_due_date(s["start_date"], period, s["freq_type"], s["freq_val"])
    except:
        return None


def _infer_base_per_hand(s, num_hands):
    """เดายอดส่งฐานต่อมือจากประวัติ เมื่อ base_payment เป็น 0"""
    for h in s.get("history", []):
        if str(h.get("win", "")).strip() == "คนอื่น":
            return float(h.get("paid", 0) or 0) / max(1, num_hands)
    if s.get("history"):
        return float(s["history"][0].get("paid", 0) or 0) / max(1, num_hands)
    return 0.0


def _base_per_hand(s, num_hands):
    base = float(s.get("base_payment", 0) or 0)
    return base if base > 0 else _infer_base_per_hand(s, num_hands)


def compute_due_amount(s):
    """ยอดที่ต้องจ่ายของงวดปัจจุบัน (รวมทุกมือ) — ตรรกะเดียวกับแอป v9
    วงเปีย: ฐาน×มือ + ดอกของทุกมือที่ 'เราเปียเอง' ไปแล้ว (ทบกันทุกงวดจนจบ)"""
    num_hands = int(s.get("num_hands", 1))
    if (s.get("share_type") or "แชร์เปีย (ประมูลดอกเบี้ย)").startswith("แชร์เปีย"):
        base = _base_per_hand(s, num_hands)
        own_bids = sum(float(h.get("bid", 0) or 0) for h in s.get("history", []) if str(h.get("win", "")).strip() == "ฉันเปียเอง")
        return base * num_hands + own_bids
    # วงขั้นบันได (รองรับวงเก่าที่ยังไม่มี hands_data)
    hands_data = s.get("hands_data", [])
    if not hands_data:
        hands_data = [{"payment": s.get("my_fixed_payment", 0.0)}]
    return sum(float(hd.get("payment", 0) or 0) for hd in hands_data)


def get_gsheet_data():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = json.loads(os.environ.get("GCP_CREDENTIALS"))
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(SHEET_URL).sheet1
    data_str = sheet.acell('A1').value
    return json.loads(data_str) if data_str else {"shares": []}


def main():
    print("เริ่มการเช็กข้อมูลประจำวัน...")
    try:
        data = get_gsheet_data()
    except Exception as e:
        print(f"เชื่อมต่อ Google Sheets ไม่สำเร็จ: {e}")
        return

    today = date.today()
    due_today_msgs = []
    total_due_pea = 0

    for s in data.get("shares", []):
        try:
            if s.get("current_period", 1) > s.get("total_periods", 0):
                continue
            due_date = get_period_date(s, s["current_period"])
            if due_date != today:
                continue

            owner_name = s.get("owner", "ไม่ระบุชื่อ")
            share_type = s.get("share_type") or "แชร์เปีย (ประมูลดอกเบี้ย)"
            num_hands = int(s.get("num_hands", 1))
            due_amt = compute_due_amount(s)

            if share_type.startswith("แชร์เปีย"):
                due_today_msgs.append(f"👤 {owner_name} | วง {s['name']} ({num_hands} มือ) งวด {s['current_period']}: {due_amt:,.2f} บาท\n")
                total_due_pea += due_amt
            else:
                due_today_msgs.append(f"👤 {owner_name} | วง {s['name']} [ขั้นบันได {num_hands} มือ] งวด {s['current_period']}: {due_amt:,.2f} บาท\n")
        except Exception as e:
            print(f"ข้ามวง {s.get('name', '?')} เพราะ error: {e}")

    if due_today_msgs:
        msg = f"🎀 สรุปแชร์ที่ต้องชำระวันนี้ ({today.strftime('%d/%m/%Y')})\n\n" + "".join(due_today_msgs)
        if total_due_pea > 0:
            msg += f"\n💰 ยอดรวม(เฉพาะวงเปีย): {total_due_pea:,.2f} บาท"

        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'}
        payload = {"messages": [{"type": "text", "text": msg}]}

        res = requests.post('https://api.line.me/v2/bot/message/broadcast', headers=headers, data=json.dumps(payload))
        if res.status_code == 200:
            print("ส่ง LINE Broadcast สำเร็จ!")
        else:
            print(f"ส่ง LINE ไม่สำเร็จ: {res.text}")
    else:
        print("วันนี้ไม่มีกำหนดชำระ")


if __name__ == "__main__":
    main()
