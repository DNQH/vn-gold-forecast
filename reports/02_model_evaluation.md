# Phase 2 – Đánh giá mô hình (walk-forward)

Dữ liệu tới 23/11/2026. Thời điểm phát hành dự báo: sáng sớm giờ VN (sau khi phiên Mỹ đóng cửa, trước khi niêm yết giá trong ngày). Huấn luyện lại mỗi 21 phiên, cửa sổ mở rộng, chỉ học trên nhãn đã biết.

Chỉ số giá tính bằng **triệu VND/lượng**. TheilU = RMSE / RMSE(Naive) (<1 là tốt hơn Naive). DM_p: p-value kiểm định Diebold–Mariano so với Naive.


## Vàng miếng SJC


### Kỳ hạn 1 ngày (h = 1 phiên) – kiểm định 04/2019–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 0.472 | 1.035 | 0.499 | 1.000 | – | – | 55.383 | – | – | 1823 |
| MovingAverage | 0.786 | 1.608 | 0.824 | 1.553 | 0.000 | 48.833 | 55.383 | -6.550 | 1.000 | 1823 |
| LinearRegression | 0.467 | 0.953 | 0.510 | 0.921 | 0.032 | 63.878 | 55.383 | 8.495 | 0.000 | 1823 |
| ARIMA | 0.486 | 1.042 | 0.513 | 1.007 | 0.579 | 52.789 | 55.383 | -2.594 | 0.981 | 1823 |
| RandomForest | 0.443 | 0.948 | 0.473 | 0.915 | 0.000 | 65.953 | 55.383 | 10.571 | 0.000 | 1823 |
| XGBoost | 0.445 | 0.965 | 0.473 | 0.933 | 0.000 | 66.667 | 55.383 | 11.284 | 0.000 | 1823 |
| Ensemble_raw | 0.449 | 0.972 | 0.476 | 0.939 | 0.000 | 66.018 | 55.383 | 10.636 | 0.000 | 1823 |
| Ensemble | 0.439 | 0.948 | 0.468 | 0.916 | 0.000 | 65.888 | 55.383 | 10.506 | 0.000 | 1823 |

Khoảng tin cậy 90% bao phủ thực tế: **90.1%** · 80%: **79.9%** · Brier score P(tăng): 0.218 (skill so với tần suất lịch sử: +0.122)

**Kết luận:** Ensemble có lợi thế có ý nghĩa thống kê so với Naive → công bố dự báo điểm.


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 91.0%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 2.214 | 1.000 | – | – | 54.106 | – | 244 |
| MovingAverage | 3.326 | 1.503 | 0.000 | 45.411 | 54.106 | -8.696 | 244 |
| LinearRegression | 1.953 | 0.882 | 0.051 | 66.184 | 54.106 | 12.077 | 244 |
| ARIMA | 2.218 | 1.002 | 0.908 | 43.478 | 54.106 | -10.628 | 244 |
| RandomForest | 2.006 | 0.906 | 0.004 | 66.667 | 54.106 | 12.560 | 244 |
| XGBoost | 2.061 | 0.931 | 0.001 | 67.633 | 54.106 | 13.527 | 244 |
| Ensemble_raw | 2.055 | 0.928 | 0.003 | 68.116 | 54.106 | 14.010 | 244 |
| Ensemble | 2.000 | 0.904 | 0.008 | 68.116 | 54.106 | 14.010 | 244 |

### Kỳ hạn 7 ngày (h = 5 phiên) – kiểm định 04/2019–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 1.238 | 2.430 | 1.294 | 1.000 | – | – | 59.665 | – | – | 1777 |
| MovingAverage | 1.389 | 2.716 | 1.448 | 1.118 | 0.001 | 46.858 | 59.665 | -12.807 | 1.000 | 1777 |
| LinearRegression | 1.565 | 2.723 | 1.767 | 1.120 | 0.000 | 55.536 | 59.665 | -4.129 | 1.000 | 1777 |
| ARIMA | 1.276 | 2.480 | 1.335 | 1.020 | 0.293 | 57.151 | 59.665 | -2.513 | 0.983 | 1777 |
| RandomForest | 1.276 | 2.476 | 1.332 | 1.019 | 0.209 | 54.339 | 59.665 | -5.326 | 1.000 | 1777 |
| XGBoost | 1.254 | 2.449 | 1.314 | 1.008 | 0.637 | 54.039 | 59.665 | -5.625 | 1.000 | 1777 |
| Ensemble_raw | 1.251 | 2.445 | 1.312 | 1.006 | 0.548 | 58.288 | 59.665 | -1.376 | 0.879 | 1777 |
| Ensemble | 1.253 | 2.457 | 1.313 | 1.011 | 0.533 | 50.628 | 59.665 | -9.037 | 1.000 | 1777 |

