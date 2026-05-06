import streamlit as st
import pandas as pd
import json
import os
import requests
import gspread
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from google.oauth2.service_account import Credentials

# ====================================================
# 🔴 จุดที่ 1: ตั้งค่า LINE Notify (ใช้แค่ Token ตัวเดียว)
# ====================================================
LINE_ACCESS_TOKEN = "xQr8uwbfyrux9WgXpyuNgtOZY+nlP3wvJUqZKwBaLnqTXZeDa1Ph4FiN2dGLuY7W9aRLn/4Yv0wtNt5mjvBLCDO6a3scT1IfwL9rRxoHumHsYD9HyYfQPZifZWNCUcY8zkO1WmX9w23stY+d7Ck1MgdB04t89/1O/w1cDnyilFU="

# ====================================================
# 🔴 จุดที่ 2: ตั้งค่า Google Sheets
# ====================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1HNNJT-rFCR55FNdvMtWyKIyJrE0ZgKecYKoFAsUwdfI/edit?usp=sharing"


# --- ฟังก์ชันส่งแจ้งเตือน LINE (แบบ Broadcast) ---
def send_line_message(message):
    if not LINE_ACCESS_TOKEN or LINE_ACCESS_TOKEN == "xQr8uwbfyrux9WgXpyuNgtOZY+nlP3wvJUqZKwBaLnqTXZeDa1Ph4FiN2dGLuY7W9aRLn/4Yv0wtNt5mjvBLCDO6a3scT1IfwL9rRxoHumHsYD9HyYfQPZifZWNCUcY8zkO1WmX9w23stY+d7Ck1MgdB04t89/1O/w1cDnyilFU=":
        return False
    url = 'https://api.line.me/v2/bot/message/broadcast'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    data = {
        "messages": [
            {
                "type": "text", 
                "text": message
            }
        ]
    }
    try:
        res = requests.post(url, headers=headers, data=json.dumps(data))
        return res.status_code == 200
    except:
        return False

# --- ฟังก์ชันเชื่อมต่อและจัดการ Google Sheets ---
def get_gsheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

def load_data():
    try:
        client = get_gsheet_client()
        sheet = client.open_by_url(SHEET_URL).sheet1
        data_str = sheet.acell('A1').value
        if data_str:
            data = json.loads(data_str)
            if "users" not in data: 
                data["users"] = ["แม้ว", "วิน"]
            return data
    except Exception as e:
        st.warning("⚠️ รอการเชื่อมต่อ Google Sheets หรือยังไม่ได้ใส่ Secrets โค้ดจะใช้ข้อมูลจำลองแทน")
    return {"users": ["แม้ว", "วิน"], "shares": []}

def save_data(data):
    try:
        client = get_gsheet_client()
        sheet = client.open_by_url(SHEET_URL).sheet1
        json_str = json.dumps(data, ensure_ascii=False)
        sheet.update('A1', [[json_str]])
    except Exception as e:
        st.error(f"❌ ไม่สามารถบันทึกข้อมูลลง Google Sheets ได้: {e}")

# --- ฟังก์ชันคำนวณวันชำระเงิน ---
def calculate_due_date(start_date_str, period, freq_type, freq_val):
    base_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    steps = (period - 1) * freq_val
    if freq_type == "รายวัน": return base_date + relativedelta(days=steps)
    elif freq_type == "รายสัปดาห์": return base_date + relativedelta(weeks=steps)
    elif freq_type == "รายเดือน": return base_date + relativedelta(months=steps)
    return base_date

# ====================================================
# --- การตั้งค่าหน้าจอและ Theme ---
# ====================================================
st.set_page_config(page_title="Share rae rae la", layout="wide", page_icon="🌸")
st.markdown("""
    <style>
    .main { background-color: #FFF0F5; }
    .stButton>button { background-color: #FFB6C1; color: black; border-radius: 20px; border: 2px solid #FF69B4; font-family: 'Sukhumvit Set', sans-serif; }
    .stButton>button:hover { background-color: #FF69B4; color: white; }
    h1, h2, h3 { color: #FF1493; font-family: 'Sukhumvit Set', sans-serif; }
    .stMetric { background-color: white; padding: 15px; border-radius: 15px; box-shadow: 2px 2px 10px rgba(255, 182, 193, 0.5); }
    </style>
    """, unsafe_allow_html=True)

