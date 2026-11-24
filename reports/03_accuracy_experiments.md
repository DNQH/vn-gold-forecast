# Phase 3 – Thí nghiệm cải thiện độ chính xác (nhánh `experiment/accuracy`)

Dữ liệu: `data/processed/dataset.csv` tới 23/11/2026 (bản chạy sáng 24/11/2026). Mốc so sánh = **Ensemble
production** đúng như trong `data/processed/backtest_*.csv` (stage `baseline` xác nhận chạy lại lớp tự học trên
các cột mô hình cho đúng cột Ensemble đã lưu, sai khác ≤ 7e-16).

Quy trình: **DEV** = các hàng ≤ 2025-11-30 (LOCK_DATE) – mọi lựa chọn ý tưởng/tham số chỉ dựa trên DEV.
**LOCK** = 01/12/2025 → 23/11/2026, chỉ mở **sau khi** đã chốt ứng viên (xem mục 2; quyết định chốt được
commit riêng trước khi chạy stage `locked`). Cùng lưới thời gian, cùng mốc huấn luyện lại (21 phiên), cùng
MIN_TRAIN (500 SJC / 250 nhẫn) như production. Đơn vị RMSE/MAE: triệu VND/lượng. DM: Diebold–Mariano (HAC,
hiệu chỉnh HLN), `DM_stat_ens < 0` = ứng viên tốt hơn Ensemble.

Tái lập: `python scripts/experiments/accuracy.py {baseline|dev|extras|locked}` (cache ở
`scripts/experiments/_cache/`, không commit).

## 1. Kết quả DEV (≤ 30/11/2025)

### 1a. Lưới ECM (SJC, h=1) – 16 cấu hình khai báo trước

Ứng viên: cửa sổ premium W ∈ {20, 60}; giá thế giới quy VND hay USD (bỏ tỷ giá); OLS cửa sổ mở rộng hay
trọng số half-life 500; OLS hay Huber. Biến: `ec` (log-premium trừ trung bình W phiên), Δlog thế giới t và t-1,
Δlog giá trong nước t và t-1.

| cấu hình | RMSE | Theil U | DM p vs Naive | DM p vs Ensemble | DirAcc % |
|---|---|---|---|---|---|
| ECM_w60_usd_hl500 (**chọn**) | 0.6519 | 0.941 | 0.001 | 0.52 (kém hơn) | 66.1 |
| ECM_w20_usd_hl500 | 0.6519 | 0.941 | 0.001 | 0.50 | 65.7 |
| ECM_w60_usd_exp | 0.6551 | 0.945 | 0.001 | 0.27 | 65.8 |
| ECM_*_usd_*_huber (4 cấu hình) | 0.6562–0.6588 | 0.947–0.951 | <0.001 | 0.12–0.17 | 65.6–66.7 |
| ECM_*_vnd_* (8 cấu hình) | 0.6630–0.6710 | 0.957–0.968 | <0.01 | 0.006–0.06 | 63.1–64.9 |
| *Ensemble production* | *0.6475* | *0.935* | *<0.001* | – | *65.5* |

Nhận xét: một hồi quy 6 tham số đạt gần như ngang cả Ensemble (U 0.941 vs 0.935) – xác nhận lợi thế h=1 gần như
hoàn toàn là **độ trễ truyền dẫn giá thế giới**. Dùng giá USD tốt hơn quy VND (tỷ giá Yahoo gây nhiễu – khớp ablation).
Huber không giúp.

### 1b. Các ứng viên h=1 (DEV)

