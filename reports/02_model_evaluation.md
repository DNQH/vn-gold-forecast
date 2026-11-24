# Phase 2 – Đánh giá mô hình (walk-forward)

Dữ liệu tới 24/11/2026. Thời điểm phát hành dự báo: sáng sớm giờ VN (sau khi phiên Mỹ đóng cửa, trước khi niêm yết giá trong ngày). Huấn luyện lại mỗi 21 phiên, cửa sổ mở rộng, chỉ học trên nhãn đã biết.

Chỉ số giá tính bằng **triệu VND/lượng**. TheilU = RMSE / RMSE(Naive) (<1 là tốt hơn Naive). DM_p: p-value kiểm định Diebold–Mariano so với Naive.


## Vàng miếng SJC


### Kỳ hạn 1 ngày (h = 1 phiên) – kiểm định 04/2019–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 0.472 | 1.035 | 0.499 | 1.000 | – | – | 55.383 | – | – | 1824 |
| MovingAverage | 0.786 | 1.607 | 0.824 | 1.553 | 0.000 | 48.833 | 55.383 | -6.550 | 1.000 | 1824 |
| LinearRegression | 0.467 | 0.953 | 0.510 | 0.921 | 0.032 | 63.878 | 55.383 | 8.495 | 0.000 | 1824 |
| ARIMA | 0.486 | 1.042 | 0.512 | 1.007 | 0.578 | 52.789 | 55.383 | -2.594 | 0.981 | 1824 |
| RandomForest | 0.443 | 0.947 | 0.473 | 0.915 | 0.000 | 65.953 | 55.383 | 10.571 | 0.000 | 1824 |
| XGBoost | 0.445 | 0.965 | 0.473 | 0.933 | 0.000 | 66.667 | 55.383 | 11.284 | 0.000 | 1824 |
| Ensemble_raw | 0.449 | 0.972 | 0.476 | 0.939 | 0.000 | 66.018 | 55.383 | 10.636 | 0.000 | 1824 |
| Ensemble | 0.439 | 0.948 | 0.468 | 0.916 | 0.000 | 65.888 | 55.383 | 10.506 | 0.000 | 1824 |

Khoảng tin cậy 90% bao phủ thực tế: **90.1%** · 80%: **79.9%** · Brier score P(tăng): 0.218 (skill so với tần suất lịch sử: +0.122)

**Kết luận:** Ensemble có lợi thế có ý nghĩa thống kê so với Naive → công bố dự báo điểm.


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 91.0%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 2.209 | 1.000 | – | – | 54.106 | – | 245 |
| MovingAverage | 3.320 | 1.503 | 0.000 | 45.411 | 54.106 | -8.696 | 245 |
| LinearRegression | 1.949 | 0.882 | 0.052 | 66.184 | 54.106 | 12.077 | 245 |
| ARIMA | 2.214 | 1.002 | 0.906 | 43.478 | 54.106 | -10.628 | 245 |
| RandomForest | 2.002 | 0.906 | 0.004 | 66.667 | 54.106 | 12.560 | 245 |
| XGBoost | 2.057 | 0.931 | 0.001 | 67.633 | 54.106 | 13.527 | 245 |
| Ensemble_raw | 2.051 | 0.928 | 0.003 | 68.116 | 54.106 | 14.010 | 245 |
| Ensemble | 1.997 | 0.904 | 0.008 | 68.116 | 54.106 | 14.010 | 245 |

### Kỳ hạn 7 ngày (h = 5 phiên) – kiểm định 04/2019–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 1.239 | 2.431 | 1.295 | 1.000 | – | – | 59.629 | – | – | 1778 |
| MovingAverage | 1.390 | 2.717 | 1.449 | 1.118 | 0.001 | 46.830 | 59.629 | -12.799 | 1.000 | 1778 |
| LinearRegression | 1.565 | 2.722 | 1.767 | 1.120 | 0.000 | 55.562 | 59.629 | -4.067 | 1.000 | 1778 |
| ARIMA | 1.277 | 2.480 | 1.335 | 1.020 | 0.289 | 57.117 | 59.629 | -2.512 | 0.983 | 1778 |
| RandomForest | 1.276 | 2.476 | 1.332 | 1.019 | 0.214 | 54.366 | 59.629 | -5.263 | 1.000 | 1778 |
| XGBoost | 1.255 | 2.449 | 1.315 | 1.008 | 0.637 | 54.067 | 59.629 | -5.562 | 1.000 | 1778 |
| Ensemble_raw | 1.252 | 2.445 | 1.312 | 1.006 | 0.551 | 58.313 | 59.629 | -1.316 | 0.869 | 1778 |
| Ensemble | 1.254 | 2.457 | 1.313 | 1.011 | 0.539 | 50.658 | 59.629 | -8.971 | 1.000 | 1778 |