if "db" not in st.session_state: 
    st.session_state.db = load_data()
if "current_user" not in st.session_state: 
    st.session_state.current_user = None

# ====================================================
# --- หน้า 1: เลือกผู้เล่น (Login) ---
# ====================================================
if st.session_state.current_user is None:
    st.title("🎀 ยินดีต้อนรับสู่ Share rae rae la")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("👤 กรุณาเลือกชื่อผู้เล่น")
        selected_user = st.selectbox("เลือกชื่อผู้เล่นที่มีอยู่:", st.session_state.db["users"])
        if st.button("เข้าสู่ระบบ"):
            st.session_state.current_user = selected_user
            st.rerun()
    with col2:
        st.subheader("➕ หรือ เพิ่มผู้เล่นใหม่")
        new_user = st.text_input("พิมพ์ชื่อใหม่ที่นี่:")
        if st.button("เพิ่มและเข้าสู่ระบบ"):
            if new_user and new_user not in st.session_state.db["users"]:
                st.session_state.db["users"].append(new_user)
                save_data(st.session_state.db)
                st.session_state.current_user = new_user
                st.rerun()
    st.stop()

# ====================================================
# --- Sidebar: เมนูนำทาง ---
# ====================================================
st.sidebar.title("🎀 Share Menu")
st.sidebar.write(f"👤 เข้าใช้งานโดย: **{st.session_state.current_user}**")
if st.sidebar.button("🔄 เปลี่ยนผู้เล่น"):
    st.session_state.current_user = None
    st.rerun()
st.sidebar.divider()
menu = st.sidebar.radio("ไปที่หน้า:", ["🏠 หน้าแรก & วงแชร์ของฉัน", "➕ สร้างวงแชร์ใหม่", "📊 สรุปกำไร/ขาดทุนรวม"])

user_shares = [s for s in st.session_state.db["shares"] if s.get("owner") == st.session_state.current_user]

