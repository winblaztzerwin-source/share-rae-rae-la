import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

# --- การตั้งค่าหน้าจอและ Theme ---
st.set_page_config(page_title="Share rae rae la", layout="wide", page_icon="🌸")

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

# --- ส่วนจัดการข้อมูล ---
DB_FILE = "shares_db.json"

def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "users" not in data: 
                data["users"] = ["แม้ว", "วิน"]
            for s in data["shares"]:
                if "owner" not in s: s["owner"] = "นวคุณ" 
            return data
    return {"users": ["แม้ว", "วิน"], "shares": []}

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if "db" not in st.session_state:
    st.session_state.db = load_data()

if "current_user" not in st.session_state:
    st.session_state.current_user = None

# --- หน้า 1: เลือกผู้เล่น (Profile Selection) ---
if st.session_state.current_user is None:
    st.title("🎀 ยินดีต้อนรับสู่ Share rae rae la")
    st.subheader("👤 กรุณาเลือกหรือระบุเจ้าของบัญชี")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        users = st.session_state.db["users"]
        selected_user = st.selectbox("เลือกชื่อผู้เล่นที่มีอยู่:", users)
        if st.button("เข้าสู่ระบบด้วยชื่อนี้"):
            st.session_state.current_user = selected_user
            st.rerun()
            
    with col2:
        st.write("หรือ เพิ่มชื่อผู้เล่นใหม่")
        new_user = st.text_input("พิมพ์ชื่อใหม่ที่นี่:")
        if st.button("เพิ่มและเข้าสู่ระบบ"):
            if new_user and new_user not in users:
                st.session_state.db["users"].append(new_user)
                save_data(st.session_state.db)
                st.session_state.current_user = new_user
                st.rerun()
    st.stop()

# --- Sidebar: เมนูหลัก ---
st.sidebar.title("🎀 Share Menu")
st.sidebar.write(f"👤 เข้าใช้งานโดย: **{st.session_state.current_user}**")
if st.sidebar.button("🔄 เปลี่ยนผู้เล่น"):
    st.session_state.current_user = None
    st.rerun()

st.sidebar.divider()
menu = st.sidebar.radio("ไปที่หน้า:", ["🏠 หน้าแรก & วงแชร์ของฉัน", "➕ สร้างวงแชร์ใหม่", "📊 สรุปกำไร/ขาดทุนรวม"])

user_shares = [s for s in st.session_state.db["shares"] if s.get("owner") == st.session_state.current_user]