| ứng viên | SJC RMSE | SJC U | DM p vs Ens | SJC Dir % | Nhẫn RMSE | Nhẫn U | DM p vs Ens | Nhẫn Dir % |
|---|---|---|---|---|---|---|---|---|
| Ensemble (production) | 0.6475 | 0.935 | – | 65.5 | 1.050 | 0.859 | – | 61.1 |
| ECM đơn lẻ | 0.6519 | 0.941 | 0.52 (kém) | 66.1 | 0.841 | 0.689 | 0.007 | 80.0 |
| **Ens+ECM** (ECM thành viên ensemble) | 0.6465 | 0.933 | 0.50 | 66.1 | 0.897 | 0.734 | 0.021 | 65.6 |
| Ens_lean (bỏ nhóm vĩ mô + tỷ giá) | 0.6477 | 0.935 | 0.84 (kém) | 64.9 | 1.057 | 0.866 | 0.67 (kém) | 56.7 |
| Ens_lean+ECM | 0.6465 | 0.933 | 0.48 | 65.2 | 0.899 | 0.736 | 0.035 | 62.2 |
| Ens_noARIMA (bỏ ARIMA, U>1 trên DEV) | 0.6464 | 0.933 | 0.10 | 65.8 | n/a | | | |
| Stack NNLS học dần (LR, RF, XGB, ECM) | 0.6462 | 0.933 | 0.76 | 65.7 | (chưa đủ 250 dự báo) | | | |
| Hurdle: P(đổi giá) × ECM | 0.6518 | 0.941 | 0.56 (kém) | 66.2 | – | | | |
| Ens+Hurdle | 0.6467 | 0.933 | 0.53 | 66.1 | – | | | |

N: SJC 1 579 phiên (04/2019–11/2025); nhẫn chỉ **114** phiên (06–11/2025). Độ phủ khoảng 90%/80% của Ens+ECM
trên DEV: SJC 89.9%/79.5% (Ensemble 90.0%/79.5%); nhẫn 83%/71% (Ensemble 83%/67%).

**SJC:** mọi biến thể chỉ hơn Ensemble 0.15–0.2% RMSE, không biến thể nào có ý nghĩa thống kê (p ≥ 0.10).
Bỏ nhóm vĩ mô/tỷ giá (ý tưởng 3) **không** giúp khi đã có ensemble. Hurdle (ý tưởng 4) không hơn ECM.
**Vàng nhẫn:** ECM cải thiện lớn (U 0.86 → 0.73 khi thêm vào ensemble, p = 0.02) nhưng mẫu DEV rất ngắn.

### 1c. Thông tin giờ sáng (GC=F 60 phút, ý tưởng 2)

Thực tế lịch giao dịch: phiên Mỹ đóng 17:00 ET = 04:00 (hè) / 05:00 (đông) giờ VN; Globex mở lại 18:00 ET =
05:00 / 06:00 VN. Với lịch chạy 07:00, chỉ dùng an toàn được nến **kết thúc trước 06:30 VN** ⇒ chỉ có **1 nến
(05:00–06:00 VN) vào mùa hè Mỹ**, mùa đông không có thông tin mới; phiên châu Á (Tokyo 07:00 VN) chưa mở.
Dữ liệu giờ của Yahoo chỉ có từ 03/07/2024.

| biến thể (SJC h=1, DEV 07/2024–11/2025, N = 347) | corr với sai số Ensemble | RMSE | Ensemble RMSE | DM p vs Ens |
|---|---|---|---|---|
| nến kết thúc ≤ 06:30 VN (an toàn) | 0.23 | 1.003 | 1.014 | 0.77 |
| nến kết thúc ≤ 07:00 VN (sát giờ chạy, chỉ tham khảo) | 0.29 | 0.990 | 1.014 | 0.57 |

Có tín hiệu cùng chiều (≈1% RMSE) nhưng **không có ý nghĩa thống kê**, mẫu ngắn, và cần thêm nguồn dữ liệu giờ
⇒ không chốt. (Lưu ý minh bạch: script in thêm tương quan trên toàn mẫu – gồm cả giai đoạn khoá – là 0.13; con
số này không được dùng cho quyết định.)

### 1d. Kỳ hạn dài (ý tưởng 6, DEV)

ECM dài hạn: `ec`, `ec120` (premium lệch trung bình 120 phiên), Δlog thế giới 1/5/21 phiên, OLS half-life 500.

