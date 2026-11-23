# Phase 2 – Đánh giá mô hình (walk-forward)

Dữ liệu tới 20/11/2026. Thời điểm phát hành dự báo: sáng sớm giờ VN (sau khi phiên Mỹ đóng cửa, trước khi niêm yết giá trong ngày). Huấn luyện lại mỗi 21 phiên, cửa sổ mở rộng, chỉ học trên nhãn đã biết.

Chỉ số giá tính bằng **triệu VND/lượng**. TheilU = RMSE / RMSE(Naive) (<1 là tốt hơn Naive). DM_p: p-value kiểm định Diebold–Mariano so với Naive.


## Vàng miếng SJC


### Kỳ hạn 1 ngày (h = 1 phiên) – kiểm định 04/2019–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 0.472 | 1.035 | 0.499 | 1.000 | – | – | 55.354 | – | – | 1822 |
| MovingAverage | 0.785 | 1.607 | 0.824 | 1.553 | 0.000 | 48.799 | 55.354 | -6.554 | 1.000 | 1822 |
| LinearRegression | 0.465 | 0.951 | 0.509 | 0.918 | 0.026 | 63.920 | 55.354 | 8.566 | 0.000 | 1822 |
| ARIMA | 0.485 | 1.042 | 0.513 | 1.006 | 0.584 | 52.823 | 55.354 | -2.531 | 0.978 | 1822 |
| RandomForest | 0.442 | 0.946 | 0.472 | 0.914 | 0.000 | 65.996 | 55.354 | 10.642 | 0.000 | 1822 |
| XGBoost | 0.444 | 0.965 | 0.473 | 0.932 | 0.000 | 66.710 | 55.354 | 11.356 | 0.000 | 1822 |
| LSTM | 0.552 | 1.069 | 0.592 | 1.033 | 0.239 | 61.648 | 55.354 | 6.295 | 0.000 | 1822 |
| Ensemble_raw | 0.448 | 0.968 | 0.476 | 0.935 | 0.000 | 65.801 | 55.354 | 10.448 | 0.000 | 1822 |
| Ensemble | 0.439 | 0.947 | 0.468 | 0.914 | 0.000 | 66.126 | 55.354 | 10.772 | 0.000 | 1822 |

Khoảng tin cậy 90% bao phủ thực tế: **90.2%** · 80%: **80.0%** · Brier score P(tăng): 0.216 (skill so với tần suất lịch sử: +0.127)

**Kết luận:** Ensemble có lợi thế có ý nghĩa thống kê so với Naive → công bố dự báo điểm.


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 91.4%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 2.218 | 1.000 | – | – | 54.369 | – | 243 |
| MovingAverage | 3.331 | 1.502 | 0.000 | 45.146 | 54.369 | -9.223 | 243 |
| LinearRegression | 1.946 | 0.877 | 0.043 | 66.505 | 54.369 | 12.136 | 243 |
| ARIMA | 2.222 | 1.002 | 0.914 | 43.689 | 54.369 | -10.680 | 243 |
| RandomForest | 2.003 | 0.903 | 0.003 | 66.990 | 54.369 | 12.621 | 243 |
| XGBoost | 2.063 | 0.930 | 0.001 | 67.961 | 54.369 | 13.592 | 243 |
| LSTM | 2.222 | 1.002 | 0.959 | 64.078 | 54.369 | 9.709 | 243 |
| Ensemble_raw | 2.058 | 0.928 | 0.004 | 66.990 | 54.369 | 12.621 | 243 |
| Ensemble | 1.998 | 0.901 | 0.006 | 68.447 | 54.369 | 14.078 | 243 |

*Lớp tự học – đóng góp từng thành phần (cùng dự báo walk-forward):*

| Biến thể | RMSE | TheilU | DirAcc_% | Bao phủ 90% |
|---|---|---|---|---|
| Trung bình thường (không tự học) | 0.968 | 0.935 | 65.801 | 90.179 |
| Chỉ hiệu chỉnh độ lệch | 0.969 | 0.936 | 64.893 | 90.179 |
| Chỉ trọng số theo kỹ năng | 0.945 | 0.912 | 66.840 | 90.123 |
| Trọng số 1/MSE (bản cũ) | 0.967 | 0.934 | 64.568 | 90.234 |
| Đầy đủ (bản mới) | 0.947 | 0.914 | 66.126 | 90.179 |
| Đầy đủ, không nới khoảng (k=1) | 0.947 | 0.914 | 66.126 | 90.067 |

