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
    _T = "PCFET0NUWVBFIGh0bWw+CjxodG1sIGxhbmc9InRyIj4KPGhlYWQ+CjxtZXRhIGNoYXJzZXQ9IlVURi04Ii8+CjxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsaW5pdGlhbC1zY2FsZT0xIi8+Cjx0aXRsZT5DQU5TTElNIFNjYW5uZXI8L3RpdGxlPgo8bGluayByZWw9Imljb24iIHR5cGU9ImltYWdlL3N2Zyt4bWwiIGhyZWY9ImRhdGE6aW1hZ2Uvc3ZnK3htbCwlM0NzdmcgeG1sbnM9J2h0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnJyB2aWV3Qm94PScwIDAgMzIgMzInJTNFJTNDcmVjdCB3aWR0aD0nMzInIGhlaWdodD0nMzInIHJ4PSc2JyBmaWxsPSclMjMwZDExMTcnLyUzRSUzQ3BvbHlsaW5lIHBvaW50cz0nNCwyNCAxMCwxNiAxNiwyMCAyMiwxMCAyOCwxNCcgZmlsbD0nbm9uZScgc3Ryb2tlPSclMjMxMGI5ODEnIHN0cm9rZS13aWR0aD0nMi41JyBzdHJva2UtbGluZWNhcD0ncm91bmQnIHN0cm9rZS1saW5lam9pbj0ncm91bmQnLyUzRSUzQy9zdmclM0UiPgo8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PVNwYWNlK0dyb3Rlc2s6d2dodEA0MDA7NTAwOzYwMDs3MDAmZmFtaWx5PUJlYmFzK05ldWUmZmFtaWx5PUpldEJyYWlucytNb25vOndnaHRANDAwOzYwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCIvPgo8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9jaGFydC5qc0A0LjQuMC9kaXN0L2NoYXJ0LnVtZC5taW4uanMiPjwvc2NyaXB0Pgo8c3R5bGU+Cjpyb290ey0tYmc6IzA1MDcwZjstLWJnMjojMGQxMTE3Oy0tYmczOiMxNjFiMjQ7LS1ib3JkZXI6cmdiYSgyNTUsMjU1LDI1NSwwLjA4KTstLXRleHQ6I2UyZThmMDstLW11dGVkOiM0YjU1NjM7LS1ncmVlbjojMTBiOTgxOy0tZ3JlZW4yOiMzNGQzOTk7LS1yZWQ6I2VmNDQ0NDstLXJlZDI6I2Y4NzE3MTstLXllbGxvdzojZjU5ZTBiO30KKntib3gtc2l6aW5nOmJvcmRlci1ib3g7bWFyZ2luOjA7cGFkZGluZzowfQpib2R5e2JhY2tncm91bmQ6dmFyKC0tYmcpO2NvbG9yOnZhcigtLXRleHQpO2ZvbnQtZmFtaWx5OidTcGFjZSBHcm90ZXNrJyxzYW5zLXNlcmlmO21pbi1oZWlnaHQ6MTAwdmh9Ci5oZWFkZXJ7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCMwZDExMTcsIzExMTgyNyk7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtwYWRkaW5nOjE0cHggMjBweDtwb3NpdGlvbjpzdGlja3k7dG9wOjA7ei1pbmRleDoxMDB9Ci5oZWFkZXItaW5uZXJ7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTBweDttYXgtd2lkdGg6MTQwMHB4O21hcmdpbjowIGF1dG99Ci5sb2dvLW1haW57Zm9udC1mYW1pbHk6J0JlYmFzIE5ldWUnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjIycHg7bGV0dGVyLXNwYWNpbmc6NHB4O2JhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZywjMTBiOTgxLCMzYjgyZjYpOy13ZWJraXQtYmFja2dyb3VuZC1jbGlwOnRleHQ7LXdlYmtpdC10ZXh0LWZpbGwtY29sb3I6dHJhbnNwYXJlbnR9Ci50aW1lc3RhbXB7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLmxpdmUtZG90e3dpZHRoOjdweDtoZWlnaHQ6N3B4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6dmFyKC0tZ3JlZW4pO2FuaW1hdGlvbjpwdWxzZSAycyBpbmZpbml0ZTtkaXNwbGF5OmlubGluZS1ibG9jazttYXJnaW4tcmlnaHQ6NXB4fQpAa2V5ZnJhbWVzIHB1bHNlezAlLDEwMCV7b3BhY2l0eToxO2JveC1zaGFkb3c6MCAwIDAgMCByZ2JhKDE2LDE4NSwxMjksLjQpfTUwJXtvcGFjaXR5Oi43O2JveC1zaGFkb3c6MCAwIDAgNnB4IHJnYmEoMTYsMTg1LDEyOSwwKX19Ci5uYXZ7ZGlzcGxheTpmbGV4O2dhcDo0cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7b3ZlcmZsb3cteDphdXRvO2ZsZXgtd3JhcDp3cmFwfQoudGFie3BhZGRpbmc6NnB4IDE0cHg7Ym9yZGVyLXJhZGl1czo2cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NTAwO2JvcmRlcjoxcHggc29saWQgdHJhbnNwYXJlbnQ7YmFja2dyb3VuZDpub25lO2NvbG9yOnZhcigtLW11dGVkKTt0cmFuc2l0aW9uOmFsbCAuMnM7d2hpdGUtc3BhY2U6bm93cmFwfQoudGFiOmhvdmVye2NvbG9yOnZhcigtLXRleHQpO2JhY2tncm91bmQ6dmFyKC0tYmczKX0KLnRhYi5hY3RpdmV7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLXRleHQpO2JvcmRlci1jb2xvcjp2YXIoLS1ib3JkZXIpfQoudGFiLnBvcnQuYWN0aXZle2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyLWNvbG9yOnJnYmEoMTYsMTg1LDEyOSwuMyl9Ci50Zi1yb3d7ZGlzcGxheTpmbGV4O2dhcDo2cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7YWxpZ24taXRlbXM6Y2VudGVyO2ZsZXgtd3JhcDp3cmFwfQoudGYtYnRue3BhZGRpbmc6NXB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Y3Vyc29yOnBvaW50ZXI7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO3RyYW5zaXRpb246YWxsIC4yc30KLnRmLWJ0bi5hY3RpdmV7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtjb2xvcjojNjBhNWZhO2JvcmRlci1jb2xvcjpyZ2JhKDU5LDEzMCwyNDYsLjQpfQoudGYtYnRuLnN0YXJ7cG9zaXRpb246cmVsYXRpdmV9Ci50Zi1idG4uc3Rhcjo6YWZ0ZXJ7Y29udGVudDon4piFJztwb3NpdGlvbjphYnNvbHV0ZTt0b3A6LTVweDtyaWdodDotNHB4O2ZvbnQtc2l6ZTo4cHg7Y29sb3I6dmFyKC0teWVsbG93KX0KLnRmLWhpbnR7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpfQouc3RhdHN7ZGlzcGxheTpmbGV4O2dhcDo4cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7ZmxleC13cmFwOndyYXB9Ci5waWxse2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjVweDtwYWRkaW5nOjRweCAxMHB4O2JvcmRlci1yYWRpdXM6MjBweDtmb250LXNpemU6MTFweDtmb250LXdlaWdodDo2MDA7Ym9yZGVyOjFweCBzb2xpZH0KLnBpbGwuZ3tiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMSk7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlci1jb2xvcjpyZ2JhKDE2LDE4NSwxMjksLjI1KX0KLnBpbGwucntiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xKTtjb2xvcjp2YXIoLS1yZWQyKTtib3JkZXItY29sb3I6cmdiYSgyMzksNjgsNjgsLjI1KX0KLnBpbGwueXtiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMSk7Y29sb3I6dmFyKC0teWVsbG93KTtib3JkZXItY29sb3I6cmdiYSgyNDUsMTU4LDExLC4yNSl9Ci5waWxsLmJ7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjEpO2NvbG9yOiM2MGE1ZmE7Ym9yZGVyLWNvbG9yOnJnYmEoNTksMTMwLDI0NiwuMjUpfQoucGlsbC5te2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Ym9yZGVyLWNvbG9yOnZhcigtLWJvcmRlcil9Ci5kb3R7d2lkdGg6NXB4O2hlaWdodDo1cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpjdXJyZW50Q29sb3J9Ci5tYWlue3BhZGRpbmc6MTRweCAyMHB4O21heC13aWR0aDoxNDAwcHg7bWFyZ2luOjAgYXV0b30KLmdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgzMDBweCwxZnIpKTtnYXA6MTBweH0KQG1lZGlhKG1heC13aWR0aDo0ODBweCl7LmdyaWR7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmcn19Ci5jYXJke2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O292ZXJmbG93OmhpZGRlbjtjdXJzb3I6cG9pbnRlcjt0cmFuc2l0aW9uOmFsbCAuMnN9Ci5jYXJkOmhvdmVye3RyYW5zZm9ybTp0cmFuc2xhdGVZKC0ycHgpO2JveC1zaGFkb3c6MCA4cHggMjRweCByZ2JhKDAsMCwwLC40KX0KLmFjY2VudHtoZWlnaHQ6M3B4fQouY2JvZHl7cGFkZGluZzoxMnB4IDE0cHh9Ci5jdG9we2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpmbGV4LXN0YXJ0O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206OHB4fQoudGlja2Vye2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyMHB4O2xldHRlci1zcGFjaW5nOjJweDtsaW5lLWhlaWdodDoxfQouY3Bye3RleHQtYWxpZ246cmlnaHR9Ci5wdmFse2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTVweDtmb250LXdlaWdodDo2MDB9Ci5wY2hne2ZvbnQtc2l6ZToxMXB4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTttYXJnaW4tdG9wOjJweH0KLmJhZGdle2Rpc3BsYXk6aW5saW5lLWJsb2NrO3BhZGRpbmc6MnB4IDhweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6LjVweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLXRvcDozcHh9Ci5wb3J0LWJhZGdle2Rpc3BsYXk6aW5saW5lLWZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDozcHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwO2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xMik7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yNSk7bWFyZ2luLWxlZnQ6NXB4fQouc2lnc3tkaXNwbGF5OmZsZXg7ZmxleC13cmFwOndyYXA7Z2FwOjNweDttYXJnaW4tYm90dG9tOjhweH0KLnNwe2ZvbnQtc2l6ZTo5cHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLnNne2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbjIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKX0KLnNie2JhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjEpO2NvbG9yOnZhcigtLXJlZDIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpfQouc257YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLW11dGVkKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5jaGFydC13e2hlaWdodDo3NXB4O21hcmdpbi10b3A6OHB4fQoubHZsc3tkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgzLDFmcik7Z2FwOjVweDttYXJnaW4tdG9wOjhweH0KLmx2e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjVweDtwYWRkaW5nOjZweDt0ZXh0LWFsaWduOmNlbnRlcjtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5sbHtmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MnB4fQoubHZhbHtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwfQoub3ZlcmxheXtwb3NpdGlvbjpmaXhlZDtpbnNldDowO2JhY2tncm91bmQ6cmdiYSgwLDAsMCwuODgpO3otaW5kZXg6MTAwMDtkaXNwbGF5Om5vbmU7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7cGFkZGluZzoxNnB4fQoub3ZlcmxheS5vcGVue2Rpc3BsYXk6ZmxleH0KLm1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjUyMHB4O21heC1oZWlnaHQ6OTJ2aDtvdmVyZmxvdy15OmF1dG99Ci5taGVhZHtwYWRkaW5nOjE4cHggMThweCAwO2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpmbGV4LXN0YXJ0fQoubXRpdGxle2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZTozMHB4O2xldHRlci1zcGFjaW5nOjNweH0KLm1jbG9zZXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTt3aWR0aDozMHB4O2hlaWdodDozMHB4O2JvcmRlci1yYWRpdXM6N3B4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxNXB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcn0KLm1ib2R5e3BhZGRpbmc6MTRweCAxOHB4IDE4cHh9Ci5tY2hhcnR3e2hlaWdodDoxNTBweDttYXJnaW4tYm90dG9tOjE0cHh9Ci5kZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjdweDttYXJnaW4tYm90dG9tOjEycHh9Ci5kY3tiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo3cHg7cGFkZGluZzo5cHggMTFweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5kbHtmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206M3B4fQouZHZ7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMH0KLmRib3h7Ym9yZGVyLXJhZGl1czo5cHg7cGFkZGluZzoxM3B4O21hcmdpbi1ib3R0b206MTJweDtib3JkZXI6MXB4IHNvbGlkfQouZGxibHtmb250LXNpemU6OXB4O2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo1cHh9Ci5kdmVyZHtmb250LWZhbWlseTonQmViYXMgTmV1ZScsc2Fucy1zZXJpZjtmb250LXNpemU6MjZweDtsZXR0ZXItc3BhY2luZzoycHg7bWFyZ2luLWJvdHRvbTo4cHh9Ci5kcm93e2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjRweDtmb250LXNpemU6MTJweH0KLmRrZXl7Y29sb3I6dmFyKC0tbXV0ZWQpfQoucnJiYXJ7aGVpZ2h0OjRweDtiYWNrZ3JvdW5kOnZhcigtLWJnKTtib3JkZXItcmFkaXVzOjJweDttYXJnaW4tdG9wOjdweDtvdmVyZmxvdzpoaWRkZW59Ci5ycmZpbGx7aGVpZ2h0OjEwMCU7Ym9yZGVyLXJhZGl1czoycHg7dHJhbnNpdGlvbjp3aWR0aCAuOHMgZWFzZX0KLnZwYm94e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjdweDtwYWRkaW5nOjEwcHg7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO21hcmdpbi1ib3R0b206MTJweH0KLnZwdGl0bGV7Zm9udC1zaXplOjlweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo3cHh9Ci52cGdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoMywxZnIpO2dhcDo1cHh9Ci52cGN7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlci1yYWRpdXM6NXB4O3BhZGRpbmc6N3B4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlcjoxcHggc29saWR9Ci5taW5mb3tkaXNwbGF5OmlubGluZS1mbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO3dpZHRoOjE0cHg7aGVpZ2h0OjE0cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpyZ2JhKDk2LDE2NSwyNTAsLjIpO2NvbG9yOiM2MGE1ZmE7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7Y3Vyc29yOnBvaW50ZXI7bWFyZ2luLWxlZnQ6NHB4O2JvcmRlcjoxcHggc29saWQgcmdiYSg5NiwxNjUsMjUwLC4zKX0KLm1pbmZvLXBvcHVwe3Bvc2l0aW9uOmZpeGVkO2luc2V0OjA7YmFja2dyb3VuZDpyZ2JhKDAsMCwwLC44OCk7ei1pbmRleDoyMDAwO2Rpc3BsYXk6bm9uZTthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjtwYWRkaW5nOjE2cHh9Ci5taW5mby1wb3B1cC5vcGVue2Rpc3BsYXk6ZmxleH0KLm1pbmZvLW1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjQ4MHB4O21heC1oZWlnaHQ6ODV2aDtvdmVyZmxvdy15OmF1dG87cGFkZGluZzoyMHB4O3Bvc2l0aW9uOnJlbGF0aXZlfQoubWluZm8tdGl0bGV7Zm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4fQoubWluZm8tc291cmNle2ZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjEycHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4O2ZsZXgtd3JhcDp3cmFwfQoubWluZm8tcmVse3BhZGRpbmc6MnB4IDdweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMH0KLm1pbmZvLXJlbC5oaWdoe2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Y29sb3I6IzEwYjk4MX0KLm1pbmZvLXJlbC5tZWRpdW17YmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjE1KTtjb2xvcjojZjU5ZTBifQoubWluZm8tcmVsLmxvd3tiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Y29sb3I6I2VmNDQ0NH0KLm1pbmZvLWRlc2N7Zm9udC1zaXplOjEycHg7Y29sb3I6Izk0YTNiODtsaW5lLWhlaWdodDoxLjY7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8td2FybmluZ3tiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjZweDtwYWRkaW5nOjhweCAxMHB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOiNmNTllMGI7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8tcmFuZ2Vze21hcmdpbi1ib3R0b206MTRweH0KLm1pbmZvLXJhbmdlLXRpdGxle2ZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHh9Ci5taW5mby1yYW5nZXtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo4cHg7bWFyZ2luLWJvdHRvbTo2cHg7cGFkZGluZzo2cHggOHB4O2JvcmRlci1yYWRpdXM6NnB4O2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMDIpfQoubWluZm8tcmFuZ2UtZG90e3dpZHRoOjhweDtoZWlnaHQ6OHB4O2JvcmRlci1yYWRpdXM6NTAlO2ZsZXgtc2hyaW5rOjB9Ci5taW5mby1jYW5zbGlte2JhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6NnB4O3BhZGRpbmc6OHB4IDEwcHg7Zm9udC1zaXplOjExcHg7Y29sb3I6IzYwYTVmYX0KLm1pbmZvLWNsb3Nle3Bvc2l0aW9uOmFic29sdXRlO3RvcDoxNnB4O3JpZ2h0OjE2cHg7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4xKTtjb2xvcjojOTRhM2I4O3dpZHRoOjI4cHg7aGVpZ2h0OjI4cHg7Ym9yZGVyLXJhZGl1czo3cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjE0cHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyfQo6Oi13ZWJraXQtc2Nyb2xsYmFye3dpZHRoOjRweDtoZWlnaHQ6NHB4fQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRyYWNre2JhY2tncm91bmQ6dmFyKC0tYmcpfQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRodW1ie2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMSk7Ym9yZGVyLXJhZGl1czoycHh9Cjwvc3R5bGU+CjwvaGVhZD4KPGJvZHk+CjxkaXYgY2xhc3M9ImhlYWRlciI+CiAgPGRpdiBjbGFzcz0iaGVhZGVyLWlubmVyIj4KICAgIDxzcGFuIGNsYXNzPSJsb2dvLW1haW4iPkNBTlNMSU0gU0NBTk5FUjwvc3Bhbj4KICAgIDxzcGFuIGNsYXNzPSJ0aW1lc3RhbXAiPjxzcGFuIGNsYXNzPSJsaXZlLWRvdCI+PC9zcGFuPiUlVElNRVNUQU1QJSU8L3NwYW4+CiAgICA8YnV0dG9uIG9uY2xpY2s9Im9wZW5FZGl0TGlzdCgpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMyk7Y29sb3I6IzYwYTVmYTtwYWRkaW5nOjVweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMXB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtZmFtaWx5OmluaGVyaXQiPuKcj++4jyBMaXN0ZXlpIETDvHplbmxlPC9idXR0b24+CiAgPC9kaXY+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJuYXYiPgogIDxidXR0b24gY2xhc3M9InRhYiBhY3RpdmUiIG9uY2xpY2s9InNldFRhYignZGFzaGJvYXJkJyx0aGlzKSI+8J+PoCBEYXNoYm9hcmQ8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignYWxsJyx0aGlzKSI+8J+TiiBIaXNzZWxlcjwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiBwb3J0IiBvbmNsaWNrPSJzZXRUYWIoJ3BvcnQnLHRoaXMpIj7wn5K8IFBvcnRmw7Z5w7xtPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2J1eScsdGhpcykiPvCfk4ggQWw8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignc2VsbCcsdGhpcykiPvCfk4kgU2F0PC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2Vhcm5pbmdzJyx0aGlzKSI+8J+ThSBFYXJuaW5nczwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdydXRpbicsdGhpcykiPuKchSBSdXRpbjwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdoYWZ0YWxpaycsdGhpcykiPvCfk4ggSGFmdGFsxLFrPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ3NjcmVlbmVyJyx0aGlzKSI+8J+UjSBTY3JlZW5lcjwvYnV0dG9uPgogICAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ3ZhbHVhdGlvbicsdGhpcykiPvCfko4gRGXEn2VybGVtZTwvYnV0dG9uPgo8L2Rpdj4KPGRpdiBjbGFzcz0idGYtcm93IiBpZD0idGZSb3ciIHN0eWxlPSJkaXNwbGF5Om5vbmUiPgogIDxidXR0b24gY2xhc3M9InRmLWJ0biBhY3RpdmUiIGRhdGEtdGY9IjFkIiBvbmNsaWNrPSJzZXRUZignMWQnLHRoaXMpIj4xRzwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRmLWJ0biBzdGFyIiBkYXRhLXRmPSIxd2siIG9uY2xpY2s9InNldFRmKCcxd2snLHRoaXMpIj4xSDwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRmLWJ0biIgZGF0YS10Zj0iMW1vIiBvbmNsaWNrPSJzZXRUZignMW1vJyx0aGlzKSI+MUE8L2J1dHRvbj4KICA8c3BhbiBjbGFzcz0idGYtaGludCI+Q0FOU0xJTSDDtm5lcmlsZW46IDFHICsgMUg8L3NwYW4+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJzdGF0cyIgaWQ9InN0YXRzIj48L2Rpdj4KPGRpdiBjbGFzcz0ibWFpbiI+PGRpdiBjbGFzcz0iZ3JpZCIgaWQ9ImdyaWQiPjwvZGl2PjwvZGl2Pgo8ZGl2IGNsYXNzPSJvdmVybGF5IiBpZD0ib3ZlcmxheSIgb25jbGljaz0iY2xvc2VNKGV2ZW50KSI+CiAgPGRpdiBjbGFzcz0ibW9kYWwiIGlkPSJtb2RhbCI+PC9kaXY+CjwvZGl2PgoKPGRpdiBjbGFzcz0ibWluZm8tcG9wdXAiIGlkPSJlZGl0UG9wdXAiIG9uY2xpY2s9ImNsb3NlRWRpdFBvcHVwKGV2ZW50KSI+CiAgPGRpdiBjbGFzcz0ibWluZm8tbW9kYWwiIHN0eWxlPSJwb3NpdGlvbjpyZWxhdGl2ZTttYXgtd2lkdGg6NTYwcHgiIGlkPSJlZGl0TW9kYWwiPgogICAgPGJ1dHRvbiBjbGFzcz0ibWluZm8tY2xvc2UiIG9uY2xpY2s9ImNsb3NlRWRpdFBvcHVwKCkiPuKclTwvYnV0dG9uPgogICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4Ij7inI/vuI8gTGlzdGV5aSBEw7x6ZW5sZTwvZGl2PgogICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MTZweCI+R2l0SHViIEFQSSBrZXkgZ2VyZWtsaSDigJQgZGXEn2nFn2lrbGlrbGVyIGFuxLFuZGEga2F5ZGVkaWxpcjwvZGl2PgogICAgPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnIgMWZyO2dhcDoxNnB4O21hcmdpbi1ib3R0b206MTZweCI+CiAgICAgIDxkaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPvCfk4sgV2F0Y2hsaXN0PC9kaXY+CiAgICAgICAgPGRpdiBpZD0id2F0Y2hsaXN0RWRpdG9yIj48L2Rpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjZweDttYXJnaW4tdG9wOjhweCI+CiAgICAgICAgICA8aW5wdXQgaWQ9Im5ld1dhdGNoVGlja2VyIiBwbGFjZWhvbGRlcj0iSGlzc2UgZWtsZSAoVFNMQSkiIHN0eWxlPSJmbGV4OjE7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS10ZXh0KTtwYWRkaW5nOjZweCAxMHB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2ZvbnQtZmFtaWx5OmluaGVyaXQ7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlIi8+CiAgICAgICAgICA8YnV0dG9uIG9uY2xpY2s9ImFkZFRpY2tlcignd2F0Y2gnKSIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjMpO2NvbG9yOnZhcigtLWdyZWVuKTtwYWRkaW5nOjZweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2N1cnNvcjpwb2ludGVyIj4rIEVrbGU8L2J1dHRvbj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CiAgICAgIDxkaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPvCfkrwgUG9ydGbDtnk8L2Rpdj4KICAgICAgICA8ZGl2IGlkPSJwb3J0Zm9saW9FZGl0b3IiPjwvZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6NnB4O21hcmdpbi10b3A6OHB4Ij4KICAgICAgICAgIDxpbnB1dCBpZD0ibmV3UG9ydFRpY2tlciIgcGxhY2Vob2xkZXI9Ikhpc3NlIGVrbGUgKEFBUEwpIiBzdHlsZT0iZmxleDoxO2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tdGV4dCk7cGFkZGluZzo2cHggMTBweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtmb250LWZhbWlseTppbmhlcml0O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZSIvPgogICAgICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJhZGRUaWNrZXIoJ3BvcnQnKSIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjMpO2NvbG9yOnZhcigtLWdyZWVuKTtwYWRkaW5nOjZweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2N1cnNvcjpwb2ludGVyIj4rIEVrbGU8L2J1dHRvbj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CiAgICA8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxMnB4O21hcmdpbi1ib3R0b206MTRweDtmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1ncmVlbikiPuKchSBEZcSfacWfaWtsaWtsZXIga2F5ZGVkaWxpbmNlIGJpciBzb25yYWtpIENvbGFiIMOnYWzEscWfdMSxcm1hc8SxbmRhIGFrdGlmIG9sdXIuPC9kaXY+CjxkaXYgc3R5bGU9Im1hcmdpbi1ib3R0b206MTJweCI+CiAgICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjVweCI+R2l0SHViIFRva2VuIChiaXIga2V6IGdpciwgdGFyYXlpY2kgaGF0aXJsYXlhY2FrKTwvZGl2PgogICAgICA8aW5wdXQgaWQ9ImdoVG9rZW5JbnB1dCIgcGxhY2Vob2xkZXI9ImdocF8uLi4iIHN0eWxlPSJ3aWR0aDoxMDAlO2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tdGV4dCk7cGFkZGluZzo4cHggMTBweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTFweDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiLz4KICAgIDwvZGl2PgogICAgPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo4cHgiPgogICAgICA8YnV0dG9uIG9uY2xpY2s9InNhdmVMaXN0VG9HaXRodWIoKSIgc3R5bGU9ImZsZXg6MTtiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6OHB4O2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMDtjdXJzb3I6cG9pbnRlciI+8J+SviBHaXRIdWJhIEtheWRldDwvYnV0dG9uPgogICAgICA8YnV0dG9uIG9uY2xpY2s9ImNsb3NlRWRpdFBvcHVwKCkiIHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTtwYWRkaW5nOjEwcHggMTZweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTNweDtjdXJzb3I6cG9pbnRlciI+xLBwdGFsPC9idXR0b24+CiAgICA8L2Rpdj4KICAgIDxkaXYgaWQ9ImVkaXRTdGF0dXMiIHN0eWxlPSJtYXJnaW4tdG9wOjEwcHg7Zm9udC1zaXplOjEycHg7dGV4dC1hbGlnbjpjZW50ZXIiPjwvZGl2PgogIDwvZGl2Pgo8L2Rpdj4KCjxkaXYgY2xhc3M9Im1pbmZvLXBvcHVwIiBpZD0ibWluZm9Qb3B1cCIgb25jbGljaz0iY2xvc2VJbmZvUG9wdXAoZXZlbnQpIj4KICA8ZGl2IGNsYXNzPSJtaW5mby1tb2RhbCIgaWQ9Im1pbmZvTW9kYWwiPgogICAgPGJ1dHRvbiBjbGFzcz0ibWluZm8tY2xvc2UiIG9uY2xpY2s9ImNsb3NlSW5mb1BvcHVwKCkiPuKclTwvYnV0dG9uPgogICAgPGRpdiBpZD0ibWluZm9Db250ZW50Ij48L2Rpdj4KICA8L2Rpdj4KPC9kaXY+CgoKPHNjcmlwdD4KdmFyIE1FVFJJQ1MgPSB7CiAgLy8gVEVLTsSwSwogICdSU0knOiB7CiAgICB0aXRsZTogJ1JTSSAoR8O2cmVjZWxpIEfDvMOnIEVuZGVrc2kpJywKICAgIGRlc2M6ICdIaXNzZW5pbiBhxZ/EsXLEsSBhbMSxbSB2ZXlhIGHFn8SxcsSxIHNhdMSxbSBiw7ZsZ2VzaW5kZSBvbHVwIG9sbWFkxLHEn8SxbsSxIGfDtnN0ZXJpci4gMTQgZ8O8bmzDvGsgZml5YXQgaGFyZWtldGxlcmluaSBhbmFsaXogZWRlci4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonQcWfxLFyxLEgU2F0xLFtJyxtaW46MCxtYXg6MzAsY29sb3I6J2dyZWVuJyxkZXNjOidGxLFyc2F0IGLDtmxnZXNpIOKAlCBmaXlhdCDDp29rIGTDvMWfbcO8xZ8nfSwKICAgICAge2xhYmVsOidOb3JtYWwnLG1pbjozMCxtYXg6NzAsY29sb3I6J3llbGxvdycsZGVzYzonTsO2dHIgYsO2bGdlJ30sCiAgICAgIHtsYWJlbDonQcWfxLFyxLEgQWzEsW0nLG1pbjo3MCxtYXg6MTAwLGNvbG9yOidyZWQnLGRlc2M6J0Rpa2thdCDigJQgZml5YXQgw6dvayB5w7xrc2VsbWnFnyd9CiAgICBdLAogICAgY2Fuc2xpbTogJ04ga3JpdGVyaSBpbGUgaWxnaWxpIOKAlCBmaXlhdCBtb21lbnR1bXUnCiAgfSwKICAnU01BNTAnOiB7CiAgICB0aXRsZTogJ1NNQSA1MCAoNTAgR8O8bmzDvGsgSGFyZWtldGxpIE9ydGFsYW1hKScsCiAgICBkZXNjOiAnU29uIDUwIGfDvG7DvG4gb3J0YWxhbWEga2FwYW7EscWfIGZpeWF0xLEuIEvEsXNhLW9ydGEgdmFkZWxpIHRyZW5kIGfDtnN0ZXJnZXNpLicsCiAgICBzb3VyY2U6ICdUZWtuaWsgQW5hbGl6JywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOifDnHplcmluZGUnLGNvbG9yOidncmVlbicsZGVzYzonS8Sxc2EgdmFkZWxpIHRyZW5kIHBveml0aWYg4oCUIGfDvMOnbMO8IHNpbnlhbCd9LAogICAgICB7bGFiZWw6J0FsdMSxbmRhJyxjb2xvcjoncmVkJyxkZXNjOidLxLFzYSB2YWRlbGkgdHJlbmQgbmVnYXRpZid9CiAgICBdLAogICAgY2Fuc2xpbTogJ00ga3JpdGVyaSDigJQgcGl5YXNhIHRyZW5kaScKICB9LAogICdTTUEyMDAnOiB7CiAgICB0aXRsZTogJ1NNQSAyMDAgKDIwMCBHw7xubMO8ayBIYXJla2V0bGkgT3J0YWxhbWEpJywKICAgIGRlc2M6ICdTb24gMjAwIGfDvG7DvG4gb3J0YWxhbWEga2FwYW7EscWfIGZpeWF0xLEuIFV6dW4gdmFkZWxpIHRyZW5kIGfDtnN0ZXJnZXNpLiBFbiDDtm5lbWxpIHRla25payBzZXZpeWUuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J8OcemVyaW5kZScsY29sb3I6J2dyZWVuJyxkZXNjOidVenVuIHZhZGVsaSBib8SfYSB0cmVuZGluZGUg4oCUIENBTlNMSU0gacOnaW4gxZ9hcnQnfSwKICAgICAge2xhYmVsOidBbHTEsW5kYScsY29sb3I6J3JlZCcsZGVzYzonVXp1biB2YWRlbGkgYXnEsSB0cmVuZGluZGUg4oCUIENBTlNMSU0gacOnaW4gZ2lybWUnfQogICAgXSwKICAgIGNhbnNsaW06ICdNIGtyaXRlcmkg4oCUIHpvcnVubHUga2/Fn3VsJwogIH0sCiAgJzUyVyc6IHsKICAgIHRpdGxlOiAnNTIgSGFmdGFsxLFrIFBvemlzeW9uJywKICAgIGRlc2M6ICdIaXNzZW5pbiBzb24gMSB5xLFsZGFraSBmaXlhdCBhcmFsxLHEn8SxbmRhIG5lcmVkZSBvbGR1xJ91bnUgZ8O2c3RlcmlyLiAwPXnEsWzEsW4gZGliaSwgMTAwPXnEsWzEsW4gemlydmVzaS4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonMC0zMCUnLGNvbG9yOidncmVlbicsZGVzYzonWcSxbMSxbiBkaWJpbmUgeWFrxLFuIOKAlCBwb3RhbnNpeWVsIGbEsXJzYXQnfSwKICAgICAge2xhYmVsOiczMC03MCUnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGEgYsO2bGdlIOKAlCBuw7Z0cid9LAogICAgICB7bGFiZWw6JzcwLTg1JScsY29sb3I6J3llbGxvdycsZGVzYzonWmlydmV5ZSB5YWtsYcWfxLF5b3Ig4oCUIGl6bGUnfSwKICAgICAge2xhYmVsOic4NS0xMDAlJyxjb2xvcjoncmVkJyxkZXNjOidaaXJ2ZXllIMOnb2sgeWFrxLFuIOKAlCBkaWtrYXRsaSBnaXInfQogICAgXSwKICAgIGNhbnNsaW06ICdOIGtyaXRlcmkg4oCUIHllbmkgemlydmUga8SxcsSxbMSxbcSxIGnDp2luIGlkZWFsIGLDtmxnZSAlODUtMTAwJwogIH0sCiAgJ0hhY2ltJzogewogICAgdGl0bGU6ICdIYWNpbSAoxLDFn2xlbSBNaWt0YXLEsSknLAogICAgZGVzYzogJ0fDvG5sw7xrIGnFn2xlbSBoYWNtaW5pbiBzb24gMjAgZ8O8bmzDvGsgb3J0YWxhbWF5YSBvcmFuxLEuIEfDvMOnbMO8IGhhcmVrZXRsZXJpbiBoYWNpbWxlIGRlc3Rla2xlbm1lc2kgZ2VyZWtpci4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonWcO8a3NlayAoPjEuM3gpJyxjb2xvcjonZ3JlZW4nLGRlc2M6J0t1cnVtc2FsIGlsZ2kgdmFyIOKAlCBnw7zDp2zDvCBzaW55YWwnfSwKICAgICAge2xhYmVsOidOb3JtYWwgKDAuNy0xLjN4KScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YWxhbWEgaWxnaSd9LAogICAgICB7bGFiZWw6J0TDvMWfw7xrICg8MC43eCknLGNvbG9yOidyZWQnLGRlc2M6J8SwbGdpIGF6YWxtxLHFnyDigJQgZGlra2F0J30KICAgIF0sCiAgICBjYW5zbGltOiAnUyBrcml0ZXJpIOKAlCBhcnovdGFsZXAgZGVuZ2VzaScKICB9LAogIC8vIFRFTUVMCiAgJ0ZvcndhcmRQRSc6IHsKICAgIHRpdGxlOiAnRm9yd2FyZCBQL0UgKMSwbGVyaXllIETDtm7DvGsgRml5YXQvS2F6YW7DpyknLAogICAgZGVzYzogJ1NpcmtldGluIG9udW3DvHpkZWtpIDEyIGF5ZGFraSB0YWhtaW5pIGthemFuY2luYSBnb3JlIGZpeWF0aS4gVHJhaWxpbmcgUC9FIGFyYWNpbmEgZ29yZSBnZWxlY2VnZSBvZGFrbGlkaWdpIGljaW4gZGFoYSBvbmVtbGlkaXIuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgQW5hbGlzdCB0YWhtaW5pJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdBbmFsaXN0IHRhaG1pbmxlcmluZSBkYXlhbsSxciwgeWFuxLFsdMSxY8SxIG9sYWJpbGlyJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzwxNScsY29sb3I6J2dyZWVuJyxkZXNjOidVY3V6IOKAlCBiw7x5w7xtZSBiZWtsZW50aXNpIGTDvMWfw7xrIHZleWEgaGlzc2UgZGXEn2VyIGFsdMSxbmRhJ30sCiAgICAgIHtsYWJlbDonMTUtMjUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwg4oCUIMOnb8SfdSBzZWt0w7ZyIGnDp2luIG5vcm1hbCd9LAogICAgICB7bGFiZWw6JzI1LTQwJyxjb2xvcjoneWVsbG93JyxkZXNjOidQYWhhbMSxIGFtYSBiw7x5w7xtZSBwcmltaSDDtmRlbml5b3InfSwKICAgICAge2xhYmVsOic+NDAnLGNvbG9yOidyZWQnLGRlc2M6J8OHb2sgcGFoYWzEsSDigJQgecO8a3NlayBiw7x5w7xtZSBiZWtsZW50aXNpIGZpeWF0bGFubcSxxZ8nfQogICAgXSwKICAgIGNhbnNsaW06ICdDIHZlIEEga3JpdGVybGVyaSBpbGUgaWxnaWxpJwogIH0sCiAgJ1BFRyc6IHsKICAgIHRpdGxlOiAnUEVHIE9yYW7EsSAoRml5YXQvS2F6YW7Dpy9Cw7x5w7xtZSknLAogICAgZGVzYzogJ1AvRSBvcmFuxLFuxLEgYsO8ecO8bWUgaMSxesSxeWxhIGthcsWfxLFsYcWfdMSxcsSxci4gQsO8ecO8eWVuIMWfaXJrZXRsZXIgaWNpbiBQL0VcJ2RlbiBkYWhhIGRvxJ9ydSBkZcSfZXJsZW1lIMO2bMOnw7x0w7wuIFBFRz0xIGFkaWwgZGXEn2VyIGthYnVsIGVkaWxpci4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBBbmFsaXN0IHRhaG1pbmknLAogICAgcmVsaWFiaWxpdHk6ICdtZWRpdW0nLAogICAgd2FybmluZzogJ0FuYWxpc3QgYsO8ecO8bWUgdGFobWlubGVyaW5lIGRheWFuxLFyJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzwxLjAnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgYsO8ecO8bWVzaW5lIGfDtnJlIGRlxJ9lciBhbHTEsW5kYSd9LAogICAgICB7bGFiZWw6JzEuMC0xLjUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwg4oCUIGFkaWwgZml5YXQgY2l2YXLEsSd9LAogICAgICB7bGFiZWw6JzEuNS0yLjAnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J0JpcmF6IHBhaGFsxLEnfSwKICAgICAge2xhYmVsOic+Mi4wJyxjb2xvcjoncmVkJyxkZXNjOidQYWhhbMSxIOKAlCBkaWtrYXRsaSBvbCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQgYsO8ecO8bWUga2FsaXRlc2knCiAgfSwKICAnRVBTR3Jvd3RoJzogewogICAgdGl0bGU6ICdFUFMgQsO8ecO8bWVzaSAow4dleXJla2xpaywgWW9ZKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIGhpc3NlIGJhxZ/EsW5hIGthemFuY8SxbsSxbiBnZcOnZW4gecSxbMSxbiBheW7EsSDDp2V5cmXEn2luZSBnw7ZyZSBhcnTEscWfxLEuIENBTlNMSU1cJ2luIGVuIGtyaXRpayBrcml0ZXJpLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUyNScsY29sb3I6J2dyZWVuJyxkZXNjOidHw7zDp2zDvCBiw7x5w7xtZSDigJQgQ0FOU0xJTSBrcml0ZXJpIGthcsWfxLFsYW5kxLEnfSwKICAgICAge2xhYmVsOiclMTUtMjUnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSBiw7x5w7xtZSd9LAogICAgICB7bGFiZWw6JyUwLTE1Jyxjb2xvcjoneWVsbG93JyxkZXNjOidaYXnEsWYgYsO8ecO8bWUnfSwKICAgICAge2xhYmVsOic8MCcsY29sb3I6J3JlZCcsZGVzYzonS2F6YW7DpyBkw7zFn8O8eW9yIOKAlCBkaWtrYXQnfQogICAgXSwKICAgIGNhbnNsaW06ICdDIGtyaXRlcmkg4oCUIGVuIGtyaXRpayBrcml0ZXIsIG1pbmltdW0gJTI1IG9sbWFsxLEnCiAgfSwKICAnUmV2R3Jvd3RoJzogewogICAgdGl0bGU6ICdHZWxpciBCw7x5w7xtZXNpIChZb1kpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gc2F0xLHFny9nZWxpcmluaW4gZ2XDp2VuIHnEsWxhIGfDtnJlIGFydMSxxZ/EsS4gRVBTIGLDvHnDvG1lc2luaSBkZXN0ZWtsZW1lc2kgZ2VyZWtpciDigJQgc2FkZWNlIG1hbGl5ZXQga2VzaW50aXNpeWxlIGLDvHnDvG1lIHPDvHJkw7xyw7xsZWJpbGlyIGRlxJ9pbC4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMTUnLGNvbG9yOidncmVlbicsZGVzYzonR8O8w6dsw7wgZ2VsaXIgYsO8ecO8bWVzaSd9LAogICAgICB7bGFiZWw6JyU1LTE1Jyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIGLDvHnDvG1lJ30sCiAgICAgIHtsYWJlbDonPDUnLGNvbG9yOidyZWQnLGRlc2M6J0dlbGlyIGLDvHnDvG1lc2kgemF5xLFmJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQSBrcml0ZXJpIOKAlCBzw7xyZMO8csO8bGViaWxpciBiw7x5w7xtZSBpw6dpbiDFn2FydCcKICB9LAogICdOZXRNYXJnaW4nOiB7CiAgICB0aXRsZTogJ05ldCBNYXJqaW4nLAogICAgZGVzYzogJ0hlciAxJCBnZWxpcmRlbiBuZSBrYWRhciBuZXQga8OiciBrYWxkxLHEn8SxbsSxIGfDtnN0ZXJpci4gWcO8a3NlayBtYXJqaW4gPSBnw7zDp2zDvCBpxZ8gbW9kZWxpLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUyMCcsY29sb3I6J2dyZWVuJyxkZXNjOifDh29rIGfDvMOnbMO8IGvDonJsxLFsxLFrJ30sCiAgICAgIHtsYWJlbDonJTEwLTIwJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWkga8OicmzEsWzEsWsnfSwKICAgICAge2xhYmVsOiclNS0xMCcsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSBrw6JybMSxbMSxayd9LAogICAgICB7bGFiZWw6Jzw1Jyxjb2xvcjoncmVkJyxkZXNjOidaYXnEsWYga8OicmzEsWzEsWsnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIGvDonJsxLFsxLFrIGthbGl0ZXNpJwogIH0sCiAgJ1JPRSc6IHsKICAgIHRpdGxlOiAnUk9FICjDlnprYXluYWsgS8OicmzEsWzEscSfxLEpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gw7Z6IHNlcm1heWVzaXlsZSBuZSBrYWRhciBrw6JyIGV0dGnEn2luaSBnw7ZzdGVyaXIuIFnDvGtzZWsgUk9FID0gc2VybWF5ZXlpIHZlcmltbGkga3VsbGFuxLF5b3IuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgR2Vyw6dlayB2ZXJpJywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic+JTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8OHb2sgZ8O8w6dsw7wg4oCUIENBTlNMSU0gaWRlYWwgc2V2aXllc2knfSwKICAgICAge2xhYmVsOiclMTUtMjUnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSd9LAogICAgICB7bGFiZWw6JyU4LTE1Jyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhJ30sCiAgICAgIHtsYWJlbDonPDgnLGNvbG9yOidyZWQnLGRlc2M6J1phecSxZid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQgbWluaW11bSAlMTcgb2xtYWzEsScKICB9LAogICdHcm9zc01hcmdpbic6IHsKICAgIHRpdGxlOiAnQnLDvHQgTWFyamluJywKICAgIGRlc2M6ICdTYXTEscWfIGdlbGlyaW5kZW4gw7xyZXRpbSBtYWxpeWV0aSBkw7zFn8O8bGTDvGt0ZW4gc29ucmEga2FsYW4gb3Jhbi4gU2VrdMO2cmUgZ8O2cmUgZGXEn2nFn2lyLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiU1MCcsY29sb3I6J2dyZWVuJyxkZXNjOifDh29rIGfDvMOnbMO8IOKAlCB5YXrEsWzEsW0vU2FhUyBzZXZpeWVzaSd9LAogICAgICB7bGFiZWw6JyUzMC01MCcsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpJ30sCiAgICAgIHtsYWJlbDonJTE1LTMwJyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIOKAlCBkb25hbsSxbS95YXLEsSBpbGV0a2VuIG5vcm1hbCd9LAogICAgICB7bGFiZWw6JzwxNScsY29sb3I6J3JlZCcsZGVzYzonRMO8xZ/DvGsgbWFyamluJ30KICAgIF0sCiAgICBjYW5zbGltOiAnS8OicmzEsWzEsWsga2FsaXRlc2kgZ8O2c3Rlcmdlc2knCiAgfSwKICAvLyBHxLBSxLDFngogICdFbnRyeVNjb3JlJzogewogICAgdGl0bGU6ICdHaXJpxZ8gS2FsaXRlc2kgU2tvcnUnLAogICAgZGVzYzogJ1JTSSwgU01BIHBvemlzeW9udSwgUC9FLCBQRUcgdmUgRVBTIGLDvHnDvG1lc2luaSBiaXJsZcWfdGlyZW4gYmlsZcWfaWsgc2tvci4gMC0xMDAgYXJhc8SxLicsCiAgICBzb3VyY2U6ICdCaXppbSBoZXNhcGxhbWEnLAogICAgcmVsaWFiaWxpdHk6ICdsb3cnLAogICAgd2FybmluZzogJ0JVIFVZR1VMQU1BIFRBUkFGSU5EQU4gSEVTQVBMQU5BTiBLQUJBIFRBSE3EsE5ExLBSLiBZYXTEsXLEsW0ga2FyYXLEsSBpw6dpbiB0ZWsgYmHFn8SxbmEga3VsbGFubWEuJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jzc1LTEwMCcsY29sb3I6J2dyZWVuJyxkZXNjOidVY3V6IOKAlCBpZGVhbCBnaXJpxZ8gYsO2bGdlc2knfSwKICAgICAge2xhYmVsOic2MC03NScsY29sb3I6J2dyZWVuJyxkZXNjOidNYWt1bCBmaXlhdCd9LAogICAgICB7bGFiZWw6JzQ1LTYwJyxjb2xvcjoneWVsbG93JyxkZXNjOidOw7Z0cid9LAogICAgICB7bGFiZWw6JzMwLTQ1Jyxjb2xvcjoncmVkJyxkZXNjOidQYWhhbMSxIOKAlCBiZWtsZSd9LAogICAgICB7bGFiZWw6JzAtMzAnLGNvbG9yOidyZWQnLGRlc2M6J8OHb2sgcGFoYWzEsSDigJQgZ2lybWUnfQogICAgXSwKICAgIGNhbnNsaW06ICdUw7xtIGtyaXRlcmxlciBiaWxlxZ9pbWknCiAgfSwKICAnUlInOiB7CiAgICB0aXRsZTogJ1Jpc2svw5Zkw7xsIE9yYW7EsSAoUi9SKScsCiAgICBkZXNjOiAnUG90YW5zaXllbCBrYXphbmPEsW4gcmlza2Ugb3JhbsSxLiAxOjIgZGVtZWsgMSQgcmlza2Uga2FyxZ/EsSAyJCBrYXphbsOnIHBvdGFuc2l5ZWxpIHZhciBkZW1lay4nLAogICAgc291cmNlOiAnQml6aW0gaGVzYXBsYW1hJywKICAgIHJlbGlhYmlsaXR5OiAnbG93JywKICAgIHdhcm5pbmc6ICdHaXJpxZ8vaGVkZWYvc3RvcCBzZXZpeWVsZXJpIGZvcm3DvGwgYmF6bMSxIGthYmEgdGFobWluZGlyJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzE6MysnLGNvbG9yOidncmVlbicsZGVzYzonTcO8a2VtbWVsIOKAlCBnw7zDp2zDvCBnaXJpxZ8gc2lueWFsaSd9LAogICAgICB7bGFiZWw6JzE6MicsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpIOKAlCBtaW5pbXVtIGthYnVsIGVkaWxlYmlsaXInfSwKICAgICAge2xhYmVsOicxOjEnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1phecSxZid9LAogICAgICB7bGFiZWw6JzwxOjEnLGNvbG9yOidyZWQnLGRlc2M6J1Jpc2sga2F6YW7Dp3RhbiBiw7x5w7xrIOKAlCBnaXJtZSd9CiAgICBdLAogICAgY2Fuc2xpbTogJ1Jpc2sgecO2bmV0aW1pJwogIH0sCiAgLy8gRUFSTklOR1MKICAnRWFybmluZ3NEYXRlJzogewogICAgdGl0bGU6ICdSYXBvciBUYXJpaGkgKEVhcm5pbmdzIERhdGUpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gw6dleXJlayBmaW5hbnNhbCBzb251w6dsYXLEsW7EsSBhw6fEsWtsYXlhY2HEn8SxIHRhcmloLiBSYXBvciDDtm5jZXNpIHZlIHNvbnJhc8SxIGZpeWF0IHNlcnQgaGFyZWtldCBlZGViaWxpci4nLAogICAgc291cmNlOiAneWZpbmFuY2Ug4oCUIGJhemVuIGhhdGFsxLEgb2xhYmlsaXInLAogICAgcmVsaWFiaWxpdHk6ICdtZWRpdW0nLAogICAgd2FybmluZzogJ1RhcmlobGVyaSByZXNtaSBJUiBzYXlmYXPEsW5kYW4gZG/En3J1bGF5xLFuJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzcgZ8O8biBpw6dpbmRlJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHlha8SxbiDigJQgcG96aXN5b24gYcOnbWFrIHJpc2tsaSd9LAogICAgICB7bGFiZWw6JzgtMTQgZ8O8bicsY29sb3I6J3llbGxvdycsZGVzYzonWWFrxLFuIOKAlCBkaWtrYXRsaSBvbCd9LAogICAgICB7bGFiZWw6JzE0KyBnw7xuJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1lldGVybGkgc8O8cmUgdmFyJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQyBrcml0ZXJpIOKAlCDDp2V5cmVrIHJhcG9yIGthbGl0ZXNpJwogIH0sCiAgJ0F2Z01vdmUnOiB7CiAgICB0aXRsZTogJ09ydGFsYW1hIFJhcG9yIEhhcmVrZXRpJywKICAgIGRlc2M6ICdTb24gNCDDp2V5cmVrIHJhcG9ydW5kYSwgcmFwb3IgZ8O8bsO8IHZlIGVydGVzaSBnw7xuIGZpeWF0xLFuIG9ydGFsYW1hIG5lIGthZGFyIGhhcmVrZXQgZXR0acSfaS4nLAogICAgc291cmNlOiAnQml6aW0gaGVzYXBsYW1hJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J1Bveml0aWYgKD4lNSknLGNvbG9yOidncmVlbicsZGVzYzonxZ5pcmtldCBnZW5lbGxpa2xlIGJla2xlbnRpeWkgYcWfxLF5b3InfSwKICAgICAge2xhYmVsOidOw7Z0ciAoJTAtNSknLGNvbG9yOid5ZWxsb3cnLGRlc2M6J0thcsSxxZ/EsWsgZ2XDp21pxZ8nfSwKICAgICAge2xhYmVsOidOZWdhdGlmJyxjb2xvcjoncmVkJyxkZXNjOidSYXBvciBkw7ZuZW1pbmRlIGZpeWF0IGdlbmVsbGlrbGUgZMO8xZ/DvHlvciDigJQgZGlra2F0J30KICAgIF0sCiAgICBjYW5zbGltOiAnQyBrcml0ZXJpIOKAlCBrYXphbsOnIHPDvHJwcml6aSBnZcOnbWnFn2knCiAgfQp9OwoKZnVuY3Rpb24gc2hvd0luZm8oa2V5LGV2ZW50KXsKICBpZihldmVudCkgZXZlbnQuc3RvcFByb3BhZ2F0aW9uKCk7CiAgdmFyIG09TUVUUklDU1trZXldOyBpZighbSkgcmV0dXJuOwogIHZhciByZWxMYWJlbD1tLnJlbGlhYmlsaXR5PT09ImhpZ2giPyJHw7x2ZW5pbGlyIjptLnJlbGlhYmlsaXR5PT09Im1lZGl1bSI/Ik9ydGEgR8O8dmVuaWxpciI6IkthYmEgVGFobWluIjsKICB2YXIgaD0nPGRpdiBjbGFzcz0ibWluZm8tdGl0bGUiPicrbS50aXRsZSsnPC9kaXY+JzsKICBoKz0nPGRpdiBjbGFzcz0ibWluZm8tc291cmNlIj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj4nK20uc291cmNlKyc8L3NwYW4+PHNwYW4gY2xhc3M9Im1pbmZvLXJlbCAnK20ucmVsaWFiaWxpdHkrJyI+JytyZWxMYWJlbCsnPC9zcGFuPjwvZGl2Pic7CiAgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLWRlc2MiPicrbS5kZXNjKyc8L2Rpdj4nOwogIGlmKG0ud2FybmluZykgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLXdhcm5pbmciPuKaoO+4jyAnK20ud2FybmluZysnPC9kaXY+JzsKICBpZihtLnJhbmdlcyYmbS5yYW5nZXMubGVuZ3RoKXsKICAgIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby1yYW5nZXMiPjxkaXYgY2xhc3M9Im1pbmZvLXJhbmdlLXRpdGxlIj5SZWZlcmFucyBEZWdlcmxlcjwvZGl2Pic7CiAgICBtLnJhbmdlcy5mb3JFYWNoKGZ1bmN0aW9uKHIpe3ZhciBkYz1yLmNvbG9yPT09ImdyZWVuIj8iIzEwYjk4MSI6ci5jb2xvcj09PSJyZWQiPyIjZWY0NDQ0IjoiI2Y1OWUwYiI7aCs9JzxkaXYgY2xhc3M9Im1pbmZvLXJhbmdlIj48ZGl2IGNsYXNzPSJtaW5mby1yYW5nZS1kb3QiIHN0eWxlPSJiYWNrZ3JvdW5kOicrZGMrJyI+PC9kaXY+PGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtmb250LXdlaWdodDo2MDA7Y29sb3I6JytkYysnIj4nK3IubGFiZWwrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytyLmRlc2MrJzwvZGl2PjwvZGl2PjwvZGl2Pic7fSk7CiAgICBoKz0nPC9kaXY+JzsKICB9CiAgaWYobS5jYW5zbGltKSBoKz0nPGRpdiBjbGFzcz0ibWluZm8tY2Fuc2xpbSI+8J+TiiBDQU5TTElNOiAnK20uY2Fuc2xpbSsnPC9kaXY+JzsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWluZm9Db250ZW50IikuaW5uZXJIVE1MPWg7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvUG9wdXAiKS5jbGFzc0xpc3QuYWRkKCJvcGVuIik7Cn0KZnVuY3Rpb24gY2xvc2VJbmZvUG9wdXAoZSl7aWYoIWV8fGUudGFyZ2V0PT09ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvUG9wdXAiKSl7ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvUG9wdXAiKS5jbGFzc0xpc3QucmVtb3ZlKCJvcGVuIik7fX0KCjwvc2NyaXB0Pgo8L3NjcmlwdD4KPHNjcmlwdD4KdmFyIFRGX0RBVEE9JSVURl9EQVRBJSU7CnZhciBQT1JUPSUlUE9SVCUlOwp2YXIgRUFSTklOR1NfREFUQT0lJUVBUk5JTkdTX0RBVEElJTsKdmFyIE1BUktFVF9EQVRBPSUlTUFSS0VUX0RBVEElJTsKdmFyIE5FV1NfREFUQT0lJU5FV1NfREFUQSUlOwp2YXIgQUlfREFUQT0lJUFJX0RBVEElJTsKdmFyIFdFRUtMWV9EQVRBPSUlV0VFS0xZX0RBVEElJTsKdmFyIFNDUkVFTkVSX0RBVEE9JSVTQ1JFRU5FUl9EQVRBJSU7CnZhciBjdXJUYWI9ImFsbCIsY3VyVGY9IjFkIixjdXJEYXRhPVRGX0RBVEFbIjFkIl0uc2xpY2UoKTsKdmFyIG1pbmlDaGFydHM9e30sbUNoYXJ0PW51bGw7CnZhciBTUz17CiAgIkdVQ0xVIEFMIjp7Ymc6InJnYmEoMTYsMTg1LDEyOSwuMTIpIixiZDoicmdiYSgxNiwxODUsMTI5LC4zNSkiLHR4OiIjMTBiOTgxIixhYzoiIzEwYjk4MSIsbGJsOiJHVUNMVSBBTCJ9LAogICJBTCI6e2JnOiJyZ2JhKDUyLDIxMSwxNTMsLjEpIixiZDoicmdiYSg1MiwyMTEsMTUzLC4zKSIsdHg6IiMzNGQzOTkiLGFjOiIjMzRkMzk5IixsYmw6IkFMIn0sCiAgIkRJS0tBVCI6e2JnOiJyZ2JhKDI0NSwxNTgsMTEsLjEpIixiZDoicmdiYSgyNDUsMTU4LDExLC4zKSIsdHg6IiNmNTllMGIiLGFjOiIjZjU5ZTBiIixsYmw6IkRJS0tBVCJ9LAogICJaQVlJRiI6e2JnOiJyZ2JhKDEwNywxMTQsMTI4LC4xKSIsYmQ6InJnYmEoMTA3LDExNCwxMjgsLjMpIix0eDoiIzljYTNhZiIsYWM6IiM2YjcyODAiLGxibDoiWkFZSUYifSwKICAiU0FUIjp7Ymc6InJnYmEoMjM5LDY4LDY4LC4xMikiLGJkOiJyZ2JhKDIzOSw2OCw2OCwuMzUpIix0eDoiI2VmNDQ0NCIsYWM6IiNlZjQ0NDQiLGxibDoiU0FUIn0KfTsKCmZ1bmN0aW9uIGliKGtleSxsYWJlbCl7CiAgcmV0dXJuIGxhYmVsKycgPHNwYW4gY2xhc3M9Im1pbmZvIiBvbmNsaWNrPSJzaG93SW5mbyhcJycra2V5KydcJyxldmVudCkiPj88L3NwYW4+JzsKfQoKZnVuY3Rpb24gc2V0VGFiKHQsZWwpewogIGN1clRhYj10OwogIGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoIi50YWIiKS5mb3JFYWNoKGZ1bmN0aW9uKGIpe2IuY2xhc3NMaXN0LnJlbW92ZSgiYWN0aXZlIik7fSk7CiAgZWwuY2xhc3NMaXN0LmFkZCgiYWN0aXZlIik7CiAgdmFyIHRmUm93PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0ZlJvdyIpOwogIGlmKHRmUm93KSB0ZlJvdy5zdHlsZS5kaXNwbGF5PSh0PT09ImRhc2hib2FyZCJ8fHQ9PT0iZWFybmluZ3MifHx0PT09InJ1dGluInx8dD09PSJoYWZ0YWxpayJ8fHQ9PT0ic2NyZWVuZXIifHx0PT09InZhbHVhdGlvbiIpPyJub25lIjoiZmxleCI7CiAgaWYodD09PSJkYXNoYm9hcmQiKSByZW5kZXJEYXNoYm9hcmQoKTsKICBlbHNlIGlmKHQ9PT0iZWFybmluZ3MiKSByZW5kZXJFYXJuaW5ncygpOwogIGVsc2UgaWYodD09PSJydXRpbiIpIHJlbmRlclJ1dGluKCk7CiAgZWxzZSBpZih0PT09ImhhZnRhbGlrIikgcmVuZGVySGFmdGFsaWsoKTsKICBlbHNlIGlmKHQ9PT0ic2NyZWVuZXIiKSByZW5kZXJTY3JlZW5lcigpOwogIGVsc2UgaWYodD09PSJ2YWx1YXRpb24iKSByZW5kZXJWYWx1YXRpb24oKTsKICBlbHNlIHsKICAgIHZhciBnPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgICBpZihnKXtnLnN0eWxlLmRpc3BsYXk9Jyc7Zy5zdHlsZS53aWR0aD0nJzt9CiAgICByZW5kZXJHcmlkKCk7CiAgfQp9CgpmdW5jdGlvbiBzZXRUZih0ZixlbCl7CiAgY3VyVGY9dGY7CiAgZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbCgiLnRmLWJ0biIpLmZvckVhY2goZnVuY3Rpb24oYil7Yi5jbGFzc0xpc3QudG9nZ2xlKCJhY3RpdmUiLGIuZGF0YXNldC50Zj09PXRmKTt9KTsKICBjdXJEYXRhPShURl9EQVRBW3RmXXx8VEZfREFUQVsiMWQiXSkuc2xpY2UoKTsKICByZW5kZXJTdGF0cygpOwogIHJlbmRlckdyaWQoKTsKfQoKZnVuY3Rpb24gZmlsdGVyZWQoKXsKICB2YXIgZD1jdXJEYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KTsKICBpZihjdXJUYWI9PT0icG9ydCIpIHJldHVybiBkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gUE9SVC5pbmNsdWRlcyhyLnRpY2tlcik7fSk7CiAgaWYoY3VyVGFiPT09ImJ1eSIpIHJldHVybiBkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0iR1VDTFUgQUwifHxyLnNpbnlhbD09PSJBTCI7fSk7CiAgaWYoY3VyVGFiPT09InNlbGwiKSByZXR1cm4gZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09IlNBVCI7fSk7CiAgcmV0dXJuIGQ7Cn0KCmZ1bmN0aW9uIHJlbmRlclN0YXRzKCl7CiAgdmFyIGQ9Y3VyRGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSk7CiAgdmFyIGNudD17fTsKICBkLmZvckVhY2goZnVuY3Rpb24ocil7Y250W3Iuc2lueWFsXT0oY250W3Iuc2lueWFsXXx8MCkrMTt9KTsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgic3RhdHMiKS5pbm5lckhUTUw9CiAgICAnPGRpdiBjbGFzcz0icGlsbCBnIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2Pkd1Y2x1IEFsOiAnKyhjbnRbIkdVQ0xVIEFMIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgZyI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5BbDogJysoY250WyJBTCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIHkiPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+RGlra2F0OiAnKyhjbnRbIkRJS0tBVCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIHIiPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+U2F0OiAnKyhjbnRbIlNBVCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIGIiIHN0eWxlPSJtYXJnaW4tbGVmdDphdXRvIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PlBvcnRmb2x5bzogJytQT1JULmxlbmd0aCsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIG0iPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+JytkLmxlbmd0aCsnIGFuYWxpejwvZGl2Pic7Cn0KCmZ1bmN0aW9uIHJlbmRlckdyaWQoKXsKICBPYmplY3QudmFsdWVzKG1pbmlDaGFydHMpLmZvckVhY2goZnVuY3Rpb24oYyl7Yy5kZXN0cm95KCk7fSk7CiAgbWluaUNoYXJ0cz17fTsKICB2YXIgZj1maWx0ZXJlZCgpOwogIHZhciBncmlkPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJncmlkIik7CiAgaWYoIWYubGVuZ3RoKXtncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMTt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjQwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5IaXNzZSBidWx1bmFtYWRpPC9kaXY+JztyZXR1cm47fQogIGdyaWQuaW5uZXJIVE1MPWYubWFwKGZ1bmN0aW9uKHIpe3JldHVybiBidWlsZENhcmQocik7fSkuam9pbigiIik7CiAgZi5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgdmFyIGN0eD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWMtIityLnRpY2tlcik7CiAgICBpZihjdHgmJnIuY2hhcnRfY2xvc2VzJiZyLmNoYXJ0X2Nsb3Nlcy5sZW5ndGgpewogICAgICB2YXIgc3M9U1Nbci5zaW55YWxdfHxTU1siRElLS0FUIl07CiAgICAgIG1pbmlDaGFydHNbIm0iK3IudGlja2VyXT1uZXcgQ2hhcnQoY3R4LHt0eXBlOiJsaW5lIixkYXRhOntsYWJlbHM6ci5jaGFydF9kYXRlcyxkYXRhc2V0czpbe2RhdGE6ci5jaGFydF9jbG9zZXMsYm9yZGVyQ29sb3I6c3MuYWMsYm9yZGVyV2lkdGg6MS41LGZpbGw6dHJ1ZSxiYWNrZ3JvdW5kQ29sb3I6c3MuYWMrIjE4Iixwb2ludFJhZGl1czowLHRlbnNpb246MC40fV19LG9wdGlvbnM6e3BsdWdpbnM6e2xlZ2VuZDp7ZGlzcGxheTpmYWxzZX19LHNjYWxlczp7eDp7ZGlzcGxheTpmYWxzZX0seTp7ZGlzcGxheTpmYWxzZX19LGFuaW1hdGlvbjp7ZHVyYXRpb246NTAwfSxyZXNwb25zaXZlOnRydWUsbWFpbnRhaW5Bc3BlY3RSYXRpbzpmYWxzZX19KTsKICAgIH0KICB9KTsKfQoKZnVuY3Rpb24gYnVpbGRDYXJkKHIpewogIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICB2YXIgZGM9ci5kZWdpc2ltPj0wPyJ2YXIoLS1ncmVlbjIpIjoidmFyKC0tcmVkMikiOwogIHZhciBkcz0oci5kZWdpc2ltPj0wPyIrIjoiIikrci5kZWdpc2ltKyIlIjsKICB2YXIgZXNjb2w9ci5lbnRyeV9zY29yZT49NzU/InZhcigtLWdyZWVuKSI6ci5lbnRyeV9zY29yZT49NjA/InZhcigtLWdyZWVuMikiOnIuZW50cnlfc2NvcmU+PTQ1PyJ2YXIoLS15ZWxsb3cpIjpyLmVudHJ5X3Njb3JlPj0zMD8idmFyKC0tcmVkMikiOiJ2YXIoLS1yZWQpIjsKICB2YXIgcHZjb2w9ci5wcmljZV92c19jb2xvcj09PSJncmVlbiI/InZhcigtLWdyZWVuKSI6ci5wcmljZV92c19jb2xvcj09PSJ5ZWxsb3ciPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkMikiOwogIHZhciBzaWdzPVsKICAgIHtsOiJUcmVuZCIsdjpyLnRyZW5kPT09Ill1a3NlbGVuIj8iWXVrc2VsaXlvciI6ci50cmVuZD09PSJEdXNlbiI/IkR1c3V5b3IiOiJZYXRheSIsZzpyLnRyZW5kPT09Ill1a3NlbGVuIj90cnVlOnIudHJlbmQ9PT0iRHVzZW4iP2ZhbHNlOm51bGx9LAogICAge2w6IlNNQTUwIix2OnIuYWJvdmU1MD8iVXplcmluZGUiOiJBbHRpbmRhIixnOnIuYWJvdmU1MH0sCiAgICB7bDoiU01BMjAwIix2OnIuYWJvdmUyMDA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIsZzpyLmFib3ZlMjAwfSwKICAgIHtsOiJSU0kiLHY6ci5yc2l8fCI/IixnOnIucnNpP3IucnNpPDMwP3RydWU6ci5yc2k+NzA/ZmFsc2U6bnVsbDpudWxsfSwKICAgIHtsOiI1MlciLHY6IiUiK3IucGN0X2Zyb21fNTJ3KyIgdXphayIsZzpyLm5lYXJfNTJ3fQogIF0ubWFwKGZ1bmN0aW9uKHMpe3JldHVybiAnPHNwYW4gY2xhc3M9InNwICcrKHMuZz09PXRydWU/InNnIjpzLmc9PT1mYWxzZT8ic2IiOiJzbiIpKyciPicrcy5sKyI6ICIrcy52KyI8L3NwYW4+Ijt9KS5qb2luKCIiKTsKICByZXR1cm4gJzxkaXYgY2xhc3M9ImNhcmQiIHN0eWxlPSJib3JkZXItY29sb3I6Jysoci5wb3J0Zm9saW8/InJnYmEoMTYsMTg1LDEyOSwuMjUpIjpzcy5iZCkrJyIgb25jbGljaz0ib3Blbk0oXCcnK3IudGlja2VyKydcJykiPicKICAgICsnPGRpdiBjbGFzcz0iYWNjZW50IiBzdHlsZT0iYmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoOTBkZWcsJytzcy5hYysnLCcrc3MuYWMrJzg4KSI+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJjYm9keSI+PGRpdiBjbGFzcz0iY3RvcCI+PGRpdj48ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo0cHgiPicKICAgICsnPHNwYW4gY2xhc3M9InRpY2tlciIgc3R5bGU9ImNvbG9yOicrc3MudHgrJyI+JytyLnRpY2tlcisnPC9zcGFuPicKICAgICsoci5wb3J0Zm9saW8/JzxzcGFuIGNsYXNzPSJwb3J0LWJhZGdlIj5QPC9zcGFuPic6JycpKwogICAgJzwvZGl2PjxzcGFuIGNsYXNzPSJiYWRnZSIgc3R5bGU9ImJhY2tncm91bmQ6Jytzcy5iZysnO2NvbG9yOicrc3MudHgrJztib3JkZXI6MXB4IHNvbGlkICcrc3MuYmQrJyI+Jytzcy5sYmwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImNwciI+PGRpdiBjbGFzcz0icHZhbCI+JCcrci5maXlhdCsnPC9kaXY+PGRpdiBjbGFzcz0icGNoZyIgc3R5bGU9ImNvbG9yOicrZGMrJyI+JytkcysnPC9kaXY+JwogICAgKyhyLnBlX2Z3ZD8nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkZ3ZFBFOicrci5wZV9md2QudG9GaXhlZCgxKSsnPC9kaXY+JzonJykKICAgICsnPC9kaXY+PC9kaXY+PGRpdiBjbGFzcz0ic2lncyI+JytzaWdzKyc8L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9Im1hcmdpbi10b3A6NnB4Ij4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjNweCI+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5HaXJpcyBLYWxpdGVzaTwvc3Bhbj48c3BhbiBzdHlsZT0iZm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X3Njb3JlKycvMTAwPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iaGVpZ2h0OjRweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czoycHg7b3ZlcmZsb3c6aGlkZGVuIj48ZGl2IHN0eWxlPSJoZWlnaHQ6MTAwJTt3aWR0aDonK3IuZW50cnlfc2NvcmUrJyU7YmFja2dyb3VuZDonK2VzY29sKyc7Ym9yZGVyLXJhZGl1czoycHgiPjwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi10b3A6M3B4Ij48c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK2VzY29sKyciPicrci5lbnRyeV9sYWJlbCsnPC9zcGFuPjxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrcHZjb2wrJyI+JytyLnByaWNlX3ZzX2lkZWFsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8L2Rpdj48ZGl2IGNsYXNzPSJjaGFydC13Ij48Y2FudmFzIGlkPSJtYy0nK3IudGlja2VyKyciPjwvY2FudmFzPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0ibHZscyI+JwogICAgKyc8ZGl2IGNsYXNzPSJsdiI+PGRpdiBjbGFzcz0ibGwiPkhlbWVuIEdpcjwvZGl2PjxkaXYgY2xhc3M9Imx2YWwiIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbjIpIj4kJytyLmVudHJ5X2FnZ3Jlc3NpdmUrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0ibHYiPjxkaXYgY2xhc3M9ImxsIj5IZWRlZjwvZGl2PjxkaXYgY2xhc3M9Imx2YWwiIHN0eWxlPSJjb2xvcjojNjBhNWZhIj4kJytyLmhlZGVmKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9Imx2Ij48ZGl2IGNsYXNzPSJsbCI+U3RvcDwvZGl2PjxkaXYgY2xhc3M9Imx2YWwiIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKSI+JCcrci5zdG9wKyc8L2Rpdj48L2Rpdj4nCiAgICArJzwvZGl2PjwvZGl2PjwvZGl2Pic7Cn0KCmZ1bmN0aW9uIHJlbmRlckRhc2hib2FyZCgpewogIHZhciBncmlkPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJncmlkIik7CiAgdmFyIG1kPU1BUktFVF9EQVRBfHx7fTsKICB2YXIgc3A9bWQuU1A1MDB8fHt9OwogIHZhciBuYXM9bWQuTkFTREFRfHx7fTsKICB2YXIgdml4PW1kLlZJWHx8e307CiAgdmFyIG1TaWduYWw9bWQuTV9TSUdOQUx8fCJOT1RSIjsKICB2YXIgbUxhYmVsPW1kLk1fTEFCRUx8fCJWZXJpIHlvayI7CiAgdmFyIG1Db2xvcj1tU2lnbmFsPT09IkdVQ0xVIj8idmFyKC0tZ3JlZW4pIjptU2lnbmFsPT09IlpBWUlGIj8idmFyKC0tcmVkMikiOiJ2YXIoLS15ZWxsb3cpIjsKICB2YXIgbUJnPW1TaWduYWw9PT0iR1VDTFUiPyJyZ2JhKDE2LDE4NSwxMjksLjA4KSI6bVNpZ25hbD09PSJaQVlJRiI/InJnYmEoMjM5LDY4LDY4LC4wOCkiOiJyZ2JhKDI0NSwxNTgsMTEsLjA4KSI7CiAgdmFyIG1Cb3JkZXI9bVNpZ25hbD09PSJHVUNMVSI/InJnYmEoMTYsMTg1LDEyOSwuMjUpIjptU2lnbmFsPT09IlpBWUlGIj8icmdiYSgyMzksNjgsNjgsLjI1KSI6InJnYmEoMjQ1LDE1OCwxMSwuMjUpIjsKICB2YXIgbUljb249bVNpZ25hbD09PSJHVUNMVSI/IuKchSI6bVNpZ25hbD09PSJaQVlJRiI/IuKdjCI6IuKaoO+4jyI7CgogIGZ1bmN0aW9uIGluZGV4Q2FyZChuYW1lLGRhdGEpewogICAgaWYoIWRhdGF8fCFkYXRhLnByaWNlKSByZXR1cm4gIiI7CiAgICB2YXIgY2M9ZGF0YS5jaGFuZ2U+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgICB2YXIgY3M9KGRhdGEuY2hhbmdlPj0wPyIrIjoiIikrZGF0YS5jaGFuZ2UrIiUiOwogICAgdmFyIHM1MD1kYXRhLmFib3ZlNTA/JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjEwcHgiPlNNQTUwIOKckzwvc3Bhbj4nOic8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMik7Zm9udC1zaXplOjEwcHgiPlNNQTUwIOKclzwvc3Bhbj4nOwogICAgdmFyIHMyMDA9ZGF0YS5hYm92ZTIwMD8nPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6MTBweCI+U01BMjAwIOKckzwvc3Bhbj4nOic8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMik7Zm9udC1zaXplOjEwcHgiPlNNQTIwMCDinJc8L3NwYW4+JzsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4IDE2cHg7ZmxleDoxO21pbi13aWR0aDoxNTBweCI+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjZweCI+JytuYW1lKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KSI+JCcrZGF0YS5wcmljZSsnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTNweDtjb2xvcjonK2NjKyc7bWFyZ2luLWJvdHRvbTo4cHgiPicrY3MrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjhweCI+JytzNTArczIwMCsnPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciBwb3J0RGF0YT1jdXJEYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YSYmUE9SVC5pbmNsdWRlcyhyLnRpY2tlcik7fSk7CiAgdmFyIHBvcnRIdG1sPSIiOwogIGlmKHBvcnREYXRhLmxlbmd0aCl7CiAgICBwb3J0SHRtbD0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTRweCI+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTJweCI+8J+SvCBQb3J0ZsO2eSDDlnpldGk8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgxNDBweCwxZnIpKTtnYXA6OHB4Ij4nOwogICAgcG9ydERhdGEuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgICAgdmFyIGRjPXIuZGVnaXNpbT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICAgICAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogICAgICBwb3J0SHRtbCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkICcrc3MuYmQrJztib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHg7Y3Vyc29yOnBvaW50ZXIiIG9uY2xpY2s9Im9wZW5NKFwnJytyLnRpY2tlcisnXCcpIj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToxNnB4O2xldHRlci1zcGFjaW5nOjJweDtjb2xvcjonK3NzLnR4KyciPicrci50aWNrZXIrJzwvc3Bhbj4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtiYWNrZ3JvdW5kOicrc3MuYmcrJztjb2xvcjonK3NzLnR4Kyc7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6MnB4Ij4nK3NzLmxibCsnPC9zcGFuPjwvZGl2PicKICAgICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDAiPiQnK3IuZml5YXQrJzwvZGl2PicKICAgICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTFweDtjb2xvcjonK2RjKyciPicrKHIuZGVnaXNpbT49MD8iKyI6IiIpK3IuZGVnaXNpbSsnJTwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICAgIHBvcnRIdG1sKz0nPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciB1cmdlbnRFYXJuaW5ncz1FQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gZS5hbGVydD09PSJyZWQifHxlLmFsZXJ0PT09InllbGxvdyI7fSk7CiAgdmFyIGVhcm5pbmdzQWxlcnQ9IiI7CiAgaWYodXJnZW50RWFybmluZ3MubGVuZ3RoKXsKICAgIGVhcm5pbmdzQWxlcnQ9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE0cHggMTZweDttYXJnaW4tYm90dG9tOjE0cHgiPicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS15ZWxsb3cpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7imqDvuI8gWWFrbGHFn2FuIFJhcG9ybGFyPC9kaXY+JzsKICAgIHVyZ2VudEVhcm5pbmdzLmZvckVhY2goZnVuY3Rpb24oZSl7CiAgICAgIHZhciBpYz1lLmFsZXJ0PT09InJlZCI/IvCflLQiOiLwn5+hIjsKICAgICAgZWFybmluZ3NBbGVydCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbTo2cHg7Zm9udC1zaXplOjEycHgiPicKICAgICAgICArJzxzcGFuPicraWMrJyA8c3Ryb25nPicrZS50aWNrZXIrJzwvc3Ryb25nPjwvc3Bhbj4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj4nK2UubmV4dF9kYXRlKycgKCcrKGUuZGF5c190b19lYXJuaW5ncz09PTA/IkJVR8OcTiI6ZS5kYXlzX3RvX2Vhcm5pbmdzKyIgZ8O8biIpKycpPC9zcGFuPjwvZGl2Pic7CiAgICB9KTsKICAgIGVhcm5pbmdzQWxlcnQrPSc8L2Rpdj4nOwogIH0KCiAgdmFyIG5ld3NIdG1sPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHgiPicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMnB4Ij7wn5OwIFNvbiBIYWJlcmxlcjwvZGl2Pic7CiAgaWYoTkVXU19EQVRBJiZORVdTX0RBVEEubGVuZ3RoKXsKICAgIE5FV1NfREFUQS5zbGljZSgwLDEwKS5mb3JFYWNoKGZ1bmN0aW9uKG4pewogICAgICB2YXIgcGI9bi5wb3J0Zm9saW8/JzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTIpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMjUpO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMCI+UDwvc3Bhbj4nOiIiOwogICAgICB2YXIgdGE9IiI7CiAgICAgIGlmKG4uZGF0ZXRpbWUpe3ZhciBkaWZmPU1hdGguZmxvb3IoKERhdGUubm93KCkvMTAwMC1uLmRhdGV0aW1lKS8zNjAwKTt0YT1kaWZmPDI0PyhkaWZmKyJzIMO2bmNlIik6KE1hdGguZmxvb3IoZGlmZi8yNCkrImcgw7ZuY2UiKTt9CiAgICAgIG5ld3NIdG1sKz0nPGRpdiBzdHlsZT0icGFkZGluZzoxMHB4IDA7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDQpIj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo2cHg7bWFyZ2luLWJvdHRvbTo0cHgiPicKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0teWVsbG93KSI+JytuLnRpY2tlcisnPC9zcGFuPicrcGIKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tbGVmdDphdXRvIj4nK3RhKyc8L3NwYW4+PC9kaXY+JwogICAgICAgICsnPGEgaHJlZj0iJytuLnVybCsnIiB0YXJnZXQ9Il9ibGFuayIgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLXRleHQpO3RleHQtZGVjb3JhdGlvbjpub25lO2xpbmUtaGVpZ2h0OjEuNTtkaXNwbGF5OmJsb2NrIj4nKyhuLmhlYWRsaW5lX3RyfHxuLmhlYWRsaW5lKSsnPC9hPicKICAgICAgICArKG4uc3VtbWFyeV90cnx8bi5zdW1tYXJ5Pyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjojOWNhM2FmO21hcmdpbi10b3A6NHB4O2xpbmUtaGVpZ2h0OjEuNCI+Jysobi5zdW1tYXJ5X3RyfHxuLnN1bW1hcnkpLnN1YnN0cmluZygwLDE1MCkrJy4uLjwvZGl2Pic6JycpKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLXRvcDozcHgiPicrbi5zb3VyY2UrJzwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICB9IGVsc2UgewogICAgbmV3c0h0bWwrPSc8ZGl2IHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1zaXplOjEycHgiPkhhYmVyIGJ1bHVuYW1hZGk8L2Rpdj4nOwogIH0KICBuZXdzSHRtbCs9JzwvZGl2Pic7CgogIGdyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nCiAgICArJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JyttQmcrJztib3JkZXI6MXB4IHNvbGlkICcrbUJvcmRlcisnO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTJweCI+JwogICAgKyc8ZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7bWFyZ2luLWJvdHRvbTo0cHgiPkNBTlNMSU0gTSBLUsSwVEVSxLA8L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK21Db2xvcisnIj4nK21JY29uKycgJyttTGFiZWwrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO3RleHQtYWxpZ246cmlnaHQiPlZJWDogJysodml4LnByaWNlfHwiPyIpKyc8YnI+JwogICAgKyc8c3BhbiBzdHlsZT0iY29sb3I6Jysodml4LnByaWNlJiZ2aXgucHJpY2U+MjU/InZhcigtLXJlZDIpIjoidmFyKC0tZ3JlZW4pIikrJyI+Jysodml4LnByaWNlJiZ2aXgucHJpY2U+MjU/IlnDvGtzZWsgdm9sYXRpbGl0ZSI6Ik5vcm1hbCB2b2xhdGlsaXRlIikrJzwvc3Bhbj48L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcDttYXJnaW4tYm90dG9tOjE0cHgiPicraW5kZXhDYXJkKCJTJlAgNTAwIChTUFkpIixzcCkraW5kZXhDYXJkKCJOQVNEQVEgKFFRUSkiLG5hcykrJzwvZGl2PicKICAgICtwb3J0SHRtbCtlYXJuaW5nc0FsZXJ0K25ld3NIdG1sKyc8L2Rpdj4nOwp9CgpmdW5jdGlvbiByZW5kZXJFYXJuaW5ncygpewogIHZhciBncmlkPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJncmlkIik7CiAgdmFyIHNvcnRlZD1FQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gZS5uZXh0X2RhdGU7fSkuc29ydChmdW5jdGlvbihhLGIpewogICAgdmFyIGRhPWEuZGF5c190b19lYXJuaW5ncyE9bnVsbD9hLmRheXNfdG9fZWFybmluZ3M6OTk5OwogICAgdmFyIGRiPWIuZGF5c190b19lYXJuaW5ncyE9bnVsbD9iLmRheXNfdG9fZWFybmluZ3M6OTk5OwogICAgcmV0dXJuIGRhLWRiOwogIH0pOwogIHZhciBub0RhdGU9RUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuICFlLm5leHRfZGF0ZTt9KTsKICBpZighc29ydGVkLmxlbmd0aCYmIW5vRGF0ZS5sZW5ndGgpe2dyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xO3RleHQtYWxpZ246Y2VudGVyO3BhZGRpbmc6NDBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkVhcm5pbmdzIHZlcmlzaSBidWx1bmFtYWRpPC9kaXY+JztyZXR1cm47fQogIHZhciBoPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwogIHNvcnRlZC5mb3JFYWNoKGZ1bmN0aW9uKGUpewogICAgdmFyIGFiPWUuYWxlcnQ9PT0icmVkIj8icmdiYSgyMzksNjgsNjgsLjEyKSI6ZS5hbGVydD09PSJ5ZWxsb3ciPyJyZ2JhKDI0NSwxNTgsMTEsLjEpIjoicmdiYSgyNTUsMjU1LDI1NSwuMDIpIjsKICAgIHZhciBhYmQ9ZS5hbGVydD09PSJyZWQiPyJyZ2JhKDIzOSw2OCw2OCwuMzUpIjplLmFsZXJ0PT09InllbGxvdyI/InJnYmEoMjQ1LDE1OCwxMSwuMykiOiJyZ2JhKDI1NSwyNTUsMjU1LC4wNykiOwogICAgdmFyIGFpPWUuYWxlcnQ9PT0icmVkIj8i8J+UtCI6ZS5hbGVydD09PSJ5ZWxsb3ciPyLwn5+hIjoi8J+ThSI7CiAgICB2YXIgZHQ9ZS5kYXlzX3RvX2Vhcm5pbmdzIT1udWxsPyhlLmRheXNfdG9fZWFybmluZ3M9PT0wPyJCVUdVTiI6ZS5kYXlzX3RvX2Vhcm5pbmdzPT09MT8iWWFyaW4iOmUuZGF5c190b19lYXJuaW5ncysiIGd1biBzb25yYSIpOiIiOwogICAgdmFyIGFtQ29sPWUuYXZnX21vdmVfcGN0IT1udWxsPyhlLmF2Z19tb3ZlX3BjdD49MD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkMikiKToidmFyKC0tbXV0ZWQpIjsKICAgIHZhciBhbVN0cj1lLmF2Z19tb3ZlX3BjdCE9bnVsbD8oZS5hdmdfbW92ZV9wY3Q+PTA/IisiOiIiKStlLmF2Z19tb3ZlX3BjdCsiJSI6IuKAlCI7CiAgICB2YXIgeWI9ZS5hbGVydD09PSJyZWQiPyc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMTUpO2NvbG9yOnZhcigtLXJlZDIpO3BhZGRpbmc6MnB4IDhweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDAiPllBS0lOREE8L3NwYW4+JzoiIjsKICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicrYWIrJztib3JkZXI6MXB4IHNvbGlkICcrYWJkKyc7Ym9yZGVyLXJhZGl1czoxMHB4O21hcmdpbi1ib3R0b206MTBweDtwYWRkaW5nOjE0cHggMTZweCI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2ZsZXgtd3JhcDp3cmFwO2dhcDo4cHgiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6MTBweCI+PHNwYW4+JythaSsnPC9zcGFuPjxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjIwcHg7bGV0dGVyLXNwYWNpbmc6MnB4O2NvbG9yOnZhcigtLXRleHQpIj4nK2UudGlja2VyKyc8L3NwYW4+Jyt5YisnPC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjE2cHg7ZmxleC13cmFwOndyYXA7YWxpZ24taXRlbXM6Y2VudGVyIj4nOwogICAgaCs9JzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+UkFQT1I8L2Rpdj48ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOnZhcigtLXRleHQpIj4nKyhlLm5leHRfZGF0ZXx8IuKAlCIpKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjonKyhlLmFsZXJ0PT09InJlZCI/InZhcigtLXJlZDIpIjplLmFsZXJ0PT09InllbGxvdyI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nK2R0Kyc8L2Rpdj48L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+RVBTIFRBSE1JTjwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo2MDA7Y29sb3I6IzYwYTVmYSI+JysoZS5lcHNfZXN0aW1hdGUhPW51bGw/IiQiK2UuZXBzX2VzdGltYXRlOiLigJQiKSsnPC9kaXY+PC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPk9SVC5IQVJFS0VUPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxNHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK2FtQ29sKyciPicrYW1TdHIrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo4cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5zb24gNCByYXBvcjwvZGl2PjwvZGl2Pic7CiAgICBoKz0nPC9kaXY+PC9kaXY+JzsKICAgIGlmKGUuaGlzdG9yeV9lcHMmJmUuaGlzdG9yeV9lcHMubGVuZ3RoKXsKICAgICAgaCs9JzxkaXYgc3R5bGU9Im1hcmdpbi10b3A6OHB4O3BhZGRpbmctdG9wOjhweDtib3JkZXItdG9wOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNikiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NXB4Ij5TT04gNCBSQVBPUjwvZGl2PjxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KDQsMWZyKTtnYXA6NHB4Ij4nOwogICAgICBlLmhpc3RvcnlfZXBzLmZvckVhY2goZnVuY3Rpb24oaGgpewogICAgICAgIHZhciBzYz1oaC5zdXJwcmlzZV9wY3QhPW51bGw/KGhoLnN1cnByaXNlX3BjdD4wPyJ2YXIoLS1ncmVlbikiOiJ2YXIoLS1yZWQyKSIpOiJ2YXIoLS1tdXRlZCkiOwogICAgICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo0cHg7cGFkZGluZzo2cHg7dGV4dC1hbGlnbjpjZW50ZXI7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNSkiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo4cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK2hoLmRhdGUuc3Vic3RyaW5nKDAsNykrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTBweCI+JysoaGguYWN0dWFsIT1udWxsPyIkIitoaC5hY3R1YWw6Ij8iKSsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK3NjKyciPicrKGhoLnN1cnByaXNlX3BjdCE9bnVsbD8oaGguc3VycHJpc2VfcGN0PjA/IisiOiIiKStoaC5zdXJwcmlzZV9wY3QrIiUiOiI/IikrJzwvZGl2PjwvZGl2Pic7CiAgICAgIH0pOwogICAgICBoKz0nPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGgrPSc8L2Rpdj4nOwogIH0pOwogIGlmKG5vRGF0ZS5sZW5ndGgpe2grPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLXRvcDo2cHgiPlRhcmloIGJ1bHVuYW1heWFuOiAnK25vRGF0ZS5tYXAoZnVuY3Rpb24oZSl7cmV0dXJuIGUudGlja2VyO30pLmpvaW4oIiwgIikrJzwvZGl2Pic7fQogIGgrPSc8L2Rpdj4nOwogIGdyaWQuaW5uZXJIVE1MPWg7Cn0KCmZ1bmN0aW9uIG9wZW5NKHRpY2tlcil7CiAgdmFyIHI9Y3VyRGF0YS5maW5kKGZ1bmN0aW9uKGQpe3JldHVybiBkLnRpY2tlcj09PXRpY2tlcjt9KTsKICBpZighcnx8ci5oYXRhKSByZXR1cm47CiAgaWYobUNoYXJ0KXttQ2hhcnQuZGVzdHJveSgpO21DaGFydD1udWxsO30KICB2YXIgc3M9U1Nbci5zaW55YWxdfHxTU1siRElLS0FUIl07CiAgdmFyIHJyUD1NYXRoLm1pbigoci5yci80KSoxMDAsMTAwKTsKICB2YXIgcnJDPXIucnI+PTM/InZhcigtLWdyZWVuKSI6ci5ycj49Mj8idmFyKC0tZ3JlZW4yKSI6ci5ycj49MT8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZDIpIjsKICB2YXIgZGM9ci5kZWdpc2ltPj0wPyJ2YXIoLS1ncmVlbjIpIjoidmFyKC0tcmVkMikiOwogIHZhciBrYz17IkdVQ0xVIEFMIjoiIzEwYjk4MSIsIkFMIjoiIzM0ZDM5OSIsIkRJS0tBVExJIjoiI2Y1OWUwYiIsIkdFQ01FIjoiI2Y4NzE3MSJ9OwogIHZhciBrbGJsPXsiR1VDTFUgQUwiOiJHVUNMVSBBTCIsIkFMIjoiQUwiLCJESUtLQVRMSSI6IkRJS0tBVExJIiwiR0VDTUUiOiJHRUNNRSJ9OwogIHZhciBlc2NvbD1yLmVudHJ5X3Njb3JlPj03NT8idmFyKC0tZ3JlZW4pIjpyLmVudHJ5X3Njb3JlPj02MD8idmFyKC0tZ3JlZW4yKSI6ci5lbnRyeV9zY29yZT49NDU/InZhcigtLXllbGxvdykiOnIuZW50cnlfc2NvcmU+PTMwPyJ2YXIoLS1yZWQyKSI6InZhcigtLXJlZCkiOwogIHZhciBwdmNvbD1yLnByaWNlX3ZzX2NvbG9yPT09ImdyZWVuIj8idmFyKC0tZ3JlZW4pIjpyLnByaWNlX3ZzX2NvbG9yPT09InllbGxvdyI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQyKSI7CgogIHZhciBtaD0nPGRpdiBjbGFzcz0ibWhlYWQiPjxkaXY+PGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6OHB4O2ZsZXgtd3JhcDp3cmFwIj4nCiAgICArJzxzcGFuIGNsYXNzPSJtdGl0bGUiIHN0eWxlPSJjb2xvcjonK3NzLnR4KyciPicrci50aWNrZXIrJzwvc3Bhbj4nCiAgICArJzxzcGFuIGNsYXNzPSJiYWRnZSIgc3R5bGU9ImJhY2tncm91bmQ6Jytzcy5iZysnO2NvbG9yOicrc3MudHgrJztib3JkZXI6MXB4IHNvbGlkICcrc3MuYmQrJztmb250LXNpemU6MTJweCI+Jytzcy5sYmwrJzwvc3Bhbj4nCiAgICArKHIucG9ydGZvbGlvPyc8c3BhbiBjbGFzcz0icG9ydC1iYWRnZSIgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O3BhZGRpbmc6M3B4IDhweCI+UG9ydGZvbHlvPC9zcGFuPic6JycpCiAgICArJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXdlaWdodDo2MDA7bWFyZ2luLXRvcDo0cHgiPiQnK3IuZml5YXQKICAgICsnIDxzcGFuIHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjonK2RjKyciPicrKHIuZGVnaXNpbT49MD8iKyI6IiIpK3IuZGVnaXNpbSsnJTwvc3Bhbj48L2Rpdj48L2Rpdj4nCiAgICArJzxidXR0b24gY2xhc3M9Im1jbG9zZSIgb25jbGljaz0iY2xvc2VNKCkiPuKclTwvYnV0dG9uPjwvZGl2Pic7CgogIG1oKz0nPGRpdiBjbGFzcz0ibWJvZHkiPjxkaXYgY2xhc3M9Im1jaGFydHciPjxjYW52YXMgaWQ9Im1jaGFydCI+PC9jYW52YXM+PC9kaXY+JzsKCiAgbWgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7bWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPicraWIoIkVudHJ5U2NvcmUiLCJHaXJpcyBLYWxpdGVzaSIpKyc8L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47bWFyZ2luLWJvdHRvbTo2cHgiPicKICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfc2NvcmUrJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTNweDtjb2xvcjp2YXIoLS1tdXRlZCkiPi8xMDA8L3NwYW4+PC9zcGFuPicKICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjonK2VzY29sKyciPicrci5lbnRyeV9sYWJlbCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iaGVpZ2h0OjZweDtiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyLXJhZGl1czozcHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi1ib3R0b206OHB4Ij48ZGl2IHN0eWxlPSJoZWlnaHQ6MTAwJTt3aWR0aDonK3IuZW50cnlfc2NvcmUrJyU7YmFja2dyb3VuZDonK2VzY29sKyc7Ym9yZGVyLXJhZGl1czozcHgiPjwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2ZvbnQtc2l6ZToxMXB4Ij4nCiAgICArJzxkaXY+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+U3UgYW5raSBmaXlhdDogPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjonK3B2Y29sKyc7Zm9udC13ZWlnaHQ6NjAwIj4nK3IucHJpY2VfdnNfaWRlYWwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXY+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+SWRlYWwgYm9sZ2U6IDwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4yKTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuaWRlYWxfZW50cnlfbG93KycgLSAkJytyLmlkZWFsX2VudHJ5X2hpZ2grJzwvc3Bhbj48L2Rpdj4nCiAgICArJzwvZGl2PjwvZGl2Pic7CgogIG1oKz0nPGRpdiBjbGFzcz0iZGJveCIgc3R5bGU9ImJhY2tncm91bmQ6Jytzcy5iZysnO2JvcmRlci1jb2xvcjonK3NzLmJkKyc7bWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgY2xhc3M9ImRsYmwiIHN0eWxlPSJjb2xvcjonK3NzLnR4KyciPicraWIoIlJSIiwiQWxpbSBLYXJhcmkgUi9SIikrJzwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHZlcmQiIHN0eWxlPSJjb2xvcjonKyhrY1tyLmthcmFyXXx8InZhcigtLW11dGVkKSIpKyciPicrKGtsYmxbci5rYXJhcl18fHIua2FyYXIpKyc8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5SaXNrIC8gT2R1bDwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6JytyckMrJztmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4xIDogJytyLnJyKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+SGVtZW4gR2lyPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbjIpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5lbnRyeV9hZ2dyZXNzaXZlKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+R2VyaSBDZWtpbG1lPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjojNjBhNWZhO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5lbnRyeV9taWQrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5CdXl1ayBEdXplbHRtZTwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0teWVsbG93KTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuZW50cnlfY29uc2VydmF0aXZlKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+SGVkZWY8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOiM2MGE1ZmE7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmhlZGVmKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+U3RvcC1Mb3NzPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3Iuc3RvcCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0icnJiYXIiPjxkaXYgY2xhc3M9InJyZmlsbCIgc3R5bGU9IndpZHRoOicrcnJQKyclO2JhY2tncm91bmQ6JytyckMrJyI+PC9kaXY+PC9kaXY+PC9kaXY+JzsKCiAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij5UZWtuaWsgQW5hbGl6PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkZ3JpZCIgc3R5bGU9Im1hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlRyZW5kIiwiVHJlbmQiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnRyZW5kPT09Ill1a3NlbGVuIj8idmFyKC0tZ3JlZW4pIjpyLnRyZW5kPT09IkR1c2VuIj8idmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrci50cmVuZCsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlJTSSIsIlJTSSAxNCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucnNpP3IucnNpPDMwPyJ2YXIoLS1ncmVlbikiOnIucnNpPjcwPyJ2YXIoLS1yZWQpIjoidmFyKC0teWVsbG93KSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucnNpfHwiPyIpKyhyLnJzaT9yLnJzaTwzMD8iIEFzaXJpIFNhdGltIjpyLnJzaT43MD8iIEFzaXJpIEFsaW0iOiIgTm90ciI6IiIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiU01BNTAiLCJTTUEgNTAiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmFib3ZlNTA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZCkiKSsnIj4nKyhyLmFib3ZlNTA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIpKyhyLnNtYTUwX2Rpc3QhPW51bGw/IiAoIityLnNtYTUwX2Rpc3QrIiUpIjoiIikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJTTUEyMDAiLCJTTUEgMjAwIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5hYm92ZTIwMD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkKSIpKyciPicrKHIuYWJvdmUyMDA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIpKyhyLnNtYTIwMF9kaXN0IT1udWxsPyIgKCIrci5zbWEyMDBfZGlzdCsiJSkiOiIiKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIjUyVyIsIjUySCBQb3ouIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci53NTJfcG9zaXRpb248PTMwPyJ2YXIoLS1ncmVlbikiOnIudzUyX3Bvc2l0aW9uPj04NT8idmFyKC0tcmVkKSI6InZhcigtLXllbGxvdykiKSsnIj4nK3IudzUyX3Bvc2l0aW9uKyclPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIkhhY2ltIiwiSGFjaW0iKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmhhY2ltPT09Ill1a3NlayI/InZhcigtLWdyZWVuKSI6ci5oYWNpbT09PSJEdXN1ayI/InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nK3IuaGFjaW0rJyAoJytyLnZvbF9yYXRpbysneCk8L2Rpdj48L2Rpdj4nCiAgICArJzwvZGl2Pic7CgogIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+VGVtZWwgQW5hbGl6PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkZ3JpZCIgc3R5bGU9Im1hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIkZvcndhcmRQRSIsIkZvcndhcmQgUEUiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnBlX2Z3ZD9yLnBlX2Z3ZDwyNT8idmFyKC0tZ3JlZW4pIjpyLnBlX2Z3ZDw0MD8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnBlX2Z3ZD9yLnBlX2Z3ZC50b0ZpeGVkKDEpOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJQRUciLCJQRUciKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnBlZz9yLnBlZzwxPyJ2YXIoLS1ncmVlbikiOnIucGVnPDI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5wZWc/ci5wZWcudG9GaXhlZCgyKToiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiRVBTR3Jvd3RoIiwiRVBTIELDvHnDvG1lIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5lcHNfZ3Jvd3RoP3IuZXBzX2dyb3d0aD49MjA/InZhcigtLWdyZWVuKSI6ci5lcHNfZ3Jvd3RoPj0wPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIuZXBzX2dyb3d0aCE9bnVsbD9yLmVwc19ncm93dGgrIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJSZXZHcm93dGgiLCJHZWxpciBCw7x5w7xtZSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucmV2X2dyb3d0aD9yLnJldl9ncm93dGg+PTE1PyJ2YXIoLS1ncmVlbikiOnIucmV2X2dyb3d0aD49MD8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnJldl9ncm93dGghPW51bGw/ci5yZXZfZ3Jvd3RoKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiTmV0TWFyZ2luIiwiTmV0IE1hcmppbiIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIubmV0X21hcmdpbj9yLm5ldF9tYXJnaW4+PTE1PyJ2YXIoLS1ncmVlbikiOnIubmV0X21hcmdpbj49NT8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLm5ldF9tYXJnaW4hPW51bGw/ci5uZXRfbWFyZ2luKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUk9FIiwiUk9FIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5yb2U/ci5yb2U+PTE1PyJ2YXIoLS1ncmVlbikiOnIucm9lPj01PyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucm9lIT1udWxsP3Iucm9lKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzwvZGl2Pic7CgogIHZhciBhaVRleHQgPSBBSV9EQVRBICYmIEFJX0RBVEFbdGlja2VyXTsKICBpZihhaVRleHQpewogICAgbWgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O21hcmdpbi1ib3R0b206MTJweCI+JzsKICAgIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPvCfpJYgQUkgQW5hbGl6IChDbGF1ZGUgU29ubmV0KTwvZGl2Pic7CiAgICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLXRleHQpO2xpbmUtaGVpZ2h0OjEuNzt3aGl0ZS1zcGFjZTpwcmUtd3JhcCI+JythaVRleHQrJzwvZGl2Pic7CiAgICBtaCs9JzwvZGl2Pic7CiAgfQogIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO3RleHQtYWxpZ246Y2VudGVyIj5CdSBhcmFjIHlhdGlyaW0gdGF2c2l5ZXNpIGRlZ2lsZGlyPC9kaXY+PC9kaXY+JzsKCiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1vZGFsIikuaW5uZXJIVE1MPW1oOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJvdmVybGF5IikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwogIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsKICAgIHZhciBjdHg9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1jaGFydCIpOwogICAgaWYoY3R4JiZyLmNoYXJ0X2Nsb3Nlcyl7CiAgICAgIG1DaGFydD1uZXcgQ2hhcnQoY3R4LHt0eXBlOiJsaW5lIixkYXRhOntsYWJlbHM6ci5jaGFydF9kYXRlcyxkYXRhc2V0czpbCiAgICAgICAge2xhYmVsOiJGaXlhdCIsZGF0YTpyLmNoYXJ0X2Nsb3Nlcyxib3JkZXJDb2xvcjpzcy5hYyxib3JkZXJXaWR0aDoyLGZpbGw6dHJ1ZSxiYWNrZ3JvdW5kQ29sb3I6c3MuYWMrIjIwIixwb2ludFJhZGl1czowLHRlbnNpb246MC4zfSwKICAgICAgICByLnNtYTUwP3tsYWJlbDoiU01BNTAiLGRhdGE6QXJyYXkoci5jaGFydF9jbG9zZXMubGVuZ3RoKS5maWxsKHIuc21hNTApLGJvcmRlckNvbG9yOiIjZjU5ZTBiIixib3JkZXJXaWR0aDoxLjUsYm9yZGVyRGFzaDpbNSw1XSxwb2ludFJhZGl1czowLGZpbGw6ZmFsc2V9Om51bGwsCiAgICAgICAgci5zbWEyMDA/e2xhYmVsOiJTTUEyMDAiLGRhdGE6QXJyYXkoci5jaGFydF9jbG9zZXMubGVuZ3RoKS5maWxsKHIuc21hMjAwKSxib3JkZXJDb2xvcjoiIzhiNWNmNiIsYm9yZGVyV2lkdGg6MS41LGJvcmRlckRhc2g6WzUsNV0scG9pbnRSYWRpdXM6MCxmaWxsOmZhbHNlfTpudWxsCiAgICAgIF0uZmlsdGVyKEJvb2xlYW4pfSxvcHRpb25zOntyZXNwb25zaXZlOnRydWUsbWFpbnRhaW5Bc3BlY3RSYXRpbzpmYWxzZSwKICAgICAgICBwbHVnaW5zOntsZWdlbmQ6e2xhYmVsczp7Y29sb3I6IiM2YjcyODAiLGZvbnQ6e3NpemU6MTB9fX19LAogICAgICAgIHNjYWxlczp7eDp7ZGlzcGxheTp0cnVlLHRpY2tzOntjb2xvcjoiIzM3NDE1MSIsbWF4VGlja3NMaW1pdDo1LGZvbnQ6e3NpemU6OX19LGdyaWQ6e2NvbG9yOiJyZ2JhKDI1NSwyNTUsMjU1LC4wNCkifX0sCiAgICAgICAgICB5OntkaXNwbGF5OnRydWUsdGlja3M6e2NvbG9yOiIjMzc0MTUxIixmb250OntzaXplOjl9fSxncmlkOntjb2xvcjoicmdiYSgyNTUsMjU1LDI1NSwuMDQpIn19fX19KTsKICAgIH0KICB9LDEwMCk7Cn0KCgovLyDilIDilIAgR8OcTkzDnEsgUlVUxLBOIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgAp2YXIgUlVUSU5fSVRFTVMgPSB7CiAgc2FiYWg6IHsKICAgIGxhYmVsOiAi8J+MhSBTYWJhaCDigJQgUGl5YXNhIEHDp8SxbG1hZGFuIMOWbmNlIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoiczEiLCB0ZXh0OiJEYXNoYm9hcmTEsSBhw6cg4oCUIE0ga3JpdGVyaSB5ZcWfaWwgbWk/IChTJlA1MDAgKyBOQVNEQVEgU01BMjAwIMO8c3TDvG5kZSkifSwKICAgICAge2lkOiJzMiIsIHRleHQ6IkVhcm5pbmdzIHNla21lc2luaSBrb250cm9sIGV0IOKAlCBidWfDvG4vYnUgaGFmdGEgcmFwb3IgdmFyIG3EsT8ifSwKICAgICAge2lkOiJzMyIsIHRleHQ6IlZJWCAyNSBhbHTEsW5kYSBtxLE/IChZw7xrc2Vrc2UgeWVuaSBwb3ppc3lvbiBhw6dtYSkifSwKICAgICAge2lkOiJzNCIsIHRleHQ6IsOWbmNla2kgZ8O8bmRlbiBiZWtsZXllbiBhbGFybSBtYWlsaSB2YXIgbcSxPyJ9CiAgICBdCiAgfSwKICBvZ2xlbjogewogICAgbGFiZWw6ICLwn5OKIMOWxJ9sZWRlbiBTb25yYSDigJQgUGl5YXNhIEHDp8Sxa2tlbiIsCiAgICBpdGVtczogWwogICAgICB7aWQ6Im8xIiwgdGV4dDoiUG9ydGbDtnnDvG0gc2VrbWVzaW5kZSBoaXNzZWxlcmltZSBiYWsg4oCUIGJla2xlbm1lZGlrIGTDvMWfw7zFnyB2YXIgbcSxPyJ9LAogICAgICB7aWQ6Im8yIiwgdGV4dDoiU3RvcCBzZXZpeWVzaW5lIHlha2xhxZ9hbiBoaXNzZSB2YXIgbcSxPyAoS8Sxcm3EsXrEsSBpxZ9hcmV0KSJ9LAogICAgICB7aWQ6Im8zIiwgdGV4dDoiQWwgc2lueWFsaSBzZWttZXNpbmRlIHllbmkgZsSxcnNhdCDDp8Sxa23EscWfIG3EsT8ifSwKICAgICAge2lkOiJvNCIsIHRleHQ6IldhdGNobGlzdHRla2kgaGlzc2VsZXJkZSBnaXJpxZ8ga2FsaXRlc2kgNjArIG9sYW4gdmFyIG3EsT8ifSwKICAgICAge2lkOiJvNSIsIHRleHQ6IkhhYmVybGVyZGUgcG9ydGbDtnnDvG3DvCBldGtpbGV5ZW4gw7ZuZW1saSBnZWxpxZ9tZSB2YXIgbcSxPyJ9CiAgICBdCiAgfSwKICBha3NhbTogewogICAgbGFiZWw6ICLwn4yZIEFrxZ9hbSDigJQgUGl5YXNhIEthcGFuZMSxa3RhbiBTb25yYSIsCiAgICBpdGVtczogWwogICAgICB7aWQ6ImExIiwgdGV4dDoiMUggc2lueWFsbGVyaW5pIGtvbnRyb2wgZXQg4oCUIGhhZnRhbMSxayB0cmVuZCBkZcSfacWfbWnFnyBtaT8ifSwKICAgICAge2lkOiJhMiIsIHRleHQ6IllhcsSxbiBpw6dpbiBwb3RhbnNpeWVsIGdpcmnFnyBub2t0YWxhcsSxbsSxIG5vdCBhbCJ9LAogICAgICB7aWQ6ImEzIiwgdGV4dDoiUG9ydGbDtnlkZWtpIGhlciBoaXNzZW5pbiBzdG9wIHNldml5ZXNpbmkgZ8O2emRlbiBnZcOnaXIifSwKICAgICAge2lkOiJhNCIsIHRleHQ6IllhcsSxbiByYXBvciBhw6fEsWtsYXlhY2FrIGhpc3NlIHZhciBtxLE/IChFYXJuaW5ncyBzZWttZXNpKSJ9CiAgICBdCiAgfSwKICBoYWZ0YWxpazogewogICAgbGFiZWw6ICLwn5OFIEhhZnRhbMSxayDigJQgUGF6YXIgQWvFn2FtxLEiLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJoMSIsIHRleHQ6IlN0b2NrIFJvdmVyZGEgQ0FOU0xJTSBzY3JlZW5lcsSxIMOnYWzEscWfdMSxciJ9LAogICAgICB7aWQ6ImgyIiwgdGV4dDoiVkNQIE1pbmVydmluaSBzY3JlZW5lcsSxIMOnYWzEscWfdMSxciJ9LAogICAgICB7aWQ6ImgzIiwgdGV4dDoiUXVsbGFtYWdnaWUgQnJlYWtvdXQgc2NyZWVuZXLEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoNCIsIHRleHQ6IkZpbnZpemRlIEluc3RpdHV0aW9uYWwgQnV5aW5nIHNjcmVlbmVyxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDUiLCB0ZXh0OiLDh2FrxLHFn2FuIGhpc3NlbGVyaSBidWwg4oCUIGVuIGfDvMOnbMO8IGFkYXlsYXIifSwKICAgICAge2lkOiJoNiIsIHRleHQ6IkdpdEh1YiBBY3Rpb25zZGFuIFJ1biBXb3JrZmxvdyBiYXMg4oCUIHNpdGUgZ8O8bmNlbGxlbmlyIn0sCiAgICAgIHtpZDoiaDciLCB0ZXh0OiJHZWxlY2VrIGhhZnRhbsSxbiBlYXJuaW5ncyB0YWt2aW1pbmkga29udHJvbCBldCJ9LAogICAgICB7aWQ6Img4IiwgdGV4dDoiUG9ydGbDtnkgZ2VuZWwgZGXEn2VybGVuZGlybWVzaSDigJQgaGVkZWZsZXIgaGFsYSBnZcOnZXJsaSBtaT8ifQogICAgXQogIH0KfTsKCmZ1bmN0aW9uIGdldFRvZGF5S2V5KCl7CiAgcmV0dXJuIG5ldyBEYXRlKCkudG9EYXRlU3RyaW5nKCk7Cn0KCmZ1bmN0aW9uIGxvYWRDaGVja2VkKCl7CiAgdHJ5ewogICAgdmFyIGRhdGEgPSBsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgncnV0aW5fY2hlY2tlZCcpOwogICAgaWYoIWRhdGEpIHJldHVybiB7fTsKICAgIHZhciBwYXJzZWQgPSBKU09OLnBhcnNlKGRhdGEpOwogICAgLy8gU2FkZWNlIGJ1Z8O8bsO8biB2ZXJpbGVyaW5pIGt1bGxhbgogICAgaWYocGFyc2VkLmRhdGUgIT09IGdldFRvZGF5S2V5KCkpIHJldHVybiB7fTsKICAgIHJldHVybiBwYXJzZWQuaXRlbXMgfHwge307CiAgfWNhdGNoKGUpe3JldHVybiB7fTt9Cn0KCmZ1bmN0aW9uIHNhdmVDaGVja2VkKGNoZWNrZWQpewogIGxvY2FsU3RvcmFnZS5zZXRJdGVtKCdydXRpbl9jaGVja2VkJywgSlNPTi5zdHJpbmdpZnkoewogICAgZGF0ZTogZ2V0VG9kYXlLZXkoKSwKICAgIGl0ZW1zOiBjaGVja2VkCiAgfSkpOwp9CgpmdW5jdGlvbiB0b2dnbGVDaGVjayhpZCl7CiAgdmFyIGNoZWNrZWQgPSBsb2FkQ2hlY2tlZCgpOwogIGlmKGNoZWNrZWRbaWRdKSBkZWxldGUgY2hlY2tlZFtpZF07CiAgZWxzZSBjaGVja2VkW2lkXSA9IHRydWU7CiAgc2F2ZUNoZWNrZWQoY2hlY2tlZCk7CiAgcmVuZGVyUnV0aW4oKTsKfQoKZnVuY3Rpb24gcmVzZXRSdXRpbigpewogIGxvY2FsU3RvcmFnZS5yZW1vdmVJdGVtKCdydXRpbl9jaGVja2VkJyk7CiAgcmVuZGVyUnV0aW4oKTsKfQoKCmZ1bmN0aW9uIHJlbmRlckhhZnRhbGlrKCl7CiAgdmFyIGdyaWQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogIHZhciB3ZCA9IFdFRUtMWV9EQVRBIHx8IHt9OwogIHZhciBwb3J0ID0gd2QucG9ydGZvbGlvIHx8IFtdOwogIHZhciB3YXRjaCA9IHdkLndhdGNobGlzdCB8fCBbXTsKICB2YXIgYmVzdCA9IHdkLmJlc3Q7CiAgdmFyIHdvcnN0ID0gd2Qud29yc3Q7CiAgdmFyIG1kID0gTUFSS0VUX0RBVEEgfHwge307CiAgdmFyIHNwID0gbWQuU1A1MDAgfHwge307CiAgdmFyIG5hcyA9IG1kLk5BU0RBUSB8fCB7fTsKCiAgZnVuY3Rpb24gY2hnQ29sb3Iodil7IHJldHVybiB2ID49IDAgPyAndmFyKC0tZ3JlZW4pJyA6ICd2YXIoLS1yZWQyKSc7IH0KICBmdW5jdGlvbiBjaGdTdHIodil7IHJldHVybiAodiA+PSAwID8gJysnIDogJycpICsgdiArICclJzsgfQoKICBmdW5jdGlvbiBwZXJmQ2FyZChpdGVtKXsKICAgIHZhciBjYyA9IGNoZ0NvbG9yKGl0ZW0ud2Vla19jaGcpOwogICAgdmFyIHBiID0gaXRlbS5wb3J0Zm9saW8gPyAnPHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xMik7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yNSk7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwO21hcmdpbi1sZWZ0OjRweCI+UDwvc3Bhbj4nIDogJyc7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDEycHg7ZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjZweCI+JwogICAgICArICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo2cHgiPjxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjE2cHg7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgaXRlbS50aWNrZXIgKyAnPC9zcGFuPicgKyBwYiArICc8L2Rpdj4nCiAgICAgICsgJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPicKICAgICAgKyAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxNHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgY2MgKyAnIj4nICsgY2hnU3RyKGl0ZW0ud2Vla19jaGcpICsgJzwvZGl2PicKICAgICAgKyAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPsOWbmNla2k6ICcgKyBjaGdTdHIoaXRlbS5wcmV2X3dlZWtfY2hnKSArICc8L2Rpdj4nCiAgICAgICsgJzwvZGl2PjwvZGl2Pic7CiAgfQoKICB2YXIgaCA9ICc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwoKICAvLyBIZWFkZXIKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4Ij7wn5OIIEhhZnRhbMSxayBQZXJmb3JtYW5zIMOWemV0aTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nICsgKHdkLmdlbmVyYXRlZCB8fCAnJykgKyAnPC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBQaXlhc2EgdnMgUG9ydGbDtnkKICB2YXIgc3BDaGcgPSBzcC5jaGFuZ2UgfHwgMDsKICB2YXIgbmFzQ2hnID0gbmFzLmNoYW5nZSB8fCAwOwogIHZhciBwb3J0QXZnID0gcG9ydC5sZW5ndGggPyBNYXRoLnJvdW5kKHBvcnQucmVkdWNlKGZ1bmN0aW9uKGEsYil7cmV0dXJuIGErYi53ZWVrX2NoZzt9LDApL3BvcnQubGVuZ3RoKjEwMCkvMTAwIDogMDsKICB2YXIgYWxwaGEgPSBNYXRoLnJvdW5kKChwb3J0QXZnIC0gc3BDaGcpKjEwMCkvMTAwOwogIHZhciBhbHBoYUNvbCA9IGFscGhhID49IDAgPyAndmFyKC0tZ3JlZW4pJyA6ICd2YXIoLS1yZWQyKSc7CgogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMTQwcHgsMWZyKSk7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPlBvcnRmw7Z5IE9ydC48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Y29sb3I6JyArIGNoZ0NvbG9yKHBvcnRBdmcpICsgJyI+JyArIGNoZ1N0cihwb3J0QXZnKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPlMmUCA1MDA8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Y29sb3I6JyArIGNoZ0NvbG9yKHNwQ2hnKSArICciPicgKyBjaGdTdHIoc3BDaGcpICsgJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+TkFTREFRPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicgKyBjaGdDb2xvcihuYXNDaGcpICsgJyI+JyArIGNoZ1N0cihuYXNDaGcpICsgJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonICsgKGFscGhhPj0wPydyZ2JhKDE2LDE4NSwxMjksLjA4KSc6J3JnYmEoMjM5LDY4LDY4LC4wOCknKSArICc7Ym9yZGVyOjFweCBzb2xpZCAnICsgKGFscGhhPj0wPydyZ2JhKDE2LDE4NSwxMjksLjI1KSc6J3JnYmEoMjM5LDY4LDY4LC4yNSknKSArICc7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPkFscGhhICh2cyBTJlApPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicgKyBhbHBoYUNvbCArICciPicgKyAoYWxwaGE+PTA/JysnOicnKSArIGFscGhhICsgJyU8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIEVuIGl5aSAvIGVuIGvDtnTDvAogIGlmKGJlc3QgfHwgd29yc3QpewogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnIgMWZyO2dhcDoxMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICAgIGlmKGJlc3QpewogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4Ij4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1ncmVlbik7bWFyZ2luLWJvdHRvbTo2cHgiPvCfj4YgQnUgSGFmdGFuxLFuIEVuIMSweWlzaTwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkJlYmFzIE5ldWUsc2Fucy1zZXJpZjtmb250LXNpemU6MjRweDtsZXR0ZXItc3BhY2luZzoycHgiPicgKyBiZXN0LnRpY2tlciArICc8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+KycgKyBiZXN0LndlZWtfY2hnICsgJyU8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaWYod29yc3QpewogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tcmVkMik7bWFyZ2luLWJvdHRvbTo2cHgiPvCfk4kgQnUgSGFmdGFuxLFuIEVuIEvDtnTDvHPDvDwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkJlYmFzIE5ldWUsc2Fucy1zZXJpZjtmb250LXNpemU6MjRweDtsZXR0ZXItc3BhY2luZzoycHgiPicgKyB3b3JzdC50aWNrZXIgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1yZWQyKSI+JyArIHdvcnN0LndlZWtfY2hnICsgJyU8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFBvcnRmw7Z5IGRldGF5CiAgaWYocG9ydC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+SvCBQb3J0ZsO2eTwvZGl2Pic7CiAgICBwb3J0LmZvckVhY2goZnVuY3Rpb24oaXRlbSl7IGggKz0gcGVyZkNhcmQoaXRlbSk7IH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFNpbnlhbGxlciBvemV0aQogIHZhciBidXlDb3VudCA9IChURl9EQVRBWycxZCddfHxbXSkuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdHVUNMVSBBTCd8fHIuc2lueWFsPT09J0FMJzt9KS5sZW5ndGg7CiAgdmFyIHNlbGxDb3VudCA9IChURl9EQVRBWycxZCddfHxbXSkuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdTQVQnO30pLmxlbmd0aDsKICB2YXIgd2F0Y2hDb3VudCA9IChURl9EQVRBWycxZCddfHxbXSkuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdESUtLQVQnO30pLmxlbmd0aDsKCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfk4ogQnUgSGFmdGFraSBTaW55YWxsZXI8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+JyArIGJ1eUNvdW50ICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+QWwgU2lueWFsaTwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjQ1LDE1OCwxMSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS15ZWxsb3cpIj4nICsgd2F0Y2hDb3VudCArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkRpa2thdDwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicgKyBzZWxsQ291bnQgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5TYXQgU2lueWFsaTwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPC9kaXY+PC9kaXY+JzsKCiAgLy8gV2F0Y2hsaXN0IHBlcmZvcm1hbnMKICBpZih3YXRjaC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+RgSBXYXRjaGxpc3Q8L2Rpdj4nOwogICAgd2F0Y2guZm9yRWFjaChmdW5jdGlvbihpdGVtKXsgaCArPSBwZXJmQ2FyZChpdGVtKTsgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgaCArPSAnPC9kaXY+JzsKICBncmlkLmlubmVySFRNTCA9IGg7Cn0KCgpmdW5jdGlvbiByZW5kZXJSdXRpbigpewogIHZhciBncmlkID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dyaWQnKTsKICB2YXIgY2hlY2tlZCA9IGxvYWRDaGVja2VkKCk7CiAgdmFyIHRvZGF5ID0gbmV3IERhdGUoKTsKICB2YXIgaXNXZWVrZW5kID0gdG9kYXkuZ2V0RGF5KCkgPT09IDAgfHwgdG9kYXkuZ2V0RGF5KCkgPT09IDY7CiAgdmFyIGRheU5hbWUgPSBbJ1BhemFyJywnUGF6YXJ0ZXNpJywnU2FsxLEnLCfDh2FyxZ9hbWJhJywnUGVyxZ9lbWJlJywnQ3VtYScsJ0N1bWFydGVzaSddW3RvZGF5LmdldERheSgpXTsKICB2YXIgZGF0ZVN0ciA9IHRvZGF5LnRvTG9jYWxlRGF0ZVN0cmluZygndHItVFInLCB7ZGF5OidudW1lcmljJyxtb250aDonbG9uZycseWVhcjonbnVtZXJpYyd9KTsKCiAgLy8gUHJvZ3Jlc3MgaGVzYXBsYQogIHZhciB0b3RhbEl0ZW1zID0gMDsKICB2YXIgZG9uZUl0ZW1zID0gMDsKICB2YXIgc2VjdGlvbnMgPSBpc1dlZWtlbmQgPyBbJ2hhZnRhbGlrJ10gOiBbJ3NhYmFoJywnb2dsZW4nLCdha3NhbSddOwogIHNlY3Rpb25zLmZvckVhY2goZnVuY3Rpb24oayl7CiAgICBSVVRJTl9JVEVNU1trXS5pdGVtcy5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0pewogICAgICB0b3RhbEl0ZW1zKys7CiAgICAgIGlmKGNoZWNrZWRbaXRlbS5pZF0pIGRvbmVJdGVtcysrOwogICAgfSk7CiAgfSk7CiAgdmFyIHBjdCA9IHRvdGFsSXRlbXMgPiAwID8gTWF0aC5yb3VuZChkb25lSXRlbXMvdG90YWxJdGVtcyoxMDApIDogMDsKICB2YXIgcGN0Q29sID0gcGN0PT09MTAwPyd2YXIoLS1ncmVlbiknOnBjdD49NTA/J3ZhcigtLXllbGxvdyknOid2YXIoLS1tdXRlZCknOwoKICB2YXIgaCA9ICc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwoKICAvLyBIZWFkZXIKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtmbGV4LXdyYXA6d3JhcDtnYXA6MTBweCI+JzsKICBoICs9ICc8ZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KSI+JytkYXlOYW1lKycgUnV0aW5pPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrZGF0ZVN0cisnPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK3BjdENvbCsnIj4nK3BjdCsnJTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK2RvbmVJdGVtcysnLycrdG90YWxJdGVtcysnIHRhbWFtbGFuZMSxPC9kaXY+PC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJoZWlnaHQ6NnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjNweDtvdmVyZmxvdzpoaWRkZW47bWFyZ2luLXRvcDoxMnB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImhlaWdodDoxMDAlO3dpZHRoOicrcGN0KyclO2JhY2tncm91bmQ6JytwY3RDb2wrJztib3JkZXItcmFkaXVzOjNweDt0cmFuc2l0aW9uOndpZHRoIC41cyBlYXNlIj48L2Rpdj48L2Rpdj4nOwogIGlmKHBjdD09PTEwMCkgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXI7bWFyZ2luLXRvcDoxMHB4O2ZvbnQtc2l6ZToxNHB4O2NvbG9yOnZhcigtLWdyZWVuKSI+8J+OiSBUw7xtIG1hZGRlbGVyIHRhbWFtbGFuZMSxITwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gU2VjdGlvbnMKICBzZWN0aW9ucy5mb3JFYWNoKGZ1bmN0aW9uKGspewogICAgdmFyIHNlYyA9IFJVVElOX0lURU1TW2tdOwogICAgdmFyIHNlY0RvbmUgPSBzZWMuaXRlbXMuZmlsdGVyKGZ1bmN0aW9uKGkpe3JldHVybiBjaGVja2VkW2kuaWRdO30pLmxlbmd0aDsKICAgIHZhciBzZWNUb3RhbCA9IHNlYy5pdGVtcy5sZW5ndGg7CiAgICB2YXIgc2VjUGN0ID0gTWF0aC5yb3VuZChzZWNEb25lL3NlY1RvdGFsKjEwMCk7CiAgICB2YXIgc2VjQ29sID0gc2VjUGN0PT09MTAwPyd2YXIoLS1ncmVlbiknOnNlY1BjdD4wPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tbXV0ZWQpJzsKCiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206MTJweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjp2YXIoLS10ZXh0KSI+JytzZWMubGFiZWwrJzwvZGl2Pic7CiAgICBoICs9ICc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6JytzZWNDb2wrJztmb250LXdlaWdodDo2MDAiPicrc2VjRG9uZSsnLycrc2VjVG90YWwrJzwvc3Bhbj48L2Rpdj4nOwoKICAgIHNlYy5pdGVtcy5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0pewogICAgICB2YXIgZG9uZSA9ICEhY2hlY2tlZFtpdGVtLmlkXTsKICAgICAgdmFyIGJnQ29sb3IgPSBkb25lID8gJ3JnYmEoMTYsMTg1LDEyOSwuMDYpJyA6ICdyZ2JhKDI1NSwyNTUsMjU1LC4wMiknOwogICAgICB2YXIgYm9yZGVyQ29sb3IgPSBkb25lID8gJ3JnYmEoMTYsMTg1LDEyOSwuMiknIDogJ3JnYmEoMjU1LDI1NSwyNTUsLjA1KSc7CiAgICAgIHZhciBjaGVja0JvcmRlciA9IGRvbmUgPyAndmFyKC0tZ3JlZW4pJyA6ICd2YXIoLS1tdXRlZCknOwogICAgICB2YXIgY2hlY2tCZyA9IGRvbmUgPyAndmFyKC0tZ3JlZW4pJyA6ICd0cmFuc3BhcmVudCc7CiAgICAgIHZhciB0ZXh0Q29sb3IgPSBkb25lID8gJ3ZhcigtLW11dGVkKScgOiAndmFyKC0tdGV4dCknOwogICAgICB2YXIgdGV4dERlY28gPSBkb25lID8gJ2xpbmUtdGhyb3VnaCcgOiAnbm9uZSc7CiAgICAgIHZhciBjaGVja21hcmsgPSBkb25lID8gJzxzdmcgd2lkdGg9IjEyIiBoZWlnaHQ9IjEyIiB2aWV3Qm94PSIwIDAgMTIgMTIiPjxwb2x5bGluZSBwb2ludHM9IjIsNiA1LDkgMTAsMyIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48L3N2Zz4nIDogJyc7CiAgICAgIGggKz0gJzxkaXYgb25jbGljaz0idG9nZ2xlQ2hlY2soXCcnICsgaXRlbS5pZCArICdcJykiIHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6ZmxleC1zdGFydDtnYXA6MTJweDtwYWRkaW5nOjEwcHg7Ym9yZGVyLXJhZGl1czo4cHg7Y3Vyc29yOnBvaW50ZXI7bWFyZ2luLWJvdHRvbTo2cHg7YmFja2dyb3VuZDonICsgYmdDb2xvciArICc7Ym9yZGVyOjFweCBzb2xpZCAnICsgYm9yZGVyQ29sb3IgKyAnIj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmbGV4LXNocmluazowO3dpZHRoOjIwcHg7aGVpZ2h0OjIwcHg7Ym9yZGVyLXJhZGl1czo1cHg7Ym9yZGVyOjJweCBzb2xpZCAnICsgY2hlY2tCb3JkZXIgKyAnO2JhY2tncm91bmQ6JyArIGNoZWNrQmcgKyAnO2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjttYXJnaW4tdG9wOjFweCI+JyArIGNoZWNrbWFyayArICc8L2Rpdj4nOwogICAgICBoICs9ICc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Y29sb3I6JyArIHRleHRDb2xvciArICc7bGluZS1oZWlnaHQ6MS41O3RleHQtZGVjb3JhdGlvbjonICsgdGV4dERlY28gKyAnIj4nICsgaXRlbS50ZXh0ICsgJzwvc3Bhbj4nOwogICAgICBoICs9ICc8L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0pOwoKICAvLyBIYWZ0YSBpw6dpIG9sZHXEn3VuZGEgaGFmdGFsxLFrIGLDtmzDvG3DvCBkZSBnw7ZzdGVyIChrYXRsYW5hYmlsaXIpCiAgaWYoIWlzV2Vla2VuZCl7CiAgICB2YXIgaFNlYyA9IFJVVElOX0lURU1TWydoYWZ0YWxpayddOwogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA0KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMTUpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y29sb3I6IzYwYTVmYTttYXJnaW4tYm90dG9tOjRweCI+JytoU2VjLmxhYmVsKyc8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5QYXphciBha8WfYW3EsSB5YXDEsWxhY2FrbGFyIOKAlCDFn3UgYW4gZ8O2c3RlcmltIG1vZHVuZGE8L2Rpdj48L2Rpdj4nOwogIH0KCiAgLy8gUmVzZXQgYnV0b251CiAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXI7bWFyZ2luLXRvcDo2cHgiPic7CiAgaCArPSAnPGJ1dHRvbiBvbmNsaWNrPSJyZXNldFJ1dGluKCkiIHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTtwYWRkaW5nOjhweCAxNnB4O2JvcmRlci1yYWRpdXM6OHB4O2ZvbnQtc2l6ZToxMnB4O2N1cnNvcjpwb2ludGVyIj7wn5SEIExpc3RleWkgU8SxZsSxcmxhPC9idXR0b24+JzsKICBoICs9ICc8L2Rpdj4nOwoKICBoICs9ICc8L2Rpdj4nOwogIGdyaWQuaW5uZXJIVE1MID0gaDsKfQoKCmZ1bmN0aW9uIGNsb3NlTShlKXsKICBpZighZXx8ZS50YXJnZXQ9PT1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgib3ZlcmxheSIpKXsKICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJvdmVybGF5IikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpOwogICAgaWYobUNoYXJ0KXttQ2hhcnQuZGVzdHJveSgpO21DaGFydD1udWxsO30KICB9Cn0KCnJlbmRlclN0YXRzKCk7CnJlbmRlckRhc2hib2FyZCgpOwoKCgovLyDilIDilIAgTMSwU1RFIETDnFpFTkxFTUUg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSACnZhciBlZGl0V2F0Y2hsaXN0ID0gW107CnZhciBlZGl0UG9ydGZvbGlvID0gW107CgpmdW5jdGlvbiBvcGVuRWRpdExpc3QoKXsKICBlZGl0V2F0Y2hsaXN0ID0gVEZfREFUQVsnMWQnXS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSkubWFwKGZ1bmN0aW9uKHIpe3JldHVybiByLnRpY2tlcjt9KTsKICBlZGl0UG9ydGZvbGlvID0gUE9SVC5zbGljZSgpOwogIHJlbmRlckVkaXRMaXN0cygpOwogIC8vIExvYWQgc2F2ZWQgdG9rZW4gZnJvbSBsb2NhbFN0b3JhZ2UKICB2YXIgc2F2ZWQgPSBsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgnZ2hfdG9rZW4nKTsKICBpZihzYXZlZCkgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdoVG9rZW5JbnB1dCIpLnZhbHVlID0gc2F2ZWQ7CiAgdmFyIHRzPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0b2tlblNlY3Rpb24iKTsgaWYodHMpIHRzLnN0eWxlLmRpc3BsYXk9Im5vbmUiOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0UG9wdXAiKS5jbGFzc0xpc3QuYWRkKCJvcGVuIik7Cn0KCgpmdW5jdGlvbiB0b2dnbGVUb2tlblNlY3Rpb24oKXsKICB2YXIgcz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidG9rZW5TZWN0aW9uIik7CiAgaWYocykgcy5zdHlsZS5kaXNwbGF5PXMuc3R5bGUuZGlzcGxheT09PSJub25lIj8iYmxvY2siOiJub25lIjsKfQoKZnVuY3Rpb24gc2F2ZVRva2VuKCl7CiAgdmFyIHQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdoVG9rZW5JbnB1dCIpLnZhbHVlLnRyaW0oKTsKICBpZighdCl7YWxlcnQoIlRva2VuIGJvcyEiKTtyZXR1cm47fQogIGxvY2FsU3RvcmFnZS5zZXRJdGVtKCJnaF90b2tlbiIsdCk7CiAgdmFyIHRzPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0b2tlblNlY3Rpb24iKTsgaWYodHMpIHRzLnN0eWxlLmRpc3BsYXk9Im5vbmUiOwogIHNldEVkaXRTdGF0dXMoIuKchSBUb2tlbiBrYXlkZWRpbGRpIiwiZ3JlZW4iKTsKfQoKZnVuY3Rpb24gY2xvc2VFZGl0UG9wdXAoZSl7CiAgaWYoIWV8fGUudGFyZ2V0PT09ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImVkaXRQb3B1cCIpKXsKICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0UG9wdXAiKS5jbGFzc0xpc3QucmVtb3ZlKCJvcGVuIik7CiAgfQp9CgpmdW5jdGlvbiByZW5kZXJFZGl0TGlzdHMoKXsKICB2YXIgd2UgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgid2F0Y2hsaXN0RWRpdG9yIik7CiAgdmFyIHBlID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInBvcnRmb2xpb0VkaXRvciIpOwogIGlmKCF3ZXx8IXBlKSByZXR1cm47CgogIHdlLmlubmVySFRNTCA9IGVkaXRXYXRjaGxpc3QubWFwKGZ1bmN0aW9uKHQsaSl7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47cGFkZGluZzo1cHggOHB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czo1cHg7bWFyZ2luLWJvdHRvbTo0cHgiPicKICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMCI+Jyt0Kyc8L3NwYW4+JwogICAgICArJzxidXR0b24gY2xhc3M9InJtLXdhdGNoLWJ0biIgZGF0YS1pZHg9IicraSsnIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMTUpO2JvcmRlcjpub25lO2NvbG9yOnZhcigtLXJlZDIpO3dpZHRoOjIwcHg7aGVpZ2h0OjIwcHg7Ym9yZGVyLXJhZGl1czo0cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEycHgiPuKclTwvYnV0dG9uPicKICAgICAgKyc8L2Rpdj4nOwogIH0pLmpvaW4oJycpOwoKICAvLyBBZGQgY2xpY2sgaGFuZGxlcnMKICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7CiAgICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCcucm0td2F0Y2gtYnRuJykuZm9yRWFjaChmdW5jdGlvbihidG4pewogICAgICBidG4ub25jbGljaz1mdW5jdGlvbigpe3JlbW92ZVRpY2tlcignd2F0Y2gnLCt0aGlzLmRhdGFzZXQuaWR4KTt9OwogICAgfSk7CiAgICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCcucm0tcG9ydC1idG4nKS5mb3JFYWNoKGZ1bmN0aW9uKGJ0bil7CiAgICAgIGJ0bi5vbmNsaWNrPWZ1bmN0aW9uKCl7cmVtb3ZlVGlja2VyKCdwb3J0JywrdGhpcy5kYXRhc2V0LmlkeCk7fTsKICAgIH0pOwogIH0sMCk7CiAgcGUuaW5uZXJIVE1MID0gZWRpdFBvcnRmb2xpby5tYXAoZnVuY3Rpb24odCxpKXsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtwYWRkaW5nOjVweCA4cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjVweDttYXJnaW4tYm90dG9tOjRweCI+JwogICAgICArJzxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOnZhcigtLWdyZWVuKSI+Jyt0Kyc8L3NwYW4+JwogICAgICArJzxidXR0b24gY2xhc3M9InJtLXBvcnQtYnRuIiBkYXRhLWlkeD0iJytpKyciIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Ym9yZGVyOm5vbmU7Y29sb3I6dmFyKC0tcmVkMik7d2lkdGg6MjBweDtoZWlnaHQ6MjBweDtib3JkZXItcmFkaXVzOjRweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTJweCI+4pyVPC9idXR0b24+JwogICAgICArJzwvZGl2Pic7CiAgfSkuam9pbignJyk7Cn0KCmZ1bmN0aW9uIGFkZFRpY2tlcihsaXN0KXsKICB2YXIgaW5wdXRJZCA9IGxpc3Q9PT0nd2F0Y2gnPyJuZXdXYXRjaFRpY2tlciI6Im5ld1BvcnRUaWNrZXIiOwogIHZhciB2YWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZChpbnB1dElkKS52YWx1ZS50cmltKCkudG9VcHBlckNhc2UoKTsKICBpZighdmFsKSByZXR1cm47CiAgaWYobGlzdD09PSd3YXRjaCcgJiYgIWVkaXRXYXRjaGxpc3QuaW5jbHVkZXModmFsKSkgZWRpdFdhdGNobGlzdC5wdXNoKHZhbCk7CiAgaWYobGlzdD09PSdwb3J0JyAgJiYgIWVkaXRQb3J0Zm9saW8uaW5jbHVkZXModmFsKSkgZWRpdFBvcnRmb2xpby5wdXNoKHZhbCk7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoaW5wdXRJZCkudmFsdWUgPSAiIjsKICByZW5kZXJFZGl0TGlzdHMoKTsKfQoKZnVuY3Rpb24gcmVtb3ZlVGlja2VyKGxpc3QsIGlkeCl7CiAgaWYobGlzdD09PSd3YXRjaCcpIGVkaXRXYXRjaGxpc3Quc3BsaWNlKGlkeCwxKTsKICBlbHNlIGVkaXRQb3J0Zm9saW8uc3BsaWNlKGlkeCwxKTsKICByZW5kZXJFZGl0TGlzdHMoKTsKfQoKZnVuY3Rpb24gc2F2ZUxpc3RUb0dpdGh1YigpewogIHZhciB0b2tlbiA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZS50cmltKCk7CiAgaWYoIXRva2VuKXsgc2V0RWRpdFN0YXR1cygi4p2MIFRva2VuIGdlcmVrbGkg4oCUIGt1dHV5YSBnaXIiLCJyZWQiKTsgcmV0dXJuOyB9CiAgbG9jYWxTdG9yYWdlLnNldEl0ZW0oJ2doX3Rva2VuJywgdG9rZW4pOwoKICB2YXIgY29uZmlnID0geyB3YXRjaGxpc3Q6IGVkaXRXYXRjaGxpc3QsIHBvcnRmb2xpbzogZWRpdFBvcnRmb2xpbyB9OwogIHZhciBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoY29uZmlnLCBudWxsLCAyKTsKICB2YXIgYjY0ID0gYnRvYSh1bmVzY2FwZShlbmNvZGVVUklDb21wb25lbnQoY29udGVudCkpKTsKCiAgc2V0RWRpdFN0YXR1cygi8J+SviBLYXlkZWRpbGl5b3IuLi4iLCJ5ZWxsb3ciKTsKCiAgdmFyIGFwaVVybCA9ICJodHRwczovL2FwaS5naXRodWIuY29tL3JlcG9zL2dodXJ6enovY2Fuc2xpbS9jb250ZW50cy9jb25maWcuanNvbiI7CiAgdmFyIGhlYWRlcnMgPSB7IkF1dGhvcml6YXRpb24iOiJ0b2tlbiAiK3Rva2VuLCJDb250ZW50LVR5cGUiOiJhcHBsaWNhdGlvbi9qc29uIn07CgogIC8vIEZpcnN0IGdldCBjdXJyZW50IFNIQSBpZiBleGlzdHMKICBmZXRjaChhcGlVcmwsIHtoZWFkZXJzOmhlYWRlcnN9KQogICAgLnRoZW4oZnVuY3Rpb24ocil7IHJldHVybiByLm9rID8gci5qc29uKCkgOiBudWxsOyB9KQogICAgLnRoZW4oZnVuY3Rpb24oZXhpc3RpbmcpewogICAgICB2YXIgcGF5bG9hZCA9IHsKICAgICAgICBtZXNzYWdlOiAiTGlzdGUgZ3VuY2VsbGVuZGkgIiArIG5ldyBEYXRlKCkudG9Mb2NhbGVEYXRlU3RyaW5nKCJ0ci1UUiIpLAogICAgICAgIGNvbnRlbnQ6IGI2NAogICAgICB9OwogICAgICBpZihleGlzdGluZyAmJiBleGlzdGluZy5zaGEpIHBheWxvYWQuc2hhID0gZXhpc3Rpbmcuc2hhOwoKICAgICAgcmV0dXJuIGZldGNoKGFwaVVybCwgewogICAgICAgIG1ldGhvZDoiUFVUIiwKICAgICAgICBoZWFkZXJzOmhlYWRlcnMsCiAgICAgICAgYm9keTpKU09OLnN0cmluZ2lmeShwYXlsb2FkKQogICAgICB9KTsKICAgIH0pCiAgICAudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYoci5vayB8fCByLnN0YXR1cz09PTIwMSl7CiAgICAgICAgc2V0RWRpdFN0YXR1cygi4pyFIEtheWRlZGlsZGkhIEJpciBzb25yYWtpIENvbGFiIMOnYWzEscWfdMSxcm1hc8SxbmRhIGFrdGlmIG9sdXIuIiwiZ3JlZW4iKTsKICAgICAgICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7Y2xvc2VFZGl0UG9wdXAoKTt9LDIwMDApOwogICAgICB9IGVsc2UgewogICAgICAgIHNldEVkaXRTdGF0dXMoIuKdjCBIYXRhOiAiK3Iuc3RhdHVzKyIg4oCUIFRva2VuxLEga29udHJvbCBldCIsInJlZCIpOwogICAgICB9CiAgICB9KQogICAgLmNhdGNoKGZ1bmN0aW9uKGUpeyBzZXRFZGl0U3RhdHVzKCLinYwgSGF0YTogIitlLm1lc3NhZ2UsInJlZCIpOyB9KTsKfQoKZnVuY3Rpb24gc2V0RWRpdFN0YXR1cyhtc2csIGNvbG9yKXsKICB2YXIgZWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFN0YXR1cyIpOwogIGlmKGVsKXsKICAgIGVsLnRleHRDb250ZW50ID0gbXNnOwogICAgZWwuc3R5bGUuY29sb3IgPSBjb2xvcj09PSJncmVlbiI/InZhcigtLWdyZWVuKSI6Y29sb3I9PT0icmVkIj8idmFyKC0tcmVkMikiOiJ2YXIoLS15ZWxsb3cpIjsKICB9Cn0KCgpmdW5jdGlvbiByZW5kZXJIYWZ0YWxpaygpewogIHZhciBncmlkID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dyaWQnKTsKICB2YXIgd2QgPSBXRUVLTFlfREFUQSB8fCB7fTsKICB2YXIgcG9ydCA9IHdkLnBvcnRmb2xpbyB8fCBbXTsKICB2YXIgd2F0Y2ggPSB3ZC53YXRjaGxpc3QgfHwgW107CiAgdmFyIGJlc3QgPSB3ZC5iZXN0OwogIHZhciB3b3JzdCA9IHdkLndvcnN0OwogIHZhciBtZCA9IE1BUktFVF9EQVRBIHx8IHt9OwogIHZhciBzcCA9IG1kLlNQNTAwIHx8IHt9OwogIHZhciBuYXMgPSBtZC5OQVNEQVEgfHwge307CiAgdmFyIGRhdGExZCA9IFRGX0RBVEFbJzFkJ10gfHwgW107CiAgdmFyIGRhdGExdyA9IFRGX0RBVEFbJzF3ayddIHx8IFtdOwoKICBmdW5jdGlvbiBjYyh2KXsgcmV0dXJuIHY+PTA/J3ZhcigtLWdyZWVuMiknOid2YXIoLS1yZWQyKSc7IH0KICBmdW5jdGlvbiBjcyh2KXsgcmV0dXJuICh2Pj0wPycrJzonJykrdisnJSc7IH0KCiAgZnVuY3Rpb24gcGVyZlJvdyhpdGVtKXsKICAgIHZhciBjb2wgPSBjYyhpdGVtLndlZWtfY2hnKTsKICAgIHZhciBwYiA9IGl0ZW0ucG9ydGZvbGlvID8gJzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWxlZnQ6NHB4Ij5QPC9zcGFuPicgOiAnJzsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCI+JwogICAgICArICc8ZGl2IHN0eWxlPSJmb250LXdlaWdodDo3MDA7Zm9udC1zaXplOjE0cHg7bGV0dGVyLXNwYWNpbmc6MXB4Ij4nICsgaXRlbS50aWNrZXIgKyBwYiArICc8L2Rpdj4nCiAgICAgICsgJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPicKICAgICAgKyAnPGRpdiBzdHlsZT0iZm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyBjb2wgKyAnIj4nICsgY3MoaXRlbS53ZWVrX2NoZykgKyAnPC9kaXY+JwogICAgICArICc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+T25jZWtpOiAnICsgY3MoaXRlbS5wcmV2X3dlZWtfY2hnKSArICc8L2Rpdj4nCiAgICAgICsgJzwvZGl2PjwvZGl2Pic7CiAgfQoKICB2YXIgcG9ydEF2ZyA9IHBvcnQubGVuZ3RoID8gTWF0aC5yb3VuZChwb3J0LnJlZHVjZShmdW5jdGlvbihhLGIpe3JldHVybiBhK2Iud2Vla19jaGc7fSwwKS9wb3J0Lmxlbmd0aCoxMDApLzEwMCA6IDA7CiAgdmFyIHNwQ2hnID0gc3AuY2hhbmdlIHx8IDA7CiAgdmFyIG5hc0NoZyA9IG5hcy5jaGFuZ2UgfHwgMDsKICB2YXIgYWxwaGEgPSBNYXRoLnJvdW5kKChwb3J0QXZnLXNwQ2hnKSoxMDApLzEwMDsKICB2YXIgYWxwaGFDb2wgPSBhbHBoYT49MD8ndmFyKC0tZ3JlZW4pJzondmFyKC0tcmVkMiknOwoKICB2YXIgaCA9ICc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwoKICAvLyBIZWFkZXIKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1ib3R0b206NHB4Ij7wn5OIIEhhZnRhbMSxayBQZXJmb3JtYW5zIMOWemV0aTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nICsgKHdkLmdlbmVyYXRlZHx8JycpICsgJzwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gUGl5YXNhIHZzIFBvcnRmb2x5bwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMTMwcHgsMWZyKSk7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIFsKICAgIHtsYWJlbDonUG9ydGbDtnkgT3J0LicsIHZhbDpwb3J0QXZnfSwKICAgIHtsYWJlbDonUyZQIDUwMCcsIHZhbDpzcENoZ30sCiAgICB7bGFiZWw6J05BU0RBUScsIHZhbDpuYXNDaGd9LAogIF0uZm9yRWFjaChmdW5jdGlvbih4KXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+JyArIHgubGFiZWwgKyAnPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgY2MoeC52YWwpICsgJyI+JyArIGNzKHgudmFsKSArICc8L2Rpdj48L2Rpdj4nOwogIH0pOwogIHZhciBhQmcgPSBhbHBoYT49MD8ncmdiYSgxNiwxODUsMTI5LC4wOCknOidyZ2JhKDIzOSw2OCw2OCwuMDgpJzsKICB2YXIgYUJkID0gYWxwaGE+PTA/J3JnYmEoMTYsMTg1LDEyOSwuMjUpJzoncmdiYSgyMzksNjgsNjgsLjI1KSc7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonICsgYUJnICsgJztib3JkZXI6MXB4IHNvbGlkICcgKyBhQmQgKyAnO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5BbHBoYSAodnMgUyZQKTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyBhbHBoYUNvbCArICciPicgKyBjcyhhbHBoYSkgKyAnPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBFbiBpeWkgLyBlbiBrb3R1CiAgaWYoYmVzdHx8d29yc3QpewogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnIgMWZyO2dhcDoxMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICAgIGlmKGJlc3QpewogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4Ij4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1ncmVlbik7bWFyZ2luLWJvdHRvbTo2cHgiPvCfj4YgRW4gxLB5aTwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtsZXR0ZXItc3BhY2luZzoycHgiPicgKyBiZXN0LnRpY2tlciArICc8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4rJyArIGJlc3Qud2Vla19jaGcgKyAnJTwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBpZih3b3JzdCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4Ij4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1yZWQyKTttYXJnaW4tYm90dG9tOjZweCI+8J+TiSBFbiBLw7Z0w7w8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgd29yc3QudGlja2VyICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1yZWQyKSI+JyArIHdvcnN0LndlZWtfY2hnICsgJyU8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFNpbnlhbGxlcgogIHZhciBidXlDICA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J0dVQ0xVIEFMJ3x8ci5zaW55YWw9PT0nQUwnO30pLmxlbmd0aDsKICB2YXIgd2FybkMgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdESUtLQVQnO30pLmxlbmd0aDsKICB2YXIgc2VsbEMgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdTQVQnO30pLmxlbmd0aDsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+TiiBTaW55YWxsZXI8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+JyArIGJ1eUMgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5BbDwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjQ1LDE1OCwxMSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS15ZWxsb3cpIj4nICsgd2FybkMgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5EaWtrYXQ8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nICsgc2VsbEMgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5TYXQ8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzwvZGl2PjwvZGl2Pic7CgogIC8vIDFHKzFIIG1vbWVudHVtCiAgdmFyIGJvdGhCdXkgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpewogICAgaWYoci5oYXRhKSByZXR1cm4gZmFsc2U7CiAgICB2YXIgdyA9IGRhdGExdy5maW5kKGZ1bmN0aW9uKHgpe3JldHVybiB4LnRpY2tlcj09PXIudGlja2VyO30pOwogICAgcmV0dXJuIChyLnNpbnlhbD09PSdHVUNMVSBBTCd8fHIuc2lueWFsPT09J0FMJykgJiYgdyAmJiAody5zaW55YWw9PT0nR1VDTFUgQUwnfHx3LnNpbnlhbD09PSdBTCcpOwogIH0pOwogIGlmKGJvdGhCdXkubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tZ3JlZW4pO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7imqEgMUcgKyAxSCBBbCBTaW55YWxpPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtmbGV4LXdyYXA6d3JhcDtnYXA6OHB4IiBpZD0iYm90aEJ1eUNvbnRhaW5lciI+PC9kaXY+PC9kaXY+JzsKICB9CgogIC8vIFRvcCAzIGVudHJ5IHNjb3JlCiAgdmFyIHRvcEVudHJ5ID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KS5zb3J0KGZ1bmN0aW9uKGEsYil7cmV0dXJuIGIuZW50cnlfc2NvcmUtYS5lbnRyeV9zY29yZTt9KS5zbGljZSgwLDMpOwogIGlmKHRvcEVudHJ5Lmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn46vIEVuIMSweWkgR2lyacWfIEthbGl0ZXNpPC9kaXY+JzsKICAgIHZhciBtZWRhbHMgPSBbJ/CfpYcnLCfwn6WIJywn8J+liSddOwogICAgdG9wRW50cnkuZm9yRWFjaChmdW5jdGlvbihyLGkpewogICAgICB2YXIgZXNjb2wgPSByLmVudHJ5X3Njb3JlPj03NT8ndmFyKC0tZ3JlZW4pJzpyLmVudHJ5X3Njb3JlPj02MD8ndmFyKC0tZ3JlZW4yKSc6J3ZhcigtLXllbGxvdyknOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO3BhZGRpbmc6OHB4IDEycHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6OHB4O21hcmdpbi1ib3R0b206NXB4IiBpZD0idGUtJyArIHIudGlja2VyICsgJyI+JzsKICAgICAgaCArPSAnPHNwYW4+JyArIG1lZGFsc1tpXSArICcgPHN0cm9uZz4nICsgci50aWNrZXIgKyAnPC9zdHJvbmc+IDxzcGFuIHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicgKyByLnNpbnlhbCArICc8L3NwYW4+PC9zcGFuPic7CiAgICAgIGggKz0gJzxzcGFuIHN0eWxlPSJmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGVzY29sICsgJyI+JyArIHIuZW50cnlfc2NvcmUgKyAnLzEwMDwvc3Bhbj48L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gU3RvcCB5YWtpbgogIHZhciBuZWFyU3RvcCA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7CiAgICBpZihyLmhhdGF8fCFQT1JULmluY2x1ZGVzKHIudGlja2VyKXx8IXIuc3RvcCkgcmV0dXJuIGZhbHNlOwogICAgcmV0dXJuIChyLmZpeWF0LXIuc3RvcCkvci5maXlhdCoxMDAgPCA4OwogIH0pLnNvcnQoZnVuY3Rpb24oYSxiKXtyZXR1cm4gKGEuZml5YXQtYS5zdG9wKS9hLmZpeWF0LShiLmZpeWF0LWIuc3RvcCkvYi5maXlhdDt9KTsKICBpZihuZWFyU3RvcC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tcmVkMik7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPuKaoO+4jyBTdG9wIFNldml5ZXNpbmUgWWFrxLFuPC9kaXY+JzsKICAgIG5lYXJTdG9wLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICAgIHZhciBkaXN0ID0gTWF0aC5yb3VuZCgoci5maXlhdC1yLnN0b3ApL3IuZml5YXQqMTAwMCkvMTA7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7cGFkZGluZzo4cHggMTJweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo4cHg7bWFyZ2luLWJvdHRvbTo1cHgiIGlkPSJucy0nICsgci50aWNrZXIgKyAnIj4nOwogICAgICBoICs9ICc8c3Ryb25nPicgKyByLnRpY2tlciArICc8L3N0cm9uZz4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij48ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS1yZWQyKTtmb250LXdlaWdodDo2MDAiPlN0b3AgJCcgKyByLnN0b3AgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5VemFrbMSxazogJScgKyBkaXN0ICsgJzwvZGl2PjwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBIZWRlZmUgeWFraW4KICB2YXIgbmVhclRhcmdldCA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7CiAgICBpZihyLmhhdGF8fCFQT1JULmluY2x1ZGVzKHIudGlja2VyKXx8IXIuaGVkZWYpIHJldHVybiBmYWxzZTsKICAgIHJldHVybiAoci5oZWRlZi1yLmZpeWF0KS9yLmZpeWF0KjEwMCA8IDE1OwogIH0pLnNvcnQoZnVuY3Rpb24oYSxiKXtyZXR1cm4gKGEuaGVkZWYtYS5maXlhdCkvYS5maXlhdC0oYi5oZWRlZi1iLmZpeWF0KS9iLmZpeWF0O30pOwogIGlmKG5lYXJUYXJnZXQubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6IzYwYTVmYTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+OryBIZWRlZmUgWWFrxLFuPC9kaXY+JzsKICAgIG5lYXJUYXJnZXQuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgICAgdmFyIGRpc3QgPSBNYXRoLnJvdW5kKChyLmhlZGVmLXIuZml5YXQpL3IuZml5YXQqMTAwMCkvMTA7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7cGFkZGluZzo4cHggMTJweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo4cHg7bWFyZ2luLWJvdHRvbTo1cHgiPic7CiAgICAgIGggKz0gJzxzdHJvbmc+JyArIHIudGlja2VyICsgJzwvc3Ryb25nPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOiM2MGE1ZmE7Zm9udC13ZWlnaHQ6NjAwIj5IZWRlZiAkJyArIHIuaGVkZWYgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5LYWxkaTogJScgKyBkaXN0ICsgJzwvZGl2PjwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBFYXJuaW5ncwogIHZhciB1cmdlbnRFID0gRUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuIGUuZGF5c190b19lYXJuaW5ncyE9bnVsbCYmZS5kYXlzX3RvX2Vhcm5pbmdzPD0xNDt9KS5zb3J0KGZ1bmN0aW9uKGEsYil7cmV0dXJuIGEuZGF5c190b19lYXJuaW5ncy1iLmRheXNfdG9fZWFybmluZ3M7fSk7CiAgaWYodXJnZW50RS5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjQ1LDE1OCwxMSwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS15ZWxsb3cpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5OFIFlha2xhxZ9hbiBSYXBvcmxhcjwvZGl2Pic7CiAgICB1cmdlbnRFLmZvckVhY2goZnVuY3Rpb24oZSl7CiAgICAgIHZhciBpYyA9IGUuYWxlcnQ9PT0ncmVkJz8n8J+UtCc6J/Cfn6EnOwogICAgICB2YXIgaW5Qb3J0ID0gUE9SVC5pbmNsdWRlcyhlLnRpY2tlcik7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7cGFkZGluZzo4cHggMTJweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo4cHg7bWFyZ2luLWJvdHRvbTo1cHgiPic7CiAgICAgIGggKz0gJzxzcGFuPicgKyBpYyArICcgPHN0cm9uZz4nICsgZS50aWNrZXIgKyAnPC9zdHJvbmc+JyArIChpblBvcnQ/JyA8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZToxMHB4Ij5QPC9zcGFuPic6JycpICsgJzwvc3Bhbj4nOwogICAgICBoICs9ICc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtc2l6ZToxMXB4Ij4nICsgZS5uZXh0X2RhdGUgKyAnICgnICsgZS5kYXlzX3RvX2Vhcm5pbmdzICsgJyBnw7xuKTwvc3Bhbj48L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gVklYCiAgdmFyIHZpeCA9IG1kLlZJWCB8fCB7fTsKICBpZih2aXgucHJpY2UpewogICAgdmFyIHZDb2wgPSB2aXgucHJpY2U+MzA/J3ZhcigtLXJlZDIpJzp2aXgucHJpY2U+MjA/J3ZhcigtLXllbGxvdyknOid2YXIoLS1ncmVlbiknOwogICAgdmFyIHZMYmwgPSB2aXgucHJpY2U+MzA/J1nDvGtzZWsgS29ya3Ug4oCUIFllbmkgcG96aXN5b24gYcOnbWEnOnZpeC5wcmljZT4yMD8nT3J0YSBWb2xhdGlsaXRlIOKAlCBEaWtrYXRsaSBvbCc6J0TDvMWfw7xrIFZvbGF0aWxpdGUg4oCUIE5vcm1hbCBrb8WfdWxsYXInOwogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNHB4IDE2cHg7bWFyZ2luLWJvdHRvbToxMHB4O2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXIiPic7CiAgICBoICs9ICc8ZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjJweCI+VklYPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6JyArIHZDb2wgKyAnIj4nICsgdkxibCArICc8L2Rpdj48L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjI4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyB2Q29sICsgJyI+JyArIHZpeC5wcmljZSArICc8L2Rpdj48L2Rpdj4nOwogIH0KCiAgLy8gUG9ydGZvbHlvIGRldGF5CiAgaWYocG9ydC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+SvCBQb3J0ZsO2eTwvZGl2Pic7CiAgICBwb3J0LmZvckVhY2goZnVuY3Rpb24oaXRlbSl7aCArPSBwZXJmUm93KGl0ZW0pO30pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFdhdGNobGlzdAogIGlmKHdhdGNoLmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5GBIFdhdGNobGlzdDwvZGl2Pic7CiAgICB3YXRjaC5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0pe2ggKz0gcGVyZlJvdyhpdGVtKTt9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICBoICs9ICc8L2Rpdj4nOwogIGdyaWQuaW5uZXJIVE1MID0gaDsKCiAgLy8gQWRkIG9uY2xpY2sgdmlhIEpTIChhdm9pZHMgcXVvdGUgbmVzdGluZyBpc3N1ZXMpCiAgYm90aEJ1eS5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgdmFyIGNudCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdib3RoQnV5Q29udGFpbmVyJyk7CiAgICBpZighY250KSByZXR1cm47CiAgICB2YXIgZCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgZC5zdHlsZS5jc3NUZXh0ID0gJ2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzo4cHggMTRweDtjdXJzb3I6cG9pbnRlcic7CiAgICBkLmlubmVySFRNTCA9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6MnB4O2NvbG9yOnZhcigtLWdyZWVuKSI+JyArIHIudGlja2VyICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+R2lyaXM6ICcgKyByLmVudHJ5X3Njb3JlICsgJy8xMDA8L2Rpdj4nOwogICAgZC5vbmNsaWNrID0gKGZ1bmN0aW9uKHQpe3JldHVybiBmdW5jdGlvbigpe29wZW5NKHQpO307fSkoci50aWNrZXIpOwogICAgY250LmFwcGVuZENoaWxkKGQpOwogIH0pOwogIHRvcEVudHJ5LmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgZWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgndGUtJyArIHIudGlja2VyKTsKICAgIGlmKGVsKSBlbC5vbmNsaWNrID0gKGZ1bmN0aW9uKHQpe3JldHVybiBmdW5jdGlvbigpe29wZW5NKHQpO307fSkoci50aWNrZXIpLCBlbC5zdHlsZS5jdXJzb3I9J3BvaW50ZXInOwogIH0pOwogIG5lYXJTdG9wLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgZWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnbnMtJyArIHIudGlja2VyKTsKICAgIGlmKGVsKSBlbC5vbmNsaWNrID0gKGZ1bmN0aW9uKHQpe3JldHVybiBmdW5jdGlvbigpe29wZW5NKHQpO307fSkoci50aWNrZXIpLCBlbC5zdHlsZS5jdXJzb3I9J3BvaW50ZXInOwogIH0pOwp9CgoKZnVuY3Rpb24gcmVuZGVyU2NyZWVuZXIoKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgdmFyIGRhdGEgPSBTQ1JFRU5FUl9EQVRBIHx8IFtdOwogIHZhciBjcml0ZXJpYSA9IFsKICAgIHtpZDonZXBzX3FvcScsICAgIGxhYmVsOidFUFMgUW9RIELDvHnDvG1lJywgICAgIGxpbWl0Oic+PTIwJScsICAgIHc6MywgaW1wOidjcml0aWNhbCd9LAogICAge2lkOidzbWEyMDAnLCAgICAgbGFiZWw6J1NNQTIwMCDDnHplcmluZGUnLCAgICAgbGltaXQ6J1A+U01BMjAwJywgdzozLCBpbXA6J2NyaXRpY2FsJ30sCiAgICB7aWQ6J21hcmtldCcsICAgICBsYWJlbDonTSBLcml0ZXJpJywgICAgICAgICAgIGxpbWl0OidHw7zDp2zDvCcsICAgIHc6MywgaW1wOidjcml0aWNhbCd9LAogICAge2lkOidlcHNfYWNjZWwnLCAgbGFiZWw6J0VQUyBIxLF6bGFubWFzxLEnLCAgICAgIGxpbWl0OidIxLF6bGFuxLF5b3InLHc6MiwgaW1wOidpbXBvcnRhbnQnfSwKICAgIHtpZDoncnNfcmF0aW5nJywgIGxhYmVsOidSUyBSYXRpbmcnLCAgICAgICAgICAgbGltaXQ6Jz49NzAnLCAgICAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOidyZXZfZ3Jvd3RoJywgbGFiZWw6J0dlbGlyIELDvHnDvG1lc2knLCAgICAgIGxpbWl0Oic+PTE1JScsICAgIHc6MiwgaW1wOidpbXBvcnRhbnQnfSwKICAgIHtpZDoncm9lJywgICAgICAgIGxhYmVsOidST0UnLCAgICAgICAgICAgICAgICAgbGltaXQ6Jz49MTUlJywgICAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOidncm9zc19tZycsICAgbGFiZWw6J0Jyw7x0IE1hcmppbicsICAgICAgICAgbGltaXQ6Jz49NDAlJywgICAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOidzbWE1MCcsICAgICAgbGFiZWw6J1NNQTUwIMOcemVyaW5kZScsICAgICAgbGltaXQ6J1A+U01BNTAnLCAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOic1MncnLCAgICAgICAgbGFiZWw6JzUySCBZYWvEsW5sxLFrJywgICAgICAgIGxpbWl0Oic+PTc1JScsICAgIHc6MiwgaW1wOidpbXBvcnRhbnQnfSwKICAgIHtpZDonbmV0X21nJywgICAgIGxhYmVsOidOZXQgTWFyamluJywgICAgICAgICAgbGltaXQ6Jz49MTAlJywgICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDonZGUnLCAgICAgICAgIGxhYmVsOidCb3LDpy/DlnprYXluYWsnLCAgICAgICBsaW1pdDonPD0xLjAnLCAgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidjcicsICAgICAgICAgbGFiZWw6J0N1cnJlbnQgUmF0aW8nLCAgICAgICBsaW1pdDonPj0xLjUnLCAgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidwZScsICAgICAgICAgbGFiZWw6J1AvRScsICAgICAgICAgICAgICAgICBsaW1pdDonPD02MCcsICAgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidta3RjYXAnLCAgICAgbGFiZWw6J1BpeWFzYSBEZcSfZXJpJywgICAgICAgbGltaXQ6Jz49MUInLCAgICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDoncmVsX3ZvbCcsICAgIGxhYmVsOidHw7ZyZWNlbGkgSGFjaW0nLCAgICAgIGxpbWl0Oic+PTAuOHgnLCAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J2F2Z192b2wnLCAgICBsYWJlbDonT3J0LiBIYWNpbScsICAgICAgICAgIGxpbWl0Oic+PTUwMEsnLCAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J2luc3Rfb3duJywgICBsYWJlbDonS3VydW1zYWwgU2FoaXBsaWsnLCAgIGxpbWl0Oic+PTQwJScsICAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J2luc3RfdHJlbmQnLCBsYWJlbDonS3VydW1zYWwgVHJlbmQnLCAgICAgIGxpbWl0OidBcnTEsXlvcicsICB3OjEsIGltcDonc3VwcG9ydCd9LAogIF07CiAgdmFyIE1BWF9XID0gMzU7CgogIGlmKCFkYXRhLmxlbmd0aCl7CiAgICBncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMTt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjQwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5TY3JlZW5lciB2ZXJpc2kgeW9rIOKAlCBBY3Rpb25zIFJ1biBXb3JrZmxvdzwvZGl2Pic7CiAgICByZXR1cm47CiAgfQoKICB2YXIgcGFzc2VkID0gZGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIucGFzc2VkO30pOwogIHZhciBmYWlsZWQgPSBkYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIucGFzc2VkO30pOwogIHZhciBbZXhwYW5kZWRUaWNrZXIsIHNldEV4cGFuZGVkXSA9IFtudWxsLCBudWxsXTsKCiAgZnVuY3Rpb24gaW1wQ29sb3IoaW1wKXsKICAgIHJldHVybiBpbXA9PT0nY3JpdGljYWwnPyd2YXIoLS1yZWQyKSc6aW1wPT09J2ltcG9ydGFudCc/J3ZhcigtLXllbGxvdyknOid2YXIoLS1tdXRlZCknOwogIH0KICBmdW5jdGlvbiBpbXBMYWJlbChpbXApewogICAgcmV0dXJuIGltcD09PSdjcml0aWNhbCc/J/CflLQgWk9SVU5MVSc6aW1wPT09J2ltcG9ydGFudCc/J/Cfn6Egw5ZORU1MxLAnOifwn5S1IERFU1RFSyc7CiAgfQoKICBmdW5jdGlvbiBjcml0ZXJpYURldGFpbChyKXsKICAgIHZhciBoID0gJzxkaXYgc3R5bGU9InBhZGRpbmc6MTJweCAxNHB4O2JvcmRlci10b3A6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA2KTtiYWNrZ3JvdW5kOnZhcigtLWJnMykiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij5LUsSwVEVSIERFVEFZSSDigJQgQcSfxLFybMSxa2zEsSBTa29yOiAnK3Iud2VpZ2h0ZWRfc2NvcmUrJy8nK3IubWF4X3dlaWdodGVkKycgKCUnK3IucGN0KycpPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyIDFmcjtnYXA6NHB4Ij4nOwogICAgY3JpdGVyaWEuZm9yRWFjaChmdW5jdGlvbihjKXsKICAgICAgdmFyIGNyID0gci5jcml0ZXJpYSAmJiByLmNyaXRlcmlhW2MuaWRdOwogICAgICBpZighY3IpIHJldHVybjsKICAgICAgdmFyIG5vRGF0YSA9IGNyLmhhc19kYXRhID09PSBmYWxzZTsKICAgICAgdmFyIGNvbCA9IG5vRGF0YSA/ICd2YXIoLS1tdXRlZCknIDogY3IucGFzc2VkID8gJ3ZhcigtLWdyZWVuKScgOiBpbXBDb2xvcihjLmltcCk7CiAgICAgIHZhciBiZyA9IG5vRGF0YSA/ICdyZ2JhKDI1NSwyNTUsMjU1LC4wMiknIDogY3IucGFzc2VkID8gJ3JnYmEoMTYsMTg1LDEyOSwuMDYpJyA6IChjLmltcD09PSdjcml0aWNhbCc/J3JnYmEoMjM5LDY4LDY4LC4wOCknOmMuaW1wPT09J2ltcG9ydGFudCc/J3JnYmEoMjQ1LDE1OCwxMSwuMDYpJzoncmdiYSgyNTUsMjU1LDI1NSwuMDIpJyk7CiAgICAgIHZhciBiZCA9IG5vRGF0YSA/ICdyZ2JhKDI1NSwyNTUsMjU1LC4wNSknIDogY3IucGFzc2VkID8gJ3JnYmEoMTYsMTg1LDEyOSwuMiknIDogKGMuaW1wPT09J2NyaXRpY2FsJz8ncmdiYSgyMzksNjgsNjgsLjIpJzpjLmltcD09PSdpbXBvcnRhbnQnPydyZ2JhKDI0NSwxNTgsMTEsLjIpJzoncmdiYSgyNTUsMjU1LDI1NSwuMDUpJyk7CiAgICAgIHZhciBpY29uID0gbm9EYXRhID8gJ+KsnCcgOiBjci5wYXNzZWQgPyAn4pyFJyA6ICfinYwnOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicrYmcrJztib3JkZXI6MXB4IHNvbGlkICcrYmQrJztib3JkZXItcmFkaXVzOjVweDtwYWRkaW5nOjVweCA4cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXIiPic7CiAgICAgIGggKz0gJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrY29sKyciPicraWNvbisnICcrYy5sYWJlbCsnPC9zcGFuPic7CiAgICAgIGggKz0gJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytpbXBMYWJlbChjLmltcCkuc3BsaXQoJyAnKVswXSsnPC9zcGFuPjwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjonKyhub0RhdGE/J3ZhcigtLW11dGVkKSc6Y3IucGFzc2VkPyd2YXIoLS10ZXh0KSc6Y29sKSsnIj4nK2NyLnZhbCsnIDxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtmb250LXdlaWdodDo0MDAiPicrKCFub0RhdGE/J2xpbWl0OiAnOicnKStjLmxpbWl0Kyc8L3NwYW4+PC9kaXY+JzsKICAgICAgaCArPSAnPC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+PC9kaXY+JzsKICAgIHJldHVybiBoOwogIH0KCiAgZnVuY3Rpb24gc3RvY2tSb3cociwgZXhwYW5kZWQpewogICAgdmFyIHBjdCA9IHIucGN0OwogICAgdmFyIGNvbCA9IHBjdD49ODA/J3ZhcigtLWdyZWVuKSc6cGN0Pj02MD8ndmFyKC0tZ3JlZW4yKSc6cGN0Pj00MD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLXJlZDIpJzsKICAgIHZhciBwYiA9IHIuaW5fcG9ydGZvbGlvPyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1sZWZ0OjRweCI+UDwvc3Bhbj4nOicnOwogICAgdmFyIHdiID0gci5pbl93YXRjaGxpc3Q/JzxzcGFuIHN0eWxlPSJjb2xvcjojNjBhNWZhO2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1sZWZ0OjRweCI+Vzwvc3Bhbj4nOicnOwogICAgdmFyIGNoZ0NvbCA9IHIuY2hhbmdlPj0wPyd2YXIoLS1ncmVlbjIpJzondmFyKC0tcmVkMiknOwogICAgdmFyIGNyaXRGYWlsID0gY3JpdGVyaWEuZmlsdGVyKGZ1bmN0aW9uKGMpe3JldHVybiByLmNyaXRlcmlhJiZyLmNyaXRlcmlhW2MuaWRdJiYhci5jcml0ZXJpYVtjLmlkXS5wYXNzZWQmJmMuaW1wPT09J2NyaXRpY2FsJzt9KTsKICAgIHZhciB3YXJuVGFncyA9IGNyaXRGYWlsLm1hcChmdW5jdGlvbihjKXsKICAgICAgcmV0dXJuICc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMSk7Y29sb3I6dmFyKC0tcmVkMik7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7bWFyZ2luLXJpZ2h0OjNweCI+4p2MJytjLmxhYmVsKyc8L3NwYW4+JzsKICAgIH0pLmpvaW4oJycpOwogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJib3JkZXItYm90dG9tOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNCkiIGlkPSJzYy1yb3ctJytyLnRpY2tlcisnIj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoxMzBweCAxZnIgODBweCA4MHB4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6MTBweDtwYWRkaW5nOjEwcHggMTRweDtjdXJzb3I6cG9pbnRlciIgaWQ9InNjLScrci50aWNrZXIrJyI+JwogICAgICArJzxkaXY+PGRpdiBzdHlsZT0iZm9udC13ZWlnaHQ6NzAwO2ZvbnQtc2l6ZToxNHB4O2xldHRlci1zcGFjaW5nOjFweCI+JytyLnRpY2tlcitwYit3YisnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK3IubmFtZS5zdWJzdHJpbmcoMCwxOCkrJzwvZGl2PjwvZGl2PicKICAgICAgKyc8ZGl2PjxkaXYgc3R5bGU9ImhlaWdodDo0cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6MnB4O292ZXJmbG93OmhpZGRlbiI+JwogICAgICArJzxkaXYgc3R5bGU9ImhlaWdodDoxMDAlO3dpZHRoOicrcGN0KyclO2JhY2tncm91bmQ6Jytjb2wrJztib3JkZXItcmFkaXVzOjJweCI+PC9kaXY+PC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjRweDttYXJnaW4tdG9wOjNweCI+Jyt3YXJuVGFncwogICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytyLnNjb3JlKycvMTk8L3NwYW4+JwogICAgICArJzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMTUpO2NvbG9yOiM2MGE1ZmE7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwIj5SUzonK3IucnNfcmF0aW5nKyc8L3NwYW4+JwogICAgICArJzwvZGl2PjwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij48ZGl2IHN0eWxlPSJmb250LXdlaWdodDo3MDA7Y29sb3I6Jytjb2wrJztmb250LXNpemU6MTVweCI+JytwY3QrJyU8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPmHEn8SxcmzEsWtsxLE8L2Rpdj48L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+PGRpdiBzdHlsZT0iZm9udC13ZWlnaHQ6NjAwIj4kJytyLnByaWNlKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6JytjaGdDb2wrJyI+Jysoci5jaGFuZ2U+PTA/JysnOicnKStyLmNoYW5nZSsnJTwvZGl2PjwvZGl2PicKICAgICAgKyc8L2Rpdj4nCiAgICAgICsoZXhwYW5kZWQgPyBjcml0ZXJpYURldGFpbChyKSA6ICcnKQogICAgICArJzwvZGl2Pic7CiAgfQoKICBmdW5jdGlvbiBidWlsZEhUTUwoKXsKICAgIHZhciBoID0gJzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CgogICAgLy8gU3VtbWFyeQogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1ib3R0b206NHB4Ij7wn5SNIENBTlNMSU0gU2NyZWVuZXI8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MTJweCI+MTYga3JpdGVyIMK3IDMgw7ZuZW0gc2V2aXllc2kgwrcgJytkYXRhLmxlbmd0aCsnIGhpc3NlIHRhcmFuZMSxPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcDttYXJnaW4tYm90dG9tOjEycHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+JytwYXNzZWQubGVuZ3RoKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkdlw6d0aTwvZGl2PjwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1yZWQyKSI+JytmYWlsZWQubGVuZ3RoKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkdlw6dlbWVkaTwvZGl2PjwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOiM2MGE1ZmEiPicrZGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuaW5fd2F0Y2hsaXN0fHxyLmluX3BvcnRmb2xpbzt9KS5sZW5ndGgrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+TGlzdGVtZGU8L2Rpdj48L2Rpdj4nOwogICAgaCArPSAnPC9kaXY+JzsKICAgIC8vIExlZ2VuZAogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2ZsZXgtd3JhcDp3cmFwO2ZvbnQtc2l6ZToxMHB4Ij4nOwogICAgaCArPSAnPHNwYW4+8J+UtCA8c3Ryb25nPlpvcnVubHU8L3N0cm9uZz4gKDN4KTogRVBTIFFvUSwgU01BMjAwLCBNIEtyaXRlcmk8L3NwYW4+JzsKICAgIGggKz0gJzxzcGFuPvCfn6EgPHN0cm9uZz7Dlm5lbWxpPC9zdHJvbmc+ICgyeCk6IEdlbGlyLCBST0UsIE1hcmppbiwgU01BNTAsIDUySDwvc3Bhbj4nOwogICAgaCArPSAnPHNwYW4+8J+UtSA8c3Ryb25nPkRlc3Rlazwvc3Ryb25nPiAoMXgpOiBEacSfZXJsZXJpPC9zcGFuPic7CiAgICBoICs9ICc8L2Rpdj48L2Rpdj4nOwoKICAgIC8vIEdlw6dlbmxlcgogICAgaWYocGFzc2VkLmxlbmd0aCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O292ZXJmbG93OmhpZGRlbjttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9InBhZGRpbmc6MTBweCAxNHB4O2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA2KTtmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1ncmVlbik7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZSI+4pyFIENBTlNMSU0gR2XDp3RpICgnK3Bhc3NlZC5sZW5ndGgrJyk8L2Rpdj4nOwogICAgICBwYXNzZWQuZm9yRWFjaChmdW5jdGlvbihyKXsgaCArPSBzdG9ja1JvdyhyLCByLnRpY2tlcj09PWV4cGFuZGVkVGlja2VyKTsgfSk7CiAgICAgIGggKz0gJzwvZGl2Pic7CiAgICB9CgogICAgLy8gV2F0Y2hsaXN0L1BvcnRmb2xpbyAoZ2XDp2VtZXllbmxlcikKICAgIHZhciBteUZhaWxlZCA9IGZhaWxlZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuaW5fd2F0Y2hsaXN0fHxyLmluX3BvcnRmb2xpbzt9KTsKICAgIGlmKG15RmFpbGVkLmxlbmd0aCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O292ZXJmbG93OmhpZGRlbjttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9InBhZGRpbmc6MTBweCAxNHB4O2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA2KTtmb250LXNpemU6MTFweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2UiPvCfk4sgTGlzdGVtZGUgKEdlw6dlbWVkaSwgJytteUZhaWxlZC5sZW5ndGgrJyk8L2Rpdj4nOwogICAgICBteUZhaWxlZC5mb3JFYWNoKGZ1bmN0aW9uKHIpeyBoICs9IHN0b2NrUm93KHIsIHIudGlja2VyPT09ZXhwYW5kZWRUaWNrZXIpOyB9KTsKICAgICAgaCArPSAnPC9kaXY+JzsKICAgIH0KCiAgICBoICs9ICc8L2Rpdj4nOwogICAgcmV0dXJuIGg7CiAgfQoKICBncmlkLmlubmVySFRNTCA9IGJ1aWxkSFRNTCgpOwoKICAvLyBvbmNsaWNrIGhhbmRsZXJzCiAgZGF0YS5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3NjLScrci50aWNrZXIpOwogICAgaWYoZWwpewogICAgICBlbC5vbmNsaWNrID0gZnVuY3Rpb24oZSl7CiAgICAgICAgZS5zdG9wUHJvcGFnYXRpb24oKTsKICAgICAgICBpZihleHBhbmRlZFRpY2tlcj09PXIudGlja2VyKXsgZXhwYW5kZWRUaWNrZXI9bnVsbDsgfQogICAgICAgIGVsc2UgeyBleHBhbmRlZFRpY2tlcj1yLnRpY2tlcjsgfQogICAgICAgIGdyaWQuaW5uZXJIVE1MID0gYnVpbGRIVE1MKCk7CiAgICAgICAgLy8gUmUtYXR0YWNoIGhhbmRsZXJzCiAgICAgICAgZGF0YS5mb3JFYWNoKGZ1bmN0aW9uKHIyKXsKICAgICAgICAgIHZhciBlbDIgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnc2MtJytyMi50aWNrZXIpOwogICAgICAgICAgaWYoZWwyKSBlbDIub25jbGljayA9IGFyZ3VtZW50cy5jYWxsZWUuYmluZCh7dGlja2VyOnIyLnRpY2tlcn0pOwogICAgICAgIH0pOwogICAgICAgIGF0dGFjaEhhbmRsZXJzKCk7CiAgICAgIH07CiAgICB9CiAgfSk7CgogIGZ1bmN0aW9uIGF0dGFjaEhhbmRsZXJzKCl7CiAgICBkYXRhLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICAgIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdzYy0nK3IudGlja2VyKTsKICAgICAgaWYoIWVsKSByZXR1cm47CiAgICAgIGVsLm9uY2xpY2sgPSAoZnVuY3Rpb24odGlja2VyKXsKICAgICAgICByZXR1cm4gZnVuY3Rpb24oZSl7CiAgICAgICAgICBlLnN0b3BQcm9wYWdhdGlvbigpOwogICAgICAgICAgZXhwYW5kZWRUaWNrZXIgPSBleHBhbmRlZFRpY2tlcj09PXRpY2tlciA/IG51bGwgOiB0aWNrZXI7CiAgICAgICAgICBncmlkLmlubmVySFRNTCA9IGJ1aWxkSFRNTCgpOwogICAgICAgICAgYXR0YWNoSGFuZGxlcnMoKTsKICAgICAgICB9OwogICAgICB9KShyLnRpY2tlcik7CiAgICB9KTsKICB9CiAgYXR0YWNoSGFuZGxlcnMoKTsKfQoKCmZ1bmN0aW9uIHJlbmRlclZhbHVhdGlvbigpewogIHZhciBjb250YWluZXIgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogIGlmKCFjb250YWluZXIpIHJldHVybjsKICAvLyBPdmVycmlkZSBncmlkIGxheW91dCBzbyB0YWJsZSBzcGFucyBmdWxsIHdpZHRoCiAgY29udGFpbmVyLnN0eWxlLmRpc3BsYXkgPSAnYmxvY2snOwogIGNvbnRhaW5lci5zdHlsZS53aWR0aCA9ICcxMDAlJzsKICBjb250YWluZXIuaW5uZXJIVE1MID0gJzxkaXYgc3R5bGU9InBhZGRpbmc6MTZweDt3aWR0aDoxMDAlO2JveC1zaXppbmc6Ym9yZGVyLWJveCI+PGgyIHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWJvdHRvbTo0cHgiPvCfko4gRGXEn2VybGVtZSBBbmFsaXppPC9oMj48cCBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MTZweCI+V2F0Y2hsaXN0IGhpc3NlbGVyaW5pbiB0ZW1lbCBkZcSfZXJsZW1lIG1ldHJpa2xlcmkga2FyxZ/EsWxhxZ90xLFybWFzxLE8L3A+PGRpdiBpZD0idmFsdWF0aW9uLWdyaWQiIHN0eWxlPSJ3aWR0aDoxMDAlO292ZXJmbG93LXg6YXV0bzstd2Via2l0LW92ZXJmbG93LXNjcm9sbGluZzp0b3VjaCI+PC9kaXY+PC9kaXY+JzsKICB2YXIgY29udGFpbmVyID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3ZhbHVhdGlvbi1ncmlkJyk7CiAgaWYoIWNvbnRhaW5lcikgcmV0dXJuOwogIHZhciBkYXRhID0gKFRGX0RBVEEgJiYgVEZfREFUQVsnMWQnXSkgPyBURl9EQVRBWycxZCddIDogW107CiAgaWYoIWRhdGEubGVuZ3RoKXtjb250YWluZXIuaW5uZXJIVE1MPSc8cCBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpO3BhZGRpbmc6MjBweCI+VmVyaSB5b2s8L3A+JztyZXR1cm47fQoKICB2YXIgbWV0cmljcyA9IFsKICAgIHtrZXk6J2Vwc19ncm93dGgnLCAgIGxhYmVsOidFUFMlJywgICAgZGVzYzonU29uIGNleXJlayBFUFMgYnV5dW1lIG9yYW5pICh5aWxsaWspLiBDQU5TTElNIEMga3JpdGVyaSDigJQgZW4ga3JpdGlrIG1ldHJpay4gU2VrdG9ydW5kZSBsaWRlciBrYXphbmMgYXJ0aXNpIGxhemltLicsICBpZGVhbDonPjIwJSBpZGVhbCwgPjMwJSBndWNsdScsICAgICAgICAgbG86MjAsIGhpOjEwMCwgZm10OiclJywgaGI6dHJ1ZX0sCiAgICB7a2V5OidyZXZfZ3Jvd3RoJywgICBsYWJlbDonR2VsaXIlJywgIGRlc2M6J1NvbiBjZXlyZWsgZ2VsaXIgYnV5dW1lIG9yYW5pLiBDQU5TTElNIEEga3JpdGVyaS4gU2lya2V0aW4gcGF6YXIgcGF5aW5pIHZlIG1vbWVudHVtIGd1Y3VudSBnb3N0ZXJpci4nLCAgICAgICAgICAgICAgICBpZGVhbDonPjE1JSBpeWksID4yNSUgZ3VjbHUnLCAgICAgICAgICAgbG86MTUsIGhpOjEwMCwgZm10OiclJywgaGI6dHJ1ZX0sCiAgICB7a2V5OidwZV9md2QnLCAgICBsYWJlbDonSWxlcmkgRi9LJywgIGRlc2M6J09udW3DvHpkZWtpIDEyIGF5IHRhaG1pbmkga2F6YW5jaW5hIGdvcmUgRi9LLiBQaXlhc2FuaW4gYnV5dW1lIGJla2xlbnRpc2luaSB5YW5zaXRpci4gQnV5dW1leWxlIGthcnNpbGFzdGlybWFrIG9uZW1saS4nLCBpZGVhbDonPDI1IGlkZWFsLCA8MzUga2FidWwnLCAgICAgICAgICBsbzowLCAgaGk6MjUsICBmbXQ6J3gnLCBoYjpmYWxzZX0sCiAgICB7a2V5OidwZWcnLCAgICAgICBsYWJlbDonUEVHJywgICAgICAgIGRlc2M6J0YvSyBvcmFuaW5pIEVQUyBidXl1bWUgaGl6aSBpbGUga2Fyc2lsYXN0aXJpci4gRW4gZGVuZ2VsaSBkZWdlcmxlbWUgbWV0cmnEn2k6IDEgYWx0aW5kYSB1Y3V6LCAxLTIgbWFrdWwsIDIgdXN0dSBwYWhhbGkuJywgaWRlYWw6JzwxIFVjdXosIDEtMiBNYWt1bCwgPjIgUGFoYWxpJywgbG86MCwgaGk6MiwgICBmbXQ6J3gnLCBoYjpmYWxzZX0sCiAgICB7a2V5Oidncm9zc19tYXJnaW4nLCBsYWJlbDonQnJ1dCUnLCAgIGRlc2M6J0JydXQga2FyIG1hcmppbmkuIFNpcmtldGluIGZpeWF0bGFtYSBndWN1bnUgdmUgdXJ1biBrYWxpdGVzaW5pIGdvc3RlcmlyLiBZdWtzZWsgbWFyamluIHJla2FiZXQgdXN0dW5sdWd1IGlzYXJldGxlci4nLCAgIGlkZWFsOidZYXppbGltID43MCUsIEdlbmVsID40MCUnLCAgICAgICBsbzo0MCwgaGk6MTAwLCBmbXQ6JyUnLCBoYjp0cnVlfSwKICAgIHtrZXk6J25ldF9tYXJnaW4nLCAgIGxhYmVsOidOZXQlJywgICAgZGVzYzonTmV0IGthciBtYXJqaW5pLiBUdW0gZ2lkZXJsZXIgZHVzdWxkdWt0ZW4gc29ucmEga2FsYW4ga2FyIHl1emRlc2kuIE9wZXJhc3lvbmVsIHZlcmltbGlsaWdpIGdvc3RlcmlyLicsICAgICAgICAgICAgICAgICAgaWRlYWw6Jz4xMCUgaXlpLCA+MjAlIG11a2VtbWVsJywgICAgICAgIGxvOjEwLCBoaToxMDAsIGZtdDonJScsIGhiOnRydWV9LAogICAge2tleToncm9lJywgICAgICAgICAgbGFiZWw6J09LRycsICAgICBkZXNjOidPenNlcm1heWUgS2FybGlsaWdpIChST0UpLiBDQU5TTElNIE4ga3JpdGVyaTogeW9uZXRpbWluIHNlcm1heWV5aSBuZSBrYWRhciB2ZXJpbWxpIGt1bGxhbmRpZ2luaSBvbGNlci4nLCAgICAgICAgICAgICAgIGlkZWFsOic+MTUlIGl5aSwgPjI1JSBtdWtlbW1lbCcsICAgICAgICBsbzoxNSwgaGk6MTAwLCBmbXQ6JyUnLCBoYjp0cnVlfSwKICAgIHtrZXk6J3BlX3R0bScsICAgIGxhYmVsOidGL0snLCAgICAgICAgZGVzYzonU29uIDEyIGF5IGdlcmNlayBrYXphbmNpbmEgZ29yZSBmaXlhdC9rYXphbmMgb3JhbmkuIFRhcmloaSBrYXJzaWxhc3Rpcm1hIGljaW4ga3VsbGFuaWxpci4nLCAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZGVhbDonVGVrbm9sb2ppIDwzNSwgR2VuZWwgPDI1JywgICAgICAgbG86MCwgIGhpOjM1LCAgZm10Oid4JywgaGI6ZmFsc2V9LAogICAge2tleToncHMnLCAgICAgICAgbGFiZWw6J0YvUycsICAgICAgICBkZXNjOidGaXlhdCAvIFNhdGlzbGFyLiBIZW51eiBrYXJzaXogdmV5YSBoaXpsaSBidXl1eWVuIHNpcmtldGxlcmkgZGVnZXJsZW5kaXJtZWsgaWNpbiBrdWxsYW5pbGlyLicsICAgICAgICAgICAgICAgICAgICAgICAgIGlkZWFsOidUZWtub2xvamkgPDgsIEdlbmVsIDwzJywgICAgICAgICBsbzowLCAgaGk6OCwgICBmbXQ6J3gnLCBoYjpmYWxzZX0sCiAgICB7a2V5OidwYicsICAgICAgICBsYWJlbDonRi9ERCcsICAgICAgIGRlc2M6J0ZpeWF0IC8gRGVmdGVyIERlZ2VyaS4gU2lya2V0aW4gbmV0IHZhcmxpa2xhcmluYSBnb3JlIGZpeWF0aW5pIGdvc3RlcmlyLiBOZWdhdGlmIG96c2VybWF5ZWRlIGFubGFtc2l6ZGlyLicsICAgICAgICAgICAgaWRlYWw6JzwzIFVjdXosIDMtNyBNYWt1bCwgPjcgUGFoYWxpJywgbG86MCwgIGhpOjUsICAgZm10Oid4JywgaGI6ZmFsc2V9LAogICAge2tleTonYW5hbHlzdF90YXJnZXQnLCBsYWJlbDonSGVkZWYnLCBkZXNjOidBbmFsaXN0IGtvbnNlbnN1cyBoZWRlZiBmaXlhdGkuIFl1emRlIHVwc2lkZSBtZXZjdXQgZml5YXRhIGdvcmUgaGVzYXBsYW5taXN0aXIuIFNvbiBrb250cm9sIG5va3Rhc2kuJywgICAgICAgICAgICAgICAgIGlkZWFsOidNZXZjdXQgZml5YXR0YW4geXVrc2VrIG9sc3VuJywgICBsbzowLCAgaGk6MCwgICBmbXQ6JyQnLCBoYjp0cnVlfSwKICBdOwoKICBmdW5jdGlvbiB0aXAobGJsLGRlc2MsaWRlYWwpewogICAgcmV0dXJuIGxibCsnPHNwYW4gc3R5bGU9ImN1cnNvcjpoZWxwO3dpZHRoOjEycHg7aGVpZ2h0OjEycHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4xKTtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1zaXplOjhweDtmb250LXdlaWdodDo3MDA7ZGlzcGxheTppbmxpbmUtZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjttYXJnaW4tbGVmdDozcHg7ZmxleC1zaHJpbms6MDt2ZXJ0aWNhbC1hbGlnbjptaWRkbGUiIHRpdGxlPSInK2Rlc2MrJyAgfCAgSWRlYWw6ICcraWRlYWwrJyI+Pzwvc3Bhbj4nOwogIH0KICBmdW5jdGlvbiBjb2xPZih2YWwsbG8saGksaGIpewogICAgaWYodmFsPT09bnVsbHx8dmFsPT09dW5kZWZpbmVkKXJldHVybiAndmFyKC0tbXV0ZWQpJzsKICAgIHZhciBuPXBhcnNlRmxvYXQodmFsKTtpZihpc05hTihuKSlyZXR1cm4gJ3ZhcigtLW11dGVkKSc7CiAgICBpZihoYil7cmV0dXJuIG4+PWhpKjAuNz8ndmFyKC0tZ3JlZW4pJzpuPj1sbz8ndmFyKC0teWVsbG93KSc6J3ZhcigtLXJlZDIpJzt9CiAgICBlbHNlICB7cmV0dXJuIG48PWxvKjEuMj8ndmFyKC0tZ3JlZW4pJzpuPD1oaT8ndmFyKC0teWVsbG93KSc6J3ZhcigtLXJlZDIpJzt9CiAgfQogIGZ1bmN0aW9uIGZtdFYodmFsLGZtdCxwcmljZSl7CiAgICBpZih2YWw9PT1udWxsfHx2YWw9PT11bmRlZmluZWQpcmV0dXJuICc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj7igJQ8L3NwYW4+JzsKICAgIHZhciBuPXBhcnNlRmxvYXQodmFsKTtpZihpc05hTihuKSlyZXR1cm4gJzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPuKAlDwvc3Bhbj4nOwogICAgaWYoZm10PT09J3gnKXJldHVybiBuLnRvRml4ZWQoMSkrJ3gnOwogICAgaWYoZm10PT09JyUnKXJldHVybiBuLnRvRml4ZWQoMSkrJyUnOwogICAgaWYoZm10PT09JyQnKXsKICAgICAgdmFyIHVwPXByaWNlPjA/KChuLXByaWNlKS9wcmljZSoxMDApLnRvRml4ZWQoMSk6bnVsbDsKICAgICAgdmFyIGM9KHVwIT09bnVsbCYmcGFyc2VGbG9hdCh1cCk+MCk/J3ZhcigtLWdyZWVuKSc6J3ZhcigtLXJlZDIpJzsKICAgICAgcmV0dXJuICckJytuLnRvRml4ZWQoMCkrKHVwIT09bnVsbD8nIDxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrYysnIj4nKyhwYXJzZUZsb2F0KHVwKT4wPycrJzonJykrdXArJyU8L3NwYW4+JzonJyk7CiAgICB9CiAgICByZXR1cm4gU3RyaW5nKG4pOwogIH0KCiAgdmFyIHJvd3M9ZGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSk7CiAgdmFyIGh0bWw9Jzx0YWJsZSBzdHlsZT0id2lkdGg6MTAwJTtib3JkZXItY29sbGFwc2U6Y29sbGFwc2U7Zm9udC1zaXplOjExcHg7bWluLXdpZHRoOjcwMHB4Ij4nOwogIGh0bWwrPSc8dGhlYWQ+PHRyIHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMikiPic7CiAgaHRtbCs9Jzx0aCBzdHlsZT0idGV4dC1hbGlnbjpsZWZ0O3BhZGRpbmc6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC13ZWlnaHQ6NjAwIj5IaXNzZTwvdGg+JzsKICBodG1sKz0nPHRoIHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O3BhZGRpbmc6MTBweCA4cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtd2VpZ2h0OjYwMCI+Rml5YXQ8L3RoPic7CiAgbWV0cmljcy5mb3JFYWNoKGZ1bmN0aW9uKG1tKXtodG1sKz0nPHRoIHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O3BhZGRpbmc6OHB4IDRweDtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC13ZWlnaHQ6NjAwO3doaXRlLXNwYWNlOm5vd3JhcDtmb250LXNpemU6MTBweCI+Jyt0aXAobW0ubGFiZWwsbW0uZGVzYyxtbS5pZGVhbCkrJzwvdGg+Jzt9KTsKICBodG1sKz0nPC90cj48L3RoZWFkPjx0Ym9keT4nOwoKICByb3dzLmZvckVhY2goZnVuY3Rpb24ocixpKXsKICAgIHZhciBiZz1pJTI9PT0wPyd2YXIoLS1iZyknOidyZ2JhKDI1NSwyNTUsMjU1LC4wMiknOwogICAgdmFyIGluUD1yLnBvcnRmb2xpbzsKICAgIGh0bWwrPSc8dHIgc3R5bGU9ImJhY2tncm91bmQ6JytiZysnO2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjAzKSI+JzsKICAgIGh0bWwrPSc8dGQgc3R5bGU9InBhZGRpbmc6MTBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JysoaW5QPyd2YXIoLS1ncmVlbiknOid2YXIoLS10ZXh0KScpKyciPicrci50aWNrZXIrKGluUD8nPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo4cHg7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzoxcHggNHB4O2JvcmRlci1yYWRpdXM6M3B4O21hcmdpbi1sZWZ0OjRweCI+UDwvc3Bhbj4nOicnKSsnPC90ZD4nOwogICAgaHRtbCs9Jzx0ZCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjhweCA0cHg7Y29sb3I6dmFyKC0tdGV4dCk7Zm9udC13ZWlnaHQ6NjAwO2ZvbnQtc2l6ZToxMHB4Ij4kJytyLmZpeWF0Kyc8L3RkPic7CiAgICBtZXRyaWNzLmZvckVhY2goZnVuY3Rpb24obW0pewogICAgICB2YXIgdmFsPW1tLmtleT09PSdhbmFseXN0X3RhcmdldCc/ci5mYWlyX3ByaWNlX2FuYWx5c3Q6clttbS5rZXldOwogICAgICB2YXIgY29sPW1tLmtleT09PSdhbmFseXN0X3RhcmdldCc/KHIuZmFpcl9wcmljZV9hbmFseXN0JiZyLmZhaXJfcHJpY2VfYW5hbHlzdD5yLmZpeWF0Pyd2YXIoLS1ncmVlbiknOid2YXIoLS1yZWQyKScpOmNvbE9mKHZhbCxtbS5sbyxtbS5oaSxtbS5oYik7CiAgICAgIGh0bWwrPSc8dGQgc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7cGFkZGluZzoxMHB4IDhweDtjb2xvcjonK2NvbCsnIj4nK2ZtdFYodmFsLG1tLmZtdCxyLmZpeWF0KSsnPC90ZD4nOwogICAgfSk7CiAgICBodG1sKz0nPC90cj4nOwogIH0pOwoKICBodG1sKz0nPC90Ym9keT48L3RhYmxlPic7CiAgaHRtbCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTZweDttYXJnaW4tdG9wOjEwcHg7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nOwogIGh0bWwrPSc8c3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pIj7il488L3NwYW4+IEl5aTwvc3Bhbj4nOwogIGh0bWwrPSc8c3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0teWVsbG93KSI+4pePPC9zcGFuPiBNYWt1bDwvc3Bhbj4nOwogIGh0bWwrPSc8c3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMikiPuKXjzwvc3Bhbj4gRGlra2F0PC9zcGFuPic7CiAgaHRtbCs9JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPuKAlCA9IFZlcmkgeW9rPC9zcGFuPic7CiAgaHRtbCs9JzxzcGFuIHN0eWxlPSJtYXJnaW4tbGVmdDphdXRvIj48c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzoxcHggNHB4O2JvcmRlci1yYWRpdXM6M3B4Ij5QPC9zcGFuPiBQb3J0Zm95PC9zcGFuPjwvZGl2Pic7CiAgY29udGFpbmVyLmlubmVySFRNTD1odG1sOwp9Cjwvc2NyaXB0PgoKPC9ib2R5Pgo8L2h0bWw+"
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


def build_html(tf_data, timestamp, earnings_data=None, market_data=None, news_data=None, ai_analyses=None, weekly_data=None, canslim_results=None):
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
html = build_html(tf_data, timestamp, earnings_data, market_data, news_data, ai_analyses, weekly_data, canslim_results)
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