Khoảng tin cậy 90% bao phủ thực tế: **89.5%** · 80%: **80.1%** · Brier score P(tăng): 0.258 (skill so với tần suất lịch sử: -0.064)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 89.6%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 4.879 | 1.000 | – | – | 56.838 | – | 240 |
| MovingAverage | 5.272 | 1.080 | 0.106 | 38.889 | 56.838 | -17.949 | 240 |
| LinearRegression | 5.356 | 1.098 | 0.038 | 50.427 | 56.838 | -6.410 | 240 |
| ARIMA | 5.113 | 1.048 | 0.138 | 40.598 | 56.838 | -16.239 | 240 |
| RandomForest | 4.884 | 1.001 | 0.956 | 50.000 | 56.838 | -6.838 | 240 |
| XGBoost | 4.980 | 1.021 | 0.460 | 49.145 | 56.838 | -7.692 | 240 |
| Ensemble_raw | 4.947 | 1.014 | 0.383 | 50.855 | 56.838 | -5.983 | 240 |
| Ensemble | 4.955 | 1.016 | 0.593 | 55.128 | 56.838 | -1.709 | 240 |

### Kỳ hạn 30 ngày (h = 21 phiên) – kiểm định 04/2019–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 3.033 | 5.231 | 3.107 | 1.000 | – | – | 66.301 | – | – | 1765 |
| MovingAverage | 3.191 | 5.452 | 3.254 | 1.042 | 0.004 | 41.720 | 66.301 | -24.582 | 1.000 | 1765 |
| LinearRegression | 4.032 | 6.226 | 4.516 | 1.190 | 0.006 | 51.471 | 66.301 | -14.830 | 1.000 | 1765 |
| ARIMA | 3.107 | 5.463 | 3.193 | 1.044 | 0.442 | 65.032 | 66.301 | -1.269 | 0.873 | 1765 |
| RandomForest | 3.137 | 5.664 | 3.201 | 1.083 | 0.257 | 59.781 | 66.301 | -6.520 | 1.000 | 1765 |
| XGBoost | 2.888 | 5.279 | 2.983 | 1.009 | 0.897 | 60.819 | 66.301 | -5.482 | 1.000 | 1765 |
| Ensemble_raw | 3.030 | 5.309 | 3.136 | 1.015 | 0.741 | 59.550 | 66.301 | -6.751 | 1.000 | 1765 |
| Ensemble | 2.986 | 5.378 | 3.085 | 1.028 | 0.651 | 59.261 | 66.301 | -7.040 | 1.000 | 1765 |

Khoảng tin cậy 90% bao phủ thực tế: **87.8%** · 80%: **79.7%** · Brier score P(tăng): 0.258 (skill so với tần suất lịch sử: -0.104)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 90.6%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 9.974 | 1.000 | – | – | 66.816 | – | 224 |
| MovingAverage | 10.314 | 1.034 | 0.143 | 34.081 | 66.816 | -32.735 | 224 |
| LinearRegression | 12.656 | 1.269 | 0.005 | 34.978 | 66.816 | -31.839 | 224 |
| ARIMA | 11.664 | 1.170 | 0.119 | 32.735 | 66.816 | -34.081 | 224 |
| RandomForest | 11.694 | 1.173 | 0.223 | 46.188 | 66.816 | -20.628 | 224 |
| XGBoost | 11.267 | 1.130 | 0.346 | 53.363 | 66.816 | -13.453 | 224 |
| Ensemble_raw | 11.068 | 1.110 | 0.192 | 41.256 | 66.816 | -25.561 | 224 |
| Ensemble | 11.166 | 1.120 | 0.333 | 52.915 | 66.816 | -13.901 | 224 |

## Vàng nhẫn 9999


### Kỳ hạn 1 ngày (h = 1 phiên) – kiểm định 06/2025–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 1.148 | 2.028 | 0.747 | 1.000 | – | – | 51.736 | – | – | 354 |
| LinearRegression | 1.133 | 1.840 | 0.736 | 0.908 | 0.078 | 69.444 | 51.736 | 17.708 | 0.000 | 354 |
| XGBoost | 1.066 | 1.871 | 0.690 | 0.923 | 0.001 | 71.528 | 51.736 | 19.792 | 0.000 | 354 |
| Ensemble_raw | 1.073 | 1.867 | 0.696 | 0.921 | 0.002 | 70.139 | 51.736 | 18.403 | 0.000 | 354 |
| Ensemble | 1.091 | 1.852 | 0.708 | 0.914 | 0.029 | 68.403 | 51.736 | 16.667 | 0.000 | 354 |

Khoảng tin cậy 90% bao phủ thực tế: **90.1%** · 80%: **79.3%** · Brier score P(tăng): 0.199 (skill so với tần suất lịch sử: +0.210)

