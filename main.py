import streamlit as st
import pandas as pd
import json
import os
import re
import math
import requests
import gspread
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from google.oauth2.service_account import Credentials

# ====================================================
# 🔴 จุดที่ 1: ตั้งค่า LINE Notify และ Google Sheets
# ====================================================
LINE_ACCESS_TOKEN = "xQr8uwbfyrux9WgXpyuNgtOZY+nlP3wvJUqZKwBaLnqTXZeDa1Ph4FiN2dGLuY7W9aRLn/4Yv0wtNt5mjvBLCDO6a3scT1IfwL9rRxoHumHsYD9HyYfQPZifZWNCUcY8zkO1WmX9w23stY+d7Ck1MgdB04t89/1O/w1cDnyilFU="
SHEET_URL = "https://docs.google.com/spreadsheets/d/1HNNJT-rFCR55FNdvMtWyKIyJrE0ZgKecYKoFAsUwdfI/edit?usp=sharing"

def send_line_message(message):
    if not LINE_ACCESS_TOKEN or LINE_ACCESS_TOKEN == "ใส่_CHANNEL_ACCESS_TOKEN_ของคุณที่นี่":
        return False
    url = 'https://api.line.me/v2/bot/message/broadcast'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    data = {"messages": [{"type": "text", "text": message}]}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(data))
        return res.status_code == 200
    except:
        return False

def get_gsheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

def load_data():
    try:
        with st.spinner("🔄 กำลังโหลดข้อมูลจาก Google Sheets..."):
            client = get_gsheet_client()
            sheet = client.open_by_url(SHEET_URL).sheet1
            data_str = sheet.acell('A1').value
            if data_str:
                data = json.loads(data_str)
                if "users" not in data: data["users"] = ["นวคุณ", "วิน", "อาร์ต", "สิ", "อั๋น"]
                return data
    except Exception as e:
        st.warning("⚠️ รอการเชื่อมต่อ Google Sheets...")
    return {"users": ["นวคุณ", "วิน", "อาร์ต", "สิ", "อั๋น"], "shares": []}

def save_data(data):
    try:
        with st.spinner("💾 กำลังบันทึกลง Google Sheets..."):
            client = get_gsheet_client()
            sheet = client.open_by_url(SHEET_URL).sheet1
            json_str = json.dumps(data, ensure_ascii=False)
            sheet.update('A1', [[json_str]])
    except Exception as e:
        st.error(f"❌ ไม่สามารถบันทึกข้อมูลลง Google Sheets ได้: {e}")

def calculate_due_date(start_date_str, period, freq_type, freq_val):
    base_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    steps = (period - 1) * freq_val
    if freq_type == "รายวัน": return base_date + relativedelta(days=steps)
    elif freq_type == "รายสัปดาห์": return base_date + relativedelta(weeks=steps)
    elif freq_type == "รายเดือน": return base_date + relativedelta(months=steps)
    return base_date

def get_period_date(s, period):
    """คืนวันที่ของงวดที่ระบุ โดยใช้ 'วันที่จริงต่องวด' (period_dates) ก่อน
    ถ้าไม่มี (วงเก่า) ค่อยถอยไปคำนวณจากความถี่แบบเดิม"""
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

# ====================================================
# 🧰 ฟังก์ชันช่วย: คำนวณยอด / จ่ายเงิน / ย้อนกลับ
# ====================================================
def _infer_base_per_hand(s, num_hands):
    """เดา 'ยอดส่งฐานต่อมือ' จากประวัติ เมื่อ base_payment เป็น 0
    ใช้ยอดจ่ายของงวด 'คนอื่น' งวดแรก (ก่อนเราเปียได้) = ฐาน×จำนวนมือ"""
    for h in s.get("history", []):
        if str(h.get("win", "")).strip() == "คนอื่น":
            return float(h.get("paid", 0) or 0) / max(1, num_hands)
    if s.get("history"):
        return float(s["history"][0].get("paid", 0) or 0) / max(1, num_hands)
    return 0.0

def _base_per_hand(s, num_hands):
    base = float(s.get("base_payment", 0) or 0)
    return base if base > 0 else _infer_base_per_hand(s, num_hands)

def _clean_history(records):
    """ทำความสะอาดประวัติที่แก้ผ่านตาราง: แปลงตัวเลขเป็น float, ตัดช่องว่างคำสถานะ
    (กันปัญหา numpy type ตอนเซฟ และคำว่า 'ฉันเปียเอง' ที่มีช่องว่างเลยจับไม่ตรง)"""
    out = []
    for h in records:
        hh = dict(h)
        for k in ("paid", "received", "bid"):
            try:
                hh[k] = float(hh.get(k, 0) or 0)
            except:
                hh[k] = 0.0
        try:
            hh["p"] = int(float(hh.get("p", 0) or 0))
        except:
            pass
        hh["win"] = str(hh.get("win", "")).strip()
        hh["date"] = str(hh.get("date", "")).strip()
        out.append(hh)
    return out

def sync_derived_from_history(s):
    """คำนวณค่าที่สืบทอด (other_bids/is_me_won/my_bid_amount) ใหม่จากประวัติ
    เรียกหลังแก้ตารางประวัติ เพื่อให้การคิดดอก/พยากรณ์ตรงกับข้อมูลจริง"""
    if not s.get("share_type", "").startswith("แชร์เปีย"):
        return
    hist = s.get("history", [])
    s["other_bids"] = [float(h.get("bid", 0) or 0) for h in hist if str(h.get("win", "")).strip() == "คนอื่น"]
    s["is_me_won"] = any(str(h.get("win", "")).strip() == "ฉันเปียเอง" for h in hist)
    s["my_bid_amount"] = sum(float(h.get("bid", 0) or 0) for h in hist if str(h.get("win", "")).strip() == "ฉันเปียเอง")

def compute_due_amount(s):
    """ยอดที่ต้องจ่ายของงวดปัจจุบัน (รวมทุกมือ)
    วงเปีย: ฐาน×มือ + ดอกของทุกมือที่ 'เราเปียเอง' ไปแล้ว (ทบกันไปทุกงวดจนจบวง)"""
    num_hands = int(s.get("num_hands", 1))
    if s.get("share_type", "").startswith("แชร์เปีย"):
        base = _base_per_hand(s, num_hands)
        own_bids = sum(float(h.get("bid", 0) or 0) for h in s.get("history", []) if str(h.get("win", "")).strip() == "ฉันเปียเอง")
        return base * num_hands + own_bids
    return sum(float(hd.get("payment", 0) or 0) for hd in s.get("hands_data", []))

def pay_one_period(s):
    """บันทึกการจ่าย 1 งวด (งวดปัจจุบัน) คืน (line_message, note_text)"""
    num_hands = int(s.get("num_hands", 1))
    today_str = datetime.now().strftime("%Y-%m-%d")
    period = s["current_period"]
    if s.get("share_type", "").startswith("แชร์เปีย"):
        due = compute_due_amount(s)
        s["history"].append({"p": period, "date": today_str, "paid": due, "received": 0, "bid": 0, "win": "รอผลเปีย"})
        s["current_period"] += 1
        msg = f"🌸 บัญชี: {st.session_state.current_user}\nจ่ายวง {s['name']} งวด {period} แล้ว!\nยอด: {due:,.2f} ฿ (รอผลเปีย)"
        return msg, f"จ่ายวง {s['name']} งวด {period} แล้ว (กรอกผลเปียได้ที่ส่วน 'กรอกผลเปีย' ด้านล่าง)"
    else:
        hands_data = s.get("hands_data", [])
        default_pay = sum(float(hd["payment"]) for hd in hands_data)
        winning_hands = [hd for hd in hands_data if hd["period"] == period]
        rec_amt = sum(float(hd["amount"]) for hd in winning_hands)
        win = "ฉันเปียเอง" if winning_hands else "คนอื่น"
        s["history"].append({"p": period, "date": today_str, "paid": default_pay, "received": rec_amt, "bid": 0, "win": win})
        s["current_period"] += 1
        if rec_amt > 0:
            msg = f"🎀 บัญชี: {st.session_state.current_user}\nส่งแชร์วง {s['name']} งวด {period} แล้ว!\nยอดส่ง: {default_pay:,.2f} ฿\n🎉 ได้รับเงินแชร์: {rec_amt:,.2f} ฿"
        else:
            msg = f"🎀 บัญชี: {st.session_state.current_user}\nส่งแชร์วง {s['name']} งวด {period} แล้ว!\nยอดส่ง: {default_pay:,.2f} ฿"
        return msg, f"จ่ายวง {s['name']} งวด {period} แล้ว"

def resolve_bid(s, bid_amt, is_me_winning):
    """บันทึกผลเปียของงวดล่าสุด (ใช้ร่วมกันทุกหน้า) — กฎ: ผู้เปียได้ = ต้น + ดอกคนก่อนหน้าทั้งหมด"""
    rec = s["history"][-1]
    rec["bid"] = bid_amt
    rec["win"] = "ฉันเปียเอง" if is_me_winning else "คนอื่น"
    if is_me_winning:
        prev_interest = sum(s.get("other_bids", []))
        rec["received"] = float(s.get("principal", 0)) + prev_interest
        s["is_me_won"] = True
        s["my_bid_amount"] = s.get("my_bid_amount", 0) + bid_amt
    else:
        s.setdefault("other_bids", []).append(bid_amt)

