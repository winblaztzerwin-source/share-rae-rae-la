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
    st.image("https://media.tenor.com/XLwkPdamUikAAAAi/hello-kitty.gif", width=150)
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
mute_line = st.sidebar.checkbox("🔕 ปิดแจ้งเตือน LINE (สำหรับลงข้อมูลย้อนหลัง)")
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
        share_type = s.get("share_type", "แชร์เปีย (ประมูลดอกเบี้ย)")
        num_hands = int(s.get("num_hands", 1))
        
        hands_data = s.get("hands_data", [])
        if not hands_data and not share_type.startswith("แชร์เปีย"):
            hands_data = [{"period": s.get("my_receive_period", 0), "payment": s.get("my_fixed_payment", 0.0), "amount": s.get("my_receive_amount", 0.0)}]
        
        current_due_date = calculate_due_date(s["start_date"], s["current_period"], s["freq_type"], s["freq_val"]) if s["current_period"] <= s["total_periods"] else None
        
        st.markdown(f"**รูปแบบวงแชร์:** 🏷️ {share_type} | **จำนวนมือที่เล่น:** {num_hands} มือ")
        col1, col2, col3, col4 = st.columns(4)
        paid = sum(float(h["paid"]) for h in s["history"])
        received = sum(float(h["received"]) for h in s["history"])
        col1.metric("จ่ายไปแล้ว", f"{paid:,.2f} ฿")
        col2.metric("ได้รับมาแล้ว", f"{received:,.2f} ฿")
        col3.metric("กำไร/ขาดทุน", f"{received - paid:,.2f} ฿")
        
        if share_type.startswith("แชร์เปีย"):
            # แก้ไขแล้ว: ดึงดอกเบี้ยสะสมของทุกคนมารวมกันทั้งหมด
            col4.metric("ดอกเบี้ยสะสม", f"{sum(float(h['bid']) for h in s['history']):,.2f} ฿")
        else:
            total_expected_receive = sum(float(hd["amount"]) for hd in hands_data)
            col4.metric("เงินต้นรวม (เป้าหมาย)", f"{total_expected_receive:,.2f} ฿")
            
        st.info(f"🗓️ **งวดถัดไปวันที่:** {current_due_date.strftime('%d/%m/%Y') if current_due_date else 'จบวงแล้ว'}")

        # --- ⚙️ ส่วนจัดการรายละเอียดและลบวงแชร์ ---
        with st.expander("⚙️ จัดการรายละเอียดวงแชร์ (แก้ไขจำนวนมือ/ลบวง)"):
            st.subheader("🛠️ แก้ไขข้อมูลพื้นฐาน")
            edit_num_hands = st.number_input("แก้ไขจำนวนมือที่เล่น:", min_value=1, value=num_hands, step=1, key="edit_num_hands")
            
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

            if st.button("💾 บันทึกการแก้ไขรายละเอียด"):
                s["num_hands"] = edit_num_hands
                if share_type.startswith("แชร์เปีย"):
                    s["base_payment"] = edit_base
                else:
                    s["hands_data"] = new_hands_data_list
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
                base_total = s["base_payment"] * num_hands
                due = base_total + sum(float(h["bid"]) for h in s["history"] if h.get("win") == "ฉันเปียเอง")
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
                            s["history"][-1]["bid"] = bid_amt
                            s["history"][-1]["win"] = "ฉันเปียเอง" if is_me_winning else "คนอื่น"
                            
                            if is_me_winning:
                                rec_amt = (s["base_payment"] * s["total_periods"]) + sum(s.get("other_bids", []))
                                s["history"][-1]["received"] = rec_amt
                                s["is_me_won"] = True
                                s["my_bid_amount"] = s.get("my_bid_amount", 0) + bid_amt
                            else:
                                if "other_bids" not in s: s["other_bids"] = []
                                s["other_bids"].append(bid_amt)
                            
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

        st.divider()
        colA, colB = st.columns(2)
        with colA:
            st.subheader("🗓️ ตารางชำระเงินล่วงหน้า")
            future_schedule = []
            if share_type.startswith("แชร์เปีย"):
                due_predict = (s["base_payment"] * num_hands) + sum(float(h["bid"]) for h in s["history"] if h.get("win") == "ฉันเปียเอง")
            else:
                due_predict = sum(float(hd["payment"]) for hd in hands_data)
            
            start_table_period = s["current_period"]
            
            for p in range(start_table_period, s["total_periods"] + 1):
                p_date = calculate_due_date(s["start_date"], p, s["freq_type"], s["freq_val"])
                row = {"งวดที่": p, "วันที่": p_date.strftime("%Y-%m-%d"), "ยอดส่งรวม": due_predict}
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
    col_t1, col_t2 = st.columns(2)
    share_type = col_t1.radio("รูปแบบวงแชร์ 🏷️", ["แชร์เปีย (ประมูลดอกเบี้ย)", "แชร์ขั้นบันได (เฉพาะมือของเรา)"])
    num_hands = col_t2.number_input("จำนวนมือที่เล่นในวงนี้", min_value=1, step=1, value=1)
    
    with st.form("create_form"):
        name = st.text_input("ชื่อวงแชร์")
        periods = st.number_input("จำนวนงวดทั้งหมด", min_value=1, step=1)
        base = 0.0
        principal = 0.0
        hands_data = []
        
        if share_type == "แชร์เปีย (ประมูลดอกเบี้ย)":
            principal = st.number_input("ยอดเงินต้นรวมทั้งหมด", min_value=0.0)
            base = st.number_input("ยอดส่งฐาน (ต่อ 1 มือ)", min_value=0.0)
            st.info(f"💡 คุณเล่น {num_hands} มือ ยอดส่งฐานรวมจะเป็น: {base * num_hands:,.2f} บาท/งวด")
        else:
            st.info("🎯 **ข้อมูลแชร์ขั้นบันได (ระบุรายละเอียดแต่ละมือ)**")
            for i in range(num_hands):
                st.write(f"**รายละเอียดของมือที่ {i+1}**")
                c1, c2, c3 = st.columns(3)
                p_period = c1.number_input(f"รับเงินงวดที่ (มือ {i+1})", min_value=1, step=1, key=f"p_{i}")
                p_pay = c2.number_input(f"จ่ายงวดละ (มือ {i+1})", min_value=0.0, key=f"pay_{i}")
                p_amt = c3.number_input(f"เงินต้นที่ได้ (มือ {i+1})", min_value=0.0, key=f"amt_{i}")
                hands_data.append({"period": p_period, "payment": p_pay, "amount": p_amt})

        st.write("🗓️ **ตั้งค่าความถี่และการชำระ**")
        start_date = st.date_input("วันที่เริ่มต้นแชร์งวดแรก")
        col1, col2 = st.columns(2)
        freq_type = col1.selectbox("รูปแบบความถี่", ["รายวัน", "รายสัปดาห์", "รายเดือน"])
        freq_val = col2.number_input(f"ทุกๆ กี่{freq_type.replace('ราย','')}", min_value=1, value=1)
        
        submit_btn = st.form_submit_button("💖 สร้างวงแชร์")
        
        if submit_btn:
            if name:
                new_share = {
                    "owner": st.session_state.current_user, "share_type": share_type, "name": name, 
                    "principal": principal, "total_periods": periods, "base_payment": base,
                    "num_hands": num_hands, "hands_data": hands_data,
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
        t_type = "ขั้นบันได" if s.get("share_type", "").startswith("แชร์ขั้นบันได") else "แชร์เปีย"
        summary_data.append({"ชื่อวงแชร์": s["name"], "รูปแบบ": t_type, "ยอดจ่ายรวม": share_paid, "ยอดรับรวม": share_received, "กำไร/ขาดทุน": share_received - share_paid})
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
                    num_h = int(s.get("num_hands", 1))
                    if s.get("share_type", "แชร์เปีย").startswith("แชร์เปีย"):
                        amt = (s["base_payment"] * num_h) + sum(float(h["bid"]) for h in s["history"] if h.get("win") == "ฉันเปียเอง")
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
