#!/usr/bin/env python3
# CANSLIM Scanner - GitHub Actions version
import os, sys

# Install dependencies
import subprocess
subprocess.run([sys.executable, "-m", "pip", "install", "yfinance", "-q"], 
               capture_output=True)

# -*- coding: utf-8 -*-
# CANSLIM Scanner v2 - Temiz versiyon

# KURULUM
import yfinance as yf
import json, base64, urllib.request
from datetime import datetime

# ── AYARLAR ───────────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get('SCANNER_TOKEN', '')
if not GITHUB_TOKEN:
    GITHUB_TOKEN = os.environ.get('GH_TOKEN', '')
print(f'Token: {GITHUB_TOKEN[:8]}...' if GITHUB_TOKEN else 'Token: BOŞ!')
GITHUB_USER  = 'ghurzzz'
GITHUB_REPO  = 'canslim'
GITHUB_FILE  = 'index.html'
FINNHUB_KEY  = os.environ.get('FINNHUB_KEY', 'd7r51k9r01qtpsm132igd7r51k9r01qtpsm132j0')

# Varsayilan liste — config.json varsa oradan okunur
_DEFAULT_WATCHLIST = [
    'MU','NVDA','AMD','MRVL','ALAB','AVGO','TSM','CRDO',
    'CLS','ARM','ANET','LRCX','POWL','WDC','FN','AMAT','ADI'
]
_DEFAULT_PORTFOLIO = ['MRVL','AMD','CLS','ANET','AVGO','MU','NVDA','ARM']

# config.json'dan oku (siteden duzenlendiyse)
import urllib.request as _ur2, json as _js2
try:
    _cfg_url = f'https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/config.json'
    with _ur2.urlopen(_cfg_url, timeout=5) as _r2:
        _cfg = _js2.loads(_r2.read())
    WATCHLIST = _cfg.get('watchlist', _DEFAULT_WATCHLIST)
    PORTFOLIO = _cfg.get('portfolio', _DEFAULT_PORTFOLIO)
    print(f'config.json okundu: {len(WATCHLIST)} hisse, {len(PORTFOLIO)} portfolyo')
except Exception as _e2:
    WATCHLIST = _DEFAULT_WATCHLIST
    PORTFOLIO = _DEFAULT_PORTFOLIO
    print('config.json bulunamadi, varsayilan liste kullaniliyor')

TF_CONFIG = {
    '1d':  {'period': '1y',  'interval': '1d',  'label': '1 Gun'},
    '1wk': {'period': '2y',  'interval': '1wk', 'label': '1 Hafta'},
    '1mo': {'period': '5y',  'interval': '1mo', 'label': '1 Ay'},
}

# ── ANALİZ ────────────────────────────────────────────────────
def analyze(ticker, period='1y', interval='1d'):
    try:
        tk   = yf.Ticker(ticker)
        hist = tk.history(period=period, interval=interval)
        info = {}
        try:
            info = tk.info or {}
        except: pass

        if hist.empty:
            return {'ticker': ticker, 'hata': 'Veri yok'}

        closes  = hist['Close'].dropna()
        volumes = hist['Volume'].dropna()
        price   = float(closes.iloc[-1])
        prev    = float(closes.iloc[-2]) if len(closes) > 1 else price
        change  = round((price - prev) / prev * 100, 2)

        # ── SMA ──────────────────────────────────────────────
        sma10  = float(closes.tail(10).mean())  if len(closes) >= 10  else None
        sma20  = float(closes.tail(20).mean())  if len(closes) >= 20  else None
        sma50  = float(closes.tail(50).mean())  if len(closes) >= 50  else None
        sma200 = float(closes.tail(200).mean()) if len(closes) >= 200 else None
        above50  = price > sma50  if sma50  else False
        above200 = price > sma200 if sma200 else False
        sma50_dist  = round((price - sma50)  / sma50  * 100, 1) if sma50  else None
        sma200_dist = round((price - sma200) / sma200 * 100, 1) if sma200 else None

        # ── 52W ──────────────────────────────────────────────
        high52w      = float(closes.max())
        low52w       = float(closes.min())
        pct_from_52w = round((high52w - price) / high52w * 100, 1)
        near_52w     = pct_from_52w <= 15
        w52_position = round((price - low52w) / (high52w - low52w) * 100, 1) if high52w != low52w else 50

        # ── Momentum Tespiti ──────────────────────────────────
        # Son 6 ayda fiyat ne kadar yükseldi?
        price_6m_ago = float(closes.iloc[-126]) if len(closes) >= 126 else float(closes.iloc[0])
        gain_6m = round((price - price_6m_ago) / price_6m_ago * 100, 1)
        is_momentum = gain_6m >= 40  # 6 ayda %40+ yükseldiyse momentum hissesi

        # ── Hacim ─────────────────────────────────────────────
        avg_vol   = float(volumes.tail(20).mean()) if len(volumes) >= 20 else float(volumes.mean())
        last_vol  = float(volumes.iloc[-1])
        vol_ratio = round(last_vol / avg_vol, 2) if avg_vol else 1
        if   last_vol > avg_vol * 1.3: vol_label = 'Yuksek'
        elif last_vol < avg_vol * 0.7: vol_label = 'Dusuk'
        else:                          vol_label = 'Normal'

        # ── RSI (14) ──────────────────────────────────────────
        rsi = None
        try:
            delta = closes.diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean()
            rs    = gain / loss
            rsi   = round(float((100 - (100 / (1 + rs))).iloc[-1]), 1)
        except: pass

        # ── ATR (Average True Range - volatilite) ────────────
        atr = None
        try:
            high_s = hist['High'].dropna()
            low_s  = hist['Low'].dropna()
            tr = (high_s - low_s).tail(14)
            atr = round(float(tr.mean()), 2)
        except: pass

        # ── Bollinger Bands ───────────────────────────────────
        bb_upper = bb_lower = bb_mid = None
        try:
            bb_mid_s = closes.rolling(20).mean()
            bb_std_s = closes.rolling(20).std()
            bb_mid   = round(float(bb_mid_s.iloc[-1]), 2)
            bb_upper = round(float(bb_mid_s.iloc[-1] + 2 * bb_std_s.iloc[-1]), 2)
            bb_lower = round(float(bb_mid_s.iloc[-1] - 2 * bb_std_s.iloc[-1]), 2)
        except: pass

        # ── Swing Low (20 gün) ────────────────────────────────
        swing_low_10  = round(float(closes.tail(10).min()), 2) if len(closes) >= 10  else None
        swing_low_20  = round(float(closes.tail(20).min()), 2) if len(closes) >= 20  else None
        swing_high_20 = round(float(closes.tail(20).max()), 2) if len(closes) >= 20  else None

        # ── Fibonacci (sadece yakın dönem için) ───────────────
        fib_range = high52w - low52w
        fib_382 = round(high52w - 0.382 * fib_range, 2)
        fib_500 = round(high52w - 0.500 * fib_range, 2)
        fib_618 = round(high52w - 0.618 * fib_range, 2)

        # ── Trend ────────────────────────────────────────────
        if   above50 and above200:        trend = 'Yukselen'
        elif not above50 and not above200: trend = 'Dusen'
        else:                              trend = 'Yatay'

        # ── Kırılım ──────────────────────────────────────────
        r20h      = float(closes.tail(20).max())
        r20l      = float(closes.tail(20).min())
        breakout  = price >= r20h * 0.99 and above50 and above200
        breakdown = price <= r20l * 1.01

        # ── Temel Veriler ─────────────────────────────────────
        def safe(key, default=None):
            try:
                v = info.get(key)
                return float(v) if v is not None else default
            except: return default

        pe_ttm         = safe('trailingPE')
        pe_fwd         = safe('forwardPE')
        peg            = safe('pegRatio')
        ps             = safe('priceToSalesTrailingTwelveMonths')
        pb             = safe('priceToBook')
        eps_growth     = safe('earningsQuarterlyGrowth')
        rev_growth     = safe('revenueGrowth')
        net_margin     = safe('profitMargins')
        roe            = safe('returnOnEquity')
        gross_margin   = safe('grossMargins')
        eps_fwd        = safe('forwardEps')
        eps_ttm        = safe('trailingEps')
        sector         = info.get('sector', '')
        analyst_target = safe('targetMeanPrice')

        if eps_growth   is not None: eps_growth   = round(eps_growth   * 100, 1)
        if rev_growth   is not None: rev_growth   = round(rev_growth   * 100, 1)
        if net_margin   is not None: net_margin   = round(net_margin   * 100, 1)
        if roe          is not None: roe          = round(roe          * 100, 1)
        if gross_margin is not None: gross_margin = round(gross_margin * 100, 1)

        # ── Temel Adil Değer ──────────────────────────────────
        sector_pe = {
            'Technology': 28, 'Semiconductors': 25,
            'Software': 32, 'Communication Services': 22,
            'Consumer Cyclical': 20, 'Healthcare': 22,
        }
        fair_pe = sector_pe.get(sector, 22)
        fair_price_pe  = round(eps_fwd * fair_pe, 2) if eps_fwd and eps_fwd > 0 else None
        fair_price_analyst = round(analyst_target, 2) if analyst_target else None

        # ── 3 Giris Senaryosu ─────────────────────────────────
        # Siralama: Hemen Gir (en yuksek) → Geri Cekilme → Buyuk Duzeltme (en dusuk)
        if is_momentum:
            # Hemen Gir: Su fiyata en yakin
            entry_now = min(
                round(price * 0.97, 2),
                round(max(
                    swing_low_10 if swing_low_10 else price * 0.95,
                    sma20 * 0.99 if sma20 else price * 0.95
                ), 2)
            )
            # Geri Cekilme Bekle: SMA20 veya 20 gun swing low
            entry_pullback = round(min(
                sma20 if sma20 else price * 0.92,
                swing_low_20 if swing_low_20 else price * 0.92
            ), 2)
            # Buyuk Duzeltme Bekle: SMA50
            entry_dip = round(sma50, 2) if sma50 else round(price * 0.85, 2)
        else:
            # Hemen Gir: %3 altı veya BB alt band
            entry_now = round(price * 0.97, 2)
            # Geri Cekilme Bekle: SMA50 veya Fibonacci 38.2
            candidates = [x for x in [sma50, fib_382] if x and x < price * 0.95]
            entry_pullback = round(max(candidates), 2) if candidates else round(price * 0.90, 2)
            # Buyuk Duzeltme Bekle: Fibonacci 50 veya SMA200
            candidates2 = [x for x in [fib_500, sma200] if x and x < price * 0.88]
            entry_dip = round(max(candidates2), 2) if candidates2 else round(price * 0.80, 2)

        # Eski degisken isimleri (geriye uyumluluk)
        entry_aggressive   = entry_now
        entry_mid          = entry_pullback
        entry_conservative = entry_dip
        # Hedef fiyat
        if analyst_target and analyst_target > price:
            target_price = round(analyst_target, 2)
        else:
            target_price = round(high52w * 1.05, 2) if pct_from_52w < 5 else round(high52w * 0.99, 2)

        # Her senaryo için R/R hesapla
        def calc_rr(entry, target, stop_pct=0.07):
            stop = round(entry * (1 - stop_pct), 2)
            if entry <= 0 or target <= entry or entry <= stop:
                return stop, 0
            rr = round((target - entry) / (entry - stop), 2)
            return stop, rr

        stop_agg,  rr_agg  = calc_rr(entry_aggressive,   target_price)
        stop_mid,  rr_mid  = calc_rr(entry_mid,           target_price)
        stop_cons, rr_cons = calc_rr(entry_conservative,  target_price)

        # Ana giriş = orta senaryo (en dengeli)
        entry  = entry_mid
        stop   = stop_mid
        rr     = rr_mid
        target = target_price

        # Konsensüs bölge = agresif ile orta arasındaki alan
        ideal_entry_low  = min(entry_aggressive, entry_mid)
        ideal_entry_high = max(entry_aggressive, entry_mid)
        consensus_low    = ideal_entry_low
        consensus_high   = ideal_entry_high

        # VP proxy
        poc = round(sma50,  2) if sma50  else None
        vah = round(sma50 * 1.05, 2) if sma50 else None
        val = round(sma20, 2) if sma20 else None

        # ── Giriş Kalitesi (0-100) ────────────────────────────
        entry_score = 50

        if sma50_dist is not None:
            if   -5  <= sma50_dist <= 5:   entry_score += 10
            elif  5  <  sma50_dist <= 15:  entry_score += 5
            elif  sma50_dist > 15:          entry_score -= 8
            elif  sma50_dist < -5:          entry_score += 12

        if w52_position is not None:
            if   w52_position <= 30:  entry_score += 15
            elif w52_position <= 50:  entry_score += 8
            elif w52_position <= 70:  entry_score += 0
            elif w52_position <= 85:  entry_score -= 5
            else:                     entry_score -= 10

        if rsi is not None:
            if   rsi < 30:   entry_score += 15
            elif rsi < 45:   entry_score += 8
            elif rsi < 55:   entry_score += 2
            elif rsi < 70:   entry_score -= 5
            else:             entry_score -= 12

        if pe_fwd is not None:
            if   pe_fwd < 15:  entry_score += 12
            elif pe_fwd < 25:  entry_score += 7
            elif pe_fwd < 35:  entry_score += 2
            elif pe_fwd < 50:  entry_score -= 3
            else:              entry_score -= 8

        if peg is not None:
            if   peg < 1:   entry_score += 10
            elif peg < 1.5: entry_score += 6
            elif peg < 2:   entry_score += 2
            elif peg < 3:   entry_score -= 5
            else:           entry_score -= 8

        if eps_growth is not None:
            if   eps_growth >= 30: entry_score += 5
            elif eps_growth >= 15: entry_score += 2
            elif eps_growth < 0:   entry_score -= 5

        if bb_lower and price <= bb_lower * 1.02: entry_score += 8
        if bb_upper and price >= bb_upper * 0.98: entry_score -= 8

        # Momentum bonusu — güçlü trend indirim sayılır
        if is_momentum and rsi and rsi < 60: entry_score += 5

        entry_score = max(0, min(100, entry_score))

        if   entry_score >= 75: entry_label = 'UCUZ — Ideal Giris'
        elif entry_score >= 60: entry_label = 'MAKUL — Iyi Fiyat'
        elif entry_score >= 45: entry_label = 'NOTR — Kabul Edilebilir'
        elif entry_score >= 30: entry_label = 'PAHALI — Bekle'
        else:                   entry_label = 'COK PAHALI — Girme'

        # Fiyat vs ideal bölge
        if price <= ideal_entry_high * 1.03:
            price_vs_ideal = 'Ideal bolgede'
            price_vs_color = 'green'
        elif price <= ideal_entry_high * 1.12:
            price_vs_ideal = 'Biraz pahali'
            price_vs_color = 'yellow'
        else:
            price_vs_ideal = 'Pahali — bekle'
            price_vs_color = 'red'

        # ── Ana Sinyal ───────────────────────────────────────
        score = 0
        if trend == 'Yukselen': score += 3
        elif trend == 'Dusen':  score -= 3
        score += 1 if above50  else -1
        score += 1 if above200 else -1
        if pct_from_52w <= 10:   score += 2
        elif pct_from_52w <= 20: score += 1
        elif pct_from_52w >= 40: score -= 1
        if breakout:  score += 1
        if breakdown: score -= 2
        if vol_label == 'Yuksek' and trend == 'Yukselen': score += 1
        elif vol_label == 'Dusuk' and trend == 'Dusen':   score -= 1

        if   score >= 6: sinyal = 'GUCLU AL'
        elif score >= 3: sinyal = 'AL'
        elif score >= 0: sinyal = 'DIKKAT'
        elif score >= -3:sinyal = 'ZAYIF'
        else:            sinyal = 'SAT'

        if   rr >= 3: karar = 'GUCLU AL'
        elif rr >= 2: karar = 'AL'
        elif rr >= 1: karar = 'DIKKATLI'
        else:         karar = 'GECME'

        chart_closes = [round(float(c), 2) for c in closes.tail(60).tolist()]
        chart_dates  = [str(d.date()) if hasattr(d, 'date') else str(d)[:10]
                        for d in closes.tail(60).index.tolist()]

        return {
            'ticker': ticker, 'fiyat': round(price, 2), 'degisim': change,
            'trend': trend,
            'sma20': round(sma20, 2) if sma20 else None,
            'sma50': round(sma50, 2) if sma50 else None,
            'sma200': round(sma200, 2) if sma200 else None,
            'sma50_dist': sma50_dist, 'sma200_dist': sma200_dist,
            'above50': above50, 'above200': above200,
            'pct_from_52w': pct_from_52w, 'high52w': round(high52w, 2),
            'low52w': round(low52w, 2), 'w52_position': w52_position,
            'near_52w': near_52w, 'hacim': vol_label, 'vol_ratio': vol_ratio,
            'rsi': rsi, 'atr': atr,
            'bb_upper': bb_upper, 'bb_mid': bb_mid, 'bb_lower': bb_lower,
            'fib_382': fib_382, 'fib_500': fib_500, 'fib_618': fib_618,
            'swing_low_10': swing_low_10, 'swing_low_20': swing_low_20,
            'is_momentum': is_momentum, 'gain_6m': gain_6m,
            'kirilim': breakout, 'cokus': breakdown,
            'sinyal': sinyal, 'skor': score,
            # 3 Senaryo
            'entry_aggressive': entry_aggressive,
            'entry_mid': entry_mid,
            'entry_conservative': entry_conservative,
            'stop_agg': stop_agg, 'rr_agg': rr_agg,
            'stop_mid': stop_mid, 'rr_mid': rr_mid,
            'stop_cons': stop_cons, 'rr_cons': rr_cons,
            'target': target,
            # Genel
            'giris': entry, 'hedef': target, 'stop': stop, 'rr': rr,
            'ideal_entry_low': ideal_entry_low,
            'ideal_entry_high': ideal_entry_high,
            'consensus_low': consensus_low,
            'consensus_high': consensus_high,
            'entry_score': entry_score, 'entry_label': entry_label,
            'price_vs_ideal': price_vs_ideal, 'price_vs_color': price_vs_color,
            'karar': karar,
            'poc': poc, 'vah': vah, 'val': val,
            'pe_ttm': pe_ttm, 'pe_fwd': pe_fwd, 'peg': peg,
            'ps': round(ps, 2) if ps else None,
            'pb': round(pb, 2) if pb else None,
            'eps_growth': eps_growth, 'rev_growth': rev_growth,
            'net_margin': net_margin, 'roe': roe,
            'gross_margin': gross_margin,
            'fair_price_pe': fair_price_pe,
            'fair_price_analyst': fair_price_analyst,
            'sector': sector,
            'chart_closes': chart_closes, 'chart_dates': chart_dates,
            'portfolio': ticker in PORTFOLIO, 'hata': None
        }
    except Exception as e:
        return {'ticker': ticker, 'hata': str(e)}