def undo_last_period(s):
    """ย้อนกลับการบันทึกงวดล่าสุด (กรณีกดจ่ายผิด/ยังไม่ถึงกำหนด) คืน True ถ้าสำเร็จ"""
    if not s.get("history"):
        return False
    rec = s["history"].pop()
    s["current_period"] = max(1, s["current_period"] - 1)
    if s.get("share_type", "").startswith("แชร์เปีย"):
        win = rec.get("win")
        if win == "คนอื่น":
            ob = s.get("other_bids", [])
            if ob:
                ob.pop()
        elif win == "ฉันเปียเอง":
            s["my_bid_amount"] = max(0.0, float(s.get("my_bid_amount", 0)) - float(rec.get("bid", 0)))
        s["is_me_won"] = any(h.get("win") == "ฉันเปียเอง" for h in s["history"])
    return True

def render_undo_section(shares, key_prefix):
    """แสดงส่วน 'ย้อนกลับงวดล่าสุด' ใช้ซ้ำได้หลายหน้า"""
    payable = [s for s in shares if s.get("history")]
    if not payable:
        st.info("ยังไม่มีวงที่บันทึกการจ่าย จึงไม่มีอะไรให้ย้อนกลับ")
        return
    sel = st.selectbox("เลือกวงที่ต้องการย้อนกลับ:", [s["name"] for s in payable], key=f"{key_prefix}_undo_sel")
    s = next(x for x in payable if x["name"] == sel)
    last = s["history"][-1]
    st.write(f"งวดล่าสุดที่บันทึก: **งวดที่ {last.get('p', '?')}** | วันที่บันทึก {last.get('date', '-')} | "
             f"จ่าย {float(last.get('paid', 0)):,.2f} ฿ | รับ {float(last.get('received', 0)):,.2f} ฿ | สถานะ: {last.get('win', '-')}")
    confirm = st.checkbox("✔️ ยืนยันว่าต้องการย้อนกลับงวดนี้ (ข้อมูลงวดล่าสุดจะถูกลบ)", key=f"{key_prefix}_undo_confirm")
    if st.button("↩️ ย้อนกลับงวดล่าสุด", key=f"{key_prefix}_undo_btn"):
        if not confirm:
            st.warning("กรุณาติ๊กยืนยันก่อนครับ")
        elif undo_last_period(s):
            save_data(st.session_state.db)
            st.success(f"ย้อนกลับงวดล่าสุดของ '{s['name']}' เรียบร้อย! ตอนนี้กลับไปที่งวด {s['current_period']}")
            st.rerun()

# ====================================================
# 🎀 ตัวช่วย: สถานะ / ความคืบหน้า / พยากรณ์
# ====================================================
def compute_status(s):
    today = date.today()
    if s["current_period"] > s["total_periods"]:
        return ("จบวงแล้ว 🎀", "#9E9E9E")
    last = s["history"][-1] if s.get("history") else None
    if last and last.get("win") == "รอผลเปีย":
        return ("รอกรอกผลเปีย 🌙", "#FB8C00")
    d = get_period_date(s, s["current_period"])
    if d:
        if d < today:
            return ("เลยกำหนด ⏰", "#E53935")
        if d == today:
            return ("ครบกำหนดวันนี้ 💖", "#43A047")
    return ("กำลังเล่นอยู่ 🌸", "#FF69B4")

def status_pill_html(s):
    label, color = compute_status(s)
    return f"<span class='pill' style='background:{color};'>{label}</span>"

# ---- สี/อิโมจิประจำวง ----
THEME_EMOJIS = ["🎀", "🟢", "🟠", "🔴", "🟡", "🔵", "🟣", "🍋", "🥐", "🍊", "🍓", "🌸", "🌼", "🐰", "🐻", "⭐"]

def guess_theme(text):
    """เดาอิโมจิ/สีประจำวงจากชื่อหรือข้อความประกาศ"""
    t = text or ""
    table = [
        (["เขียว", "มะนาว", "lime", "เลม่อน"], ("🍋", "#43A047")),
        (["ส้ม", "orange"], ("🟠", "#FB8C00")),
        (["แดง"], ("🔴", "#E53935")),
        (["ชมพู", "พิงค์", "pink"], ("🌸", "#FF69B4")),
        (["ฟ้า", "น้ำเงิน", "blue"], ("🔵", "#1E88E5")),
        (["ม่วง", "purple"], ("🟣", "#8E24AA")),
        (["เหลือง", "ทอง", "gold"], ("🟡", "#FBC02D")),
        (["ครัวซอง", "ขนมปัง", "เบเกอ", "ขนม"], ("🥐", "#D7A86E")),
        (["สตรอ", "strawberry"], ("🍓", "#E91E63")),
    ]
    for kws, theme in table:
        if any(k in t for k in kws):
            return theme
    return ("🎀", "#FF69B4")

def get_emoji(s):
    return s.get("emoji") or guess_theme(s.get("name", ""))[0]

def get_color(s):
    return s.get("color") or guess_theme(s.get("name", ""))[1]

def _text_on(hex_color):
    """เลือกสีตัวอักษรให้ตัดกับพื้นหลัง (เข้มบนสีอ่อน / ขาวบนสีเข้ม)"""
    try:
        h = str(hex_color).lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "#3a2a2a" if (0.299 * r + 0.587 * g + 0.114 * b) > 165 else "white"
    except:
        return "white"

def circle_chip_html(s):
    c = get_color(s)
    return f"<span class='chip' style='background:{c};color:{_text_on(c)};'>{get_emoji(s)} {s.get('name','')}</span>"

def project_circle(s):
    """พยากรณ์ ยอดจ่าย/รับ/กำไร เมื่อเล่นจนจบวง (รองรับหลายมือ)
    วงเปีย: เปียได้กี่มือก็รับเงินกี่ครั้ง และดอกที่เปียแต่ละมือทบกันในยอดจ่ายทุกงวดจนจบ"""
    num_hands = int(s.get("num_hands", 1))
    N = int(s.get("total_periods", 0))
    cur = int(s.get("current_period", 1))
    res = {"is_pia": False}
    if s.get("share_type", "").startswith("แชร์เปีย"):
        res["is_pia"] = True
        P = float(s.get("principal", 0) or 0)
        base = _base_per_hand(s, num_hands)
        B = base * num_hands
        win_rows = [h for h in s.get("history", []) if str(h.get("win", "")).strip() == "ฉันเปียเอง"]
        won_count = len(win_rows)
        own_ongoing = sum(float(h.get("bid", 0) or 0) for h in win_rows)         # ดอกที่ล็อกแล้ว/งวด
        accumulated = sum(float(h.get("bid", 0) or 0) for h in s.get("history", []) if str(h.get("win", "")).strip() == "คนอื่น")
        bids = [float(h.get("bid", 0) or 0) for h in s.get("history", []) if str(h.get("win", "")).strip() == "คนอื่น" and float(h.get("bid", 0) or 0) > 0]
        avg_bid = (sum(bids) / len(bids)) if bids else float(s.get("start_bid", 0) or 0)
        remaining_hands = max(0, num_hands - won_count)

        past_paid = sum(float(h.get("paid", 0) or 0) for h in s.get("history", []))
        past_received = sum(float(h.get("received", 0) or 0) for h in s.get("history", []))
        future_periods = max(0, N - (cur - 1))
        # อนาคต: จ่ายฐาน+ดอกที่ล็อกแล้วทุกงวด (มือที่เหลือสมมุติเปียช่วงท้าย = ดอกส่วนเกินน้อยมาก)
        future_pay = future_periods * (B + own_ongoing)
        est_each_receive = P + accumulated + avg_bid * max(0, N - cur)           # มือที่เหลือเปียท้ายวง
        future_receive = remaining_hands * est_each_receive
        pay = past_paid + future_pay
        receive = past_received + future_receive
        if remaining_hands == 0:
            note = f"เปียครบทุกมือแล้ว — งวดที่เหลือจ่ายงวดละ {B + own_ongoing:,.0f} ฿ จนจบวง"
        else:
            note = f"กรณีดีสุด: อีก {remaining_hands} มือเปียช่วงท้ายวง (ตอนนี้จ่ายงวดละ {B + own_ongoing:,.0f} ฿)"
        res.update({"P": P, "B": B, "N": N, "cur": cur, "base": base, "own_ongoing": own_ongoing,
                    "accumulated": accumulated, "avg_bid": avg_bid, "won_count": won_count,
                    "remaining_hands": remaining_hands, "past_paid": past_paid, "past_received": past_received,
                    "future_periods": future_periods})
    else:
        pay_per = sum(float(hd.get("payment", 0) or 0) for hd in s.get("hands_data", []))
        pay = pay_per * N
        receive = sum(float(hd.get("amount", 0) or 0) for hd in s.get("hands_data", []))
        note = "อิงตารางขั้นบันไดที่กำหนดไว้แน่นอน"
    res.update({"pay": pay, "receive": receive, "profit": receive - pay, "note": note})
    return res

# ====================================================
# 🧠 ตัวช่วยแกะข้อความประกาศวงแชร์ (Parser)
# ====================================================
DATE_TOKEN_RE = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2}|[ก-๙\.]{2,8})(?:\s*/\s*(\d{2,4}))?")