# --- หน้าหลัก & จัดการวงแชร์ ---
if menu == "🏠 หน้าแรก & วงแชร์ของฉัน":
    st.title("🌸 วงแชร์ของฉัน")
    
    if not user_shares:
        st.info("คุณยังไม่มีวงแชร์ในระบบ เริ่มสร้างวงแรกได้ที่เมนู 'สร้างวงแชร์ใหม่'")
    else:
        share_names = [s["name"] for s in user_shares]
        selected_name = st.selectbox("เลือกวงแชร์เพื่อดูหรือแก้ไขรายละเอียด:", share_names)
        
        s = next(s for s in user_shares if s["name"] == selected_name)
        
        # 1. Summary
        col1, col2, col3 = st.columns(3)
        paid = sum(float(h["paid"]) for h in s["history"])
        received = sum(float(h["received"]) for h in s["history"])
        profit = received - paid
        
        col1.metric("จ่ายไปแล้ว", f"{paid:,.2f} ฿")
        col2.metric("ได้รับมาแล้ว", f"{received:,.2f} ฿")
        col3.metric("กำไร/ขาดทุน", f"{profit:,.2f} ฿", delta=profit)

        # 2. ฟังก์ชันลบวงแชร์
        with st.expander("⚙️ ตั้งค่า (ลบวงแชร์)"):
            st.warning("หากลบวงแชร์นี้แล้ว จะไม่สามารถกู้คืนข้อมูลได้")
            if st.button("🗑️ ยืนยันการลบวงแชร์นี้"):
                st.session_state.db["shares"].remove(s)
                save_data(st.session_state.db)
                st.success("ลบวงแชร์เรียบร้อยแล้ว")
                st.rerun()

        # 3. บันทึกงวดปัจจุบัน
        if s["current_period"] <= s["total_periods"]:
            st.subheader(f"📝 บันทึกงวดที่ {s['current_period']}")
            
            # คำนวณยอดที่ต้องจ่าย: ยอดฐาน + ยอดเปียสะสมทั้งหมดที่เราเคยเปียได้
            my_total_past_bids = sum(float(h["bid"]) for h in s["history"] if h["win"] == "ฉันเปียเอง")
            due = s["base_payment"] + my_total_past_bids
            
            with st.expander(f"กดเพื่อบันทึกการจ่ายงวดนี้ (ยอดเรียกเก็บ: {due:,.2f} บาท)", expanded=True):
                c1, c2, c3 = st.columns(3)
                bid_amt = c1.number_input("ยอดเปียงวดนี้ (ถ้ามี)", min_value=0.0)
                winner = c2.selectbox("ใครเป็นคนเปีย?", ["คนอื่น", "ฉันเปียเอง"])
                
                if c3.button("✅ ยืนยันการจ่ายเงิน"):
                    rec_amt = 0
                    if winner == "ฉันเปียเอง":
                        # ปลดล็อกการดักจับเปียซ้ำ เพื่อให้เปียได้หลายมือ
                        s["is_me_won"] = True
                        if "my_bid_amount" not in s: s["my_bid_amount"] = 0.0
                        s["my_bid_amount"] += bid_amt # เก็บยอดสะสมลง DB ด้วย
                        
                        rec_amt = (s["base_payment"] * s["total_periods"]) + sum(s.get("other_bids", []))
                    else:
                        if "other_bids" not in s: s["other_bids"] = []
                        s["other_bids"].append(bid_amt)
                    
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
            st.success("✨ วงแชร์นี้ส่งครบทุกงวดแล้ว ✨")

        # 4. ตารางประวัติ & ระบบแก้ไขข้อมูล
        st.divider()
        st.subheader("📜 ประวัติการส่งแชร์ (สามารถแก้ไข/ลบ ข้อมูลในตารางได้โดยตรง)")
        st.caption("💡 ทริค: ดับเบิลคลิกที่ช่องตัวเลขเพื่อแก้ไข หรือเลือกแถวแล้วกด Delete เพื่อลบงวดนั้น")
        
        if s["history"]:
            df = pd.DataFrame(s["history"])
            
            edited_df = st.data_editor(
                df, 
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "p": "งวดที่",
                    "date": "วันที่จ่าย",
                    "paid": st.column_config.NumberColumn("ยอดที่จ่าย", format="%.2f"),
                    "received": st.column_config.NumberColumn("ยอดที่รับ", format="%.2f"),
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
                st.success("อัปเดตประวัติการเปียและการจ่ายเรียบร้อยแล้ว!")
                st.rerun()

# --- หน้า 2: สร้างวงแชร์ใหม่ ---
elif menu == "➕ สร้างวงแชร์ใหม่":
    st.title("➕ ตั้งค่างานแชร์ใหม่")
    with st.form("create_form"):
        name = st.text_input("ชื่อวงแชร์")
        principal = st.number_input("เงินต้น (รวม)", min_value=0.0)
        periods = st.number_input("จำนวนงวดทั้งหมด", min_value=1, step=1)
        base = st.number_input("ยอดส่งฐานต่อคนต่องวด", min_value=0.0)
        
        if st.form_submit_button("💖 สร้างวงแชร์"):
            if not name:
                st.error("กรุณาระบุชื่อวงแชร์")
            else:
                new_share = {
                    "owner": st.session_state.current_user,
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
                st.success(f"สร้างวงแชร์ '{name}' สำเร็จ! ไปที่เมนู 'วงแชร์ของฉัน' เพื่อเริ่มใช้งาน")

# --- หน้า 3: สรุปภาพรวม ---
elif menu == "📊 สรุปกำไร/ขาดทุนรวม":
    st.title("📊 สรุปภาพรวมของคุณ")
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("ตั้งแต่วันที่", value=datetime(2024, 1, 1))
    end_date = col2.date_input("ถึงวันที่", value=datetime.now())
    
    total_paid = 0
    total_received = 0
    
    for s in user_shares:
        for h in s["history"]:
            try:
                h_date = datetime.strptime(h["date"], "%Y-%m-%d").date()
                if start_date <= h_date <= end_date:
                    total_paid += float(h["paid"])
                    total_received += float(h["received"])
            except ValueError:
                pass 
    
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("ยอดจ่ายรวมทั้งหมด", f"{total_paid:,.2f} ฿")
    c2.metric("ยอดรับรวมทั้งหมด", f"{total_received:,.2f} ฿")
    diff = total_received - total_paid
    c3.metric("กำไรสุทธิ", f"{diff:,.2f} ฿", delta=diff)