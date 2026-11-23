"""Phiên bản CHUYÊN SÂU – Vietnam Gold Market Intelligence.

Dự báo đa mô hình, đối chiếu lịch sử (Historical tracking price), giải thích SHAP,
kiểm định walk-forward, triển vọng dài hạn và các biến số cần theo dõi.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import (GOLD, INK, MUTED, NAVY, PROC, TARGET_SHORT, chart, inject_css, live_prices, load, outlook,
                tracking, vn_date)
from vngold.explain import LABELS

RED, BLUE, GREY, GREEN = "#b91c1c", "#2563eb", "#64748b", "#15803d"

inject_css("""
.block-container {max-width: 1320px;}
.pro-title {font-size: 1.9rem; font-weight: 800; color: #1e3a5f; margin-bottom: 0;}
.pro-sub {color: #6b7280; margin-top: 2px; margin-bottom: 14px;}
[data-testid="stTabs"] button p {font-size: 0.95rem; font-weight: 600;}
""")


def fmt(v, d=2):
    return "–" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:,.{d}f}"


if not (PROC / "forecast.json").exists():
    st.error("Chưa có kết quả. Hãy chạy: `python scripts/run_pipeline.py`")
    st.stop()

fc, df = load()
last = df.iloc[-1]
prev = df.iloc[-2]

# ------------------------------------------------------------------ Header
st.markdown("<div class='pro-title'>Vietnam Gold Market Intelligence</div>"
            f"<div class='pro-sub'>Dự báo định lượng giá vàng SJC &amp; nhẫn 9999 · dữ liệu tới "
            f"<b>{vn_date(fc['as_of'])}</b> · cập nhật {pd.Timestamp(fc['generated_at']):%H:%M %d/%m/%Y} · "
            "công cụ nghiên cứu, không phải khuyến nghị đầu tư</div>", unsafe_allow_html=True)

c = st.columns(5)
c[0].metric("SJC bán ra (tr/lượng)", f"{fmt(last.sjc_sell)}", f"{fmt(last.sjc_sell - prev.sjc_sell)}", border=True)
c[1].metric("Nhẫn 9999 bán ra (tr/lượng)", f"{fmt(last.ring_sell)}",
            f"{fmt(last.ring_sell - prev.ring_sell)}" if pd.notna(prev.ring_sell) else None, border=True)
c[2].metric("XAU/USD ($/oz)", f"{fmt(last.xau_usd, 1)}", f"{(last.xau_usd / prev.xau_usd - 1) * 100:+.2f}%",
            border=True)
c[3].metric("Premium SJC (tr/lượng)", f"{fmt(last.premium)}", f"{last.premium_pct * 100:.1f}% so với TG",
            delta_color="off", border=True)
c[4].metric("USD/VND", f"{fmt(last.usd_vnd, 0)}", f"{(last.usd_vnd / prev.usd_vnd - 1) * 100:+.2f}%", border=True)

# ------------------------------------------------------------------ Bộ chọn
f1, f2, f3 = st.columns([3, 3, 4])
tkey = f1.segmented_control("Loại vàng", list(fc["targets"]), default="sjc_sell",
                            format_func=lambda k: TARGET_SHORT.get(k, k)) or "sjc_sell"
T = fc["targets"][tkey]
hkeys = list(T["horizons"])
hsel = f2.segmented_control("Kỳ hạn dự báo", hkeys, default=hkeys[0],
                            format_func=lambda h: T["horizons"][h]["label"]) or hkeys[0]
H = T["horizons"][hsel]
f3.caption("Dự báo phát hành sáng sớm giờ VN: đã biết phiên Mỹ đêm trước, chưa biết giá niêm yết trong ngày. "
           "Kỳ hạn 3 và 5 tháng xem ở tab **Dài hạn**.")

tabs = st.tabs(["Dự báo", "Historical tracking price", "Giải thích (SHAP)", "Độ tin cậy", "Dài hạn",
                "Biến số theo dõi", "Thị trường"])
TAB_WATCH, TAB_MARKET = 5, 6

# ------------------------------------------------------------------ 1. Forecast
with tabs[0]:
    col = tkey
    left, right = st.columns([3, 2])
    with left:
        hist = df[col].dropna().iloc[-130:]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist, name="Thực tế", line=dict(color=RED, width=2)))
        xs = [hist.index[-1]] + [pd.Timestamp(T["horizons"][h]["target_date"]) for h in hkeys]
        mid = [hist.iloc[-1]] + [T["horizons"][h]["pred_price"] for h in hkeys]
        lo90 = [hist.iloc[-1]] + [T["horizons"][h]["lo90"] for h in hkeys]
        hi90 = [hist.iloc[-1]] + [T["horizons"][h]["hi90"] for h in hkeys]
        lo80 = [hist.iloc[-1]] + [T["horizons"][h]["lo80"] for h in hkeys]
        hi80 = [hist.iloc[-1]] + [T["horizons"][h]["hi80"] for h in hkeys]
        fig.add_trace(go.Scatter(x=xs + xs[::-1], y=hi90 + lo90[::-1], fill="toself",
                                 fillcolor="rgba(29,78,216,0.12)", line=dict(width=0), name="Khoảng 90%"))
        fig.add_trace(go.Scatter(x=xs + xs[::-1], y=hi80 + lo80[::-1], fill="toself",
                                 fillcolor="rgba(29,78,216,0.22)", line=dict(width=0), name="Khoảng 80%"))
        fig.add_trace(go.Scatter(x=xs, y=mid, name="Dự báo (ensemble)", mode="lines+markers",
                                 line=dict(color=BLUE, dash="dash")))
        fig.update_layout(height=450, margin=dict(l=10, r=10, t=40, b=10), yaxis_title="triệu VND/lượng",
                          legend=dict(orientation="h", y=-0.12), title=f"{T['name']}: 6 tháng gần nhất & dự báo")
        chart(fig)
    with right:
        st.subheader("Bảng dự báo")
        rows = []
        for h in hkeys:
            r = T["horizons"][h]
            edge = r.get("has_edge", True)
            rows.append({"Kỳ hạn": r["label"], "Phiên chốt": pd.Timestamp(r["target_date"]).strftime("%d/%m/%Y"),
                         "Giá dự báo": f"{r['pred_price']:.2f}" if edge else "—",
                         "Thay đổi %": f"{r['pred_return_pct']:+.2f}" if edge else "—",
                         "Lợi thế": "✓" if edge else "✗",
                         "Khoảng 90%": f"{r['lo90']:.1f} – {r['hi90']:.1f}",
                         "P(tăng)": f"{r['p_up'] * 100:.0f}%"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.markdown(f"**Giá hiện tại:** {fmt(T['last_price'])} triệu/lượng")
        st.caption("Lưới thời gian là ngày làm việc T2–T6: biến động thứ Bảy/Chủ nhật được tính vào phiên thứ Hai.")
        bt = H["backtest"]
        if H.get("has_edge", True):
            st.success(f"Ở kỳ hạn **{H['label']}**, backtest từ {pd.Timestamp(bt['start']):%m/%Y}: ensemble "
                       f"**tốt hơn** Naive (Theil U = {bt['ensemble_theilU']:.3f}, DM p = {bt.get('ensemble_dm_p', float('nan')):.3f}).")
        else:
            st.warning(f"Ở kỳ hạn **{H['label']}**, ensemble **không vượt** dự báo Naive một cách có ý nghĩa "
                       f"(Theil U = {bt['ensemble_theilU']:.3f}). Vì vậy chỉ công bố khoảng tin cậy và xác suất quanh "
                       f"giá hiện tại; mô hình nghiêng về {H.get('model_return_pct', 0):+.2f}% nhưng không đủ tin cậy.")
        if "dir_base" in bt:
            st.markdown(f"Đoán đúng chiều **{bt['ensemble_diracc']:.1f}%** so với mốc 'luôn đoán chiều phổ biến' "
                        f"**{bt['dir_base']:.1f}%** → chênh lệch **{bt['dir_edge_pp']:+.1f} điểm %**.")
        st.subheader("Dự báo từng mô hình")
        mrows = [{"Mô hình": m, "Lợi suất %": round(v["return_pct"], 3), "Giá": round(v["price"], 2),
                  "Sau tự hiệu chỉnh": round(v["corrected_price"], 2),
                  "Trọng số ensemble": f"{H['weights'].get(m, 0) * 100:.0f}%"}
                 for m, v in H["models"].items()]
        st.dataframe(pd.DataFrame(mrows), hide_index=True, width="stretch")

# ------------------------------------------------------------------ 1b. Historical tracking price
RATING_COLORS = {"Rất gần": GREEN, "Gần": "#65a30d", "Khá xa": GOLD, "Xa": RED}

with tabs[1]:
    from vngold.tracking import RATINGS, rating_bands
    h_int = int(hsel)
    lock = (H["backtest"].get("locked") or {}).get("from")
    st.subheader(f"📜 Historical tracking price – {T['name']}, kỳ hạn {H['label']}")
    st.markdown(
        "Mỗi điểm dưới đây là **một dự báo được lập trong quá khứ**, rồi đặt cạnh **giá thực tế** của đúng ngày đích. "
        "Mỗi dự báo chỉ dùng dữ liệu có đến ngày lập (mô hình được huấn luyện lại theo thời gian, lớp tự học chỉ học "
        "từ những sai số đã biết), tức là đúng như khi phần mềm chạy thật mỗi sáng – không có thông tin tương lai.")

    # ---------- Live: dự báo đang chờ & giá niêm yết thời gian thực
    cbtn, cinfo = st.columns([1, 4])
    if cbtn.button("🔄 Làm mới giá live"):
        live_prices.clear()
        tracking.clear()
    live = live_prices()
    lp = live.get(tkey)
    if lp:
        cinfo.caption(f"Giá niêm yết mới nhất (CafeF): **{lp['price']:.2f}** triệu/lượng lúc "
                      f"{pd.Timestamp(lp['ts']):%H:%M %d/%m/%Y} · tự làm mới mỗi 5 phút.")
    else:
        cinfo.warning("Không lấy được giá live lúc này – chỉ hiển thị dữ liệu đã chốt.")
    tr, summ = tracking(tkey, h_int, lock, live)
    if tr.empty:
        st.info("Chưa có dữ liệu backtest cho lựa chọn này.")
    else:
        pend = tr[(tr.source == "Live") & (tr.actual.isna() | tr.provisional)]
        if len(pend):
            st.markdown("##### ⏱️ Dự báo đang theo dõi (live)")
            prow = []
            for _, r in pend.iterrows():
                prov = bool(r.provisional) and pd.notna(r.actual)
                prow.append({
                    "Lập ngày": f"{r.issued:%d/%m/%Y}", "Phiên chốt": f"{r.target_date:%d/%m/%Y}",
                    "Giá lúc lập": round(r.price_issue, 2), "Dự báo": round(r.pred, 2),
                    "Khoảng 90%": f"{r.lo:.1f} – {r.hi:.1f}" if pd.notna(r.lo) else "–",
                    "Giá live hiện tại": f"{r.actual:.2f}" if prov else (f"{lp['price']:.2f}" if lp else "–"),
                    "Sai số tạm": f"{r.error:+.2f} ({r.error_pct:+.2f}%)" if prov else "chưa đến hạn",
                    "Đánh giá tạm": r.rating if prov else "–"})
            st.dataframe(pd.DataFrame(prow), hide_index=True, width="stretch")
            st.caption("Sai số tạm tính bằng giá niêm yết mới nhất; điểm chính thức được chốt theo giá cuối phiên "
                       "ở lần chạy 7h sáng hôm sau.")

        # ---------- bộ lọc
        f1, f2 = st.columns([2, 3])
        period = f1.selectbox("Giai đoạn", ["3 tháng", "6 tháng", "1 năm", "Giai đoạn khoá", "Toàn bộ"], index=1)
        srcs = f2.multiselect("Nguồn dự báo", ["Live", "Giai đoạn khoá", "Backtest"],
                              default=["Live", "Giai đoạn khoá", "Backtest"],
                              help="Live = dự báo thật đã lưu lúc phát hành. Giai đoạn khoá = backtest sau khi đã chốt "
                                   "cấu hình (chưa từng dùng để chỉnh tham số). Backtest = mô phỏng giai đoạn trước đó.")
        done = tr[tr.actual.notna() & tr.source.isin(srcs)]
        end = done.target_date.max() if len(done) else pd.Timestamp.today()
        cut = {"3 tháng": end - pd.DateOffset(months=3), "6 tháng": end - pd.DateOffset(months=6),
               "1 năm": end - pd.DateOffset(years=1),
               "Giai đoạn khoá": pd.Timestamp(lock) if lock else done.target_date.min(),
               "Toàn bộ": done.target_date.min()}[period]
        view = done[done.target_date >= cut]
        from vngold.tracking import tracking_summary as _ts
        sv = _ts(view)
        b1, b2, b3 = rating_bands(h_int)

        if sv["n"] == 0:
            st.info("Không có dự báo nào đã có giá thực tế trong giai đoạn đã chọn.")
        else:
            if not H.get("has_edge", True):
                st.warning("Ở kỳ hạn này mô hình **không vượt** dự báo Naive, nên phần mềm chỉ công bố khoảng tin cậy. "
                           "Bảng dưới vẫn hiển thị dự báo điểm của mô hình để bạn tự đánh giá.")
            k = st.columns(5)
            k[0].metric("Đã đối chiếu", f"{sv['n']:,}")
            k[1].metric("Sai số trung bình", f"{sv['mae']:.2f} tr", f"{sv['mape']:.2f}% giá", delta_color="off")
            better = sv["naive_mape"] - sv["mape"]
            k[2].metric("So với Naive", f"{sv['naive_mape']:.2f}%",
                        f"mô hình {'tốt hơn' if better > 0 else 'kém hơn'} {abs(better):.2f} điểm %",
                        delta_color="normal" if better > 0 else "inverse",
                        help="Naive = giả định giá không đổi so với lúc lập dự báo.")
            k[3].metric("Trong khoảng 90%", f"{sv['in_band']:.0f}%" if sv["in_band"] == sv["in_band"] else "–",
                        "mục tiêu ≈ 90%", delta_color="off")
            k[4].metric("Đoán đúng chiều", f"{sv['dir_ok']:.0f}%" if sv["dir_ok"] == sv["dir_ok"] else "–",
                        f"gần hơn Naive {sv['closer_than_naive']:.0f}% phiên có biến động", delta_color="off")

            # ---------- biểu đồ giá dự báo vs giá thực tế
            fig = go.Figure()
            v = view.sort_values("target_date")
            if v.lo.notna().any():
                fig.add_trace(go.Scatter(x=v.target_date, y=v.hi, line=dict(width=0), showlegend=False,
                                         hoverinfo="skip"))
                fig.add_trace(go.Scatter(x=v.target_date, y=v.lo, fill="tonexty", line=dict(width=0),
                                         fillcolor="rgba(29,78,216,0.12)", name="Khoảng 90% đã công bố",
                                         hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=v.target_date, y=v.actual, name="Giá thực tế", line=dict(color=RED, width=2)))
            fig.add_trace(go.Scatter(
                x=v.target_date, y=v.pred, name=f"Giá dự báo (lập trước {h_int} phiên)", mode="markers",
                marker=dict(size=6 if len(v) < 300 else 4, color=[RATING_COLORS.get(r, GREY) for r in v.rating]),
                customdata=np.stack([v.issued.dt.strftime("%d/%m/%Y"), v.error_pct.round(2), v.rating, v.source], 1),
                hovertemplate="Phiên chốt %{x|%d/%m/%Y}<br>Dự báo %{y:.2f} (lập %{customdata[0]})"
                              "<br>Sai số %{customdata[1]}% · %{customdata[2]}<br>%{customdata[3]}<extra></extra>"))
            live_pts = v[v.source == "Live"]
            if len(live_pts):
                fig.add_trace(go.Scatter(x=live_pts.target_date, y=live_pts.pred, mode="markers", name="Dự báo live",
                                         marker=dict(symbol="star", size=12, color=BLUE)))
            if lock and v.target_date.min() < pd.Timestamp(lock) < v.target_date.max():
                fig.add_vline(x=pd.Timestamp(lock), line_dash="dot", line_color=GREY)
                fig.add_annotation(x=pd.Timestamp(lock), y=1, yref="paper", text="bắt đầu giai đoạn khoá",
                                   showarrow=False, xanchor="left", font=dict(size=11, color=GREY))
            fig.update_layout(height=430, margin=dict(l=10, r=10, t=40, b=10), yaxis_title="triệu VND/lượng",
                              title="Giá dự báo so với giá thực tế (trục x = ngày đích)",
                              legend=dict(orientation="h", y=-0.15))
            chart(fig)
            st.caption(f"Màu điểm dự báo: 🟢 Rất gần (sai ≤ {b1:.1f}%) · 🟩 Gần (≤ {b2:.1f}%) · "
                       f"🟡 Khá xa (≤ {b3:.1f}%) · 🔴 Xa (> {b3:.1f}%). Ngưỡng nới theo √kỳ hạn.")

            # ---------- sai số theo thời gian & phân bố mức độ
            c1, c2 = st.columns([3, 2])
            with c1:
                fe = go.Figure(go.Bar(x=v.target_date, y=v.error_pct,
                                      marker_color=[RATING_COLORS.get(r, GREY) for r in v.rating],
                                      hovertemplate="%{x|%d/%m/%Y}: %{y:+.2f}%<extra></extra>"))
                for y0 in (b1, -b1, b3, -b3):
                    fe.add_hline(y=y0, line_dash="dot", line_color=GREY, line_width=1)
                fe.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), yaxis_title="% (thực tế − dự báo)",
                                 title="Sai số từng dự báo (dương = giá thật cao hơn dự báo)")
                chart(fe)
            with c2:
                fr = go.Figure()
                for r in RATINGS:
                    fr.add_trace(go.Bar(y=["Naive", "Mô hình"], x=[sv["naive_rating_share"][r], sv["rating_share"][r]],
                                        name=r, orientation="h", marker_color=RATING_COLORS[r],
                                        text=[f"{sv['naive_rating_share'][r]:.0f}%", f"{sv['rating_share'][r]:.0f}%"],
                                        textposition="inside"))
                fr.update_layout(barmode="stack", height=320, margin=dict(l=10, r=10, t=40, b=10),
                                 title="Tỷ lệ dự báo theo mức độ gần/xa", xaxis_title="% số dự báo",
                                 legend=dict(orientation="h", y=-0.25))
                chart(fr)
            st.caption(f"Một nửa số dự báo sai không quá **{sv['median_ape']:.2f}%** giá (trung vị). "
                       "So sánh với Naive cho biết mô hình có thực sự thêm giá trị hay chỉ ăn theo việc giá ít thay đổi.")

            # ---------- theo tháng
            m = view.assign(month=view.target_date.dt.to_period("M"))
            mt = m.groupby("month").agg(
                **{"Số dự báo": ("abs_pct", "size"), "Sai số TB %": ("abs_pct", "mean"),
                   "Naive %": ("naive_abs_pct", "mean"),
                   "Trong khoảng 90%": ("in_band", lambda s: pd.to_numeric(s).dropna().mean() * 100),
                   "Đúng chiều %": ("dir_ok", lambda s: pd.to_numeric(s).dropna().mean() * 100)})
            mt["Mô hình tốt hơn?"] = np.where(mt["Sai số TB %"] < mt["Naive %"], "✓", "✗")
            mt.index = mt.index.astype(str)
            mt.index.name = "Tháng"
            st.markdown("##### Theo từng tháng (12 tháng gần nhất trong giai đoạn đã chọn)")
            st.dataframe(mt.iloc[::-1].head(12).round(2), width="stretch")

            # ---------- chi tiết
            st.markdown("##### Chi tiết từng dự báo")
            icon = {"Rất gần": "🟢", "Gần": "🟩", "Khá xa": "🟡", "Xa": "🔴"}
            det = view.sort_values("issued", ascending=False).head(200)
            st.dataframe(pd.DataFrame({
                "Lập ngày": det.issued.dt.strftime("%d/%m/%Y"), "Phiên chốt": det.target_date.dt.strftime("%d/%m/%Y"),
                "Giá lúc lập": det.price_issue.round(2), "Dự báo": det.pred.round(2),
                "Thực tế": det.actual.round(2), "Sai số (tr)": det.error.round(2),
                "Sai số %": det.error_pct.round(2),
                "Mức độ": [f"{icon.get(r, '')} {r}" for r in det.rating],
                "Trong khoảng 90%": det.in_band.map({1.0: "✓", 0.0: "✗", True: "✓", False: "✗"}).fillna("–"),
                "Nguồn": det.source + np.where(det.provisional, " (tạm)", "")}),
                hide_index=True, width="stretch", height=380)
            st.download_button("⬇️ Tải toàn bộ lịch sử đối chiếu (CSV)",
                               tr.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"historical_tracking_{tkey}_h{h_int}.csv", mime="text/csv")
        st.caption("Lưu ý trung thực: tham số mô hình được chọn khi đã xem dữ liệu trước giai đoạn khoá, nên phần "
                   "**Giai đoạn khoá** và **Live** là bằng chứng đáng tin nhất. Hiệu quả trong quá khứ không bảo đảm "
                   "cho tương lai.")

# ------------------------------------------------------------------ 2. Why
with tabs[2]:
    if H.get("shap_top"):
        st.subheader(f"Các yếu tố đóng góp vào dự báo XGBoost – {H['label']}")
        s = pd.DataFrame(H["shap_top"])[::-1]
        s["label"] = [LABELS.get(f, l) for f, l in zip(s.feature, s.label)]
        fig = go.Figure(go.Bar(x=s.contribution_pct, y=s.label, orientation="h",
                               marker_color=[GREEN if v > 0 else RED for v in s.contribution_pct],
                               text=[f"{v:+.3f}%" for v in s.contribution_pct], textposition="outside"))
        fig.update_layout(height=420, margin=dict(l=10, r=40, t=10, b=10),
                          xaxis_title="Đóng góp vào lợi suất dự báo (điểm %)")
        chart(fig)
        xgb_ret = H["models"].get("XGBoost", {}).get("return_pct")
        st.markdown(f"XGBoost dự báo **{xgb_ret:+.2f}%**. Các yếu tố:")
        for d in H["shap_top"]:
            icon = "🟢" if d["contribution_pct"] > 0 else "🔴"
            val = "" if d["value"] is None else f" (giá trị hiện tại: {d['value']:.4g})"
            st.markdown(f"- {icon} **{LABELS.get(d['feature'], d['label'])}**{val}: {d['direction']} {d['contribution_pct']:+.3f}%")
        st.caption("SHAP giải thích đóng góp của biến vào **dự báo của mô hình**, không chứng minh quan hệ nhân quả.")
        st.subheader("Mức quan trọng trung bình (|SHAP|, 250 phiên gần nhất)")
        g = pd.DataFrame(H["shap_global"])[::-1]
        g["label"] = [LABELS.get(f, l) for f, l in zip(g.feature, g.label)]
        fig2 = go.Figure(go.Bar(x=g.mean_abs_shap, y=g.label, orientation="h", marker_color=GREY))
        fig2.update_layout(height=450, margin=dict(l=10, r=10, t=10, b=10))
        chart(fig2)
    else:
        st.info("Không có giải thích SHAP cho lựa chọn này.")

# ------------------------------------------------------------------ 3. Confidence
with tabs[3]:
    bt = H["backtest"]
    a, b, c3 = st.columns(3)
    a.metric("Bao phủ khoảng 90% (backtest)", f"{bt['coverage90'] * 100:.1f}%")
    b.metric("Bao phủ khoảng 80% (backtest)", f"{bt['coverage80'] * 100:.1f}%")
    c3.metric("Mô hình RMSE thấp nhất", bt["best_model"])
    st.subheader("Walk-forward backtest (đơn vị: triệu VND/lượng)")
    tb = pd.DataFrame(bt["table"]).set_index("model")
    cols = [c for c in ["MAE", "RMSE", "MAPE_%", "TheilU", "DM_p", "DirAcc_%", "DirBase_%", "DirEdge_pp", "Dir_p", "N"]
            if c in tb]
    st.dataframe(tb[cols], width="stretch")
    st.caption("TheilU < 1: tốt hơn Naive (giá ngày mai = giá hôm nay). DM_p < 0.05: khác biệt có ý nghĩa thống kê. "
               "DirBase_% = tỷ lệ đúng nếu luôn đoán chiều phổ biến (vd luôn đoán tăng); DirEdge_pp = phần hơn mốc đó; "
               "Dir_p = kiểm định nhị thức. Ensemble = tổ hợp tự học: trọng số theo kỹ năng so với Naive "
               "+ hiệu chỉnh độ lệch (chỉ khi có ích) + khoảng tin cậy tự nới/co.")
    lk = bt.get("locked")
    if lk:
        st.subheader(f"Giai đoạn khoá (sau {pd.Timestamp(lk['from']):%d/%m/%Y})")
        st.caption("Cấu hình đã chốt trước giai đoạn này. Đây là phần kiểm định chưa từng dùng để chỉnh tham số.")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Theil U ensemble", f"{lk['ensemble_theilU']:.3f}")
        k2.metric("DM p-value", f"{lk['ensemble_dm_p']:.3f}")
        k3.metric("Đúng chiều / mốc", f"{lk['ensemble_diracc']:.0f}% / {lk['dir_base']:.0f}%")
        k4.metric("Bao phủ 90%", f"{lk['coverage90'] * 100:.0f}%", f"N = {lk['n']}", delta_color="off")

    f = PROC / f"backtest_{tkey}_h{hsel}.csv"
    if f.exists():
        wf = pd.read_csv(f, index_col=0, parse_dates=True).iloc[-260:]
        h = int(hsel)
        tgt_idx = wf.index  # dự báo lập tại t cho t+h -> vẽ theo ngày lập
        fig = go.Figure()
        p_act = wf.price_t * np.exp(wf.actual)
        fig.add_trace(go.Scatter(x=tgt_idx, y=wf.price_t * np.exp(wf.hi), line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=tgt_idx, y=wf.price_t * np.exp(wf.lo), fill="tonexty", line=dict(width=0),
                                 fillcolor="rgba(29,78,216,0.15)", name="Khoảng 90%"))
        fig.add_trace(go.Scatter(x=tgt_idx, y=p_act, name=f"Thực tế (t+{h})", line=dict(color=RED)))
        fig.add_trace(go.Scatter(x=tgt_idx, y=wf.price_t * np.exp(wf.Ensemble), name="Ensemble dự báo",
                                 line=dict(color=BLUE, dash="dot")))
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                          title="1 năm gần nhất trong backtest (trục x = ngày lập dự báo)",
                          legend=dict(orientation="h", y=1.1))
        chart(fig)
        roll = (np.sign(wf.Ensemble) == np.sign(wf.actual))[wf.actual != 0].rolling(60).mean() * 100
        fr = go.Figure(go.Scatter(x=roll.index, y=roll, line=dict(color=NAVY)))
        fr.add_hline(y=50, line_dash="dot", line_color=GREY)
        fr.update_layout(height=260, margin=dict(l=10, r=10, t=40, b=10), title="Tỷ lệ đúng chiều trượt 60 phiên (%)")
        chart(fr)

    st.subheader("📒 Nhật ký dự báo thực tế (tự chấm điểm khi có giá thực tế)")
    lg = PROC / "predictions_log.csv"
    if lg.exists():
        log = pd.read_csv(lg)
        log = log[(log.target == tkey) & (log.model == "Ensemble")].sort_values("as_of", ascending=False)
        done = log[log.actual_price.notna()] if "actual_price" in log else log.iloc[:0]
        if len(done):
            l1, l2, l3 = st.columns(3)
            l1.metric("Dự báo đã chấm điểm", f"{len(done)}")
            l2.metric("Sai số tuyệt đối TB", f"{done.abs_pct_error.mean():.2f}%")
            cov = done.in_interval.dropna()
            l3.metric("Nằm trong khoảng 90%", f"{cov.mean() * 100:.0f}%" if len(cov) else "–")
        else:
            st.caption("Chưa có dự báo thực tế nào đáo hạn – số liệu sẽ xuất hiện sau vài phiên chạy hằng ngày.")
        st.dataframe(log[["as_of", "h", "target_date", "price_at_issue", "pred_price", "lo", "hi",
                          "actual_price", "abs_pct_error", "dir_correct", "in_interval"]].head(60),
                     hide_index=True, width="stretch")

# ------------------------------------------------------------------ 4. Long horizon
with tabs[4]:
    O = outlook(tkey)
    st.subheader(f"Triển vọng dài hạn – {T['name']}")
    st.markdown(
        "Ở kỳ hạn 7 và 30 ngày, các mô hình đã **không vượt** dự báo Naive, nên với 3–5 tháng phần mềm **không dự báo "
        "chiều giá**. Thay vào đó công bố một **khoảng giá 80% đối xứng**: biến động ngày (126 phiên) × √h × hệ số hiệu "
        "chỉnh bằng phân vị 80% của sai số chuẩn hoá đã đáo hạn (cửa sổ mở rộng, không dùng thông tin tương lai).")
    rows = [{"Kỳ hạn": o["label"], "Ngày đích (≈)": f"{pd.Timestamp(o['target_date']):%d/%m/%Y}",
             "Giá hiện tại": round(o["price_now"], 2),
             "Khoảng 80%": f"{o['lo']:.1f} – {o['hi']:.1f}",
             "Biên độ": f"{o['lo_pct']:+.1f}% / {o['hi_pct']:+.1f}%",
             "Độ phủ lịch sử": f"{o['coverage'] * 100:.0f}% (N={o['n_eval']})" if o.get("coverage") else "–",
             "Độ phủ giai đoạn khoá": f"{o['coverage_locked'] * 100:.0f}% (N={o['n_locked']})"
             if o.get("coverage_locked") is not None else "–"} for o in O.values()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    c1, c2 = st.columns([3, 2])
    with c1:
        d = df[tkey].dropna().iloc[-500:]
        fig = go.Figure()
        x0 = d.index[-1]
        xs = [x0] + [pd.Timestamp(o["target_date"]) for o in O.values()]
        lo = [d.iloc[-1]] + [o["lo"] for o in O.values()]
        hi = [d.iloc[-1]] + [o["hi"] for o in O.values()]
        fig.add_trace(go.Scatter(x=xs + xs[::-1], y=hi + lo[::-1], fill="toself", fillcolor="rgba(183,121,31,0.18)", mode="lines",
                                 line=dict(width=0), name="Khoảng 80%"))
        fig.add_trace(go.Scatter(x=d.index, y=d, name="Giá thực tế", line=dict(color=INK, width=2)))
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10), yaxis_title="triệu VND/lượng",
                          title="2 năm gần nhất và khoảng giá 3 – 5 tháng tới", legend=dict(orientation="h", y=-0.15))
        chart(fig)
    with c2:
        o5 = O.get("105") or list(O.values())[-1]
        yrs = o5.get("hist_up_by_year", {})
        if yrs:
            fy = go.Figure(go.Bar(x=[str(k) for k in yrs], y=[v * 100 for v in yrs.values()], marker_color=GOLD,
                                  text=[f"{v * 100:.0f}%" for v in yrs.values()], textposition="outside"))
            fy.add_hline(y=50, line_dash="dot", line_color=GREY)
            fy.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10), yaxis_range=[0, 115],
                             title=f"Tỷ lệ giá cao hơn sau {o5['label']}, theo năm lập", yaxis_title="%")
            chart(fy)
    st.caption("Tỷ lệ tăng sau 3–5 tháng thay đổi rất mạnh giữa các năm – đó là lý do không công bố P(tăng) ở các kỳ hạn "
               "này. Độ phủ lịch sử thấp hơn 80% ở giai đoạn có xu hướng mạnh (2019–2021, 2024–2025): khoảng giá đối "
               "xứng đánh giá thấp những đợt tăng kéo dài.")

# ------------------------------------------------------------------ 5. Watch
with tabs[TAB_WATCH]:
    W = fc["targets"]["sjc_sell"].get("watch", [])
    if W:
        st.subheader("Biến số cần theo dõi")
        st.caption("Z-score so với 1 năm gần nhất. |z| > 1.5 được đánh dấu bất thường. "
                   "'Top mô hình' = nằm trong 10 biến quan trọng nhất theo SHAP.")
        wdf = pd.DataFrame(W)
        wdf["Trạng thái"] = np.where(wdf.unusual, "⚠️ Bất thường", "Bình thường")
        wdf["Top mô hình"] = np.where(wdf.in_model_top10, "✓", "")
        st.dataframe(wdf[["label", "value", "z_1y", "Trạng thái", "Top mô hình"]]
                     .rename(columns={"label": "Biến", "value": "Giá trị", "z_1y": "Z-score 1 năm"}),
                     hide_index=True, width="stretch")
    st.markdown("""
**Các yếu tố cấu trúc cần lưu ý**
- **Chính sách**: Nghị định 232/2025/NĐ-CP (bỏ độc quyền vàng miếng, cấp phép nhập khẩu/sản xuất) – nguồn cung tăng có thể thu hẹp premium.
- **Premium** cao bất thường thường đi kèm rủi ro điều chỉnh giảm khi nguồn cung cải thiện, kể cả khi giá thế giới tăng.
- **Tỷ giá USD/VND** và **phiên Mỹ đêm trước** là động lực ngắn hạn lớn nhất.
""")

# ------------------------------------------------------------------ 6. Market
with tabs[TAB_MARKET]:
    d = df.iloc[-750:]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d.index, y=d.sjc_sell, name="SJC", line=dict(color=RED)))
    fig.add_trace(go.Scatter(x=d.index, y=d.ring_sell, name="Nhẫn 9999", line=dict(color=GOLD)))
    fig.add_trace(go.Scatter(x=d.index, y=d.world_vnd, name="Thế giới quy đổi", line=dict(color=BLUE)))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), title="Giá 3 năm gần nhất (triệu/lượng)",
                      legend=dict(orientation="h", y=1.1))
    chart(fig)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df.premium_pct * 100, name="SJC premium %", fill="tozeroy",
                             line=dict(color=RED)))
    fig.add_trace(go.Scatter(x=df.index, y=df.ring_premium_pct * 100, name="Nhẫn premium %", line=dict(color=GOLD)))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), title="Domestic Gold Premium (%)",
                      legend=dict(orientation="h", y=1.12))
    chart(fig)
    st.markdown(r"**Công thức:** $P^{VND}_{World,t} = XAUUSD_t \times USDVND_t \times \frac{37.5}{31.1035}$, "
                r"$Premium_t = P_{Vietnam,t} - P^{VND}_{World,t}$")