def _clean_num(s):
    s = re.sub(r"[^\d.]", "", str(s))
    if s in ("", "."): return 0.0
    try: return float(s)
    except: return 0.0

def _to_ce_year(y):
    y = int(re.sub(r"\D", "", str(y)))
    if y > 2400: return y - 543      # พ.ศ. -> ค.ศ.
    if y < 100: return 2000 + (y % 100)
    return y

def _month_from_thai(tok):
    key = re.sub(r"[\s\.]", "", tok)
    table = {
        "มค": 1, "มกรา": 1, "กพ": 2, "กุมภา": 2, "มีค": 3, "มีนา": 3,
        "เมย": 4, "เมษา": 4, "พค": 5, "พฤษภา": 5, "มิย": 6, "มิถุนา": 6,
        "กค": 7, "กรกฎา": 7, "สค": 8, "สิงหา": 8, "กย": 9, "กันยา": 9,
        "ตค": 10, "ตุลา": 10, "พย": 11, "พฤศจิ": 11, "ธค": 12, "ธันวา": 12,
    }
    if key in table: return table[key]
    for k, v in table.items():
        if key.startswith(k): return v
    return None

def _parse_date_match(m):
    try:
        day = int(m.group(1))
    except:
        return None
    mon_raw = m.group(2)
    if re.fullmatch(r"\d{1,2}", mon_raw):
        month = int(mon_raw)
    else:
        month = _month_from_thai(mon_raw)
    year = _to_ce_year(m.group(3)) if m.group(3) else None
    if not month or not (1 <= month <= 12) or not (1 <= day <= 31):
        return None
    return (day, month, year)

def _assign_years(tuples):
    """แปลง (วัน, เดือน, ปีหรือNone) -> list ของ date(สตริง) โดยเดาปีให้
    เมื่อเดือนถัดไปน้อยลง = ขึ้นปีใหม่"""
    n = len(tuples)
    if n == 0: return []
    years = [t[2] for t in tuples]
    months = [t[1] for t in tuples]
    anchor = next((i for i, y in enumerate(years) if y), None)
    if anchor is None:
        years[0] = date.today().year
        anchor = 0
    for i in range(anchor + 1, n):
        if years[i] is None:
            y = years[i - 1]
            if months[i] < months[i - 1]: y += 1
            years[i] = y
    for i in range(anchor - 1, -1, -1):
        if years[i] is None:
            y = years[i + 1]
            if months[i] > months[i + 1]: y -= 1
            years[i] = y
    out = []
    for (d, mth, _), y in zip(tuples, years):
        try:
            out.append(date(y, mth, d).strftime("%Y-%m-%d"))
        except:
            out.append("")
    return out

def _normalize_date_str(s):
    """รับสตริงวันที่จากตารางที่ผู้ใช้แก้ -> 'YYYY-MM-DD' (รองรับ ISO และ วัน/เดือน แบบไทย)"""
    s = str(s).strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try: return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except: return None
    dm = DATE_TOKEN_RE.search(s)
    if dm:
        d = _parse_date_match(dm)
        if d:
            y = d[2] or date.today().year
            try: return date(y, d[1], d[0]).strftime("%Y-%m-%d")
            except: return None
    return None

def _parse_members(text):
    """แกะ ลำดับ/ยอด/ชื่อ/วันที่ จากบรรทัดที่ขึ้นต้นด้วยเลขลำดับ (ใช้อ้างอิงเฉยๆ)"""
    out = []
    for line in text.splitlines():
        m = re.match(r"^\s*(\d{1,2})\s*[\.\)]\s*(.+)$", line)
        if not m: continue
        no = int(m.group(1))
        rest = m.group(2)
        dstr = ""
        dm = DATE_TOKEN_RE.search(rest)
        if dm:
            d = _parse_date_match(dm)
            if d:
                dstr = f"{d[0]}/{d[1]}" + (f"/{d[2]}" if d[2] else "")
                rest = (rest[:dm.start()] + " " + rest[dm.end():]).strip()
        amount = ""
        am = re.match(r"\s*([\d,]+)\s*(.*)$", rest)
        name = rest
        if am and am.group(1):
            amount = am.group(1).replace(",", "")
            name = am.group(2)
        name = re.sub(r"[^\wก-๙\s]", "", name).strip()
        out.append({"ลำดับ": no, "ยอด/ดอก": amount, "ชื่อ": name, "วันที่": dstr})
    return out

def parse_share_text(text):
    text = text or ""
    res = {"raw": text}

    # ---- ประเภทวง ----
    if "ขั้นบันได" in text:
        res["share_type"] = "แชร์ขั้นบันได (เฉพาะมือของเรา)"
    elif re.search(r"(เปีย|บิท|บิด|ตารางรับยอด|อั้นดอก|หมุนเสีย|ดอกเริ่ม|เปียขั้นต่ำ)", text):
        res["share_type"] = "แชร์เปีย (ประมูลดอกเบี้ย)"
    else:
        res["share_type"] = "แชร์ขั้นบันได (เฉพาะมือของเรา)"

    # ---- ชื่อวง ----
    name = ""
    for line in text.splitlines():
        if "วง" in line and "บัญชี" not in line and "วันที่" not in line:
            cand = re.sub(r"[^\wก-๙\s]", "", line).strip()
            cand = re.sub(r"\s+", " ", cand)
            if cand:
                name = cand
                break
    res["name"] = name

    # ---- ตัวเลขหลัก (ทนอิโมจิ/สัญลักษณ์คั่นระหว่างคำกับเลข) ----
    m = re.search(r"ต้น[^\d\n]*([\d,]+)", text)
    res["principal"] = _clean_num(m.group(1)) if m else 0.0
    m = re.search(r"ส่งมือละ[^\d\n]*([\d,]+)", text)
    res["base_payment"] = _clean_num(m.group(1)) if m else 0.0
    m = re.search(r"(?:ดอกเริ่มต้นที่|เปียขั้นต่ำ|ดอกเริ่ม)[^\d\n]*([\d,]+)", text)
    res["start_bid"] = _clean_num(m.group(1)) if m else 0.0
    m = re.search(r"ค่าดูแล[^\d\n]*([\d,]+)", text)
    res["admin_fee"] = _clean_num(m.group(1)) if m else 0.0

    # ---- ความถี่ (สำรอง) ----
    if re.search(r"รายเดือน", text):
        res["freq_type"], res["freq_val"] = "รายเดือน", 1
    elif re.search(r"รายสัปดาห์|รายอาทิตย์", text):
        res["freq_type"], res["freq_val"] = "รายสัปดาห์", 1
    else:
        fm = re.search(r"ราย\s*(\d+)\s*วัน", text)
        res["freq_type"] = "รายวัน"
        res["freq_val"] = int(fm.group(1)) if fm else 1

    # ---- งวดปัจจุบัน + จุดอ้างอิงปี ----
    header_period = None
    pm = re.search(r"งวดที่\s*(\d+)", text)
    if pm: header_period = int(pm.group(1))
    res["current_period"] = header_period or 1

    # ---- ตารางวันที่ (ข้ามบรรทัด header ที่มีคำว่า 'วันที่') ----
    schedule_tuples = []
    for line in text.splitlines():
        if "วันที่" in line:   # บรรทัดอ้างอิงงวดปัจจุบัน ไม่ใช่ตาราง
            continue
        dm = DATE_TOKEN_RE.search(line)
        if dm:
            d = _parse_date_match(dm)
            if d:
                schedule_tuples.append(list(d))

    # เติมปีจากจุดอ้างอิง header ถ้ามี (งวดที่ N วันที่ .../.../25xx)
    for line in text.splitlines():
        if "วันที่" in line:
            dm = DATE_TOKEN_RE.search(line)
            d = _parse_date_match(dm) if dm else None
            if d and d[2] and header_period and 1 <= header_period <= len(schedule_tuples):
                schedule_tuples[header_period - 1][2] = d[2]
            break

    res["period_dates"] = _assign_years([tuple(t) for t in schedule_tuples])
    res["members"] = _parse_members(text)
    res["num_hands"] = 1
    res["emoji"], res["color"] = guess_theme(text)
    return res