**Kết luận:** Ensemble có lợi thế có ý nghĩa thống kê so với Naive → công bố dự báo điểm.


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 92.5%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 2.314 | 1.000 | – | – | 53.535 | – | 240 |
| LinearRegression | 2.108 | 0.911 | 0.129 | 69.192 | 53.535 | 15.657 | 240 |
| XGBoost | 2.159 | 0.933 | 0.008 | 67.677 | 53.535 | 14.141 | 240 |
| Ensemble_raw | 2.147 | 0.928 | 0.012 | 68.182 | 53.535 | 14.646 | 240 |
| Ensemble | 2.130 | 0.921 | 0.072 | 71.717 | 53.535 | 18.182 | 240 |

### Kỳ hạn 7 ngày (h = 5 phiên) – kiểm định 06/2025–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 3.099 | 4.558 | 2.037 | 1.000 | – | – | 51.479 | – | – | 346 |
| LinearRegression | 7.023 | 8.801 | 4.639 | 1.931 | 0.000 | 51.479 | 51.479 | 0.000 | 0.522 | 346 |
| XGBoost | 3.275 | 4.720 | 2.141 | 1.036 | 0.282 | 60.947 | 51.479 | 9.467 | 0.000 | 346 |
| Ensemble_raw | 3.810 | 5.233 | 2.496 | 1.148 | 0.004 | 52.959 | 51.479 | 1.479 | 0.312 | 346 |
| Ensemble | 3.095 | 4.559 | 2.031 | 1.000 | 0.989 | 61.834 | 51.479 | 10.355 | 0.000 | 346 |

Khoảng tin cậy 90% bao phủ thực tế: **89.1%** · 80%: **77.9%** · Brier score P(tăng): 0.257 (skill so với tần suất lịch sử: +0.019)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 94.0%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 5.028 | 1.000 | – | – | 58.850 | – | 232 |
| LinearRegression | 9.208 | 1.831 | 0.000 | 50.442 | 58.850 | -8.407 | 232 |
| XGBoost | 5.283 | 1.051 | 0.189 | 55.752 | 58.850 | -3.097 | 232 |
| Ensemble_raw | 5.666 | 1.127 | 0.027 | 50.442 | 58.850 | -8.407 | 232 |
| Ensemble | 5.071 | 1.009 | 0.765 | 58.407 | 58.850 | -0.442 | 232 |

### Kỳ hạn 30 ngày (h = 21 phiên) – kiểm định 06/2025–11/2026

| model | MAE | RMSE | MAPE_% | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | Dir_p | N |
|---|---|---|---|---|---|---|---|---|---|---|
| Naive | 7.790 | 9.792 | 5.097 | 1.000 | – | – | 55.927 | – | – | 330 |
| LinearRegression | 16.844 | 21.120 | 10.966 | 2.157 | 0.006 | 50.760 | 55.927 | -5.167 | 0.974 | 330 |
| XGBoost | 8.324 | 10.512 | 5.453 | 1.073 | 0.547 | 55.927 | 55.927 | 0.000 | 0.523 | 330 |
| Ensemble_raw | 10.215 | 12.442 | 6.650 | 1.271 | 0.100 | 48.936 | 55.927 | -6.991 | 0.995 | 330 |
| Ensemble | 7.863 | 9.977 | 5.156 | 1.019 | 0.843 | 63.222 | 55.927 | 7.295 | 0.004 | 330 |

Khoảng tin cậy 90% bao phủ thực tế: **87.5%** · 80%: **76.4%** · Brier score P(tăng): 0.262 (skill so với tần suất lịch sử: +0.200)

**Kết luận:** Ensemble **không** vượt Naive có ý nghĩa thống kê → dashboard chỉ công bố khoảng tin cậy và xác suất, điểm trung tâm = giá hiện tại (Naive).


*Giai đoạn khoá (sau 2025-11-30, chưa từng dùng để chỉnh tham số):* bao phủ 90% = 90.3%

| model | RMSE | TheilU | DM_p | DirAcc_% | DirBase_% | DirEdge_pp | N |
|---|---|---|---|---|---|---|---|
| Naive | 10.317 | 1.000 | – | – | 65.581 | – | 216 |
| LinearRegression | 24.296 | 2.355 | 0.007 | 26.512 | 65.581 | -39.070 | 216 |
| XGBoost | 12.148 | 1.177 | 0.231 | 34.419 | 65.581 | -31.163 | 216 |
| Ensemble_raw | 14.460 | 1.402 | 0.039 | 23.721 | 65.581 | -41.860 | 216 |
| Ensemble | 11.068 | 1.073 | 0.553 | 55.349 | 65.581 | -10.233 | 216 |