### Kỳ hạn 7 ngày (h = 5 phiên) – kiểm định 04/2019–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 1.237 | 2.430 | 1.294 | 1.000 | – | – | 59.701 | – | – | 1776 |
| MovingAverage | 1.387 | 2.715 | 1.447 | 1.117 | 0.002 | 46.886 | 59.701 | -12.814 | 1.000 | 1776 |
| LinearRegression | 1.565 | 2.723 | 1.768 | 1.121 | 0.000 | 55.509 | 59.701 | -4.192 | 1.000 | 1776 |
| ARIMA | 1.275 | 2.479 | 1.334 | 1.020 | 0.298 | 57.186 | 59.701 | -2.515 | 0.983 | 1776 |
| RandomForest | 1.275 | 2.476 | 1.332 | 1.019 | 0.204 | 54.311 | 59.701 | -5.389 | 1.000 | 1776 |
| XGBoost | 1.253 | 2.449 | 1.314 | 1.008 | 0.634 | 54.012 | 59.701 | -5.689 | 1.000 | 1776 |
| LSTM | 1.593 | 2.824 | 1.690 | 1.162 | 0.000 | 50.240 | 59.701 | -9.461 | 1.000 | 1776 |
| Ensemble_raw | 1.263 | 2.463 | 1.323 | 1.014 | 0.196 | 56.467 | 59.701 | -3.234 | 0.997 | 1776 |
| Ensemble | 1.253 | 2.457 | 1.313 | 1.011 | 0.526 | 50.479 | 59.701 | -9.222 | 1.000 | 1776 |

Khoảng tin cậy 90% bao phủ thực tế: **89.5%** · 80%: **80.1%** · Brier score P(tăng): 0.258 (skill so với tần suất lịch sử: -0.065)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 89.5%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 4.885 | 1.000 | – | – | 56.652 | – | 239 |
| MovingAverage | 5.276 | 1.080 | 0.110 | 39.056 | 56.652 | -17.597 | 239 |
| LinearRegression | 5.366 | 1.098 | 0.037 | 50.215 | 56.652 | -6.438 | 239 |
| ARIMA | 5.118 | 1.048 | 0.141 | 40.773 | 56.652 | -15.880 | 239 |
| RandomForest | 4.892 | 1.001 | 0.939 | 49.785 | 56.652 | -6.867 | 239 |
| XGBoost | 4.987 | 1.021 | 0.458 | 48.927 | 56.652 | -7.725 | 239 |
| LSTM | 5.472 | 1.120 | 0.002 | 45.923 | 56.652 | -10.730 | 239 |
| Ensemble_raw | 4.988 | 1.021 | 0.215 | 48.927 | 56.652 | -7.725 | 239 |
| Ensemble | 4.963 | 1.016 | 0.585 | 54.936 | 56.652 | -1.717 | 239 |

*Lớp tự học – đóng góp từng thành phần (cùng dự báo walk-forward):*

| Biến thể | RMSE | TheilU | DirAcc_% | Bao phủ 90% |
|---|---|---|---|---|
| Trung bình thường (không tự học) | 2.463 | 1.014 | 56.467 | 89.667 |
| Chỉ hiệu chỉnh độ lệch | 2.468 | 1.015 | 57.305 | 89.552 |
| Chỉ trọng số theo kỹ năng | 2.439 | 1.004 | 52.994 | 89.552 |
| Trọng số 1/MSE (bản cũ) | 2.450 | 1.008 | 58.862 | 89.552 |
| Đầy đủ (bản mới) | 2.457 | 1.011 | 50.479 | 89.495 |
| Đầy đủ, không nới khoảng (k=1) | 2.457 | 1.011 | 50.479 | 88.576 |