# ====================================================
# --- การตั้งค่าหน้าจอและ Theme (Sanrio Style) ---
# ====================================================
st.set_page_config(page_title="Share La La La", layout="wide", page_icon="🎀", initial_sidebar_state="collapsed")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Itim&family=Mali:wght@400;600&display=swap');
    html, body, .stApp, .stMarkdown, .stMarkdown p, p, label, h1, h2, h3, h4,
    .stButton>button, input, textarea, select,
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"], [data-testid="stWidgetLabel"] {
        font-family: 'Itim', 'Mali', 'Sukhumvit Set', sans-serif !important;
    }
    /* คืนฟอนต์ไอคอนของ Streamlit ไม่ให้ Itim ทับ (กันคำว่า arrow_right โผล่บน expander/ลูกศร metric) */
    span[data-testid="stIconMaterial"], .material-icons, .material-icons-outlined,
    .material-symbols-outlined, .material-symbols-rounded,
    [class*="material-symbols"], [class*="material-icons"] {
        font-family: 'Material Symbols Outlined','Material Symbols Rounded','Material Icons Outlined','Material Icons' !important;
    }
    .main, .stApp { background-color: #FFF0F5; }
    .stButton>button { background-color: #FFB6C1; color: #5a2a3a; border-radius: 20px; border: 2px solid #FF69B4; font-weight: 600; transition: all .15s ease; }
    .stButton>button:hover { background-color: #FF69B4; color: white; transform: translateY(-1px); }
    h1, h2, h3 { color: #FF1493 !important; }
    .stMetric { background-color: white; padding: 15px; border-radius: 18px; box-shadow: 2px 4px 14px rgba(255, 105, 180, 0.18); }
    .pill { display:inline-block; padding:4px 14px; border-radius:999px; color:white; font-size:0.9rem; font-weight:600; box-shadow: 1px 2px 6px rgba(0,0,0,0.12); }
    .chip { display:inline-block; padding:5px 16px; border-radius:999px; font-weight:600; font-size:1.05rem; box-shadow: 1px 2px 6px rgba(0,0,0,0.15); margin: 2px 0; }
    .stProgress > div > div > div > div { background-color: #FF69B4 !important; }

    /* ===== ปรับให้เหมาะกับมือถือ ===== */
    /* ปิด sidebar ของ Streamlit ทั้งหมด (ใช้เมนูปุ่มในแอปแทน) */
    [data-testid="stSidebar"], [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"], [data-testid="stExpandSidebarButton"] { display: none !important; }
    /* เผื่อ status bar มือถือ: ดันแถบบน (Fork/เมนู) และ sidebar ให้พ้นนาฬิกา/ไอคอนแจ้งเตือน */
    [data-testid="stHeader"] { padding-top: 2.6rem !important; }
    /* ซ่อนแถบ dev ของ Streamlit (Fork/GitHub/Deploy/เมนู ⋮) — ไม่จำเป็นสำหรับผู้ใช้ และเป็นตัวที่ไปชนปุ่มเมนู */
    [data-testid="stToolbar"], [data-testid="stToolbarActions"], [data-testid="stDecoration"],
    [data-testid="stStatusWidget"], #MainMenu, [class*="viewerBadge"] { display: none !important; }
    [data-testid="stSidebar"] { padding-top: 2.6rem !important; }
    [data-testid="stSidebarHeader"] { padding-top: 0.4rem !important; }
    .block-container { padding-top: 3.4rem !important; padding-bottom: 4rem !important;
        padding-left: 1rem !important; padding-right: 1rem !important; }

    /* ปุ่มเปิด sidebar ตอน 'ปิด' อยู่ (ลอยมุมซ้าย) ขยับลงพ้น status bar */
    [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"] {
        top: 2.6rem !important; left: 0.5rem !important; z-index: 999990 !important;
    }
    /* ปุ่ม <</> ให้ใหญ่พอกด สีชมพู */
    [data-testid="collapsedControl"] button, [data-testid="stSidebarCollapsedControl"] button,
    [data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapseButton"] button {
        width: 2.6rem !important; height: 2.6rem !important;
        background: #FFB6C1 !important; border: 2px solid #FF69B4 !important; border-radius: 14px !important;
    }
    [data-testid="collapsedControl"] svg, [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="stSidebarCollapseButton"] svg { color: #7a2a45 !important; }

    /* ปุ่มทั่วไปใหญ่ขึ้น กดสะดวก */
    .stButton>button { min-height: 48px !important; font-size: 1.05rem !important; padding: 0.55rem 1.1rem !important; }

    @media (max-width: 640px) {
        .stButton>button { width: 100% !important; min-height: 54px !important; font-size: 1.12rem !important; }
        [data-baseweb="input"] input, [data-baseweb="select"] > div, textarea,
        .stNumberInput input, .stTextInput input { min-height: 46px !important; font-size: 1rem !important; }
        h1 { font-size: 1.55rem !important; } h2 { font-size: 1.3rem !important; } h3 { font-size: 1.12rem !important; }
        [data-testid="stMetricValue"] { font-size: 1.35rem !important; }
        [data-testid="stSidebar"] label { font-size: 1.05rem !important; padding: 4px 0 !important; }
    }
    </style>
    """, unsafe_allow_html=True)

if "db" not in st.session_state: st.session_state.db = load_data()
if "current_user" not in st.session_state: st.session_state.current_user = None

# ====================================================
# --- หน้า 1: เลือกผู้เล่น (Login) ---
# ====================================================
if st.session_state.current_user is None:
    st.image("https://media.tenor.com/XLwkPdamUikAAAAi/hello-kitty.gif", width=150)
    st.title("🎀 ยินดีต้อนรับสู่ Share La La La")
    col1, col2 = st.columns(2)
    with col1:
        selected_user = st.selectbox("👤 เลือกชื่อผู้เล่นที่มีอยู่:", st.session_state.db["users"])
        if st.button("เข้าสู่ระบบ"):
            st.session_state.current_user = selected_user
            st.rerun()
    with col2:
        new_user = st.text_input("➕ หรือ พิมพ์ชื่อผู้เล่นใหม่ที่นี่:")
        if st.button("เพิ่มและเข้าสู่ระบบ"):
            if new_user and new_user not in st.session_state.db["users"]:
                st.session_state.db["users"].append(new_user)
                save_data(st.session_state.db)
                st.session_state.current_user = new_user
                st.rerun()
    st.stop()

# ====================================================
# --- เมนูนำทางแบบแอปมือถือ (แทน Sidebar) ---
# ====================================================
if "page" not in st.session_state:
    st.session_state.page = "💰 จ่ายวันนี้"

st.markdown("### 🎀 Share La La La")
st.caption(f"👤 เข้าใช้งานโดย: **{st.session_state.current_user}**")

# ปุ่มเมนู 4 ปุ่ม (2x2) — ปุ่มหน้าที่เลือกอยู่เป็นสีเข้ม
nav_items = [
    ("💰 จ่ายวันนี้", "💰 จ่ายวันนี้"),
    ("🏠 วงแชร์ของฉัน", "🏠 วงแชร์ของฉัน"),
    ("➕ สร้างวงใหม่", "➕ สร้างวงแชร์ใหม่"),
    ("📊 สรุป", "📊 สรุปกำไร/ขาดทุนรวม"),
]
nav_cells = list(st.columns(2)) + list(st.columns(2))
for (label, key), cell in zip(nav_items, nav_cells):
    active = (st.session_state.page == key)
    if cell.button(label, key=f"nav_{key}", use_container_width=True,
                   type=("primary" if active else "secondary")):
        st.session_state.page = key
        st.rerun()

with st.expander("⚙️ บัญชี & ตั้งค่า"):
    if st.button("🔄 เปลี่ยนผู้เล่น"):
        st.session_state.current_user = None
        st.session_state.pop("page", None)
        st.rerun()
    mute_line = st.checkbox("🔕 ปิดแจ้งเตือน LINE (สำหรับลงข้อมูลย้อนหลัง)")

st.divider()
menu = st.session_state.page

user_shares = [s for s in st.session_state.db["shares"] if s.get("owner") == st.session_state.current_user]

# ====================================================
# --- เมนู 1: หน้าแรก & วงแชร์ของฉัน ---
# ====================================================
if menu == "🏠 วงแชร์ของฉัน":
    st.title("🌸 วงแชร์ของฉัน")
    if not user_shares:
        st.info("คุณยังไม่มีวงแชร์ในระบบ ไปสร้างวงแรกได้ที่เมนู 'สร้างวงแชร์ใหม่' ทางซ้ายมือครับ")
    else:
        name_to_share = {x["name"]: x for x in user_shares}
        selected_name = st.selectbox("เลือกวงแชร์เพื่อดูรายละเอียด:", list(name_to_share.keys()),
                                     format_func=lambda n: f"{get_emoji(name_to_share[n])} {n}")
        s = next(s for s in user_shares if s["name"] == selected_name)
        share_type = s.get("share_type", "แชร์เปีย (ประมูลดอกเบี้ย)")
        num_hands = int(s.get("num_hands", 1))

        st.markdown(circle_chip_html(s), unsafe_allow_html=True)

        hands_data = s.get("hands_data", [])
        if not hands_data and not share_type.startswith("แชร์เปีย"):
            hands_data = [{"period": s.get("my_receive_period", 0), "payment": s.get("my_fixed_payment", 0.0), "amount": s.get("my_receive_amount", 0.0)}]

        current_due_date = get_period_date(s, s["current_period"]) if s["current_period"] <= s["total_periods"] else None

        st.markdown(f"**รูปแบบวงแชร์:** 🏷️ {share_type} | **จำนวนมือที่เล่น:** {num_hands} มือ")
        st.markdown(status_pill_html(s), unsafe_allow_html=True)
        _done = max(0, min(s["current_period"] - 1, s["total_periods"]))
        st.progress(_done / s["total_periods"] if s["total_periods"] else 0.0,
                    text=f"ความคืบหน้า {_done}/{s['total_periods']} งวด")
        col1, col2, col3, col4 = st.columns(4)
        paid = sum(float(h["paid"]) for h in s["history"])
        received = sum(float(h["received"]) for h in s["history"])
        col1.metric("จ่ายไปแล้ว", f"{paid:,.2f} ฿")
        col2.metric("ได้รับมาแล้ว", f"{received:,.2f} ฿")
        col3.metric("กำไร/ขาดทุน", f"{received - paid:,.2f} ฿")

        if share_type.startswith("แชร์เปีย"):
            # ดึงดอกเบี้ยสะสมของทุกคนมารวมกันทั้งหมด
            col4.metric("ดอกเบี้ยสะสม", f"{sum(float(h['bid']) for h in s['history']):,.2f} ฿")
        else:
            total_expected_receive = sum(float(hd["amount"]) for hd in hands_data)
            col4.metric("เงินต้นรวม (เป้าหมาย)", f"{total_expected_receive:,.2f} ฿")

        st.info(f"🗓️ **งวดถัดไปวันที่:** {current_due_date.strftime('%d/%m/%Y') if current_due_date else 'จบวงแล้ว'}")

        with st.expander("🔮 พยากรณ์ & จุดคุ้มทุน"):
            pj = project_circle(s)
            pc1, pc2, pc3 = st.columns(3)
            pc1.metric("จ่ายทั้งหมด (คาด)", f"{pj['pay']:,.0f} ฿")
            pc2.metric("รับทั้งหมด (คาด)", f"{pj['receive']:,.0f} ฿")
            pc3.metric("กำไร/ขาดทุน (คาด)", f"{pj['profit']:,.0f} ฿", delta=pj['profit'])
            st.caption("ℹ️ " + pj["note"])

            if pj.get("is_pia") and pj.get("remaining_hands", 0) > 0:
                B, N, cur, P = pj["B"], pj["N"], pj["cur"], pj["P"]
                acc, avg, own = pj["accumulated"], pj["avg_bid"], pj["own_ongoing"]
                past_paid, past_received, fp = pj["past_paid"], pj["past_received"], pj["future_periods"]
                st.markdown(f"**🎯 จุดคุ้มทุน — ควรเปีย 'มือถัดไป' งวดไหน** (เหลือ {pj['remaining_hands']} มือ)")
                a1, a2 = st.columns(2)
                others_avg = a1.number_input("ดอกเฉลี่ยที่คนอื่นเปีย/งวด", min_value=0.0, value=float(round(avg)), step=50.0, key=f"be_oth_{s['name']}")
                my_bid = a2.number_input("ดอกที่เราจะเปีย/งวด (มือนี้)", min_value=0.0, value=float(round(avg)), step=50.0, key=f"be_my_{s['name']}")
                rows, be_period = [], None
                for k in range(cur, N + 1):
                    # ยอดรับของมือนี้ถ้าเปียงวด k
                    recv_k = P + acc + others_avg * (k - cur)
                    # จ่ายทั้งวง = จ่ายไปแล้ว + (ฐาน+ดอกที่ล็อก)*งวดที่เหลือ + ดอกมือนี้*(งวดหลังเปีย)
                    pay_k = past_paid + (B + own) * fp + my_bid * (N - k)
                    recv_total = past_received + recv_k
                    profit_k = recv_total - pay_k
                    if be_period is None and profit_k >= 0:
                        be_period = k
                    rows.append({"เปียงวดที่": k, "รับมือนี้(คาด)": round(recv_k),
                                 "จ่ายทั้งวง(คาด)": round(pay_k), "กำไร/ขาดทุนรวม": round(profit_k)})
                if be_period:
                    st.success(f"🎯 ควรเปียมือนี้ตั้งแต่ **งวดที่ {be_period}** เป็นต้นไปถึงจะเริ่มได้กำไร — เปียก่อนหน้านี้ขาดทุน")
                else:
                    st.warning("⚠️ ด้วยสมมุติฐานนี้ ไม่มีงวดไหนได้กำไร ลองลด 'ดอกที่เราจะเปีย' ลง")
                st.caption("📌 ยิ่งเปียช้า+ดอกต่ำ ยิ่งกำไร (จ่ายดอกส่วนเกินน้อยงวด + ได้ดอกคนก่อนหน้าเยอะ) · ตารางคิดทีละ 1 มือ ถ้าเหลือหลายมือให้ดูทีละมือ")
                st.dataframe(
                    pd.DataFrame(rows).style.format({"รับมือนี้(คาด)": "{:,.0f}", "จ่ายทั้งวง(คาด)": "{:,.0f}", "กำไร/ขาดทุนรวม": "{:,.0f}"}),
                    use_container_width=True, hide_index=True)

        # --- ⚙️ ส่วนจัดการรายละเอียดและลบวงแชร์ ---
        with st.expander("⚙️ จัดการรายละเอียดวงแชร์ (แก้ไขจำนวนมือ/วันที่/สี/ลบวง)"):
            st.subheader("🛠️ แก้ไขข้อมูลพื้นฐาน")
            edit_num_hands = st.number_input("แก้ไขจำนวนมือที่เล่น:", min_value=1, value=num_hands, step=1, key="edit_num_hands")

            st.write("🎨 **สี/อิโมจิประจำวง**")
            mecol1, mecol2 = st.columns(2)
            _cur_emoji = get_emoji(s)
            _e_idx = THEME_EMOJIS.index(_cur_emoji) if _cur_emoji in THEME_EMOJIS else 0
            edit_emoji = mecol1.selectbox("อิโมจิ", THEME_EMOJIS, index=_e_idx, key="edit_emoji")
            edit_color = mecol2.color_picker("สี", value=get_color(s), key="edit_color")
            st.markdown(f"<span class='chip' style='background:{edit_color};color:{_text_on(edit_color)};'>{edit_emoji} {s['name']}</span>", unsafe_allow_html=True)

            new_hands_data_list = []
            if share_type.startswith("แชร์เปีย"):
                edit_base = st.number_input("แก้ไขยอดส่งฐาน (ต่อ 1 มือ):", min_value=0.0, value=float(s.get("base_payment", 0.0)))
            else:
                st.write("📂 **ระบุรายละเอียดแต่ละมือใหม่ (ขั้นบันได)**")
                temp_hands = hands_data.copy()
                while len(temp_hands) < edit_num_hands:
                    temp_hands.append({"period": 1, "payment": 0.0, "amount": 0.0})

                for i in range(edit_num_hands):
                    st.write(f"**มือที่ {i+1}**")
                    ec1, ec2, ec3 = st.columns(3)
                    ep_period = ec1.number_input(f"รับเงินงวดที่ (มือ {i+1})", min_value=1, step=1, value=int(temp_hands[i]["period"]), key=f"ep_{i}")
                    ep_pay = ec2.number_input(f"จ่ายงวดละ (มือ {i+1})", min_value=0.0, value=float(temp_hands[i]["payment"]), key=f"epay_{i}")
                    ep_amt = ec3.number_input(f"เงินต้นที่ได้ (มือ {i+1})", min_value=0.0, value=float(temp_hands[i]["amount"]), key=f"eamt_{i}")
                    new_hands_data_list.append({"period": ep_period, "payment": ep_pay, "amount": ep_amt})

            # แก้ไขตารางวันจ่ายจริงต่องวด
            st.write("🗓️ **แก้ไขวันจ่าย/รับเงินจริงต่องวด** (ถ้าท้าวหยุดรับบางงวด แก้วันที่ตรงนี้ได้)")
            existing_pd = s.get("period_dates", [])
            if not existing_pd:
                existing_pd = []
                for p in range(1, s["total_periods"] + 1):
                    gd = get_period_date(s, p)
                    existing_pd.append(gd.strftime("%Y-%m-%d") if gd else "")
            pd_df = pd.DataFrame({"งวดที่": list(range(1, len(existing_pd) + 1)), "วันที่ (YYYY-MM-DD)": existing_pd})
            edited_pd = st.data_editor(pd_df, num_rows="dynamic", use_container_width=True, key="edit_pd")

            if st.button("💾 บันทึกการแก้ไขรายละเอียด"):
                s["num_hands"] = edit_num_hands
                s["emoji"] = edit_emoji
                s["color"] = edit_color
                if share_type.startswith("แชร์เปีย"):
                    s["base_payment"] = edit_base
                else:
                    s["hands_data"] = new_hands_data_list
                new_pd = []
                for _, row in edited_pd.iterrows():
                    norm = _normalize_date_str(row.get("วันที่ (YYYY-MM-DD)", ""))
                    if norm: new_pd.append(norm)
                if new_pd:
                    s["period_dates"] = new_pd
                    s["total_periods"] = len(new_pd)
                    s["start_date"] = new_pd[0]
                save_data(st.session_state.db)
                st.success("อัปเดตรายละเอียดเรียบร้อย!")
                st.rerun()

            st.divider()
            if st.button("🗑️ ยืนยันการลบวงแชร์นี้ (ลบแล้วกู้คืนไม่ได้)"):
                st.session_state.db["shares"].remove(s)
                save_data(st.session_state.db)
                st.rerun()

        # ==========================================
        # --- ส่วนบันทึกการจ่ายเงิน (แยกตามประเภทแชร์) ---
        # ==========================================
        last_record = s["history"][-1] if s["history"] else None
        is_waiting_bid = last_record and last_record.get("win") == "รอผลเปีย"

        if s["current_period"] <= s["total_periods"] or is_waiting_bid:
            display_period = last_record['p'] if is_waiting_bid else s["current_period"]
            st.subheader(f"📝 บันทึกงวดที่ {display_period}")

            if share_type.startswith("แชร์เปีย"):
                due = compute_due_amount(s)
                times_won = sum(1 for h in s["history"] if h.get("win") == "ฉันเปียเอง")

                if is_waiting_bid:
                    st.info(f"⏳ **คุณจ่ายเงินงวดที่ {display_period} แล้ว กรุณากรอกผลเปียตอนเย็นครับ**")
                    with st.container():
                        c1, c2, c3 = st.columns(3)
                        bid_amt = c1.number_input("ยอดเปียที่ชนะ (บาท)", min_value=0.0)
                        win_options = ["คนอื่น", "ฉันเปียเอง"] if times_won < num_hands else ["คนอื่น (สิทธิ์เปียครบแล้ว)"]
                        winner = c2.selectbox("ใครได้เงินเปียงวดนี้?", win_options)
                        is_me_winning = (winner == "ฉันเปียเอง")

                        if c3.button(f"✅ บันทึกผลเปียงวด {display_period}"):
                            resolve_bid(s, bid_amt, is_me_winning)
                            save_data(st.session_state.db)
                            if not mute_line:
                                send_line_message(f"🌸 อัปเดตผลเปียวง {s['name']} งวด {display_period}\nคนเปียได้: {'คุณ' if is_me_winning else 'คนอื่น'}\nยอดดอกเบี้ย: {bid_amt:,.2f} ฿")
                            st.rerun()
                else:
                    with st.container():
                        st.write(f"💸 **ยอดเรียกเก็บงวดนี้ (รวม {num_hands} มือ):** {due:,.2f} บาท")
                        if st.button("✅ ยืนยันจ่ายเงิน (รอผลเปียตอนเย็น)"):
                            s["history"].append({"p": s["current_period"], "date": datetime.now().strftime("%Y-%m-%d"), "paid": due, "received": 0, "bid": 0, "win": "รอผลเปีย"})
                            s["current_period"] += 1
                            save_data(st.session_state.db)
                            if not mute_line:
                                send_line_message(f"🌸 บัญชี: {st.session_state.current_user}\nจ่ายวง {s['name']} งวด {s['current_period']-1} แล้ว!\nยอด: {due:,.2f} ฿ (รอผลเปีย)")
                            st.rerun()

            else:
                if s["current_period"] <= s["total_periods"]:
                    default_pay = sum(float(hd["payment"]) for hd in hands_data)
                    winning_hands = [hd for hd in hands_data if hd["period"] == s["current_period"]]
                    is_my_turn_now = len(winning_hands) > 0
                    default_rec_amt = sum(float(hd["amount"]) for hd in winning_hands)

                    with st.container():
                        if is_my_turn_now:
                            st.success(f"🎉 **งวดนี้ถึงคิวรับเงินของคุณแล้ว!** ได้รับเงินต้นรวม: {default_rec_amt:,.2f} บาท")
                            st.write(f"💸 ยอดจ่ายรวมงวดนี้ ({num_hands} มือ): {default_pay:,.2f} บาท")
                            if st.button("✅ ยืนยันจ่ายเงิน และ รับเงินแชร์"):
                                s["history"].append({"p": s["current_period"], "date": datetime.now().strftime("%Y-%m-%d"), "paid": default_pay, "received": default_rec_amt, "bid": 0, "win": "ฉันเปียเอง"})
                                s["current_period"] += 1
                                save_data(st.session_state.db)
                                if not mute_line:
                                    send_line_message(f"🎀 บัญชี: {st.session_state.current_user}\nส่งแชร์วง {s['name']} งวด {s['current_period']-1} แล้ว!\nยอดส่ง: {default_pay:,.2f} ฿\n🎉 ได้รับเงินแชร์: {default_rec_amt:,.2f} ฿")
                                st.rerun()
                        else:
                            st.write(f"💸 **ยอดจ่ายรวมงวดนี้ ({num_hands} มือ):** {default_pay:,.2f} บาท")
                            if st.button("✅ ยืนยันจ่ายเงิน"):
                                s["history"].append({"p": s["current_period"], "date": datetime.now().strftime("%Y-%m-%d"), "paid": default_pay, "received": 0, "bid": 0, "win": "คนอื่น"})
                                s["current_period"] += 1
                                save_data(st.session_state.db)
                                if not mute_line:
                                    send_line_message(f"🎀 บัญชี: {st.session_state.current_user}\nส่งแชร์วง {s['name']} งวด {s['current_period']-1} แล้ว!\nยอดส่ง: {default_pay:,.2f} ฿")
                                st.rerun()

        if s["history"]:
            with st.expander("↩️ เผลอกดจ่ายผิด? ย้อนกลับงวดล่าสุดของวงนี้"):
                render_undo_section([s], "home")

        st.divider()
        colA, colB = st.columns(2)
        with colA:
            st.subheader("🗓️ ตารางชำระเงินล่วงหน้า")
            future_schedule = []
            if share_type.startswith("แชร์เปีย"):
                due_predict = compute_due_amount(s)
            else:
                due_predict = sum(float(hd["payment"]) for hd in hands_data)

            start_table_period = s["current_period"]

            for p in range(start_table_period, s["total_periods"] + 1):
                p_date = get_period_date(s, p)
                row = {"งวดที่": p, "วันที่": p_date.strftime("%Y-%m-%d") if p_date else "-", "ยอดส่งรวม": due_predict}
                if not share_type.startswith("แชร์เปีย"):
                    win_amts = sum(float(hd["amount"]) for hd in hands_data if hd["period"] == p)
                    row["หมายเหตุ"] = f"🎉 รับเงิน ({win_amts:,.2f})" if win_amts > 0 else "-"
                else:
                    row["หมายเหตุ"] = "-"
                future_schedule.append(row)
            if future_schedule:
                st.dataframe(pd.DataFrame(future_schedule), use_container_width=True)
            else:
                st.info("ไม่มีตารางค้างชำระ (จบวงแล้ว)")

        with colB:
            st.subheader("📜 ประวัติการส่ง (พิมพ์แก้ไขได้)")
            if s["history"]:
                edited_df = st.data_editor(pd.DataFrame(s["history"]), num_rows="dynamic", use_container_width=True)
                if st.button("💾 บันทึกการแก้ไขตาราง"):
                    s["history"] = _clean_history(edited_df.to_dict("records"))
                    s["current_period"] = len(s["history"]) + 1
                    sync_derived_from_history(s)
                    save_data(st.session_state.db)
                    st.success("อัปเดตประวัติเรียบร้อย!")
                    st.rerun()

# ====================================================
# --- เมนูหลัก: จ่ายวันนี้ (แดชบอร์ดกดทีเดียวจบ) ---
# ====================================================
elif menu == "💰 จ่ายวันนี้":
    st.title("💰 จ่ายวันนี้")
    today = date.today()
    st.caption(f"วันนี้ {today.strftime('%d/%m/%Y')} — ติ๊กวงที่จะจ่าย แล้วกดบันทึกครั้งเดียวจบทุกวง")

    # ---- หา "วงที่ถึง/เลยกำหนด" และ "วงที่รอกรอกผลเปีย" ----
    due_list = []
    for s in user_shares:
        if s["current_period"] <= s["total_periods"]:
            d = get_period_date(s, s["current_period"])
            if d and d <= today:
                due_list.append((s, d))
    waiting = [s for s in user_shares if s.get("history") and s["history"][-1].get("win") == "รอผลเปีย"]

    # สรุปด้านบน
    total_due = sum(compute_due_amount(s) for s, _ in due_list)
    m1, m2, m3 = st.columns(3)
    m1.metric("วงที่ต้องจ่าย", f"{len(due_list)} วง")
    m2.metric("ยอดรวมวันนี้", f"{total_due:,.0f} ฿")
    m3.metric("รอกรอกผลเปีย", f"{len(waiting)} วง")

    st.divider()

    # ===== ส่วนที่ 1: จ่ายแบบเลือกทีเดียว =====
    st.subheader("✅ จ่ายวันนี้")
    if not due_list:
        st.success("🎉 วันนี้ไม่มีวงที่ต้องจ่ายแล้ว สบายใจได้เลย!")
    else:
        with st.form("paytoday_form"):
            st.write("ติ๊กวงที่จะจ่าย (ติ๊กให้อัตโนมัติแล้ว) — เอาออกได้ถ้ายังไม่จ่ายวงนั้น")
            picks = {}
            for s, d in due_list:
                num_hands = int(s.get("num_hands", 1))
                is_pia = s.get("share_type", "").startswith("แชร์เปีย")
                amt = compute_due_amount(s)
                tag = "🔴 เลยกำหนด" if d < today else "🟢 ครบวันนี้"
                extra = ""
                if not is_pia:
                    win_amt = sum(float(hd["amount"]) for hd in s.get("hands_data", []) if hd["period"] == s["current_period"])
                    if win_amt > 0:
                        extra = f" — 🎉 งวดนี้รับ {win_amt:,.0f} ฿"
                label = f"{tag} {get_emoji(s)} **{s['name']}**  · งวด {s['current_period']} ({d.strftime('%d/%m')}) · {num_hands} มือ · จ่าย {amt:,.0f} ฿{extra}"
                picks[s["name"]] = st.checkbox(label, value=True, key=f"paychk_{s['name']}")
            submitted = st.form_submit_button("💾 บันทึกการจ่ายที่เลือกทั้งหมด")

        if submitted:
            line_lines, count = [], 0
            for s, d in due_list:
                if picks.get(s["name"]):
                    period = s["current_period"]
                    amt = compute_due_amount(s)
                    pay_one_period(s)
                    rec = float(s["history"][-1].get("received", 0))
                    extra = f" 🎉รับ {rec:,.0f}" if rec else ""
                    line_lines.append(f"- {s['name']} งวด {period}: {amt:,.0f} ฿{extra}")
                    count += 1
            if count:
                save_data(st.session_state.db)
                if not mute_line and line_lines:
                    send_line_message(f"🌸 {st.session_state.current_user} บันทึกจ่ายวันนี้ ({count} วง)\n" + "\n".join(line_lines))
                st.success(f"บันทึกจ่าย {count} วงเรียบร้อย! 🎀")
                st.rerun()
            else:
                st.warning("ยังไม่ได้เลือกวงไหนเลยครับ")

    # ===== ส่วนที่ 2: กรอกผลเปีย (ในหน้าเดียวกัน ไม่ต้องไปหน้าอื่น) =====
    if waiting:
        st.divider()
        st.subheader("🌙 กรอกผลเปีย (วงที่จ่ายแล้ว)")
        for s in waiting:
            num_hands = int(s.get("num_hands", 1))
            times_won = sum(1 for h in s["history"] if h.get("win") == "ฉันเปียเอง")
            period = s["history"][-1].get("p", "?")
            st.markdown(f"**{get_emoji(s)} {s['name']}** · งวด {period}")
            wc1, wc2, wc3 = st.columns([1.2, 1.2, 1])
            bid_amt = wc1.number_input("ยอดดอกที่ชนะ (บาท)", min_value=0.0, key=f"wbid_{s['name']}")
            can_win = times_won < num_hands
            who = wc2.selectbox("ใครได้เปียงวดนี้?", (["คนอื่น", "ฉันเปียเอง"] if can_win else ["คนอื่น (สิทธิ์ครบแล้ว)"]), key=f"wwho_{s['name']}")
            is_me = (who == "ฉันเปียเอง")
            if wc3.button("บันทึกผล", key=f"wbtn_{s['name']}"):
                resolve_bid(s, bid_amt, is_me)
                save_data(st.session_state.db)
                if not mute_line:
                    send_line_message(f"🌸 อัปเดตผลเปียวง {s['name']} งวด {period}\nคนเปียได้: {'คุณ' if is_me else 'คนอื่น'}\nยอดดอก: {bid_amt:,.2f} ฿")
                st.rerun()

    # ===== ย้อนกลับงวดล่าสุด (กดจ่ายผิด) =====
    st.divider()
    with st.expander("↩️ เผลอกดจ่ายผิดวง? ย้อนกลับงวดล่าสุดได้ที่นี่"):
        render_undo_section(user_shares, "today")

# ====================================================
# --- เมนู 2: สร้างวงแชร์ใหม่ (วางข้อความประกาศ -> วิเคราะห์อัตโนมัติ) ---
# ====================================================
elif menu == "➕ สร้างวงแชร์ใหม่":
    st.title("➕ ตั้งค่างานแชร์ใหม่")
    st.caption("วิธีใช้: วางข้อความประกาศวงจากท้าวแชร์ในช่องด้านล่าง → กด 'วิเคราะห์ข้อความ' "
               "ระบบจะกรอกข้อมูลให้อัตโนมัติ (รวมถึงวันจ่ายจริงของแต่ละงวด) จากนั้นตรวจ/แก้ส่วนที่ขาดแล้วกดสร้างวง")

    raw_text = st.text_area("📋 วางข้อความประกาศวงแชร์ที่นี่", height=260,
                            value=st.session_state.get("c_raw_keep", ""))
    bcol1, bcol2 = st.columns(2)
    if bcol1.button("🔍 วิเคราะห์ข้อความ"):
        st.session_state.c_parsed = parse_share_text(raw_text)
        st.session_state.c_raw_keep = raw_text
        st.session_state.c_parse_n = st.session_state.get("c_parse_n", 0) + 1
        st.success("วิเคราะห์เรียบร้อย! ตรวจสอบ/แก้ไขข้อมูลด้านล่างได้เลย")
    if bcol2.button("🧹 ล้างข้อมูลที่วิเคราะห์ / เริ่มใหม่"):
        for k in ["c_parsed", "c_raw_keep"]:
            st.session_state.pop(k, None)
        st.session_state.c_parse_n = st.session_state.get("c_parse_n", 0) + 1
        st.rerun()

    p = st.session_state.get("c_parsed", {}) or {}
    pn = st.session_state.get("c_parse_n", 0)   # ต่อท้าย key เพื่อรีเฟรชค่า default เมื่อวิเคราะห์ใหม่

    st.divider()
    st.subheader("📝 ตรวจสอบ & เติมข้อมูลวงแชร์")

    type_options = ["แชร์เปีย (ประมูลดอกเบี้ย)", "แชร์ขั้นบันได (เฉพาะมือของเรา)"]
    default_type_idx = type_options.index(p["share_type"]) if p.get("share_type") in type_options else 0
    share_type = st.radio("รูปแบบวงแชร์ 🏷️ (ระบบเดาให้ ปรับได้)", type_options, index=default_type_idx, key=f"c_type_{pn}")

    ca, cb = st.columns(2)
    name = ca.text_input("ชื่อวงแชร์", value=p.get("name", ""), key=f"c_name_{pn}")
    num_hands = cb.number_input("จำนวนมือที่เราเล่นในวงนี้", min_value=1, step=1,
                                value=int(p.get("num_hands", 1)), key=f"c_hands_{pn}")

    ce, cf = st.columns(2)
    _def_emoji = p.get("emoji", "🎀")
    _emoji_idx = THEME_EMOJIS.index(_def_emoji) if _def_emoji in THEME_EMOJIS else 0
    emoji = ce.selectbox("อิโมจิประจำวง", THEME_EMOJIS, index=_emoji_idx, key=f"c_emoji_{pn}")
    color = cf.color_picker("สีประจำวง", value=p.get("color", "#FF69B4"), key=f"c_color_{pn}")
    st.markdown(f"<span class='chip' style='background:{color};color:{_text_on(color)};'>{emoji} {name or 'ชื่อวง'}</span>", unsafe_allow_html=True)

    cc, cd = st.columns(2)
    principal = cc.number_input("ยอดเงินต้นรวม (ต้น)", min_value=0.0,
                                value=float(p.get("principal", 0.0)), key=f"c_principal_{pn}")
    current_period = cd.number_input("ตอนนี้อยู่งวดที่ (งวดถัดไปที่จะจ่าย)", min_value=1, step=1,
                                     value=int(p.get("current_period", 1)), key=f"c_curper_{pn}")

    # ---------- ตารางวันจ่ายจริง ----------
    st.write("🗓️ **ตารางวันจ่าย/รับเงินจริงของแต่ละงวด** — แก้ไขได้ ถ้าระบบอ่านผิด/มีงวดที่ท้าวหยุดรับ")
    period_dates_parsed = p.get("period_dates", [])
    gen_periods = max(1, len(period_dates_parsed))
    if period_dates_parsed:
        sched_df = pd.DataFrame({"งวดที่": list(range(1, len(period_dates_parsed) + 1)),
                                 "วันที่ (YYYY-MM-DD)": period_dates_parsed})
    else:
        st.info("ไม่พบตารางวันที่ในข้อความ — กรอกจำนวนงวด แล้วพิมพ์วันที่เอง (รูปแบบ YYYY-MM-DD หรือ วัน/เดือน)")
        gen_periods = st.number_input("จำนวนงวดทั้งหมด", min_value=1, step=1, value=1, key=f"c_genper_{pn}")
        sched_df = pd.DataFrame({"งวดที่": list(range(1, int(gen_periods) + 1)),
                                 "วันที่ (YYYY-MM-DD)": [""] * int(gen_periods)})
    edited_sched = st.data_editor(sched_df, num_rows="dynamic", use_container_width=True, key=f"c_sched_{pn}")

    # ---------- ความถี่สำรอง ----------
    with st.expander("⚙️ ความถี่ (ใช้สำรองเฉพาะกรณีไม่มีวันที่ในตาราง)"):
        freq_types = ["รายวัน", "รายสัปดาห์", "รายเดือน"]
        fidx = freq_types.index(p.get("freq_type", "รายวัน")) if p.get("freq_type") in freq_types else 0
        fc1, fc2 = st.columns(2)
        freq_type = fc1.selectbox("รูปแบบความถี่", freq_types, index=fidx, key=f"c_freqtype_{pn}")
        freq_val = fc2.number_input("ทุกๆ กี่หน่วย", min_value=1, value=int(p.get("freq_val", 1)), key=f"c_freqval_{pn}")

    # ---------- ข้อมูลเฉพาะประเภท ----------
    base_payment = 0.0
    hands_data = []
    start_bid = float(p.get("start_bid", 0.0))
    admin_fee = float(p.get("admin_fee", 0.0))

    if share_type.startswith("แชร์เปีย"):
        bc1, bc2 = st.columns(2)
        base_payment = bc1.number_input("ยอดส่งฐาน ต่อ 1 มือ (ส่งมือละ)", min_value=0.0,
                                        value=float(p.get("base_payment", 0.0)), key=f"c_base_{pn}")
        start_bid = bc2.number_input("ดอกเริ่มต้น/เปียขั้นต่ำ (เก็บไว้อ้างอิง)", min_value=0.0,
                                     value=start_bid, key=f"c_startbid_{pn}")
        st.info(f"💡 เล่น {int(num_hands)} มือ → ยอดส่งฐานรวม {base_payment * num_hands:,.2f} บาท/งวด "
                f"(ยังไม่รวมดอกที่ต้องจ่ายเองตอนเปียได้)")
    else:
        admin_fee = st.number_input("ค่าดูแล (ถ้ามี)", min_value=0.0, value=admin_fee, key=f"c_admin_{pn}")
        if p.get("members"):
            with st.expander("📋 รายชื่อ/ตารางที่ระบบอ่านได้จากข้อความ (ไว้ดูประกอบการเลือกมือของเรา)"):
                st.dataframe(pd.DataFrame(p["members"]), use_container_width=True)
        st.write("🎯 **ระบุรายละเอียดเฉพาะ 'มือของเรา' (แชร์ขั้นบันได)**")
        total_p_now = max(1, len(edited_sched))
        for i in range(int(num_hands)):
            st.write(f"**มือที่ {i+1}**")
            h1, h2, h3 = st.columns(3)
            hp = h1.number_input(f"รับเงินงวดที่ (มือ {i+1})", min_value=1, max_value=total_p_now, step=1,
                                 value=min(i + 1, total_p_now), key=f"c_hp_{i}_{pn}")
            hpay = h2.number_input(f"จ่ายงวดละ (มือ {i+1})", min_value=0.0, value=0.0, key=f"c_hpay_{i}_{pn}")
            hamt = h3.number_input(f"เงินต้นที่ได้รับ (มือ {i+1})", min_value=0.0,
                                   value=float(principal), key=f"c_hamt_{i}_{pn}")
            hands_data.append({"period": int(hp), "payment": float(hpay), "amount": float(hamt)})

    # ---------- สร้างวง ----------
    st.divider()
    if st.button("💖 สร้างวงแชร์"):
        final_dates = []
        for _, row in edited_sched.iterrows():
            norm = _normalize_date_str(row.get("วันที่ (YYYY-MM-DD)", ""))
            if norm:
                final_dates.append(norm)

        if not name:
            st.error("กรุณากรอกชื่อวงแชร์ก่อนครับ")
        else:
            total_periods = len(final_dates) if final_dates else int(gen_periods)
            start_date_str = final_dates[0] if final_dates else date.today().strftime("%Y-%m-%d")
            new_share = {
                "owner": st.session_state.current_user, "share_type": share_type, "name": name,
                "emoji": emoji, "color": color,
                "principal": float(principal), "total_periods": int(total_periods), "base_payment": float(base_payment),
                "num_hands": int(num_hands), "hands_data": hands_data,
                "start_date": start_date_str, "freq_type": freq_type, "freq_val": int(freq_val),
                "period_dates": final_dates,
                "start_bid": float(start_bid), "admin_fee": float(admin_fee),
                "current_period": int(current_period), "is_me_won": False, "my_bid_amount": 0.0,
                "other_bids": [], "history": [], "source_text": st.session_state.get("c_raw_keep", "")
            }
            st.session_state.db["shares"].append(new_share)
            save_data(st.session_state.db)
            for k in ["c_parsed", "c_raw_keep"]:
                st.session_state.pop(k, None)
            st.session_state.c_parse_n = st.session_state.get("c_parse_n", 0) + 1
            st.success(f"สร้างวงแชร์ '{name}' สำเร็จ! ({total_periods} งวด) "
                       f"ไปที่เมนู 'วงแชร์ของฉัน' ได้เลย 🎉")

# ====================================================
# --- เมนู 3: สรุปภาพรวม ---
# ====================================================
elif menu == "📊 สรุปกำไร/ขาดทุนรวม":
    st.title("📊 สรุปภาพรวมของคุณ")
    colA, colB = st.columns(2)
    start_date = colA.date_input("ตั้งแต่วันที่", value=datetime(2024, 1, 1))
    end_date = colB.date_input("ถึงวันที่", value=datetime.now())

    total_paid, total_received = 0, 0
    summary_data = []

    for s in user_shares:
        share_paid, share_received = 0, 0
        for h in s["history"]:
            try:
                h_date = datetime.strptime(h["date"], "%Y-%m-%d").date()
                if start_date <= h_date <= end_date:
                    share_paid += float(h["paid"])
                    share_received += float(h["received"])
            except: pass
        t_type = "ขั้นบันได" if s.get("share_type", "").startswith("แชร์ขั้นบันได") else "แชร์เปีย"
        summary_data.append({"ชื่อวงแชร์": f"{get_emoji(s)} {s['name']}", "รูปแบบ": t_type, "ยอดจ่ายรวม": share_paid, "ยอดรับรวม": share_received, "กำไร/ขาดทุน": share_received - share_paid})
        total_paid += share_paid
        total_received += share_received

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("ยอดจ่ายรวมทั้งหมด", f"{total_paid:,.2f} ฿")
    c2.metric("ยอดรับรวมทั้งหมด", f"{total_received:,.2f} ฿")
    c3.metric("กำไรสุทธิ", f"{total_received - total_paid:,.2f} ฿", delta=total_received - total_paid)

    if summary_data:
        st.dataframe(pd.DataFrame(summary_data).style.format({"ยอดจ่ายรวม": "{:,.2f}", "ยอดรับรวม": "{:,.2f}", "กำไร/ขาดทุน": "{:,.2f}"}), use_container_width=True)

        st.subheader("📈 กราฟกำไร/ขาดทุน")
        cg1, cg2 = st.columns(2)
        with cg1:
            st.caption("กำไร/ขาดทุนรายวง (ในช่วงที่เลือก)")
            st.bar_chart(pd.DataFrame(summary_data).set_index("ชื่อวงแชร์")[["กำไร/ขาดทุน"]], color="#FF69B4")
        with cg2:
            st.caption("กำไรสะสมตามวันที่")
            rows = []
            for s in user_shares:
                for h in s.get("history", []):
                    try:
                        hd = datetime.strptime(h["date"], "%Y-%m-%d").date()
                    except:
                        continue
                    if start_date <= hd <= end_date:
                        rows.append({"วันที่": hd, "net": float(h.get("received", 0)) - float(h.get("paid", 0))})
            if rows:
                cdf = pd.DataFrame(rows).groupby("วันที่")["net"].sum().sort_index().cumsum()
                st.line_chart(cdf, color="#FF1493")
            else:
                st.info("ยังไม่มีประวัติในช่วงนี้")

    st.divider()
    st.subheader("🔮 พยากรณ์กำไรเมื่อจบทุกวง")
    proj_rows = []
    for s in user_shares:
        pj = project_circle(s)
        proj_rows.append({"ชื่อวงแชร์": f"{get_emoji(s)} {s['name']}", "จ่ายทั้งหมด(คาด)": pj["pay"],
                          "รับทั้งหมด(คาด)": pj["receive"], "กำไรคาดการณ์": pj["profit"]})
    if proj_rows:
        pdf = pd.DataFrame(proj_rows)
        total_proj = float(pdf["กำไรคาดการณ์"].sum())
        st.metric("กำไรคาดการณ์รวมเมื่อจบทุกวง", f"{total_proj:,.2f} ฿", delta=total_proj)
        st.bar_chart(pdf.set_index("ชื่อวงแชร์")[["กำไรคาดการณ์"]], color="#FFB6C1")
        st.dataframe(pdf.style.format({"จ่ายทั้งหมด(คาด)": "{:,.2f}", "รับทั้งหมด(คาด)": "{:,.2f}", "กำไรคาดการณ์": "{:,.2f}"}), use_container_width=True)
        st.caption("ℹ️ วงเปียที่ยังไม่ได้เปีย = กรณีดีสุด (เปียงวดท้าย) ตัวเลขจริงขึ้นกับว่าเปียงวดไหนและเปียดอกเท่าไหร่ ดูจุดคุ้มทุนรายวงได้ในหน้า 'วงแชร์ของฉัน'")
    else:
        st.info("ยังไม่มีวงให้พยากรณ์")

    st.divider()
    if st.button("🔔 ทดสอบส่ง LINE ยอดที่ต้องจ่าย 'วันนี้' (ส่งหาทุกคน)"):
        today = date.today()
        due_msgs = []
        for s in user_shares:
            if s["current_period"] <= s["total_periods"]:
                if get_period_date(s, s["current_period"]) == today:
                    num_h = int(s.get("num_hands", 1))
                    if s.get("share_type", "แชร์เปีย").startswith("แชร์เปีย"):
                        amt = compute_due_amount(s)
                        due_msgs.append(f"- {s['name']} ({num_h} มือ): {amt:,.2f} ฿")
                    else:
                        amt = sum(float(hd["payment"]) for hd in s.get("hands_data", []))
                        due_msgs.append(f"- {s['name']} (ขั้นบันได {num_h} มือ): {amt:,.2f} ฿")
        if due_msgs:
            msg = f"🌸 แจ้งเตือนแชร์วันนี้ ({st.session_state.current_user})\n" + "\n".join(due_msgs)
            if send_line_message(msg): st.success("ส่งแจ้งเตือนสำเร็จ!")
            else: st.error("ส่ง LINE ไม่สำเร็จ ตรวจสอบ Token")
        else:
            st.success("วันนี้คุณไม่มีแชร์ที่ต้องจ่ายครับ 🎉")