# ── EARNINGS FONKSİYONU ───────────────────────────────────────
def get_earnings(ticker):
    try:
        tk = yf.Ticker(ticker)
        info = {}
        try:
            info = tk.info or {}
        except: pass

        # Method 1: earnings_dates
        next_date = None
        try:
            ed = tk.earnings_dates
            if ed is not None and not ed.empty:
                from datetime import date
                today = date.today()
                future_dates = [d for d in ed.index if hasattr(d, 'date') and d.date() >= today]
                if future_dates:
                    next_date = str(min(future_dates).date())
        except: pass

        # Method 2: calendar fallback
        if not next_date:
            try:
                cal = tk.calendar
                if cal is not None:
                    if isinstance(cal, dict):
                        ed_list = cal.get('Earnings Date', [])
                        if ed_list:
                            from datetime import date
                            today = date.today()
                            future = [d for d in ed_list if hasattr(d, 'date') and d.date() >= today]
                            if future:
                                next_date = str(min(future).date())
            except: pass

        # Method 3: info fields
        if not next_date:
            try:
                from datetime import datetime, date
                ed = info.get('earningsTimestamp') or info.get('earningsDate')
                if ed:
                    if isinstance(ed, (int, float)):
                        dt = datetime.fromtimestamp(ed).date()
                        if dt >= date.today():
                            next_date = str(dt)
            except: pass

        # EPS estimate
        eps_est = None
        try:
            v = info.get('forwardEps')
            if v: eps_est = round(float(v), 2)
        except: pass

        # Earnings surprise
        surprise_pct = None
        try:
            ed = tk.earnings_dates
            if ed is not None and not ed.empty and 'EPS Estimate' in ed.columns and 'Reported EPS' in ed.columns:
                past = ed.dropna(subset=['Reported EPS', 'EPS Estimate'])
                if not past.empty:
                    last = past.iloc[0]
                    est = float(last['EPS Estimate'])
                    rep = float(last['Reported EPS'])
                    if est and est != 0:
                        surprise_pct = round((rep - est) / abs(est) * 100, 1)
        except: pass

        # Days to earnings
        days_to_earnings = None
        if next_date:
            try:
                from datetime import date
                nd = date.fromisoformat(next_date)
                days_to_earnings = (nd - date.today()).days
            except: pass

        alert = None
        if days_to_earnings is not None:
            if 0 <= days_to_earnings <= 7:   alert = 'red'
            elif 0 <= days_to_earnings <= 14: alert = 'yellow'

        # ── Rapor öncesi/sonrası fiyat hareketi (son 4 rapor) ──
        avg_move_pct = None
        history_eps  = []
        try:
            ed = tk.earnings_dates
            if ed is not None and not ed.empty:
                from datetime import date, timedelta
                hist_prices = tk.history(period='2y')
                closes = hist_prices['Close'] if not hist_prices.empty else None

                if closes is not None and 'EPS Estimate' in ed.columns and 'Reported EPS' in ed.columns:
                    past = ed.dropna(subset=['Reported EPS', 'EPS Estimate']).head(4)
                    moves = []
                    for dt, row in past.iterrows():
                        try:
                            report_date = dt.date()
                            # Rapor günü ve 1 gün öncesi fiyatları
                            pre_dates  = [d for d in closes.index if d.date() == report_date - timedelta(days=1)]
                            post_dates = [d for d in closes.index if d.date() == report_date or d.date() == report_date + timedelta(days=1)]
                            if pre_dates and post_dates:
                                pre_price  = float(closes[pre_dates[0]])
                                post_price = float(closes[post_dates[-1]])
                                move_pct   = round((post_price - pre_price) / pre_price * 100, 1)
                                moves.append(move_pct)

                            # EPS geçmişi
                            est = float(row['EPS Estimate']) if row['EPS Estimate'] else None
                            rep = float(row['Reported EPS']) if row['Reported EPS'] else None
                            surp = round((rep - est) / abs(est) * 100, 1) if est and rep and est != 0 else None
                            history_eps.append({
                                'date': str(report_date),
                                'estimate': est,
                                'actual': rep,
                                'surprise_pct': surp
                            })
                        except: pass

                    if moves:
                        avg_move_pct = round(sum(moves) / len(moves), 1)
        except: pass

        return {
            'ticker': ticker, 'next_date': next_date,
            'days_to_earnings': days_to_earnings,
            'eps_estimate': eps_est, 'surprise': None,
            'surprise_pct': surprise_pct, 'alert': alert,
            'avg_move_pct': avg_move_pct,
            'history_eps': history_eps,
            'hata': None
        }
    except Exception as e:
        return {'ticker': ticker, 'next_date': None, 'days_to_earnings': None,
                'eps_estimate': None, 'surprise': None, 'surprise_pct': None,
                'alert': None, 'avg_move_pct': None, 'history_eps': [],
                'hata': str(e)}