### Kỳ hạn 30 ngày (h = 21 phiên) – kiểm định 04/2019–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 3.031 | 5.230 | 3.106 | 1.000 | – | – | 66.339 | – | – | 1764 |
| MovingAverage | 3.189 | 5.450 | 3.253 | 1.042 | 0.004 | 41.744 | 66.339 | -24.596 | 1.000 | 1764 |
| LinearRegression | 4.032 | 6.226 | 4.516 | 1.191 | 0.006 | 51.443 | 66.339 | -14.896 | 1.000 | 1764 |
| ARIMA | 3.104 | 5.460 | 3.190 | 1.044 | 0.447 | 65.069 | 66.339 | -1.270 | 0.874 | 1764 |
| RandomForest | 3.136 | 5.663 | 3.201 | 1.083 | 0.256 | 59.758 | 66.339 | -6.582 | 1.000 | 1764 |
| XGBoost | 2.887 | 5.279 | 2.983 | 1.009 | 0.894 | 60.797 | 66.339 | -5.543 | 1.000 | 1764 |
| LSTM | 3.310 | 5.901 | 3.421 | 1.128 | 0.163 | 54.215 | 66.339 | -12.125 | 1.000 | 1764 |
| Ensemble_raw | 2.979 | 5.309 | 3.075 | 1.015 | 0.758 | 60.624 | 66.339 | -5.716 | 1.000 | 1764 |
| Ensemble | 2.984 | 5.389 | 3.083 | 1.030 | 0.625 | 59.296 | 66.339 | -7.044 | 1.000 | 1764 |

Khoảng tin cậy 90% bao phủ thực tế: **87.7%** · 80%: **79.6%** · Brier score P(tăng): 0.257 (skill so với tần suất lịch sử: -0.101)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 90.6%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 9.985 | 1.000 | – | – | 66.667 | – | 223 |
| MovingAverage | 10.325 | 1.034 | 0.144 | 34.234 | 66.667 | -32.432 | 223 |
| LinearRegression | 12.679 | 1.270 | 0.004 | 34.685 | 66.667 | -31.982 | 223 |
| ARIMA | 11.672 | 1.169 | 0.121 | 32.883 | 66.667 | -33.784 | 223 |
| RandomForest | 11.713 | 1.173 | 0.222 | 45.946 | 66.667 | -20.721 | 223 |
| XGBoost | 11.287 | 1.130 | 0.344 | 53.153 | 66.667 | -13.514 | 223 |
| LSTM | 11.236 | 1.125 | 0.446 | 42.793 | 66.667 | -23.874 | 223 |
| Ensemble_raw | 10.998 | 1.102 | 0.298 | 38.739 | 66.667 | -27.928 | 223 |
| Ensemble | 11.184 | 1.120 | 0.332 | 52.703 | 66.667 | -13.964 | 223 |

*Lớp tự học – đóng góp từng thành phần (cùng dự báo walk-forward):*

| Biến thể | RMSE | TheilU | DirAcc_% | Bao phủ 90% |
|---|---|---|---|---|
| Trung bình thường (không tự học) | 5.309 | 1.015 | 60.624 | 87.748 |
| Chỉ hiệu chỉnh độ lệch | 5.450 | 1.042 | 61.259 | 88.040 |
| Chỉ trọng số theo kỹ năng | 5.328 | 1.019 | 56.755 | 87.631 |
| Trọng số 1/MSE (bản cũ) | 5.353 | 1.024 | 59.527 | 88.506 |
| Đầy đủ (bản mới) | 5.389 | 1.030 | 59.296 | 87.748 |
| Đầy đủ, không nới khoảng (k=1) | 5.389 | 1.030 | 59.296 | 82.905 |

## Vàng nhẫn 9999


### Kỳ hạn 1 ngày (h = 1 phiên) – kiểm định 06/2025–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 1.150 | 2.030 | 0.748 | 1.000 | – | – | 51.568 | – | – | 353 |
| LinearRegression | 1.129 | 1.837 | 0.732 | 0.905 | 0.069 | 69.686 | 51.568 | 18.118 | 0.000 | 353 |
| XGBoost | 1.066 | 1.872 | 0.690 | 0.922 | 0.001 | 71.777 | 51.568 | 20.209 | 0.000 | 353 |
| Ensemble_raw | 1.072 | 1.869 | 0.695 | 0.920 | 0.002 | 70.383 | 51.568 | 18.815 | 0.000 | 353 |
| Ensemble | 1.088 | 1.852 | 0.705 | 0.912 | 0.027 | 68.641 | 51.568 | 17.073 | 0.000 | 353 |

Khoảng tin cậy 90% bao phủ thực tế: **90.1%** · 80%: **79.6%** · Brier score P(tăng): 0.197 (skill so với tần suất lịch sử: +0.218)

