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
    _T = "PCFET0NUWVBFIGh0bWw+CjxodG1sIGxhbmc9InRyIj4KPGhlYWQ+CjxtZXRhIGNoYXJzZXQ9IlVURi04Ii8+CjxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsaW5pdGlhbC1zY2FsZT0xIi8+Cjx0aXRsZT5DQU5TTElNIFNjYW5uZXI8L3RpdGxlPgo8bGluayByZWw9Imljb24iIHR5cGU9ImltYWdlL3N2Zyt4bWwiIGhyZWY9ImRhdGE6aW1hZ2Uvc3ZnK3htbCwlM0NzdmcgeG1sbnM9J2h0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnJyB2aWV3Qm94PScwIDAgMzIgMzInJTNFJTNDcmVjdCB3aWR0aD0nMzInIGhlaWdodD0nMzInIHJ4PSc2JyBmaWxsPSclMjMwZDExMTcnLyUzRSUzQ3BvbHlsaW5lIHBvaW50cz0nNCwyNCAxMCwxNiAxNiwyMCAyMiwxMCAyOCwxNCcgZmlsbD0nbm9uZScgc3Ryb2tlPSclMjMxMGI5ODEnIHN0cm9rZS13aWR0aD0nMi41JyBzdHJva2UtbGluZWNhcD0ncm91bmQnIHN0cm9rZS1saW5lam9pbj0ncm91bmQnLyUzRSUzQy9zdmclM0UiPgo8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PVNwYWNlK0dyb3Rlc2s6d2dodEA0MDA7NTAwOzYwMDs3MDAmZmFtaWx5PUJlYmFzK05ldWUmZmFtaWx5PUpldEJyYWlucytNb25vOndnaHRANDAwOzYwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCIvPgo8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9jaGFydC5qc0A0LjQuMC9kaXN0L2NoYXJ0LnVtZC5taW4uanMiPjwvc2NyaXB0Pgo8c3R5bGU+Cjpyb290ey0tYmc6IzA1MDcwZjstLWJnMjojMGQxMTE3Oy0tYmczOiMxNjFiMjQ7LS1ib3JkZXI6cmdiYSgyNTUsMjU1LDI1NSwwLjA4KTstLXRleHQ6I2UyZThmMDstLW11dGVkOiM0YjU1NjM7LS1ncmVlbjojMTBiOTgxOy0tZ3JlZW4yOiMzNGQzOTk7LS1yZWQ6I2VmNDQ0NDstLXJlZDI6I2Y4NzE3MTstLXllbGxvdzojZjU5ZTBiO30KKntib3gtc2l6aW5nOmJvcmRlci1ib3g7bWFyZ2luOjA7cGFkZGluZzowfQpib2R5e2JhY2tncm91bmQ6dmFyKC0tYmcpO2NvbG9yOnZhcigtLXRleHQpO2ZvbnQtZmFtaWx5OidTcGFjZSBHcm90ZXNrJyxzYW5zLXNlcmlmO21pbi1oZWlnaHQ6MTAwdmh9Ci5oZWFkZXJ7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCMwZDExMTcsIzExMTgyNyk7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtwYWRkaW5nOjE0cHggMjBweDtwb3NpdGlvbjpzdGlja3k7dG9wOjA7ei1pbmRleDoxMDB9Ci5oZWFkZXItaW5uZXJ7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTBweDttYXgtd2lkdGg6MTQwMHB4O21hcmdpbjowIGF1dG99Ci5sb2dvLW1haW57Zm9udC1mYW1pbHk6J0JlYmFzIE5ldWUnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjIycHg7bGV0dGVyLXNwYWNpbmc6NHB4O2JhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZywjMTBiOTgxLCMzYjgyZjYpOy13ZWJraXQtYmFja2dyb3VuZC1jbGlwOnRleHQ7LXdlYmtpdC10ZXh0LWZpbGwtY29sb3I6dHJhbnNwYXJlbnR9Ci50aW1lc3RhbXB7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLmxpdmUtZG90e3dpZHRoOjdweDtoZWlnaHQ6N3B4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6dmFyKC0tZ3JlZW4pO2FuaW1hdGlvbjpwdWxzZSAycyBpbmZpbml0ZTtkaXNwbGF5OmlubGluZS1ibG9jazttYXJnaW4tcmlnaHQ6NXB4fQpAa2V5ZnJhbWVzIHB1bHNlezAlLDEwMCV7b3BhY2l0eToxO2JveC1zaGFkb3c6MCAwIDAgMCByZ2JhKDE2LDE4NSwxMjksLjQpfTUwJXtvcGFjaXR5Oi43O2JveC1zaGFkb3c6MCAwIDAgNnB4IHJnYmEoMTYsMTg1LDEyOSwwKX19Ci5uYXZ7ZGlzcGxheTpmbGV4O2dhcDo0cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7b3ZlcmZsb3cteDphdXRvO2ZsZXgtd3JhcDp3cmFwfQoudGFie3BhZGRpbmc6NnB4IDE0cHg7Ym9yZGVyLXJhZGl1czo2cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NTAwO2JvcmRlcjoxcHggc29saWQgdHJhbnNwYXJlbnQ7YmFja2dyb3VuZDpub25lO2NvbG9yOnZhcigtLW11dGVkKTt0cmFuc2l0aW9uOmFsbCAuMnM7d2hpdGUtc3BhY2U6bm93cmFwfQoudGFiOmhvdmVye2NvbG9yOnZhcigtLXRleHQpO2JhY2tncm91bmQ6dmFyKC0tYmczKX0KLnRhYi5hY3RpdmV7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLXRleHQpO2JvcmRlci1jb2xvcjp2YXIoLS1ib3JkZXIpfQoudGFiLnBvcnQuYWN0aXZle2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyLWNvbG9yOnJnYmEoMTYsMTg1LDEyOSwuMyl9Ci50Zi1yb3d7ZGlzcGxheTpmbGV4O2dhcDo2cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7YWxpZ24taXRlbXM6Y2VudGVyO2ZsZXgtd3JhcDp3cmFwfQoudGYtYnRue3BhZGRpbmc6NXB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Y3Vyc29yOnBvaW50ZXI7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO3RyYW5zaXRpb246YWxsIC4yc30KLnRmLWJ0bi5hY3RpdmV7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtjb2xvcjojNjBhNWZhO2JvcmRlci1jb2xvcjpyZ2JhKDU5LDEzMCwyNDYsLjQpfQoudGYtYnRuLnN0YXJ7cG9zaXRpb246cmVsYXRpdmV9Ci50Zi1idG4uc3Rhcjo6YWZ0ZXJ7Y29udGVudDon4piFJztwb3NpdGlvbjphYnNvbHV0ZTt0b3A6LTVweDtyaWdodDotNHB4O2ZvbnQtc2l6ZTo4cHg7Y29sb3I6dmFyKC0teWVsbG93KX0KLnRmLWhpbnR7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpfQouc3RhdHN7ZGlzcGxheTpmbGV4O2dhcDo4cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7ZmxleC13cmFwOndyYXB9Ci5waWxse2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjVweDtwYWRkaW5nOjRweCAxMHB4O2JvcmRlci1yYWRpdXM6MjBweDtmb250LXNpemU6MTFweDtmb250LXdlaWdodDo2MDA7Ym9yZGVyOjFweCBzb2xpZH0KLnBpbGwuZ3tiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMSk7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlci1jb2xvcjpyZ2JhKDE2LDE4NSwxMjksLjI1KX0KLnBpbGwucntiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xKTtjb2xvcjp2YXIoLS1yZWQyKTtib3JkZXItY29sb3I6cmdiYSgyMzksNjgsNjgsLjI1KX0KLnBpbGwueXtiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMSk7Y29sb3I6dmFyKC0teWVsbG93KTtib3JkZXItY29sb3I6cmdiYSgyNDUsMTU4LDExLC4yNSl9Ci5waWxsLmJ7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjEpO2NvbG9yOiM2MGE1ZmE7Ym9yZGVyLWNvbG9yOnJnYmEoNTksMTMwLDI0NiwuMjUpfQoucGlsbC5te2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Ym9yZGVyLWNvbG9yOnZhcigtLWJvcmRlcil9Ci5kb3R7d2lkdGg6NXB4O2hlaWdodDo1cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpjdXJyZW50Q29sb3J9Ci5tYWlue3BhZGRpbmc6MTRweCAyMHB4O21heC13aWR0aDoxNDAwcHg7bWFyZ2luOjAgYXV0b30KLmdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgzMDBweCwxZnIpKTtnYXA6MTBweH0KQG1lZGlhKG1heC13aWR0aDo0ODBweCl7LmdyaWR7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmcn19Ci5jYXJke2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O292ZXJmbG93OmhpZGRlbjtjdXJzb3I6cG9pbnRlcjt0cmFuc2l0aW9uOmFsbCAuMnN9Ci5jYXJkOmhvdmVye3RyYW5zZm9ybTp0cmFuc2xhdGVZKC0ycHgpO2JveC1zaGFkb3c6MCA4cHggMjRweCByZ2JhKDAsMCwwLC40KX0KLmFjY2VudHtoZWlnaHQ6M3B4fQouY2JvZHl7cGFkZGluZzoxMnB4IDE0cHh9Ci5jdG9we2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpmbGV4LXN0YXJ0O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206OHB4fQoudGlja2Vye2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyMHB4O2xldHRlci1zcGFjaW5nOjJweDtsaW5lLWhlaWdodDoxfQouY3Bye3RleHQtYWxpZ246cmlnaHR9Ci5wdmFse2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTVweDtmb250LXdlaWdodDo2MDB9Ci5wY2hne2ZvbnQtc2l6ZToxMXB4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTttYXJnaW4tdG9wOjJweH0KLmJhZGdle2Rpc3BsYXk6aW5saW5lLWJsb2NrO3BhZGRpbmc6MnB4IDhweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6LjVweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLXRvcDozcHh9Ci5wb3J0LWJhZGdle2Rpc3BsYXk6aW5saW5lLWZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDozcHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwO2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xMik7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yNSk7bWFyZ2luLWxlZnQ6NXB4fQouc2lnc3tkaXNwbGF5OmZsZXg7ZmxleC13cmFwOndyYXA7Z2FwOjNweDttYXJnaW4tYm90dG9tOjhweH0KLnNwe2ZvbnQtc2l6ZTo5cHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLnNne2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbjIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKX0KLnNie2JhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjEpO2NvbG9yOnZhcigtLXJlZDIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpfQouc257YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLW11dGVkKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5jaGFydC13e2hlaWdodDo3NXB4O21hcmdpbi10b3A6OHB4fQoubHZsc3tkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgzLDFmcik7Z2FwOjVweDttYXJnaW4tdG9wOjhweH0KLmx2e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjVweDtwYWRkaW5nOjZweDt0ZXh0LWFsaWduOmNlbnRlcjtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5sbHtmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MnB4fQoubHZhbHtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwfQoub3ZlcmxheXtwb3NpdGlvbjpmaXhlZDtpbnNldDowO2JhY2tncm91bmQ6cmdiYSgwLDAsMCwuODgpO3otaW5kZXg6MTAwMDtkaXNwbGF5Om5vbmU7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7cGFkZGluZzoxNnB4fQoub3ZlcmxheS5vcGVue2Rpc3BsYXk6ZmxleH0KLm1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjUyMHB4O21heC1oZWlnaHQ6OTJ2aDtvdmVyZmxvdy15OmF1dG99Ci5taGVhZHtwYWRkaW5nOjE4cHggMThweCAwO2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpmbGV4LXN0YXJ0fQoubXRpdGxle2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZTozMHB4O2xldHRlci1zcGFjaW5nOjNweH0KLm1jbG9zZXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTt3aWR0aDozMHB4O2hlaWdodDozMHB4O2JvcmRlci1yYWRpdXM6N3B4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxNXB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcn0KLm1ib2R5e3BhZGRpbmc6MTRweCAxOHB4IDE4cHh9Ci5tY2hhcnR3e2hlaWdodDoxNTBweDttYXJnaW4tYm90dG9tOjE0cHh9Ci5kZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjdweDttYXJnaW4tYm90dG9tOjEycHh9Ci5kY3tiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo3cHg7cGFkZGluZzo5cHggMTFweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5kbHtmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206M3B4fQouZHZ7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMH0KLmRib3h7Ym9yZGVyLXJhZGl1czo5cHg7cGFkZGluZzoxM3B4O21hcmdpbi1ib3R0b206MTJweDtib3JkZXI6MXB4IHNvbGlkfQouZGxibHtmb250LXNpemU6OXB4O2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo1cHh9Ci5kdmVyZHtmb250LWZhbWlseTonQmViYXMgTmV1ZScsc2Fucy1zZXJpZjtmb250LXNpemU6MjZweDtsZXR0ZXItc3BhY2luZzoycHg7bWFyZ2luLWJvdHRvbTo4cHh9Ci5kcm93e2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjRweDtmb250LXNpemU6MTJweH0KLmRrZXl7Y29sb3I6dmFyKC0tbXV0ZWQpfQoucnJiYXJ7aGVpZ2h0OjRweDtiYWNrZ3JvdW5kOnZhcigtLWJnKTtib3JkZXItcmFkaXVzOjJweDttYXJnaW4tdG9wOjdweDtvdmVyZmxvdzpoaWRkZW59Ci5ycmZpbGx7aGVpZ2h0OjEwMCU7Ym9yZGVyLXJhZGl1czoycHg7dHJhbnNpdGlvbjp3aWR0aCAuOHMgZWFzZX0KLnZwYm94e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjdweDtwYWRkaW5nOjEwcHg7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO21hcmdpbi1ib3R0b206MTJweH0KLnZwdGl0bGV7Zm9udC1zaXplOjlweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo3cHh9Ci52cGdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoMywxZnIpO2dhcDo1cHh9Ci52cGN7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlci1yYWRpdXM6NXB4O3BhZGRpbmc6N3B4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlcjoxcHggc29saWR9Ci5taW5mb3tkaXNwbGF5OmlubGluZS1mbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO3dpZHRoOjE0cHg7aGVpZ2h0OjE0cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpyZ2JhKDk2LDE2NSwyNTAsLjIpO2NvbG9yOiM2MGE1ZmE7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7Y3Vyc29yOnBvaW50ZXI7bWFyZ2luLWxlZnQ6NHB4O2JvcmRlcjoxcHggc29saWQgcmdiYSg5NiwxNjUsMjUwLC4zKX0KLm1pbmZvLXBvcHVwe3Bvc2l0aW9uOmZpeGVkO2luc2V0OjA7YmFja2dyb3VuZDpyZ2JhKDAsMCwwLC44OCk7ei1pbmRleDoyMDAwO2Rpc3BsYXk6bm9uZTthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjtwYWRkaW5nOjE2cHh9Ci5taW5mby1wb3B1cC5vcGVue2Rpc3BsYXk6ZmxleH0KLm1pbmZvLW1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjQ4MHB4O21heC1oZWlnaHQ6ODV2aDtvdmVyZmxvdy15OmF1dG87cGFkZGluZzoyMHB4O3Bvc2l0aW9uOnJlbGF0aXZlfQoubWluZm8tdGl0bGV7Zm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4fQoubWluZm8tc291cmNle2ZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjEycHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4O2ZsZXgtd3JhcDp3cmFwfQoubWluZm8tcmVse3BhZGRpbmc6MnB4IDdweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMH0KLm1pbmZvLXJlbC5oaWdoe2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Y29sb3I6IzEwYjk4MX0KLm1pbmZvLXJlbC5tZWRpdW17YmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjE1KTtjb2xvcjojZjU5ZTBifQoubWluZm8tcmVsLmxvd3tiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Y29sb3I6I2VmNDQ0NH0KLm1pbmZvLWRlc2N7Zm9udC1zaXplOjEycHg7Y29sb3I6Izk0YTNiODtsaW5lLWhlaWdodDoxLjY7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8td2FybmluZ3tiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjZweDtwYWRkaW5nOjhweCAxMHB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOiNmNTllMGI7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8tcmFuZ2Vze21hcmdpbi1ib3R0b206MTRweH0KLm1pbmZvLXJhbmdlLXRpdGxle2ZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHh9Ci5taW5mby1yYW5nZXtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo4cHg7bWFyZ2luLWJvdHRvbTo2cHg7cGFkZGluZzo2cHggOHB4O2JvcmRlci1yYWRpdXM6NnB4O2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMDIpfQoubWluZm8tcmFuZ2UtZG90e3dpZHRoOjhweDtoZWlnaHQ6OHB4O2JvcmRlci1yYWRpdXM6NTAlO2ZsZXgtc2hyaW5rOjB9Ci5taW5mby1jYW5zbGlte2JhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6NnB4O3BhZGRpbmc6OHB4IDEwcHg7Zm9udC1zaXplOjExcHg7Y29sb3I6IzYwYTVmYX0KLm1pbmZvLWNsb3Nle3Bvc2l0aW9uOmFic29sdXRlO3RvcDoxNnB4O3JpZ2h0OjE2cHg7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4xKTtjb2xvcjojOTRhM2I4O3dpZHRoOjI4cHg7aGVpZ2h0OjI4cHg7Ym9yZGVyLXJhZGl1czo3cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjE0cHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyfQo6Oi13ZWJraXQtc2Nyb2xsYmFye3dpZHRoOjRweDtoZWlnaHQ6NHB4fQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRyYWNre2JhY2tncm91bmQ6dmFyKC0tYmcpfQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRodW1ie2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMSk7Ym9yZGVyLXJhZGl1czoycHh9Cjwvc3R5bGU+CjwvaGVhZD4KPGJvZHk+CjxkaXYgY2xhc3M9ImhlYWRlciI+CiAgPGRpdiBjbGFzcz0iaGVhZGVyLWlubmVyIj4KICAgIDxzcGFuIGNsYXNzPSJsb2dvLW1haW4iPkNBTlNMSU0gU0NBTk5FUjwvc3Bhbj4KICAgIDxzcGFuIGNsYXNzPSJ0aW1lc3RhbXAiPjxzcGFuIGNsYXNzPSJsaXZlLWRvdCI+PC9zcGFuPiUlVElNRVNUQU1QJSU8L3NwYW4+CiAgICA8YnV0dG9uIG9uY2xpY2s9Im9wZW5FZGl0TGlzdCgpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMyk7Y29sb3I6IzYwYTVmYTtwYWRkaW5nOjVweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMXB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtZmFtaWx5OmluaGVyaXQiPuKcj++4jyBMaXN0ZXlpIETDvHplbmxlPC9idXR0b24+CiAgPC9kaXY+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJuYXYiPgogIDxidXR0b24gY2xhc3M9InRhYiBhY3RpdmUiIG9uY2xpY2s9InNldFRhYignZGFzaGJvYXJkJyx0aGlzKSI+8J+PoCBEYXNoYm9hcmQ8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignYWxsJyx0aGlzKSI+8J+TiiBIaXNzZWxlcjwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiBwb3J0IiBvbmNsaWNrPSJzZXRUYWIoJ3BvcnQnLHRoaXMpIj7wn5K8IFBvcnRmw7Z5w7xtPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2J1eScsdGhpcykiPvCfk4ggQWw8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignc2VsbCcsdGhpcykiPvCfk4kgU2F0PC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2Vhcm5pbmdzJyx0aGlzKSI+8J+ThSBFYXJuaW5nczwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdydXRpbicsdGhpcykiPuKchSBSdXRpbjwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdoYWZ0YWxpaycsdGhpcykiPvCfk4ggSGFmdGFsxLFrPC9idXR0b24+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJ0Zi1yb3ciIGlkPSJ0ZlJvdyIgc3R5bGU9ImRpc3BsYXk6bm9uZSI+CiAgPGJ1dHRvbiBjbGFzcz0idGYtYnRuIGFjdGl2ZSIgZGF0YS10Zj0iMWQiIG9uY2xpY2s9InNldFRmKCcxZCcsdGhpcykiPjFHPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGYtYnRuIHN0YXIiIGRhdGEtdGY9IjF3ayIgb25jbGljaz0ic2V0VGYoJzF3aycsdGhpcykiPjFIPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGYtYnRuIiBkYXRhLXRmPSIxbW8iIG9uY2xpY2s9InNldFRmKCcxbW8nLHRoaXMpIj4xQTwvYnV0dG9uPgogIDxzcGFuIGNsYXNzPSJ0Zi1oaW50Ij5DQU5TTElNIMO2bmVyaWxlbjogMUcgKyAxSDwvc3Bhbj4KPC9kaXY+CjxkaXYgY2xhc3M9InN0YXRzIiBpZD0ic3RhdHMiPjwvZGl2Pgo8ZGl2IGNsYXNzPSJtYWluIj48ZGl2IGNsYXNzPSJncmlkIiBpZD0iZ3JpZCI+PC9kaXY+PC9kaXY+CjxkaXYgY2xhc3M9Im92ZXJsYXkiIGlkPSJvdmVybGF5IiBvbmNsaWNrPSJjbG9zZU0oZXZlbnQpIj4KICA8ZGl2IGNsYXNzPSJtb2RhbCIgaWQ9Im1vZGFsIj48L2Rpdj4KPC9kaXY+Cgo8ZGl2IGNsYXNzPSJtaW5mby1wb3B1cCIgaWQ9ImVkaXRQb3B1cCIgb25jbGljaz0iY2xvc2VFZGl0UG9wdXAoZXZlbnQpIj4KICA8ZGl2IGNsYXNzPSJtaW5mby1tb2RhbCIgc3R5bGU9InBvc2l0aW9uOnJlbGF0aXZlO21heC13aWR0aDo1NjBweCIgaWQ9ImVkaXRNb2RhbCI+CiAgICA8YnV0dG9uIGNsYXNzPSJtaW5mby1jbG9zZSIgb25jbGljaz0iY2xvc2VFZGl0UG9wdXAoKSI+4pyVPC9idXR0b24+CiAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCk7bWFyZ2luLWJvdHRvbTo0cHgiPuKcj++4jyBMaXN0ZXlpIETDvHplbmxlPC9kaXY+CiAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbToxNnB4Ij5HaXRIdWIgQVBJIGtleSBnZXJla2xpIOKAlCBkZcSfacWfaWtsaWtsZXIgYW7EsW5kYSBrYXlkZWRpbGlyPC9kaXY+CiAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjE2cHg7bWFyZ2luLWJvdHRvbToxNnB4Ij4KICAgICAgPGRpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+8J+TiyBXYXRjaGxpc3Q8L2Rpdj4KICAgICAgICA8ZGl2IGlkPSJ3YXRjaGxpc3RFZGl0b3IiPjwvZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6NnB4O21hcmdpbi10b3A6OHB4Ij4KICAgICAgICAgIDxpbnB1dCBpZD0ibmV3V2F0Y2hUaWNrZXIiIHBsYWNlaG9sZGVyPSJIaXNzZSBla2xlIChUU0xBKSIgc3R5bGU9ImZsZXg6MTtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLXRleHQpO3BhZGRpbmc6NnB4IDEwcHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Zm9udC1mYW1pbHk6aW5oZXJpdDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2UiLz4KICAgICAgICAgIDxidXR0b24gb25jbGljaz0iYWRkVGlja2VyKCd3YXRjaCcpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6NnB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Y3Vyc29yOnBvaW50ZXIiPisgRWtsZTwvYnV0dG9uPgogICAgICAgIDwvZGl2PgogICAgICA8L2Rpdj4KICAgICAgPGRpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+8J+SvCBQb3J0ZsO2eTwvZGl2PgogICAgICAgIDxkaXYgaWQ9InBvcnRmb2xpb0VkaXRvciI+PC9kaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo2cHg7bWFyZ2luLXRvcDo4cHgiPgogICAgICAgICAgPGlucHV0IGlkPSJuZXdQb3J0VGlja2VyIiBwbGFjZWhvbGRlcj0iSGlzc2UgZWtsZSAoQUFQTCkiIHN0eWxlPSJmbGV4OjE7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS10ZXh0KTtwYWRkaW5nOjZweCAxMHB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2ZvbnQtZmFtaWx5OmluaGVyaXQ7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlIi8+CiAgICAgICAgICA8YnV0dG9uIG9uY2xpY2s9ImFkZFRpY2tlcigncG9ydCcpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6NnB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Y3Vyc29yOnBvaW50ZXIiPisgRWtsZTwvYnV0dG9uPgogICAgICAgIDwvZGl2PgogICAgICA8L2Rpdj4KICAgIDwvZGl2PgogICAgPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDEycHg7bWFyZ2luLWJvdHRvbToxNHB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLWdyZWVuKSI+4pyFIERlxJ9pxZ9pa2xpa2xlciBrYXlkZWRpbGluY2UgYmlyIHNvbnJha2kgQ29sYWIgw6dhbMSxxZ90xLFybWFzxLFuZGEgYWt0aWYgb2x1ci48L2Rpdj4KPGRpdiBzdHlsZT0ibWFyZ2luLWJvdHRvbToxMnB4Ij4KICAgICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NXB4Ij5HaXRIdWIgVG9rZW4gKGJpciBrZXogZ2lyLCB0YXJheWljaSBoYXRpcmxheWFjYWspPC9kaXY+CiAgICAgIDxpbnB1dCBpZD0iZ2hUb2tlbklucHV0IiBwbGFjZWhvbGRlcj0iZ2hwXy4uLiIgc3R5bGU9IndpZHRoOjEwMCU7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS10ZXh0KTtwYWRkaW5nOjhweCAxMHB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMXB4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSIvPgogICAgPC9kaXY+CiAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjhweCI+CiAgICAgIDxidXR0b24gb25jbGljaz0ic2F2ZUxpc3RUb0dpdGh1YigpIiBzdHlsZT0iZmxleDoxO2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjMpO2NvbG9yOnZhcigtLWdyZWVuKTtwYWRkaW5nOjEwcHg7Ym9yZGVyLXJhZGl1czo4cHg7Zm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2N1cnNvcjpwb2ludGVyIj7wn5K+IEdpdEh1YidhIEtheWRldDwvYnV0dG9uPgogICAgICA8YnV0dG9uIG9uY2xpY2s9ImNsb3NlRWRpdFBvcHVwKCkiIHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTtwYWRkaW5nOjEwcHggMTZweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTNweDtjdXJzb3I6cG9pbnRlciI+xLBwdGFsPC9idXR0b24+CiAgICA8L2Rpdj4KICAgIDxkaXYgaWQ9ImVkaXRTdGF0dXMiIHN0eWxlPSJtYXJnaW4tdG9wOjEwcHg7Zm9udC1zaXplOjEycHg7dGV4dC1hbGlnbjpjZW50ZXIiPjwvZGl2PgogIDwvZGl2Pgo8L2Rpdj4KCjxkaXYgY2xhc3M9Im1pbmZvLXBvcHVwIiBpZD0ibWluZm9Qb3B1cCIgb25jbGljaz0iY2xvc2VJbmZvUG9wdXAoZXZlbnQpIj4KICA8ZGl2IGNsYXNzPSJtaW5mby1tb2RhbCIgaWQ9Im1pbmZvTW9kYWwiPgogICAgPGJ1dHRvbiBjbGFzcz0ibWluZm8tY2xvc2UiIG9uY2xpY2s9ImNsb3NlSW5mb1BvcHVwKCkiPuKclTwvYnV0dG9uPgogICAgPGRpdiBpZD0ibWluZm9Db250ZW50Ij48L2Rpdj4KICA8L2Rpdj4KPC9kaXY+CjxzY3JpcHQ+CnZhciBNRVRSSUNTID0gewogIC8vIFRFS07EsEsKICAnUlNJJzogewogICAgdGl0bGU6ICdSU0kgKEfDtnJlY2VsaSBHw7zDpyBFbmRla3NpKScsCiAgICBkZXNjOiAnSGlzc2VuaW4gYcWfxLFyxLEgYWzEsW0gdmV5YSBhxZ/EsXLEsSBzYXTEsW0gYsO2bGdlc2luZGUgb2x1cCBvbG1hZMSxxJ/EsW7EsSBnw7ZzdGVyaXIuIDE0IGfDvG5sw7xrIGZpeWF0IGhhcmVrZXRsZXJpbmkgYW5hbGl6IGVkZXIuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J0HFn8SxcsSxIFNhdMSxbScsbWluOjAsbWF4OjMwLGNvbG9yOidncmVlbicsZGVzYzonRsSxcnNhdCBiw7ZsZ2VzaSDigJQgZml5YXQgw6dvayBkw7zFn23DvMWfJ30sCiAgICAgIHtsYWJlbDonTm9ybWFsJyxtaW46MzAsbWF4OjcwLGNvbG9yOid5ZWxsb3cnLGRlc2M6J07DtnRyIGLDtmxnZSd9LAogICAgICB7bGFiZWw6J0HFn8SxcsSxIEFsxLFtJyxtaW46NzAsbWF4OjEwMCxjb2xvcjoncmVkJyxkZXNjOidEaWtrYXQg4oCUIGZpeWF0IMOnb2sgecO8a3NlbG1pxZ8nfQogICAgXSwKICAgIGNhbnNsaW06ICdOIGtyaXRlcmkgaWxlIGlsZ2lsaSDigJQgZml5YXQgbW9tZW50dW11JwogIH0sCiAgJ1NNQTUwJzogewogICAgdGl0bGU6ICdTTUEgNTAgKDUwIEfDvG5sw7xrIEhhcmVrZXRsaSBPcnRhbGFtYSknLAogICAgZGVzYzogJ1NvbiA1MCBnw7xuw7xuIG9ydGFsYW1hIGthcGFuxLHFnyBmaXlhdMSxLiBLxLFzYS1vcnRhIHZhZGVsaSB0cmVuZCBnw7ZzdGVyZ2VzaS4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonw5x6ZXJpbmRlJyxjb2xvcjonZ3JlZW4nLGRlc2M6J0vEsXNhIHZhZGVsaSB0cmVuZCBwb3ppdGlmIOKAlCBnw7zDp2zDvCBzaW55YWwnfSwKICAgICAge2xhYmVsOidBbHTEsW5kYScsY29sb3I6J3JlZCcsZGVzYzonS8Sxc2EgdmFkZWxpIHRyZW5kIG5lZ2F0aWYnfQogICAgXSwKICAgIGNhbnNsaW06ICdNIGtyaXRlcmkg4oCUIHBpeWFzYSB0cmVuZGknCiAgfSwKICAnU01BMjAwJzogewogICAgdGl0bGU6ICdTTUEgMjAwICgyMDAgR8O8bmzDvGsgSGFyZWtldGxpIE9ydGFsYW1hKScsCiAgICBkZXNjOiAnU29uIDIwMCBnw7xuw7xuIG9ydGFsYW1hIGthcGFuxLHFnyBmaXlhdMSxLiBVenVuIHZhZGVsaSB0cmVuZCBnw7ZzdGVyZ2VzaS4gRW4gw7ZuZW1saSB0ZWtuaWsgc2V2aXllLicsCiAgICBzb3VyY2U6ICdUZWtuaWsgQW5hbGl6JywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOifDnHplcmluZGUnLGNvbG9yOidncmVlbicsZGVzYzonVXp1biB2YWRlbGkgYm/En2EgdHJlbmRpbmRlIOKAlCBDQU5TTElNIGnDp2luIMWfYXJ0J30sCiAgICAgIHtsYWJlbDonQWx0xLFuZGEnLGNvbG9yOidyZWQnLGRlc2M6J1V6dW4gdmFkZWxpIGF5xLEgdHJlbmRpbmRlIOKAlCBDQU5TTElNIGnDp2luIGdpcm1lJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTSBrcml0ZXJpIOKAlCB6b3J1bmx1IGtvxZ91bCcKICB9LAogICc1MlcnOiB7CiAgICB0aXRsZTogJzUyIEhhZnRhbMSxayBQb3ppc3lvbicsCiAgICBkZXNjOiAnSGlzc2VuaW4gc29uIDEgecSxbGRha2kgZml5YXQgYXJhbMSxxJ/EsW5kYSBuZXJlZGUgb2xkdcSfdW51IGfDtnN0ZXJpci4gMD15xLFsxLFuIGRpYmksIDEwMD15xLFsxLFuIHppcnZlc2kuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzAtMzAlJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1nEsWzEsW4gZGliaW5lIHlha8SxbiDigJQgcG90YW5zaXllbCBmxLFyc2F0J30sCiAgICAgIHtsYWJlbDonMzAtNzAlJyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIGLDtmxnZSDigJQgbsO2dHInfSwKICAgICAge2xhYmVsOic3MC04NSUnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1ppcnZleWUgeWFrbGHFn8SxeW9yIOKAlCBpemxlJ30sCiAgICAgIHtsYWJlbDonODUtMTAwJScsY29sb3I6J3JlZCcsZGVzYzonWmlydmV5ZSDDp29rIHlha8SxbiDigJQgZGlra2F0bGkgZ2lyJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTiBrcml0ZXJpIOKAlCB5ZW5pIHppcnZlIGvEsXLEsWzEsW3EsSBpw6dpbiBpZGVhbCBiw7ZsZ2UgJTg1LTEwMCcKICB9LAogICdIYWNpbSc6IHsKICAgIHRpdGxlOiAnSGFjaW0gKMSwxZ9sZW0gTWlrdGFyxLEpJywKICAgIGRlc2M6ICdHw7xubMO8ayBpxZ9sZW0gaGFjbWluaW4gc29uIDIwIGfDvG5sw7xrIG9ydGFsYW1heWEgb3JhbsSxLiBHw7zDp2zDvCBoYXJla2V0bGVyaW4gaGFjaW1sZSBkZXN0ZWtsZW5tZXNpIGdlcmVraXIuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J1nDvGtzZWsgKD4xLjN4KScsY29sb3I6J2dyZWVuJyxkZXNjOidLdXJ1bXNhbCBpbGdpIHZhciDigJQgZ8O8w6dsw7wgc2lueWFsJ30sCiAgICAgIHtsYWJlbDonTm9ybWFsICgwLjctMS4zeCknLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGFsYW1hIGlsZ2knfSwKICAgICAge2xhYmVsOidEw7zFn8O8ayAoPDAuN3gpJyxjb2xvcjoncmVkJyxkZXNjOifEsGxnaSBhemFsbcSxxZ8g4oCUIGRpa2thdCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ1Mga3JpdGVyaSDigJQgYXJ6L3RhbGVwIGRlbmdlc2knCiAgfSwKICAvLyBURU1FTAogICdGb3J3YXJkUEUnOiB7CiAgICB0aXRsZTogJ0ZvcndhcmQgUC9FICjEsGxlcml5ZSBEw7Zuw7xrIEZpeWF0L0themFuw6cpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gw7Zuw7xtw7x6ZGVraSAxMiBheWRha2kgdGFobWluaSBrYXphbmPEsW5hIGfDtnJlIGZpeWF0xLEuIFRyYWlsaW5nIFAvRVwnZGVuIGRhaGEgw7ZuZW1saSDDp8O8bmvDvCBnZWxlY2XEn2UgYmFrxLF5b3IuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgQW5hbGlzdCB0YWhtaW5pJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdBbmFsaXN0IHRhaG1pbmxlcmluZSBkYXlhbsSxciwgeWFuxLFsdMSxY8SxIG9sYWJpbGlyJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzwxNScsY29sb3I6J2dyZWVuJyxkZXNjOidVY3V6IOKAlCBiw7x5w7xtZSBiZWtsZW50aXNpIGTDvMWfw7xrIHZleWEgaGlzc2UgZGXEn2VyIGFsdMSxbmRhJ30sCiAgICAgIHtsYWJlbDonMTUtMjUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwg4oCUIMOnb8SfdSBzZWt0w7ZyIGnDp2luIG5vcm1hbCd9LAogICAgICB7bGFiZWw6JzI1LTQwJyxjb2xvcjoneWVsbG93JyxkZXNjOidQYWhhbMSxIGFtYSBiw7x5w7xtZSBwcmltaSDDtmRlbml5b3InfSwKICAgICAge2xhYmVsOic+NDAnLGNvbG9yOidyZWQnLGRlc2M6J8OHb2sgcGFoYWzEsSDigJQgecO8a3NlayBiw7x5w7xtZSBiZWtsZW50aXNpIGZpeWF0bGFubcSxxZ8nfQogICAgXSwKICAgIGNhbnNsaW06ICdDIHZlIEEga3JpdGVybGVyaSBpbGUgaWxnaWxpJwogIH0sCiAgJ1BFRyc6IHsKICAgIHRpdGxlOiAnUEVHIE9yYW7EsSAoRml5YXQvS2F6YW7Dpy9Cw7x5w7xtZSknLAogICAgZGVzYzogJ1AvRSBvcmFuxLFuxLEgYsO8ecO8bWUgaMSxesSxeWxhIGthcsWfxLFsYcWfdMSxcsSxci4gQsO8ecO8eWVuIMWfaXJrZXRsZXIgacOnaW4gUC9FXCdkZW4gZGFoYSBkb8SfcnUgZGXEn2VybGVtZSDDtmzDp8O8dMO8LiBQRUc9MSBhZGlsIGRlxJ9lciBrYWJ1bCBlZGlsaXIuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgQW5hbGlzdCB0YWhtaW5pJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdBbmFsaXN0IGLDvHnDvG1lIHRhaG1pbmxlcmluZSBkYXlhbsSxcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic8MS4wJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1VjdXog4oCUIGLDvHnDvG1lc2luZSBnw7ZyZSBkZcSfZXIgYWx0xLFuZGEnfSwKICAgICAge2xhYmVsOicxLjAtMS41Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J01ha3VsIOKAlCBhZGlsIGZpeWF0IGNpdmFyxLEnfSwKICAgICAge2xhYmVsOicxLjUtMi4wJyxjb2xvcjoneWVsbG93JyxkZXNjOidCaXJheiBwYWhhbMSxJ30sCiAgICAgIHtsYWJlbDonPjIuMCcsY29sb3I6J3JlZCcsZGVzYzonUGFoYWzEsSDigJQgZGlra2F0bGkgb2wnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIGLDvHnDvG1lIGthbGl0ZXNpJwogIH0sCiAgJ0VQU0dyb3d0aCc6IHsKICAgIHRpdGxlOiAnRVBTIELDvHnDvG1lc2kgKMOHZXlyZWtsaWssIFlvWSknLAogICAgZGVzYzogJ8WeaXJrZXRpbiBoaXNzZSBiYcWfxLFuYSBrYXphbmPEsW7EsW4gZ2XDp2VuIHnEsWzEsW4gYXluxLEgw6dleXJlxJ9pbmUgZ8O2cmUgYXJ0xLHFn8SxLiBDQU5TTElNXCdpbiBlbiBrcml0aWsga3JpdGVyaS4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMjUnLGNvbG9yOidncmVlbicsZGVzYzonR8O8w6dsw7wgYsO8ecO8bWUg4oCUIENBTlNMSU0ga3JpdGVyaSBrYXLFn8SxbGFuZMSxJ30sCiAgICAgIHtsYWJlbDonJTE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWkgYsO8ecO8bWUnfSwKICAgICAge2xhYmVsOiclMC0xNScsY29sb3I6J3llbGxvdycsZGVzYzonWmF5xLFmIGLDvHnDvG1lJ30sCiAgICAgIHtsYWJlbDonPDAnLGNvbG9yOidyZWQnLGRlc2M6J0themFuw6cgZMO8xZ/DvHlvciDigJQgZGlra2F0J30KICAgIF0sCiAgICBjYW5zbGltOiAnQyBrcml0ZXJpIOKAlCBlbiBrcml0aWsga3JpdGVyLCBtaW5pbXVtICUyNSBvbG1hbMSxJwogIH0sCiAgJ1Jldkdyb3d0aCc6IHsKICAgIHRpdGxlOiAnR2VsaXIgQsO8ecO8bWVzaSAoWW9ZKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIHNhdMSxxZ8vZ2VsaXJpbmluIGdlw6dlbiB5xLFsYSBnw7ZyZSBhcnTEscWfxLEuIEVQUyBiw7x5w7xtZXNpbmkgZGVzdGVrbGVtZXNpIGdlcmVraXIg4oCUIHNhZGVjZSBtYWxpeWV0IGtlc2ludGlzaXlsZSBiw7x5w7xtZSBzw7xyZMO8csO8bGViaWxpciBkZcSfaWwuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgR2Vyw6dlayB2ZXJpJywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic+JTE1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J0fDvMOnbMO8IGdlbGlyIGLDvHnDvG1lc2knfSwKICAgICAge2xhYmVsOiclNS0xNScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSBiw7x5w7xtZSd9LAogICAgICB7bGFiZWw6Jzw1Jyxjb2xvcjoncmVkJyxkZXNjOidHZWxpciBiw7x5w7xtZXNpIHphecSxZid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQgc8O8cmTDvHLDvGxlYmlsaXIgYsO8ecO8bWUgacOnaW4gxZ9hcnQnCiAgfSwKICAnTmV0TWFyZ2luJzogewogICAgdGl0bGU6ICdOZXQgTWFyamluJywKICAgIGRlc2M6ICdIZXIgMSQgZ2VsaXJkZW4gbmUga2FkYXIgbmV0IGvDonIga2FsZMSxxJ/EsW7EsSBnw7ZzdGVyaXIuIFnDvGtzZWsgbWFyamluID0gZ8O8w6dsw7wgacWfIG1vZGVsaS4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMjAnLGNvbG9yOidncmVlbicsZGVzYzonw4dvayBnw7zDp2zDvCBrw6JybMSxbMSxayd9LAogICAgICB7bGFiZWw6JyUxMC0yMCcsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpIGvDonJsxLFsxLFrJ30sCiAgICAgIHtsYWJlbDonJTUtMTAnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGEga8OicmzEsWzEsWsnfSwKICAgICAge2xhYmVsOic8NScsY29sb3I6J3JlZCcsZGVzYzonWmF5xLFmIGvDonJsxLFsxLFrJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQSBrcml0ZXJpIOKAlCBrw6JybMSxbMSxayBrYWxpdGVzaScKICB9LAogICdST0UnOiB7CiAgICB0aXRsZTogJ1JPRSAow5Z6a2F5bmFrIEvDonJsxLFsxLHEn8SxKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIMO2eiBzZXJtYXllc2l5bGUgbmUga2FkYXIga8OiciBldHRpxJ9pbmkgZ8O2c3RlcmlyLiBZw7xrc2VrIFJPRSA9IHNlcm1heWV5aSB2ZXJpbWxpIGt1bGxhbsSxeW9yLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUyNScsY29sb3I6J2dyZWVuJyxkZXNjOifDh29rIGfDvMOnbMO8IOKAlCBDQU5TTElNIGlkZWFsIHNldml5ZXNpJ30sCiAgICAgIHtsYWJlbDonJTE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWknfSwKICAgICAge2xhYmVsOiclOC0xNScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSd9LAogICAgICB7bGFiZWw6Jzw4Jyxjb2xvcjoncmVkJyxkZXNjOidaYXnEsWYnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIG1pbmltdW0gJTE3IG9sbWFsxLEnCiAgfSwKICAnR3Jvc3NNYXJnaW4nOiB7CiAgICB0aXRsZTogJ0Jyw7x0IE1hcmppbicsCiAgICBkZXNjOiAnU2F0xLHFnyBnZWxpcmluZGVuIMO8cmV0aW0gbWFsaXlldGkgZMO8xZ/DvGxkw7xrdGVuIHNvbnJhIGthbGFuIG9yYW4uIFNla3TDtnJlIGfDtnJlIGRlxJ9pxZ9pci4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lNTAnLGNvbG9yOidncmVlbicsZGVzYzonw4dvayBnw7zDp2zDvCDigJQgeWF6xLFsxLFtL1NhYVMgc2V2aXllc2knfSwKICAgICAge2xhYmVsOiclMzAtNTAnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSd9LAogICAgICB7bGFiZWw6JyUxNS0zMCcsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSDigJQgZG9uYW7EsW0veWFyxLEgaWxldGtlbiBub3JtYWwnfSwKICAgICAge2xhYmVsOic8MTUnLGNvbG9yOidyZWQnLGRlc2M6J0TDvMWfw7xrIG1hcmppbid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0vDonJsxLFsxLFrIGthbGl0ZXNpIGfDtnN0ZXJnZXNpJwogIH0sCiAgLy8gR8SwUsSwxZ4KICAnRW50cnlTY29yZSc6IHsKICAgIHRpdGxlOiAnR2lyacWfIEthbGl0ZXNpIFNrb3J1JywKICAgIGRlc2M6ICdSU0ksIFNNQSBwb3ppc3lvbnUsIFAvRSwgUEVHIHZlIEVQUyBiw7x5w7xtZXNpbmkgYmlybGXFn3RpcmVuIGJpbGXFn2lrIHNrb3IuIDAtMTAwIGFyYXPEsS4nLAogICAgc291cmNlOiAnQml6aW0gaGVzYXBsYW1hJywKICAgIHJlbGlhYmlsaXR5OiAnbG93JywKICAgIHdhcm5pbmc6ICdCVSBVWUdVTEFNQSBUQVJBRklOREFOIEhFU0FQTEFOQU4gS0FCQSBUQUhNxLBORMSwUi4gWWF0xLFyxLFtIGthcmFyxLEgacOnaW4gdGVrIGJhxZ/EsW5hIGt1bGxhbm1hLicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic3NS0xMDAnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgaWRlYWwgZ2lyacWfIGLDtmxnZXNpJ30sCiAgICAgIHtsYWJlbDonNjAtNzUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwgZml5YXQnfSwKICAgICAge2xhYmVsOic0NS02MCcsY29sb3I6J3llbGxvdycsZGVzYzonTsO2dHInfSwKICAgICAge2xhYmVsOiczMC00NScsY29sb3I6J3JlZCcsZGVzYzonUGFoYWzEsSDigJQgYmVrbGUnfSwKICAgICAge2xhYmVsOicwLTMwJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHBhaGFsxLEg4oCUIGdpcm1lJ30KICAgIF0sCiAgICBjYW5zbGltOiAnVMO8bSBrcml0ZXJsZXIgYmlsZcWfaW1pJwogIH0sCiAgJ1JSJzogewogICAgdGl0bGU6ICdSaXNrL8OWZMO8bCBPcmFuxLEgKFIvUiknLAogICAgZGVzYzogJ1BvdGFuc2l5ZWwga2F6YW5jxLFuIHJpc2tlIG9yYW7EsS4gMToyIGRlbWVrIDEkIHJpc2tlIGthcsWfxLEgMiQga2F6YW7DpyBwb3RhbnNpeWVsaSB2YXIgZGVtZWsuJywKICAgIHNvdXJjZTogJ0JpemltIGhlc2FwbGFtYScsCiAgICByZWxpYWJpbGl0eTogJ2xvdycsCiAgICB3YXJuaW5nOiAnR2lyacWfL2hlZGVmL3N0b3Agc2V2aXllbGVyaSBmb3Jtw7xsIGJhemzEsSBrYWJhIHRhaG1pbmRpcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOicxOjMrJyxjb2xvcjonZ3JlZW4nLGRlc2M6J03DvGtlbW1lbCDigJQgZ8O8w6dsw7wgZ2lyacWfIHNpbnlhbGknfSwKICAgICAge2xhYmVsOicxOjInLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSDigJQgbWluaW11bSBrYWJ1bCBlZGlsZWJpbGlyJ30sCiAgICAgIHtsYWJlbDonMToxJyxjb2xvcjoneWVsbG93JyxkZXNjOidaYXnEsWYnfSwKICAgICAge2xhYmVsOic8MToxJyxjb2xvcjoncmVkJyxkZXNjOidSaXNrIGthemFuw6d0YW4gYsO8ecO8ayDigJQgZ2lybWUnfQogICAgXSwKICAgIGNhbnNsaW06ICdSaXNrIHnDtm5ldGltaScKICB9LAogIC8vIEVBUk5JTkdTCiAgJ0Vhcm5pbmdzRGF0ZSc6IHsKICAgIHRpdGxlOiAnUmFwb3IgVGFyaWhpIChFYXJuaW5ncyBEYXRlKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIMOnZXlyZWsgZmluYW5zYWwgc29udcOnbGFyxLFuxLEgYcOnxLFrbGF5YWNhxJ/EsSB0YXJpaC4gUmFwb3Igw7ZuY2VzaSB2ZSBzb25yYXPEsSBmaXlhdCBzZXJ0IGhhcmVrZXQgZWRlYmlsaXIuJywKICAgIHNvdXJjZTogJ3lmaW5hbmNlIOKAlCBiYXplbiBoYXRhbMSxIG9sYWJpbGlyJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdUYXJpaGxlcmkgcmVzbWkgSVIgc2F5ZmFzxLFuZGFuIGRvxJ9ydWxhecSxbicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic3IGfDvG4gacOnaW5kZScsY29sb3I6J3JlZCcsZGVzYzonw4dvayB5YWvEsW4g4oCUIHBvemlzeW9uIGHDp21hayByaXNrbGknfSwKICAgICAge2xhYmVsOic4LTE0IGfDvG4nLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1lha8SxbiDigJQgZGlra2F0bGkgb2wnfSwKICAgICAge2xhYmVsOicxNCsgZ8O8bicsY29sb3I6J2dyZWVuJyxkZXNjOidZZXRlcmxpIHPDvHJlIHZhcid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Mga3JpdGVyaSDigJQgw6dleXJlayByYXBvciBrYWxpdGVzaScKICB9LAogICdBdmdNb3ZlJzogewogICAgdGl0bGU6ICdPcnRhbGFtYSBSYXBvciBIYXJla2V0aScsCiAgICBkZXNjOiAnU29uIDQgw6dleXJlayByYXBvcnVuZGEsIHJhcG9yIGfDvG7DvCB2ZSBlcnRlc2kgZ8O8biBmaXlhdMSxbiBvcnRhbGFtYSBuZSBrYWRhciBoYXJla2V0IGV0dGnEn2kuJywKICAgIHNvdXJjZTogJ0JpemltIGhlc2FwbGFtYScsCiAgICByZWxpYWJpbGl0eTogJ21lZGl1bScsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOidQb3ppdGlmICg+JTUpJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8WeaXJrZXQgZ2VuZWxsaWtsZSBiZWtsZW50aXlpIGHFn8SxeW9yJ30sCiAgICAgIHtsYWJlbDonTsO2dHIgKCUwLTUpJyxjb2xvcjoneWVsbG93JyxkZXNjOidLYXLEscWfxLFrIGdlw6dtacWfJ30sCiAgICAgIHtsYWJlbDonTmVnYXRpZicsY29sb3I6J3JlZCcsZGVzYzonUmFwb3IgZMO2bmVtaW5kZSBmaXlhdCBnZW5lbGxpa2xlIGTDvMWfw7x5b3Ig4oCUIGRpa2thdCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Mga3JpdGVyaSDigJQga2F6YW7DpyBzw7xycHJpemkgZ2XDp21pxZ9pJwogIH0KfTsKCmZ1bmN0aW9uIHNob3dJbmZvKGtleSxldmVudCl7CiAgaWYoZXZlbnQpIGV2ZW50LnN0b3BQcm9wYWdhdGlvbigpOwogIHZhciBtPU1FVFJJQ1Nba2V5XTsgaWYoIW0pIHJldHVybjsKICB2YXIgcmVsTGFiZWw9bS5yZWxpYWJpbGl0eT09PSJoaWdoIj8iR8O8dmVuaWxpciI6bS5yZWxpYWJpbGl0eT09PSJtZWRpdW0iPyJPcnRhIEfDvHZlbmlsaXIiOiJLYWJhIFRhaG1pbiI7CiAgdmFyIGg9JzxkaXYgY2xhc3M9Im1pbmZvLXRpdGxlIj4nK20udGl0bGUrJzwvZGl2Pic7CiAgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLXNvdXJjZSI+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+JyttLnNvdXJjZSsnPC9zcGFuPjxzcGFuIGNsYXNzPSJtaW5mby1yZWwgJyttLnJlbGlhYmlsaXR5KyciPicrcmVsTGFiZWwrJzwvc3Bhbj48L2Rpdj4nOwogIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby1kZXNjIj4nK20uZGVzYysnPC9kaXY+JzsKICBpZihtLndhcm5pbmcpIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby13YXJuaW5nIj7imqDvuI8gJyttLndhcm5pbmcrJzwvZGl2Pic7CiAgaWYobS5yYW5nZXMmJm0ucmFuZ2VzLmxlbmd0aCl7CiAgICBoKz0nPGRpdiBjbGFzcz0ibWluZm8tcmFuZ2VzIj48ZGl2IGNsYXNzPSJtaW5mby1yYW5nZS10aXRsZSI+UmVmZXJhbnMgRGVnZXJsZXI8L2Rpdj4nOwogICAgbS5yYW5nZXMuZm9yRWFjaChmdW5jdGlvbihyKXt2YXIgZGM9ci5jb2xvcj09PSJncmVlbiI/IiMxMGI5ODEiOnIuY29sb3I9PT0icmVkIj8iI2VmNDQ0NCI6IiNmNTllMGIiO2grPSc8ZGl2IGNsYXNzPSJtaW5mby1yYW5nZSI+PGRpdiBjbGFzcz0ibWluZm8tcmFuZ2UtZG90IiBzdHlsZT0iYmFja2dyb3VuZDonK2RjKyciPjwvZGl2PjxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOicrZGMrJyI+JytyLmxhYmVsKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrci5kZXNjKyc8L2Rpdj48L2Rpdj48L2Rpdj4nO30pOwogICAgaCs9JzwvZGl2Pic7CiAgfQogIGlmKG0uY2Fuc2xpbSkgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLWNhbnNsaW0iPvCfk4ogQ0FOU0xJTTogJyttLmNhbnNsaW0rJzwvZGl2Pic7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvQ29udGVudCIpLmlubmVySFRNTD1oOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwp9CmZ1bmN0aW9uIGNsb3NlSW5mb1BvcHVwKGUpe2lmKCFlfHxlLnRhcmdldD09PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikpe2RvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpO319Cgo8L3NjcmlwdD4KPC9zY3JpcHQ+CjxzY3JpcHQ+CnZhciBURl9EQVRBPSUlVEZfREFUQSUlOwp2YXIgUE9SVD0lJVBPUlQlJTsKdmFyIEVBUk5JTkdTX0RBVEE9JSVFQVJOSU5HU19EQVRBJSU7CnZhciBNQVJLRVRfREFUQT0lJU1BUktFVF9EQVRBJSU7CnZhciBORVdTX0RBVEE9JSVORVdTX0RBVEElJTsKdmFyIEFJX0RBVEE9JSVBSV9EQVRBJSU7CnZhciBXRUVLTFlfREFUQT0lJVdFRUtMWV9EQVRBJSU7CnZhciBjdXJUYWI9ImFsbCIsY3VyVGY9IjFkIixjdXJEYXRhPVRGX0RBVEFbIjFkIl0uc2xpY2UoKTsKdmFyIG1pbmlDaGFydHM9e30sbUNoYXJ0PW51bGw7CnZhciBTUz17CiAgIkdVQ0xVIEFMIjp7Ymc6InJnYmEoMTYsMTg1LDEyOSwuMTIpIixiZDoicmdiYSgxNiwxODUsMTI5LC4zNSkiLHR4OiIjMTBiOTgxIixhYzoiIzEwYjk4MSIsbGJsOiJHVUNMVSBBTCJ9LAogICJBTCI6e2JnOiJyZ2JhKDUyLDIxMSwxNTMsLjEpIixiZDoicmdiYSg1MiwyMTEsMTUzLC4zKSIsdHg6IiMzNGQzOTkiLGFjOiIjMzRkMzk5IixsYmw6IkFMIn0sCiAgIkRJS0tBVCI6e2JnOiJyZ2JhKDI0NSwxNTgsMTEsLjEpIixiZDoicmdiYSgyNDUsMTU4LDExLC4zKSIsdHg6IiNmNTllMGIiLGFjOiIjZjU5ZTBiIixsYmw6IkRJS0tBVCJ9LAogICJaQVlJRiI6e2JnOiJyZ2JhKDEwNywxMTQsMTI4LC4xKSIsYmQ6InJnYmEoMTA3LDExNCwxMjgsLjMpIix0eDoiIzljYTNhZiIsYWM6IiM2YjcyODAiLGxibDoiWkFZSUYifSwKICAiU0FUIjp7Ymc6InJnYmEoMjM5LDY4LDY4LC4xMikiLGJkOiJyZ2JhKDIzOSw2OCw2OCwuMzUpIix0eDoiI2VmNDQ0NCIsYWM6IiNlZjQ0NDQiLGxibDoiU0FUIn0KfTsKCmZ1bmN0aW9uIGliKGtleSxsYWJlbCl7CiAgcmV0dXJuIGxhYmVsKycgPHNwYW4gY2xhc3M9Im1pbmZvIiBvbmNsaWNrPSJzaG93SW5mbyhcJycra2V5KydcJyxldmVudCkiPj88L3NwYW4+JzsKfQoKZnVuY3Rpb24gc2V0VGFiKHQsZWwpewogIGN1clRhYj10OwogIGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoIi50YWIiKS5mb3JFYWNoKGZ1bmN0aW9uKGIpe2IuY2xhc3NMaXN0LnJlbW92ZSgiYWN0aXZlIik7fSk7CiAgZWwuY2xhc3NMaXN0LmFkZCgiYWN0aXZlIik7CiAgdmFyIHRmUm93PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0ZlJvdyIpOwogIGlmKHRmUm93KSB0ZlJvdy5zdHlsZS5kaXNwbGF5PSh0PT09ImRhc2hib2FyZCJ8fHQ9PT0iZWFybmluZ3MifHx0PT09InJ1dGluInx8dD09PSJoYWZ0YWxpayIpPyJub25lIjoiZmxleCI7CiAgaWYodD09PSJkYXNoYm9hcmQiKSByZW5kZXJEYXNoYm9hcmQoKTsKICBlbHNlIGlmKHQ9PT0iZWFybmluZ3MiKSByZW5kZXJFYXJuaW5ncygpOwogIGVsc2UgaWYodD09PSJydXRpbiIpIHJlbmRlclJ1dGluKCk7CiAgZWxzZSBpZih0PT09ImhhZnRhbGlrIikgcmVuZGVySGFmdGFsaWsoKTsKICBlbHNlIHJlbmRlckdyaWQoKTsKfQoKZnVuY3Rpb24gc2V0VGYodGYsZWwpewogIGN1clRmPXRmOwogIGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoIi50Zi1idG4iKS5mb3JFYWNoKGZ1bmN0aW9uKGIpe2IuY2xhc3NMaXN0LnRvZ2dsZSgiYWN0aXZlIixiLmRhdGFzZXQudGY9PT10Zik7fSk7CiAgY3VyRGF0YT0oVEZfREFUQVt0Zl18fFRGX0RBVEFbIjFkIl0pLnNsaWNlKCk7CiAgcmVuZGVyU3RhdHMoKTsKICByZW5kZXJHcmlkKCk7Cn0KCmZ1bmN0aW9uIGZpbHRlcmVkKCl7CiAgdmFyIGQ9Y3VyRGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSk7CiAgaWYoY3VyVGFiPT09InBvcnQiKSByZXR1cm4gZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIFBPUlQuaW5jbHVkZXMoci50aWNrZXIpO30pOwogIGlmKGN1clRhYj09PSJidXkiKSByZXR1cm4gZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09IkdVQ0xVIEFMInx8ci5zaW55YWw9PT0iQUwiO30pOwogIGlmKGN1clRhYj09PSJzZWxsIikgcmV0dXJuIGQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSJTQVQiO30pOwogIHJldHVybiBkOwp9CgpmdW5jdGlvbiByZW5kZXJTdGF0cygpewogIHZhciBkPWN1ckRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pOwogIHZhciBjbnQ9e307CiAgZC5mb3JFYWNoKGZ1bmN0aW9uKHIpe2NudFtyLnNpbnlhbF09KGNudFtyLnNpbnlhbF18fDApKzE7fSk7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInN0YXRzIikuaW5uZXJIVE1MPQogICAgJzxkaXYgY2xhc3M9InBpbGwgZyI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5HdWNsdSBBbDogJysoY250WyJHVUNMVSBBTCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIGciPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+QWw6ICcrKGNudFsiQUwiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCB5Ij48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PkRpa2thdDogJysoY250WyJESUtLQVQiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCByIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PlNhdDogJysoY250WyJTQVQiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCBiIiBzdHlsZT0ibWFyZ2luLWxlZnQ6YXV0byI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5Qb3J0Zm9seW86ICcrUE9SVC5sZW5ndGgrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCBtIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PicrZC5sZW5ndGgrJyBhbmFsaXo8L2Rpdj4nOwp9CgpmdW5jdGlvbiByZW5kZXJHcmlkKCl7CiAgT2JqZWN0LnZhbHVlcyhtaW5pQ2hhcnRzKS5mb3JFYWNoKGZ1bmN0aW9uKGMpe2MuZGVzdHJveSgpO30pOwogIG1pbmlDaGFydHM9e307CiAgdmFyIGY9ZmlsdGVyZWQoKTsKICB2YXIgZ3JpZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ3JpZCIpOwogIGlmKCFmLmxlbmd0aCl7Z3JpZC5pbm5lckhUTUw9JzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTE7dGV4dC1hbGlnbjpjZW50ZXI7cGFkZGluZzo0MHB4O2NvbG9yOnZhcigtLW11dGVkKSI+SGlzc2UgYnVsdW5hbWFkaTwvZGl2Pic7cmV0dXJuO30KICBncmlkLmlubmVySFRNTD1mLm1hcChmdW5jdGlvbihyKXtyZXR1cm4gYnVpbGRDYXJkKHIpO30pLmpvaW4oIiIpOwogIGYuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBjdHg9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1jLSIrci50aWNrZXIpOwogICAgaWYoY3R4JiZyLmNoYXJ0X2Nsb3NlcyYmci5jaGFydF9jbG9zZXMubGVuZ3RoKXsKICAgICAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogICAgICBtaW5pQ2hhcnRzWyJtIityLnRpY2tlcl09bmV3IENoYXJ0KGN0eCx7dHlwZToibGluZSIsZGF0YTp7bGFiZWxzOnIuY2hhcnRfZGF0ZXMsZGF0YXNldHM6W3tkYXRhOnIuY2hhcnRfY2xvc2VzLGJvcmRlckNvbG9yOnNzLmFjLGJvcmRlcldpZHRoOjEuNSxmaWxsOnRydWUsYmFja2dyb3VuZENvbG9yOnNzLmFjKyIxOCIscG9pbnRSYWRpdXM6MCx0ZW5zaW9uOjAuNH1dfSxvcHRpb25zOntwbHVnaW5zOntsZWdlbmQ6e2Rpc3BsYXk6ZmFsc2V9fSxzY2FsZXM6e3g6e2Rpc3BsYXk6ZmFsc2V9LHk6e2Rpc3BsYXk6ZmFsc2V9fSxhbmltYXRpb246e2R1cmF0aW9uOjUwMH0scmVzcG9uc2l2ZTp0cnVlLG1haW50YWluQXNwZWN0UmF0aW86ZmFsc2V9fSk7CiAgICB9CiAgfSk7Cn0KCmZ1bmN0aW9uIGJ1aWxkQ2FyZChyKXsKICB2YXIgc3M9U1Nbci5zaW55YWxdfHxTU1siRElLS0FUIl07CiAgdmFyIGRjPXIuZGVnaXNpbT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICB2YXIgZHM9KHIuZGVnaXNpbT49MD8iKyI6IiIpK3IuZGVnaXNpbSsiJSI7CiAgdmFyIGVzY29sPXIuZW50cnlfc2NvcmU+PTc1PyJ2YXIoLS1ncmVlbikiOnIuZW50cnlfc2NvcmU+PTYwPyJ2YXIoLS1ncmVlbjIpIjpyLmVudHJ5X3Njb3JlPj00NT8idmFyKC0teWVsbG93KSI6ci5lbnRyeV9zY29yZT49MzA/InZhcigtLXJlZDIpIjoidmFyKC0tcmVkKSI7CiAgdmFyIHB2Y29sPXIucHJpY2VfdnNfY29sb3I9PT0iZ3JlZW4iPyJ2YXIoLS1ncmVlbikiOnIucHJpY2VfdnNfY29sb3I9PT0ieWVsbG93Ij8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZDIpIjsKICB2YXIgc2lncz1bCiAgICB7bDoiVHJlbmQiLHY6ci50cmVuZD09PSJZdWtzZWxlbiI/Ill1a3NlbGl5b3IiOnIudHJlbmQ9PT0iRHVzZW4iPyJEdXN1eW9yIjoiWWF0YXkiLGc6ci50cmVuZD09PSJZdWtzZWxlbiI/dHJ1ZTpyLnRyZW5kPT09IkR1c2VuIj9mYWxzZTpudWxsfSwKICAgIHtsOiJTTUE1MCIsdjpyLmFib3ZlNTA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIsZzpyLmFib3ZlNTB9LAogICAge2w6IlNNQTIwMCIsdjpyLmFib3ZlMjAwPyJVemVyaW5kZSI6IkFsdGluZGEiLGc6ci5hYm92ZTIwMH0sCiAgICB7bDoiUlNJIix2OnIucnNpfHwiPyIsZzpyLnJzaT9yLnJzaTwzMD90cnVlOnIucnNpPjcwP2ZhbHNlOm51bGw6bnVsbH0sCiAgICB7bDoiNTJXIix2OiIlIityLnBjdF9mcm9tXzUydysiIHV6YWsiLGc6ci5uZWFyXzUyd30KICBdLm1hcChmdW5jdGlvbihzKXtyZXR1cm4gJzxzcGFuIGNsYXNzPSJzcCAnKyhzLmc9PT10cnVlPyJzZyI6cy5nPT09ZmFsc2U/InNiIjoic24iKSsnIj4nK3MubCsiOiAiK3MudisiPC9zcGFuPiI7fSkuam9pbigiIik7CiAgcmV0dXJuICc8ZGl2IGNsYXNzPSJjYXJkIiBzdHlsZT0iYm9yZGVyLWNvbG9yOicrKHIucG9ydGZvbGlvPyJyZ2JhKDE2LDE4NSwxMjksLjI1KSI6c3MuYmQpKyciIG9uY2xpY2s9Im9wZW5NKFwnJytyLnRpY2tlcisnXCcpIj4nCiAgICArJzxkaXYgY2xhc3M9ImFjY2VudCIgc3R5bGU9ImJhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDkwZGVnLCcrc3MuYWMrJywnK3NzLmFjKyc4OCkiPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iY2JvZHkiPjxkaXYgY2xhc3M9ImN0b3AiPjxkaXY+PGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NHB4Ij4nCiAgICArJzxzcGFuIGNsYXNzPSJ0aWNrZXIiIHN0eWxlPSJjb2xvcjonK3NzLnR4KyciPicrci50aWNrZXIrJzwvc3Bhbj4nCiAgICArKHIucG9ydGZvbGlvPyc8c3BhbiBjbGFzcz0icG9ydC1iYWRnZSI+UDwvc3Bhbj4nOicnKSsKICAgICc8L2Rpdj48c3BhbiBjbGFzcz0iYmFkZ2UiIHN0eWxlPSJiYWNrZ3JvdW5kOicrc3MuYmcrJztjb2xvcjonK3NzLnR4Kyc7Ym9yZGVyOjFweCBzb2xpZCAnK3NzLmJkKyciPicrc3MubGJsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJjcHIiPjxkaXYgY2xhc3M9InB2YWwiPiQnK3IuZml5YXQrJzwvZGl2PjxkaXYgY2xhc3M9InBjaGciIHN0eWxlPSJjb2xvcjonK2RjKyciPicrZHMrJzwvZGl2PicKICAgICsoci5wZV9md2Q/JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5Gd2RQRTonK3IucGVfZndkLnRvRml4ZWQoMSkrJzwvZGl2Pic6JycpCiAgICArJzwvZGl2PjwvZGl2PjxkaXYgY2xhc3M9InNpZ3MiPicrc2lncysnPC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJtYXJnaW4tdG9wOjZweCI+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47bWFyZ2luLWJvdHRvbTozcHgiPjxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+R2lyaXMgS2FsaXRlc2k8L3NwYW4+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK2VzY29sKyciPicrci5lbnRyeV9zY29yZSsnLzEwMDwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImhlaWdodDo0cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6MnB4O292ZXJmbG93OmhpZGRlbiI+PGRpdiBzdHlsZT0iaGVpZ2h0OjEwMCU7d2lkdGg6JytyLmVudHJ5X3Njb3JlKyclO2JhY2tncm91bmQ6Jytlc2NvbCsnO2JvcmRlci1yYWRpdXM6MnB4Ij48L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tdG9wOjNweCI+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfbGFiZWwrJzwvc3Bhbj48c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK3B2Y29sKyciPicrci5wcmljZV92c19pZGVhbCsnPC9zcGFuPjwvZGl2PicKICAgICsnPC9kaXY+PGRpdiBjbGFzcz0iY2hhcnQtdyI+PGNhbnZhcyBpZD0ibWMtJytyLnRpY2tlcisnIj48L2NhbnZhcz48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9Imx2bHMiPicKICAgICsnPGRpdiBjbGFzcz0ibHYiPjxkaXYgY2xhc3M9ImxsIj5IZW1lbiBHaXI8L2Rpdj48ZGl2IGNsYXNzPSJsdmFsIiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4yKSI+JCcrci5lbnRyeV9hZ2dyZXNzaXZlKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9Imx2Ij48ZGl2IGNsYXNzPSJsbCI+SGVkZWY8L2Rpdj48ZGl2IGNsYXNzPSJsdmFsIiBzdHlsZT0iY29sb3I6IzYwYTVmYSI+JCcrci5oZWRlZisnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJsdiI+PGRpdiBjbGFzcz0ibGwiPlN0b3A8L2Rpdj48ZGl2IGNsYXNzPSJsdmFsIiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMikiPiQnK3Iuc3RvcCsnPC9kaXY+PC9kaXY+JwogICAgKyc8L2Rpdj48L2Rpdj48L2Rpdj4nOwp9CgpmdW5jdGlvbiByZW5kZXJEYXNoYm9hcmQoKXsKICB2YXIgZ3JpZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ3JpZCIpOwogIHZhciBtZD1NQVJLRVRfREFUQXx8e307CiAgdmFyIHNwPW1kLlNQNTAwfHx7fTsKICB2YXIgbmFzPW1kLk5BU0RBUXx8e307CiAgdmFyIHZpeD1tZC5WSVh8fHt9OwogIHZhciBtU2lnbmFsPW1kLk1fU0lHTkFMfHwiTk9UUiI7CiAgdmFyIG1MYWJlbD1tZC5NX0xBQkVMfHwiVmVyaSB5b2siOwogIHZhciBtQ29sb3I9bVNpZ25hbD09PSJHVUNMVSI/InZhcigtLWdyZWVuKSI6bVNpZ25hbD09PSJaQVlJRiI/InZhcigtLXJlZDIpIjoidmFyKC0teWVsbG93KSI7CiAgdmFyIG1CZz1tU2lnbmFsPT09IkdVQ0xVIj8icmdiYSgxNiwxODUsMTI5LC4wOCkiOm1TaWduYWw9PT0iWkFZSUYiPyJyZ2JhKDIzOSw2OCw2OCwuMDgpIjoicmdiYSgyNDUsMTU4LDExLC4wOCkiOwogIHZhciBtQm9yZGVyPW1TaWduYWw9PT0iR1VDTFUiPyJyZ2JhKDE2LDE4NSwxMjksLjI1KSI6bVNpZ25hbD09PSJaQVlJRiI/InJnYmEoMjM5LDY4LDY4LC4yNSkiOiJyZ2JhKDI0NSwxNTgsMTEsLjI1KSI7CiAgdmFyIG1JY29uPW1TaWduYWw9PT0iR1VDTFUiPyLinIUiOm1TaWduYWw9PT0iWkFZSUYiPyLinYwiOiLimqDvuI8iOwoKICBmdW5jdGlvbiBpbmRleENhcmQobmFtZSxkYXRhKXsKICAgIGlmKCFkYXRhfHwhZGF0YS5wcmljZSkgcmV0dXJuICIiOwogICAgdmFyIGNjPWRhdGEuY2hhbmdlPj0wPyJ2YXIoLS1ncmVlbjIpIjoidmFyKC0tcmVkMikiOwogICAgdmFyIGNzPShkYXRhLmNoYW5nZT49MD8iKyI6IiIpK2RhdGEuY2hhbmdlKyIlIjsKICAgIHZhciBzNTA9ZGF0YS5hYm92ZTUwPyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZToxMHB4Ij5TTUE1MCDinJM8L3NwYW4+JzonPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpO2ZvbnQtc2l6ZToxMHB4Ij5TTUE1MCDinJc8L3NwYW4+JzsKICAgIHZhciBzMjAwPWRhdGEuYWJvdmUyMDA/JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjEwcHgiPlNNQTIwMCDinJM8L3NwYW4+JzonPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpO2ZvbnQtc2l6ZToxMHB4Ij5TTUEyMDAg4pyXPC9zcGFuPic7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCAxNnB4O2ZsZXg6MTttaW4td2lkdGg6MTUwcHgiPicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo2cHgiPicrbmFtZSsnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCkiPiQnK2RhdGEucHJpY2UrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEzcHg7Y29sb3I6JytjYysnO21hcmdpbi1ib3R0b206OHB4Ij4nK2NzKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo4cHgiPicrczUwK3MyMDArJzwvZGl2PjwvZGl2Pic7CiAgfQoKICB2YXIgcG9ydERhdGE9Y3VyRGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGEmJlBPUlQuaW5jbHVkZXMoci50aWNrZXIpO30pOwogIHZhciBwb3J0SHRtbD0iIjsKICBpZihwb3J0RGF0YS5sZW5ndGgpewogICAgcG9ydEh0bWw9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjE0cHgiPicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEycHgiPvCfkrwgUG9ydGbDtnkgw5Z6ZXRpPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMTQwcHgsMWZyKSk7Z2FwOjhweCI+JzsKICAgIHBvcnREYXRhLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICAgIHZhciBkYz1yLmRlZ2lzaW0+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgICAgIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICAgICAgcG9ydEh0bWwrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCAnK3NzLmJkKyc7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4O2N1cnNvcjpwb2ludGVyIiBvbmNsaWNrPSJvcGVuTShcJycrci50aWNrZXIrJ1wnKSI+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjRweCI+JwogICAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OkJlYmFzIE5ldWUsc2Fucy1zZXJpZjtmb250LXNpemU6MTZweDtsZXR0ZXItc3BhY2luZzoycHg7Y29sb3I6Jytzcy50eCsnIj4nK3IudGlja2VyKyc8L3NwYW4+JwogICAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7YmFja2dyb3VuZDonK3NzLmJnKyc7Y29sb3I6Jytzcy50eCsnO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjJweCI+Jytzcy5sYmwrJzwvc3Bhbj48L2Rpdj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwIj4kJytyLmZpeWF0Kyc8L2Rpdj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjExcHg7Y29sb3I6JytkYysnIj4nKyhyLmRlZ2lzaW0+PTA/IisiOiIiKStyLmRlZ2lzaW0rJyU8L2Rpdj48L2Rpdj4nOwogICAgfSk7CiAgICBwb3J0SHRtbCs9JzwvZGl2PjwvZGl2Pic7CiAgfQoKICB2YXIgdXJnZW50RWFybmluZ3M9RUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuIGUuYWxlcnQ9PT0icmVkInx8ZS5hbGVydD09PSJ5ZWxsb3ciO30pOwogIHZhciBlYXJuaW5nc0FsZXJ0PSIiOwogIGlmKHVyZ2VudEVhcm5pbmdzLmxlbmd0aCl7CiAgICBlYXJuaW5nc0FsZXJ0PSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNHB4IDE2cHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0teWVsbG93KTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+4pqg77iPIFlha2xhxZ9hbiBSYXBvcmxhcjwvZGl2Pic7CiAgICB1cmdlbnRFYXJuaW5ncy5mb3JFYWNoKGZ1bmN0aW9uKGUpewogICAgICB2YXIgaWM9ZS5hbGVydD09PSJyZWQiPyLwn5S0Ijoi8J+foSI7CiAgICAgIGVhcm5pbmdzQWxlcnQrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206NnB4O2ZvbnQtc2l6ZToxMnB4Ij4nCiAgICAgICAgKyc8c3Bhbj4nK2ljKycgPHN0cm9uZz4nK2UudGlja2VyKyc8L3N0cm9uZz48L3NwYW4+JwogICAgICAgICsnPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+JytlLm5leHRfZGF0ZSsnICgnKyhlLmRheXNfdG9fZWFybmluZ3M9PT0wPyJCVUfDnE4iOmUuZGF5c190b19lYXJuaW5ncysiIGfDvG4iKSsnKTwvc3Bhbj48L2Rpdj4nOwogICAgfSk7CiAgICBlYXJuaW5nc0FsZXJ0Kz0nPC9kaXY+JzsKICB9CgogIHZhciBuZXdzSHRtbD0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4Ij4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTJweCI+8J+TsCBTb24gSGFiZXJsZXI8L2Rpdj4nOwogIGlmKE5FV1NfREFUQSYmTkVXU19EQVRBLmxlbmd0aCl7CiAgICBORVdTX0RBVEEuc2xpY2UoMCwxMCkuZm9yRWFjaChmdW5jdGlvbihuKXsKICAgICAgdmFyIHBiPW4ucG9ydGZvbGlvPyc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEyKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjI1KTtwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo2MDAiPlA8L3NwYW4+JzoiIjsKICAgICAgdmFyIHRhPSIiOwogICAgICBpZihuLmRhdGV0aW1lKXt2YXIgZGlmZj1NYXRoLmZsb29yKChEYXRlLm5vdygpLzEwMDAtbi5kYXRldGltZSkvMzYwMCk7dGE9ZGlmZjwyND8oZGlmZisicyDDtm5jZSIpOihNYXRoLmZsb29yKGRpZmYvMjQpKyJnIMO2bmNlIik7fQogICAgICBuZXdzSHRtbCs9JzxkaXYgc3R5bGU9InBhZGRpbmc6MTBweCAwO2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA0KSI+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4O21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXllbGxvdykiPicrbi50aWNrZXIrJzwvc3Bhbj4nK3BiCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWxlZnQ6YXV0byI+Jyt0YSsnPC9zcGFuPjwvZGl2PicKICAgICAgICArJzxhIGhyZWY9Iicrbi51cmwrJyIgdGFyZ2V0PSJfYmxhbmsiIHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS10ZXh0KTt0ZXh0LWRlY29yYXRpb246bm9uZTtsaW5lLWhlaWdodDoxLjU7ZGlzcGxheTpibG9jayI+JytuLmhlYWRsaW5lKyc8L2E+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi10b3A6M3B4Ij4nK24uc291cmNlKyc8L2Rpdj48L2Rpdj4nOwogICAgfSk7CiAgfSBlbHNlIHsKICAgIG5ld3NIdG1sKz0nPGRpdiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtc2l6ZToxMnB4Ij5IYWJlciBidWx1bmFtYWRpPC9kaXY+JzsKICB9CiAgbmV3c0h0bWwrPSc8L2Rpdj4nOwoKICBncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JwogICAgKyc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicrbUJnKyc7Ym9yZGVyOjFweCBzb2xpZCAnK21Cb3JkZXIrJztib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47ZmxleC13cmFwOndyYXA7Z2FwOjEycHgiPicKICAgICsnPGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4O21hcmdpbi1ib3R0b206NHB4Ij5DQU5TTElNIE0gS1LEsFRFUsSwPC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyttQ29sb3IrJyI+JyttSWNvbisnICcrbUxhYmVsKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTt0ZXh0LWFsaWduOnJpZ2h0Ij5WSVg6ICcrKHZpeC5wcmljZXx8Ij8iKSsnPGJyPicKICAgICsnPHNwYW4gc3R5bGU9ImNvbG9yOicrKHZpeC5wcmljZSYmdml4LnByaWNlPjI1PyJ2YXIoLS1yZWQyKSI6InZhcigtLWdyZWVuKSIpKyciPicrKHZpeC5wcmljZSYmdml4LnByaWNlPjI1PyJZw7xrc2VrIHZvbGF0aWxpdGUiOiJOb3JtYWwgdm9sYXRpbGl0ZSIpKyc8L3NwYW4+PC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXA7bWFyZ2luLWJvdHRvbToxNHB4Ij4nK2luZGV4Q2FyZCgiUyZQIDUwMCAoU1BZKSIsc3ApK2luZGV4Q2FyZCgiTkFTREFRIChRUVEpIixuYXMpKyc8L2Rpdj4nCiAgICArcG9ydEh0bWwrZWFybmluZ3NBbGVydCtuZXdzSHRtbCsnPC9kaXY+JzsKfQoKZnVuY3Rpb24gcmVuZGVyRWFybmluZ3MoKXsKICB2YXIgZ3JpZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ3JpZCIpOwogIHZhciBzb3J0ZWQ9RUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuIGUubmV4dF9kYXRlO30pLnNvcnQoZnVuY3Rpb24oYSxiKXsKICAgIHZhciBkYT1hLmRheXNfdG9fZWFybmluZ3MhPW51bGw/YS5kYXlzX3RvX2Vhcm5pbmdzOjk5OTsKICAgIHZhciBkYj1iLmRheXNfdG9fZWFybmluZ3MhPW51bGw/Yi5kYXlzX3RvX2Vhcm5pbmdzOjk5OTsKICAgIHJldHVybiBkYS1kYjsKICB9KTsKICB2YXIgbm9EYXRlPUVBUk5JTkdTX0RBVEEuZmlsdGVyKGZ1bmN0aW9uKGUpe3JldHVybiAhZS5uZXh0X2RhdGU7fSk7CiAgaWYoIXNvcnRlZC5sZW5ndGgmJiFub0RhdGUubGVuZ3RoKXtncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMTt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjQwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5FYXJuaW5ncyB2ZXJpc2kgYnVsdW5hbWFkaTwvZGl2Pic7cmV0dXJuO30KICB2YXIgaD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKICBzb3J0ZWQuZm9yRWFjaChmdW5jdGlvbihlKXsKICAgIHZhciBhYj1lLmFsZXJ0PT09InJlZCI/InJnYmEoMjM5LDY4LDY4LC4xMikiOmUuYWxlcnQ9PT0ieWVsbG93Ij8icmdiYSgyNDUsMTU4LDExLC4xKSI6InJnYmEoMjU1LDI1NSwyNTUsLjAyKSI7CiAgICB2YXIgYWJkPWUuYWxlcnQ9PT0icmVkIj8icmdiYSgyMzksNjgsNjgsLjM1KSI6ZS5hbGVydD09PSJ5ZWxsb3ciPyJyZ2JhKDI0NSwxNTgsMTEsLjMpIjoicmdiYSgyNTUsMjU1LDI1NSwuMDcpIjsKICAgIHZhciBhaT1lLmFsZXJ0PT09InJlZCI/IvCflLQiOmUuYWxlcnQ9PT0ieWVsbG93Ij8i8J+foSI6IvCfk4UiOwogICAgdmFyIGR0PWUuZGF5c190b19lYXJuaW5ncyE9bnVsbD8oZS5kYXlzX3RvX2Vhcm5pbmdzPT09MD8iQlVHVU4iOmUuZGF5c190b19lYXJuaW5ncz09PTE/IllhcmluIjplLmRheXNfdG9fZWFybmluZ3MrIiBndW4gc29ucmEiKToiIjsKICAgIHZhciBhbUNvbD1lLmF2Z19tb3ZlX3BjdCE9bnVsbD8oZS5hdmdfbW92ZV9wY3Q+PTA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZDIpIik6InZhcigtLW11dGVkKSI7CiAgICB2YXIgYW1TdHI9ZS5hdmdfbW92ZV9wY3QhPW51bGw/KGUuYXZnX21vdmVfcGN0Pj0wPyIrIjoiIikrZS5hdmdfbW92ZV9wY3QrIiUiOiLigJQiOwogICAgdmFyIHliPWUuYWxlcnQ9PT0icmVkIj8nPHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtjb2xvcjp2YXIoLS1yZWQyKTtwYWRkaW5nOjJweCA4cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjEwcHg7Zm9udC13ZWlnaHQ6NzAwIj5ZQUtJTkRBPC9zcGFuPic6IiI7CiAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonK2FiKyc7Ym9yZGVyOjFweCBzb2xpZCAnK2FiZCsnO2JvcmRlci1yYWRpdXM6MTBweDttYXJnaW4tYm90dG9tOjEwcHg7cGFkZGluZzoxNHB4IDE2cHgiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6OHB4Ij4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjEwcHgiPjxzcGFuPicrYWkrJzwvc3Bhbj48c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyMHB4O2xldHRlci1zcGFjaW5nOjJweDtjb2xvcjp2YXIoLS10ZXh0KSI+JytlLnRpY2tlcisnPC9zcGFuPicreWIrJzwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxNnB4O2ZsZXgtd3JhcDp3cmFwO2FsaWduLWl0ZW1zOmNlbnRlciI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlJBUE9SPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjp2YXIoLS10ZXh0KSI+JysoZS5uZXh0X2RhdGV8fCLigJQiKSsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6JysoZS5hbGVydD09PSJyZWQiPyJ2YXIoLS1yZWQyKSI6ZS5hbGVydD09PSJ5ZWxsb3ciPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tbXV0ZWQpIikrJyI+JytkdCsnPC9kaXY+PC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkVQUyBUQUhNSU48L2Rpdj48ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOiM2MGE1ZmEiPicrKGUuZXBzX2VzdGltYXRlIT1udWxsPyIkIitlLmVwc19lc3RpbWF0ZToi4oCUIikrJzwvZGl2PjwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5PUlQuSEFSRUtFVDwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JythbUNvbCsnIj4nK2FtU3RyKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKSI+c29uIDQgcmFwb3I8L2Rpdj48L2Rpdj4nOwogICAgaCs9JzwvZGl2PjwvZGl2Pic7CiAgICBpZihlLmhpc3RvcnlfZXBzJiZlLmhpc3RvcnlfZXBzLmxlbmd0aCl7CiAgICAgIGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW4tdG9wOjhweDtwYWRkaW5nLXRvcDo4cHg7Ym9yZGVyLXRvcDoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjVweCI+U09OIDQgUkFQT1I8L2Rpdj48ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCg0LDFmcik7Z2FwOjRweCI+JzsKICAgICAgZS5oaXN0b3J5X2Vwcy5mb3JFYWNoKGZ1bmN0aW9uKGhoKXsKICAgICAgICB2YXIgc2M9aGguc3VycHJpc2VfcGN0IT1udWxsPyhoaC5zdXJwcmlzZV9wY3Q+MD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkMikiKToidmFyKC0tbXV0ZWQpIjsKICAgICAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6NHB4O3BhZGRpbmc6NnB4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDUpIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytoaC5kYXRlLnN1YnN0cmluZygwLDcpKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEwcHgiPicrKGhoLmFjdHVhbCE9bnVsbD8iJCIraGguYWN0dWFsOiI/IikrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6JytzYysnIj4nKyhoaC5zdXJwcmlzZV9wY3QhPW51bGw/KGhoLnN1cnByaXNlX3BjdD4wPyIrIjoiIikraGguc3VycHJpc2VfcGN0KyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nOwogICAgICB9KTsKICAgICAgaCs9JzwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBoKz0nPC9kaXY+JzsKICB9KTsKICBpZihub0RhdGUubGVuZ3RoKXtoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi10b3A6NnB4Ij5UYXJpaCBidWx1bmFtYXlhbjogJytub0RhdGUubWFwKGZ1bmN0aW9uKGUpe3JldHVybiBlLnRpY2tlcjt9KS5qb2luKCIsICIpKyc8L2Rpdj4nO30KICBoKz0nPC9kaXY+JzsKICBncmlkLmlubmVySFRNTD1oOwp9CgpmdW5jdGlvbiBvcGVuTSh0aWNrZXIpewogIHZhciByPWN1ckRhdGEuZmluZChmdW5jdGlvbihkKXtyZXR1cm4gZC50aWNrZXI9PT10aWNrZXI7fSk7CiAgaWYoIXJ8fHIuaGF0YSkgcmV0dXJuOwogIGlmKG1DaGFydCl7bUNoYXJ0LmRlc3Ryb3koKTttQ2hhcnQ9bnVsbDt9CiAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogIHZhciByclA9TWF0aC5taW4oKHIucnIvNCkqMTAwLDEwMCk7CiAgdmFyIHJyQz1yLnJyPj0zPyJ2YXIoLS1ncmVlbikiOnIucnI+PTI/InZhcigtLWdyZWVuMikiOnIucnI+PTE/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIGRjPXIuZGVnaXNpbT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICB2YXIga2M9eyJHVUNMVSBBTCI6IiMxMGI5ODEiLCJBTCI6IiMzNGQzOTkiLCJESUtLQVRMSSI6IiNmNTllMGIiLCJHRUNNRSI6IiNmODcxNzEifTsKICB2YXIga2xibD17IkdVQ0xVIEFMIjoiR1VDTFUgQUwiLCJBTCI6IkFMIiwiRElLS0FUTEkiOiJESUtLQVRMSSIsIkdFQ01FIjoiR0VDTUUifTsKICB2YXIgZXNjb2w9ci5lbnRyeV9zY29yZT49NzU/InZhcigtLWdyZWVuKSI6ci5lbnRyeV9zY29yZT49NjA/InZhcigtLWdyZWVuMikiOnIuZW50cnlfc2NvcmU+PTQ1PyJ2YXIoLS15ZWxsb3cpIjpyLmVudHJ5X3Njb3JlPj0zMD8idmFyKC0tcmVkMikiOiJ2YXIoLS1yZWQpIjsKICB2YXIgcHZjb2w9ci5wcmljZV92c19jb2xvcj09PSJncmVlbiI/InZhcigtLWdyZWVuKSI6ci5wcmljZV92c19jb2xvcj09PSJ5ZWxsb3ciPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkMikiOwoKICB2YXIgbWg9JzxkaXYgY2xhc3M9Im1oZWFkIj48ZGl2PjxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjhweDtmbGV4LXdyYXA6d3JhcCI+JwogICAgKyc8c3BhbiBjbGFzcz0ibXRpdGxlIiBzdHlsZT0iY29sb3I6Jytzcy50eCsnIj4nK3IudGlja2VyKyc8L3NwYW4+JwogICAgKyc8c3BhbiBjbGFzcz0iYmFkZ2UiIHN0eWxlPSJiYWNrZ3JvdW5kOicrc3MuYmcrJztjb2xvcjonK3NzLnR4Kyc7Ym9yZGVyOjFweCBzb2xpZCAnK3NzLmJkKyc7Zm9udC1zaXplOjEycHgiPicrc3MubGJsKyc8L3NwYW4+JwogICAgKyhyLnBvcnRmb2xpbz8nPHNwYW4gY2xhc3M9InBvcnQtYmFkZ2UiIHN0eWxlPSJmb250LXNpemU6MTFweDtwYWRkaW5nOjNweCA4cHgiPlBvcnRmb2x5bzwvc3Bhbj4nOicnKQogICAgKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC13ZWlnaHQ6NjAwO21hcmdpbi10b3A6NHB4Ij4kJytyLmZpeWF0CiAgICArJyA8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6JytkYysnIj4nKyhyLmRlZ2lzaW0+PTA/IisiOiIiKStyLmRlZ2lzaW0rJyU8L3NwYW4+PC9kaXY+PC9kaXY+JwogICAgKyc8YnV0dG9uIGNsYXNzPSJtY2xvc2UiIG9uY2xpY2s9ImNsb3NlTSgpIj7inJU8L2J1dHRvbj48L2Rpdj4nOwoKICBtaCs9JzxkaXYgY2xhc3M9Im1ib2R5Ij48ZGl2IGNsYXNzPSJtY2hhcnR3Ij48Y2FudmFzIGlkPSJtY2hhcnQiPjwvY2FudmFzPjwvZGl2Pic7CgogIG1oKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O21hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij4nK2liKCJFbnRyeVNjb3JlIiwiR2lyaXMgS2FsaXRlc2kiKSsnPC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206NnB4Ij4nCiAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X3Njb3JlKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4vMTAwPC9zcGFuPjwvc3Bhbj4nCiAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfbGFiZWwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImhlaWdodDo2cHg7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlci1yYWRpdXM6M3B4O292ZXJmbG93OmhpZGRlbjttYXJnaW4tYm90dG9tOjhweCI+PGRpdiBzdHlsZT0iaGVpZ2h0OjEwMCU7d2lkdGg6JytyLmVudHJ5X3Njb3JlKyclO2JhY2tncm91bmQ6Jytlc2NvbCsnO2JvcmRlci1yYWRpdXM6M3B4Ij48L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2Vlbjtmb250LXNpemU6MTFweCI+JwogICAgKyc8ZGl2PjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPlN1IGFua2kgZml5YXQ6IDwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6JytwdmNvbCsnO2ZvbnQtd2VpZ2h0OjYwMCI+JytyLnByaWNlX3ZzX2lkZWFsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2PjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPklkZWFsIGJvbGdlOiA8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuMik7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmlkZWFsX2VudHJ5X2xvdysnIC0gJCcrci5pZGVhbF9lbnRyeV9oaWdoKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8L2Rpdj48L2Rpdj4nOwoKICBtaCs9JzxkaXYgY2xhc3M9ImRib3giIHN0eWxlPSJiYWNrZ3JvdW5kOicrc3MuYmcrJztib3JkZXItY29sb3I6Jytzcy5iZCsnO21hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IGNsYXNzPSJkbGJsIiBzdHlsZT0iY29sb3I6Jytzcy50eCsnIj4nK2liKCJSUiIsIkFsaW0gS2FyYXJpIFIvUiIpKyc8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImR2ZXJkIiBzdHlsZT0iY29sb3I6Jysoa2Nbci5rYXJhcl18fCJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhrbGJsW3Iua2FyYXJdfHxyLmthcmFyKSsnPC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+UmlzayAvIE9kdWw8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOicrcnJDKyc7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+MSA6ICcrci5ycisnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkhlbWVuIEdpcjwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4yKTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuZW50cnlfYWdncmVzc2l2ZSsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkdlcmkgQ2VraWxtZTwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6IzYwYTVmYTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuZW50cnlfbWlkKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+QnV5dWsgRHV6ZWx0bWU8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXllbGxvdyk7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmVudHJ5X2NvbnNlcnZhdGl2ZSsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkhlZGVmPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjojNjBhNWZhO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5oZWRlZisnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPlN0b3AtTG9zczwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMik7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLnN0b3ArJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9InJyYmFyIj48ZGl2IGNsYXNzPSJycmZpbGwiIHN0eWxlPSJ3aWR0aDonK3JyUCsnJTtiYWNrZ3JvdW5kOicrcnJDKyciPjwvZGl2PjwvZGl2PjwvZGl2Pic7CgogIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+VGVrbmlrIEFuYWxpejwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGdyaWQiIHN0eWxlPSJtYXJnaW4tYm90dG9tOjEycHgiPicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJUcmVuZCIsIlRyZW5kIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci50cmVuZD09PSJZdWtzZWxlbiI/InZhcigtLWdyZWVuKSI6ci50cmVuZD09PSJEdXNlbiI/InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nK3IudHJlbmQrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJSU0kiLCJSU0kgMTQiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnJzaT9yLnJzaTwzMD8idmFyKC0tZ3JlZW4pIjpyLnJzaT43MD8idmFyKC0tcmVkKSI6InZhcigtLXllbGxvdykiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnJzaXx8Ij8iKSsoci5yc2k/ci5yc2k8MzA/IiBBc2lyaSBTYXRpbSI6ci5yc2k+NzA/IiBBc2lyaSBBbGltIjoiIE5vdHIiOiIiKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlNNQTUwIiwiU01BIDUwIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5hYm92ZTUwPyJ2YXIoLS1ncmVlbikiOiJ2YXIoLS1yZWQpIikrJyI+Jysoci5hYm92ZTUwPyJVemVyaW5kZSI6IkFsdGluZGEiKSsoci5zbWE1MF9kaXN0IT1udWxsPyIgKCIrci5zbWE1MF9kaXN0KyIlKSI6IiIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiU01BMjAwIiwiU01BIDIwMCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuYWJvdmUyMDA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZCkiKSsnIj4nKyhyLmFib3ZlMjAwPyJVemVyaW5kZSI6IkFsdGluZGEiKSsoci5zbWEyMDBfZGlzdCE9bnVsbD8iICgiK3Iuc21hMjAwX2Rpc3QrIiUpIjoiIikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCI1MlciLCI1MkggUG96LiIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIudzUyX3Bvc2l0aW9uPD0zMD8idmFyKC0tZ3JlZW4pIjpyLnc1Ml9wb3NpdGlvbj49ODU/InZhcigtLXJlZCkiOiJ2YXIoLS15ZWxsb3cpIikrJyI+JytyLnc1Ml9wb3NpdGlvbisnJTwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJIYWNpbSIsIkhhY2ltIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5oYWNpbT09PSJZdWtzZWsiPyJ2YXIoLS1ncmVlbikiOnIuaGFjaW09PT0iRHVzdWsiPyJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+JytyLmhhY2ltKycgKCcrci52b2xfcmF0aW8rJ3gpPC9kaXY+PC9kaXY+JwogICAgKyc8L2Rpdj4nOwoKICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPlRlbWVsIEFuYWxpejwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGdyaWQiIHN0eWxlPSJtYXJnaW4tYm90dG9tOjEycHgiPicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJGb3J3YXJkUEUiLCJGb3J3YXJkIFBFIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5wZV9md2Q/ci5wZV9md2Q8MjU/InZhcigtLWdyZWVuKSI6ci5wZV9md2Q8NDA/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5wZV9md2Q/ci5wZV9md2QudG9GaXhlZCgxKToiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUEVHIiwiUEVHIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5wZWc/ci5wZWc8MT8idmFyKC0tZ3JlZW4pIjpyLnBlZzwyPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucGVnP3IucGVnLnRvRml4ZWQoMik6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIkVQU0dyb3d0aCIsIkVQUyBCw7x5w7xtZSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuZXBzX2dyb3d0aD9yLmVwc19ncm93dGg+PTIwPyJ2YXIoLS1ncmVlbikiOnIuZXBzX2dyb3d0aD49MD8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLmVwc19ncm93dGghPW51bGw/ci5lcHNfZ3Jvd3RoKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUmV2R3Jvd3RoIiwiR2VsaXIgQsO8ecO8bWUiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnJldl9ncm93dGg/ci5yZXZfZ3Jvd3RoPj0xNT8idmFyKC0tZ3JlZW4pIjpyLnJldl9ncm93dGg+PTA/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5yZXZfZ3Jvd3RoIT1udWxsP3IucmV2X2dyb3d0aCsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIk5ldE1hcmdpbiIsIk5ldCBNYXJqaW4iKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLm5ldF9tYXJnaW4/ci5uZXRfbWFyZ2luPj0xNT8idmFyKC0tZ3JlZW4pIjpyLm5ldF9tYXJnaW4+PTU/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5uZXRfbWFyZ2luIT1udWxsP3IubmV0X21hcmdpbisiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlJPRSIsIlJPRSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucm9lP3Iucm9lPj0xNT8idmFyKC0tZ3JlZW4pIjpyLnJvZT49NT8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnJvZSE9bnVsbD9yLnJvZSsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8L2Rpdj4nOwoKICB2YXIgYWlUZXh0ID0gQUlfREFUQSAmJiBBSV9EQVRBW3RpY2tlcl07CiAgaWYoYWlUZXh0KXsKICAgIG1oKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDttYXJnaW4tYm90dG9tOjEycHgiPic7CiAgICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6IzYwYTVmYTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij7wn6SWIEFJIEFuYWxpeiAoQ2xhdWRlIFNvbm5ldCk8L2Rpdj4nOwogICAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS10ZXh0KTtsaW5lLWhlaWdodDoxLjc7d2hpdGUtc3BhY2U6cHJlLXdyYXAiPicrYWlUZXh0Kyc8L2Rpdj4nOwogICAgbWgrPSc8L2Rpdj4nOwogIH0KICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTt0ZXh0LWFsaWduOmNlbnRlciI+QnUgYXJhYyB5YXRpcmltIHRhdnNpeWVzaSBkZWdpbGRpcjwvZGl2PjwvZGl2Pic7CgogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtb2RhbCIpLmlubmVySFRNTD1taDsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgib3ZlcmxheSIpLmNsYXNzTGlzdC5hZGQoIm9wZW4iKTsKICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7CiAgICB2YXIgY3R4PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtY2hhcnQiKTsKICAgIGlmKGN0eCYmci5jaGFydF9jbG9zZXMpewogICAgICBtQ2hhcnQ9bmV3IENoYXJ0KGN0eCx7dHlwZToibGluZSIsZGF0YTp7bGFiZWxzOnIuY2hhcnRfZGF0ZXMsZGF0YXNldHM6WwogICAgICAgIHtsYWJlbDoiRml5YXQiLGRhdGE6ci5jaGFydF9jbG9zZXMsYm9yZGVyQ29sb3I6c3MuYWMsYm9yZGVyV2lkdGg6MixmaWxsOnRydWUsYmFja2dyb3VuZENvbG9yOnNzLmFjKyIyMCIscG9pbnRSYWRpdXM6MCx0ZW5zaW9uOjAuM30sCiAgICAgICAgci5zbWE1MD97bGFiZWw6IlNNQTUwIixkYXRhOkFycmF5KHIuY2hhcnRfY2xvc2VzLmxlbmd0aCkuZmlsbChyLnNtYTUwKSxib3JkZXJDb2xvcjoiI2Y1OWUwYiIsYm9yZGVyV2lkdGg6MS41LGJvcmRlckRhc2g6WzUsNV0scG9pbnRSYWRpdXM6MCxmaWxsOmZhbHNlfTpudWxsLAogICAgICAgIHIuc21hMjAwP3tsYWJlbDoiU01BMjAwIixkYXRhOkFycmF5KHIuY2hhcnRfY2xvc2VzLmxlbmd0aCkuZmlsbChyLnNtYTIwMCksYm9yZGVyQ29sb3I6IiM4YjVjZjYiLGJvcmRlcldpZHRoOjEuNSxib3JkZXJEYXNoOls1LDVdLHBvaW50UmFkaXVzOjAsZmlsbDpmYWxzZX06bnVsbAogICAgICBdLmZpbHRlcihCb29sZWFuKX0sb3B0aW9uczp7cmVzcG9uc2l2ZTp0cnVlLG1haW50YWluQXNwZWN0UmF0aW86ZmFsc2UsCiAgICAgICAgcGx1Z2luczp7bGVnZW5kOntsYWJlbHM6e2NvbG9yOiIjNmI3MjgwIixmb250OntzaXplOjEwfX19fSwKICAgICAgICBzY2FsZXM6e3g6e2Rpc3BsYXk6dHJ1ZSx0aWNrczp7Y29sb3I6IiMzNzQxNTEiLG1heFRpY2tzTGltaXQ6NSxmb250OntzaXplOjl9fSxncmlkOntjb2xvcjoicmdiYSgyNTUsMjU1LDI1NSwuMDQpIn19LAogICAgICAgICAgeTp7ZGlzcGxheTp0cnVlLHRpY2tzOntjb2xvcjoiIzM3NDE1MSIsZm9udDp7c2l6ZTo5fX0sZ3JpZDp7Y29sb3I6InJnYmEoMjU1LDI1NSwyNTUsLjA0KSJ9fX19fSk7CiAgICB9CiAgfSwxMDApOwp9CgoKLy8g4pSA4pSAIEfDnE5Mw5xLIFJVVMSwTiDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAKdmFyIFJVVElOX0lURU1TID0gewogIHNhYmFoOiB7CiAgICBsYWJlbDogIvCfjIUgU2FiYWgg4oCUIFBpeWFzYSBBw6fEsWxtYWRhbiDDlm5jZSIsCiAgICBpdGVtczogWwogICAgICB7aWQ6InMxIiwgdGV4dDoiRGFzaGJvYXJkJ8SxIGHDpyDigJQgTSBrcml0ZXJpIHllxZ9pbCBtaT8gKFMmUDUwMCArIE5BU0RBUSBTTUEyMDAgw7xzdMO8bmRlKSJ9LAogICAgICB7aWQ6InMyIiwgdGV4dDoiRWFybmluZ3Mgc2VrbWVzaW5pIGtvbnRyb2wgZXQg4oCUIGJ1Z8O8bi9idSBoYWZ0YSByYXBvciB2YXIgbcSxPyJ9LAogICAgICB7aWQ6InMzIiwgdGV4dDoiVklYIDI1IGFsdMSxbmRhIG3EsT8gKFnDvGtzZWtzZSB5ZW5pIHBvemlzeW9uIGHDp21hKSJ9LAogICAgICB7aWQ6InM0IiwgdGV4dDoiw5ZuY2VraSBnw7xuZGVuIGJla2xleWVuIGFsYXJtIG1haWxpIHZhciBtxLE/In0KICAgIF0KICB9LAogIG9nbGVuOiB7CiAgICBsYWJlbDogIvCfk4ogw5bEn2xlZGVuIFNvbnJhIOKAlCBQaXlhc2EgQcOnxLFra2VuIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoibzEiLCB0ZXh0OiJQb3J0ZsO2ecO8bSBzZWttZXNpbmRlIGhpc3NlbGVyaW1lIGJhayDigJQgYmVrbGVubWVkaWsgZMO8xZ/DvMWfIHZhciBtxLE/In0sCiAgICAgIHtpZDoibzIiLCB0ZXh0OiJTdG9wIHNldml5ZXNpbmUgeWFrbGHFn2FuIGhpc3NlIHZhciBtxLE/IChLxLFybcSxesSxIGnFn2FyZXQpIn0sCiAgICAgIHtpZDoibzMiLCB0ZXh0OiJBbCBzaW55YWxpIHNla21lc2luZGUgeWVuaSBmxLFyc2F0IMOnxLFrbcSxxZ8gbcSxPyJ9LAogICAgICB7aWQ6Im80IiwgdGV4dDoiV2F0Y2hsaXN0J3Rla2kgaGlzc2VsZXJkZSBnaXJpxZ8ga2FsaXRlc2kgNjArIG9sYW4gdmFyIG3EsT8ifSwKICAgICAge2lkOiJvNSIsIHRleHQ6IkhhYmVybGVyZGUgcG9ydGbDtnnDvG3DvCBldGtpbGV5ZW4gw7ZuZW1saSBnZWxpxZ9tZSB2YXIgbcSxPyJ9CiAgICBdCiAgfSwKICBha3NhbTogewogICAgbGFiZWw6ICLwn4yZIEFrxZ9hbSDigJQgUGl5YXNhIEthcGFuZMSxa3RhbiBTb25yYSIsCiAgICBpdGVtczogWwogICAgICB7aWQ6ImExIiwgdGV4dDoiMUggc2lueWFsbGVyaW5pIGtvbnRyb2wgZXQg4oCUIGhhZnRhbMSxayB0cmVuZCBkZcSfacWfbWnFnyBtaT8ifSwKICAgICAge2lkOiJhMiIsIHRleHQ6IllhcsSxbiBpw6dpbiBwb3RhbnNpeWVsIGdpcmnFnyBub2t0YWxhcsSxbsSxIG5vdCBhbCJ9LAogICAgICB7aWQ6ImEzIiwgdGV4dDoiUG9ydGbDtnlkZWtpIGhlciBoaXNzZW5pbiBzdG9wIHNldml5ZXNpbmkgZ8O2emRlbiBnZcOnaXIifSwKICAgICAge2lkOiJhNCIsIHRleHQ6IllhcsSxbiByYXBvciBhw6fEsWtsYXlhY2FrIGhpc3NlIHZhciBtxLE/IChFYXJuaW5ncyBzZWttZXNpKSJ9CiAgICBdCiAgfSwKICBoYWZ0YWxpazogewogICAgbGFiZWw6ICLwn5OFIEhhZnRhbMSxayDigJQgUGF6YXIgQWvFn2FtxLEiLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJoMSIsIHRleHQ6IlN0b2NrIFJvdmVyJ2RhIENBTlNMSU0gc2NyZWVuZXInxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDIiLCB0ZXh0OiJWQ1AgTWluZXJ2aW5pIHNjcmVlbmVyJ8SxIMOnYWzEscWfdMSxciJ9LAogICAgICB7aWQ6ImgzIiwgdGV4dDoiUXVsbGFtYWdnaWUgQnJlYWtvdXQgc2NyZWVuZXInxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDQiLCB0ZXh0OiJGaW52aXonZGUgSW5zdGl0dXRpb25hbCBCdXlpbmcgc2NyZWVuZXInxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDUiLCB0ZXh0OiLDh2FrxLHFn2FuIGhpc3NlbGVyaSBidWwg4oCUIGVuIGfDvMOnbMO8IGFkYXlsYXIifSwKICAgICAge2lkOiJoNiIsIHRleHQ6IkdpdEh1YiBBY3Rpb25zJ2RhbiBSdW4gV29ya2Zsb3cgYmFzIOKAlCBzaXRlIGfDvG5jZWxsZW5pciJ9LAogICAgICB7aWQ6Img3IiwgdGV4dDoiR2VsZWNlayBoYWZ0YW7EsW4gZWFybmluZ3MgdGFrdmltaW5pIGtvbnRyb2wgZXQifSwKICAgICAge2lkOiJoOCIsIHRleHQ6IlBvcnRmw7Z5IGdlbmVsIGRlxJ9lcmxlbmRpcm1lc2kg4oCUIGhlZGVmbGVyIGhhbGEgZ2XDp2VybGkgbWk/In0KICAgIF0KICB9Cn07CgpmdW5jdGlvbiBnZXRUb2RheUtleSgpewogIHJldHVybiBuZXcgRGF0ZSgpLnRvRGF0ZVN0cmluZygpOwp9CgpmdW5jdGlvbiBsb2FkQ2hlY2tlZCgpewogIHRyeXsKICAgIHZhciBkYXRhID0gbG9jYWxTdG9yYWdlLmdldEl0ZW0oJ3J1dGluX2NoZWNrZWQnKTsKICAgIGlmKCFkYXRhKSByZXR1cm4ge307CiAgICB2YXIgcGFyc2VkID0gSlNPTi5wYXJzZShkYXRhKTsKICAgIC8vIFNhZGVjZSBidWfDvG7DvG4gdmVyaWxlcmluaSBrdWxsYW4KICAgIGlmKHBhcnNlZC5kYXRlICE9PSBnZXRUb2RheUtleSgpKSByZXR1cm4ge307CiAgICByZXR1cm4gcGFyc2VkLml0ZW1zIHx8IHt9OwogIH1jYXRjaChlKXtyZXR1cm4ge307fQp9CgpmdW5jdGlvbiBzYXZlQ2hlY2tlZChjaGVja2VkKXsKICBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgncnV0aW5fY2hlY2tlZCcsIEpTT04uc3RyaW5naWZ5KHsKICAgIGRhdGU6IGdldFRvZGF5S2V5KCksCiAgICBpdGVtczogY2hlY2tlZAogIH0pKTsKfQoKZnVuY3Rpb24gdG9nZ2xlQ2hlY2soaWQpewogIHZhciBjaGVja2VkID0gbG9hZENoZWNrZWQoKTsKICBpZihjaGVja2VkW2lkXSkgZGVsZXRlIGNoZWNrZWRbaWRdOwogIGVsc2UgY2hlY2tlZFtpZF0gPSB0cnVlOwogIHNhdmVDaGVja2VkKGNoZWNrZWQpOwogIHJlbmRlclJ1dGluKCk7Cn0KCmZ1bmN0aW9uIHJlc2V0UnV0aW4oKXsKICBsb2NhbFN0b3JhZ2UucmVtb3ZlSXRlbSgncnV0aW5fY2hlY2tlZCcpOwogIHJlbmRlclJ1dGluKCk7Cn0KCgpmdW5jdGlvbiByZW5kZXJIYWZ0YWxpaygpewogIHZhciBncmlkID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dyaWQnKTsKICB2YXIgd2QgPSBXRUVLTFlfREFUQSB8fCB7fTsKICB2YXIgcG9ydCA9IHdkLnBvcnRmb2xpbyB8fCBbXTsKICB2YXIgd2F0Y2ggPSB3ZC53YXRjaGxpc3QgfHwgW107CiAgdmFyIGJlc3QgPSB3ZC5iZXN0OwogIHZhciB3b3JzdCA9IHdkLndvcnN0OwogIHZhciBtZCA9IE1BUktFVF9EQVRBIHx8IHt9OwogIHZhciBzcCA9IG1kLlNQNTAwIHx8IHt9OwogIHZhciBuYXMgPSBtZC5OQVNEQVEgfHwge307CgogIGZ1bmN0aW9uIGNoZ0NvbG9yKHYpeyByZXR1cm4gdiA+PSAwID8gJ3ZhcigtLWdyZWVuKScgOiAndmFyKC0tcmVkMiknOyB9CiAgZnVuY3Rpb24gY2hnU3RyKHYpeyByZXR1cm4gKHYgPj0gMCA/ICcrJyA6ICcnKSArIHYgKyAnJSc7IH0KCiAgZnVuY3Rpb24gcGVyZkNhcmQoaXRlbSl7CiAgICB2YXIgY2MgPSBjaGdDb2xvcihpdGVtLndlZWtfY2hnKTsKICAgIHZhciBwYiA9IGl0ZW0ucG9ydGZvbGlvID8gJzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTIpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMjUpO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMDttYXJnaW4tbGVmdDo0cHgiPlA8L3NwYW4+JyA6ICcnOwogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxMnB4O2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbTo2cHgiPicKICAgICAgKyAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4Ij48c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToxNnB4O2xldHRlci1zcGFjaW5nOjJweCI+JyArIGl0ZW0udGlja2VyICsgJzwvc3Bhbj4nICsgcGIgKyAnPC9kaXY+JwogICAgICArICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGNjICsgJyI+JyArIGNoZ1N0cihpdGVtLndlZWtfY2hnKSArICc8L2Rpdj4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj7Dlm5jZWtpOiAnICsgY2hnU3RyKGl0ZW0ucHJldl93ZWVrX2NoZykgKyAnPC9kaXY+JwogICAgICArICc8L2Rpdj48L2Rpdj4nOwogIH0KCiAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgLy8gSGVhZGVyCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KTttYXJnaW4tYm90dG9tOjRweCI+8J+TiCBIYWZ0YWzEsWsgUGVyZm9ybWFucyDDlnpldGk8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JyArICh3ZC5nZW5lcmF0ZWQgfHwgJycpICsgJzwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gUGl5YXNhIHZzIFBvcnRmw7Z5CiAgdmFyIHNwQ2hnID0gc3AuY2hhbmdlIHx8IDA7CiAgdmFyIG5hc0NoZyA9IG5hcy5jaGFuZ2UgfHwgMDsKICB2YXIgcG9ydEF2ZyA9IHBvcnQubGVuZ3RoID8gTWF0aC5yb3VuZChwb3J0LnJlZHVjZShmdW5jdGlvbihhLGIpe3JldHVybiBhK2Iud2Vla19jaGc7fSwwKS9wb3J0Lmxlbmd0aCoxMDApLzEwMCA6IDA7CiAgdmFyIGFscGhhID0gTWF0aC5yb3VuZCgocG9ydEF2ZyAtIHNwQ2hnKSoxMDApLzEwMDsKICB2YXIgYWxwaGFDb2wgPSBhbHBoYSA+PSAwID8gJ3ZhcigtLWdyZWVuKScgOiAndmFyKC0tcmVkMiknOwoKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDE0MHB4LDFmcikpO2dhcDoxMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5Qb3J0ZsO2eSBPcnQuPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicgKyBjaGdDb2xvcihwb3J0QXZnKSArICciPicgKyBjaGdTdHIocG9ydEF2ZykgKyAnPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5TJlAgNTAwPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicgKyBjaGdDb2xvcihzcENoZykgKyAnIj4nICsgY2hnU3RyKHNwQ2hnKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPk5BU0RBUTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonICsgY2hnQ29sb3IobmFzQ2hnKSArICciPicgKyBjaGdTdHIobmFzQ2hnKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JyArIChhbHBoYT49MD8ncmdiYSgxNiwxODUsMTI5LC4wOCknOidyZ2JhKDIzOSw2OCw2OCwuMDgpJykgKyAnO2JvcmRlcjoxcHggc29saWQgJyArIChhbHBoYT49MD8ncmdiYSgxNiwxODUsMTI5LC4yNSknOidyZ2JhKDIzOSw2OCw2OCwuMjUpJykgKyAnO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5BbHBoYSAodnMgUyZQKTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonICsgYWxwaGFDb2wgKyAnIj4nICsgKGFscGhhPj0wPycrJzonJykgKyBhbHBoYSArICclPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBFbiBpeWkgLyBlbiBrw7Z0w7wKICBpZihiZXN0IHx8IHdvcnN0KXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyIDFmcjtnYXA6MTBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgICBpZihiZXN0KXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tZ3JlZW4pO21hcmdpbi1ib3R0b206NnB4Ij7wn4+GIEJ1IEhhZnRhbsSxbiBFbiDEsHlpc2k8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjI0cHg7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgYmVzdC50aWNrZXIgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPisnICsgYmVzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGlmKHdvcnN0KXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLXJlZDIpO21hcmdpbi1ib3R0b206NnB4Ij7wn5OJIEJ1IEhhZnRhbsSxbiBFbiBLw7Z0w7xzw7w8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjI0cHg7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgd29yc3QudGlja2VyICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicgKyB3b3JzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBQb3J0ZsO2eSBkZXRheQogIGlmKHBvcnQubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkrwgUG9ydGbDtnk8L2Rpdj4nOwogICAgcG9ydC5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0peyBoICs9IHBlcmZDYXJkKGl0ZW0pOyB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBTaW55YWxsZXIgb3pldGkKICB2YXIgYnV5Q291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nR1VDTFUgQUwnfHxyLnNpbnlhbD09PSdBTCc7fSkubGVuZ3RoOwogIHZhciBzZWxsQ291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nU0FUJzt9KS5sZW5ndGg7CiAgdmFyIHdhdGNoQ291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nRElLS0FUJzt9KS5sZW5ndGg7CgogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5OKIEJ1IEhhZnRha2kgU2lueWFsbGVyPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXAiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicgKyBidXlDb3VudCArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkFsIFNpbnlhbGk8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0teWVsbG93KSI+JyArIHdhdGNoQ291bnQgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5EaWtrYXQ8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nICsgc2VsbENvdW50ICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+U2F0IFNpbnlhbGk8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzwvZGl2PjwvZGl2Pic7CgogIC8vIFdhdGNobGlzdCBwZXJmb3JtYW5zCiAgaWYod2F0Y2gubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkYEgV2F0Y2hsaXN0PC9kaXY+JzsKICAgIHdhdGNoLmZvckVhY2goZnVuY3Rpb24oaXRlbSl7IGggKz0gcGVyZkNhcmQoaXRlbSk7IH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIGggKz0gJzwvZGl2Pic7CiAgZ3JpZC5pbm5lckhUTUwgPSBoOwp9CgoKZnVuY3Rpb24gcmVuZGVyUnV0aW4oKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgdmFyIGNoZWNrZWQgPSBsb2FkQ2hlY2tlZCgpOwogIHZhciB0b2RheSA9IG5ldyBEYXRlKCk7CiAgdmFyIGlzV2Vla2VuZCA9IHRvZGF5LmdldERheSgpID09PSAwIHx8IHRvZGF5LmdldERheSgpID09PSA2OwogIHZhciBkYXlOYW1lID0gWydQYXphcicsJ1BhemFydGVzaScsJ1NhbMSxJywnw4dhcsWfYW1iYScsJ1BlcsWfZW1iZScsJ0N1bWEnLCdDdW1hcnRlc2knXVt0b2RheS5nZXREYXkoKV07CiAgdmFyIGRhdGVTdHIgPSB0b2RheS50b0xvY2FsZURhdGVTdHJpbmcoJ3RyLVRSJywge2RheTonbnVtZXJpYycsbW9udGg6J2xvbmcnLHllYXI6J251bWVyaWMnfSk7CgogIC8vIFByb2dyZXNzIGhlc2FwbGEKICB2YXIgdG90YWxJdGVtcyA9IDA7CiAgdmFyIGRvbmVJdGVtcyA9IDA7CiAgdmFyIHNlY3Rpb25zID0gaXNXZWVrZW5kID8gWydoYWZ0YWxpayddIDogWydzYWJhaCcsJ29nbGVuJywnYWtzYW0nXTsKICBzZWN0aW9ucy5mb3JFYWNoKGZ1bmN0aW9uKGspewogICAgUlVUSU5fSVRFTVNba10uaXRlbXMuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsKICAgICAgdG90YWxJdGVtcysrOwogICAgICBpZihjaGVja2VkW2l0ZW0uaWRdKSBkb25lSXRlbXMrKzsKICAgIH0pOwogIH0pOwogIHZhciBwY3QgPSB0b3RhbEl0ZW1zID4gMCA/IE1hdGgucm91bmQoZG9uZUl0ZW1zL3RvdGFsSXRlbXMqMTAwKSA6IDA7CiAgdmFyIHBjdENvbCA9IHBjdD09PTEwMD8ndmFyKC0tZ3JlZW4pJzpwY3Q+PTUwPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tbXV0ZWQpJzsKCiAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgLy8gSGVhZGVyCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7ZmxleC13cmFwOndyYXA7Z2FwOjEwcHgiPic7CiAgaCArPSAnPGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrZGF5TmFtZSsnIFJ1dGluaTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK2RhdGVTdHIrJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjhweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JytwY3RDb2wrJyI+JytwY3QrJyU8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+Jytkb25lSXRlbXMrJy8nK3RvdGFsSXRlbXMrJyB0YW1hbWxhbmTEsTwvZGl2PjwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iaGVpZ2h0OjZweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czozcHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi10b3A6MTJweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJoZWlnaHQ6MTAwJTt3aWR0aDonK3BjdCsnJTtiYWNrZ3JvdW5kOicrcGN0Q29sKyc7Ym9yZGVyLXJhZGl1czozcHg7dHJhbnNpdGlvbjp3aWR0aCAuNXMgZWFzZSI+PC9kaXY+PC9kaXY+JzsKICBpZihwY3Q9PT0xMDApIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyO21hcmdpbi10b3A6MTBweDtmb250LXNpemU6MTRweDtjb2xvcjp2YXIoLS1ncmVlbikiPvCfjokgVMO8bSBtYWRkZWxlciB0YW1hbWxhbmTEsSE8L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIFNlY3Rpb25zCiAgc2VjdGlvbnMuZm9yRWFjaChmdW5jdGlvbihrKXsKICAgIHZhciBzZWMgPSBSVVRJTl9JVEVNU1trXTsKICAgIHZhciBzZWNEb25lID0gc2VjLml0ZW1zLmZpbHRlcihmdW5jdGlvbihpKXtyZXR1cm4gY2hlY2tlZFtpLmlkXTt9KS5sZW5ndGg7CiAgICB2YXIgc2VjVG90YWwgPSBzZWMuaXRlbXMubGVuZ3RoOwogICAgdmFyIHNlY1BjdCA9IE1hdGgucm91bmQoc2VjRG9uZS9zZWNUb3RhbCoxMDApOwogICAgdmFyIHNlY0NvbCA9IHNlY1BjdD09PTEwMD8ndmFyKC0tZ3JlZW4pJzpzZWNQY3Q+MD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLW11dGVkKSc7CgogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjEycHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrc2VjLmxhYmVsKyc8L2Rpdj4nOwogICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOicrc2VjQ29sKyc7Zm9udC13ZWlnaHQ6NjAwIj4nK3NlY0RvbmUrJy8nK3NlY1RvdGFsKyc8L3NwYW4+PC9kaXY+JzsKCiAgICBzZWMuaXRlbXMuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsKICAgICAgdmFyIGRvbmUgPSAhIWNoZWNrZWRbaXRlbS5pZF07CiAgICAgIHZhciBiZ0NvbG9yID0gZG9uZSA/ICdyZ2JhKDE2LDE4NSwxMjksLjA2KScgOiAncmdiYSgyNTUsMjU1LDI1NSwuMDIpJzsKICAgICAgdmFyIGJvcmRlckNvbG9yID0gZG9uZSA/ICdyZ2JhKDE2LDE4NSwxMjksLjIpJyA6ICdyZ2JhKDI1NSwyNTUsMjU1LC4wNSknOwogICAgICB2YXIgY2hlY2tCb3JkZXIgPSBkb25lID8gJ3ZhcigtLWdyZWVuKScgOiAndmFyKC0tbXV0ZWQpJzsKICAgICAgdmFyIGNoZWNrQmcgPSBkb25lID8gJ3ZhcigtLWdyZWVuKScgOiAndHJhbnNwYXJlbnQnOwogICAgICB2YXIgdGV4dENvbG9yID0gZG9uZSA/ICd2YXIoLS1tdXRlZCknIDogJ3ZhcigtLXRleHQpJzsKICAgICAgdmFyIHRleHREZWNvID0gZG9uZSA/ICdsaW5lLXRocm91Z2gnIDogJ25vbmUnOwogICAgICB2YXIgY2hlY2ttYXJrID0gZG9uZSA/ICc8c3ZnIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cG9seWxpbmUgcG9pbnRzPSIyLDYgNSw5IDEwLDMiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+PC9zdmc+JyA6ICcnOwogICAgICBoICs9ICc8ZGl2IG9uY2xpY2s9InRvZ2dsZUNoZWNrKFwnJyArIGl0ZW0uaWQgKyAnXCcpIiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmZsZXgtc3RhcnQ7Z2FwOjEycHg7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6OHB4O2N1cnNvcjpwb2ludGVyO21hcmdpbi1ib3R0b206NnB4O2JhY2tncm91bmQ6JyArIGJnQ29sb3IgKyAnO2JvcmRlcjoxcHggc29saWQgJyArIGJvcmRlckNvbG9yICsgJyI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZmxleC1zaHJpbms6MDt3aWR0aDoyMHB4O2hlaWdodDoyMHB4O2JvcmRlci1yYWRpdXM6NXB4O2JvcmRlcjoycHggc29saWQgJyArIGNoZWNrQm9yZGVyICsgJztiYWNrZ3JvdW5kOicgKyBjaGVja0JnICsgJztkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7bWFyZ2luLXRvcDoxcHgiPicgKyBjaGVja21hcmsgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2NvbG9yOicgKyB0ZXh0Q29sb3IgKyAnO2xpbmUtaGVpZ2h0OjEuNTt0ZXh0LWRlY29yYXRpb246JyArIHRleHREZWNvICsgJyI+JyArIGl0ZW0udGV4dCArICc8L3NwYW4+JzsKICAgICAgaCArPSAnPC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9KTsKCiAgLy8gSGFmdGEgacOnaSBvbGR1xJ91bmRhIGhhZnRhbMSxayBiw7Zsw7xtw7wgZGUgZ8O2c3RlciAoa2F0bGFuYWJpbGlyKQogIGlmKCFpc1dlZWtlbmQpewogICAgdmFyIGhTZWMgPSBSVVRJTl9JVEVNU1snaGFmdGFsaWsnXTsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wNCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjE1KTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOiM2MGE1ZmE7bWFyZ2luLWJvdHRvbTo0cHgiPicraFNlYy5sYWJlbCsnPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+UGF6YXIgYWvFn2FtxLEgeWFwxLFsYWNha2xhciDigJQgxZ91IGFuIGfDtnN0ZXJpbSBtb2R1bmRhPC9kaXY+PC9kaXY+JzsKICB9CgogIC8vIFJlc2V0IGJ1dG9udQogIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyO21hcmdpbi10b3A6NnB4Ij4nOwogIGggKz0gJzxidXR0b24gb25jbGljaz0icmVzZXRSdXRpbigpIiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS1tdXRlZCk7cGFkZGluZzo4cHggMTZweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTJweDtjdXJzb3I6cG9pbnRlciI+8J+UhCBMaXN0ZXlpIFPEsWbEsXJsYTwvYnV0dG9uPic7CiAgaCArPSAnPC9kaXY+JzsKCiAgaCArPSAnPC9kaXY+JzsKICBncmlkLmlubmVySFRNTCA9IGg7Cn0KCgpmdW5jdGlvbiBjbG9zZU0oZSl7CiAgaWYoIWV8fGUudGFyZ2V0PT09ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm92ZXJsYXkiKSl7CiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgib3ZlcmxheSIpLmNsYXNzTGlzdC5yZW1vdmUoIm9wZW4iKTsKICAgIGlmKG1DaGFydCl7bUNoYXJ0LmRlc3Ryb3koKTttQ2hhcnQ9bnVsbDt9CiAgfQp9CgpyZW5kZXJTdGF0cygpOwpyZW5kZXJEYXNoYm9hcmQoKTsKCgoKLy8g4pSA4pSAIEzEsFNURSBEw5xaRU5MRU1FIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgAp2YXIgZWRpdFdhdGNobGlzdCA9IFtdOwp2YXIgZWRpdFBvcnRmb2xpbyA9IFtdOwoKZnVuY3Rpb24gb3BlbkVkaXRMaXN0KCl7CiAgZWRpdFdhdGNobGlzdCA9IFRGX0RBVEFbJzFkJ10uZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pLm1hcChmdW5jdGlvbihyKXtyZXR1cm4gci50aWNrZXI7fSk7CiAgZWRpdFBvcnRmb2xpbyA9IFBPUlQuc2xpY2UoKTsKICByZW5kZXJFZGl0TGlzdHMoKTsKICAvLyBMb2FkIHNhdmVkIHRva2VuIGZyb20gbG9jYWxTdG9yYWdlCiAgdmFyIHNhdmVkID0gbG9jYWxTdG9yYWdlLmdldEl0ZW0oJ2doX3Rva2VuJyk7CiAgaWYoc2F2ZWQpIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZSA9IHNhdmVkOwogIHZhciB0cz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidG9rZW5TZWN0aW9uIik7IGlmKHRzKSB0cy5zdHlsZS5kaXNwbGF5PSJub25lIjsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFBvcHVwIikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwp9CgoKZnVuY3Rpb24gdG9nZ2xlVG9rZW5TZWN0aW9uKCl7CiAgdmFyIHM9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInRva2VuU2VjdGlvbiIpOwogIGlmKHMpIHMuc3R5bGUuZGlzcGxheT1zLnN0eWxlLmRpc3BsYXk9PT0ibm9uZSI/ImJsb2NrIjoibm9uZSI7Cn0KCmZ1bmN0aW9uIHNhdmVUb2tlbigpewogIHZhciB0PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZS50cmltKCk7CiAgaWYoIXQpe2FsZXJ0KCJUb2tlbiBib3MhIik7cmV0dXJuO30KICBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgiZ2hfdG9rZW4iLHQpOwogIHZhciB0cz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidG9rZW5TZWN0aW9uIik7IGlmKHRzKSB0cy5zdHlsZS5kaXNwbGF5PSJub25lIjsKICBzZXRFZGl0U3RhdHVzKCLinIUgVG9rZW4ga2F5ZGVkaWxkaSIsImdyZWVuIik7Cn0KCmZ1bmN0aW9uIGNsb3NlRWRpdFBvcHVwKGUpewogIGlmKCFlfHxlLnRhcmdldD09PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0UG9wdXAiKSl7CiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFBvcHVwIikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpOwogIH0KfQoKZnVuY3Rpb24gcmVuZGVyRWRpdExpc3RzKCl7CiAgdmFyIHdlID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIndhdGNobGlzdEVkaXRvciIpOwogIHZhciBwZSA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJwb3J0Zm9saW9FZGl0b3IiKTsKICBpZighd2V8fCFwZSkgcmV0dXJuOwoKICB3ZS5pbm5lckhUTUwgPSBlZGl0V2F0Y2hsaXN0Lm1hcChmdW5jdGlvbih0LGkpewogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO3BhZGRpbmc6NXB4IDhweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6NXB4O21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo2MDAiPicrdCsnPC9zcGFuPicKICAgICAgKyc8YnV0dG9uIG9uY2xpY2s9InJlbW92ZVRpY2tlcihcJ3dhdGNoXCcsJytpKycpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMTUpO2JvcmRlcjpub25lO2NvbG9yOnZhcigtLXJlZDIpO3dpZHRoOjIwcHg7aGVpZ2h0OjIwcHg7Ym9yZGVyLXJhZGl1czo0cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEycHgiPuKclTwvYnV0dG9uPicKICAgICAgKyc8L2Rpdj4nOwogIH0pLmpvaW4oJycpOwoKICBwZS5pbm5lckhUTUwgPSBlZGl0UG9ydGZvbGlvLm1hcChmdW5jdGlvbih0LGkpewogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO3BhZGRpbmc6NXB4IDhweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6NXB4O21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nK3QrJzwvc3Bhbj4nCiAgICAgICsnPGJ1dHRvbiBvbmNsaWNrPSJyZW1vdmVUaWNrZXIoXCdwb3J0XCcsJytpKycpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMTUpO2JvcmRlcjpub25lO2NvbG9yOnZhcigtLXJlZDIpO3dpZHRoOjIwcHg7aGVpZ2h0OjIwcHg7Ym9yZGVyLXJhZGl1czo0cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEycHgiPuKclTwvYnV0dG9uPicKICAgICAgKyc8L2Rpdj4nOwogIH0pLmpvaW4oJycpOwp9CgpmdW5jdGlvbiBhZGRUaWNrZXIobGlzdCl7CiAgdmFyIGlucHV0SWQgPSBsaXN0PT09J3dhdGNoJz8ibmV3V2F0Y2hUaWNrZXIiOiJuZXdQb3J0VGlja2VyIjsKICB2YXIgdmFsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoaW5wdXRJZCkudmFsdWUudHJpbSgpLnRvVXBwZXJDYXNlKCk7CiAgaWYoIXZhbCkgcmV0dXJuOwogIGlmKGxpc3Q9PT0nd2F0Y2gnICYmICFlZGl0V2F0Y2hsaXN0LmluY2x1ZGVzKHZhbCkpIGVkaXRXYXRjaGxpc3QucHVzaCh2YWwpOwogIGlmKGxpc3Q9PT0ncG9ydCcgICYmICFlZGl0UG9ydGZvbGlvLmluY2x1ZGVzKHZhbCkpIGVkaXRQb3J0Zm9saW8ucHVzaCh2YWwpOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKGlucHV0SWQpLnZhbHVlID0gIiI7CiAgcmVuZGVyRWRpdExpc3RzKCk7Cn0KCmZ1bmN0aW9uIHJlbW92ZVRpY2tlcihsaXN0LCBpZHgpewogIGlmKGxpc3Q9PT0nd2F0Y2gnKSBlZGl0V2F0Y2hsaXN0LnNwbGljZShpZHgsMSk7CiAgZWxzZSBlZGl0UG9ydGZvbGlvLnNwbGljZShpZHgsMSk7CiAgcmVuZGVyRWRpdExpc3RzKCk7Cn0KCmZ1bmN0aW9uIHNhdmVMaXN0VG9HaXRodWIoKXsKICB2YXIgdG9rZW4gPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ2hUb2tlbklucHV0IikudmFsdWUudHJpbSgpOwogIGlmKCF0b2tlbil7IHNldEVkaXRTdGF0dXMoIuKdjCBUb2tlbiBnZXJla2xpIOKAlCBrdXR1eWEgZ2lyIiwicmVkIik7IHJldHVybjsgfQogIGxvY2FsU3RvcmFnZS5zZXRJdGVtKCdnaF90b2tlbicsIHRva2VuKTsKCiAgdmFyIGNvbmZpZyA9IHsgd2F0Y2hsaXN0OiBlZGl0V2F0Y2hsaXN0LCBwb3J0Zm9saW86IGVkaXRQb3J0Zm9saW8gfTsKICB2YXIgY29udGVudCA9IEpTT04uc3RyaW5naWZ5KGNvbmZpZywgbnVsbCwgMik7CiAgdmFyIGI2NCA9IGJ0b2EodW5lc2NhcGUoZW5jb2RlVVJJQ29tcG9uZW50KGNvbnRlbnQpKSk7CgogIHNldEVkaXRTdGF0dXMoIvCfkr4gS2F5ZGVkaWxpeW9yLi4uIiwieWVsbG93Iik7CgogIHZhciBhcGlVcmwgPSAiaHR0cHM6Ly9hcGkuZ2l0aHViLmNvbS9yZXBvcy9naHVyenp6L2NhbnNsaW0vY29udGVudHMvY29uZmlnLmpzb24iOwogIHZhciBoZWFkZXJzID0geyJBdXRob3JpemF0aW9uIjoidG9rZW4gIit0b2tlbiwiQ29udGVudC1UeXBlIjoiYXBwbGljYXRpb24vanNvbiJ9OwoKICAvLyBGaXJzdCBnZXQgY3VycmVudCBTSEEgaWYgZXhpc3RzCiAgZmV0Y2goYXBpVXJsLCB7aGVhZGVyczpoZWFkZXJzfSkKICAgIC50aGVuKGZ1bmN0aW9uKHIpeyByZXR1cm4gci5vayA/IHIuanNvbigpIDogbnVsbDsgfSkKICAgIC50aGVuKGZ1bmN0aW9uKGV4aXN0aW5nKXsKICAgICAgdmFyIHBheWxvYWQgPSB7CiAgICAgICAgbWVzc2FnZTogIkxpc3RlIGd1bmNlbGxlbmRpICIgKyBuZXcgRGF0ZSgpLnRvTG9jYWxlRGF0ZVN0cmluZygidHItVFIiKSwKICAgICAgICBjb250ZW50OiBiNjQKICAgICAgfTsKICAgICAgaWYoZXhpc3RpbmcgJiYgZXhpc3Rpbmcuc2hhKSBwYXlsb2FkLnNoYSA9IGV4aXN0aW5nLnNoYTsKCiAgICAgIHJldHVybiBmZXRjaChhcGlVcmwsIHsKICAgICAgICBtZXRob2Q6IlBVVCIsCiAgICAgICAgaGVhZGVyczpoZWFkZXJzLAogICAgICAgIGJvZHk6SlNPTi5zdHJpbmdpZnkocGF5bG9hZCkKICAgICAgfSk7CiAgICB9KQogICAgLnRoZW4oZnVuY3Rpb24ocil7CiAgICAgIGlmKHIub2sgfHwgci5zdGF0dXM9PT0yMDEpewogICAgICAgIHNldEVkaXRTdGF0dXMoIuKchSBLYXlkZWRpbGRpISBCaXIgc29ucmFraSBDb2xhYiDDp2FsxLHFn3TEsXJtYXPEsW5kYSBha3RpZiBvbHVyLiIsImdyZWVuIik7CiAgICAgICAgc2V0VGltZW91dChmdW5jdGlvbigpe2Nsb3NlRWRpdFBvcHVwKCk7fSwyMDAwKTsKICAgICAgfSBlbHNlIHsKICAgICAgICBzZXRFZGl0U3RhdHVzKCLinYwgSGF0YTogIityLnN0YXR1cysiIOKAlCBUb2tlbifEsSBrb250cm9sIGV0IiwicmVkIik7CiAgICAgIH0KICAgIH0pCiAgICAuY2F0Y2goZnVuY3Rpb24oZSl7IHNldEVkaXRTdGF0dXMoIuKdjCBIYXRhOiAiK2UubWVzc2FnZSwicmVkIik7IH0pOwp9CgpmdW5jdGlvbiBzZXRFZGl0U3RhdHVzKG1zZywgY29sb3IpewogIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0U3RhdHVzIik7CiAgaWYoZWwpewogICAgZWwudGV4dENvbnRlbnQgPSBtc2c7CiAgICBlbC5zdHlsZS5jb2xvciA9IGNvbG9yPT09ImdyZWVuIj8idmFyKC0tZ3JlZW4pIjpjb2xvcj09PSJyZWQiPyJ2YXIoLS1yZWQyKSI6InZhcigtLXllbGxvdykiOwogIH0KfQoKCmZ1bmN0aW9uIHJlbmRlckhhZnRhbGlrKCl7CiAgdmFyIGdyaWQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogIHZhciB3ZCA9IFdFRUtMWV9EQVRBIHx8IHt9OwogIHZhciBwb3J0ID0gd2QucG9ydGZvbGlvIHx8IFtdOwogIHZhciB3YXRjaCA9IHdkLndhdGNobGlzdCB8fCBbXTsKICB2YXIgYmVzdCA9IHdkLmJlc3Q7CiAgdmFyIHdvcnN0ID0gd2Qud29yc3Q7CiAgdmFyIG1kID0gTUFSS0VUX0RBVEEgfHwge307CiAgdmFyIHNwID0gbWQuU1A1MDAgfHwge307CiAgdmFyIG5hcyA9IG1kLk5BU0RBUSB8fCB7fTsKICB2YXIgZGF0YTFkID0gVEZfREFUQVsnMWQnXSB8fCBbXTsKICB2YXIgZGF0YTF3ID0gVEZfREFUQVsnMXdrJ10gfHwgW107CgogIGZ1bmN0aW9uIGNjKHYpeyByZXR1cm4gdj49MD8ndmFyKC0tZ3JlZW4yKSc6J3ZhcigtLXJlZDIpJzsgfQogIGZ1bmN0aW9uIGNzKHYpeyByZXR1cm4gKHY+PTA/JysnOicnKSt2KyclJzsgfQoKICBmdW5jdGlvbiBwZXJmUm93KGl0ZW0pewogICAgdmFyIGNvbCA9IGNjKGl0ZW0ud2Vla19jaGcpOwogICAgdmFyIHBiID0gaXRlbS5wb3J0Zm9saW8gPyAnPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tbGVmdDo0cHgiPlA8L3NwYW4+JyA6ICcnOwogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO3BhZGRpbmc6OHB4IDEycHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6OHB4O21hcmdpbi1ib3R0b206NXB4Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtmb250LXNpemU6MTRweDtsZXR0ZXItc3BhY2luZzoxcHgiPicgKyBpdGVtLnRpY2tlciArIHBiICsgJzwvZGl2PicKICAgICAgKyAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+JwogICAgICArICc8ZGl2IHN0eWxlPSJmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGNvbCArICciPicgKyBjcyhpdGVtLndlZWtfY2hnKSArICc8L2Rpdj4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5PbmNla2k6ICcgKyBjcyhpdGVtLnByZXZfd2Vla19jaGcpICsgJzwvZGl2PicKICAgICAgKyAnPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciBwb3J0QXZnID0gcG9ydC5sZW5ndGggPyBNYXRoLnJvdW5kKHBvcnQucmVkdWNlKGZ1bmN0aW9uKGEsYil7cmV0dXJuIGErYi53ZWVrX2NoZzt9LDApL3BvcnQubGVuZ3RoKjEwMCkvMTAwIDogMDsKICB2YXIgc3BDaGcgPSBzcC5jaGFuZ2UgfHwgMDsKICB2YXIgbmFzQ2hnID0gbmFzLmNoYW5nZSB8fCAwOwogIHZhciBhbHBoYSA9IE1hdGgucm91bmQoKHBvcnRBdmctc3BDaGcpKjEwMCkvMTAwOwogIHZhciBhbHBoYUNvbCA9IGFscGhhPj0wPyd2YXIoLS1ncmVlbiknOid2YXIoLS1yZWQyKSc7CgogIHZhciBoID0gJzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CgogIC8vIEhlYWRlcgogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWJvdHRvbTo0cHgiPvCfk4ggSGFmdGFsxLFrIFBlcmZvcm1hbnMgw5Z6ZXRpPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicgKyAod2QuZ2VuZXJhdGVkfHwnJykgKyAnPC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBQaXlhc2EgdnMgUG9ydGZvbHlvCiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgxMzBweCwxZnIpKTtnYXA6MTBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgWwogICAge2xhYmVsOidQb3J0ZsO2eSBPcnQuJywgdmFsOnBvcnRBdmd9LAogICAge2xhYmVsOidTJlAgNTAwJywgdmFsOnNwQ2hnfSwKICAgIHtsYWJlbDonTkFTREFRJywgdmFsOm5hc0NoZ30sCiAgXS5mb3JFYWNoKGZ1bmN0aW9uKHgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij4nICsgeC5sYWJlbCArICc8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyBjYyh4LnZhbCkgKyAnIj4nICsgY3MoeC52YWwpICsgJzwvZGl2PjwvZGl2Pic7CiAgfSk7CiAgdmFyIGFCZyA9IGFscGhhPj0wPydyZ2JhKDE2LDE4NSwxMjksLjA4KSc6J3JnYmEoMjM5LDY4LDY4LC4wOCknOwogIHZhciBhQmQgPSBhbHBoYT49MD8ncmdiYSgxNiwxODUsMTI5LC4yNSknOidyZ2JhKDIzOSw2OCw2OCwuMjUpJzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicgKyBhQmcgKyAnO2JvcmRlcjoxcHggc29saWQgJyArIGFCZCArICc7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPkFscGhhICh2cyBTJlApPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGFscGhhQ29sICsgJyI+JyArIGNzKGFscGhhKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIEVuIGl5aSAvIGVuIGtvdHUKICBpZihiZXN0fHx3b3JzdCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogICAgaWYoYmVzdCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLWdyZWVuKTttYXJnaW4tYm90dG9tOjZweCI+8J+PhiBFbiDEsHlpPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2xldHRlci1zcGFjaW5nOjJweCI+JyArIGJlc3QudGlja2VyICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPisnICsgYmVzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGlmKHdvcnN0KXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLXJlZDIpO21hcmdpbi1ib3R0b206NnB4Ij7wn5OJIEVuIEvDtnTDvDwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtsZXR0ZXItc3BhY2luZzoycHgiPicgKyB3b3JzdC50aWNrZXIgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nICsgd29yc3Qud2Vla19jaGcgKyAnJTwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gU2lueWFsbGVyCiAgdmFyIGJ1eUMgID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nR1VDTFUgQUwnfHxyLnNpbnlhbD09PSdBTCc7fSkubGVuZ3RoOwogIHZhciB3YXJuQyA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J0RJS0tBVCc7fSkubGVuZ3RoOwogIHZhciBzZWxsQyA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J1NBVCc7fSkubGVuZ3RoOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5OKIFNpbnlhbGxlcjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2ZsZXgtd3JhcDp3cmFwIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nICsgYnV5QyArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkFsPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXllbGxvdykiPicgKyB3YXJuQyArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkRpa2thdDwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicgKyBzZWxsQyArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlNhdDwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPC9kaXY+PC9kaXY+JzsKCiAgLy8gMUcrMUggbW9tZW50dW0KICB2YXIgYm90aEJ1eSA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7CiAgICBpZihyLmhhdGEpIHJldHVybiBmYWxzZTsKICAgIHZhciB3ID0gZGF0YTF3LmZpbmQoZnVuY3Rpb24oeCl7cmV0dXJuIHgudGlja2VyPT09ci50aWNrZXI7fSk7CiAgICByZXR1cm4gKHIuc2lueWFsPT09J0dVQ0xVIEFMJ3x8ci5zaW55YWw9PT0nQUwnKSAmJiB3ICYmICh3LnNpbnlhbD09PSdHVUNMVSBBTCd8fHcuc2lueWFsPT09J0FMJyk7CiAgfSk7CiAgaWYoYm90aEJ1eS5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1ncmVlbik7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPuKaoSAxRyArIDFIIEFsIFNpbnlhbGk8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2ZsZXgtd3JhcDp3cmFwO2dhcDo4cHgiIGlkPSJib3RoQnV5Q29udGFpbmVyIj48L2Rpdj48L2Rpdj4nOwogIH0KCiAgLy8gVG9wIDMgZW50cnkgc2NvcmUKICB2YXIgdG9wRW50cnkgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pLnNvcnQoZnVuY3Rpb24oYSxiKXtyZXR1cm4gYi5lbnRyeV9zY29yZS1hLmVudHJ5X3Njb3JlO30pLnNsaWNlKDAsMyk7CiAgaWYodG9wRW50cnkubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfjq8gRW4gxLB5aSBHaXJpxZ8gS2FsaXRlc2k8L2Rpdj4nOwogICAgdmFyIG1lZGFscyA9IFsn8J+lhycsJ/CfpYgnLCfwn6WJJ107CiAgICB0b3BFbnRyeS5mb3JFYWNoKGZ1bmN0aW9uKHIsaSl7CiAgICAgIHZhciBlc2NvbCA9IHIuZW50cnlfc2NvcmU+PTc1Pyd2YXIoLS1ncmVlbiknOnIuZW50cnlfc2NvcmU+PTYwPyd2YXIoLS1ncmVlbjIpJzondmFyKC0teWVsbG93KSc7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47cGFkZGluZzo4cHggMTJweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo4cHg7bWFyZ2luLWJvdHRvbTo1cHgiIGlkPSJ0ZS0nICsgci50aWNrZXIgKyAnIj4nOwogICAgICBoICs9ICc8c3Bhbj4nICsgbWVkYWxzW2ldICsgJyA8c3Ryb25nPicgKyByLnRpY2tlciArICc8L3N0cm9uZz4gPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JyArIHIuc2lueWFsICsgJzwvc3Bhbj48L3NwYW4+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgZXNjb2wgKyAnIj4nICsgci5lbnRyeV9zY29yZSArICcvMTAwPC9zcGFuPjwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBTdG9wIHlha2luCiAgdmFyIG5lYXJTdG9wID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXsKICAgIGlmKHIuaGF0YXx8IVBPUlQuaW5jbHVkZXMoci50aWNrZXIpfHwhci5zdG9wKSByZXR1cm4gZmFsc2U7CiAgICByZXR1cm4gKHIuZml5YXQtci5zdG9wKS9yLmZpeWF0KjEwMCA8IDg7CiAgfSkuc29ydChmdW5jdGlvbihhLGIpe3JldHVybiAoYS5maXlhdC1hLnN0b3ApL2EuZml5YXQtKGIuZml5YXQtYi5zdG9wKS9iLmZpeWF0O30pOwogIGlmKG5lYXJTdG9wLmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1yZWQyKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+4pqg77iPIFN0b3AgU2V2aXllc2luZSBZYWvEsW48L2Rpdj4nOwogICAgbmVhclN0b3AuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgICAgdmFyIGRpc3QgPSBNYXRoLnJvdW5kKChyLmZpeWF0LXIuc3RvcCkvci5maXlhdCoxMDAwKS8xMDsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCIgaWQ9Im5zLScgKyByLnRpY2tlciArICciPic7CiAgICAgIGggKz0gJzxzdHJvbmc+JyArIHIudGlja2VyICsgJzwvc3Ryb25nPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLXJlZDIpO2ZvbnQtd2VpZ2h0OjYwMCI+U3RvcCAkJyArIHIuc3RvcCArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlV6YWtsxLFrOiAlJyArIGRpc3QgKyAnPC9kaXY+PC9kaXY+PC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIEhlZGVmZSB5YWtpbgogIHZhciBuZWFyVGFyZ2V0ID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXsKICAgIGlmKHIuaGF0YXx8IVBPUlQuaW5jbHVkZXMoci50aWNrZXIpfHwhci5oZWRlZikgcmV0dXJuIGZhbHNlOwogICAgcmV0dXJuIChyLmhlZGVmLXIuZml5YXQpL3IuZml5YXQqMTAwIDwgMTU7CiAgfSkuc29ydChmdW5jdGlvbihhLGIpe3JldHVybiAoYS5oZWRlZi1hLmZpeWF0KS9hLmZpeWF0LShiLmhlZGVmLWIuZml5YXQpL2IuZml5YXQ7fSk7CiAgaWYobmVhclRhcmdldC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn46vIEhlZGVmZSBZYWvEsW48L2Rpdj4nOwogICAgbmVhclRhcmdldC5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgICB2YXIgZGlzdCA9IE1hdGgucm91bmQoKHIuaGVkZWYtci5maXlhdCkvci5maXlhdCoxMDAwKS8xMDsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCI+JzsKICAgICAgaCArPSAnPHN0cm9uZz4nICsgci50aWNrZXIgKyAnPC9zdHJvbmc+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6IzYwYTVmYTtmb250LXdlaWdodDo2MDAiPkhlZGVmICQnICsgci5oZWRlZiArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkthbGRpOiAlJyArIGRpc3QgKyAnPC9kaXY+PC9kaXY+PC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIEVhcm5pbmdzCiAgdmFyIHVyZ2VudEUgPSBFQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gZS5kYXlzX3RvX2Vhcm5pbmdzIT1udWxsJiZlLmRheXNfdG9fZWFybmluZ3M8PTE0O30pLnNvcnQoZnVuY3Rpb24oYSxiKXtyZXR1cm4gYS5kYXlzX3RvX2Vhcm5pbmdzLWIuZGF5c190b19lYXJuaW5nczt9KTsKICBpZih1cmdlbnRFLmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLXllbGxvdyk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfk4UgWWFrbGHFn2FuIFJhcG9ybGFyPC9kaXY+JzsKICAgIHVyZ2VudEUuZm9yRWFjaChmdW5jdGlvbihlKXsKICAgICAgdmFyIGljID0gZS5hbGVydD09PSdyZWQnPyfwn5S0Jzon8J+foSc7CiAgICAgIHZhciBpblBvcnQgPSBQT1JULmluY2x1ZGVzKGUudGlja2VyKTsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCI+JzsKICAgICAgaCArPSAnPHNwYW4+JyArIGljICsgJyA8c3Ryb25nPicgKyBlLnRpY2tlciArICc8L3N0cm9uZz4nICsgKGluUG9ydD8nIDxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjEwcHgiPlA8L3NwYW4+JzonJykgKyAnPC9zcGFuPic7CiAgICAgIGggKz0gJzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1zaXplOjExcHgiPicgKyBlLm5leHRfZGF0ZSArICcgKCcgKyBlLmRheXNfdG9fZWFybmluZ3MgKyAnIGfDvG4pPC9zcGFuPjwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBWSVgKICB2YXIgdml4ID0gbWQuVklYIHx8IHt9OwogIGlmKHZpeC5wcmljZSl7CiAgICB2YXIgdkNvbCA9IHZpeC5wcmljZT4zMD8ndmFyKC0tcmVkMiknOnZpeC5wcmljZT4yMD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLWdyZWVuKSc7CiAgICB2YXIgdkxibCA9IHZpeC5wcmljZT4zMD8nWcO8a3NlayBLb3JrdSDigJQgWWVuaSBwb3ppc3lvbiBhw6dtYSc6dml4LnByaWNlPjIwPydPcnRhIFZvbGF0aWxpdGUg4oCUIERpa2thdGxpIG9sJzonRMO8xZ/DvGsgVm9sYXRpbGl0ZSDigJQgTm9ybWFsIGtvxZ91bGxhcic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE0cHggMTZweDttYXJnaW4tYm90dG9tOjEwcHg7ZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlciI+JzsKICAgIGggKz0gJzxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MnB4Ij5WSVg8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjonICsgdkNvbCArICciPicgKyB2TGJsICsgJzwvZGl2PjwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjhweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIHZDb2wgKyAnIj4nICsgdml4LnByaWNlICsgJzwvZGl2PjwvZGl2Pic7CiAgfQoKICAvLyBQb3J0Zm9seW8gZGV0YXkKICBpZihwb3J0Lmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5K8IFBvcnRmw7Z5PC9kaXY+JzsKICAgIHBvcnQuZm9yRWFjaChmdW5jdGlvbihpdGVtKXtoICs9IHBlcmZSb3coaXRlbSk7fSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gV2F0Y2hsaXN0CiAgaWYod2F0Y2gubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkYEgV2F0Y2hsaXN0PC9kaXY+JzsKICAgIHdhdGNoLmZvckVhY2goZnVuY3Rpb24oaXRlbSl7aCArPSBwZXJmUm93KGl0ZW0pO30pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIGggKz0gJzwvZGl2Pic7CiAgZ3JpZC5pbm5lckhUTUwgPSBoOwoKICAvLyBBZGQgb25jbGljayB2aWEgSlMgKGF2b2lkcyBxdW90ZSBuZXN0aW5nIGlzc3VlcykKICBib3RoQnV5LmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgY250ID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2JvdGhCdXlDb250YWluZXInKTsKICAgIGlmKCFjbnQpIHJldHVybjsKICAgIHZhciBkID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2Jyk7CiAgICBkLnN0eWxlLmNzc1RleHQgPSAnYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjhweCAxNHB4O2N1cnNvcjpwb2ludGVyJzsKICAgIGQuaW5uZXJIVE1MID0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDtsZXR0ZXItc3BhY2luZzoycHg7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nICsgci50aWNrZXIgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5HaXJpczogJyArIHIuZW50cnlfc2NvcmUgKyAnLzEwMDwvZGl2Pic7CiAgICBkLm9uY2xpY2sgPSAoZnVuY3Rpb24odCl7cmV0dXJuIGZ1bmN0aW9uKCl7b3Blbk0odCk7fTt9KShyLnRpY2tlcik7CiAgICBjbnQuYXBwZW5kQ2hpbGQoZCk7CiAgfSk7CiAgdG9wRW50cnkuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCd0ZS0nICsgci50aWNrZXIpOwogICAgaWYoZWwpIGVsLm9uY2xpY2sgPSAoZnVuY3Rpb24odCl7cmV0dXJuIGZ1bmN0aW9uKCl7b3Blbk0odCk7fTt9KShyLnRpY2tlciksIGVsLnN0eWxlLmN1cnNvcj0ncG9pbnRlcic7CiAgfSk7CiAgbmVhclN0b3AuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCducy0nICsgci50aWNrZXIpOwogICAgaWYoZWwpIGVsLm9uY2xpY2sgPSAoZnVuY3Rpb24odCl7cmV0dXJuIGZ1bmN0aW9uKCl7b3Blbk0odCk7fTt9KShyLnRpY2tlciksIGVsLnN0eWxlLmN1cnNvcj0ncG9pbnRlcic7CiAgfSk7Cn0KCjwvc2NyaXB0Pgo8L2JvZHk+CjwvaHRtbD4="
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
