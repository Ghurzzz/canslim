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
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY', '')
GMAIL_USER   = os.environ.get('GMAIL_USER', 'gursanbkr@gmail.com')
GMAIL_PASS   = os.environ.get('GMAIL_PASS', 'dmsg nmfo ezju hgep')

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
        eps_growth_fwd = safe('earningsGrowth')  # Forward yillik buyume tahmini
        rev_growth     = safe('revenueGrowth')
        net_margin     = safe('profitMargins')
        roe            = safe('returnOnEquity')
        gross_margin   = safe('grossMargins')
        eps_fwd        = safe('forwardEps')
        eps_ttm        = safe('trailingEps')
        sector         = info.get('sector', '')
        analyst_target = safe('targetMeanPrice')

        if eps_growth     is not None: eps_growth     = round(eps_growth     * 100, 1)
        if eps_growth_fwd is not None: eps_growth_fwd = round(eps_growth_fwd * 100, 1)
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
        # ── Pro Hedef Fiyat (4 yontem agirlikli ortalama) ────────────
        target_components = []
        target_weights    = []
        target_details    = {}

        # Yontem 1: Analist Konsensus (%40)
        if analyst_target and analyst_target > price:
            target_components.append(float(analyst_target))
            target_weights.append(0.40)
            target_details['Analist'] = round(analyst_target, 2)

        # Yontem 2: Forward P/E x Sektor P/E (%30)
        sector_median_pe = {
            'Technology': 32, 'Semiconductors': 28, 'Software': 38,
            'Communication Services': 24, 'Consumer Cyclical': 22,
            'Healthcare': 25, 'Financial Services': 14, 'Energy': 13,
            'Industrials': 20, 'Materials': 18,
        }
        ref_pe = sector_median_pe.get(sector, 25)
        # En iyi buyume verisini kullan: ceyreklik, yoksa yillik forward
        best_growth = eps_growth if eps_growth else eps_growth_fwd
        if eps_fwd and eps_fwd > 0:
            growth_premium = 1.0
            if best_growth and best_growth > 0:
                if   best_growth >= 30: growth_premium = 1.20
                elif best_growth >= 20: growth_premium = 1.10
                elif best_growth >= 10: growth_premium = 1.05
            fwd_pe_target = round(eps_fwd * ref_pe * growth_premium, 2)
            if fwd_pe_target > price:
                target_components.append(fwd_pe_target)
                target_weights.append(0.30)
                target_details['Fwd P/E'] = fwd_pe_target

        # Yontem 3: PEG Bazlı (%20)
        if eps_fwd and eps_fwd > 0 and best_growth and best_growth > 10:
            peg_target_pe = min(best_growth, 50)
            peg_target = round(eps_fwd * peg_target_pe, 2)
            if peg_target > price:
                target_components.append(peg_target)
                target_weights.append(0.20)
                target_details['PEG'] = peg_target

        # Yontem 4: P/S Bazlı (%10)
        sector_median_ps = {
            'Technology': 8, 'Semiconductors': 7, 'Software': 12,
            'Communication Services': 5, 'Consumer Cyclical': 2, 'Healthcare': 4,
        }
        ref_ps = sector_median_ps.get(sector, 5)
        if ps and ps > 0:
            rev_per_share = price / ps
            ps_target = round(rev_per_share * ref_ps, 2)
            if ps_target > price:
                target_components.append(ps_target)
                target_weights.append(0.10)
                target_details['P/S'] = ps_target

        # Agirlikli ortalama
        if target_components:
            total_w = sum(target_weights)
            norm_w  = [w/total_w for w in target_weights]
            target_price = round(sum(t*w for t,w in zip(target_components, norm_w)), 2)
            target_price = min(target_price, price * 2.0)   # max 2x cap
            target_price = max(target_price, round(price * 1.05, 2))  # min %5 upside
        else:
            target_price = round(high52w * 0.99, 2) if high52w > price else round(price * 1.15, 2)
            target_details['52W High'] = target_price
        
        # Debug: hangi yontemler kullanildi
        if target_details:
            methods_str = ', '.join([f"{k}:${v}" for k,v in target_details.items()])
        else:
            methods_str = 'yok'

        # Her senaryo için R/R hesapla
        def calc_rr(entry, target, atr_val=None, multiplier=2.0):
            # ATR bazlı stop: giriş - (ATR x çarpan)
            # ATR yoksa volatilite bazlı fallback
            if atr_val and atr_val > 0:
                stop = round(entry - (atr_val * multiplier), 2)
            else:
                # ATR yoksa 52W pozisyona göre dinamik %
                if w52_position >= 70:
                    stop_pct = 0.08  # Zirveye yakın: daha geniş stop
                elif w52_position >= 40:
                    stop_pct = 0.07  # Orta: standart
                else:
                    stop_pct = 0.06  # Dipte: daha dar stop
                stop = round(entry * (1 - stop_pct), 2)
            
            # Stop mantik kontrolu
            stop = max(stop, round(entry * 0.85, 2))  # Max %15 risk
            stop = min(stop, round(entry * 0.95, 2))  # Min %5 risk
            
            if entry <= 0 or target <= entry or entry <= stop:
                return stop, 0
            rr = round((target - entry) / (entry - stop), 2)
            return stop, rr

        stop_agg,  rr_agg  = calc_rr(entry_aggressive,   target_price, atr)
        stop_mid,  rr_mid  = calc_rr(entry_mid,           target_price, atr)
        stop_cons, rr_cons = calc_rr(entry_conservative,  target_price, atr)

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
            'target_details': target_details,
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



# ── AI ANALİZ (Claude Sonnet 4.6) ─────────────────────────────
def get_ai_analysis(ticker, data, news_list):
    """Hisse için Claude API ile AI analizi yap"""
    if not ANTHROPIC_KEY:
        return None
    
    import urllib.request, json as _json
    
    # Hisse verisini özetle
    news_headlines = [n.get('headline','') for n in news_list[:3] if n.get('ticker')==ticker]
    
    prompt = f"""Sen bir CANSLIM metodolojisi uzmanısın. Aşağıdaki verilere göre {ticker} hissesi için kısa bir analiz yap.

Teknik Durum:
- Fiyat: ${data.get('fiyat')}
- Sinyal: {data.get('sinyal')}
- RSI: {data.get('rsi')}
- SMA50 Üzerinde: {data.get('above50')}
- SMA200 Üzerinde: {data.get('above200')}
- Giriş Kalitesi: {data.get('entry_score')}/100

Temel Veriler:
- EPS Büyüme: {data.get('eps_growth')}%
- Gelir Büyüme: {data.get('rev_growth')}%
- Forward P/E: {data.get('pe_fwd')}
- Net Marjin: {data.get('net_margin')}%

Son Haberler:
{chr(10).join(news_headlines) if news_headlines else 'Haber yok'}

Giriş seviyeleri:
- Hemen Gir: ${data.get('entry_aggressive')}
- Hedef: ${data.get('hedef')}
- Stop: ${data.get('stop')}

Lütfen şunları yaz:
1. Genel durum (1 cümle)
2. Güçlü yönler (max 2 madde)
3. Riskler (max 2 madde)
4. Tavsiye (AL/BEKLE/SATMA - 1 cümle)

Türkçe, kısa ve net yaz. Toplam 100 kelimeyi geçme."""

    try:
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=_json.dumps(payload).encode('utf-8'),
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = _json.loads(resp.read())
            return result['content'][0]['text']
    except Exception as e:
        print(f"  AI analiz hatasi {ticker}: {e}")
        return None

# ── EMAIL ALARM ───────────────────────────────────────────────
def send_alarm_email(alerts):
    if not alerts or not GMAIL_USER or not GMAIL_PASS:
        return
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Email icerigi olustur
        subject = f"📊 CANSLIM Fiyat Alarmi — {len(alerts)} sinyal"
        
        html_body = """
        <html><body style="font-family:Arial,sans-serif;background:#0d1117;color:#e2e8f0;padding:20px">
        <h2 style="color:#10b981">📊 CANSLIM Fiyat Alarmlari</h2>
        """
        
        for a in alerts:
            color = "#10b981" if a['type'] == 'buy' else "#ef4444" if a['type'] == 'stop' else "#60a5fa"
            icon = "🟢" if a['type'] == 'buy' else "⚠️" if a['type'] == 'stop' else "🎯"
            html_body += f"""
            <div style="background:#161b24;border:1px solid {color};border-radius:8px;padding:16px;margin-bottom:12px">
                <h3 style="color:{color};margin:0 0 8px 0">{icon} {a['ticker']} — {a['message']}</h3>
                <p style="margin:4px 0">Guncel Fiyat: <strong>${a['price']}</strong></p>
                <p style="margin:4px 0">Seviye: <strong>${a['level']}</strong></p>
                {"<p style='color:#10b981'>Portfoyunuzde var</p>" if a.get('portfolio') else ""}
            </div>
            """
        
        html_body += f"""
        <p style="color:#4b5563;font-size:12px">Bu e-posta CANSLIM Scanner tarafindan otomatik gonderilmistir.<br>
        Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
        </body></html>
        """
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER
        msg.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        
        print(f"  ✅ Email gonderildi: {len(alerts)} alarm")
    except Exception as e:
        print(f"  ❌ Email hatasi: {e}")

def check_alarms(tf_data, portfolio):
    alerts = []
    data_1d = tf_data.get('1d', [])
    
    for r in data_1d:
        if r.get('hata'):
            continue
        
        price = r.get('fiyat', 0)
        ticker = r.get('ticker', '')
        is_portfolio = ticker in portfolio
        
        # Hemen Gir seviyesine dusmus mu?
        entry_agg = r.get('entry_aggressive')
        if entry_agg and price <= entry_agg * 1.02:
            alerts.append({
                'type': 'buy',
                'ticker': ticker,
                'price': price,
                'level': entry_agg,
                'message': 'Hemen Gir seviyesine ulasti!',
                'portfolio': is_portfolio
            })
        
        # Geri cekilme seviyesine dusmus mu?
        entry_mid = r.get('entry_mid')
        if entry_mid and price <= entry_mid * 1.02 and (not entry_agg or price < entry_agg * 0.98):
            alerts.append({
                'type': 'buy',
                'ticker': ticker,
                'price': price,
                'level': entry_mid,
                'message': 'Geri Cekilme seviyesine ulasti',
                'portfolio': is_portfolio
            })
        
        # Hedef fiyata ulasti mi?
        hedef = r.get('hedef')
        if hedef and price >= hedef * 0.98:
            alerts.append({
                'type': 'target',
                'ticker': ticker,
                'price': price,
                'level': hedef,
                'message': 'Hedef fiyata ulasti!',
                'portfolio': is_portfolio
            })
        
        # Stop seviyesine dusmus mu? (sadece portfolyo)
        if is_portfolio:
            stop = r.get('stop')
            if stop and price <= stop * 1.02:
                alerts.append({
                    'type': 'stop',
                    'ticker': ticker,
                    'price': price,
                    'level': stop,
                    'message': 'STOP seviyesine dusuu! Dikkat!',
                    'portfolio': True
                })
    
    return alerts

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

# ── ALARM KONTROLU ─────────────────────────────────────────────
print('\n🔔 Alarm kontrolu yapiliyor...')
alerts = check_alarms(tf_data, PORTFOLIO)
if alerts:
    print(f'  {len(alerts)} alarm bulundu:')
    for a in alerts:
        print(f"  {'🟢' if a['type']=='buy' else '⚠️' if a['type']=='stop' else '🎯'} {a['ticker']}: {a['message']} (${a['price']})")
    send_alarm_email(alerts)
else:
    print('  Alarm yok')

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

# ── HAFTALIK PERFORMANS VERİSİ ────────────────────────────────
print('\n📈 Haftalik performans verisi cekiliyor...')
def get_weekly_performance(watchlist, portfolio):
    weekly = {}
    for ticker in watchlist:
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period='1mo')
            if hist.empty or len(hist) < 2:
                continue
            closes = hist['Close'].dropna()
            
            # Bu hafta performans (5 gun)
            week_start = float(closes.iloc[-6]) if len(closes) >= 6 else float(closes.iloc[0])
            week_end   = float(closes.iloc[-1])
            week_chg   = round((week_end - week_start) / week_start * 100, 2)
            
            # Onceki hafta
            prev_start = float(closes.iloc[-11]) if len(closes) >= 11 else float(closes.iloc[0])
            prev_end   = float(closes.iloc[-6]) if len(closes) >= 6 else float(closes.iloc[-1])
            prev_chg   = round((prev_end - prev_start) / prev_start * 100, 2)
            
            # Son 4 hafta
            month_start = float(closes.iloc[0])
            month_chg   = round((week_end - month_start) / month_start * 100, 2)
            
            weekly[ticker] = {
                'ticker': ticker,
                'price': round(week_end, 2),
                'week_chg': week_chg,
                'prev_week_chg': prev_chg,
                'month_chg': month_chg,
                'portfolio': ticker in portfolio
            }
        except Exception as e:
            print(f'  Haftalik veri hatasi {ticker}: {e}')
    
    # Sirala
    port_items = sorted([v for v in weekly.values() if v['portfolio']], key=lambda x: x['week_chg'], reverse=True)
    watch_items = sorted([v for v in weekly.values() if not v['portfolio']], key=lambda x: x['week_chg'], reverse=True)
    
    return {
        'portfolio': port_items,
        'watchlist': watch_items,
        'best': max(weekly.values(), key=lambda x: x['week_chg']) if weekly else None,
        'worst': min(weekly.values(), key=lambda x: x['week_chg']) if weekly else None,
        'generated': datetime.now().strftime('%d.%m.%Y %H:%M')
    }

