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
# 🔴 จุดที่ 1: ตั้งค่า LINE Notify และ Google Sheets
# ====================================================
LINE_ACCESS_TOKEN = ""
SHEET_URL = "https://docs.google.com/spreadsheets/d/1HNNJT-rFCR55FNdvMtWyKIyJrE0ZgKecYKoFAsUwdfI/edit?usp=sharing"

def send_line_message(message):
    if not LINE_ACCESS_TOKEN:
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

# ====================================================
# --- การตั้งค่าหน้าจอและ Theme (Sanrio Style) ---
# ====================================================
st.set_page_config(page_title="Share rae rae la", layout="wide", page_icon="🎀")
st.markdown("""
    <style>
    .main { background-color: #FFF0F5; }
    .stButton>button { background-color: #FFB6C1; color: black; border-radius: 20px; border: 2px solid #FF69B4; font-family: 'Sukhumvit Set', sans-serif; }
    .stButton>button:hover { background-color: #FF69B4; color: white; }
    h1, h2, h3 { color: #FF1493; font-family: 'Sukhumvit Set', sans-serif; }
    .stMetric { background-color: white; padding: 15px; border-radius: 15px; box-shadow: 2px 2px 10px rgba(255, 182, 193, 0.5); }
    </style>
    """, unsafe_allow_html=True)

if "db" not in st.session_state: st.session_state.db = load_data()
if "current_user" not in st.session_state: st.session_state.current_user = None