| | SJC h=5 U | DM p vs Naive | SJC h=21 U | DM p vs Naive | Nhẫn h=5 U | p | Nhẫn h=21 U | p |
|---|---|---|---|---|---|---|---|---|
| Ensemble | 1.006 | 0.76 | 0.943 | 0.22 | 0.963 | 0.52 | 0.859 | 0.24 |
| ECM dài hạn | 0.979 | 0.18 | 0.906 | 0.050 | 0.855 | 0.058 | 0.628 | 0.15 |
| Ens+ECM | 0.998 | 0.93 | 0.940 | 0.21 | 0.895 | 0.18 | 0.861 | 0.24 |
| XGBoost | 0.992 | 0.48 | 0.893 | 0.037 | 0.966 | 0.53 | 0.728 | 0.03 |

Không có gì đạt p < 0.05 một cách thuyết phục sau khi tính đến số phép thử (≈ 8 phép thử ở h=5/21); với h=21 các
quan sát chồng lấn mạnh (≈ 75 quan sát độc lập trong DEV) và XGBoost h=21 cũng từng "có vẻ tốt" trên DEV rồi thua
Naive trên giai đoạn khoá (production report: U 1.13).

## 2. Quyết định chốt (ghi lại TRƯỚC khi mở giai đoạn khoá)

* **Ứng viên chính: `Ens+ECM`** – giữ nguyên toàn bộ ensemble production, thêm `ECM_w60_usd_hl500` làm một thành
  viên của lớp tự học (trọng số theo kỹ năng, ACI không đổi), áp dụng **một công thức duy nhất** cho cả SJC và
  nhẫn, mọi kỳ hạn (h=5/21 dùng ECM dài hạn). Lý do: cải thiện trên DEV ở cả hai mục tiêu h=1 (SJC nhỏ, nhẫn
  lớn), đơn giản nhất, không đổi đặc trưng của các mô hình cũ. Không chọn Stack_NNLS/Ens_noARIMA dù RMSE SJC DEV
  thấp hơn 0.0001–0.0003 (chênh lệch vô nghĩa, không áp dụng được cho nhẫn).
* **Ứng viên phụ (chỉ để kiểm chứng giả thuyết, không triển khai nếu không thắng rõ): ECM dài hạn đơn lẻ ở h=21.**
* Tiêu chí "cải thiện": RMSE DEV < Ensemble **và** RMSE LOCK ≤ Ensemble, báo cáo DM vs Ensemble ở cả hai giai đoạn.

## 3. Giai đoạn khoá (01/12/2025 → 23/11/2026) – đánh giá MỘT LẦN ứng viên đã chốt

| mục tiêu, h | mô hình | RMSE | MAE | Theil U | DM p vs Naive | DM p vs Ensemble | DirAcc % (base) | Phủ 90% / 80% | N |
|---|---|---|---|---|---|---|---|---|---|
| SJC, 1 | Ensemble | 2.000 | 1.211 | 0.904 | 0.008 | – | 68.1 (54.1) | 91.0 / 82.8 | 244 |
| SJC, 1 | **Ens+ECM** | **1.965** | 1.208 | **0.888** | 0.016 | 0.27 (stat −1.10) | 67.6 (54.1) | 91.0 / 82.0 | 244 |
| Nhẫn, 1 | Ensemble | 2.130 | 1.277 | 0.921 | 0.072 | – | 71.7 (53.5) | 92.5 / 83.8 | 240 |
| Nhẫn, 1 | **Ens+ECM** | **2.111** | 1.273 | **0.912** | 0.171 | 0.74 (stat −0.34) | 71.7 (53.5) | 92.1 / 80.8 | 240 |
| SJC, 5 | Ensemble / Ens+ECM | 4.955 / 4.908 | 3.41 / 3.41 | 1.016 / 1.006 | 0.59 / 0.84 | 0.21 | 55.1 / 56.0 (56.8) | 90%: 89.6 / 90.0 | 240 |
| SJC, 21 | Ensemble / Ens+ECM | 11.17 / 10.91 | 8.74 / 8.46 | 1.120 / 1.093 | 0.33 / 0.43 | 0.18 | 52.9 / 44.8 (66.8) | 90%: 90.6 / 90.6 | 224 |
| Nhẫn, 5 | Ensemble / Ens+ECM | 5.071 / 5.032 | 3.45 / 3.46 | 1.009 / 1.001 | 0.77 / 0.99 | 0.74 | 58.4 / 55.8 (58.8) | 90%: 94.0 / 92.7 | 232 |
| Nhẫn, 21 | Ensemble / Ens+ECM | 11.07 / 11.07 | 8.71 / 8.71 | 1.073 / 1.073 | 0.55 / 0.55 | 0.61 | 55.3 / 55.3 (65.6) | 90%: 90.3 / 90.3 | 216 |

