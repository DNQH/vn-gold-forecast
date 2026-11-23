"""Module 4 - ML Prediction Engine.

Mọi mô hình dự báo **lợi suất log h phiên** r̂_{t,h}. Giao diện chung:
    model.fit(ds, train_idx, h)      # train_idx: vị trí các hàng được phép học
    model.predict(ds, test_idx, h)   # -> np.ndarray lợi suất dự báo
`ds` là WFData chứa X (đặc trưng), Y (mục tiêu), r1 (lợi suất ngày), giá.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from vngold.config import RANDOM_STATE

SCALE = 100.0  # học trên đơn vị % để ổn định số học


@dataclass
class WFData:
    X: pd.DataFrame
    Y: pd.DataFrame          # cột y_h
    price: pd.Series
    r1: pd.Series            # lợi suất log ngày

    def y(self, h: int) -> np.ndarray:
        return self.Y[f"y_{h}"].to_numpy()


def recency_weights(n: int, halflife: float | None) -> np.ndarray:
    if not halflife:
        return np.ones(n)
    age = np.arange(n)[::-1]
    return 0.5 ** (age / halflife)


# ------------------------------------------------------------------ Benchmarks
class Naive:
    """Giá ngày mai = giá hôm nay (random walk)."""
    name = "Naive"

    def fit(self, ds, idx, h):
        return self

    def predict(self, ds, idx, h):
        return np.zeros(len(idx))


class MovingAverage:
    """Giá tương lai = trung bình giá k phiên gần nhất."""
    name = "MovingAverage"

    def __init__(self, k: int = 5):
        self.k = k

    def fit(self, ds, idx, h):
        return self

    def predict(self, ds, idx, h):
        lp = np.log(ds.price)
        ma = np.log(ds.price.rolling(self.k).mean())
        return (ma - lp).to_numpy()[idx]


# ------------------------------------------------------------------ Thống kê
class ARIMAModel:
    """ARIMA(p,0,q) trên lợi suất ngày; dự báo h bước rồi cộng dồn."""
    name = "ARIMA"

    def __init__(self, order=(1, 0, 1), window: int = 750):
        self.order, self.window = order, window

    def fit(self, ds, idx, h):
        from statsmodels.tsa.arima.model import ARIMA
        end = idx[-1] + h  # lợi suất ngày đã biết tới thời điểm huấn luyện
        r = ds.r1.to_numpy()[max(1, end - self.window + 1): end + 1] * SCALE
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.res = ARIMA(r, order=self.order, trend="c").fit()
        return self

    def predict(self, ds, idx, h):
        r_all = ds.r1.to_numpy() * SCALE
        out = np.empty(len(idx))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for k, t in enumerate(idx):
                hist = r_all[max(1, t - self.window + 1): t + 1]
                out[k] = self.res.apply(hist).forecast(h).sum()
        return out / SCALE


# ------------------------------------------------------------------ ML dạng bảng
class _Tabular:
    halflife = None

    def _xy(self, ds, idx, h):
        y = ds.y(h)[idx]
        m = ~np.isnan(y)
        return ds.X.iloc[idx[m]], y[m] * SCALE, recency_weights(m.sum(), self.halflife)

    def predict(self, ds, idx, h):
        return self.model.predict(ds.X.iloc[idx]) / SCALE


class LinearRegressionModel(_Tabular):
    """Hồi quy tuyến tính (Ridge, chọn alpha bằng CV) - baseline."""
    name = "LinearRegression"

    def fit(self, ds, idx, h):
        X, y, w = self._xy(ds, idx, h)
        self.model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                   RidgeCV(alphas=np.logspace(-1, 4, 20)))
        self.model.fit(X, y)
        return self


class RandomForestModel(_Tabular):
    name = "RandomForest"

    def fit(self, ds, idx, h):
        X, y, w = self._xy(ds, idx, h)
        self.model = make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestRegressor(n_estimators=300, max_depth=6, min_samples_leaf=20,
                                  max_features=0.5, n_jobs=-1, random_state=RANDOM_STATE))
        self.model.fit(X, y)
        return self


class XGBoostModel(_Tabular):
    name = "XGBoost"

    def __init__(self, halflife: float | None = 750, **params):
        self.halflife = halflife
        self.params = dict(n_estimators=300, max_depth=2, learning_rate=0.02,
                           subsample=0.8, colsample_bytree=0.5, min_child_weight=30,
                           reg_lambda=5.0, objective="reg:pseudohubererror",
                           random_state=RANDOM_STATE, n_jobs=-1, tree_method="hist")
        self.params.update(params)

    def fit(self, ds, idx, h):
        from xgboost import XGBRegressor
        X, y, w = self._xy(ds, idx, h)
        self.model = XGBRegressor(**self.params)
        self.model.fit(X, y, sample_weight=w)
        return self


# ------------------------------------------------------------------ Deep Learning
class LSTMModel:
    """LSTM (PyTorch) học trên chuỗi L phiên đặc trưng.

    Học liên tục (warm start): mỗi lần walk-forward huấn luyện lại, mạng tiếp tục
    từ trọng số cũ với dữ liệu mới thay vì học lại từ đầu.
    Mạng chạy trong tiến trình riêng (xem lstm_worker.py) để tránh xung đột OpenMP.
    """
    name = "LSTM"
    _counter = 0

    def __init__(self, seq_len: int = 20, hidden: int = 32, epochs_first: int = 40,
                 epochs_update: int = 8, lr: float = 1e-3, max_features: int = 30):
        self.seq_len, self.hidden = seq_len, hidden
        self.epochs_first, self.epochs_update, self.lr = epochs_first, epochs_update, lr
        self.max_features = max_features
        self.trained = False
        LSTMModel._counter += 1
        self.key = f"lstm{LSTMModel._counter}"

    def _prep(self, ds):
        X = ds.X[self.cols].to_numpy(dtype=np.float32)
        X = np.where(np.isnan(X), self.med, X)
        return np.clip((X - self.mu) / self.sd, -5, 5).astype(np.float32)

    def _seq(self, Z, idx):
        L = self.seq_len
        out = np.zeros((len(idx), L, Z.shape[1]), dtype=np.float32)
        for k, t in enumerate(idx):
            s = max(0, t - L + 1)
            out[k, L - (t - s + 1):] = Z[s:t + 1]
        return out

    def fit(self, ds, idx, h):
        from vngold.lstm_worker import TorchWorker
        y = ds.y(h)[idx]
        m = ~np.isnan(y)
        idx, y = idx[m], y[m] * SCALE
        if not self.trained:
            # chọn tập đặc trưng gọn cho LSTM (tương quan tuyệt đối lớn nhất với mục tiêu)
            corr = ds.X.iloc[idx].corrwith(pd.Series(y, index=ds.X.index[idx])).abs()
            self.cols = list(corr.dropna().sort_values(ascending=False).index[: self.max_features])
            # chuẩn hoá cố định theo dữ liệu lần đầu để warm start nhất quán
            Xtr = ds.X.iloc[idx][self.cols].to_numpy(dtype=np.float32)
            self.med = np.nanmedian(Xtr, axis=0)
            Xtr = np.where(np.isnan(Xtr), self.med, Xtr)
            self.mu, self.sd = Xtr.mean(0), Xtr.std(0) + 1e-8
        S = self._seq(self._prep(ds), idx)
        w = recency_weights(len(y), 750).astype(np.float32)
        epochs = self.epochs_update if self.trained else self.epochs_first
        TorchWorker.get(RANDOM_STATE).call("fit", self.key, S, y.astype(np.float32), w,
                                           epochs, self.hidden, self.lr)
        self.trained = True
        return self

    def predict(self, ds, idx, h):
        from vngold.lstm_worker import TorchWorker
        S = self._seq(self._prep(ds), np.asarray(idx))
        return np.asarray(TorchWorker.get().call("predict", self.key, S)) / SCALE


def default_models(include_lstm: bool = True):
    ms = [Naive(), MovingAverage(5), LinearRegressionModel(), ARIMAModel(),
          RandomForestModel(), XGBoostModel()]
    if include_lstm:
        ms.append(LSTMModel())
    return ms
