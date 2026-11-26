"""Module 1 - Data Collection.

Nguồn dữ liệu:
  * Yahoo Finance  : vàng thế giới, DXY, US10Y, USD/VND, bạc, VIX
  * FRED           : lãi suất thực, Fed funds, kỳ vọng lạm phát, CPI, thất nghiệp
  * giavang.org    : lịch sử giá vàng SJC (và vàng nhẫn SJC 99,99 từ 2024) theo ngày
  * CafeF          : lịch sử giá SJC (02/2025 -> nay) và vàng nhẫn 999.9 (03/2024 -> nay)

Tất cả giá vàng trong nước được quy về **triệu VND / lượng**.
"""
from __future__ import annotations

import io
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup

from vngold.config import DATA_RAW, FRED_SERIES, HTTP_HEADERS, START_DATE, YAHOO_TICKERS

VN_TZ = "Asia/Ho_Chi_Minh"


# ----------------------------------------------------------------- Yahoo
def fetch_yahoo(start: str = START_DATE) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(list(YAHOO_TICKERS), start=start, progress=False,
                      threads=False, auto_adjust=False)
    close = raw["Close"].rename(columns=YAHOO_TICKERS)
    vol = raw["Volume"][["GC=F"]].rename(columns={"GC=F": "gold_volume"})
    df = close.join(vol)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "date"
    # Yahoo USD/VND đôi khi có điểm dị thường (vd. 0 hoặc nhảy x10) -> làm sạch
    v = df["usd_vnd"]
    df.loc[(v < 15000) | (v > 40000), "usd_vnd"] = pd.NA
    df.to_csv(DATA_RAW / "yahoo.csv")
    return df


# ----------------------------------------------------------------- FRED
def fetch_fred() -> pd.DataFrame:
    frames = []
    for sid, (name, _lag) in FRED_SERIES.items():
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=60)  # UA trình duyệt bị FRED treo -> dùng UA mặc định
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(3)
        s = pd.read_csv(io.StringIO(r.text))
        s.columns = ["date", name]
        s["date"] = pd.to_datetime(s["date"])
        s[name] = pd.to_numeric(s[name], errors="coerce")
        frames.append(s.set_index("date"))
    df = pd.concat(frames, axis=1).sort_index()
    df = df[df.index >= pd.Timestamp(START_DATE) - pd.DateOffset(years=1)]
    df.to_csv(DATA_RAW / "fred.csv")
    return df