# ── PİYASA TRENDİ (SPY + QQQ via yfinance) ───────────────────
def get_market_data():
    results = {}
    indices = {
        'SP500': 'SPY',   # S&P 500 ETF
        'NASDAQ': 'QQQ',  # NASDAQ ETF
        'VIX': '^VIX'     # Volatilite endeksi
    }
    for name, ticker in indices.items():
        try:
            tk   = yf.Ticker(ticker)
            hist = tk.history(period='1y')
            if hist.empty:
                continue
            closes = hist['Close'].dropna()
            price  = round(float(closes.iloc[-1]), 2)
            prev   = round(float(closes.iloc[-2]), 2) if len(closes) > 1 else price
            change = round((price - prev) / prev * 100, 2)
            sma50  = round(float(closes.tail(50).mean()), 2) if len(closes) >= 50  else None
            sma200 = round(float(closes.tail(200).mean()), 2) if len(closes) >= 200 else None
            above50  = price > sma50  if sma50  else False
            above200 = price > sma200 if sma200 else False
            results[name] = {
                'price': price, 'change': change,
                'sma50': sma50, 'sma200': sma200,
                'above50': above50, 'above200': above200
            }
        except Exception as e:
            results[name] = {'price': None, 'change': None, 'error': str(e)}

    # M Kriteri — piyasa durumu
    sp  = results.get('SP500', {})
    nas = results.get('NASDAQ', {})
    vix = results.get('VIX', {})

    both_above200 = sp.get('above200') and nas.get('above200')
    both_above50  = sp.get('above50')  and nas.get('above50')
    vix_high      = vix.get('price', 0) and vix.get('price', 0) > 25

    if both_above200 and both_above50 and not vix_high:
        m_signal = 'GUCLU'
        m_label  = 'Piyasa Güçlü — Giriş yapılabilir'
        m_color  = 'green'
    elif both_above200 and not vix_high:
        m_signal = 'NOTR'
        m_label  = 'Piyasa Nötr — Dikkatli ol'
        m_color  = 'yellow'
    else:
        m_signal = 'ZAYIF'
        m_label  = 'Piyasa Zayıf — Yeni pozisyon açma'
        m_color  = 'red'

    results['M_SIGNAL'] = m_signal
    results['M_LABEL']  = m_label
    results['M_COLOR']  = m_color
    return results

# ── HABER AKIŞI (Finnhub) ─────────────────────────────────────
def get_news(watchlist, portfolio, finnhub_key):
    import urllib.request, json as _json
    all_news = []
    seen_ids = set()

    # Önce portföy hisseleri, sonra watchlist
    priority = list(portfolio) + [t for t in watchlist if t not in portfolio]

    for ticker in priority[:8]:  # Max 8 hisse — limit aşmamak için
        try:
            url = f'https://finnhub.io/api/v1/company-news?symbol={ticker}&from=2020-01-01&to=2099-01-01&token={finnhub_key}'
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                news_list = _json.loads(resp.read())
                for n in news_list[:3]:  # Her hisseden max 3 haber
                    nid = n.get('id', n.get('url', ''))
                    if nid not in seen_ids:
                        seen_ids.add(nid)
                        all_news.append({
                            'ticker':   ticker,
                            'headline': n.get('headline', ''),
                            'summary':  n.get('summary', '')[:200] if n.get('summary') else '',
                            'url':      n.get('url', ''),
                            'datetime': n.get('datetime', 0),
                            'source':   n.get('source', ''),
                            'portfolio': ticker in portfolio
                        })
        except Exception as e:
            print(f'  Haber hatasi {ticker}: {e}')
            continue

    # Tarihe göre sırala (en yeni önce)
    all_news.sort(key=lambda x: x['datetime'], reverse=True)
    return all_news[:20]  # Max 20 haber

# ── TARAMA ────────────────────────────────────────────────────
print('CANSLIM Scanner v2 baslatiliyor...')
print(f'Watchlist: {len(WATCHLIST)} hisse | Portfolio: {len(PORTFOLIO)} hisse')
print('3 zaman dilimi taranacak\n')

TF_CONFIG = {
    '1d':  {'period': '1y',  'interval': '1d',  'label': '1 Gun'},
    '1wk': {'period': '2y',  'interval': '1wk', 'label': '1 Hafta'},
    '1mo': {'period': '5y',  'interval': '1mo', 'label': '1 Ay'},
}

tf_data = {}
for tf_key, cfg in TF_CONFIG.items():
    print(f"\n{cfg['label']} taranıyor...")
    tf_results = []
    for i, ticker in enumerate(WATCHLIST, 1):
        print(f'  [{i:2}/{len(WATCHLIST)}] {ticker:<6}...', end=' ', flush=True)
        r = analyze(ticker, period=cfg['period'], interval=cfg['interval'])
        tf_results.append(r)
        if r.get('hata'):
            print(f'HATA: {r["hata"]}')
        else:
            print(f'{r["sinyal"]:<10} ${r["fiyat"]}')
    tf_data[tf_key] = tf_results

print(f'\nTarama tamamlandi! {len(tf_data)} zaman dilimi x {len(WATCHLIST)} hisse')

# ── PİYASA VERİSİ ─────────────────────────────────────────────
print('\n📊 Piyasa verisi cekiliyor...')
market_data = get_market_data()
sp = market_data.get('SP500', {})
nas = market_data.get('NASDAQ', {})
vix = market_data.get('VIX', {})
print(f'  S&P 500: ${sp.get("price","?")} ({sp.get("change","?")}%)')
print(f'  NASDAQ:  ${nas.get("price","?")} ({nas.get("change","?")}%)')
print(f'  VIX:     ${vix.get("price","?")}')
print(f'  M Kriteri: {market_data.get("M_LABEL","?")}')

# ── HABER AKIŞI ───────────────────────────────────────────────
print('\n📰 Haberler cekiliyor...')
news_data = get_news(WATCHLIST, PORTFOLIO, FINNHUB_KEY)
print(f'  {len(news_data)} haber bulundu')

# ── EARNINGS VERİSİ ───────────────────────────────────────────
print('\n📅 Earnings takvimi cekiliyor...')
earnings_data = []
for i, ticker in enumerate(WATCHLIST, 1):
    print(f'  [{i:2}/{len(WATCHLIST)}] {ticker:<6}...', end=' ', flush=True)
    e = get_earnings(ticker)
    earnings_data.append(e)
    if e['next_date']:
        days = e['days_to_earnings']
        alert = '🔴' if e['alert']=='red' else '🟡' if e['alert']=='yellow' else '📅'
        print(f'{alert} {e["next_date"]} ({days} gun)')
    else:
        print('tarih yok')





# ── HTML TEMPLATE ─────────────────────────────────────────────
import base64 as _b64

