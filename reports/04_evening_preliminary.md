# Phase 4 – Dự báo SƠ BỘ lúc 19h cho phiên kế tiếp: kiểm định walk-forward

Dữ liệu tới 25/11/2026. Tạo lúc 26/11/2026 15:10.

**Câu hỏi:** lúc 19h ngày T (giờ VN) đã biết giá trong nước ngày T nhưng phiên Mỹ ngày T chưa đóng cửa. Nếu lấy giá thế giới *đang chạy* lúc 19h (thanh 1 giờ đóng lúc 12:00 UTC) thay cho giá đóng cửa phiên Mỹ rồi áp đúng các mô hình h = 1 của bản sáng, dự báo giá chốt phiên T+1 có còn lợi thế không?

**Cách kiểm định (không nhìn trộm tương lai):** cùng lịch walk-forward với bản sáng (huấn luyện lại mỗi 21 phiên, chỉ học nhãn đã biết). Ở hàng T chỉ thay 6 biến thế giới (vàng, DXY, lợi suất 10 năm, USD/VND, bạc, VIX) bằng giá của thanh 1 giờ đã đóng trước 19h; mã không giao dịch giờ đó (vd. lợi suất 10 năm) giữ giá gần nhất trước đó; khối lượng vàng giữ của phiên trước. Các hàng trước T giữ giá đóng cửa thật (lúc 19h đã biết). Lớp tự học chạy riêng cho từng phiên bản (khởi động bằng dự báo walk-forward của bản sáng trước giai đoạn kiểm định). Ba phiên bản được so trên **cùng các ngày**. Mốc so sánh: Naive (giá giữ nguyên), "luôn đoán tăng"/chiều phổ biến hơn, và tần suất tăng lịch sử (cho xác suất).


## Tóm tắt

- **Vàng miếng SJC** (605 phiên): bản 19h đoán đúng chiều 61.1% số phiên giá có đổi (mốc 54.8%, p = 0.004; bản 7h sáng 70.1%), sai số bằng 97.8% của Naive (DM p = 0.35; bản sáng 89.2%, p = 0.002), Brier skill +0.041 (bản sáng +0.189). → **Khó đoán**.
- **Vàng nhẫn 9999 (PNJ)** (365 phiên): bản 19h đoán đúng chiều 55.0% số phiên giá có đổi (mốc 51.6%, p = 0.132; bản 7h sáng 69.9%), sai số bằng 101.8% của Naive (DM p = 0.55; bản sáng 89.4%, p = 0.065), Brier skill +0.028 (bản sáng +0.269). → **Khó đoán**.

Phần lớn lợi thế của bản sáng đến từ diễn biến **phiên Mỹ** (đêm T) mà lúc 19h chưa có. Giá thế giới lúc 19h giữ lại được một phần tín hiệu về chiều (so với khi không dùng nó), nhưng chưa đủ để vượt Naive có ý nghĩa thống kê và các mức "nghiêng về tăng/giảm" của bản 19h chỉ đúng 41–57% số lần (mức có ≥ 20 lần, tính cả phiên giá đứng yên). Vì vậy thông báo 19h chỉ báo **giá hôm nay** và **khoảng giá có thể** cho phiên tới; chiều tăng/giảm ghi **"Khó đoán"** cho tới khi kiểm định (chạy lại mỗi tuần) cho thấy có lợi thế. Dự báo chính thức vẫn là bản 7h sáng.

Cột: TheilU = RMSE / RMSE(Naive) (< 1 là hơn Naive); DM p: kiểm định Diebold–Mariano so với Naive; Đúng chiều: % phiên đoán đúng tăng/giảm (chỉ phiên giá có đổi); Mốc chiều: % của chiều phổ biến hơn (≥ "luôn đoán tăng"); p (chiều): kiểm định nhị thức một phía "đúng chiều > mốc"; Brier: sai số bình phương của P(tăng) (thấp là tốt), skill so với tần suất lịch sử; Phủ 80%: tỷ lệ giá thật rơi vào khoảng "nhiều khả năng".


## Vàng miếng SJC – 10/07/2024 → 25/11/2026 (605 phiên)


### Toàn giai đoạn có giá theo giờ

| Phiên bản | TheilU | DM p | Đúng chiều % | Mốc chiều % | p (chiều) | Brier | Brier skill | Phủ 80% | N |
|---|---|---|---|---|---|---|---|---|---|
| Bản chính thức 7h sáng (có phiên Mỹ đóng cửa) | 0.892 | 0.002 | 70.1 | 54.8 | 0.000 | 0.201 | +0.189 | 83.9% | 590 |
| **Bản sơ bộ 19h** (giá thế giới lúc 19h) | 0.978 | 0.348 | 61.1 | 54.8 | 0.004 | 0.238 | +0.041 | 84.6% | 590 |
| 19h nhưng KHÔNG dùng giá thế giới trong ngày | 1.010 | 0.404 | 55.9 | 54.8 | 0.337 | 0.251 | -0.014 | 84.7% | 590 |

Mốc: "luôn đoán tăng" đúng **54.8%** trong 458 phiên giá có đổi; 22.4% phiên giá đứng yên; Brier của tần suất lịch sử = 0.248.


### Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số)

| Phiên bản | TheilU | DM p | Đúng chiều % | Mốc chiều % | p (chiều) | Brier | Brier skill | Phủ 80% | N |
|---|---|---|---|---|---|---|---|---|---|
| Bản chính thức 7h sáng (có phiên Mỹ đóng cửa) | 0.888 | 0.016 | 67.8 | 54.3 | 0.000 | 0.206 | +0.205 | 82.1% | 246 |
| **Bản sơ bộ 19h** (giá thế giới lúc 19h) | 0.980 | 0.523 | 61.1 | 54.3 | 0.030 | 0.234 | +0.096 | 85.0% | 246 |
| 19h nhưng KHÔNG dùng giá thế giới trong ngày | 1.015 | 0.347 | 49.5 | 54.3 | 0.928 | 0.255 | +0.017 | 85.0% | 246 |

