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

# ── FINNHUB ANLИК FİYAT ──────────────────────────────────────
def get_realtime_price(ticker, finnhub_key):
    import urllib.request, json as _json
    try:
        url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={finnhub_key}'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
            # c=current, pc=previous close, d=change, dp=change%
            if data.get('c') and data['c'] > 0:
                return {
                    'price':  round(float(data['c']), 2),
                    'change': round(float(data.get('dp', 0)), 2),
                    'prev':   round(float(data.get('pc', 0)), 2),
                    'high':   round(float(data.get('h', 0)), 2),
                    'low':    round(float(data.get('l', 0)), 2),
                }
    except Exception as e:
        pass
    return None

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
            
            # Finnhub anlık fiyat ile güncelle
            rt = get_realtime_price(ticker, FINNHUB_KEY)
            if rt and rt['price'] > 0:
                price  = rt['price']
                change = rt['change']
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


# ── PİYASA YÖNÜ (FTD + Dağıtım Günleri) ──────────────────────
def get_market_direction():
    """O'Neil follow-through day ve dağıtım günü analizi (S&P 500 + Nasdaq)."""
    CORRECTION_THRESHOLD = -0.08   # zirveden %8+ düşüş = düzeltme
    DISTRIBUTION_DROP    = -0.002  # %0.2+ düşüş + artan hacim = dağıtım günü
    DIST_LOOKBACK        = 25
    FTD_MIN_GAIN         = 0.015   # FTD için min %1.5 yükseliş
    FTD_WINDOW           = (4, 10) # deneme 4-10. günü (ideal 4-7)
    RALLY_EXPIRY         = 15

    out = {}
    for name, sym in {'SP500': '^GSPC', 'NASDAQ': '^IXIC'}.items():
        try:
            hist = yf.Ticker(sym).history(period='1y')
            hist = hist.dropna(subset=['Close'])  # NaN satırları temizle (Zirveden %NaN fix)
            if hist.empty or len(hist) < 60:
                out[name] = {'error': 'veri yok'}
                continue
            closes = hist['Close']; lows = hist['Low']; vols = hist['Volume']
            peak     = closes.cummax()
            drawdown = closes / peak - 1.0
            chg      = closes.pct_change()

            # Dağıtım günleri (son 25 işlem günü)
            dist_days = []
            recent = set(hist.index[-DIST_LOOKBACK:])
            for i in range(1, len(hist)):
                ts = hist.index[i]
                if ts not in recent:
                    continue
                if chg.iloc[i] <= DISTRIBUTION_DROP and vols.iloc[i] > vols.iloc[i-1]:
                    dist_days.append({'date': ts.strftime('%d %b'),
                                      'chg': round(float(chg.iloc[i]) * 100, 2)})

            dd_now   = float(drawdown.iloc[-1])
            in_corr  = dd_now <= CORRECTION_THRESHOLD
            was_corr = bool((drawdown.tail(40) <= CORRECTION_THRESHOLD).any())

            rally_day, rally_low, ftd = 0, None, None
            if in_corr or was_corr:
                corr_mask = drawdown <= CORRECTION_THRESHOLD
                if corr_mask.any():
                    first_corr = corr_mask.idxmax()
                    low_idx    = lows.loc[first_corr:].idxmin()
                    rally_low  = float(lows.loc[low_idx])
                    after      = hist.loc[low_idx:].iloc[1:]
                    day_count  = 0
                    for ts, row in after.iterrows():
                        # Deneme dibi kırılırsa sayaç sıfırlanır, yeni dip baz alınır
                        if float(row['Low']) < rally_low:
                            day_count = 0
                            rally_low = float(row['Low'])
                            continue
                        c = float(chg.loc[ts]) if chg.loc[ts] == chg.loc[ts] else 0.0
                        if day_count == 0:
                            rng   = float(row['High']) - float(row['Low'])
                            upper = rng > 0 and (float(row['Close']) - float(row['Low'])) / rng >= 0.5
                            if c > 0 or upper:
                                day_count = 1
                            continue
                        day_count += 1
                        prev_vol = float(vols.shift(1).loc[ts])
                        if (FTD_WINDOW[0] <= day_count <= FTD_WINDOW[1]
                                and c >= FTD_MIN_GAIN
                                and float(row['Volume']) > prev_vol):
                            ftd = {'date': ts.strftime('%d %b'),
                                   'gain': round(c * 100, 2),
                                   'day': day_count}
                            break
                        if day_count > RALLY_EXPIRY:
                            day_count = 0
                    rally_day = day_count

            if ftd:
                status = 'ftd'
            elif in_corr and rally_day > 0:
                status = 'rally'
            elif in_corr:
                status = 'correction'
            elif len(dist_days) >= 5:
                status = 'pressure'
            else:
                status = 'uptrend'

            out[name] = {
                'drawdown':   round(dd_now * 100, 1),
                'dist_count': len(dist_days),
                'dist_days':  dist_days,
                'rally_day':  rally_day,
                'rally_low':  round(rally_low) if rally_low else None,
                'ftd':        ftd,
                'status':     status,
            }
        except Exception as e:
            out[name] = {'error': str(e)}
    return out

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