weekly_data = get_weekly_performance(WATCHLIST, PORTFOLIO)
print(f'  {len(weekly_data.get("portfolio",[]))} portföy + {len(weekly_data.get("watchlist",[]))} watchlist verisi alindi')

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
    import base64 as _b64t
    _T = "PCFET0NUWVBFIGh0bWw+CjxodG1sIGxhbmc9InRyIj4KPGhlYWQ+CjxtZXRhIGNoYXJzZXQ9IlVURi04Ii8+CjxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsaW5pdGlhbC1zY2FsZT0xIi8+Cjx0aXRsZT5DQU5TTElNIFNjYW5uZXI8L3RpdGxlPgo8bGluayByZWw9Imljb24iIHR5cGU9ImltYWdlL3N2Zyt4bWwiIGhyZWY9ImRhdGE6aW1hZ2Uvc3ZnK3htbCwlM0NzdmcgeG1sbnM9J2h0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnJyB2aWV3Qm94PScwIDAgMzIgMzInJTNFJTNDcmVjdCB3aWR0aD0nMzInIGhlaWdodD0nMzInIHJ4PSc2JyBmaWxsPSclMjMwZDExMTcnLyUzRSUzQ3BvbHlsaW5lIHBvaW50cz0nNCwyNCAxMCwxNiAxNiwyMCAyMiwxMCAyOCwxNCcgZmlsbD0nbm9uZScgc3Ryb2tlPSclMjMxMGI5ODEnIHN0cm9rZS13aWR0aD0nMi41JyBzdHJva2UtbGluZWNhcD0ncm91bmQnIHN0cm9rZS1saW5lam9pbj0ncm91bmQnLyUzRSUzQy9zdmclM0UiPgo8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PVNwYWNlK0dyb3Rlc2s6d2dodEA0MDA7NTAwOzYwMDs3MDAmZmFtaWx5PUJlYmFzK05ldWUmZmFtaWx5PUpldEJyYWlucytNb25vOndnaHRANDAwOzYwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCIvPgo8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9jaGFydC5qc0A0LjQuMC9kaXN0L2NoYXJ0LnVtZC5taW4uanMiPjwvc2NyaXB0Pgo8c3R5bGU+Cjpyb290ey0tYmc6IzA1MDcwZjstLWJnMjojMGQxMTE3Oy0tYmczOiMxNjFiMjQ7LS1ib3JkZXI6cmdiYSgyNTUsMjU1LDI1NSwwLjA4KTstLXRleHQ6I2UyZThmMDstLW11dGVkOiM0YjU1NjM7LS1ncmVlbjojMTBiOTgxOy0tZ3JlZW4yOiMzNGQzOTk7LS1yZWQ6I2VmNDQ0NDstLXJlZDI6I2Y4NzE3MTstLXllbGxvdzojZjU5ZTBiO30KKntib3gtc2l6aW5nOmJvcmRlci1ib3g7bWFyZ2luOjA7cGFkZGluZzowfQpib2R5e2JhY2tncm91bmQ6dmFyKC0tYmcpO2NvbG9yOnZhcigtLXRleHQpO2ZvbnQtZmFtaWx5OidTcGFjZSBHcm90ZXNrJyxzYW5zLXNlcmlmO21pbi1oZWlnaHQ6MTAwdmh9Ci5oZWFkZXJ7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCMwZDExMTcsIzExMTgyNyk7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtwYWRkaW5nOjE0cHggMjBweDtwb3NpdGlvbjpzdGlja3k7dG9wOjA7ei1pbmRleDoxMDB9Ci5oZWFkZXItaW5uZXJ7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTBweDttYXgtd2lkdGg6MTQwMHB4O21hcmdpbjowIGF1dG99Ci5sb2dvLW1haW57Zm9udC1mYW1pbHk6J0JlYmFzIE5ldWUnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjIycHg7bGV0dGVyLXNwYWNpbmc6NHB4O2JhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZywjMTBiOTgxLCMzYjgyZjYpOy13ZWJraXQtYmFja2dyb3VuZC1jbGlwOnRleHQ7LXdlYmtpdC10ZXh0LWZpbGwtY29sb3I6dHJhbnNwYXJlbnR9Ci50aW1lc3RhbXB7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtZmFtaWx5OidKZXRCcmFpbnMgTW9ubycsbW9ub3NwYWNlfQoubGl2ZS1kb3R7d2lkdGg6N3B4O2hlaWdodDo3cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDp2YXIoLS1ncmVlbik7YW5pbWF0aW9uOnB1bHNlIDJzIGluZmluaXRlO2Rpc3BsYXk6aW5saW5lLWJsb2NrO21hcmdpbi1yaWdodDo1cHh9CkBrZXlmcmFtZXMgcHVsc2V7MCUsMTAwJXtvcGFjaXR5OjE7Ym94LXNoYWRvdzowIDAgMCAwIHJnYmEoMTYsMTg1LDEyOSwuNCl9NTAle29wYWNpdHk6Ljc7Ym94LXNoYWRvdzowIDAgMCA2cHggcmdiYSgxNiwxODUsMTI5LDApfX0KLm5hdntkaXNwbGF5OmZsZXg7Z2FwOjRweDtwYWRkaW5nOjEwcHggMjBweDtib3JkZXItYm90dG9tOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmcyKTtvdmVyZmxvdy14OmF1dG87ZmxleC13cmFwOndyYXB9Ci50YWJ7cGFkZGluZzo2cHggMTRweDtib3JkZXItcmFkaXVzOjZweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo1MDA7Ym9yZGVyOjFweCBzb2xpZCB0cmFuc3BhcmVudDtiYWNrZ3JvdW5kOm5vbmU7Y29sb3I6dmFyKC0tbXV0ZWQpO3RyYW5zaXRpb246YWxsIC4yczt3aGl0ZS1zcGFjZTpub3dyYXB9Ci50YWI6aG92ZXJ7Y29sb3I6dmFyKC0tdGV4dCk7YmFja2dyb3VuZDp2YXIoLS1iZzMpfQoudGFiLmFjdGl2ZXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Y29sb3I6dmFyKC0tdGV4dCk7Ym9yZGVyLWNvbG9yOnZhcigtLWJvcmRlcil9Ci50YWIucG9ydC5hY3RpdmV7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXItY29sb3I6cmdiYSgxNiwxODUsMTI5LC4zKX0KLnRmLXJvd3tkaXNwbGF5OmZsZXg7Z2FwOjZweDtwYWRkaW5nOjEwcHggMjBweDtib3JkZXItYm90dG9tOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmcyKTthbGlnbi1pdGVtczpjZW50ZXI7ZmxleC13cmFwOndyYXB9Ci50Zi1idG57cGFkZGluZzo1cHggMTJweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTFweDtjdXJzb3I6cG9pbnRlcjtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLW11dGVkKTtmb250LWZhbWlseTonSmV0QnJhaW5zIE1vbm8nLG1vbm9zcGFjZTt0cmFuc2l0aW9uOmFsbCAuMnN9Ci50Zi1idG4uYWN0aXZle2JhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4xNSk7Y29sb3I6IzYwYTVmYTtib3JkZXItY29sb3I6cmdiYSg1OSwxMzAsMjQ2LC40KX0KLnRmLWJ0bi5zdGFye3Bvc2l0aW9uOnJlbGF0aXZlfQoudGYtYnRuLnN0YXI6OmFmdGVye2NvbnRlbnQ6J+KYhSc7cG9zaXRpb246YWJzb2x1dGU7dG9wOi01cHg7cmlnaHQ6LTRweDtmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLXllbGxvdyl9Ci50Zi1oaW50e2ZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKX0KLnN0YXRze2Rpc3BsYXk6ZmxleDtnYXA6OHB4O3BhZGRpbmc6MTBweCAyMHB4O2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2ZsZXgtd3JhcDp3cmFwfQoucGlsbHtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo1cHg7cGFkZGluZzo0cHggMTBweDtib3JkZXItcmFkaXVzOjIwcHg7Zm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwO2JvcmRlcjoxcHggc29saWR9Ci5waWxsLmd7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXItY29sb3I6cmdiYSgxNiwxODUsMTI5LC4yNSl9Ci5waWxsLnJ7YmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMSk7Y29sb3I6dmFyKC0tcmVkMik7Ym9yZGVyLWNvbG9yOnJnYmEoMjM5LDY4LDY4LC4yNSl9Ci5waWxsLnl7YmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjEpO2NvbG9yOnZhcigtLXllbGxvdyk7Ym9yZGVyLWNvbG9yOnJnYmEoMjQ1LDE1OCwxMSwuMjUpfQoucGlsbC5ie2JhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4xKTtjb2xvcjojNjBhNWZhO2JvcmRlci1jb2xvcjpyZ2JhKDU5LDEzMCwyNDYsLjI1KX0KLnBpbGwubXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Y29sb3I6dmFyKC0tbXV0ZWQpO2JvcmRlci1jb2xvcjp2YXIoLS1ib3JkZXIpfQouZG90e3dpZHRoOjVweDtoZWlnaHQ6NXB4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6Y3VycmVudENvbG9yfQoubWFpbntwYWRkaW5nOjE0cHggMjBweDttYXgtd2lkdGg6MTQwMHB4O21hcmdpbjowIGF1dG99Ci5ncmlke2Rpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMzAwcHgsMWZyKSk7Z2FwOjEwcHh9CkBtZWRpYShtYXgtd2lkdGg6NDgwcHgpey5ncmlke2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnJ9fQouY2FyZHtiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtvdmVyZmxvdzpoaWRkZW47Y3Vyc29yOnBvaW50ZXI7dHJhbnNpdGlvbjphbGwgLjJzfQouY2FyZDpob3Zlcnt0cmFuc2Zvcm06dHJhbnNsYXRlWSgtMnB4KTtib3gtc2hhZG93OjAgOHB4IDI0cHggcmdiYSgwLDAsMCwuNCl9Ci5hY2NlbnR7aGVpZ2h0OjNweH0KLmNib2R5e3BhZGRpbmc6MTJweCAxNHB4fQouY3RvcHtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6ZmxleC1zdGFydDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjhweH0KLnRpY2tlcntmb250LWZhbWlseTonQmViYXMgTmV1ZScsc2Fucy1zZXJpZjtmb250LXNpemU6MjBweDtsZXR0ZXItc3BhY2luZzoycHg7bGluZS1oZWlnaHQ6MX0KLmNwcnt0ZXh0LWFsaWduOnJpZ2h0fQoucHZhbHtmb250LWZhbWlseTonSmV0QnJhaW5zIE1vbm8nLG1vbm9zcGFjZTtmb250LXNpemU6MTVweDtmb250LXdlaWdodDo2MDB9Ci5wY2hne2ZvbnQtc2l6ZToxMXB4O2ZvbnQtZmFtaWx5OidKZXRCcmFpbnMgTW9ubycsbW9ub3NwYWNlO21hcmdpbi10b3A6MnB4fQouYmFkZ2V7ZGlzcGxheTppbmxpbmUtYmxvY2s7cGFkZGluZzoycHggOHB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZToxMHB4O2ZvbnQtd2VpZ2h0OjcwMDtsZXR0ZXItc3BhY2luZzouNXB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tdG9wOjNweH0KLnBvcnQtYmFkZ2V7ZGlzcGxheTppbmxpbmUtZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjNweDtwYWRkaW5nOjJweCA2cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo2MDA7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEyKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjI1KTttYXJnaW4tbGVmdDo1cHh9Ci5zaWdze2Rpc3BsYXk6ZmxleDtmbGV4LXdyYXA6d3JhcDtnYXA6M3B4O21hcmdpbi1ib3R0b206OHB4fQouc3B7Zm9udC1zaXplOjlweDtwYWRkaW5nOjJweCA2cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1mYW1pbHk6J0pldEJyYWlucyBNb25vJyxtb25vc3BhY2V9Ci5zZ3tiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMSk7Y29sb3I6dmFyKC0tZ3JlZW4yKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMil9Ci5zYntiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xKTtjb2xvcjp2YXIoLS1yZWQyKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKX0KLnNue2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpfQouY2hhcnQtd3toZWlnaHQ6NzVweDttYXJnaW4tdG9wOjhweH0KLmx2bHN7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoMywxZnIpO2dhcDo1cHg7bWFyZ2luLXRvcDo4cHh9Ci5sdntiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo1cHg7cGFkZGluZzo2cHg7dGV4dC1hbGlnbjpjZW50ZXI7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpfQoubGx7Zm9udC1zaXplOjhweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjJweH0KLmx2YWx7Zm9udC1mYW1pbHk6J0pldEJyYWlucyBNb25vJyxtb25vc3BhY2U7Zm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwfQoub3ZlcmxheXtwb3NpdGlvbjpmaXhlZDtpbnNldDowO2JhY2tncm91bmQ6cmdiYSgwLDAsMCwuODgpO3otaW5kZXg6MTAwMDtkaXNwbGF5Om5vbmU7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7cGFkZGluZzoxNnB4fQoub3ZlcmxheS5vcGVue2Rpc3BsYXk6ZmxleH0KLm1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjUyMHB4O21heC1oZWlnaHQ6OTJ2aDtvdmVyZmxvdy15OmF1dG99Ci5taGVhZHtwYWRkaW5nOjE4cHggMThweCAwO2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpmbGV4LXN0YXJ0fQoubXRpdGxle2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZTozMHB4O2xldHRlci1zcGFjaW5nOjNweH0KLm1jbG9zZXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTt3aWR0aDozMHB4O2hlaWdodDozMHB4O2JvcmRlci1yYWRpdXM6N3B4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxNXB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcn0KLm1ib2R5e3BhZGRpbmc6MTRweCAxOHB4IDE4cHh9Ci5tY2hhcnR3e2hlaWdodDoxNTBweDttYXJnaW4tYm90dG9tOjE0cHh9Ci5kZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjdweDttYXJnaW4tYm90dG9tOjEycHh9Ci5kY3tiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo3cHg7cGFkZGluZzo5cHggMTFweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5kbHtmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206M3B4fQouZHZ7Zm9udC1mYW1pbHk6J0pldEJyYWlucyBNb25vJyxtb25vc3BhY2U7Zm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwfQouZGJveHtib3JkZXItcmFkaXVzOjlweDtwYWRkaW5nOjEzcHg7bWFyZ2luLWJvdHRvbToxMnB4O2JvcmRlcjoxcHggc29saWR9Ci5kbGJse2ZvbnQtc2l6ZTo5cHg7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjVweH0KLmR2ZXJke2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyNnB4O2xldHRlci1zcGFjaW5nOjJweDttYXJnaW4tYm90dG9tOjhweH0KLmRyb3d7ZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206NHB4O2ZvbnQtc2l6ZToxMnB4fQouZGtleXtjb2xvcjp2YXIoLS1tdXRlZCl9Ci5ycmJhcntoZWlnaHQ6NHB4O2JhY2tncm91bmQ6dmFyKC0tYmcpO2JvcmRlci1yYWRpdXM6MnB4O21hcmdpbi10b3A6N3B4O292ZXJmbG93OmhpZGRlbn0KLnJyZmlsbHtoZWlnaHQ6MTAwJTtib3JkZXItcmFkaXVzOjJweDt0cmFuc2l0aW9uOndpZHRoIC44cyBlYXNlfQoudnBib3h7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6N3B4O3BhZGRpbmc6MTBweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7bWFyZ2luLWJvdHRvbToxMnB4fQoudnB0aXRsZXtmb250LXNpemU6OXB4O2NvbG9yOiM2MGE1ZmE7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjdweH0KLnZwZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgzLDFmcik7Z2FwOjVweH0KLnZwY3tiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyLXJhZGl1czo1cHg7cGFkZGluZzo3cHg7dGV4dC1hbGlnbjpjZW50ZXI7Ym9yZGVyOjFweCBzb2xpZH0KLm1pbmZve2Rpc3BsYXk6aW5saW5lLWZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7d2lkdGg6MTRweDtoZWlnaHQ6MTRweDtib3JkZXItcmFkaXVzOjUwJTtiYWNrZ3JvdW5kOnJnYmEoOTYsMTY1LDI1MCwuMik7Y29sb3I6IzYwYTVmYTtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjcwMDtjdXJzb3I6cG9pbnRlcjttYXJnaW4tbGVmdDo0cHg7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDk2LDE2NSwyNTAsLjMpfQoubWluZm8tcG9wdXB7cG9zaXRpb246Zml4ZWQ7aW5zZXQ6MDtiYWNrZ3JvdW5kOnJnYmEoMCwwLDAsLjg4KTt6LWluZGV4OjIwMDA7ZGlzcGxheTpub25lO2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO3BhZGRpbmc6MTZweH0KLm1pbmZvLXBvcHVwLm9wZW57ZGlzcGxheTpmbGV4fQoubWluZm8tbW9kYWx7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjE0cHg7d2lkdGg6MTAwJTttYXgtd2lkdGg6NDgwcHg7bWF4LWhlaWdodDo4NXZoO292ZXJmbG93LXk6YXV0bztwYWRkaW5nOjIwcHg7cG9zaXRpb246cmVsYXRpdmV9Ci5taW5mby10aXRsZXtmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCk7bWFyZ2luLWJvdHRvbTo0cHh9Ci5taW5mby1zb3VyY2V7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MTJweDtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo2cHg7ZmxleC13cmFwOndyYXB9Ci5taW5mby1yZWx7cGFkZGluZzoycHggN3B4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwfQoubWluZm8tcmVsLmhpZ2h7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtjb2xvcjojMTBiOTgxfQoubWluZm8tcmVsLm1lZGl1bXtiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMTUpO2NvbG9yOiNmNTllMGJ9Ci5taW5mby1yZWwubG93e2JhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtjb2xvcjojZWY0NDQ0fQoubWluZm8tZGVzY3tmb250LXNpemU6MTJweDtjb2xvcjojOTRhM2I4O2xpbmUtaGVpZ2h0OjEuNjttYXJnaW4tYm90dG9tOjE0cHh9Ci5taW5mby13YXJuaW5ne2JhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6NnB4O3BhZGRpbmc6OHB4IDEwcHg7Zm9udC1zaXplOjExcHg7Y29sb3I6I2Y1OWUwYjttYXJnaW4tYm90dG9tOjE0cHh9Ci5taW5mby1yYW5nZXN7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8tcmFuZ2UtdGl0bGV7Zm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweH0KLm1pbmZvLXJhbmdle2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjhweDttYXJnaW4tYm90dG9tOjZweDtwYWRkaW5nOjZweCA4cHg7Ym9yZGVyLXJhZGl1czo2cHg7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wMil9Ci5taW5mby1yYW5nZS1kb3R7d2lkdGg6OHB4O2hlaWdodDo4cHg7Ym9yZGVyLXJhZGl1czo1MCU7ZmxleC1zaHJpbms6MH0KLm1pbmZvLWNhbnNsaW17YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czo2cHg7cGFkZGluZzo4cHggMTBweDtmb250LXNpemU6MTFweDtjb2xvcjojNjBhNWZhfQoubWluZm8tY2xvc2V7cG9zaXRpb246YWJzb2x1dGU7dG9wOjE2cHg7cmlnaHQ6MTZweDtiYWNrZ3JvdW5kOnJnYmEoMjU1LDI1NSwyNTUsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjEpO2NvbG9yOiM5NGEzYjg7d2lkdGg6MjhweDtoZWlnaHQ6MjhweDtib3JkZXItcmFkaXVzOjdweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTRweDtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXJ9Cjo6LXdlYmtpdC1zY3JvbGxiYXJ7d2lkdGg6NHB4O2hlaWdodDo0cHh9Cjo6LXdlYmtpdC1zY3JvbGxiYXItdHJhY2t7YmFja2dyb3VuZDp2YXIoLS1iZyl9Cjo6LXdlYmtpdC1zY3JvbGxiYXItdGh1bWJ7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4xKTtib3JkZXItcmFkaXVzOjJweH0KPC9zdHlsZT4KPC9oZWFkPgo8Ym9keT4KPGRpdiBjbGFzcz0iaGVhZGVyIj4KICA8ZGl2IGNsYXNzPSJoZWFkZXItaW5uZXIiPgogICAgPHNwYW4gY2xhc3M9ImxvZ28tbWFpbiI+Q0FOU0xJTSBTQ0FOTkVSPC9zcGFuPgogICAgPHNwYW4gY2xhc3M9InRpbWVzdGFtcCI+PHNwYW4gY2xhc3M9ImxpdmUtZG90Ij48L3NwYW4+JSVUSU1FU1RBTVAlJTwvc3Bhbj4KICAgIDxidXR0b24gb25jbGljaz0ib3BlbkVkaXRMaXN0KCkiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4zKTtjb2xvcjojNjBhNWZhO3BhZGRpbmc6NXB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1mYW1pbHk6aW5oZXJpdCI+4pyP77iPIExpc3RleWkgRMO8emVubGU8L2J1dHRvbj4KICA8L2Rpdj4KPC9kaXY+CjxkaXYgY2xhc3M9Im5hdiI+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIGFjdGl2ZSIgb25jbGljaz0ic2V0VGFiKCdkYXNoYm9hcmQnLHRoaXMpIj7wn4+gIERhc2hib2FyZDwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdhbGwnLHRoaXMpIj7wn5OKIEhpc3NlbGVyPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIHBvcnQiIG9uY2xpY2s9InNldFRhYigncG9ydCcsdGhpcykiPvCfkrwgUG9ydGbDtnnDvG08L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignYnV5Jyx0aGlzKSI+8J+TiCBBbDwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdzZWxsJyx0aGlzKSI+8J+TiSBTYXQ8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignZWFybmluZ3MnLHRoaXMpIj7wn5OFIEVhcm5pbmdzPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ3J1dGluJyx0aGlzKSI+4pyFIFJ1dGluPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2hhZnRhbGlrJyx0aGlzKSI+8J+TiCBIYWZ0YWzEsWs8L2J1dHRvbj4KPC9kaXY+CjxkaXYgY2xhc3M9InRmLXJvdyIgaWQ9InRmUm93IiBzdHlsZT0iZGlzcGxheTpub25lIj4KICA8YnV0dG9uIGNsYXNzPSJ0Zi1idG4gYWN0aXZlIiBkYXRhLXRmPSIxZCIgb25jbGljaz0ic2V0VGYoJzFkJyx0aGlzKSI+MUc8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0Zi1idG4gc3RhciIgZGF0YS10Zj0iMXdrIiBvbmNsaWNrPSJzZXRUZignMXdrJyx0aGlzKSI+MUg8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0Zi1idG4iIGRhdGEtdGY9IjFtbyIgb25jbGljaz0ic2V0VGYoJzFtbycsdGhpcykiPjFBPC9idXR0b24+CiAgPHNwYW4gY2xhc3M9InRmLWhpbnQiPkNBTlNMSU0gw7ZuZXJpbGVuOiAxRyArIDFIPC9zcGFuPgo8L2Rpdj4KPGRpdiBjbGFzcz0ic3RhdHMiIGlkPSJzdGF0cyI+PC9kaXY+CjxkaXYgY2xhc3M9Im1haW4iPjxkaXYgY2xhc3M9ImdyaWQiIGlkPSJncmlkIj48L2Rpdj48L2Rpdj4KPGRpdiBjbGFzcz0ib3ZlcmxheSIgaWQ9Im92ZXJsYXkiIG9uY2xpY2s9ImNsb3NlTShldmVudCkiPgogIDxkaXYgY2xhc3M9Im1vZGFsIiBpZD0ibW9kYWwiPjwvZGl2Pgo8L2Rpdj4KCjxkaXYgY2xhc3M9Im1pbmZvLXBvcHVwIiBpZD0iZWRpdFBvcHVwIiBvbmNsaWNrPSJjbG9zZUVkaXRQb3B1cChldmVudCkiPgogIDxkaXYgY2xhc3M9Im1pbmZvLW1vZGFsIiBzdHlsZT0icG9zaXRpb246cmVsYXRpdmU7bWF4LXdpZHRoOjU2MHB4IiBpZD0iZWRpdE1vZGFsIj4KICAgIDxidXR0b24gY2xhc3M9Im1pbmZvLWNsb3NlIiBvbmNsaWNrPSJjbG9zZUVkaXRQb3B1cCgpIj7inJU8L2J1dHRvbj4KICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KTttYXJnaW4tYm90dG9tOjRweCI+4pyP77iPIExpc3RleWkgRMO8emVubGU8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjE2cHgiPkdpdEh1YiBBUEkga2V5IGdlcmVrbGkg4oCUIGRlxJ9pxZ9pa2xpa2xlciBhbsSxbmRhIGtheWRlZGlsaXI8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyIDFmcjtnYXA6MTZweDttYXJnaW4tYm90dG9tOjE2cHgiPgogICAgICA8ZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij7wn5OLIFdhdGNobGlzdDwvZGl2PgogICAgICAgIDxkaXYgaWQ9IndhdGNobGlzdEVkaXRvciI+PC9kaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo2cHg7bWFyZ2luLXRvcDo4cHgiPgogICAgICAgICAgPGlucHV0IGlkPSJuZXdXYXRjaFRpY2tlciIgcGxhY2Vob2xkZXI9Ikhpc3NlIGVrbGUgKFRTTEEpIiBzdHlsZT0iZmxleDoxO2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tdGV4dCk7cGFkZGluZzo2cHggMTBweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtmb250LWZhbWlseTppbmhlcml0O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZSIvPgogICAgICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJhZGRUaWNrZXIoJ3dhdGNoJykiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzo2cHggMTJweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtjdXJzb3I6cG9pbnRlciI+KyBFa2xlPC9idXR0b24+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgogICAgICA8ZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij7wn5K8IFBvcnRmw7Z5PC9kaXY+CiAgICAgICAgPGRpdiBpZD0icG9ydGZvbGlvRWRpdG9yIj48L2Rpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjZweDttYXJnaW4tdG9wOjhweCI+CiAgICAgICAgICA8aW5wdXQgaWQ9Im5ld1BvcnRUaWNrZXIiIHBsYWNlaG9sZGVyPSJIaXNzZSBla2xlIChBQVBMKSIgc3R5bGU9ImZsZXg6MTtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLXRleHQpO3BhZGRpbmc6NnB4IDEwcHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Zm9udC1mYW1pbHk6aW5oZXJpdDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2UiLz4KICAgICAgICAgIDxidXR0b24gb25jbGljaz0iYWRkVGlja2VyKCdwb3J0JykiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzo2cHggMTJweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtjdXJzb3I6cG9pbnRlciI+KyBFa2xlPC9idXR0b24+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgogICAgPC9kaXY+CiAgICA8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTJweDttYXJnaW4tYm90dG9tOjE0cHg7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tZ3JlZW4pIj7inIUgRGXEn2nFn2lrbGlrbGVyIGtheWRlZGlsaW5jZSBiaXIgc29ucmFraSBDb2xhYiDDp2FsxLHFn3TEsXJtYXPEsW5kYSBha3RpZiBvbHVyLjwvZGl2Pgo8ZGl2IHN0eWxlPSJtYXJnaW4tYm90dG9tOjEycHgiPgogICAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo1cHgiPkdpdEh1YiBUb2tlbiAoYmlyIGtleiBnaXIsIHRhcmF5aWNpIGhhdGlybGF5YWNhayk8L2Rpdj4KICAgICAgPGlucHV0IGlkPSJnaFRva2VuSW5wdXQiIHBsYWNlaG9sZGVyPSJnaHBfLi4uIiBzdHlsZT0id2lkdGg6MTAwJTtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLXRleHQpO3BhZGRpbmc6OHB4IDEwcHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Zm9udC1mYW1pbHk6J0pldEJyYWlucyBNb25vJyxtb25vc3BhY2UiLz4KICAgIDwvZGl2PgogICAgPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo4cHgiPgogICAgICA8YnV0dG9uIG9uY2xpY2s9InNhdmVMaXN0VG9HaXRodWIoKSIgc3R5bGU9ImZsZXg6MTtiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6OHB4O2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMDtjdXJzb3I6cG9pbnRlciI+8J+SviBHaXRIdWInYSBLYXlkZXQ8L2J1dHRvbj4KICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJjbG9zZUVkaXRQb3B1cCgpIiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS1tdXRlZCk7cGFkZGluZzoxMHB4IDE2cHg7Ym9yZGVyLXJhZGl1czo4cHg7Zm9udC1zaXplOjEzcHg7Y3Vyc29yOnBvaW50ZXIiPsSwcHRhbDwvYnV0dG9uPgogICAgPC9kaXY+CiAgICA8ZGl2IGlkPSJlZGl0U3RhdHVzIiBzdHlsZT0ibWFyZ2luLXRvcDoxMHB4O2ZvbnQtc2l6ZToxMnB4O3RleHQtYWxpZ246Y2VudGVyIj48L2Rpdj4KICA8L2Rpdj4KPC9kaXY+Cgo8ZGl2IGNsYXNzPSJtaW5mby1wb3B1cCIgaWQ9Im1pbmZvUG9wdXAiIG9uY2xpY2s9ImNsb3NlSW5mb1BvcHVwKGV2ZW50KSI+CiAgPGRpdiBjbGFzcz0ibWluZm8tbW9kYWwiIGlkPSJtaW5mb01vZGFsIj4KICAgIDxidXR0b24gY2xhc3M9Im1pbmZvLWNsb3NlIiBvbmNsaWNrPSJjbG9zZUluZm9Qb3B1cCgpIj7inJU8L2J1dHRvbj4KICAgIDxkaXYgaWQ9Im1pbmZvQ29udGVudCI+PC9kaXY+CiAgPC9kaXY+CjwvZGl2Pgo8c2NyaXB0Pgp2YXIgTUVUUklDUyA9IHsKICAvLyBURUtOxLBLCiAgJ1JTSSc6IHsKICAgIHRpdGxlOiAnUlNJIChHw7ZyZWNlbGkgR8O8w6cgRW5kZWtzaSknLAogICAgZGVzYzogJ0hpc3NlbmluIGHFn8SxcsSxIGFsxLFtIHZleWEgYcWfxLFyxLEgc2F0xLFtIGLDtmxnZXNpbmRlIG9sdXAgb2xtYWTEscSfxLFuxLEgZ8O2c3RlcmlyLiAxNCBnw7xubMO8ayBmaXlhdCBoYXJla2V0bGVyaW5pIGFuYWxpeiBlZGVyLicsCiAgICBzb3VyY2U6ICdUZWtuaWsgQW5hbGl6JywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOidBxZ/EsXLEsSBTYXTEsW0nLG1pbjowLG1heDozMCxjb2xvcjonZ3JlZW4nLGRlc2M6J0bEsXJzYXQgYsO2bGdlc2kg4oCUIGZpeWF0IMOnb2sgZMO8xZ9tw7zFnyd9LAogICAgICB7bGFiZWw6J05vcm1hbCcsbWluOjMwLG1heDo3MCxjb2xvcjoneWVsbG93JyxkZXNjOidOw7Z0ciBiw7ZsZ2UnfSwKICAgICAge2xhYmVsOidBxZ/EsXLEsSBBbMSxbScsbWluOjcwLG1heDoxMDAsY29sb3I6J3JlZCcsZGVzYzonRGlra2F0IOKAlCBmaXlhdCDDp29rIHnDvGtzZWxtacWfJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTiBrcml0ZXJpIGlsZSBpbGdpbGkg4oCUIGZpeWF0IG1vbWVudHVtdScKICB9LAogICdTTUE1MCc6IHsKICAgIHRpdGxlOiAnU01BIDUwICg1MCBHw7xubMO8ayBIYXJla2V0bGkgT3J0YWxhbWEpJywKICAgIGRlc2M6ICdTb24gNTAgZ8O8bsO8biBvcnRhbGFtYSBrYXBhbsSxxZ8gZml5YXTEsS4gS8Sxc2Etb3J0YSB2YWRlbGkgdHJlbmQgZ8O2c3Rlcmdlc2kuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J8OcemVyaW5kZScsY29sb3I6J2dyZWVuJyxkZXNjOidLxLFzYSB2YWRlbGkgdHJlbmQgcG96aXRpZiDigJQgZ8O8w6dsw7wgc2lueWFsJ30sCiAgICAgIHtsYWJlbDonQWx0xLFuZGEnLGNvbG9yOidyZWQnLGRlc2M6J0vEsXNhIHZhZGVsaSB0cmVuZCBuZWdhdGlmJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTSBrcml0ZXJpIOKAlCBwaXlhc2EgdHJlbmRpJwogIH0sCiAgJ1NNQTIwMCc6IHsKICAgIHRpdGxlOiAnU01BIDIwMCAoMjAwIEfDvG5sw7xrIEhhcmVrZXRsaSBPcnRhbGFtYSknLAogICAgZGVzYzogJ1NvbiAyMDAgZ8O8bsO8biBvcnRhbGFtYSBrYXBhbsSxxZ8gZml5YXTEsS4gVXp1biB2YWRlbGkgdHJlbmQgZ8O2c3Rlcmdlc2kuIEVuIMO2bmVtbGkgdGVrbmlrIHNldml5ZS4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonw5x6ZXJpbmRlJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1V6dW4gdmFkZWxpIGJvxJ9hIHRyZW5kaW5kZSDigJQgQ0FOU0xJTSBpw6dpbiDFn2FydCd9LAogICAgICB7bGFiZWw6J0FsdMSxbmRhJyxjb2xvcjoncmVkJyxkZXNjOidVenVuIHZhZGVsaSBhecSxIHRyZW5kaW5kZSDigJQgQ0FOU0xJTSBpw6dpbiBnaXJtZSd9CiAgICBdLAogICAgY2Fuc2xpbTogJ00ga3JpdGVyaSDigJQgem9ydW5sdSBrb8WfdWwnCiAgfSwKICAnNTJXJzogewogICAgdGl0bGU6ICc1MiBIYWZ0YWzEsWsgUG96aXN5b24nLAogICAgZGVzYzogJ0hpc3NlbmluIHNvbiAxIHnEsWxkYWtpIGZpeWF0IGFyYWzEscSfxLFuZGEgbmVyZWRlIG9sZHXEn3VudSBnw7ZzdGVyaXIuIDA9ecSxbMSxbiBkaWJpLCAxMDA9ecSxbMSxbiB6aXJ2ZXNpLicsCiAgICBzb3VyY2U6ICdUZWtuaWsgQW5hbGl6JywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOicwLTMwJScsY29sb3I6J2dyZWVuJyxkZXNjOidZxLFsxLFuIGRpYmluZSB5YWvEsW4g4oCUIHBvdGFuc2l5ZWwgZsSxcnNhdCd9LAogICAgICB7bGFiZWw6JzMwLTcwJScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSBiw7ZsZ2Ug4oCUIG7DtnRyJ30sCiAgICAgIHtsYWJlbDonNzAtODUlJyxjb2xvcjoneWVsbG93JyxkZXNjOidaaXJ2ZXllIHlha2xhxZ/EsXlvciDigJQgaXpsZSd9LAogICAgICB7bGFiZWw6Jzg1LTEwMCUnLGNvbG9yOidyZWQnLGRlc2M6J1ppcnZleWUgw6dvayB5YWvEsW4g4oCUIGRpa2thdGxpIGdpcid9CiAgICBdLAogICAgY2Fuc2xpbTogJ04ga3JpdGVyaSDigJQgeWVuaSB6aXJ2ZSBrxLFyxLFsxLFtxLEgacOnaW4gaWRlYWwgYsO2bGdlICU4NS0xMDAnCiAgfSwKICAnSGFjaW0nOiB7CiAgICB0aXRsZTogJ0hhY2ltICjEsMWfbGVtIE1pa3RhcsSxKScsCiAgICBkZXNjOiAnR8O8bmzDvGsgacWfbGVtIGhhY21pbmluIHNvbiAyMCBnw7xubMO8ayBvcnRhbGFtYXlhIG9yYW7EsS4gR8O8w6dsw7wgaGFyZWtldGxlcmluIGhhY2ltbGUgZGVzdGVrbGVubWVzaSBnZXJla2lyLicsCiAgICBzb3VyY2U6ICdUZWtuaWsgQW5hbGl6JywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOidZw7xrc2VrICg+MS4zeCknLGNvbG9yOidncmVlbicsZGVzYzonS3VydW1zYWwgaWxnaSB2YXIg4oCUIGfDvMOnbMO8IHNpbnlhbCd9LAogICAgICB7bGFiZWw6J05vcm1hbCAoMC43LTEuM3gpJyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhbGFtYSBpbGdpJ30sCiAgICAgIHtsYWJlbDonRMO8xZ/DvGsgKDwwLjd4KScsY29sb3I6J3JlZCcsZGVzYzonxLBsZ2kgYXphbG3EscWfIOKAlCBkaWtrYXQnfQogICAgXSwKICAgIGNhbnNsaW06ICdTIGtyaXRlcmkg4oCUIGFyei90YWxlcCBkZW5nZXNpJwogIH0sCiAgLy8gVEVNRUwKICAnRm9yd2FyZFBFJzogewogICAgdGl0bGU6ICdGb3J3YXJkIFAvRSAoxLBsZXJpeWUgRMO2bsO8ayBGaXlhdC9LYXphbsOnKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIMO2bsO8bcO8emRla2kgMTIgYXlkYWtpIHRhaG1pbmkga2F6YW5jxLFuYSBnw7ZyZSBmaXlhdMSxLiBUcmFpbGluZyBQL0VcJ2RlbiBkYWhhIMO2bmVtbGkgw6fDvG5rw7wgZ2VsZWNlxJ9lIGJha8SxeW9yLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEFuYWxpc3QgdGFobWluaScsCiAgICByZWxpYWJpbGl0eTogJ21lZGl1bScsCiAgICB3YXJuaW5nOiAnQW5hbGlzdCB0YWhtaW5sZXJpbmUgZGF5YW7EsXIsIHlhbsSxbHTEsWPEsSBvbGFiaWxpcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic8MTUnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgYsO8ecO8bWUgYmVrbGVudGlzaSBkw7zFn8O8ayB2ZXlhIGhpc3NlIGRlxJ9lciBhbHTEsW5kYSd9LAogICAgICB7bGFiZWw6JzE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J01ha3VsIOKAlCDDp2/En3Ugc2VrdMO2ciBpw6dpbiBub3JtYWwnfSwKICAgICAge2xhYmVsOicyNS00MCcsY29sb3I6J3llbGxvdycsZGVzYzonUGFoYWzEsSBhbWEgYsO8ecO8bWUgcHJpbWkgw7ZkZW5peW9yJ30sCiAgICAgIHtsYWJlbDonPjQwJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHBhaGFsxLEg4oCUIHnDvGtzZWsgYsO8ecO8bWUgYmVrbGVudGlzaSBmaXlhdGxhbm3EscWfJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQyB2ZSBBIGtyaXRlcmxlcmkgaWxlIGlsZ2lsaScKICB9LAogICdQRUcnOiB7CiAgICB0aXRsZTogJ1BFRyBPcmFuxLEgKEZpeWF0L0themFuw6cvQsO8ecO8bWUpJywKICAgIGRlc2M6ICdQL0Ugb3JhbsSxbsSxIGLDvHnDvG1lIGjEsXrEsXlsYSBrYXLFn8SxbGHFn3TEsXLEsXIuIELDvHnDvHllbiDFn2lya2V0bGVyIGnDp2luIFAvRVwnZGVuIGRhaGEgZG/En3J1IGRlxJ9lcmxlbWUgw7Zsw6fDvHTDvC4gUEVHPTEgYWRpbCBkZcSfZXIga2FidWwgZWRpbGlyLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEFuYWxpc3QgdGFobWluaScsCiAgICByZWxpYWJpbGl0eTogJ21lZGl1bScsCiAgICB3YXJuaW5nOiAnQW5hbGlzdCBiw7x5w7xtZSB0YWhtaW5sZXJpbmUgZGF5YW7EsXInLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPDEuMCcsY29sb3I6J2dyZWVuJyxkZXNjOidVY3V6IOKAlCBiw7x5w7xtZXNpbmUgZ8O2cmUgZGXEn2VyIGFsdMSxbmRhJ30sCiAgICAgIHtsYWJlbDonMS4wLTEuNScsY29sb3I6J2dyZWVuJyxkZXNjOidNYWt1bCDigJQgYWRpbCBmaXlhdCBjaXZhcsSxJ30sCiAgICAgIHtsYWJlbDonMS41LTIuMCcsY29sb3I6J3llbGxvdycsZGVzYzonQmlyYXogcGFoYWzEsSd9LAogICAgICB7bGFiZWw6Jz4yLjAnLGNvbG9yOidyZWQnLGRlc2M6J1BhaGFsxLEg4oCUIGRpa2thdGxpIG9sJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQSBrcml0ZXJpIOKAlCBiw7x5w7xtZSBrYWxpdGVzaScKICB9LAogICdFUFNHcm93dGgnOiB7CiAgICB0aXRsZTogJ0VQUyBCw7x5w7xtZXNpICjDh2V5cmVrbGlrLCBZb1kpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gaGlzc2UgYmHFn8SxbmEga2F6YW5jxLFuxLFuIGdlw6dlbiB5xLFsxLFuIGF5bsSxIMOnZXlyZcSfaW5lIGfDtnJlIGFydMSxxZ/EsS4gQ0FOU0xJTVwnaW4gZW4ga3JpdGlrIGtyaXRlcmkuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgR2Vyw6dlayB2ZXJpJywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic+JTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J0fDvMOnbMO8IGLDvHnDvG1lIOKAlCBDQU5TTElNIGtyaXRlcmkga2FyxZ/EsWxhbmTEsSd9LAogICAgICB7bGFiZWw6JyUxNS0yNScsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpIGLDvHnDvG1lJ30sCiAgICAgIHtsYWJlbDonJTAtMTUnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1phecSxZiBiw7x5w7xtZSd9LAogICAgICB7bGFiZWw6JzwwJyxjb2xvcjoncmVkJyxkZXNjOidLYXphbsOnIGTDvMWfw7x5b3Ig4oCUIGRpa2thdCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Mga3JpdGVyaSDigJQgZW4ga3JpdGlrIGtyaXRlciwgbWluaW11bSAlMjUgb2xtYWzEsScKICB9LAogICdSZXZHcm93dGgnOiB7CiAgICB0aXRsZTogJ0dlbGlyIELDvHnDvG1lc2kgKFlvWSknLAogICAgZGVzYzogJ8WeaXJrZXRpbiBzYXTEscWfL2dlbGlyaW5pbiBnZcOnZW4gecSxbGEgZ8O2cmUgYXJ0xLHFn8SxLiBFUFMgYsO8ecO8bWVzaW5pIGRlc3Rla2xlbWVzaSBnZXJla2lyIOKAlCBzYWRlY2UgbWFsaXlldCBrZXNpbnRpc2l5bGUgYsO8ecO8bWUgc8O8cmTDvHLDvGxlYmlsaXIgZGXEn2lsLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUxNScsY29sb3I6J2dyZWVuJyxkZXNjOidHw7zDp2zDvCBnZWxpciBiw7x5w7xtZXNpJ30sCiAgICAgIHtsYWJlbDonJTUtMTUnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGEgYsO8ecO8bWUnfSwKICAgICAge2xhYmVsOic8NScsY29sb3I6J3JlZCcsZGVzYzonR2VsaXIgYsO8ecO8bWVzaSB6YXnEsWYnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIHPDvHJkw7xyw7xsZWJpbGlyIGLDvHnDvG1lIGnDp2luIMWfYXJ0JwogIH0sCiAgJ05ldE1hcmdpbic6IHsKICAgIHRpdGxlOiAnTmV0IE1hcmppbicsCiAgICBkZXNjOiAnSGVyIDEkIGdlbGlyZGVuIG5lIGthZGFyIG5ldCBrw6JyIGthbGTEscSfxLFuxLEgZ8O2c3RlcmlyLiBZw7xrc2VrIG1hcmppbiA9IGfDvMOnbMO8IGnFnyBtb2RlbGkuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgR2Vyw6dlayB2ZXJpJywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic+JTIwJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8OHb2sgZ8O8w6dsw7wga8OicmzEsWzEsWsnfSwKICAgICAge2xhYmVsOiclMTAtMjAnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSBrw6JybMSxbMSxayd9LAogICAgICB7bGFiZWw6JyU1LTEwJyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIGvDonJsxLFsxLFrJ30sCiAgICAgIHtsYWJlbDonPDUnLGNvbG9yOidyZWQnLGRlc2M6J1phecSxZiBrw6JybMSxbMSxayd9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQga8OicmzEsWzEsWsga2FsaXRlc2knCiAgfSwKICAnUk9FJzogewogICAgdGl0bGU6ICdST0UgKMOWemtheW5hayBLw6JybMSxbMSxxJ/EsSknLAogICAgZGVzYzogJ8WeaXJrZXRpbiDDtnogc2VybWF5ZXNpeWxlIG5lIGthZGFyIGvDonIgZXR0acSfaW5pIGfDtnN0ZXJpci4gWcO8a3NlayBST0UgPSBzZXJtYXlleWkgdmVyaW1saSBrdWxsYW7EsXlvci4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMjUnLGNvbG9yOidncmVlbicsZGVzYzonw4dvayBnw7zDp2zDvCDigJQgQ0FOU0xJTSBpZGVhbCBzZXZpeWVzaSd9LAogICAgICB7bGFiZWw6JyUxNS0yNScsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpJ30sCiAgICAgIHtsYWJlbDonJTgtMTUnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGEnfSwKICAgICAge2xhYmVsOic8OCcsY29sb3I6J3JlZCcsZGVzYzonWmF5xLFmJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQSBrcml0ZXJpIOKAlCBtaW5pbXVtICUxNyBvbG1hbMSxJwogIH0sCiAgJ0dyb3NzTWFyZ2luJzogewogICAgdGl0bGU6ICdCcsO8dCBNYXJqaW4nLAogICAgZGVzYzogJ1NhdMSxxZ8gZ2VsaXJpbmRlbiDDvHJldGltIG1hbGl5ZXRpIGTDvMWfw7xsZMO8a3RlbiBzb25yYSBrYWxhbiBvcmFuLiBTZWt0w7ZyZSBnw7ZyZSBkZcSfacWfaXIuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgR2Vyw6dlayB2ZXJpJywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic+JTUwJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8OHb2sgZ8O8w6dsw7wg4oCUIHlhesSxbMSxbS9TYWFTIHNldml5ZXNpJ30sCiAgICAgIHtsYWJlbDonJTMwLTUwJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWknfSwKICAgICAge2xhYmVsOiclMTUtMzAnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGEg4oCUIGRvbmFuxLFtL3lhcsSxIGlsZXRrZW4gbm9ybWFsJ30sCiAgICAgIHtsYWJlbDonPDE1Jyxjb2xvcjoncmVkJyxkZXNjOidEw7zFn8O8ayBtYXJqaW4nfQogICAgXSwKICAgIGNhbnNsaW06ICdLw6JybMSxbMSxayBrYWxpdGVzaSBnw7ZzdGVyZ2VzaScKICB9LAogIC8vIEfEsFLEsMWeCiAgJ0VudHJ5U2NvcmUnOiB7CiAgICB0aXRsZTogJ0dpcmnFnyBLYWxpdGVzaSBTa29ydScsCiAgICBkZXNjOiAnUlNJLCBTTUEgcG96aXN5b251LCBQL0UsIFBFRyB2ZSBFUFMgYsO8ecO8bWVzaW5pIGJpcmxlxZ90aXJlbiBiaWxlxZ9payBza29yLiAwLTEwMCBhcmFzxLEuJywKICAgIHNvdXJjZTogJ0JpemltIGhlc2FwbGFtYScsCiAgICByZWxpYWJpbGl0eTogJ2xvdycsCiAgICB3YXJuaW5nOiAnQlUgVVlHVUxBTUEgVEFSQUZJTkRBTiBIRVNBUExBTkFOIEtBQkEgVEFITcSwTkTEsFIuIFlhdMSxcsSxbSBrYXJhcsSxIGnDp2luIHRlayBiYcWfxLFuYSBrdWxsYW5tYS4nLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonNzUtMTAwJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1VjdXog4oCUIGlkZWFsIGdpcmnFnyBiw7ZsZ2VzaSd9LAogICAgICB7bGFiZWw6JzYwLTc1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J01ha3VsIGZpeWF0J30sCiAgICAgIHtsYWJlbDonNDUtNjAnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J07DtnRyJ30sCiAgICAgIHtsYWJlbDonMzAtNDUnLGNvbG9yOidyZWQnLGRlc2M6J1BhaGFsxLEg4oCUIGJla2xlJ30sCiAgICAgIHtsYWJlbDonMC0zMCcsY29sb3I6J3JlZCcsZGVzYzonw4dvayBwYWhhbMSxIOKAlCBnaXJtZSd9CiAgICBdLAogICAgY2Fuc2xpbTogJ1TDvG0ga3JpdGVybGVyIGJpbGXFn2ltaScKICB9LAogICdSUic6IHsKICAgIHRpdGxlOiAnUmlzay/DlmTDvGwgT3JhbsSxIChSL1IpJywKICAgIGRlc2M6ICdQb3RhbnNpeWVsIGthemFuY8SxbiByaXNrZSBvcmFuxLEuIDE6MiBkZW1layAxJCByaXNrZSBrYXLFn8SxIDIkIGthemFuw6cgcG90YW5zaXllbGkgdmFyIGRlbWVrLicsCiAgICBzb3VyY2U6ICdCaXppbSBoZXNhcGxhbWEnLAogICAgcmVsaWFiaWxpdHk6ICdsb3cnLAogICAgd2FybmluZzogJ0dpcmnFny9oZWRlZi9zdG9wIHNldml5ZWxlcmkgZm9ybcO8bCBiYXpsxLEga2FiYSB0YWhtaW5kaXInLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonMTozKycsY29sb3I6J2dyZWVuJyxkZXNjOidNw7xrZW1tZWwg4oCUIGfDvMOnbMO8IGdpcmnFnyBzaW55YWxpJ30sCiAgICAgIHtsYWJlbDonMToyJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWkg4oCUIG1pbmltdW0ga2FidWwgZWRpbGViaWxpcid9LAogICAgICB7bGFiZWw6JzE6MScsY29sb3I6J3llbGxvdycsZGVzYzonWmF5xLFmJ30sCiAgICAgIHtsYWJlbDonPDE6MScsY29sb3I6J3JlZCcsZGVzYzonUmlzayBrYXphbsOndGFuIGLDvHnDvGsg4oCUIGdpcm1lJ30KICAgIF0sCiAgICBjYW5zbGltOiAnUmlzayB5w7ZuZXRpbWknCiAgfSwKICAvLyBFQVJOSU5HUwogICdFYXJuaW5nc0RhdGUnOiB7CiAgICB0aXRsZTogJ1JhcG9yIFRhcmloaSAoRWFybmluZ3MgRGF0ZSknLAogICAgZGVzYzogJ8WeaXJrZXRpbiDDp2V5cmVrIGZpbmFuc2FsIHNvbnXDp2xhcsSxbsSxIGHDp8Sxa2xheWFjYcSfxLEgdGFyaWguIFJhcG9yIMO2bmNlc2kgdmUgc29ucmFzxLEgZml5YXQgc2VydCBoYXJla2V0IGVkZWJpbGlyLicsCiAgICBzb3VyY2U6ICd5ZmluYW5jZSDigJQgYmF6ZW4gaGF0YWzEsSBvbGFiaWxpcicsCiAgICByZWxpYWJpbGl0eTogJ21lZGl1bScsCiAgICB3YXJuaW5nOiAnVGFyaWhsZXJpIHJlc21pIElSIHNheWZhc8SxbmRhbiBkb8SfcnVsYXnEsW4nLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonNyBnw7xuIGnDp2luZGUnLGNvbG9yOidyZWQnLGRlc2M6J8OHb2sgeWFrxLFuIOKAlCBwb3ppc3lvbiBhw6dtYWsgcmlza2xpJ30sCiAgICAgIHtsYWJlbDonOC0xNCBnw7xuJyxjb2xvcjoneWVsbG93JyxkZXNjOidZYWvEsW4g4oCUIGRpa2thdGxpIG9sJ30sCiAgICAgIHtsYWJlbDonMTQrIGfDvG4nLGNvbG9yOidncmVlbicsZGVzYzonWWV0ZXJsaSBzw7xyZSB2YXInfQogICAgXSwKICAgIGNhbnNsaW06ICdDIGtyaXRlcmkg4oCUIMOnZXlyZWsgcmFwb3Iga2FsaXRlc2knCiAgfSwKICAnQXZnTW92ZSc6IHsKICAgIHRpdGxlOiAnT3J0YWxhbWEgUmFwb3IgSGFyZWtldGknLAogICAgZGVzYzogJ1NvbiA0IMOnZXlyZWsgcmFwb3J1bmRhLCByYXBvciBnw7xuw7wgdmUgZXJ0ZXNpIGfDvG4gZml5YXTEsW4gb3J0YWxhbWEgbmUga2FkYXIgaGFyZWtldCBldHRpxJ9pLicsCiAgICBzb3VyY2U6ICdCaXppbSBoZXNhcGxhbWEnLAogICAgcmVsaWFiaWxpdHk6ICdtZWRpdW0nLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonUG96aXRpZiAoPiU1KScsY29sb3I6J2dyZWVuJyxkZXNjOifFnmlya2V0IGdlbmVsbGlrbGUgYmVrbGVudGl5aSBhxZ/EsXlvcid9LAogICAgICB7bGFiZWw6J07DtnRyICglMC01KScsY29sb3I6J3llbGxvdycsZGVzYzonS2FyxLHFn8SxayBnZcOnbWnFnyd9LAogICAgICB7bGFiZWw6J05lZ2F0aWYnLGNvbG9yOidyZWQnLGRlc2M6J1JhcG9yIGTDtm5lbWluZGUgZml5YXQgZ2VuZWxsaWtsZSBkw7zFn8O8eW9yIOKAlCBkaWtrYXQnfQogICAgXSwKICAgIGNhbnNsaW06ICdDIGtyaXRlcmkg4oCUIGthemFuw6cgc8O8cnByaXppIGdlw6dtacWfaScKICB9Cn07CgpmdW5jdGlvbiBzaG93SW5mbyhrZXksZXZlbnQpewogIGlmKGV2ZW50KSBldmVudC5zdG9wUHJvcGFnYXRpb24oKTsKICB2YXIgbT1NRVRSSUNTW2tleV07IGlmKCFtKSByZXR1cm47CiAgdmFyIHJlbExhYmVsPW0ucmVsaWFiaWxpdHk9PT0iaGlnaCI/IkfDvHZlbmlsaXIiOm0ucmVsaWFiaWxpdHk9PT0ibWVkaXVtIj8iT3J0YSBHw7x2ZW5pbGlyIjoiS2FiYSBUYWhtaW4iOwogIHZhciBoPSc8ZGl2IGNsYXNzPSJtaW5mby10aXRsZSI+JyttLnRpdGxlKyc8L2Rpdj4nOwogIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby1zb3VyY2UiPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPicrbS5zb3VyY2UrJzwvc3Bhbj48c3BhbiBjbGFzcz0ibWluZm8tcmVsICcrbS5yZWxpYWJpbGl0eSsnIj4nK3JlbExhYmVsKyc8L3NwYW4+PC9kaXY+JzsKICBoKz0nPGRpdiBjbGFzcz0ibWluZm8tZGVzYyI+JyttLmRlc2MrJzwvZGl2Pic7CiAgaWYobS53YXJuaW5nKSBoKz0nPGRpdiBjbGFzcz0ibWluZm8td2FybmluZyI+4pqg77iPICcrbS53YXJuaW5nKyc8L2Rpdj4nOwogIGlmKG0ucmFuZ2VzJiZtLnJhbmdlcy5sZW5ndGgpewogICAgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLXJhbmdlcyI+PGRpdiBjbGFzcz0ibWluZm8tcmFuZ2UtdGl0bGUiPlJlZmVyYW5zIERlZ2VybGVyPC9kaXY+JzsKICAgIG0ucmFuZ2VzLmZvckVhY2goZnVuY3Rpb24ocil7dmFyIGRjPXIuY29sb3I9PT0iZ3JlZW4iPyIjMTBiOTgxIjpyLmNvbG9yPT09InJlZCI/IiNlZjQ0NDQiOiIjZjU5ZTBiIjtoKz0nPGRpdiBjbGFzcz0ibWluZm8tcmFuZ2UiPjxkaXYgY2xhc3M9Im1pbmZvLXJhbmdlLWRvdCIgc3R5bGU9ImJhY2tncm91bmQ6JytkYysnIj48L2Rpdj48ZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjonK2RjKyciPicrci5sYWJlbCsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK3IuZGVzYysnPC9kaXY+PC9kaXY+PC9kaXY+Jzt9KTsKICAgIGgrPSc8L2Rpdj4nOwogIH0KICBpZihtLmNhbnNsaW0pIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby1jYW5zbGltIj7wn5OKIENBTlNMSU06ICcrbS5jYW5zbGltKyc8L2Rpdj4nOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb0NvbnRlbnQiKS5pbm5lckhUTUw9aDsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWluZm9Qb3B1cCIpLmNsYXNzTGlzdC5hZGQoIm9wZW4iKTsKfQpmdW5jdGlvbiBjbG9zZUluZm9Qb3B1cChlKXtpZighZXx8ZS50YXJnZXQ9PT1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWluZm9Qb3B1cCIpKXtkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWluZm9Qb3B1cCIpLmNsYXNzTGlzdC5yZW1vdmUoIm9wZW4iKTt9fQoKPC9zY3JpcHQ+CjxzY3JpcHQ+CnZhciBURl9EQVRBPSUlVEZfREFUQSUlOwp2YXIgUE9SVD0lJVBPUlQlJTsKdmFyIEVBUk5JTkdTX0RBVEE9JSVFQVJOSU5HU19EQVRBJSU7CnZhciBNQVJLRVRfREFUQT0lJU1BUktFVF9EQVRBJSU7CnZhciBORVdTX0RBVEE9JSVORVdTX0RBVEElJTsKdmFyIEFJX0RBVEE9JSVBSV9EQVRBJSU7CnZhciBXRUVLTFlfREFUQT0lJVdFRUtMWV9EQVRBJSU7CnZhciBXRUVLTFlfREFUQT0lJVdFRUtMWV9EQVRBJSU7CnZhciBjdXJUYWI9ImFsbCIsY3VyVGY9IjFkIixjdXJEYXRhPVRGX0RBVEFbIjFkIl0uc2xpY2UoKTsKdmFyIG1pbmlDaGFydHM9e30sbUNoYXJ0PW51bGw7CnZhciBTUz17CiAgIkdVQ0xVIEFMIjp7Ymc6InJnYmEoMTYsMTg1LDEyOSwuMTIpIixiZDoicmdiYSgxNiwxODUsMTI5LC4zNSkiLHR4OiIjMTBiOTgxIixhYzoiIzEwYjk4MSIsbGJsOiJHVUNMVSBBTCJ9LAogICJBTCI6e2JnOiJyZ2JhKDUyLDIxMSwxNTMsLjEpIixiZDoicmdiYSg1MiwyMTEsMTUzLC4zKSIsdHg6IiMzNGQzOTkiLGFjOiIjMzRkMzk5IixsYmw6IkFMIn0sCiAgIkRJS0tBVCI6e2JnOiJyZ2JhKDI0NSwxNTgsMTEsLjEpIixiZDoicmdiYSgyNDUsMTU4LDExLC4zKSIsdHg6IiNmNTllMGIiLGFjOiIjZjU5ZTBiIixsYmw6IkRJS0tBVCJ9LAogICJaQVlJRiI6e2JnOiJyZ2JhKDEwNywxMTQsMTI4LC4xKSIsYmQ6InJnYmEoMTA3LDExNCwxMjgsLjMpIix0eDoiIzljYTNhZiIsYWM6IiM2YjcyODAiLGxibDoiWkFZSUYifSwKICAiU0FUIjp7Ymc6InJnYmEoMjM5LDY4LDY4LC4xMikiLGJkOiJyZ2JhKDIzOSw2OCw2OCwuMzUpIix0eDoiI2VmNDQ0NCIsYWM6IiNlZjQ0NDQiLGxibDoiU0FUIn0KfTsKCmZ1bmN0aW9uIGliKGtleSxsYWJlbCl7CiAgcmV0dXJuIGxhYmVsKycgPHNwYW4gY2xhc3M9Im1pbmZvIiBvbmNsaWNrPSJzaG93SW5mbyhcJycra2V5KydcJyxldmVudCkiPj88L3NwYW4+JzsKfQoKZnVuY3Rpb24gc2V0VGFiKHQsZWwpewogIGN1clRhYj10OwogIGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoIi50YWIiKS5mb3JFYWNoKGZ1bmN0aW9uKGIpe2IuY2xhc3NMaXN0LnJlbW92ZSgiYWN0aXZlIik7fSk7CiAgZWwuY2xhc3NMaXN0LmFkZCgiYWN0aXZlIik7CiAgdmFyIHRmUm93PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0ZlJvdyIpOwogIGlmKHRmUm93KSB0ZlJvdy5zdHlsZS5kaXNwbGF5PSh0PT09ImRhc2hib2FyZCJ8fHQ9PT0iZWFybmluZ3MifHx0PT09InJ1dGluInx8dD09PSJoYWZ0YWxpayIpPyJub25lIjoiZmxleCI7CiAgaWYodD09PSJkYXNoYm9hcmQiKSByZW5kZXJEYXNoYm9hcmQoKTsKICBlbHNlIGlmKHQ9PT0iZWFybmluZ3MiKSByZW5kZXJFYXJuaW5ncygpOwogIGVsc2UgaWYodD09PSJydXRpbiIpIHJlbmRlclJ1dGluKCk7CiAgZWxzZSBpZih0PT09ImhhZnRhbGlrIikgcmVuZGVySGFmdGFsaWsoKTsKICBlbHNlIHJlbmRlckdyaWQoKTsKfQoKZnVuY3Rpb24gc2V0VGYodGYsZWwpewogIGN1clRmPXRmOwogIGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoIi50Zi1idG4iKS5mb3JFYWNoKGZ1bmN0aW9uKGIpe2IuY2xhc3NMaXN0LnRvZ2dsZSgiYWN0aXZlIixiLmRhdGFzZXQudGY9PT10Zik7fSk7CiAgY3VyRGF0YT0oVEZfREFUQVt0Zl18fFRGX0RBVEFbIjFkIl0pLnNsaWNlKCk7CiAgcmVuZGVyU3RhdHMoKTsKICByZW5kZXJHcmlkKCk7Cn0KCmZ1bmN0aW9uIGZpbHRlcmVkKCl7CiAgdmFyIGQ9Y3VyRGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSk7CiAgaWYoY3VyVGFiPT09InBvcnQiKSByZXR1cm4gZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIFBPUlQuaW5jbHVkZXMoci50aWNrZXIpO30pOwogIGlmKGN1clRhYj09PSJidXkiKSByZXR1cm4gZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09IkdVQ0xVIEFMInx8ci5zaW55YWw9PT0iQUwiO30pOwogIGlmKGN1clRhYj09PSJzZWxsIikgcmV0dXJuIGQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSJTQVQiO30pOwogIHJldHVybiBkOwp9CgpmdW5jdGlvbiByZW5kZXJTdGF0cygpewogIHZhciBkPWN1ckRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pOwogIHZhciBjbnQ9e307CiAgZC5mb3JFYWNoKGZ1bmN0aW9uKHIpe2NudFtyLnNpbnlhbF09KGNudFtyLnNpbnlhbF18fDApKzE7fSk7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInN0YXRzIikuaW5uZXJIVE1MPQogICAgJzxkaXYgY2xhc3M9InBpbGwgZyI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5HdWNsdSBBbDogJysoY250WyJHVUNMVSBBTCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIGciPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+QWw6ICcrKGNudFsiQUwiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCB5Ij48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PkRpa2thdDogJysoY250WyJESUtLQVQiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCByIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PlNhdDogJysoY250WyJTQVQiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCBiIiBzdHlsZT0ibWFyZ2luLWxlZnQ6YXV0byI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5Qb3J0Zm9seW86ICcrUE9SVC5sZW5ndGgrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCBtIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PicrZC5sZW5ndGgrJyBhbmFsaXo8L2Rpdj4nOwp9CgpmdW5jdGlvbiByZW5kZXJHcmlkKCl7CiAgT2JqZWN0LnZhbHVlcyhtaW5pQ2hhcnRzKS5mb3JFYWNoKGZ1bmN0aW9uKGMpe2MuZGVzdHJveSgpO30pOwogIG1pbmlDaGFydHM9e307CiAgdmFyIGY9ZmlsdGVyZWQoKTsKICB2YXIgZ3JpZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ3JpZCIpOwogIGlmKCFmLmxlbmd0aCl7Z3JpZC5pbm5lckhUTUw9JzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTE7dGV4dC1hbGlnbjpjZW50ZXI7cGFkZGluZzo0MHB4O2NvbG9yOnZhcigtLW11dGVkKSI+SGlzc2UgYnVsdW5hbWFkaTwvZGl2Pic7cmV0dXJuO30KICBncmlkLmlubmVySFRNTD1mLm1hcChmdW5jdGlvbihyKXtyZXR1cm4gYnVpbGRDYXJkKHIpO30pLmpvaW4oIiIpOwogIGYuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBjdHg9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1jLSIrci50aWNrZXIpOwogICAgaWYoY3R4JiZyLmNoYXJ0X2Nsb3NlcyYmci5jaGFydF9jbG9zZXMubGVuZ3RoKXsKICAgICAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogICAgICBtaW5pQ2hhcnRzWyJtIityLnRpY2tlcl09bmV3IENoYXJ0KGN0eCx7dHlwZToibGluZSIsZGF0YTp7bGFiZWxzOnIuY2hhcnRfZGF0ZXMsZGF0YXNldHM6W3tkYXRhOnIuY2hhcnRfY2xvc2VzLGJvcmRlckNvbG9yOnNzLmFjLGJvcmRlcldpZHRoOjEuNSxmaWxsOnRydWUsYmFja2dyb3VuZENvbG9yOnNzLmFjKyIxOCIscG9pbnRSYWRpdXM6MCx0ZW5zaW9uOjAuNH1dfSxvcHRpb25zOntwbHVnaW5zOntsZWdlbmQ6e2Rpc3BsYXk6ZmFsc2V9fSxzY2FsZXM6e3g6e2Rpc3BsYXk6ZmFsc2V9LHk6e2Rpc3BsYXk6ZmFsc2V9fSxhbmltYXRpb246e2R1cmF0aW9uOjUwMH0scmVzcG9uc2l2ZTp0cnVlLG1haW50YWluQXNwZWN0UmF0aW86ZmFsc2V9fSk7CiAgICB9CiAgfSk7Cn0KCmZ1bmN0aW9uIGJ1aWxkQ2FyZChyKXsKICB2YXIgc3M9U1Nbci5zaW55YWxdfHxTU1siRElLS0FUIl07CiAgdmFyIGRjPXIuZGVnaXNpbT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICB2YXIgZHM9KHIuZGVnaXNpbT49MD8iKyI6IiIpK3IuZGVnaXNpbSsiJSI7CiAgdmFyIGVzY29sPXIuZW50cnlfc2NvcmU+PTc1PyJ2YXIoLS1ncmVlbikiOnIuZW50cnlfc2NvcmU+PTYwPyJ2YXIoLS1ncmVlbjIpIjpyLmVudHJ5X3Njb3JlPj00NT8idmFyKC0teWVsbG93KSI6ci5lbnRyeV9zY29yZT49MzA/InZhcigtLXJlZDIpIjoidmFyKC0tcmVkKSI7CiAgdmFyIHB2Y29sPXIucHJpY2VfdnNfY29sb3I9PT0iZ3JlZW4iPyJ2YXIoLS1ncmVlbikiOnIucHJpY2VfdnNfY29sb3I9PT0ieWVsbG93Ij8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZDIpIjsKICB2YXIgc2lncz1bCiAgICB7bDoiVHJlbmQiLHY6ci50cmVuZD09PSJZdWtzZWxlbiI/Ill1a3NlbGl5b3IiOnIudHJlbmQ9PT0iRHVzZW4iPyJEdXN1eW9yIjoiWWF0YXkiLGc6ci50cmVuZD09PSJZdWtzZWxlbiI/dHJ1ZTpyLnRyZW5kPT09IkR1c2VuIj9mYWxzZTpudWxsfSwKICAgIHtsOiJTTUE1MCIsdjpyLmFib3ZlNTA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIsZzpyLmFib3ZlNTB9LAogICAge2w6IlNNQTIwMCIsdjpyLmFib3ZlMjAwPyJVemVyaW5kZSI6IkFsdGluZGEiLGc6ci5hYm92ZTIwMH0sCiAgICB7bDoiUlNJIix2OnIucnNpfHwiPyIsZzpyLnJzaT9yLnJzaTwzMD90cnVlOnIucnNpPjcwP2ZhbHNlOm51bGw6bnVsbH0sCiAgICB7bDoiNTJXIix2OiIlIityLnBjdF9mcm9tXzUydysiIHV6YWsiLGc6ci5uZWFyXzUyd30KICBdLm1hcChmdW5jdGlvbihzKXtyZXR1cm4gJzxzcGFuIGNsYXNzPSJzcCAnKyhzLmc9PT10cnVlPyJzZyI6cy5nPT09ZmFsc2U/InNiIjoic24iKSsnIj4nK3MubCsiOiAiK3MudisiPC9zcGFuPiI7fSkuam9pbigiIik7CiAgcmV0dXJuICc8ZGl2IGNsYXNzPSJjYXJkIiBzdHlsZT0iYm9yZGVyLWNvbG9yOicrKHIucG9ydGZvbGlvPyJyZ2JhKDE2LDE4NSwxMjksLjI1KSI6c3MuYmQpKyciIG9uY2xpY2s9Im9wZW5NKFwnJytyLnRpY2tlcisnXCcpIj4nCiAgICArJzxkaXYgY2xhc3M9ImFjY2VudCIgc3R5bGU9ImJhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDkwZGVnLCcrc3MuYWMrJywnK3NzLmFjKyc4OCkiPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iY2JvZHkiPjxkaXYgY2xhc3M9ImN0b3AiPjxkaXY+PGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NHB4Ij4nCiAgICArJzxzcGFuIGNsYXNzPSJ0aWNrZXIiIHN0eWxlPSJjb2xvcjonK3NzLnR4KyciPicrci50aWNrZXIrJzwvc3Bhbj4nCiAgICArKHIucG9ydGZvbGlvPyc8c3BhbiBjbGFzcz0icG9ydC1iYWRnZSI+UDwvc3Bhbj4nOicnKSsKICAgICc8L2Rpdj48c3BhbiBjbGFzcz0iYmFkZ2UiIHN0eWxlPSJiYWNrZ3JvdW5kOicrc3MuYmcrJztjb2xvcjonK3NzLnR4Kyc7Ym9yZGVyOjFweCBzb2xpZCAnK3NzLmJkKyciPicrc3MubGJsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJjcHIiPjxkaXYgY2xhc3M9InB2YWwiPiQnK3IuZml5YXQrJzwvZGl2PjxkaXYgY2xhc3M9InBjaGciIHN0eWxlPSJjb2xvcjonK2RjKyciPicrZHMrJzwvZGl2PicKICAgICsoci5wZV9md2Q/JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5Gd2RQRTonK3IucGVfZndkLnRvRml4ZWQoMSkrJzwvZGl2Pic6JycpCiAgICArJzwvZGl2PjwvZGl2PjxkaXYgY2xhc3M9InNpZ3MiPicrc2lncysnPC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJtYXJnaW4tdG9wOjZweCI+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47bWFyZ2luLWJvdHRvbTozcHgiPjxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+R2lyaXMgS2FsaXRlc2k8L3NwYW4+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK2VzY29sKyciPicrci5lbnRyeV9zY29yZSsnLzEwMDwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImhlaWdodDo0cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6MnB4O292ZXJmbG93OmhpZGRlbiI+PGRpdiBzdHlsZT0iaGVpZ2h0OjEwMCU7d2lkdGg6JytyLmVudHJ5X3Njb3JlKyclO2JhY2tncm91bmQ6Jytlc2NvbCsnO2JvcmRlci1yYWRpdXM6MnB4Ij48L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tdG9wOjNweCI+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfbGFiZWwrJzwvc3Bhbj48c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK3B2Y29sKyciPicrci5wcmljZV92c19pZGVhbCsnPC9zcGFuPjwvZGl2PicKICAgICsnPC9kaXY+PGRpdiBjbGFzcz0iY2hhcnQtdyI+PGNhbnZhcyBpZD0ibWMtJytyLnRpY2tlcisnIj48L2NhbnZhcz48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9Imx2bHMiPicKICAgICsnPGRpdiBjbGFzcz0ibHYiPjxkaXYgY2xhc3M9ImxsIj5IZW1lbiBHaXI8L2Rpdj48ZGl2IGNsYXNzPSJsdmFsIiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4yKSI+JCcrci5lbnRyeV9hZ2dyZXNzaXZlKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9Imx2Ij48ZGl2IGNsYXNzPSJsbCI+SGVkZWY8L2Rpdj48ZGl2IGNsYXNzPSJsdmFsIiBzdHlsZT0iY29sb3I6IzYwYTVmYSI+JCcrci5oZWRlZisnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJsdiI+PGRpdiBjbGFzcz0ibGwiPlN0b3A8L2Rpdj48ZGl2IGNsYXNzPSJsdmFsIiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMikiPiQnK3Iuc3RvcCsnPC9kaXY+PC9kaXY+JwogICAgKyc8L2Rpdj48L2Rpdj48L2Rpdj4nOwp9CgpmdW5jdGlvbiByZW5kZXJEYXNoYm9hcmQoKXsKICB2YXIgZ3JpZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ3JpZCIpOwogIHZhciBtZD1NQVJLRVRfREFUQXx8e307CiAgdmFyIHNwPW1kLlNQNTAwfHx7fTsKICB2YXIgbmFzPW1kLk5BU0RBUXx8e307CiAgdmFyIHZpeD1tZC5WSVh8fHt9OwogIHZhciBtU2lnbmFsPW1kLk1fU0lHTkFMfHwiTk9UUiI7CiAgdmFyIG1MYWJlbD1tZC5NX0xBQkVMfHwiVmVyaSB5b2siOwogIHZhciBtQ29sb3I9bVNpZ25hbD09PSJHVUNMVSI/InZhcigtLWdyZWVuKSI6bVNpZ25hbD09PSJaQVlJRiI/InZhcigtLXJlZDIpIjoidmFyKC0teWVsbG93KSI7CiAgdmFyIG1CZz1tU2lnbmFsPT09IkdVQ0xVIj8icmdiYSgxNiwxODUsMTI5LC4wOCkiOm1TaWduYWw9PT0iWkFZSUYiPyJyZ2JhKDIzOSw2OCw2OCwuMDgpIjoicmdiYSgyNDUsMTU4LDExLC4wOCkiOwogIHZhciBtQm9yZGVyPW1TaWduYWw9PT0iR1VDTFUiPyJyZ2JhKDE2LDE4NSwxMjksLjI1KSI6bVNpZ25hbD09PSJaQVlJRiI/InJnYmEoMjM5LDY4LDY4LC4yNSkiOiJyZ2JhKDI0NSwxNTgsMTEsLjI1KSI7CiAgdmFyIG1JY29uPW1TaWduYWw9PT0iR1VDTFUiPyLinIUiOm1TaWduYWw9PT0iWkFZSUYiPyLinYwiOiLimqDvuI8iOwoKICBmdW5jdGlvbiBpbmRleENhcmQobmFtZSxkYXRhKXsKICAgIGlmKCFkYXRhfHwhZGF0YS5wcmljZSkgcmV0dXJuICIiOwogICAgdmFyIGNjPWRhdGEuY2hhbmdlPj0wPyJ2YXIoLS1ncmVlbjIpIjoidmFyKC0tcmVkMikiOwogICAgdmFyIGNzPShkYXRhLmNoYW5nZT49MD8iKyI6IiIpK2RhdGEuY2hhbmdlKyIlIjsKICAgIHZhciBzNTA9ZGF0YS5hYm92ZTUwPyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZToxMHB4Ij5TTUE1MCDinJM8L3NwYW4+JzonPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpO2ZvbnQtc2l6ZToxMHB4Ij5TTUE1MCDinJc8L3NwYW4+JzsKICAgIHZhciBzMjAwPWRhdGEuYWJvdmUyMDA/JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjEwcHgiPlNNQTIwMCDinJM8L3NwYW4+JzonPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpO2ZvbnQtc2l6ZToxMHB4Ij5TTUEyMDAg4pyXPC9zcGFuPic7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCAxNnB4O2ZsZXg6MTttaW4td2lkdGg6MTUwcHgiPicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo2cHgiPicrbmFtZSsnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2U7Zm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpIj4kJytkYXRhLnByaWNlKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZTtmb250LXNpemU6MTNweDtjb2xvcjonK2NjKyc7bWFyZ2luLWJvdHRvbTo4cHgiPicrY3MrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjhweCI+JytzNTArczIwMCsnPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciBwb3J0RGF0YT1jdXJEYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YSYmUE9SVC5pbmNsdWRlcyhyLnRpY2tlcik7fSk7CiAgdmFyIHBvcnRIdG1sPSIiOwogIGlmKHBvcnREYXRhLmxlbmd0aCl7CiAgICBwb3J0SHRtbD0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTRweCI+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTJweCI+8J+SvCBQb3J0ZsO2eSDDlnpldGk8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgxNDBweCwxZnIpKTtnYXA6OHB4Ij4nOwogICAgcG9ydERhdGEuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgICAgdmFyIGRjPXIuZGVnaXNpbT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICAgICAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogICAgICBwb3J0SHRtbCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkICcrc3MuYmQrJztib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHg7Y3Vyc29yOnBvaW50ZXIiIG9uY2xpY2s9Im9wZW5NKFwnJytyLnRpY2tlcisnXCcpIj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6XCdCZWJhcyBOZXVlXCcsc2Fucy1zZXJpZjtmb250LXNpemU6MTZweDtsZXR0ZXItc3BhY2luZzoycHg7Y29sb3I6Jytzcy50eCsnIj4nK3IudGlja2VyKyc8L3NwYW4+JwogICAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7YmFja2dyb3VuZDonK3NzLmJnKyc7Y29sb3I6Jytzcy50eCsnO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjJweCI+Jytzcy5sYmwrJzwvc3Bhbj48L2Rpdj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpcJ0pldEJyYWlucyBNb25vXCcsbW9ub3NwYWNlO2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMCI+JCcrci5maXlhdCsnPC9kaXY+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZTtmb250LXNpemU6MTFweDtjb2xvcjonK2RjKyciPicrKHIuZGVnaXNpbT49MD8iKyI6IiIpK3IuZGVnaXNpbSsnJTwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICAgIHBvcnRIdG1sKz0nPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciB1cmdlbnRFYXJuaW5ncz1FQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gZS5hbGVydD09PSJyZWQifHxlLmFsZXJ0PT09InllbGxvdyI7fSk7CiAgdmFyIGVhcm5pbmdzQWxlcnQ9IiI7CiAgaWYodXJnZW50RWFybmluZ3MubGVuZ3RoKXsKICAgIGVhcm5pbmdzQWxlcnQ9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE0cHggMTZweDttYXJnaW4tYm90dG9tOjE0cHgiPicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS15ZWxsb3cpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7imqDvuI8gWWFrbGHFn2FuIFJhcG9ybGFyPC9kaXY+JzsKICAgIHVyZ2VudEVhcm5pbmdzLmZvckVhY2goZnVuY3Rpb24oZSl7CiAgICAgIHZhciBpYz1lLmFsZXJ0PT09InJlZCI/IvCflLQiOiLwn5+hIjsKICAgICAgZWFybmluZ3NBbGVydCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbTo2cHg7Zm9udC1zaXplOjEycHgiPicKICAgICAgICArJzxzcGFuPicraWMrJyA8c3Ryb25nPicrZS50aWNrZXIrJzwvc3Ryb25nPjwvc3Bhbj4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj4nK2UubmV4dF9kYXRlKycgKCcrKGUuZGF5c190b19lYXJuaW5ncz09PTA/IkJVR8OcTiI6ZS5kYXlzX3RvX2Vhcm5pbmdzKyIgZ8O8biIpKycpPC9zcGFuPjwvZGl2Pic7CiAgICB9KTsKICAgIGVhcm5pbmdzQWxlcnQrPSc8L2Rpdj4nOwogIH0KCiAgdmFyIG5ld3NIdG1sPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHgiPicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMnB4Ij7wn5OwIFNvbiBIYWJlcmxlcjwvZGl2Pic7CiAgaWYoTkVXU19EQVRBJiZORVdTX0RBVEEubGVuZ3RoKXsKICAgIE5FV1NfREFUQS5zbGljZSgwLDEwKS5mb3JFYWNoKGZ1bmN0aW9uKG4pewogICAgICB2YXIgcGI9bi5wb3J0Zm9saW8/JzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTIpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMjUpO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMCI+UDwvc3Bhbj4nOiIiOwogICAgICB2YXIgdGE9IiI7CiAgICAgIGlmKG4uZGF0ZXRpbWUpe3ZhciBkaWZmPU1hdGguZmxvb3IoKERhdGUubm93KCkvMTAwMC1uLmRhdGV0aW1lKS8zNjAwKTt0YT1kaWZmPDI0PyhkaWZmKyJzIMO2bmNlIik6KE1hdGguZmxvb3IoZGlmZi8yNCkrImcgw7ZuY2UiKTt9CiAgICAgIG5ld3NIdG1sKz0nPGRpdiBzdHlsZT0icGFkZGluZzoxMHB4IDA7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDQpIj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo2cHg7bWFyZ2luLWJvdHRvbTo0cHgiPicKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0teWVsbG93KSI+JytuLnRpY2tlcisnPC9zcGFuPicrcGIKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tbGVmdDphdXRvIj4nK3RhKyc8L3NwYW4+PC9kaXY+JwogICAgICAgICsnPGEgaHJlZj0iJytuLnVybCsnIiB0YXJnZXQ9Il9ibGFuayIgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLXRleHQpO3RleHQtZGVjb3JhdGlvbjpub25lO2xpbmUtaGVpZ2h0OjEuNTtkaXNwbGF5OmJsb2NrIj4nK24uaGVhZGxpbmUrJzwvYT4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLXRvcDozcHgiPicrbi5zb3VyY2UrJzwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICB9IGVsc2UgewogICAgbmV3c0h0bWwrPSc8ZGl2IHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1zaXplOjEycHgiPkhhYmVyIGJ1bHVuYW1hZGk8L2Rpdj4nOwogIH0KICBuZXdzSHRtbCs9JzwvZGl2Pic7CgogIGdyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nCiAgICArJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JyttQmcrJztib3JkZXI6MXB4IHNvbGlkICcrbUJvcmRlcisnO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTJweCI+JwogICAgKyc8ZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7bWFyZ2luLWJvdHRvbTo0cHgiPkNBTlNMSU0gTSBLUsSwVEVSxLA8L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK21Db2xvcisnIj4nK21JY29uKycgJyttTGFiZWwrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO3RleHQtYWxpZ246cmlnaHQiPlZJWDogJysodml4LnByaWNlfHwiPyIpKyc8YnI+JwogICAgKyc8c3BhbiBzdHlsZT0iY29sb3I6Jysodml4LnByaWNlJiZ2aXgucHJpY2U+MjU/InZhcigtLXJlZDIpIjoidmFyKC0tZ3JlZW4pIikrJyI+Jysodml4LnByaWNlJiZ2aXgucHJpY2U+MjU/IlnDvGtzZWsgdm9sYXRpbGl0ZSI6Ik5vcm1hbCB2b2xhdGlsaXRlIikrJzwvc3Bhbj48L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcDttYXJnaW4tYm90dG9tOjE0cHgiPicraW5kZXhDYXJkKCJTJlAgNTAwIChTUFkpIixzcCkraW5kZXhDYXJkKCJOQVNEQVEgKFFRUSkiLG5hcykrJzwvZGl2PicKICAgICtwb3J0SHRtbCtlYXJuaW5nc0FsZXJ0K25ld3NIdG1sKyc8L2Rpdj4nOwp9CgpmdW5jdGlvbiByZW5kZXJFYXJuaW5ncygpewogIHZhciBncmlkPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJncmlkIik7CiAgdmFyIHNvcnRlZD1FQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gZS5uZXh0X2RhdGU7fSkuc29ydChmdW5jdGlvbihhLGIpewogICAgdmFyIGRhPWEuZGF5c190b19lYXJuaW5ncyE9bnVsbD9hLmRheXNfdG9fZWFybmluZ3M6OTk5OwogICAgdmFyIGRiPWIuZGF5c190b19lYXJuaW5ncyE9bnVsbD9iLmRheXNfdG9fZWFybmluZ3M6OTk5OwogICAgcmV0dXJuIGRhLWRiOwogIH0pOwogIHZhciBub0RhdGU9RUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuICFlLm5leHRfZGF0ZTt9KTsKICBpZighc29ydGVkLmxlbmd0aCYmIW5vRGF0ZS5sZW5ndGgpe2dyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xO3RleHQtYWxpZ246Y2VudGVyO3BhZGRpbmc6NDBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkVhcm5pbmdzIHZlcmlzaSBidWx1bmFtYWRpPC9kaXY+JztyZXR1cm47fQogIHZhciBoPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwogIHNvcnRlZC5mb3JFYWNoKGZ1bmN0aW9uKGUpewogICAgdmFyIGFiPWUuYWxlcnQ9PT0icmVkIj8icmdiYSgyMzksNjgsNjgsLjEyKSI6ZS5hbGVydD09PSJ5ZWxsb3ciPyJyZ2JhKDI0NSwxNTgsMTEsLjEpIjoicmdiYSgyNTUsMjU1LDI1NSwuMDIpIjsKICAgIHZhciBhYmQ9ZS5hbGVydD09PSJyZWQiPyJyZ2JhKDIzOSw2OCw2OCwuMzUpIjplLmFsZXJ0PT09InllbGxvdyI/InJnYmEoMjQ1LDE1OCwxMSwuMykiOiJyZ2JhKDI1NSwyNTUsMjU1LC4wNykiOwogICAgdmFyIGFpPWUuYWxlcnQ9PT0icmVkIj8i8J+UtCI6ZS5hbGVydD09PSJ5ZWxsb3ciPyLwn5+hIjoi8J+ThSI7CiAgICB2YXIgZHQ9ZS5kYXlzX3RvX2Vhcm5pbmdzIT1udWxsPyhlLmRheXNfdG9fZWFybmluZ3M9PT0wPyJCVUdVTiI6ZS5kYXlzX3RvX2Vhcm5pbmdzPT09MT8iWWFyaW4iOmUuZGF5c190b19lYXJuaW5ncysiIGd1biBzb25yYSIpOiIiOwogICAgdmFyIGFtQ29sPWUuYXZnX21vdmVfcGN0IT1udWxsPyhlLmF2Z19tb3ZlX3BjdD49MD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkMikiKToidmFyKC0tbXV0ZWQpIjsKICAgIHZhciBhbVN0cj1lLmF2Z19tb3ZlX3BjdCE9bnVsbD8oZS5hdmdfbW92ZV9wY3Q+PTA/IisiOiIiKStlLmF2Z19tb3ZlX3BjdCsiJSI6IuKAlCI7CiAgICB2YXIgeWI9ZS5hbGVydD09PSJyZWQiPyc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMTUpO2NvbG9yOnZhcigtLXJlZDIpO3BhZGRpbmc6MnB4IDhweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDAiPllBS0lOREE8L3NwYW4+JzoiIjsKICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicrYWIrJztib3JkZXI6MXB4IHNvbGlkICcrYWJkKyc7Ym9yZGVyLXJhZGl1czoxMHB4O21hcmdpbi1ib3R0b206MTBweDtwYWRkaW5nOjE0cHggMTZweCI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2ZsZXgtd3JhcDp3cmFwO2dhcDo4cHgiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6MTBweCI+PHNwYW4+JythaSsnPC9zcGFuPjxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpcJ0JlYmFzIE5ldWVcJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyMHB4O2xldHRlci1zcGFjaW5nOjJweDtjb2xvcjp2YXIoLS10ZXh0KSI+JytlLnRpY2tlcisnPC9zcGFuPicreWIrJzwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxNnB4O2ZsZXgtd3JhcDp3cmFwO2FsaWduLWl0ZW1zOmNlbnRlciI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlJBUE9SPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZTtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrKGUubmV4dF9kYXRlfHwi4oCUIikrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOicrKGUuYWxlcnQ9PT0icmVkIj8idmFyKC0tcmVkMikiOmUuYWxlcnQ9PT0ieWVsbG93Ij8idmFyKC0teWVsbG93KSI6InZhcigtLW11dGVkKSIpKyciPicrZHQrJzwvZGl2PjwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5FUFMgVEFITUlOPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZTtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo2MDA7Y29sb3I6IzYwYTVmYSI+JysoZS5lcHNfZXN0aW1hdGUhPW51bGw/IiQiK2UuZXBzX2VzdGltYXRlOiLigJQiKSsnPC9kaXY+PC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPk9SVC5IQVJFS0VUPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZTtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JythbUNvbCsnIj4nK2FtU3RyKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKSI+c29uIDQgcmFwb3I8L2Rpdj48L2Rpdj4nOwogICAgaCs9JzwvZGl2PjwvZGl2Pic7CiAgICBpZihlLmhpc3RvcnlfZXBzJiZlLmhpc3RvcnlfZXBzLmxlbmd0aCl7CiAgICAgIGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW4tdG9wOjhweDtwYWRkaW5nLXRvcDo4cHg7Ym9yZGVyLXRvcDoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjVweCI+U09OIDQgUkFQT1I8L2Rpdj48ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCg0LDFmcik7Z2FwOjRweCI+JzsKICAgICAgZS5oaXN0b3J5X2Vwcy5mb3JFYWNoKGZ1bmN0aW9uKGhoKXsKICAgICAgICB2YXIgc2M9aGguc3VycHJpc2VfcGN0IT1udWxsPyhoaC5zdXJwcmlzZV9wY3Q+MD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkMikiKToidmFyKC0tbXV0ZWQpIjsKICAgICAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6NHB4O3BhZGRpbmc6NnB4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDUpIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytoaC5kYXRlLnN1YnN0cmluZygwLDcpKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LWZhbWlseTpcJ0pldEJyYWlucyBNb25vXCcsbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMHB4Ij4nKyhoaC5hY3R1YWwhPW51bGw/IiQiK2hoLmFjdHVhbDoiPyIpKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrc2MrJyI+JysoaGguc3VycHJpc2VfcGN0IT1udWxsPyhoaC5zdXJwcmlzZV9wY3Q+MD8iKyI6IiIpK2hoLnN1cnByaXNlX3BjdCsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JzsKICAgICAgfSk7CiAgICAgIGgrPSc8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaCs9JzwvZGl2Pic7CiAgfSk7CiAgaWYobm9EYXRlLmxlbmd0aCl7aCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tdG9wOjZweCI+VGFyaWggYnVsdW5hbWF5YW46ICcrbm9EYXRlLm1hcChmdW5jdGlvbihlKXtyZXR1cm4gZS50aWNrZXI7fSkuam9pbigiLCAiKSsnPC9kaXY+Jzt9CiAgaCs9JzwvZGl2Pic7CiAgZ3JpZC5pbm5lckhUTUw9aDsKfQoKZnVuY3Rpb24gb3Blbk0odGlja2VyKXsKICB2YXIgcj1jdXJEYXRhLmZpbmQoZnVuY3Rpb24oZCl7cmV0dXJuIGQudGlja2VyPT09dGlja2VyO30pOwogIGlmKCFyfHxyLmhhdGEpIHJldHVybjsKICBpZihtQ2hhcnQpe21DaGFydC5kZXN0cm95KCk7bUNoYXJ0PW51bGw7fQogIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICB2YXIgcnJQPU1hdGgubWluKChyLnJyLzQpKjEwMCwxMDApOwogIHZhciByckM9ci5ycj49Mz8idmFyKC0tZ3JlZW4pIjpyLnJyPj0yPyJ2YXIoLS1ncmVlbjIpIjpyLnJyPj0xPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkMikiOwogIHZhciBkYz1yLmRlZ2lzaW0+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIGtjPXsiR1VDTFUgQUwiOiIjMTBiOTgxIiwiQUwiOiIjMzRkMzk5IiwiRElLS0FUTEkiOiIjZjU5ZTBiIiwiR0VDTUUiOiIjZjg3MTcxIn07CiAgdmFyIGtsYmw9eyJHVUNMVSBBTCI6IkdVQ0xVIEFMIiwiQUwiOiJBTCIsIkRJS0tBVExJIjoiRElLS0FUTEkiLCJHRUNNRSI6IkdFQ01FIn07CiAgdmFyIGVzY29sPXIuZW50cnlfc2NvcmU+PTc1PyJ2YXIoLS1ncmVlbikiOnIuZW50cnlfc2NvcmU+PTYwPyJ2YXIoLS1ncmVlbjIpIjpyLmVudHJ5X3Njb3JlPj00NT8idmFyKC0teWVsbG93KSI6ci5lbnRyeV9zY29yZT49MzA/InZhcigtLXJlZDIpIjoidmFyKC0tcmVkKSI7CiAgdmFyIHB2Y29sPXIucHJpY2VfdnNfY29sb3I9PT0iZ3JlZW4iPyJ2YXIoLS1ncmVlbikiOnIucHJpY2VfdnNfY29sb3I9PT0ieWVsbG93Ij8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZDIpIjsKCiAgdmFyIG1oPSc8ZGl2IGNsYXNzPSJtaGVhZCI+PGRpdj48ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo4cHg7ZmxleC13cmFwOndyYXAiPicKICAgICsnPHNwYW4gY2xhc3M9Im10aXRsZSIgc3R5bGU9ImNvbG9yOicrc3MudHgrJyI+JytyLnRpY2tlcisnPC9zcGFuPicKICAgICsnPHNwYW4gY2xhc3M9ImJhZGdlIiBzdHlsZT0iYmFja2dyb3VuZDonK3NzLmJnKyc7Y29sb3I6Jytzcy50eCsnO2JvcmRlcjoxcHggc29saWQgJytzcy5iZCsnO2ZvbnQtc2l6ZToxMnB4Ij4nK3NzLmxibCsnPC9zcGFuPicKICAgICsoci5wb3J0Zm9saW8/JzxzcGFuIGNsYXNzPSJwb3J0LWJhZGdlIiBzdHlsZT0iZm9udC1zaXplOjExcHg7cGFkZGluZzozcHggOHB4Ij5Qb3J0Zm9seW88L3NwYW4+JzonJykKICAgICsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZTtmb250LXdlaWdodDo2MDA7bWFyZ2luLXRvcDo0cHgiPiQnK3IuZml5YXQKICAgICsnIDxzcGFuIHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjonK2RjKyciPicrKHIuZGVnaXNpbT49MD8iKyI6IiIpK3IuZGVnaXNpbSsnJTwvc3Bhbj48L2Rpdj48L2Rpdj4nCiAgICArJzxidXR0b24gY2xhc3M9Im1jbG9zZSIgb25jbGljaz0iY2xvc2VNKCkiPuKclTwvYnV0dG9uPjwvZGl2Pic7CgogIG1oKz0nPGRpdiBjbGFzcz0ibWJvZHkiPjxkaXYgY2xhc3M9Im1jaGFydHciPjxjYW52YXMgaWQ9Im1jaGFydCI+PC9jYW52YXM+PC9kaXY+JzsKCiAgbWgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7bWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPicraWIoIkVudHJ5U2NvcmUiLCJHaXJpcyBLYWxpdGVzaSIpKyc8L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47bWFyZ2luLWJvdHRvbTo2cHgiPicKICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpcJ0pldEJyYWlucyBNb25vXCcsbW9ub3NwYWNlO2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X3Njb3JlKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4vMTAwPC9zcGFuPjwvc3Bhbj4nCiAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfbGFiZWwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImhlaWdodDo2cHg7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlci1yYWRpdXM6M3B4O292ZXJmbG93OmhpZGRlbjttYXJnaW4tYm90dG9tOjhweCI+PGRpdiBzdHlsZT0iaGVpZ2h0OjEwMCU7d2lkdGg6JytyLmVudHJ5X3Njb3JlKyclO2JhY2tncm91bmQ6Jytlc2NvbCsnO2JvcmRlci1yYWRpdXM6M3B4Ij48L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2Vlbjtmb250LXNpemU6MTFweCI+JwogICAgKyc8ZGl2PjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPlN1IGFua2kgZml5YXQ6IDwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6JytwdmNvbCsnO2ZvbnQtd2VpZ2h0OjYwMCI+JytyLnByaWNlX3ZzX2lkZWFsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2PjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPklkZWFsIGJvbGdlOiA8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuMik7Zm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZSI+JCcrci5pZGVhbF9lbnRyeV9sb3crJyAtICQnK3IuaWRlYWxfZW50cnlfaGlnaCsnPC9zcGFuPjwvZGl2PicKICAgICsnPC9kaXY+PC9kaXY+JzsKCiAgbWgrPSc8ZGl2IGNsYXNzPSJkYm94IiBzdHlsZT0iYmFja2dyb3VuZDonK3NzLmJnKyc7Ym9yZGVyLWNvbG9yOicrc3MuYmQrJzttYXJnaW4tYm90dG9tOjEycHgiPicKICAgICsnPGRpdiBjbGFzcz0iZGxibCIgc3R5bGU9ImNvbG9yOicrc3MudHgrJyI+JytpYigiUlIiLCJBbGltIEthcmFyaSBSL1IiKSsnPC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkdmVyZCIgc3R5bGU9ImNvbG9yOicrKGtjW3Iua2FyYXJdfHwidmFyKC0tbXV0ZWQpIikrJyI+Jysoa2xibFtyLmthcmFyXXx8ci5rYXJhcikrJzwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPlJpc2sgLyBPZHVsPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjonK3JyQysnO2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpcJ0pldEJyYWlucyBNb25vXCcsbW9ub3NwYWNlIj4xIDogJytyLnJyKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+SGVtZW4gR2lyPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbjIpO2ZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2UiPiQnK3IuZW50cnlfYWdncmVzc2l2ZSsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkdlcmkgQ2VraWxtZTwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6IzYwYTVmYTtmb250LWZhbWlseTpcJ0pldEJyYWlucyBNb25vXCcsbW9ub3NwYWNlIj4kJytyLmVudHJ5X21pZCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkJ1eXVrIER1emVsdG1lPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS15ZWxsb3cpO2ZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2UiPiQnK3IuZW50cnlfY29uc2VydmF0aXZlKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+SGVkZWY8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOiM2MGE1ZmE7Zm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZSI+JCcrci5oZWRlZisnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPlN0b3AtTG9zczwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMik7Zm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZSI+JCcrci5zdG9wKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJycmJhciI+PGRpdiBjbGFzcz0icnJmaWxsIiBzdHlsZT0id2lkdGg6JytyclArJyU7YmFja2dyb3VuZDonK3JyQysnIj48L2Rpdj48L2Rpdj48L2Rpdj4nOwoKICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPlRla25payBBbmFsaXo8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRncmlkIiBzdHlsZT0ibWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiVHJlbmQiLCJUcmVuZCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIudHJlbmQ9PT0iWXVrc2VsZW4iPyJ2YXIoLS1ncmVlbikiOnIudHJlbmQ9PT0iRHVzZW4iPyJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+JytyLnRyZW5kKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUlNJIiwiUlNJIDE0IikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5yc2k/ci5yc2k8MzA/InZhcigtLWdyZWVuKSI6ci5yc2k+NzA/InZhcigtLXJlZCkiOiJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5yc2l8fCI/IikrKHIucnNpP3IucnNpPDMwPyIgQXNpcmkgU2F0aW0iOnIucnNpPjcwPyIgQXNpcmkgQWxpbSI6IiBOb3RyIjoiIikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJTTUE1MCIsIlNNQSA1MCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuYWJvdmU1MD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkKSIpKyciPicrKHIuYWJvdmU1MD8iVXplcmluZGUiOiJBbHRpbmRhIikrKHIuc21hNTBfZGlzdCE9bnVsbD8iICgiK3Iuc21hNTBfZGlzdCsiJSkiOiIiKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlNNQTIwMCIsIlNNQSAyMDAiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmFib3ZlMjAwPyJ2YXIoLS1ncmVlbikiOiJ2YXIoLS1yZWQpIikrJyI+Jysoci5hYm92ZTIwMD8iVXplcmluZGUiOiJBbHRpbmRhIikrKHIuc21hMjAwX2Rpc3QhPW51bGw/IiAoIityLnNtYTIwMF9kaXN0KyIlKSI6IiIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiNTJXIiwiNTJIIFBvei4iKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnc1Ml9wb3NpdGlvbjw9MzA/InZhcigtLWdyZWVuKSI6ci53NTJfcG9zaXRpb24+PTg1PyJ2YXIoLS1yZWQpIjoidmFyKC0teWVsbG93KSIpKyciPicrci53NTJfcG9zaXRpb24rJyU8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiSGFjaW0iLCJIYWNpbSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuaGFjaW09PT0iWXVrc2VrIj8idmFyKC0tZ3JlZW4pIjpyLmhhY2ltPT09IkR1c3VrIj8idmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrci5oYWNpbSsnICgnK3Iudm9sX3JhdGlvKyd4KTwvZGl2PjwvZGl2PicKICAgICsnPC9kaXY+JzsKCiAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij5UZW1lbCBBbmFsaXo8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRncmlkIiBzdHlsZT0ibWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiRm9yd2FyZFBFIiwiRm9yd2FyZCBQRSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucGVfZndkP3IucGVfZndkPDI1PyJ2YXIoLS1ncmVlbikiOnIucGVfZndkPDQwPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucGVfZndkP3IucGVfZndkLnRvRml4ZWQoMSk6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlBFRyIsIlBFRyIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucGVnP3IucGVnPDE/InZhcigtLWdyZWVuKSI6ci5wZWc8Mj8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnBlZz9yLnBlZy50b0ZpeGVkKDIpOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJFUFNHcm93dGgiLCJFUFMgQsO8ecO8bWUiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmVwc19ncm93dGg/ci5lcHNfZ3Jvd3RoPj0yMD8idmFyKC0tZ3JlZW4pIjpyLmVwc19ncm93dGg+PTA/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5lcHNfZ3Jvd3RoIT1udWxsP3IuZXBzX2dyb3d0aCsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlJldkdyb3d0aCIsIkdlbGlyIELDvHnDvG1lIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5yZXZfZ3Jvd3RoP3IucmV2X2dyb3d0aD49MTU/InZhcigtLWdyZWVuKSI6ci5yZXZfZ3Jvd3RoPj0wPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucmV2X2dyb3d0aCE9bnVsbD9yLnJldl9ncm93dGgrIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJOZXRNYXJnaW4iLCJOZXQgTWFyamluIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5uZXRfbWFyZ2luP3IubmV0X21hcmdpbj49MTU/InZhcigtLWdyZWVuKSI6ci5uZXRfbWFyZ2luPj01PyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIubmV0X21hcmdpbiE9bnVsbD9yLm5ldF9tYXJnaW4rIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJST0UiLCJST0UiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnJvZT9yLnJvZT49MTU/InZhcigtLWdyZWVuKSI6ci5yb2U+PTU/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5yb2UhPW51bGw/ci5yb2UrIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPC9kaXY+JzsKCiAgdmFyIGFpVGV4dCA9IEFJX0RBVEEgJiYgQUlfREFUQVt0aWNrZXJdOwogIGlmKGFpVGV4dCl7CiAgICBtaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7bWFyZ2luLWJvdHRvbToxMnB4Ij4nOwogICAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOiM2MGE1ZmE7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+8J+kliBBSSBBbmFsaXogKENsYXVkZSBTb25uZXQpPC9kaXY+JzsKICAgIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tdGV4dCk7bGluZS1oZWlnaHQ6MS43O3doaXRlLXNwYWNlOnByZS13cmFwIj4nK2FpVGV4dCsnPC9kaXY+JzsKICAgIG1oKz0nPC9kaXY+JzsKICB9CiAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7dGV4dC1hbGlnbjpjZW50ZXIiPkJ1IGFyYWMgeWF0aXJpbSB0YXZzaXllc2kgZGVnaWxkaXI8L2Rpdj48L2Rpdj4nOwoKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibW9kYWwiKS5pbm5lckhUTUw9bWg7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm92ZXJsYXkiKS5jbGFzc0xpc3QuYWRkKCJvcGVuIik7CiAgc2V0VGltZW91dChmdW5jdGlvbigpewogICAgdmFyIGN0eD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWNoYXJ0Iik7CiAgICBpZihjdHgmJnIuY2hhcnRfY2xvc2VzKXsKICAgICAgbUNoYXJ0PW5ldyBDaGFydChjdHgse3R5cGU6ImxpbmUiLGRhdGE6e2xhYmVsczpyLmNoYXJ0X2RhdGVzLGRhdGFzZXRzOlsKICAgICAgICB7bGFiZWw6IkZpeWF0IixkYXRhOnIuY2hhcnRfY2xvc2VzLGJvcmRlckNvbG9yOnNzLmFjLGJvcmRlcldpZHRoOjIsZmlsbDp0cnVlLGJhY2tncm91bmRDb2xvcjpzcy5hYysiMjAiLHBvaW50UmFkaXVzOjAsdGVuc2lvbjowLjN9LAogICAgICAgIHIuc21hNTA/e2xhYmVsOiJTTUE1MCIsZGF0YTpBcnJheShyLmNoYXJ0X2Nsb3Nlcy5sZW5ndGgpLmZpbGwoci5zbWE1MCksYm9yZGVyQ29sb3I6IiNmNTllMGIiLGJvcmRlcldpZHRoOjEuNSxib3JkZXJEYXNoOls1LDVdLHBvaW50UmFkaXVzOjAsZmlsbDpmYWxzZX06bnVsbCwKICAgICAgICByLnNtYTIwMD97bGFiZWw6IlNNQTIwMCIsZGF0YTpBcnJheShyLmNoYXJ0X2Nsb3Nlcy5sZW5ndGgpLmZpbGwoci5zbWEyMDApLGJvcmRlckNvbG9yOiIjOGI1Y2Y2Iixib3JkZXJXaWR0aDoxLjUsYm9yZGVyRGFzaDpbNSw1XSxwb2ludFJhZGl1czowLGZpbGw6ZmFsc2V9Om51bGwKICAgICAgXS5maWx0ZXIoQm9vbGVhbil9LG9wdGlvbnM6e3Jlc3BvbnNpdmU6dHJ1ZSxtYWludGFpbkFzcGVjdFJhdGlvOmZhbHNlLAogICAgICAgIHBsdWdpbnM6e2xlZ2VuZDp7bGFiZWxzOntjb2xvcjoiIzZiNzI4MCIsZm9udDp7c2l6ZToxMH19fX0sCiAgICAgICAgc2NhbGVzOnt4OntkaXNwbGF5OnRydWUsdGlja3M6e2NvbG9yOiIjMzc0MTUxIixtYXhUaWNrc0xpbWl0OjUsZm9udDp7c2l6ZTo5fX0sZ3JpZDp7Y29sb3I6InJnYmEoMjU1LDI1NSwyNTUsLjA0KSJ9fSwKICAgICAgICAgIHk6e2Rpc3BsYXk6dHJ1ZSx0aWNrczp7Y29sb3I6IiMzNzQxNTEiLGZvbnQ6e3NpemU6OX19LGdyaWQ6e2NvbG9yOiJyZ2JhKDI1NSwyNTUsMjU1LC4wNCkifX19fX0pOwogICAgfQogIH0sMTAwKTsKfQoKCi8vIOKUgOKUgCBHw5xOTMOcSyBSVVTEsE4g4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSACnZhciBSVVRJTl9JVEVNUyA9IHsKICBzYWJhaDogewogICAgbGFiZWw6ICLwn4yFIFNhYmFoIOKAlCBQaXlhc2EgQcOnxLFsbWFkYW4gw5ZuY2UiLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJzMSIsIHRleHQ6IkRhc2hib2FyZCfEsSBhw6cg4oCUIE0ga3JpdGVyaSB5ZcWfaWwgbWk/IChTJlA1MDAgKyBOQVNEQVEgU01BMjAwIMO8c3TDvG5kZSkifSwKICAgICAge2lkOiJzMiIsIHRleHQ6IkVhcm5pbmdzIHNla21lc2luaSBrb250cm9sIGV0IOKAlCBidWfDvG4vYnUgaGFmdGEgcmFwb3IgdmFyIG3EsT8ifSwKICAgICAge2lkOiJzMyIsIHRleHQ6IlZJWCAyNSBhbHTEsW5kYSBtxLE/IChZw7xrc2Vrc2UgeWVuaSBwb3ppc3lvbiBhw6dtYSkifSwKICAgICAge2lkOiJzNCIsIHRleHQ6IsOWbmNla2kgZ8O8bmRlbiBiZWtsZXllbiBhbGFybSBtYWlsaSB2YXIgbcSxPyJ9CiAgICBdCiAgfSwKICBvZ2xlbjogewogICAgbGFiZWw6ICLwn5OKIMOWxJ9sZWRlbiBTb25yYSDigJQgUGl5YXNhIEHDp8Sxa2tlbiIsCiAgICBpdGVtczogWwogICAgICB7aWQ6Im8xIiwgdGV4dDoiUG9ydGbDtnnDvG0gc2VrbWVzaW5kZSBoaXNzZWxlcmltZSBiYWsg4oCUIGJla2xlbm1lZGlrIGTDvMWfw7zFnyB2YXIgbcSxPyJ9LAogICAgICB7aWQ6Im8yIiwgdGV4dDoiU3RvcCBzZXZpeWVzaW5lIHlha2xhxZ9hbiBoaXNzZSB2YXIgbcSxPyAoS8Sxcm3EsXrEsSBpxZ9hcmV0KSJ9LAogICAgICB7aWQ6Im8zIiwgdGV4dDoiQWwgc2lueWFsaSBzZWttZXNpbmRlIHllbmkgZsSxcnNhdCDDp8Sxa23EscWfIG3EsT8ifSwKICAgICAge2lkOiJvNCIsIHRleHQ6IldhdGNobGlzdCd0ZWtpIGhpc3NlbGVyZGUgZ2lyacWfIGthbGl0ZXNpIDYwKyBvbGFuIHZhciBtxLE/In0sCiAgICAgIHtpZDoibzUiLCB0ZXh0OiJIYWJlcmxlcmRlIHBvcnRmw7Z5w7xtw7wgZXRraWxleWVuIMO2bmVtbGkgZ2VsacWfbWUgdmFyIG3EsT8ifQogICAgXQogIH0sCiAgYWtzYW06IHsKICAgIGxhYmVsOiAi8J+MmSBBa8WfYW0g4oCUIFBpeWFzYSBLYXBhbmTEsWt0YW4gU29ucmEiLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJhMSIsIHRleHQ6IjFIIHNpbnlhbGxlcmluaSBrb250cm9sIGV0IOKAlCBoYWZ0YWzEsWsgdHJlbmQgZGXEn2nFn21pxZ8gbWk/In0sCiAgICAgIHtpZDoiYTIiLCB0ZXh0OiJZYXLEsW4gacOnaW4gcG90YW5zaXllbCBnaXJpxZ8gbm9rdGFsYXLEsW7EsSBub3QgYWwifSwKICAgICAge2lkOiJhMyIsIHRleHQ6IlBvcnRmw7Z5ZGVraSBoZXIgaGlzc2VuaW4gc3RvcCBzZXZpeWVzaW5pIGfDtnpkZW4gZ2XDp2lyIn0sCiAgICAgIHtpZDoiYTQiLCB0ZXh0OiJZYXLEsW4gcmFwb3IgYcOnxLFrbGF5YWNhayBoaXNzZSB2YXIgbcSxPyAoRWFybmluZ3Mgc2VrbWVzaSkifQogICAgXQogIH0sCiAgaGFmdGFsaWs6IHsKICAgIGxhYmVsOiAi8J+ThSBIYWZ0YWzEsWsg4oCUIFBhemFyIEFrxZ9hbcSxIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoiaDEiLCB0ZXh0OiJTdG9jayBSb3ZlcidkYSBDQU5TTElNIHNjcmVlbmVyJ8SxIMOnYWzEscWfdMSxciJ9LAogICAgICB7aWQ6ImgyIiwgdGV4dDoiVkNQIE1pbmVydmluaSBzY3JlZW5lcifEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoMyIsIHRleHQ6IlF1bGxhbWFnZ2llIEJyZWFrb3V0IHNjcmVlbmVyJ8SxIMOnYWzEscWfdMSxciJ9LAogICAgICB7aWQ6Img0IiwgdGV4dDoiRmludml6J2RlIEluc3RpdHV0aW9uYWwgQnV5aW5nIHNjcmVlbmVyJ8SxIMOnYWzEscWfdMSxciJ9LAogICAgICB7aWQ6Img1IiwgdGV4dDoiw4dha8SxxZ9hbiBoaXNzZWxlcmkgYnVsIOKAlCBlbiBnw7zDp2zDvCBhZGF5bGFyIn0sCiAgICAgIHtpZDoiaDYiLCB0ZXh0OiJHaXRIdWIgQWN0aW9ucydkYW4gUnVuIFdvcmtmbG93IGJhcyDigJQgc2l0ZSBnw7xuY2VsbGVuaXIifSwKICAgICAge2lkOiJoNyIsIHRleHQ6IkdlbGVjZWsgaGFmdGFuxLFuIGVhcm5pbmdzIHRha3ZpbWluaSBrb250cm9sIGV0In0sCiAgICAgIHtpZDoiaDgiLCB0ZXh0OiJQb3J0ZsO2eSBnZW5lbCBkZcSfZXJsZW5kaXJtZXNpIOKAlCBoZWRlZmxlciBoYWxhIGdlw6dlcmxpIG1pPyJ9CiAgICBdCiAgfQp9OwoKZnVuY3Rpb24gZ2V0VG9kYXlLZXkoKXsKICByZXR1cm4gbmV3IERhdGUoKS50b0RhdGVTdHJpbmcoKTsKfQoKZnVuY3Rpb24gbG9hZENoZWNrZWQoKXsKICB0cnl7CiAgICB2YXIgZGF0YSA9IGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdydXRpbl9jaGVja2VkJyk7CiAgICBpZighZGF0YSkgcmV0dXJuIHt9OwogICAgdmFyIHBhcnNlZCA9IEpTT04ucGFyc2UoZGF0YSk7CiAgICAvLyBTYWRlY2UgYnVnw7xuw7xuIHZlcmlsZXJpbmkga3VsbGFuCiAgICBpZihwYXJzZWQuZGF0ZSAhPT0gZ2V0VG9kYXlLZXkoKSkgcmV0dXJuIHt9OwogICAgcmV0dXJuIHBhcnNlZC5pdGVtcyB8fCB7fTsKICB9Y2F0Y2goZSl7cmV0dXJuIHt9O30KfQoKZnVuY3Rpb24gc2F2ZUNoZWNrZWQoY2hlY2tlZCl7CiAgbG9jYWxTdG9yYWdlLnNldEl0ZW0oJ3J1dGluX2NoZWNrZWQnLCBKU09OLnN0cmluZ2lmeSh7CiAgICBkYXRlOiBnZXRUb2RheUtleSgpLAogICAgaXRlbXM6IGNoZWNrZWQKICB9KSk7Cn0KCmZ1bmN0aW9uIHRvZ2dsZUNoZWNrKGlkKXsKICB2YXIgY2hlY2tlZCA9IGxvYWRDaGVja2VkKCk7CiAgaWYoY2hlY2tlZFtpZF0pIGRlbGV0ZSBjaGVja2VkW2lkXTsKICBlbHNlIGNoZWNrZWRbaWRdID0gdHJ1ZTsKICBzYXZlQ2hlY2tlZChjaGVja2VkKTsKICByZW5kZXJSdXRpbigpOwp9CgpmdW5jdGlvbiByZXNldFJ1dGluKCl7CiAgbG9jYWxTdG9yYWdlLnJlbW92ZUl0ZW0oJ3J1dGluX2NoZWNrZWQnKTsKICByZW5kZXJSdXRpbigpOwp9CgoKZnVuY3Rpb24gcmVuZGVySGFmdGFsaWsoKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgdmFyIHdkID0gV0VFS0xZX0RBVEEgfHwge307CiAgdmFyIHBvcnQgPSB3ZC5wb3J0Zm9saW8gfHwgW107CiAgdmFyIHdhdGNoID0gd2Qud2F0Y2hsaXN0IHx8IFtdOwogIHZhciBiZXN0ID0gd2QuYmVzdDsKICB2YXIgd29yc3QgPSB3ZC53b3JzdDsKICB2YXIgbWQgPSBNQVJLRVRfREFUQSB8fCB7fTsKICB2YXIgc3AgPSBtZC5TUDUwMCB8fCB7fTsKICB2YXIgbmFzID0gbWQuTkFTREFRIHx8IHt9OwoKICBmdW5jdGlvbiBjaGdDb2xvcih2KXsgcmV0dXJuIHYgPj0gMCA/ICd2YXIoLS1ncmVlbiknIDogJ3ZhcigtLXJlZDIpJzsgfQogIGZ1bmN0aW9uIGNoZ1N0cih2KXsgcmV0dXJuICh2ID49IDAgPyAnKycgOiAnJykgKyB2ICsgJyUnOyB9CgogIGZ1bmN0aW9uIHBlcmZDYXJkKGl0ZW0pewogICAgdmFyIGNjID0gY2hnQ29sb3IoaXRlbS53ZWVrX2NoZyk7CiAgICB2YXIgcGIgPSBpdGVtLnBvcnRmb2xpbyA/ICc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEyKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjI1KTtwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo2MDA7bWFyZ2luLWxlZnQ6NHB4Ij5QPC9zcGFuPicgOiAnJzsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTJweDtkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206NnB4Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjZweCI+PHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToxNnB4O2xldHRlci1zcGFjaW5nOjJweCI+JyArIGl0ZW0udGlja2VyICsgJzwvc3Bhbj4nICsgcGIgKyAnPC9kaXY+JwogICAgICArICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OidKZXRCcmFpbnMgTW9ubycsbW9ub3NwYWNlO2ZvbnQtc2l6ZToxNHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgY2MgKyAnIj4nICsgY2hnU3RyKGl0ZW0ud2Vla19jaGcpICsgJzwvZGl2PicKICAgICAgKyAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPsOWbmNla2k6ICcgKyBjaGdTdHIoaXRlbS5wcmV2X3dlZWtfY2hnKSArICc8L2Rpdj4nCiAgICAgICsgJzwvZGl2PjwvZGl2Pic7CiAgfQoKICB2YXIgaCA9ICc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwoKICAvLyBIZWFkZXIKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4Ij7wn5OIIEhhZnRhbMSxayBQZXJmb3JtYW5zIMOWemV0aTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nICsgKHdkLmdlbmVyYXRlZCB8fCAnJykgKyAnPC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBQaXlhc2EgdnMgUG9ydGbDtnkKICB2YXIgc3BDaGcgPSBzcC5jaGFuZ2UgfHwgMDsKICB2YXIgbmFzQ2hnID0gbmFzLmNoYW5nZSB8fCAwOwogIHZhciBwb3J0QXZnID0gcG9ydC5sZW5ndGggPyBNYXRoLnJvdW5kKHBvcnQucmVkdWNlKGZ1bmN0aW9uKGEsYil7cmV0dXJuIGErYi53ZWVrX2NoZzt9LDApL3BvcnQubGVuZ3RoKjEwMCkvMTAwIDogMDsKICB2YXIgYWxwaGEgPSBNYXRoLnJvdW5kKChwb3J0QXZnIC0gc3BDaGcpKjEwMCkvMTAwOwogIHZhciBhbHBoYUNvbCA9IGFscGhhID49IDAgPyAndmFyKC0tZ3JlZW4pJyA6ICd2YXIoLS1yZWQyKSc7CgogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMTQwcHgsMWZyKSk7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPlBvcnRmw7Z5IE9ydC48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTonSmV0QnJhaW5zIE1vbm8nLG1vbm9zcGFjZTtjb2xvcjonICsgY2hnQ29sb3IocG9ydEF2ZykgKyAnIj4nICsgY2hnU3RyKHBvcnRBdmcpICsgJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+UyZQIDUwMDwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OidKZXRCcmFpbnMgTW9ubycsbW9ub3NwYWNlO2NvbG9yOicgKyBjaGdDb2xvcihzcENoZykgKyAnIj4nICsgY2hnU3RyKHNwQ2hnKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPk5BU0RBUTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OidKZXRCcmFpbnMgTW9ubycsbW9ub3NwYWNlO2NvbG9yOicgKyBjaGdDb2xvcihuYXNDaGcpICsgJyI+JyArIGNoZ1N0cihuYXNDaGcpICsgJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonICsgKGFscGhhPj0wPydyZ2JhKDE2LDE4NSwxMjksLjA4KSc6J3JnYmEoMjM5LDY4LDY4LC4wOCknKSArICc7Ym9yZGVyOjFweCBzb2xpZCAnICsgKGFscGhhPj0wPydyZ2JhKDE2LDE4NSwxMjksLjI1KSc6J3JnYmEoMjM5LDY4LDY4LC4yNSknKSArICc7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPkFscGhhICh2cyBTJlApPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6J0pldEJyYWlucyBNb25vJyxtb25vc3BhY2U7Y29sb3I6JyArIGFscGhhQ29sICsgJyI+JyArIChhbHBoYT49MD8nKyc6JycpICsgYWxwaGEgKyAnJTwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gRW4gaXlpIC8gZW4ga8O2dMO8CiAgaWYoYmVzdCB8fCB3b3JzdCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogICAgaWYoYmVzdCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLWdyZWVuKTttYXJnaW4tYm90dG9tOjZweCI+8J+PhiBCdSBIYWZ0YW7EsW4gRW4gxLB5aXNpPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6J0JlYmFzIE5ldWUnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjI0cHg7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgYmVzdC50aWNrZXIgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6J0pldEJyYWlucyBNb25vJyxtb25vc3BhY2U7Zm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+KycgKyBiZXN0LndlZWtfY2hnICsgJyU8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaWYod29yc3QpewogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tcmVkMik7bWFyZ2luLWJvdHRvbTo2cHgiPvCfk4kgQnUgSGFmdGFuxLFuIEVuIEvDtnTDvHPDvDwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyNHB4O2xldHRlci1zcGFjaW5nOjJweCI+JyArIHdvcnN0LnRpY2tlciArICc8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTonSmV0QnJhaW5zIE1vbm8nLG1vbm9zcGFjZTtmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicgKyB3b3JzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBQb3J0ZsO2eSBkZXRheQogIGlmKHBvcnQubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkrwgUG9ydGbDtnk8L2Rpdj4nOwogICAgcG9ydC5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0peyBoICs9IHBlcmZDYXJkKGl0ZW0pOyB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBTaW55YWxsZXIgb3pldGkKICB2YXIgYnV5Q291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nR1VDTFUgQUwnfHxyLnNpbnlhbD09PSdBTCc7fSkubGVuZ3RoOwogIHZhciBzZWxsQ291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nU0FUJzt9KS5sZW5ndGg7CiAgdmFyIHdhdGNoQ291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nRElLS0FUJzt9KS5sZW5ndGg7CgogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5OKIEJ1IEhhZnRha2kgU2lueWFsbGVyPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXAiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicgKyBidXlDb3VudCArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkFsIFNpbnlhbGk8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0teWVsbG93KSI+JyArIHdhdGNoQ291bnQgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5EaWtrYXQ8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nICsgc2VsbENvdW50ICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+U2F0IFNpbnlhbGk8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzwvZGl2PjwvZGl2Pic7CgogIC8vIFdhdGNobGlzdCBwZXJmb3JtYW5zCiAgaWYod2F0Y2gubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkYEgV2F0Y2hsaXN0PC9kaXY+JzsKICAgIHdhdGNoLmZvckVhY2goZnVuY3Rpb24oaXRlbSl7IGggKz0gcGVyZkNhcmQoaXRlbSk7IH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIGggKz0gJzwvZGl2Pic7CiAgZ3JpZC5pbm5lckhUTUwgPSBoOwp9CgoKZnVuY3Rpb24gcmVuZGVyUnV0aW4oKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgdmFyIGNoZWNrZWQgPSBsb2FkQ2hlY2tlZCgpOwogIHZhciB0b2RheSA9IG5ldyBEYXRlKCk7CiAgdmFyIGlzV2Vla2VuZCA9IHRvZGF5LmdldERheSgpID09PSAwIHx8IHRvZGF5LmdldERheSgpID09PSA2OwogIHZhciBkYXlOYW1lID0gWydQYXphcicsJ1BhemFydGVzaScsJ1NhbMSxJywnw4dhcsWfYW1iYScsJ1BlcsWfZW1iZScsJ0N1bWEnLCdDdW1hcnRlc2knXVt0b2RheS5nZXREYXkoKV07CiAgdmFyIGRhdGVTdHIgPSB0b2RheS50b0xvY2FsZURhdGVTdHJpbmcoJ3RyLVRSJywge2RheTonbnVtZXJpYycsbW9udGg6J2xvbmcnLHllYXI6J251bWVyaWMnfSk7CgogIC8vIFByb2dyZXNzIGhlc2FwbGEKICB2YXIgdG90YWxJdGVtcyA9IDA7CiAgdmFyIGRvbmVJdGVtcyA9IDA7CiAgdmFyIHNlY3Rpb25zID0gaXNXZWVrZW5kID8gWydoYWZ0YWxpayddIDogWydzYWJhaCcsJ29nbGVuJywnYWtzYW0nXTsKICBzZWN0aW9ucy5mb3JFYWNoKGZ1bmN0aW9uKGspewogICAgUlVUSU5fSVRFTVNba10uaXRlbXMuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsKICAgICAgdG90YWxJdGVtcysrOwogICAgICBpZihjaGVja2VkW2l0ZW0uaWRdKSBkb25lSXRlbXMrKzsKICAgIH0pOwogIH0pOwogIHZhciBwY3QgPSB0b3RhbEl0ZW1zID4gMCA/IE1hdGgucm91bmQoZG9uZUl0ZW1zL3RvdGFsSXRlbXMqMTAwKSA6IDA7CiAgdmFyIHBjdENvbCA9IHBjdD09PTEwMD8ndmFyKC0tZ3JlZW4pJzpwY3Q+PTUwPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tbXV0ZWQpJzsKCiAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgLy8gSGVhZGVyCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7ZmxleC13cmFwOndyYXA7Z2FwOjEwcHgiPic7CiAgaCArPSAnPGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrZGF5TmFtZSsnIFJ1dGluaTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK2RhdGVTdHIrJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjhweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JytwY3RDb2wrJyI+JytwY3QrJyU8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+Jytkb25lSXRlbXMrJy8nK3RvdGFsSXRlbXMrJyB0YW1hbWxhbmTEsTwvZGl2PjwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iaGVpZ2h0OjZweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czozcHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi10b3A6MTJweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJoZWlnaHQ6MTAwJTt3aWR0aDonK3BjdCsnJTtiYWNrZ3JvdW5kOicrcGN0Q29sKyc7Ym9yZGVyLXJhZGl1czozcHg7dHJhbnNpdGlvbjp3aWR0aCAuNXMgZWFzZSI+PC9kaXY+PC9kaXY+JzsKICBpZihwY3Q9PT0xMDApIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyO21hcmdpbi10b3A6MTBweDtmb250LXNpemU6MTRweDtjb2xvcjp2YXIoLS1ncmVlbikiPvCfjokgVMO8bSBtYWRkZWxlciB0YW1hbWxhbmTEsSE8L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIFNlY3Rpb25zCiAgc2VjdGlvbnMuZm9yRWFjaChmdW5jdGlvbihrKXsKICAgIHZhciBzZWMgPSBSVVRJTl9JVEVNU1trXTsKICAgIHZhciBzZWNEb25lID0gc2VjLml0ZW1zLmZpbHRlcihmdW5jdGlvbihpKXtyZXR1cm4gY2hlY2tlZFtpLmlkXTt9KS5sZW5ndGg7CiAgICB2YXIgc2VjVG90YWwgPSBzZWMuaXRlbXMubGVuZ3RoOwogICAgdmFyIHNlY1BjdCA9IE1hdGgucm91bmQoc2VjRG9uZS9zZWNUb3RhbCoxMDApOwogICAgdmFyIHNlY0NvbCA9IHNlY1BjdD09PTEwMD8ndmFyKC0tZ3JlZW4pJzpzZWNQY3Q+MD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLW11dGVkKSc7CgogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjEycHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrc2VjLmxhYmVsKyc8L2Rpdj4nOwogICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOicrc2VjQ29sKyc7Zm9udC13ZWlnaHQ6NjAwIj4nK3NlY0RvbmUrJy8nK3NlY1RvdGFsKyc8L3NwYW4+PC9kaXY+JzsKCiAgICBzZWMuaXRlbXMuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsKICAgICAgdmFyIGRvbmUgPSAhIWNoZWNrZWRbaXRlbS5pZF07CiAgICAgIHZhciBiZ0NvbG9yID0gZG9uZSA/ICdyZ2JhKDE2LDE4NSwxMjksLjA2KScgOiAncmdiYSgyNTUsMjU1LDI1NSwuMDIpJzsKICAgICAgdmFyIGJvcmRlckNvbG9yID0gZG9uZSA/ICdyZ2JhKDE2LDE4NSwxMjksLjIpJyA6ICdyZ2JhKDI1NSwyNTUsMjU1LC4wNSknOwogICAgICB2YXIgY2hlY2tCb3JkZXIgPSBkb25lID8gJ3ZhcigtLWdyZWVuKScgOiAndmFyKC0tbXV0ZWQpJzsKICAgICAgdmFyIGNoZWNrQmcgPSBkb25lID8gJ3ZhcigtLWdyZWVuKScgOiAndHJhbnNwYXJlbnQnOwogICAgICB2YXIgdGV4dENvbG9yID0gZG9uZSA/ICd2YXIoLS1tdXRlZCknIDogJ3ZhcigtLXRleHQpJzsKICAgICAgdmFyIHRleHREZWNvID0gZG9uZSA/ICdsaW5lLXRocm91Z2gnIDogJ25vbmUnOwogICAgICB2YXIgY2hlY2ttYXJrID0gZG9uZSA/ICc8c3ZnIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cG9seWxpbmUgcG9pbnRzPSIyLDYgNSw5IDEwLDMiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+PC9zdmc+JyA6ICcnOwogICAgICBoICs9ICc8ZGl2IG9uY2xpY2s9InRvZ2dsZUNoZWNrKFwnJyArIGl0ZW0uaWQgKyAnXCcpIiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmZsZXgtc3RhcnQ7Z2FwOjEycHg7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6OHB4O2N1cnNvcjpwb2ludGVyO21hcmdpbi1ib3R0b206NnB4O2JhY2tncm91bmQ6JyArIGJnQ29sb3IgKyAnO2JvcmRlcjoxcHggc29saWQgJyArIGJvcmRlckNvbG9yICsgJyI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZmxleC1zaHJpbms6MDt3aWR0aDoyMHB4O2hlaWdodDoyMHB4O2JvcmRlci1yYWRpdXM6NXB4O2JvcmRlcjoycHggc29saWQgJyArIGNoZWNrQm9yZGVyICsgJztiYWNrZ3JvdW5kOicgKyBjaGVja0JnICsgJztkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7bWFyZ2luLXRvcDoxcHgiPicgKyBjaGVja21hcmsgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2NvbG9yOicgKyB0ZXh0Q29sb3IgKyAnO2xpbmUtaGVpZ2h0OjEuNTt0ZXh0LWRlY29yYXRpb246JyArIHRleHREZWNvICsgJyI+JyArIGl0ZW0udGV4dCArICc8L3NwYW4+JzsKICAgICAgaCArPSAnPC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9KTsKCiAgLy8gSGFmdGEgacOnaSBvbGR1xJ91bmRhIGhhZnRhbMSxayBiw7Zsw7xtw7wgZGUgZ8O2c3RlciAoa2F0bGFuYWJpbGlyKQogIGlmKCFpc1dlZWtlbmQpewogICAgdmFyIGhTZWMgPSBSVVRJTl9JVEVNU1snaGFmdGFsaWsnXTsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wNCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjE1KTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOiM2MGE1ZmE7bWFyZ2luLWJvdHRvbTo0cHgiPicraFNlYy5sYWJlbCsnPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+UGF6YXIgYWvFn2FtxLEgeWFwxLFsYWNha2xhciDigJQgxZ91IGFuIGfDtnN0ZXJpbSBtb2R1bmRhPC9kaXY+PC9kaXY+JzsKICB9CgogIC8vIFJlc2V0IGJ1dG9udQogIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyO21hcmdpbi10b3A6NnB4Ij4nOwogIGggKz0gJzxidXR0b24gb25jbGljaz0icmVzZXRSdXRpbigpIiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS1tdXRlZCk7cGFkZGluZzo4cHggMTZweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTJweDtjdXJzb3I6cG9pbnRlciI+8J+UhCBMaXN0ZXlpIFPEsWbEsXJsYTwvYnV0dG9uPic7CiAgaCArPSAnPC9kaXY+JzsKCiAgaCArPSAnPC9kaXY+JzsKICBncmlkLmlubmVySFRNTCA9IGg7Cn0KCgpmdW5jdGlvbiBjbG9zZU0oZSl7CiAgaWYoIWV8fGUudGFyZ2V0PT09ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm92ZXJsYXkiKSl7CiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgib3ZlcmxheSIpLmNsYXNzTGlzdC5yZW1vdmUoIm9wZW4iKTsKICAgIGlmKG1DaGFydCl7bUNoYXJ0LmRlc3Ryb3koKTttQ2hhcnQ9bnVsbDt9CiAgfQp9CgpyZW5kZXJTdGF0cygpOwpyZW5kZXJEYXNoYm9hcmQoKTsKCgoKLy8g4pSA4pSAIEzEsFNURSBEw5xaRU5MRU1FIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgAp2YXIgZWRpdFdhdGNobGlzdCA9IFtdOwp2YXIgZWRpdFBvcnRmb2xpbyA9IFtdOwoKZnVuY3Rpb24gb3BlbkVkaXRMaXN0KCl7CiAgZWRpdFdhdGNobGlzdCA9IFRGX0RBVEFbJzFkJ10uZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pLm1hcChmdW5jdGlvbihyKXtyZXR1cm4gci50aWNrZXI7fSk7CiAgZWRpdFBvcnRmb2xpbyA9IFBPUlQuc2xpY2UoKTsKICByZW5kZXJFZGl0TGlzdHMoKTsKICAvLyBMb2FkIHNhdmVkIHRva2VuIGZyb20gbG9jYWxTdG9yYWdlCiAgdmFyIHNhdmVkID0gbG9jYWxTdG9yYWdlLmdldEl0ZW0oJ2doX3Rva2VuJyk7CiAgaWYoc2F2ZWQpIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZSA9IHNhdmVkOwogIHZhciB0cz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidG9rZW5TZWN0aW9uIik7IGlmKHRzKSB0cy5zdHlsZS5kaXNwbGF5PSJub25lIjsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFBvcHVwIikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwp9CgoKZnVuY3Rpb24gdG9nZ2xlVG9rZW5TZWN0aW9uKCl7CiAgdmFyIHM9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInRva2VuU2VjdGlvbiIpOwogIGlmKHMpIHMuc3R5bGUuZGlzcGxheT1zLnN0eWxlLmRpc3BsYXk9PT0ibm9uZSI/ImJsb2NrIjoibm9uZSI7Cn0KCmZ1bmN0aW9uIHNhdmVUb2tlbigpewogIHZhciB0PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZS50cmltKCk7CiAgaWYoIXQpe2FsZXJ0KCJUb2tlbiBib3MhIik7cmV0dXJuO30KICBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgiZ2hfdG9rZW4iLHQpOwogIHZhciB0cz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidG9rZW5TZWN0aW9uIik7IGlmKHRzKSB0cy5zdHlsZS5kaXNwbGF5PSJub25lIjsKICBzZXRFZGl0U3RhdHVzKCLinIUgVG9rZW4ga2F5ZGVkaWxkaSIsImdyZWVuIik7Cn0KCmZ1bmN0aW9uIGNsb3NlRWRpdFBvcHVwKGUpewogIGlmKCFlfHxlLnRhcmdldD09PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0UG9wdXAiKSl7CiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFBvcHVwIikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpOwogIH0KfQoKZnVuY3Rpb24gcmVuZGVyRWRpdExpc3RzKCl7CiAgdmFyIHdlID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIndhdGNobGlzdEVkaXRvciIpOwogIHZhciBwZSA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJwb3J0Zm9saW9FZGl0b3IiKTsKICBpZighd2V8fCFwZSkgcmV0dXJuOwoKICB3ZS5pbm5lckhUTUwgPSBlZGl0V2F0Y2hsaXN0Lm1hcChmdW5jdGlvbih0LGkpewogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO3BhZGRpbmc6NXB4IDhweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6NXB4O21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwIj4nK3QrJzwvc3Bhbj4nCiAgICAgICsnPGJ1dHRvbiBvbmNsaWNrPSJyZW1vdmVUaWNrZXIoXCd3YXRjaFwnLCcraSsnKSIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtib3JkZXI6bm9uZTtjb2xvcjp2YXIoLS1yZWQyKTt3aWR0aDoyMHB4O2hlaWdodDoyMHB4O2JvcmRlci1yYWRpdXM6NHB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxMnB4Ij7inJU8L2J1dHRvbj4nCiAgICAgICsnPC9kaXY+JzsKICB9KS5qb2luKCcnKTsKCiAgcGUuaW5uZXJIVE1MID0gZWRpdFBvcnRmb2xpby5tYXAoZnVuY3Rpb24odCxpKXsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtwYWRkaW5nOjVweCA4cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjVweDttYXJnaW4tYm90dG9tOjRweCI+JwogICAgICArJzxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpcJ0pldEJyYWlucyBNb25vXCcsbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicrdCsnPC9zcGFuPicKICAgICAgKyc8YnV0dG9uIG9uY2xpY2s9InJlbW92ZVRpY2tlcihcJ3BvcnRcJywnK2krJykiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Ym9yZGVyOm5vbmU7Y29sb3I6dmFyKC0tcmVkMik7d2lkdGg6MjBweDtoZWlnaHQ6MjBweDtib3JkZXItcmFkaXVzOjRweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTJweCI+4pyVPC9idXR0b24+JwogICAgICArJzwvZGl2Pic7CiAgfSkuam9pbignJyk7Cn0KCmZ1bmN0aW9uIGFkZFRpY2tlcihsaXN0KXsKICB2YXIgaW5wdXRJZCA9IGxpc3Q9PT0nd2F0Y2gnPyJuZXdXYXRjaFRpY2tlciI6Im5ld1BvcnRUaWNrZXIiOwogIHZhciB2YWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZChpbnB1dElkKS52YWx1ZS50cmltKCkudG9VcHBlckNhc2UoKTsKICBpZighdmFsKSByZXR1cm47CiAgaWYobGlzdD09PSd3YXRjaCcgJiYgIWVkaXRXYXRjaGxpc3QuaW5jbHVkZXModmFsKSkgZWRpdFdhdGNobGlzdC5wdXNoKHZhbCk7CiAgaWYobGlzdD09PSdwb3J0JyAgJiYgIWVkaXRQb3J0Zm9saW8uaW5jbHVkZXModmFsKSkgZWRpdFBvcnRmb2xpby5wdXNoKHZhbCk7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoaW5wdXRJZCkudmFsdWUgPSAiIjsKICByZW5kZXJFZGl0TGlzdHMoKTsKfQoKZnVuY3Rpb24gcmVtb3ZlVGlja2VyKGxpc3QsIGlkeCl7CiAgaWYobGlzdD09PSd3YXRjaCcpIGVkaXRXYXRjaGxpc3Quc3BsaWNlKGlkeCwxKTsKICBlbHNlIGVkaXRQb3J0Zm9saW8uc3BsaWNlKGlkeCwxKTsKICByZW5kZXJFZGl0TGlzdHMoKTsKfQoKZnVuY3Rpb24gc2F2ZUxpc3RUb0dpdGh1YigpewogIHZhciB0b2tlbiA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZS50cmltKCk7CiAgaWYoIXRva2VuKXsgc2V0RWRpdFN0YXR1cygi4p2MIFRva2VuIGdlcmVrbGkg4oCUIGt1dHV5YSBnaXIiLCJyZWQiKTsgcmV0dXJuOyB9CiAgbG9jYWxTdG9yYWdlLnNldEl0ZW0oJ2doX3Rva2VuJywgdG9rZW4pOwoKICB2YXIgY29uZmlnID0geyB3YXRjaGxpc3Q6IGVkaXRXYXRjaGxpc3QsIHBvcnRmb2xpbzogZWRpdFBvcnRmb2xpbyB9OwogIHZhciBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoY29uZmlnLCBudWxsLCAyKTsKICB2YXIgYjY0ID0gYnRvYSh1bmVzY2FwZShlbmNvZGVVUklDb21wb25lbnQoY29udGVudCkpKTsKCiAgc2V0RWRpdFN0YXR1cygi8J+SviBLYXlkZWRpbGl5b3IuLi4iLCJ5ZWxsb3ciKTsKCiAgdmFyIGFwaVVybCA9ICJodHRwczovL2FwaS5naXRodWIuY29tL3JlcG9zL2dodXJ6enovY2Fuc2xpbS9jb250ZW50cy9jb25maWcuanNvbiI7CiAgdmFyIGhlYWRlcnMgPSB7IkF1dGhvcml6YXRpb24iOiJ0b2tlbiAiK3Rva2VuLCJDb250ZW50LVR5cGUiOiJhcHBsaWNhdGlvbi9qc29uIn07CgogIC8vIEZpcnN0IGdldCBjdXJyZW50IFNIQSBpZiBleGlzdHMKICBmZXRjaChhcGlVcmwsIHtoZWFkZXJzOmhlYWRlcnN9KQogICAgLnRoZW4oZnVuY3Rpb24ocil7IHJldHVybiByLm9rID8gci5qc29uKCkgOiBudWxsOyB9KQogICAgLnRoZW4oZnVuY3Rpb24oZXhpc3RpbmcpewogICAgICB2YXIgcGF5bG9hZCA9IHsKICAgICAgICBtZXNzYWdlOiAiTGlzdGUgZ3VuY2VsbGVuZGkgIiArIG5ldyBEYXRlKCkudG9Mb2NhbGVEYXRlU3RyaW5nKCJ0ci1UUiIpLAogICAgICAgIGNvbnRlbnQ6IGI2NAogICAgICB9OwogICAgICBpZihleGlzdGluZyAmJiBleGlzdGluZy5zaGEpIHBheWxvYWQuc2hhID0gZXhpc3Rpbmcuc2hhOwoKICAgICAgcmV0dXJuIGZldGNoKGFwaVVybCwgewogICAgICAgIG1ldGhvZDoiUFVUIiwKICAgICAgICBoZWFkZXJzOmhlYWRlcnMsCiAgICAgICAgYm9keTpKU09OLnN0cmluZ2lmeShwYXlsb2FkKQogICAgICB9KTsKICAgIH0pCiAgICAudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYoci5vayB8fCByLnN0YXR1cz09PTIwMSl7CiAgICAgICAgc2V0RWRpdFN0YXR1cygi4pyFIEtheWRlZGlsZGkhIEJpciBzb25yYWtpIENvbGFiIMOnYWzEscWfdMSxcm1hc8SxbmRhIGFrdGlmIG9sdXIuIiwiZ3JlZW4iKTsKICAgICAgICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7Y2xvc2VFZGl0UG9wdXAoKTt9LDIwMDApOwogICAgICB9IGVsc2UgewogICAgICAgIHNldEVkaXRTdGF0dXMoIuKdjCBIYXRhOiAiK3Iuc3RhdHVzKyIg4oCUIFRva2VuJ8SxIGtvbnRyb2wgZXQiLCJyZWQiKTsKICAgICAgfQogICAgfSkKICAgIC5jYXRjaChmdW5jdGlvbihlKXsgc2V0RWRpdFN0YXR1cygi4p2MIEhhdGE6ICIrZS5tZXNzYWdlLCJyZWQiKTsgfSk7Cn0KCmZ1bmN0aW9uIHNldEVkaXRTdGF0dXMobXNnLCBjb2xvcil7CiAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImVkaXRTdGF0dXMiKTsKICBpZihlbCl7CiAgICBlbC50ZXh0Q29udGVudCA9IG1zZzsKICAgIGVsLnN0eWxlLmNvbG9yID0gY29sb3I9PT0iZ3JlZW4iPyJ2YXIoLS1ncmVlbikiOmNvbG9yPT09InJlZCI/InZhcigtLXJlZDIpIjoidmFyKC0teWVsbG93KSI7CiAgfQp9Cgo8L3NjcmlwdD4KPC9ib2R5Pgo8L2h0bWw+"
    return _b64t.b64decode(_T).decode('utf-8')


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


