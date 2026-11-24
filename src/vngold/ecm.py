"""Mô hình hiệu chỉnh sai số (Error-Correction Model, ECM) cho giá vàng trong nước.

Ý tưởng cấu trúc: giá trong nước P_dom bám theo giá thế giới quy đổi P_w cộng một mức
chênh lệch (premium) thay đổi chậm. Khi phiên Mỹ đêm qua làm P_w dịch chuyển mà P_dom
chưa kịp theo, độ lệch của log-premium so với mức "bình thường" gần đây sẽ được điều
chỉnh dần trong các phiên sau:

    Δlog P_dom(t+1) = a + γ·ec_t + β0·Δlog P_w(t) + β1·Δlog P_w(t-1)
                      + δ0·Δlog P_dom(t) + δ1·Δlog P_dom(t-1) + ε
    ec_t = q_t - mean(q_{t-W+1..t}),   q = log P_dom - log P_w

Chống rò rỉ: mọi biến tại hàng t chỉ dùng P_dom chốt ngày t và phiên Mỹ ngày t (đóng
cửa ~4-5h sáng t+1 giờ VN), tức là đã biết trước thời điểm phát hành ~7h sáng t+1.
Ước lượng: OLS có trọng số giảm dần theo tuổi (half-life) hoặc Huber (bền với ngoại lai),
chỉ trên các hàng có nhãn đã biết (walk-forward cung cấp train_idx đúng chuẩn).

Biến thể dài hạn (h=5, 21) dùng cùng khung với động lượng vàng thế giới 5/21 phiên.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SCALE = 100.0
ECM_COLS = ["ec", "dw0", "dw1", "dp0", "dp1"]


def ecm_frame(df: pd.DataFrame, target: str = "sjc_sell", prem_window: int = 20,
              world: str = "vnd") -> pd.DataFrame:
    """Biến hồi quy ECM tại mỗi hàng t (chỉ dùng thông tin đến hàng t).

    world="vnd": P_w = giá thế giới quy đổi VND (xau_usd × usd_vnd);
    world="usd": P_w = xau_usd (bỏ tỷ giá - biến động chậm được hấp thụ bởi mean trượt).
    """
    lp = np.log(df[target])
    lw = np.log(df["world_vnd"] if world == "vnd" else df["xau_usd"])
    q = lp - lw
    dw, dp = lw.diff(), lp.diff()
    Z = pd.DataFrame({
        "ec": q - q.rolling(prem_window).mean(),
        "dw0": dw, "dw1": dw.shift(1),
        "dp0": dp, "dp1": dp.shift(1),
        # cho kỳ hạn dài: động lượng vàng thế giới & độ lệch premium dài hạn
        "dw5": lw.diff(5), "dw21": lw.diff(21),
        "ec120": q - q.rolling(120).mean(),
    }, index=df.index)
    return Z.replace([np.inf, -np.inf], np.nan)


def _weights(n: int, halflife: float | None) -> np.ndarray:
    if not halflife:
        return np.ones(n)
    return 0.5 ** (np.arange(n)[::-1] / halflife)


class ECMModel:
    """ECM tuyến tính, cùng giao diện fit/predict với các mô hình trong models.py.

    Z: DataFrame biến hồi quy đã căn theo ds.X.index (xem ecm_frame).
    window: chỉ dùng `window` hàng gần nhất (None = cửa sổ mở rộng).
    """
    name = "ECM"

    def __init__(self, Z: pd.DataFrame, cols=tuple(ECM_COLS), halflife: float | None = None,
                 window: int | None = None, robust: bool = False, name: str = "ECM"):
        self.Z, self.cols = Z, list(cols)
        self.halflife, self.window, self.robust = halflife, window, robust
        self.name = name

    def _design(self, idx):
        return self.Z[self.cols].to_numpy()[idx]

    def fit(self, ds, idx, h):
        if self.window:
            idx = idx[-self.window:]
        y = ds.y(h)[idx] * SCALE
        Zt = self._design(idx) * SCALE
        m = ~np.isnan(y) & ~np.isnan(Zt).any(axis=1)
        Zt, y = Zt[m], y[m]
        w = _weights(len(y), self.halflife)
        A = np.column_stack([np.ones(len(y)), Zt])
        if self.robust:
            from sklearn.linear_model import HuberRegressor
            hr = HuberRegressor(epsilon=1.35, alpha=1e-4, max_iter=500)
            hr.fit(Zt, y, sample_weight=w)
            self.beta = np.r_[hr.intercept_, hr.coef_]
        else:
            sw = np.sqrt(w)
            self.beta = np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)[0]
        return self

    def predict(self, ds, idx, h):
        Zt = self._design(np.asarray(idx)) * SCALE
        Zt = np.where(np.isnan(Zt), 0.0, Zt)  # thiếu dữ liệu -> coi biến động = 0
        return (self.beta[0] + Zt @ self.beta[1:]) / SCALE