def get_html_template():
    return """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CANSLIM Scanner</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%230d1117'/%3E%3Cpolyline points='4,24 10,16 16,20 22,10 28,14' fill='none' stroke='%2310b981' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Bebas+Neue&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#05070f;--bg2:#0d1117;--bg3:#161b24;--border:rgba(255,255,255,0.08);--text:#e2e8f0;--muted:#4b5563;--green:#10b981;--green2:#34d399;--red:#ef4444;--red2:#f87171;--yellow:#f59e0b;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Space Grotesk',sans-serif;min-height:100vh}
.header{background:linear-gradient(135deg,#0d1117,#111827);border-bottom:1px solid var(--border);padding:14px 20px;position:sticky;top:0;z-index:100}
.header-inner{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;max-width:1400px;margin:0 auto}
.logo-main{font-family:'Bebas Neue',sans-serif;font-size:22px;letter-spacing:4px;background:linear-gradient(135deg,#10b981,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.timestamp{font-size:11px;color:var(--muted);font-family:'JetBrains Mono',monospace}
.live-dot{width:7px;height:7px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;display:inline-block;margin-right:5px}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(16,185,129,.4)}50%{opacity:.7;box-shadow:0 0 0 6px rgba(16,185,129,0)}}
.nav{display:flex;gap:4px;padding:10px 20px;border-bottom:1px solid var(--border);background:var(--bg2);overflow-x:auto;flex-wrap:wrap}
.tab{padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;border:1px solid transparent;background:none;color:var(--muted);transition:all .2s;white-space:nowrap}
.tab:hover{color:var(--text);background:var(--bg3)}
.tab.active{background:var(--bg3);color:var(--text);border-color:var(--border)}
.tab.port.active{background:rgba(16,185,129,.1);color:var(--green);border-color:rgba(16,185,129,.3)}
.tf-row{display:flex;gap:6px;padding:10px 20px;border-bottom:1px solid var(--border);background:var(--bg2);align-items:center;flex-wrap:wrap}
.tf-btn{padding:5px 12px;border-radius:6px;font-size:11px;cursor:pointer;border:1px solid var(--border);background:var(--bg3);color:var(--muted);font-family:'JetBrains Mono',monospace;transition:all .2s}
.tf-btn.active{background:rgba(59,130,246,.15);color:#60a5fa;border-color:rgba(59,130,246,.4)}
.tf-btn.star{position:relative}
.tf-btn.star::after{content:'★';position:absolute;top:-5px;right:-4px;font-size:8px;color:var(--yellow)}
.tf-hint{font-size:10px;color:var(--muted)}
.stats{display:flex;gap:8px;padding:10px 20px;border-bottom:1px solid var(--border);background:var(--bg2);flex-wrap:wrap}
.pill{display:flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;border:1px solid}
.pill.g{background:rgba(16,185,129,.1);color:var(--green);border-color:rgba(16,185,129,.25)}
.pill.r{background:rgba(239,68,68,.1);color:var(--red2);border-color:rgba(239,68,68,.25)}
.pill.y{background:rgba(245,158,11,.1);color:var(--yellow);border-color:rgba(245,158,11,.25)}
.pill.b{background:rgba(59,130,246,.1);color:#60a5fa;border-color:rgba(59,130,246,.25)}
.pill.m{background:var(--bg3);color:var(--muted);border-color:var(--border)}
.dot{width:5px;height:5px;border-radius:50%;background:currentColor}
.main{padding:14px 20px;max-width:1400px;margin:0 auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}
@media(max-width:480px){.grid{grid-template-columns:1fr}}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;overflow:hidden;cursor:pointer;transition:all .2s}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.4)}
.accent{height:3px}
.cbody{padding:12px 14px}
.ctop{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:8px}
.ticker{font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:2px;line-height:1}
.cpr{text-align:right}
.pval{font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:600}
.pchg{font-size:11px;font-family:'JetBrains Mono',monospace;margin-top:2px}
.badge{display:inline-block;padding:2px 8px;border-radius:3px;font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;margin-top:3px}
.port-badge{display:inline-flex;align-items:center;gap:3px;padding:2px 6px;border-radius:3px;font-size:9px;font-weight:600;background:rgba(16,185,129,.12);color:var(--green);border:1px solid rgba(16,185,129,.25);margin-left:5px}
.sigs{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:8px}
.sp{font-size:9px;padding:2px 6px;border-radius:3px;font-family:'JetBrains Mono',monospace}
.sg{background:rgba(16,185,129,.1);color:var(--green2);border:1px solid rgba(16,185,129,.2)}
.sb{background:rgba(239,68,68,.1);color:var(--red2);border:1px solid rgba(239,68,68,.2)}
.sn{background:var(--bg3);color:var(--muted);border:1px solid var(--border)}
.chart-w{height:75px;margin-top:8px}
.lvls{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:8px}
.lv{background:var(--bg3);border-radius:5px;padding:6px;text-align:center;border:1px solid var(--border)}
.ll{font-size:8px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:2px}
.lval{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600}
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:1000;display:none;align-items:center;justify-content:center;padding:16px}
.overlay.open{display:flex}
.modal{background:var(--bg2);border:1px solid var(--border);border-radius:14px;width:100%;max-width:520px;max-height:92vh;overflow-y:auto}
.mhead{padding:18px 18px 0;display:flex;justify-content:space-between;align-items:flex-start}
.mtitle{font-family:'Bebas Neue',sans-serif;font-size:30px;letter-spacing:3px}
.mclose{background:var(--bg3);border:1px solid var(--border);color:var(--muted);width:30px;height:30px;border-radius:7px;cursor:pointer;font-size:15px;display:flex;align-items:center;justify-content:center}
.mbody{padding:14px 18px 18px}
.mchartw{height:150px;margin-bottom:14px}
.dgrid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:12px}
.dc{background:var(--bg3);border-radius:7px;padding:9px 11px;border:1px solid var(--border)}
.dl{font-size:9px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:3px}
.dv{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600}
.dbox{border-radius:9px;padding:13px;margin-bottom:12px;border:1px solid}
.dlbl{font-size:9px;letter-spacing:2px;text-transform:uppercase;margin-bottom:5px}
.dverd{font-family:'Bebas Neue',sans-serif;font-size:26px;letter-spacing:2px;margin-bottom:8px}
.drow{display:flex;justify-content:space-between;margin-bottom:4px;font-size:12px}
.dkey{color:var(--muted)}
.rrbar{height:4px;background:var(--bg);border-radius:2px;margin-top:7px;overflow:hidden}
.rrfill{height:100%;border-radius:2px;transition:width .8s ease}
.vpbox{background:var(--bg3);border-radius:7px;padding:10px;border:1px solid var(--border);margin-bottom:12px}
.vptitle{font-size:9px;color:#60a5fa;letter-spacing:2px;text-transform:uppercase;margin-bottom:7px}
.vpgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}
.vpc{background:var(--bg2);border-radius:5px;padding:7px;text-align:center;border:1px solid}
.minfo{display:inline-flex;align-items:center;justify-content:center;width:14px;height:14px;border-radius:50%;background:rgba(96,165,250,.2);color:#60a5fa;font-size:9px;font-weight:700;cursor:pointer;margin-left:4px;border:1px solid rgba(96,165,250,.3)}
.minfo-popup{position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:2000;display:none;align-items:center;justify-content:center;padding:16px}
.minfo-popup.open{display:flex}
.minfo-modal{background:var(--bg2);border:1px solid var(--border);border-radius:14px;width:100%;max-width:480px;max-height:85vh;overflow-y:auto;padding:20px;position:relative}
.minfo-title{font-size:16px;font-weight:700;color:var(--text);margin-bottom:4px}
.minfo-source{font-size:10px;color:var(--muted);margin-bottom:12px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.minfo-rel{padding:2px 7px;border-radius:3px;font-size:9px;font-weight:600}
.minfo-rel.high{background:rgba(16,185,129,.15);color:#10b981}
.minfo-rel.medium{background:rgba(245,158,11,.15);color:#f59e0b}
.minfo-rel.low{background:rgba(239,68,68,.15);color:#ef4444}
.minfo-desc{font-size:12px;color:#94a3b8;line-height:1.6;margin-bottom:14px}
.minfo-warning{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);border-radius:6px;padding:8px 10px;font-size:11px;color:#f59e0b;margin-bottom:14px}
.minfo-ranges{margin-bottom:14px}
.minfo-range-title{font-size:9px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:8px}
.minfo-range{display:flex;align-items:center;gap:8px;margin-bottom:6px;padding:6px 8px;border-radius:6px;background:rgba(255,255,255,.02)}
.minfo-range-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.minfo-canslim{background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.2);border-radius:6px;padding:8px 10px;font-size:11px;color:#60a5fa}
.minfo-close{position:absolute;top:16px;right:16px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);color:#94a3b8;width:28px;height:28px;border-radius:7px;cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center}
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:2px}
</style>
</head>
<body>
<div class="header">
  <div class="header-inner">
    <span class="logo-main">CANSLIM SCANNER</span>
    <span class="timestamp"><span class="live-dot"></span>%%TIMESTAMP%%</span>
    <button onclick="openEditList()" style="background:rgba(59,130,246,.15);border:1px solid rgba(59,130,246,.3);color:#60a5fa;padding:5px 12px;border-radius:6px;font-size:11px;cursor:pointer;font-family:inherit">✏️ Listeyi Düzenle</button>
  </div>
</div>
<div class="nav">
  <button class="tab active" onclick="setTab('dashboard',this)">🏠 Dashboard</button>
  <button class="tab" onclick="setTab('all',this)">📊 Hisseler</button>
  <button class="tab port" onclick="setTab('port',this)">💼 Portföyüm</button>
  <button class="tab" onclick="setTab('buy',this)">📈 Al</button>
  <button class="tab" onclick="setTab('sell',this)">📉 Sat</button>
  <button class="tab" onclick="setTab('earnings',this)">📅 Earnings</button>
</div>
<div class="tf-row" id="tfRow" style="display:none">
  <button class="tf-btn active" data-tf="1d" onclick="setTf('1d',this)">1G</button>
  <button class="tf-btn star" data-tf="1wk" onclick="setTf('1wk',this)">1H</button>
  <button class="tf-btn" data-tf="1mo" onclick="setTf('1mo',this)">1A</button>
  <span class="tf-hint">CANSLIM önerilen: 1G + 1H</span>
</div>
<div class="stats" id="stats"></div>
<div class="main"><div class="grid" id="grid"></div></div>
<div class="overlay" id="overlay" onclick="closeM(event)">
  <div class="modal" id="modal"></div>
</div>

<div class="minfo-popup" id="editPopup" onclick="closeEditPopup(event)">
  <div class="minfo-modal" style="position:relative;max-width:560px" id="editModal">
    <button class="minfo-close" onclick="closeEditPopup()">✕</button>
    <div style="font-size:16px;font-weight:700;color:var(--text);margin-bottom:4px">✏️ Listeyi Düzenle</div>
    <div style="font-size:11px;color:var(--muted);margin-bottom:16px">GitHub API key gerekli — değişiklikler anında kaydedilir</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
      <div>
        <div style="font-size:11px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">📋 Watchlist</div>
        <div id="watchlistEditor"></div>
        <div style="display:flex;gap:6px;margin-top:8px">
          <input id="newWatchTicker" placeholder="Hisse ekle (TSLA)" style="flex:1;background:var(--bg3);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:12px;font-family:inherit;text-transform:uppercase"/>
          <button onclick="addTicker('watch')" style="background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.3);color:var(--green);padding:6px 12px;border-radius:6px;font-size:12px;cursor:pointer">+ Ekle</button>
        </div>
      </div>
      <div>
        <div style="font-size:11px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px">💼 Portföy</div>
        <div id="portfolioEditor"></div>
        <div style="display:flex;gap:6px;margin-top:8px">
          <input id="newPortTicker" placeholder="Hisse ekle (AAPL)" style="flex:1;background:var(--bg3);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:12px;font-family:inherit;text-transform:uppercase"/>
          <button onclick="addTicker('port')" style="background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.3);color:var(--green);padding:6px 12px;border-radius:6px;font-size:12px;cursor:pointer">+ Ekle</button>
        </div>
      </div>
    </div>
    <div style="background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.2);border-radius:8px;padding:10px 12px;margin-bottom:14px;font-size:11px;color:var(--green)">✅ Değişiklikler kaydedilince bir sonraki Colab çalıştırmasında aktif olur.</div>
<input type="hidden" id="ghTokenInput" placeholder="ghp_..." style="width:100%;background:var(--bg3);border:1px solid var(--border);color:var(--text);padding:8px 10px;border-radius:6px;font-size:11px;font-family:JetBrains Mono,monospace"/>
    <div style="display:flex;gap:8px">
      <button onclick="saveListToGithub()" style="flex:1;background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.3);color:var(--green);padding:10px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer">💾 GitHub'a Kaydet</button>
      <button onclick="closeEditPopup()" style="background:var(--bg3);border:1px solid var(--border);color:var(--muted);padding:10px 16px;border-radius:8px;font-size:13px;cursor:pointer">İptal</button>
    </div>
    <div id="editStatus" style="margin-top:10px;font-size:12px;text-align:center"></div>
  </div>
</div>

<div class="minfo-popup" id="minfoPopup" onclick="closeInfoPopup(event)">
  <div class="minfo-modal" id="minfoModal">
    <button class="minfo-close" onclick="closeInfoPopup()">✕</button>
    <div id="minfoContent"></div>
  </div>
</div>
<script>
var METRICS = {
  // TEKNİK
  'RSI': {
    title: 'RSI (Göreceli Güç Endeksi)',
    desc: 'Hissenin aşırı alım veya aşırı satım bölgesinde olup olmadığını gösterir. 14 günlük fiyat hareketlerini analiz eder.',
    source: 'Teknik Analiz',
    reliability: 'high',
    ranges: [
      {label:'Aşırı Satım',min:0,max:30,color:'green',desc:'Fırsat bölgesi — fiyat çok düşmüş'},
      {label:'Normal',min:30,max:70,color:'yellow',desc:'Nötr bölge'},
      {label:'Aşırı Alım',min:70,max:100,color:'red',desc:'Dikkat — fiyat çok yükselmiş'}
    ],
    canslim: 'N kriteri ile ilgili — fiyat momentumu'
  },
  'SMA50': {
    title: 'SMA 50 (50 Günlük Hareketli Ortalama)',
    desc: 'Son 50 günün ortalama kapanış fiyatı. Kısa-orta vadeli trend göstergesi.',
    source: 'Teknik Analiz',
    reliability: 'high',
    ranges: [
      {label:'Üzerinde',color:'green',desc:'Kısa vadeli trend pozitif — güçlü sinyal'},
      {label:'Altında',color:'red',desc:'Kısa vadeli trend negatif'}
    ],
    canslim: 'M kriteri — piyasa trendi'
  },
  'SMA200': {
    title: 'SMA 200 (200 Günlük Hareketli Ortalama)',
    desc: 'Son 200 günün ortalama kapanış fiyatı. Uzun vadeli trend göstergesi. En önemli teknik seviye.',
    source: 'Teknik Analiz',
    reliability: 'high',
    ranges: [
      {label:'Üzerinde',color:'green',desc:'Uzun vadeli boğa trendinde — CANSLIM için şart'},
      {label:'Altında',color:'red',desc:'Uzun vadeli ayı trendinde — CANSLIM için girme'}
    ],
    canslim: 'M kriteri — zorunlu koşul'
  },
  '52W': {
    title: '52 Haftalık Pozisyon',
    desc: 'Hissenin son 1 yıldaki fiyat aralığında nerede olduğunu gösterir. 0=yılın dibi, 100=yılın zirvesi.',
    source: 'Teknik Analiz',
    reliability: 'high',
    ranges: [
      {label:'0-30%',color:'green',desc:'Yılın dibine yakın — potansiyel fırsat'},
      {label:'30-70%',color:'yellow',desc:'Orta bölge — nötr'},
      {label:'70-85%',color:'yellow',desc:'Zirveye yaklaşıyor — izle'},
      {label:'85-100%',color:'red',desc:'Zirveye çok yakın — dikkatli gir'}
    ],
    canslim: 'N kriteri — yeni zirve kırılımı için ideal bölge %85-100'
  },
  'Hacim': {
    title: 'Hacim (İşlem Miktarı)',
    desc: 'Günlük işlem hacminin son 20 günlük ortalamaya oranı. Güçlü hareketlerin hacimle desteklenmesi gerekir.',
    source: 'Teknik Analiz',
    reliability: 'high',
    ranges: [
      {label:'Yüksek (>1.3x)',color:'green',desc:'Kurumsal ilgi var — güçlü sinyal'},
      {label:'Normal (0.7-1.3x)',color:'yellow',desc:'Ortalama ilgi'},
      {label:'Düşük (<0.7x)',color:'red',desc:'İlgi azalmış — dikkat'}
    ],
    canslim: 'S kriteri — arz/talep dengesi'
  },
  // TEMEL
  'ForwardPE': {
    title: 'Forward P/E (İleriye Dönük Fiyat/Kazanç)',
    desc: 'Şirketin önümüzdeki 12 aydaki tahmini kazancına göre fiyatı. Trailing P/E\\'den daha önemli çünkü geleceğe bakıyor.',
    source: 'Temel Analiz — Analist tahmini',
    reliability: 'medium',
    warning: 'Analist tahminlerine dayanır, yanıltıcı olabilir',
    ranges: [
      {label:'<15',color:'green',desc:'Ucuz — büyüme beklentisi düşük veya hisse değer altında'},
      {label:'15-25',color:'green',desc:'Makul — çoğu sektör için normal'},
      {label:'25-40',color:'yellow',desc:'Pahalı ama büyüme primi ödeniyor'},
      {label:'>40',color:'red',desc:'Çok pahalı — yüksek büyüme beklentisi fiyatlanmış'}
    ],
    canslim: 'C ve A kriterleri ile ilgili'
  },
  'PEG': {
    title: 'PEG Oranı (Fiyat/Kazanç/Büyüme)',
    desc: 'P/E oranını büyüme hızıyla karşılaştırır. Büyüyen şirketler için P/E\\'den daha doğru değerleme ölçütü. PEG=1 adil değer kabul edilir.',
    source: 'Temel Analiz — Analist tahmini',
    reliability: 'medium',
    warning: 'Analist büyüme tahminlerine dayanır',
    ranges: [
      {label:'<1.0',color:'green',desc:'Ucuz — büyümesine göre değer altında'},
      {label:'1.0-1.5',color:'green',desc:'Makul — adil fiyat civarı'},
      {label:'1.5-2.0',color:'yellow',desc:'Biraz pahalı'},
      {label:'>2.0',color:'red',desc:'Pahalı — dikkatli ol'}
    ],
    canslim: 'A kriteri — büyüme kalitesi'
  },
  'EPSGrowth': {
    title: 'EPS Büyümesi (Çeyreklik, YoY)',
    desc: 'Şirketin hisse başına kazancının geçen yılın aynı çeyreğine göre artışı. CANSLIM\\'in en kritik kriteri.',
    source: 'Temel Analiz — Gerçek veri',
    reliability: 'high',
    ranges: [
      {label:'>%25',color:'green',desc:'Güçlü büyüme — CANSLIM kriteri karşılandı'},
      {label:'%15-25',color:'green',desc:'İyi büyüme'},
      {label:'%0-15',color:'yellow',desc:'Zayıf büyüme'},
      {label:'<0',color:'red',desc:'Kazanç düşüyor — dikkat'}
    ],
    canslim: 'C kriteri — en kritik kriter, minimum %25 olmalı'
  },
  'RevGrowth': {
    title: 'Gelir Büyümesi (YoY)',
    desc: 'Şirketin satış/gelirinin geçen yıla göre artışı. EPS büyümesini desteklemesi gerekir — sadece maliyet kesintisiyle büyüme sürdürülebilir değil.',
    source: 'Temel Analiz — Gerçek veri',
    reliability: 'high',
    ranges: [
      {label:'>%15',color:'green',desc:'Güçlü gelir büyümesi'},
      {label:'%5-15',color:'yellow',desc:'Orta büyüme'},
      {label:'<5',color:'red',desc:'Gelir büyümesi zayıf'}
    ],
    canslim: 'A kriteri — sürdürülebilir büyüme için şart'
  },
  'NetMargin': {
    title: 'Net Marjin',
    desc: 'Her 1$ gelirden ne kadar net kâr kaldığını gösterir. Yüksek marjin = güçlü iş modeli.',
    source: 'Temel Analiz — Gerçek veri',
    reliability: 'high',
    ranges: [
      {label:'>%20',color:'green',desc:'Çok güçlü kârlılık'},
      {label:'%10-20',color:'green',desc:'İyi kârlılık'},
      {label:'%5-10',color:'yellow',desc:'Orta kârlılık'},
      {label:'<5',color:'red',desc:'Zayıf kârlılık'}
    ],
    canslim: 'A kriteri — kârlılık kalitesi'
  },
  'ROE': {
    title: 'ROE (Özkaynak Kârlılığı)',
    desc: 'Şirketin öz sermayesiyle ne kadar kâr ettiğini gösterir. Yüksek ROE = sermayeyi verimli kullanıyor.',
    source: 'Temel Analiz — Gerçek veri',
    reliability: 'high',
    ranges: [
      {label:'>%25',color:'green',desc:'Çok güçlü — CANSLIM ideal seviyesi'},
      {label:'%15-25',color:'green',desc:'İyi'},
      {label:'%8-15',color:'yellow',desc:'Orta'},
      {label:'<8',color:'red',desc:'Zayıf'}
    ],
    canslim: 'A kriteri — minimum %17 olmalı'
  },
  'GrossMargin': {
    title: 'Brüt Marjin',
    desc: 'Satış gelirinden üretim maliyeti düşüldükten sonra kalan oran. Sektöre göre değişir.',
    source: 'Temel Analiz — Gerçek veri',
    reliability: 'high',
    ranges: [
      {label:'>%50',color:'green',desc:'Çok güçlü — yazılım/SaaS seviyesi'},
      {label:'%30-50',color:'green',desc:'İyi'},
      {label:'%15-30',color:'yellow',desc:'Orta — donanım/yarı iletken normal'},
      {label:'<15',color:'red',desc:'Düşük marjin'}
    ],
    canslim: 'Kârlılık kalitesi göstergesi'
  },
  // GİRİŞ
  'EntryScore': {
    title: 'Giriş Kalitesi Skoru',
    desc: 'RSI, SMA pozisyonu, P/E, PEG ve EPS büyümesini birleştiren bileşik skor. 0-100 arası.',
    source: 'Bizim hesaplama',
    reliability: 'low',
    warning: 'BU UYGULAMA TARAFINDAN HESAPLANAN KABA TAHMİNDİR. Yatırım kararı için tek başına kullanma.',
    ranges: [
      {label:'75-100',color:'green',desc:'Ucuz — ideal giriş bölgesi'},
      {label:'60-75',color:'green',desc:'Makul fiyat'},
      {label:'45-60',color:'yellow',desc:'Nötr'},
      {label:'30-45',color:'red',desc:'Pahalı — bekle'},
      {label:'0-30',color:'red',desc:'Çok pahalı — girme'}
    ],
    canslim: 'Tüm kriterler bileşimi'
  },
  'RR': {
    title: 'Risk/Ödül Oranı (R/R)',
    desc: 'Potansiyel kazancın riske oranı. 1:2 demek 1$ riske karşı 2$ kazanç potansiyeli var demek.',
    source: 'Bizim hesaplama',
    reliability: 'low',
    warning: 'Giriş/hedef/stop seviyeleri formül bazlı kaba tahmindir',
    ranges: [
      {label:'1:3+',color:'green',desc:'Mükemmel — güçlü giriş sinyali'},
      {label:'1:2',color:'green',desc:'İyi — minimum kabul edilebilir'},
      {label:'1:1',color:'yellow',desc:'Zayıf'},
      {label:'<1:1',color:'red',desc:'Risk kazançtan büyük — girme'}
    ],
    canslim: 'Risk yönetimi'
  },
  // EARNINGS
  'EarningsDate': {
    title: 'Rapor Tarihi (Earnings Date)',
    desc: 'Şirketin çeyrek finansal sonuçlarını açıklayacağı tarih. Rapor öncesi ve sonrası fiyat sert hareket edebilir.',
    source: 'yfinance — bazen hatalı olabilir',
    reliability: 'medium',
    warning: 'Tarihleri resmi IR sayfasından doğrulayın',
    ranges: [
      {label:'7 gün içinde',color:'red',desc:'Çok yakın — pozisyon açmak riskli'},
      {label:'8-14 gün',color:'yellow',desc:'Yakın — dikkatli ol'},
      {label:'14+ gün',color:'green',desc:'Yeterli süre var'}
    ],
    canslim: 'C kriteri — çeyrek rapor kalitesi'
  },
  'AvgMove': {
    title: 'Ortalama Rapor Hareketi',
    desc: 'Son 4 çeyrek raporunda, rapor günü ve ertesi gün fiyatın ortalama ne kadar hareket ettiği.',
    source: 'Bizim hesaplama',
    reliability: 'medium',
    ranges: [
      {label:'Pozitif (>%5)',color:'green',desc:'Şirket genellikle beklentiyi aşıyor'},
      {label:'Nötr (%0-5)',color:'yellow',desc:'Karışık geçmiş'},
      {label:'Negatif',color:'red',desc:'Rapor döneminde fiyat genellikle düşüyor — dikkat'}
    ],
    canslim: 'C kriteri — kazanç sürprizi geçmişi'
  }
};

function showInfo(key,event){
  if(event) event.stopPropagation();
  var m=METRICS[key]; if(!m) return;
  var relLabel=m.reliability==="high"?"Güvenilir":m.reliability==="medium"?"Orta Güvenilir":"Kaba Tahmin";
  var h='<div class="minfo-title">'+m.title+'</div>';
  h+='<div class="minfo-source"><span style="color:var(--muted)">'+m.source+'</span><span class="minfo-rel '+m.reliability+'">'+relLabel+'</span></div>';
  h+='<div class="minfo-desc">'+m.desc+'</div>';
  if(m.warning) h+='<div class="minfo-warning">⚠️ '+m.warning+'</div>';
  if(m.ranges&&m.ranges.length){
    h+='<div class="minfo-ranges"><div class="minfo-range-title">Referans Degerler</div>';
    m.ranges.forEach(function(r){var dc=r.color==="green"?"#10b981":r.color==="red"?"#ef4444":"#f59e0b";h+='<div class="minfo-range"><div class="minfo-range-dot" style="background:'+dc+'"></div><div><div style="font-size:11px;font-weight:600;color:'+dc+'">'+r.label+'</div><div style="font-size:10px;color:var(--muted)">'+r.desc+'</div></div></div>';});
    h+='</div>';
  }
  if(m.canslim) h+='<div class="minfo-canslim">📊 CANSLIM: '+m.canslim+'</div>';
  document.getElementById("minfoContent").innerHTML=h;
  document.getElementById("minfoPopup").classList.add("open");
}
function closeInfoPopup(e){if(!e||e.target===document.getElementById("minfoPopup")){document.getElementById("minfoPopup").classList.remove("open");}}

</script>
<script>
var TF_DATA=%%TF_DATA%%;
var PORT=%%PORT%%;
var EARNINGS_DATA=%%EARNINGS_DATA%%;
var MARKET_DATA=%%MARKET_DATA%%;
var NEWS_DATA=%%NEWS_DATA%%;
var curTab="all",curTf="1d",curData=TF_DATA["1d"].slice();
var miniCharts={},mChart=null;
var SS={
  "GUCLU AL":{bg:"rgba(16,185,129,.12)",bd:"rgba(16,185,129,.35)",tx:"#10b981",ac:"#10b981",lbl:"GUCLU AL"},
  "AL":{bg:"rgba(52,211,153,.1)",bd:"rgba(52,211,153,.3)",tx:"#34d399",ac:"#34d399",lbl:"AL"},
  "DIKKAT":{bg:"rgba(245,158,11,.1)",bd:"rgba(245,158,11,.3)",tx:"#f59e0b",ac:"#f59e0b",lbl:"DIKKAT"},
  "ZAYIF":{bg:"rgba(107,114,128,.1)",bd:"rgba(107,114,128,.3)",tx:"#9ca3af",ac:"#6b7280",lbl:"ZAYIF"},
  "SAT":{bg:"rgba(239,68,68,.12)",bd:"rgba(239,68,68,.35)",tx:"#ef4444",ac:"#ef4444",lbl:"SAT"}
};

function ib(key,label){
  return label+' <span class="minfo" onclick="showInfo(\\''+key+'\\',event)">?</span>';
}

function setTab(t,el){
  curTab=t;
  document.querySelectorAll(".tab").forEach(function(b){b.classList.remove("active");});
  el.classList.add("active");
  var tfRow=document.getElementById("tfRow");
  if(tfRow) tfRow.style.display=(t==="dashboard"||t==="earnings")?"none":"flex";
  if(t==="dashboard") renderDashboard();
  else if(t==="earnings") renderEarnings();
  else renderGrid();
}

function setTf(tf,el){
  curTf=tf;
  document.querySelectorAll(".tf-btn").forEach(function(b){b.classList.toggle("active",b.dataset.tf===tf);});
  curData=(TF_DATA[tf]||TF_DATA["1d"]).slice();
  renderStats();
  renderGrid();
}

function filtered(){
  var d=curData.filter(function(r){return !r.hata;});
  if(curTab==="port") return d.filter(function(r){return PORT.includes(r.ticker);});
  if(curTab==="buy") return d.filter(function(r){return r.sinyal==="GUCLU AL"||r.sinyal==="AL";});
  if(curTab==="sell") return d.filter(function(r){return r.sinyal==="SAT";});
  return d;
}

function renderStats(){
  var d=curData.filter(function(r){return !r.hata;});
  var cnt={};
  d.forEach(function(r){cnt[r.sinyal]=(cnt[r.sinyal]||0)+1;});
  document.getElementById("stats").innerHTML=
    '<div class="pill g"><div class="dot"></div>Guclu Al: '+(cnt["GUCLU AL"]||0)+'</div>'+
    '<div class="pill g"><div class="dot"></div>Al: '+(cnt["AL"]||0)+'</div>'+
    '<div class="pill y"><div class="dot"></div>Dikkat: '+(cnt["DIKKAT"]||0)+'</div>'+
    '<div class="pill r"><div class="dot"></div>Sat: '+(cnt["SAT"]||0)+'</div>'+
    '<div class="pill b" style="margin-left:auto"><div class="dot"></div>Portfolyo: '+PORT.length+'</div>'+
    '<div class="pill m"><div class="dot"></div>'+d.length+' analiz</div>';
}

function renderGrid(){
  Object.values(miniCharts).forEach(function(c){c.destroy();});
  miniCharts={};
  var f=filtered();
  var grid=document.getElementById("grid");
  if(!f.length){grid.innerHTML='<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--muted)">Hisse bulunamadi</div>';return;}
  grid.innerHTML=f.map(function(r){return buildCard(r);}).join("");
  f.forEach(function(r){
    var ctx=document.getElementById("mc-"+r.ticker);
    if(ctx&&r.chart_closes&&r.chart_closes.length){
      var ss=SS[r.sinyal]||SS["DIKKAT"];
      miniCharts["m"+r.ticker]=new Chart(ctx,{type:"line",data:{labels:r.chart_dates,datasets:[{data:r.chart_closes,borderColor:ss.ac,borderWidth:1.5,fill:true,backgroundColor:ss.ac+"18",pointRadius:0,tension:0.4}]},options:{plugins:{legend:{display:false}},scales:{x:{display:false},y:{display:false}},animation:{duration:500},responsive:true,maintainAspectRatio:false}});
    }
  });
}

function buildCard(r){
  var ss=SS[r.sinyal]||SS["DIKKAT"];
  var dc=r.degisim>=0?"var(--green2)":"var(--red2)";
  var ds=(r.degisim>=0?"+":"")+r.degisim+"%";
  var escol=r.entry_score>=75?"var(--green)":r.entry_score>=60?"var(--green2)":r.entry_score>=45?"var(--yellow)":r.entry_score>=30?"var(--red2)":"var(--red)";
  var pvcol=r.price_vs_color==="green"?"var(--green)":r.price_vs_color==="yellow"?"var(--yellow)":"var(--red2)";
  var sigs=[
    {l:"Trend",v:r.trend==="Yukselen"?"Yukseliyor":r.trend==="Dusen"?"Dusuyor":"Yatay",g:r.trend==="Yukselen"?true:r.trend==="Dusen"?false:null},
    {l:"SMA50",v:r.above50?"Uzerinde":"Altinda",g:r.above50},
    {l:"SMA200",v:r.above200?"Uzerinde":"Altinda",g:r.above200},
    {l:"RSI",v:r.rsi||"?",g:r.rsi?r.rsi<30?true:r.rsi>70?false:null:null},
    {l:"52W",v:"%"+r.pct_from_52w+" uzak",g:r.near_52w}
  ].map(function(s){return '<span class="sp '+(s.g===true?"sg":s.g===false?"sb":"sn")+'">'+s.l+": "+s.v+"</span>";}).join("");
  return '<div class="card" style="border-color:'+(r.portfolio?"rgba(16,185,129,.25)":ss.bd)+'" onclick="openM(\\''+r.ticker+'\\')">'
    +'<div class="accent" style="background:linear-gradient(90deg,'+ss.ac+','+ss.ac+'88)"></div>'
    +'<div class="cbody"><div class="ctop"><div><div style="display:flex;align-items:center;gap:4px">'
    +'<span class="ticker" style="color:'+ss.tx+'">'+r.ticker+'</span>'
    +(r.portfolio?'<span class="port-badge">P</span>':'')+
    '</div><span class="badge" style="background:'+ss.bg+';color:'+ss.tx+';border:1px solid '+ss.bd+'">'+ss.lbl+'</span></div>'
    +'<div class="cpr"><div class="pval">$'+r.fiyat+'</div><div class="pchg" style="color:'+dc+'">'+ds+'</div>'
    +(r.pe_fwd?'<div style="font-size:9px;color:var(--muted)">FwdPE:'+r.pe_fwd.toFixed(1)+'</div>':'')
    +'</div></div><div class="sigs">'+sigs+'</div>'
    +'<div style="margin-top:6px">'
    +'<div style="display:flex;justify-content:space-between;margin-bottom:3px"><span style="font-size:9px;color:var(--muted)">Giris Kalitesi</span><span style="font-size:11px;font-weight:700;color:'+escol+'">'+r.entry_score+'/100</span></div>'
    +'<div style="height:4px;background:var(--bg3);border-radius:2px;overflow:hidden"><div style="height:100%;width:'+r.entry_score+'%;background:'+escol+';border-radius:2px"></div></div>'
    +'<div style="display:flex;justify-content:space-between;margin-top:3px"><span style="font-size:9px;color:'+escol+'">'+r.entry_label+'</span><span style="font-size:9px;color:'+pvcol+'">'+r.price_vs_ideal+'</span></div>'
    +'</div><div class="chart-w"><canvas id="mc-'+r.ticker+'"></canvas></div>'
    +'<div class="lvls">'
    +'<div class="lv"><div class="ll">Hemen Gir</div><div class="lval" style="color:var(--green2)">$'+r.entry_aggressive+'</div></div>'
    +'<div class="lv"><div class="ll">Hedef</div><div class="lval" style="color:#60a5fa">$'+r.hedef+'</div></div>'
    +'<div class="lv"><div class="ll">Stop</div><div class="lval" style="color:var(--red2)">$'+r.stop+'</div></div>'
    +'</div></div></div>';
}

function renderDashboard(){
  var grid=document.getElementById("grid");
  var md=MARKET_DATA||{};
  var sp=md.SP500||{};
  var nas=md.NASDAQ||{};
  var vix=md.VIX||{};
  var mSignal=md.M_SIGNAL||"NOTR";
  var mLabel=md.M_LABEL||"Veri yok";
  var mColor=mSignal==="GUCLU"?"var(--green)":mSignal==="ZAYIF"?"var(--red2)":"var(--yellow)";
  var mBg=mSignal==="GUCLU"?"rgba(16,185,129,.08)":mSignal==="ZAYIF"?"rgba(239,68,68,.08)":"rgba(245,158,11,.08)";
  var mBorder=mSignal==="GUCLU"?"rgba(16,185,129,.25)":mSignal==="ZAYIF"?"rgba(239,68,68,.25)":"rgba(245,158,11,.25)";
  var mIcon=mSignal==="GUCLU"?"✅":mSignal==="ZAYIF"?"❌":"⚠️";

  function indexCard(name,data){
    if(!data||!data.price) return "";
    var cc=data.change>=0?"var(--green2)":"var(--red2)";
    var cs=(data.change>=0?"+":"")+data.change+"%";
    var s50=data.above50?'<span style="color:var(--green);font-size:10px">SMA50 ✓</span>':'<span style="color:var(--red2);font-size:10px">SMA50 ✗</span>';
    var s200=data.above200?'<span style="color:var(--green);font-size:10px">SMA200 ✓</span>':'<span style="color:var(--red2);font-size:10px">SMA200 ✗</span>';
    return '<div style="background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:14px 16px;flex:1;min-width:150px">'
      +'<div style="font-size:11px;color:var(--muted);margin-bottom:6px">'+name+'</div>'
      +'<div style="font-family:\\'JetBrains Mono\\',monospace;font-size:20px;font-weight:700;color:var(--text)">$'+data.price+'</div>'
      +'<div style="font-family:\\'JetBrains Mono\\',monospace;font-size:13px;color:'+cc+';margin-bottom:8px">'+cs+'</div>'
      +'<div style="display:flex;gap:8px">'+s50+s200+'</div></div>';
  }

  var portData=curData.filter(function(r){return !r.hata&&PORT.includes(r.ticker);});
  var portHtml="";
  if(portData.length){
    portHtml='<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:14px">'
      +'<div style="font-size:11px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:12px">💼 Portföy Özeti</div>'
      +'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px">';
    portData.forEach(function(r){
      var dc=r.degisim>=0?"var(--green2)":"var(--red2)";
      var ss=SS[r.sinyal]||SS["DIKKAT"];
      portHtml+='<div style="background:var(--bg3);border:1px solid '+ss.bd+';border-radius:8px;padding:10px;cursor:pointer" onclick="openM(\\''+r.ticker+'\\')">'
        +'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
        +'<span style="font-family:\\'Bebas Neue\\',sans-serif;font-size:16px;letter-spacing:2px;color:'+ss.tx+'">'+r.ticker+'</span>'
        +'<span style="font-size:9px;background:'+ss.bg+';color:'+ss.tx+';padding:1px 5px;border-radius:2px">'+ss.lbl+'</span></div>'
        +'<div style="font-family:\\'JetBrains Mono\\',monospace;font-size:13px;font-weight:600">$'+r.fiyat+'</div>'
        +'<div style="font-family:\\'JetBrains Mono\\',monospace;font-size:11px;color:'+dc+'">'+(r.degisim>=0?"+":"")+r.degisim+'%</div></div>';
    });
    portHtml+='</div></div>';
  }

  var urgentEarnings=EARNINGS_DATA.filter(function(e){return e.alert==="red"||e.alert==="yellow";});
  var earningsAlert="";
  if(urgentEarnings.length){
    earningsAlert='<div style="background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.2);border-radius:12px;padding:14px 16px;margin-bottom:14px">'
      +'<div style="font-size:11px;color:var(--yellow);letter-spacing:2px;text-transform:uppercase;margin-bottom:10px">⚠️ Yaklaşan Raporlar</div>';
    urgentEarnings.forEach(function(e){
      var ic=e.alert==="red"?"🔴":"🟡";
      earningsAlert+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;font-size:12px">'
        +'<span>'+ic+' <strong>'+e.ticker+'</strong></span>'
        +'<span style="color:var(--muted)">'+e.next_date+' ('+(e.days_to_earnings===0?"BUGÜN":e.days_to_earnings+" gün")+')</span></div>';
    });
    earningsAlert+='</div>';
  }

  var newsHtml='<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px">'
    +'<div style="font-size:11px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:12px">📰 Son Haberler</div>';
  if(NEWS_DATA&&NEWS_DATA.length){
    NEWS_DATA.slice(0,10).forEach(function(n){
      var pb=n.portfolio?'<span style="background:rgba(16,185,129,.12);color:var(--green);border:1px solid rgba(16,185,129,.25);padding:1px 5px;border-radius:3px;font-size:9px;font-weight:600">P</span>':"";
      var ta="";
      if(n.datetime){var diff=Math.floor((Date.now()/1000-n.datetime)/3600);ta=diff<24?(diff+"s önce"):(Math.floor(diff/24)+"g önce");}
      newsHtml+='<div style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,.04)">'
        +'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">'
        +'<span style="font-size:10px;font-weight:700;color:var(--yellow)">'+n.ticker+'</span>'+pb
        +'<span style="font-size:9px;color:var(--muted);margin-left:auto">'+ta+'</span></div>'
        +'<a href="'+n.url+'" target="_blank" style="font-size:12px;color:var(--text);text-decoration:none;line-height:1.5;display:block">'+n.headline+'</a>'
        +'<div style="font-size:10px;color:var(--muted);margin-top:3px">'+n.source+'</div></div>';
    });
  } else {
    newsHtml+='<div style="color:var(--muted);font-size:12px">Haber bulunamadi</div>';
  }
  newsHtml+='</div>';

  grid.innerHTML='<div style="grid-column:1/-1">'
    +'<div style="background:'+mBg+';border:1px solid '+mBorder+';border-radius:12px;padding:16px 20px;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">'
    +'<div><div style="font-size:12px;color:var(--muted);letter-spacing:1px;margin-bottom:4px">CANSLIM M KRİTERİ</div>'
    +'<div style="font-size:18px;font-weight:700;color:'+mColor+'">'+mIcon+' '+mLabel+'</div></div>'
    +'<div style="font-size:10px;color:var(--muted);text-align:right">VIX: '+(vix.price||"?")+'<br>'
    +'<span style="color:'+(vix.price&&vix.price>25?"var(--red2)":"var(--green)")+'">'+(vix.price&&vix.price>25?"Yüksek volatilite":"Normal volatilite")+'</span></div></div>'
    +'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px">'+indexCard("S&P 500 (SPY)",sp)+indexCard("NASDAQ (QQQ)",nas)+'</div>'
    +portHtml+earningsAlert+newsHtml+'</div>';
}

function renderEarnings(){
  var grid=document.getElementById("grid");
  var sorted=EARNINGS_DATA.filter(function(e){return e.next_date;}).sort(function(a,b){
    var da=a.days_to_earnings!=null?a.days_to_earnings:999;
    var db=b.days_to_earnings!=null?b.days_to_earnings:999;
    return da-db;
  });
  var noDate=EARNINGS_DATA.filter(function(e){return !e.next_date;});
  if(!sorted.length&&!noDate.length){grid.innerHTML='<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--muted)">Earnings verisi bulunamadi</div>';return;}
  var h='<div style="grid-column:1/-1">';
  sorted.forEach(function(e){
    var ab=e.alert==="red"?"rgba(239,68,68,.12)":e.alert==="yellow"?"rgba(245,158,11,.1)":"rgba(255,255,255,.02)";
    var abd=e.alert==="red"?"rgba(239,68,68,.35)":e.alert==="yellow"?"rgba(245,158,11,.3)":"rgba(255,255,255,.07)";
    var ai=e.alert==="red"?"🔴":e.alert==="yellow"?"🟡":"📅";
    var dt=e.days_to_earnings!=null?(e.days_to_earnings===0?"BUGUN":e.days_to_earnings===1?"Yarin":e.days_to_earnings+" gun sonra"):"";
    var amCol=e.avg_move_pct!=null?(e.avg_move_pct>=0?"var(--green)":"var(--red2)"):"var(--muted)";
    var amStr=e.avg_move_pct!=null?(e.avg_move_pct>=0?"+":"")+e.avg_move_pct+"%":"—";
    var yb=e.alert==="red"?'<span style="background:rgba(239,68,68,.15);color:var(--red2);padding:2px 8px;border-radius:3px;font-size:10px;font-weight:700">YAKINDA</span>':"";
    h+='<div style="background:'+ab+';border:1px solid '+abd+';border-radius:10px;margin-bottom:10px;padding:14px 16px">';
    h+='<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">';
    h+='<div style="display:flex;align-items:center;gap:10px"><span>'+ai+'</span><span style="font-family:\\'Bebas Neue\\',sans-serif;font-size:20px;letter-spacing:2px;color:var(--text)">'+e.ticker+'</span>'+yb+'</div>';
    h+='<div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center">';
    h+='<div style="text-align:center"><div style="font-size:9px;color:var(--muted)">RAPOR</div><div style="font-family:\\'JetBrains Mono\\',monospace;font-size:12px;font-weight:600;color:var(--text)">'+(e.next_date||"—")+'</div><div style="font-size:10px;color:'+(e.alert==="red"?"var(--red2)":e.alert==="yellow"?"var(--yellow)":"var(--muted)")+'">'+dt+'</div></div>';
    h+='<div style="text-align:center"><div style="font-size:9px;color:var(--muted)">EPS TAHMIN</div><div style="font-family:\\'JetBrains Mono\\',monospace;font-size:12px;font-weight:600;color:#60a5fa">'+(e.eps_estimate!=null?"$"+e.eps_estimate:"—")+'</div></div>';
    h+='<div style="text-align:center"><div style="font-size:9px;color:var(--muted)">ORT.HAREKET</div><div style="font-family:\\'JetBrains Mono\\',monospace;font-size:14px;font-weight:700;color:'+amCol+'">'+amStr+'</div><div style="font-size:8px;color:var(--muted)">son 4 rapor</div></div>';
    h+='</div></div>';
    if(e.history_eps&&e.history_eps.length){
      h+='<div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,.06)"><div style="font-size:9px;color:var(--muted);margin-bottom:5px">SON 4 RAPOR</div><div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px">';
      e.history_eps.forEach(function(hh){
        var sc=hh.surprise_pct!=null?(hh.surprise_pct>0?"var(--green)":"var(--red2)"):"var(--muted)";
        h+='<div style="background:var(--bg3);border-radius:4px;padding:6px;text-align:center;border:1px solid rgba(255,255,255,.05)"><div style="font-size:8px;color:var(--muted)">'+hh.date.substring(0,7)+'</div><div style="font-family:\\'JetBrains Mono\\',monospace;font-size:10px">'+(hh.actual!=null?"$"+hh.actual:"?")+'</div><div style="font-size:9px;color:'+sc+'">'+(hh.surprise_pct!=null?(hh.surprise_pct>0?"+":"")+hh.surprise_pct+"%":"?")+'</div></div>';
      });
      h+='</div></div>';
    }
    h+='</div>';
  });
  if(noDate.length){h+='<div style="font-size:10px;color:var(--muted);margin-top:6px">Tarih bulunamayan: '+noDate.map(function(e){return e.ticker;}).join(", ")+'</div>';}
  h+='</div>';
  grid.innerHTML=h;
}

function openM(ticker){
  var r=curData.find(function(d){return d.ticker===ticker;});
  if(!r||r.hata) return;
  if(mChart){mChart.destroy();mChart=null;}
  var ss=SS[r.sinyal]||SS["DIKKAT"];
  var rrP=Math.min((r.rr/4)*100,100);
  var rrC=r.rr>=3?"var(--green)":r.rr>=2?"var(--green2)":r.rr>=1?"var(--yellow)":"var(--red2)";
  var dc=r.degisim>=0?"var(--green2)":"var(--red2)";
  var kc={"GUCLU AL":"#10b981","AL":"#34d399","DIKKATLI":"#f59e0b","GECME":"#f87171"};
  var klbl={"GUCLU AL":"GUCLU AL","AL":"AL","DIKKATLI":"DIKKATLI","GECME":"GECME"};
  var escol=r.entry_score>=75?"var(--green)":r.entry_score>=60?"var(--green2)":r.entry_score>=45?"var(--yellow)":r.entry_score>=30?"var(--red2)":"var(--red)";
  var pvcol=r.price_vs_color==="green"?"var(--green)":r.price_vs_color==="yellow"?"var(--yellow)":"var(--red2)";

  var mh='<div class="mhead"><div><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
    +'<span class="mtitle" style="color:'+ss.tx+'">'+r.ticker+'</span>'
    +'<span class="badge" style="background:'+ss.bg+';color:'+ss.tx+';border:1px solid '+ss.bd+';font-size:12px">'+ss.lbl+'</span>'
    +(r.portfolio?'<span class="port-badge" style="font-size:11px;padding:3px 8px">Portfolyo</span>':'')
    +'</div><div style="font-size:20px;font-family:\\'JetBrains Mono\\',monospace;font-weight:600;margin-top:4px">$'+r.fiyat
    +' <span style="font-size:12px;color:'+dc+'">'+(r.degisim>=0?"+":"")+r.degisim+'%</span></div></div>'
    +'<button class="mclose" onclick="closeM()">✕</button></div>';

  mh+='<div class="mbody"><div class="mchartw"><canvas id="mchart"></canvas></div>';

  mh+='<div style="background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:12px">'
    +'<div style="font-size:9px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:8px">'+ib("EntryScore","Giris Kalitesi")+'</div>'
    +'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">'
    +'<span style="font-size:22px;font-weight:700;font-family:\\'JetBrains Mono\\',monospace;color:'+escol+'">'+r.entry_score+'<span style="font-size:13px;color:var(--muted)">/100</span></span>'
    +'<span style="font-size:13px;font-weight:600;color:'+escol+'">'+r.entry_label+'</span></div>'
    +'<div style="height:6px;background:var(--bg2);border-radius:3px;overflow:hidden;margin-bottom:8px"><div style="height:100%;width:'+r.entry_score+'%;background:'+escol+';border-radius:3px"></div></div>'
    +'<div style="display:flex;justify-content:space-between;font-size:11px">'
    +'<div><span style="color:var(--muted)">Su anki fiyat: </span><span style="color:'+pvcol+';font-weight:600">'+r.price_vs_ideal+'</span></div>'
    +'<div><span style="color:var(--muted)">Ideal bolge: </span><span style="color:var(--green2);font-family:\\'JetBrains Mono\\',monospace">$'+r.ideal_entry_low+' - $'+r.ideal_entry_high+'</span></div>'
    +'</div></div>';

  mh+='<div class="dbox" style="background:'+ss.bg+';border-color:'+ss.bd+';margin-bottom:12px">'
    +'<div class="dlbl" style="color:'+ss.tx+'">'+ib("RR","Alim Karari R/R")+'</div>'
    +'<div class="dverd" style="color:'+(kc[r.karar]||"var(--muted)")+'">'+(klbl[r.karar]||r.karar)+'</div>'
    +'<div class="drow"><span class="dkey">Risk / Odul</span><span style="color:'+rrC+';font-weight:700;font-family:\\'JetBrains Mono\\',monospace">1 : '+r.rr+'</span></div>'
    +'<div class="drow"><span class="dkey">Hemen Gir</span><span style="color:var(--green2);font-family:\\'JetBrains Mono\\',monospace">$'+r.entry_aggressive+'</span></div>'
    +'<div class="drow"><span class="dkey">Geri Cekilme</span><span style="color:#60a5fa;font-family:\\'JetBrains Mono\\',monospace">$'+r.entry_mid+'</span></div>'
    +'<div class="drow"><span class="dkey">Buyuk Duzeltme</span><span style="color:var(--yellow);font-family:\\'JetBrains Mono\\',monospace">$'+r.entry_conservative+'</span></div>'
    +'<div class="drow"><span class="dkey">Hedef</span><span style="color:#60a5fa;font-family:\\'JetBrains Mono\\',monospace">$'+r.hedef+'</span></div>'
    +'<div class="drow"><span class="dkey">Stop-Loss</span><span style="color:var(--red2);font-family:\\'JetBrains Mono\\',monospace">$'+r.stop+'</span></div>'
    +'<div class="rrbar"><div class="rrfill" style="width:'+rrP+'%;background:'+rrC+'"></div></div></div>';

  mh+='<div style="font-size:9px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:8px">Teknik Analiz</div>'
    +'<div class="dgrid" style="margin-bottom:12px">'
    +'<div class="dc"><div class="dl">'+ib("Trend","Trend")+'</div><div class="dv" style="color:'+(r.trend==="Yukselen"?"var(--green)":r.trend==="Dusen"?"var(--red)":"var(--muted)")+'">'+r.trend+'</div></div>'
    +'<div class="dc"><div class="dl">'+ib("RSI","RSI 14")+'</div><div class="dv" style="color:'+(r.rsi?r.rsi<30?"var(--green)":r.rsi>70?"var(--red)":"var(--yellow)":"var(--muted)")+'">'+(r.rsi||"?")+(r.rsi?r.rsi<30?" Asiri Satim":r.rsi>70?" Asiri Alim":" Notr":"")+'</div></div>'
    +'<div class="dc"><div class="dl">'+ib("SMA50","SMA 50")+'</div><div class="dv" style="color:'+(r.above50?"var(--green)":"var(--red)")+'">'+(r.above50?"Uzerinde":"Altinda")+(r.sma50_dist!=null?" ("+r.sma50_dist+"%)":"")+'</div></div>'
    +'<div class="dc"><div class="dl">'+ib("SMA200","SMA 200")+'</div><div class="dv" style="color:'+(r.above200?"var(--green)":"var(--red)")+'">'+(r.above200?"Uzerinde":"Altinda")+(r.sma200_dist!=null?" ("+r.sma200_dist+"%)":"")+'</div></div>'
    +'<div class="dc"><div class="dl">'+ib("52W","52H Poz.")+'</div><div class="dv" style="color:'+(r.w52_position<=30?"var(--green)":r.w52_position>=85?"var(--red)":"var(--yellow)")+'">'+r.w52_position+'%</div></div>'
    +'<div class="dc"><div class="dl">'+ib("Hacim","Hacim")+'</div><div class="dv" style="color:'+(r.hacim==="Yuksek"?"var(--green)":r.hacim==="Dusuk"?"var(--red)":"var(--muted)")+'">'+r.hacim+' ('+r.vol_ratio+'x)</div></div>'
    +'</div>';

  mh+='<div style="font-size:9px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:8px">Temel Analiz</div>'
    +'<div class="dgrid" style="margin-bottom:12px">'
    +'<div class="dc"><div class="dl">'+ib("ForwardPE","Forward PE")+'</div><div class="dv" style="color:'+(r.pe_fwd?r.pe_fwd<25?"var(--green)":r.pe_fwd<40?"var(--yellow)":"var(--red)":"var(--muted)")+'">'+(r.pe_fwd?r.pe_fwd.toFixed(1):"?")+'</div></div>'
    +'<div class="dc"><div class="dl">'+ib("PEG","PEG")+'</div><div class="dv" style="color:'+(r.peg?r.peg<1?"var(--green)":r.peg<2?"var(--yellow)":"var(--red)":"var(--muted)")+'">'+(r.peg?r.peg.toFixed(2):"?")+'</div></div>'
    +'<div class="dc"><div class="dl">'+ib("EPSGrowth","EPS Büyüme")+'</div><div class="dv" style="color:'+(r.eps_growth?r.eps_growth>=20?"var(--green)":r.eps_growth>=0?"var(--yellow)":"var(--red)":"var(--muted)")+'">'+(r.eps_growth!=null?r.eps_growth+"%":"?")+'</div></div>'
    +'<div class="dc"><div class="dl">'+ib("RevGrowth","Gelir Büyüme")+'</div><div class="dv" style="color:'+(r.rev_growth?r.rev_growth>=15?"var(--green)":r.rev_growth>=0?"var(--yellow)":"var(--red)":"var(--muted)")+'">'+(r.rev_growth!=null?r.rev_growth+"%":"?")+'</div></div>'
    +'<div class="dc"><div class="dl">'+ib("NetMargin","Net Marjin")+'</div><div class="dv" style="color:'+(r.net_margin?r.net_margin>=15?"var(--green)":r.net_margin>=5?"var(--yellow)":"var(--red)":"var(--muted)")+'">'+(r.net_margin!=null?r.net_margin+"%":"?")+'</div></div>'
    +'<div class="dc"><div class="dl">'+ib("ROE","ROE")+'</div><div class="dv" style="color:'+(r.roe?r.roe>=15?"var(--green)":r.roe>=5?"var(--yellow)":"var(--red)":"var(--muted)")+'">'+(r.roe!=null?r.roe+"%":"?")+'</div></div>'
    +'</div>';

  mh+='<div style="font-size:10px;color:var(--muted);text-align:center">Bu arac yatirim tavsiyesi degildir</div></div>';

  document.getElementById("modal").innerHTML=mh;
  document.getElementById("overlay").classList.add("open");
  setTimeout(function(){
    var ctx=document.getElementById("mchart");
    if(ctx&&r.chart_closes){
      mChart=new Chart(ctx,{type:"line",data:{labels:r.chart_dates,datasets:[
        {label:"Fiyat",data:r.chart_closes,borderColor:ss.ac,borderWidth:2,fill:true,backgroundColor:ss.ac+"20",pointRadius:0,tension:0.3},
        r.sma50?{label:"SMA50",data:Array(r.chart_closes.length).fill(r.sma50),borderColor:"#f59e0b",borderWidth:1.5,borderDash:[5,5],pointRadius:0,fill:false}:null,
        r.sma200?{label:"SMA200",data:Array(r.chart_closes.length).fill(r.sma200),borderColor:"#8b5cf6",borderWidth:1.5,borderDash:[5,5],pointRadius:0,fill:false}:null
      ].filter(Boolean)},options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{labels:{color:"#6b7280",font:{size:10}}}},
        scales:{x:{display:true,ticks:{color:"#374151",maxTicksLimit:5,font:{size:9}},grid:{color:"rgba(255,255,255,.04)"}},
          y:{display:true,ticks:{color:"#374151",font:{size:9}},grid:{color:"rgba(255,255,255,.04)"}}}}});
    }
  },100);
}

function closeM(e){
  if(!e||e.target===document.getElementById("overlay")){
    document.getElementById("overlay").classList.remove("open");
    if(mChart){mChart.destroy();mChart=null;}
  }
}

renderStats();
renderDashboard();



// ── LİSTE DÜZENLEME ───────────────────────────────────────────
var editWatchlist = [];
var editPortfolio = [];

function openEditList(){
  editWatchlist = TF_DATA['1d'].filter(function(r){return !r.hata;}).map(function(r){return r.ticker;});
  editPortfolio = PORT.slice();
  renderEditLists();
  document.getElementById("editPopup").classList.add("open");
}

function closeEditPopup(e){
  if(!e||e.target===document.getElementById("editPopup")){
    document.getElementById("editPopup").classList.remove("open");
  }
}

function renderEditLists(){
  var we = document.getElementById("watchlistEditor");
  var pe = document.getElementById("portfolioEditor");
  if(!we||!pe) return;

  we.innerHTML = editWatchlist.map(function(t,i){
    return '<div style="display:flex;align-items:center;justify-content:space-between;padding:5px 8px;background:var(--bg3);border:1px solid var(--border);border-radius:5px;margin-bottom:4px">'
      +'<span style="font-family:\\'JetBrains Mono\\',monospace;font-size:12px;font-weight:600">'+t+'</span>'
      +'<button onclick="removeTicker(\\'watch\\','+i+')" style="background:rgba(239,68,68,.15);border:none;color:var(--red2);width:20px;height:20px;border-radius:4px;cursor:pointer;font-size:12px">✕</button>'
      +'</div>';
  }).join('');

  pe.innerHTML = editPortfolio.map(function(t,i){
    return '<div style="display:flex;align-items:center;justify-content:space-between;padding:5px 8px;background:var(--bg3);border:1px solid rgba(16,185,129,.2);border-radius:5px;margin-bottom:4px">'
      +'<span style="font-family:\\'JetBrains Mono\\',monospace;font-size:12px;font-weight:600;color:var(--green)">'+t+'</span>'
      +'<button onclick="removeTicker(\\'port\\','+i+')" style="background:rgba(239,68,68,.15);border:none;color:var(--red2);width:20px;height:20px;border-radius:4px;cursor:pointer;font-size:12px">✕</button>'
      +'</div>';
  }).join('');
}

function addTicker(list){
  var inputId = list==='watch'?"newWatchTicker":"newPortTicker";
  var val = document.getElementById(inputId).value.trim().toUpperCase();
  if(!val) return;
  if(list==='watch' && !editWatchlist.includes(val)) editWatchlist.push(val);
  if(list==='port'  && !editPortfolio.includes(val)) editPortfolio.push(val);
  document.getElementById(inputId).value = "";
  renderEditLists();
}

function removeTicker(list, idx){
  if(list==='watch') editWatchlist.splice(idx,1);
  else editPortfolio.splice(idx,1);
  renderEditLists();
}

function saveListToGithub(){
  var token = document.getElementById("ghTokenInput").value.trim();
  if(!token){ setEditStatus("❌ GitHub Token gerekli","red"); return; }

  var config = { watchlist: editWatchlist, portfolio: editPortfolio };
  var content = JSON.stringify(config, null, 2);
  var b64 = btoa(unescape(encodeURIComponent(content)));

  setEditStatus("💾 Kaydediliyor...","yellow");

  var apiUrl = "https://api.github.com/repos/ghurzzz/canslim/contents/config.json";
  var headers = {"Authorization":"token "+token,"Content-Type":"application/json"};

  // First get current SHA if exists
  fetch(apiUrl, {headers:headers})
    .then(function(r){ return r.ok ? r.json() : null; })
    .then(function(existing){
      var payload = {
        message: "Liste guncellendi " + new Date().toLocaleDateString("tr-TR"),
        content: b64
      };
      if(existing && existing.sha) payload.sha = existing.sha;

      return fetch(apiUrl, {
        method:"PUT",
        headers:headers,
        body:JSON.stringify(payload)
      });
    })
    .then(function(r){
      if(r.ok || r.status===201){
        setEditStatus("✅ Kaydedildi! Bir sonraki Colab çalıştırmasında aktif olur.","green");
        setTimeout(function(){closeEditPopup();},2000);
      } else {
        setEditStatus("❌ Hata: "+r.status+" — Token'ı kontrol et","red");
      }
    })
    .catch(function(e){ setEditStatus("❌ Hata: "+e.message,"red"); });
}

function setEditStatus(msg, color){
  var el = document.getElementById("editStatus");
  if(el){
    el.textContent = msg;
    el.style.color = color==="green"?"var(--green)":color==="red"?"var(--red2)":"var(--yellow)";
  }
}

</script>
</body>
</html>"""