# ====================================================
# --- หน้า 1: เลือกผู้เล่น (Login) ---
# ====================================================
if st.session_state.current_user is None:
    st.image("https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzRjM2UwZmFjMjUyYTNmNWU1N2U0ZTVmMWJlODQ2NGRlNmUwZjQwZCZlcD12MV9pbnRlcm5hbF9naWZzX2dpZklkJmN0PWc/10bKPDUM5H7m7u/giphy.gif", width=150)
    st.title("🎀 ยินดีต้อนรับสู่ Share rae rae la")
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
# --- Sidebar: เมนูนำทาง ---
# ====================================================
st.sidebar.image("https://i.pinimg.com/originals/60/0a/85/600a850123992b8d00924968846c483a.png", use_container_width=True)
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
        share_type = s.get("share_type", "แชร์เปีย") # เช็กประเภทแชร์
        
        current_due_date = calculate_due_date(s["start_date"], s["current_period"], s["freq_type"], s["freq_val"]) if s["current_period"] <= s["total_periods"] else None
        
        st.markdown(f"**รูปแบบวงแชร์:** 🏷️ {share_type}")
        col1, col2, col3, col4 = st.columns(4)
        paid = sum(float(h["paid"]) for h in s["history"])
        received = sum(float(h["received"]) for h in s["history"])
        col1.metric("จ่ายไปแล้ว", f"{paid:,.2f} ฿")
        col2.metric("ได้รับมาแล้ว", f"{received:,.2f} ฿")
        col3.metric("กำไร/ขาดทุน", f"{received - paid:,.2f} ฿")
        
        if share_type == "แชร์เปีย":
            col4.metric("ดอกเบี้ยสะสม", f"{sum(float(h['bid']) for h in s['history']):,.2f} ฿")
        else:
            col4.metric("เงินต้นรวม", f"{s['principal']:,.2f} ฿")
            
        st.info(f"🗓️ **งวดถัดไปวันที่:** {current_due_date.strftime('%d/%m/%Y') if current_due_date else 'จบวงแล้ว'}")

        with st.expander("⚙️ ลบวงแชร์นี้"):
            if st.button("🗑️ ยืนยันการลบวงแชร์นี้"):
                st.session_state.db["shares"].remove(s)
                save_data(st.session_state.db)
                st.rerun()

        # --- ส่วนบันทึกการจ่ายเงิน (แยกตามประเภทแชร์) ---
        if s["current_period"] <= s["total_periods"]:
            st.subheader(f"📝 บันทึกงวดที่ {s['current_period']}")
            
            if share_type == "แชร์เปีย":
                due = s["base_payment"] + sum(float(h["bid"]) for h in s["history"] if h["win"] == "ฉันเปียเอง")
                with st.expander(f"บันทึกการจ่าย (ยอดเรียกเก็บ: {due:,.2f} บาท)", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    bid_amt = c1.number_input("ยอดเปียงวดนี้ (ถ้ามี)", min_value=0.0)
                    winner = c2.selectbox("ใครเปีย?", ["คนอื่น", "ฉันเปียเอง"])
                    if c3.button("✅ ยืนยันการจ่ายเงิน"):
                        rec_amt = (s["base_payment"] * s["total_periods"]) + sum(s.get("other_bids", [])) if winner == "ฉันเปียเอง" else 0
                        s["history"].append({"p": s["current_period"], "date": datetime.now().strftime("%Y-%m-%d"), "paid": due, "received": rec_amt, "bid": bid_amt, "win": winner})
                        if winner == "ฉันเปียเอง":
                            s["is_me_won"] = True
                            s["my_bid_amount"] = s.get("my_bid_amount", 0) + bid_amt
                        else:
                            if "other_bids" not in s: s["other_bids"] = []
                            s["other_bids"].append(bid_amt)
                        s["current_period"] += 1
                        save_data(st.session_state.db)
                        send_line_message(f"🌸 บัญชี: {st.session_state.current_user}\nจ่ายวง {s['name']} งวด {s['current_period']-1} แล้ว!\nยอด: {due:,.2f} ฿")
                        st.rerun()
            
            else: # ถ้าเป็นแชร์ขั้นบันได
                with st.expander(f"บันทึกการจ่ายแชร์ขั้นบันไดงวดที่ {s['current_period']}", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    pay_amt = c1.number_input("💸 ยอดส่งงวดนี้ (ดูจากตารางของท้าว)", min_value=0.0)
                    is_receive = c2.checkbox("🎉 ถึงคิวรับเงินงวดนี้!")
                    rec_amt = c2.number_input("ยอดเงินที่ได้รับสุทธิ", min_value=0.0, value=float(s["principal"])) if is_receive else 0.0
                    
                    if c3.button("✅ ยืนยันการจ่ายเงิน"):
                        s["history"].append({"p": s["current_period"], "date": datetime.now().strftime("%Y-%m-%d"), "paid": pay_amt, "received": rec_amt, "bid": 0, "win": "ฉันเปียเอง" if is_receive else "คนอื่น"})
                        s["current_period"] += 1
                        save_data(st.session_state.db)
                        msg = f"🎀 บัญชี: {st.session_state.current_user}\nส่งแชร์วง {s['name']} งวด {s['current_period']-1} แล้ว!\nยอดส่ง: {pay_amt:,.2f} ฿"
                        if is_receive: msg += f"\n🎉 ได้รับเงินแชร์: {rec_amt:,.2f} ฿"
                        send_line_message(msg)
                        st.rerun()

        st.divider()
        st.subheader("📜 ประวัติการส่ง (พิมพ์แก้ไขได้)")
        if s["history"]:
            edited_df = st.data_editor(pd.DataFrame(s["history"]), num_rows="dynamic", use_container_width=True)
            if st.button("💾 บันทึกการแก้ไขตาราง"):
                s["history"] = edited_df.to_dict("records")
                s["current_period"] = len(s["history"]) + 1
                save_data(st.session_state.db)
                st.success("อัปเดตประวัติเรียบร้อย!")
                st.rerun()

# ====================================================
# --- เมนู 2: สร้างวงแชร์ใหม่ ---
# ====================================================
elif menu == "➕ สร้างวงแชร์ใหม่":
    st.title("➕ ตั้งค่างานแชร์ใหม่")
    with st.form("create_form"):
        share_type = st.radio("รูปแบบวงแชร์ 🏷️", ["แชร์เปีย (ประมูลดอกเบี้ย)", "แชร์ขั้นบันได (ส่งยอดตามตาราง)"])
        name = st.text_input("ชื่อวงแชร์")
        principal = st.number_input("เงินต้นรวม / ยอดรับทั้งหมด", min_value=0.0)
        periods = st.number_input("จำนวนงวดทั้งหมด", min_value=1, step=1)
        base = st.number_input("ยอดส่งฐาน (ถ้าเป็นแชร์ขั้นบันไดให้ใส่ 0)", min_value=0.0) if share_type == "แชร์เปีย" else 0.0
        
        st.write("🗓️ **ตั้งค่าความถี่และการชำระ**")
        start_date = st.date_input("วันที่เริ่มต้นแชร์งวดแรก")
        col1, col2 = st.columns(2)
        freq_type = col1.selectbox("รูปแบบความถี่", ["รายวัน", "รายสัปดาห์", "รายเดือน"])
        freq_val = col2.number_input(f"ทุกๆ กี่{freq_type.replace('ราย','')}", min_value=1, value=1)
        
        if st.form_submit_button("💖 สร้างวงแชร์"):
            if name:
                new_share = {
                    "owner": st.session_state.current_user, "share_type": share_type, "name": name, 
                    "principal": principal, "total_periods": periods, "base_payment": base,
                    "start_date": start_date.strftime("%Y-%m-%d"), "freq_type": freq_type, "freq_val": freq_val,
                    "current_period": 1, "is_me_won": False, "my_bid_amount": 0.0, "other_bids": [], "history": []
                }
                st.session_state.db["shares"].append(new_share)
                save_data(st.session_state.db)
                st.success(f"สร้างวงแชร์สำเร็จ! ไปที่เมนู 'วงแชร์ของฉัน' ได้เลย")

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
        summary_data.append({"ชื่อวงแชร์": s["name"], "รูปแบบ": s.get("share_type", "แชร์เปีย"), "ยอดจ่ายรวม": share_paid, "ยอดรับรวม": share_received, "กำไร/ขาดทุน": share_received - share_paid})
        total_paid += share_paid
        total_received += share_received
    
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("ยอดจ่ายรวมทั้งหมด", f"{total_paid:,.2f} ฿")
    c2.metric("ยอดรับรวมทั้งหมด", f"{total_received:,.2f} ฿")
    c3.metric("กำไรสุทธิ", f"{total_received - total_paid:,.2f} ฿", delta=total_received - total_paid)
    
    if summary_data:
        st.dataframe(pd.DataFrame(summary_data).style.format({"ยอดจ่ายรวม": "{:,.2f}", "ยอดรับรวม": "{:,.2f}", "กำไร/ขาดทุน": "{:,.2f}"}), use_container_width=True)
    
    st.divider()
    if st.button("🔔 ทดสอบส่ง LINE ยอดที่ต้องจ่าย 'วันนี้' (ส่งหาทุกคน)"):
        today = date.today()
        due_msgs = []
        for s in user_shares:
            if s["current_period"] <= s["total_periods"]:
                if calculate_due_date(s["start_date"], s["current_period"], s["freq_type"], s["freq_val"]) == today:
                    if s.get("share_type", "แชร์เปีย") == "แชร์เปีย":
                        amt = s["base_payment"] + sum(float(h["bid"]) for h in s["history"] if h["win"] == "ฉันเปียเอง")
                        due_msgs.append(f"- {s['name']}: {amt:,.2f} ฿")
                    else:
                        due_msgs.append(f"- {s['name']} (ขั้นบันได): ดูยอดในตาราง ฿")
        if due_msgs:
            msg = f"🌸 แจ้งเตือนแชร์วันนี้ ({st.session_state.current_user})\n" + "\n".join(due_msgs)
            if send_line_message(msg): st.success("ส่งแจ้งเตือนสำเร็จ!")
            else: st.error("ส่ง LINE ไม่สำเร็จ ตรวจสอบ Token")
        else:
            st.success("วันนี้คุณไม่มีแชร์ที่ต้องจ่ายครับ 🎉")