# ----------------------------------------------------------------- CafeF
def _cafef_json(url: str) -> dict:
    r = requests.get(url, headers=HTTP_HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()["Data"]


def fetch_cafef() -> pd.DataFrame:
    """SJC (triệu/lượng) và vàng nhẫn PNJ 999.9 (nghìn/chỉ -> triệu/lượng)."""
    d = _cafef_json("https://cafef.vn/du-lieu/Ajax/ajaxgoldpricehistory.ashx?index=all")
    sjc = pd.DataFrame(d["goldPriceWorldHistories"])
    sjc["ts"] = pd.to_datetime(sjc["createdAt"], utc=True).dt.tz_convert(VN_TZ)
    sjc = sjc.rename(columns={"buyPrice": "sjc_buy", "sellPrice": "sjc_sell"})

    d2 = _cafef_json("https://cafef.vn/du-lieu/Ajax/AjaxGoldPriceRing.ashx?time=all&zone=11")
    ring = pd.DataFrame(d2["goldPriceWorldHistories"])
    ring["ts"] = pd.to_datetime(ring["lastUpdated"]).dt.tz_localize(VN_TZ)
    ring["ring_buy"] = ring["buyPrice"] / 100.0   # nghìn đồng/chỉ -> triệu đồng/lượng
    ring["ring_sell"] = ring["sellPrice"] / 100.0

    def daily_last(df, cols):
        df = df.sort_values("ts")
        df["date"] = df["ts"].dt.tz_localize(None).dt.normalize()
        return df.groupby("date")[cols].last()

    out = daily_last(sjc, ["sjc_buy", "sjc_sell"]).join(
        daily_last(ring, ["ring_buy", "ring_sell"]), how="outer")
    out["source"] = "cafef"
    out.to_csv(DATA_RAW / "cafef.csv")
    return out


def fetch_live_prices(timeout: int = 15) -> dict:
    """Giá niêm yết MỚI NHẤT (thời gian thực) của SJC và nhẫn PNJ 999.9 từ CafeF.

    Trả về {"sjc_sell": {"price", "buy", "ts"}, "ring_sell": {...}}; mục nào lỗi thì bỏ qua.
    Dùng cho dashboard (chấm điểm tạm thời dự báo của phiên đang diễn ra).
    """
    out = {}
    try:
        d = _cafef_json_t("https://cafef.vn/du-lieu/Ajax/ajaxgoldpricehistory.ashx?index=1W", timeout)
        h = max(d["goldPriceWorldHistories"], key=lambda r: r["createdAt"])
        ts = pd.Timestamp(h["createdAt"]).tz_convert(VN_TZ).tz_localize(None)
        out["sjc_sell"] = {"price": float(h["sellPrice"]), "buy": float(h["buyPrice"]), "ts": ts}
    except Exception:  # noqa: BLE001 - nguồn live không được làm hỏng dashboard
        pass
    try:
        d = _cafef_json_t("https://cafef.vn/du-lieu/Ajax/AjaxGoldPriceRing.ashx?time=1w&zone=11", timeout)
        h = max(d["goldPriceWorldHistories"], key=lambda r: r["lastUpdated"])
        out["ring_sell"] = {"price": h["sellPrice"] / 100.0, "buy": h["buyPrice"] / 100.0,
                            "ts": pd.Timestamp(h["lastUpdated"])}
    except Exception:  # noqa: BLE001
        pass
    return out


def fetch_recent_domestic(timeout: int = 15) -> dict:
    """Giá SJC và nhẫn PNJ 999.9 theo ngày trong ~1 tuần gần nhất (CafeF): bản ghi muộn nhất mỗi ngày.

    Trả về {"sjc_sell": DataFrame[date -> sell, buy, ts], "ring_sell": ...}; mục nào lỗi thì bỏ qua.
    Bản ghi của ngày hôm nay là giá đang niêm yết (CafeF cập nhật liên tục, chốt ~23h59)."""
    out = {}
    try:
        d = _cafef_json_t("https://cafef.vn/du-lieu/Ajax/ajaxgoldpricehistory.ashx?index=1W", timeout)
        s = pd.DataFrame(d["goldPriceWorldHistories"])
        s["ts"] = pd.to_datetime(s["createdAt"], utc=True).dt.tz_convert(VN_TZ).dt.tz_localize(None)
        s = s.rename(columns={"sellPrice": "sell", "buyPrice": "buy"})[["ts", "sell", "buy"]]
        out["sjc_sell"] = s
    except Exception:  # noqa: BLE001
        pass
    try:
        d = _cafef_json_t("https://cafef.vn/du-lieu/Ajax/AjaxGoldPriceRing.ashx?time=1w&zone=11", timeout)
        r = pd.DataFrame(d["goldPriceWorldHistories"])
        r["ts"] = pd.to_datetime(r["lastUpdated"])
        r["sell"], r["buy"] = r["sellPrice"] / 100.0, r["buyPrice"] / 100.0
        out["ring_sell"] = r[["ts", "sell", "buy"]]
    except Exception:  # noqa: BLE001
        pass
    for k, v in list(out.items()):
        v = v.sort_values("ts").astype({"sell": float, "buy": float})
        v["date"] = v["ts"].dt.normalize()
        out[k] = v.groupby("date")[["sell", "buy", "ts"]].last()
    return out


def _cafef_json_t(url: str, timeout: int) -> dict:
    r = requests.get(url, headers=HTTP_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()["Data"]


# ----------------------------------------------------------------- giavang.org
_PRICE = re.compile(r"^\d{1,3}(\.\d{3})+$|^\d{2,3}\.\d{1,3}$")
_TIME = re.compile(r"(\d{2}:\d{2}:\d{2}) (\d{2}/\d{2}/\d{4})")


def _to_million(txt: str) -> float:
    """'36.740' -> 36.74 ; '120.500' -> 120.5 (đơn vị gốc: nghìn đồng/lượng)."""
    return float(txt.replace(".", "").replace(",", "")) / 1000.0


def parse_giavang_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for table in soup.find_all("table"):
        current_type = None
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            prices = [c for c in cells if _PRICE.match(c)]
            times = [m for c in cells for m in _TIME.findall(c)]
            texts = [c for c in cells if not _PRICE.match(c) and not _TIME.search(c)]
            for t in texts:
                if t.lower().startswith(("vàng", "nữ trang")):
                    current_type = t
            if len(prices) >= 2 and times and current_type:
                hh, dmy = times[0]
                rows.append({
                    "ts": pd.to_datetime(f"{dmy} {hh}", format="%d/%m/%Y %H:%M:%S"),
                    "type": current_type,
                    "buy": _to_million(prices[0]),
                    "sell": _to_million(prices[1]),
                })
    return rows


def _fetch_giavang_day(d: date, session: requests.Session) -> tuple[date, list[dict] | None]:
    url = f"https://giavang.org/trong-nuoc/sjc/lich-su/{d:%Y-%m-%d}.html"
    for attempt in range(3):
        try:
            r = session.get(url, timeout=40)
            if r.status_code == 200:
                return d, parse_giavang_page(r.text)
        except requests.RequestException:
            pass
        time.sleep(1.5 * (attempt + 1))
    return d, None  # lỗi mạng -> sẽ thử lại lần chạy sau


def fetch_giavang_org(start: str = START_DATE, end: str | None = None,
                      workers: int = 6, verbose: bool = True) -> pd.DataFrame:
    """Cào lịch sử theo ngày, có cache: chỉ tải những ngày chưa có."""
    cache = DATA_RAW / "giavang_org_ticks.csv"
    done_file = DATA_RAW / "giavang_org_done.txt"
    ticks = pd.read_csv(cache, parse_dates=["ts"]) if cache.exists() else pd.DataFrame(
        columns=["ts", "type", "buy", "sell", "page_date"])
    done = set(done_file.read_text().split()) if done_file.exists() else set()

    end_d = pd.Timestamp(end).date() if end else date.today()
    days, d = [], pd.Timestamp(start).date()
    while d <= end_d:
        # các ngày gần đây luôn tải lại vì có thể chưa cập nhật đủ
        if d.isoformat() not in done or (end_d - d).days < 3:
            days.append(d)
        d += timedelta(days=1)

    new_rows, n_ok = [], 0
    s = requests.Session()
    s.headers.update(HTTP_HEADERS)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_fetch_giavang_day, day, s) for day in days]
        for i, f in enumerate(as_completed(futs), 1):
            day, rows = f.result()
            if rows is None:
                continue
            done.add(day.isoformat())
            for r in rows:
                r["page_date"] = day.isoformat()
            new_rows.extend(rows)
            n_ok += 1
            if verbose and i % 200 == 0:
                print(f"  giavang.org: {i}/{len(days)} trang")
                pd.concat([ticks, pd.DataFrame(new_rows)]).drop_duplicates(
                    ["ts", "type"]).to_csv(cache, index=False)
                done_file.write_text("\n".join(sorted(done)))
    ticks = pd.concat([ticks, pd.DataFrame(new_rows)], ignore_index=True)
    ticks["ts"] = pd.to_datetime(ticks["ts"])
    # sắp xếp ỔN ĐỊNH: các dòng cùng giờ giữ nguyên thứ tự cũ -> file không bị xáo trộn (diff git nhỏ) mỗi lần chạy
    ticks = ticks.drop_duplicates(["ts", "type"]).sort_values("ts", kind="stable")
    ticks.to_csv(cache, index=False)
    done_file.write_text("\n".join(sorted(done)))
    if verbose:
        print(f"  giavang.org: tải {n_ok} trang mới, tổng {len(ticks)} bản ghi")
    return ticks