# ── UPLOAD ────────────────────────────────────────────────────
def upload_to_github(html_content):
    import urllib.request, urllib.error, json as _json, time
    api_url = f'https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}'
    
    # GitHub Actions'da GITHUB_TOKEN env variable'i override edilebilir
    # SCANNER_TOKEN kullan
    token = os.environ.get('SCANNER_TOKEN', os.environ.get('GITHUB_TOKEN', GITHUB_TOKEN))
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json"
    }
    
    content_b64 = _b64.b64encode(html_content.encode("utf-8")).decode("utf-8")
    
    for attempt in range(5):
        # Her denemede fresh SHA al
        sha = None
        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req) as resp:
                data = _json.loads(resp.read())
                sha = data.get("sha")
                print(f"  SHA: {sha[:8] if sha else 'None'}...")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("  Dosya yok, yeni olusturulacak")
            else:
                print(f"  SHA hatasi {e.code}: {e.read().decode()[:100]}")
        
        payload = {
            "message": f"CANSLIM {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            "content": content_b64,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
        
        try:
            data = _json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(api_url, data=data, headers=headers, method="PUT")
            with urllib.request.urlopen(req) as resp:
                result = _json.loads(resp.read())
                print(f"  Yuklendi: {result.get('content', {}).get('name', 'OK')}")
                return True
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"  Deneme {attempt+1} hatasi {e.code}: {body[:200]}")
            if e.code == 409:
                print(f"  409 Conflict - 3 saniye bekleniyor...")
                time.sleep(3)
                continue
            else:
                raise
    
    return False


