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
    _T = "PCFET0NUWVBFIGh0bWw+CjxodG1sIGxhbmc9InRyIj4KPGhlYWQ+CjxtZXRhIGNoYXJzZXQ9IlVURi04Ii8+CjxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsaW5pdGlhbC1zY2FsZT0xIi8+Cjx0aXRsZT5DQU5TTElNIFNjYW5uZXI8L3RpdGxlPgo8bGluayByZWw9Imljb24iIHR5cGU9ImltYWdlL3N2Zyt4bWwiIGhyZWY9ImRhdGE6aW1hZ2Uvc3ZnK3htbCwlM0NzdmcgeG1sbnM9J2h0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnJyB2aWV3Qm94PScwIDAgMzIgMzInJTNFJTNDcmVjdCB3aWR0aD0nMzInIGhlaWdodD0nMzInIHJ4PSc2JyBmaWxsPSclMjMwZDExMTcnLyUzRSUzQ3BvbHlsaW5lIHBvaW50cz0nNCwyNCAxMCwxNiAxNiwyMCAyMiwxMCAyOCwxNCcgZmlsbD0nbm9uZScgc3Ryb2tlPSclMjMxMGI5ODEnIHN0cm9rZS13aWR0aD0nMi41JyBzdHJva2UtbGluZWNhcD0ncm91bmQnIHN0cm9rZS1saW5lam9pbj0ncm91bmQnLyUzRSUzQy9zdmclM0UiPgo8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PVNwYWNlK0dyb3Rlc2s6d2dodEA0MDA7NTAwOzYwMDs3MDAmZmFtaWx5PUJlYmFzK05ldWUmZmFtaWx5PUpldEJyYWlucytNb25vOndnaHRANDAwOzYwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCIvPgo8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9jaGFydC5qc0A0LjQuMC9kaXN0L2NoYXJ0LnVtZC5taW4uanMiPjwvc2NyaXB0Pgo8c3R5bGU+Cjpyb290ey0tYmc6IzA1MDcwZjstLWJnMjojMGQxMTE3Oy0tYmczOiMxNjFiMjQ7LS1ib3JkZXI6cmdiYSgyNTUsMjU1LDI1NSwwLjA4KTstLXRleHQ6I2UyZThmMDstLW11dGVkOiM0YjU1NjM7LS1ncmVlbjojMTBiOTgxOy0tZ3JlZW4yOiMzNGQzOTk7LS1yZWQ6I2VmNDQ0NDstLXJlZDI6I2Y4NzE3MTstLXllbGxvdzojZjU5ZTBiO30KKntib3gtc2l6aW5nOmJvcmRlci1ib3g7bWFyZ2luOjA7cGFkZGluZzowfQpib2R5e2JhY2tncm91bmQ6dmFyKC0tYmcpO2NvbG9yOnZhcigtLXRleHQpO2ZvbnQtZmFtaWx5OidTcGFjZSBHcm90ZXNrJyxzYW5zLXNlcmlmO21pbi1oZWlnaHQ6MTAwdmh9Ci5oZWFkZXJ7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCMwZDExMTcsIzExMTgyNyk7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtwYWRkaW5nOjE0cHggMjBweDtwb3NpdGlvbjpzdGlja3k7dG9wOjA7ei1pbmRleDoxMDB9Ci5oZWFkZXItaW5uZXJ7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTBweDttYXgtd2lkdGg6MTQwMHB4O21hcmdpbjowIGF1dG99Ci5sb2dvLW1haW57Zm9udC1mYW1pbHk6J0JlYmFzIE5ldWUnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjIycHg7bGV0dGVyLXNwYWNpbmc6NHB4O2JhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZywjMTBiOTgxLCMzYjgyZjYpOy13ZWJraXQtYmFja2dyb3VuZC1jbGlwOnRleHQ7LXdlYmtpdC10ZXh0LWZpbGwtY29sb3I6dHJhbnNwYXJlbnR9Ci50aW1lc3RhbXB7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLmxpdmUtZG90e3dpZHRoOjdweDtoZWlnaHQ6N3B4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6dmFyKC0tZ3JlZW4pO2FuaW1hdGlvbjpwdWxzZSAycyBpbmZpbml0ZTtkaXNwbGF5OmlubGluZS1ibG9jazttYXJnaW4tcmlnaHQ6NXB4fQpAa2V5ZnJhbWVzIHB1bHNlezAlLDEwMCV7b3BhY2l0eToxO2JveC1zaGFkb3c6MCAwIDAgMCByZ2JhKDE2LDE4NSwxMjksLjQpfTUwJXtvcGFjaXR5Oi43O2JveC1zaGFkb3c6MCAwIDAgNnB4IHJnYmEoMTYsMTg1LDEyOSwwKX19Ci5uYXZ7ZGlzcGxheTpmbGV4O2dhcDo0cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7b3ZlcmZsb3cteDphdXRvO2ZsZXgtd3JhcDp3cmFwfQoudGFie3BhZGRpbmc6NnB4IDE0cHg7Ym9yZGVyLXJhZGl1czo2cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NTAwO2JvcmRlcjoxcHggc29saWQgdHJhbnNwYXJlbnQ7YmFja2dyb3VuZDpub25lO2NvbG9yOnZhcigtLW11dGVkKTt0cmFuc2l0aW9uOmFsbCAuMnM7d2hpdGUtc3BhY2U6bm93cmFwfQoudGFiOmhvdmVye2NvbG9yOnZhcigtLXRleHQpO2JhY2tncm91bmQ6dmFyKC0tYmczKX0KLnRhYi5hY3RpdmV7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLXRleHQpO2JvcmRlci1jb2xvcjp2YXIoLS1ib3JkZXIpfQoudGFiLnBvcnQuYWN0aXZle2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyLWNvbG9yOnJnYmEoMTYsMTg1LDEyOSwuMyl9Ci50Zi1yb3d7ZGlzcGxheTpmbGV4O2dhcDo2cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7YWxpZ24taXRlbXM6Y2VudGVyO2ZsZXgtd3JhcDp3cmFwfQoudGYtYnRue3BhZGRpbmc6NXB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Y3Vyc29yOnBvaW50ZXI7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO3RyYW5zaXRpb246YWxsIC4yc30KLnRmLWJ0bi5hY3RpdmV7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtjb2xvcjojNjBhNWZhO2JvcmRlci1jb2xvcjpyZ2JhKDU5LDEzMCwyNDYsLjQpfQoudGYtYnRuLnN0YXJ7cG9zaXRpb246cmVsYXRpdmV9Ci50Zi1idG4uc3Rhcjo6YWZ0ZXJ7Y29udGVudDon4piFJztwb3NpdGlvbjphYnNvbHV0ZTt0b3A6LTVweDtyaWdodDotNHB4O2ZvbnQtc2l6ZTo4cHg7Y29sb3I6dmFyKC0teWVsbG93KX0KLnRmLWhpbnR7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpfQouc3RhdHN7ZGlzcGxheTpmbGV4O2dhcDo4cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7ZmxleC13cmFwOndyYXB9Ci5waWxse2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjVweDtwYWRkaW5nOjRweCAxMHB4O2JvcmRlci1yYWRpdXM6MjBweDtmb250LXNpemU6MTFweDtmb250LXdlaWdodDo2MDA7Ym9yZGVyOjFweCBzb2xpZH0KLnBpbGwuZ3tiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMSk7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlci1jb2xvcjpyZ2JhKDE2LDE4NSwxMjksLjI1KX0KLnBpbGwucntiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xKTtjb2xvcjp2YXIoLS1yZWQyKTtib3JkZXItY29sb3I6cmdiYSgyMzksNjgsNjgsLjI1KX0KLnBpbGwueXtiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMSk7Y29sb3I6dmFyKC0teWVsbG93KTtib3JkZXItY29sb3I6cmdiYSgyNDUsMTU4LDExLC4yNSl9Ci5waWxsLmJ7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjEpO2NvbG9yOiM2MGE1ZmE7Ym9yZGVyLWNvbG9yOnJnYmEoNTksMTMwLDI0NiwuMjUpfQoucGlsbC5te2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Ym9yZGVyLWNvbG9yOnZhcigtLWJvcmRlcil9Ci5kb3R7d2lkdGg6NXB4O2hlaWdodDo1cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpjdXJyZW50Q29sb3J9Ci5tYWlue3BhZGRpbmc6MTRweCAyMHB4O21heC13aWR0aDoxNDAwcHg7bWFyZ2luOjAgYXV0b30KLmdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgzMDBweCwxZnIpKTtnYXA6MTBweH0KQG1lZGlhKG1heC13aWR0aDo0ODBweCl7LmdyaWR7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmcn19Ci5jYXJke2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O292ZXJmbG93OmhpZGRlbjtjdXJzb3I6cG9pbnRlcjt0cmFuc2l0aW9uOmFsbCAuMnN9Ci5jYXJkOmhvdmVye3RyYW5zZm9ybTp0cmFuc2xhdGVZKC0ycHgpO2JveC1zaGFkb3c6MCA4cHggMjRweCByZ2JhKDAsMCwwLC40KX0KLmFjY2VudHtoZWlnaHQ6M3B4fQouY2JvZHl7cGFkZGluZzoxMnB4IDE0cHh9Ci5jdG9we2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpmbGV4LXN0YXJ0O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206OHB4fQoudGlja2Vye2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyMHB4O2xldHRlci1zcGFjaW5nOjJweDtsaW5lLWhlaWdodDoxfQouY3Bye3RleHQtYWxpZ246cmlnaHR9Ci5wdmFse2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTVweDtmb250LXdlaWdodDo2MDB9Ci5wY2hne2ZvbnQtc2l6ZToxMXB4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTttYXJnaW4tdG9wOjJweH0KLmJhZGdle2Rpc3BsYXk6aW5saW5lLWJsb2NrO3BhZGRpbmc6MnB4IDhweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6LjVweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLXRvcDozcHh9Ci5wb3J0LWJhZGdle2Rpc3BsYXk6aW5saW5lLWZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDozcHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwO2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xMik7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yNSk7bWFyZ2luLWxlZnQ6NXB4fQouc2lnc3tkaXNwbGF5OmZsZXg7ZmxleC13cmFwOndyYXA7Z2FwOjNweDttYXJnaW4tYm90dG9tOjhweH0KLnNwe2ZvbnQtc2l6ZTo5cHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLnNne2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbjIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKX0KLnNie2JhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjEpO2NvbG9yOnZhcigtLXJlZDIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpfQouc257YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLW11dGVkKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5jaGFydC13e2hlaWdodDo3NXB4O21hcmdpbi10b3A6OHB4fQoubHZsc3tkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgzLDFmcik7Z2FwOjVweDttYXJnaW4tdG9wOjhweH0KLmx2e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjVweDtwYWRkaW5nOjZweDt0ZXh0LWFsaWduOmNlbnRlcjtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5sbHtmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MnB4fQoubHZhbHtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwfQoub3ZlcmxheXtwb3NpdGlvbjpmaXhlZDtpbnNldDowO2JhY2tncm91bmQ6cmdiYSgwLDAsMCwuODgpO3otaW5kZXg6MTAwMDtkaXNwbGF5Om5vbmU7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7cGFkZGluZzoxNnB4fQoub3ZlcmxheS5vcGVue2Rpc3BsYXk6ZmxleH0KLm1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjUyMHB4O21heC1oZWlnaHQ6OTJ2aDtvdmVyZmxvdy15OmF1dG99Ci5taGVhZHtwYWRkaW5nOjE4cHggMThweCAwO2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpmbGV4LXN0YXJ0fQoubXRpdGxle2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZTozMHB4O2xldHRlci1zcGFjaW5nOjNweH0KLm1jbG9zZXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTt3aWR0aDozMHB4O2hlaWdodDozMHB4O2JvcmRlci1yYWRpdXM6N3B4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxNXB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcn0KLm1ib2R5e3BhZGRpbmc6MTRweCAxOHB4IDE4cHh9Ci5tY2hhcnR3e2hlaWdodDoxNTBweDttYXJnaW4tYm90dG9tOjE0cHh9Ci5kZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjdweDttYXJnaW4tYm90dG9tOjEycHh9Ci5kY3tiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo3cHg7cGFkZGluZzo5cHggMTFweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5kbHtmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206M3B4fQouZHZ7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMH0KLmRib3h7Ym9yZGVyLXJhZGl1czo5cHg7cGFkZGluZzoxM3B4O21hcmdpbi1ib3R0b206MTJweDtib3JkZXI6MXB4IHNvbGlkfQouZGxibHtmb250LXNpemU6OXB4O2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo1cHh9Ci5kdmVyZHtmb250LWZhbWlseTonQmViYXMgTmV1ZScsc2Fucy1zZXJpZjtmb250LXNpemU6MjZweDtsZXR0ZXItc3BhY2luZzoycHg7bWFyZ2luLWJvdHRvbTo4cHh9Ci5kcm93e2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjRweDtmb250LXNpemU6MTJweH0KLmRrZXl7Y29sb3I6dmFyKC0tbXV0ZWQpfQoucnJiYXJ7aGVpZ2h0OjRweDtiYWNrZ3JvdW5kOnZhcigtLWJnKTtib3JkZXItcmFkaXVzOjJweDttYXJnaW4tdG9wOjdweDtvdmVyZmxvdzpoaWRkZW59Ci5ycmZpbGx7aGVpZ2h0OjEwMCU7Ym9yZGVyLXJhZGl1czoycHg7dHJhbnNpdGlvbjp3aWR0aCAuOHMgZWFzZX0KLnZwYm94e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjdweDtwYWRkaW5nOjEwcHg7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO21hcmdpbi1ib3R0b206MTJweH0KLnZwdGl0bGV7Zm9udC1zaXplOjlweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo3cHh9Ci52cGdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoMywxZnIpO2dhcDo1cHh9Ci52cGN7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlci1yYWRpdXM6NXB4O3BhZGRpbmc6N3B4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlcjoxcHggc29saWR9Ci5taW5mb3tkaXNwbGF5OmlubGluZS1mbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO3dpZHRoOjE0cHg7aGVpZ2h0OjE0cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpyZ2JhKDk2LDE2NSwyNTAsLjIpO2NvbG9yOiM2MGE1ZmE7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7Y3Vyc29yOnBvaW50ZXI7bWFyZ2luLWxlZnQ6NHB4O2JvcmRlcjoxcHggc29saWQgcmdiYSg5NiwxNjUsMjUwLC4zKX0KLm1pbmZvLXBvcHVwe3Bvc2l0aW9uOmZpeGVkO2luc2V0OjA7YmFja2dyb3VuZDpyZ2JhKDAsMCwwLC44OCk7ei1pbmRleDoyMDAwO2Rpc3BsYXk6bm9uZTthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjtwYWRkaW5nOjE2cHh9Ci5taW5mby1wb3B1cC5vcGVue2Rpc3BsYXk6ZmxleH0KLm1pbmZvLW1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjQ4MHB4O21heC1oZWlnaHQ6ODV2aDtvdmVyZmxvdy15OmF1dG87cGFkZGluZzoyMHB4O3Bvc2l0aW9uOnJlbGF0aXZlfQoubWluZm8tdGl0bGV7Zm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4fQoubWluZm8tc291cmNle2ZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjEycHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4O2ZsZXgtd3JhcDp3cmFwfQoubWluZm8tcmVse3BhZGRpbmc6MnB4IDdweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMH0KLm1pbmZvLXJlbC5oaWdoe2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Y29sb3I6IzEwYjk4MX0KLm1pbmZvLXJlbC5tZWRpdW17YmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjE1KTtjb2xvcjojZjU5ZTBifQoubWluZm8tcmVsLmxvd3tiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Y29sb3I6I2VmNDQ0NH0KLm1pbmZvLWRlc2N7Zm9udC1zaXplOjEycHg7Y29sb3I6Izk0YTNiODtsaW5lLWhlaWdodDoxLjY7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8td2FybmluZ3tiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjZweDtwYWRkaW5nOjhweCAxMHB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOiNmNTllMGI7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8tcmFuZ2Vze21hcmdpbi1ib3R0b206MTRweH0KLm1pbmZvLXJhbmdlLXRpdGxle2ZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHh9Ci5taW5mby1yYW5nZXtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo4cHg7bWFyZ2luLWJvdHRvbTo2cHg7cGFkZGluZzo2cHggOHB4O2JvcmRlci1yYWRpdXM6NnB4O2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMDIpfQoubWluZm8tcmFuZ2UtZG90e3dpZHRoOjhweDtoZWlnaHQ6OHB4O2JvcmRlci1yYWRpdXM6NTAlO2ZsZXgtc2hyaW5rOjB9Ci5taW5mby1jYW5zbGlte2JhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6NnB4O3BhZGRpbmc6OHB4IDEwcHg7Zm9udC1zaXplOjExcHg7Y29sb3I6IzYwYTVmYX0KLm1pbmZvLWNsb3Nle3Bvc2l0aW9uOmFic29sdXRlO3RvcDoxNnB4O3JpZ2h0OjE2cHg7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4xKTtjb2xvcjojOTRhM2I4O3dpZHRoOjI4cHg7aGVpZ2h0OjI4cHg7Ym9yZGVyLXJhZGl1czo3cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjE0cHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyfQo6Oi13ZWJraXQtc2Nyb2xsYmFye3dpZHRoOjRweDtoZWlnaHQ6NHB4fQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRyYWNre2JhY2tncm91bmQ6dmFyKC0tYmcpfQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRodW1ie2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMSk7Ym9yZGVyLXJhZGl1czoycHh9Cjwvc3R5bGU+CjwvaGVhZD4KPGJvZHk+CjxkaXYgY2xhc3M9ImhlYWRlciI+CiAgPGRpdiBjbGFzcz0iaGVhZGVyLWlubmVyIj4KICAgIDxzcGFuIGNsYXNzPSJsb2dvLW1haW4iPkNBTlNMSU0gU0NBTk5FUjwvc3Bhbj4KICAgIDxzcGFuIGNsYXNzPSJ0aW1lc3RhbXAiPjxzcGFuIGNsYXNzPSJsaXZlLWRvdCI+PC9zcGFuPiUlVElNRVNUQU1QJSU8L3NwYW4+CiAgICA8YnV0dG9uIG9uY2xpY2s9Im9wZW5FZGl0TGlzdCgpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMyk7Y29sb3I6IzYwYTVmYTtwYWRkaW5nOjVweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMXB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtZmFtaWx5OmluaGVyaXQiPuKcj++4jyBMaXN0ZXlpIETDvHplbmxlPC9idXR0b24+CiAgPC9kaXY+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJuYXYiPgogIDxidXR0b24gY2xhc3M9InRhYiBhY3RpdmUiIG9uY2xpY2s9InNldFRhYignZGFzaGJvYXJkJyx0aGlzKSI+8J+PoCBEYXNoYm9hcmQ8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignYWxsJyx0aGlzKSI+8J+TiiBIaXNzZWxlcjwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiBwb3J0IiBvbmNsaWNrPSJzZXRUYWIoJ3BvcnQnLHRoaXMpIj7wn5K8IFBvcnRmw7Z5w7xtPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2J1eScsdGhpcykiPvCfk4ggQWw8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignc2VsbCcsdGhpcykiPvCfk4kgU2F0PC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2Vhcm5pbmdzJyx0aGlzKSI+8J+ThSBFYXJuaW5nczwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdydXRpbicsdGhpcykiPuKchSBSdXRpbjwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdoYWZ0YWxpaycsdGhpcykiPvCfk4ggSGFmdGFsxLFrPC9idXR0b24+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJ0Zi1yb3ciIGlkPSJ0ZlJvdyIgc3R5bGU9ImRpc3BsYXk6bm9uZSI+CiAgPGJ1dHRvbiBjbGFzcz0idGYtYnRuIGFjdGl2ZSIgZGF0YS10Zj0iMWQiIG9uY2xpY2s9InNldFRmKCcxZCcsdGhpcykiPjFHPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGYtYnRuIHN0YXIiIGRhdGEtdGY9IjF3ayIgb25jbGljaz0ic2V0VGYoJzF3aycsdGhpcykiPjFIPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGYtYnRuIiBkYXRhLXRmPSIxbW8iIG9uY2xpY2s9InNldFRmKCcxbW8nLHRoaXMpIj4xQTwvYnV0dG9uPgogIDxzcGFuIGNsYXNzPSJ0Zi1oaW50Ij5DQU5TTElNIMO2bmVyaWxlbjogMUcgKyAxSDwvc3Bhbj4KPC9kaXY+CjxkaXYgY2xhc3M9InN0YXRzIiBpZD0ic3RhdHMiPjwvZGl2Pgo8ZGl2IGNsYXNzPSJtYWluIj48ZGl2IGNsYXNzPSJncmlkIiBpZD0iZ3JpZCI+PC9kaXY+PC9kaXY+CjxkaXYgY2xhc3M9Im92ZXJsYXkiIGlkPSJvdmVybGF5IiBvbmNsaWNrPSJjbG9zZU0oZXZlbnQpIj4KICA8ZGl2IGNsYXNzPSJtb2RhbCIgaWQ9Im1vZGFsIj48L2Rpdj4KPC9kaXY+Cgo8ZGl2IGNsYXNzPSJtaW5mby1wb3B1cCIgaWQ9ImVkaXRQb3B1cCIgb25jbGljaz0iY2xvc2VFZGl0UG9wdXAoZXZlbnQpIj4KICA8ZGl2IGNsYXNzPSJtaW5mby1tb2RhbCIgc3R5bGU9InBvc2l0aW9uOnJlbGF0aXZlO21heC13aWR0aDo1NjBweCIgaWQ9ImVkaXRNb2RhbCI+CiAgICA8YnV0dG9uIGNsYXNzPSJtaW5mby1jbG9zZSIgb25jbGljaz0iY2xvc2VFZGl0UG9wdXAoKSI+4pyVPC9idXR0b24+CiAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCk7bWFyZ2luLWJvdHRvbTo0cHgiPuKcj++4jyBMaXN0ZXlpIETDvHplbmxlPC9kaXY+CiAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbToxNnB4Ij5HaXRIdWIgQVBJIGtleSBnZXJla2xpIOKAlCBkZcSfacWfaWtsaWtsZXIgYW7EsW5kYSBrYXlkZWRpbGlyPC9kaXY+CiAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjE2cHg7bWFyZ2luLWJvdHRvbToxNnB4Ij4KICAgICAgPGRpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+8J+TiyBXYXRjaGxpc3Q8L2Rpdj4KICAgICAgICA8ZGl2IGlkPSJ3YXRjaGxpc3RFZGl0b3IiPjwvZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6NnB4O21hcmdpbi10b3A6OHB4Ij4KICAgICAgICAgIDxpbnB1dCBpZD0ibmV3V2F0Y2hUaWNrZXIiIHBsYWNlaG9sZGVyPSJIaXNzZSBla2xlIChUU0xBKSIgc3R5bGU9ImZsZXg6MTtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLXRleHQpO3BhZGRpbmc6NnB4IDEwcHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Zm9udC1mYW1pbHk6aW5oZXJpdDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2UiLz4KICAgICAgICAgIDxidXR0b24gb25jbGljaz0iYWRkVGlja2VyKCd3YXRjaCcpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6NnB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Y3Vyc29yOnBvaW50ZXIiPisgRWtsZTwvYnV0dG9uPgogICAgICAgIDwvZGl2PgogICAgICA8L2Rpdj4KICAgICAgPGRpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+8J+SvCBQb3J0ZsO2eTwvZGl2PgogICAgICAgIDxkaXYgaWQ9InBvcnRmb2xpb0VkaXRvciI+PC9kaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo2cHg7bWFyZ2luLXRvcDo4cHgiPgogICAgICAgICAgPGlucHV0IGlkPSJuZXdQb3J0VGlja2VyIiBwbGFjZWhvbGRlcj0iSGlzc2UgZWtsZSAoQUFQTCkiIHN0eWxlPSJmbGV4OjE7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS10ZXh0KTtwYWRkaW5nOjZweCAxMHB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2ZvbnQtZmFtaWx5OmluaGVyaXQ7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlIi8+CiAgICAgICAgICA8YnV0dG9uIG9uY2xpY2s9ImFkZFRpY2tlcigncG9ydCcpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6NnB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Y3Vyc29yOnBvaW50ZXIiPisgRWtsZTwvYnV0dG9uPgogICAgICAgIDwvZGl2PgogICAgICA8L2Rpdj4KICAgIDwvZGl2PgogICAgPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDEycHg7bWFyZ2luLWJvdHRvbToxNHB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLWdyZWVuKSI+4pyFIERlxJ9pxZ9pa2xpa2xlciBrYXlkZWRpbGluY2UgYmlyIHNvbnJha2kgQ29sYWIgw6dhbMSxxZ90xLFybWFzxLFuZGEgYWt0aWYgb2x1ci48L2Rpdj4KPGRpdiBzdHlsZT0ibWFyZ2luLWJvdHRvbToxMnB4Ij4KICAgICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NXB4Ij5HaXRIdWIgVG9rZW4gKGJpciBrZXogZ2lyLCB0YXJheWljaSBoYXRpcmxheWFjYWspPC9kaXY+CiAgICAgIDxpbnB1dCBpZD0iZ2hUb2tlbklucHV0IiBwbGFjZWhvbGRlcj0iZ2hwXy4uLiIgc3R5bGU9IndpZHRoOjEwMCU7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS10ZXh0KTtwYWRkaW5nOjhweCAxMHB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMXB4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSIvPgogICAgPC9kaXY+CiAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjhweCI+CiAgICAgIDxidXR0b24gb25jbGljaz0ic2F2ZUxpc3RUb0dpdGh1YigpIiBzdHlsZT0iZmxleDoxO2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjMpO2NvbG9yOnZhcigtLWdyZWVuKTtwYWRkaW5nOjEwcHg7Ym9yZGVyLXJhZGl1czo4cHg7Zm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2N1cnNvcjpwb2ludGVyIj7wn5K+IEdpdEh1YidhIEtheWRldDwvYnV0dG9uPgogICAgICA8YnV0dG9uIG9uY2xpY2s9ImNsb3NlRWRpdFBvcHVwKCkiIHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTtwYWRkaW5nOjEwcHggMTZweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTNweDtjdXJzb3I6cG9pbnRlciI+xLBwdGFsPC9idXR0b24+CiAgICA8L2Rpdj4KICAgIDxkaXYgaWQ9ImVkaXRTdGF0dXMiIHN0eWxlPSJtYXJnaW4tdG9wOjEwcHg7Zm9udC1zaXplOjEycHg7dGV4dC1hbGlnbjpjZW50ZXIiPjwvZGl2PgogIDwvZGl2Pgo8L2Rpdj4KCjxkaXYgY2xhc3M9Im1pbmZvLXBvcHVwIiBpZD0ibWluZm9Qb3B1cCIgb25jbGljaz0iY2xvc2VJbmZvUG9wdXAoZXZlbnQpIj4KICA8ZGl2IGNsYXNzPSJtaW5mby1tb2RhbCIgaWQ9Im1pbmZvTW9kYWwiPgogICAgPGJ1dHRvbiBjbGFzcz0ibWluZm8tY2xvc2UiIG9uY2xpY2s9ImNsb3NlSW5mb1BvcHVwKCkiPuKclTwvYnV0dG9uPgogICAgPGRpdiBpZD0ibWluZm9Db250ZW50Ij48L2Rpdj4KICA8L2Rpdj4KPC9kaXY+CjxzY3JpcHQ+CnZhciBNRVRSSUNTID0gewogIC8vIFRFS07EsEsKICAnUlNJJzogewogICAgdGl0bGU6ICdSU0kgKEfDtnJlY2VsaSBHw7zDpyBFbmRla3NpKScsCiAgICBkZXNjOiAnSGlzc2VuaW4gYcWfxLFyxLEgYWzEsW0gdmV5YSBhxZ/EsXLEsSBzYXTEsW0gYsO2bGdlc2luZGUgb2x1cCBvbG1hZMSxxJ/EsW7EsSBnw7ZzdGVyaXIuIDE0IGfDvG5sw7xrIGZpeWF0IGhhcmVrZXRsZXJpbmkgYW5hbGl6IGVkZXIuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J0HFn8SxcsSxIFNhdMSxbScsbWluOjAsbWF4OjMwLGNvbG9yOidncmVlbicsZGVzYzonRsSxcnNhdCBiw7ZsZ2VzaSDigJQgZml5YXQgw6dvayBkw7zFn23DvMWfJ30sCiAgICAgIHtsYWJlbDonTm9ybWFsJyxtaW46MzAsbWF4OjcwLGNvbG9yOid5ZWxsb3cnLGRlc2M6J07DtnRyIGLDtmxnZSd9LAogICAgICB7bGFiZWw6J0HFn8SxcsSxIEFsxLFtJyxtaW46NzAsbWF4OjEwMCxjb2xvcjoncmVkJyxkZXNjOidEaWtrYXQg4oCUIGZpeWF0IMOnb2sgecO8a3NlbG1pxZ8nfQogICAgXSwKICAgIGNhbnNsaW06ICdOIGtyaXRlcmkgaWxlIGlsZ2lsaSDigJQgZml5YXQgbW9tZW50dW11JwogIH0sCiAgJ1NNQTUwJzogewogICAgdGl0bGU6ICdTTUEgNTAgKDUwIEfDvG5sw7xrIEhhcmVrZXRsaSBPcnRhbGFtYSknLAogICAgZGVzYzogJ1NvbiA1MCBnw7xuw7xuIG9ydGFsYW1hIGthcGFuxLHFnyBmaXlhdMSxLiBLxLFzYS1vcnRhIHZhZGVsaSB0cmVuZCBnw7ZzdGVyZ2VzaS4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonw5x6ZXJpbmRlJyxjb2xvcjonZ3JlZW4nLGRlc2M6J0vEsXNhIHZhZGVsaSB0cmVuZCBwb3ppdGlmIOKAlCBnw7zDp2zDvCBzaW55YWwnfSwKICAgICAge2xhYmVsOidBbHTEsW5kYScsY29sb3I6J3JlZCcsZGVzYzonS8Sxc2EgdmFkZWxpIHRyZW5kIG5lZ2F0aWYnfQogICAgXSwKICAgIGNhbnNsaW06ICdNIGtyaXRlcmkg4oCUIHBpeWFzYSB0cmVuZGknCiAgfSwKICAnU01BMjAwJzogewogICAgdGl0bGU6ICdTTUEgMjAwICgyMDAgR8O8bmzDvGsgSGFyZWtldGxpIE9ydGFsYW1hKScsCiAgICBkZXNjOiAnU29uIDIwMCBnw7xuw7xuIG9ydGFsYW1hIGthcGFuxLHFnyBmaXlhdMSxLiBVenVuIHZhZGVsaSB0cmVuZCBnw7ZzdGVyZ2VzaS4gRW4gw7ZuZW1saSB0ZWtuaWsgc2V2aXllLicsCiAgICBzb3VyY2U6ICdUZWtuaWsgQW5hbGl6JywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOifDnHplcmluZGUnLGNvbG9yOidncmVlbicsZGVzYzonVXp1biB2YWRlbGkgYm/En2EgdHJlbmRpbmRlIOKAlCBDQU5TTElNIGnDp2luIMWfYXJ0J30sCiAgICAgIHtsYWJlbDonQWx0xLFuZGEnLGNvbG9yOidyZWQnLGRlc2M6J1V6dW4gdmFkZWxpIGF5xLEgdHJlbmRpbmRlIOKAlCBDQU5TTElNIGnDp2luIGdpcm1lJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTSBrcml0ZXJpIOKAlCB6b3J1bmx1IGtvxZ91bCcKICB9LAogICc1MlcnOiB7CiAgICB0aXRsZTogJzUyIEhhZnRhbMSxayBQb3ppc3lvbicsCiAgICBkZXNjOiAnSGlzc2VuaW4gc29uIDEgecSxbGRha2kgZml5YXQgYXJhbMSxxJ/EsW5kYSBuZXJlZGUgb2xkdcSfdW51IGfDtnN0ZXJpci4gMD15xLFsxLFuIGRpYmksIDEwMD15xLFsxLFuIHppcnZlc2kuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzAtMzAlJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1nEsWzEsW4gZGliaW5lIHlha8SxbiDigJQgcG90YW5zaXllbCBmxLFyc2F0J30sCiAgICAgIHtsYWJlbDonMzAtNzAlJyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIGLDtmxnZSDigJQgbsO2dHInfSwKICAgICAge2xhYmVsOic3MC04NSUnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1ppcnZleWUgeWFrbGHFn8SxeW9yIOKAlCBpemxlJ30sCiAgICAgIHtsYWJlbDonODUtMTAwJScsY29sb3I6J3JlZCcsZGVzYzonWmlydmV5ZSDDp29rIHlha8SxbiDigJQgZGlra2F0bGkgZ2lyJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTiBrcml0ZXJpIOKAlCB5ZW5pIHppcnZlIGvEsXLEsWzEsW3EsSBpw6dpbiBpZGVhbCBiw7ZsZ2UgJTg1LTEwMCcKICB9LAogICdIYWNpbSc6IHsKICAgIHRpdGxlOiAnSGFjaW0gKMSwxZ9sZW0gTWlrdGFyxLEpJywKICAgIGRlc2M6ICdHw7xubMO8ayBpxZ9sZW0gaGFjbWluaW4gc29uIDIwIGfDvG5sw7xrIG9ydGFsYW1heWEgb3JhbsSxLiBHw7zDp2zDvCBoYXJla2V0bGVyaW4gaGFjaW1sZSBkZXN0ZWtsZW5tZXNpIGdlcmVraXIuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J1nDvGtzZWsgKD4xLjN4KScsY29sb3I6J2dyZWVuJyxkZXNjOidLdXJ1bXNhbCBpbGdpIHZhciDigJQgZ8O8w6dsw7wgc2lueWFsJ30sCiAgICAgIHtsYWJlbDonTm9ybWFsICgwLjctMS4zeCknLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGFsYW1hIGlsZ2knfSwKICAgICAge2xhYmVsOidEw7zFn8O8ayAoPDAuN3gpJyxjb2xvcjoncmVkJyxkZXNjOifEsGxnaSBhemFsbcSxxZ8g4oCUIGRpa2thdCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ1Mga3JpdGVyaSDigJQgYXJ6L3RhbGVwIGRlbmdlc2knCiAgfSwKICAvLyBURU1FTAogICdGb3J3YXJkUEUnOiB7CiAgICB0aXRsZTogJ0ZvcndhcmQgUC9FICjEsGxlcml5ZSBEw7Zuw7xrIEZpeWF0L0themFuw6cpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gw7Zuw7xtw7x6ZGVraSAxMiBheWRha2kgdGFobWluaSBrYXphbmPEsW5hIGfDtnJlIGZpeWF0xLEuIFRyYWlsaW5nIFAvRVwnZGVuIGRhaGEgw7ZuZW1saSDDp8O8bmvDvCBnZWxlY2XEn2UgYmFrxLF5b3IuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgQW5hbGlzdCB0YWhtaW5pJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdBbmFsaXN0IHRhaG1pbmxlcmluZSBkYXlhbsSxciwgeWFuxLFsdMSxY8SxIG9sYWJpbGlyJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzwxNScsY29sb3I6J2dyZWVuJyxkZXNjOidVY3V6IOKAlCBiw7x5w7xtZSBiZWtsZW50aXNpIGTDvMWfw7xrIHZleWEgaGlzc2UgZGXEn2VyIGFsdMSxbmRhJ30sCiAgICAgIHtsYWJlbDonMTUtMjUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwg4oCUIMOnb8SfdSBzZWt0w7ZyIGnDp2luIG5vcm1hbCd9LAogICAgICB7bGFiZWw6JzI1LTQwJyxjb2xvcjoneWVsbG93JyxkZXNjOidQYWhhbMSxIGFtYSBiw7x5w7xtZSBwcmltaSDDtmRlbml5b3InfSwKICAgICAge2xhYmVsOic+NDAnLGNvbG9yOidyZWQnLGRlc2M6J8OHb2sgcGFoYWzEsSDigJQgecO8a3NlayBiw7x5w7xtZSBiZWtsZW50aXNpIGZpeWF0bGFubcSxxZ8nfQogICAgXSwKICAgIGNhbnNsaW06ICdDIHZlIEEga3JpdGVybGVyaSBpbGUgaWxnaWxpJwogIH0sCiAgJ1BFRyc6IHsKICAgIHRpdGxlOiAnUEVHIE9yYW7EsSAoRml5YXQvS2F6YW7Dpy9Cw7x5w7xtZSknLAogICAgZGVzYzogJ1AvRSBvcmFuxLFuxLEgYsO8ecO8bWUgaMSxesSxeWxhIGthcsWfxLFsYcWfdMSxcsSxci4gQsO8ecO8eWVuIMWfaXJrZXRsZXIgacOnaW4gUC9FXCdkZW4gZGFoYSBkb8SfcnUgZGXEn2VybGVtZSDDtmzDp8O8dMO8LiBQRUc9MSBhZGlsIGRlxJ9lciBrYWJ1bCBlZGlsaXIuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgQW5hbGlzdCB0YWhtaW5pJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdBbmFsaXN0IGLDvHnDvG1lIHRhaG1pbmxlcmluZSBkYXlhbsSxcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic8MS4wJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1VjdXog4oCUIGLDvHnDvG1lc2luZSBnw7ZyZSBkZcSfZXIgYWx0xLFuZGEnfSwKICAgICAge2xhYmVsOicxLjAtMS41Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J01ha3VsIOKAlCBhZGlsIGZpeWF0IGNpdmFyxLEnfSwKICAgICAge2xhYmVsOicxLjUtMi4wJyxjb2xvcjoneWVsbG93JyxkZXNjOidCaXJheiBwYWhhbMSxJ30sCiAgICAgIHtsYWJlbDonPjIuMCcsY29sb3I6J3JlZCcsZGVzYzonUGFoYWzEsSDigJQgZGlra2F0bGkgb2wnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIGLDvHnDvG1lIGthbGl0ZXNpJwogIH0sCiAgJ0VQU0dyb3d0aCc6IHsKICAgIHRpdGxlOiAnRVBTIELDvHnDvG1lc2kgKMOHZXlyZWtsaWssIFlvWSknLAogICAgZGVzYzogJ8WeaXJrZXRpbiBoaXNzZSBiYcWfxLFuYSBrYXphbmPEsW7EsW4gZ2XDp2VuIHnEsWzEsW4gYXluxLEgw6dleXJlxJ9pbmUgZ8O2cmUgYXJ0xLHFn8SxLiBDQU5TTElNXCdpbiBlbiBrcml0aWsga3JpdGVyaS4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMjUnLGNvbG9yOidncmVlbicsZGVzYzonR8O8w6dsw7wgYsO8ecO8bWUg4oCUIENBTlNMSU0ga3JpdGVyaSBrYXLFn8SxbGFuZMSxJ30sCiAgICAgIHtsYWJlbDonJTE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWkgYsO8ecO8bWUnfSwKICAgICAge2xhYmVsOiclMC0xNScsY29sb3I6J3llbGxvdycsZGVzYzonWmF5xLFmIGLDvHnDvG1lJ30sCiAgICAgIHtsYWJlbDonPDAnLGNvbG9yOidyZWQnLGRlc2M6J0themFuw6cgZMO8xZ/DvHlvciDigJQgZGlra2F0J30KICAgIF0sCiAgICBjYW5zbGltOiAnQyBrcml0ZXJpIOKAlCBlbiBrcml0aWsga3JpdGVyLCBtaW5pbXVtICUyNSBvbG1hbMSxJwogIH0sCiAgJ1Jldkdyb3d0aCc6IHsKICAgIHRpdGxlOiAnR2VsaXIgQsO8ecO8bWVzaSAoWW9ZKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIHNhdMSxxZ8vZ2VsaXJpbmluIGdlw6dlbiB5xLFsYSBnw7ZyZSBhcnTEscWfxLEuIEVQUyBiw7x5w7xtZXNpbmkgZGVzdGVrbGVtZXNpIGdlcmVraXIg4oCUIHNhZGVjZSBtYWxpeWV0IGtlc2ludGlzaXlsZSBiw7x5w7xtZSBzw7xyZMO8csO8bGViaWxpciBkZcSfaWwuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgR2Vyw6dlayB2ZXJpJywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic+JTE1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J0fDvMOnbMO8IGdlbGlyIGLDvHnDvG1lc2knfSwKICAgICAge2xhYmVsOiclNS0xNScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSBiw7x5w7xtZSd9LAogICAgICB7bGFiZWw6Jzw1Jyxjb2xvcjoncmVkJyxkZXNjOidHZWxpciBiw7x5w7xtZXNpIHphecSxZid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQgc8O8cmTDvHLDvGxlYmlsaXIgYsO8ecO8bWUgacOnaW4gxZ9hcnQnCiAgfSwKICAnTmV0TWFyZ2luJzogewogICAgdGl0bGU6ICdOZXQgTWFyamluJywKICAgIGRlc2M6ICdIZXIgMSQgZ2VsaXJkZW4gbmUga2FkYXIgbmV0IGvDonIga2FsZMSxxJ/EsW7EsSBnw7ZzdGVyaXIuIFnDvGtzZWsgbWFyamluID0gZ8O8w6dsw7wgacWfIG1vZGVsaS4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMjAnLGNvbG9yOidncmVlbicsZGVzYzonw4dvayBnw7zDp2zDvCBrw6JybMSxbMSxayd9LAogICAgICB7bGFiZWw6JyUxMC0yMCcsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpIGvDonJsxLFsxLFrJ30sCiAgICAgIHtsYWJlbDonJTUtMTAnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGEga8OicmzEsWzEsWsnfSwKICAgICAge2xhYmVsOic8NScsY29sb3I6J3JlZCcsZGVzYzonWmF5xLFmIGvDonJsxLFsxLFrJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQSBrcml0ZXJpIOKAlCBrw6JybMSxbMSxayBrYWxpdGVzaScKICB9LAogICdST0UnOiB7CiAgICB0aXRsZTogJ1JPRSAow5Z6a2F5bmFrIEvDonJsxLFsxLHEn8SxKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIMO2eiBzZXJtYXllc2l5bGUgbmUga2FkYXIga8OiciBldHRpxJ9pbmkgZ8O2c3RlcmlyLiBZw7xrc2VrIFJPRSA9IHNlcm1heWV5aSB2ZXJpbWxpIGt1bGxhbsSxeW9yLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUyNScsY29sb3I6J2dyZWVuJyxkZXNjOifDh29rIGfDvMOnbMO8IOKAlCBDQU5TTElNIGlkZWFsIHNldml5ZXNpJ30sCiAgICAgIHtsYWJlbDonJTE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWknfSwKICAgICAge2xhYmVsOiclOC0xNScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSd9LAogICAgICB7bGFiZWw6Jzw4Jyxjb2xvcjoncmVkJyxkZXNjOidaYXnEsWYnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIG1pbmltdW0gJTE3IG9sbWFsxLEnCiAgfSwKICAnR3Jvc3NNYXJnaW4nOiB7CiAgICB0aXRsZTogJ0Jyw7x0IE1hcmppbicsCiAgICBkZXNjOiAnU2F0xLHFnyBnZWxpcmluZGVuIMO8cmV0aW0gbWFsaXlldGkgZMO8xZ/DvGxkw7xrdGVuIHNvbnJhIGthbGFuIG9yYW4uIFNla3TDtnJlIGfDtnJlIGRlxJ9pxZ9pci4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lNTAnLGNvbG9yOidncmVlbicsZGVzYzonw4dvayBnw7zDp2zDvCDigJQgeWF6xLFsxLFtL1NhYVMgc2V2aXllc2knfSwKICAgICAge2xhYmVsOiclMzAtNTAnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSd9LAogICAgICB7bGFiZWw6JyUxNS0zMCcsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSDigJQgZG9uYW7EsW0veWFyxLEgaWxldGtlbiBub3JtYWwnfSwKICAgICAge2xhYmVsOic8MTUnLGNvbG9yOidyZWQnLGRlc2M6J0TDvMWfw7xrIG1hcmppbid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0vDonJsxLFsxLFrIGthbGl0ZXNpIGfDtnN0ZXJnZXNpJwogIH0sCiAgLy8gR8SwUsSwxZ4KICAnRW50cnlTY29yZSc6IHsKICAgIHRpdGxlOiAnR2lyacWfIEthbGl0ZXNpIFNrb3J1JywKICAgIGRlc2M6ICdSU0ksIFNNQSBwb3ppc3lvbnUsIFAvRSwgUEVHIHZlIEVQUyBiw7x5w7xtZXNpbmkgYmlybGXFn3RpcmVuIGJpbGXFn2lrIHNrb3IuIDAtMTAwIGFyYXPEsS4nLAogICAgc291cmNlOiAnQml6aW0gaGVzYXBsYW1hJywKICAgIHJlbGlhYmlsaXR5OiAnbG93JywKICAgIHdhcm5pbmc6ICdCVSBVWUdVTEFNQSBUQVJBRklOREFOIEhFU0FQTEFOQU4gS0FCQSBUQUhNxLBORMSwUi4gWWF0xLFyxLFtIGthcmFyxLEgacOnaW4gdGVrIGJhxZ/EsW5hIGt1bGxhbm1hLicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic3NS0xMDAnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgaWRlYWwgZ2lyacWfIGLDtmxnZXNpJ30sCiAgICAgIHtsYWJlbDonNjAtNzUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwgZml5YXQnfSwKICAgICAge2xhYmVsOic0NS02MCcsY29sb3I6J3llbGxvdycsZGVzYzonTsO2dHInfSwKICAgICAge2xhYmVsOiczMC00NScsY29sb3I6J3JlZCcsZGVzYzonUGFoYWzEsSDigJQgYmVrbGUnfSwKICAgICAge2xhYmVsOicwLTMwJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHBhaGFsxLEg4oCUIGdpcm1lJ30KICAgIF0sCiAgICBjYW5zbGltOiAnVMO8bSBrcml0ZXJsZXIgYmlsZcWfaW1pJwogIH0sCiAgJ1JSJzogewogICAgdGl0bGU6ICdSaXNrL8OWZMO8bCBPcmFuxLEgKFIvUiknLAogICAgZGVzYzogJ1BvdGFuc2l5ZWwga2F6YW5jxLFuIHJpc2tlIG9yYW7EsS4gMToyIGRlbWVrIDEkIHJpc2tlIGthcsWfxLEgMiQga2F6YW7DpyBwb3RhbnNpeWVsaSB2YXIgZGVtZWsuJywKICAgIHNvdXJjZTogJ0JpemltIGhlc2FwbGFtYScsCiAgICByZWxpYWJpbGl0eTogJ2xvdycsCiAgICB3YXJuaW5nOiAnR2lyacWfL2hlZGVmL3N0b3Agc2V2aXllbGVyaSBmb3Jtw7xsIGJhemzEsSBrYWJhIHRhaG1pbmRpcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOicxOjMrJyxjb2xvcjonZ3JlZW4nLGRlc2M6J03DvGtlbW1lbCDigJQgZ8O8w6dsw7wgZ2lyacWfIHNpbnlhbGknfSwKICAgICAge2xhYmVsOicxOjInLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSDigJQgbWluaW11bSBrYWJ1bCBlZGlsZWJpbGlyJ30sCiAgICAgIHtsYWJlbDonMToxJyxjb2xvcjoneWVsbG93JyxkZXNjOidaYXnEsWYnfSwKICAgICAge2xhYmVsOic8MToxJyxjb2xvcjoncmVkJyxkZXNjOidSaXNrIGthemFuw6d0YW4gYsO8ecO8ayDigJQgZ2lybWUnfQogICAgXSwKICAgIGNhbnNsaW06ICdSaXNrIHnDtm5ldGltaScKICB9LAogIC8vIEVBUk5JTkdTCiAgJ0Vhcm5pbmdzRGF0ZSc6IHsKICAgIHRpdGxlOiAnUmFwb3IgVGFyaWhpIChFYXJuaW5ncyBEYXRlKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIMOnZXlyZWsgZmluYW5zYWwgc29udcOnbGFyxLFuxLEgYcOnxLFrbGF5YWNhxJ/EsSB0YXJpaC4gUmFwb3Igw7ZuY2VzaSB2ZSBzb25yYXPEsSBmaXlhdCBzZXJ0IGhhcmVrZXQgZWRlYmlsaXIuJywKICAgIHNvdXJjZTogJ3lmaW5hbmNlIOKAlCBiYXplbiBoYXRhbMSxIG9sYWJpbGlyJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdUYXJpaGxlcmkgcmVzbWkgSVIgc2F5ZmFzxLFuZGFuIGRvxJ9ydWxhecSxbicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic3IGfDvG4gacOnaW5kZScsY29sb3I6J3JlZCcsZGVzYzonw4dvayB5YWvEsW4g4oCUIHBvemlzeW9uIGHDp21hayByaXNrbGknfSwKICAgICAge2xhYmVsOic4LTE0IGfDvG4nLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1lha8SxbiDigJQgZGlra2F0bGkgb2wnfSwKICAgICAge2xhYmVsOicxNCsgZ8O8bicsY29sb3I6J2dyZWVuJyxkZXNjOidZZXRlcmxpIHPDvHJlIHZhcid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Mga3JpdGVyaSDigJQgw6dleXJlayByYXBvciBrYWxpdGVzaScKICB9LAogICdBdmdNb3ZlJzogewogICAgdGl0bGU6ICdPcnRhbGFtYSBSYXBvciBIYXJla2V0aScsCiAgICBkZXNjOiAnU29uIDQgw6dleXJlayByYXBvcnVuZGEsIHJhcG9yIGfDvG7DvCB2ZSBlcnRlc2kgZ8O8biBmaXlhdMSxbiBvcnRhbGFtYSBuZSBrYWRhciBoYXJla2V0IGV0dGnEn2kuJywKICAgIHNvdXJjZTogJ0JpemltIGhlc2FwbGFtYScsCiAgICByZWxpYWJpbGl0eTogJ21lZGl1bScsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOidQb3ppdGlmICg+JTUpJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8WeaXJrZXQgZ2VuZWxsaWtsZSBiZWtsZW50aXlpIGHFn8SxeW9yJ30sCiAgICAgIHtsYWJlbDonTsO2dHIgKCUwLTUpJyxjb2xvcjoneWVsbG93JyxkZXNjOidLYXLEscWfxLFrIGdlw6dtacWfJ30sCiAgICAgIHtsYWJlbDonTmVnYXRpZicsY29sb3I6J3JlZCcsZGVzYzonUmFwb3IgZMO2bmVtaW5kZSBmaXlhdCBnZW5lbGxpa2xlIGTDvMWfw7x5b3Ig4oCUIGRpa2thdCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Mga3JpdGVyaSDigJQga2F6YW7DpyBzw7xycHJpemkgZ2XDp21pxZ9pJwogIH0KfTsKCmZ1bmN0aW9uIHNob3dJbmZvKGtleSxldmVudCl7CiAgaWYoZXZlbnQpIGV2ZW50LnN0b3BQcm9wYWdhdGlvbigpOwogIHZhciBtPU1FVFJJQ1Nba2V5XTsgaWYoIW0pIHJldHVybjsKICB2YXIgcmVsTGFiZWw9bS5yZWxpYWJpbGl0eT09PSJoaWdoIj8iR8O8dmVuaWxpciI6bS5yZWxpYWJpbGl0eT09PSJtZWRpdW0iPyJPcnRhIEfDvHZlbmlsaXIiOiJLYWJhIFRhaG1pbiI7CiAgdmFyIGg9JzxkaXYgY2xhc3M9Im1pbmZvLXRpdGxlIj4nK20udGl0bGUrJzwvZGl2Pic7CiAgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLXNvdXJjZSI+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+JyttLnNvdXJjZSsnPC9zcGFuPjxzcGFuIGNsYXNzPSJtaW5mby1yZWwgJyttLnJlbGlhYmlsaXR5KyciPicrcmVsTGFiZWwrJzwvc3Bhbj48L2Rpdj4nOwogIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby1kZXNjIj4nK20uZGVzYysnPC9kaXY+JzsKICBpZihtLndhcm5pbmcpIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby13YXJuaW5nIj7imqDvuI8gJyttLndhcm5pbmcrJzwvZGl2Pic7CiAgaWYobS5yYW5nZXMmJm0ucmFuZ2VzLmxlbmd0aCl7CiAgICBoKz0nPGRpdiBjbGFzcz0ibWluZm8tcmFuZ2VzIj48ZGl2IGNsYXNzPSJtaW5mby1yYW5nZS10aXRsZSI+UmVmZXJhbnMgRGVnZXJsZXI8L2Rpdj4nOwogICAgbS5yYW5nZXMuZm9yRWFjaChmdW5jdGlvbihyKXt2YXIgZGM9ci5jb2xvcj09PSJncmVlbiI/IiMxMGI5ODEiOnIuY29sb3I9PT0icmVkIj8iI2VmNDQ0NCI6IiNmNTllMGIiO2grPSc8ZGl2IGNsYXNzPSJtaW5mby1yYW5nZSI+PGRpdiBjbGFzcz0ibWluZm8tcmFuZ2UtZG90IiBzdHlsZT0iYmFja2dyb3VuZDonK2RjKyciPjwvZGl2PjxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOicrZGMrJyI+JytyLmxhYmVsKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrci5kZXNjKyc8L2Rpdj48L2Rpdj48L2Rpdj4nO30pOwogICAgaCs9JzwvZGl2Pic7CiAgfQogIGlmKG0uY2Fuc2xpbSkgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLWNhbnNsaW0iPvCfk4ogQ0FOU0xJTTogJyttLmNhbnNsaW0rJzwvZGl2Pic7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvQ29udGVudCIpLmlubmVySFRNTD1oOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwp9CmZ1bmN0aW9uIGNsb3NlSW5mb1BvcHVwKGUpe2lmKCFlfHxlLnRhcmdldD09PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikpe2RvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpO319Cgo8L3NjcmlwdD4KPHNjcmlwdD4KdmFyIFRGX0RBVEE9JSVURl9EQVRBJSU7CnZhciBQT1JUPSUlUE9SVCUlOwp2YXIgRUFSTklOR1NfREFUQT0lJUVBUk5JTkdTX0RBVEElJTsKdmFyIE1BUktFVF9EQVRBPSUlTUFSS0VUX0RBVEElJTsKdmFyIE5FV1NfREFUQT0lJU5FV1NfREFUQSUlOwp2YXIgQUlfREFUQT0lJUFJX0RBVEElJTsKdmFyIFdFRUtMWV9EQVRBPSUlV0VFS0xZX0RBVEElJTsKdmFyIGN1clRhYj0iYWxsIixjdXJUZj0iMWQiLGN1ckRhdGE9VEZfREFUQVsiMWQiXS5zbGljZSgpOwp2YXIgbWluaUNoYXJ0cz17fSxtQ2hhcnQ9bnVsbDsKdmFyIFNTPXsKICAiR1VDTFUgQUwiOntiZzoicmdiYSgxNiwxODUsMTI5LC4xMikiLGJkOiJyZ2JhKDE2LDE4NSwxMjksLjM1KSIsdHg6IiMxMGI5ODEiLGFjOiIjMTBiOTgxIixsYmw6IkdVQ0xVIEFMIn0sCiAgIkFMIjp7Ymc6InJnYmEoNTIsMjExLDE1MywuMSkiLGJkOiJyZ2JhKDUyLDIxMSwxNTMsLjMpIix0eDoiIzM0ZDM5OSIsYWM6IiMzNGQzOTkiLGxibDoiQUwifSwKICAiRElLS0FUIjp7Ymc6InJnYmEoMjQ1LDE1OCwxMSwuMSkiLGJkOiJyZ2JhKDI0NSwxNTgsMTEsLjMpIix0eDoiI2Y1OWUwYiIsYWM6IiNmNTllMGIiLGxibDoiRElLS0FUIn0sCiAgIlpBWUlGIjp7Ymc6InJnYmEoMTA3LDExNCwxMjgsLjEpIixiZDoicmdiYSgxMDcsMTE0LDEyOCwuMykiLHR4OiIjOWNhM2FmIixhYzoiIzZiNzI4MCIsbGJsOiJaQVlJRiJ9LAogICJTQVQiOntiZzoicmdiYSgyMzksNjgsNjgsLjEyKSIsYmQ6InJnYmEoMjM5LDY4LDY4LC4zNSkiLHR4OiIjZWY0NDQ0IixhYzoiI2VmNDQ0NCIsbGJsOiJTQVQifQp9OwoKZnVuY3Rpb24gaWIoa2V5LGxhYmVsKXsKICByZXR1cm4gbGFiZWwrJyA8c3BhbiBjbGFzcz0ibWluZm8iIG9uY2xpY2s9InNob3dJbmZvKFwnJytrZXkrJ1wnLGV2ZW50KSI+Pzwvc3Bhbj4nOwp9CgpmdW5jdGlvbiBzZXRUYWIodCxlbCl7CiAgY3VyVGFiPXQ7CiAgZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbCgiLnRhYiIpLmZvckVhY2goZnVuY3Rpb24oYil7Yi5jbGFzc0xpc3QucmVtb3ZlKCJhY3RpdmUiKTt9KTsKICBlbC5jbGFzc0xpc3QuYWRkKCJhY3RpdmUiKTsKICB2YXIgdGZSb3c9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInRmUm93Iik7CiAgaWYodGZSb3cpIHRmUm93LnN0eWxlLmRpc3BsYXk9KHQ9PT0iZGFzaGJvYXJkInx8dD09PSJlYXJuaW5ncyJ8fHQ9PT0icnV0aW4ifHx0PT09ImhhZnRhbGlrIik/Im5vbmUiOiJmbGV4IjsKICBpZih0PT09ImRhc2hib2FyZCIpIHJlbmRlckRhc2hib2FyZCgpOwogIGVsc2UgaWYodD09PSJlYXJuaW5ncyIpIHJlbmRlckVhcm5pbmdzKCk7CiAgZWxzZSBpZih0PT09InJ1dGluIikgcmVuZGVyUnV0aW4oKTsKICBlbHNlIGlmKHQ9PT0iaGFmdGFsaWsiKSByZW5kZXJIYWZ0YWxpaygpOwogIGVsc2UgcmVuZGVyR3JpZCgpOwp9CgpmdW5jdGlvbiBzZXRUZih0ZixlbCl7CiAgY3VyVGY9dGY7CiAgZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbCgiLnRmLWJ0biIpLmZvckVhY2goZnVuY3Rpb24oYil7Yi5jbGFzc0xpc3QudG9nZ2xlKCJhY3RpdmUiLGIuZGF0YXNldC50Zj09PXRmKTt9KTsKICBjdXJEYXRhPShURl9EQVRBW3RmXXx8VEZfREFUQVsiMWQiXSkuc2xpY2UoKTsKICByZW5kZXJTdGF0cygpOwogIHJlbmRlckdyaWQoKTsKfQoKZnVuY3Rpb24gZmlsdGVyZWQoKXsKICB2YXIgZD1jdXJEYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KTsKICBpZihjdXJUYWI9PT0icG9ydCIpIHJldHVybiBkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gUE9SVC5pbmNsdWRlcyhyLnRpY2tlcik7fSk7CiAgaWYoY3VyVGFiPT09ImJ1eSIpIHJldHVybiBkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0iR1VDTFUgQUwifHxyLnNpbnlhbD09PSJBTCI7fSk7CiAgaWYoY3VyVGFiPT09InNlbGwiKSByZXR1cm4gZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09IlNBVCI7fSk7CiAgcmV0dXJuIGQ7Cn0KCmZ1bmN0aW9uIHJlbmRlclN0YXRzKCl7CiAgdmFyIGQ9Y3VyRGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSk7CiAgdmFyIGNudD17fTsKICBkLmZvckVhY2goZnVuY3Rpb24ocil7Y250W3Iuc2lueWFsXT0oY250W3Iuc2lueWFsXXx8MCkrMTt9KTsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgic3RhdHMiKS5pbm5lckhUTUw9CiAgICAnPGRpdiBjbGFzcz0icGlsbCBnIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2Pkd1Y2x1IEFsOiAnKyhjbnRbIkdVQ0xVIEFMIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgZyI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5BbDogJysoY250WyJBTCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIHkiPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+RGlra2F0OiAnKyhjbnRbIkRJS0tBVCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIHIiPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+U2F0OiAnKyhjbnRbIlNBVCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIGIiIHN0eWxlPSJtYXJnaW4tbGVmdDphdXRvIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PlBvcnRmb2x5bzogJytQT1JULmxlbmd0aCsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIG0iPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+JytkLmxlbmd0aCsnIGFuYWxpejwvZGl2Pic7Cn0KCmZ1bmN0aW9uIHJlbmRlckdyaWQoKXsKICBPYmplY3QudmFsdWVzKG1pbmlDaGFydHMpLmZvckVhY2goZnVuY3Rpb24oYyl7Yy5kZXN0cm95KCk7fSk7CiAgbWluaUNoYXJ0cz17fTsKICB2YXIgZj1maWx0ZXJlZCgpOwogIHZhciBncmlkPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJncmlkIik7CiAgaWYoIWYubGVuZ3RoKXtncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMTt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjQwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5IaXNzZSBidWx1bmFtYWRpPC9kaXY+JztyZXR1cm47fQogIGdyaWQuaW5uZXJIVE1MPWYubWFwKGZ1bmN0aW9uKHIpe3JldHVybiBidWlsZENhcmQocik7fSkuam9pbigiIik7CiAgZi5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgdmFyIGN0eD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWMtIityLnRpY2tlcik7CiAgICBpZihjdHgmJnIuY2hhcnRfY2xvc2VzJiZyLmNoYXJ0X2Nsb3Nlcy5sZW5ndGgpewogICAgICB2YXIgc3M9U1Nbci5zaW55YWxdfHxTU1siRElLS0FUIl07CiAgICAgIG1pbmlDaGFydHNbIm0iK3IudGlja2VyXT1uZXcgQ2hhcnQoY3R4LHt0eXBlOiJsaW5lIixkYXRhOntsYWJlbHM6ci5jaGFydF9kYXRlcyxkYXRhc2V0czpbe2RhdGE6ci5jaGFydF9jbG9zZXMsYm9yZGVyQ29sb3I6c3MuYWMsYm9yZGVyV2lkdGg6MS41LGZpbGw6dHJ1ZSxiYWNrZ3JvdW5kQ29sb3I6c3MuYWMrIjE4Iixwb2ludFJhZGl1czowLHRlbnNpb246MC40fV19LG9wdGlvbnM6e3BsdWdpbnM6e2xlZ2VuZDp7ZGlzcGxheTpmYWxzZX19LHNjYWxlczp7eDp7ZGlzcGxheTpmYWxzZX0seTp7ZGlzcGxheTpmYWxzZX19LGFuaW1hdGlvbjp7ZHVyYXRpb246NTAwfSxyZXNwb25zaXZlOnRydWUsbWFpbnRhaW5Bc3BlY3RSYXRpbzpmYWxzZX19KTsKICAgIH0KICB9KTsKfQoKZnVuY3Rpb24gYnVpbGRDYXJkKHIpewogIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICB2YXIgZGM9ci5kZWdpc2ltPj0wPyJ2YXIoLS1ncmVlbjIpIjoidmFyKC0tcmVkMikiOwogIHZhciBkcz0oci5kZWdpc2ltPj0wPyIrIjoiIikrci5kZWdpc2ltKyIlIjsKICB2YXIgZXNjb2w9ci5lbnRyeV9zY29yZT49NzU/InZhcigtLWdyZWVuKSI6ci5lbnRyeV9zY29yZT49NjA/InZhcigtLWdyZWVuMikiOnIuZW50cnlfc2NvcmU+PTQ1PyJ2YXIoLS15ZWxsb3cpIjpyLmVudHJ5X3Njb3JlPj0zMD8idmFyKC0tcmVkMikiOiJ2YXIoLS1yZWQpIjsKICB2YXIgcHZjb2w9ci5wcmljZV92c19jb2xvcj09PSJncmVlbiI/InZhcigtLWdyZWVuKSI6ci5wcmljZV92c19jb2xvcj09PSJ5ZWxsb3ciPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkMikiOwogIHZhciBzaWdzPVsKICAgIHtsOiJUcmVuZCIsdjpyLnRyZW5kPT09Ill1a3NlbGVuIj8iWXVrc2VsaXlvciI6ci50cmVuZD09PSJEdXNlbiI/IkR1c3V5b3IiOiJZYXRheSIsZzpyLnRyZW5kPT09Ill1a3NlbGVuIj90cnVlOnIudHJlbmQ9PT0iRHVzZW4iP2ZhbHNlOm51bGx9LAogICAge2w6IlNNQTUwIix2OnIuYWJvdmU1MD8iVXplcmluZGUiOiJBbHRpbmRhIixnOnIuYWJvdmU1MH0sCiAgICB7bDoiU01BMjAwIix2OnIuYWJvdmUyMDA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIsZzpyLmFib3ZlMjAwfSwKICAgIHtsOiJSU0kiLHY6ci5yc2l8fCI/IixnOnIucnNpP3IucnNpPDMwP3RydWU6ci5yc2k+NzA/ZmFsc2U6bnVsbDpudWxsfSwKICAgIHtsOiI1MlciLHY6IiUiK3IucGN0X2Zyb21fNTJ3KyIgdXphayIsZzpyLm5lYXJfNTJ3fQogIF0ubWFwKGZ1bmN0aW9uKHMpe3JldHVybiAnPHNwYW4gY2xhc3M9InNwICcrKHMuZz09PXRydWU/InNnIjpzLmc9PT1mYWxzZT8ic2IiOiJzbiIpKyciPicrcy5sKyI6ICIrcy52KyI8L3NwYW4+Ijt9KS5qb2luKCIiKTsKICByZXR1cm4gJzxkaXYgY2xhc3M9ImNhcmQiIHN0eWxlPSJib3JkZXItY29sb3I6Jysoci5wb3J0Zm9saW8/InJnYmEoMTYsMTg1LDEyOSwuMjUpIjpzcy5iZCkrJyIgb25jbGljaz0ib3Blbk0oXCcnK3IudGlja2VyKydcJykiPicKICAgICsnPGRpdiBjbGFzcz0iYWNjZW50IiBzdHlsZT0iYmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoOTBkZWcsJytzcy5hYysnLCcrc3MuYWMrJzg4KSI+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJjYm9keSI+PGRpdiBjbGFzcz0iY3RvcCI+PGRpdj48ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo0cHgiPicKICAgICsnPHNwYW4gY2xhc3M9InRpY2tlciIgc3R5bGU9ImNvbG9yOicrc3MudHgrJyI+JytyLnRpY2tlcisnPC9zcGFuPicKICAgICsoci5wb3J0Zm9saW8/JzxzcGFuIGNsYXNzPSJwb3J0LWJhZGdlIj5QPC9zcGFuPic6JycpKwogICAgJzwvZGl2PjxzcGFuIGNsYXNzPSJiYWRnZSIgc3R5bGU9ImJhY2tncm91bmQ6Jytzcy5iZysnO2NvbG9yOicrc3MudHgrJztib3JkZXI6MXB4IHNvbGlkICcrc3MuYmQrJyI+Jytzcy5sYmwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImNwciI+PGRpdiBjbGFzcz0icHZhbCI+JCcrci5maXlhdCsnPC9kaXY+PGRpdiBjbGFzcz0icGNoZyIgc3R5bGU9ImNvbG9yOicrZGMrJyI+JytkcysnPC9kaXY+JwogICAgKyhyLnBlX2Z3ZD8nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkZ3ZFBFOicrci5wZV9md2QudG9GaXhlZCgxKSsnPC9kaXY+JzonJykKICAgICsnPC9kaXY+PC9kaXY+PGRpdiBjbGFzcz0ic2lncyI+JytzaWdzKyc8L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9Im1hcmdpbi10b3A6NnB4Ij4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjNweCI+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5HaXJpcyBLYWxpdGVzaTwvc3Bhbj48c3BhbiBzdHlsZT0iZm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X3Njb3JlKycvMTAwPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iaGVpZ2h0OjRweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czoycHg7b3ZlcmZsb3c6aGlkZGVuIj48ZGl2IHN0eWxlPSJoZWlnaHQ6MTAwJTt3aWR0aDonK3IuZW50cnlfc2NvcmUrJyU7YmFja2dyb3VuZDonK2VzY29sKyc7Ym9yZGVyLXJhZGl1czoycHgiPjwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi10b3A6M3B4Ij48c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK2VzY29sKyciPicrci5lbnRyeV9sYWJlbCsnPC9zcGFuPjxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrcHZjb2wrJyI+JytyLnByaWNlX3ZzX2lkZWFsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8L2Rpdj48ZGl2IGNsYXNzPSJjaGFydC13Ij48Y2FudmFzIGlkPSJtYy0nK3IudGlja2VyKyciPjwvY2FudmFzPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0ibHZscyI+JwogICAgKyc8ZGl2IGNsYXNzPSJsdiI+PGRpdiBjbGFzcz0ibGwiPkhlbWVuIEdpcjwvZGl2PjxkaXYgY2xhc3M9Imx2YWwiIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbjIpIj4kJytyLmVudHJ5X2FnZ3Jlc3NpdmUrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0ibHYiPjxkaXYgY2xhc3M9ImxsIj5IZWRlZjwvZGl2PjxkaXYgY2xhc3M9Imx2YWwiIHN0eWxlPSJjb2xvcjojNjBhNWZhIj4kJytyLmhlZGVmKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9Imx2Ij48ZGl2IGNsYXNzPSJsbCI+U3RvcDwvZGl2PjxkaXYgY2xhc3M9Imx2YWwiIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKSI+JCcrci5zdG9wKyc8L2Rpdj48L2Rpdj4nCiAgICArJzwvZGl2PjwvZGl2PjwvZGl2Pic7Cn0KCmZ1bmN0aW9uIHJlbmRlckRhc2hib2FyZCgpewogIHZhciBncmlkPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJncmlkIik7CiAgdmFyIG1kPU1BUktFVF9EQVRBfHx7fTsKICB2YXIgc3A9bWQuU1A1MDB8fHt9OwogIHZhciBuYXM9bWQuTkFTREFRfHx7fTsKICB2YXIgdml4PW1kLlZJWHx8e307CiAgdmFyIG1TaWduYWw9bWQuTV9TSUdOQUx8fCJOT1RSIjsKICB2YXIgbUxhYmVsPW1kLk1fTEFCRUx8fCJWZXJpIHlvayI7CiAgdmFyIG1Db2xvcj1tU2lnbmFsPT09IkdVQ0xVIj8idmFyKC0tZ3JlZW4pIjptU2lnbmFsPT09IlpBWUlGIj8idmFyKC0tcmVkMikiOiJ2YXIoLS15ZWxsb3cpIjsKICB2YXIgbUJnPW1TaWduYWw9PT0iR1VDTFUiPyJyZ2JhKDE2LDE4NSwxMjksLjA4KSI6bVNpZ25hbD09PSJaQVlJRiI/InJnYmEoMjM5LDY4LDY4LC4wOCkiOiJyZ2JhKDI0NSwxNTgsMTEsLjA4KSI7CiAgdmFyIG1Cb3JkZXI9bVNpZ25hbD09PSJHVUNMVSI/InJnYmEoMTYsMTg1LDEyOSwuMjUpIjptU2lnbmFsPT09IlpBWUlGIj8icmdiYSgyMzksNjgsNjgsLjI1KSI6InJnYmEoMjQ1LDE1OCwxMSwuMjUpIjsKICB2YXIgbUljb249bVNpZ25hbD09PSJHVUNMVSI/IuKchSI6bVNpZ25hbD09PSJaQVlJRiI/IuKdjCI6IuKaoO+4jyI7CgogIGZ1bmN0aW9uIGluZGV4Q2FyZChuYW1lLGRhdGEpewogICAgaWYoIWRhdGF8fCFkYXRhLnByaWNlKSByZXR1cm4gIiI7CiAgICB2YXIgY2M9ZGF0YS5jaGFuZ2U+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgICB2YXIgY3M9KGRhdGEuY2hhbmdlPj0wPyIrIjoiIikrZGF0YS5jaGFuZ2UrIiUiOwogICAgdmFyIHM1MD1kYXRhLmFib3ZlNTA/JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjEwcHgiPlNNQTUwIOKckzwvc3Bhbj4nOic8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMik7Zm9udC1zaXplOjEwcHgiPlNNQTUwIOKclzwvc3Bhbj4nOwogICAgdmFyIHMyMDA9ZGF0YS5hYm92ZTIwMD8nPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6MTBweCI+U01BMjAwIOKckzwvc3Bhbj4nOic8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMik7Zm9udC1zaXplOjEwcHgiPlNNQTIwMCDinJc8L3NwYW4+JzsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4IDE2cHg7ZmxleDoxO21pbi13aWR0aDoxNTBweCI+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjZweCI+JytuYW1lKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KSI+JCcrZGF0YS5wcmljZSsnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTNweDtjb2xvcjonK2NjKyc7bWFyZ2luLWJvdHRvbTo4cHgiPicrY3MrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjhweCI+JytzNTArczIwMCsnPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciBwb3J0RGF0YT1jdXJEYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YSYmUE9SVC5pbmNsdWRlcyhyLnRpY2tlcik7fSk7CiAgdmFyIHBvcnRIdG1sPSIiOwogIGlmKHBvcnREYXRhLmxlbmd0aCl7CiAgICBwb3J0SHRtbD0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTRweCI+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTJweCI+8J+SvCBQb3J0ZsO2eSDDlnpldGk8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgxNDBweCwxZnIpKTtnYXA6OHB4Ij4nOwogICAgcG9ydERhdGEuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgICAgdmFyIGRjPXIuZGVnaXNpbT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICAgICAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogICAgICBwb3J0SHRtbCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkICcrc3MuYmQrJztib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHg7Y3Vyc29yOnBvaW50ZXIiIG9uY2xpY2s9Im9wZW5NKFwnJytyLnRpY2tlcisnXCcpIj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToxNnB4O2xldHRlci1zcGFjaW5nOjJweDtjb2xvcjonK3NzLnR4KyciPicrci50aWNrZXIrJzwvc3Bhbj4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtiYWNrZ3JvdW5kOicrc3MuYmcrJztjb2xvcjonK3NzLnR4Kyc7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6MnB4Ij4nK3NzLmxibCsnPC9zcGFuPjwvZGl2PicKICAgICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDAiPiQnK3IuZml5YXQrJzwvZGl2PicKICAgICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTFweDtjb2xvcjonK2RjKyciPicrKHIuZGVnaXNpbT49MD8iKyI6IiIpK3IuZGVnaXNpbSsnJTwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICAgIHBvcnRIdG1sKz0nPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciB1cmdlbnRFYXJuaW5ncz1FQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gZS5hbGVydD09PSJyZWQifHxlLmFsZXJ0PT09InllbGxvdyI7fSk7CiAgdmFyIGVhcm5pbmdzQWxlcnQ9IiI7CiAgaWYodXJnZW50RWFybmluZ3MubGVuZ3RoKXsKICAgIGVhcm5pbmdzQWxlcnQ9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE0cHggMTZweDttYXJnaW4tYm90dG9tOjE0cHgiPicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS15ZWxsb3cpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7imqDvuI8gWWFrbGHFn2FuIFJhcG9ybGFyPC9kaXY+JzsKICAgIHVyZ2VudEVhcm5pbmdzLmZvckVhY2goZnVuY3Rpb24oZSl7CiAgICAgIHZhciBpYz1lLmFsZXJ0PT09InJlZCI/IvCflLQiOiLwn5+hIjsKICAgICAgZWFybmluZ3NBbGVydCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbTo2cHg7Zm9udC1zaXplOjEycHgiPicKICAgICAgICArJzxzcGFuPicraWMrJyA8c3Ryb25nPicrZS50aWNrZXIrJzwvc3Ryb25nPjwvc3Bhbj4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj4nK2UubmV4dF9kYXRlKycgKCcrKGUuZGF5c190b19lYXJuaW5ncz09PTA/IkJVR8OcTiI6ZS5kYXlzX3RvX2Vhcm5pbmdzKyIgZ8O8biIpKycpPC9zcGFuPjwvZGl2Pic7CiAgICB9KTsKICAgIGVhcm5pbmdzQWxlcnQrPSc8L2Rpdj4nOwogIH0KCiAgdmFyIG5ld3NIdG1sPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHgiPicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMnB4Ij7wn5OwIFNvbiBIYWJlcmxlcjwvZGl2Pic7CiAgaWYoTkVXU19EQVRBJiZORVdTX0RBVEEubGVuZ3RoKXsKICAgIE5FV1NfREFUQS5zbGljZSgwLDEwKS5mb3JFYWNoKGZ1bmN0aW9uKG4pewogICAgICB2YXIgcGI9bi5wb3J0Zm9saW8/JzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTIpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMjUpO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMCI+UDwvc3Bhbj4nOiIiOwogICAgICB2YXIgdGE9IiI7CiAgICAgIGlmKG4uZGF0ZXRpbWUpe3ZhciBkaWZmPU1hdGguZmxvb3IoKERhdGUubm93KCkvMTAwMC1uLmRhdGV0aW1lKS8zNjAwKTt0YT1kaWZmPDI0PyhkaWZmKyJzIMO2bmNlIik6KE1hdGguZmxvb3IoZGlmZi8yNCkrImcgw7ZuY2UiKTt9CiAgICAgIG5ld3NIdG1sKz0nPGRpdiBzdHlsZT0icGFkZGluZzoxMHB4IDA7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDQpIj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo2cHg7bWFyZ2luLWJvdHRvbTo0cHgiPicKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0teWVsbG93KSI+JytuLnRpY2tlcisnPC9zcGFuPicrcGIKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tbGVmdDphdXRvIj4nK3RhKyc8L3NwYW4+PC9kaXY+JwogICAgICAgICsnPGEgaHJlZj0iJytuLnVybCsnIiB0YXJnZXQ9Il9ibGFuayIgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLXRleHQpO3RleHQtZGVjb3JhdGlvbjpub25lO2xpbmUtaGVpZ2h0OjEuNTtkaXNwbGF5OmJsb2NrIj4nK24uaGVhZGxpbmUrJzwvYT4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLXRvcDozcHgiPicrbi5zb3VyY2UrJzwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICB9IGVsc2UgewogICAgbmV3c0h0bWwrPSc8ZGl2IHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1zaXplOjEycHgiPkhhYmVyIGJ1bHVuYW1hZGk8L2Rpdj4nOwogIH0KICBuZXdzSHRtbCs9JzwvZGl2Pic7CgogIGdyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nCiAgICArJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JyttQmcrJztib3JkZXI6MXB4IHNvbGlkICcrbUJvcmRlcisnO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTJweCI+JwogICAgKyc8ZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7bWFyZ2luLWJvdHRvbTo0cHgiPkNBTlNMSU0gTSBLUsSwVEVSxLA8L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK21Db2xvcisnIj4nK21JY29uKycgJyttTGFiZWwrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO3RleHQtYWxpZ246cmlnaHQiPlZJWDogJysodml4LnByaWNlfHwiPyIpKyc8YnI+JwogICAgKyc8c3BhbiBzdHlsZT0iY29sb3I6Jysodml4LnByaWNlJiZ2aXgucHJpY2U+MjU/InZhcigtLXJlZDIpIjoidmFyKC0tZ3JlZW4pIikrJyI+Jysodml4LnByaWNlJiZ2aXgucHJpY2U+MjU/IlnDvGtzZWsgdm9sYXRpbGl0ZSI6Ik5vcm1hbCB2b2xhdGlsaXRlIikrJzwvc3Bhbj48L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcDttYXJnaW4tYm90dG9tOjE0cHgiPicraW5kZXhDYXJkKCJTJlAgNTAwIChTUFkpIixzcCkraW5kZXhDYXJkKCJOQVNEQVEgKFFRUSkiLG5hcykrJzwvZGl2PicKICAgICtwb3J0SHRtbCtlYXJuaW5nc0FsZXJ0K25ld3NIdG1sKyc8L2Rpdj4nOwp9CgpmdW5jdGlvbiByZW5kZXJFYXJuaW5ncygpewogIHZhciBncmlkPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJncmlkIik7CiAgdmFyIHNvcnRlZD1FQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gZS5uZXh0X2RhdGU7fSkuc29ydChmdW5jdGlvbihhLGIpewogICAgdmFyIGRhPWEuZGF5c190b19lYXJuaW5ncyE9bnVsbD9hLmRheXNfdG9fZWFybmluZ3M6OTk5OwogICAgdmFyIGRiPWIuZGF5c190b19lYXJuaW5ncyE9bnVsbD9iLmRheXNfdG9fZWFybmluZ3M6OTk5OwogICAgcmV0dXJuIGRhLWRiOwogIH0pOwogIHZhciBub0RhdGU9RUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuICFlLm5leHRfZGF0ZTt9KTsKICBpZighc29ydGVkLmxlbmd0aCYmIW5vRGF0ZS5sZW5ndGgpe2dyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xO3RleHQtYWxpZ246Y2VudGVyO3BhZGRpbmc6NDBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkVhcm5pbmdzIHZlcmlzaSBidWx1bmFtYWRpPC9kaXY+JztyZXR1cm47fQogIHZhciBoPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwogIHNvcnRlZC5mb3JFYWNoKGZ1bmN0aW9uKGUpewogICAgdmFyIGFiPWUuYWxlcnQ9PT0icmVkIj8icmdiYSgyMzksNjgsNjgsLjEyKSI6ZS5hbGVydD09PSJ5ZWxsb3ciPyJyZ2JhKDI0NSwxNTgsMTEsLjEpIjoicmdiYSgyNTUsMjU1LDI1NSwuMDIpIjsKICAgIHZhciBhYmQ9ZS5hbGVydD09PSJyZWQiPyJyZ2JhKDIzOSw2OCw2OCwuMzUpIjplLmFsZXJ0PT09InllbGxvdyI/InJnYmEoMjQ1LDE1OCwxMSwuMykiOiJyZ2JhKDI1NSwyNTUsMjU1LC4wNykiOwogICAgdmFyIGFpPWUuYWxlcnQ9PT0icmVkIj8i8J+UtCI6ZS5hbGVydD09PSJ5ZWxsb3ciPyLwn5+hIjoi8J+ThSI7CiAgICB2YXIgZHQ9ZS5kYXlzX3RvX2Vhcm5pbmdzIT1udWxsPyhlLmRheXNfdG9fZWFybmluZ3M9PT0wPyJCVUdVTiI6ZS5kYXlzX3RvX2Vhcm5pbmdzPT09MT8iWWFyaW4iOmUuZGF5c190b19lYXJuaW5ncysiIGd1biBzb25yYSIpOiIiOwogICAgdmFyIGFtQ29sPWUuYXZnX21vdmVfcGN0IT1udWxsPyhlLmF2Z19tb3ZlX3BjdD49MD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkMikiKToidmFyKC0tbXV0ZWQpIjsKICAgIHZhciBhbVN0cj1lLmF2Z19tb3ZlX3BjdCE9bnVsbD8oZS5hdmdfbW92ZV9wY3Q+PTA/IisiOiIiKStlLmF2Z19tb3ZlX3BjdCsiJSI6IuKAlCI7CiAgICB2YXIgeWI9ZS5hbGVydD09PSJyZWQiPyc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMTUpO2NvbG9yOnZhcigtLXJlZDIpO3BhZGRpbmc6MnB4IDhweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDAiPllBS0lOREE8L3NwYW4+JzoiIjsKICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicrYWIrJztib3JkZXI6MXB4IHNvbGlkICcrYWJkKyc7Ym9yZGVyLXJhZGl1czoxMHB4O21hcmdpbi1ib3R0b206MTBweDtwYWRkaW5nOjE0cHggMTZweCI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2ZsZXgtd3JhcDp3cmFwO2dhcDo4cHgiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6MTBweCI+PHNwYW4+JythaSsnPC9zcGFuPjxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjIwcHg7bGV0dGVyLXNwYWNpbmc6MnB4O2NvbG9yOnZhcigtLXRleHQpIj4nK2UudGlja2VyKyc8L3NwYW4+Jyt5YisnPC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjE2cHg7ZmxleC13cmFwOndyYXA7YWxpZ24taXRlbXM6Y2VudGVyIj4nOwogICAgaCs9JzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+UkFQT1I8L2Rpdj48ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOnZhcigtLXRleHQpIj4nKyhlLm5leHRfZGF0ZXx8IuKAlCIpKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjonKyhlLmFsZXJ0PT09InJlZCI/InZhcigtLXJlZDIpIjplLmFsZXJ0PT09InllbGxvdyI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nK2R0Kyc8L2Rpdj48L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+RVBTIFRBSE1JTjwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo2MDA7Y29sb3I6IzYwYTVmYSI+JysoZS5lcHNfZXN0aW1hdGUhPW51bGw/IiQiK2UuZXBzX2VzdGltYXRlOiLigJQiKSsnPC9kaXY+PC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPk9SVC5IQVJFS0VUPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxNHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK2FtQ29sKyciPicrYW1TdHIrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo4cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5zb24gNCByYXBvcjwvZGl2PjwvZGl2Pic7CiAgICBoKz0nPC9kaXY+PC9kaXY+JzsKICAgIGlmKGUuaGlzdG9yeV9lcHMmJmUuaGlzdG9yeV9lcHMubGVuZ3RoKXsKICAgICAgaCs9JzxkaXYgc3R5bGU9Im1hcmdpbi10b3A6OHB4O3BhZGRpbmctdG9wOjhweDtib3JkZXItdG9wOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNikiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NXB4Ij5TT04gNCBSQVBPUjwvZGl2PjxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KDQsMWZyKTtnYXA6NHB4Ij4nOwogICAgICBlLmhpc3RvcnlfZXBzLmZvckVhY2goZnVuY3Rpb24oaGgpewogICAgICAgIHZhciBzYz1oaC5zdXJwcmlzZV9wY3QhPW51bGw/KGhoLnN1cnByaXNlX3BjdD4wPyJ2YXIoLS1ncmVlbikiOiJ2YXIoLS1yZWQyKSIpOiJ2YXIoLS1tdXRlZCkiOwogICAgICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo0cHg7cGFkZGluZzo2cHg7dGV4dC1hbGlnbjpjZW50ZXI7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNSkiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo4cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK2hoLmRhdGUuc3Vic3RyaW5nKDAsNykrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTBweCI+JysoaGguYWN0dWFsIT1udWxsPyIkIitoaC5hY3R1YWw6Ij8iKSsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK3NjKyciPicrKGhoLnN1cnByaXNlX3BjdCE9bnVsbD8oaGguc3VycHJpc2VfcGN0PjA/IisiOiIiKStoaC5zdXJwcmlzZV9wY3QrIiUiOiI/IikrJzwvZGl2PjwvZGl2Pic7CiAgICAgIH0pOwogICAgICBoKz0nPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGgrPSc8L2Rpdj4nOwogIH0pOwogIGlmKG5vRGF0ZS5sZW5ndGgpe2grPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLXRvcDo2cHgiPlRhcmloIGJ1bHVuYW1heWFuOiAnK25vRGF0ZS5tYXAoZnVuY3Rpb24oZSl7cmV0dXJuIGUudGlja2VyO30pLmpvaW4oIiwgIikrJzwvZGl2Pic7fQogIGgrPSc8L2Rpdj4nOwogIGdyaWQuaW5uZXJIVE1MPWg7Cn0KCmZ1bmN0aW9uIG9wZW5NKHRpY2tlcil7CiAgdmFyIHI9Y3VyRGF0YS5maW5kKGZ1bmN0aW9uKGQpe3JldHVybiBkLnRpY2tlcj09PXRpY2tlcjt9KTsKICBpZighcnx8ci5oYXRhKSByZXR1cm47CiAgaWYobUNoYXJ0KXttQ2hhcnQuZGVzdHJveSgpO21DaGFydD1udWxsO30KICB2YXIgc3M9U1Nbci5zaW55YWxdfHxTU1siRElLS0FUIl07CiAgdmFyIHJyUD1NYXRoLm1pbigoci5yci80KSoxMDAsMTAwKTsKICB2YXIgcnJDPXIucnI+PTM/InZhcigtLWdyZWVuKSI6ci5ycj49Mj8idmFyKC0tZ3JlZW4yKSI6ci5ycj49MT8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZDIpIjsKICB2YXIgZGM9ci5kZWdpc2ltPj0wPyJ2YXIoLS1ncmVlbjIpIjoidmFyKC0tcmVkMikiOwogIHZhciBrYz17IkdVQ0xVIEFMIjoiIzEwYjk4MSIsIkFMIjoiIzM0ZDM5OSIsIkRJS0tBVExJIjoiI2Y1OWUwYiIsIkdFQ01FIjoiI2Y4NzE3MSJ9OwogIHZhciBrbGJsPXsiR1VDTFUgQUwiOiJHVUNMVSBBTCIsIkFMIjoiQUwiLCJESUtLQVRMSSI6IkRJS0tBVExJIiwiR0VDTUUiOiJHRUNNRSJ9OwogIHZhciBlc2NvbD1yLmVudHJ5X3Njb3JlPj03NT8idmFyKC0tZ3JlZW4pIjpyLmVudHJ5X3Njb3JlPj02MD8idmFyKC0tZ3JlZW4yKSI6ci5lbnRyeV9zY29yZT49NDU/InZhcigtLXllbGxvdykiOnIuZW50cnlfc2NvcmU+PTMwPyJ2YXIoLS1yZWQyKSI6InZhcigtLXJlZCkiOwogIHZhciBwdmNvbD1yLnByaWNlX3ZzX2NvbG9yPT09ImdyZWVuIj8idmFyKC0tZ3JlZW4pIjpyLnByaWNlX3ZzX2NvbG9yPT09InllbGxvdyI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQyKSI7CgogIHZhciBtaD0nPGRpdiBjbGFzcz0ibWhlYWQiPjxkaXY+PGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6OHB4O2ZsZXgtd3JhcDp3cmFwIj4nCiAgICArJzxzcGFuIGNsYXNzPSJtdGl0bGUiIHN0eWxlPSJjb2xvcjonK3NzLnR4KyciPicrci50aWNrZXIrJzwvc3Bhbj4nCiAgICArJzxzcGFuIGNsYXNzPSJiYWRnZSIgc3R5bGU9ImJhY2tncm91bmQ6Jytzcy5iZysnO2NvbG9yOicrc3MudHgrJztib3JkZXI6MXB4IHNvbGlkICcrc3MuYmQrJztmb250LXNpemU6MTJweCI+Jytzcy5sYmwrJzwvc3Bhbj4nCiAgICArKHIucG9ydGZvbGlvPyc8c3BhbiBjbGFzcz0icG9ydC1iYWRnZSIgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O3BhZGRpbmc6M3B4IDhweCI+UG9ydGZvbHlvPC9zcGFuPic6JycpCiAgICArJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXdlaWdodDo2MDA7bWFyZ2luLXRvcDo0cHgiPiQnK3IuZml5YXQKICAgICsnIDxzcGFuIHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjonK2RjKyciPicrKHIuZGVnaXNpbT49MD8iKyI6IiIpK3IuZGVnaXNpbSsnJTwvc3Bhbj48L2Rpdj48L2Rpdj4nCiAgICArJzxidXR0b24gY2xhc3M9Im1jbG9zZSIgb25jbGljaz0iY2xvc2VNKCkiPuKclTwvYnV0dG9uPjwvZGl2Pic7CgogIG1oKz0nPGRpdiBjbGFzcz0ibWJvZHkiPjxkaXYgY2xhc3M9Im1jaGFydHciPjxjYW52YXMgaWQ9Im1jaGFydCI+PC9jYW52YXM+PC9kaXY+JzsKCiAgbWgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7bWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPicraWIoIkVudHJ5U2NvcmUiLCJHaXJpcyBLYWxpdGVzaSIpKyc8L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47bWFyZ2luLWJvdHRvbTo2cHgiPicKICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfc2NvcmUrJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTNweDtjb2xvcjp2YXIoLS1tdXRlZCkiPi8xMDA8L3NwYW4+PC9zcGFuPicKICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjonK2VzY29sKyciPicrci5lbnRyeV9sYWJlbCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iaGVpZ2h0OjZweDtiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyLXJhZGl1czozcHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi1ib3R0b206OHB4Ij48ZGl2IHN0eWxlPSJoZWlnaHQ6MTAwJTt3aWR0aDonK3IuZW50cnlfc2NvcmUrJyU7YmFja2dyb3VuZDonK2VzY29sKyc7Ym9yZGVyLXJhZGl1czozcHgiPjwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2ZvbnQtc2l6ZToxMXB4Ij4nCiAgICArJzxkaXY+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+U3UgYW5raSBmaXlhdDogPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjonK3B2Y29sKyc7Zm9udC13ZWlnaHQ6NjAwIj4nK3IucHJpY2VfdnNfaWRlYWwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXY+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+SWRlYWwgYm9sZ2U6IDwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4yKTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuaWRlYWxfZW50cnlfbG93KycgLSAkJytyLmlkZWFsX2VudHJ5X2hpZ2grJzwvc3Bhbj48L2Rpdj4nCiAgICArJzwvZGl2PjwvZGl2Pic7CgogIG1oKz0nPGRpdiBjbGFzcz0iZGJveCIgc3R5bGU9ImJhY2tncm91bmQ6Jytzcy5iZysnO2JvcmRlci1jb2xvcjonK3NzLmJkKyc7bWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgY2xhc3M9ImRsYmwiIHN0eWxlPSJjb2xvcjonK3NzLnR4KyciPicraWIoIlJSIiwiQWxpbSBLYXJhcmkgUi9SIikrJzwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHZlcmQiIHN0eWxlPSJjb2xvcjonKyhrY1tyLmthcmFyXXx8InZhcigtLW11dGVkKSIpKyciPicrKGtsYmxbci5rYXJhcl18fHIua2FyYXIpKyc8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5SaXNrIC8gT2R1bDwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6JytyckMrJztmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4xIDogJytyLnJyKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+SGVtZW4gR2lyPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbjIpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5lbnRyeV9hZ2dyZXNzaXZlKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+R2VyaSBDZWtpbG1lPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjojNjBhNWZhO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5lbnRyeV9taWQrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5CdXl1ayBEdXplbHRtZTwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0teWVsbG93KTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuZW50cnlfY29uc2VydmF0aXZlKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+SGVkZWY8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOiM2MGE1ZmE7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmhlZGVmKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+U3RvcC1Mb3NzPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3Iuc3RvcCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0icnJiYXIiPjxkaXYgY2xhc3M9InJyZmlsbCIgc3R5bGU9IndpZHRoOicrcnJQKyclO2JhY2tncm91bmQ6JytyckMrJyI+PC9kaXY+PC9kaXY+PC9kaXY+JzsKCiAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij5UZWtuaWsgQW5hbGl6PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkZ3JpZCIgc3R5bGU9Im1hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlRyZW5kIiwiVHJlbmQiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnRyZW5kPT09Ill1a3NlbGVuIj8idmFyKC0tZ3JlZW4pIjpyLnRyZW5kPT09IkR1c2VuIj8idmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrci50cmVuZCsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlJTSSIsIlJTSSAxNCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucnNpP3IucnNpPDMwPyJ2YXIoLS1ncmVlbikiOnIucnNpPjcwPyJ2YXIoLS1yZWQpIjoidmFyKC0teWVsbG93KSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucnNpfHwiPyIpKyhyLnJzaT9yLnJzaTwzMD8iIEFzaXJpIFNhdGltIjpyLnJzaT43MD8iIEFzaXJpIEFsaW0iOiIgTm90ciI6IiIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiU01BNTAiLCJTTUEgNTAiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmFib3ZlNTA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZCkiKSsnIj4nKyhyLmFib3ZlNTA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIpKyhyLnNtYTUwX2Rpc3QhPW51bGw/IiAoIityLnNtYTUwX2Rpc3QrIiUpIjoiIikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJTTUEyMDAiLCJTTUEgMjAwIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5hYm92ZTIwMD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkKSIpKyciPicrKHIuYWJvdmUyMDA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIpKyhyLnNtYTIwMF9kaXN0IT1udWxsPyIgKCIrci5zbWEyMDBfZGlzdCsiJSkiOiIiKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIjUyVyIsIjUySCBQb3ouIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci53NTJfcG9zaXRpb248PTMwPyJ2YXIoLS1ncmVlbikiOnIudzUyX3Bvc2l0aW9uPj04NT8idmFyKC0tcmVkKSI6InZhcigtLXllbGxvdykiKSsnIj4nK3IudzUyX3Bvc2l0aW9uKyclPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIkhhY2ltIiwiSGFjaW0iKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmhhY2ltPT09Ill1a3NlayI/InZhcigtLWdyZWVuKSI6ci5oYWNpbT09PSJEdXN1ayI/InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nK3IuaGFjaW0rJyAoJytyLnZvbF9yYXRpbysneCk8L2Rpdj48L2Rpdj4nCiAgICArJzwvZGl2Pic7CgogIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+VGVtZWwgQW5hbGl6PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkZ3JpZCIgc3R5bGU9Im1hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIkZvcndhcmRQRSIsIkZvcndhcmQgUEUiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnBlX2Z3ZD9yLnBlX2Z3ZDwyNT8idmFyKC0tZ3JlZW4pIjpyLnBlX2Z3ZDw0MD8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnBlX2Z3ZD9yLnBlX2Z3ZC50b0ZpeGVkKDEpOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJQRUciLCJQRUciKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnBlZz9yLnBlZzwxPyJ2YXIoLS1ncmVlbikiOnIucGVnPDI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5wZWc/ci5wZWcudG9GaXhlZCgyKToiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiRVBTR3Jvd3RoIiwiRVBTIELDvHnDvG1lIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5lcHNfZ3Jvd3RoP3IuZXBzX2dyb3d0aD49MjA/InZhcigtLWdyZWVuKSI6ci5lcHNfZ3Jvd3RoPj0wPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIuZXBzX2dyb3d0aCE9bnVsbD9yLmVwc19ncm93dGgrIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJSZXZHcm93dGgiLCJHZWxpciBCw7x5w7xtZSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucmV2X2dyb3d0aD9yLnJldl9ncm93dGg+PTE1PyJ2YXIoLS1ncmVlbikiOnIucmV2X2dyb3d0aD49MD8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnJldl9ncm93dGghPW51bGw/ci5yZXZfZ3Jvd3RoKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiTmV0TWFyZ2luIiwiTmV0IE1hcmppbiIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIubmV0X21hcmdpbj9yLm5ldF9tYXJnaW4+PTE1PyJ2YXIoLS1ncmVlbikiOnIubmV0X21hcmdpbj49NT8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLm5ldF9tYXJnaW4hPW51bGw/ci5uZXRfbWFyZ2luKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUk9FIiwiUk9FIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5yb2U/ci5yb2U+PTE1PyJ2YXIoLS1ncmVlbikiOnIucm9lPj01PyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucm9lIT1udWxsP3Iucm9lKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzwvZGl2Pic7CgogIHZhciBhaVRleHQgPSBBSV9EQVRBICYmIEFJX0RBVEFbdGlja2VyXTsKICBpZihhaVRleHQpewogICAgbWgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O21hcmdpbi1ib3R0b206MTJweCI+JzsKICAgIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPvCfpJYgQUkgQW5hbGl6IChDbGF1ZGUgU29ubmV0KTwvZGl2Pic7CiAgICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLXRleHQpO2xpbmUtaGVpZ2h0OjEuNzt3aGl0ZS1zcGFjZTpwcmUtd3JhcCI+JythaVRleHQrJzwvZGl2Pic7CiAgICBtaCs9JzwvZGl2Pic7CiAgfQogIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO3RleHQtYWxpZ246Y2VudGVyIj5CdSBhcmFjIHlhdGlyaW0gdGF2c2l5ZXNpIGRlZ2lsZGlyPC9kaXY+PC9kaXY+JzsKCiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1vZGFsIikuaW5uZXJIVE1MPW1oOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJvdmVybGF5IikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwogIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsKICAgIHZhciBjdHg9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1jaGFydCIpOwogICAgaWYoY3R4JiZyLmNoYXJ0X2Nsb3Nlcyl7CiAgICAgIG1DaGFydD1uZXcgQ2hhcnQoY3R4LHt0eXBlOiJsaW5lIixkYXRhOntsYWJlbHM6ci5jaGFydF9kYXRlcyxkYXRhc2V0czpbCiAgICAgICAge2xhYmVsOiJGaXlhdCIsZGF0YTpyLmNoYXJ0X2Nsb3Nlcyxib3JkZXJDb2xvcjpzcy5hYyxib3JkZXJXaWR0aDoyLGZpbGw6dHJ1ZSxiYWNrZ3JvdW5kQ29sb3I6c3MuYWMrIjIwIixwb2ludFJhZGl1czowLHRlbnNpb246MC4zfSwKICAgICAgICByLnNtYTUwP3tsYWJlbDoiU01BNTAiLGRhdGE6QXJyYXkoci5jaGFydF9jbG9zZXMubGVuZ3RoKS5maWxsKHIuc21hNTApLGJvcmRlckNvbG9yOiIjZjU5ZTBiIixib3JkZXJXaWR0aDoxLjUsYm9yZGVyRGFzaDpbNSw1XSxwb2ludFJhZGl1czowLGZpbGw6ZmFsc2V9Om51bGwsCiAgICAgICAgci5zbWEyMDA/e2xhYmVsOiJTTUEyMDAiLGRhdGE6QXJyYXkoci5jaGFydF9jbG9zZXMubGVuZ3RoKS5maWxsKHIuc21hMjAwKSxib3JkZXJDb2xvcjoiIzhiNWNmNiIsYm9yZGVyV2lkdGg6MS41LGJvcmRlckRhc2g6WzUsNV0scG9pbnRSYWRpdXM6MCxmaWxsOmZhbHNlfTpudWxsCiAgICAgIF0uZmlsdGVyKEJvb2xlYW4pfSxvcHRpb25zOntyZXNwb25zaXZlOnRydWUsbWFpbnRhaW5Bc3BlY3RSYXRpbzpmYWxzZSwKICAgICAgICBwbHVnaW5zOntsZWdlbmQ6e2xhYmVsczp7Y29sb3I6IiM2YjcyODAiLGZvbnQ6e3NpemU6MTB9fX19LAogICAgICAgIHNjYWxlczp7eDp7ZGlzcGxheTp0cnVlLHRpY2tzOntjb2xvcjoiIzM3NDE1MSIsbWF4VGlja3NMaW1pdDo1LGZvbnQ6e3NpemU6OX19LGdyaWQ6e2NvbG9yOiJyZ2JhKDI1NSwyNTUsMjU1LC4wNCkifX0sCiAgICAgICAgICB5OntkaXNwbGF5OnRydWUsdGlja3M6e2NvbG9yOiIjMzc0MTUxIixmb250OntzaXplOjl9fSxncmlkOntjb2xvcjoicmdiYSgyNTUsMjU1LDI1NSwuMDQpIn19fX19KTsKICAgIH0KICB9LDEwMCk7Cn0KCgovLyDilIDilIAgR8OcTkzDnEsgUlVUxLBOIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgAp2YXIgUlVUSU5fSVRFTVMgPSB7CiAgc2FiYWg6IHsKICAgIGxhYmVsOiAi8J+MhSBTYWJhaCDigJQgUGl5YXNhIEHDp8SxbG1hZGFuIMOWbmNlIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoiczEiLCB0ZXh0OiJEYXNoYm9hcmQnxLEgYcOnIOKAlCBNIGtyaXRlcmkgeWXFn2lsIG1pPyAoUyZQNTAwICsgTkFTREFRIFNNQTIwMCDDvHN0w7xuZGUpIn0sCiAgICAgIHtpZDoiczIiLCB0ZXh0OiJFYXJuaW5ncyBzZWttZXNpbmkga29udHJvbCBldCDigJQgYnVnw7xuL2J1IGhhZnRhIHJhcG9yIHZhciBtxLE/In0sCiAgICAgIHtpZDoiczMiLCB0ZXh0OiJWSVggMjUgYWx0xLFuZGEgbcSxPyAoWcO8a3Nla3NlIHllbmkgcG96aXN5b24gYcOnbWEpIn0sCiAgICAgIHtpZDoiczQiLCB0ZXh0OiLDlm5jZWtpIGfDvG5kZW4gYmVrbGV5ZW4gYWxhcm0gbWFpbGkgdmFyIG3EsT8ifQogICAgXQogIH0sCiAgb2dsZW46IHsKICAgIGxhYmVsOiAi8J+TiiDDlsSfbGVkZW4gU29ucmEg4oCUIFBpeWFzYSBBw6fEsWtrZW4iLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJvMSIsIHRleHQ6IlBvcnRmw7Z5w7xtIHNla21lc2luZGUgaGlzc2VsZXJpbWUgYmFrIOKAlCBiZWtsZW5tZWRpayBkw7zFn8O8xZ8gdmFyIG3EsT8ifSwKICAgICAge2lkOiJvMiIsIHRleHQ6IlN0b3Agc2V2aXllc2luZSB5YWtsYcWfYW4gaGlzc2UgdmFyIG3EsT8gKEvEsXJtxLF6xLEgacWfYXJldCkifSwKICAgICAge2lkOiJvMyIsIHRleHQ6IkFsIHNpbnlhbGkgc2VrbWVzaW5kZSB5ZW5pIGbEsXJzYXQgw6fEsWttxLHFnyBtxLE/In0sCiAgICAgIHtpZDoibzQiLCB0ZXh0OiJXYXRjaGxpc3QndGVraSBoaXNzZWxlcmRlIGdpcmnFnyBrYWxpdGVzaSA2MCsgb2xhbiB2YXIgbcSxPyJ9LAogICAgICB7aWQ6Im81IiwgdGV4dDoiSGFiZXJsZXJkZSBwb3J0ZsO2ecO8bcO8IGV0a2lsZXllbiDDtm5lbWxpIGdlbGnFn21lIHZhciBtxLE/In0KICAgIF0KICB9LAogIGFrc2FtOiB7CiAgICBsYWJlbDogIvCfjJkgQWvFn2FtIOKAlCBQaXlhc2EgS2FwYW5kxLFrdGFuIFNvbnJhIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoiYTEiLCB0ZXh0OiIxSCBzaW55YWxsZXJpbmkga29udHJvbCBldCDigJQgaGFmdGFsxLFrIHRyZW5kIGRlxJ9pxZ9tacWfIG1pPyJ9LAogICAgICB7aWQ6ImEyIiwgdGV4dDoiWWFyxLFuIGnDp2luIHBvdGFuc2l5ZWwgZ2lyacWfIG5va3RhbGFyxLFuxLEgbm90IGFsIn0sCiAgICAgIHtpZDoiYTMiLCB0ZXh0OiJQb3J0ZsO2eWRla2kgaGVyIGhpc3NlbmluIHN0b3Agc2V2aXllc2luaSBnw7Z6ZGVuIGdlw6dpciJ9LAogICAgICB7aWQ6ImE0IiwgdGV4dDoiWWFyxLFuIHJhcG9yIGHDp8Sxa2xheWFjYWsgaGlzc2UgdmFyIG3EsT8gKEVhcm5pbmdzIHNla21lc2kpIn0KICAgIF0KICB9LAogIGhhZnRhbGlrOiB7CiAgICBsYWJlbDogIvCfk4UgSGFmdGFsxLFrIOKAlCBQYXphciBBa8WfYW3EsSIsCiAgICBpdGVtczogWwogICAgICB7aWQ6ImgxIiwgdGV4dDoiU3RvY2sgUm92ZXInZGEgQ0FOU0xJTSBzY3JlZW5lcifEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoMiIsIHRleHQ6IlZDUCBNaW5lcnZpbmkgc2NyZWVuZXInxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDMiLCB0ZXh0OiJRdWxsYW1hZ2dpZSBCcmVha291dCBzY3JlZW5lcifEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoNCIsIHRleHQ6IkZpbnZpeidkZSBJbnN0aXR1dGlvbmFsIEJ1eWluZyBzY3JlZW5lcifEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoNSIsIHRleHQ6IsOHYWvEscWfYW4gaGlzc2VsZXJpIGJ1bCDigJQgZW4gZ8O8w6dsw7wgYWRheWxhciJ9LAogICAgICB7aWQ6Img2IiwgdGV4dDoiR2l0SHViIEFjdGlvbnMnZGFuIFJ1biBXb3JrZmxvdyBiYXMg4oCUIHNpdGUgZ8O8bmNlbGxlbmlyIn0sCiAgICAgIHtpZDoiaDciLCB0ZXh0OiJHZWxlY2VrIGhhZnRhbsSxbiBlYXJuaW5ncyB0YWt2aW1pbmkga29udHJvbCBldCJ9LAogICAgICB7aWQ6Img4IiwgdGV4dDoiUG9ydGbDtnkgZ2VuZWwgZGXEn2VybGVuZGlybWVzaSDigJQgaGVkZWZsZXIgaGFsYSBnZcOnZXJsaSBtaT8ifQogICAgXQogIH0KfTsKCmZ1bmN0aW9uIGdldFRvZGF5S2V5KCl7CiAgcmV0dXJuIG5ldyBEYXRlKCkudG9EYXRlU3RyaW5nKCk7Cn0KCmZ1bmN0aW9uIGxvYWRDaGVja2VkKCl7CiAgdHJ5ewogICAgdmFyIGRhdGEgPSBsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgncnV0aW5fY2hlY2tlZCcpOwogICAgaWYoIWRhdGEpIHJldHVybiB7fTsKICAgIHZhciBwYXJzZWQgPSBKU09OLnBhcnNlKGRhdGEpOwogICAgLy8gU2FkZWNlIGJ1Z8O8bsO8biB2ZXJpbGVyaW5pIGt1bGxhbgogICAgaWYocGFyc2VkLmRhdGUgIT09IGdldFRvZGF5S2V5KCkpIHJldHVybiB7fTsKICAgIHJldHVybiBwYXJzZWQuaXRlbXMgfHwge307CiAgfWNhdGNoKGUpe3JldHVybiB7fTt9Cn0KCmZ1bmN0aW9uIHNhdmVDaGVja2VkKGNoZWNrZWQpewogIGxvY2FsU3RvcmFnZS5zZXRJdGVtKCdydXRpbl9jaGVja2VkJywgSlNPTi5zdHJpbmdpZnkoewogICAgZGF0ZTogZ2V0VG9kYXlLZXkoKSwKICAgIGl0ZW1zOiBjaGVja2VkCiAgfSkpOwp9CgpmdW5jdGlvbiB0b2dnbGVDaGVjayhpZCl7CiAgdmFyIGNoZWNrZWQgPSBsb2FkQ2hlY2tlZCgpOwogIGlmKGNoZWNrZWRbaWRdKSBkZWxldGUgY2hlY2tlZFtpZF07CiAgZWxzZSBjaGVja2VkW2lkXSA9IHRydWU7CiAgc2F2ZUNoZWNrZWQoY2hlY2tlZCk7CiAgcmVuZGVyUnV0aW4oKTsKfQoKZnVuY3Rpb24gcmVzZXRSdXRpbigpewogIGxvY2FsU3RvcmFnZS5yZW1vdmVJdGVtKCdydXRpbl9jaGVja2VkJyk7CiAgcmVuZGVyUnV0aW4oKTsKfQoKCmZ1bmN0aW9uIHJlbmRlckhhZnRhbGlrKCl7CiAgdmFyIGdyaWQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogIHZhciB3ZCA9IFdFRUtMWV9EQVRBIHx8IHt9OwogIHZhciBwb3J0ID0gd2QucG9ydGZvbGlvIHx8IFtdOwogIHZhciB3YXRjaCA9IHdkLndhdGNobGlzdCB8fCBbXTsKICB2YXIgYmVzdCA9IHdkLmJlc3Q7CiAgdmFyIHdvcnN0ID0gd2Qud29yc3Q7CiAgdmFyIG1kID0gTUFSS0VUX0RBVEEgfHwge307CiAgdmFyIHNwID0gbWQuU1A1MDAgfHwge307CiAgdmFyIG5hcyA9IG1kLk5BU0RBUSB8fCB7fTsKCiAgZnVuY3Rpb24gY2hnQ29sb3Iodil7IHJldHVybiB2ID49IDAgPyAndmFyKC0tZ3JlZW4pJyA6ICd2YXIoLS1yZWQyKSc7IH0KICBmdW5jdGlvbiBjaGdTdHIodil7IHJldHVybiAodiA+PSAwID8gJysnIDogJycpICsgdiArICclJzsgfQoKICBmdW5jdGlvbiBwZXJmQ2FyZChpdGVtKXsKICAgIHZhciBjYyA9IGNoZ0NvbG9yKGl0ZW0ud2Vla19jaGcpOwogICAgdmFyIHBiID0gaXRlbS5wb3J0Zm9saW8gPyAnPHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xMik7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yNSk7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwO21hcmdpbi1sZWZ0OjRweCI+UDwvc3Bhbj4nIDogJyc7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDEycHg7ZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjZweCI+JwogICAgICArICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo2cHgiPjxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjE2cHg7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgaXRlbS50aWNrZXIgKyAnPC9zcGFuPicgKyBwYiArICc8L2Rpdj4nCiAgICAgICsgJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPicKICAgICAgKyAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxNHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgY2MgKyAnIj4nICsgY2hnU3RyKGl0ZW0ud2Vla19jaGcpICsgJzwvZGl2PicKICAgICAgKyAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPsOWbmNla2k6ICcgKyBjaGdTdHIoaXRlbS5wcmV2X3dlZWtfY2hnKSArICc8L2Rpdj4nCiAgICAgICsgJzwvZGl2PjwvZGl2Pic7CiAgfQoKICB2YXIgaCA9ICc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwoKICAvLyBIZWFkZXIKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4Ij7wn5OIIEhhZnRhbMSxayBQZXJmb3JtYW5zIMOWemV0aTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nICsgKHdkLmdlbmVyYXRlZCB8fCAnJykgKyAnPC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBQaXlhc2EgdnMgUG9ydGbDtnkKICB2YXIgc3BDaGcgPSBzcC5jaGFuZ2UgfHwgMDsKICB2YXIgbmFzQ2hnID0gbmFzLmNoYW5nZSB8fCAwOwogIHZhciBwb3J0QXZnID0gcG9ydC5sZW5ndGggPyBNYXRoLnJvdW5kKHBvcnQucmVkdWNlKGZ1bmN0aW9uKGEsYil7cmV0dXJuIGErYi53ZWVrX2NoZzt9LDApL3BvcnQubGVuZ3RoKjEwMCkvMTAwIDogMDsKICB2YXIgYWxwaGEgPSBNYXRoLnJvdW5kKChwb3J0QXZnIC0gc3BDaGcpKjEwMCkvMTAwOwogIHZhciBhbHBoYUNvbCA9IGFscGhhID49IDAgPyAndmFyKC0tZ3JlZW4pJyA6ICd2YXIoLS1yZWQyKSc7CgogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMTQwcHgsMWZyKSk7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPlBvcnRmw7Z5IE9ydC48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Y29sb3I6JyArIGNoZ0NvbG9yKHBvcnRBdmcpICsgJyI+JyArIGNoZ1N0cihwb3J0QXZnKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPlMmUCA1MDA8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Y29sb3I6JyArIGNoZ0NvbG9yKHNwQ2hnKSArICciPicgKyBjaGdTdHIoc3BDaGcpICsgJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+TkFTREFRPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicgKyBjaGdDb2xvcihuYXNDaGcpICsgJyI+JyArIGNoZ1N0cihuYXNDaGcpICsgJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonICsgKGFscGhhPj0wPydyZ2JhKDE2LDE4NSwxMjksLjA4KSc6J3JnYmEoMjM5LDY4LDY4LC4wOCknKSArICc7Ym9yZGVyOjFweCBzb2xpZCAnICsgKGFscGhhPj0wPydyZ2JhKDE2LDE4NSwxMjksLjI1KSc6J3JnYmEoMjM5LDY4LDY4LC4yNSknKSArICc7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPkFscGhhICh2cyBTJlApPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicgKyBhbHBoYUNvbCArICciPicgKyAoYWxwaGE+PTA/JysnOicnKSArIGFscGhhICsgJyU8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIEVuIGl5aSAvIGVuIGvDtnTDvAogIGlmKGJlc3QgfHwgd29yc3QpewogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnIgMWZyO2dhcDoxMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICAgIGlmKGJlc3QpewogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4Ij4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1ncmVlbik7bWFyZ2luLWJvdHRvbTo2cHgiPvCfj4YgQnUgSGFmdGFuxLFuIEVuIMSweWlzaTwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkJlYmFzIE5ldWUsc2Fucy1zZXJpZjtmb250LXNpemU6MjRweDtsZXR0ZXItc3BhY2luZzoycHgiPicgKyBiZXN0LnRpY2tlciArICc8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+KycgKyBiZXN0LndlZWtfY2hnICsgJyU8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaWYod29yc3QpewogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tcmVkMik7bWFyZ2luLWJvdHRvbTo2cHgiPvCfk4kgQnUgSGFmdGFuxLFuIEVuIEvDtnTDvHPDvDwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkJlYmFzIE5ldWUsc2Fucy1zZXJpZjtmb250LXNpemU6MjRweDtsZXR0ZXItc3BhY2luZzoycHgiPicgKyB3b3JzdC50aWNrZXIgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1yZWQyKSI+JyArIHdvcnN0LndlZWtfY2hnICsgJyU8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFBvcnRmw7Z5IGRldGF5CiAgaWYocG9ydC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+SvCBQb3J0ZsO2eTwvZGl2Pic7CiAgICBwb3J0LmZvckVhY2goZnVuY3Rpb24oaXRlbSl7IGggKz0gcGVyZkNhcmQoaXRlbSk7IH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFNpbnlhbGxlciBvemV0aQogIHZhciBidXlDb3VudCA9IChURl9EQVRBWycxZCddfHxbXSkuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdHVUNMVSBBTCd8fHIuc2lueWFsPT09J0FMJzt9KS5sZW5ndGg7CiAgdmFyIHNlbGxDb3VudCA9IChURl9EQVRBWycxZCddfHxbXSkuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdTQVQnO30pLmxlbmd0aDsKICB2YXIgd2F0Y2hDb3VudCA9IChURl9EQVRBWycxZCddfHxbXSkuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdESUtLQVQnO30pLmxlbmd0aDsKCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfk4ogQnUgSGFmdGFraSBTaW55YWxsZXI8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+JyArIGJ1eUNvdW50ICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+QWwgU2lueWFsaTwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjQ1LDE1OCwxMSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS15ZWxsb3cpIj4nICsgd2F0Y2hDb3VudCArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkRpa2thdDwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicgKyBzZWxsQ291bnQgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5TYXQgU2lueWFsaTwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPC9kaXY+PC9kaXY+JzsKCiAgLy8gV2F0Y2hsaXN0IHBlcmZvcm1hbnMKICBpZih3YXRjaC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+RgSBXYXRjaGxpc3Q8L2Rpdj4nOwogICAgd2F0Y2guZm9yRWFjaChmdW5jdGlvbihpdGVtKXsgaCArPSBwZXJmQ2FyZChpdGVtKTsgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgaCArPSAnPC9kaXY+JzsKICBncmlkLmlubmVySFRNTCA9IGg7Cn0KCgpmdW5jdGlvbiByZW5kZXJSdXRpbigpewogIHZhciBncmlkID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dyaWQnKTsKICB2YXIgY2hlY2tlZCA9IGxvYWRDaGVja2VkKCk7CiAgdmFyIHRvZGF5ID0gbmV3IERhdGUoKTsKICB2YXIgaXNXZWVrZW5kID0gdG9kYXkuZ2V0RGF5KCkgPT09IDAgfHwgdG9kYXkuZ2V0RGF5KCkgPT09IDY7CiAgdmFyIGRheU5hbWUgPSBbJ1BhemFyJywnUGF6YXJ0ZXNpJywnU2FsxLEnLCfDh2FyxZ9hbWJhJywnUGVyxZ9lbWJlJywnQ3VtYScsJ0N1bWFydGVzaSddW3RvZGF5LmdldERheSgpXTsKICB2YXIgZGF0ZVN0ciA9IHRvZGF5LnRvTG9jYWxlRGF0ZVN0cmluZygndHItVFInLCB7ZGF5OidudW1lcmljJyxtb250aDonbG9uZycseWVhcjonbnVtZXJpYyd9KTsKCiAgLy8gUHJvZ3Jlc3MgaGVzYXBsYQogIHZhciB0b3RhbEl0ZW1zID0gMDsKICB2YXIgZG9uZUl0ZW1zID0gMDsKICB2YXIgc2VjdGlvbnMgPSBpc1dlZWtlbmQgPyBbJ2hhZnRhbGlrJ10gOiBbJ3NhYmFoJywnb2dsZW4nLCdha3NhbSddOwogIHNlY3Rpb25zLmZvckVhY2goZnVuY3Rpb24oayl7CiAgICBSVVRJTl9JVEVNU1trXS5pdGVtcy5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0pewogICAgICB0b3RhbEl0ZW1zKys7CiAgICAgIGlmKGNoZWNrZWRbaXRlbS5pZF0pIGRvbmVJdGVtcysrOwogICAgfSk7CiAgfSk7CiAgdmFyIHBjdCA9IHRvdGFsSXRlbXMgPiAwID8gTWF0aC5yb3VuZChkb25lSXRlbXMvdG90YWxJdGVtcyoxMDApIDogMDsKICB2YXIgcGN0Q29sID0gcGN0PT09MTAwPyd2YXIoLS1ncmVlbiknOnBjdD49NTA/J3ZhcigtLXllbGxvdyknOid2YXIoLS1tdXRlZCknOwoKICB2YXIgaCA9ICc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwoKICAvLyBIZWFkZXIKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtmbGV4LXdyYXA6d3JhcDtnYXA6MTBweCI+JzsKICBoICs9ICc8ZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KSI+JytkYXlOYW1lKycgUnV0aW5pPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrZGF0ZVN0cisnPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK3BjdENvbCsnIj4nK3BjdCsnJTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK2RvbmVJdGVtcysnLycrdG90YWxJdGVtcysnIHRhbWFtbGFuZMSxPC9kaXY+PC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJoZWlnaHQ6NnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjNweDtvdmVyZmxvdzpoaWRkZW47bWFyZ2luLXRvcDoxMnB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImhlaWdodDoxMDAlO3dpZHRoOicrcGN0KyclO2JhY2tncm91bmQ6JytwY3RDb2wrJztib3JkZXItcmFkaXVzOjNweDt0cmFuc2l0aW9uOndpZHRoIC41cyBlYXNlIj48L2Rpdj48L2Rpdj4nOwogIGlmKHBjdD09PTEwMCkgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXI7bWFyZ2luLXRvcDoxMHB4O2ZvbnQtc2l6ZToxNHB4O2NvbG9yOnZhcigtLWdyZWVuKSI+8J+OiSBUw7xtIG1hZGRlbGVyIHRhbWFtbGFuZMSxITwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gU2VjdGlvbnMKICBzZWN0aW9ucy5mb3JFYWNoKGZ1bmN0aW9uKGspewogICAgdmFyIHNlYyA9IFJVVElOX0lURU1TW2tdOwogICAgdmFyIHNlY0RvbmUgPSBzZWMuaXRlbXMuZmlsdGVyKGZ1bmN0aW9uKGkpe3JldHVybiBjaGVja2VkW2kuaWRdO30pLmxlbmd0aDsKICAgIHZhciBzZWNUb3RhbCA9IHNlYy5pdGVtcy5sZW5ndGg7CiAgICB2YXIgc2VjUGN0ID0gTWF0aC5yb3VuZChzZWNEb25lL3NlY1RvdGFsKjEwMCk7CiAgICB2YXIgc2VjQ29sID0gc2VjUGN0PT09MTAwPyd2YXIoLS1ncmVlbiknOnNlY1BjdD4wPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tbXV0ZWQpJzsKCiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206MTJweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjp2YXIoLS10ZXh0KSI+JytzZWMubGFiZWwrJzwvZGl2Pic7CiAgICBoICs9ICc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6JytzZWNDb2wrJztmb250LXdlaWdodDo2MDAiPicrc2VjRG9uZSsnLycrc2VjVG90YWwrJzwvc3Bhbj48L2Rpdj4nOwoKICAgIHNlYy5pdGVtcy5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0pewogICAgICB2YXIgZG9uZSA9ICEhY2hlY2tlZFtpdGVtLmlkXTsKICAgICAgdmFyIGJnQ29sb3IgPSBkb25lID8gJ3JnYmEoMTYsMTg1LDEyOSwuMDYpJyA6ICdyZ2JhKDI1NSwyNTUsMjU1LC4wMiknOwogICAgICB2YXIgYm9yZGVyQ29sb3IgPSBkb25lID8gJ3JnYmEoMTYsMTg1LDEyOSwuMiknIDogJ3JnYmEoMjU1LDI1NSwyNTUsLjA1KSc7CiAgICAgIHZhciBjaGVja0JvcmRlciA9IGRvbmUgPyAndmFyKC0tZ3JlZW4pJyA6ICd2YXIoLS1tdXRlZCknOwogICAgICB2YXIgY2hlY2tCZyA9IGRvbmUgPyAndmFyKC0tZ3JlZW4pJyA6ICd0cmFuc3BhcmVudCc7CiAgICAgIHZhciB0ZXh0Q29sb3IgPSBkb25lID8gJ3ZhcigtLW11dGVkKScgOiAndmFyKC0tdGV4dCknOwogICAgICB2YXIgdGV4dERlY28gPSBkb25lID8gJ2xpbmUtdGhyb3VnaCcgOiAnbm9uZSc7CiAgICAgIHZhciBjaGVja21hcmsgPSBkb25lID8gJzxzdmcgd2lkdGg9IjEyIiBoZWlnaHQ9IjEyIiB2aWV3Qm94PSIwIDAgMTIgMTIiPjxwb2x5bGluZSBwb2ludHM9IjIsNiA1LDkgMTAsMyIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48L3N2Zz4nIDogJyc7CiAgICAgIGggKz0gJzxkaXYgb25jbGljaz0idG9nZ2xlQ2hlY2soXCcnICsgaXRlbS5pZCArICdcJykiIHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6ZmxleC1zdGFydDtnYXA6MTJweDtwYWRkaW5nOjEwcHg7Ym9yZGVyLXJhZGl1czo4cHg7Y3Vyc29yOnBvaW50ZXI7bWFyZ2luLWJvdHRvbTo2cHg7YmFja2dyb3VuZDonICsgYmdDb2xvciArICc7Ym9yZGVyOjFweCBzb2xpZCAnICsgYm9yZGVyQ29sb3IgKyAnIj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmbGV4LXNocmluazowO3dpZHRoOjIwcHg7aGVpZ2h0OjIwcHg7Ym9yZGVyLXJhZGl1czo1cHg7Ym9yZGVyOjJweCBzb2xpZCAnICsgY2hlY2tCb3JkZXIgKyAnO2JhY2tncm91bmQ6JyArIGNoZWNrQmcgKyAnO2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjttYXJnaW4tdG9wOjFweCI+JyArIGNoZWNrbWFyayArICc8L2Rpdj4nOwogICAgICBoICs9ICc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Y29sb3I6JyArIHRleHRDb2xvciArICc7bGluZS1oZWlnaHQ6MS41O3RleHQtZGVjb3JhdGlvbjonICsgdGV4dERlY28gKyAnIj4nICsgaXRlbS50ZXh0ICsgJzwvc3Bhbj4nOwogICAgICBoICs9ICc8L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0pOwoKICAvLyBIYWZ0YSBpw6dpIG9sZHXEn3VuZGEgaGFmdGFsxLFrIGLDtmzDvG3DvCBkZSBnw7ZzdGVyIChrYXRsYW5hYmlsaXIpCiAgaWYoIWlzV2Vla2VuZCl7CiAgICB2YXIgaFNlYyA9IFJVVElOX0lURU1TWydoYWZ0YWxpayddOwogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA0KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMTUpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y29sb3I6IzYwYTVmYTttYXJnaW4tYm90dG9tOjRweCI+JytoU2VjLmxhYmVsKyc8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5QYXphciBha8WfYW3EsSB5YXDEsWxhY2FrbGFyIOKAlCDFn3UgYW4gZ8O2c3RlcmltIG1vZHVuZGE8L2Rpdj48L2Rpdj4nOwogIH0KCiAgLy8gUmVzZXQgYnV0b251CiAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXI7bWFyZ2luLXRvcDo2cHgiPic7CiAgaCArPSAnPGJ1dHRvbiBvbmNsaWNrPSJyZXNldFJ1dGluKCkiIHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTtwYWRkaW5nOjhweCAxNnB4O2JvcmRlci1yYWRpdXM6OHB4O2ZvbnQtc2l6ZToxMnB4O2N1cnNvcjpwb2ludGVyIj7wn5SEIExpc3RleWkgU8SxZsSxcmxhPC9idXR0b24+JzsKICBoICs9ICc8L2Rpdj4nOwoKICBoICs9ICc8L2Rpdj4nOwogIGdyaWQuaW5uZXJIVE1MID0gaDsKfQoKCmZ1bmN0aW9uIGNsb3NlTShlKXsKICBpZighZXx8ZS50YXJnZXQ9PT1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgib3ZlcmxheSIpKXsKICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJvdmVybGF5IikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpOwogICAgaWYobUNoYXJ0KXttQ2hhcnQuZGVzdHJveSgpO21DaGFydD1udWxsO30KICB9Cn0KCnJlbmRlclN0YXRzKCk7CnJlbmRlckRhc2hib2FyZCgpOwoKCgovLyDilIDilIAgTMSwU1RFIETDnFpFTkxFTUUg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSACnZhciBlZGl0V2F0Y2hsaXN0ID0gW107CnZhciBlZGl0UG9ydGZvbGlvID0gW107CgpmdW5jdGlvbiBvcGVuRWRpdExpc3QoKXsKICBlZGl0V2F0Y2hsaXN0ID0gVEZfREFUQVsnMWQnXS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSkubWFwKGZ1bmN0aW9uKHIpe3JldHVybiByLnRpY2tlcjt9KTsKICBlZGl0UG9ydGZvbGlvID0gUE9SVC5zbGljZSgpOwogIHJlbmRlckVkaXRMaXN0cygpOwogIC8vIExvYWQgc2F2ZWQgdG9rZW4gZnJvbSBsb2NhbFN0b3JhZ2UKICB2YXIgc2F2ZWQgPSBsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgnZ2hfdG9rZW4nKTsKICBpZihzYXZlZCkgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdoVG9rZW5JbnB1dCIpLnZhbHVlID0gc2F2ZWQ7CiAgdmFyIHRzPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0b2tlblNlY3Rpb24iKTsgaWYodHMpIHRzLnN0eWxlLmRpc3BsYXk9Im5vbmUiOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0UG9wdXAiKS5jbGFzc0xpc3QuYWRkKCJvcGVuIik7Cn0KCgpmdW5jdGlvbiB0b2dnbGVUb2tlblNlY3Rpb24oKXsKICB2YXIgcz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidG9rZW5TZWN0aW9uIik7CiAgaWYocykgcy5zdHlsZS5kaXNwbGF5PXMuc3R5bGUuZGlzcGxheT09PSJub25lIj8iYmxvY2siOiJub25lIjsKfQoKZnVuY3Rpb24gc2F2ZVRva2VuKCl7CiAgdmFyIHQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdoVG9rZW5JbnB1dCIpLnZhbHVlLnRyaW0oKTsKICBpZighdCl7YWxlcnQoIlRva2VuIGJvcyEiKTtyZXR1cm47fQogIGxvY2FsU3RvcmFnZS5zZXRJdGVtKCJnaF90b2tlbiIsdCk7CiAgdmFyIHRzPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0b2tlblNlY3Rpb24iKTsgaWYodHMpIHRzLnN0eWxlLmRpc3BsYXk9Im5vbmUiOwogIHNldEVkaXRTdGF0dXMoIuKchSBUb2tlbiBrYXlkZWRpbGRpIiwiZ3JlZW4iKTsKfQoKZnVuY3Rpb24gY2xvc2VFZGl0UG9wdXAoZSl7CiAgaWYoIWV8fGUudGFyZ2V0PT09ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImVkaXRQb3B1cCIpKXsKICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0UG9wdXAiKS5jbGFzc0xpc3QucmVtb3ZlKCJvcGVuIik7CiAgfQp9CgpmdW5jdGlvbiByZW5kZXJFZGl0TGlzdHMoKXsKICB2YXIgd2UgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgid2F0Y2hsaXN0RWRpdG9yIik7CiAgdmFyIHBlID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInBvcnRmb2xpb0VkaXRvciIpOwogIGlmKCF3ZXx8IXBlKSByZXR1cm47CgogIHdlLmlubmVySFRNTCA9IGVkaXRXYXRjaGxpc3QubWFwKGZ1bmN0aW9uKHQsaSl7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47cGFkZGluZzo1cHggOHB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czo1cHg7bWFyZ2luLWJvdHRvbTo0cHgiPicKICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMCI+Jyt0Kyc8L3NwYW4+JwogICAgICArJzxidXR0b24gb25jbGljaz0icmVtb3ZlVGlja2VyKFwnd2F0Y2hcJywnK2krJykiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Ym9yZGVyOm5vbmU7Y29sb3I6dmFyKC0tcmVkMik7d2lkdGg6MjBweDtoZWlnaHQ6MjBweDtib3JkZXItcmFkaXVzOjRweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTJweCI+4pyVPC9idXR0b24+JwogICAgICArJzwvZGl2Pic7CiAgfSkuam9pbignJyk7CgogIHBlLmlubmVySFRNTCA9IGVkaXRQb3J0Zm9saW8ubWFwKGZ1bmN0aW9uKHQsaSl7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47cGFkZGluZzo1cHggOHB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo1cHg7bWFyZ2luLWJvdHRvbTo0cHgiPicKICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicrdCsnPC9zcGFuPicKICAgICAgKyc8YnV0dG9uIG9uY2xpY2s9InJlbW92ZVRpY2tlcihcJ3BvcnRcJywnK2krJykiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Ym9yZGVyOm5vbmU7Y29sb3I6dmFyKC0tcmVkMik7d2lkdGg6MjBweDtoZWlnaHQ6MjBweDtib3JkZXItcmFkaXVzOjRweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTJweCI+4pyVPC9idXR0b24+JwogICAgICArJzwvZGl2Pic7CiAgfSkuam9pbignJyk7Cn0KCmZ1bmN0aW9uIGFkZFRpY2tlcihsaXN0KXsKICB2YXIgaW5wdXRJZCA9IGxpc3Q9PT0nd2F0Y2gnPyJuZXdXYXRjaFRpY2tlciI6Im5ld1BvcnRUaWNrZXIiOwogIHZhciB2YWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZChpbnB1dElkKS52YWx1ZS50cmltKCkudG9VcHBlckNhc2UoKTsKICBpZighdmFsKSByZXR1cm47CiAgaWYobGlzdD09PSd3YXRjaCcgJiYgIWVkaXRXYXRjaGxpc3QuaW5jbHVkZXModmFsKSkgZWRpdFdhdGNobGlzdC5wdXNoKHZhbCk7CiAgaWYobGlzdD09PSdwb3J0JyAgJiYgIWVkaXRQb3J0Zm9saW8uaW5jbHVkZXModmFsKSkgZWRpdFBvcnRmb2xpby5wdXNoKHZhbCk7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoaW5wdXRJZCkudmFsdWUgPSAiIjsKICByZW5kZXJFZGl0TGlzdHMoKTsKfQoKZnVuY3Rpb24gcmVtb3ZlVGlja2VyKGxpc3QsIGlkeCl7CiAgaWYobGlzdD09PSd3YXRjaCcpIGVkaXRXYXRjaGxpc3Quc3BsaWNlKGlkeCwxKTsKICBlbHNlIGVkaXRQb3J0Zm9saW8uc3BsaWNlKGlkeCwxKTsKICByZW5kZXJFZGl0TGlzdHMoKTsKfQoKZnVuY3Rpb24gc2F2ZUxpc3RUb0dpdGh1YigpewogIHZhciB0b2tlbiA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZS50cmltKCk7CiAgaWYoIXRva2VuKXsgc2V0RWRpdFN0YXR1cygi4p2MIFRva2VuIGdlcmVrbGkg4oCUIGt1dHV5YSBnaXIiLCJyZWQiKTsgcmV0dXJuOyB9CiAgbG9jYWxTdG9yYWdlLnNldEl0ZW0oJ2doX3Rva2VuJywgdG9rZW4pOwoKICB2YXIgY29uZmlnID0geyB3YXRjaGxpc3Q6IGVkaXRXYXRjaGxpc3QsIHBvcnRmb2xpbzogZWRpdFBvcnRmb2xpbyB9OwogIHZhciBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoY29uZmlnLCBudWxsLCAyKTsKICB2YXIgYjY0ID0gYnRvYSh1bmVzY2FwZShlbmNvZGVVUklDb21wb25lbnQoY29udGVudCkpKTsKCiAgc2V0RWRpdFN0YXR1cygi8J+SviBLYXlkZWRpbGl5b3IuLi4iLCJ5ZWxsb3ciKTsKCiAgdmFyIGFwaVVybCA9ICJodHRwczovL2FwaS5naXRodWIuY29tL3JlcG9zL2dodXJ6enovY2Fuc2xpbS9jb250ZW50cy9jb25maWcuanNvbiI7CiAgdmFyIGhlYWRlcnMgPSB7IkF1dGhvcml6YXRpb24iOiJ0b2tlbiAiK3Rva2VuLCJDb250ZW50LVR5cGUiOiJhcHBsaWNhdGlvbi9qc29uIn07CgogIC8vIEZpcnN0IGdldCBjdXJyZW50IFNIQSBpZiBleGlzdHMKICBmZXRjaChhcGlVcmwsIHtoZWFkZXJzOmhlYWRlcnN9KQogICAgLnRoZW4oZnVuY3Rpb24ocil7IHJldHVybiByLm9rID8gci5qc29uKCkgOiBudWxsOyB9KQogICAgLnRoZW4oZnVuY3Rpb24oZXhpc3RpbmcpewogICAgICB2YXIgcGF5bG9hZCA9IHsKICAgICAgICBtZXNzYWdlOiAiTGlzdGUgZ3VuY2VsbGVuZGkgIiArIG5ldyBEYXRlKCkudG9Mb2NhbGVEYXRlU3RyaW5nKCJ0ci1UUiIpLAogICAgICAgIGNvbnRlbnQ6IGI2NAogICAgICB9OwogICAgICBpZihleGlzdGluZyAmJiBleGlzdGluZy5zaGEpIHBheWxvYWQuc2hhID0gZXhpc3Rpbmcuc2hhOwoKICAgICAgcmV0dXJuIGZldGNoKGFwaVVybCwgewogICAgICAgIG1ldGhvZDoiUFVUIiwKICAgICAgICBoZWFkZXJzOmhlYWRlcnMsCiAgICAgICAgYm9keTpKU09OLnN0cmluZ2lmeShwYXlsb2FkKQogICAgICB9KTsKICAgIH0pCiAgICAudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYoci5vayB8fCByLnN0YXR1cz09PTIwMSl7CiAgICAgICAgc2V0RWRpdFN0YXR1cygi4pyFIEtheWRlZGlsZGkhIEJpciBzb25yYWtpIENvbGFiIMOnYWzEscWfdMSxcm1hc8SxbmRhIGFrdGlmIG9sdXIuIiwiZ3JlZW4iKTsKICAgICAgICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7Y2xvc2VFZGl0UG9wdXAoKTt9LDIwMDApOwogICAgICB9IGVsc2UgewogICAgICAgIHNldEVkaXRTdGF0dXMoIuKdjCBIYXRhOiAiK3Iuc3RhdHVzKyIg4oCUIFRva2VuJ8SxIGtvbnRyb2wgZXQiLCJyZWQiKTsKICAgICAgfQogICAgfSkKICAgIC5jYXRjaChmdW5jdGlvbihlKXsgc2V0RWRpdFN0YXR1cygi4p2MIEhhdGE6ICIrZS5tZXNzYWdlLCJyZWQiKTsgfSk7Cn0KCmZ1bmN0aW9uIHNldEVkaXRTdGF0dXMobXNnLCBjb2xvcil7CiAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImVkaXRTdGF0dXMiKTsKICBpZihlbCl7CiAgICBlbC50ZXh0Q29udGVudCA9IG1zZzsKICAgIGVsLnN0eWxlLmNvbG9yID0gY29sb3I9PT0iZ3JlZW4iPyJ2YXIoLS1ncmVlbikiOmNvbG9yPT09InJlZCI/InZhcigtLXJlZDIpIjoidmFyKC0teWVsbG93KSI7CiAgfQp9Cgo8L3NjcmlwdD4KZnVuY3Rpb24gcmVuZGVySGFmdGFsaWsoKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgdmFyIHdkID0gV0VFS0xZX0RBVEEgfHwge307CiAgdmFyIHBvcnQgPSB3ZC5wb3J0Zm9saW8gfHwgW107CiAgdmFyIHdhdGNoID0gd2Qud2F0Y2hsaXN0IHx8IFtdOwogIHZhciBiZXN0ID0gd2QuYmVzdDsKICB2YXIgd29yc3QgPSB3ZC53b3JzdDsKICB2YXIgbWQgPSBNQVJLRVRfREFUQSB8fCB7fTsKICB2YXIgc3AgPSBtZC5TUDUwMCB8fCB7fTsKICB2YXIgbmFzID0gbWQuTkFTREFRIHx8IHt9OwogIHZhciBkYXRhMWQgPSBURl9EQVRBWycxZCddIHx8IFtdOwogIHZhciBkYXRhMXcgPSBURl9EQVRBWycxd2snXSB8fCBbXTsKCiAgZnVuY3Rpb24gY2Modil7IHJldHVybiB2Pj0wPyd2YXIoLS1ncmVlbjIpJzondmFyKC0tcmVkMiknOyB9CiAgZnVuY3Rpb24gY3Modil7IHJldHVybiAodj49MD8nKyc6JycpK3YrJyUnOyB9CgogIGZ1bmN0aW9uIHBlcmZSb3coaXRlbSl7CiAgICB2YXIgY29sID0gY2MoaXRlbS53ZWVrX2NoZyk7CiAgICB2YXIgcGIgPSBpdGVtLnBvcnRmb2xpbyA/ICc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1sZWZ0OjRweCI+UDwvc3Bhbj4nIDogJyc7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7cGFkZGluZzo4cHggMTJweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo4cHg7bWFyZ2luLWJvdHRvbTo1cHgiPicKICAgICAgKyAnPGRpdiBzdHlsZT0iZm9udC13ZWlnaHQ6NzAwO2ZvbnQtc2l6ZToxNHB4O2xldHRlci1zcGFjaW5nOjFweCI+JyArIGl0ZW0udGlja2VyICsgcGIgKyAnPC9kaXY+JwogICAgICArICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgY29sICsgJyI+JyArIGNzKGl0ZW0ud2Vla19jaGcpICsgJzwvZGl2PicKICAgICAgKyAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPk9uY2VraTogJyArIGNzKGl0ZW0ucHJldl93ZWVrX2NoZykgKyAnPC9kaXY+JwogICAgICArICc8L2Rpdj48L2Rpdj4nOwogIH0KCiAgdmFyIHBvcnRBdmcgPSBwb3J0Lmxlbmd0aCA/IE1hdGgucm91bmQocG9ydC5yZWR1Y2UoZnVuY3Rpb24oYSxiKXtyZXR1cm4gYStiLndlZWtfY2hnO30sMCkvcG9ydC5sZW5ndGgqMTAwKS8xMDAgOiAwOwogIHZhciBzcENoZyA9IHNwLmNoYW5nZSB8fCAwOwogIHZhciBuYXNDaGcgPSBuYXMuY2hhbmdlIHx8IDA7CiAgdmFyIGFscGhhID0gTWF0aC5yb3VuZCgocG9ydEF2Zy1zcENoZykqMTAwKS8xMDA7CiAgdmFyIGFscGhhQ29sID0gYWxwaGE+PTA/J3ZhcigtLWdyZWVuKSc6J3ZhcigtLXJlZDIpJzsKCiAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgLy8gSGVhZGVyCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tYm90dG9tOjRweCI+8J+TiCBIYWZ0YWzEsWsgUGVyZm9ybWFucyDDlnpldGk8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JyArICh3ZC5nZW5lcmF0ZWR8fCcnKSArICc8L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIFBpeWFzYSB2cyBQb3J0Zm9seW8KICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDEzMHB4LDFmcikpO2dhcDoxMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBbCiAgICB7bGFiZWw6J1BvcnRmw7Z5IE9ydC4nLCB2YWw6cG9ydEF2Z30sCiAgICB7bGFiZWw6J1MmUCA1MDAnLCB2YWw6c3BDaGd9LAogICAge2xhYmVsOidOQVNEQVEnLCB2YWw6bmFzQ2hnfSwKICBdLmZvckVhY2goZnVuY3Rpb24oeCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPicgKyB4LmxhYmVsICsgJzwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGNjKHgudmFsKSArICciPicgKyBjcyh4LnZhbCkgKyAnPC9kaXY+PC9kaXY+JzsKICB9KTsKICB2YXIgYUJnID0gYWxwaGE+PTA/J3JnYmEoMTYsMTg1LDEyOSwuMDgpJzoncmdiYSgyMzksNjgsNjgsLjA4KSc7CiAgdmFyIGFCZCA9IGFscGhhPj0wPydyZ2JhKDE2LDE4NSwxMjksLjI1KSc6J3JnYmEoMjM5LDY4LDY4LC4yNSknOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JyArIGFCZyArICc7Ym9yZGVyOjFweCBzb2xpZCAnICsgYUJkICsgJztib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+QWxwaGEgKHZzIFMmUCk8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgYWxwaGFDb2wgKyAnIj4nICsgY3MoYWxwaGEpICsgJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gRW4gaXlpIC8gZW4ga290dQogIGlmKGJlc3R8fHdvcnN0KXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyIDFmcjtnYXA6MTBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgICBpZihiZXN0KXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tZ3JlZW4pO21hcmdpbi1ib3R0b206NnB4Ij7wn4+GIEVuIMSweWk8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgYmVzdC50aWNrZXIgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+KycgKyBiZXN0LndlZWtfY2hnICsgJyU8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaWYod29yc3QpewogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tcmVkMik7bWFyZ2luLWJvdHRvbTo2cHgiPvCfk4kgRW4gS8O2dMO8PC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2xldHRlci1zcGFjaW5nOjJweCI+JyArIHdvcnN0LnRpY2tlciArICc8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicgKyB3b3JzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBTaW55YWxsZXIKICB2YXIgYnV5QyAgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdHVUNMVSBBTCd8fHIuc2lueWFsPT09J0FMJzt9KS5sZW5ndGg7CiAgdmFyIHdhcm5DID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nRElLS0FUJzt9KS5sZW5ndGg7CiAgdmFyIHNlbGxDID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nU0FUJzt9KS5sZW5ndGg7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfk4ogU2lueWFsbGVyPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXAiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicgKyBidXlDICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+QWw8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0teWVsbG93KSI+JyArIHdhcm5DICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+RGlra2F0PC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1yZWQyKSI+JyArIHNlbGxDICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+U2F0PC9kaXY+PC9kaXY+JzsKICBoICs9ICc8L2Rpdj48L2Rpdj4nOwoKICAvLyAxRysxSCBtb21lbnR1bQogIHZhciBib3RoQnV5ID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXsKICAgIGlmKHIuaGF0YSkgcmV0dXJuIGZhbHNlOwogICAgdmFyIHcgPSBkYXRhMXcuZmluZChmdW5jdGlvbih4KXtyZXR1cm4geC50aWNrZXI9PT1yLnRpY2tlcjt9KTsKICAgIHJldHVybiAoci5zaW55YWw9PT0nR1VDTFUgQUwnfHxyLnNpbnlhbD09PSdBTCcpICYmIHcgJiYgKHcuc2lueWFsPT09J0dVQ0xVIEFMJ3x8dy5zaW55YWw9PT0nQUwnKTsKICB9KTsKICBpZihib3RoQnV5Lmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLWdyZWVuKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+4pqhIDFHICsgMUggQWwgU2lueWFsaTwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7ZmxleC13cmFwOndyYXA7Z2FwOjhweCIgaWQ9ImJvdGhCdXlDb250YWluZXIiPjwvZGl2PjwvZGl2Pic7CiAgfQoKICAvLyBUb3AgMyBlbnRyeSBzY29yZQogIHZhciB0b3BFbnRyeSA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSkuc29ydChmdW5jdGlvbihhLGIpe3JldHVybiBiLmVudHJ5X3Njb3JlLWEuZW50cnlfc2NvcmU7fSkuc2xpY2UoMCwzKTsKICBpZih0b3BFbnRyeS5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+OryBFbiDEsHlpIEdpcmnFnyBLYWxpdGVzaTwvZGl2Pic7CiAgICB2YXIgbWVkYWxzID0gWyfwn6WHJywn8J+liCcsJ/CfpYknXTsKICAgIHRvcEVudHJ5LmZvckVhY2goZnVuY3Rpb24ocixpKXsKICAgICAgdmFyIGVzY29sID0gci5lbnRyeV9zY29yZT49NzU/J3ZhcigtLWdyZWVuKSc6ci5lbnRyeV9zY29yZT49NjA/J3ZhcigtLWdyZWVuMiknOid2YXIoLS15ZWxsb3cpJzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCIgaWQ9InRlLScgKyByLnRpY2tlciArICciPic7CiAgICAgIGggKz0gJzxzcGFuPicgKyBtZWRhbHNbaV0gKyAnIDxzdHJvbmc+JyArIHIudGlja2VyICsgJzwvc3Ryb25nPiA8c3BhbiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nICsgci5zaW55YWwgKyAnPC9zcGFuPjwvc3Bhbj4nOwogICAgICBoICs9ICc8c3BhbiBzdHlsZT0iZm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyBlc2NvbCArICciPicgKyByLmVudHJ5X3Njb3JlICsgJy8xMDA8L3NwYW4+PC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFN0b3AgeWFraW4KICB2YXIgbmVhclN0b3AgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpewogICAgaWYoci5oYXRhfHwhUE9SVC5pbmNsdWRlcyhyLnRpY2tlcil8fCFyLnN0b3ApIHJldHVybiBmYWxzZTsKICAgIHJldHVybiAoci5maXlhdC1yLnN0b3ApL3IuZml5YXQqMTAwIDwgODsKICB9KS5zb3J0KGZ1bmN0aW9uKGEsYil7cmV0dXJuIChhLmZpeWF0LWEuc3RvcCkvYS5maXlhdC0oYi5maXlhdC1iLnN0b3ApL2IuZml5YXQ7fSk7CiAgaWYobmVhclN0b3AubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLXJlZDIpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7imqDvuI8gU3RvcCBTZXZpeWVzaW5lIFlha8SxbjwvZGl2Pic7CiAgICBuZWFyU3RvcC5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgICB2YXIgZGlzdCA9IE1hdGgucm91bmQoKHIuZml5YXQtci5zdG9wKS9yLmZpeWF0KjEwMDApLzEwOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO3BhZGRpbmc6OHB4IDEycHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6OHB4O21hcmdpbi1ib3R0b206NXB4IiBpZD0ibnMtJyArIHIudGlja2VyICsgJyI+JzsKICAgICAgaCArPSAnPHN0cm9uZz4nICsgci50aWNrZXIgKyAnPC9zdHJvbmc+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tcmVkMik7Zm9udC13ZWlnaHQ6NjAwIj5TdG9wICQnICsgci5zdG9wICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+VXpha2zEsWs6ICUnICsgZGlzdCArICc8L2Rpdj48L2Rpdj48L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gSGVkZWZlIHlha2luCiAgdmFyIG5lYXJUYXJnZXQgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpewogICAgaWYoci5oYXRhfHwhUE9SVC5pbmNsdWRlcyhyLnRpY2tlcil8fCFyLmhlZGVmKSByZXR1cm4gZmFsc2U7CiAgICByZXR1cm4gKHIuaGVkZWYtci5maXlhdCkvci5maXlhdCoxMDAgPCAxNTsKICB9KS5zb3J0KGZ1bmN0aW9uKGEsYil7cmV0dXJuIChhLmhlZGVmLWEuZml5YXQpL2EuZml5YXQtKGIuaGVkZWYtYi5maXlhdCkvYi5maXlhdDt9KTsKICBpZihuZWFyVGFyZ2V0Lmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOiM2MGE1ZmE7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfjq8gSGVkZWZlIFlha8SxbjwvZGl2Pic7CiAgICBuZWFyVGFyZ2V0LmZvckVhY2goZnVuY3Rpb24ocil7CiAgICAgIHZhciBkaXN0ID0gTWF0aC5yb3VuZCgoci5oZWRlZi1yLmZpeWF0KS9yLmZpeWF0KjEwMDApLzEwOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO3BhZGRpbmc6OHB4IDEycHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6OHB4O21hcmdpbi1ib3R0b206NXB4Ij4nOwogICAgICBoICs9ICc8c3Ryb25nPicgKyByLnRpY2tlciArICc8L3N0cm9uZz4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij48ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjojNjBhNWZhO2ZvbnQtd2VpZ2h0OjYwMCI+SGVkZWYgJCcgKyByLmhlZGVmICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+S2FsZGk6ICUnICsgZGlzdCArICc8L2Rpdj48L2Rpdj48L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gRWFybmluZ3MKICB2YXIgdXJnZW50RSA9IEVBUk5JTkdTX0RBVEEuZmlsdGVyKGZ1bmN0aW9uKGUpe3JldHVybiBlLmRheXNfdG9fZWFybmluZ3MhPW51bGwmJmUuZGF5c190b19lYXJuaW5nczw9MTQ7fSkuc29ydChmdW5jdGlvbihhLGIpe3JldHVybiBhLmRheXNfdG9fZWFybmluZ3MtYi5kYXlzX3RvX2Vhcm5pbmdzO30pOwogIGlmKHVyZ2VudEUubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0teWVsbG93KTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+ThSBZYWtsYcWfYW4gUmFwb3JsYXI8L2Rpdj4nOwogICAgdXJnZW50RS5mb3JFYWNoKGZ1bmN0aW9uKGUpewogICAgICB2YXIgaWMgPSBlLmFsZXJ0PT09J3JlZCc/J/CflLQnOifwn5+hJzsKICAgICAgdmFyIGluUG9ydCA9IFBPUlQuaW5jbHVkZXMoZS50aWNrZXIpOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO3BhZGRpbmc6OHB4IDEycHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6OHB4O21hcmdpbi1ib3R0b206NXB4Ij4nOwogICAgICBoICs9ICc8c3Bhbj4nICsgaWMgKyAnIDxzdHJvbmc+JyArIGUudGlja2VyICsgJzwvc3Ryb25nPicgKyAoaW5Qb3J0PycgPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6MTBweCI+UDwvc3Bhbj4nOicnKSArICc8L3NwYW4+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKTtmb250LXNpemU6MTFweCI+JyArIGUubmV4dF9kYXRlICsgJyAoJyArIGUuZGF5c190b19lYXJuaW5ncyArICcgZ8O8bik8L3NwYW4+PC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFZJWAogIHZhciB2aXggPSBtZC5WSVggfHwge307CiAgaWYodml4LnByaWNlKXsKICAgIHZhciB2Q29sID0gdml4LnByaWNlPjMwPyd2YXIoLS1yZWQyKSc6dml4LnByaWNlPjIwPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tZ3JlZW4pJzsKICAgIHZhciB2TGJsID0gdml4LnByaWNlPjMwPydZw7xrc2VrIEtvcmt1IOKAlCBZZW5pIHBvemlzeW9uIGHDp21hJzp2aXgucHJpY2U+MjA/J09ydGEgVm9sYXRpbGl0ZSDigJQgRGlra2F0bGkgb2wnOidEw7zFn8O8ayBWb2xhdGlsaXRlIOKAlCBOb3JtYWwga2/Fn3VsbGFyJzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTRweCAxNnB4O21hcmdpbi1ib3R0b206MTBweDtkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyIj4nOwogICAgaCArPSAnPGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbToycHgiPlZJWDwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOicgKyB2Q29sICsgJyI+JyArIHZMYmwgKyAnPC9kaXY+PC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgdkNvbCArICciPicgKyB2aXgucHJpY2UgKyAnPC9kaXY+PC9kaXY+JzsKICB9CgogIC8vIFBvcnRmb2x5byBkZXRheQogIGlmKHBvcnQubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkrwgUG9ydGbDtnk8L2Rpdj4nOwogICAgcG9ydC5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0pe2ggKz0gcGVyZlJvdyhpdGVtKTt9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBXYXRjaGxpc3QKICBpZih3YXRjaC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+RgSBXYXRjaGxpc3Q8L2Rpdj4nOwogICAgd2F0Y2guZm9yRWFjaChmdW5jdGlvbihpdGVtKXtoICs9IHBlcmZSb3coaXRlbSk7fSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgaCArPSAnPC9kaXY+JzsKICBncmlkLmlubmVySFRNTCA9IGg7CgogIC8vIEFkZCBvbmNsaWNrIHZpYSBKUyAoYXZvaWRzIHF1b3RlIG5lc3RpbmcgaXNzdWVzKQogIGJvdGhCdXkuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBjbnQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnYm90aEJ1eUNvbnRhaW5lcicpOwogICAgaWYoIWNudCkgcmV0dXJuOwogICAgdmFyIGQgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgIGQuc3R5bGUuY3NzVGV4dCA9ICdiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjMpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6OHB4IDE0cHg7Y3Vyc29yOnBvaW50ZXInOwogICAgZC5pbm5lckhUTUwgPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2xldHRlci1zcGFjaW5nOjJweDtjb2xvcjp2YXIoLS1ncmVlbikiPicgKyByLnRpY2tlciArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkdpcmlzOiAnICsgci5lbnRyeV9zY29yZSArICcvMTAwPC9kaXY+JzsKICAgIGQub25jbGljayA9IChmdW5jdGlvbih0KXtyZXR1cm4gZnVuY3Rpb24oKXtvcGVuTSh0KTt9O30pKHIudGlja2VyKTsKICAgIGNudC5hcHBlbmRDaGlsZChkKTsKICB9KTsKICB0b3BFbnRyeS5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3RlLScgKyByLnRpY2tlcik7CiAgICBpZihlbCkgZWwub25jbGljayA9IChmdW5jdGlvbih0KXtyZXR1cm4gZnVuY3Rpb24oKXtvcGVuTSh0KTt9O30pKHIudGlja2VyKSwgZWwuc3R5bGUuY3Vyc29yPSdwb2ludGVyJzsKICB9KTsKICBuZWFyU3RvcC5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ25zLScgKyByLnRpY2tlcik7CiAgICBpZihlbCkgZWwub25jbGljayA9IChmdW5jdGlvbih0KXtyZXR1cm4gZnVuY3Rpb24oKXtvcGVuTSh0KTt9O30pKHIudGlja2VyKSwgZWwuc3R5bGUuY3Vyc29yPSdwb2ludGVyJzsKICB9KTsKfQoKPC9ib2R5Pgo8L2h0bWw+"
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