Độ rộng trung bình khoảng 90% (log-return) SJC h=1: 0.0382 → 0.0400; nhẫn h=1: 0.0529 → 0.0518.

**Ứng viên phụ – ECM dài hạn đơn lẻ, h=21:** SJC U = 1.054 (DM p vs Naive 0.65), nhẫn U = 1.239 ⇒ "lợi thế" trên DEV
(U 0.906, p 0.050) **không** lặp lại. Kết luận: không có mô hình nào có lợi thế ở h=5/h=21; giữ nguyên chính sách
"chỉ công bố khoảng, tâm = Naive".

*Hậu kiểm (KHÔNG dùng để chọn, chỉ để minh bạch):* SJC h=1 LOCK – ECM đơn lẻ RMSE 1.914 (U 0.865, p vs Ens 0.32),
Ens_lean+ECM 1.965, Stack_NNLS 1.973, Ens_noARIMA 1.999, Ens_lean 2.013. Nhẫn h=1 LOCK – ECM đơn lẻ 2.155 (thua
Ensemble; mức cải thiện lớn trên 114 phiên DEV **không** lặp lại), Ens_lean+ECM 2.110. Không biến thể nào đạt
p < 0.05 vs Ensemble.

Toàn bộ giai đoạn backtest (DEV+LOCK) với cờ bật: SJC h=1 U 0.916 → 0.905 (DM p vs Naive 0.0003 → 0.001);
nhẫn h=1 U 0.914 → 0.893 nhưng DM p vs Naive 0.029 → 0.065 (vẫn dưới ngưỡng công bố 0.10, nên trạng thái
"có lợi thế" không đổi). Kiểm tra: chạy `pipeline.backtest` với cờ bật cho nhẫn h=1 tái lập đúng cột Ens+ECM
của thí nghiệm (sai khác 4e-16).

## 4. Kết luận

* `Ens+ECM` **đạt tiêu chí đã khai báo** (RMSE thấp hơn Ensemble trên DEV ở cả SJC và nhẫn h=1, và không thua trên
  LOCK ở cả 6 tổ hợp mục tiêu × kỳ hạn), **nhưng** không có kiểm định DM nào vs Ensemble có ý nghĩa
  (p = 0.27–0.74 trên LOCK; 0.02 chỉ ở 114 phiên DEV của nhẫn). Đây là cải thiện **nhỏ, chưa chứng minh được
  thống kê**: RMSE giảm ~1–2%, MAE gần như không đổi (giảm chủ yếu ở các ngày sai lớn), độ chính xác chiều
  không đổi (SJC 68.1% → 67.6%, nhẫn 71.7% → 71.7%).
* Phát hiện chính có giá trị: một ECM 6 tham số (premium so với vàng USD + nhịp thế giới đêm qua) đạt gần như
  toàn bộ lợi thế của ensemble ML ⇒ lợi thế h=1 là độ trễ truyền dẫn, không phải "tín hiệu ML" phức tạp.
* Không làm được: thông tin giờ sáng (gần như không có giao dịch mới trước 06:30 VN), lọc đặc trưng, hurdle,
  stacking, h=5/h=21 – không có cải thiện đáng tin cậy.

**Áp dụng (nếu muốn):** merge nhánh, rồi đặt `USE_ECM = True` trong `src/vngold/config.py` (hoặc
`VNGOLD_USE_ECM=1` trong `scripts/daily.sh`). Khuyến nghị theo dõi thêm 3–6 tháng (so ECM vs Ensemble trong
predictions_log) trước khi coi là cải thiện thật.