Khoảng tin cậy 90% bao phủ thực tế: **89.5%** · 80%: **80.2%** · Brier score P(tăng): 0.258 (skill so với tần suất lịch sử: -0.063)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 89.6%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 4.872 | 1.000 | – | – | 57.021 | – | 241 |
| MovingAverage | 5.266 | 1.081 | 0.105 | 38.723 | 57.021 | -18.298 | 241 |
| LinearRegression | 5.346 | 1.097 | 0.039 | 50.638 | 57.021 | -6.383 | 241 |
| ARIMA | 5.107 | 1.048 | 0.136 | 40.426 | 57.021 | -16.596 | 241 |
| RandomForest | 4.875 | 1.001 | 0.970 | 50.213 | 57.021 | -6.809 | 241 |
| XGBoost | 4.972 | 1.021 | 0.461 | 49.362 | 57.021 | -7.660 | 241 |
| Ensemble_raw | 4.940 | 1.014 | 0.386 | 51.064 | 57.021 | -5.957 | 241 |
| Ensemble | 4.946 | 1.015 | 0.601 | 55.319 | 57.021 | -1.702 | 241 |

### Kỳ hạn 30 ngày (h = 21 phiên) – kiểm định 04/2019–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 3.035 | 5.232 | 3.108 | 1.000 | – | – | 66.263 | – | – | 1766 |
| MovingAverage | 3.193 | 5.453 | 3.255 | 1.042 | 0.004 | 41.696 | 66.263 | -24.567 | 1.000 | 1766 |
| LinearRegression | 4.033 | 6.225 | 4.516 | 1.190 | 0.006 | 51.499 | 66.263 | -14.764 | 1.000 | 1766 |
| ARIMA | 3.111 | 5.467 | 3.195 | 1.045 | 0.438 | 64.994 | 66.263 | -1.269 | 0.873 | 1766 |
| RandomForest | 3.139 | 5.664 | 3.202 | 1.083 | 0.257 | 59.804 | 66.263 | -6.459 | 1.000 | 1766 |
| XGBoost | 2.889 | 5.278 | 2.984 | 1.009 | 0.899 | 60.842 | 66.263 | -5.421 | 1.000 | 1766 |
| Ensemble_raw | 3.032 | 5.310 | 3.137 | 1.015 | 0.742 | 59.573 | 66.263 | -6.690 | 1.000 | 1766 |
| Ensemble | 2.987 | 5.379 | 3.085 | 1.028 | 0.653 | 59.285 | 66.263 | -6.978 | 1.000 | 1766 |

Khoảng tin cậy 90% bao phủ thực tế: **87.8%** · 80%: **79.7%** · Brier score P(tăng): 0.258 (skill so với tần suất lịch sử: -0.103)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 90.7%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 9.961 | 1.000 | – | – | 66.964 | – | 225 |
| MovingAverage | 10.302 | 1.034 | 0.141 | 33.929 | 66.964 | -33.036 | 225 |
| LinearRegression | 12.632 | 1.268 | 0.005 | 35.268 | 66.964 | -31.696 | 225 |
| ARIMA | 11.655 | 1.170 | 0.116 | 32.589 | 66.964 | -34.375 | 225 |
| RandomForest | 11.675 | 1.172 | 0.223 | 46.429 | 66.964 | -20.536 | 225 |
| XGBoost | 11.246 | 1.129 | 0.348 | 53.571 | 66.964 | -13.393 | 225 |
| Ensemble_raw | 11.052 | 1.109 | 0.193 | 41.518 | 66.964 | -25.446 | 225 |
| Ensemble | 11.148 | 1.119 | 0.334 | 53.125 | 66.964 | -13.839 | 225 |

## Vàng nhẫn 9999


### Kỳ hạn 1 ngày (h = 1 phiên) – kiểm định 06/2025–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 1.145 | 2.025 | 0.745 | 1.000 | – | – | 51.736 | – | – | 355 |
| LinearRegression | 1.134 | 1.839 | 0.737 | 0.908 | 0.080 | 69.444 | 51.736 | 17.708 | 0.000 | 355 |
| XGBoost | 1.065 | 1.868 | 0.690 | 0.923 | 0.001 | 71.528 | 51.736 | 19.792 | 0.000 | 355 |
| Ensemble_raw | 1.072 | 1.865 | 0.696 | 0.921 | 0.002 | 70.139 | 51.736 | 18.403 | 0.000 | 355 |
| Ensemble | 1.091 | 1.851 | 0.708 | 0.914 | 0.030 | 68.403 | 51.736 | 16.667 | 0.000 | 355 |