# ── HABER ÇEVİRİSİ (Cache ile) ────────────────────────────────
def load_news_cache():
    """GitHub'dan onceki cevrilmis haber cache'ini yukler"""
    try:
        import urllib.request, json as _json, base64 as _b64
        url = f'https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/news_cache.json'
        req = urllib.request.Request(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
            content = _b64.b64decode(data['content']).decode('utf-8')
            cache = _json.loads(content)
            print(f'  Cache yuklendi: {len(cache)} cevrilmis haber')
            return cache
    except Exception as e:
        print(f'  Cache yok, sıfırdan baslıyoruz')
        return {}

def save_news_cache(cache):
    """Cache'i GitHub'a kaydet"""
    try:
        import urllib.request, json as _json, base64 as _b64
        content = _json.dumps(cache, ensure_ascii=False, indent=2)
        encoded = _b64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        # Mevcut SHA'yı al
        url = f'https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/news_cache.json'
        sha = None
        try:
            req = urllib.request.Request(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                sha = _json.loads(resp.read()).get('sha')
        except: pass
        
        payload = {
            'message': 'Update news cache',
            'content': encoded,
        }
        if sha: payload['sha'] = sha
        
        req = urllib.request.Request(url, 
            data=_json.dumps(payload).encode('utf-8'),
            headers={'Authorization': f'token {GITHUB_TOKEN}', 'Content-Type': 'application/json'},
            method='PUT')
        urllib.request.urlopen(req, timeout=10)
        print(f'  Cache kaydedildi: {len(cache)} haber')
    except Exception as e:
        print(f'  Cache kayit hatasi: {e}')

def translate_news(news_list, cache):
    """Haber baslik ve icerikleri Turkceye cevir (cache kullanarak)"""
    if not ANTHROPIC_KEY or not news_list:
        return news_list
    
    import urllib.request, json as _json
    new_translations = 0
    
    for n in news_list:
        # Haber ID veya URL'i cache anahtarı olarak kullan
        cache_key = n.get('url') or n.get('headline', '')[:100]
        if not cache_key:
            continue
        
        # Cache'de varsa kullan
        if cache_key in cache:
            n['headline_tr'] = cache[cache_key].get('headline_tr', '')
            n['summary_tr']  = cache[cache_key].get('summary_tr', '')
            continue
        
        # Cache'de yoksa cevir
        try:
            prompt = f"""Su finansal haberi Turkceye cevir. Sadece JSON dondur, baska sey yazma.

Baslik: {n.get('headline', '')}
Ozet: {n.get('summary', '')}

Format:
{{"headline_tr": "<turkce baslik>", "summary_tr": "<turkce ozet>"}}"""

            payload = {
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 500,
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
                text = result['content'][0]['text'].strip()
                # JSON parse
                if text.startswith('```'):
                    text = text.split('```')[1].replace('json', '').strip()
                translated = _json.loads(text)
                
                n['headline_tr'] = translated.get('headline_tr', '')
                n['summary_tr']  = translated.get('summary_tr', '')
                
                # Cache'e ekle
                cache[cache_key] = {
                    'headline_tr': n['headline_tr'],
                    'summary_tr':  n['summary_tr']
                }
                new_translations += 1
        except Exception as e:
            print(f"  Ceviri hatasi: {e}")
            n['headline_tr'] = ''
            n['summary_tr']  = ''
    
    print(f'  {new_translations} yeni ceviri yapildi (cache: {len(cache)})')
    return news_list


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


# ── CANSLIM SCREENER ──────────────────────────────────────────
# S&P 500 + NASDAQ teknoloji hisseleri listesi
TECH_UNIVERSE = [
    # Yarı iletkenler
    'NVDA','AMD','INTC','QCOM','AVGO','MU','AMAT','LRCX','KLAC','MRVL',
    'ARM','CRDO','ALAB','ON','WOLF','MPWR','ENTG','COHR','ONTO','TER',
    'TSM','ASML',
    # Yazılım / Bulut
    'MSFT','CRM','NOW','SNOW','DDOG','MDB','NET','HUBS','ZS','CRWD',
    'PANW','FTNT','OKTA','TEAM','WDAY','VEEV','ADBE','ORCL','SAP',
    'PLTR','PATH','AI','GTLB','CFLT','TOST',
    # Internet / AI
    'META','GOOGL','AMZN','NFLX','UBER','ABNB','SNAP','PINS','RDDT',
    # Donanım / Altyapı
    'ANET','CSCO','HPE','DELL','SMCI','GLW','CGNX','KEYS','TRMB',
    # Fintech / Diğer
    'PYPL','SQ','ADYEN','INTU','FIS','FISV',
    # Türkiye
    'AAPL','TSLA'
]

# Kriter tanımları: (id, label, threshold_str, weight, importance)
CANSLIM_CRITERIA = [
    ('eps_qoq',    'EPS QoQ Büyüme',    '>=20%',    3, 'critical'),
    ('sma200',     'SMA200 Üzerinde',   'P>SMA200', 3, 'critical'),
    ('market',     'M Kriteri',         'Güçlü',    3, 'critical'),
    ('rev_growth', 'Gelir Büyümesi',    '>=15%',    2, 'important'),
    ('roe',        'ROE',               '>=15%',    2, 'important'),
    ('gross_mg',   'Brüt Marjin',       '>=40%',    2, 'important'),
    ('sma50',      'SMA50 Üzerinde',    'P>SMA50',  2, 'important'),
    ('52w',        '52H Yakınlık',      '>=75%',    2, 'important'),
    ('net_mg',     'Net Marjin',        '>=10%',    1, 'support'),
    ('de',         'Borç/Özkaynak',     '<=1.0',    1, 'support'),
    ('cr',         'Current Ratio',     '>=1.5',    1, 'support'),
    ('pe',         'P/E',               '<=60',     1, 'support'),
    ('mktcap',     'Piyasa Değeri',     '>=1B',     1, 'support'),
    ('rel_vol',    'Göreceli Hacim',    '>=0.8x',   1, 'support'),
    ('avg_vol',    'Ort. Hacim',        '>=500K',   1, 'support'),
    ('inst_own',   'Kurumsal Sahip.',   '>=40%',    1, 'support'),
]
MAX_WEIGHTED_SCORE = sum(c[3] for c in CANSLIM_CRITERIA)

# Genisletilmis kriter listesi (RS Rating + EPS Hizlanmasi + Kurumsal Trend)
CANSLIM_CRITERIA_EXTENDED = CANSLIM_CRITERIA + [
    ('eps_accel',  'EPS Hizlanmasi',  'Hizlaniyor', 2, 'important'),
    ('rs_rating',  'RS Rating',       '>=70',       2, 'important'),
    ('inst_trend', 'Kurumsal Trend',  'Artiyor',    1, 'support'),
]
MAX_WEIGHTED_SCORE_EXT = sum(c[3] for c in CANSLIM_CRITERIA_EXTENDED)

def canslim_score(ticker, info, hist, market_ok=True, rs_rating=50, prev_inst=None):
    """16 CANSLIM kriteri + RS Rating + EPS Hizlanmasi + Kurumsal Trend"""
    cr_res = {}
    closes = hist['Close'].dropna() if not hist.empty else None
    if closes is None or len(closes) < 50:
        return None, None, {}
    price = float(closes.iloc[-1])

    def safe(key, d=None):
        try:
            v = info.get(key)
            return float(v) if v is not None else d
        except: return d

    def add(cid, val_str, passed, limit, has_data=True):
        cr_res[cid] = {'val': val_str, 'passed': passed, 'limit': limit, 'has_data': has_data}

    # 1. EPS QoQ [ZORUNLU] - Ceyreklik buyume + hizlanma kontrolu
    v = safe('earningsQuarterlyGrowth')
    if v is not None:
        pct = round(v*100, 1)
        add('eps_qoq', f'{pct:+.1f}%', pct >= 20, '>=20%')
    else:
        v2 = safe('earningsGrowth')
        if v2 is not None:
            pct = round(v2*100, 1)
            add('eps_qoq', f'{pct:+.1f}% (yil)', pct >= 20, '>=20%')
        else:
            add('eps_qoq', 'Veri yok', False, '>=20%', False)

    # 2. EPS Hizlanmasi [ONEMLI] - Son ceyrek oncekinden daha iyi mi?
    try:
        import yfinance as _yf
        tk_tmp = _yf.Ticker(ticker)
        earnings_hist = tk_tmp.quarterly_earnings
        if earnings_hist is not None and len(earnings_hist) >= 3:
            eps_vals = earnings_hist['Actual'].dropna().tail(4).tolist()
            if len(eps_vals) >= 3:
                # Son 3 ceyrek buyume oranlari
                growths = []
                for i in range(1, len(eps_vals)):
                    if eps_vals[i-1] > 0:
                        g = (eps_vals[i] - eps_vals[i-1]) / abs(eps_vals[i-1]) * 100
                        growths.append(g)
                if len(growths) >= 2:
                    accelerating = growths[-1] > growths[-2]
                    last_g = round(growths[-1], 1)
                    prev_g = round(growths[-2], 1)
                    add('eps_accel', f'{last_g:+.1f}% (prev:{prev_g:+.1f}%)', 
                        accelerating and growths[-1] > 0, 'Hizlaniyor')
                else:
                    add('eps_accel', 'Veri yetersiz', False, 'Hizlaniyor', False)
            else:
                add('eps_accel', 'Veri yetersiz', False, 'Hizlaniyor', False)
        else:
            add('eps_accel', 'Veri yok', False, 'Hizlaniyor', False)
    except:
        add('eps_accel', 'Veri yok', False, 'Hizlaniyor', False)

    # 3. Rev Growth [ONEMLI]
    v = safe('revenueGrowth')
    if v is not None:
        pct = round(v*100, 1)
        add('rev_growth', f'{pct:+.1f}%', pct >= 15, '>=15%')
    else:
        add('rev_growth', 'Veri yok', False, '>=15%', False)

    # 4. ROE [ONEMLI]
    v = safe('returnOnEquity')
    if v is not None:
        pct = round(v*100, 1)
        add('roe', f'{pct:.1f}%', pct >= 15, '>=15%')
    else:
        add('roe', 'Veri yok', False, '>=15%', False)

    # 5. Gross Margin [ONEMLI]
    v = safe('grossMargins')
    if v is not None:
        pct = round(v*100, 1)
        add('gross_mg', f'{pct:.1f}%', pct >= 40, '>=40%')
    else:
        add('gross_mg', 'Veri yok', False, '>=40%', False)

    # 6. Net Margin [DESTEK]
    v = safe('profitMargins')
    if v is not None:
        pct = round(v*100, 1)
        add('net_mg', f'{pct:.1f}%', pct >= 10, '>=10%')
    else:
        add('net_mg', 'Veri yok', False, '>=10%', False)

    # 7. D/E [DESTEK]
    v = safe('debtToEquity')
    if v is not None:
        val = round(v / 100, 2)
        add('de', str(val), val <= 1.0, '<=1.0')
    else:
        add('de', 'Veri yok', False, '<=1.0', False)

    # 8. Current Ratio [DESTEK]
    v = safe('currentRatio')
    if v is not None:
        add('cr', str(round(v, 2)), v >= 1.5, '>=1.5')
    else:
        add('cr', 'Veri yok', False, '>=1.5', False)

    # 9. P/E [DESTEK]
    v = safe('trailingPE')
    if v is not None and v > 0:
        add('pe', str(round(v, 1)), v <= 60, '<=60')
    else:
        v2 = safe('forwardPE')
        if v2 is not None and v2 > 0:
            add('pe', f'{round(v2,1)} (fwd)', v2 <= 60, '<=60')
        else:
            add('pe', 'Veri yok', False, '<=60', False)

    # 10. Market Cap [DESTEK]
    v = safe('marketCap')
    if v is not None:
        s = f'${v/1e9:.1f}B' if v >= 1e9 else f'${v/1e6:.0f}M'
        add('mktcap', s, v >= 1e9, '>=1B')
    else:
        add('mktcap', 'Veri yok', False, '>=1B', False)

    # 11. 52H Yakinlik [ONEMLI]
    h52 = safe('fiftyTwoWeekHigh')
    if h52 and price > 0:
        pct = round(price / h52 * 100, 1)
        add('52w', f'{pct:.1f}%', pct >= 75, '>=75%')
    else:
        add('52w', 'Veri yok', False, '>=75%', False)

    # 12. SMA50 [ONEMLI]
    if len(closes) >= 50:
        sma50 = float(closes.tail(50).mean())
        dist = round((price - sma50) / sma50 * 100, 1)
        add('sma50', f'${round(sma50,2)} ({dist:+.1f}%)', price > sma50, 'P>SMA50')
    else:
        add('sma50', 'Veri yetersiz', False, 'P>SMA50', False)

    # 13. SMA200 [ZORUNLU]
    if len(closes) >= 200:
        sma200 = float(closes.tail(200).mean())
        dist = round((price - sma200) / sma200 * 100, 1)
        add('sma200', f'${round(sma200,2)} ({dist:+.1f}%)', price > sma200, 'P>SMA200')
    else:
        add('sma200', 'Veri yetersiz', False, 'P>SMA200', False)

    # 14. Rel Vol [DESTEK] - 5g/20g ortalama karsilastirma
    if len(hist) >= 20:
        vols = hist['Volume'].dropna()
        avg20 = float(vols.tail(20).mean())
        avg5  = float(vols.tail(5).mean())
        rv = round(avg5 / avg20, 2) if avg20 > 0 else 0
        add('rel_vol', f'{rv}x', rv >= 0.8, '>=0.8x')
    else:
        add('rel_vol', 'Veri yetersiz', False, '>=0.8x', False)

    # 15. Avg Vol [DESTEK]
    v = safe('averageVolume')
    if v is not None:
        s = f'{int(v/1000)}K' if v < 1e6 else f'{v/1e6:.1f}M'
        add('avg_vol', s, v >= 500000, '>=500K')
    else:
        add('avg_vol', 'Veri yok', False, '>=500K', False)

    # 16. Kurumsal Sahiplik [DESTEK]
    # Birden fazla kaynaktan dene
    inst_pct = None
    for field in ['institutionsPercentHeld', 'institutionHoldingsPercent', 'institutionalOwnership']:
        v = safe(field)
        if v is not None:
            inst_pct = round(v * 100, 1) if v <= 1 else round(v, 1)
            break
    if inst_pct is not None:
        add('inst_own', f'{inst_pct:.1f}%', inst_pct >= 40, '>=40%')
    else:
        # Hesaplamayı atla, nötr say
        add('inst_own', 'Veri yok', True, '>=40%', False)

    # 17. Kurumsal Alim Trendi [DESTEK] - Artıyor mu?
    if prev_inst is not None and inst_pct is not None:
        trend_up = inst_pct > prev_inst
        diff = round(inst_pct - prev_inst, 1)
        add('inst_trend', f'{inst_pct:.1f}% ({diff:+.1f}%)', trend_up, 'Artiyor')
    else:
        add('inst_trend', 'Veri yok', True, 'Artiyor', False)

    # 18. RS Rating [ONEMLI] - Goreceli guc skoru (1-99)
    add('rs_rating', str(rs_rating), rs_rating >= 70, '>=70')

    # 19. M Kriteri [ZORUNLU]
    add('market', 'Guclu' if market_ok else 'Zayif', market_ok, 'Guclu')

    # Agirlikli skor (yeni kriterler dahil)
    all_criteria = CANSLIM_CRITERIA + [
        ('eps_accel',  'EPS Hizlanmasi',    'Hizlaniyor', 2, 'important'),
        ('inst_trend', 'Kurumsal Trend',     'Artiyor',    1, 'support'),
        ('rs_rating',  'RS Rating',          '>=70',       2, 'important'),
    ]
    weighted = sum(c[3] for c in all_criteria if cr_res.get(c[0], {}).get('passed'))
    raw      = sum(1     for c in all_criteria if cr_res.get(c[0], {}).get('passed'))
    return weighted, raw, cr_res


def run_canslim_screener(market_data, watchlist, portfolio):
    """CANSLIM screener - RS Rating + EPS Hizlanmasi + Kurumsal Trend"""
    import yfinance as yf2

    # M kriteri
    md = market_data or {}
    sp  = md.get('SP500', {})
    nas = md.get('NASDAQ', {})
    market_ok = sp.get('above200', False) and nas.get('above200', False)

    all_tickers = list(set(TECH_UNIVERSE + watchlist + portfolio))
    print(f'  {len(all_tickers)} hisse taranıyor...')

    # ADIM 1: Tum hisselerin 12 aylik performansini hesapla (RS Rating icin)
    perf_map = {}
    print('  RS Rating hesaplaniyor...')
    for ticker in all_tickers:
        try:
            tk = yf2.Ticker(ticker)
            hist = tk.history(period='1y', interval='1d')
            if hist.empty or len(hist) < 50:
                continue
            closes = hist['Close'].dropna()
            if len(closes) >= 200:
                p_now  = float(closes.iloc[-1])
                p_1y   = float(closes.iloc[0])
                p_3m   = float(closes.iloc[-63])  if len(closes) >= 63  else p_1y
                p_6m   = float(closes.iloc[-126]) if len(closes) >= 126 else p_1y
                # O'Neil formulü: son 3 ay 2x agirlikli
                ret_1y = (p_now - p_1y) / p_1y * 100
                ret_6m = (p_now - p_6m) / p_6m * 100
                ret_3m = (p_now - p_3m) / p_3m * 100
                # Agirlikli performans
                weighted_perf = ret_3m * 2 + ret_6m + ret_1y
                perf_map[ticker] = {
                    'hist': hist,
                    'perf': weighted_perf,
                    'ret_1y': round(ret_1y, 1)
                }
        except:
            continue

    # RS Rating: performansa gore siralayip 1-99 arasi puan ver
    sorted_perfs = sorted(perf_map.items(), key=lambda x: x[1]['perf'])
    rs_ratings = {}
    n = len(sorted_perfs)
    for rank, (ticker, _) in enumerate(sorted_perfs):
        rs_ratings[ticker] = max(1, min(99, round((rank / n) * 98 + 1)))

    print(f'  {len(rs_ratings)} hisse icin RS Rating hesaplandi')

    # ADIM 2: Her hisse icin tam CANSLIM analizi
    results = []
    for ticker in all_tickers:
        try:
            tk = yf2.Ticker(ticker)
            hist = perf_map.get(ticker, {}).get('hist')
            if hist is None:
                hist = tk.history(period='1y', interval='1d')
            if hist is None or hist.empty or len(hist) < 50:
                continue

            info = tk.info or {}
            rs   = rs_ratings.get(ticker, 50)

            weighted_score, raw_score, criteria_results = canslim_score(
                ticker, info, hist, market_ok,
                rs_rating=rs,
                prev_inst=None
            )
            if weighted_score is None:
                continue

            closes = hist['Close'].dropna()
            price  = round(float(closes.iloc[-1]), 2)
            prev   = round(float(closes.iloc[-2]), 2) if len(closes) > 1 else price
            change = round((price - prev) / prev * 100, 2)

            rt = get_realtime_price(ticker, FINNHUB_KEY)
            if rt and rt['price'] > 0:
                price  = rt['price']
                change = rt['change']

            sector = info.get('sector', 'Technology')
            name   = info.get('shortName', ticker)
            ret_1y = perf_map.get(ticker, {}).get('ret_1y', 0)

            results.append({
                'ticker':         ticker,
                'name':           name,
                'price':          price,
                'change':         change,
                'ret_1y':         ret_1y,
                'score':          raw_score,
                'weighted_score': weighted_score,
                'max_score':      19,  # 16 + 3 yeni kriter
                'max_weighted':   MAX_WEIGHTED_SCORE_EXT,
                'pct':            round(weighted_score / MAX_WEIGHTED_SCORE_EXT * 100),
                'rs_rating':      rs,
                'criteria':       criteria_results,
                'sector':         sector,
                'in_watchlist':   ticker in watchlist,
                'in_portfolio':   ticker in portfolio,
                'passed':         weighted_score >= round(MAX_WEIGHTED_SCORE_EXT * 0.70)
            })
        except Exception as e:
            continue

    results.sort(key=lambda x: x['weighted_score'], reverse=True)
    passed = [r for r in results if r['passed']]
    print(f'  {len(passed)} hisse CANSLIM gecti (%70+), toplam {len(results)} taranidi')
    return results



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

# ── PİYASA VERİSİ ────────────────────────────────────────────
print('\n📊 Piyasa verisi cekiliyor...')
market_data = get_market_data()
print(f'  M Kriteri: {market_data.get("M_LABEL","?")}')

# ── PİYASA YÖNÜ (FTD) ────────────────────────────────────────
print('\n📊 Piyasa yönü (FTD) analiz ediliyor...')
direction_data = get_market_direction()
for _n, _d in direction_data.items():
    print(f'  {_n}: {_d.get("status", _d.get("error", "?"))}')

# ── CANSLIM SCREENER ──────────────────────────────────────────
print('\n🔍 CANSLIM Screener çalışıyor...')
canslim_results = run_canslim_screener(market_data, WATCHLIST, PORTFOLIO)
print(f'  {len(weekly_data.get("portfolio",[]))} portföy + {len(weekly_data.get("watchlist",[]))} watchlist verisi alindi')

# ── HABER AKIŞI ───────────────────────────────────────────────
print('\n📰 Haberler cekiliyor...')
news_data = get_news(WATCHLIST, PORTFOLIO, FINNHUB_KEY)
print(f'  {len(news_data)} haber bulundu')

# Cache yukle, ceviri yap, cache kaydet
news_cache = load_news_cache()
news_data = translate_news(news_data, news_cache)
save_news_cache(news_cache)

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
    _T = "PCFET0NUWVBFIGh0bWw+CjxodG1sIGxhbmc9InRyIj4KPGhlYWQ+CjxtZXRhIGNoYXJzZXQ9IlVURi04Ii8+CjxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsaW5pdGlhbC1zY2FsZT0xIi8+Cjx0aXRsZT5DQU5TTElNIFNjYW5uZXI8L3RpdGxlPgo8bGluayByZWw9Imljb24iIHR5cGU9ImltYWdlL3N2Zyt4bWwiIGhyZWY9ImRhdGE6aW1hZ2Uvc3ZnK3htbCwlM0NzdmcgeG1sbnM9J2h0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnJyB2aWV3Qm94PScwIDAgMzIgMzInJTNFJTNDcmVjdCB3aWR0aD0nMzInIGhlaWdodD0nMzInIHJ4PSc2JyBmaWxsPSclMjMwZDExMTcnLyUzRSUzQ3BvbHlsaW5lIHBvaW50cz0nNCwyNCAxMCwxNiAxNiwyMCAyMiwxMCAyOCwxNCcgZmlsbD0nbm9uZScgc3Ryb2tlPSclMjMxMGI5ODEnIHN0cm9rZS13aWR0aD0nMi41JyBzdHJva2UtbGluZWNhcD0ncm91bmQnIHN0cm9rZS1saW5lam9pbj0ncm91bmQnLyUzRSUzQy9zdmclM0UiPgo8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PVNwYWNlK0dyb3Rlc2s6d2dodEA0MDA7NTAwOzYwMDs3MDAmZmFtaWx5PUJlYmFzK05ldWUmZmFtaWx5PUpldEJyYWlucytNb25vOndnaHRANDAwOzYwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCIvPgo8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9jaGFydC5qc0A0LjQuMC9kaXN0L2NoYXJ0LnVtZC5taW4uanMiPjwvc2NyaXB0Pgo8c3R5bGU+Cjpyb290ey0tYmc6IzA1MDcwZjstLWJnMjojMGQxMTE3Oy0tYmczOiMxNjFiMjQ7LS1ib3JkZXI6cmdiYSgyNTUsMjU1LDI1NSwwLjA4KTstLXRleHQ6I2UyZThmMDstLW11dGVkOiM0YjU1NjM7LS1ncmVlbjojMTBiOTgxOy0tZ3JlZW4yOiMzNGQzOTk7LS1yZWQ6I2VmNDQ0NDstLXJlZDI6I2Y4NzE3MTstLXllbGxvdzojZjU5ZTBiO30KKntib3gtc2l6aW5nOmJvcmRlci1ib3g7bWFyZ2luOjA7cGFkZGluZzowfQpib2R5e2JhY2tncm91bmQ6dmFyKC0tYmcpO2NvbG9yOnZhcigtLXRleHQpO2ZvbnQtZmFtaWx5OidTcGFjZSBHcm90ZXNrJyxzYW5zLXNlcmlmO21pbi1oZWlnaHQ6MTAwdmh9Ci5oZWFkZXJ7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCMwZDExMTcsIzExMTgyNyk7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtwYWRkaW5nOjE0cHggMjBweDtwb3NpdGlvbjpzdGlja3k7dG9wOjA7ei1pbmRleDoxMDB9Ci5oZWFkZXItaW5uZXJ7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTBweDttYXgtd2lkdGg6MTQwMHB4O21hcmdpbjowIGF1dG99Ci5sb2dvLW1haW57Zm9udC1mYW1pbHk6J0JlYmFzIE5ldWUnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjIycHg7bGV0dGVyLXNwYWNpbmc6NHB4O2JhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZywjMTBiOTgxLCMzYjgyZjYpOy13ZWJraXQtYmFja2dyb3VuZC1jbGlwOnRleHQ7LXdlYmtpdC10ZXh0LWZpbGwtY29sb3I6dHJhbnNwYXJlbnR9Ci50aW1lc3RhbXB7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLmxpdmUtZG90e3dpZHRoOjdweDtoZWlnaHQ6N3B4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6dmFyKC0tZ3JlZW4pO2FuaW1hdGlvbjpwdWxzZSAycyBpbmZpbml0ZTtkaXNwbGF5OmlubGluZS1ibG9jazttYXJnaW4tcmlnaHQ6NXB4fQpAa2V5ZnJhbWVzIHB1bHNlezAlLDEwMCV7b3BhY2l0eToxO2JveC1zaGFkb3c6MCAwIDAgMCByZ2JhKDE2LDE4NSwxMjksLjQpfTUwJXtvcGFjaXR5Oi43O2JveC1zaGFkb3c6MCAwIDAgNnB4IHJnYmEoMTYsMTg1LDEyOSwwKX19Ci5uYXZ7ZGlzcGxheTpmbGV4O2dhcDo0cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7b3ZlcmZsb3cteDphdXRvO2ZsZXgtd3JhcDp3cmFwfQoudGFie3BhZGRpbmc6NnB4IDE0cHg7Ym9yZGVyLXJhZGl1czo2cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NTAwO2JvcmRlcjoxcHggc29saWQgdHJhbnNwYXJlbnQ7YmFja2dyb3VuZDpub25lO2NvbG9yOnZhcigtLW11dGVkKTt0cmFuc2l0aW9uOmFsbCAuMnM7d2hpdGUtc3BhY2U6bm93cmFwfQoudGFiOmhvdmVye2NvbG9yOnZhcigtLXRleHQpO2JhY2tncm91bmQ6dmFyKC0tYmczKX0KLnRhYi5hY3RpdmV7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLXRleHQpO2JvcmRlci1jb2xvcjp2YXIoLS1ib3JkZXIpfQoudGFiLnBvcnQuYWN0aXZle2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyLWNvbG9yOnJnYmEoMTYsMTg1LDEyOSwuMyl9Ci50Zi1yb3d7ZGlzcGxheTpmbGV4O2dhcDo2cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7YWxpZ24taXRlbXM6Y2VudGVyO2ZsZXgtd3JhcDp3cmFwfQoudGYtYnRue3BhZGRpbmc6NXB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Y3Vyc29yOnBvaW50ZXI7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO3RyYW5zaXRpb246YWxsIC4yc30KLnRmLWJ0bi5hY3RpdmV7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtjb2xvcjojNjBhNWZhO2JvcmRlci1jb2xvcjpyZ2JhKDU5LDEzMCwyNDYsLjQpfQoudGYtYnRuLnN0YXJ7cG9zaXRpb246cmVsYXRpdmV9Ci50Zi1idG4uc3Rhcjo6YWZ0ZXJ7Y29udGVudDon4piFJztwb3NpdGlvbjphYnNvbHV0ZTt0b3A6LTVweDtyaWdodDotNHB4O2ZvbnQtc2l6ZTo4cHg7Y29sb3I6dmFyKC0teWVsbG93KX0KLnRmLWhpbnR7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpfQouc3RhdHN7ZGlzcGxheTpmbGV4O2dhcDo4cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7ZmxleC13cmFwOndyYXB9Ci5waWxse2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjVweDtwYWRkaW5nOjRweCAxMHB4O2JvcmRlci1yYWRpdXM6MjBweDtmb250LXNpemU6MTFweDtmb250LXdlaWdodDo2MDA7Ym9yZGVyOjFweCBzb2xpZH0KLnBpbGwuZ3tiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMSk7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlci1jb2xvcjpyZ2JhKDE2LDE4NSwxMjksLjI1KX0KLnBpbGwucntiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xKTtjb2xvcjp2YXIoLS1yZWQyKTtib3JkZXItY29sb3I6cmdiYSgyMzksNjgsNjgsLjI1KX0KLnBpbGwueXtiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMSk7Y29sb3I6dmFyKC0teWVsbG93KTtib3JkZXItY29sb3I6cmdiYSgyNDUsMTU4LDExLC4yNSl9Ci5waWxsLmJ7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjEpO2NvbG9yOiM2MGE1ZmE7Ym9yZGVyLWNvbG9yOnJnYmEoNTksMTMwLDI0NiwuMjUpfQoucGlsbC5te2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Ym9yZGVyLWNvbG9yOnZhcigtLWJvcmRlcil9Ci5kb3R7d2lkdGg6NXB4O2hlaWdodDo1cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpjdXJyZW50Q29sb3J9Ci5tYWlue3BhZGRpbmc6MTRweCAyMHB4O21heC13aWR0aDoxNDAwcHg7bWFyZ2luOjAgYXV0b30KLmdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgzMDBweCwxZnIpKTtnYXA6MTBweH0KQG1lZGlhKG1heC13aWR0aDo0ODBweCl7LmdyaWR7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmcn19Ci5jYXJke2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O292ZXJmbG93OmhpZGRlbjtjdXJzb3I6cG9pbnRlcjt0cmFuc2l0aW9uOmFsbCAuMnN9Ci5jYXJkOmhvdmVye3RyYW5zZm9ybTp0cmFuc2xhdGVZKC0ycHgpO2JveC1zaGFkb3c6MCA4cHggMjRweCByZ2JhKDAsMCwwLC40KX0KLmFjY2VudHtoZWlnaHQ6M3B4fQouY2JvZHl7cGFkZGluZzoxMnB4IDE0cHh9Ci5jdG9we2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpmbGV4LXN0YXJ0O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206OHB4fQoudGlja2Vye2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyMHB4O2xldHRlci1zcGFjaW5nOjJweDtsaW5lLWhlaWdodDoxfQouY3Bye3RleHQtYWxpZ246cmlnaHR9Ci5wdmFse2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTVweDtmb250LXdlaWdodDo2MDB9Ci5wY2hne2ZvbnQtc2l6ZToxMXB4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTttYXJnaW4tdG9wOjJweH0KLmJhZGdle2Rpc3BsYXk6aW5saW5lLWJsb2NrO3BhZGRpbmc6MnB4IDhweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6LjVweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLXRvcDozcHh9Ci5wb3J0LWJhZGdle2Rpc3BsYXk6aW5saW5lLWZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDozcHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwO2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xMik7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yNSk7bWFyZ2luLWxlZnQ6NXB4fQouc2lnc3tkaXNwbGF5OmZsZXg7ZmxleC13cmFwOndyYXA7Z2FwOjNweDttYXJnaW4tYm90dG9tOjhweH0KLnNwe2ZvbnQtc2l6ZTo5cHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLnNne2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbjIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKX0KLnNie2JhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjEpO2NvbG9yOnZhcigtLXJlZDIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpfQouc257YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLW11dGVkKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5jaGFydC13e2hlaWdodDo3NXB4O21hcmdpbi10b3A6OHB4fQoubHZsc3tkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgzLDFmcik7Z2FwOjVweDttYXJnaW4tdG9wOjhweH0KLmx2e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjVweDtwYWRkaW5nOjZweDt0ZXh0LWFsaWduOmNlbnRlcjtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5sbHtmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MnB4fQoubHZhbHtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwfQoub3ZlcmxheXtwb3NpdGlvbjpmaXhlZDtpbnNldDowO2JhY2tncm91bmQ6cmdiYSgwLDAsMCwuODgpO3otaW5kZXg6MTAwMDtkaXNwbGF5Om5vbmU7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7cGFkZGluZzoxNnB4fQoub3ZlcmxheS5vcGVue2Rpc3BsYXk6ZmxleH0KLm1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjUyMHB4O21heC1oZWlnaHQ6OTJ2aDtvdmVyZmxvdy15OmF1dG99Ci5taGVhZHtwYWRkaW5nOjE4cHggMThweCAwO2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpmbGV4LXN0YXJ0fQoubXRpdGxle2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZTozMHB4O2xldHRlci1zcGFjaW5nOjNweH0KLm1jbG9zZXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTt3aWR0aDozMHB4O2hlaWdodDozMHB4O2JvcmRlci1yYWRpdXM6N3B4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxNXB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcn0KLm1ib2R5e3BhZGRpbmc6MTRweCAxOHB4IDE4cHh9Ci5tY2hhcnR3e2hlaWdodDoxNTBweDttYXJnaW4tYm90dG9tOjE0cHh9Ci5kZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjdweDttYXJnaW4tYm90dG9tOjEycHh9Ci5kY3tiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo3cHg7cGFkZGluZzo5cHggMTFweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5kbHtmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206M3B4fQouZHZ7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMH0KLmRib3h7Ym9yZGVyLXJhZGl1czo5cHg7cGFkZGluZzoxM3B4O21hcmdpbi1ib3R0b206MTJweDtib3JkZXI6MXB4IHNvbGlkfQouZGxibHtmb250LXNpemU6OXB4O2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo1cHh9Ci5kdmVyZHtmb250LWZhbWlseTonQmViYXMgTmV1ZScsc2Fucy1zZXJpZjtmb250LXNpemU6MjZweDtsZXR0ZXItc3BhY2luZzoycHg7bWFyZ2luLWJvdHRvbTo4cHh9Ci5kcm93e2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjRweDtmb250LXNpemU6MTJweH0KLmRrZXl7Y29sb3I6dmFyKC0tbXV0ZWQpfQoucnJiYXJ7aGVpZ2h0OjRweDtiYWNrZ3JvdW5kOnZhcigtLWJnKTtib3JkZXItcmFkaXVzOjJweDttYXJnaW4tdG9wOjdweDtvdmVyZmxvdzpoaWRkZW59Ci5ycmZpbGx7aGVpZ2h0OjEwMCU7Ym9yZGVyLXJhZGl1czoycHg7dHJhbnNpdGlvbjp3aWR0aCAuOHMgZWFzZX0KLnZwYm94e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjdweDtwYWRkaW5nOjEwcHg7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO21hcmdpbi1ib3R0b206MTJweH0KLnZwdGl0bGV7Zm9udC1zaXplOjlweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo3cHh9Ci52cGdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoMywxZnIpO2dhcDo1cHh9Ci52cGN7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlci1yYWRpdXM6NXB4O3BhZGRpbmc6N3B4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlcjoxcHggc29saWR9Ci5taW5mb3tkaXNwbGF5OmlubGluZS1mbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO3dpZHRoOjE0cHg7aGVpZ2h0OjE0cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpyZ2JhKDk2LDE2NSwyNTAsLjIpO2NvbG9yOiM2MGE1ZmE7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7Y3Vyc29yOnBvaW50ZXI7bWFyZ2luLWxlZnQ6NHB4O2JvcmRlcjoxcHggc29saWQgcmdiYSg5NiwxNjUsMjUwLC4zKX0KLm1pbmZvLXBvcHVwe3Bvc2l0aW9uOmZpeGVkO2luc2V0OjA7YmFja2dyb3VuZDpyZ2JhKDAsMCwwLC44OCk7ei1pbmRleDoyMDAwO2Rpc3BsYXk6bm9uZTthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjtwYWRkaW5nOjE2cHh9Ci5taW5mby1wb3B1cC5vcGVue2Rpc3BsYXk6ZmxleH0KLm1pbmZvLW1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjQ4MHB4O21heC1oZWlnaHQ6ODV2aDtvdmVyZmxvdy15OmF1dG87cGFkZGluZzoyMHB4O3Bvc2l0aW9uOnJlbGF0aXZlfQoubWluZm8tdGl0bGV7Zm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4fQoubWluZm8tc291cmNle2ZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjEycHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4O2ZsZXgtd3JhcDp3cmFwfQoubWluZm8tcmVse3BhZGRpbmc6MnB4IDdweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMH0KLm1pbmZvLXJlbC5oaWdoe2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Y29sb3I6IzEwYjk4MX0KLm1pbmZvLXJlbC5tZWRpdW17YmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjE1KTtjb2xvcjojZjU5ZTBifQoubWluZm8tcmVsLmxvd3tiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Y29sb3I6I2VmNDQ0NH0KLm1pbmZvLWRlc2N7Zm9udC1zaXplOjEycHg7Y29sb3I6Izk0YTNiODtsaW5lLWhlaWdodDoxLjY7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8td2FybmluZ3tiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjZweDtwYWRkaW5nOjhweCAxMHB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOiNmNTllMGI7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8tcmFuZ2Vze21hcmdpbi1ib3R0b206MTRweH0KLm1pbmZvLXJhbmdlLXRpdGxle2ZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHh9Ci5taW5mby1yYW5nZXtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo4cHg7bWFyZ2luLWJvdHRvbTo2cHg7cGFkZGluZzo2cHggOHB4O2JvcmRlci1yYWRpdXM6NnB4O2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMDIpfQoubWluZm8tcmFuZ2UtZG90e3dpZHRoOjhweDtoZWlnaHQ6OHB4O2JvcmRlci1yYWRpdXM6NTAlO2ZsZXgtc2hyaW5rOjB9Ci5taW5mby1jYW5zbGlte2JhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6NnB4O3BhZGRpbmc6OHB4IDEwcHg7Zm9udC1zaXplOjExcHg7Y29sb3I6IzYwYTVmYX0KLm1pbmZvLWNsb3Nle3Bvc2l0aW9uOmFic29sdXRlO3RvcDoxNnB4O3JpZ2h0OjE2cHg7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4xKTtjb2xvcjojOTRhM2I4O3dpZHRoOjI4cHg7aGVpZ2h0OjI4cHg7Ym9yZGVyLXJhZGl1czo3cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjE0cHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyfQo6Oi13ZWJraXQtc2Nyb2xsYmFye3dpZHRoOjRweDtoZWlnaHQ6NHB4fQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRyYWNre2JhY2tncm91bmQ6dmFyKC0tYmcpfQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRodW1ie2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMSk7Ym9yZGVyLXJhZGl1czoycHh9Cjwvc3R5bGU+CjwvaGVhZD4KPGJvZHk+CjxkaXYgY2xhc3M9ImhlYWRlciI+CiAgPGRpdiBjbGFzcz0iaGVhZGVyLWlubmVyIj4KICAgIDxzcGFuIGNsYXNzPSJsb2dvLW1haW4iPkNBTlNMSU0gU0NBTk5FUjwvc3Bhbj4KICAgIDxzcGFuIGNsYXNzPSJ0aW1lc3RhbXAiPjxzcGFuIGNsYXNzPSJsaXZlLWRvdCI+PC9zcGFuPiUlVElNRVNUQU1QJSU8L3NwYW4+CiAgICA8YnV0dG9uIG9uY2xpY2s9Im9wZW5FZGl0TGlzdCgpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMyk7Y29sb3I6IzYwYTVmYTtwYWRkaW5nOjVweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMXB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtZmFtaWx5OmluaGVyaXQiPuKcj++4jyBMaXN0ZXlpIETDvHplbmxlPC9idXR0b24+CiAgPC9kaXY+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJuYXYiPgogIDxidXR0b24gY2xhc3M9InRhYiBhY3RpdmUiIG9uY2xpY2s9InNldFRhYignZGFzaGJvYXJkJyx0aGlzKSI+8J+PoCBEYXNoYm9hcmQ8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignYWxsJyx0aGlzKSI+8J+TiiBIaXNzZWxlcjwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiBwb3J0IiBvbmNsaWNrPSJzZXRUYWIoJ3BvcnQnLHRoaXMpIj7wn5K8IFBvcnRmw7Z5w7xtPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2J1eScsdGhpcykiPvCfk4ggQWw8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignc2VsbCcsdGhpcykiPvCfk4kgU2F0PC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2Vhcm5pbmdzJyx0aGlzKSI+8J+ThSBFYXJuaW5nczwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdydXRpbicsdGhpcykiPuKchSBSdXRpbjwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdoYWZ0YWxpaycsdGhpcykiPvCfk4ggSGFmdGFsxLFrPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ3NjcmVlbmVyJyx0aGlzKSI+8J+UjSBTY3JlZW5lcjwvYnV0dG9uPgogICAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ3ZhbHVhdGlvbicsdGhpcykiPvCfko4gRGXEn2VybGVtZTwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdkaXJlY3Rpb24nLHRoaXMpIj7wn5OKIFBpeWFzYSBZw7Zuw7w8L2J1dHRvbj4KPC9kaXY+CjxkaXYgY2xhc3M9InRmLXJvdyIgaWQ9InRmUm93IiBzdHlsZT0iZGlzcGxheTpub25lIj4KICA8YnV0dG9uIGNsYXNzPSJ0Zi1idG4gYWN0aXZlIiBkYXRhLXRmPSIxZCIgb25jbGljaz0ic2V0VGYoJzFkJyx0aGlzKSI+MUc8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0Zi1idG4gc3RhciIgZGF0YS10Zj0iMXdrIiBvbmNsaWNrPSJzZXRUZignMXdrJyx0aGlzKSI+MUg8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0Zi1idG4iIGRhdGEtdGY9IjFtbyIgb25jbGljaz0ic2V0VGYoJzFtbycsdGhpcykiPjFBPC9idXR0b24+CiAgPHNwYW4gY2xhc3M9InRmLWhpbnQiPkNBTlNMSU0gw7ZuZXJpbGVuOiAxRyArIDFIPC9zcGFuPgo8L2Rpdj4KPGRpdiBjbGFzcz0ic3RhdHMiIGlkPSJzdGF0cyI+PC9kaXY+CjxkaXYgY2xhc3M9Im1haW4iPjxkaXYgY2xhc3M9ImdyaWQiIGlkPSJncmlkIj48L2Rpdj48L2Rpdj4KPGRpdiBjbGFzcz0ib3ZlcmxheSIgaWQ9Im92ZXJsYXkiIG9uY2xpY2s9ImNsb3NlTShldmVudCkiPgogIDxkaXYgY2xhc3M9Im1vZGFsIiBpZD0ibW9kYWwiPjwvZGl2Pgo8L2Rpdj4KCjxkaXYgY2xhc3M9Im1pbmZvLXBvcHVwIiBpZD0iZWRpdFBvcHVwIiBvbmNsaWNrPSJjbG9zZUVkaXRQb3B1cChldmVudCkiPgogIDxkaXYgY2xhc3M9Im1pbmZvLW1vZGFsIiBzdHlsZT0icG9zaXRpb246cmVsYXRpdmU7bWF4LXdpZHRoOjU2MHB4IiBpZD0iZWRpdE1vZGFsIj4KICAgIDxidXR0b24gY2xhc3M9Im1pbmZvLWNsb3NlIiBvbmNsaWNrPSJjbG9zZUVkaXRQb3B1cCgpIj7inJU8L2J1dHRvbj4KICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KTttYXJnaW4tYm90dG9tOjRweCI+4pyP77iPIExpc3RleWkgRMO8emVubGU8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjE2cHgiPkdpdEh1YiBBUEkga2V5IGdlcmVrbGkg4oCUIGRlxJ9pxZ9pa2xpa2xlciBhbsSxbmRhIGtheWRlZGlsaXI8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyIDFmcjtnYXA6MTZweDttYXJnaW4tYm90dG9tOjE2cHgiPgogICAgICA8ZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij7wn5OLIFdhdGNobGlzdDwvZGl2PgogICAgICAgIDxkaXYgaWQ9IndhdGNobGlzdEVkaXRvciI+PC9kaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo2cHg7bWFyZ2luLXRvcDo4cHgiPgogICAgICAgICAgPGlucHV0IGlkPSJuZXdXYXRjaFRpY2tlciIgcGxhY2Vob2xkZXI9Ikhpc3NlIGVrbGUgKFRTTEEpIiBzdHlsZT0iZmxleDoxO2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tdGV4dCk7cGFkZGluZzo2cHggMTBweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtmb250LWZhbWlseTppbmhlcml0O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZSIvPgogICAgICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJhZGRUaWNrZXIoJ3dhdGNoJykiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzo2cHggMTJweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtjdXJzb3I6cG9pbnRlciI+KyBFa2xlPC9idXR0b24+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgogICAgICA8ZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij7wn5K8IFBvcnRmw7Z5PC9kaXY+CiAgICAgICAgPGRpdiBpZD0icG9ydGZvbGlvRWRpdG9yIj48L2Rpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjZweDttYXJnaW4tdG9wOjhweCI+CiAgICAgICAgICA8aW5wdXQgaWQ9Im5ld1BvcnRUaWNrZXIiIHBsYWNlaG9sZGVyPSJIaXNzZSBla2xlIChBQVBMKSIgc3R5bGU9ImZsZXg6MTtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLXRleHQpO3BhZGRpbmc6NnB4IDEwcHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Zm9udC1mYW1pbHk6aW5oZXJpdDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2UiLz4KICAgICAgICAgIDxidXR0b24gb25jbGljaz0iYWRkVGlja2VyKCdwb3J0JykiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzo2cHggMTJweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtjdXJzb3I6cG9pbnRlciI+KyBFa2xlPC9idXR0b24+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgogICAgPC9kaXY+CiAgICA8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTJweDttYXJnaW4tYm90dG9tOjE0cHg7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tZ3JlZW4pIj7inIUgRGXEn2nFn2lrbGlrbGVyIGtheWRlZGlsaW5jZSBiaXIgc29ucmFraSBDb2xhYiDDp2FsxLHFn3TEsXJtYXPEsW5kYSBha3RpZiBvbHVyLjwvZGl2Pgo8ZGl2IHN0eWxlPSJtYXJnaW4tYm90dG9tOjEycHgiPgogICAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo1cHgiPkdpdEh1YiBUb2tlbiAoYmlyIGtleiBnaXIsIHRhcmF5aWNpIGhhdGlybGF5YWNhayk8L2Rpdj4KICAgICAgPGlucHV0IGlkPSJnaFRva2VuSW5wdXQiIHBsYWNlaG9sZGVyPSJnaHBfLi4uIiBzdHlsZT0id2lkdGg6MTAwJTtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLXRleHQpO3BhZGRpbmc6OHB4IDEwcHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIi8+CiAgICA8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6OHB4Ij4KICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJzYXZlTGlzdFRvR2l0aHViKCkiIHN0eWxlPSJmbGV4OjE7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6MTBweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y3Vyc29yOnBvaW50ZXIiPvCfkr4gR2l0SHViYSBLYXlkZXQ8L2J1dHRvbj4KICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJjbG9zZUVkaXRQb3B1cCgpIiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS1tdXRlZCk7cGFkZGluZzoxMHB4IDE2cHg7Ym9yZGVyLXJhZGl1czo4cHg7Zm9udC1zaXplOjEzcHg7Y3Vyc29yOnBvaW50ZXIiPsSwcHRhbDwvYnV0dG9uPgogICAgPC9kaXY+CiAgICA8ZGl2IGlkPSJlZGl0U3RhdHVzIiBzdHlsZT0ibWFyZ2luLXRvcDoxMHB4O2ZvbnQtc2l6ZToxMnB4O3RleHQtYWxpZ246Y2VudGVyIj48L2Rpdj4KICA8L2Rpdj4KPC9kaXY+Cgo8ZGl2IGNsYXNzPSJtaW5mby1wb3B1cCIgaWQ9Im1pbmZvUG9wdXAiIG9uY2xpY2s9ImNsb3NlSW5mb1BvcHVwKGV2ZW50KSI+CiAgPGRpdiBjbGFzcz0ibWluZm8tbW9kYWwiIGlkPSJtaW5mb01vZGFsIj4KICAgIDxidXR0b24gY2xhc3M9Im1pbmZvLWNsb3NlIiBvbmNsaWNrPSJjbG9zZUluZm9Qb3B1cCgpIj7inJU8L2J1dHRvbj4KICAgIDxkaXYgaWQ9Im1pbmZvQ29udGVudCI+PC9kaXY+CiAgPC9kaXY+CjwvZGl2PgoKCjxzY3JpcHQ+CnZhciBNRVRSSUNTID0gewogIC8vIFRFS07EsEsKICAnUlNJJzogewogICAgdGl0bGU6ICdSU0kgKEfDtnJlY2VsaSBHw7zDpyBFbmRla3NpKScsCiAgICBkZXNjOiAnSGlzc2VuaW4gYcWfxLFyxLEgYWzEsW0gdmV5YSBhxZ/EsXLEsSBzYXTEsW0gYsO2bGdlc2luZGUgb2x1cCBvbG1hZMSxxJ/EsW7EsSBnw7ZzdGVyaXIuIDE0IGfDvG5sw7xrIGZpeWF0IGhhcmVrZXRsZXJpbmkgYW5hbGl6IGVkZXIuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J0HFn8SxcsSxIFNhdMSxbScsbWluOjAsbWF4OjMwLGNvbG9yOidncmVlbicsZGVzYzonRsSxcnNhdCBiw7ZsZ2VzaSDigJQgZml5YXQgw6dvayBkw7zFn23DvMWfJ30sCiAgICAgIHtsYWJlbDonTm9ybWFsJyxtaW46MzAsbWF4OjcwLGNvbG9yOid5ZWxsb3cnLGRlc2M6J07DtnRyIGLDtmxnZSd9LAogICAgICB7bGFiZWw6J0HFn8SxcsSxIEFsxLFtJyxtaW46NzAsbWF4OjEwMCxjb2xvcjoncmVkJyxkZXNjOidEaWtrYXQg4oCUIGZpeWF0IMOnb2sgecO8a3NlbG1pxZ8nfQogICAgXSwKICAgIGNhbnNsaW06ICdOIGtyaXRlcmkgaWxlIGlsZ2lsaSDigJQgZml5YXQgbW9tZW50dW11JwogIH0sCiAgJ1NNQTUwJzogewogICAgdGl0bGU6ICdTTUEgNTAgKDUwIEfDvG5sw7xrIEhhcmVrZXRsaSBPcnRhbGFtYSknLAogICAgZGVzYzogJ1NvbiA1MCBnw7xuw7xuIG9ydGFsYW1hIGthcGFuxLHFnyBmaXlhdMSxLiBLxLFzYS1vcnRhIHZhZGVsaSB0cmVuZCBnw7ZzdGVyZ2VzaS4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonw5x6ZXJpbmRlJyxjb2xvcjonZ3JlZW4nLGRlc2M6J0vEsXNhIHZhZGVsaSB0cmVuZCBwb3ppdGlmIOKAlCBnw7zDp2zDvCBzaW55YWwnfSwKICAgICAge2xhYmVsOidBbHTEsW5kYScsY29sb3I6J3JlZCcsZGVzYzonS8Sxc2EgdmFkZWxpIHRyZW5kIG5lZ2F0aWYnfQogICAgXSwKICAgIGNhbnNsaW06ICdNIGtyaXRlcmkg4oCUIHBpeWFzYSB0cmVuZGknCiAgfSwKICAnU01BMjAwJzogewogICAgdGl0bGU6ICdTTUEgMjAwICgyMDAgR8O8bmzDvGsgSGFyZWtldGxpIE9ydGFsYW1hKScsCiAgICBkZXNjOiAnU29uIDIwMCBnw7xuw7xuIG9ydGFsYW1hIGthcGFuxLHFnyBmaXlhdMSxLiBVenVuIHZhZGVsaSB0cmVuZCBnw7ZzdGVyZ2VzaS4gRW4gw7ZuZW1saSB0ZWtuaWsgc2V2aXllLicsCiAgICBzb3VyY2U6ICdUZWtuaWsgQW5hbGl6JywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOifDnHplcmluZGUnLGNvbG9yOidncmVlbicsZGVzYzonVXp1biB2YWRlbGkgYm/En2EgdHJlbmRpbmRlIOKAlCBDQU5TTElNIGnDp2luIMWfYXJ0J30sCiAgICAgIHtsYWJlbDonQWx0xLFuZGEnLGNvbG9yOidyZWQnLGRlc2M6J1V6dW4gdmFkZWxpIGF5xLEgdHJlbmRpbmRlIOKAlCBDQU5TTElNIGnDp2luIGdpcm1lJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTSBrcml0ZXJpIOKAlCB6b3J1bmx1IGtvxZ91bCcKICB9LAogICc1MlcnOiB7CiAgICB0aXRsZTogJzUyIEhhZnRhbMSxayBQb3ppc3lvbicsCiAgICBkZXNjOiAnSGlzc2VuaW4gc29uIDEgecSxbGRha2kgZml5YXQgYXJhbMSxxJ/EsW5kYSBuZXJlZGUgb2xkdcSfdW51IGfDtnN0ZXJpci4gMD15xLFsxLFuIGRpYmksIDEwMD15xLFsxLFuIHppcnZlc2kuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzAtMzAlJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1nEsWzEsW4gZGliaW5lIHlha8SxbiDigJQgcG90YW5zaXllbCBmxLFyc2F0J30sCiAgICAgIHtsYWJlbDonMzAtNzAlJyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIGLDtmxnZSDigJQgbsO2dHInfSwKICAgICAge2xhYmVsOic3MC04NSUnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1ppcnZleWUgeWFrbGHFn8SxeW9yIOKAlCBpemxlJ30sCiAgICAgIHtsYWJlbDonODUtMTAwJScsY29sb3I6J3JlZCcsZGVzYzonWmlydmV5ZSDDp29rIHlha8SxbiDigJQgZGlra2F0bGkgZ2lyJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTiBrcml0ZXJpIOKAlCB5ZW5pIHppcnZlIGvEsXLEsWzEsW3EsSBpw6dpbiBpZGVhbCBiw7ZsZ2UgJTg1LTEwMCcKICB9LAogICdIYWNpbSc6IHsKICAgIHRpdGxlOiAnSGFjaW0gKMSwxZ9sZW0gTWlrdGFyxLEpJywKICAgIGRlc2M6ICdHw7xubMO8ayBpxZ9sZW0gaGFjbWluaW4gc29uIDIwIGfDvG5sw7xrIG9ydGFsYW1heWEgb3JhbsSxLiBHw7zDp2zDvCBoYXJla2V0bGVyaW4gaGFjaW1sZSBkZXN0ZWtsZW5tZXNpIGdlcmVraXIuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J1nDvGtzZWsgKD4xLjN4KScsY29sb3I6J2dyZWVuJyxkZXNjOidLdXJ1bXNhbCBpbGdpIHZhciDigJQgZ8O8w6dsw7wgc2lueWFsJ30sCiAgICAgIHtsYWJlbDonTm9ybWFsICgwLjctMS4zeCknLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGFsYW1hIGlsZ2knfSwKICAgICAge2xhYmVsOidEw7zFn8O8ayAoPDAuN3gpJyxjb2xvcjoncmVkJyxkZXNjOifEsGxnaSBhemFsbcSxxZ8g4oCUIGRpa2thdCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ1Mga3JpdGVyaSDigJQgYXJ6L3RhbGVwIGRlbmdlc2knCiAgfSwKICAvLyBURU1FTAogICdGb3J3YXJkUEUnOiB7CiAgICB0aXRsZTogJ0ZvcndhcmQgUC9FICjEsGxlcml5ZSBEw7Zuw7xrIEZpeWF0L0themFuw6cpJywKICAgIGRlc2M6ICdTaXJrZXRpbiBvbnVtw7x6ZGVraSAxMiBheWRha2kgdGFobWluaSBrYXphbmNpbmEgZ29yZSBmaXlhdGkuIFRyYWlsaW5nIFAvRSBhcmFjaW5hIGdvcmUgZ2VsZWNlZ2Ugb2Rha2xpZGlnaSBpY2luIGRhaGEgb25lbWxpZGlyLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEFuYWxpc3QgdGFobWluaScsCiAgICByZWxpYWJpbGl0eTogJ21lZGl1bScsCiAgICB3YXJuaW5nOiAnQW5hbGlzdCB0YWhtaW5sZXJpbmUgZGF5YW7EsXIsIHlhbsSxbHTEsWPEsSBvbGFiaWxpcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic8MTUnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgYsO8ecO8bWUgYmVrbGVudGlzaSBkw7zFn8O8ayB2ZXlhIGhpc3NlIGRlxJ9lciBhbHTEsW5kYSd9LAogICAgICB7bGFiZWw6JzE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J01ha3VsIOKAlCDDp2/En3Ugc2VrdMO2ciBpw6dpbiBub3JtYWwnfSwKICAgICAge2xhYmVsOicyNS00MCcsY29sb3I6J3llbGxvdycsZGVzYzonUGFoYWzEsSBhbWEgYsO8ecO8bWUgcHJpbWkgw7ZkZW5peW9yJ30sCiAgICAgIHtsYWJlbDonPjQwJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHBhaGFsxLEg4oCUIHnDvGtzZWsgYsO8ecO8bWUgYmVrbGVudGlzaSBmaXlhdGxhbm3EscWfJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQyB2ZSBBIGtyaXRlcmxlcmkgaWxlIGlsZ2lsaScKICB9LAogICdQRUcnOiB7CiAgICB0aXRsZTogJ1BFRyBPcmFuxLEgKEZpeWF0L0themFuw6cvQsO8ecO8bWUpJywKICAgIGRlc2M6ICdQL0Ugb3JhbsSxbsSxIGLDvHnDvG1lIGjEsXrEsXlsYSBrYXLFn8SxbGHFn3TEsXLEsXIuIELDvHnDvHllbiDFn2lya2V0bGVyIGljaW4gUC9FXCdkZW4gZGFoYSBkb8SfcnUgZGXEn2VybGVtZSDDtmzDp8O8dMO8LiBQRUc9MSBhZGlsIGRlxJ9lciBrYWJ1bCBlZGlsaXIuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgQW5hbGlzdCB0YWhtaW5pJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdBbmFsaXN0IGLDvHnDvG1lIHRhaG1pbmxlcmluZSBkYXlhbsSxcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic8MS4wJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1VjdXog4oCUIGLDvHnDvG1lc2luZSBnw7ZyZSBkZcSfZXIgYWx0xLFuZGEnfSwKICAgICAge2xhYmVsOicxLjAtMS41Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J01ha3VsIOKAlCBhZGlsIGZpeWF0IGNpdmFyxLEnfSwKICAgICAge2xhYmVsOicxLjUtMi4wJyxjb2xvcjoneWVsbG93JyxkZXNjOidCaXJheiBwYWhhbMSxJ30sCiAgICAgIHtsYWJlbDonPjIuMCcsY29sb3I6J3JlZCcsZGVzYzonUGFoYWzEsSDigJQgZGlra2F0bGkgb2wnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIGLDvHnDvG1lIGthbGl0ZXNpJwogIH0sCiAgJ0VQU0dyb3d0aCc6IHsKICAgIHRpdGxlOiAnRVBTIELDvHnDvG1lc2kgKMOHZXlyZWtsaWssIFlvWSknLAogICAgZGVzYzogJ8WeaXJrZXRpbiBoaXNzZSBiYcWfxLFuYSBrYXphbmPEsW7EsW4gZ2XDp2VuIHnEsWzEsW4gYXluxLEgw6dleXJlxJ9pbmUgZ8O2cmUgYXJ0xLHFn8SxLiBDQU5TTElNXCdpbiBlbiBrcml0aWsga3JpdGVyaS4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMjUnLGNvbG9yOidncmVlbicsZGVzYzonR8O8w6dsw7wgYsO8ecO8bWUg4oCUIENBTlNMSU0ga3JpdGVyaSBrYXLFn8SxbGFuZMSxJ30sCiAgICAgIHtsYWJlbDonJTE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWkgYsO8ecO8bWUnfSwKICAgICAge2xhYmVsOiclMC0xNScsY29sb3I6J3llbGxvdycsZGVzYzonWmF5xLFmIGLDvHnDvG1lJ30sCiAgICAgIHtsYWJlbDonPDAnLGNvbG9yOidyZWQnLGRlc2M6J0themFuw6cgZMO8xZ/DvHlvciDigJQgZGlra2F0J30KICAgIF0sCiAgICBjYW5zbGltOiAnQyBrcml0ZXJpIOKAlCBlbiBrcml0aWsga3JpdGVyLCBtaW5pbXVtICUyNSBvbG1hbMSxJwogIH0sCiAgJ1Jldkdyb3d0aCc6IHsKICAgIHRpdGxlOiAnR2VsaXIgQsO8ecO8bWVzaSAoWW9ZKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIHNhdMSxxZ8vZ2VsaXJpbmluIGdlw6dlbiB5xLFsYSBnw7ZyZSBhcnTEscWfxLEuIEVQUyBiw7x5w7xtZXNpbmkgZGVzdGVrbGVtZXNpIGdlcmVraXIg4oCUIHNhZGVjZSBtYWxpeWV0IGtlc2ludGlzaXlsZSBiw7x5w7xtZSBzw7xyZMO8csO8bGViaWxpciBkZcSfaWwuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgR2Vyw6dlayB2ZXJpJywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic+JTE1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J0fDvMOnbMO8IGdlbGlyIGLDvHnDvG1lc2knfSwKICAgICAge2xhYmVsOiclNS0xNScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSBiw7x5w7xtZSd9LAogICAgICB7bGFiZWw6Jzw1Jyxjb2xvcjoncmVkJyxkZXNjOidHZWxpciBiw7x5w7xtZXNpIHphecSxZid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQgc8O8cmTDvHLDvGxlYmlsaXIgYsO8ecO8bWUgacOnaW4gxZ9hcnQnCiAgfSwKICAnTmV0TWFyZ2luJzogewogICAgdGl0bGU6ICdOZXQgTWFyamluJywKICAgIGRlc2M6ICdIZXIgMSQgZ2VsaXJkZW4gbmUga2FkYXIgbmV0IGvDonIga2FsZMSxxJ/EsW7EsSBnw7ZzdGVyaXIuIFnDvGtzZWsgbWFyamluID0gZ8O8w6dsw7wgacWfIG1vZGVsaS4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMjAnLGNvbG9yOidncmVlbicsZGVzYzonw4dvayBnw7zDp2zDvCBrw6JybMSxbMSxayd9LAogICAgICB7bGFiZWw6JyUxMC0yMCcsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpIGvDonJsxLFsxLFrJ30sCiAgICAgIHtsYWJlbDonJTUtMTAnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGEga8OicmzEsWzEsWsnfSwKICAgICAge2xhYmVsOic8NScsY29sb3I6J3JlZCcsZGVzYzonWmF5xLFmIGvDonJsxLFsxLFrJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQSBrcml0ZXJpIOKAlCBrw6JybMSxbMSxayBrYWxpdGVzaScKICB9LAogICdST0UnOiB7CiAgICB0aXRsZTogJ1JPRSAow5Z6a2F5bmFrIEvDonJsxLFsxLHEn8SxKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIMO2eiBzZXJtYXllc2l5bGUgbmUga2FkYXIga8OiciBldHRpxJ9pbmkgZ8O2c3RlcmlyLiBZw7xrc2VrIFJPRSA9IHNlcm1heWV5aSB2ZXJpbWxpIGt1bGxhbsSxeW9yLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUyNScsY29sb3I6J2dyZWVuJyxkZXNjOifDh29rIGfDvMOnbMO8IOKAlCBDQU5TTElNIGlkZWFsIHNldml5ZXNpJ30sCiAgICAgIHtsYWJlbDonJTE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWknfSwKICAgICAge2xhYmVsOiclOC0xNScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSd9LAogICAgICB7bGFiZWw6Jzw4Jyxjb2xvcjoncmVkJyxkZXNjOidaYXnEsWYnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIG1pbmltdW0gJTE3IG9sbWFsxLEnCiAgfSwKICAnR3Jvc3NNYXJnaW4nOiB7CiAgICB0aXRsZTogJ0Jyw7x0IE1hcmppbicsCiAgICBkZXNjOiAnU2F0xLHFnyBnZWxpcmluZGVuIMO8cmV0aW0gbWFsaXlldGkgZMO8xZ/DvGxkw7xrdGVuIHNvbnJhIGthbGFuIG9yYW4uIFNla3TDtnJlIGfDtnJlIGRlxJ9pxZ9pci4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lNTAnLGNvbG9yOidncmVlbicsZGVzYzonw4dvayBnw7zDp2zDvCDigJQgeWF6xLFsxLFtL1NhYVMgc2V2aXllc2knfSwKICAgICAge2xhYmVsOiclMzAtNTAnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSd9LAogICAgICB7bGFiZWw6JyUxNS0zMCcsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSDigJQgZG9uYW7EsW0veWFyxLEgaWxldGtlbiBub3JtYWwnfSwKICAgICAge2xhYmVsOic8MTUnLGNvbG9yOidyZWQnLGRlc2M6J0TDvMWfw7xrIG1hcmppbid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0vDonJsxLFsxLFrIGthbGl0ZXNpIGfDtnN0ZXJnZXNpJwogIH0sCiAgLy8gR8SwUsSwxZ4KICAnRW50cnlTY29yZSc6IHsKICAgIHRpdGxlOiAnR2lyacWfIEthbGl0ZXNpIFNrb3J1JywKICAgIGRlc2M6ICdSU0ksIFNNQSBwb3ppc3lvbnUsIFAvRSwgUEVHIHZlIEVQUyBiw7x5w7xtZXNpbmkgYmlybGXFn3RpcmVuIGJpbGXFn2lrIHNrb3IuIDAtMTAwIGFyYXPEsS4nLAogICAgc291cmNlOiAnQml6aW0gaGVzYXBsYW1hJywKICAgIHJlbGlhYmlsaXR5OiAnbG93JywKICAgIHdhcm5pbmc6ICdCVSBVWUdVTEFNQSBUQVJBRklOREFOIEhFU0FQTEFOQU4gS0FCQSBUQUhNxLBORMSwUi4gWWF0xLFyxLFtIGthcmFyxLEgacOnaW4gdGVrIGJhxZ/EsW5hIGt1bGxhbm1hLicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic3NS0xMDAnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgaWRlYWwgZ2lyacWfIGLDtmxnZXNpJ30sCiAgICAgIHtsYWJlbDonNjAtNzUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwgZml5YXQnfSwKICAgICAge2xhYmVsOic0NS02MCcsY29sb3I6J3llbGxvdycsZGVzYzonTsO2dHInfSwKICAgICAge2xhYmVsOiczMC00NScsY29sb3I6J3JlZCcsZGVzYzonUGFoYWzEsSDigJQgYmVrbGUnfSwKICAgICAge2xhYmVsOicwLTMwJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHBhaGFsxLEg4oCUIGdpcm1lJ30KICAgIF0sCiAgICBjYW5zbGltOiAnVMO8bSBrcml0ZXJsZXIgYmlsZcWfaW1pJwogIH0sCiAgJ1JSJzogewogICAgdGl0bGU6ICdSaXNrL8OWZMO8bCBPcmFuxLEgKFIvUiknLAogICAgZGVzYzogJ1BvdGFuc2l5ZWwga2F6YW5jxLFuIHJpc2tlIG9yYW7EsS4gMToyIGRlbWVrIDEkIHJpc2tlIGthcsWfxLEgMiQga2F6YW7DpyBwb3RhbnNpeWVsaSB2YXIgZGVtZWsuJywKICAgIHNvdXJjZTogJ0JpemltIGhlc2FwbGFtYScsCiAgICByZWxpYWJpbGl0eTogJ2xvdycsCiAgICB3YXJuaW5nOiAnR2lyacWfL2hlZGVmL3N0b3Agc2V2aXllbGVyaSBmb3Jtw7xsIGJhemzEsSBrYWJhIHRhaG1pbmRpcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOicxOjMrJyxjb2xvcjonZ3JlZW4nLGRlc2M6J03DvGtlbW1lbCDigJQgZ8O8w6dsw7wgZ2lyacWfIHNpbnlhbGknfSwKICAgICAge2xhYmVsOicxOjInLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSDigJQgbWluaW11bSBrYWJ1bCBlZGlsZWJpbGlyJ30sCiAgICAgIHtsYWJlbDonMToxJyxjb2xvcjoneWVsbG93JyxkZXNjOidaYXnEsWYnfSwKICAgICAge2xhYmVsOic8MToxJyxjb2xvcjoncmVkJyxkZXNjOidSaXNrIGthemFuw6d0YW4gYsO8ecO8ayDigJQgZ2lybWUnfQogICAgXSwKICAgIGNhbnNsaW06ICdSaXNrIHnDtm5ldGltaScKICB9LAogIC8vIEVBUk5JTkdTCiAgJ0Vhcm5pbmdzRGF0ZSc6IHsKICAgIHRpdGxlOiAnUmFwb3IgVGFyaWhpIChFYXJuaW5ncyBEYXRlKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIMOnZXlyZWsgZmluYW5zYWwgc29udcOnbGFyxLFuxLEgYcOnxLFrbGF5YWNhxJ/EsSB0YXJpaC4gUmFwb3Igw7ZuY2VzaSB2ZSBzb25yYXPEsSBmaXlhdCBzZXJ0IGhhcmVrZXQgZWRlYmlsaXIuJywKICAgIHNvdXJjZTogJ3lmaW5hbmNlIOKAlCBiYXplbiBoYXRhbMSxIG9sYWJpbGlyJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdUYXJpaGxlcmkgcmVzbWkgSVIgc2F5ZmFzxLFuZGFuIGRvxJ9ydWxhecSxbicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic3IGfDvG4gacOnaW5kZScsY29sb3I6J3JlZCcsZGVzYzonw4dvayB5YWvEsW4g4oCUIHBvemlzeW9uIGHDp21hayByaXNrbGknfSwKICAgICAge2xhYmVsOic4LTE0IGfDvG4nLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1lha8SxbiDigJQgZGlra2F0bGkgb2wnfSwKICAgICAge2xhYmVsOicxNCsgZ8O8bicsY29sb3I6J2dyZWVuJyxkZXNjOidZZXRlcmxpIHPDvHJlIHZhcid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Mga3JpdGVyaSDigJQgw6dleXJlayByYXBvciBrYWxpdGVzaScKICB9LAogICdBdmdNb3ZlJzogewogICAgdGl0bGU6ICdPcnRhbGFtYSBSYXBvciBIYXJla2V0aScsCiAgICBkZXNjOiAnU29uIDQgw6dleXJlayByYXBvcnVuZGEsIHJhcG9yIGfDvG7DvCB2ZSBlcnRlc2kgZ8O8biBmaXlhdMSxbiBvcnRhbGFtYSBuZSBrYWRhciBoYXJla2V0IGV0dGnEn2kuJywKICAgIHNvdXJjZTogJ0JpemltIGhlc2FwbGFtYScsCiAgICByZWxpYWJpbGl0eTogJ21lZGl1bScsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOidQb3ppdGlmICg+JTUpJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8WeaXJrZXQgZ2VuZWxsaWtsZSBiZWtsZW50aXlpIGHFn8SxeW9yJ30sCiAgICAgIHtsYWJlbDonTsO2dHIgKCUwLTUpJyxjb2xvcjoneWVsbG93JyxkZXNjOidLYXLEscWfxLFrIGdlw6dtacWfJ30sCiAgICAgIHtsYWJlbDonTmVnYXRpZicsY29sb3I6J3JlZCcsZGVzYzonUmFwb3IgZMO2bmVtaW5kZSBmaXlhdCBnZW5lbGxpa2xlIGTDvMWfw7x5b3Ig4oCUIGRpa2thdCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Mga3JpdGVyaSDigJQga2F6YW7DpyBzw7xycHJpemkgZ2XDp21pxZ9pJwogIH0KfTsKCmZ1bmN0aW9uIHNob3dJbmZvKGtleSxldmVudCl7CiAgaWYoZXZlbnQpIGV2ZW50LnN0b3BQcm9wYWdhdGlvbigpOwogIHZhciBtPU1FVFJJQ1Nba2V5XTsgaWYoIW0pIHJldHVybjsKICB2YXIgcmVsTGFiZWw9bS5yZWxpYWJpbGl0eT09PSJoaWdoIj8iR8O8dmVuaWxpciI6bS5yZWxpYWJpbGl0eT09PSJtZWRpdW0iPyJPcnRhIEfDvHZlbmlsaXIiOiJLYWJhIFRhaG1pbiI7CiAgdmFyIGg9JzxkaXYgY2xhc3M9Im1pbmZvLXRpdGxlIj4nK20udGl0bGUrJzwvZGl2Pic7CiAgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLXNvdXJjZSI+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+JyttLnNvdXJjZSsnPC9zcGFuPjxzcGFuIGNsYXNzPSJtaW5mby1yZWwgJyttLnJlbGlhYmlsaXR5KyciPicrcmVsTGFiZWwrJzwvc3Bhbj48L2Rpdj4nOwogIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby1kZXNjIj4nK20uZGVzYysnPC9kaXY+JzsKICBpZihtLndhcm5pbmcpIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby13YXJuaW5nIj7imqDvuI8gJyttLndhcm5pbmcrJzwvZGl2Pic7CiAgaWYobS5yYW5nZXMmJm0ucmFuZ2VzLmxlbmd0aCl7CiAgICBoKz0nPGRpdiBjbGFzcz0ibWluZm8tcmFuZ2VzIj48ZGl2IGNsYXNzPSJtaW5mby1yYW5nZS10aXRsZSI+UmVmZXJhbnMgRGVnZXJsZXI8L2Rpdj4nOwogICAgbS5yYW5nZXMuZm9yRWFjaChmdW5jdGlvbihyKXt2YXIgZGM9ci5jb2xvcj09PSJncmVlbiI/IiMxMGI5ODEiOnIuY29sb3I9PT0icmVkIj8iI2VmNDQ0NCI6IiNmNTllMGIiO2grPSc8ZGl2IGNsYXNzPSJtaW5mby1yYW5nZSI+PGRpdiBjbGFzcz0ibWluZm8tcmFuZ2UtZG90IiBzdHlsZT0iYmFja2dyb3VuZDonK2RjKyciPjwvZGl2PjxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOicrZGMrJyI+JytyLmxhYmVsKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrci5kZXNjKyc8L2Rpdj48L2Rpdj48L2Rpdj4nO30pOwogICAgaCs9JzwvZGl2Pic7CiAgfQogIGlmKG0uY2Fuc2xpbSkgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLWNhbnNsaW0iPvCfk4ogQ0FOU0xJTTogJyttLmNhbnNsaW0rJzwvZGl2Pic7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvQ29udGVudCIpLmlubmVySFRNTD1oOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwp9CmZ1bmN0aW9uIGNsb3NlSW5mb1BvcHVwKGUpe2lmKCFlfHxlLnRhcmdldD09PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikpe2RvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpO319Cgo8L3NjcmlwdD4KPC9zY3JpcHQ+CjxzY3JpcHQ+CnZhciBURl9EQVRBPSUlVEZfREFUQSUlOwp2YXIgUE9SVD0lJVBPUlQlJTsKdmFyIEVBUk5JTkdTX0RBVEE9JSVFQVJOSU5HU19EQVRBJSU7CnZhciBNQVJLRVRfREFUQT0lJU1BUktFVF9EQVRBJSU7CnZhciBORVdTX0RBVEE9JSVORVdTX0RBVEElJTsKdmFyIEFJX0RBVEE9JSVBSV9EQVRBJSU7CnZhciBXRUVLTFlfREFUQT0lJVdFRUtMWV9EQVRBJSU7CnZhciBTQ1JFRU5FUl9EQVRBPSUlU0NSRUVORVJfREFUQSUlOwp2YXIgRElSRUNUSU9OX0RBVEE9JSVESVJFQ1RJT05fREFUQSUlOwp2YXIgY3VyVGFiPSJhbGwiLGN1clRmPSIxZCIsY3VyRGF0YT1URl9EQVRBWyIxZCJdLnNsaWNlKCk7CnZhciBtaW5pQ2hhcnRzPXt9LG1DaGFydD1udWxsOwp2YXIgU1M9ewogICJHVUNMVSBBTCI6e2JnOiJyZ2JhKDE2LDE4NSwxMjksLjEyKSIsYmQ6InJnYmEoMTYsMTg1LDEyOSwuMzUpIix0eDoiIzEwYjk4MSIsYWM6IiMxMGI5ODEiLGxibDoiR1VDTFUgQUwifSwKICAiQUwiOntiZzoicmdiYSg1MiwyMTEsMTUzLC4xKSIsYmQ6InJnYmEoNTIsMjExLDE1MywuMykiLHR4OiIjMzRkMzk5IixhYzoiIzM0ZDM5OSIsbGJsOiJBTCJ9LAogICJESUtLQVQiOntiZzoicmdiYSgyNDUsMTU4LDExLC4xKSIsYmQ6InJnYmEoMjQ1LDE1OCwxMSwuMykiLHR4OiIjZjU5ZTBiIixhYzoiI2Y1OWUwYiIsbGJsOiJESUtLQVQifSwKICAiWkFZSUYiOntiZzoicmdiYSgxMDcsMTE0LDEyOCwuMSkiLGJkOiJyZ2JhKDEwNywxMTQsMTI4LC4zKSIsdHg6IiM5Y2EzYWYiLGFjOiIjNmI3MjgwIixsYmw6IlpBWUlGIn0sCiAgIlNBVCI6e2JnOiJyZ2JhKDIzOSw2OCw2OCwuMTIpIixiZDoicmdiYSgyMzksNjgsNjgsLjM1KSIsdHg6IiNlZjQ0NDQiLGFjOiIjZWY0NDQ0IixsYmw6IlNBVCJ9Cn07CgpmdW5jdGlvbiBpYihrZXksbGFiZWwpewogIHJldHVybiBsYWJlbCsnIDxzcGFuIGNsYXNzPSJtaW5mbyIgb25jbGljaz0ic2hvd0luZm8oXCcnK2tleSsnXCcsZXZlbnQpIj4/PC9zcGFuPic7Cn0KCmZ1bmN0aW9uIHNldFRhYih0LGVsKXsKICBjdXJUYWI9dDsKICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIudGFiIikuZm9yRWFjaChmdW5jdGlvbihiKXtiLmNsYXNzTGlzdC5yZW1vdmUoImFjdGl2ZSIpO30pOwogIGVsLmNsYXNzTGlzdC5hZGQoImFjdGl2ZSIpOwogIHZhciB0ZlJvdz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidGZSb3ciKTsKICBpZih0ZlJvdykgdGZSb3cuc3R5bGUuZGlzcGxheT0odD09PSJkYXNoYm9hcmQifHx0PT09ImVhcm5pbmdzInx8dD09PSJydXRpbiJ8fHQ9PT0iaGFmdGFsaWsifHx0PT09InNjcmVlbmVyInx8dD09PSJ2YWx1YXRpb24ifHx0PT09ImRpcmVjdGlvbiIpPyJub25lIjoiZmxleCI7CiAgaWYodD09PSJkYXNoYm9hcmQiKSByZW5kZXJEYXNoYm9hcmQoKTsKICBlbHNlIGlmKHQ9PT0iZWFybmluZ3MiKSByZW5kZXJFYXJuaW5ncygpOwogIGVsc2UgaWYodD09PSJydXRpbiIpIHJlbmRlclJ1dGluKCk7CiAgZWxzZSBpZih0PT09ImhhZnRhbGlrIikgcmVuZGVySGFmdGFsaWsoKTsKICBlbHNlIGlmKHQ9PT0ic2NyZWVuZXIiKSByZW5kZXJTY3JlZW5lcigpOwogIGVsc2UgaWYodD09PSJ2YWx1YXRpb24iKSByZW5kZXJWYWx1YXRpb24oKTsKICBlbHNlIGlmKHQ9PT0iZGlyZWN0aW9uIikgcmVuZGVyRGlyZWN0aW9uKCk7CiAgZWxzZSB7CiAgICB2YXIgZz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogICAgaWYoZyl7Zy5zdHlsZS5kaXNwbGF5PScnO2cuc3R5bGUud2lkdGg9Jyc7fQogICAgcmVuZGVyR3JpZCgpOwogIH0KfQoKZnVuY3Rpb24gc2V0VGYodGYsZWwpewogIGN1clRmPXRmOwogIGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoIi50Zi1idG4iKS5mb3JFYWNoKGZ1bmN0aW9uKGIpe2IuY2xhc3NMaXN0LnRvZ2dsZSgiYWN0aXZlIixiLmRhdGFzZXQudGY9PT10Zik7fSk7CiAgY3VyRGF0YT0oVEZfREFUQVt0Zl18fFRGX0RBVEFbIjFkIl0pLnNsaWNlKCk7CiAgcmVuZGVyU3RhdHMoKTsKICByZW5kZXJHcmlkKCk7Cn0KCmZ1bmN0aW9uIGZpbHRlcmVkKCl7CiAgdmFyIGQ9Y3VyRGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSk7CiAgaWYoY3VyVGFiPT09InBvcnQiKSByZXR1cm4gZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIFBPUlQuaW5jbHVkZXMoci50aWNrZXIpO30pOwogIGlmKGN1clRhYj09PSJidXkiKSByZXR1cm4gZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09IkdVQ0xVIEFMInx8ci5zaW55YWw9PT0iQUwiO30pOwogIGlmKGN1clRhYj09PSJzZWxsIikgcmV0dXJuIGQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSJTQVQiO30pOwogIHJldHVybiBkOwp9CgpmdW5jdGlvbiByZW5kZXJTdGF0cygpewogIHZhciBkPWN1ckRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pOwogIHZhciBjbnQ9e307CiAgZC5mb3JFYWNoKGZ1bmN0aW9uKHIpe2NudFtyLnNpbnlhbF09KGNudFtyLnNpbnlhbF18fDApKzE7fSk7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInN0YXRzIikuaW5uZXJIVE1MPQogICAgJzxkaXYgY2xhc3M9InBpbGwgZyI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5HdWNsdSBBbDogJysoY250WyJHVUNMVSBBTCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIGciPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+QWw6ICcrKGNudFsiQUwiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCB5Ij48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PkRpa2thdDogJysoY250WyJESUtLQVQiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCByIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PlNhdDogJysoY250WyJTQVQiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCBiIiBzdHlsZT0ibWFyZ2luLWxlZnQ6YXV0byI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5Qb3J0Zm9seW86ICcrUE9SVC5sZW5ndGgrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCBtIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PicrZC5sZW5ndGgrJyBhbmFsaXo8L2Rpdj4nOwp9CgpmdW5jdGlvbiByZW5kZXJHcmlkKCl7CiAgT2JqZWN0LnZhbHVlcyhtaW5pQ2hhcnRzKS5mb3JFYWNoKGZ1bmN0aW9uKGMpe2MuZGVzdHJveSgpO30pOwogIG1pbmlDaGFydHM9e307CiAgdmFyIGY9ZmlsdGVyZWQoKTsKICB2YXIgZ3JpZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ3JpZCIpOwogIGlmKCFmLmxlbmd0aCl7Z3JpZC5pbm5lckhUTUw9JzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTE7dGV4dC1hbGlnbjpjZW50ZXI7cGFkZGluZzo0MHB4O2NvbG9yOnZhcigtLW11dGVkKSI+SGlzc2UgYnVsdW5hbWFkaTwvZGl2Pic7cmV0dXJuO30KICBncmlkLmlubmVySFRNTD1mLm1hcChmdW5jdGlvbihyKXtyZXR1cm4gYnVpbGRDYXJkKHIpO30pLmpvaW4oIiIpOwogIGYuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBjdHg9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1jLSIrci50aWNrZXIpOwogICAgaWYoY3R4JiZyLmNoYXJ0X2Nsb3NlcyYmci5jaGFydF9jbG9zZXMubGVuZ3RoKXsKICAgICAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogICAgICBtaW5pQ2hhcnRzWyJtIityLnRpY2tlcl09bmV3IENoYXJ0KGN0eCx7dHlwZToibGluZSIsZGF0YTp7bGFiZWxzOnIuY2hhcnRfZGF0ZXMsZGF0YXNldHM6W3tkYXRhOnIuY2hhcnRfY2xvc2VzLGJvcmRlckNvbG9yOnNzLmFjLGJvcmRlcldpZHRoOjEuNSxmaWxsOnRydWUsYmFja2dyb3VuZENvbG9yOnNzLmFjKyIxOCIscG9pbnRSYWRpdXM6MCx0ZW5zaW9uOjAuNH1dfSxvcHRpb25zOntwbHVnaW5zOntsZWdlbmQ6e2Rpc3BsYXk6ZmFsc2V9fSxzY2FsZXM6e3g6e2Rpc3BsYXk6ZmFsc2V9LHk6e2Rpc3BsYXk6ZmFsc2V9fSxhbmltYXRpb246e2R1cmF0aW9uOjUwMH0scmVzcG9uc2l2ZTp0cnVlLG1haW50YWluQXNwZWN0UmF0aW86ZmFsc2V9fSk7CiAgICB9CiAgfSk7Cn0KCmZ1bmN0aW9uIGJ1aWxkQ2FyZChyKXsKICB2YXIgc3M9U1Nbci5zaW55YWxdfHxTU1siRElLS0FUIl07CiAgdmFyIGRjPXIuZGVnaXNpbT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICB2YXIgZHM9KHIuZGVnaXNpbT49MD8iKyI6IiIpK3IuZGVnaXNpbSsiJSI7CiAgdmFyIGVzY29sPXIuZW50cnlfc2NvcmU+PTc1PyJ2YXIoLS1ncmVlbikiOnIuZW50cnlfc2NvcmU+PTYwPyJ2YXIoLS1ncmVlbjIpIjpyLmVudHJ5X3Njb3JlPj00NT8idmFyKC0teWVsbG93KSI6ci5lbnRyeV9zY29yZT49MzA/InZhcigtLXJlZDIpIjoidmFyKC0tcmVkKSI7CiAgdmFyIHB2Y29sPXIucHJpY2VfdnNfY29sb3I9PT0iZ3JlZW4iPyJ2YXIoLS1ncmVlbikiOnIucHJpY2VfdnNfY29sb3I9PT0ieWVsbG93Ij8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZDIpIjsKICB2YXIgc2lncz1bCiAgICB7bDoiVHJlbmQiLHY6ci50cmVuZD09PSJZdWtzZWxlbiI/Ill1a3NlbGl5b3IiOnIudHJlbmQ9PT0iRHVzZW4iPyJEdXN1eW9yIjoiWWF0YXkiLGc6ci50cmVuZD09PSJZdWtzZWxlbiI/dHJ1ZTpyLnRyZW5kPT09IkR1c2VuIj9mYWxzZTpudWxsfSwKICAgIHtsOiJTTUE1MCIsdjpyLmFib3ZlNTA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIsZzpyLmFib3ZlNTB9LAogICAge2w6IlNNQTIwMCIsdjpyLmFib3ZlMjAwPyJVemVyaW5kZSI6IkFsdGluZGEiLGc6ci5hYm92ZTIwMH0sCiAgICB7bDoiUlNJIix2OnIucnNpfHwiPyIsZzpyLnJzaT9yLnJzaTwzMD90cnVlOnIucnNpPjcwP2ZhbHNlOm51bGw6bnVsbH0sCiAgICB7bDoiNTJXIix2OiIlIityLnBjdF9mcm9tXzUydysiIHV6YWsiLGc6ci5uZWFyXzUyd30KICBdLm1hcChmdW5jdGlvbihzKXtyZXR1cm4gJzxzcGFuIGNsYXNzPSJzcCAnKyhzLmc9PT10cnVlPyJzZyI6cy5nPT09ZmFsc2U/InNiIjoic24iKSsnIj4nK3MubCsiOiAiK3MudisiPC9zcGFuPiI7fSkuam9pbigiIik7CiAgcmV0dXJuICc8ZGl2IGNsYXNzPSJjYXJkIiBzdHlsZT0iYm9yZGVyLWNvbG9yOicrKHIucG9ydGZvbGlvPyJyZ2JhKDE2LDE4NSwxMjksLjI1KSI6c3MuYmQpKyciIG9uY2xpY2s9Im9wZW5NKFwnJytyLnRpY2tlcisnXCcpIj4nCiAgICArJzxkaXYgY2xhc3M9ImFjY2VudCIgc3R5bGU9ImJhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDkwZGVnLCcrc3MuYWMrJywnK3NzLmFjKyc4OCkiPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iY2JvZHkiPjxkaXYgY2xhc3M9ImN0b3AiPjxkaXY+PGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NHB4Ij4nCiAgICArJzxzcGFuIGNsYXNzPSJ0aWNrZXIiIHN0eWxlPSJjb2xvcjonK3NzLnR4KyciPicrci50aWNrZXIrJzwvc3Bhbj4nCiAgICArKHIucG9ydGZvbGlvPyc8c3BhbiBjbGFzcz0icG9ydC1iYWRnZSI+UDwvc3Bhbj4nOicnKSsKICAgICc8L2Rpdj48c3BhbiBjbGFzcz0iYmFkZ2UiIHN0eWxlPSJiYWNrZ3JvdW5kOicrc3MuYmcrJztjb2xvcjonK3NzLnR4Kyc7Ym9yZGVyOjFweCBzb2xpZCAnK3NzLmJkKyciPicrc3MubGJsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJjcHIiPjxkaXYgY2xhc3M9InB2YWwiPiQnK3IuZml5YXQrJzwvZGl2PjxkaXYgY2xhc3M9InBjaGciIHN0eWxlPSJjb2xvcjonK2RjKyciPicrZHMrJzwvZGl2PicKICAgICsoci5wZV9md2Q/JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5Gd2RQRTonK3IucGVfZndkLnRvRml4ZWQoMSkrJzwvZGl2Pic6JycpCiAgICArJzwvZGl2PjwvZGl2PjxkaXYgY2xhc3M9InNpZ3MiPicrc2lncysnPC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJtYXJnaW4tdG9wOjZweCI+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47bWFyZ2luLWJvdHRvbTozcHgiPjxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+R2lyaXMgS2FsaXRlc2k8L3NwYW4+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK2VzY29sKyciPicrci5lbnRyeV9zY29yZSsnLzEwMDwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImhlaWdodDo0cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6MnB4O292ZXJmbG93OmhpZGRlbiI+PGRpdiBzdHlsZT0iaGVpZ2h0OjEwMCU7d2lkdGg6JytyLmVudHJ5X3Njb3JlKyclO2JhY2tncm91bmQ6Jytlc2NvbCsnO2JvcmRlci1yYWRpdXM6MnB4Ij48L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tdG9wOjNweCI+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfbGFiZWwrJzwvc3Bhbj48c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK3B2Y29sKyciPicrci5wcmljZV92c19pZGVhbCsnPC9zcGFuPjwvZGl2PicKICAgICsnPC9kaXY+PGRpdiBjbGFzcz0iY2hhcnQtdyI+PGNhbnZhcyBpZD0ibWMtJytyLnRpY2tlcisnIj48L2NhbnZhcz48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9Imx2bHMiPicKICAgICsnPGRpdiBjbGFzcz0ibHYiPjxkaXYgY2xhc3M9ImxsIj5IZW1lbiBHaXI8L2Rpdj48ZGl2IGNsYXNzPSJsdmFsIiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4yKSI+JCcrci5lbnRyeV9hZ2dyZXNzaXZlKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9Imx2Ij48ZGl2IGNsYXNzPSJsbCI+SGVkZWY8L2Rpdj48ZGl2IGNsYXNzPSJsdmFsIiBzdHlsZT0iY29sb3I6IzYwYTVmYSI+JCcrci5oZWRlZisnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJsdiI+PGRpdiBjbGFzcz0ibGwiPlN0b3A8L2Rpdj48ZGl2IGNsYXNzPSJsdmFsIiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMikiPiQnK3Iuc3RvcCsnPC9kaXY+PC9kaXY+JwogICAgKyc8L2Rpdj48L2Rpdj48L2Rpdj4nOwp9CgpmdW5jdGlvbiByZW5kZXJEYXNoYm9hcmQoKXsKICB2YXIgZ3JpZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ3JpZCIpOwogIHZhciBtZD1NQVJLRVRfREFUQXx8e307CiAgdmFyIHNwPW1kLlNQNTAwfHx7fTsKICB2YXIgbmFzPW1kLk5BU0RBUXx8e307CiAgdmFyIHZpeD1tZC5WSVh8fHt9OwogIHZhciBtU2lnbmFsPW1kLk1fU0lHTkFMfHwiTk9UUiI7CiAgdmFyIG1MYWJlbD1tZC5NX0xBQkVMfHwiVmVyaSB5b2siOwogIHZhciBtQ29sb3I9bVNpZ25hbD09PSJHVUNMVSI/InZhcigtLWdyZWVuKSI6bVNpZ25hbD09PSJaQVlJRiI/InZhcigtLXJlZDIpIjoidmFyKC0teWVsbG93KSI7CiAgdmFyIG1CZz1tU2lnbmFsPT09IkdVQ0xVIj8icmdiYSgxNiwxODUsMTI5LC4wOCkiOm1TaWduYWw9PT0iWkFZSUYiPyJyZ2JhKDIzOSw2OCw2OCwuMDgpIjoicmdiYSgyNDUsMTU4LDExLC4wOCkiOwogIHZhciBtQm9yZGVyPW1TaWduYWw9PT0iR1VDTFUiPyJyZ2JhKDE2LDE4NSwxMjksLjI1KSI6bVNpZ25hbD09PSJaQVlJRiI/InJnYmEoMjM5LDY4LDY4LC4yNSkiOiJyZ2JhKDI0NSwxNTgsMTEsLjI1KSI7CiAgdmFyIG1JY29uPW1TaWduYWw9PT0iR1VDTFUiPyLinIUiOm1TaWduYWw9PT0iWkFZSUYiPyLinYwiOiLimqDvuI8iOwoKICBmdW5jdGlvbiBpbmRleENhcmQobmFtZSxkYXRhKXsKICAgIGlmKCFkYXRhfHwhZGF0YS5wcmljZSkgcmV0dXJuICIiOwogICAgdmFyIGNjPWRhdGEuY2hhbmdlPj0wPyJ2YXIoLS1ncmVlbjIpIjoidmFyKC0tcmVkMikiOwogICAgdmFyIGNzPShkYXRhLmNoYW5nZT49MD8iKyI6IiIpK2RhdGEuY2hhbmdlKyIlIjsKICAgIHZhciBzNTA9ZGF0YS5hYm92ZTUwPyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZToxMHB4Ij5TTUE1MCDinJM8L3NwYW4+JzonPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpO2ZvbnQtc2l6ZToxMHB4Ij5TTUE1MCDinJc8L3NwYW4+JzsKICAgIHZhciBzMjAwPWRhdGEuYWJvdmUyMDA/JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjEwcHgiPlNNQTIwMCDinJM8L3NwYW4+JzonPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpO2ZvbnQtc2l6ZToxMHB4Ij5TTUEyMDAg4pyXPC9zcGFuPic7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCAxNnB4O2ZsZXg6MTttaW4td2lkdGg6MTUwcHgiPicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo2cHgiPicrbmFtZSsnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCkiPiQnK2RhdGEucHJpY2UrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEzcHg7Y29sb3I6JytjYysnO21hcmdpbi1ib3R0b206OHB4Ij4nK2NzKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo4cHgiPicrczUwK3MyMDArJzwvZGl2PjwvZGl2Pic7CiAgfQoKICB2YXIgcG9ydERhdGE9Y3VyRGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGEmJlBPUlQuaW5jbHVkZXMoci50aWNrZXIpO30pOwogIHZhciBwb3J0SHRtbD0iIjsKICBpZihwb3J0RGF0YS5sZW5ndGgpewogICAgcG9ydEh0bWw9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjE0cHgiPicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEycHgiPvCfkrwgUG9ydGbDtnkgw5Z6ZXRpPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMTQwcHgsMWZyKSk7Z2FwOjhweCI+JzsKICAgIHBvcnREYXRhLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICAgIHZhciBkYz1yLmRlZ2lzaW0+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgICAgIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICAgICAgcG9ydEh0bWwrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCAnK3NzLmJkKyc7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4O2N1cnNvcjpwb2ludGVyIiBvbmNsaWNrPSJvcGVuTShcJycrci50aWNrZXIrJ1wnKSI+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjRweCI+JwogICAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OkJlYmFzIE5ldWUsc2Fucy1zZXJpZjtmb250LXNpemU6MTZweDtsZXR0ZXItc3BhY2luZzoycHg7Y29sb3I6Jytzcy50eCsnIj4nK3IudGlja2VyKyc8L3NwYW4+JwogICAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7YmFja2dyb3VuZDonK3NzLmJnKyc7Y29sb3I6Jytzcy50eCsnO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjJweCI+Jytzcy5sYmwrJzwvc3Bhbj48L2Rpdj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwIj4kJytyLmZpeWF0Kyc8L2Rpdj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjExcHg7Y29sb3I6JytkYysnIj4nKyhyLmRlZ2lzaW0+PTA/IisiOiIiKStyLmRlZ2lzaW0rJyU8L2Rpdj48L2Rpdj4nOwogICAgfSk7CiAgICBwb3J0SHRtbCs9JzwvZGl2PjwvZGl2Pic7CiAgfQoKICB2YXIgdXJnZW50RWFybmluZ3M9RUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuIGUuYWxlcnQ9PT0icmVkInx8ZS5hbGVydD09PSJ5ZWxsb3ciO30pOwogIHZhciBlYXJuaW5nc0FsZXJ0PSIiOwogIGlmKHVyZ2VudEVhcm5pbmdzLmxlbmd0aCl7CiAgICBlYXJuaW5nc0FsZXJ0PSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNHB4IDE2cHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0teWVsbG93KTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+4pqg77iPIFlha2xhxZ9hbiBSYXBvcmxhcjwvZGl2Pic7CiAgICB1cmdlbnRFYXJuaW5ncy5mb3JFYWNoKGZ1bmN0aW9uKGUpewogICAgICB2YXIgaWM9ZS5hbGVydD09PSJyZWQiPyLwn5S0Ijoi8J+foSI7CiAgICAgIGVhcm5pbmdzQWxlcnQrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206NnB4O2ZvbnQtc2l6ZToxMnB4Ij4nCiAgICAgICAgKyc8c3Bhbj4nK2ljKycgPHN0cm9uZz4nK2UudGlja2VyKyc8L3N0cm9uZz48L3NwYW4+JwogICAgICAgICsnPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+JytlLm5leHRfZGF0ZSsnICgnKyhlLmRheXNfdG9fZWFybmluZ3M9PT0wPyJCVUfDnE4iOmUuZGF5c190b19lYXJuaW5ncysiIGfDvG4iKSsnKTwvc3Bhbj48L2Rpdj4nOwogICAgfSk7CiAgICBlYXJuaW5nc0FsZXJ0Kz0nPC9kaXY+JzsKICB9CgogIHZhciBuZXdzSHRtbD0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4Ij4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTJweCI+8J+TsCBTb24gSGFiZXJsZXI8L2Rpdj4nOwogIGlmKE5FV1NfREFUQSYmTkVXU19EQVRBLmxlbmd0aCl7CiAgICBORVdTX0RBVEEuc2xpY2UoMCwxMCkuZm9yRWFjaChmdW5jdGlvbihuKXsKICAgICAgdmFyIHBiPW4ucG9ydGZvbGlvPyc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEyKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjI1KTtwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo2MDAiPlA8L3NwYW4+JzoiIjsKICAgICAgdmFyIHRhPSIiOwogICAgICBpZihuLmRhdGV0aW1lKXt2YXIgZGlmZj1NYXRoLmZsb29yKChEYXRlLm5vdygpLzEwMDAtbi5kYXRldGltZSkvMzYwMCk7dGE9ZGlmZjwyND8oZGlmZisicyDDtm5jZSIpOihNYXRoLmZsb29yKGRpZmYvMjQpKyJnIMO2bmNlIik7fQogICAgICBuZXdzSHRtbCs9JzxkaXYgc3R5bGU9InBhZGRpbmc6MTBweCAwO2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA0KSI+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4O21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXllbGxvdykiPicrbi50aWNrZXIrJzwvc3Bhbj4nK3BiCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWxlZnQ6YXV0byI+Jyt0YSsnPC9zcGFuPjwvZGl2PicKICAgICAgICArJzxhIGhyZWY9Iicrbi51cmwrJyIgdGFyZ2V0PSJfYmxhbmsiIHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS10ZXh0KTt0ZXh0LWRlY29yYXRpb246bm9uZTtsaW5lLWhlaWdodDoxLjU7ZGlzcGxheTpibG9jayI+Jysobi5oZWFkbGluZV90cnx8bi5oZWFkbGluZSkrJzwvYT4nCiAgICAgICAgKyhuLnN1bW1hcnlfdHJ8fG4uc3VtbWFyeT8nPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6IzljYTNhZjttYXJnaW4tdG9wOjRweDtsaW5lLWhlaWdodDoxLjQiPicrKG4uc3VtbWFyeV90cnx8bi5zdW1tYXJ5KS5zdWJzdHJpbmcoMCwxNTApKycuLi48L2Rpdj4nOicnKSsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi10b3A6M3B4Ij4nK24uc291cmNlKyc8L2Rpdj48L2Rpdj4nOwogICAgfSk7CiAgfSBlbHNlIHsKICAgIG5ld3NIdG1sKz0nPGRpdiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtc2l6ZToxMnB4Ij5IYWJlciBidWx1bmFtYWRpPC9kaXY+JzsKICB9CiAgbmV3c0h0bWwrPSc8L2Rpdj4nOwoKICBncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JwogICAgKyc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicrbUJnKyc7Ym9yZGVyOjFweCBzb2xpZCAnK21Cb3JkZXIrJztib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47ZmxleC13cmFwOndyYXA7Z2FwOjEycHgiPicKICAgICsnPGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4O21hcmdpbi1ib3R0b206NHB4Ij5DQU5TTElNIE0gS1LEsFRFUsSwPC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyttQ29sb3IrJyI+JyttSWNvbisnICcrbUxhYmVsKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTt0ZXh0LWFsaWduOnJpZ2h0Ij5WSVg6ICcrKHZpeC5wcmljZXx8Ij8iKSsnPGJyPicKICAgICsnPHNwYW4gc3R5bGU9ImNvbG9yOicrKHZpeC5wcmljZSYmdml4LnByaWNlPjI1PyJ2YXIoLS1yZWQyKSI6InZhcigtLWdyZWVuKSIpKyciPicrKHZpeC5wcmljZSYmdml4LnByaWNlPjI1PyJZw7xrc2VrIHZvbGF0aWxpdGUiOiJOb3JtYWwgdm9sYXRpbGl0ZSIpKyc8L3NwYW4+PC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXA7bWFyZ2luLWJvdHRvbToxNHB4Ij4nK2luZGV4Q2FyZCgiUyZQIDUwMCAoU1BZKSIsc3ApK2luZGV4Q2FyZCgiTkFTREFRIChRUVEpIixuYXMpKyc8L2Rpdj4nCiAgICArcG9ydEh0bWwrZWFybmluZ3NBbGVydCtuZXdzSHRtbCsnPC9kaXY+JzsKfQoKZnVuY3Rpb24gcmVuZGVyRWFybmluZ3MoKXsKICB2YXIgZ3JpZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ3JpZCIpOwogIHZhciBzb3J0ZWQ9RUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuIGUubmV4dF9kYXRlO30pLnNvcnQoZnVuY3Rpb24oYSxiKXsKICAgIHZhciBkYT1hLmRheXNfdG9fZWFybmluZ3MhPW51bGw/YS5kYXlzX3RvX2Vhcm5pbmdzOjk5OTsKICAgIHZhciBkYj1iLmRheXNfdG9fZWFybmluZ3MhPW51bGw/Yi5kYXlzX3RvX2Vhcm5pbmdzOjk5OTsKICAgIHJldHVybiBkYS1kYjsKICB9KTsKICB2YXIgbm9EYXRlPUVBUk5JTkdTX0RBVEEuZmlsdGVyKGZ1bmN0aW9uKGUpe3JldHVybiAhZS5uZXh0X2RhdGU7fSk7CiAgaWYoIXNvcnRlZC5sZW5ndGgmJiFub0RhdGUubGVuZ3RoKXtncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMTt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjQwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5FYXJuaW5ncyB2ZXJpc2kgYnVsdW5hbWFkaTwvZGl2Pic7cmV0dXJuO30KICB2YXIgaD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKICBzb3J0ZWQuZm9yRWFjaChmdW5jdGlvbihlKXsKICAgIHZhciBhYj1lLmFsZXJ0PT09InJlZCI/InJnYmEoMjM5LDY4LDY4LC4xMikiOmUuYWxlcnQ9PT0ieWVsbG93Ij8icmdiYSgyNDUsMTU4LDExLC4xKSI6InJnYmEoMjU1LDI1NSwyNTUsLjAyKSI7CiAgICB2YXIgYWJkPWUuYWxlcnQ9PT0icmVkIj8icmdiYSgyMzksNjgsNjgsLjM1KSI6ZS5hbGVydD09PSJ5ZWxsb3ciPyJyZ2JhKDI0NSwxNTgsMTEsLjMpIjoicmdiYSgyNTUsMjU1LDI1NSwuMDcpIjsKICAgIHZhciBhaT1lLmFsZXJ0PT09InJlZCI/IvCflLQiOmUuYWxlcnQ9PT0ieWVsbG93Ij8i8J+foSI6IvCfk4UiOwogICAgdmFyIGR0PWUuZGF5c190b19lYXJuaW5ncyE9bnVsbD8oZS5kYXlzX3RvX2Vhcm5pbmdzPT09MD8iQlVHVU4iOmUuZGF5c190b19lYXJuaW5ncz09PTE/IllhcmluIjplLmRheXNfdG9fZWFybmluZ3MrIiBndW4gc29ucmEiKToiIjsKICAgIHZhciBhbUNvbD1lLmF2Z19tb3ZlX3BjdCE9bnVsbD8oZS5hdmdfbW92ZV9wY3Q+PTA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZDIpIik6InZhcigtLW11dGVkKSI7CiAgICB2YXIgYW1TdHI9ZS5hdmdfbW92ZV9wY3QhPW51bGw/KGUuYXZnX21vdmVfcGN0Pj0wPyIrIjoiIikrZS5hdmdfbW92ZV9wY3QrIiUiOiLigJQiOwogICAgdmFyIHliPWUuYWxlcnQ9PT0icmVkIj8nPHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtjb2xvcjp2YXIoLS1yZWQyKTtwYWRkaW5nOjJweCA4cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjEwcHg7Zm9udC13ZWlnaHQ6NzAwIj5ZQUtJTkRBPC9zcGFuPic6IiI7CiAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonK2FiKyc7Ym9yZGVyOjFweCBzb2xpZCAnK2FiZCsnO2JvcmRlci1yYWRpdXM6MTBweDttYXJnaW4tYm90dG9tOjEwcHg7cGFkZGluZzoxNHB4IDE2cHgiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6OHB4Ij4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjEwcHgiPjxzcGFuPicrYWkrJzwvc3Bhbj48c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyMHB4O2xldHRlci1zcGFjaW5nOjJweDtjb2xvcjp2YXIoLS10ZXh0KSI+JytlLnRpY2tlcisnPC9zcGFuPicreWIrJzwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxNnB4O2ZsZXgtd3JhcDp3cmFwO2FsaWduLWl0ZW1zOmNlbnRlciI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlJBUE9SPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjp2YXIoLS10ZXh0KSI+JysoZS5uZXh0X2RhdGV8fCLigJQiKSsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6JysoZS5hbGVydD09PSJyZWQiPyJ2YXIoLS1yZWQyKSI6ZS5hbGVydD09PSJ5ZWxsb3ciPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tbXV0ZWQpIikrJyI+JytkdCsnPC9kaXY+PC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkVQUyBUQUhNSU48L2Rpdj48ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOiM2MGE1ZmEiPicrKGUuZXBzX2VzdGltYXRlIT1udWxsPyIkIitlLmVwc19lc3RpbWF0ZToi4oCUIikrJzwvZGl2PjwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5PUlQuSEFSRUtFVDwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JythbUNvbCsnIj4nK2FtU3RyKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKSI+c29uIDQgcmFwb3I8L2Rpdj48L2Rpdj4nOwogICAgaCs9JzwvZGl2PjwvZGl2Pic7CiAgICBpZihlLmhpc3RvcnlfZXBzJiZlLmhpc3RvcnlfZXBzLmxlbmd0aCl7CiAgICAgIGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW4tdG9wOjhweDtwYWRkaW5nLXRvcDo4cHg7Ym9yZGVyLXRvcDoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjVweCI+U09OIDQgUkFQT1I8L2Rpdj48ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCg0LDFmcik7Z2FwOjRweCI+JzsKICAgICAgZS5oaXN0b3J5X2Vwcy5mb3JFYWNoKGZ1bmN0aW9uKGhoKXsKICAgICAgICB2YXIgc2M9aGguc3VycHJpc2VfcGN0IT1udWxsPyhoaC5zdXJwcmlzZV9wY3Q+MD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkMikiKToidmFyKC0tbXV0ZWQpIjsKICAgICAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6NHB4O3BhZGRpbmc6NnB4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDUpIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytoaC5kYXRlLnN1YnN0cmluZygwLDcpKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEwcHgiPicrKGhoLmFjdHVhbCE9bnVsbD8iJCIraGguYWN0dWFsOiI/IikrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6JytzYysnIj4nKyhoaC5zdXJwcmlzZV9wY3QhPW51bGw/KGhoLnN1cnByaXNlX3BjdD4wPyIrIjoiIikraGguc3VycHJpc2VfcGN0KyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nOwogICAgICB9KTsKICAgICAgaCs9JzwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBoKz0nPC9kaXY+JzsKICB9KTsKICBpZihub0RhdGUubGVuZ3RoKXtoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi10b3A6NnB4Ij5UYXJpaCBidWx1bmFtYXlhbjogJytub0RhdGUubWFwKGZ1bmN0aW9uKGUpe3JldHVybiBlLnRpY2tlcjt9KS5qb2luKCIsICIpKyc8L2Rpdj4nO30KICBoKz0nPC9kaXY+JzsKICBncmlkLmlubmVySFRNTD1oOwp9CgpmdW5jdGlvbiBvcGVuTSh0aWNrZXIpewogIHZhciByPWN1ckRhdGEuZmluZChmdW5jdGlvbihkKXtyZXR1cm4gZC50aWNrZXI9PT10aWNrZXI7fSk7CiAgaWYoIXJ8fHIuaGF0YSkgcmV0dXJuOwogIGlmKG1DaGFydCl7bUNoYXJ0LmRlc3Ryb3koKTttQ2hhcnQ9bnVsbDt9CiAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogIHZhciByclA9TWF0aC5taW4oKHIucnIvNCkqMTAwLDEwMCk7CiAgdmFyIHJyQz1yLnJyPj0zPyJ2YXIoLS1ncmVlbikiOnIucnI+PTI/InZhcigtLWdyZWVuMikiOnIucnI+PTE/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIGRjPXIuZGVnaXNpbT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICB2YXIga2M9eyJHVUNMVSBBTCI6IiMxMGI5ODEiLCJBTCI6IiMzNGQzOTkiLCJESUtLQVRMSSI6IiNmNTllMGIiLCJHRUNNRSI6IiNmODcxNzEifTsKICB2YXIga2xibD17IkdVQ0xVIEFMIjoiR1VDTFUgQUwiLCJBTCI6IkFMIiwiRElLS0FUTEkiOiJESUtLQVRMSSIsIkdFQ01FIjoiR0VDTUUifTsKICB2YXIgZXNjb2w9ci5lbnRyeV9zY29yZT49NzU/InZhcigtLWdyZWVuKSI6ci5lbnRyeV9zY29yZT49NjA/InZhcigtLWdyZWVuMikiOnIuZW50cnlfc2NvcmU+PTQ1PyJ2YXIoLS15ZWxsb3cpIjpyLmVudHJ5X3Njb3JlPj0zMD8idmFyKC0tcmVkMikiOiJ2YXIoLS1yZWQpIjsKICB2YXIgcHZjb2w9ci5wcmljZV92c19jb2xvcj09PSJncmVlbiI/InZhcigtLWdyZWVuKSI6ci5wcmljZV92c19jb2xvcj09PSJ5ZWxsb3ciPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkMikiOwoKICB2YXIgbWg9JzxkaXYgY2xhc3M9Im1oZWFkIj48ZGl2PjxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjhweDtmbGV4LXdyYXA6d3JhcCI+JwogICAgKyc8c3BhbiBjbGFzcz0ibXRpdGxlIiBzdHlsZT0iY29sb3I6Jytzcy50eCsnIj4nK3IudGlja2VyKyc8L3NwYW4+JwogICAgKyc8c3BhbiBjbGFzcz0iYmFkZ2UiIHN0eWxlPSJiYWNrZ3JvdW5kOicrc3MuYmcrJztjb2xvcjonK3NzLnR4Kyc7Ym9yZGVyOjFweCBzb2xpZCAnK3NzLmJkKyc7Zm9udC1zaXplOjEycHgiPicrc3MubGJsKyc8L3NwYW4+JwogICAgKyhyLnBvcnRmb2xpbz8nPHNwYW4gY2xhc3M9InBvcnQtYmFkZ2UiIHN0eWxlPSJmb250LXNpemU6MTFweDtwYWRkaW5nOjNweCA4cHgiPlBvcnRmb2x5bzwvc3Bhbj4nOicnKQogICAgKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC13ZWlnaHQ6NjAwO21hcmdpbi10b3A6NHB4Ij4kJytyLmZpeWF0CiAgICArJyA8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6JytkYysnIj4nKyhyLmRlZ2lzaW0+PTA/IisiOiIiKStyLmRlZ2lzaW0rJyU8L3NwYW4+PC9kaXY+PC9kaXY+JwogICAgKyc8YnV0dG9uIGNsYXNzPSJtY2xvc2UiIG9uY2xpY2s9ImNsb3NlTSgpIj7inJU8L2J1dHRvbj48L2Rpdj4nOwoKICBtaCs9JzxkaXYgY2xhc3M9Im1ib2R5Ij48ZGl2IGNsYXNzPSJtY2hhcnR3Ij48Y2FudmFzIGlkPSJtY2hhcnQiPjwvY2FudmFzPjwvZGl2Pic7CgogIG1oKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O21hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij4nK2liKCJFbnRyeVNjb3JlIiwiR2lyaXMgS2FsaXRlc2kiKSsnPC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206NnB4Ij4nCiAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X3Njb3JlKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4vMTAwPC9zcGFuPjwvc3Bhbj4nCiAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfbGFiZWwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImhlaWdodDo2cHg7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlci1yYWRpdXM6M3B4O292ZXJmbG93OmhpZGRlbjttYXJnaW4tYm90dG9tOjhweCI+PGRpdiBzdHlsZT0iaGVpZ2h0OjEwMCU7d2lkdGg6JytyLmVudHJ5X3Njb3JlKyclO2JhY2tncm91bmQ6Jytlc2NvbCsnO2JvcmRlci1yYWRpdXM6M3B4Ij48L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2Vlbjtmb250LXNpemU6MTFweCI+JwogICAgKyc8ZGl2PjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPlN1IGFua2kgZml5YXQ6IDwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6JytwdmNvbCsnO2ZvbnQtd2VpZ2h0OjYwMCI+JytyLnByaWNlX3ZzX2lkZWFsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2PjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPklkZWFsIGJvbGdlOiA8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuMik7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmlkZWFsX2VudHJ5X2xvdysnIC0gJCcrci5pZGVhbF9lbnRyeV9oaWdoKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8L2Rpdj48L2Rpdj4nOwoKICBtaCs9JzxkaXYgY2xhc3M9ImRib3giIHN0eWxlPSJiYWNrZ3JvdW5kOicrc3MuYmcrJztib3JkZXItY29sb3I6Jytzcy5iZCsnO21hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IGNsYXNzPSJkbGJsIiBzdHlsZT0iY29sb3I6Jytzcy50eCsnIj4nK2liKCJSUiIsIkFsaW0gS2FyYXJpIFIvUiIpKyc8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImR2ZXJkIiBzdHlsZT0iY29sb3I6Jysoa2Nbci5rYXJhcl18fCJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhrbGJsW3Iua2FyYXJdfHxyLmthcmFyKSsnPC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+UmlzayAvIE9kdWw8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOicrcnJDKyc7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+MSA6ICcrci5ycisnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkhlbWVuIEdpcjwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4yKTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuZW50cnlfYWdncmVzc2l2ZSsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkdlcmkgQ2VraWxtZTwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6IzYwYTVmYTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuZW50cnlfbWlkKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+QnV5dWsgRHV6ZWx0bWU8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXllbGxvdyk7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmVudHJ5X2NvbnNlcnZhdGl2ZSsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkhlZGVmPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjojNjBhNWZhO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5oZWRlZisnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPlN0b3AtTG9zczwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMik7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLnN0b3ArJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9InJyYmFyIj48ZGl2IGNsYXNzPSJycmZpbGwiIHN0eWxlPSJ3aWR0aDonK3JyUCsnJTtiYWNrZ3JvdW5kOicrcnJDKyciPjwvZGl2PjwvZGl2PjwvZGl2Pic7CgogIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+VGVrbmlrIEFuYWxpejwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGdyaWQiIHN0eWxlPSJtYXJnaW4tYm90dG9tOjEycHgiPicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJUcmVuZCIsIlRyZW5kIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci50cmVuZD09PSJZdWtzZWxlbiI/InZhcigtLWdyZWVuKSI6ci50cmVuZD09PSJEdXNlbiI/InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nK3IudHJlbmQrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJSU0kiLCJSU0kgMTQiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnJzaT9yLnJzaTwzMD8idmFyKC0tZ3JlZW4pIjpyLnJzaT43MD8idmFyKC0tcmVkKSI6InZhcigtLXllbGxvdykiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnJzaXx8Ij8iKSsoci5yc2k/ci5yc2k8MzA/IiBBc2lyaSBTYXRpbSI6ci5yc2k+NzA/IiBBc2lyaSBBbGltIjoiIE5vdHIiOiIiKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlNNQTUwIiwiU01BIDUwIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5hYm92ZTUwPyJ2YXIoLS1ncmVlbikiOiJ2YXIoLS1yZWQpIikrJyI+Jysoci5hYm92ZTUwPyJVemVyaW5kZSI6IkFsdGluZGEiKSsoci5zbWE1MF9kaXN0IT1udWxsPyIgKCIrci5zbWE1MF9kaXN0KyIlKSI6IiIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiU01BMjAwIiwiU01BIDIwMCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuYWJvdmUyMDA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZCkiKSsnIj4nKyhyLmFib3ZlMjAwPyJVemVyaW5kZSI6IkFsdGluZGEiKSsoci5zbWEyMDBfZGlzdCE9bnVsbD8iICgiK3Iuc21hMjAwX2Rpc3QrIiUpIjoiIikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCI1MlciLCI1MkggUG96LiIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIudzUyX3Bvc2l0aW9uPD0zMD8idmFyKC0tZ3JlZW4pIjpyLnc1Ml9wb3NpdGlvbj49ODU/InZhcigtLXJlZCkiOiJ2YXIoLS15ZWxsb3cpIikrJyI+JytyLnc1Ml9wb3NpdGlvbisnJTwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJIYWNpbSIsIkhhY2ltIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5oYWNpbT09PSJZdWtzZWsiPyJ2YXIoLS1ncmVlbikiOnIuaGFjaW09PT0iRHVzdWsiPyJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+JytyLmhhY2ltKycgKCcrci52b2xfcmF0aW8rJ3gpPC9kaXY+PC9kaXY+JwogICAgKyc8L2Rpdj4nOwoKICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPlRlbWVsIEFuYWxpejwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGdyaWQiIHN0eWxlPSJtYXJnaW4tYm90dG9tOjEycHgiPicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJGb3J3YXJkUEUiLCJGb3J3YXJkIFBFIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5wZV9md2Q/ci5wZV9md2Q8MjU/InZhcigtLWdyZWVuKSI6ci5wZV9md2Q8NDA/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5wZV9md2Q/ci5wZV9md2QudG9GaXhlZCgxKToiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUEVHIiwiUEVHIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5wZWc/ci5wZWc8MT8idmFyKC0tZ3JlZW4pIjpyLnBlZzwyPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucGVnP3IucGVnLnRvRml4ZWQoMik6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIkVQU0dyb3d0aCIsIkVQUyBCw7x5w7xtZSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuZXBzX2dyb3d0aD9yLmVwc19ncm93dGg+PTIwPyJ2YXIoLS1ncmVlbikiOnIuZXBzX2dyb3d0aD49MD8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLmVwc19ncm93dGghPW51bGw/ci5lcHNfZ3Jvd3RoKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUmV2R3Jvd3RoIiwiR2VsaXIgQsO8ecO8bWUiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnJldl9ncm93dGg/ci5yZXZfZ3Jvd3RoPj0xNT8idmFyKC0tZ3JlZW4pIjpyLnJldl9ncm93dGg+PTA/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5yZXZfZ3Jvd3RoIT1udWxsP3IucmV2X2dyb3d0aCsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIk5ldE1hcmdpbiIsIk5ldCBNYXJqaW4iKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLm5ldF9tYXJnaW4/ci5uZXRfbWFyZ2luPj0xNT8idmFyKC0tZ3JlZW4pIjpyLm5ldF9tYXJnaW4+PTU/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5uZXRfbWFyZ2luIT1udWxsP3IubmV0X21hcmdpbisiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlJPRSIsIlJPRSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucm9lP3Iucm9lPj0xNT8idmFyKC0tZ3JlZW4pIjpyLnJvZT49NT8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnJvZSE9bnVsbD9yLnJvZSsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8L2Rpdj4nOwoKICB2YXIgYWlUZXh0ID0gQUlfREFUQSAmJiBBSV9EQVRBW3RpY2tlcl07CiAgaWYoYWlUZXh0KXsKICAgIG1oKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDttYXJnaW4tYm90dG9tOjEycHgiPic7CiAgICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6IzYwYTVmYTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij7wn6SWIEFJIEFuYWxpeiAoQ2xhdWRlIFNvbm5ldCk8L2Rpdj4nOwogICAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS10ZXh0KTtsaW5lLWhlaWdodDoxLjc7d2hpdGUtc3BhY2U6cHJlLXdyYXAiPicrYWlUZXh0Kyc8L2Rpdj4nOwogICAgbWgrPSc8L2Rpdj4nOwogIH0KICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTt0ZXh0LWFsaWduOmNlbnRlciI+QnUgYXJhYyB5YXRpcmltIHRhdnNpeWVzaSBkZWdpbGRpcjwvZGl2PjwvZGl2Pic7CgogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtb2RhbCIpLmlubmVySFRNTD1taDsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgib3ZlcmxheSIpLmNsYXNzTGlzdC5hZGQoIm9wZW4iKTsKICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7CiAgICB2YXIgY3R4PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtY2hhcnQiKTsKICAgIGlmKGN0eCYmci5jaGFydF9jbG9zZXMpewogICAgICBtQ2hhcnQ9bmV3IENoYXJ0KGN0eCx7dHlwZToibGluZSIsZGF0YTp7bGFiZWxzOnIuY2hhcnRfZGF0ZXMsZGF0YXNldHM6WwogICAgICAgIHtsYWJlbDoiRml5YXQiLGRhdGE6ci5jaGFydF9jbG9zZXMsYm9yZGVyQ29sb3I6c3MuYWMsYm9yZGVyV2lkdGg6MixmaWxsOnRydWUsYmFja2dyb3VuZENvbG9yOnNzLmFjKyIyMCIscG9pbnRSYWRpdXM6MCx0ZW5zaW9uOjAuM30sCiAgICAgICAgci5zbWE1MD97bGFiZWw6IlNNQTUwIixkYXRhOkFycmF5KHIuY2hhcnRfY2xvc2VzLmxlbmd0aCkuZmlsbChyLnNtYTUwKSxib3JkZXJDb2xvcjoiI2Y1OWUwYiIsYm9yZGVyV2lkdGg6MS41LGJvcmRlckRhc2g6WzUsNV0scG9pbnRSYWRpdXM6MCxmaWxsOmZhbHNlfTpudWxsLAogICAgICAgIHIuc21hMjAwP3tsYWJlbDoiU01BMjAwIixkYXRhOkFycmF5KHIuY2hhcnRfY2xvc2VzLmxlbmd0aCkuZmlsbChyLnNtYTIwMCksYm9yZGVyQ29sb3I6IiM4YjVjZjYiLGJvcmRlcldpZHRoOjEuNSxib3JkZXJEYXNoOls1LDVdLHBvaW50UmFkaXVzOjAsZmlsbDpmYWxzZX06bnVsbAogICAgICBdLmZpbHRlcihCb29sZWFuKX0sb3B0aW9uczp7cmVzcG9uc2l2ZTp0cnVlLG1haW50YWluQXNwZWN0UmF0aW86ZmFsc2UsCiAgICAgICAgcGx1Z2luczp7bGVnZW5kOntsYWJlbHM6e2NvbG9yOiIjNmI3MjgwIixmb250OntzaXplOjEwfX19fSwKICAgICAgICBzY2FsZXM6e3g6e2Rpc3BsYXk6dHJ1ZSx0aWNrczp7Y29sb3I6IiMzNzQxNTEiLG1heFRpY2tzTGltaXQ6NSxmb250OntzaXplOjl9fSxncmlkOntjb2xvcjoicmdiYSgyNTUsMjU1LDI1NSwuMDQpIn19LAogICAgICAgICAgeTp7ZGlzcGxheTp0cnVlLHRpY2tzOntjb2xvcjoiIzM3NDE1MSIsZm9udDp7c2l6ZTo5fX0sZ3JpZDp7Y29sb3I6InJnYmEoMjU1LDI1NSwyNTUsLjA0KSJ9fX19fSk7CiAgICB9CiAgfSwxMDApOwp9CgoKLy8g4pSA4pSAIEfDnE5Mw5xLIFJVVMSwTiDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAKdmFyIFJVVElOX0lURU1TID0gewogIHNhYmFoOiB7CiAgICBsYWJlbDogIvCfjIUgU2FiYWgg4oCUIFBpeWFzYSBBw6fEsWxtYWRhbiDDlm5jZSIsCiAgICBpdGVtczogWwogICAgICB7aWQ6InMxIiwgdGV4dDoiRGFzaGJvYXJkxLEgYcOnIOKAlCBNIGtyaXRlcmkgeWXFn2lsIG1pPyAoUyZQNTAwICsgTkFTREFRIFNNQTIwMCDDvHN0w7xuZGUpIn0sCiAgICAgIHtpZDoiczIiLCB0ZXh0OiJFYXJuaW5ncyBzZWttZXNpbmkga29udHJvbCBldCDigJQgYnVnw7xuL2J1IGhhZnRhIHJhcG9yIHZhciBtxLE/In0sCiAgICAgIHtpZDoiczMiLCB0ZXh0OiJWSVggMjUgYWx0xLFuZGEgbcSxPyAoWcO8a3Nla3NlIHllbmkgcG96aXN5b24gYcOnbWEpIn0sCiAgICAgIHtpZDoiczQiLCB0ZXh0OiLDlm5jZWtpIGfDvG5kZW4gYmVrbGV5ZW4gYWxhcm0gbWFpbGkgdmFyIG3EsT8ifQogICAgXQogIH0sCiAgb2dsZW46IHsKICAgIGxhYmVsOiAi8J+TiiDDlsSfbGVkZW4gU29ucmEg4oCUIFBpeWFzYSBBw6fEsWtrZW4iLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJvMSIsIHRleHQ6IlBvcnRmw7Z5w7xtIHNla21lc2luZGUgaGlzc2VsZXJpbWUgYmFrIOKAlCBiZWtsZW5tZWRpayBkw7zFn8O8xZ8gdmFyIG3EsT8ifSwKICAgICAge2lkOiJvMiIsIHRleHQ6IlN0b3Agc2V2aXllc2luZSB5YWtsYcWfYW4gaGlzc2UgdmFyIG3EsT8gKEvEsXJtxLF6xLEgacWfYXJldCkifSwKICAgICAge2lkOiJvMyIsIHRleHQ6IkFsIHNpbnlhbGkgc2VrbWVzaW5kZSB5ZW5pIGbEsXJzYXQgw6fEsWttxLHFnyBtxLE/In0sCiAgICAgIHtpZDoibzQiLCB0ZXh0OiJXYXRjaGxpc3R0ZWtpIGhpc3NlbGVyZGUgZ2lyacWfIGthbGl0ZXNpIDYwKyBvbGFuIHZhciBtxLE/In0sCiAgICAgIHtpZDoibzUiLCB0ZXh0OiJIYWJlcmxlcmRlIHBvcnRmw7Z5w7xtw7wgZXRraWxleWVuIMO2bmVtbGkgZ2VsacWfbWUgdmFyIG3EsT8ifQogICAgXQogIH0sCiAgYWtzYW06IHsKICAgIGxhYmVsOiAi8J+MmSBBa8WfYW0g4oCUIFBpeWFzYSBLYXBhbmTEsWt0YW4gU29ucmEiLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJhMSIsIHRleHQ6IjFIIHNpbnlhbGxlcmluaSBrb250cm9sIGV0IOKAlCBoYWZ0YWzEsWsgdHJlbmQgZGXEn2nFn21pxZ8gbWk/In0sCiAgICAgIHtpZDoiYTIiLCB0ZXh0OiJZYXLEsW4gacOnaW4gcG90YW5zaXllbCBnaXJpxZ8gbm9rdGFsYXLEsW7EsSBub3QgYWwifSwKICAgICAge2lkOiJhMyIsIHRleHQ6IlBvcnRmw7Z5ZGVraSBoZXIgaGlzc2VuaW4gc3RvcCBzZXZpeWVzaW5pIGfDtnpkZW4gZ2XDp2lyIn0sCiAgICAgIHtpZDoiYTQiLCB0ZXh0OiJZYXLEsW4gcmFwb3IgYcOnxLFrbGF5YWNhayBoaXNzZSB2YXIgbcSxPyAoRWFybmluZ3Mgc2VrbWVzaSkifQogICAgXQogIH0sCiAgaGFmdGFsaWs6IHsKICAgIGxhYmVsOiAi8J+ThSBIYWZ0YWzEsWsg4oCUIFBhemFyIEFrxZ9hbcSxIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoiaDEiLCB0ZXh0OiJTdG9jayBSb3ZlcmRhIENBTlNMSU0gc2NyZWVuZXLEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoMiIsIHRleHQ6IlZDUCBNaW5lcnZpbmkgc2NyZWVuZXLEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoMyIsIHRleHQ6IlF1bGxhbWFnZ2llIEJyZWFrb3V0IHNjcmVlbmVyxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDQiLCB0ZXh0OiJGaW52aXpkZSBJbnN0aXR1dGlvbmFsIEJ1eWluZyBzY3JlZW5lcsSxIMOnYWzEscWfdMSxciJ9LAogICAgICB7aWQ6Img1IiwgdGV4dDoiw4dha8SxxZ9hbiBoaXNzZWxlcmkgYnVsIOKAlCBlbiBnw7zDp2zDvCBhZGF5bGFyIn0sCiAgICAgIHtpZDoiaDYiLCB0ZXh0OiJHaXRIdWIgQWN0aW9uc2RhbiBSdW4gV29ya2Zsb3cgYmFzIOKAlCBzaXRlIGfDvG5jZWxsZW5pciJ9LAogICAgICB7aWQ6Img3IiwgdGV4dDoiR2VsZWNlayBoYWZ0YW7EsW4gZWFybmluZ3MgdGFrdmltaW5pIGtvbnRyb2wgZXQifSwKICAgICAge2lkOiJoOCIsIHRleHQ6IlBvcnRmw7Z5IGdlbmVsIGRlxJ9lcmxlbmRpcm1lc2kg4oCUIGhlZGVmbGVyIGhhbGEgZ2XDp2VybGkgbWk/In0KICAgIF0KICB9Cn07CgpmdW5jdGlvbiBnZXRUb2RheUtleSgpewogIHJldHVybiBuZXcgRGF0ZSgpLnRvRGF0ZVN0cmluZygpOwp9CgpmdW5jdGlvbiBsb2FkQ2hlY2tlZCgpewogIHRyeXsKICAgIHZhciBkYXRhID0gbG9jYWxTdG9yYWdlLmdldEl0ZW0oJ3J1dGluX2NoZWNrZWQnKTsKICAgIGlmKCFkYXRhKSByZXR1cm4ge307CiAgICB2YXIgcGFyc2VkID0gSlNPTi5wYXJzZShkYXRhKTsKICAgIC8vIFNhZGVjZSBidWfDvG7DvG4gdmVyaWxlcmluaSBrdWxsYW4KICAgIGlmKHBhcnNlZC5kYXRlICE9PSBnZXRUb2RheUtleSgpKSByZXR1cm4ge307CiAgICByZXR1cm4gcGFyc2VkLml0ZW1zIHx8IHt9OwogIH1jYXRjaChlKXtyZXR1cm4ge307fQp9CgpmdW5jdGlvbiBzYXZlQ2hlY2tlZChjaGVja2VkKXsKICBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgncnV0aW5fY2hlY2tlZCcsIEpTT04uc3RyaW5naWZ5KHsKICAgIGRhdGU6IGdldFRvZGF5S2V5KCksCiAgICBpdGVtczogY2hlY2tlZAogIH0pKTsKfQoKZnVuY3Rpb24gdG9nZ2xlQ2hlY2soaWQpewogIHZhciBjaGVja2VkID0gbG9hZENoZWNrZWQoKTsKICBpZihjaGVja2VkW2lkXSkgZGVsZXRlIGNoZWNrZWRbaWRdOwogIGVsc2UgY2hlY2tlZFtpZF0gPSB0cnVlOwogIHNhdmVDaGVja2VkKGNoZWNrZWQpOwogIHJlbmRlclJ1dGluKCk7Cn0KCmZ1bmN0aW9uIHJlc2V0UnV0aW4oKXsKICBsb2NhbFN0b3JhZ2UucmVtb3ZlSXRlbSgncnV0aW5fY2hlY2tlZCcpOwogIHJlbmRlclJ1dGluKCk7Cn0KCgpmdW5jdGlvbiByZW5kZXJIYWZ0YWxpaygpewogIHZhciBncmlkID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dyaWQnKTsKICB2YXIgd2QgPSBXRUVLTFlfREFUQSB8fCB7fTsKICB2YXIgcG9ydCA9IHdkLnBvcnRmb2xpbyB8fCBbXTsKICB2YXIgd2F0Y2ggPSB3ZC53YXRjaGxpc3QgfHwgW107CiAgdmFyIGJlc3QgPSB3ZC5iZXN0OwogIHZhciB3b3JzdCA9IHdkLndvcnN0OwogIHZhciBtZCA9IE1BUktFVF9EQVRBIHx8IHt9OwogIHZhciBzcCA9IG1kLlNQNTAwIHx8IHt9OwogIHZhciBuYXMgPSBtZC5OQVNEQVEgfHwge307CgogIGZ1bmN0aW9uIGNoZ0NvbG9yKHYpeyByZXR1cm4gdiA+PSAwID8gJ3ZhcigtLWdyZWVuKScgOiAndmFyKC0tcmVkMiknOyB9CiAgZnVuY3Rpb24gY2hnU3RyKHYpeyByZXR1cm4gKHYgPj0gMCA/ICcrJyA6ICcnKSArIHYgKyAnJSc7IH0KCiAgZnVuY3Rpb24gcGVyZkNhcmQoaXRlbSl7CiAgICB2YXIgY2MgPSBjaGdDb2xvcihpdGVtLndlZWtfY2hnKTsKICAgIHZhciBwYiA9IGl0ZW0ucG9ydGZvbGlvID8gJzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTIpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMjUpO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMDttYXJnaW4tbGVmdDo0cHgiPlA8L3NwYW4+JyA6ICcnOwogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxMnB4O2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbTo2cHgiPicKICAgICAgKyAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4Ij48c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToxNnB4O2xldHRlci1zcGFjaW5nOjJweCI+JyArIGl0ZW0udGlja2VyICsgJzwvc3Bhbj4nICsgcGIgKyAnPC9kaXY+JwogICAgICArICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGNjICsgJyI+JyArIGNoZ1N0cihpdGVtLndlZWtfY2hnKSArICc8L2Rpdj4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj7Dlm5jZWtpOiAnICsgY2hnU3RyKGl0ZW0ucHJldl93ZWVrX2NoZykgKyAnPC9kaXY+JwogICAgICArICc8L2Rpdj48L2Rpdj4nOwogIH0KCiAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgLy8gSGVhZGVyCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KTttYXJnaW4tYm90dG9tOjRweCI+8J+TiCBIYWZ0YWzEsWsgUGVyZm9ybWFucyDDlnpldGk8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JyArICh3ZC5nZW5lcmF0ZWQgfHwgJycpICsgJzwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gUGl5YXNhIHZzIFBvcnRmw7Z5CiAgdmFyIHNwQ2hnID0gc3AuY2hhbmdlIHx8IDA7CiAgdmFyIG5hc0NoZyA9IG5hcy5jaGFuZ2UgfHwgMDsKICB2YXIgcG9ydEF2ZyA9IHBvcnQubGVuZ3RoID8gTWF0aC5yb3VuZChwb3J0LnJlZHVjZShmdW5jdGlvbihhLGIpe3JldHVybiBhK2Iud2Vla19jaGc7fSwwKS9wb3J0Lmxlbmd0aCoxMDApLzEwMCA6IDA7CiAgdmFyIGFscGhhID0gTWF0aC5yb3VuZCgocG9ydEF2ZyAtIHNwQ2hnKSoxMDApLzEwMDsKICB2YXIgYWxwaGFDb2wgPSBhbHBoYSA+PSAwID8gJ3ZhcigtLWdyZWVuKScgOiAndmFyKC0tcmVkMiknOwoKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDE0MHB4LDFmcikpO2dhcDoxMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5Qb3J0ZsO2eSBPcnQuPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicgKyBjaGdDb2xvcihwb3J0QXZnKSArICciPicgKyBjaGdTdHIocG9ydEF2ZykgKyAnPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5TJlAgNTAwPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicgKyBjaGdDb2xvcihzcENoZykgKyAnIj4nICsgY2hnU3RyKHNwQ2hnKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPk5BU0RBUTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonICsgY2hnQ29sb3IobmFzQ2hnKSArICciPicgKyBjaGdTdHIobmFzQ2hnKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JyArIChhbHBoYT49MD8ncmdiYSgxNiwxODUsMTI5LC4wOCknOidyZ2JhKDIzOSw2OCw2OCwuMDgpJykgKyAnO2JvcmRlcjoxcHggc29saWQgJyArIChhbHBoYT49MD8ncmdiYSgxNiwxODUsMTI5LC4yNSknOidyZ2JhKDIzOSw2OCw2OCwuMjUpJykgKyAnO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5BbHBoYSAodnMgUyZQKTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonICsgYWxwaGFDb2wgKyAnIj4nICsgKGFscGhhPj0wPycrJzonJykgKyBhbHBoYSArICclPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBFbiBpeWkgLyBlbiBrw7Z0w7wKICBpZihiZXN0IHx8IHdvcnN0KXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyIDFmcjtnYXA6MTBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgICBpZihiZXN0KXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tZ3JlZW4pO21hcmdpbi1ib3R0b206NnB4Ij7wn4+GIEJ1IEhhZnRhbsSxbiBFbiDEsHlpc2k8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjI0cHg7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgYmVzdC50aWNrZXIgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPisnICsgYmVzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGlmKHdvcnN0KXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLXJlZDIpO21hcmdpbi1ib3R0b206NnB4Ij7wn5OJIEJ1IEhhZnRhbsSxbiBFbiBLw7Z0w7xzw7w8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjI0cHg7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgd29yc3QudGlja2VyICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicgKyB3b3JzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBQb3J0ZsO2eSBkZXRheQogIGlmKHBvcnQubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkrwgUG9ydGbDtnk8L2Rpdj4nOwogICAgcG9ydC5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0peyBoICs9IHBlcmZDYXJkKGl0ZW0pOyB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBTaW55YWxsZXIgb3pldGkKICB2YXIgYnV5Q291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nR1VDTFUgQUwnfHxyLnNpbnlhbD09PSdBTCc7fSkubGVuZ3RoOwogIHZhciBzZWxsQ291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nU0FUJzt9KS5sZW5ndGg7CiAgdmFyIHdhdGNoQ291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nRElLS0FUJzt9KS5sZW5ndGg7CgogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5OKIEJ1IEhhZnRha2kgU2lueWFsbGVyPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXAiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicgKyBidXlDb3VudCArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkFsIFNpbnlhbGk8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0teWVsbG93KSI+JyArIHdhdGNoQ291bnQgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5EaWtrYXQ8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nICsgc2VsbENvdW50ICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+U2F0IFNpbnlhbGk8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzwvZGl2PjwvZGl2Pic7CgogIC8vIFdhdGNobGlzdCBwZXJmb3JtYW5zCiAgaWYod2F0Y2gubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkYEgV2F0Y2hsaXN0PC9kaXY+JzsKICAgIHdhdGNoLmZvckVhY2goZnVuY3Rpb24oaXRlbSl7IGggKz0gcGVyZkNhcmQoaXRlbSk7IH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIGggKz0gJzwvZGl2Pic7CiAgZ3JpZC5pbm5lckhUTUwgPSBoOwp9CgoKZnVuY3Rpb24gcmVuZGVyUnV0aW4oKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgdmFyIGNoZWNrZWQgPSBsb2FkQ2hlY2tlZCgpOwogIHZhciB0b2RheSA9IG5ldyBEYXRlKCk7CiAgdmFyIGlzV2Vla2VuZCA9IHRvZGF5LmdldERheSgpID09PSAwIHx8IHRvZGF5LmdldERheSgpID09PSA2OwogIHZhciBkYXlOYW1lID0gWydQYXphcicsJ1BhemFydGVzaScsJ1NhbMSxJywnw4dhcsWfYW1iYScsJ1BlcsWfZW1iZScsJ0N1bWEnLCdDdW1hcnRlc2knXVt0b2RheS5nZXREYXkoKV07CiAgdmFyIGRhdGVTdHIgPSB0b2RheS50b0xvY2FsZURhdGVTdHJpbmcoJ3RyLVRSJywge2RheTonbnVtZXJpYycsbW9udGg6J2xvbmcnLHllYXI6J251bWVyaWMnfSk7CgogIC8vIFByb2dyZXNzIGhlc2FwbGEKICB2YXIgdG90YWxJdGVtcyA9IDA7CiAgdmFyIGRvbmVJdGVtcyA9IDA7CiAgdmFyIHNlY3Rpb25zID0gaXNXZWVrZW5kID8gWydoYWZ0YWxpayddIDogWydzYWJhaCcsJ29nbGVuJywnYWtzYW0nXTsKICBzZWN0aW9ucy5mb3JFYWNoKGZ1bmN0aW9uKGspewogICAgUlVUSU5fSVRFTVNba10uaXRlbXMuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsKICAgICAgdG90YWxJdGVtcysrOwogICAgICBpZihjaGVja2VkW2l0ZW0uaWRdKSBkb25lSXRlbXMrKzsKICAgIH0pOwogIH0pOwogIHZhciBwY3QgPSB0b3RhbEl0ZW1zID4gMCA/IE1hdGgucm91bmQoZG9uZUl0ZW1zL3RvdGFsSXRlbXMqMTAwKSA6IDA7CiAgdmFyIHBjdENvbCA9IHBjdD09PTEwMD8ndmFyKC0tZ3JlZW4pJzpwY3Q+PTUwPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tbXV0ZWQpJzsKCiAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgLy8gSGVhZGVyCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7ZmxleC13cmFwOndyYXA7Z2FwOjEwcHgiPic7CiAgaCArPSAnPGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrZGF5TmFtZSsnIFJ1dGluaTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK2RhdGVTdHIrJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjhweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JytwY3RDb2wrJyI+JytwY3QrJyU8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+Jytkb25lSXRlbXMrJy8nK3RvdGFsSXRlbXMrJyB0YW1hbWxhbmTEsTwvZGl2PjwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iaGVpZ2h0OjZweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czozcHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi10b3A6MTJweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJoZWlnaHQ6MTAwJTt3aWR0aDonK3BjdCsnJTtiYWNrZ3JvdW5kOicrcGN0Q29sKyc7Ym9yZGVyLXJhZGl1czozcHg7dHJhbnNpdGlvbjp3aWR0aCAuNXMgZWFzZSI+PC9kaXY+PC9kaXY+JzsKICBpZihwY3Q9PT0xMDApIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyO21hcmdpbi10b3A6MTBweDtmb250LXNpemU6MTRweDtjb2xvcjp2YXIoLS1ncmVlbikiPvCfjokgVMO8bSBtYWRkZWxlciB0YW1hbWxhbmTEsSE8L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIFNlY3Rpb25zCiAgc2VjdGlvbnMuZm9yRWFjaChmdW5jdGlvbihrKXsKICAgIHZhciBzZWMgPSBSVVRJTl9JVEVNU1trXTsKICAgIHZhciBzZWNEb25lID0gc2VjLml0ZW1zLmZpbHRlcihmdW5jdGlvbihpKXtyZXR1cm4gY2hlY2tlZFtpLmlkXTt9KS5sZW5ndGg7CiAgICB2YXIgc2VjVG90YWwgPSBzZWMuaXRlbXMubGVuZ3RoOwogICAgdmFyIHNlY1BjdCA9IE1hdGgucm91bmQoc2VjRG9uZS9zZWNUb3RhbCoxMDApOwogICAgdmFyIHNlY0NvbCA9IHNlY1BjdD09PTEwMD8ndmFyKC0tZ3JlZW4pJzpzZWNQY3Q+MD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLW11dGVkKSc7CgogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjEycHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrc2VjLmxhYmVsKyc8L2Rpdj4nOwogICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOicrc2VjQ29sKyc7Zm9udC13ZWlnaHQ6NjAwIj4nK3NlY0RvbmUrJy8nK3NlY1RvdGFsKyc8L3NwYW4+PC9kaXY+JzsKCiAgICBzZWMuaXRlbXMuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsKICAgICAgdmFyIGRvbmUgPSAhIWNoZWNrZWRbaXRlbS5pZF07CiAgICAgIHZhciBiZ0NvbG9yID0gZG9uZSA/ICdyZ2JhKDE2LDE4NSwxMjksLjA2KScgOiAncmdiYSgyNTUsMjU1LDI1NSwuMDIpJzsKICAgICAgdmFyIGJvcmRlckNvbG9yID0gZG9uZSA/ICdyZ2JhKDE2LDE4NSwxMjksLjIpJyA6ICdyZ2JhKDI1NSwyNTUsMjU1LC4wNSknOwogICAgICB2YXIgY2hlY2tCb3JkZXIgPSBkb25lID8gJ3ZhcigtLWdyZWVuKScgOiAndmFyKC0tbXV0ZWQpJzsKICAgICAgdmFyIGNoZWNrQmcgPSBkb25lID8gJ3ZhcigtLWdyZWVuKScgOiAndHJhbnNwYXJlbnQnOwogICAgICB2YXIgdGV4dENvbG9yID0gZG9uZSA/ICd2YXIoLS1tdXRlZCknIDogJ3ZhcigtLXRleHQpJzsKICAgICAgdmFyIHRleHREZWNvID0gZG9uZSA/ICdsaW5lLXRocm91Z2gnIDogJ25vbmUnOwogICAgICB2YXIgY2hlY2ttYXJrID0gZG9uZSA/ICc8c3ZnIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cG9seWxpbmUgcG9pbnRzPSIyLDYgNSw5IDEwLDMiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+PC9zdmc+JyA6ICcnOwogICAgICBoICs9ICc8ZGl2IG9uY2xpY2s9InRvZ2dsZUNoZWNrKFwnJyArIGl0ZW0uaWQgKyAnXCcpIiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmZsZXgtc3RhcnQ7Z2FwOjEycHg7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6OHB4O2N1cnNvcjpwb2ludGVyO21hcmdpbi1ib3R0b206NnB4O2JhY2tncm91bmQ6JyArIGJnQ29sb3IgKyAnO2JvcmRlcjoxcHggc29saWQgJyArIGJvcmRlckNvbG9yICsgJyI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZmxleC1zaHJpbms6MDt3aWR0aDoyMHB4O2hlaWdodDoyMHB4O2JvcmRlci1yYWRpdXM6NXB4O2JvcmRlcjoycHggc29saWQgJyArIGNoZWNrQm9yZGVyICsgJztiYWNrZ3JvdW5kOicgKyBjaGVja0JnICsgJztkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7bWFyZ2luLXRvcDoxcHgiPicgKyBjaGVja21hcmsgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2NvbG9yOicgKyB0ZXh0Q29sb3IgKyAnO2xpbmUtaGVpZ2h0OjEuNTt0ZXh0LWRlY29yYXRpb246JyArIHRleHREZWNvICsgJyI+JyArIGl0ZW0udGV4dCArICc8L3NwYW4+JzsKICAgICAgaCArPSAnPC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9KTsKCiAgLy8gSGFmdGEgacOnaSBvbGR1xJ91bmRhIGhhZnRhbMSxayBiw7Zsw7xtw7wgZGUgZ8O2c3RlciAoa2F0bGFuYWJpbGlyKQogIGlmKCFpc1dlZWtlbmQpewogICAgdmFyIGhTZWMgPSBSVVRJTl9JVEVNU1snaGFmdGFsaWsnXTsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wNCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjE1KTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOiM2MGE1ZmE7bWFyZ2luLWJvdHRvbTo0cHgiPicraFNlYy5sYWJlbCsnPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+UGF6YXIgYWvFn2FtxLEgeWFwxLFsYWNha2xhciDigJQgxZ91IGFuIGfDtnN0ZXJpbSBtb2R1bmRhPC9kaXY+PC9kaXY+JzsKICB9CgogIC8vIFJlc2V0IGJ1dG9udQogIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyO21hcmdpbi10b3A6NnB4Ij4nOwogIGggKz0gJzxidXR0b24gb25jbGljaz0icmVzZXRSdXRpbigpIiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS1tdXRlZCk7cGFkZGluZzo4cHggMTZweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTJweDtjdXJzb3I6cG9pbnRlciI+8J+UhCBMaXN0ZXlpIFPEsWbEsXJsYTwvYnV0dG9uPic7CiAgaCArPSAnPC9kaXY+JzsKCiAgaCArPSAnPC9kaXY+JzsKICBncmlkLmlubmVySFRNTCA9IGg7Cn0KCgpmdW5jdGlvbiBjbG9zZU0oZSl7CiAgaWYoIWV8fGUudGFyZ2V0PT09ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm92ZXJsYXkiKSl7CiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgib3ZlcmxheSIpLmNsYXNzTGlzdC5yZW1vdmUoIm9wZW4iKTsKICAgIGlmKG1DaGFydCl7bUNoYXJ0LmRlc3Ryb3koKTttQ2hhcnQ9bnVsbDt9CiAgfQp9CgpyZW5kZXJTdGF0cygpOwpyZW5kZXJEYXNoYm9hcmQoKTsKCgoKLy8g4pSA4pSAIEzEsFNURSBEw5xaRU5MRU1FIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgAp2YXIgZWRpdFdhdGNobGlzdCA9IFtdOwp2YXIgZWRpdFBvcnRmb2xpbyA9IFtdOwoKZnVuY3Rpb24gb3BlbkVkaXRMaXN0KCl7CiAgZWRpdFdhdGNobGlzdCA9IFRGX0RBVEFbJzFkJ10uZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pLm1hcChmdW5jdGlvbihyKXtyZXR1cm4gci50aWNrZXI7fSk7CiAgZWRpdFBvcnRmb2xpbyA9IFBPUlQuc2xpY2UoKTsKICByZW5kZXJFZGl0TGlzdHMoKTsKICAvLyBMb2FkIHNhdmVkIHRva2VuIGZyb20gbG9jYWxTdG9yYWdlCiAgdmFyIHNhdmVkID0gbG9jYWxTdG9yYWdlLmdldEl0ZW0oJ2doX3Rva2VuJyk7CiAgaWYoc2F2ZWQpIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZSA9IHNhdmVkOwogIHZhciB0cz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidG9rZW5TZWN0aW9uIik7IGlmKHRzKSB0cy5zdHlsZS5kaXNwbGF5PSJub25lIjsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFBvcHVwIikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwp9CgoKZnVuY3Rpb24gdG9nZ2xlVG9rZW5TZWN0aW9uKCl7CiAgdmFyIHM9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInRva2VuU2VjdGlvbiIpOwogIGlmKHMpIHMuc3R5bGUuZGlzcGxheT1zLnN0eWxlLmRpc3BsYXk9PT0ibm9uZSI/ImJsb2NrIjoibm9uZSI7Cn0KCmZ1bmN0aW9uIHNhdmVUb2tlbigpewogIHZhciB0PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZS50cmltKCk7CiAgaWYoIXQpe2FsZXJ0KCJUb2tlbiBib3MhIik7cmV0dXJuO30KICBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgiZ2hfdG9rZW4iLHQpOwogIHZhciB0cz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidG9rZW5TZWN0aW9uIik7IGlmKHRzKSB0cy5zdHlsZS5kaXNwbGF5PSJub25lIjsKICBzZXRFZGl0U3RhdHVzKCLinIUgVG9rZW4ga2F5ZGVkaWxkaSIsImdyZWVuIik7Cn0KCmZ1bmN0aW9uIGNsb3NlRWRpdFBvcHVwKGUpewogIGlmKCFlfHxlLnRhcmdldD09PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0UG9wdXAiKSl7CiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFBvcHVwIikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpOwogIH0KfQoKZnVuY3Rpb24gcmVuZGVyRWRpdExpc3RzKCl7CiAgdmFyIHdlID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIndhdGNobGlzdEVkaXRvciIpOwogIHZhciBwZSA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJwb3J0Zm9saW9FZGl0b3IiKTsKICBpZighd2V8fCFwZSkgcmV0dXJuOwoKICB3ZS5pbm5lckhUTUwgPSBlZGl0V2F0Y2hsaXN0Lm1hcChmdW5jdGlvbih0LGkpewogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO3BhZGRpbmc6NXB4IDhweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6NXB4O21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo2MDAiPicrdCsnPC9zcGFuPicKICAgICAgKyc8YnV0dG9uIGNsYXNzPSJybS13YXRjaC1idG4iIGRhdGEtaWR4PSInK2krJyIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtib3JkZXI6bm9uZTtjb2xvcjp2YXIoLS1yZWQyKTt3aWR0aDoyMHB4O2hlaWdodDoyMHB4O2JvcmRlci1yYWRpdXM6NHB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxMnB4Ij7inJU8L2J1dHRvbj4nCiAgICAgICsnPC9kaXY+JzsKICB9KS5qb2luKCcnKTsKCiAgLy8gQWRkIGNsaWNrIGhhbmRsZXJzCiAgc2V0VGltZW91dChmdW5jdGlvbigpewogICAgZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbCgnLnJtLXdhdGNoLWJ0bicpLmZvckVhY2goZnVuY3Rpb24oYnRuKXsKICAgICAgYnRuLm9uY2xpY2s9ZnVuY3Rpb24oKXtyZW1vdmVUaWNrZXIoJ3dhdGNoJywrdGhpcy5kYXRhc2V0LmlkeCk7fTsKICAgIH0pOwogICAgZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbCgnLnJtLXBvcnQtYnRuJykuZm9yRWFjaChmdW5jdGlvbihidG4pewogICAgICBidG4ub25jbGljaz1mdW5jdGlvbigpe3JlbW92ZVRpY2tlcigncG9ydCcsK3RoaXMuZGF0YXNldC5pZHgpO307CiAgICB9KTsKICB9LDApOwogIHBlLmlubmVySFRNTCA9IGVkaXRQb3J0Zm9saW8ubWFwKGZ1bmN0aW9uKHQsaSl7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47cGFkZGluZzo1cHggOHB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo1cHg7bWFyZ2luLWJvdHRvbTo0cHgiPicKICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicrdCsnPC9zcGFuPicKICAgICAgKyc8YnV0dG9uIGNsYXNzPSJybS1wb3J0LWJ0biIgZGF0YS1pZHg9IicraSsnIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMTUpO2JvcmRlcjpub25lO2NvbG9yOnZhcigtLXJlZDIpO3dpZHRoOjIwcHg7aGVpZ2h0OjIwcHg7Ym9yZGVyLXJhZGl1czo0cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEycHgiPuKclTwvYnV0dG9uPicKICAgICAgKyc8L2Rpdj4nOwogIH0pLmpvaW4oJycpOwp9CgpmdW5jdGlvbiBhZGRUaWNrZXIobGlzdCl7CiAgdmFyIGlucHV0SWQgPSBsaXN0PT09J3dhdGNoJz8ibmV3V2F0Y2hUaWNrZXIiOiJuZXdQb3J0VGlja2VyIjsKICB2YXIgdmFsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoaW5wdXRJZCkudmFsdWUudHJpbSgpLnRvVXBwZXJDYXNlKCk7CiAgaWYoIXZhbCkgcmV0dXJuOwogIGlmKGxpc3Q9PT0nd2F0Y2gnICYmICFlZGl0V2F0Y2hsaXN0LmluY2x1ZGVzKHZhbCkpIGVkaXRXYXRjaGxpc3QucHVzaCh2YWwpOwogIGlmKGxpc3Q9PT0ncG9ydCcgICYmICFlZGl0UG9ydGZvbGlvLmluY2x1ZGVzKHZhbCkpIGVkaXRQb3J0Zm9saW8ucHVzaCh2YWwpOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKGlucHV0SWQpLnZhbHVlID0gIiI7CiAgcmVuZGVyRWRpdExpc3RzKCk7Cn0KCmZ1bmN0aW9uIHJlbW92ZVRpY2tlcihsaXN0LCBpZHgpewogIGlmKGxpc3Q9PT0nd2F0Y2gnKSBlZGl0V2F0Y2hsaXN0LnNwbGljZShpZHgsMSk7CiAgZWxzZSBlZGl0UG9ydGZvbGlvLnNwbGljZShpZHgsMSk7CiAgcmVuZGVyRWRpdExpc3RzKCk7Cn0KCmZ1bmN0aW9uIHNhdmVMaXN0VG9HaXRodWIoKXsKICB2YXIgdG9rZW4gPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ2hUb2tlbklucHV0IikudmFsdWUudHJpbSgpOwogIGlmKCF0b2tlbil7IHNldEVkaXRTdGF0dXMoIuKdjCBUb2tlbiBnZXJla2xpIOKAlCBrdXR1eWEgZ2lyIiwicmVkIik7IHJldHVybjsgfQogIGxvY2FsU3RvcmFnZS5zZXRJdGVtKCdnaF90b2tlbicsIHRva2VuKTsKCiAgdmFyIGNvbmZpZyA9IHsgd2F0Y2hsaXN0OiBlZGl0V2F0Y2hsaXN0LCBwb3J0Zm9saW86IGVkaXRQb3J0Zm9saW8gfTsKICB2YXIgY29udGVudCA9IEpTT04uc3RyaW5naWZ5KGNvbmZpZywgbnVsbCwgMik7CiAgdmFyIGI2NCA9IGJ0b2EodW5lc2NhcGUoZW5jb2RlVVJJQ29tcG9uZW50KGNvbnRlbnQpKSk7CgogIHNldEVkaXRTdGF0dXMoIvCfkr4gS2F5ZGVkaWxpeW9yLi4uIiwieWVsbG93Iik7CgogIHZhciBhcGlVcmwgPSAiaHR0cHM6Ly9hcGkuZ2l0aHViLmNvbS9yZXBvcy9naHVyenp6L2NhbnNsaW0vY29udGVudHMvY29uZmlnLmpzb24iOwogIHZhciBoZWFkZXJzID0geyJBdXRob3JpemF0aW9uIjoidG9rZW4gIit0b2tlbiwiQ29udGVudC1UeXBlIjoiYXBwbGljYXRpb24vanNvbiJ9OwoKICAvLyBGaXJzdCBnZXQgY3VycmVudCBTSEEgaWYgZXhpc3RzCiAgZmV0Y2goYXBpVXJsLCB7aGVhZGVyczpoZWFkZXJzfSkKICAgIC50aGVuKGZ1bmN0aW9uKHIpeyByZXR1cm4gci5vayA/IHIuanNvbigpIDogbnVsbDsgfSkKICAgIC50aGVuKGZ1bmN0aW9uKGV4aXN0aW5nKXsKICAgICAgdmFyIHBheWxvYWQgPSB7CiAgICAgICAgbWVzc2FnZTogIkxpc3RlIGd1bmNlbGxlbmRpICIgKyBuZXcgRGF0ZSgpLnRvTG9jYWxlRGF0ZVN0cmluZygidHItVFIiKSwKICAgICAgICBjb250ZW50OiBiNjQKICAgICAgfTsKICAgICAgaWYoZXhpc3RpbmcgJiYgZXhpc3Rpbmcuc2hhKSBwYXlsb2FkLnNoYSA9IGV4aXN0aW5nLnNoYTsKCiAgICAgIHJldHVybiBmZXRjaChhcGlVcmwsIHsKICAgICAgICBtZXRob2Q6IlBVVCIsCiAgICAgICAgaGVhZGVyczpoZWFkZXJzLAogICAgICAgIGJvZHk6SlNPTi5zdHJpbmdpZnkocGF5bG9hZCkKICAgICAgfSk7CiAgICB9KQogICAgLnRoZW4oZnVuY3Rpb24ocil7CiAgICAgIGlmKHIub2sgfHwgci5zdGF0dXM9PT0yMDEpewogICAgICAgIHNldEVkaXRTdGF0dXMoIuKchSBLYXlkZWRpbGRpISBCaXIgc29ucmFraSBDb2xhYiDDp2FsxLHFn3TEsXJtYXPEsW5kYSBha3RpZiBvbHVyLiIsImdyZWVuIik7CiAgICAgICAgc2V0VGltZW91dChmdW5jdGlvbigpe2Nsb3NlRWRpdFBvcHVwKCk7fSwyMDAwKTsKICAgICAgfSBlbHNlIHsKICAgICAgICBzZXRFZGl0U3RhdHVzKCLinYwgSGF0YTogIityLnN0YXR1cysiIOKAlCBUb2tlbsSxIGtvbnRyb2wgZXQiLCJyZWQiKTsKICAgICAgfQogICAgfSkKICAgIC5jYXRjaChmdW5jdGlvbihlKXsgc2V0RWRpdFN0YXR1cygi4p2MIEhhdGE6ICIrZS5tZXNzYWdlLCJyZWQiKTsgfSk7Cn0KCmZ1bmN0aW9uIHNldEVkaXRTdGF0dXMobXNnLCBjb2xvcil7CiAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImVkaXRTdGF0dXMiKTsKICBpZihlbCl7CiAgICBlbC50ZXh0Q29udGVudCA9IG1zZzsKICAgIGVsLnN0eWxlLmNvbG9yID0gY29sb3I9PT0iZ3JlZW4iPyJ2YXIoLS1ncmVlbikiOmNvbG9yPT09InJlZCI/InZhcigtLXJlZDIpIjoidmFyKC0teWVsbG93KSI7CiAgfQp9CgoKZnVuY3Rpb24gcmVuZGVySGFmdGFsaWsoKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgdmFyIHdkID0gV0VFS0xZX0RBVEEgfHwge307CiAgdmFyIHBvcnQgPSB3ZC5wb3J0Zm9saW8gfHwgW107CiAgdmFyIHdhdGNoID0gd2Qud2F0Y2hsaXN0IHx8IFtdOwogIHZhciBiZXN0ID0gd2QuYmVzdDsKICB2YXIgd29yc3QgPSB3ZC53b3JzdDsKICB2YXIgbWQgPSBNQVJLRVRfREFUQSB8fCB7fTsKICB2YXIgc3AgPSBtZC5TUDUwMCB8fCB7fTsKICB2YXIgbmFzID0gbWQuTkFTREFRIHx8IHt9OwogIHZhciBkYXRhMWQgPSBURl9EQVRBWycxZCddIHx8IFtdOwogIHZhciBkYXRhMXcgPSBURl9EQVRBWycxd2snXSB8fCBbXTsKCiAgZnVuY3Rpb24gY2Modil7IHJldHVybiB2Pj0wPyd2YXIoLS1ncmVlbjIpJzondmFyKC0tcmVkMiknOyB9CiAgZnVuY3Rpb24gY3Modil7IHJldHVybiAodj49MD8nKyc6JycpK3YrJyUnOyB9CgogIGZ1bmN0aW9uIHBlcmZSb3coaXRlbSl7CiAgICB2YXIgY29sID0gY2MoaXRlbS53ZWVrX2NoZyk7CiAgICB2YXIgcGIgPSBpdGVtLnBvcnRmb2xpbyA/ICc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1sZWZ0OjRweCI+UDwvc3Bhbj4nIDogJyc7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7cGFkZGluZzo4cHggMTJweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo4cHg7bWFyZ2luLWJvdHRvbTo1cHgiPicKICAgICAgKyAnPGRpdiBzdHlsZT0iZm9udC13ZWlnaHQ6NzAwO2ZvbnQtc2l6ZToxNHB4O2xldHRlci1zcGFjaW5nOjFweCI+JyArIGl0ZW0udGlja2VyICsgcGIgKyAnPC9kaXY+JwogICAgICArICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgY29sICsgJyI+JyArIGNzKGl0ZW0ud2Vla19jaGcpICsgJzwvZGl2PicKICAgICAgKyAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPk9uY2VraTogJyArIGNzKGl0ZW0ucHJldl93ZWVrX2NoZykgKyAnPC9kaXY+JwogICAgICArICc8L2Rpdj48L2Rpdj4nOwogIH0KCiAgdmFyIHBvcnRBdmcgPSBwb3J0Lmxlbmd0aCA/IE1hdGgucm91bmQocG9ydC5yZWR1Y2UoZnVuY3Rpb24oYSxiKXtyZXR1cm4gYStiLndlZWtfY2hnO30sMCkvcG9ydC5sZW5ndGgqMTAwKS8xMDAgOiAwOwogIHZhciBzcENoZyA9IHNwLmNoYW5nZSB8fCAwOwogIHZhciBuYXNDaGcgPSBuYXMuY2hhbmdlIHx8IDA7CiAgdmFyIGFscGhhID0gTWF0aC5yb3VuZCgocG9ydEF2Zy1zcENoZykqMTAwKS8xMDA7CiAgdmFyIGFscGhhQ29sID0gYWxwaGE+PTA/J3ZhcigtLWdyZWVuKSc6J3ZhcigtLXJlZDIpJzsKCiAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgLy8gSGVhZGVyCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tYm90dG9tOjRweCI+8J+TiCBIYWZ0YWzEsWsgUGVyZm9ybWFucyDDlnpldGk8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JyArICh3ZC5nZW5lcmF0ZWR8fCcnKSArICc8L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIFBpeWFzYSB2cyBQb3J0Zm9seW8KICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDEzMHB4LDFmcikpO2dhcDoxMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBbCiAgICB7bGFiZWw6J1BvcnRmw7Z5IE9ydC4nLCB2YWw6cG9ydEF2Z30sCiAgICB7bGFiZWw6J1MmUCA1MDAnLCB2YWw6c3BDaGd9LAogICAge2xhYmVsOidOQVNEQVEnLCB2YWw6bmFzQ2hnfSwKICBdLmZvckVhY2goZnVuY3Rpb24oeCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPicgKyB4LmxhYmVsICsgJzwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGNjKHgudmFsKSArICciPicgKyBjcyh4LnZhbCkgKyAnPC9kaXY+PC9kaXY+JzsKICB9KTsKICB2YXIgYUJnID0gYWxwaGE+PTA/J3JnYmEoMTYsMTg1LDEyOSwuMDgpJzoncmdiYSgyMzksNjgsNjgsLjA4KSc7CiAgdmFyIGFCZCA9IGFscGhhPj0wPydyZ2JhKDE2LDE4NSwxMjksLjI1KSc6J3JnYmEoMjM5LDY4LDY4LC4yNSknOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JyArIGFCZyArICc7Ym9yZGVyOjFweCBzb2xpZCAnICsgYUJkICsgJztib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+QWxwaGEgKHZzIFMmUCk8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgYWxwaGFDb2wgKyAnIj4nICsgY3MoYWxwaGEpICsgJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gRW4gaXlpIC8gZW4ga290dQogIGlmKGJlc3R8fHdvcnN0KXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyIDFmcjtnYXA6MTBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgICBpZihiZXN0KXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tZ3JlZW4pO21hcmdpbi1ib3R0b206NnB4Ij7wn4+GIEVuIMSweWk8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgYmVzdC50aWNrZXIgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+KycgKyBiZXN0LndlZWtfY2hnICsgJyU8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaWYod29yc3QpewogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tcmVkMik7bWFyZ2luLWJvdHRvbTo2cHgiPvCfk4kgRW4gS8O2dMO8PC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2xldHRlci1zcGFjaW5nOjJweCI+JyArIHdvcnN0LnRpY2tlciArICc8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicgKyB3b3JzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBTaW55YWxsZXIKICB2YXIgYnV5QyAgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdHVUNMVSBBTCd8fHIuc2lueWFsPT09J0FMJzt9KS5sZW5ndGg7CiAgdmFyIHdhcm5DID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nRElLS0FUJzt9KS5sZW5ndGg7CiAgdmFyIHNlbGxDID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nU0FUJzt9KS5sZW5ndGg7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfk4ogU2lueWFsbGVyPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXAiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicgKyBidXlDICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+QWw8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0teWVsbG93KSI+JyArIHdhcm5DICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+RGlra2F0PC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1yZWQyKSI+JyArIHNlbGxDICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+U2F0PC9kaXY+PC9kaXY+JzsKICBoICs9ICc8L2Rpdj48L2Rpdj4nOwoKICAvLyAxRysxSCBtb21lbnR1bQogIHZhciBib3RoQnV5ID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXsKICAgIGlmKHIuaGF0YSkgcmV0dXJuIGZhbHNlOwogICAgdmFyIHcgPSBkYXRhMXcuZmluZChmdW5jdGlvbih4KXtyZXR1cm4geC50aWNrZXI9PT1yLnRpY2tlcjt9KTsKICAgIHJldHVybiAoci5zaW55YWw9PT0nR1VDTFUgQUwnfHxyLnNpbnlhbD09PSdBTCcpICYmIHcgJiYgKHcuc2lueWFsPT09J0dVQ0xVIEFMJ3x8dy5zaW55YWw9PT0nQUwnKTsKICB9KTsKICBpZihib3RoQnV5Lmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLWdyZWVuKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+4pqhIDFHICsgMUggQWwgU2lueWFsaTwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7ZmxleC13cmFwOndyYXA7Z2FwOjhweCIgaWQ9ImJvdGhCdXlDb250YWluZXIiPjwvZGl2PjwvZGl2Pic7CiAgfQoKICAvLyBUb3AgMyBlbnRyeSBzY29yZQogIHZhciB0b3BFbnRyeSA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSkuc29ydChmdW5jdGlvbihhLGIpe3JldHVybiBiLmVudHJ5X3Njb3JlLWEuZW50cnlfc2NvcmU7fSkuc2xpY2UoMCwzKTsKICBpZih0b3BFbnRyeS5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+OryBFbiDEsHlpIEdpcmnFnyBLYWxpdGVzaTwvZGl2Pic7CiAgICB2YXIgbWVkYWxzID0gWyfwn6WHJywn8J+liCcsJ/CfpYknXTsKICAgIHRvcEVudHJ5LmZvckVhY2goZnVuY3Rpb24ocixpKXsKICAgICAgdmFyIGVzY29sID0gci5lbnRyeV9zY29yZT49NzU/J3ZhcigtLWdyZWVuKSc6ci5lbnRyeV9zY29yZT49NjA/J3ZhcigtLWdyZWVuMiknOid2YXIoLS15ZWxsb3cpJzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCIgaWQ9InRlLScgKyByLnRpY2tlciArICciPic7CiAgICAgIGggKz0gJzxzcGFuPicgKyBtZWRhbHNbaV0gKyAnIDxzdHJvbmc+JyArIHIudGlja2VyICsgJzwvc3Ryb25nPiA8c3BhbiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nICsgci5zaW55YWwgKyAnPC9zcGFuPjwvc3Bhbj4nOwogICAgICBoICs9ICc8c3BhbiBzdHlsZT0iZm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyBlc2NvbCArICciPicgKyByLmVudHJ5X3Njb3JlICsgJy8xMDA8L3NwYW4+PC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFN0b3AgeWFraW4KICB2YXIgbmVhclN0b3AgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpewogICAgaWYoci5oYXRhfHwhUE9SVC5pbmNsdWRlcyhyLnRpY2tlcil8fCFyLnN0b3ApIHJldHVybiBmYWxzZTsKICAgIHJldHVybiAoci5maXlhdC1yLnN0b3ApL3IuZml5YXQqMTAwIDwgODsKICB9KS5zb3J0KGZ1bmN0aW9uKGEsYil7cmV0dXJuIChhLmZpeWF0LWEuc3RvcCkvYS5maXlhdC0oYi5maXlhdC1iLnN0b3ApL2IuZml5YXQ7fSk7CiAgaWYobmVhclN0b3AubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLXJlZDIpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7imqDvuI8gU3RvcCBTZXZpeWVzaW5lIFlha8SxbjwvZGl2Pic7CiAgICBuZWFyU3RvcC5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgICB2YXIgZGlzdCA9IE1hdGgucm91bmQoKHIuZml5YXQtci5zdG9wKS9yLmZpeWF0KjEwMDApLzEwOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO3BhZGRpbmc6OHB4IDEycHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6OHB4O21hcmdpbi1ib3R0b206NXB4IiBpZD0ibnMtJyArIHIudGlja2VyICsgJyI+JzsKICAgICAgaCArPSAnPHN0cm9uZz4nICsgci50aWNrZXIgKyAnPC9zdHJvbmc+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tcmVkMik7Zm9udC13ZWlnaHQ6NjAwIj5TdG9wICQnICsgci5zdG9wICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+VXpha2zEsWs6ICUnICsgZGlzdCArICc8L2Rpdj48L2Rpdj48L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gSGVkZWZlIHlha2luCiAgdmFyIG5lYXJUYXJnZXQgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpewogICAgaWYoci5oYXRhfHwhUE9SVC5pbmNsdWRlcyhyLnRpY2tlcil8fCFyLmhlZGVmKSByZXR1cm4gZmFsc2U7CiAgICByZXR1cm4gKHIuaGVkZWYtci5maXlhdCkvci5maXlhdCoxMDAgPCAxNTsKICB9KS5zb3J0KGZ1bmN0aW9uKGEsYil7cmV0dXJuIChhLmhlZGVmLWEuZml5YXQpL2EuZml5YXQtKGIuaGVkZWYtYi5maXlhdCkvYi5maXlhdDt9KTsKICBpZihuZWFyVGFyZ2V0Lmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOiM2MGE1ZmE7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfjq8gSGVkZWZlIFlha8SxbjwvZGl2Pic7CiAgICBuZWFyVGFyZ2V0LmZvckVhY2goZnVuY3Rpb24ocil7CiAgICAgIHZhciBkaXN0ID0gTWF0aC5yb3VuZCgoci5oZWRlZi1yLmZpeWF0KS9yLmZpeWF0KjEwMDApLzEwOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO3BhZGRpbmc6OHB4IDEycHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6OHB4O21hcmdpbi1ib3R0b206NXB4Ij4nOwogICAgICBoICs9ICc8c3Ryb25nPicgKyByLnRpY2tlciArICc8L3N0cm9uZz4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij48ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjojNjBhNWZhO2ZvbnQtd2VpZ2h0OjYwMCI+SGVkZWYgJCcgKyByLmhlZGVmICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+S2FsZGk6ICUnICsgZGlzdCArICc8L2Rpdj48L2Rpdj48L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gRWFybmluZ3MKICB2YXIgdXJnZW50RSA9IEVBUk5JTkdTX0RBVEEuZmlsdGVyKGZ1bmN0aW9uKGUpe3JldHVybiBlLmRheXNfdG9fZWFybmluZ3MhPW51bGwmJmUuZGF5c190b19lYXJuaW5nczw9MTQ7fSkuc29ydChmdW5jdGlvbihhLGIpe3JldHVybiBhLmRheXNfdG9fZWFybmluZ3MtYi5kYXlzX3RvX2Vhcm5pbmdzO30pOwogIGlmKHVyZ2VudEUubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0teWVsbG93KTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+ThSBZYWtsYcWfYW4gUmFwb3JsYXI8L2Rpdj4nOwogICAgdXJnZW50RS5mb3JFYWNoKGZ1bmN0aW9uKGUpewogICAgICB2YXIgaWMgPSBlLmFsZXJ0PT09J3JlZCc/J/CflLQnOifwn5+hJzsKICAgICAgdmFyIGluUG9ydCA9IFBPUlQuaW5jbHVkZXMoZS50aWNrZXIpOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO3BhZGRpbmc6OHB4IDEycHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6OHB4O21hcmdpbi1ib3R0b206NXB4Ij4nOwogICAgICBoICs9ICc8c3Bhbj4nICsgaWMgKyAnIDxzdHJvbmc+JyArIGUudGlja2VyICsgJzwvc3Ryb25nPicgKyAoaW5Qb3J0PycgPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6MTBweCI+UDwvc3Bhbj4nOicnKSArICc8L3NwYW4+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKTtmb250LXNpemU6MTFweCI+JyArIGUubmV4dF9kYXRlICsgJyAoJyArIGUuZGF5c190b19lYXJuaW5ncyArICcgZ8O8bik8L3NwYW4+PC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFZJWAogIHZhciB2aXggPSBtZC5WSVggfHwge307CiAgaWYodml4LnByaWNlKXsKICAgIHZhciB2Q29sID0gdml4LnByaWNlPjMwPyd2YXIoLS1yZWQyKSc6dml4LnByaWNlPjIwPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tZ3JlZW4pJzsKICAgIHZhciB2TGJsID0gdml4LnByaWNlPjMwPydZw7xrc2VrIEtvcmt1IOKAlCBZZW5pIHBvemlzeW9uIGHDp21hJzp2aXgucHJpY2U+MjA/J09ydGEgVm9sYXRpbGl0ZSDigJQgRGlra2F0bGkgb2wnOidEw7zFn8O8ayBWb2xhdGlsaXRlIOKAlCBOb3JtYWwga2/Fn3VsbGFyJzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTRweCAxNnB4O21hcmdpbi1ib3R0b206MTBweDtkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyIj4nOwogICAgaCArPSAnPGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbToycHgiPlZJWDwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOicgKyB2Q29sICsgJyI+JyArIHZMYmwgKyAnPC9kaXY+PC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgdkNvbCArICciPicgKyB2aXgucHJpY2UgKyAnPC9kaXY+PC9kaXY+JzsKICB9CgogIC8vIFBvcnRmb2x5byBkZXRheQogIGlmKHBvcnQubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkrwgUG9ydGbDtnk8L2Rpdj4nOwogICAgcG9ydC5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0pe2ggKz0gcGVyZlJvdyhpdGVtKTt9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBXYXRjaGxpc3QKICBpZih3YXRjaC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+RgSBXYXRjaGxpc3Q8L2Rpdj4nOwogICAgd2F0Y2guZm9yRWFjaChmdW5jdGlvbihpdGVtKXtoICs9IHBlcmZSb3coaXRlbSk7fSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgaCArPSAnPC9kaXY+JzsKICBncmlkLmlubmVySFRNTCA9IGg7CgogIC8vIEFkZCBvbmNsaWNrIHZpYSBKUyAoYXZvaWRzIHF1b3RlIG5lc3RpbmcgaXNzdWVzKQogIGJvdGhCdXkuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBjbnQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnYm90aEJ1eUNvbnRhaW5lcicpOwogICAgaWYoIWNudCkgcmV0dXJuOwogICAgdmFyIGQgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgIGQuc3R5bGUuY3NzVGV4dCA9ICdiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjMpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6OHB4IDE0cHg7Y3Vyc29yOnBvaW50ZXInOwogICAgZC5pbm5lckhUTUwgPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2xldHRlci1zcGFjaW5nOjJweDtjb2xvcjp2YXIoLS1ncmVlbikiPicgKyByLnRpY2tlciArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkdpcmlzOiAnICsgci5lbnRyeV9zY29yZSArICcvMTAwPC9kaXY+JzsKICAgIGQub25jbGljayA9IChmdW5jdGlvbih0KXtyZXR1cm4gZnVuY3Rpb24oKXtvcGVuTSh0KTt9O30pKHIudGlja2VyKTsKICAgIGNudC5hcHBlbmRDaGlsZChkKTsKICB9KTsKICB0b3BFbnRyeS5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3RlLScgKyByLnRpY2tlcik7CiAgICBpZihlbCkgZWwub25jbGljayA9IChmdW5jdGlvbih0KXtyZXR1cm4gZnVuY3Rpb24oKXtvcGVuTSh0KTt9O30pKHIudGlja2VyKSwgZWwuc3R5bGUuY3Vyc29yPSdwb2ludGVyJzsKICB9KTsKICBuZWFyU3RvcC5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ25zLScgKyByLnRpY2tlcik7CiAgICBpZihlbCkgZWwub25jbGljayA9IChmdW5jdGlvbih0KXtyZXR1cm4gZnVuY3Rpb24oKXtvcGVuTSh0KTt9O30pKHIudGlja2VyKSwgZWwuc3R5bGUuY3Vyc29yPSdwb2ludGVyJzsKICB9KTsKfQoKCmZ1bmN0aW9uIHJlbmRlclNjcmVlbmVyKCl7CiAgdmFyIGdyaWQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogIHZhciBkYXRhID0gU0NSRUVORVJfREFUQSB8fCBbXTsKICB2YXIgY3JpdGVyaWEgPSBbCiAgICB7aWQ6J2Vwc19xb3EnLCAgICBsYWJlbDonRVBTIFFvUSBCw7x5w7xtZScsICAgICBsaW1pdDonPj0yMCUnLCAgICB3OjMsIGltcDonY3JpdGljYWwnfSwKICAgIHtpZDonc21hMjAwJywgICAgIGxhYmVsOidTTUEyMDAgw5x6ZXJpbmRlJywgICAgIGxpbWl0OidQPlNNQTIwMCcsIHc6MywgaW1wOidjcml0aWNhbCd9LAogICAge2lkOidtYXJrZXQnLCAgICAgbGFiZWw6J00gS3JpdGVyaScsICAgICAgICAgICBsaW1pdDonR8O8w6dsw7wnLCAgICB3OjMsIGltcDonY3JpdGljYWwnfSwKICAgIHtpZDonZXBzX2FjY2VsJywgIGxhYmVsOidFUFMgSMSxemxhbm1hc8SxJywgICAgICBsaW1pdDonSMSxemxhbsSxeW9yJyx3OjIsIGltcDonaW1wb3J0YW50J30sCiAgICB7aWQ6J3JzX3JhdGluZycsICBsYWJlbDonUlMgUmF0aW5nJywgICAgICAgICAgIGxpbWl0Oic+PTcwJywgICAgIHc6MiwgaW1wOidpbXBvcnRhbnQnfSwKICAgIHtpZDoncmV2X2dyb3d0aCcsIGxhYmVsOidHZWxpciBCw7x5w7xtZXNpJywgICAgICBsaW1pdDonPj0xNSUnLCAgICB3OjIsIGltcDonaW1wb3J0YW50J30sCiAgICB7aWQ6J3JvZScsICAgICAgICBsYWJlbDonUk9FJywgICAgICAgICAgICAgICAgIGxpbWl0Oic+PTE1JScsICAgIHc6MiwgaW1wOidpbXBvcnRhbnQnfSwKICAgIHtpZDonZ3Jvc3NfbWcnLCAgIGxhYmVsOidCcsO8dCBNYXJqaW4nLCAgICAgICAgIGxpbWl0Oic+PTQwJScsICAgIHc6MiwgaW1wOidpbXBvcnRhbnQnfSwKICAgIHtpZDonc21hNTAnLCAgICAgIGxhYmVsOidTTUE1MCDDnHplcmluZGUnLCAgICAgIGxpbWl0OidQPlNNQTUwJywgIHc6MiwgaW1wOidpbXBvcnRhbnQnfSwKICAgIHtpZDonNTJ3JywgICAgICAgIGxhYmVsOic1MkggWWFrxLFubMSxaycsICAgICAgICBsaW1pdDonPj03NSUnLCAgICB3OjIsIGltcDonaW1wb3J0YW50J30sCiAgICB7aWQ6J25ldF9tZycsICAgICBsYWJlbDonTmV0IE1hcmppbicsICAgICAgICAgIGxpbWl0Oic+PTEwJScsICAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J2RlJywgICAgICAgICBsYWJlbDonQm9yw6cvw5Z6a2F5bmFrJywgICAgICAgbGltaXQ6Jzw9MS4wJywgICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDonY3InLCAgICAgICAgIGxhYmVsOidDdXJyZW50IFJhdGlvJywgICAgICAgbGltaXQ6Jz49MS41JywgICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDoncGUnLCAgICAgICAgIGxhYmVsOidQL0UnLCAgICAgICAgICAgICAgICAgbGltaXQ6Jzw9NjAnLCAgICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDonbWt0Y2FwJywgICAgIGxhYmVsOidQaXlhc2EgRGXEn2VyaScsICAgICAgIGxpbWl0Oic+PTFCJywgICAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J3JlbF92b2wnLCAgICBsYWJlbDonR8O2cmVjZWxpIEhhY2ltJywgICAgICBsaW1pdDonPj0wLjh4JywgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidhdmdfdm9sJywgICAgbGFiZWw6J09ydC4gSGFjaW0nLCAgICAgICAgICBsaW1pdDonPj01MDBLJywgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidpbnN0X293bicsICAgbGFiZWw6J0t1cnVtc2FsIFNhaGlwbGlrJywgICBsaW1pdDonPj00MCUnLCAgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidpbnN0X3RyZW5kJywgbGFiZWw6J0t1cnVtc2FsIFRyZW5kJywgICAgICBsaW1pdDonQXJ0xLF5b3InLCAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICBdOwogIHZhciBNQVhfVyA9IDM1OwoKICBpZighZGF0YS5sZW5ndGgpewogICAgZ3JpZC5pbm5lckhUTUw9JzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTE7dGV4dC1hbGlnbjpjZW50ZXI7cGFkZGluZzo0MHB4O2NvbG9yOnZhcigtLW11dGVkKSI+U2NyZWVuZXIgdmVyaXNpIHlvayDigJQgQWN0aW9ucyBSdW4gV29ya2Zsb3c8L2Rpdj4nOwogICAgcmV0dXJuOwogIH0KCiAgdmFyIHBhc3NlZCA9IGRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnBhc3NlZDt9KTsKICB2YXIgZmFpbGVkID0gZGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLnBhc3NlZDt9KTsKICB2YXIgW2V4cGFuZGVkVGlja2VyLCBzZXRFeHBhbmRlZF0gPSBbbnVsbCwgbnVsbF07CgogIGZ1bmN0aW9uIGltcENvbG9yKGltcCl7CiAgICByZXR1cm4gaW1wPT09J2NyaXRpY2FsJz8ndmFyKC0tcmVkMiknOmltcD09PSdpbXBvcnRhbnQnPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tbXV0ZWQpJzsKICB9CiAgZnVuY3Rpb24gaW1wTGFiZWwoaW1wKXsKICAgIHJldHVybiBpbXA9PT0nY3JpdGljYWwnPyfwn5S0IFpPUlVOTFUnOmltcD09PSdpbXBvcnRhbnQnPyfwn5+hIMOWTkVNTMSwJzon8J+UtSBERVNURUsnOwogIH0KCiAgZnVuY3Rpb24gY3JpdGVyaWFEZXRhaWwocil7CiAgICB2YXIgaCA9ICc8ZGl2IHN0eWxlPSJwYWRkaW5nOjEycHggMTRweDtib3JkZXItdG9wOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNik7YmFja2dyb3VuZDp2YXIoLS1iZzMpIj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+S1LEsFRFUiBERVRBWUkg4oCUIEHEn8SxcmzEsWtsxLEgU2tvcjogJytyLndlaWdodGVkX3Njb3JlKycvJytyLm1heF93ZWlnaHRlZCsnICglJytyLnBjdCsnKTwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjRweCI+JzsKICAgIGNyaXRlcmlhLmZvckVhY2goZnVuY3Rpb24oYyl7CiAgICAgIHZhciBjciA9IHIuY3JpdGVyaWEgJiYgci5jcml0ZXJpYVtjLmlkXTsKICAgICAgaWYoIWNyKSByZXR1cm47CiAgICAgIHZhciBub0RhdGEgPSBjci5oYXNfZGF0YSA9PT0gZmFsc2U7CiAgICAgIHZhciBjb2wgPSBub0RhdGEgPyAndmFyKC0tbXV0ZWQpJyA6IGNyLnBhc3NlZCA/ICd2YXIoLS1ncmVlbiknIDogaW1wQ29sb3IoYy5pbXApOwogICAgICB2YXIgYmcgPSBub0RhdGEgPyAncmdiYSgyNTUsMjU1LDI1NSwuMDIpJyA6IGNyLnBhc3NlZCA/ICdyZ2JhKDE2LDE4NSwxMjksLjA2KScgOiAoYy5pbXA9PT0nY3JpdGljYWwnPydyZ2JhKDIzOSw2OCw2OCwuMDgpJzpjLmltcD09PSdpbXBvcnRhbnQnPydyZ2JhKDI0NSwxNTgsMTEsLjA2KSc6J3JnYmEoMjU1LDI1NSwyNTUsLjAyKScpOwogICAgICB2YXIgYmQgPSBub0RhdGEgPyAncmdiYSgyNTUsMjU1LDI1NSwuMDUpJyA6IGNyLnBhc3NlZCA/ICdyZ2JhKDE2LDE4NSwxMjksLjIpJyA6IChjLmltcD09PSdjcml0aWNhbCc/J3JnYmEoMjM5LDY4LDY4LC4yKSc6Yy5pbXA9PT0naW1wb3J0YW50Jz8ncmdiYSgyNDUsMTU4LDExLC4yKSc6J3JnYmEoMjU1LDI1NSwyNTUsLjA1KScpOwogICAgICB2YXIgaWNvbiA9IG5vRGF0YSA/ICfirJwnIDogY3IucGFzc2VkID8gJ+KchScgOiAn4p2MJzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonK2JnKyc7Ym9yZGVyOjFweCBzb2xpZCAnK2JkKyc7Ym9yZGVyLXJhZGl1czo1cHg7cGFkZGluZzo1cHggOHB4Ij4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyIj4nOwogICAgICBoICs9ICc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK2NvbCsnIj4nK2ljb24rJyAnK2MubGFiZWwrJzwvc3Bhbj4nOwogICAgICBoICs9ICc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicraW1wTGFiZWwoYy5pbXApLnNwbGl0KCcgJylbMF0rJzwvc3Bhbj48L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtmb250LXdlaWdodDo2MDA7Y29sb3I6Jysobm9EYXRhPyd2YXIoLS1tdXRlZCknOmNyLnBhc3NlZD8ndmFyKC0tdGV4dCknOmNvbCkrJyI+Jytjci52YWwrJyA8c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC13ZWlnaHQ6NDAwIj4nKyghbm9EYXRhPydsaW1pdDogJzonJykrYy5saW1pdCsnPC9zcGFuPjwvZGl2Pic7CiAgICAgIGggKz0gJzwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2PjwvZGl2Pic7CiAgICByZXR1cm4gaDsKICB9CgogIGZ1bmN0aW9uIHN0b2NrUm93KHIsIGV4cGFuZGVkKXsKICAgIHZhciBwY3QgPSByLnBjdDsKICAgIHZhciBjb2wgPSBwY3Q+PTgwPyd2YXIoLS1ncmVlbiknOnBjdD49NjA/J3ZhcigtLWdyZWVuMiknOnBjdD49NDA/J3ZhcigtLXllbGxvdyknOid2YXIoLS1yZWQyKSc7CiAgICB2YXIgcGIgPSByLmluX3BvcnRmb2xpbz8nPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tbGVmdDo0cHgiPlA8L3NwYW4+JzonJzsKICAgIHZhciB3YiA9IHIuaW5fd2F0Y2hsaXN0Pyc8c3BhbiBzdHlsZT0iY29sb3I6IzYwYTVmYTtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tbGVmdDo0cHgiPlc8L3NwYW4+JzonJzsKICAgIHZhciBjaGdDb2wgPSByLmNoYW5nZT49MD8ndmFyKC0tZ3JlZW4yKSc6J3ZhcigtLXJlZDIpJzsKICAgIHZhciBjcml0RmFpbCA9IGNyaXRlcmlhLmZpbHRlcihmdW5jdGlvbihjKXtyZXR1cm4gci5jcml0ZXJpYSYmci5jcml0ZXJpYVtjLmlkXSYmIXIuY3JpdGVyaWFbYy5pZF0ucGFzc2VkJiZjLmltcD09PSdjcml0aWNhbCc7fSk7CiAgICB2YXIgd2FyblRhZ3MgPSBjcml0RmFpbC5tYXAoZnVuY3Rpb24oYyl7CiAgICAgIHJldHVybiAnPHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjEpO2NvbG9yOnZhcigtLXJlZDIpO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O21hcmdpbi1yaWdodDozcHgiPuKdjCcrYy5sYWJlbCsnPC9zcGFuPic7CiAgICB9KS5qb2luKCcnKTsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iYm9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDQpIiBpZD0ic2Mtcm93LScrci50aWNrZXIrJyI+JwogICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MTMwcHggMWZyIDgwcHggODBweDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjEwcHg7cGFkZGluZzoxMHB4IDE0cHg7Y3Vyc29yOnBvaW50ZXIiIGlkPSJzYy0nK3IudGlja2VyKyciPicKICAgICAgKyc8ZGl2PjxkaXYgc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtmb250LXNpemU6MTRweDtsZXR0ZXItc3BhY2luZzoxcHgiPicrci50aWNrZXIrcGIrd2IrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytyLm5hbWUuc3Vic3RyaW5nKDAsMTgpKyc8L2Rpdj48L2Rpdj4nCiAgICAgICsnPGRpdj48ZGl2IHN0eWxlPSJoZWlnaHQ6NHB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjJweDtvdmVyZmxvdzpoaWRkZW4iPicKICAgICAgKyc8ZGl2IHN0eWxlPSJoZWlnaHQ6MTAwJTt3aWR0aDonK3BjdCsnJTtiYWNrZ3JvdW5kOicrY29sKyc7Ym9yZGVyLXJhZGl1czoycHgiPjwvZGl2PjwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo0cHg7bWFyZ2luLXRvcDozcHgiPicrd2FyblRhZ3MKICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrci5zY29yZSsnLzE5PC9zcGFuPicKICAgICAgKyc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtjb2xvcjojNjBhNWZhO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMCI+UlM6JytyLnJzX3JhdGluZysnPC9zcGFuPicKICAgICAgKyc8L2Rpdj48L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+PGRpdiBzdHlsZT0iZm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrY29sKyc7Zm9udC1zaXplOjE1cHgiPicrcGN0KyclPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5hxJ/EsXJsxLFrbMSxPC9kaXY+PC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPjxkaXYgc3R5bGU9ImZvbnQtd2VpZ2h0OjYwMCI+JCcrci5wcmljZSsnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOicrY2hnQ29sKyciPicrKHIuY2hhbmdlPj0wPycrJzonJykrci5jaGFuZ2UrJyU8L2Rpdj48L2Rpdj4nCiAgICAgICsnPC9kaXY+JwogICAgICArKGV4cGFuZGVkID8gY3JpdGVyaWFEZXRhaWwocikgOiAnJykKICAgICAgKyc8L2Rpdj4nOwogIH0KCiAgZnVuY3Rpb24gYnVpbGRIVE1MKCl7CiAgICB2YXIgaCA9ICc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwoKICAgIC8vIFN1bW1hcnkKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tYm90dG9tOjRweCI+8J+UjSBDQU5TTElNIFNjcmVlbmVyPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjEycHgiPjE2IGtyaXRlciDCtyAzIMO2bmVtIHNldml5ZXNpIMK3ICcrZGF0YS5sZW5ndGgrJyBoaXNzZSB0YXJhbmTEsTwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXA7bWFyZ2luLWJvdHRvbToxMnB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicrcGFzc2VkLmxlbmd0aCsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5HZcOndGk8L2Rpdj48L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicrZmFpbGVkLmxlbmd0aCsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5HZcOnZW1lZGk8L2Rpdj48L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjojNjBhNWZhIj4nK2RhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLmluX3dhdGNobGlzdHx8ci5pbl9wb3J0Zm9saW87fSkubGVuZ3RoKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkxpc3RlbWRlPC9kaXY+PC9kaXY+JzsKICAgIGggKz0gJzwvZGl2Pic7CiAgICAvLyBMZWdlbmQKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcDtmb250LXNpemU6MTBweCI+JzsKICAgIGggKz0gJzxzcGFuPvCflLQgPHN0cm9uZz5ab3J1bmx1PC9zdHJvbmc+ICgzeCk6IEVQUyBRb1EsIFNNQTIwMCwgTSBLcml0ZXJpPC9zcGFuPic7CiAgICBoICs9ICc8c3Bhbj7wn5+hIDxzdHJvbmc+w5ZuZW1saTwvc3Ryb25nPiAoMngpOiBHZWxpciwgUk9FLCBNYXJqaW4sIFNNQTUwLCA1Mkg8L3NwYW4+JzsKICAgIGggKz0gJzxzcGFuPvCflLUgPHN0cm9uZz5EZXN0ZWs8L3N0cm9uZz4gKDF4KTogRGnEn2VybGVyaTwvc3Bhbj4nOwogICAgaCArPSAnPC9kaXY+PC9kaXY+JzsKCiAgICAvLyBHZcOnZW5sZXIKICAgIGlmKHBhc3NlZC5sZW5ndGgpewogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6MTJweDtvdmVyZmxvdzpoaWRkZW47bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJwYWRkaW5nOjEwcHggMTRweDtib3JkZXItYm90dG9tOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNik7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tZ3JlZW4pO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2UiPuKchSBDQU5TTElNIEdlw6d0aSAoJytwYXNzZWQubGVuZ3RoKycpPC9kaXY+JzsKICAgICAgcGFzc2VkLmZvckVhY2goZnVuY3Rpb24ocil7IGggKz0gc3RvY2tSb3cociwgci50aWNrZXI9PT1leHBhbmRlZFRpY2tlcik7IH0pOwogICAgICBoICs9ICc8L2Rpdj4nOwogICAgfQoKICAgIC8vIFdhdGNobGlzdC9Qb3J0Zm9saW8gKGdlw6dlbWV5ZW5sZXIpCiAgICB2YXIgbXlGYWlsZWQgPSBmYWlsZWQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLmluX3dhdGNobGlzdHx8ci5pbl9wb3J0Zm9saW87fSk7CiAgICBpZihteUZhaWxlZC5sZW5ndGgpewogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtvdmVyZmxvdzpoaWRkZW47bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJwYWRkaW5nOjEwcHggMTRweDtib3JkZXItYm90dG9tOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNik7Zm9udC1zaXplOjExcHg7Y29sb3I6IzYwYTVmYTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlIj7wn5OLIExpc3RlbWRlIChHZcOnZW1lZGksICcrbXlGYWlsZWQubGVuZ3RoKycpPC9kaXY+JzsKICAgICAgbXlGYWlsZWQuZm9yRWFjaChmdW5jdGlvbihyKXsgaCArPSBzdG9ja1JvdyhyLCByLnRpY2tlcj09PWV4cGFuZGVkVGlja2VyKTsgfSk7CiAgICAgIGggKz0gJzwvZGl2Pic7CiAgICB9CgogICAgaCArPSAnPC9kaXY+JzsKICAgIHJldHVybiBoOwogIH0KCiAgZ3JpZC5pbm5lckhUTUwgPSBidWlsZEhUTUwoKTsKCiAgLy8gb25jbGljayBoYW5kbGVycwogIGRhdGEuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdzYy0nK3IudGlja2VyKTsKICAgIGlmKGVsKXsKICAgICAgZWwub25jbGljayA9IGZ1bmN0aW9uKGUpewogICAgICAgIGUuc3RvcFByb3BhZ2F0aW9uKCk7CiAgICAgICAgaWYoZXhwYW5kZWRUaWNrZXI9PT1yLnRpY2tlcil7IGV4cGFuZGVkVGlja2VyPW51bGw7IH0KICAgICAgICBlbHNlIHsgZXhwYW5kZWRUaWNrZXI9ci50aWNrZXI7IH0KICAgICAgICBncmlkLmlubmVySFRNTCA9IGJ1aWxkSFRNTCgpOwogICAgICAgIC8vIFJlLWF0dGFjaCBoYW5kbGVycwogICAgICAgIGRhdGEuZm9yRWFjaChmdW5jdGlvbihyMil7CiAgICAgICAgICB2YXIgZWwyID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3NjLScrcjIudGlja2VyKTsKICAgICAgICAgIGlmKGVsMikgZWwyLm9uY2xpY2sgPSBhcmd1bWVudHMuY2FsbGVlLmJpbmQoe3RpY2tlcjpyMi50aWNrZXJ9KTsKICAgICAgICB9KTsKICAgICAgICBhdHRhY2hIYW5kbGVycygpOwogICAgICB9OwogICAgfQogIH0pOwoKICBmdW5jdGlvbiBhdHRhY2hIYW5kbGVycygpewogICAgZGF0YS5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgICB2YXIgZWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnc2MtJytyLnRpY2tlcik7CiAgICAgIGlmKCFlbCkgcmV0dXJuOwogICAgICBlbC5vbmNsaWNrID0gKGZ1bmN0aW9uKHRpY2tlcil7CiAgICAgICAgcmV0dXJuIGZ1bmN0aW9uKGUpewogICAgICAgICAgZS5zdG9wUHJvcGFnYXRpb24oKTsKICAgICAgICAgIGV4cGFuZGVkVGlja2VyID0gZXhwYW5kZWRUaWNrZXI9PT10aWNrZXIgPyBudWxsIDogdGlja2VyOwogICAgICAgICAgZ3JpZC5pbm5lckhUTUwgPSBidWlsZEhUTUwoKTsKICAgICAgICAgIGF0dGFjaEhhbmRsZXJzKCk7CiAgICAgICAgfTsKICAgICAgfSkoci50aWNrZXIpOwogICAgfSk7CiAgfQogIGF0dGFjaEhhbmRsZXJzKCk7Cn0KCgpmdW5jdGlvbiByZW5kZXJEaXJlY3Rpb24oKXsKICB2YXIgZ3JpZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogIGlmKGdyaWQpe2dyaWQuc3R5bGUuZGlzcGxheT0nJztncmlkLnN0eWxlLndpZHRoPScnO30KICB2YXIgRD1ESVJFQ1RJT05fREFUQXx8e307CiAgdmFyIE1FVEE9ewogICAgdXB0cmVuZDp7aWM6J1x1ZDgzZFx1ZGZlMicsbGJsOidUZXlpdGxpIFlcdTAwZmNrc2VsaVx1MDE1ZicsYWR2OidQaXZvdCBrXHUwMTMxcmFuIGxpZGVybGVyZSBub3JtYWwgcG96aXN5b25sYSBnaXJpbGViaWxpci4nLGM6J3ZhcigtLWdyZWVuKScsYmc6J3JnYmEoMTYsMTg1LDEyOSwuMDgpJyxiZDoncmdiYSgxNiwxODUsMTI5LC4yNSknfSwKICAgIHByZXNzdXJlOntpYzonXHVkODNkXHVkZmUxJyxsYmw6J0Jhc2tcdTAxMzEgQWx0XHUwMTMxbmRhJyxhZHY6J1llbmkgYWxcdTAxMzFtIHlhcG1hLiBTdG9wIHNldml5ZWxlcmluaSBzXHUwMTMxa1x1MDEzMWxhXHUwMTVmdFx1MDEzMXIsIHpheVx1MDEzMWYgcG96aXN5b25sYXJcdTAxMzEgYXphbHQuJyxjOid2YXIoLS15ZWxsb3cpJyxiZzoncmdiYSgyNDUsMTU4LDExLC4wOCknLGJkOidyZ2JhKDI0NSwxNTgsMTEsLjI1KSd9LAogICAgY29ycmVjdGlvbjp7aWM6J1x1ZDgzZFx1ZGQzNCcsbGJsOidEXHUwMGZjemVsdG1lJyxhZHY6J05ha2l0dGUgKFNHT1YpIGJla2xlLiBXYXRjaGxpc3RcdTIwMTlpIGdcdTAwZmNuY2VsbGUsIGZvbGxvdy10aHJvdWdoIGRheSBzaW55YWxpbmkgaXpsZS4nLGM6J3ZhcigtLXJlZDIpJyxiZzoncmdiYSgyMzksNjgsNjgsLjA4KScsYmQ6J3JnYmEoMjM5LDY4LDY4LC4yNSknfSwKICAgIHJhbGx5OntpYzonXHVkODNkXHVkZmUwJyxsYmw6J1RvcGFybGFubWEgRGVuZW1lc2knLGFkdjonSGVuXHUwMGZjeiBnaXJtZSBcdTIwMTQgRlREIHBlbmNlcmVzaSBhXHUwMGU3XHUwMTMxbFx1MDEzMXlvci4gSGFjaW1saSAlMS41KyB5XHUwMGZja3NlbGlcdTAxNWYgZ1x1MDBmY25cdTAwZmNuXHUwMGZjIGJla2xlLicsYzondmFyKC0teWVsbG93KScsYmc6J3JnYmEoMjQ1LDE1OCwxMSwuMDgpJyxiZDoncmdiYSgyNDUsMTU4LDExLC4yNSknfSwKICAgIGZ0ZDp7aWM6J1x1MjZhMScsbGJsOidGT0xMT1ctVEhST1VHSCBEQVkhJyxhZHY6J0thZGVtZWxpIGdpcmlcdTAxNWYgYmFcdTAxNWZsYXQ6IGtcdTAwZmNcdTAwZTdcdTAwZmNrIHBvemlzeW9ubGEgdGVzdCBldCwgcGl5YXNhIGhha2xcdTAxMzEgXHUwMGU3XHUwMTMxa2FyXHUwMTMxcnNhIGJcdTAwZmN5XHUwMGZjdC4nLGM6J3ZhcigtLWdyZWVuKScsYmc6J3JnYmEoMTYsMTg1LDEyOSwuMSknLGJkOidyZ2JhKDE2LDE4NSwxMjksLjM1KSd9CiAgfTsKICB2YXIgaD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWJvdHRvbTo0cHgiPlx1ZDgzZFx1ZGNjYSBQaXlhc2EgWVx1MDBmNm5cdTAwZmMgXHUyMDE0IEZURCBUYWtpYmk8L2Rpdj4nOwogIGgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGluZS1oZWlnaHQ6MS42Ij5Gb2xsb3ctdGhyb3VnaCBkYXk6IGRpcHRlbiA0LTEwIGdcdTAwZmNuIHNvbnJhIGdlbGVuIGhhY2ltbGkgJTEuNSsgeVx1MDBmY2tzZWxpXHUwMTVmIGdcdTAwZmNuXHUwMGZjIFx1MjAxNCB5ZW5pIHlcdTAwZmNrc2VsaVx1MDE1ZiB0cmVuZGluaSB0ZXlpdCBlZGVyLiBEYVx1MDExZlx1MDEzMXRcdTAxMzFtIGdcdTAwZmNuXHUwMGZjOiBhcnRhbiBoYWNpbWxlICUwLjIrIGRcdTAwZmNcdTAxNWZcdTAwZmNcdTAxNWYgXHUyMDE0IGt1cnVtc2FsIHNhdFx1MDEzMVx1MDE1ZiBpemkuIDI1IGdcdTAwZmNuZGUgNSsgZGFcdTAxMWZcdTAxMzF0XHUwMTMxbSA9IHBpeWFzYSBiYXNrXHUwMTMxIGFsdFx1MDEzMW5kYS48L2Rpdj48L2Rpdj4nOwogIFsnU1A1MDAnLCdOQVNEQVEnXS5mb3JFYWNoKGZ1bmN0aW9uKG5hbWUpewogICAgdmFyIGQ9RFtuYW1lXXx8e307CiAgICBpZihkLmVycm9yfHxkLnN0YXR1cz09PXVuZGVmaW5lZCl7aCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK25hbWUrJzogdmVyaSB5b2s8L2Rpdj4nO3JldHVybjt9CiAgICB2YXIgbT1NRVRBW2Quc3RhdHVzXXx8TUVUQS5wcmVzc3VyZTsKICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicrbS5iZysnO2JvcmRlcjoxcHggc29saWQgJyttLmJkKyc7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTJweCI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO2ZsZXgtd3JhcDp3cmFwO2dhcDo4cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCs9JzxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweCI+JysobmFtZT09PSdTUDUwMCc/J1MmUCA1MDAnOidOQVNEQVEnKSsnPC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyttLmMrJyI+JyttLmljKycgJyttLmxibCsnPC9kaXY+PC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+WmlydmVkZW46IDxzcGFuIHN0eWxlPSJmb250LXdlaWdodDo3MDA7Y29sb3I6JysoZC5kcmF3ZG93bjw9LTg/J3ZhcigtLXJlZDIpJzpkLmRyYXdkb3duPD0tND8ndmFyKC0teWVsbG93KSc6J3ZhcigtLWdyZWVuKScpKyciPiUnK2QuZHJhd2Rvd24rJzwvc3Bhbj48L2Rpdj48L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLXRleHQpO2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMDMpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxMnB4O21hcmdpbi1ib3R0b206MTBweCI+XHVkODNkXHVkY2ExICcrbS5hZHYrJzwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgxNDBweCwxZnIpKTtnYXA6OHB4Ij4nOwogICAgdmFyIGRjb2w9ZC5kaXN0X2NvdW50Pj01Pyd2YXIoLS1yZWQyKSc6ZC5kaXN0X2NvdW50Pj0zPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tZ3JlZW4pJzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4Ij5EQVx1MDExZUlUSU0gR1x1MDBkY05cdTAwZGMgKDI1Ryk8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JytkY29sKyciPicrZC5kaXN0X2NvdW50KycgLyA1PC9kaXY+PC9kaXY+JzsKICAgIGlmKGQuZnRkKXsKICAgICAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHgiPkZURDwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicrZC5mdGQuZGF0ZSsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tZ3JlZW4pIj4rJScrZC5mdGQuZ2FpbisnICgnK2QuZnRkLmRheSsnLiBnXHUwMGZjbik8L2Rpdj48L2Rpdj4nOwogICAgfSBlbHNlIGlmKGQucmFsbHlfZGF5PjApewogICAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweCI+VE9QQVJMQU5NQTwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS15ZWxsb3cpIj4nK2QucmFsbHlfZGF5KycuIGdcdTAwZmNuPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkZURCBwZW5jZXJlc2k6IDQtMTAuIGdcdTAwZmNuPC9kaXY+PC9kaXY+JzsKICAgICAgaWYoZC5yYWxseV9sb3cpIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4Ij5cdTAxMzBQVEFMIFNFVlx1MDEzMFlFU1x1MDEzMDwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1yZWQyKSI+JytkLnJhbGx5X2xvdysnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPmRlbmVtZSBkaWJpIGtcdTAxMzFyXHUwMTMxbFx1MDEzMXJzYSBzYXlhXHUwMGU3IHNcdTAxMzFmXHUwMTMxcmxhblx1MDEzMXI8L2Rpdj48L2Rpdj4nOwogICAgfSBlbHNlIHsKICAgICAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHgiPlRPUEFSTEFOTUE8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tbXV0ZWQpIj5cdTIwMTQ8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaCs9JzwvZGl2Pic7CiAgICBpZihkLmRpc3RfZGF5cyYmZC5kaXN0X2RheXMubGVuZ3RoKXsKICAgICAgaCs9JzxkaXYgc3R5bGU9Im1hcmdpbi10b3A6MTBweDtmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlNvbiBkYVx1MDExZlx1MDEzMXRcdTAxMzFtIGdcdTAwZmNubGVyaTogJytkLmRpc3RfZGF5cy5tYXAoZnVuY3Rpb24oeCl7cmV0dXJuIHguZGF0ZSsnICgnK3guY2hnKyclKSc7fSkuam9pbignIFx1MDBiNyAnKSsnPC9kaXY+JzsKICAgIH0KICAgIGgrPSc8L2Rpdj4nOwogIH0pOwogIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweCI+JzsKICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij5cdWQ4M2RcdWRjY2IgMyBBZFx1MDEzMW1sXHUwMTMxIFBsYW48L2Rpdj4nOwogIGgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtsaW5lLWhlaWdodDoxLjg7Y29sb3I6dmFyKC0tdGV4dCkiPic7CiAgaCs9JzFcdWZlMGZcdTIwZTMgPHN0cm9uZz5EXHUwMGZjemVsdG1lZGU6PC9zdHJvbmc+IE5ha2l0IFNHT1ZcdTIwMTlkYSBiZWtsZXIsIG1ldmN1dCBwb3ppc3lvbmxhcmRhIHN0b3AgZGlzaXBsaW5pLjxicj4nOwogIGgrPScyXHVmZTBmXHUyMGUzIDxzdHJvbmc+QmVrbGVya2VuOjwvc3Ryb25nPiBTY3JlZW5lciArIERlXHUwMTFmZXJsZW1lIHNla21lc2l5bGUgUlNcdTIwMTlpIHlcdTAwZmNrc2VrLCBiYXogeWFwYW4gbGlkZXJsZXJpIGlcdTAxNWZhcmV0bGUuPGJyPic7CiAgaCs9JzNcdWZlMGZcdTIwZTMgPHN0cm9uZz5GVEQgZ2VsaW5jZTo8L3N0cm9uZz4gS2FkZW1lbGkgZ2lyaVx1MDE1ZiBcdTIwMTQgXHUwMGY2bmNlIGtcdTAwZmNcdTAwZTdcdTAwZmNrIHRlc3QgcG96aXN5b251LCB0ZXlpdCBnZWxpcnNlIHBpdm90IGtcdTAxMzFyYW5sYXJsYSBiXHUwMGZjeVx1MDBmY3QuJzsKICBoKz0nPC9kaXY+PC9kaXY+JzsKICBoKz0nPC9kaXY+JzsKICBncmlkLmlubmVySFRNTD1oOwp9CgoKZnVuY3Rpb24gcmVuZGVyVmFsdWF0aW9uKCl7CiAgdmFyIGNvbnRhaW5lciA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgaWYoIWNvbnRhaW5lcikgcmV0dXJuOwogIC8vIE92ZXJyaWRlIGdyaWQgbGF5b3V0IHNvIHRhYmxlIHNwYW5zIGZ1bGwgd2lkdGgKICBjb250YWluZXIuc3R5bGUuZGlzcGxheSA9ICdibG9jayc7CiAgY29udGFpbmVyLnN0eWxlLndpZHRoID0gJzEwMCUnOwogIGNvbnRhaW5lci5pbm5lckhUTUwgPSAnPGRpdiBzdHlsZT0icGFkZGluZzoxNnB4O3dpZHRoOjEwMCU7Ym94LXNpemluZzpib3JkZXItYm94Ij48aDIgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tYm90dG9tOjRweCI+8J+SjiBEZcSfZXJsZW1lIEFuYWxpemk8L2gyPjxwIHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbToxNnB4Ij5XYXRjaGxpc3QgaGlzc2VsZXJpbmluIHRlbWVsIGRlxJ9lcmxlbWUgbWV0cmlrbGVyaSBrYXLFn8SxbGHFn3TEsXJtYXPEsTwvcD48ZGl2IGlkPSJ2YWx1YXRpb24tZ3JpZCIgc3R5bGU9IndpZHRoOjEwMCU7b3ZlcmZsb3cteDphdXRvOy13ZWJraXQtb3ZlcmZsb3ctc2Nyb2xsaW5nOnRvdWNoIj48L2Rpdj48L2Rpdj4nOwogIHZhciBjb250YWluZXIgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgndmFsdWF0aW9uLWdyaWQnKTsKICBpZighY29udGFpbmVyKSByZXR1cm47CiAgdmFyIGRhdGEgPSAoVEZfREFUQSAmJiBURl9EQVRBWycxZCddKSA/IFRGX0RBVEFbJzFkJ10gOiBbXTsKICBpZighZGF0YS5sZW5ndGgpe2NvbnRhaW5lci5pbm5lckhUTUw9JzxwIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCk7cGFkZGluZzoyMHB4Ij5WZXJpIHlvazwvcD4nO3JldHVybjt9CgogIHZhciBtZXRyaWNzID0gWwogICAge2tleTonZXBzX2dyb3d0aCcsICAgbGFiZWw6J0VQUyUnLCAgICBkZXNjOidTb24gY2V5cmVrIEVQUyBidXl1bWUgb3JhbmkgKHlpbGxpaykuIENBTlNMSU0gQyBrcml0ZXJpIOKAlCBlbiBrcml0aWsgbWV0cmlrLiBTZWt0b3J1bmRlIGxpZGVyIGthemFuYyBhcnRpc2kgbGF6aW0uJywgIGlkZWFsOic+MjAlIGlkZWFsLCA+MzAlIGd1Y2x1JywgICAgICAgICBsbzoyMCwgaGk6MTAwLCBmbXQ6JyUnLCBoYjp0cnVlfSwKICAgIHtrZXk6J3Jldl9ncm93dGgnLCAgIGxhYmVsOidHZWxpciUnLCAgZGVzYzonU29uIGNleXJlayBnZWxpciBidXl1bWUgb3JhbmkuIENBTlNMSU0gQSBrcml0ZXJpLiBTaXJrZXRpbiBwYXphciBwYXlpbmkgdmUgbW9tZW50dW0gZ3VjdW51IGdvc3RlcmlyLicsICAgICAgICAgICAgICAgIGlkZWFsOic+MTUlIGl5aSwgPjI1JSBndWNsdScsICAgICAgICAgICBsbzoxNSwgaGk6MTAwLCBmbXQ6JyUnLCBoYjp0cnVlfSwKICAgIHtrZXk6J3BlX2Z3ZCcsICAgIGxhYmVsOidJbGVyaSBGL0snLCAgZGVzYzonT251bcO8emRla2kgMTIgYXkgdGFobWluaSBrYXphbmNpbmEgZ29yZSBGL0suIFBpeWFzYW5pbiBidXl1bWUgYmVrbGVudGlzaW5pIHlhbnNpdGlyLiBCdXl1bWV5bGUga2Fyc2lsYXN0aXJtYWsgb25lbWxpLicsIGlkZWFsOic8MjUgaWRlYWwsIDwzNSBrYWJ1bCcsICAgICAgICAgIGxvOjAsICBoaToyNSwgIGZtdDoneCcsIGhiOmZhbHNlfSwKICAgIHtrZXk6J3BlZycsICAgICAgIGxhYmVsOidQRUcnLCAgICAgICAgZGVzYzonRi9LIG9yYW5pbmkgRVBTIGJ1eXVtZSBoaXppIGlsZSBrYXJzaWxhc3RpcmlyLiBFbiBkZW5nZWxpIGRlZ2VybGVtZSBtZXRyacSfaTogMSBhbHRpbmRhIHVjdXosIDEtMiBtYWt1bCwgMiB1c3R1IHBhaGFsaS4nLCBpZGVhbDonPDEgVWN1eiwgMS0yIE1ha3VsLCA+MiBQYWhhbGknLCBsbzowLCBoaToyLCAgIGZtdDoneCcsIGhiOmZhbHNlfSwKICAgIHtrZXk6J2dyb3NzX21hcmdpbicsIGxhYmVsOidCcnV0JScsICAgZGVzYzonQnJ1dCBrYXIgbWFyamluaS4gU2lya2V0aW4gZml5YXRsYW1hIGd1Y3VudSB2ZSB1cnVuIGthbGl0ZXNpbmkgZ29zdGVyaXIuIFl1a3NlayBtYXJqaW4gcmVrYWJldCB1c3R1bmx1Z3UgaXNhcmV0bGVyLicsICAgaWRlYWw6J1lhemlsaW0gPjcwJSwgR2VuZWwgPjQwJScsICAgICAgIGxvOjQwLCBoaToxMDAsIGZtdDonJScsIGhiOnRydWV9LAogICAge2tleTonbmV0X21hcmdpbicsICAgbGFiZWw6J05ldCUnLCAgICBkZXNjOidOZXQga2FyIG1hcmppbmkuIFR1bSBnaWRlcmxlciBkdXN1bGR1a3RlbiBzb25yYSBrYWxhbiBrYXIgeXV6ZGVzaS4gT3BlcmFzeW9uZWwgdmVyaW1saWxpZ2kgZ29zdGVyaXIuJywgICAgICAgICAgICAgICAgICBpZGVhbDonPjEwJSBpeWksID4yMCUgbXVrZW1tZWwnLCAgICAgICAgbG86MTAsIGhpOjEwMCwgZm10OiclJywgaGI6dHJ1ZX0sCiAgICB7a2V5Oidyb2UnLCAgICAgICAgICBsYWJlbDonT0tHJywgICAgIGRlc2M6J096c2VybWF5ZSBLYXJsaWxpZ2kgKFJPRSkuIENBTlNMSU0gTiBrcml0ZXJpOiB5b25ldGltaW4gc2VybWF5ZXlpIG5lIGthZGFyIHZlcmltbGkga3VsbGFuZGlnaW5pIG9sY2VyLicsICAgICAgICAgICAgICAgaWRlYWw6Jz4xNSUgaXlpLCA+MjUlIG11a2VtbWVsJywgICAgICAgIGxvOjE1LCBoaToxMDAsIGZtdDonJScsIGhiOnRydWV9LAogICAge2tleToncGVfdHRtJywgICAgbGFiZWw6J0YvSycsICAgICAgICBkZXNjOidTb24gMTIgYXkgZ2VyY2VrIGthemFuY2luYSBnb3JlIGZpeWF0L2themFuYyBvcmFuaS4gVGFyaWhpIGthcnNpbGFzdGlybWEgaWNpbiBrdWxsYW5pbGlyLicsICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlkZWFsOidUZWtub2xvamkgPDM1LCBHZW5lbCA8MjUnLCAgICAgICBsbzowLCAgaGk6MzUsICBmbXQ6J3gnLCBoYjpmYWxzZX0sCiAgICB7a2V5OidwcycsICAgICAgICBsYWJlbDonRi9TJywgICAgICAgIGRlc2M6J0ZpeWF0IC8gU2F0aXNsYXIuIEhlbnV6IGthcnNpeiB2ZXlhIGhpemxpIGJ1eXV5ZW4gc2lya2V0bGVyaSBkZWdlcmxlbmRpcm1layBpY2luIGt1bGxhbmlsaXIuJywgICAgICAgICAgICAgICAgICAgICAgICAgaWRlYWw6J1Rla25vbG9qaSA8OCwgR2VuZWwgPDMnLCAgICAgICAgIGxvOjAsICBoaTo4LCAgIGZtdDoneCcsIGhiOmZhbHNlfSwKICAgIHtrZXk6J3BiJywgICAgICAgIGxhYmVsOidGL0REJywgICAgICAgZGVzYzonRml5YXQgLyBEZWZ0ZXIgRGVnZXJpLiBTaXJrZXRpbiBuZXQgdmFybGlrbGFyaW5hIGdvcmUgZml5YXRpbmkgZ29zdGVyaXIuIE5lZ2F0aWYgb3pzZXJtYXllZGUgYW5sYW1zaXpkaXIuJywgICAgICAgICAgICBpZGVhbDonPDMgVWN1eiwgMy03IE1ha3VsLCA+NyBQYWhhbGknLCBsbzowLCAgaGk6NSwgICBmbXQ6J3gnLCBoYjpmYWxzZX0sCiAgICB7a2V5OidhbmFseXN0X3RhcmdldCcsIGxhYmVsOidIZWRlZicsIGRlc2M6J0FuYWxpc3Qga29uc2Vuc3VzIGhlZGVmIGZpeWF0aS4gWXV6ZGUgdXBzaWRlIG1ldmN1dCBmaXlhdGEgZ29yZSBoZXNhcGxhbm1pc3Rpci4gU29uIGtvbnRyb2wgbm9rdGFzaS4nLCAgICAgICAgICAgICAgICAgaWRlYWw6J01ldmN1dCBmaXlhdHRhbiB5dWtzZWsgb2xzdW4nLCAgIGxvOjAsICBoaTowLCAgIGZtdDonJCcsIGhiOnRydWV9LAogIF07CgogIGZ1bmN0aW9uIHRpcChsYmwsZGVzYyxpZGVhbCl7CiAgICByZXR1cm4gbGJsKyc8c3BhbiBzdHlsZT0iY3Vyc29yOmhlbHA7d2lkdGg6MTJweDtoZWlnaHQ6MTJweDtib3JkZXItcmFkaXVzOjUwJTtiYWNrZ3JvdW5kOnJnYmEoMjU1LDI1NSwyNTUsLjEpO2NvbG9yOnZhcigtLW11dGVkKTtmb250LXNpemU6OHB4O2ZvbnQtd2VpZ2h0OjcwMDtkaXNwbGF5OmlubGluZS1mbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO21hcmdpbi1sZWZ0OjNweDtmbGV4LXNocmluazowO3ZlcnRpY2FsLWFsaWduOm1pZGRsZSIgdGl0bGU9IicrZGVzYysnICB8ICBJZGVhbDogJytpZGVhbCsnIj4/PC9zcGFuPic7CiAgfQogIGZ1bmN0aW9uIGNvbE9mKHZhbCxsbyxoaSxoYil7CiAgICBpZih2YWw9PT1udWxsfHx2YWw9PT11bmRlZmluZWQpcmV0dXJuICd2YXIoLS1tdXRlZCknOwogICAgdmFyIG49cGFyc2VGbG9hdCh2YWwpO2lmKGlzTmFOKG4pKXJldHVybiAndmFyKC0tbXV0ZWQpJzsKICAgIGlmKGhiKXtyZXR1cm4gbj49aGkqMC43Pyd2YXIoLS1ncmVlbiknOm4+PWxvPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tcmVkMiknO30KICAgIGVsc2UgIHtyZXR1cm4gbjw9bG8qMS4yPyd2YXIoLS1ncmVlbiknOm48PWhpPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tcmVkMiknO30KICB9CiAgZnVuY3Rpb24gZm10Vih2YWwsZm10LHByaWNlKXsKICAgIGlmKHZhbD09PW51bGx8fHZhbD09PXVuZGVmaW5lZClyZXR1cm4gJzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPuKAlDwvc3Bhbj4nOwogICAgdmFyIG49cGFyc2VGbG9hdCh2YWwpO2lmKGlzTmFOKG4pKXJldHVybiAnPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+4oCUPC9zcGFuPic7CiAgICBpZihmbXQ9PT0neCcpcmV0dXJuIG4udG9GaXhlZCgxKSsneCc7CiAgICBpZihmbXQ9PT0nJScpcmV0dXJuIG4udG9GaXhlZCgxKSsnJSc7CiAgICBpZihmbXQ9PT0nJCcpewogICAgICB2YXIgdXA9cHJpY2U+MD8oKG4tcHJpY2UpL3ByaWNlKjEwMCkudG9GaXhlZCgxKTpudWxsOwogICAgICB2YXIgYz0odXAhPT1udWxsJiZwYXJzZUZsb2F0KHVwKT4wKT8ndmFyKC0tZ3JlZW4pJzondmFyKC0tcmVkMiknOwogICAgICByZXR1cm4gJyQnK24udG9GaXhlZCgwKSsodXAhPT1udWxsPycgPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6JytjKyciPicrKHBhcnNlRmxvYXQodXApPjA/JysnOicnKSt1cCsnJTwvc3Bhbj4nOicnKTsKICAgIH0KICAgIHJldHVybiBTdHJpbmcobik7CiAgfQoKICB2YXIgcm93cz1kYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KTsKICB2YXIgaHRtbD0nPHRhYmxlIHN0eWxlPSJ3aWR0aDoxMDAlO2JvcmRlci1jb2xsYXBzZTpjb2xsYXBzZTtmb250LXNpemU6MTFweDttaW4td2lkdGg6NzAwcHgiPic7CiAgaHRtbCs9Jzx0aGVhZD48dHIgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKSI+JzsKICBodG1sKz0nPHRoIHN0eWxlPSJ0ZXh0LWFsaWduOmxlZnQ7cGFkZGluZzoxMHB4O2NvbG9yOnZhcigtLW11dGVkKTtmb250LXdlaWdodDo2MDAiPkhpc3NlPC90aD4nOwogIGh0bWwrPSc8dGggc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7cGFkZGluZzoxMHB4IDhweDtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC13ZWlnaHQ6NjAwIj5GaXlhdDwvdGg+JzsKICBtZXRyaWNzLmZvckVhY2goZnVuY3Rpb24obW0pe2h0bWwrPSc8dGggc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7cGFkZGluZzo4cHggNHB4O2NvbG9yOnZhcigtLW11dGVkKTtmb250LXdlaWdodDo2MDA7d2hpdGUtc3BhY2U6bm93cmFwO2ZvbnQtc2l6ZToxMHB4Ij4nK3RpcChtbS5sYWJlbCxtbS5kZXNjLG1tLmlkZWFsKSsnPC90aD4nO30pOwogIGh0bWwrPSc8L3RyPjwvdGhlYWQ+PHRib2R5Pic7CgogIHJvd3MuZm9yRWFjaChmdW5jdGlvbihyLGkpewogICAgdmFyIGJnPWklMj09PTA/J3ZhcigtLWJnKSc6J3JnYmEoMjU1LDI1NSwyNTUsLjAyKSc7CiAgICB2YXIgaW5QPXIucG9ydGZvbGlvOwogICAgaHRtbCs9Jzx0ciBzdHlsZT0iYmFja2dyb3VuZDonK2JnKyc7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDMpIj4nOwogICAgaHRtbCs9Jzx0ZCBzdHlsZT0icGFkZGluZzoxMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonKyhpblA/J3ZhcigtLWdyZWVuKSc6J3ZhcigtLXRleHQpJykrJyI+JytyLnRpY2tlcisoaW5QPyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjhweDtiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2NvbG9yOnZhcigtLWdyZWVuKTtwYWRkaW5nOjFweCA0cHg7Ym9yZGVyLXJhZGl1czozcHg7bWFyZ2luLWxlZnQ6NHB4Ij5QPC9zcGFuPic6JycpKyc8L3RkPic7CiAgICBodG1sKz0nPHRkIHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O3BhZGRpbmc6OHB4IDRweDtjb2xvcjp2YXIoLS10ZXh0KTtmb250LXdlaWdodDo2MDA7Zm9udC1zaXplOjEwcHgiPiQnK3IuZml5YXQrJzwvdGQ+JzsKICAgIG1ldHJpY3MuZm9yRWFjaChmdW5jdGlvbihtbSl7CiAgICAgIHZhciB2YWw9bW0ua2V5PT09J2FuYWx5c3RfdGFyZ2V0Jz9yLmZhaXJfcHJpY2VfYW5hbHlzdDpyW21tLmtleV07CiAgICAgIHZhciBjb2w9bW0ua2V5PT09J2FuYWx5c3RfdGFyZ2V0Jz8oci5mYWlyX3ByaWNlX2FuYWx5c3QmJnIuZmFpcl9wcmljZV9hbmFseXN0PnIuZml5YXQ/J3ZhcigtLWdyZWVuKSc6J3ZhcigtLXJlZDIpJyk6Y29sT2YodmFsLG1tLmxvLG1tLmhpLG1tLmhiKTsKICAgICAgaHRtbCs9Jzx0ZCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjEwcHggOHB4O2NvbG9yOicrY29sKyciPicrZm10Vih2YWwsbW0uZm10LHIuZml5YXQpKyc8L3RkPic7CiAgICB9KTsKICAgIGh0bWwrPSc8L3RyPic7CiAgfSk7CgogIGh0bWwrPSc8L3Rib2R5PjwvdGFibGU+JzsKICBodG1sKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxNnB4O21hcmdpbi10b3A6MTBweDtmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPic7CiAgaHRtbCs9JzxzcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbikiPuKXjzwvc3Bhbj4gSXlpPC9zcGFuPic7CiAgaHRtbCs9JzxzcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS15ZWxsb3cpIj7il488L3NwYW4+IE1ha3VsPC9zcGFuPic7CiAgaHRtbCs9JzxzcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKSI+4pePPC9zcGFuPiBEaWtrYXQ8L3NwYW4+JzsKICBodG1sKz0nPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+4oCUID0gVmVyaSB5b2s8L3NwYW4+JzsKICBodG1sKz0nPHNwYW4gc3R5bGU9Im1hcmdpbi1sZWZ0OmF1dG8iPjxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2NvbG9yOnZhcigtLWdyZWVuKTtwYWRkaW5nOjFweCA0cHg7Ym9yZGVyLXJhZGl1czozcHgiPlA8L3NwYW4+IFBvcnRmb3k8L3NwYW4+PC9kaXY+JzsKICBjb250YWluZXIuaW5uZXJIVE1MPWh0bWw7Cn0KPC9zY3JpcHQ+Cgo8L2JvZHk+CjwvaHRtbD4="
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


def build_html(tf_data, timestamp, earnings_data=None, market_data=None, news_data=None, ai_analyses=None, weekly_data=None, canslim_results=None, direction_data=None):
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
    weekly_json   = json.dumps(weekly_data    or {}, ensure_ascii=False)
    screener_json = json.dumps(canslim_results or [], ensure_ascii=False)
    html = html.replace("%%AI_DATA%%",        ai_json)
    html = html.replace("%%WEEKLY_DATA%%",    weekly_json)
    html = html.replace("%%SCREENER_DATA%%",  screener_json)
    direction_json = json.dumps(direction_data or {}, ensure_ascii=False)
    html = html.replace("%%DIRECTION_DATA%%", direction_json)
    html = html.replace("%%PORT%%",          port_json)
    html = html.replace("%%GITHUB_TOKEN%%",  "")
    html = html.replace("%%GITHUB_USER%%",  GITHUB_USER)
    html = html.replace("%%GITHUB_REPO%%",  GITHUB_REPO)
    return html

# ── ANA TARAMA ────────────────────────────────────────────────
print('\n📊 Hisse analizi yapiliyor...')
tf_data = {}
for tf_key, tf_cfg in TF_CONFIG.items():
    print(f'  {tf_cfg["label"]} zaman dilimi...')
    tf_results = []
    for i, ticker in enumerate(WATCHLIST, 1):
        print(f'  [{i:2}/{len(WATCHLIST)}] {tf_cfg["label"]} {ticker:<6}...', end=' ', flush=True)
        r = analyze(ticker, period=tf_cfg['period'], interval=tf_cfg['interval'])
        tf_results.append(r)
        print(r.get('sinyal', 'HATA'))
    tf_data[tf_key] = tf_results
print(f'\nTarama tamamlandi! {len(TF_CONFIG)} zaman dilimi x {len(WATCHLIST)} hisse')

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
html = build_html(tf_data, timestamp, earnings_data, market_data, news_data, ai_analyses, weekly_data, canslim_results, direction_data)
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
