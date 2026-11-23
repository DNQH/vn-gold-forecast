"""Vietnam Gold Forecast – ứng dụng web (Streamlit).

    streamlit run app/dashboard.py

Hai phiên bản giao diện:
  • Dễ hiểu   (views/family.py) – cho người lớn tuổi, người không rành công nghệ.
  • Chuyên sâu (views/pro.py)   – số liệu, kiểm định, giải thích mô hình đầy đủ.
"""
import sys
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parent
for p in (APP, APP.parent / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

st.set_page_config(page_title="Giá vàng Việt Nam – Dự báo", page_icon="🪙", layout="wide",
                   initial_sidebar_state="collapsed")

pages = [
    st.Page(APP / "views" / "family.py", title="Dễ hiểu", icon="🏠", default=True, url_path="de-hieu"),
    st.Page(APP / "views" / "pro.py", title="Chuyên sâu", icon="📊", url_path="chuyen-sau"),
]
# Thanh chuyển trang tự vẽ: luôn nằm trên cùng, không bị gập vào thanh bên trên điện thoại.
pg = st.navigation(pages, position="hidden")
st.markdown("""<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display: none;}
.st-key-topnav {position: sticky; top: 0; z-index: 99; background: var(--vg-bg, #fbfaf7);
                border-bottom: 1px solid #ece8dc; padding: 6px 0 4px; margin-bottom: 4px;}
.st-key-topnav [data-testid="stPageLink"] a {border-radius: 999px; padding: 2px 12px;}
</style>""", unsafe_allow_html=True)
with st.container(key="topnav", horizontal=True, gap="small"):
    for page in pages:
        st.page_link(page, label=page.title, icon=page.icon, width="content")
pg.run()