Khoảng tin cậy 90% bao phủ thực tế: **90.2%** · 80%: **79.4%** · Brier score P(tăng): 0.199 (skill so với tần suất lịch sử: +0.210)

**Kết luận:** Ensemble có lợi thế có ý nghĩa thống kê so với Naive → công bố dự báo điểm.


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 92.5%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 2.309 | 1.000 | – | – | 53.535 | – | 241 |
| LinearRegression | 2.106 | 0.912 | 0.132 | 69.192 | 53.535 | 15.657 | 241 |
| XGBoost | 2.155 | 0.933 | 0.008 | 67.677 | 53.535 | 14.141 | 241 |
| Ensemble_raw | 2.143 | 0.928 | 0.012 | 68.182 | 53.535 | 14.646 | 241 |
| Ensemble | 2.127 | 0.921 | 0.074 | 71.717 | 53.535 | 18.182 | 241 |

### Kỳ hạn 7 ngày (h = 5 phiên) – kiểm định 06/2025–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 3.103 | 4.558 | 2.042 | 1.000 | – | – | 51.327 | – | – | 347 |
| LinearRegression | 7.003 | 8.788 | 4.625 | 1.928 | 0.000 | 51.622 | 51.327 | 0.295 | 0.479 | 347 |
| XGBoost | 3.279 | 4.720 | 2.145 | 1.036 | 0.281 | 60.767 | 51.327 | 9.440 | 0.000 | 347 |
| Ensemble_raw | 3.809 | 5.229 | 2.495 | 1.147 | 0.004 | 53.097 | 51.327 | 1.770 | 0.275 | 347 |
| Ensemble | 3.098 | 4.558 | 2.034 | 1.000 | 0.998 | 61.947 | 51.327 | 10.619 | 0.000 | 347 |

Khoảng tin cậy 90% bao phủ thực tế: **89.1%** · 80%: **78.0%** · Brier score P(tăng): 0.256 (skill so với tần suất lịch sử: +0.020)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 94.0%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 5.027 | 1.000 | – | – | 59.031 | – | 233 |
| LinearRegression | 9.188 | 1.828 | 0.000 | 50.661 | 59.031 | -8.370 | 233 |
| XGBoost | 5.281 | 1.050 | 0.188 | 55.507 | 59.031 | -3.524 | 233 |
| Ensemble_raw | 5.657 | 1.125 | 0.028 | 50.661 | 59.031 | -8.370 | 233 |
| Ensemble | 5.068 | 1.008 | 0.774 | 58.590 | 59.031 | -0.441 | 233 |

### Kỳ hạn 30 ngày (h = 21 phiên) – kiểm định 06/2025–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 7.791 | 9.788 | 5.100 | 1.000 | – | – | 55.758 | – | – | 331 |
| LinearRegression | 16.822 | 21.095 | 10.954 | 2.155 | 0.006 | 50.606 | 55.758 | -5.152 | 0.974 | 331 |
| XGBoost | 8.327 | 10.509 | 5.458 | 1.074 | 0.545 | 55.758 | 55.758 | 0.000 | 0.523 | 331 |
| Ensemble_raw | 10.211 | 12.433 | 6.651 | 1.270 | 0.099 | 48.788 | 55.758 | -6.970 | 0.995 | 331 |
| Ensemble | 7.860 | 9.969 | 5.157 | 1.019 | 0.845 | 63.333 | 55.758 | 7.576 | 0.003 | 331 |

Khoảng tin cậy 90% bao phủ thực tế: **87.5%** · 80%: **76.5%** · Brier score P(tăng): 0.262 (skill so với tần suất lịch sử: +0.202)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 90.3%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 10.308 | 1.000 | – | – | 65.741 | – | 217 |
| LinearRegression | 24.249 | 2.353 | 0.007 | 26.389 | 65.741 | -39.352 | 217 |
| XGBoost | 12.136 | 1.177 | 0.230 | 34.259 | 65.741 | -31.481 | 217 |
| Ensemble_raw | 14.440 | 1.401 | 0.039 | 23.611 | 65.741 | -42.130 | 217 |
| Ensemble | 11.052 | 1.072 | 0.555 | 55.556 | 65.741 | -10.185 | 217 |