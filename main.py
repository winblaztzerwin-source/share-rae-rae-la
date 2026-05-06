import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

# --- การตั้งค่าหน้าจอและ Theme ---
st.set_page_config(page_title="Share rae rae la", layout="wide", page_icon="🌸")

# Custom CSS เพื่อทำให้เป็นโทนชมพู Sanrio
st.markdown("""
    <style>
    .main { background-color: #FFF0F5; }
    .stButton>button {
        background-color: #FFB6C1;
        color: black;
        border-radius: 20px;
        border: 2px solid #FF69B4;
        font-family: 'Sukhumvit Set', sans-serif;
    }
    .stButton>button:hover { background-color: #FF69B4; color: white; }
    h1, h2, h3 { color: #FF1493; font-family: 'Sukhumvit Set', sans-serif; }
    .stMetric {
        background-color: white;
        padding: 15px;
        border-radius: 15px;
        box-shadow: 2px 2px 10px rgba(255, 182, 193, 0.5);
    }
    </style>
    """, unsafe_allow_html=True)

# --- ส่วนจัดการข้อมูล (Database Simulation) ---
DB_FILE = "shares_data.json"

def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"shares": []}

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Initialize Session State
if "db" not in st.session_state:
    st.session_state.db = load_data()

# --- Sidebar: เมนูหลัก ---
st.sidebar.title("🎀 Share Menu")
menu = st.sidebar.radio("ไปที่หน้า:", ["🏠 หน้าแรก & วงแชร์ของฉัน", "➕ สร้างวงแชร์ใหม่", "📊 สรุปกำไร/ขาดทุนรวม"])

# --- หน้า 1: หน้าแรก & รายละเอียดวงแชร์ ---
if menu == "🏠 หน้าแรก & วงแชร์ของฉัน":
    st.title("🌸 วงแชร์ของฉัน")
    
    shares = st.session_state.db["shares"]
    if not shares:
        st.info("ยังไม่มีวงแชร์ในระบบ เริ่มสร้างวงแรกได้ที่เมนู 'สร้างวงแชร์ใหม่'")
    else:
        # เลือกวงแชร์ที่ต้องการดู
        share_names = [s["name"] for s in shares]
        selected_name = st.selectbox("เลือกวงแชร์เพื่อดูรายละเอียด:", share_names)
        
        # ค้นหาข้อมูลวงที่เลือก
        idx = next(i for i, s in enumerate(shares) if s["name"] == selected_name)
        s = shares[idx]
        
        # ส่วนแสดงผล Summary ของวงนั้น
        col1, col2, col3 = st.columns(3)
        paid = sum(h["paid"] for h in s["history"])
        received = sum(h["received"] for h in s["history"])
        profit = received - paid
        
        col1.metric("จ่ายไปแล้ว", f"{paid:,.2f} ฿")
        col2.metric("ได้รับมาแล้ว", f"{received:,.2f} ฿")
        col3.metric("กำไร/ขาดทุน", f"{profit:,.2f} ฿", delta=profit)

        # ส่วนบันทึกงวดปัจจุบัน
        if s["current_period"] <= s["total_periods"]:
            st.subheader(f"📝 บันทึกงวดที่ {s['current_period']}")
            due = s["base_payment"] + (s["my_bid_amount"] if s["is_me_won"] else 0)
            
            with st.expander(f"กดเพื่อบันทึกการจ่ายงวดนี้ ({due:,.2f} บาท)", expanded=True):
                c1, c2, c3 = st.columns(3)
                bid_amt = c1.number_input("ยอดเปียงวดนี้ (ถ้ามี)", min_value=0.0)
                winner = c2.selectbox("ใครเป็นคนเปีย?", ["คนอื่น", "ฉันเปียเอง"])
                
                if c3.button("✅ ยืนยันการจ่ายเงิน"):
                    rec_amt = 0
                    if winner == "ฉันเปียเอง":
                        if s["is_me_won"]:
                            st.error("คุณเคยเปียไปแล้วในวงนี้!")
                        else:
                            s["is_me_won"] = True
                            s["my_bid_amount"] = bid_amt
                            rec_amt = (s["base_payment"] * s["total_periods"]) + sum(s["other_bids"])
                    else:
                        s["other_bids"].append(bid_amt)
                    
                    # บันทึกประวัติ
                    s["history"].append({
                        "p": s["current_period"],
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "paid": due,
                        "received": rec_amt,
                        "bid": bid_amt,
                        "win": winner
                    })
                    s["current_period"] += 1
                    save_data(st.session_state.db)
                    st.success("บันทึกข้อมูลเรียบร้อย!")
                    st.rerun()
        else:
            st.success("✨ วงแชร์นี้สิ้นสุดแล้ว ✨")

        # ตารางประวัติ
        if s["history"]:
            st.write("### 📜 ประวัติการส่งแชร์")
            df = pd.DataFrame(s["history"])
            st.dataframe(df, use_container_width=True)

# --- หน้า 2: สร้างวงแชร์ใหม่ ---
elif menu == "➕ สร้างวงแชร์ใหม่":
    st.title("➕ ตั้งค่างานแชร์ใหม่")
    with st.form("create_form"):
        name = st.text_input("ชื่อวงแชร์")
        principal = st.number_input("เงินต้น (รวม)", min_value=0.0)
        periods = st.number_input("จำนวนงวดทั้งหมด", min_value=1, step=1)
        base = st.number_input("ยอดส่งฐานต่อคนต่องวด", min_value=0.0)
        
        if st.form_submit_button("💖 สร้างวงแชร์"):
            new_share = {
                "name": name,
                "principal": principal,
                "total_periods": periods,
                "base_payment": base,
                "current_period": 1,
                "is_me_won": False,
                "my_bid_amount": 0.0,
                "other_bids": [],
                "history": [],
                "created_at": datetime.now().strftime("%Y-%m-%d")
            }
            st.session_state.db["shares"].append(new_share)
            save_data(st.session_state.db)
            st.success(f"สร้างวงแชร์ '{name}' สำเร็จ!")

# --- หน้า 3: สรุปภาพรวม (Filter วันที่) ---
elif menu == "📊 สรุปกำไร/ขาดทุนรวม":
    st.title("📊 สรุปภาพรวมทุกวงแชร์")
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("ตั้งแต่วันที่", value=datetime(2024, 1, 1))
    end_date = col2.date_input("ถึงวันที่", value=datetime.now())
    
    total_paid = 0
    total_received = 0
    
    for s in st.session_state.db["shares"]:
        for h in s["history"]:
            h_date = datetime.strptime(h["date"], "%Y-%m-%d").date()
            if start_date <= h_date <= end_date:
                total_paid += h["paid"]
                total_received += h["received"]
    
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("ยอดจ่ายรวมทั้งหมด", f"{total_paid:,.2f} ฿")
    c2.metric("ยอดรับรวมทั้งหมด", f"{total_received:,.2f} ฿")
    diff = total_received - total_paid
    c3.metric("กำไรสุทธิ", f"{diff:,.2f} ฿", delta=diff)