def giavang_daily(ticks: pd.DataFrame) -> pd.DataFrame:
    """Giá cuối ngày (bản cập nhật muộn nhất) cho SJC miếng và nhẫn SJC 99,99."""
    t = ticks.copy()
    t["date"] = t["ts"].dt.normalize()
    is_bar = t["type"].str.contains("SJC 1L", case=False)
    is_ring = t["type"].str.contains("nhẫn", case=False) & t["type"].str.contains("1 chỉ")
    bar = t[is_bar].sort_values("ts").groupby("date")[["buy", "sell"]].last()
    ring = t[is_ring].sort_values("ts").groupby("date")[["buy", "sell"]].last()
    out = bar.add_prefix("sjc_").join(ring.add_prefix("ring_"), how="outer")
    out["source"] = "giavang.org"
    return out


def parse_giavang_pnj_page(html: str) -> list[dict]:
    """Trang PNJ: các dòng 'SJC' (vàng miếng SJC bán tại PNJ) và 'PNJ' (nhẫn trơn 999.9), lấy khu vực TPHCM."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for table in soup.find_all("table"):
        region = None
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            prices = [c for c in cells if _PRICE.match(c)]
            times = [m for c in cells for m in _TIME.findall(c)]
            texts = [c for c in cells if not _PRICE.match(c) and not _TIME.search(c)]
            if len(texts) >= 2:
                region = texts[0]
            if region and region.upper().replace(" ", "") in ("TPHCM", "HỒCHÍMINH") \
                    and len(prices) >= 2 and times and texts:
                kind = texts[-1].upper()
                if kind in ("SJC", "PNJ"):
                    hh, dmy = times[0]
                    rows.append({
                        "ts": pd.to_datetime(f"{dmy} {hh}", format="%d/%m/%Y %H:%M:%S"),
                        "type": "PNJ-SJC" if kind == "SJC" else "PNJ-nhẫn",
                        "buy": _to_million(prices[0]), "sell": _to_million(prices[1]),
                    })
    return rows


def fetch_gap_from_pnj(start: str = "2024-10-25", end: str = "2025-02-15") -> pd.DataFrame:
    """Lấp khoảng trống dữ liệu SJC (11/2024 - 02/2025) bằng giá SJC niêm yết tại PNJ."""
    cache = DATA_RAW / "giavang_org_pnj_gap.csv"
    if cache.exists():
        return pd.read_csv(cache, parse_dates=["ts"])
    s = requests.Session()
    s.headers.update(HTTP_HEADERS)
    days = pd.date_range(start, end).date
    rows = []

    def one(d):
        url = f"https://giavang.org/trong-nuoc/pnj/lich-su/{d:%Y-%m-%d}.html"
        for attempt in range(3):
            try:
                r = s.get(url, timeout=40)
                if r.status_code == 200:
                    return parse_giavang_pnj_page(r.text)
            except requests.RequestException:
                time.sleep(1.5 * (attempt + 1))
        return []

    with ThreadPoolExecutor(max_workers=6) as ex:
        for res in ex.map(one, days):
            rows.extend(res)
    out = pd.DataFrame(rows).drop_duplicates(["ts", "type"]).sort_values("ts")
    out.to_csv(cache, index=False)
    return out


def pnj_daily(ticks: pd.DataFrame) -> pd.DataFrame:
    t = ticks.copy()
    t["date"] = t["ts"].dt.normalize()
    bar = t[t["type"] == "PNJ-SJC"].sort_values("ts").groupby("date")[["buy", "sell"]].last()
    ring = t[t["type"] == "PNJ-nhẫn"].sort_values("ts").groupby("date")[["buy", "sell"]].last()
    out = bar.add_prefix("sjc_").join(ring.add_prefix("ring_"), how="outer")
    out["source"] = "giavang.org/pnj"
    return out


def collect_all(scrape_start: str = START_DATE) -> dict[str, pd.DataFrame]:
    print("[1/4] Yahoo Finance ...")
    yahoo = fetch_yahoo()
    print("[2/4] FRED ...")
    fred = fetch_fred()
    print("[3/4] CafeF ...")
    cafef = fetch_cafef()
    print("[4/4] giavang.org (có cache) ...")
    ticks = fetch_giavang_org(scrape_start, end="2025-03-31")  # sau 03/2025 dùng CafeF
    gap = fetch_gap_from_pnj()
    return {"yahoo": yahoo, "fred": fred, "cafef": cafef,
            "giavang": giavang_daily(ticks), "pnj": pnj_daily(gap)}