# ====================================================
# --- เมนู 1: หน้าแรก & วงแชร์ของฉัน ---
# ====================================================
if menu == "🏠 หน้าแรก & วงแชร์ของฉัน":
    st.title("🌸 วงแชร์ของฉัน")
    
    if not user_shares:
        st.info("คุณยังไม่มีวงแชร์ในระบบ ไปสร้างวงแรกได้ที่เมนู 'สร้างวงแชร์ใหม่' ทางซ้ายมือครับ")
    else:
        selected_name = st.selectbox("เลือกวงแชร์เพื่อดูรายละเอียด:", [s["name"] for s in user_shares])
        s = next(s for s in user_shares if s["name"] == selected_name)
        
        current_due_date = calculate_due_date(s["start_date"], s["current_period"], s["freq_type"], s["freq_val"]) if s["current_period"] <= s["total_periods"] else None
        
        col1, col2, col3, col4 = st.columns(4)
        paid = sum(float(h["paid"]) for h in s["history"])
        received = sum(float(h["received"]) for h in s["history"])
        total_interest = sum(float(h["bid"]) for h in s["history"])
        col1.metric("จ่ายไปแล้ว", f"{paid:,.2f} ฿")
        col2.metric("ได้รับมาแล้ว", f"{received:,.2f} ฿")
        col3.metric("กำไร/ขาดทุน", f"{received - paid:,.2f} ฿")
        col4.metric("ดอกเบี้ยสะสม", f"{total_interest:,.2f} ฿")
        
        st.info(f"🗓️ **งวดถัดไปวันที่:** {current_due_date.strftime('%d/%m/%Y') if current_due_date else 'จบวงแล้ว'}")

        with st.expander("⚙️ ลบวงแชร์นี้"):
            st.warning("หากลบวงแชร์นี้แล้ว ข้อมูลจะหายไปจาก Google Sheets ทันที")
            if st.button("🗑️ ยืนยันการลบวงแชร์นี้"):
                st.session_state.db["shares"].remove(s)
                save_data(st.session_state.db)
                st.success("ลบวงแชร์เรียบร้อยแล้ว")
                st.rerun()

        if s["current_period"] <= s["total_periods"]:
            st.subheader(f"📝 บันทึกงวดที่ {s['current_period']}")
            my_total_past_bids = sum(float(h["bid"]) for h in s["history"] if h["win"] == "ฉันเปียเอง")
            due = s["base_payment"] + my_total_past_bids
            
            with st.expander(f"กดเพื่อบันทึกการจ่ายงวดนี้ (ยอดเรียกเก็บ: {due:,.2f} บาท)", expanded=True):
                c1, c2, c3 = st.columns(3)
                bid_amt = c1.number_input("ยอดเปียงวดนี้ (ถ้ามี)", min_value=0.0)
                winner = c2.selectbox("ใครเปีย?", ["คนอื่น", "ฉันเปียเอง"])
                
                if c3.button("✅ ยืนยันการจ่ายเงิน"):
                    rec_amt = 0
                    if winner == "ฉันเปียเอง":
                        s["is_me_won"] = True
                        if "my_bid_amount" not in s: s["my_bid_amount"] = 0.0
                        s["my_bid_amount"] += bid_amt 
                        rec_amt = (s["base_payment"] * s["total_periods"]) + sum(s.get("other_bids", []))
                    else:
                        if "other_bids" not in s: s["other_bids"] = []
                        s["other_bids"].append(bid_amt)
                    
                    s["history"].append({
                        "p": s["current_period"],
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "paid": due, "received": rec_amt, "bid": bid_amt, "win": winner
                    })
                    s["current_period"] += 1
                    save_data(st.session_state.db)
                    
                    msg = f"🌸 Share rae rae la 🌸\nวง: {s['name']}\nบัญชี: {st.session_state.current_user}\nจ่ายงวดที่ {s['current_period']-1} เรียบร้อย!\n💰 ยอดที่จ่าย: {due:,.2f} บาท"
                    send_line_message(msg)
                    st.success("บันทึกข้อมูลและส่งแจ้งเตือน LINE หาเพื่อนทุกคนเรียบร้อย!")
                    st.rerun()
        else:
            st.success("✨ วงแชร์นี้ส่งครบทุกงวดแล้ว ✨")

        st.divider()
        colA, colB = st.columns(2)
        with colA:
            st.subheader("🗓️ ตารางชำระเงินล่วงหน้า")
            future_schedule = []
            due_predict = s["base_payment"] + sum(float(h["bid"]) for h in s["history"] if h["win"] == "ฉันเปียเอง")
            for p in range(s["current_period"], s["total_periods"] + 1):
                p_date = calculate_due_date(s["start_date"], p, s["freq_type"], s["freq_val"])
                future_schedule.append({"งวดที่": p, "วันที่": p_date.strftime("%Y-%m-%d"), "ยอดจัดเก็บเบื้องต้น": due_predict})
            if future_schedule:
                st.dataframe(pd.DataFrame(future_schedule), use_container_width=True)
            else:
                st.info("ไม่มีตารางค้างชำระ (จบวงแล้ว)")
        
        with colB:
            st.subheader("📜 ประวัติการเปีย (พิมพ์แก้ไขได้)")
            if s["history"]:
                edited_df = st.data_editor(
                    pd.DataFrame(s["history"]), 
                    num_rows="dynamic",
                    use_container_width=True,
                    column_config={
                        "p": "งวดที่", "date": "วันที่", 
                        "paid": st.column_config.NumberColumn("ยอดจ่าย", format="%.2f"),
                        "received": st.column_config.NumberColumn("ยอดรับ", format="%.2f"),
                        "bid": st.column_config.NumberColumn("ยอดเปีย", format="%.2f"),
                        "win": st.column_config.SelectboxColumn("คนเปีย", options=["คนอื่น", "ฉันเปียเอง"])
                    }
                )
                if st.button("💾 บันทึกการแก้ไขตาราง"):
                    new_history = edited_df.to_dict("records")
                    is_me_won = False
                    my_total_bids = 0.0
                    other_bids = []
                    
                    for i, h in enumerate(new_history):
                        h["p"] = i + 1 
                        if h["win"] == "ฉันเปียเอง":
                            is_me_won = True
                            my_total_bids += float(h["bid"])
                        elif h["win"] == "คนอื่น" and float(h["bid"]) > 0:
                            other_bids.append(float(h["bid"]))
                    
                    s["history"] = new_history
                    s["is_me_won"] = is_me_won
                    s["my_bid_amount"] = my_total_bids
                    s["other_bids"] = other_bids
                    s["current_period"] = len(new_history) + 1
                    save_data(st.session_state.db)
                    st.success("อัปเดตประวัติในฐานข้อมูลเรียบร้อย!")
                    st.rerun()

