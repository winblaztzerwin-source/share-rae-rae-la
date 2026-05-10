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
        if s["current_period"] <= s["total_periods"]:
            due_date = calculate_due_date(s["start_date"], s["current_period"], s["freq_type"], s["freq_val"])
            if due_date == today:
                owner_name = s.get("owner", "ไม่ระบุชื่อ")
                share_type = s.get("share_type", "แชร์เปีย")
                num_hands = int(s.get("num_hands", 1))
                
                if share_type.startswith("แชร์เปีย"):
                    due_amt = (s["base_payment"] * num_hands) + sum(float(h["bid"]) for h in s["history"] if h.get("win") == "ฉันเปียเอง")
                    due_today_msgs.append(f"👤 {owner_name} | วง {s['name']} ({num_hands} มือ) งวด {s['current_period']}: {due_amt:,.2f} บาท\n")
                    total_due_pea += due_amt
                else:
                    # 🔴 เพิ่มโค้ดรองรับวงขั้นบันไดที่สร้างไว้ตั้งแต่เวอร์ชันเก่า
                    hands_data = s.get("hands_data", [])
                    if not hands_data:
                        hands_data = [{"payment": s.get("my_fixed_payment", 0.0)}]
                        
                    due_amt = sum(float(hd["payment"]) for hd in hands_data)
                    due_today_msgs.append(f"👤 {owner_name} | วง {s['name']} [ขั้นบันได {num_hands} มือ] งวด {s['current_period']}: {due_amt:,.2f} บาท\n")

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