Mốc: "luôn đoán tăng" đúng **45.7%** trong 208 phiên giá có đổi; 15.4% phiên giá đứng yên; Brier của tần suất lịch sử = 0.259.


**Bản sơ bộ: khi nói ... thì đúng mấy lần** (phiên giá đứng yên tính là *không đúng*):

| Mức | Số lần | Đúng |
|---|---|---|
| Nghiêng rõ về giảm | 37 | 54% |
| Hơi nghiêng về giảm | 111 | 48% |
| Không rõ ràng | 95 | – |
| Hơi nghiêng về tăng | 205 | 41% |
| Nghiêng rõ về tăng | 142 | 57% |

**Kết luận cổng trung thực:** KHÔNG đủ lợi thế → thông báo 19h ghi “Khó đoán” (chưa vượt Naive (TheilU 0.978, DM p 0.348)).


*Kiểm tra kỹ thuật:* tái tạo dự báo bản sáng lệch tối đa 1.17e-13 (log-return) so với backtest đã lưu; tính đặc trưng trên cửa sổ cắt lệch tối đa 8.2e-12 so với đặc trưng gốc; 6 ngày chưa có giá vàng của phiên T trước 19h (dùng giá gần nhất).


## Vàng nhẫn 9999 (PNJ) – 20/06/2025 → 25/11/2026 (365 phiên)


### Toàn giai đoạn có giá theo giờ

| Phiên bản | TheilU | DM p | Đúng chiều % | Mốc chiều % | p (chiều) | Brier | Brier skill | Phủ 80% | N |
|---|---|---|---|---|---|---|---|---|---|
| Bản chính thức 7h sáng (có phiên Mỹ đóng cửa) | 0.894 | 0.065 | 69.9 | 51.6 | 0.000 | 0.188 | +0.269 | 78.5% | 356 |
| **Bản sơ bộ 19h** (giá thế giới lúc 19h) | 1.018 | 0.549 | 55.0 | 51.6 | 0.132 | 0.249 | +0.028 | 78.8% | 356 |
| 19h nhưng KHÔNG dùng giá thế giới trong ngày | 1.014 | 0.320 | 51.2 | 51.6 | 0.570 | 0.255 | +0.008 | 78.5% | 356 |

Mốc: "luôn đoán tăng" đúng **51.6%** trong 289 phiên giá có đổi; 18.8% phiên giá đứng yên; Brier của tần suất lịch sử = 0.257.


### Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số)

| Phiên bản | TheilU | DM p | Đúng chiều % | Mốc chiều % | p (chiều) | Brier | Brier skill | Phủ 80% | N |
|---|---|---|---|---|---|---|---|---|---|
| Bản chính thức 7h sáng (có phiên Mỹ đóng cửa) | 0.913 | 0.172 | 71.9 | 53.8 | 0.000 | 0.205 | +0.209 | 81.0% | 242 |
| **Bản sơ bộ 19h** (giá thế giới lúc 19h) | 1.025 | 0.474 | 56.3 | 53.8 | 0.262 | 0.254 | +0.020 | 82.6% | 242 |
| 19h nhưng KHÔNG dùng giá thế giới trong ngày | 1.020 | 0.207 | 49.2 | 53.8 | 0.911 | 0.258 | +0.005 | 83.5% | 242 |

Mốc: "luôn đoán tăng" đúng **46.2%** trong 199 phiên giá có đổi; 17.8% phiên giá đứng yên; Brier của tần suất lịch sử = 0.259.


**Bản sơ bộ: khi nói ... thì đúng mấy lần** (phiên giá đứng yên tính là *không đúng*):

| Mức | Số lần | Đúng |
|---|---|---|
| Nghiêng rõ về giảm | 8 | 25% |
| Hơi nghiêng về giảm | 88 | 55% |
| Không rõ ràng | 79 | – |
| Hơi nghiêng về tăng | 58 | 47% |
| Nghiêng rõ về tăng | 93 | 53% |

**Kết luận cổng trung thực:** KHÔNG đủ lợi thế → thông báo 19h ghi “Khó đoán” (chưa vượt Naive (TheilU 1.018, DM p 0.549); giai đoạn khoá TheilU 1.025 >= 1).


*Kiểm tra kỹ thuật:* tái tạo dự báo bản sáng lệch tối đa 2.43e-16 (log-return) so với backtest đã lưu; tính đặc trưng trên cửa sổ cắt lệch tối đa 6.9e-12 so với đặc trưng gốc; 3 ngày chưa có giá vàng của phiên T trước 19h (dùng giá gần nhất).


## Hạn chế

- Giá trong nước ngày T trong kiểm định là giá **cuối ngày** (bản ghi ~23h59 của CafeF). Thông báo dùng giá lúc 19h; dữ liệu CafeF cho thấy giá hầu như không đổi sau 19h (1/465 ngày khác biệt với SJC trong lịch sử CafeF), nên ảnh hưởng nhỏ.
- Giá theo giờ của Yahoo chỉ có ~2 năm gần nhất, nên giai đoạn kiểm định ngắn hơn bản sáng.
- Khi chạy thật, mô hình được huấn luyện trên mọi nhãn đã biết (mới hơn so với lịch huấn luyện lại 21 phiên trong kiểm định), và lớp tự học dùng trạng thái tại lần kiểm định gần nhất (chạy lại tự động mỗi tuần).
- Nếu gửi bù muộn hơn 19h, giá thế giới dùng là giá lúc gửi (nhiều thông tin hơn, không ít hơn).