def build_html(tf_data, timestamp, earnings_data=None, market_data=None, news_data=None):
    tf_json       = json.dumps(tf_data, ensure_ascii=False)
    earnings_json = json.dumps(earnings_data or [], ensure_ascii=False)
    market_json   = json.dumps(market_data   or {}, ensure_ascii=False)
    news_json     = json.dumps(news_data     or [], ensure_ascii=False)
    port_json     = json.dumps(PORTFOLIO, ensure_ascii=False)
    html = get_html_template()
    html = html.replace("%%TIMESTAMP%%", timestamp)
    html = html.replace("%%TF_DATA%%",   tf_json)
    html = html.replace("%%EARNINGS_DATA%%", earnings_json)
    html = html.replace("%%MARKET_DATA%%",   market_json)
    html = html.replace("%%NEWS_DATA%%",     news_json)
    html = html.replace("%%PORT%%",          port_json)
    html = html.replace("%%GITHUB_TOKEN%%",  "")
    html = html.replace("%%GITHUB_USER%%",  GITHUB_USER)
    html = html.replace("%%GITHUB_REPO%%",  GITHUB_REPO)
    return html

# ── MAIN ──────────────────────────────────────────────────────
timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
print("\n📊 HTML olusturuluyor...")
html = build_html(tf_data, timestamp, earnings_data, market_data, news_data)
print("📤 GitHub'a yukleniyor...")
try:
    ok = upload_to_github(html)
    if ok:
        print(f"\n✅ Basarili! https://{GITHUB_USER}.github.io/{GITHUB_REPO}")
    else:
        print("❌ Yukleme basarisiz")
        sys.exit(1)
except Exception as e:
    print(f"❌ Hata: {e}")
    sys.exit(1)
