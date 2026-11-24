"""Phiên bản DỄ HIỂU – dành cho người lớn tuổi, người không rành công nghệ.

Nguyên tắc: chữ to, ít số, nói bằng lời thường, màu xanh = tăng / đỏ = giảm / xám = khó đoán,
và luôn trung thực về những gì phần mềm KHÔNG đoán được.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import (WEEKDAYS, DOWN, FLAT, GOLD, MUTED, PROC, TARGET_SHORT, UP, bucket_of, calibration, chart, inject_css,
                freshness, live_prices, load, outlook, plotly_layout, ten, tracking, vn, vn_date, vn_now,
                when_label)
from vngold.plain import plain_reason  # noqa: E402  (src/ được ui.py thêm vào sys.path)

inject_css("""
html {font-size: 19px;}
.block-container {max-width: 1180px;}
.hero {background: linear-gradient(135deg,#fffaf0 0%,#fdf3dc 100%); border:1px solid #f1dfb4; border-radius:20px;
       padding: 22px 26px; display:grid; grid-template-columns: 1.15fr 1fr; gap: 18px 40px; align-items:end;}
@media (max-width: 720px) {
  .hero {grid-template-columns: 1fr; padding: 18px;} .hero .big {font-size:2.3rem;} .hero .unit {display:block;}
  h1 {font-size: 1.75rem !important;} h2 {font-size: 1.4rem !important;}
}
.fc-grid.two {grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr));}
.group {font-size:1.05rem; font-weight:700; color:#374151; margin: 18px 0 4px;}
.hero .lbl {font-size:0.95rem; color:#6b5a2e;}
.hero .big {font-size:2.6rem; font-weight:700; color:#1f2937; line-height:1.1;}
.hero .unit {font-size:1rem; color:#6b7280; font-weight:500;}
.hero .chg {font-size:1.05rem; font-weight:600; margin-top:4px;}
.hero .time {font-size:0.85rem; color:#6b7280; margin-top:6px;}
.fc-grid {display:grid; grid-template-columns: repeat(auto-fit, minmax(min(205px, 100%), 1fr)); gap:14px; margin: 6px 0 4px;}
.fc-card {background:#fff; border:1px solid #e5e7eb; border-radius:18px; padding:16px 16px 14px; text-align:center;
          box-shadow: 0 1px 2px rgba(0,0,0,.04);}
.fc-when {font-size:1.05rem; font-weight:700; color:#1f2937;}
.fc-date {font-size:0.8rem; color:#6b7280; margin-bottom:6px;}
.fc-icon {font-size:2.6rem; line-height:1.15; font-weight:700;}
.fc-verdict {font-size:1.25rem; font-weight:800; margin-bottom:6px;}
.fc-main {font-size:1rem; color:#1f2937;}
.fc-main b {font-size:1.3rem;}
.fc-sub {font-size:0.82rem; color:#6b7280; margin-bottom:8px;}
.fc-range {font-size:0.88rem; background:#f8fafc; border-radius:10px; padding:6px 8px; margin:6px 0; color:#374151;}
.fc-conf {font-size:0.85rem; font-weight:600; margin-top:6px;}
.fc-hist {font-size:0.78rem; color:#6b7280; margin-top:4px;}
.note {background:#f8fafc; border-left:5px solid #b7791f; border-radius:10px; padding:14px 18px; margin:8px 0;}
.reason {font-size:1rem; padding:10px 14px; border-radius:12px; background:#fff; border:1px solid #e5e7eb; margin-bottom:8px;}
.dots {display:flex; flex-wrap:wrap; gap:6px; margin:8px 0 4px;}
.dot {width:22px; height:22px; border-radius:50%;}
.stat {font-size:1.05rem; margin: 4px 0;}
.stat b {font-size:1.25rem;}
.stale-banner {background:#fde047; border:3px solid #ca8a04; border-radius:16px; padding:18px 22px; margin:10px 0 14px;
               font-size:1.45rem; font-weight:700; color:#422006; line-height:1.4;}
.fc-card.past {background:#f3f4f6; border-top:6px solid #9ca3af; color:#6b7280;}
.fc-warn {font-size:0.88rem; background:#fef3c7; border:1px solid #f59e0b; border-radius:10px; padding:8px 10px;
          margin:8px 0; color:#78350f; text-align:left;}
.fc-live {font-size:0.88rem; color:#374151; margin-top:4px;}
""")

if not (PROC / "forecast.json").exists():
    st.error("Chưa có dữ liệu dự báo. Người quản trị cần chạy: python scripts/run_pipeline.py")
    st.stop()

fc, df = load()
live = live_prices()

# ------------------------------------------------------------------ tiêu đề + chọn loại vàng
st.markdown("# 🪙 Giá vàng hôm nay và sắp tới")
st.markdown(f"<div class='vg-muted'>Phần mềm tự cập nhật mỗi sáng. Lần cập nhật gần nhất: "
            f"<b>{pd.Timestamp(fc['generated_at']):%H:%M}, {vn_date(fc['generated_at'])}</b></div>",
            unsafe_allow_html=True)
st.write("")
choice = st.segmented_control("Chọn loại vàng", list(TARGET_SHORT.values()), default=TARGET_SHORT["sjc_sell"],
                              label_visibility="collapsed")
tkey = {v: k for k, v in TARGET_SHORT.items()}.get(choice or TARGET_SHORT["sjc_sell"])
T = fc["targets"][tkey]
FR = freshness(fc, df)
TODAY = vn_now().normalize()
if FR["stale"] or FR["source_stale"].get(tkey):
    stop_day = FR["last_observed"][tkey] if FR["source_stale"].get(tkey) and not FR["stale"] else FR["as_of"]
    st.markdown(f"<div class='stale-banner'>⚠️ Dự đoán chưa được cập nhật – số liệu dừng ở {vn_date(stop_day)}. "
                "Đừng dựa vào phần dự đoán bên dưới cho tới khi phần mềm cập nhật.</div>", unsafe_allow_html=True)
buy_col = "sjc_buy" if tkey == "sjc_sell" else "ring_buy"

# ------------------------------------------------------------------ giá hiện tại
s = df[[tkey, buy_col]].dropna()
close_sell, close_buy = float(s[tkey].iloc[-1]), float(s[buy_col].iloc[-1])
prev_sell = float(s[tkey].iloc[-2])
close_day = s.index[-1]
lp = live.get(tkey)
use_live = bool(lp) and pd.Timestamp(lp["ts"]).normalize() >= close_day.normalize()
if use_live:
    sell, buy = lp["price"], lp["buy"]
    ref, ref_txt = close_sell, f"giá chốt {vn_date(close_day)}"
    time_txt = f"Giá đang niêm yết lúc {pd.Timestamp(lp['ts']):%H:%M} {vn_date(lp['ts'])} (nguồn CafeF)"
else:
    sell, buy = close_sell, close_buy
    ref, ref_txt = prev_sell, "phiên trước"
    time_txt = f"Giá chốt phiên {vn_date(close_day)}"
chg = sell - ref
chg_html = (f"<span style='color:{UP}'>▲ Tăng {vn(chg)} triệu</span>" if chg > 0.05 else
            f"<span style='color:{DOWN}'>▼ Giảm {vn(-chg)} triệu</span>" if chg < -0.05 else
            f"<span style='color:{FLAT}'>● Không đổi</span>") + f" <span class='vg-muted'>so với {ref_txt}</span>"
spread = sell - buy
close_spread = close_sell - close_buy
st.markdown(f"""
<div class="hero">
  <div><div class="lbl">Giá BÁN ra (tiệm bán cho mình)</div>
       <div class="big">{vn(sell)} <span class="unit">triệu đồng / lượng</span></div>
       <div class="chg">{chg_html}</div></div>
  <div><div class="lbl">Giá MUA vào (tiệm mua lại của mình)</div>
       <div class="big" style="font-size:2rem">{vn(buy)} <span class="unit">triệu đồng / lượng</span></div>
       <div class="time">{time_txt}</div></div>
</div>""", unsafe_allow_html=True)

# ------------------------------------------------------------------ thẻ dự báo
st.markdown("## Giá vàng sắp tới sẽ thế nào?")
st.markdown(f"<div class='vg-muted'>Tính từ giá chốt <b>{vn_date(close_day)}</b>: "
            f"<b>{vn(T['last_price'])}</b> triệu/lượng (giá bán ra).</div>", unsafe_allow_html=True)

CONF = {"strong": ("●●●○", "Nghiêng rõ về {dir}"), "lean": ("●●○○", "Hơi nghiêng về {dir}"),
        "unclear": ("●○○○", "Không rõ ràng"), "none": ("○○○○", "Chưa đoán được chiều")}


def short_card(h: str, r: dict) -> str:
    p0 = T["last_price"]
    when = when_label(r["target_date"])
    date = vn_date(r["target_date"])
    if pd.Timestamp(r["target_date"]).normalize() < TODAY:
        return f"""<div class="fc-card past">
<div class="fc-when">{when}</div><div class="fc-date">{date}</div>
<div class="fc-icon">⏳</div>
<div class="fc-sub" style="font-size:1rem">Đã qua ngày dự đoán ({vn_date(r['target_date'], False)}) – chờ bản cập nhật mới</div></div>"""
    if h == "5":
        when = "Khoảng 1 tuần nữa"
    elif h == "21":
        when = "Khoảng 1 tháng nữa"
    rng = f"Nhiều khả năng trong khoảng<br><b>{vn(r['lo80'])} – {vn(r['hi80'])}</b> triệu"
    if not r.get("has_edge", True):
        return f"""<div class="fc-card" style="border-top:6px solid {FLAT}">
<div class="fc-when">{when}</div><div class="fc-date">{date}</div>
<div class="fc-icon" style="color:{FLAT}">?</div>
<div class="fc-verdict" style="color:{FLAT}">Khó đoán</div>
<div class="fc-sub">Ở mốc này, phần mềm chưa đoán tăng/giảm tốt hơn việc coi như giá giữ nguyên.</div>
<div class="fc-range">{rng}</div>
<div class="fc-conf" style="color:{FLAT}">{CONF['none'][0]} {CONF['none'][1]}</div></div>"""
    p = r["p_up"]
    b = bucket_of(p)
    up_side = b in ("strong_up", "lean_up")
    down_side = b in ("strong_down", "lean_down")
    color = UP if up_side else DOWN if down_side else FLAT
    icon = "▲" if up_side else "▼" if down_side else "●"
    verdict = "Có thể TĂNG" if up_side else "Có thể GIẢM" if down_side else "Có thể đi ngang"
    level = "strong" if b.startswith("strong") else "lean" if (up_side or down_side) else "unclear"
    d = r["pred_price"] - p0
    extra = ""
    close_txt = "giá chốt gần nhất"
    if up_side or down_side:
        close_txt = f"giá chốt {WEEKDAYS[close_day.weekday()]} {close_day:%d/%m}"
        if h == "1":
            if use_live and pd.Timestamp(lp["ts"]).normalize() == pd.Timestamp(r["target_date"]).normalize():
                extra += f"<div class='fc-live'>Giá đang niêm yết: <b>{vn(lp['price'])}</b> triệu</div>"
            if abs(d) < close_spread:
                extra += (f"<div class='fc-warn'>Mức thay đổi này ({vn(abs(d))} triệu) nhỏ hơn chênh lệch mua–bán "
                          f"({vn(close_spread)} triệu): không đáng mua bán chỉ vì dự đoán này.</div>")
    move = f"{'tăng' if d > 0 else 'giảm'} khoảng {vn(abs(d))} triệu" if abs(d) >= 0.05 else "gần như không đổi"
    cal = calibration(tkey, int(h))
    hist = ""
    if len(cal) and b in cal.index and cal.loc[b, "n"] >= 20 and (up_side or down_side):
        hit = cal.loc[b, "up"] if up_side else 1 - cal.loc[b, "up"]
        word = "tăng" if up_side else "giảm"
        hist = f"<div class='fc-hist'>Những lần trước phần mềm nói “{word}” như vậy:<br>đúng <b>{ten(hit)}/10</b> lần</div>"
    return f"""<div class="fc-card" style="border-top:6px solid {color}">
<div class="fc-when">{when}</div><div class="fc-date">{date}</div>
<div class="fc-icon" style="color:{color}">{icon}</div>
<div class="fc-verdict" style="color:{color}">{verdict}</div>
<div class="fc-main">khoảng <b>{vn(r['pred_price'])}</b> triệu</div>
<div class="fc-sub">{move} so với {close_txt}</div>{extra}
<div class="fc-range">{rng}</div>
<div class="fc-conf" style="color:{color}">{CONF[level][0]} {CONF[level][1].format(dir='tăng' if up_side else 'giảm')}</div>{hist}</div>"""


def long_card(o: dict) -> str:
    return f"""<div class="fc-card" style="border-top:6px solid {GOLD}">
<div class="fc-when">Khoảng {o['label']} nữa</div><div class="fc-date">tháng {pd.Timestamp(o['target_date']):%m/%Y}</div>
<div class="fc-icon" style="color:{GOLD}">↕</div>
<div class="fc-verdict" style="color:{GOLD}">Không ai đoán chắc</div>
<div class="fc-sub">Xa như vậy, giá có thể lên hoặc xuống rất nhiều. Phần mềm chỉ ước lượng khoảng giá.</div>
<div class="fc-range">Phần lớn trường hợp trong khoảng<br><b>{vn(o['lo'], 0)} – {vn(o['hi'], 0)}</b> triệu</div>
<div class="fc-conf" style="color:{GOLD}">{CONF['none'][0]} Chỉ để tham khảo</div></div>"""


near = [short_card(h, T["horizons"][h]) for h in ("1", "5", "21") if h in T["horizons"]]
O = outlook(tkey)
far = [long_card(O[h]) for h in ("63", "105") if h in O]
st.markdown(f"<div class='group'>Trong tháng tới</div><div class='fc-grid'>{''.join(near)}</div>"
            f"<div class='group'>Xa hơn: 3 – 5 tháng</div><div class='fc-grid two'>{''.join(far)}</div>",
            unsafe_allow_html=True)
st.caption("“Nhiều khả năng trong khoảng” = khoảng mà trước đây giá thật rơi vào khoảng 8 trên 10 lần. "
           "Ngày tính theo ngày làm việc (Thứ Hai – Thứ Sáu).")
st.markdown(f"""<div class="note">
💡 <b>Chênh lệch giữa giá bán và giá mua hiện là {vn(spread)} triệu/lượng.</b><br>
Nghĩa là nếu mua 1 lượng hôm nay rồi bán lại ngay, mình sẽ mất khoảng <b>{vn(spread)} triệu</b>.
Giá cần tăng hơn mức này thì mới có lời – nên vàng hợp để giữ lâu hơn là mua bán theo từng ngày.
</div>""", unsafe_allow_html=True)

# ------------------------------------------------------------------ biểu đồ
st.markdown("## Giá 3 tháng qua và dự đoán 1 tháng tới")
hist = df[tkey].dropna().iloc[-66:]
fig = go.Figure()
xs = [hist.index[-1]] + [pd.Timestamp(T["horizons"][h]["target_date"]) for h in ("1", "5", "21")]
lo = [hist.iloc[-1]] + [T["horizons"][h]["lo80"] for h in ("1", "5", "21")]
hi = [hist.iloc[-1]] + [T["horizons"][h]["hi80"] for h in ("1", "5", "21")]
mid = [hist.iloc[-1]] + [T["horizons"][h]["pred_price"] for h in ("1", "5", "21")]
fig.add_trace(go.Scatter(x=xs + xs[::-1], y=hi + lo[::-1], fill="toself", fillcolor="rgba(183,121,31,0.16)", mode="lines",
                         line=dict(width=0), hoverinfo="skip", name="Khoảng giá nhiều khả năng"))
fig.add_trace(go.Scatter(x=hist.index, y=hist, name="Giá đã qua", line=dict(color="#1f2937", width=3),
                         hovertemplate="%{x|%d/%m}: %{y:.1f} triệu<extra></extra>"))
fig.add_trace(go.Scatter(x=xs, y=mid, name="Dự đoán", mode="lines+markers", line=dict(color=GOLD, width=3, dash="dot"),
                         marker=dict(size=10), hovertemplate="%{x|%d/%m}: khoảng %{y:.1f} triệu<extra></extra>"))
plotly_layout(fig, height=420, yaxis_title="triệu đồng / lượng")
fig.update_layout(font=dict(size=16), legend=dict(font=dict(size=15)), margin=dict(l=70, r=16, t=16, b=8))
fig.update_xaxes(tickformat="%d/%m")
chart(fig)

# ------------------------------------------------------------------ vì sao
H1 = T["horizons"].get("1", {})


if H1.get("has_edge") and H1.get("shap_top"):
    st.markdown("## Vì sao phần mềm nghĩ như vậy?")
    st.markdown("<div class='vg-muted'>Những điều chính phần mềm đang dựa vào để đoán giá phiên kế tiếp:</div>",
                unsafe_allow_html=True)
    shown = 0
    for d in sorted(H1["shap_top"], key=lambda d: -abs(d["contribution_pct"])):
        txt = plain_reason(d["feature"], d["value"], d["contribution_pct"])
        if not txt:
            continue
        pushes_up = d["contribution_pct"] > 0
        col = UP if pushes_up else DOWN
        st.markdown(f"<div class='reason'><span style='color:{col};font-weight:700'>{'⬆ đẩy giá lên' if pushes_up else '⬇ kéo giá xuống'}</span>"
                    f" &nbsp;·&nbsp; {txt}</div>", unsafe_allow_html=True)
        shown += 1
        if shown == 3:
            break

# ------------------------------------------------------------------ có đáng tin không
st.markdown("## Phần mềm đoán có đúng không?")
lock = (H1.get("backtest", {}).get("locked") or {}).get("from")
tr, _ = tracking(tkey, 1, lock, live)
if len(tr):
    done = tr[tr.actual.notna() & ~tr.provisional.astype(bool)].sort_values("target_date").tail(30)
    valid = done.dir_ok.dropna()
    n_ok, n_dir = int(valid.sum()), int(len(valid))
    inband = pd.to_numeric(done.in_band, errors="coerce").dropna()
    mae = done.error.abs().mean()
    mape = done.abs_pct.mean()
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        st.markdown(f"Nhìn lại **{len(done)} lần đoán “phiên kế tiếp” gần nhất**, mỗi chấm là một lần:")
        dots = "".join(
            f"<div class='dot' title='{r.target_date:%d/%m}' style='background:"
            f"{UP if r.dir_ok == 1 else DOWN if r.dir_ok == 0 else '#d1d5db'}'></div>" for r in done.itertuples())
        st.markdown(f"<div class='dots'>{dots}</div>", unsafe_allow_html=True)
        st.markdown(f"<span style='color:{UP}'>●</span> đoán đúng tăng/giảm &nbsp; "
                    f"<span style='color:{DOWN}'>●</span> đoán sai &nbsp; "
                    f"<span style='color:#9ca3af'>●</span> giá đứng yên (không tính)", unsafe_allow_html=True)
    with c2:
        if n_dir:
            st.markdown(f"<div class='stat'>Đoán đúng tăng hay giảm: <b>{n_ok}/{n_dir}</b> lần</div>",
                        unsafe_allow_html=True)
        st.markdown(f"<div class='stat'>Lệch trung bình: <b>{vn(mae)} triệu</b> mỗi lượng "
                    f"(khoảng {vn(mape)}% giá)</div>", unsafe_allow_html=True)
        if len(inband):
            st.markdown(f"<div class='stat'>Giá thật nằm trong khoảng dự đoán: <b>{int(inband.sum())}/{len(inband)}</b> lần</div>",
                        unsafe_allow_html=True)
    pend = tr[(tr.source == "Live") & tr.provisional.astype(bool) & tr.actual.notna()]
    if len(pend):
        r = pend.sort_values("target_date").iloc[-1]
        st.markdown(f"<div class='note'>⏱️ <b>Đang theo dõi:</b> sáng nay phần mềm đoán giá chốt "
                    f"{vn_date(r.target_date)} khoảng <b>{vn(r.pred)}</b> triệu. Giá đang niêm yết hiện là "
                    f"<b>{vn(r.actual)}</b> triệu (lệch {vn(abs(r.error))} triệu). Kết quả chính thức có vào sáng mai.</div>",
                    unsafe_allow_html=True)
    st.caption("Mỗi lần đoán chỉ dùng thông tin có trước ngày đó, giống hệt như khi phần mềm chạy thật mỗi sáng. "
               "Xem chi tiết ở trang “Chuyên sâu”.")

# ------------------------------------------------------------------ lời khuyên thực tế
st.markdown("## Điều nên biết trước khi mua bán")
st.markdown("""<div class="note">⚠️ Đây là <b>dự đoán để tham khảo</b>, dựa trên số liệu trong quá khứ – <b>không phải lời khuyên mua hay bán</b>.
Giá vàng có thể thay đổi bất ngờ vì tin tức trong nước và thế giới.</div>""", unsafe_allow_html=True)

with st.expander("❓ Câu hỏi thường gặp"):
    st.markdown("""
**Phần mềm lấy giá ở đâu?** Giá vàng trong nước lấy từ CafeF và giavang.org; giá vàng thế giới, tỷ giá đô la
lấy từ Yahoo Finance và Cục Dự trữ Liên bang Mỹ (FRED).

**Bao lâu cập nhật một lần?** Mỗi sáng khoảng 7 giờ (Thứ Ba – Thứ Bảy), sau khi thị trường Mỹ đóng cửa đêm trước.
Giá đang niêm yết trên trang này được làm mới mỗi 5 phút.

**Vì sao “1 tuần” và “1 tháng” lại ghi “Khó đoán”?** Vì khi kiểm tra trên nhiều năm dữ liệu, phần mềm đoán chiều
tăng/giảm ở các mốc này không tốt hơn việc coi như giá giữ nguyên. Thay vì đoán bừa, phần mềm nói thật là chưa đoán được
và chỉ cho biết khoảng giá có thể xảy ra.

**Vì sao 3 tháng, 5 tháng khoảng giá lại rộng như vậy?** Giá vàng mấy năm qua lên xuống rất mạnh (có năm tăng hơn 50%).
Khoảng rộng là cách trung thực để nói: xa như vậy thì không ai biết chắc.
""")
