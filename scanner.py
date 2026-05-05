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
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY', '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')
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
    _T = "PCFET0NUWVBFIGh0bWw+CjxodG1sIGxhbmc9InRyIj4KPGhlYWQ+CjxtZXRhIGNoYXJzZXQ9IlVURi04Ii8+CjxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsaW5pdGlhbC1zY2FsZT0xIi8+Cjx0aXRsZT5DQU5TTElNIFNjYW5uZXI8L3RpdGxlPgo8bGluayByZWw9Imljb24iIHR5cGU9ImltYWdlL3N2Zyt4bWwiIGhyZWY9ImRhdGE6aW1hZ2Uvc3ZnK3htbCwlM0NzdmcgeG1sbnM9J2h0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnJyB2aWV3Qm94PScwIDAgMzIgMzInJTNFJTNDcmVjdCB3aWR0aD0nMzInIGhlaWdodD0nMzInIHJ4PSc2JyBmaWxsPSclMjMwZDExMTcnLyUzRSUzQ3BvbHlsaW5lIHBvaW50cz0nNCwyNCAxMCwxNiAxNiwyMCAyMiwxMCAyOCwxNCcgZmlsbD0nbm9uZScgc3Ryb2tlPSclMjMxMGI5ODEnIHN0cm9rZS13aWR0aD0nMi41JyBzdHJva2UtbGluZWNhcD0ncm91bmQnIHN0cm9rZS1saW5lam9pbj0ncm91bmQnLyUzRSUzQy9zdmclM0UiPgo8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PVNwYWNlK0dyb3Rlc2s6d2dodEA0MDA7NTAwOzYwMDs3MDAmZmFtaWx5PUJlYmFzK05ldWUmZmFtaWx5PUpldEJyYWlucytNb25vOndnaHRANDAwOzYwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCIvPgo8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9jaGFydC5qc0A0LjQuMC9kaXN0L2NoYXJ0LnVtZC5taW4uanMiPjwvc2NyaXB0Pgo8c3R5bGU+Cjpyb290ey0tYmc6IzA1MDcwZjstLWJnMjojMGQxMTE3Oy0tYmczOiMxNjFiMjQ7LS1ib3JkZXI6cmdiYSgyNTUsMjU1LDI1NSwwLjA4KTstLXRleHQ6I2UyZThmMDstLW11dGVkOiM0YjU1NjM7LS1ncmVlbjojMTBiOTgxOy0tZ3JlZW4yOiMzNGQzOTk7LS1yZWQ6I2VmNDQ0NDstLXJlZDI6I2Y4NzE3MTstLXllbGxvdzojZjU5ZTBiO30KKntib3gtc2l6aW5nOmJvcmRlci1ib3g7bWFyZ2luOjA7cGFkZGluZzowfQpib2R5e2JhY2tncm91bmQ6dmFyKC0tYmcpO2NvbG9yOnZhcigtLXRleHQpO2ZvbnQtZmFtaWx5OidTcGFjZSBHcm90ZXNrJyxzYW5zLXNlcmlmO21pbi1oZWlnaHQ6MTAwdmh9Ci5oZWFkZXJ7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCMwZDExMTcsIzExMTgyNyk7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtwYWRkaW5nOjE0cHggMjBweDtwb3NpdGlvbjpzdGlja3k7dG9wOjA7ei1pbmRleDoxMDB9Ci5oZWFkZXItaW5uZXJ7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTBweDttYXgtd2lkdGg6MTQwMHB4O21hcmdpbjowIGF1dG99Ci5sb2dvLW1haW57Zm9udC1mYW1pbHk6J0JlYmFzIE5ldWUnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjIycHg7bGV0dGVyLXNwYWNpbmc6NHB4O2JhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZywjMTBiOTgxLCMzYjgyZjYpOy13ZWJraXQtYmFja2dyb3VuZC1jbGlwOnRleHQ7LXdlYmtpdC10ZXh0LWZpbGwtY29sb3I6dHJhbnNwYXJlbnR9Ci50aW1lc3RhbXB7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtZmFtaWx5OidKZXRCcmFpbnMgTW9ubycsbW9ub3NwYWNlfQoubGl2ZS1kb3R7d2lkdGg6N3B4O2hlaWdodDo3cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDp2YXIoLS1ncmVlbik7YW5pbWF0aW9uOnB1bHNlIDJzIGluZmluaXRlO2Rpc3BsYXk6aW5saW5lLWJsb2NrO21hcmdpbi1yaWdodDo1cHh9CkBrZXlmcmFtZXMgcHVsc2V7MCUsMTAwJXtvcGFjaXR5OjE7Ym94LXNoYWRvdzowIDAgMCAwIHJnYmEoMTYsMTg1LDEyOSwuNCl9NTAle29wYWNpdHk6Ljc7Ym94LXNoYWRvdzowIDAgMCA2cHggcmdiYSgxNiwxODUsMTI5LDApfX0KLm5hdntkaXNwbGF5OmZsZXg7Z2FwOjRweDtwYWRkaW5nOjEwcHggMjBweDtib3JkZXItYm90dG9tOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmcyKTtvdmVyZmxvdy14OmF1dG87ZmxleC13cmFwOndyYXB9Ci50YWJ7cGFkZGluZzo2cHggMTRweDtib3JkZXItcmFkaXVzOjZweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo1MDA7Ym9yZGVyOjFweCBzb2xpZCB0cmFuc3BhcmVudDtiYWNrZ3JvdW5kOm5vbmU7Y29sb3I6dmFyKC0tbXV0ZWQpO3RyYW5zaXRpb246YWxsIC4yczt3aGl0ZS1zcGFjZTpub3dyYXB9Ci50YWI6aG92ZXJ7Y29sb3I6dmFyKC0tdGV4dCk7YmFja2dyb3VuZDp2YXIoLS1iZzMpfQoudGFiLmFjdGl2ZXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Y29sb3I6dmFyKC0tdGV4dCk7Ym9yZGVyLWNvbG9yOnZhcigtLWJvcmRlcil9Ci50YWIucG9ydC5hY3RpdmV7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXItY29sb3I6cmdiYSgxNiwxODUsMTI5LC4zKX0KLnRmLXJvd3tkaXNwbGF5OmZsZXg7Z2FwOjZweDtwYWRkaW5nOjEwcHggMjBweDtib3JkZXItYm90dG9tOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmcyKTthbGlnbi1pdGVtczpjZW50ZXI7ZmxleC13cmFwOndyYXB9Ci50Zi1idG57cGFkZGluZzo1cHggMTJweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTFweDtjdXJzb3I6cG9pbnRlcjtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLW11dGVkKTtmb250LWZhbWlseTonSmV0QnJhaW5zIE1vbm8nLG1vbm9zcGFjZTt0cmFuc2l0aW9uOmFsbCAuMnN9Ci50Zi1idG4uYWN0aXZle2JhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4xNSk7Y29sb3I6IzYwYTVmYTtib3JkZXItY29sb3I6cmdiYSg1OSwxMzAsMjQ2LC40KX0KLnRmLWJ0bi5zdGFye3Bvc2l0aW9uOnJlbGF0aXZlfQoudGYtYnRuLnN0YXI6OmFmdGVye2NvbnRlbnQ6J+KYhSc7cG9zaXRpb246YWJzb2x1dGU7dG9wOi01cHg7cmlnaHQ6LTRweDtmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLXllbGxvdyl9Ci50Zi1oaW50e2ZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKX0KLnN0YXRze2Rpc3BsYXk6ZmxleDtnYXA6OHB4O3BhZGRpbmc6MTBweCAyMHB4O2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2ZsZXgtd3JhcDp3cmFwfQoucGlsbHtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo1cHg7cGFkZGluZzo0cHggMTBweDtib3JkZXItcmFkaXVzOjIwcHg7Zm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwO2JvcmRlcjoxcHggc29saWR9Ci5waWxsLmd7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXItY29sb3I6cmdiYSgxNiwxODUsMTI5LC4yNSl9Ci5waWxsLnJ7YmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMSk7Y29sb3I6dmFyKC0tcmVkMik7Ym9yZGVyLWNvbG9yOnJnYmEoMjM5LDY4LDY4LC4yNSl9Ci5waWxsLnl7YmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjEpO2NvbG9yOnZhcigtLXllbGxvdyk7Ym9yZGVyLWNvbG9yOnJnYmEoMjQ1LDE1OCwxMSwuMjUpfQoucGlsbC5ie2JhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4xKTtjb2xvcjojNjBhNWZhO2JvcmRlci1jb2xvcjpyZ2JhKDU5LDEzMCwyNDYsLjI1KX0KLnBpbGwubXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Y29sb3I6dmFyKC0tbXV0ZWQpO2JvcmRlci1jb2xvcjp2YXIoLS1ib3JkZXIpfQouZG90e3dpZHRoOjVweDtoZWlnaHQ6NXB4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6Y3VycmVudENvbG9yfQoubWFpbntwYWRkaW5nOjE0cHggMjBweDttYXgtd2lkdGg6MTQwMHB4O21hcmdpbjowIGF1dG99Ci5ncmlke2Rpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMzAwcHgsMWZyKSk7Z2FwOjEwcHh9CkBtZWRpYShtYXgtd2lkdGg6NDgwcHgpey5ncmlke2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnJ9fQouY2FyZHtiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtvdmVyZmxvdzpoaWRkZW47Y3Vyc29yOnBvaW50ZXI7dHJhbnNpdGlvbjphbGwgLjJzfQouY2FyZDpob3Zlcnt0cmFuc2Zvcm06dHJhbnNsYXRlWSgtMnB4KTtib3gtc2hhZG93OjAgOHB4IDI0cHggcmdiYSgwLDAsMCwuNCl9Ci5hY2NlbnR7aGVpZ2h0OjNweH0KLmNib2R5e3BhZGRpbmc6MTJweCAxNHB4fQouY3RvcHtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6ZmxleC1zdGFydDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjhweH0KLnRpY2tlcntmb250LWZhbWlseTonQmViYXMgTmV1ZScsc2Fucy1zZXJpZjtmb250LXNpemU6MjBweDtsZXR0ZXItc3BhY2luZzoycHg7bGluZS1oZWlnaHQ6MX0KLmNwcnt0ZXh0LWFsaWduOnJpZ2h0fQoucHZhbHtmb250LWZhbWlseTonSmV0QnJhaW5zIE1vbm8nLG1vbm9zcGFjZTtmb250LXNpemU6MTVweDtmb250LXdlaWdodDo2MDB9Ci5wY2hne2ZvbnQtc2l6ZToxMXB4O2ZvbnQtZmFtaWx5OidKZXRCcmFpbnMgTW9ubycsbW9ub3NwYWNlO21hcmdpbi10b3A6MnB4fQouYmFkZ2V7ZGlzcGxheTppbmxpbmUtYmxvY2s7cGFkZGluZzoycHggOHB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZToxMHB4O2ZvbnQtd2VpZ2h0OjcwMDtsZXR0ZXItc3BhY2luZzouNXB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tdG9wOjNweH0KLnBvcnQtYmFkZ2V7ZGlzcGxheTppbmxpbmUtZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjNweDtwYWRkaW5nOjJweCA2cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo2MDA7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEyKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjI1KTttYXJnaW4tbGVmdDo1cHh9Ci5zaWdze2Rpc3BsYXk6ZmxleDtmbGV4LXdyYXA6d3JhcDtnYXA6M3B4O21hcmdpbi1ib3R0b206OHB4fQouc3B7Zm9udC1zaXplOjlweDtwYWRkaW5nOjJweCA2cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1mYW1pbHk6J0pldEJyYWlucyBNb25vJyxtb25vc3BhY2V9Ci5zZ3tiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMSk7Y29sb3I6dmFyKC0tZ3JlZW4yKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMil9Ci5zYntiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xKTtjb2xvcjp2YXIoLS1yZWQyKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKX0KLnNue2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpfQouY2hhcnQtd3toZWlnaHQ6NzVweDttYXJnaW4tdG9wOjhweH0KLmx2bHN7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoMywxZnIpO2dhcDo1cHg7bWFyZ2luLXRvcDo4cHh9Ci5sdntiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo1cHg7cGFkZGluZzo2cHg7dGV4dC1hbGlnbjpjZW50ZXI7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpfQoubGx7Zm9udC1zaXplOjhweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjJweH0KLmx2YWx7Zm9udC1mYW1pbHk6J0pldEJyYWlucyBNb25vJyxtb25vc3BhY2U7Zm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwfQoub3ZlcmxheXtwb3NpdGlvbjpmaXhlZDtpbnNldDowO2JhY2tncm91bmQ6cmdiYSgwLDAsMCwuODgpO3otaW5kZXg6MTAwMDtkaXNwbGF5Om5vbmU7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7cGFkZGluZzoxNnB4fQoub3ZlcmxheS5vcGVue2Rpc3BsYXk6ZmxleH0KLm1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjUyMHB4O21heC1oZWlnaHQ6OTJ2aDtvdmVyZmxvdy15OmF1dG99Ci5taGVhZHtwYWRkaW5nOjE4cHggMThweCAwO2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpmbGV4LXN0YXJ0fQoubXRpdGxle2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZTozMHB4O2xldHRlci1zcGFjaW5nOjNweH0KLm1jbG9zZXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTt3aWR0aDozMHB4O2hlaWdodDozMHB4O2JvcmRlci1yYWRpdXM6N3B4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxNXB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcn0KLm1ib2R5e3BhZGRpbmc6MTRweCAxOHB4IDE4cHh9Ci5tY2hhcnR3e2hlaWdodDoxNTBweDttYXJnaW4tYm90dG9tOjE0cHh9Ci5kZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjdweDttYXJnaW4tYm90dG9tOjEycHh9Ci5kY3tiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo3cHg7cGFkZGluZzo5cHggMTFweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5kbHtmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206M3B4fQouZHZ7Zm9udC1mYW1pbHk6J0pldEJyYWlucyBNb25vJyxtb25vc3BhY2U7Zm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwfQouZGJveHtib3JkZXItcmFkaXVzOjlweDtwYWRkaW5nOjEzcHg7bWFyZ2luLWJvdHRvbToxMnB4O2JvcmRlcjoxcHggc29saWR9Ci5kbGJse2ZvbnQtc2l6ZTo5cHg7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjVweH0KLmR2ZXJke2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyNnB4O2xldHRlci1zcGFjaW5nOjJweDttYXJnaW4tYm90dG9tOjhweH0KLmRyb3d7ZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206NHB4O2ZvbnQtc2l6ZToxMnB4fQouZGtleXtjb2xvcjp2YXIoLS1tdXRlZCl9Ci5ycmJhcntoZWlnaHQ6NHB4O2JhY2tncm91bmQ6dmFyKC0tYmcpO2JvcmRlci1yYWRpdXM6MnB4O21hcmdpbi10b3A6N3B4O292ZXJmbG93OmhpZGRlbn0KLnJyZmlsbHtoZWlnaHQ6MTAwJTtib3JkZXItcmFkaXVzOjJweDt0cmFuc2l0aW9uOndpZHRoIC44cyBlYXNlfQoudnBib3h7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6N3B4O3BhZGRpbmc6MTBweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7bWFyZ2luLWJvdHRvbToxMnB4fQoudnB0aXRsZXtmb250LXNpemU6OXB4O2NvbG9yOiM2MGE1ZmE7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjdweH0KLnZwZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgzLDFmcik7Z2FwOjVweH0KLnZwY3tiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyLXJhZGl1czo1cHg7cGFkZGluZzo3cHg7dGV4dC1hbGlnbjpjZW50ZXI7Ym9yZGVyOjFweCBzb2xpZH0KLm1pbmZve2Rpc3BsYXk6aW5saW5lLWZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7d2lkdGg6MTRweDtoZWlnaHQ6MTRweDtib3JkZXItcmFkaXVzOjUwJTtiYWNrZ3JvdW5kOnJnYmEoOTYsMTY1LDI1MCwuMik7Y29sb3I6IzYwYTVmYTtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjcwMDtjdXJzb3I6cG9pbnRlcjttYXJnaW4tbGVmdDo0cHg7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDk2LDE2NSwyNTAsLjMpfQoubWluZm8tcG9wdXB7cG9zaXRpb246Zml4ZWQ7aW5zZXQ6MDtiYWNrZ3JvdW5kOnJnYmEoMCwwLDAsLjg4KTt6LWluZGV4OjIwMDA7ZGlzcGxheTpub25lO2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO3BhZGRpbmc6MTZweH0KLm1pbmZvLXBvcHVwLm9wZW57ZGlzcGxheTpmbGV4fQoubWluZm8tbW9kYWx7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjE0cHg7d2lkdGg6MTAwJTttYXgtd2lkdGg6NDgwcHg7bWF4LWhlaWdodDo4NXZoO292ZXJmbG93LXk6YXV0bztwYWRkaW5nOjIwcHg7cG9zaXRpb246cmVsYXRpdmV9Ci5taW5mby10aXRsZXtmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCk7bWFyZ2luLWJvdHRvbTo0cHh9Ci5taW5mby1zb3VyY2V7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MTJweDtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo2cHg7ZmxleC13cmFwOndyYXB9Ci5taW5mby1yZWx7cGFkZGluZzoycHggN3B4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwfQoubWluZm8tcmVsLmhpZ2h7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtjb2xvcjojMTBiOTgxfQoubWluZm8tcmVsLm1lZGl1bXtiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMTUpO2NvbG9yOiNmNTllMGJ9Ci5taW5mby1yZWwubG93e2JhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtjb2xvcjojZWY0NDQ0fQoubWluZm8tZGVzY3tmb250LXNpemU6MTJweDtjb2xvcjojOTRhM2I4O2xpbmUtaGVpZ2h0OjEuNjttYXJnaW4tYm90dG9tOjE0cHh9Ci5taW5mby13YXJuaW5ne2JhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6NnB4O3BhZGRpbmc6OHB4IDEwcHg7Zm9udC1zaXplOjExcHg7Y29sb3I6I2Y1OWUwYjttYXJnaW4tYm90dG9tOjE0cHh9Ci5taW5mby1yYW5nZXN7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8tcmFuZ2UtdGl0bGV7Zm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweH0KLm1pbmZvLXJhbmdle2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjhweDttYXJnaW4tYm90dG9tOjZweDtwYWRkaW5nOjZweCA4cHg7Ym9yZGVyLXJhZGl1czo2cHg7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wMil9Ci5taW5mby1yYW5nZS1kb3R7d2lkdGg6OHB4O2hlaWdodDo4cHg7Ym9yZGVyLXJhZGl1czo1MCU7ZmxleC1zaHJpbms6MH0KLm1pbmZvLWNhbnNsaW17YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czo2cHg7cGFkZGluZzo4cHggMTBweDtmb250LXNpemU6MTFweDtjb2xvcjojNjBhNWZhfQoubWluZm8tY2xvc2V7cG9zaXRpb246YWJzb2x1dGU7dG9wOjE2cHg7cmlnaHQ6MTZweDtiYWNrZ3JvdW5kOnJnYmEoMjU1LDI1NSwyNTUsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjEpO2NvbG9yOiM5NGEzYjg7d2lkdGg6MjhweDtoZWlnaHQ6MjhweDtib3JkZXItcmFkaXVzOjdweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTRweDtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXJ9Cjo6LXdlYmtpdC1zY3JvbGxiYXJ7d2lkdGg6NHB4O2hlaWdodDo0cHh9Cjo6LXdlYmtpdC1zY3JvbGxiYXItdHJhY2t7YmFja2dyb3VuZDp2YXIoLS1iZyl9Cjo6LXdlYmtpdC1zY3JvbGxiYXItdGh1bWJ7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4xKTtib3JkZXItcmFkaXVzOjJweH0KPC9zdHlsZT4KPC9oZWFkPgo8Ym9keT4KPGRpdiBjbGFzcz0iaGVhZGVyIj4KICA8ZGl2IGNsYXNzPSJoZWFkZXItaW5uZXIiPgogICAgPHNwYW4gY2xhc3M9ImxvZ28tbWFpbiI+Q0FOU0xJTSBTQ0FOTkVSPC9zcGFuPgogICAgPHNwYW4gY2xhc3M9InRpbWVzdGFtcCI+PHNwYW4gY2xhc3M9ImxpdmUtZG90Ij48L3NwYW4+JSVUSU1FU1RBTVAlJTwvc3Bhbj4KICAgIDxidXR0b24gb25jbGljaz0ib3BlbkVkaXRMaXN0KCkiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4zKTtjb2xvcjojNjBhNWZhO3BhZGRpbmc6NXB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1mYW1pbHk6aW5oZXJpdCI+4pyP77iPIExpc3RleWkgRMO8emVubGU8L2J1dHRvbj4KICA8L2Rpdj4KPC9kaXY+CjxkaXYgY2xhc3M9Im5hdiI+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIGFjdGl2ZSIgb25jbGljaz0ic2V0VGFiKCdkYXNoYm9hcmQnLHRoaXMpIj7wn4+gIERhc2hib2FyZDwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdhbGwnLHRoaXMpIj7wn5OKIEhpc3NlbGVyPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIHBvcnQiIG9uY2xpY2s9InNldFRhYigncG9ydCcsdGhpcykiPvCfkrwgUG9ydGbDtnnDvG08L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignYnV5Jyx0aGlzKSI+8J+TiCBBbDwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdzZWxsJyx0aGlzKSI+8J+TiSBTYXQ8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignZWFybmluZ3MnLHRoaXMpIj7wn5OFIEVhcm5pbmdzPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ3J1dGluJyx0aGlzKSI+4pyFIFJ1dGluPC9idXR0b24+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJ0Zi1yb3ciIGlkPSJ0ZlJvdyIgc3R5bGU9ImRpc3BsYXk6bm9uZSI+CiAgPGJ1dHRvbiBjbGFzcz0idGYtYnRuIGFjdGl2ZSIgZGF0YS10Zj0iMWQiIG9uY2xpY2s9InNldFRmKCcxZCcsdGhpcykiPjFHPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGYtYnRuIHN0YXIiIGRhdGEtdGY9IjF3ayIgb25jbGljaz0ic2V0VGYoJzF3aycsdGhpcykiPjFIPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGYtYnRuIiBkYXRhLXRmPSIxbW8iIG9uY2xpY2s9InNldFRmKCcxbW8nLHRoaXMpIj4xQTwvYnV0dG9uPgogIDxzcGFuIGNsYXNzPSJ0Zi1oaW50Ij5DQU5TTElNIMO2bmVyaWxlbjogMUcgKyAxSDwvc3Bhbj4KPC9kaXY+CjxkaXYgY2xhc3M9InN0YXRzIiBpZD0ic3RhdHMiPjwvZGl2Pgo8ZGl2IGNsYXNzPSJtYWluIj48ZGl2IGNsYXNzPSJncmlkIiBpZD0iZ3JpZCI+PC9kaXY+PC9kaXY+CjxkaXYgY2xhc3M9Im92ZXJsYXkiIGlkPSJvdmVybGF5IiBvbmNsaWNrPSJjbG9zZU0oZXZlbnQpIj4KICA8ZGl2IGNsYXNzPSJtb2RhbCIgaWQ9Im1vZGFsIj48L2Rpdj4KPC9kaXY+Cgo8ZGl2IGNsYXNzPSJtaW5mby1wb3B1cCIgaWQ9ImVkaXRQb3B1cCIgb25jbGljaz0iY2xvc2VFZGl0UG9wdXAoZXZlbnQpIj4KICA8ZGl2IGNsYXNzPSJtaW5mby1tb2RhbCIgc3R5bGU9InBvc2l0aW9uOnJlbGF0aXZlO21heC13aWR0aDo1NjBweCIgaWQ9ImVkaXRNb2RhbCI+CiAgICA8YnV0dG9uIGNsYXNzPSJtaW5mby1jbG9zZSIgb25jbGljaz0iY2xvc2VFZGl0UG9wdXAoKSI+4pyVPC9idXR0b24+CiAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCk7bWFyZ2luLWJvdHRvbTo0cHgiPuKcj++4jyBMaXN0ZXlpIETDvHplbmxlPC9kaXY+CiAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbToxNnB4Ij5HaXRIdWIgQVBJIGtleSBnZXJla2xpIOKAlCBkZcSfacWfaWtsaWtsZXIgYW7EsW5kYSBrYXlkZWRpbGlyPC9kaXY+CiAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjE2cHg7bWFyZ2luLWJvdHRvbToxNnB4Ij4KICAgICAgPGRpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+8J+TiyBXYXRjaGxpc3Q8L2Rpdj4KICAgICAgICA8ZGl2IGlkPSJ3YXRjaGxpc3RFZGl0b3IiPjwvZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6NnB4O21hcmdpbi10b3A6OHB4Ij4KICAgICAgICAgIDxpbnB1dCBpZD0ibmV3V2F0Y2hUaWNrZXIiIHBsYWNlaG9sZGVyPSJIaXNzZSBla2xlIChUU0xBKSIgc3R5bGU9ImZsZXg6MTtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLXRleHQpO3BhZGRpbmc6NnB4IDEwcHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Zm9udC1mYW1pbHk6aW5oZXJpdDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2UiLz4KICAgICAgICAgIDxidXR0b24gb25jbGljaz0iYWRkVGlja2VyKCd3YXRjaCcpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6NnB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Y3Vyc29yOnBvaW50ZXIiPisgRWtsZTwvYnV0dG9uPgogICAgICAgIDwvZGl2PgogICAgICA8L2Rpdj4KICAgICAgPGRpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+8J+SvCBQb3J0ZsO2eTwvZGl2PgogICAgICAgIDxkaXYgaWQ9InBvcnRmb2xpb0VkaXRvciI+PC9kaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo2cHg7bWFyZ2luLXRvcDo4cHgiPgogICAgICAgICAgPGlucHV0IGlkPSJuZXdQb3J0VGlja2VyIiBwbGFjZWhvbGRlcj0iSGlzc2UgZWtsZSAoQUFQTCkiIHN0eWxlPSJmbGV4OjE7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS10ZXh0KTtwYWRkaW5nOjZweCAxMHB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2ZvbnQtZmFtaWx5OmluaGVyaXQ7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlIi8+CiAgICAgICAgICA8YnV0dG9uIG9uY2xpY2s9ImFkZFRpY2tlcigncG9ydCcpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6NnB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Y3Vyc29yOnBvaW50ZXIiPisgRWtsZTwvYnV0dG9uPgogICAgICAgIDwvZGl2PgogICAgICA8L2Rpdj4KICAgIDwvZGl2PgogICAgPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDEycHg7bWFyZ2luLWJvdHRvbToxNHB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLWdyZWVuKSI+4pyFIERlxJ9pxZ9pa2xpa2xlciBrYXlkZWRpbGluY2UgYmlyIHNvbnJha2kgQ29sYWIgw6dhbMSxxZ90xLFybWFzxLFuZGEgYWt0aWYgb2x1ci48L2Rpdj4KPGRpdiBzdHlsZT0ibWFyZ2luLWJvdHRvbToxMnB4Ij4KICAgICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NXB4Ij5HaXRIdWIgVG9rZW4gKGJpciBrZXogZ2lyLCB0YXJheWljaSBoYXRpcmxheWFjYWspPC9kaXY+CiAgICAgIDxpbnB1dCBpZD0iZ2hUb2tlbklucHV0IiBwbGFjZWhvbGRlcj0iZ2hwXy4uLiIgc3R5bGU9IndpZHRoOjEwMCU7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS10ZXh0KTtwYWRkaW5nOjhweCAxMHB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMXB4O2ZvbnQtZmFtaWx5OidKZXRCcmFpbnMgTW9ubycsbW9ub3NwYWNlIi8+CiAgICA8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6OHB4Ij4KICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJzYXZlTGlzdFRvR2l0aHViKCkiIHN0eWxlPSJmbGV4OjE7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6MTBweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y3Vyc29yOnBvaW50ZXIiPvCfkr4gR2l0SHViJ2EgS2F5ZGV0PC9idXR0b24+CiAgICAgIDxidXR0b24gb25jbGljaz0iY2xvc2VFZGl0UG9wdXAoKSIgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tbXV0ZWQpO3BhZGRpbmc6MTBweCAxNnB4O2JvcmRlci1yYWRpdXM6OHB4O2ZvbnQtc2l6ZToxM3B4O2N1cnNvcjpwb2ludGVyIj7EsHB0YWw8L2J1dHRvbj4KICAgIDwvZGl2PgogICAgPGRpdiBpZD0iZWRpdFN0YXR1cyIgc3R5bGU9Im1hcmdpbi10b3A6MTBweDtmb250LXNpemU6MTJweDt0ZXh0LWFsaWduOmNlbnRlciI+PC9kaXY+CiAgPC9kaXY+CjwvZGl2PgoKPGRpdiBjbGFzcz0ibWluZm8tcG9wdXAiIGlkPSJtaW5mb1BvcHVwIiBvbmNsaWNrPSJjbG9zZUluZm9Qb3B1cChldmVudCkiPgogIDxkaXYgY2xhc3M9Im1pbmZvLW1vZGFsIiBpZD0ibWluZm9Nb2RhbCI+CiAgICA8YnV0dG9uIGNsYXNzPSJtaW5mby1jbG9zZSIgb25jbGljaz0iY2xvc2VJbmZvUG9wdXAoKSI+4pyVPC9idXR0b24+CiAgICA8ZGl2IGlkPSJtaW5mb0NvbnRlbnQiPjwvZGl2PgogIDwvZGl2Pgo8L2Rpdj4KPHNjcmlwdD4KdmFyIE1FVFJJQ1MgPSB7CiAgLy8gVEVLTsSwSwogICdSU0knOiB7CiAgICB0aXRsZTogJ1JTSSAoR8O2cmVjZWxpIEfDvMOnIEVuZGVrc2kpJywKICAgIGRlc2M6ICdIaXNzZW5pbiBhxZ/EsXLEsSBhbMSxbSB2ZXlhIGHFn8SxcsSxIHNhdMSxbSBiw7ZsZ2VzaW5kZSBvbHVwIG9sbWFkxLHEn8SxbsSxIGfDtnN0ZXJpci4gMTQgZ8O8bmzDvGsgZml5YXQgaGFyZWtldGxlcmluaSBhbmFsaXogZWRlci4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonQcWfxLFyxLEgU2F0xLFtJyxtaW46MCxtYXg6MzAsY29sb3I6J2dyZWVuJyxkZXNjOidGxLFyc2F0IGLDtmxnZXNpIOKAlCBmaXlhdCDDp29rIGTDvMWfbcO8xZ8nfSwKICAgICAge2xhYmVsOidOb3JtYWwnLG1pbjozMCxtYXg6NzAsY29sb3I6J3llbGxvdycsZGVzYzonTsO2dHIgYsO2bGdlJ30sCiAgICAgIHtsYWJlbDonQcWfxLFyxLEgQWzEsW0nLG1pbjo3MCxtYXg6MTAwLGNvbG9yOidyZWQnLGRlc2M6J0Rpa2thdCDigJQgZml5YXQgw6dvayB5w7xrc2VsbWnFnyd9CiAgICBdLAogICAgY2Fuc2xpbTogJ04ga3JpdGVyaSBpbGUgaWxnaWxpIOKAlCBmaXlhdCBtb21lbnR1bXUnCiAgfSwKICAnU01BNTAnOiB7CiAgICB0aXRsZTogJ1NNQSA1MCAoNTAgR8O8bmzDvGsgSGFyZWtldGxpIE9ydGFsYW1hKScsCiAgICBkZXNjOiAnU29uIDUwIGfDvG7DvG4gb3J0YWxhbWEga2FwYW7EscWfIGZpeWF0xLEuIEvEsXNhLW9ydGEgdmFkZWxpIHRyZW5kIGfDtnN0ZXJnZXNpLicsCiAgICBzb3VyY2U6ICdUZWtuaWsgQW5hbGl6JywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOifDnHplcmluZGUnLGNvbG9yOidncmVlbicsZGVzYzonS8Sxc2EgdmFkZWxpIHRyZW5kIHBveml0aWYg4oCUIGfDvMOnbMO8IHNpbnlhbCd9LAogICAgICB7bGFiZWw6J0FsdMSxbmRhJyxjb2xvcjoncmVkJyxkZXNjOidLxLFzYSB2YWRlbGkgdHJlbmQgbmVnYXRpZid9CiAgICBdLAogICAgY2Fuc2xpbTogJ00ga3JpdGVyaSDigJQgcGl5YXNhIHRyZW5kaScKICB9LAogICdTTUEyMDAnOiB7CiAgICB0aXRsZTogJ1NNQSAyMDAgKDIwMCBHw7xubMO8ayBIYXJla2V0bGkgT3J0YWxhbWEpJywKICAgIGRlc2M6ICdTb24gMjAwIGfDvG7DvG4gb3J0YWxhbWEga2FwYW7EscWfIGZpeWF0xLEuIFV6dW4gdmFkZWxpIHRyZW5kIGfDtnN0ZXJnZXNpLiBFbiDDtm5lbWxpIHRla25payBzZXZpeWUuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J8OcemVyaW5kZScsY29sb3I6J2dyZWVuJyxkZXNjOidVenVuIHZhZGVsaSBib8SfYSB0cmVuZGluZGUg4oCUIENBTlNMSU0gacOnaW4gxZ9hcnQnfSwKICAgICAge2xhYmVsOidBbHTEsW5kYScsY29sb3I6J3JlZCcsZGVzYzonVXp1biB2YWRlbGkgYXnEsSB0cmVuZGluZGUg4oCUIENBTlNMSU0gacOnaW4gZ2lybWUnfQogICAgXSwKICAgIGNhbnNsaW06ICdNIGtyaXRlcmkg4oCUIHpvcnVubHUga2/Fn3VsJwogIH0sCiAgJzUyVyc6IHsKICAgIHRpdGxlOiAnNTIgSGFmdGFsxLFrIFBvemlzeW9uJywKICAgIGRlc2M6ICdIaXNzZW5pbiBzb24gMSB5xLFsZGFraSBmaXlhdCBhcmFsxLHEn8SxbmRhIG5lcmVkZSBvbGR1xJ91bnUgZ8O2c3RlcmlyLiAwPXnEsWzEsW4gZGliaSwgMTAwPXnEsWzEsW4gemlydmVzaS4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonMC0zMCUnLGNvbG9yOidncmVlbicsZGVzYzonWcSxbMSxbiBkaWJpbmUgeWFrxLFuIOKAlCBwb3RhbnNpeWVsIGbEsXJzYXQnfSwKICAgICAge2xhYmVsOiczMC03MCUnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGEgYsO2bGdlIOKAlCBuw7Z0cid9LAogICAgICB7bGFiZWw6JzcwLTg1JScsY29sb3I6J3llbGxvdycsZGVzYzonWmlydmV5ZSB5YWtsYcWfxLF5b3Ig4oCUIGl6bGUnfSwKICAgICAge2xhYmVsOic4NS0xMDAlJyxjb2xvcjoncmVkJyxkZXNjOidaaXJ2ZXllIMOnb2sgeWFrxLFuIOKAlCBkaWtrYXRsaSBnaXInfQogICAgXSwKICAgIGNhbnNsaW06ICdOIGtyaXRlcmkg4oCUIHllbmkgemlydmUga8SxcsSxbMSxbcSxIGnDp2luIGlkZWFsIGLDtmxnZSAlODUtMTAwJwogIH0sCiAgJ0hhY2ltJzogewogICAgdGl0bGU6ICdIYWNpbSAoxLDFn2xlbSBNaWt0YXLEsSknLAogICAgZGVzYzogJ0fDvG5sw7xrIGnFn2xlbSBoYWNtaW5pbiBzb24gMjAgZ8O8bmzDvGsgb3J0YWxhbWF5YSBvcmFuxLEuIEfDvMOnbMO8IGhhcmVrZXRsZXJpbiBoYWNpbWxlIGRlc3Rla2xlbm1lc2kgZ2VyZWtpci4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonWcO8a3NlayAoPjEuM3gpJyxjb2xvcjonZ3JlZW4nLGRlc2M6J0t1cnVtc2FsIGlsZ2kgdmFyIOKAlCBnw7zDp2zDvCBzaW55YWwnfSwKICAgICAge2xhYmVsOidOb3JtYWwgKDAuNy0xLjN4KScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YWxhbWEgaWxnaSd9LAogICAgICB7bGFiZWw6J0TDvMWfw7xrICg8MC43eCknLGNvbG9yOidyZWQnLGRlc2M6J8SwbGdpIGF6YWxtxLHFnyDigJQgZGlra2F0J30KICAgIF0sCiAgICBjYW5zbGltOiAnUyBrcml0ZXJpIOKAlCBhcnovdGFsZXAgZGVuZ2VzaScKICB9LAogIC8vIFRFTUVMCiAgJ0ZvcndhcmRQRSc6IHsKICAgIHRpdGxlOiAnRm9yd2FyZCBQL0UgKMSwbGVyaXllIETDtm7DvGsgRml5YXQvS2F6YW7DpyknLAogICAgZGVzYzogJ8WeaXJrZXRpbiDDtm7DvG3DvHpkZWtpIDEyIGF5ZGFraSB0YWhtaW5pIGthemFuY8SxbmEgZ8O2cmUgZml5YXTEsS4gVHJhaWxpbmcgUC9FXCdkZW4gZGFoYSDDtm5lbWxpIMOnw7xua8O8IGdlbGVjZcSfZSBiYWvEsXlvci4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBBbmFsaXN0IHRhaG1pbmknLAogICAgcmVsaWFiaWxpdHk6ICdtZWRpdW0nLAogICAgd2FybmluZzogJ0FuYWxpc3QgdGFobWlubGVyaW5lIGRheWFuxLFyLCB5YW7EsWx0xLFjxLEgb2xhYmlsaXInLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPDE1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J1VjdXog4oCUIGLDvHnDvG1lIGJla2xlbnRpc2kgZMO8xZ/DvGsgdmV5YSBoaXNzZSBkZcSfZXIgYWx0xLFuZGEnfSwKICAgICAge2xhYmVsOicxNS0yNScsY29sb3I6J2dyZWVuJyxkZXNjOidNYWt1bCDigJQgw6dvxJ91IHNla3TDtnIgacOnaW4gbm9ybWFsJ30sCiAgICAgIHtsYWJlbDonMjUtNDAnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1BhaGFsxLEgYW1hIGLDvHnDvG1lIHByaW1pIMO2ZGVuaXlvcid9LAogICAgICB7bGFiZWw6Jz40MCcsY29sb3I6J3JlZCcsZGVzYzonw4dvayBwYWhhbMSxIOKAlCB5w7xrc2VrIGLDvHnDvG1lIGJla2xlbnRpc2kgZml5YXRsYW5txLHFnyd9CiAgICBdLAogICAgY2Fuc2xpbTogJ0MgdmUgQSBrcml0ZXJsZXJpIGlsZSBpbGdpbGknCiAgfSwKICAnUEVHJzogewogICAgdGl0bGU6ICdQRUcgT3JhbsSxIChGaXlhdC9LYXphbsOnL0LDvHnDvG1lKScsCiAgICBkZXNjOiAnUC9FIG9yYW7EsW7EsSBiw7x5w7xtZSBoxLF6xLF5bGEga2FyxZ/EsWxhxZ90xLFyxLFyLiBCw7x5w7x5ZW4gxZ9pcmtldGxlciBpw6dpbiBQL0VcJ2RlbiBkYWhhIGRvxJ9ydSBkZcSfZXJsZW1lIMO2bMOnw7x0w7wuIFBFRz0xIGFkaWwgZGXEn2VyIGthYnVsIGVkaWxpci4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBBbmFsaXN0IHRhaG1pbmknLAogICAgcmVsaWFiaWxpdHk6ICdtZWRpdW0nLAogICAgd2FybmluZzogJ0FuYWxpc3QgYsO8ecO8bWUgdGFobWlubGVyaW5lIGRheWFuxLFyJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzwxLjAnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgYsO8ecO8bWVzaW5lIGfDtnJlIGRlxJ9lciBhbHTEsW5kYSd9LAogICAgICB7bGFiZWw6JzEuMC0xLjUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwg4oCUIGFkaWwgZml5YXQgY2l2YXLEsSd9LAogICAgICB7bGFiZWw6JzEuNS0yLjAnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J0JpcmF6IHBhaGFsxLEnfSwKICAgICAge2xhYmVsOic+Mi4wJyxjb2xvcjoncmVkJyxkZXNjOidQYWhhbMSxIOKAlCBkaWtrYXRsaSBvbCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQgYsO8ecO8bWUga2FsaXRlc2knCiAgfSwKICAnRVBTR3Jvd3RoJzogewogICAgdGl0bGU6ICdFUFMgQsO8ecO8bWVzaSAow4dleXJla2xpaywgWW9ZKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIGhpc3NlIGJhxZ/EsW5hIGthemFuY8SxbsSxbiBnZcOnZW4gecSxbMSxbiBheW7EsSDDp2V5cmXEn2luZSBnw7ZyZSBhcnTEscWfxLEuIENBTlNMSU1cJ2luIGVuIGtyaXRpayBrcml0ZXJpLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUyNScsY29sb3I6J2dyZWVuJyxkZXNjOidHw7zDp2zDvCBiw7x5w7xtZSDigJQgQ0FOU0xJTSBrcml0ZXJpIGthcsWfxLFsYW5kxLEnfSwKICAgICAge2xhYmVsOiclMTUtMjUnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSBiw7x5w7xtZSd9LAogICAgICB7bGFiZWw6JyUwLTE1Jyxjb2xvcjoneWVsbG93JyxkZXNjOidaYXnEsWYgYsO8ecO8bWUnfSwKICAgICAge2xhYmVsOic8MCcsY29sb3I6J3JlZCcsZGVzYzonS2F6YW7DpyBkw7zFn8O8eW9yIOKAlCBkaWtrYXQnfQogICAgXSwKICAgIGNhbnNsaW06ICdDIGtyaXRlcmkg4oCUIGVuIGtyaXRpayBrcml0ZXIsIG1pbmltdW0gJTI1IG9sbWFsxLEnCiAgfSwKICAnUmV2R3Jvd3RoJzogewogICAgdGl0bGU6ICdHZWxpciBCw7x5w7xtZXNpIChZb1kpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gc2F0xLHFny9nZWxpcmluaW4gZ2XDp2VuIHnEsWxhIGfDtnJlIGFydMSxxZ/EsS4gRVBTIGLDvHnDvG1lc2luaSBkZXN0ZWtsZW1lc2kgZ2VyZWtpciDigJQgc2FkZWNlIG1hbGl5ZXQga2VzaW50aXNpeWxlIGLDvHnDvG1lIHPDvHJkw7xyw7xsZWJpbGlyIGRlxJ9pbC4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMTUnLGNvbG9yOidncmVlbicsZGVzYzonR8O8w6dsw7wgZ2VsaXIgYsO8ecO8bWVzaSd9LAogICAgICB7bGFiZWw6JyU1LTE1Jyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIGLDvHnDvG1lJ30sCiAgICAgIHtsYWJlbDonPDUnLGNvbG9yOidyZWQnLGRlc2M6J0dlbGlyIGLDvHnDvG1lc2kgemF5xLFmJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQSBrcml0ZXJpIOKAlCBzw7xyZMO8csO8bGViaWxpciBiw7x5w7xtZSBpw6dpbiDFn2FydCcKICB9LAogICdOZXRNYXJnaW4nOiB7CiAgICB0aXRsZTogJ05ldCBNYXJqaW4nLAogICAgZGVzYzogJ0hlciAxJCBnZWxpcmRlbiBuZSBrYWRhciBuZXQga8OiciBrYWxkxLHEn8SxbsSxIGfDtnN0ZXJpci4gWcO8a3NlayBtYXJqaW4gPSBnw7zDp2zDvCBpxZ8gbW9kZWxpLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUyMCcsY29sb3I6J2dyZWVuJyxkZXNjOifDh29rIGfDvMOnbMO8IGvDonJsxLFsxLFrJ30sCiAgICAgIHtsYWJlbDonJTEwLTIwJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWkga8OicmzEsWzEsWsnfSwKICAgICAge2xhYmVsOiclNS0xMCcsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSBrw6JybMSxbMSxayd9LAogICAgICB7bGFiZWw6Jzw1Jyxjb2xvcjoncmVkJyxkZXNjOidaYXnEsWYga8OicmzEsWzEsWsnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIGvDonJsxLFsxLFrIGthbGl0ZXNpJwogIH0sCiAgJ1JPRSc6IHsKICAgIHRpdGxlOiAnUk9FICjDlnprYXluYWsgS8OicmzEsWzEscSfxLEpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gw7Z6IHNlcm1heWVzaXlsZSBuZSBrYWRhciBrw6JyIGV0dGnEn2luaSBnw7ZzdGVyaXIuIFnDvGtzZWsgUk9FID0gc2VybWF5ZXlpIHZlcmltbGkga3VsbGFuxLF5b3IuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgR2Vyw6dlayB2ZXJpJywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic+JTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8OHb2sgZ8O8w6dsw7wg4oCUIENBTlNMSU0gaWRlYWwgc2V2aXllc2knfSwKICAgICAge2xhYmVsOiclMTUtMjUnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSd9LAogICAgICB7bGFiZWw6JyU4LTE1Jyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhJ30sCiAgICAgIHtsYWJlbDonPDgnLGNvbG9yOidyZWQnLGRlc2M6J1phecSxZid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQgbWluaW11bSAlMTcgb2xtYWzEsScKICB9LAogICdHcm9zc01hcmdpbic6IHsKICAgIHRpdGxlOiAnQnLDvHQgTWFyamluJywKICAgIGRlc2M6ICdTYXTEscWfIGdlbGlyaW5kZW4gw7xyZXRpbSBtYWxpeWV0aSBkw7zFn8O8bGTDvGt0ZW4gc29ucmEga2FsYW4gb3Jhbi4gU2VrdMO2cmUgZ8O2cmUgZGXEn2nFn2lyLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiU1MCcsY29sb3I6J2dyZWVuJyxkZXNjOifDh29rIGfDvMOnbMO8IOKAlCB5YXrEsWzEsW0vU2FhUyBzZXZpeWVzaSd9LAogICAgICB7bGFiZWw6JyUzMC01MCcsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpJ30sCiAgICAgIHtsYWJlbDonJTE1LTMwJyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIOKAlCBkb25hbsSxbS95YXLEsSBpbGV0a2VuIG5vcm1hbCd9LAogICAgICB7bGFiZWw6JzwxNScsY29sb3I6J3JlZCcsZGVzYzonRMO8xZ/DvGsgbWFyamluJ30KICAgIF0sCiAgICBjYW5zbGltOiAnS8OicmzEsWzEsWsga2FsaXRlc2kgZ8O2c3Rlcmdlc2knCiAgfSwKICAvLyBHxLBSxLDFngogICdFbnRyeVNjb3JlJzogewogICAgdGl0bGU6ICdHaXJpxZ8gS2FsaXRlc2kgU2tvcnUnLAogICAgZGVzYzogJ1JTSSwgU01BIHBvemlzeW9udSwgUC9FLCBQRUcgdmUgRVBTIGLDvHnDvG1lc2luaSBiaXJsZcWfdGlyZW4gYmlsZcWfaWsgc2tvci4gMC0xMDAgYXJhc8SxLicsCiAgICBzb3VyY2U6ICdCaXppbSBoZXNhcGxhbWEnLAogICAgcmVsaWFiaWxpdHk6ICdsb3cnLAogICAgd2FybmluZzogJ0JVIFVZR1VMQU1BIFRBUkFGSU5EQU4gSEVTQVBMQU5BTiBLQUJBIFRBSE3EsE5ExLBSLiBZYXTEsXLEsW0ga2FyYXLEsSBpw6dpbiB0ZWsgYmHFn8SxbmEga3VsbGFubWEuJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jzc1LTEwMCcsY29sb3I6J2dyZWVuJyxkZXNjOidVY3V6IOKAlCBpZGVhbCBnaXJpxZ8gYsO2bGdlc2knfSwKICAgICAge2xhYmVsOic2MC03NScsY29sb3I6J2dyZWVuJyxkZXNjOidNYWt1bCBmaXlhdCd9LAogICAgICB7bGFiZWw6JzQ1LTYwJyxjb2xvcjoneWVsbG93JyxkZXNjOidOw7Z0cid9LAogICAgICB7bGFiZWw6JzMwLTQ1Jyxjb2xvcjoncmVkJyxkZXNjOidQYWhhbMSxIOKAlCBiZWtsZSd9LAogICAgICB7bGFiZWw6JzAtMzAnLGNvbG9yOidyZWQnLGRlc2M6J8OHb2sgcGFoYWzEsSDigJQgZ2lybWUnfQogICAgXSwKICAgIGNhbnNsaW06ICdUw7xtIGtyaXRlcmxlciBiaWxlxZ9pbWknCiAgfSwKICAnUlInOiB7CiAgICB0aXRsZTogJ1Jpc2svw5Zkw7xsIE9yYW7EsSAoUi9SKScsCiAgICBkZXNjOiAnUG90YW5zaXllbCBrYXphbmPEsW4gcmlza2Ugb3JhbsSxLiAxOjIgZGVtZWsgMSQgcmlza2Uga2FyxZ/EsSAyJCBrYXphbsOnIHBvdGFuc2l5ZWxpIHZhciBkZW1lay4nLAogICAgc291cmNlOiAnQml6aW0gaGVzYXBsYW1hJywKICAgIHJlbGlhYmlsaXR5OiAnbG93JywKICAgIHdhcm5pbmc6ICdHaXJpxZ8vaGVkZWYvc3RvcCBzZXZpeWVsZXJpIGZvcm3DvGwgYmF6bMSxIGthYmEgdGFobWluZGlyJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzE6MysnLGNvbG9yOidncmVlbicsZGVzYzonTcO8a2VtbWVsIOKAlCBnw7zDp2zDvCBnaXJpxZ8gc2lueWFsaSd9LAogICAgICB7bGFiZWw6JzE6MicsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpIOKAlCBtaW5pbXVtIGthYnVsIGVkaWxlYmlsaXInfSwKICAgICAge2xhYmVsOicxOjEnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1phecSxZid9LAogICAgICB7bGFiZWw6JzwxOjEnLGNvbG9yOidyZWQnLGRlc2M6J1Jpc2sga2F6YW7Dp3RhbiBiw7x5w7xrIOKAlCBnaXJtZSd9CiAgICBdLAogICAgY2Fuc2xpbTogJ1Jpc2sgecO2bmV0aW1pJwogIH0sCiAgLy8gRUFSTklOR1MKICAnRWFybmluZ3NEYXRlJzogewogICAgdGl0bGU6ICdSYXBvciBUYXJpaGkgKEVhcm5pbmdzIERhdGUpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gw6dleXJlayBmaW5hbnNhbCBzb251w6dsYXLEsW7EsSBhw6fEsWtsYXlhY2HEn8SxIHRhcmloLiBSYXBvciDDtm5jZXNpIHZlIHNvbnJhc8SxIGZpeWF0IHNlcnQgaGFyZWtldCBlZGViaWxpci4nLAogICAgc291cmNlOiAneWZpbmFuY2Ug4oCUIGJhemVuIGhhdGFsxLEgb2xhYmlsaXInLAogICAgcmVsaWFiaWxpdHk6ICdtZWRpdW0nLAogICAgd2FybmluZzogJ1RhcmlobGVyaSByZXNtaSBJUiBzYXlmYXPEsW5kYW4gZG/En3J1bGF5xLFuJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzcgZ8O8biBpw6dpbmRlJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHlha8SxbiDigJQgcG96aXN5b24gYcOnbWFrIHJpc2tsaSd9LAogICAgICB7bGFiZWw6JzgtMTQgZ8O8bicsY29sb3I6J3llbGxvdycsZGVzYzonWWFrxLFuIOKAlCBkaWtrYXRsaSBvbCd9LAogICAgICB7bGFiZWw6JzE0KyBnw7xuJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1lldGVybGkgc8O8cmUgdmFyJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQyBrcml0ZXJpIOKAlCDDp2V5cmVrIHJhcG9yIGthbGl0ZXNpJwogIH0sCiAgJ0F2Z01vdmUnOiB7CiAgICB0aXRsZTogJ09ydGFsYW1hIFJhcG9yIEhhcmVrZXRpJywKICAgIGRlc2M6ICdTb24gNCDDp2V5cmVrIHJhcG9ydW5kYSwgcmFwb3IgZ8O8bsO8IHZlIGVydGVzaSBnw7xuIGZpeWF0xLFuIG9ydGFsYW1hIG5lIGthZGFyIGhhcmVrZXQgZXR0acSfaS4nLAogICAgc291cmNlOiAnQml6aW0gaGVzYXBsYW1hJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J1Bveml0aWYgKD4lNSknLGNvbG9yOidncmVlbicsZGVzYzonxZ5pcmtldCBnZW5lbGxpa2xlIGJla2xlbnRpeWkgYcWfxLF5b3InfSwKICAgICAge2xhYmVsOidOw7Z0ciAoJTAtNSknLGNvbG9yOid5ZWxsb3cnLGRlc2M6J0thcsSxxZ/EsWsgZ2XDp21pxZ8nfSwKICAgICAge2xhYmVsOidOZWdhdGlmJyxjb2xvcjoncmVkJyxkZXNjOidSYXBvciBkw7ZuZW1pbmRlIGZpeWF0IGdlbmVsbGlrbGUgZMO8xZ/DvHlvciDigJQgZGlra2F0J30KICAgIF0sCiAgICBjYW5zbGltOiAnQyBrcml0ZXJpIOKAlCBrYXphbsOnIHPDvHJwcml6aSBnZcOnbWnFn2knCiAgfQp9OwoKZnVuY3Rpb24gc2hvd0luZm8oa2V5LGV2ZW50KXsKICBpZihldmVudCkgZXZlbnQuc3RvcFByb3BhZ2F0aW9uKCk7CiAgdmFyIG09TUVUUklDU1trZXldOyBpZighbSkgcmV0dXJuOwogIHZhciByZWxMYWJlbD1tLnJlbGlhYmlsaXR5PT09ImhpZ2giPyJHw7x2ZW5pbGlyIjptLnJlbGlhYmlsaXR5PT09Im1lZGl1bSI/Ik9ydGEgR8O8dmVuaWxpciI6IkthYmEgVGFobWluIjsKICB2YXIgaD0nPGRpdiBjbGFzcz0ibWluZm8tdGl0bGUiPicrbS50aXRsZSsnPC9kaXY+JzsKICBoKz0nPGRpdiBjbGFzcz0ibWluZm8tc291cmNlIj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj4nK20uc291cmNlKyc8L3NwYW4+PHNwYW4gY2xhc3M9Im1pbmZvLXJlbCAnK20ucmVsaWFiaWxpdHkrJyI+JytyZWxMYWJlbCsnPC9zcGFuPjwvZGl2Pic7CiAgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLWRlc2MiPicrbS5kZXNjKyc8L2Rpdj4nOwogIGlmKG0ud2FybmluZykgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLXdhcm5pbmciPuKaoO+4jyAnK20ud2FybmluZysnPC9kaXY+JzsKICBpZihtLnJhbmdlcyYmbS5yYW5nZXMubGVuZ3RoKXsKICAgIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby1yYW5nZXMiPjxkaXYgY2xhc3M9Im1pbmZvLXJhbmdlLXRpdGxlIj5SZWZlcmFucyBEZWdlcmxlcjwvZGl2Pic7CiAgICBtLnJhbmdlcy5mb3JFYWNoKGZ1bmN0aW9uKHIpe3ZhciBkYz1yLmNvbG9yPT09ImdyZWVuIj8iIzEwYjk4MSI6ci5jb2xvcj09PSJyZWQiPyIjZWY0NDQ0IjoiI2Y1OWUwYiI7aCs9JzxkaXYgY2xhc3M9Im1pbmZvLXJhbmdlIj48ZGl2IGNsYXNzPSJtaW5mby1yYW5nZS1kb3QiIHN0eWxlPSJiYWNrZ3JvdW5kOicrZGMrJyI+PC9kaXY+PGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtmb250LXdlaWdodDo2MDA7Y29sb3I6JytkYysnIj4nK3IubGFiZWwrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytyLmRlc2MrJzwvZGl2PjwvZGl2PjwvZGl2Pic7fSk7CiAgICBoKz0nPC9kaXY+JzsKICB9CiAgaWYobS5jYW5zbGltKSBoKz0nPGRpdiBjbGFzcz0ibWluZm8tY2Fuc2xpbSI+8J+TiiBDQU5TTElNOiAnK20uY2Fuc2xpbSsnPC9kaXY+JzsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWluZm9Db250ZW50IikuaW5uZXJIVE1MPWg7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvUG9wdXAiKS5jbGFzc0xpc3QuYWRkKCJvcGVuIik7Cn0KZnVuY3Rpb24gY2xvc2VJbmZvUG9wdXAoZSl7aWYoIWV8fGUudGFyZ2V0PT09ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvUG9wdXAiKSl7ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvUG9wdXAiKS5jbGFzc0xpc3QucmVtb3ZlKCJvcGVuIik7fX0KCjwvc2NyaXB0Pgo8c2NyaXB0Pgp2YXIgVEZfREFUQT0lJVRGX0RBVEElJTsKdmFyIFBPUlQ9JSVQT1JUJSU7CnZhciBFQVJOSU5HU19EQVRBPSUlRUFSTklOR1NfREFUQSUlOwp2YXIgTUFSS0VUX0RBVEE9JSVNQVJLRVRfREFUQSUlOwp2YXIgTkVXU19EQVRBPSUlTkVXU19EQVRBJSU7CnZhciBBSV9EQVRBPSUlQUlfREFUQSUlOwp2YXIgY3VyVGFiPSJhbGwiLGN1clRmPSIxZCIsY3VyRGF0YT1URl9EQVRBWyIxZCJdLnNsaWNlKCk7CnZhciBtaW5pQ2hhcnRzPXt9LG1DaGFydD1udWxsOwp2YXIgU1M9ewogICJHVUNMVSBBTCI6e2JnOiJyZ2JhKDE2LDE4NSwxMjksLjEyKSIsYmQ6InJnYmEoMTYsMTg1LDEyOSwuMzUpIix0eDoiIzEwYjk4MSIsYWM6IiMxMGI5ODEiLGxibDoiR1VDTFUgQUwifSwKICAiQUwiOntiZzoicmdiYSg1MiwyMTEsMTUzLC4xKSIsYmQ6InJnYmEoNTIsMjExLDE1MywuMykiLHR4OiIjMzRkMzk5IixhYzoiIzM0ZDM5OSIsbGJsOiJBTCJ9LAogICJESUtLQVQiOntiZzoicmdiYSgyNDUsMTU4LDExLC4xKSIsYmQ6InJnYmEoMjQ1LDE1OCwxMSwuMykiLHR4OiIjZjU5ZTBiIixhYzoiI2Y1OWUwYiIsbGJsOiJESUtLQVQifSwKICAiWkFZSUYiOntiZzoicmdiYSgxMDcsMTE0LDEyOCwuMSkiLGJkOiJyZ2JhKDEwNywxMTQsMTI4LC4zKSIsdHg6IiM5Y2EzYWYiLGFjOiIjNmI3MjgwIixsYmw6IlpBWUlGIn0sCiAgIlNBVCI6e2JnOiJyZ2JhKDIzOSw2OCw2OCwuMTIpIixiZDoicmdiYSgyMzksNjgsNjgsLjM1KSIsdHg6IiNlZjQ0NDQiLGFjOiIjZWY0NDQ0IixsYmw6IlNBVCJ9Cn07CgpmdW5jdGlvbiBpYihrZXksbGFiZWwpewogIHJldHVybiBsYWJlbCsnIDxzcGFuIGNsYXNzPSJtaW5mbyIgb25jbGljaz0ic2hvd0luZm8oXCcnK2tleSsnXCcsZXZlbnQpIj4/PC9zcGFuPic7Cn0KCmZ1bmN0aW9uIHNldFRhYih0LGVsKXsKICBjdXJUYWI9dDsKICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIudGFiIikuZm9yRWFjaChmdW5jdGlvbihiKXtiLmNsYXNzTGlzdC5yZW1vdmUoImFjdGl2ZSIpO30pOwogIGVsLmNsYXNzTGlzdC5hZGQoImFjdGl2ZSIpOwogIHZhciB0ZlJvdz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidGZSb3ciKTsKICBpZih0ZlJvdykgdGZSb3cuc3R5bGUuZGlzcGxheT0odD09PSJkYXNoYm9hcmQifHx0PT09ImVhcm5pbmdzInx8dD09PSJydXRpbiIpPyJub25lIjoiZmxleCI7CiAgaWYodD09PSJkYXNoYm9hcmQiKSByZW5kZXJEYXNoYm9hcmQoKTsKICBlbHNlIGlmKHQ9PT0iZWFybmluZ3MiKSByZW5kZXJFYXJuaW5ncygpOwogIGVsc2UgaWYodD09PSJydXRpbiIpIHJlbmRlclJ1dGluKCk7CiAgZWxzZSByZW5kZXJHcmlkKCk7Cn0KCmZ1bmN0aW9uIHNldFRmKHRmLGVsKXsKICBjdXJUZj10ZjsKICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIudGYtYnRuIikuZm9yRWFjaChmdW5jdGlvbihiKXtiLmNsYXNzTGlzdC50b2dnbGUoImFjdGl2ZSIsYi5kYXRhc2V0LnRmPT09dGYpO30pOwogIGN1ckRhdGE9KFRGX0RBVEFbdGZdfHxURl9EQVRBWyIxZCJdKS5zbGljZSgpOwogIHJlbmRlclN0YXRzKCk7CiAgcmVuZGVyR3JpZCgpOwp9CgpmdW5jdGlvbiBmaWx0ZXJlZCgpewogIHZhciBkPWN1ckRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pOwogIGlmKGN1clRhYj09PSJwb3J0IikgcmV0dXJuIGQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiBQT1JULmluY2x1ZGVzKHIudGlja2VyKTt9KTsKICBpZihjdXJUYWI9PT0iYnV5IikgcmV0dXJuIGQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSJHVUNMVSBBTCJ8fHIuc2lueWFsPT09IkFMIjt9KTsKICBpZihjdXJUYWI9PT0ic2VsbCIpIHJldHVybiBkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0iU0FUIjt9KTsKICByZXR1cm4gZDsKfQoKZnVuY3Rpb24gcmVuZGVyU3RhdHMoKXsKICB2YXIgZD1jdXJEYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KTsKICB2YXIgY250PXt9OwogIGQuZm9yRWFjaChmdW5jdGlvbihyKXtjbnRbci5zaW55YWxdPShjbnRbci5zaW55YWxdfHwwKSsxO30pOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJzdGF0cyIpLmlubmVySFRNTD0KICAgICc8ZGl2IGNsYXNzPSJwaWxsIGciPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+R3VjbHUgQWw6ICcrKGNudFsiR1VDTFUgQUwiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCBnIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PkFsOiAnKyhjbnRbIkFMIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgeSI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5EaWtrYXQ6ICcrKGNudFsiRElLS0FUIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgciI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5TYXQ6ICcrKGNudFsiU0FUIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgYiIgc3R5bGU9Im1hcmdpbi1sZWZ0OmF1dG8iPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+UG9ydGZvbHlvOiAnK1BPUlQubGVuZ3RoKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgbSI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj4nK2QubGVuZ3RoKycgYW5hbGl6PC9kaXY+JzsKfQoKZnVuY3Rpb24gcmVuZGVyR3JpZCgpewogIE9iamVjdC52YWx1ZXMobWluaUNoYXJ0cykuZm9yRWFjaChmdW5jdGlvbihjKXtjLmRlc3Ryb3koKTt9KTsKICBtaW5pQ2hhcnRzPXt9OwogIHZhciBmPWZpbHRlcmVkKCk7CiAgdmFyIGdyaWQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdyaWQiKTsKICBpZighZi5sZW5ndGgpe2dyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xO3RleHQtYWxpZ246Y2VudGVyO3BhZGRpbmc6NDBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkhpc3NlIGJ1bHVuYW1hZGk8L2Rpdj4nO3JldHVybjt9CiAgZ3JpZC5pbm5lckhUTUw9Zi5tYXAoZnVuY3Rpb24ocil7cmV0dXJuIGJ1aWxkQ2FyZChyKTt9KS5qb2luKCIiKTsKICBmLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgY3R4PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtYy0iK3IudGlja2VyKTsKICAgIGlmKGN0eCYmci5jaGFydF9jbG9zZXMmJnIuY2hhcnRfY2xvc2VzLmxlbmd0aCl7CiAgICAgIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICAgICAgbWluaUNoYXJ0c1sibSIrci50aWNrZXJdPW5ldyBDaGFydChjdHgse3R5cGU6ImxpbmUiLGRhdGE6e2xhYmVsczpyLmNoYXJ0X2RhdGVzLGRhdGFzZXRzOlt7ZGF0YTpyLmNoYXJ0X2Nsb3Nlcyxib3JkZXJDb2xvcjpzcy5hYyxib3JkZXJXaWR0aDoxLjUsZmlsbDp0cnVlLGJhY2tncm91bmRDb2xvcjpzcy5hYysiMTgiLHBvaW50UmFkaXVzOjAsdGVuc2lvbjowLjR9XX0sb3B0aW9uczp7cGx1Z2luczp7bGVnZW5kOntkaXNwbGF5OmZhbHNlfX0sc2NhbGVzOnt4OntkaXNwbGF5OmZhbHNlfSx5OntkaXNwbGF5OmZhbHNlfX0sYW5pbWF0aW9uOntkdXJhdGlvbjo1MDB9LHJlc3BvbnNpdmU6dHJ1ZSxtYWludGFpbkFzcGVjdFJhdGlvOmZhbHNlfX0pOwogICAgfQogIH0pOwp9CgpmdW5jdGlvbiBidWlsZENhcmQocil7CiAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogIHZhciBkYz1yLmRlZ2lzaW0+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIGRzPShyLmRlZ2lzaW0+PTA/IisiOiIiKStyLmRlZ2lzaW0rIiUiOwogIHZhciBlc2NvbD1yLmVudHJ5X3Njb3JlPj03NT8idmFyKC0tZ3JlZW4pIjpyLmVudHJ5X3Njb3JlPj02MD8idmFyKC0tZ3JlZW4yKSI6ci5lbnRyeV9zY29yZT49NDU/InZhcigtLXllbGxvdykiOnIuZW50cnlfc2NvcmU+PTMwPyJ2YXIoLS1yZWQyKSI6InZhcigtLXJlZCkiOwogIHZhciBwdmNvbD1yLnByaWNlX3ZzX2NvbG9yPT09ImdyZWVuIj8idmFyKC0tZ3JlZW4pIjpyLnByaWNlX3ZzX2NvbG9yPT09InllbGxvdyI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIHNpZ3M9WwogICAge2w6IlRyZW5kIix2OnIudHJlbmQ9PT0iWXVrc2VsZW4iPyJZdWtzZWxpeW9yIjpyLnRyZW5kPT09IkR1c2VuIj8iRHVzdXlvciI6IllhdGF5IixnOnIudHJlbmQ9PT0iWXVrc2VsZW4iP3RydWU6ci50cmVuZD09PSJEdXNlbiI/ZmFsc2U6bnVsbH0sCiAgICB7bDoiU01BNTAiLHY6ci5hYm92ZTUwPyJVemVyaW5kZSI6IkFsdGluZGEiLGc6ci5hYm92ZTUwfSwKICAgIHtsOiJTTUEyMDAiLHY6ci5hYm92ZTIwMD8iVXplcmluZGUiOiJBbHRpbmRhIixnOnIuYWJvdmUyMDB9LAogICAge2w6IlJTSSIsdjpyLnJzaXx8Ij8iLGc6ci5yc2k/ci5yc2k8MzA/dHJ1ZTpyLnJzaT43MD9mYWxzZTpudWxsOm51bGx9LAogICAge2w6IjUyVyIsdjoiJSIrci5wY3RfZnJvbV81MncrIiB1emFrIixnOnIubmVhcl81Mnd9CiAgXS5tYXAoZnVuY3Rpb24ocyl7cmV0dXJuICc8c3BhbiBjbGFzcz0ic3AgJysocy5nPT09dHJ1ZT8ic2ciOnMuZz09PWZhbHNlPyJzYiI6InNuIikrJyI+JytzLmwrIjogIitzLnYrIjwvc3Bhbj4iO30pLmpvaW4oIiIpOwogIHJldHVybiAnPGRpdiBjbGFzcz0iY2FyZCIgc3R5bGU9ImJvcmRlci1jb2xvcjonKyhyLnBvcnRmb2xpbz8icmdiYSgxNiwxODUsMTI5LC4yNSkiOnNzLmJkKSsnIiBvbmNsaWNrPSJvcGVuTShcJycrci50aWNrZXIrJ1wnKSI+JwogICAgKyc8ZGl2IGNsYXNzPSJhY2NlbnQiIHN0eWxlPSJiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCg5MGRlZywnK3NzLmFjKycsJytzcy5hYysnODgpIj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImNib2R5Ij48ZGl2IGNsYXNzPSJjdG9wIj48ZGl2PjxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjRweCI+JwogICAgKyc8c3BhbiBjbGFzcz0idGlja2VyIiBzdHlsZT0iY29sb3I6Jytzcy50eCsnIj4nK3IudGlja2VyKyc8L3NwYW4+JwogICAgKyhyLnBvcnRmb2xpbz8nPHNwYW4gY2xhc3M9InBvcnQtYmFkZ2UiPlA8L3NwYW4+JzonJykrCiAgICAnPC9kaXY+PHNwYW4gY2xhc3M9ImJhZGdlIiBzdHlsZT0iYmFja2dyb3VuZDonK3NzLmJnKyc7Y29sb3I6Jytzcy50eCsnO2JvcmRlcjoxcHggc29saWQgJytzcy5iZCsnIj4nK3NzLmxibCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iY3ByIj48ZGl2IGNsYXNzPSJwdmFsIj4kJytyLmZpeWF0Kyc8L2Rpdj48ZGl2IGNsYXNzPSJwY2hnIiBzdHlsZT0iY29sb3I6JytkYysnIj4nK2RzKyc8L2Rpdj4nCiAgICArKHIucGVfZndkPyc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+RndkUEU6JytyLnBlX2Z3ZC50b0ZpeGVkKDEpKyc8L2Rpdj4nOicnKQogICAgKyc8L2Rpdj48L2Rpdj48ZGl2IGNsYXNzPSJzaWdzIj4nK3NpZ3MrJzwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0ibWFyZ2luLXRvcDo2cHgiPicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206M3B4Ij48c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkdpcmlzIEthbGl0ZXNpPC9zcGFuPjxzcGFuIHN0eWxlPSJmb250LXNpemU6MTFweDtmb250LXdlaWdodDo3MDA7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfc2NvcmUrJy8xMDA8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJoZWlnaHQ6NHB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjJweDtvdmVyZmxvdzpoaWRkZW4iPjxkaXYgc3R5bGU9ImhlaWdodDoxMDAlO3dpZHRoOicrci5lbnRyeV9zY29yZSsnJTtiYWNrZ3JvdW5kOicrZXNjb2wrJztib3JkZXItcmFkaXVzOjJweCI+PC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47bWFyZ2luLXRvcDozcHgiPjxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X2xhYmVsKyc8L3NwYW4+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6JytwdmNvbCsnIj4nK3IucHJpY2VfdnNfaWRlYWwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzwvZGl2PjxkaXYgY2xhc3M9ImNoYXJ0LXciPjxjYW52YXMgaWQ9Im1jLScrci50aWNrZXIrJyI+PC9jYW52YXM+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJsdmxzIj4nCiAgICArJzxkaXYgY2xhc3M9Imx2Ij48ZGl2IGNsYXNzPSJsbCI+SGVtZW4gR2lyPC9kaXY+PGRpdiBjbGFzcz0ibHZhbCIgc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuMikiPiQnK3IuZW50cnlfYWdncmVzc2l2ZSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJsdiI+PGRpdiBjbGFzcz0ibGwiPkhlZGVmPC9kaXY+PGRpdiBjbGFzcz0ibHZhbCIgc3R5bGU9ImNvbG9yOiM2MGE1ZmEiPiQnK3IuaGVkZWYrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0ibHYiPjxkaXYgY2xhc3M9ImxsIj5TdG9wPC9kaXY+PGRpdiBjbGFzcz0ibHZhbCIgc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpIj4kJytyLnN0b3ArJzwvZGl2PjwvZGl2PicKICAgICsnPC9kaXY+PC9kaXY+PC9kaXY+JzsKfQoKZnVuY3Rpb24gcmVuZGVyRGFzaGJvYXJkKCl7CiAgdmFyIGdyaWQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdyaWQiKTsKICB2YXIgbWQ9TUFSS0VUX0RBVEF8fHt9OwogIHZhciBzcD1tZC5TUDUwMHx8e307CiAgdmFyIG5hcz1tZC5OQVNEQVF8fHt9OwogIHZhciB2aXg9bWQuVklYfHx7fTsKICB2YXIgbVNpZ25hbD1tZC5NX1NJR05BTHx8Ik5PVFIiOwogIHZhciBtTGFiZWw9bWQuTV9MQUJFTHx8IlZlcmkgeW9rIjsKICB2YXIgbUNvbG9yPW1TaWduYWw9PT0iR1VDTFUiPyJ2YXIoLS1ncmVlbikiOm1TaWduYWw9PT0iWkFZSUYiPyJ2YXIoLS1yZWQyKSI6InZhcigtLXllbGxvdykiOwogIHZhciBtQmc9bVNpZ25hbD09PSJHVUNMVSI/InJnYmEoMTYsMTg1LDEyOSwuMDgpIjptU2lnbmFsPT09IlpBWUlGIj8icmdiYSgyMzksNjgsNjgsLjA4KSI6InJnYmEoMjQ1LDE1OCwxMSwuMDgpIjsKICB2YXIgbUJvcmRlcj1tU2lnbmFsPT09IkdVQ0xVIj8icmdiYSgxNiwxODUsMTI5LC4yNSkiOm1TaWduYWw9PT0iWkFZSUYiPyJyZ2JhKDIzOSw2OCw2OCwuMjUpIjoicmdiYSgyNDUsMTU4LDExLC4yNSkiOwogIHZhciBtSWNvbj1tU2lnbmFsPT09IkdVQ0xVIj8i4pyFIjptU2lnbmFsPT09IlpBWUlGIj8i4p2MIjoi4pqg77iPIjsKCiAgZnVuY3Rpb24gaW5kZXhDYXJkKG5hbWUsZGF0YSl7CiAgICBpZighZGF0YXx8IWRhdGEucHJpY2UpIHJldHVybiAiIjsKICAgIHZhciBjYz1kYXRhLmNoYW5nZT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICAgIHZhciBjcz0oZGF0YS5jaGFuZ2U+PTA/IisiOiIiKStkYXRhLmNoYW5nZSsiJSI7CiAgICB2YXIgczUwPWRhdGEuYWJvdmU1MD8nPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6MTBweCI+U01BNTAg4pyTPC9zcGFuPic6JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKTtmb250LXNpemU6MTBweCI+U01BNTAg4pyXPC9zcGFuPic7CiAgICB2YXIgczIwMD1kYXRhLmFib3ZlMjAwPyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZToxMHB4Ij5TTUEyMDAg4pyTPC9zcGFuPic6JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKTtmb250LXNpemU6MTBweCI+U01BMjAwIOKclzwvc3Bhbj4nOwogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHggMTZweDtmbGV4OjE7bWluLXdpZHRoOjE1MHB4Ij4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NnB4Ij4nK25hbWUrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpcJ0pldEJyYWlucyBNb25vXCcsbW9ub3NwYWNlO2ZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KSI+JCcrZGF0YS5wcmljZSsnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2U7Zm9udC1zaXplOjEzcHg7Y29sb3I6JytjYysnO21hcmdpbi1ib3R0b206OHB4Ij4nK2NzKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo4cHgiPicrczUwK3MyMDArJzwvZGl2PjwvZGl2Pic7CiAgfQoKICB2YXIgcG9ydERhdGE9Y3VyRGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGEmJlBPUlQuaW5jbHVkZXMoci50aWNrZXIpO30pOwogIHZhciBwb3J0SHRtbD0iIjsKICBpZihwb3J0RGF0YS5sZW5ndGgpewogICAgcG9ydEh0bWw9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjE0cHgiPicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEycHgiPvCfkrwgUG9ydGbDtnkgw5Z6ZXRpPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMTQwcHgsMWZyKSk7Z2FwOjhweCI+JzsKICAgIHBvcnREYXRhLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICAgIHZhciBkYz1yLmRlZ2lzaW0+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgICAgIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICAgICAgcG9ydEh0bWwrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCAnK3NzLmJkKyc7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4O2N1cnNvcjpwb2ludGVyIiBvbmNsaWNrPSJvcGVuTShcJycrci50aWNrZXIrJ1wnKSI+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjRweCI+JwogICAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OlwnQmViYXMgTmV1ZVwnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjE2cHg7bGV0dGVyLXNwYWNpbmc6MnB4O2NvbG9yOicrc3MudHgrJyI+JytyLnRpY2tlcisnPC9zcGFuPicKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2JhY2tncm91bmQ6Jytzcy5iZysnO2NvbG9yOicrc3MudHgrJztwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czoycHgiPicrc3MubGJsKyc8L3NwYW4+PC9kaXY+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZTtmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDAiPiQnK3IuZml5YXQrJzwvZGl2PicKICAgICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2U7Zm9udC1zaXplOjExcHg7Y29sb3I6JytkYysnIj4nKyhyLmRlZ2lzaW0+PTA/IisiOiIiKStyLmRlZ2lzaW0rJyU8L2Rpdj48L2Rpdj4nOwogICAgfSk7CiAgICBwb3J0SHRtbCs9JzwvZGl2PjwvZGl2Pic7CiAgfQoKICB2YXIgdXJnZW50RWFybmluZ3M9RUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuIGUuYWxlcnQ9PT0icmVkInx8ZS5hbGVydD09PSJ5ZWxsb3ciO30pOwogIHZhciBlYXJuaW5nc0FsZXJ0PSIiOwogIGlmKHVyZ2VudEVhcm5pbmdzLmxlbmd0aCl7CiAgICBlYXJuaW5nc0FsZXJ0PSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNHB4IDE2cHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0teWVsbG93KTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+4pqg77iPIFlha2xhxZ9hbiBSYXBvcmxhcjwvZGl2Pic7CiAgICB1cmdlbnRFYXJuaW5ncy5mb3JFYWNoKGZ1bmN0aW9uKGUpewogICAgICB2YXIgaWM9ZS5hbGVydD09PSJyZWQiPyLwn5S0Ijoi8J+foSI7CiAgICAgIGVhcm5pbmdzQWxlcnQrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206NnB4O2ZvbnQtc2l6ZToxMnB4Ij4nCiAgICAgICAgKyc8c3Bhbj4nK2ljKycgPHN0cm9uZz4nK2UudGlja2VyKyc8L3N0cm9uZz48L3NwYW4+JwogICAgICAgICsnPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+JytlLm5leHRfZGF0ZSsnICgnKyhlLmRheXNfdG9fZWFybmluZ3M9PT0wPyJCVUfDnE4iOmUuZGF5c190b19lYXJuaW5ncysiIGfDvG4iKSsnKTwvc3Bhbj48L2Rpdj4nOwogICAgfSk7CiAgICBlYXJuaW5nc0FsZXJ0Kz0nPC9kaXY+JzsKICB9CgogIHZhciBuZXdzSHRtbD0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4Ij4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTJweCI+8J+TsCBTb24gSGFiZXJsZXI8L2Rpdj4nOwogIGlmKE5FV1NfREFUQSYmTkVXU19EQVRBLmxlbmd0aCl7CiAgICBORVdTX0RBVEEuc2xpY2UoMCwxMCkuZm9yRWFjaChmdW5jdGlvbihuKXsKICAgICAgdmFyIHBiPW4ucG9ydGZvbGlvPyc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEyKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjI1KTtwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo2MDAiPlA8L3NwYW4+JzoiIjsKICAgICAgdmFyIHRhPSIiOwogICAgICBpZihuLmRhdGV0aW1lKXt2YXIgZGlmZj1NYXRoLmZsb29yKChEYXRlLm5vdygpLzEwMDAtbi5kYXRldGltZSkvMzYwMCk7dGE9ZGlmZjwyND8oZGlmZisicyDDtm5jZSIpOihNYXRoLmZsb29yKGRpZmYvMjQpKyJnIMO2bmNlIik7fQogICAgICBuZXdzSHRtbCs9JzxkaXYgc3R5bGU9InBhZGRpbmc6MTBweCAwO2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA0KSI+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4O21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXllbGxvdykiPicrbi50aWNrZXIrJzwvc3Bhbj4nK3BiCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWxlZnQ6YXV0byI+Jyt0YSsnPC9zcGFuPjwvZGl2PicKICAgICAgICArJzxhIGhyZWY9Iicrbi51cmwrJyIgdGFyZ2V0PSJfYmxhbmsiIHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS10ZXh0KTt0ZXh0LWRlY29yYXRpb246bm9uZTtsaW5lLWhlaWdodDoxLjU7ZGlzcGxheTpibG9jayI+JytuLmhlYWRsaW5lKyc8L2E+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi10b3A6M3B4Ij4nK24uc291cmNlKyc8L2Rpdj48L2Rpdj4nOwogICAgfSk7CiAgfSBlbHNlIHsKICAgIG5ld3NIdG1sKz0nPGRpdiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtc2l6ZToxMnB4Ij5IYWJlciBidWx1bmFtYWRpPC9kaXY+JzsKICB9CiAgbmV3c0h0bWwrPSc8L2Rpdj4nOwoKICBncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JwogICAgKyc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicrbUJnKyc7Ym9yZGVyOjFweCBzb2xpZCAnK21Cb3JkZXIrJztib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47ZmxleC13cmFwOndyYXA7Z2FwOjEycHgiPicKICAgICsnPGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4O21hcmdpbi1ib3R0b206NHB4Ij5DQU5TTElNIE0gS1LEsFRFUsSwPC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyttQ29sb3IrJyI+JyttSWNvbisnICcrbUxhYmVsKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTt0ZXh0LWFsaWduOnJpZ2h0Ij5WSVg6ICcrKHZpeC5wcmljZXx8Ij8iKSsnPGJyPicKICAgICsnPHNwYW4gc3R5bGU9ImNvbG9yOicrKHZpeC5wcmljZSYmdml4LnByaWNlPjI1PyJ2YXIoLS1yZWQyKSI6InZhcigtLWdyZWVuKSIpKyciPicrKHZpeC5wcmljZSYmdml4LnByaWNlPjI1PyJZw7xrc2VrIHZvbGF0aWxpdGUiOiJOb3JtYWwgdm9sYXRpbGl0ZSIpKyc8L3NwYW4+PC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXA7bWFyZ2luLWJvdHRvbToxNHB4Ij4nK2luZGV4Q2FyZCgiUyZQIDUwMCAoU1BZKSIsc3ApK2luZGV4Q2FyZCgiTkFTREFRIChRUVEpIixuYXMpKyc8L2Rpdj4nCiAgICArcG9ydEh0bWwrZWFybmluZ3NBbGVydCtuZXdzSHRtbCsnPC9kaXY+JzsKfQoKZnVuY3Rpb24gcmVuZGVyRWFybmluZ3MoKXsKICB2YXIgZ3JpZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ3JpZCIpOwogIHZhciBzb3J0ZWQ9RUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuIGUubmV4dF9kYXRlO30pLnNvcnQoZnVuY3Rpb24oYSxiKXsKICAgIHZhciBkYT1hLmRheXNfdG9fZWFybmluZ3MhPW51bGw/YS5kYXlzX3RvX2Vhcm5pbmdzOjk5OTsKICAgIHZhciBkYj1iLmRheXNfdG9fZWFybmluZ3MhPW51bGw/Yi5kYXlzX3RvX2Vhcm5pbmdzOjk5OTsKICAgIHJldHVybiBkYS1kYjsKICB9KTsKICB2YXIgbm9EYXRlPUVBUk5JTkdTX0RBVEEuZmlsdGVyKGZ1bmN0aW9uKGUpe3JldHVybiAhZS5uZXh0X2RhdGU7fSk7CiAgaWYoIXNvcnRlZC5sZW5ndGgmJiFub0RhdGUubGVuZ3RoKXtncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMTt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjQwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5FYXJuaW5ncyB2ZXJpc2kgYnVsdW5hbWFkaTwvZGl2Pic7cmV0dXJuO30KICB2YXIgaD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKICBzb3J0ZWQuZm9yRWFjaChmdW5jdGlvbihlKXsKICAgIHZhciBhYj1lLmFsZXJ0PT09InJlZCI/InJnYmEoMjM5LDY4LDY4LC4xMikiOmUuYWxlcnQ9PT0ieWVsbG93Ij8icmdiYSgyNDUsMTU4LDExLC4xKSI6InJnYmEoMjU1LDI1NSwyNTUsLjAyKSI7CiAgICB2YXIgYWJkPWUuYWxlcnQ9PT0icmVkIj8icmdiYSgyMzksNjgsNjgsLjM1KSI6ZS5hbGVydD09PSJ5ZWxsb3ciPyJyZ2JhKDI0NSwxNTgsMTEsLjMpIjoicmdiYSgyNTUsMjU1LDI1NSwuMDcpIjsKICAgIHZhciBhaT1lLmFsZXJ0PT09InJlZCI/IvCflLQiOmUuYWxlcnQ9PT0ieWVsbG93Ij8i8J+foSI6IvCfk4UiOwogICAgdmFyIGR0PWUuZGF5c190b19lYXJuaW5ncyE9bnVsbD8oZS5kYXlzX3RvX2Vhcm5pbmdzPT09MD8iQlVHVU4iOmUuZGF5c190b19lYXJuaW5ncz09PTE/IllhcmluIjplLmRheXNfdG9fZWFybmluZ3MrIiBndW4gc29ucmEiKToiIjsKICAgIHZhciBhbUNvbD1lLmF2Z19tb3ZlX3BjdCE9bnVsbD8oZS5hdmdfbW92ZV9wY3Q+PTA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZDIpIik6InZhcigtLW11dGVkKSI7CiAgICB2YXIgYW1TdHI9ZS5hdmdfbW92ZV9wY3QhPW51bGw/KGUuYXZnX21vdmVfcGN0Pj0wPyIrIjoiIikrZS5hdmdfbW92ZV9wY3QrIiUiOiLigJQiOwogICAgdmFyIHliPWUuYWxlcnQ9PT0icmVkIj8nPHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtjb2xvcjp2YXIoLS1yZWQyKTtwYWRkaW5nOjJweCA4cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjEwcHg7Zm9udC13ZWlnaHQ6NzAwIj5ZQUtJTkRBPC9zcGFuPic6IiI7CiAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonK2FiKyc7Ym9yZGVyOjFweCBzb2xpZCAnK2FiZCsnO2JvcmRlci1yYWRpdXM6MTBweDttYXJnaW4tYm90dG9tOjEwcHg7cGFkZGluZzoxNHB4IDE2cHgiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6OHB4Ij4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjEwcHgiPjxzcGFuPicrYWkrJzwvc3Bhbj48c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6XCdCZWJhcyBOZXVlXCcsc2Fucy1zZXJpZjtmb250LXNpemU6MjBweDtsZXR0ZXItc3BhY2luZzoycHg7Y29sb3I6dmFyKC0tdGV4dCkiPicrZS50aWNrZXIrJzwvc3Bhbj4nK3liKyc8L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTZweDtmbGV4LXdyYXA6d3JhcDthbGlnbi1pdGVtczpjZW50ZXIiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5SQVBPUjwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOnZhcigtLXRleHQpIj4nKyhlLm5leHRfZGF0ZXx8IuKAlCIpKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjonKyhlLmFsZXJ0PT09InJlZCI/InZhcigtLXJlZDIpIjplLmFsZXJ0PT09InllbGxvdyI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nK2R0Kyc8L2Rpdj48L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+RVBTIFRBSE1JTjwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOiM2MGE1ZmEiPicrKGUuZXBzX2VzdGltYXRlIT1udWxsPyIkIitlLmVwc19lc3RpbWF0ZToi4oCUIikrJzwvZGl2PjwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5PUlQuSEFSRUtFVDwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2U7Zm9udC1zaXplOjE0cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrYW1Db2wrJyI+JythbVN0cisnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjhweDtjb2xvcjp2YXIoLS1tdXRlZCkiPnNvbiA0IHJhcG9yPC9kaXY+PC9kaXY+JzsKICAgIGgrPSc8L2Rpdj48L2Rpdj4nOwogICAgaWYoZS5oaXN0b3J5X2VwcyYmZS5oaXN0b3J5X2Vwcy5sZW5ndGgpewogICAgICBoKz0nPGRpdiBzdHlsZT0ibWFyZ2luLXRvcDo4cHg7cGFkZGluZy10b3A6OHB4O2JvcmRlci10b3A6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA2KSI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo1cHgiPlNPTiA0IFJBUE9SPC9kaXY+PGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoNCwxZnIpO2dhcDo0cHgiPic7CiAgICAgIGUuaGlzdG9yeV9lcHMuZm9yRWFjaChmdW5jdGlvbihoaCl7CiAgICAgICAgdmFyIHNjPWhoLnN1cnByaXNlX3BjdCE9bnVsbD8oaGguc3VycHJpc2VfcGN0PjA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZDIpIik6InZhcigtLW11dGVkKSI7CiAgICAgICAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjRweDtwYWRkaW5nOjZweDt0ZXh0LWFsaWduOmNlbnRlcjtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA1KSI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjhweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicraGguZGF0ZS5zdWJzdHJpbmcoMCw3KSsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZTtmb250LXNpemU6MTBweCI+JysoaGguYWN0dWFsIT1udWxsPyIkIitoaC5hY3R1YWw6Ij8iKSsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK3NjKyciPicrKGhoLnN1cnByaXNlX3BjdCE9bnVsbD8oaGguc3VycHJpc2VfcGN0PjA/IisiOiIiKStoaC5zdXJwcmlzZV9wY3QrIiUiOiI/IikrJzwvZGl2PjwvZGl2Pic7CiAgICAgIH0pOwogICAgICBoKz0nPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGgrPSc8L2Rpdj4nOwogIH0pOwogIGlmKG5vRGF0ZS5sZW5ndGgpe2grPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLXRvcDo2cHgiPlRhcmloIGJ1bHVuYW1heWFuOiAnK25vRGF0ZS5tYXAoZnVuY3Rpb24oZSl7cmV0dXJuIGUudGlja2VyO30pLmpvaW4oIiwgIikrJzwvZGl2Pic7fQogIGgrPSc8L2Rpdj4nOwogIGdyaWQuaW5uZXJIVE1MPWg7Cn0KCmZ1bmN0aW9uIG9wZW5NKHRpY2tlcil7CiAgdmFyIHI9Y3VyRGF0YS5maW5kKGZ1bmN0aW9uKGQpe3JldHVybiBkLnRpY2tlcj09PXRpY2tlcjt9KTsKICBpZighcnx8ci5oYXRhKSByZXR1cm47CiAgaWYobUNoYXJ0KXttQ2hhcnQuZGVzdHJveSgpO21DaGFydD1udWxsO30KICB2YXIgc3M9U1Nbci5zaW55YWxdfHxTU1siRElLS0FUIl07CiAgdmFyIHJyUD1NYXRoLm1pbigoci5yci80KSoxMDAsMTAwKTsKICB2YXIgcnJDPXIucnI+PTM/InZhcigtLWdyZWVuKSI6ci5ycj49Mj8idmFyKC0tZ3JlZW4yKSI6ci5ycj49MT8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZDIpIjsKICB2YXIgZGM9ci5kZWdpc2ltPj0wPyJ2YXIoLS1ncmVlbjIpIjoidmFyKC0tcmVkMikiOwogIHZhciBrYz17IkdVQ0xVIEFMIjoiIzEwYjk4MSIsIkFMIjoiIzM0ZDM5OSIsIkRJS0tBVExJIjoiI2Y1OWUwYiIsIkdFQ01FIjoiI2Y4NzE3MSJ9OwogIHZhciBrbGJsPXsiR1VDTFUgQUwiOiJHVUNMVSBBTCIsIkFMIjoiQUwiLCJESUtLQVRMSSI6IkRJS0tBVExJIiwiR0VDTUUiOiJHRUNNRSJ9OwogIHZhciBlc2NvbD1yLmVudHJ5X3Njb3JlPj03NT8idmFyKC0tZ3JlZW4pIjpyLmVudHJ5X3Njb3JlPj02MD8idmFyKC0tZ3JlZW4yKSI6ci5lbnRyeV9zY29yZT49NDU/InZhcigtLXllbGxvdykiOnIuZW50cnlfc2NvcmU+PTMwPyJ2YXIoLS1yZWQyKSI6InZhcigtLXJlZCkiOwogIHZhciBwdmNvbD1yLnByaWNlX3ZzX2NvbG9yPT09ImdyZWVuIj8idmFyKC0tZ3JlZW4pIjpyLnByaWNlX3ZzX2NvbG9yPT09InllbGxvdyI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQyKSI7CgogIHZhciBtaD0nPGRpdiBjbGFzcz0ibWhlYWQiPjxkaXY+PGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6OHB4O2ZsZXgtd3JhcDp3cmFwIj4nCiAgICArJzxzcGFuIGNsYXNzPSJtdGl0bGUiIHN0eWxlPSJjb2xvcjonK3NzLnR4KyciPicrci50aWNrZXIrJzwvc3Bhbj4nCiAgICArJzxzcGFuIGNsYXNzPSJiYWRnZSIgc3R5bGU9ImJhY2tncm91bmQ6Jytzcy5iZysnO2NvbG9yOicrc3MudHgrJztib3JkZXI6MXB4IHNvbGlkICcrc3MuYmQrJztmb250LXNpemU6MTJweCI+Jytzcy5sYmwrJzwvc3Bhbj4nCiAgICArKHIucG9ydGZvbGlvPyc8c3BhbiBjbGFzcz0icG9ydC1iYWRnZSIgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O3BhZGRpbmc6M3B4IDhweCI+UG9ydGZvbHlvPC9zcGFuPic6JycpCiAgICArJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2U7Zm9udC13ZWlnaHQ6NjAwO21hcmdpbi10b3A6NHB4Ij4kJytyLmZpeWF0CiAgICArJyA8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6JytkYysnIj4nKyhyLmRlZ2lzaW0+PTA/IisiOiIiKStyLmRlZ2lzaW0rJyU8L3NwYW4+PC9kaXY+PC9kaXY+JwogICAgKyc8YnV0dG9uIGNsYXNzPSJtY2xvc2UiIG9uY2xpY2s9ImNsb3NlTSgpIj7inJU8L2J1dHRvbj48L2Rpdj4nOwoKICBtaCs9JzxkaXYgY2xhc3M9Im1ib2R5Ij48ZGl2IGNsYXNzPSJtY2hhcnR3Ij48Y2FudmFzIGlkPSJtY2hhcnQiPjwvY2FudmFzPjwvZGl2Pic7CgogIG1oKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O21hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij4nK2liKCJFbnRyeVNjb3JlIiwiR2lyaXMgS2FsaXRlc2kiKSsnPC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206NnB4Ij4nCiAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZTtjb2xvcjonK2VzY29sKyciPicrci5lbnRyeV9zY29yZSsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2NvbG9yOnZhcigtLW11dGVkKSI+LzEwMDwvc3Bhbj48L3NwYW4+JwogICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X2xhYmVsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJoZWlnaHQ6NnB4O2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXItcmFkaXVzOjNweDtvdmVyZmxvdzpoaWRkZW47bWFyZ2luLWJvdHRvbTo4cHgiPjxkaXYgc3R5bGU9ImhlaWdodDoxMDAlO3dpZHRoOicrci5lbnRyeV9zY29yZSsnJTtiYWNrZ3JvdW5kOicrZXNjb2wrJztib3JkZXItcmFkaXVzOjNweCI+PC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47Zm9udC1zaXplOjExcHgiPicKICAgICsnPGRpdj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj5TdSBhbmtpIGZpeWF0OiA8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOicrcHZjb2wrJztmb250LXdlaWdodDo2MDAiPicrci5wcmljZV92c19pZGVhbCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj5JZGVhbCBib2xnZTogPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbjIpO2ZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2UiPiQnK3IuaWRlYWxfZW50cnlfbG93KycgLSAkJytyLmlkZWFsX2VudHJ5X2hpZ2grJzwvc3Bhbj48L2Rpdj4nCiAgICArJzwvZGl2PjwvZGl2Pic7CgogIG1oKz0nPGRpdiBjbGFzcz0iZGJveCIgc3R5bGU9ImJhY2tncm91bmQ6Jytzcy5iZysnO2JvcmRlci1jb2xvcjonK3NzLmJkKyc7bWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgY2xhc3M9ImRsYmwiIHN0eWxlPSJjb2xvcjonK3NzLnR4KyciPicraWIoIlJSIiwiQWxpbSBLYXJhcmkgUi9SIikrJzwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHZlcmQiIHN0eWxlPSJjb2xvcjonKyhrY1tyLmthcmFyXXx8InZhcigtLW11dGVkKSIpKyciPicrKGtsYmxbci5rYXJhcl18fHIua2FyYXIpKyc8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5SaXNrIC8gT2R1bDwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6JytyckMrJztmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZSI+MSA6ICcrci5ycisnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkhlbWVuIEdpcjwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4yKTtmb250LWZhbWlseTpcJ0pldEJyYWlucyBNb25vXCcsbW9ub3NwYWNlIj4kJytyLmVudHJ5X2FnZ3Jlc3NpdmUrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5HZXJpIENla2lsbWU8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOiM2MGE1ZmE7Zm9udC1mYW1pbHk6XCdKZXRCcmFpbnMgTW9ub1wnLG1vbm9zcGFjZSI+JCcrci5lbnRyeV9taWQrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5CdXl1ayBEdXplbHRtZTwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0teWVsbG93KTtmb250LWZhbWlseTpcJ0pldEJyYWlucyBNb25vXCcsbW9ub3NwYWNlIj4kJytyLmVudHJ5X2NvbnNlcnZhdGl2ZSsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkhlZGVmPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjojNjBhNWZhO2ZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2UiPiQnK3IuaGVkZWYrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5TdG9wLUxvc3M8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpO2ZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2UiPiQnK3Iuc3RvcCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0icnJiYXIiPjxkaXYgY2xhc3M9InJyZmlsbCIgc3R5bGU9IndpZHRoOicrcnJQKyclO2JhY2tncm91bmQ6JytyckMrJyI+PC9kaXY+PC9kaXY+PC9kaXY+JzsKCiAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij5UZWtuaWsgQW5hbGl6PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkZ3JpZCIgc3R5bGU9Im1hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlRyZW5kIiwiVHJlbmQiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnRyZW5kPT09Ill1a3NlbGVuIj8idmFyKC0tZ3JlZW4pIjpyLnRyZW5kPT09IkR1c2VuIj8idmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrci50cmVuZCsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlJTSSIsIlJTSSAxNCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucnNpP3IucnNpPDMwPyJ2YXIoLS1ncmVlbikiOnIucnNpPjcwPyJ2YXIoLS1yZWQpIjoidmFyKC0teWVsbG93KSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucnNpfHwiPyIpKyhyLnJzaT9yLnJzaTwzMD8iIEFzaXJpIFNhdGltIjpyLnJzaT43MD8iIEFzaXJpIEFsaW0iOiIgTm90ciI6IiIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiU01BNTAiLCJTTUEgNTAiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmFib3ZlNTA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZCkiKSsnIj4nKyhyLmFib3ZlNTA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIpKyhyLnNtYTUwX2Rpc3QhPW51bGw/IiAoIityLnNtYTUwX2Rpc3QrIiUpIjoiIikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJTTUEyMDAiLCJTTUEgMjAwIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5hYm92ZTIwMD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkKSIpKyciPicrKHIuYWJvdmUyMDA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIpKyhyLnNtYTIwMF9kaXN0IT1udWxsPyIgKCIrci5zbWEyMDBfZGlzdCsiJSkiOiIiKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIjUyVyIsIjUySCBQb3ouIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci53NTJfcG9zaXRpb248PTMwPyJ2YXIoLS1ncmVlbikiOnIudzUyX3Bvc2l0aW9uPj04NT8idmFyKC0tcmVkKSI6InZhcigtLXllbGxvdykiKSsnIj4nK3IudzUyX3Bvc2l0aW9uKyclPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIkhhY2ltIiwiSGFjaW0iKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmhhY2ltPT09Ill1a3NlayI/InZhcigtLWdyZWVuKSI6ci5oYWNpbT09PSJEdXN1ayI/InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nK3IuaGFjaW0rJyAoJytyLnZvbF9yYXRpbysneCk8L2Rpdj48L2Rpdj4nCiAgICArJzwvZGl2Pic7CgogIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+VGVtZWwgQW5hbGl6PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkZ3JpZCIgc3R5bGU9Im1hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIkZvcndhcmRQRSIsIkZvcndhcmQgUEUiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnBlX2Z3ZD9yLnBlX2Z3ZDwyNT8idmFyKC0tZ3JlZW4pIjpyLnBlX2Z3ZDw0MD8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnBlX2Z3ZD9yLnBlX2Z3ZC50b0ZpeGVkKDEpOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJQRUciLCJQRUciKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnBlZz9yLnBlZzwxPyJ2YXIoLS1ncmVlbikiOnIucGVnPDI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5wZWc/ci5wZWcudG9GaXhlZCgyKToiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiRVBTR3Jvd3RoIiwiRVBTIELDvHnDvG1lIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5lcHNfZ3Jvd3RoP3IuZXBzX2dyb3d0aD49MjA/InZhcigtLWdyZWVuKSI6ci5lcHNfZ3Jvd3RoPj0wPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIuZXBzX2dyb3d0aCE9bnVsbD9yLmVwc19ncm93dGgrIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJSZXZHcm93dGgiLCJHZWxpciBCw7x5w7xtZSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucmV2X2dyb3d0aD9yLnJldl9ncm93dGg+PTE1PyJ2YXIoLS1ncmVlbikiOnIucmV2X2dyb3d0aD49MD8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnJldl9ncm93dGghPW51bGw/ci5yZXZfZ3Jvd3RoKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiTmV0TWFyZ2luIiwiTmV0IE1hcmppbiIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIubmV0X21hcmdpbj9yLm5ldF9tYXJnaW4+PTE1PyJ2YXIoLS1ncmVlbikiOnIubmV0X21hcmdpbj49NT8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLm5ldF9tYXJnaW4hPW51bGw/ci5uZXRfbWFyZ2luKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUk9FIiwiUk9FIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5yb2U/ci5yb2U+PTE1PyJ2YXIoLS1ncmVlbikiOnIucm9lPj01PyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucm9lIT1udWxsP3Iucm9lKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzwvZGl2Pic7CgogIHZhciBhaVRleHQgPSBBSV9EQVRBICYmIEFJX0RBVEFbdGlja2VyXTsKICBpZihhaVRleHQpewogICAgbWgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O21hcmdpbi1ib3R0b206MTJweCI+JzsKICAgIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPvCfpJYgQUkgQW5hbGl6IChDbGF1ZGUgU29ubmV0KTwvZGl2Pic7CiAgICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLXRleHQpO2xpbmUtaGVpZ2h0OjEuNzt3aGl0ZS1zcGFjZTpwcmUtd3JhcCI+JythaVRleHQrJzwvZGl2Pic7CiAgICBtaCs9JzwvZGl2Pic7CiAgfQogIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO3RleHQtYWxpZ246Y2VudGVyIj5CdSBhcmFjIHlhdGlyaW0gdGF2c2l5ZXNpIGRlZ2lsZGlyPC9kaXY+PC9kaXY+JzsKCiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1vZGFsIikuaW5uZXJIVE1MPW1oOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJvdmVybGF5IikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwogIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsKICAgIHZhciBjdHg9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1jaGFydCIpOwogICAgaWYoY3R4JiZyLmNoYXJ0X2Nsb3Nlcyl7CiAgICAgIG1DaGFydD1uZXcgQ2hhcnQoY3R4LHt0eXBlOiJsaW5lIixkYXRhOntsYWJlbHM6ci5jaGFydF9kYXRlcyxkYXRhc2V0czpbCiAgICAgICAge2xhYmVsOiJGaXlhdCIsZGF0YTpyLmNoYXJ0X2Nsb3Nlcyxib3JkZXJDb2xvcjpzcy5hYyxib3JkZXJXaWR0aDoyLGZpbGw6dHJ1ZSxiYWNrZ3JvdW5kQ29sb3I6c3MuYWMrIjIwIixwb2ludFJhZGl1czowLHRlbnNpb246MC4zfSwKICAgICAgICByLnNtYTUwP3tsYWJlbDoiU01BNTAiLGRhdGE6QXJyYXkoci5jaGFydF9jbG9zZXMubGVuZ3RoKS5maWxsKHIuc21hNTApLGJvcmRlckNvbG9yOiIjZjU5ZTBiIixib3JkZXJXaWR0aDoxLjUsYm9yZGVyRGFzaDpbNSw1XSxwb2ludFJhZGl1czowLGZpbGw6ZmFsc2V9Om51bGwsCiAgICAgICAgci5zbWEyMDA/e2xhYmVsOiJTTUEyMDAiLGRhdGE6QXJyYXkoci5jaGFydF9jbG9zZXMubGVuZ3RoKS5maWxsKHIuc21hMjAwKSxib3JkZXJDb2xvcjoiIzhiNWNmNiIsYm9yZGVyV2lkdGg6MS41LGJvcmRlckRhc2g6WzUsNV0scG9pbnRSYWRpdXM6MCxmaWxsOmZhbHNlfTpudWxsCiAgICAgIF0uZmlsdGVyKEJvb2xlYW4pfSxvcHRpb25zOntyZXNwb25zaXZlOnRydWUsbWFpbnRhaW5Bc3BlY3RSYXRpbzpmYWxzZSwKICAgICAgICBwbHVnaW5zOntsZWdlbmQ6e2xhYmVsczp7Y29sb3I6IiM2YjcyODAiLGZvbnQ6e3NpemU6MTB9fX19LAogICAgICAgIHNjYWxlczp7eDp7ZGlzcGxheTp0cnVlLHRpY2tzOntjb2xvcjoiIzM3NDE1MSIsbWF4VGlja3NMaW1pdDo1LGZvbnQ6e3NpemU6OX19LGdyaWQ6e2NvbG9yOiJyZ2JhKDI1NSwyNTUsMjU1LC4wNCkifX0sCiAgICAgICAgICB5OntkaXNwbGF5OnRydWUsdGlja3M6e2NvbG9yOiIjMzc0MTUxIixmb250OntzaXplOjl9fSxncmlkOntjb2xvcjoicmdiYSgyNTUsMjU1LDI1NSwuMDQpIn19fX19KTsKICAgIH0KICB9LDEwMCk7Cn0KCgovLyDilIDilIAgR8OcTkzDnEsgUlVUxLBOIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgAp2YXIgUlVUSU5fSVRFTVMgPSB7CiAgc2FiYWg6IHsKICAgIGxhYmVsOiAi8J+MhSBTYWJhaCDigJQgUGl5YXNhIEHDp8SxbG1hZGFuIMOWbmNlIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoiczEiLCB0ZXh0OiJEYXNoYm9hcmQnxLEgYcOnIOKAlCBNIGtyaXRlcmkgeWXFn2lsIG1pPyAoUyZQNTAwICsgTkFTREFRIFNNQTIwMCDDvHN0w7xuZGUpIn0sCiAgICAgIHtpZDoiczIiLCB0ZXh0OiJFYXJuaW5ncyBzZWttZXNpbmkga29udHJvbCBldCDigJQgYnVnw7xuL2J1IGhhZnRhIHJhcG9yIHZhciBtxLE/In0sCiAgICAgIHtpZDoiczMiLCB0ZXh0OiJWSVggMjUgYWx0xLFuZGEgbcSxPyAoWcO8a3Nla3NlIHllbmkgcG96aXN5b24gYcOnbWEpIn0sCiAgICAgIHtpZDoiczQiLCB0ZXh0OiLDlm5jZWtpIGfDvG5kZW4gYmVrbGV5ZW4gYWxhcm0gbWFpbGkgdmFyIG3EsT8ifQogICAgXQogIH0sCiAgb2dsZW46IHsKICAgIGxhYmVsOiAi8J+TiiDDlsSfbGVkZW4gU29ucmEg4oCUIFBpeWFzYSBBw6fEsWtrZW4iLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJvMSIsIHRleHQ6IlBvcnRmw7Z5w7xtIHNla21lc2luZGUgaGlzc2VsZXJpbWUgYmFrIOKAlCBiZWtsZW5tZWRpayBkw7zFn8O8xZ8gdmFyIG3EsT8ifSwKICAgICAge2lkOiJvMiIsIHRleHQ6IlN0b3Agc2V2aXllc2luZSB5YWtsYcWfYW4gaGlzc2UgdmFyIG3EsT8gKEvEsXJtxLF6xLEgacWfYXJldCkifSwKICAgICAge2lkOiJvMyIsIHRleHQ6IkFsIHNpbnlhbGkgc2VrbWVzaW5kZSB5ZW5pIGbEsXJzYXQgw6fEsWttxLHFnyBtxLE/In0sCiAgICAgIHtpZDoibzQiLCB0ZXh0OiJXYXRjaGxpc3QndGVraSBoaXNzZWxlcmRlIGdpcmnFnyBrYWxpdGVzaSA2MCsgb2xhbiB2YXIgbcSxPyJ9LAogICAgICB7aWQ6Im81IiwgdGV4dDoiSGFiZXJsZXJkZSBwb3J0ZsO2ecO8bcO8IGV0a2lsZXllbiDDtm5lbWxpIGdlbGnFn21lIHZhciBtxLE/In0KICAgIF0KICB9LAogIGFrc2FtOiB7CiAgICBsYWJlbDogIvCfjJkgQWvFn2FtIOKAlCBQaXlhc2EgS2FwYW5kxLFrdGFuIFNvbnJhIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoiYTEiLCB0ZXh0OiIxSCBzaW55YWxsZXJpbmkga29udHJvbCBldCDigJQgaGFmdGFsxLFrIHRyZW5kIGRlxJ9pxZ9tacWfIG1pPyJ9LAogICAgICB7aWQ6ImEyIiwgdGV4dDoiWWFyxLFuIGnDp2luIHBvdGFuc2l5ZWwgZ2lyacWfIG5va3RhbGFyxLFuxLEgbm90IGFsIn0sCiAgICAgIHtpZDoiYTMiLCB0ZXh0OiJQb3J0ZsO2eWRla2kgaGVyIGhpc3NlbmluIHN0b3Agc2V2aXllc2luaSBnw7Z6ZGVuIGdlw6dpciJ9LAogICAgICB7aWQ6ImE0IiwgdGV4dDoiWWFyxLFuIHJhcG9yIGHDp8Sxa2xheWFjYWsgaGlzc2UgdmFyIG3EsT8gKEVhcm5pbmdzIHNla21lc2kpIn0KICAgIF0KICB9LAogIGhhZnRhbGlrOiB7CiAgICBsYWJlbDogIvCfk4UgSGFmdGFsxLFrIOKAlCBQYXphciBBa8WfYW3EsSIsCiAgICBpdGVtczogWwogICAgICB7aWQ6ImgxIiwgdGV4dDoiU3RvY2sgUm92ZXInZGEgQ0FOU0xJTSBzY3JlZW5lcifEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoMiIsIHRleHQ6IlZDUCBNaW5lcnZpbmkgc2NyZWVuZXInxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDMiLCB0ZXh0OiJRdWxsYW1hZ2dpZSBCcmVha291dCBzY3JlZW5lcifEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoNCIsIHRleHQ6IkZpbnZpeidkZSBJbnN0aXR1dGlvbmFsIEJ1eWluZyBzY3JlZW5lcifEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoNSIsIHRleHQ6IsOHYWvEscWfYW4gaGlzc2VsZXJpIGJ1bCDigJQgZW4gZ8O8w6dsw7wgYWRheWxhciJ9LAogICAgICB7aWQ6Img2IiwgdGV4dDoiR2l0SHViIEFjdGlvbnMnZGFuIFJ1biBXb3JrZmxvdyBiYXMg4oCUIHNpdGUgZ8O8bmNlbGxlbmlyIn0sCiAgICAgIHtpZDoiaDciLCB0ZXh0OiJHZWxlY2VrIGhhZnRhbsSxbiBlYXJuaW5ncyB0YWt2aW1pbmkga29udHJvbCBldCJ9LAogICAgICB7aWQ6Img4IiwgdGV4dDoiUG9ydGbDtnkgZ2VuZWwgZGXEn2VybGVuZGlybWVzaSDigJQgaGVkZWZsZXIgaGFsYSBnZcOnZXJsaSBtaT8ifQogICAgXQogIH0KfTsKCmZ1bmN0aW9uIGdldFRvZGF5S2V5KCl7CiAgcmV0dXJuIG5ldyBEYXRlKCkudG9EYXRlU3RyaW5nKCk7Cn0KCmZ1bmN0aW9uIGxvYWRDaGVja2VkKCl7CiAgdHJ5ewogICAgdmFyIGRhdGEgPSBsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgncnV0aW5fY2hlY2tlZCcpOwogICAgaWYoIWRhdGEpIHJldHVybiB7fTsKICAgIHZhciBwYXJzZWQgPSBKU09OLnBhcnNlKGRhdGEpOwogICAgLy8gU2FkZWNlIGJ1Z8O8bsO8biB2ZXJpbGVyaW5pIGt1bGxhbgogICAgaWYocGFyc2VkLmRhdGUgIT09IGdldFRvZGF5S2V5KCkpIHJldHVybiB7fTsKICAgIHJldHVybiBwYXJzZWQuaXRlbXMgfHwge307CiAgfWNhdGNoKGUpe3JldHVybiB7fTt9Cn0KCmZ1bmN0aW9uIHNhdmVDaGVja2VkKGNoZWNrZWQpewogIGxvY2FsU3RvcmFnZS5zZXRJdGVtKCdydXRpbl9jaGVja2VkJywgSlNPTi5zdHJpbmdpZnkoewogICAgZGF0ZTogZ2V0VG9kYXlLZXkoKSwKICAgIGl0ZW1zOiBjaGVja2VkCiAgfSkpOwp9CgpmdW5jdGlvbiB0b2dnbGVDaGVjayhpZCl7CiAgdmFyIGNoZWNrZWQgPSBsb2FkQ2hlY2tlZCgpOwogIGlmKGNoZWNrZWRbaWRdKSBkZWxldGUgY2hlY2tlZFtpZF07CiAgZWxzZSBjaGVja2VkW2lkXSA9IHRydWU7CiAgc2F2ZUNoZWNrZWQoY2hlY2tlZCk7CiAgcmVuZGVyUnV0aW4oKTsKfQoKZnVuY3Rpb24gcmVzZXRSdXRpbigpewogIGxvY2FsU3RvcmFnZS5yZW1vdmVJdGVtKCdydXRpbl9jaGVja2VkJyk7CiAgcmVuZGVyUnV0aW4oKTsKfQoKZnVuY3Rpb24gcmVuZGVyUnV0aW4oKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgdmFyIGNoZWNrZWQgPSBsb2FkQ2hlY2tlZCgpOwogIHZhciB0b2RheSA9IG5ldyBEYXRlKCk7CiAgdmFyIGlzV2Vla2VuZCA9IHRvZGF5LmdldERheSgpID09PSAwIHx8IHRvZGF5LmdldERheSgpID09PSA2OwogIHZhciBkYXlOYW1lID0gWydQYXphcicsJ1BhemFydGVzaScsJ1NhbMSxJywnw4dhcsWfYW1iYScsJ1BlcsWfZW1iZScsJ0N1bWEnLCdDdW1hcnRlc2knXVt0b2RheS5nZXREYXkoKV07CiAgdmFyIGRhdGVTdHIgPSB0b2RheS50b0xvY2FsZURhdGVTdHJpbmcoJ3RyLVRSJywge2RheTonbnVtZXJpYycsbW9udGg6J2xvbmcnLHllYXI6J251bWVyaWMnfSk7CgogIC8vIFByb2dyZXNzIGhlc2FwbGEKICB2YXIgdG90YWxJdGVtcyA9IDA7CiAgdmFyIGRvbmVJdGVtcyA9IDA7CiAgdmFyIHNlY3Rpb25zID0gaXNXZWVrZW5kID8gWydoYWZ0YWxpayddIDogWydzYWJhaCcsJ29nbGVuJywnYWtzYW0nXTsKICBzZWN0aW9ucy5mb3JFYWNoKGZ1bmN0aW9uKGspewogICAgUlVUSU5fSVRFTVNba10uaXRlbXMuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsKICAgICAgdG90YWxJdGVtcysrOwogICAgICBpZihjaGVja2VkW2l0ZW0uaWRdKSBkb25lSXRlbXMrKzsKICAgIH0pOwogIH0pOwogIHZhciBwY3QgPSB0b3RhbEl0ZW1zID4gMCA/IE1hdGgucm91bmQoZG9uZUl0ZW1zL3RvdGFsSXRlbXMqMTAwKSA6IDA7CiAgdmFyIHBjdENvbCA9IHBjdD09PTEwMD8ndmFyKC0tZ3JlZW4pJzpwY3Q+PTUwPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tbXV0ZWQpJzsKCiAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgLy8gSGVhZGVyCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7ZmxleC13cmFwOndyYXA7Z2FwOjEwcHgiPic7CiAgaCArPSAnPGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrZGF5TmFtZSsnIFJ1dGluaTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK2RhdGVTdHIrJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjhweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JytwY3RDb2wrJyI+JytwY3QrJyU8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+Jytkb25lSXRlbXMrJy8nK3RvdGFsSXRlbXMrJyB0YW1hbWxhbmTEsTwvZGl2PjwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iaGVpZ2h0OjZweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czozcHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi10b3A6MTJweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJoZWlnaHQ6MTAwJTt3aWR0aDonK3BjdCsnJTtiYWNrZ3JvdW5kOicrcGN0Q29sKyc7Ym9yZGVyLXJhZGl1czozcHg7dHJhbnNpdGlvbjp3aWR0aCAuNXMgZWFzZSI+PC9kaXY+PC9kaXY+JzsKICBpZihwY3Q9PT0xMDApIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyO21hcmdpbi10b3A6MTBweDtmb250LXNpemU6MTRweDtjb2xvcjp2YXIoLS1ncmVlbikiPvCfjokgVMO8bSBtYWRkZWxlciB0YW1hbWxhbmTEsSE8L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIFNlY3Rpb25zCiAgc2VjdGlvbnMuZm9yRWFjaChmdW5jdGlvbihrKXsKICAgIHZhciBzZWMgPSBSVVRJTl9JVEVNU1trXTsKICAgIHZhciBzZWNEb25lID0gc2VjLml0ZW1zLmZpbHRlcihmdW5jdGlvbihpKXtyZXR1cm4gY2hlY2tlZFtpLmlkXTt9KS5sZW5ndGg7CiAgICB2YXIgc2VjVG90YWwgPSBzZWMuaXRlbXMubGVuZ3RoOwogICAgdmFyIHNlY1BjdCA9IE1hdGgucm91bmQoc2VjRG9uZS9zZWNUb3RhbCoxMDApOwogICAgdmFyIHNlY0NvbCA9IHNlY1BjdD09PTEwMD8ndmFyKC0tZ3JlZW4pJzpzZWNQY3Q+MD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLW11dGVkKSc7CgogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjEycHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrc2VjLmxhYmVsKyc8L2Rpdj4nOwogICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOicrc2VjQ29sKyc7Zm9udC13ZWlnaHQ6NjAwIj4nK3NlY0RvbmUrJy8nK3NlY1RvdGFsKyc8L3NwYW4+PC9kaXY+JzsKCiAgICBzZWMuaXRlbXMuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsKICAgICAgdmFyIGRvbmUgPSAhIWNoZWNrZWRbaXRlbS5pZF07CiAgICAgIHZhciBiZ0NvbG9yID0gZG9uZSA/ICdyZ2JhKDE2LDE4NSwxMjksLjA2KScgOiAncmdiYSgyNTUsMjU1LDI1NSwuMDIpJzsKICAgICAgdmFyIGJvcmRlckNvbG9yID0gZG9uZSA/ICdyZ2JhKDE2LDE4NSwxMjksLjIpJyA6ICdyZ2JhKDI1NSwyNTUsMjU1LC4wNSknOwogICAgICB2YXIgY2hlY2tCb3JkZXIgPSBkb25lID8gJ3ZhcigtLWdyZWVuKScgOiAndmFyKC0tbXV0ZWQpJzsKICAgICAgdmFyIGNoZWNrQmcgPSBkb25lID8gJ3ZhcigtLWdyZWVuKScgOiAndHJhbnNwYXJlbnQnOwogICAgICB2YXIgdGV4dENvbG9yID0gZG9uZSA/ICd2YXIoLS1tdXRlZCknIDogJ3ZhcigtLXRleHQpJzsKICAgICAgdmFyIHRleHREZWNvID0gZG9uZSA/ICdsaW5lLXRocm91Z2gnIDogJ25vbmUnOwogICAgICB2YXIgY2hlY2ttYXJrID0gZG9uZSA/ICc8c3ZnIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cG9seWxpbmUgcG9pbnRzPSIyLDYgNSw5IDEwLDMiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+PC9zdmc+JyA6ICcnOwogICAgICBoICs9ICc8ZGl2IG9uY2xpY2s9InRvZ2dsZUNoZWNrKFwnJyArIGl0ZW0uaWQgKyAnXCcpIiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmZsZXgtc3RhcnQ7Z2FwOjEycHg7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6OHB4O2N1cnNvcjpwb2ludGVyO21hcmdpbi1ib3R0b206NnB4O2JhY2tncm91bmQ6JyArIGJnQ29sb3IgKyAnO2JvcmRlcjoxcHggc29saWQgJyArIGJvcmRlckNvbG9yICsgJyI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZmxleC1zaHJpbms6MDt3aWR0aDoyMHB4O2hlaWdodDoyMHB4O2JvcmRlci1yYWRpdXM6NXB4O2JvcmRlcjoycHggc29saWQgJyArIGNoZWNrQm9yZGVyICsgJztiYWNrZ3JvdW5kOicgKyBjaGVja0JnICsgJztkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7bWFyZ2luLXRvcDoxcHgiPicgKyBjaGVja21hcmsgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2NvbG9yOicgKyB0ZXh0Q29sb3IgKyAnO2xpbmUtaGVpZ2h0OjEuNTt0ZXh0LWRlY29yYXRpb246JyArIHRleHREZWNvICsgJyI+JyArIGl0ZW0udGV4dCArICc8L3NwYW4+JzsKICAgICAgaCArPSAnPC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9KTsKCiAgLy8gSGFmdGEgacOnaSBvbGR1xJ91bmRhIGhhZnRhbMSxayBiw7Zsw7xtw7wgZGUgZ8O2c3RlciAoa2F0bGFuYWJpbGlyKQogIGlmKCFpc1dlZWtlbmQpewogICAgdmFyIGhTZWMgPSBSVVRJTl9JVEVNU1snaGFmdGFsaWsnXTsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wNCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjE1KTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOiM2MGE1ZmE7bWFyZ2luLWJvdHRvbTo0cHgiPicraFNlYy5sYWJlbCsnPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+UGF6YXIgYWvFn2FtxLEgeWFwxLFsYWNha2xhciDigJQgxZ91IGFuIGfDtnN0ZXJpbSBtb2R1bmRhPC9kaXY+PC9kaXY+JzsKICB9CgogIC8vIFJlc2V0IGJ1dG9udQogIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyO21hcmdpbi10b3A6NnB4Ij4nOwogIGggKz0gJzxidXR0b24gb25jbGljaz0icmVzZXRSdXRpbigpIiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS1tdXRlZCk7cGFkZGluZzo4cHggMTZweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTJweDtjdXJzb3I6cG9pbnRlciI+8J+UhCBMaXN0ZXlpIFPEsWbEsXJsYTwvYnV0dG9uPic7CiAgaCArPSAnPC9kaXY+JzsKCiAgaCArPSAnPC9kaXY+JzsKICBncmlkLmlubmVySFRNTCA9IGg7Cn0KCgpmdW5jdGlvbiBjbG9zZU0oZSl7CiAgaWYoIWV8fGUudGFyZ2V0PT09ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm92ZXJsYXkiKSl7CiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgib3ZlcmxheSIpLmNsYXNzTGlzdC5yZW1vdmUoIm9wZW4iKTsKICAgIGlmKG1DaGFydCl7bUNoYXJ0LmRlc3Ryb3koKTttQ2hhcnQ9bnVsbDt9CiAgfQp9CgpyZW5kZXJTdGF0cygpOwpyZW5kZXJEYXNoYm9hcmQoKTsKCgoKLy8g4pSA4pSAIEzEsFNURSBEw5xaRU5MRU1FIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgAp2YXIgZWRpdFdhdGNobGlzdCA9IFtdOwp2YXIgZWRpdFBvcnRmb2xpbyA9IFtdOwoKZnVuY3Rpb24gb3BlbkVkaXRMaXN0KCl7CiAgZWRpdFdhdGNobGlzdCA9IFRGX0RBVEFbJzFkJ10uZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pLm1hcChmdW5jdGlvbihyKXtyZXR1cm4gci50aWNrZXI7fSk7CiAgZWRpdFBvcnRmb2xpbyA9IFBPUlQuc2xpY2UoKTsKICByZW5kZXJFZGl0TGlzdHMoKTsKICAvLyBMb2FkIHNhdmVkIHRva2VuIGZyb20gbG9jYWxTdG9yYWdlCiAgdmFyIHNhdmVkID0gbG9jYWxTdG9yYWdlLmdldEl0ZW0oJ2doX3Rva2VuJyk7CiAgaWYoc2F2ZWQpIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZSA9IHNhdmVkOwogIHZhciB0cz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidG9rZW5TZWN0aW9uIik7IGlmKHRzKSB0cy5zdHlsZS5kaXNwbGF5PSJub25lIjsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFBvcHVwIikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwp9CgoKZnVuY3Rpb24gdG9nZ2xlVG9rZW5TZWN0aW9uKCl7CiAgdmFyIHM9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInRva2VuU2VjdGlvbiIpOwogIGlmKHMpIHMuc3R5bGUuZGlzcGxheT1zLnN0eWxlLmRpc3BsYXk9PT0ibm9uZSI/ImJsb2NrIjoibm9uZSI7Cn0KCmZ1bmN0aW9uIHNhdmVUb2tlbigpewogIHZhciB0PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZS50cmltKCk7CiAgaWYoIXQpe2FsZXJ0KCJUb2tlbiBib3MhIik7cmV0dXJuO30KICBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgiZ2hfdG9rZW4iLHQpOwogIHZhciB0cz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidG9rZW5TZWN0aW9uIik7IGlmKHRzKSB0cy5zdHlsZS5kaXNwbGF5PSJub25lIjsKICBzZXRFZGl0U3RhdHVzKCLinIUgVG9rZW4ga2F5ZGVkaWxkaSIsImdyZWVuIik7Cn0KCmZ1bmN0aW9uIGNsb3NlRWRpdFBvcHVwKGUpewogIGlmKCFlfHxlLnRhcmdldD09PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0UG9wdXAiKSl7CiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFBvcHVwIikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpOwogIH0KfQoKZnVuY3Rpb24gcmVuZGVyRWRpdExpc3RzKCl7CiAgdmFyIHdlID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIndhdGNobGlzdEVkaXRvciIpOwogIHZhciBwZSA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJwb3J0Zm9saW9FZGl0b3IiKTsKICBpZighd2V8fCFwZSkgcmV0dXJuOwoKICB3ZS5pbm5lckhUTUwgPSBlZGl0V2F0Y2hsaXN0Lm1hcChmdW5jdGlvbih0LGkpewogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO3BhZGRpbmc6NXB4IDhweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6NXB4O21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OlwnSmV0QnJhaW5zIE1vbm9cJyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwIj4nK3QrJzwvc3Bhbj4nCiAgICAgICsnPGJ1dHRvbiBvbmNsaWNrPSJyZW1vdmVUaWNrZXIoXCd3YXRjaFwnLCcraSsnKSIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtib3JkZXI6bm9uZTtjb2xvcjp2YXIoLS1yZWQyKTt3aWR0aDoyMHB4O2hlaWdodDoyMHB4O2JvcmRlci1yYWRpdXM6NHB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxMnB4Ij7inJU8L2J1dHRvbj4nCiAgICAgICsnPC9kaXY+JzsKICB9KS5qb2luKCcnKTsKCiAgcGUuaW5uZXJIVE1MID0gZWRpdFBvcnRmb2xpby5tYXAoZnVuY3Rpb24odCxpKXsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtwYWRkaW5nOjVweCA4cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjVweDttYXJnaW4tYm90dG9tOjRweCI+JwogICAgICArJzxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpcJ0pldEJyYWlucyBNb25vXCcsbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicrdCsnPC9zcGFuPicKICAgICAgKyc8YnV0dG9uIG9uY2xpY2s9InJlbW92ZVRpY2tlcihcJ3BvcnRcJywnK2krJykiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Ym9yZGVyOm5vbmU7Y29sb3I6dmFyKC0tcmVkMik7d2lkdGg6MjBweDtoZWlnaHQ6MjBweDtib3JkZXItcmFkaXVzOjRweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTJweCI+4pyVPC9idXR0b24+JwogICAgICArJzwvZGl2Pic7CiAgfSkuam9pbignJyk7Cn0KCmZ1bmN0aW9uIGFkZFRpY2tlcihsaXN0KXsKICB2YXIgaW5wdXRJZCA9IGxpc3Q9PT0nd2F0Y2gnPyJuZXdXYXRjaFRpY2tlciI6Im5ld1BvcnRUaWNrZXIiOwogIHZhciB2YWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZChpbnB1dElkKS52YWx1ZS50cmltKCkudG9VcHBlckNhc2UoKTsKICBpZighdmFsKSByZXR1cm47CiAgaWYobGlzdD09PSd3YXRjaCcgJiYgIWVkaXRXYXRjaGxpc3QuaW5jbHVkZXModmFsKSkgZWRpdFdhdGNobGlzdC5wdXNoKHZhbCk7CiAgaWYobGlzdD09PSdwb3J0JyAgJiYgIWVkaXRQb3J0Zm9saW8uaW5jbHVkZXModmFsKSkgZWRpdFBvcnRmb2xpby5wdXNoKHZhbCk7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoaW5wdXRJZCkudmFsdWUgPSAiIjsKICByZW5kZXJFZGl0TGlzdHMoKTsKfQoKZnVuY3Rpb24gcmVtb3ZlVGlja2VyKGxpc3QsIGlkeCl7CiAgaWYobGlzdD09PSd3YXRjaCcpIGVkaXRXYXRjaGxpc3Quc3BsaWNlKGlkeCwxKTsKICBlbHNlIGVkaXRQb3J0Zm9saW8uc3BsaWNlKGlkeCwxKTsKICByZW5kZXJFZGl0TGlzdHMoKTsKfQoKZnVuY3Rpb24gc2F2ZUxpc3RUb0dpdGh1YigpewogIHZhciB0b2tlbiA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZS50cmltKCk7CiAgaWYoIXRva2VuKXsgc2V0RWRpdFN0YXR1cygi4p2MIFRva2VuIGdlcmVrbGkg4oCUIGt1dHV5YSBnaXIiLCJyZWQiKTsgcmV0dXJuOyB9CiAgbG9jYWxTdG9yYWdlLnNldEl0ZW0oJ2doX3Rva2VuJywgdG9rZW4pOwoKICB2YXIgY29uZmlnID0geyB3YXRjaGxpc3Q6IGVkaXRXYXRjaGxpc3QsIHBvcnRmb2xpbzogZWRpdFBvcnRmb2xpbyB9OwogIHZhciBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoY29uZmlnLCBudWxsLCAyKTsKICB2YXIgYjY0ID0gYnRvYSh1bmVzY2FwZShlbmNvZGVVUklDb21wb25lbnQoY29udGVudCkpKTsKCiAgc2V0RWRpdFN0YXR1cygi8J+SviBLYXlkZWRpbGl5b3IuLi4iLCJ5ZWxsb3ciKTsKCiAgdmFyIGFwaVVybCA9ICJodHRwczovL2FwaS5naXRodWIuY29tL3JlcG9zL2dodXJ6enovY2Fuc2xpbS9jb250ZW50cy9jb25maWcuanNvbiI7CiAgdmFyIGhlYWRlcnMgPSB7IkF1dGhvcml6YXRpb24iOiJ0b2tlbiAiK3Rva2VuLCJDb250ZW50LVR5cGUiOiJhcHBsaWNhdGlvbi9qc29uIn07CgogIC8vIEZpcnN0IGdldCBjdXJyZW50IFNIQSBpZiBleGlzdHMKICBmZXRjaChhcGlVcmwsIHtoZWFkZXJzOmhlYWRlcnN9KQogICAgLnRoZW4oZnVuY3Rpb24ocil7IHJldHVybiByLm9rID8gci5qc29uKCkgOiBudWxsOyB9KQogICAgLnRoZW4oZnVuY3Rpb24oZXhpc3RpbmcpewogICAgICB2YXIgcGF5bG9hZCA9IHsKICAgICAgICBtZXNzYWdlOiAiTGlzdGUgZ3VuY2VsbGVuZGkgIiArIG5ldyBEYXRlKCkudG9Mb2NhbGVEYXRlU3RyaW5nKCJ0ci1UUiIpLAogICAgICAgIGNvbnRlbnQ6IGI2NAogICAgICB9OwogICAgICBpZihleGlzdGluZyAmJiBleGlzdGluZy5zaGEpIHBheWxvYWQuc2hhID0gZXhpc3Rpbmcuc2hhOwoKICAgICAgcmV0dXJuIGZldGNoKGFwaVVybCwgewogICAgICAgIG1ldGhvZDoiUFVUIiwKICAgICAgICBoZWFkZXJzOmhlYWRlcnMsCiAgICAgICAgYm9keTpKU09OLnN0cmluZ2lmeShwYXlsb2FkKQogICAgICB9KTsKICAgIH0pCiAgICAudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYoci5vayB8fCByLnN0YXR1cz09PTIwMSl7CiAgICAgICAgc2V0RWRpdFN0YXR1cygi4pyFIEtheWRlZGlsZGkhIEJpciBzb25yYWtpIENvbGFiIMOnYWzEscWfdMSxcm1hc8SxbmRhIGFrdGlmIG9sdXIuIiwiZ3JlZW4iKTsKICAgICAgICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7Y2xvc2VFZGl0UG9wdXAoKTt9LDIwMDApOwogICAgICB9IGVsc2UgewogICAgICAgIHNldEVkaXRTdGF0dXMoIuKdjCBIYXRhOiAiK3Iuc3RhdHVzKyIg4oCUIFRva2VuJ8SxIGtvbnRyb2wgZXQiLCJyZWQiKTsKICAgICAgfQogICAgfSkKICAgIC5jYXRjaChmdW5jdGlvbihlKXsgc2V0RWRpdFN0YXR1cygi4p2MIEhhdGE6ICIrZS5tZXNzYWdlLCJyZWQiKTsgfSk7Cn0KCmZ1bmN0aW9uIHNldEVkaXRTdGF0dXMobXNnLCBjb2xvcil7CiAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImVkaXRTdGF0dXMiKTsKICBpZihlbCl7CiAgICBlbC50ZXh0Q29udGVudCA9IG1zZzsKICAgIGVsLnN0eWxlLmNvbG9yID0gY29sb3I9PT0iZ3JlZW4iPyJ2YXIoLS1ncmVlbikiOmNvbG9yPT09InJlZCI/InZhcigtLXJlZDIpIjoidmFyKC0teWVsbG93KSI7CiAgfQp9Cgo8L3NjcmlwdD4KPC9ib2R5Pgo8L2h0bWw+"
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


def build_html(tf_data, timestamp, earnings_data=None, market_data=None, news_data=None, ai_analyses=None):
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
    ai_json = json.dumps(ai_analyses or {}, ensure_ascii=False)
    html = html.replace("%%AI_DATA%%",       ai_json)
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
    if r.get('hata') or r.get('sinyal') not in ['GUCLU AL','AL']:
        continue
    if len(ai_analyses) >= 5:
        break
    print(f'  {r["ticker"]} analiz ediliyor...')
    analysis = get_ai_analysis(r['ticker'], r, news_data)
    if analysis:
        ai_analyses[r['ticker']] = analysis
        print(f'  ✅ {r["ticker"]} tamamlandi')
print(f'  {len(ai_analyses)} AI analizi tamamlandi')

# ── MAIN ──────────────────────────────────────────────────────
timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
print("\n📊 HTML olusturuluyor...")
html = build_html(tf_data, timestamp, earnings_data, market_data, news_data, ai_analyses)
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
