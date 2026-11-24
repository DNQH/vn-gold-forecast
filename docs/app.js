"use strict";
/* Ứng dụng giá vàng (PWA) – thuần JavaScript, không thư viện ngoài. Nội dung và lời lẽ theo trang "Dễ hiểu" của bản Streamlit. */
(function () {
  var WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"];
  var CONF = {strong: ["●●●○", "Nghiêng rõ về {dir}"], lean: ["●●○○", "Hơi nghiêng về {dir}"],
              unclear: ["●○○○", "Không rõ ràng"], none: ["○○○○", "Chưa đoán được chiều"]};
  var COL = {up: "#15803d", down: "#b91c1c", flat: "#6b7280", gold: "#b7791f"};
  var VN_TZ = "Asia/Ho_Chi_Minh";
  var REFRESH_MS = 5 * 60 * 1000;

  var state = {data: null, live: {}, liveFailed: false, fromCache: false, target: "sjc_sell", loadFailed: false};
  var $ = function (id) { return document.getElementById(id); };

  // ---------- lưu trữ an toàn
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* bỏ qua */ } }

  // ---------- định dạng
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]; }); }
  function vn(v, d) {
    if (v === null || v === undefined || isNaN(v)) return "–";
    d = d === undefined ? 1 : d;
    var neg = v < 0, s = Math.abs(v).toFixed(d), p = s.split("."), i = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return (neg ? "-" : "") + i + (p[1] ? "," + p[1] : "");
  }
  function ten(x) { return Math.round(x * 10); }
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  // ngày dạng 'YYYY-MM-DD' <-> Date UTC (nửa đêm)
  function pd(s) { var a = String(s).slice(0, 10).split("-"); return new Date(Date.UTC(+a[0], +a[1] - 1, +a[2])); }
  function iso(d) { return d.getUTCFullYear() + "-" + pad(d.getUTCMonth() + 1) + "-" + pad(d.getUTCDate()); }
  function wd(d) { return (d.getUTCDay() + 6) % 7; } // 0 = Thứ Hai
  function ddmm(s) { var d = pd(s); return pad(d.getUTCDate()) + "/" + pad(d.getUTCMonth() + 1); }
  function ddmmyyyy(s) { return ddmm(s) + "/" + pd(s).getUTCFullYear(); }
  function vnDate(s, weekday) { return (weekday === false ? "" : WEEKDAYS[wd(pd(s))] + ", ") + ddmmyyyy(s); }

  // giờ Việt Nam hiện tại; thêm ?now=YYYY-MM-DD+HH:MM vào địa chỉ để thử nghiệm
  function vnNow() {
    var m = /[?&]now=(\d{4}-\d{2}-\d{2})[ +T](\d{2}):(\d{2})/.exec(location.search);
    if (m) return {date: m[1], h: +m[2], m: +m[3]};
    var parts = {};
    new Intl.DateTimeFormat("en-GB", {timeZone: VN_TZ, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23"}).formatToParts(new Date()).forEach(function (p) { parts[p.type] = p.value; });
    return {date: parts.year + "-" + parts.month + "-" + parts.day, h: +parts.hour, m: +parts.minute};
  }
  function whenLabel(target, today) {
    var d = Math.round((pd(target) - pd(today)) / 864e5);
    if (d === 0) return "Cuối ngày hôm nay";
    if (d === 1) return "Ngày mai";
    return WEEKDAYS[wd(pd(target))] + " " + ddmm(target);
  }

  // ---------- độ mới của dữ liệu (cổng của freshness() trong src/vngold/plain.py)
  // ngày làm việc (T2–T6) gần nhất NHỎ HƠN d: T7, CN, T2 -> thứ Sáu trước đó
  function prevBday(d) {
    d = new Date(d.getTime());
    do { d.setUTCDate(d.getUTCDate() - 1); } while (wd(d) >= 5);
    return d;
  }
  function freshness(asOf, now) {
    var expected = prevBday(pd(now.date)), w = wd(pd(now.date));
    if (w >= 1 && w <= 5 && (now.h * 60 + now.m) < 7 * 60 + 30) expected = prevBday(expected);
    return {stale: pd(asOf) < expected, expected: iso(expected)};
  }

  // ---------- giá niêm yết trực tiếp từ CafeF
  function fetchJSON(url, ms) {
    var ctl = new AbortController(), t = setTimeout(function () { ctl.abort(); }, ms || 10000);
    return fetch(url, {signal: ctl.signal, cache: "no-store"}).then(function (r) {
      clearTimeout(t); if (!r.ok) throw new Error(r.status); return r.json();
    }, function (e) { clearTimeout(t); throw e; });
  }
  function maxBy(arr, k) { return arr.reduce(function (a, b) { return String(b[k]) > String(a[k]) ? b : a; }); }
  function vnParts(d) {
    var o = {};
    new Intl.DateTimeFormat("en-GB", {timeZone: VN_TZ, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23"}).formatToParts(d).forEach(function (p) { o[p.type] = p.value; });
    return {date: o.year + "-" + o.month + "-" + o.day, time: o.hour + ":" + o.minute};
  }
  function fetchLive() {
    var live = {}, ok = 0;
    var sjc = fetchJSON("https://cafef.vn/du-lieu/Ajax/ajaxgoldpricehistory.ashx?index=1W").then(function (j) {
      var h = maxBy(j.Data.goldPriceWorldHistories, "createdAt"), p = vnParts(new Date(h.createdAt));
      if (!isFinite(h.sellPrice)) throw new Error("bad");
      live.sjc_sell = {price: +h.sellPrice, buy: +h.buyPrice, date: p.date, time: p.time}; ok++;
    }).catch(function () {});
    var ring = fetchJSON("https://cafef.vn/du-lieu/Ajax/AjaxGoldPriceRing.ashx?time=1w&zone=11").then(function (j) {
      var h = maxBy(j.Data.goldPriceWorldHistories, "lastUpdated"), m = /(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})/.exec(h.lastUpdated);
      if (!m || !isFinite(h.sellPrice)) throw new Error("bad");
      live.ring_sell = {price: h.sellPrice / 100, buy: h.buyPrice / 100, date: m[1], time: m[2]}; ok++;
    }).catch(function () {});
    return Promise.all([sjc, ring]).then(function () {
      state.live = live; state.liveFailed = ok === 0; render();
    });
  }

  // ---------- tải latest.json
  function loadData() {
    return fetch("data/latest.json?t=" + Date.now(), {cache: "no-store"}).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      state.fromCache = r.headers.get("X-From-Cache") === "1";
      return r.json();
    }).then(function (d) { state.data = d; state.loadFailed = false; render(); }, function () {
      state.loadFailed = true; render();
    });
  }
  function refreshAll() {
    var b = $("refresh"); b.disabled = true; b.textContent = "⏳ Đang tải…";
    return Promise.all([loadData(), fetchLive()]).then(function () {
      b.disabled = false; b.textContent = "🔄 Cập nhật";
    });
  }

  // ---------- thẻ dự báo
  function shortCard(T, h, r, ctx) {
    var date = vnDate(r.target_date), when = whenLabel(r.target_date, ctx.today.date);
    if (pd(r.target_date) < pd(ctx.today.date)) {
      return '<div class="card past"><div class="when">' + esc(when) + '</div><div class="date">' + esc(date) + '</div>' +
        '<div class="icon">⏳</div><div class="sub" style="font-size:1rem">Đã qua ngày dự đoán (' + ddmmyyyy(r.target_date) +
        ') – chờ bản cập nhật mới</div></div>';
    }
    if (h === "5") when = "Khoảng 1 tuần nữa"; else if (h === "21") when = "Khoảng 1 tháng nữa";
    var rng = 'Nhiều khả năng trong khoảng<br><b>' + vn(r.lo80) + " – " + vn(r.hi80) + "</b> triệu";
    if (!r.has_edge) {
      return '<div class="card" style="border-top:6px solid ' + COL.flat + '"><div class="when">' + esc(when) + '</div><div class="date">' + esc(date) + '</div>' +
        '<div class="icon flat">?</div><div class="verdict flat">Khó đoán</div>' +
        '<div class="sub">Ở mốc này, phần mềm chưa đoán tăng/giảm tốt hơn việc coi như giá giữ nguyên.</div>' +
        '<div class="range">' + rng + '</div><div class="conf flat">' + CONF.none[0] + " " + CONF.none[1] + "</div></div>";
    }
    var b = r.bucket, upSide = b === "strong_up" || b === "lean_up", downSide = b === "strong_down" || b === "lean_down";
    var color = upSide ? COL.up : downSide ? COL.down : COL.flat;
    var icon = upSide ? "▲" : downSide ? "▼" : "●";
    var verdict = upSide ? "Có thể TĂNG" : downSide ? "Có thể GIẢM" : "Có thể đi ngang";
    var level = b.indexOf("strong") === 0 ? "strong" : (upSide || downSide) ? "lean" : "unclear";
    var d = r.pred_price - T.last_price, extra = "", closeTxt = "giá chốt gần nhất";
    if (upSide || downSide) {
      var cd = T.last_close.date;
      closeTxt = "giá chốt " + WEEKDAYS[wd(pd(cd))] + " " + ddmm(cd);
      if (h === "1") {
        if (ctx.useLive && ctx.lp.date === r.target_date)
          extra += '<div class="live">Giá đang niêm yết: <b>' + vn(ctx.lp.price) + "</b> triệu</div>";
        if (Math.abs(d) < T.last_close.spread)
          extra += '<div class="warn">Mức thay đổi này (' + vn(Math.abs(d)) + " triệu) nhỏ hơn chênh lệch mua–bán (" +
            vn(T.last_close.spread) + " triệu): không đáng mua bán chỉ vì dự đoán này.</div>";
      }
    }
    var move = Math.abs(d) >= 0.05 ? (d > 0 ? "tăng" : "giảm") + " khoảng " + vn(Math.abs(d)) + " triệu" : "gần như không đổi";
    var hist = "";
    if (r.hit && (upSide || downSide))
      hist = '<div class="hist">Những lần trước phần mềm nói “' + (upSide ? "tăng" : "giảm") + '” như vậy:<br>đúng <b>' + ten(r.hit.rate) + "/10</b> lần</div>";
    return '<div class="card" style="border-top:6px solid ' + color + '"><div class="when">' + esc(when) + '</div><div class="date">' + esc(date) + '</div>' +
      '<div class="icon" style="color:' + color + '">' + icon + '</div><div class="verdict" style="color:' + color + '">' + verdict + '</div>' +
      '<div class="main">khoảng <b>' + vn(r.pred_price) + '</b> triệu</div><div class="sub">' + move + " so với " + esc(closeTxt) + "</div>" + extra +
      '<div class="range">' + rng + '</div><div class="conf" style="color:' + color + '">' + CONF[level][0] + " " +
      CONF[level][1].replace("{dir}", upSide ? "tăng" : "giảm") + "</div>" + hist + "</div>";
  }
  function longCard(o) {
    var d = pd(o.target_date);
    return '<div class="card" style="border-top:6px solid ' + COL.gold + '"><div class="when">Khoảng ' + esc(o.label) + ' nữa</div>' +
      '<div class="date">tháng ' + pad(d.getUTCMonth() + 1) + "/" + d.getUTCFullYear() + '</div>' +
      '<div class="icon gold">↕</div><div class="verdict gold">Không ai đoán chắc</div>' +
      '<div class="sub">Xa như vậy, giá có thể lên hoặc xuống rất nhiều. Phần mềm chỉ ước lượng khoảng giá.</div>' +
      '<div class="range">Phần lớn trường hợp trong khoảng<br><b>' + vn(o.lo, 0) + " – " + vn(o.hi, 0) + '</b> triệu</div>' +
      '<div class="conf gold">' + CONF.none[0] + " Chỉ để tham khảo</div></div>";
  }

  // ---------- biểu đồ SVG
  function chartSVG(T) {
    var W = 340, H = 230, L = 40, R = 10, Tp = 12, B = 26;
    var hist = T.history.map(function (p) { return {t: pd(p.date).getTime(), v: p.sell}; });
    var last = hist[hist.length - 1], pts = [{t: last.t, lo: last.v, hi: last.v, mid: last.v}];
    ["1", "5", "21"].forEach(function (h) {
      var r = T.horizons[h]; if (r) pts.push({t: pd(r.target_date).getTime(), lo: r.lo80, hi: r.hi80, mid: r.pred_price});
    });
    var vals = hist.map(function (p) { return p.v; }).concat(pts.map(function (p) { return p.lo; }), pts.map(function (p) { return p.hi; }));
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), pad_ = (hi - lo) * 0.06 || 1;
    lo -= pad_; hi += pad_;
    var t0 = hist[0].t, t1 = pts[pts.length - 1].t;
    var X = function (t) { return L + (t - t0) / (t1 - t0 || 1) * (W - L - R); };
    var Y = function (v) { return Tp + (hi - v) / (hi - lo) * (H - Tp - B); };
    var f = function (n) { return n.toFixed(1); };
    var svg = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Biểu đồ giá 3 tháng qua và dự đoán 1 tháng tới" font-family="inherit">';
    var dec = (hi - lo) > 8 ? 0 : 1;
    for (var i = 0; i < 5; i++) {
      var v = lo + (hi - lo) * i / 4, y = Y(v);
      svg += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + f(y) + '" y2="' + f(y) + '" stroke="#eef0f3"/>' +
        '<text x="' + (L - 5) + '" y="' + f(y + 4) + '" text-anchor="end" font-size="12" fill="#6b7280">' + vn(v, dec) + "</text>";
    }
    var nx = 4;
    for (var k = 0; k <= nx; k++) {
      var tt = t0 + (t1 - t0) * k / nx, dd = new Date(tt), x = X(tt);
      svg += '<text x="' + f(x) + '" y="' + (H - 7) + '" text-anchor="' + (k === 0 ? "start" : k === nx ? "end" : "middle") +
        '" font-size="12" fill="#6b7280">' + pad(dd.getUTCDate()) + "/" + pad(dd.getUTCMonth() + 1) + "</text>";
    }
    var band = pts.map(function (p) { return f(X(p.t)) + "," + f(Y(p.hi)); }).concat(pts.slice().reverse().map(function (p) { return f(X(p.t)) + "," + f(Y(p.lo)); }));
    svg += '<polygon points="' + band.join(" ") + '" fill="rgba(183,121,31,0.2)"/>';
    svg += '<polyline fill="none" stroke="#1f2937" stroke-width="2.6" stroke-linejoin="round" points="' +
      hist.map(function (p) { return f(X(p.t)) + "," + f(Y(p.v)); }).join(" ") + '"/>';
    svg += '<polyline fill="none" stroke="#b7791f" stroke-width="2.6" stroke-dasharray="2 6" stroke-linecap="round" points="' +
      pts.map(function (p) { return f(X(p.t)) + "," + f(Y(p.mid)); }).join(" ") + '"/>';
    pts.slice(1).forEach(function (p) { svg += '<circle cx="' + f(X(p.t)) + '" cy="' + f(Y(p.mid)) + '" r="4.5" fill="#b7791f" stroke="#fff" stroke-width="1.5"/>'; });
    svg += '<circle cx="' + f(X(last.t)) + '" cy="' + f(Y(last.v)) + '" r="4" fill="#1f2937"/></svg>';
    return svg;
  }

  // ---------- dựng trang
  function render() {
    var D = state.data, c = $("content"), notes = [];
    if (!D) {
      c.innerHTML = state.loadFailed ? '<div class="banner">Không tải được dữ liệu. Hãy kiểm tra mạng rồi bấm “Cập nhật”.</div>' :
        '<p class="muted">Đang tải dữ liệu…</p>';
      return;
    }
    var T = D.targets[state.target] || D.targets.sjc_sell, tkey = D.targets[state.target] ? state.target : "sjc_sell";
    var now = vnNow(), today = now, fr = freshness(D.as_of, now);
    var gen = String(D.generated_at);
    $("updated").innerHTML = "Phần mềm tự cập nhật mỗi sáng. Lần cập nhật gần nhất: <b>" + esc(gen.slice(11, 16)) + ", " + vnDate(gen.slice(0, 10)) + "</b>";
    $("foot-update").textContent = "Dữ liệu cập nhật lúc " + gen.slice(11, 16) + " ngày " + ddmmyyyy(gen.slice(0, 10)) + ". Giá niêm yết làm mới mỗi 5 phút.";

    if (fr.stale || T.source_stale) {
      var stop = T.source_stale && !fr.stale ? T.last_observed : D.as_of;
      notes.push('<div class="banner">⚠️ Chưa có số liệu mới – số liệu dừng ở ' + vnDate(stop) +
        " (có thể do ngày nghỉ lễ, Tết hoặc lỗi cập nhật). Đừng dựa vào phần dự đoán bên dưới cho tới khi có số liệu mới.</div>");
    }
    if (state.fromCache || state.loadFailed) notes.push('<div class="info">📴 Đang xem dữ liệu đã lưu trên máy (chưa có mạng hoặc chưa tải được bản mới).</div>');
    if (state.liveFailed) notes.push('<div class="info">Chưa lấy được giá đang niêm yết – đang hiện giá chốt gần nhất.</div>');
    $("notes").innerHTML = notes.join("");

    var lc = T.last_close, lp = state.live[tkey];
    var useLive = !!lp && lp.date >= lc.date;
    var sell, buy, ref, refTxt, timeTxt;
    if (useLive) {
      sell = lp.price; buy = lp.buy; ref = lc.sell; refTxt = "giá chốt " + vnDate(lc.date);
      timeTxt = "Giá đang niêm yết lúc " + lp.time + " " + vnDate(lp.date) + " (nguồn CafeF)";
    } else {
      sell = lc.sell; buy = lc.buy; ref = T.prev_close; refTxt = "phiên trước"; timeTxt = "Giá chốt phiên " + vnDate(lc.date);
    }
    var chg = sell - ref;
    var chgHtml = (chg > 0.05 ? '<span class="up">▲ Tăng ' + vn(chg) + " triệu</span>" :
      chg < -0.05 ? '<span class="down">▼ Giảm ' + vn(-chg) + " triệu</span>" : '<span class="flat">● Không đổi</span>') +
      ' <span class="muted">so với ' + esc(refTxt) + "</span>";
    var spread = sell - buy;
    var ctx = {today: today, useLive: useLive, lp: lp};

    var h = '<section class="hero"><div><div class="lbl">Giá BÁN ra (tiệm bán cho mình)</div><div class="big">' + vn(sell) +
      ' <span class="unit">triệu đồng / lượng</span></div><div class="chg">' + chgHtml + "</div></div>" +
      '<div><div class="lbl">Giá MUA vào (tiệm mua lại của mình)</div><div class="big s">' + vn(buy) +
      ' <span class="unit">triệu đồng / lượng</span></div><div class="when-note">' + esc(timeTxt) + "</div></div></section>";
    if (tkey === "ring_sell")
      h += '<p class="cap">Giá vàng nhẫn ở đây là giá <b>nhẫn trơn 999.9 của PNJ</b>. Tiệm khác (SJC, DOJI, Bảo Tín…) có thể chênh lệch vài trăm nghìn – khi so, hãy so với bảng giá PNJ.</p>';

    h += "<h2>Giá vàng sắp tới sẽ thế nào?</h2><div class=\"muted\">Tính từ giá chốt <b>" + vnDate(lc.date) + "</b>: <b>" + vn(T.last_price) +
      "</b> triệu/lượng (giá bán ra).</div>";
    var near = ["1", "5", "21"].filter(function (k) { return T.horizons[k]; }).map(function (k) { return shortCard(T, k, T.horizons[k], ctx); });
    var far = ["63", "105"].filter(function (k) { return T.outlook[k]; }).map(function (k) { return longCard(T.outlook[k]); });
    h += '<div class="group">Trong tháng tới</div><div class="grid">' + near.join("") + "</div>" +
      '<div class="group">Xa hơn: 3 – 5 tháng</div><div class="grid two">' + far.join("") + "</div>";
    h += '<p class="cap">“Nhiều khả năng trong khoảng” = khoảng mà trước đây giá thật rơi vào khoảng 8 trên 10 lần. Ngày tính theo ngày làm việc (Thứ Hai – Thứ Sáu).</p>';
    h += '<div class="note">💡 <b>Chênh lệch giữa giá bán và giá mua hiện là ' + vn(spread) + " triệu/lượng.</b><br>" +
      "Nghĩa là nếu mua 1 lượng hôm nay rồi bán lại ngay, mình sẽ mất khoảng <b>" + vn(spread) + " triệu</b>. " +
      "Giá cần tăng hơn mức này thì mới có lời – nên vàng hợp để giữ lâu hơn là mua bán theo từng ngày.</div>";

    h += "<h2>Giá 3 tháng qua và dự đoán 1 tháng tới</h2><div class=\"chart\">" + chartSVG(T) + "</div>" +
      '<div class="legend"><span><i style="border-color:#1f2937"></i>Giá đã qua</span><span><i style="border-color:#b7791f;border-top-style:dotted"></i>Dự đoán</span>' +
      '<span><i class="band"></i>Khoảng giá nhiều khả năng</span></div>';

    if (T.reasons && T.reasons.length) {
      h += "<h2>Vì sao phần mềm nghĩ như vậy?</h2><div class=\"muted\">Những điều chính phần mềm đang dựa vào để đoán giá phiên kế tiếp:</div><div style=\"margin-top:8px\">";
      T.reasons.forEach(function (r) {
        h += '<div class="reason"><b class="' + (r.up ? "up" : "down") + '">' + (r.up ? "⬆ đẩy giá lên" : "⬇ kéo giá xuống") + "</b> &nbsp;·&nbsp; " + esc(r.text) + "</div>";
      });
      h += "</div>";
    }

    h += "<h2>Phần mềm đoán có đúng không?</h2>";
    if (T.track && T.track.length) {
      var s = T.stats;
      h += "<p>Nhìn lại <b>" + T.track.length + " lần đoán “phiên kế tiếp” gần nhất</b>, mỗi chấm là một lần:</p><div class=\"dots\">" +
        T.track.map(function (r) {
          return '<div class="dot" title="' + ddmm(r.target_date) + '" style="background:' + (r.dir_ok === 1 ? COL.up : r.dir_ok === 0 ? COL.down : "#d1d5db") + '"></div>';
        }).join("") + "</div>" +
        '<div class="cap"><span class="up">●</span> đoán đúng tăng/giảm &nbsp; <span class="down">●</span> đoán sai &nbsp; <span style="color:#9ca3af">●</span> giá đứng yên (không tính)</div>';
      if (s.n_dir) h += '<div class="stat">Đoán đúng tăng hay giảm: <b>' + s.n_ok + "/" + s.n_dir + "</b> lần</div>";
      h += '<div class="stat">Lệch trung bình: <b>' + vn(s.mae) + " triệu</b> mỗi lượng (khoảng " + vn(s.mape) + "% giá)</div>";
      if (s.inband_n) h += '<div class="stat">Giá thật nằm trong khoảng “nhiều khả năng”: <b>' + s.inband_ok + "/" + s.inband_n + "</b> lần</div>";
      h += '<p class="cap">Mỗi lần đoán chỉ dùng thông tin có trước ngày đó, giống hệt như khi phần mềm chạy thật mỗi sáng.</p>';
    }

    h += "<h2>Điều nên biết trước khi mua bán</h2>" +
      '<div class="note">⚠️ Đây là <b>dự đoán để tham khảo</b>, dựa trên số liệu trong quá khứ – <b>không phải lời khuyên mua hay bán</b>. Giá vàng có thể thay đổi bất ngờ vì tin tức trong nước và thế giới.</div>';
    h += '<details><summary>❓ Câu hỏi thường gặp</summary>' +
      "<p><b>Phần mềm lấy giá ở đâu?</b> Giá vàng trong nước lấy từ CafeF và giavang.org: vàng miếng là giá niêm yết của công ty SJC, vàng nhẫn là giá <b>nhẫn trơn 999.9 của PNJ</b>. Giá vàng thế giới, tỷ giá đô la lấy từ Yahoo Finance và Cục Dự trữ Liên bang Mỹ (FRED).</p>" +
      "<p><b>Bao lâu cập nhật một lần?</b> Mỗi sáng khoảng 7 giờ (Thứ Ba – Thứ Bảy), sau khi thị trường Mỹ đóng cửa đêm trước. Giá đang niêm yết trên trang này được làm mới mỗi 5 phút.</p>" +
      "<p><b>Vì sao “1 tuần” và “1 tháng” lại ghi “Khó đoán”?</b> Vì khi kiểm tra trên nhiều năm dữ liệu, phần mềm đoán chiều tăng/giảm ở các mốc này không tốt hơn việc coi như giá giữ nguyên. Thay vì đoán bừa, phần mềm nói thật là chưa đoán được và chỉ cho biết khoảng giá có thể xảy ra.</p>" +
      "<p><b>Vì sao 3 tháng, 5 tháng khoảng giá lại rộng như vậy?</b> Giá vàng mấy năm qua lên xuống rất mạnh (có năm tăng hơn 50%). Khoảng rộng là cách trung thực để nói: xa như vậy thì không ai biết chắc.</p></details>";
    c.innerHTML = h;
  }

  // ---------- chọn loại vàng
  function setTarget(t) {
    state.target = t; lsSet("vg_target", t);
    Array.prototype.forEach.call(document.querySelectorAll(".seg button"), function (b) { b.setAttribute("aria-selected", b.dataset.t === t ? "true" : "false"); });
    render();
  }

  // ---------- gợi ý cài đặt
  var deferred = null;
  function standalone() {
    return (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone === true;
  }
  function renderInstall() {
    var el = $("install");
    if (standalone()) { el.hidden = true; return; }
    var ua = navigator.userAgent || "", ios = /iPhone|iPad|iPod/.test(ua), android = /Android/.test(ua);
    var dismissed = lsGet("vg_install_dismissed") === "1";
    var html = "";
    if (deferred) {
      html = '<b>Cài vào điện thoại để mở nhanh bằng một chạm.</b><div class="row"><button class="btn primary" id="do-install" type="button">Cài vào điện thoại</button>' +
        '<button class="btn" id="hide-install" type="button">Để sau</button></div>';
    } else if (!dismissed && (ios || android)) {
      html = ios ? "📲 <b>Cài vào màn hình chính:</b> bấm nút <b>Chia sẻ</b> (hình ô vuông có mũi tên) → <b>Thêm vào MH chính</b>."
                 : "📲 <b>Cài vào màn hình chính:</b> bấm <b>⋮</b> → <b>Thêm vào màn hình chính</b>.";
      html += '<div class="row"><button class="btn" id="hide-install" type="button">Đã hiểu, ẩn đi</button></div>';
    }
    if (dismissed && !deferred) html = "";
    if (dismissed && deferred) html = "";
    el.innerHTML = html; el.hidden = !html;
    var hb = $("hide-install"); if (hb) hb.onclick = function () { lsSet("vg_install_dismissed", "1"); renderInstall(); };
    var ib = $("do-install");
    if (ib) ib.onclick = function () {
      var p = deferred; deferred = null; p.prompt();
      p.userChoice.then(function () { renderInstall(); }, function () { renderInstall(); });
    };
  }
  window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); deferred = e; renderInstall(); });
  window.addEventListener("appinstalled", function () { deferred = null; renderInstall(); });

  // ---------- khởi động
  function init() {
    var saved = lsGet("vg_target");
    if (saved === "sjc_sell" || saved === "ring_sell") state.target = saved;
    Array.prototype.forEach.call(document.querySelectorAll(".seg button"), function (b) {
      b.setAttribute("aria-selected", b.dataset.t === state.target ? "true" : "false");
      b.onclick = function () { setTarget(b.dataset.t); };
    });
    $("refresh").onclick = refreshAll;
    renderInstall();
    loadData(); fetchLive();
    setInterval(function () { if (document.visibilityState === "visible") fetchLive(); }, REFRESH_MS);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "visible") { fetchLive(); render(); }
    });
    if ("serviceWorker" in navigator) {
      // Khi có bản ứng dụng mới (sw.js đổi), service worker mới tự kích hoạt -> tải lại trang một lần để dùng bản mới.
      // Lần cài đầu tiên (chưa có controller) thì không tải lại.
      var hadController = !!navigator.serviceWorker.controller, reloading = false;
      navigator.serviceWorker.addEventListener("controllerchange", function () {
        if (!hadController || reloading) return;
        reloading = true; location.reload();
      });
      window.addEventListener("load", function () {
        navigator.serviceWorker.register("sw.js", {scope: "./", updateViaCache: "none"}).then(function (reg) {
          // điện thoại để app mở lâu ngày: kiểm tra bản mới mỗi khi quay lại app
          document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") reg.update().catch(function () {}); });
        }).catch(function () {});
      });
    }
  }
  init();
})();