def build_html(tf_data, timestamp, earnings_data=None, market_data=None, news_data=None, ai_analyses=None, weekly_data=None):
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
    ai_json     = json.dumps(ai_analyses or {}, ensure_ascii=False)
    weekly_json = json.dumps(weekly_data  or {}, ensure_ascii=False)
    html = html.replace("%%AI_DATA%%",      ai_json)
    html = html.replace("%%WEEKLY_DATA%%",  weekly_json)
    html = html.replace("%%PORT%%",          port_json)
    html = html.replace("%%GITHUB_TOKEN%%",  "")
    html = html.replace("%%GITHUB_USER%%",  GITHUB_USER)
    html = html.replace("%%GITHUB_REPO%%",  GITHUB_REPO)
    return html

# ── AI ANALİZLERİ ─────────────────────────────────────────────
print('\n🤖 AI analizleri yapiliyor...')
data_1d = tf_data.get('1d', [])
ai_analyses = {}
for r in data_1d:
    if r.get('hata'):
        continue
    print(f'  {r["ticker"]} analiz ediliyor...')
    analysis = get_ai_analysis(r['ticker'], r, news_data)
    if analysis:
        ai_analyses[r['ticker']] = analysis
        print(f'  ✅ {r["ticker"]} tamamlandi')
print(f'  {len(ai_analyses)} AI analizi tamamlandi')

# ── MAIN ──────────────────────────────────────────────────────
timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
print("\n📊 HTML olusturuluyor...")
html = build_html(tf_data, timestamp, earnings_data, market_data, news_data, ai_analyses, weekly_data)
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