**Kết luận:** Ensemble có lợi thế có ý nghĩa thống kê so với Naive → công bố dự báo điểm.


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 92.5%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 2.319 | 1.000 | – | – | 53.807 | – | 239 |
| LinearRegression | 2.105 | 0.908 | 0.116 | 69.543 | 53.807 | 15.736 | 239 |
| XGBoost | 2.163 | 0.933 | 0.008 | 68.020 | 53.807 | 14.213 | 239 |
| Ensemble_raw | 2.149 | 0.927 | 0.011 | 68.528 | 53.807 | 14.721 | 239 |
| Ensemble | 2.131 | 0.919 | 0.067 | 72.081 | 53.807 | 18.274 | 239 |

*Lớp tự học – đóng góp từng thành phần (cùng dự báo walk-forward):*

| Biến thể | RMSE | TheilU | DirAcc_% | Bao phủ 90% |
|---|---|---|---|---|
| Trung bình thường (không tự học) | 1.869 | 0.920 | 70.383 | 90.093 |
| Chỉ hiệu chỉnh độ lệch | 1.873 | 0.923 | 71.777 | 90.402 |
| Chỉ trọng số theo kỹ năng | 1.855 | 0.914 | 63.763 | 90.402 |
| Trọng số 1/MSE (bản cũ) | 1.867 | 0.920 | 73.171 | 90.402 |
| Đầy đủ (bản mới) | 1.852 | 0.912 | 68.641 | 90.093 |
| Đầy đủ, không nới khoảng (k=1) | 1.852 | 0.912 | 68.641 | 90.093 |

### Kỳ hạn 7 ngày (h = 5 phiên) – kiểm định 06/2025–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 3.095 | 4.558 | 2.034 | 1.000 | – | – | 51.632 | – | – | 345 |
| LinearRegression | 7.040 | 8.813 | 4.650 | 1.934 | 0.000 | 51.335 | 51.632 | -0.297 | 0.565 | 345 |
| XGBoost | 3.272 | 4.721 | 2.138 | 1.036 | 0.281 | 60.831 | 51.632 | 9.199 | 0.000 | 345 |
| Ensemble_raw | 3.812 | 5.238 | 2.496 | 1.149 | 0.004 | 52.819 | 51.632 | 1.187 | 0.352 | 345 |
| Ensemble | 3.092 | 4.561 | 2.028 | 1.001 | 0.982 | 61.721 | 51.632 | 10.089 | 0.000 | 345 |

Khoảng tin cậy 90% bao phủ thực tế: **89.1%** · 80%: **77.8%** · Brier score P(tăng): 0.257 (skill so với tần suất lịch sử: +0.017)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 93.9%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 5.031 | 1.000 | – | – | 58.667 | – | 231 |
| LinearRegression | 9.228 | 1.834 | 0.000 | 50.222 | 58.667 | -8.444 | 231 |
| XGBoost | 5.287 | 1.051 | 0.188 | 55.556 | 58.667 | -3.111 | 231 |
| Ensemble_raw | 5.674 | 1.128 | 0.025 | 50.222 | 58.667 | -8.444 | 231 |
| Ensemble | 5.075 | 1.009 | 0.757 | 58.222 | 58.667 | -0.444 | 231 |

*Lớp tự học – đóng góp từng thành phần (cùng dự báo walk-forward):*

| Biến thể | RMSE | TheilU | DirAcc_% | Bao phủ 90% |
|---|---|---|---|---|
| Trung bình thường (không tự học) | 5.238 | 1.149 | 52.819 | 88.746 |
| Chỉ hiệu chỉnh độ lệch | 5.112 | 1.122 | 56.973 | 90.032 |
| Chỉ trọng số theo kỹ năng | 4.605 | 1.010 | 32.641 | 88.424 |
| Trọng số 1/MSE (bản cũ) | 4.651 | 1.020 | 62.315 | 89.389 |
| Đầy đủ (bản mới) | 4.561 | 1.001 | 61.721 | 89.068 |
| Đầy đủ, không nới khoảng (k=1) | 4.561 | 1.001 | 61.721 | 85.531 |

### Kỳ hạn 30 ngày (h = 21 phiên) – kiểm định 06/2025–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 7.788 | 9.796 | 5.093 | 1.000 | – | – | 56.098 | – | – | 329 |
| LinearRegression | 16.877 | 21.150 | 10.986 | 2.159 | 0.006 | 50.610 | 56.098 | -5.488 | 0.980 | 329 |
| XGBoost | 8.320 | 10.514 | 5.447 | 1.073 | 0.549 | 56.098 | 56.098 | 0.000 | 0.523 | 329 |
| Ensemble_raw | 10.221 | 12.453 | 6.652 | 1.271 | 0.100 | 48.780 | 56.098 | -7.317 | 0.997 | 329 |
| Ensemble | 7.864 | 9.984 | 5.155 | 1.019 | 0.841 | 63.110 | 56.098 | 7.012 | 0.006 | 329 |