# ====================================================
# --- เมนู 2: สร้างวงแชร์ใหม่ ---
# ====================================================
elif menu == "➕ สร้างวงแชร์ใหม่":
    st.title("➕ ตั้งค่างานแชร์ใหม่")
    with st.form("create_form"):
        name = st.text_input("ชื่อวงแชร์")
        principal = st.number_input("เงินต้นรวมทั้งหมด", min_value=0.0)
        periods = st.number_input("จำนวนงวดทั้งหมด", min_value=1, step=1)
        base = st.number_input("ยอดส่งฐานต่อคนต่องวด", min_value=0.0)
        
        st.write("🗓️ **ตั้งค่าความถี่และการชำระ**")
        start_date = st.date_input("วันที่เริ่มต้นแชร์งวดแรก")
        col1, col2 = st.columns(2)
        freq_type = col1.selectbox("รูปแบบความถี่", ["รายวัน", "รายสัปดาห์", "รายเดือน"])
        freq_val = col2.number_input(f"ทุกๆ กี่{freq_type.replace('ราย','')}", min_value=1, value=1)
        
        if st.form_submit_button("💖 สร้างวงแชร์"):
            if name:
                new_share = {
                    "owner": st.session_state.current_user,
                    "name": name, "principal": principal, "total_periods": periods, "base_payment": base,
                    "start_date": start_date.strftime("%Y-%m-%d"), "freq_type": freq_type, "freq_val": freq_val,
                    "current_period": 1, "is_me_won": False, "my_bid_amount": 0.0, "other_bids": [], "history": []
                }
                st.session_state.db["shares"].append(new_share)
                save_data(st.session_state.db)
                st.success(f"สร้างวงแชร์ '{name}' สำเร็จ! ไปที่เมนู 'วงแชร์ของฉัน' ได้เลย")

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
        
        summary_data.append({"ชื่อวงแชร์": s["name"], "ยอดจ่ายรวม": share_paid, "ยอดรับรวม": share_received, "กำไร/ขาดทุน": share_received - share_paid})
        total_paid += share_paid
        total_received += share_received
    
    st.divider()
    st.subheader("💰 สรุปยอดสุทธิทุกวงรวมกัน")
    c1, c2, c3 = st.columns(3)
    c1.metric("ยอดจ่ายรวมทั้งหมด", f"{total_paid:,.2f} ฿")
    c2.metric("ยอดรับรวมทั้งหมด", f"{total_received:,.2f} ฿")
    c3.metric("กำไรสุทธิ", f"{total_received - total_paid:,.2f} ฿", delta=total_received - total_paid)
    
    st.divider()
    st.subheader("📑 รายละเอียดแยกตามวงแชร์")
    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        st.dataframe(df_summary.style.format({"ยอดจ่ายรวม": "{:,.2f}", "ยอดรับรวม": "{:,.2f}", "กำไร/ขาดทุน": "{:,.2f}"}), use_container_width=True)
    
    st.divider()
    if st.button("🔔 ทดสอบส่ง LINE ยอดที่ต้องจ่าย 'วันนี้' (ส่งหาทุกคน)"):
        today = date.today()
        due_today_msgs = []
        total_due_today = 0
        for s in user_shares:
            if s["current_period"] <= s["total_periods"]:
                d_date = calculate_due_date(s["start_date"], s["current_period"], s["freq_type"], s["freq_val"])
                if d_date == today:
                    d_amt = s["base_payment"] + sum(float(h["bid"]) for h in s["history"] if h["win"] == "ฉันเปียเอง")
                    due_today_msgs.append(f"- วง {s['name']}: {d_amt:,.2f} ฿")
                    total_due_today += d_amt
        if due_today_msgs:
            msg = f"🌸 แจ้งเตือนแชร์วันนี้ (บัญชี: {st.session_state.current_user})\n" + "\n".join(due_today_msgs) + f"\n\n💰 เตรียมเงินรวม: {total_due_today:,.2f} บาท"
            if send_line_message(msg): st.success("ส่งแจ้งเตือนหาทุกคนสำเร็จ!")
            else: st.error("ส่ง LINE ไม่สำเร็จ ตรวจสอบ Token")
        else:
            st.success("วันนี้คุณไม่มีแชร์ที่ต้องจ่ายครับ 🎉")