Khoảng tin cậy 90% bao phủ thực tế: **87.5%** · 80%: **76.3%** · Brier score P(tăng): 0.263 (skill so với tần suất lịch sử: +0.199)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 90.2%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 10.324 | 1.000 | – | – | 65.421 | – | 215 |
| LinearRegression | 24.349 | 2.358 | 0.007 | 26.168 | 65.421 | -39.252 | 215 |
| XGBoost | 12.157 | 1.178 | 0.233 | 34.579 | 65.421 | -30.841 | 215 |
| Ensemble_raw | 14.483 | 1.403 | 0.039 | 23.364 | 65.421 | -42.056 | 215 |
| Ensemble | 11.082 | 1.073 | 0.551 | 55.140 | 65.421 | -10.280 | 215 |

*Lớp tự học – đóng góp từng thành phần (cùng dự báo walk-forward):*

| Biến thể | RMSE | TheilU | DirAcc_% | Bao phủ 90% |
|---|---|---|---|---|
| Trung bình thường (không tự học) | 12.453 | 1.271 | 48.780 | 85.305 |
| Chỉ hiệu chỉnh độ lệch | 12.546 | 1.281 | 61.890 | 85.305 |
| Chỉ trọng số theo kỹ năng | 10.110 | 1.032 | 39.634 | 87.455 |
| Trọng số 1/MSE (bản cũ) | 10.009 | 1.022 | 66.463 | 87.814 |
| Đầy đủ (bản mới) | 9.984 | 1.019 | 63.110 | 87.455 |
| Đầy đủ, không nới khoảng (k=1) | 9.984 | 1.019 | 63.110 | 85.305 |

## Thí nghiệm: nếu phát hành dự báo vào cuối ngày (h = 1)

Khi chưa biết diễn biến phiên Mỹ đêm đó, lợi thế gần như biến mất – phần lớn khả năng dự báo ngắn hạn đến từ độ trễ truyền dẫn giá thế giới vào giá trong nước.

| model | RMSE | DirAcc_% | TheilU | DM_p |
|---|---|---|---|---|
| Naive | 1.044 | – | 1.000 | – |
| LinearRegression | 1.046 | 54.492 | 1.002 | 0.428 |
| XGBoost | 1.054 | 52.000 | 1.010 | 0.016 |

## Kiểm tra từng nhóm đặc trưng (XGBoost, bỏ lần lượt từng nhóm)

Δ RMSE > 0 nghĩa là bỏ nhóm đó làm mô hình tệ đi ⇒ nhóm có giá trị dự báo.


### h = 1

| Bỏ nhóm | RMSE | TheilU | DirAcc_% | Δ RMSE khi bỏ |
|---|---|---|---|---|
| (đầy đủ) | 0.965 | 0.932 | 66.710 | – |
| Technical indicators | 0.969 | 0.935 | 66.191 | 0.003 |
| Macro (DXY, lợi suất, Fed, CPI...) | 0.963 | 0.930 | 66.580 | -0.002 |
| Domestic premium & pass-through | 0.972 | 0.939 | 65.542 | 0.007 |
| Vàng thế giới (XAU) | 0.981 | 0.948 | 65.801 | 0.016 |
| Tỷ giá USD/VND | 0.963 | 0.930 | 66.126 | -0.002 |

### h = 5

| Bỏ nhóm | RMSE | TheilU | DirAcc_% | Δ RMSE khi bỏ |
|---|---|---|---|---|
| (đầy đủ) | 2.449 | 1.008 | 54.012 | – |
| Technical indicators | 2.425 | 0.998 | 56.766 | -0.024 |
| Macro (DXY, lợi suất, Fed, CPI...) | 2.431 | 1.000 | 54.910 | -0.018 |
| Domestic premium & pass-through | 2.458 | 1.012 | 54.551 | 0.009 |
| Vàng thế giới (XAU) | 2.458 | 1.012 | 54.671 | 0.009 |
| Tỷ giá USD/VND | 2.436 | 1.003 | 55.090 | -0.012 |