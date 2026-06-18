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
    _T = "PCFET0NUWVBFIGh0bWw+CjxodG1sIGxhbmc9InRyIj4KPGhlYWQ+CjxtZXRhIGNoYXJzZXQ9IlVURi04Ii8+CjxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsaW5pdGlhbC1zY2FsZT0xIi8+Cjx0aXRsZT5DQU5TTElNIFNjYW5uZXI8L3RpdGxlPgo8bGluayByZWw9Imljb24iIHR5cGU9ImltYWdlL3N2Zyt4bWwiIGhyZWY9ImRhdGE6aW1hZ2Uvc3ZnK3htbCwlM0NzdmcgeG1sbnM9J2h0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnJyB2aWV3Qm94PScwIDAgMzIgMzInJTNFJTNDcmVjdCB3aWR0aD0nMzInIGhlaWdodD0nMzInIHJ4PSc2JyBmaWxsPSclMjMwZDExMTcnLyUzRSUzQ3BvbHlsaW5lIHBvaW50cz0nNCwyNCAxMCwxNiAxNiwyMCAyMiwxMCAyOCwxNCcgZmlsbD0nbm9uZScgc3Ryb2tlPSclMjMxMGI5ODEnIHN0cm9rZS13aWR0aD0nMi41JyBzdHJva2UtbGluZWNhcD0ncm91bmQnIHN0cm9rZS1saW5lam9pbj0ncm91bmQnLyUzRSUzQy9zdmclM0UiPgo8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PVNwYWNlK0dyb3Rlc2s6d2dodEA0MDA7NTAwOzYwMDs3MDAmZmFtaWx5PUJlYmFzK05ldWUmZmFtaWx5PUpldEJyYWlucytNb25vOndnaHRANDAwOzYwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCIvPgo8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9jaGFydC5qc0A0LjQuMC9kaXN0L2NoYXJ0LnVtZC5taW4uanMiPgovLyDilIDilIAgRGXEn2VybGVtZSB0b29sdGlwIOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgOKUgAooZnVuY3Rpb24oKXsKICB2YXIgdGlwID0gbnVsbDsKICBmdW5jdGlvbiBnZXRPckNyZWF0ZVRpcCgpewogICAgaWYoIXRpcCl7CiAgICAgIHRpcCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgICB0aXAuaWQgPSAndmFsLXRvb2x0aXAnOwogICAgICB0aXAuc3R5bGUuY3NzVGV4dCA9ICdwb3NpdGlvbjpmaXhlZDtiYWNrZ3JvdW5kOiMxZTI5M2I7Ym9yZGVyOjFweCBzb2xpZCAjMzc0MTUxO2NvbG9yOiNlMmU4ZjA7cGFkZGluZzoxMHB4IDE0cHg7Ym9yZGVyLXJhZGl1czo4cHg7Zm9udC1zaXplOjExcHg7bGluZS1oZWlnaHQ6MS43O21heC13aWR0aDoyODBweDt6LWluZGV4Ojk5OTk7cG9pbnRlci1ldmVudHM6bm9uZTtib3gtc2hhZG93OjAgNHB4IDIwcHggcmdiYSgwLDAsMCwuNSk7ZGlzcGxheTpub25lJzsKICAgICAgZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZCh0aXApOwogICAgfQogICAgcmV0dXJuIHRpcDsKICB9CiAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbW91c2VvdmVyJywgZnVuY3Rpb24oZSl7CiAgICB2YXIgZWwgPSBlLnRhcmdldC5jbG9zZXN0KCcudmFsLXRpcCcpOwogICAgaWYoIWVsKSByZXR1cm47CiAgICB2YXIgcGFydHMgPSBlbC5nZXRBdHRyaWJ1dGUoJ2RhdGEtdGlwJykuc3BsaXQoJ3x8Jyk7CiAgICB2YXIgdCA9IGdldE9yQ3JlYXRlVGlwKCk7CiAgICB0LmlubmVySFRNTCA9ICc8c3Ryb25nIHN0eWxlPSJjb2xvcjojNjBhNWZhIj4nK3BhcnRzWzBdKyc8L3N0cm9uZz48YnI+JytwYXJ0c1sxXSsnPGJyPjxicj48c3BhbiBzdHlsZT0iY29sb3I6I2Y1OWUwYiI+JytwYXJ0c1syXSsnPC9zcGFuPic7CiAgICB0LnN0eWxlLmRpc3BsYXkgPSAnYmxvY2snOwogICAgdC5zdHlsZS5sZWZ0ID0gTWF0aC5taW4oZS5jbGllbnRYKzE0LCB3aW5kb3cuaW5uZXJXaWR0aC0zMDApKydweCc7CiAgICB0LnN0eWxlLnRvcCA9IE1hdGgubWF4KGUuY2xpZW50WS0xMCwgMTApKydweCc7CiAgfSk7CiAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbW91c2Vtb3ZlJywgZnVuY3Rpb24oZSl7CiAgICBpZighdGlwIHx8IHRpcC5zdHlsZS5kaXNwbGF5PT09J25vbmUnKSByZXR1cm47CiAgICBpZighZS50YXJnZXQuY2xvc2VzdCgnLnZhbC10aXAnKSl7IHRpcC5zdHlsZS5kaXNwbGF5PSdub25lJzsgcmV0dXJuOyB9CiAgICB0aXAuc3R5bGUubGVmdCA9IE1hdGgubWluKGUuY2xpZW50WCsxNCwgd2luZG93LmlubmVyV2lkdGgtMzAwKSsncHgnOwogICAgdGlwLnN0eWxlLnRvcCA9IE1hdGgubWF4KGUuY2xpZW50WS0xMCwgMTApKydweCc7CiAgfSk7CiAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignbW91c2VvdXQnLCBmdW5jdGlvbihlKXsKICAgIGlmKCFlLnRhcmdldC5jbG9zZXN0KCcudmFsLXRpcCcpKSByZXR1cm47CiAgICBpZighZS5yZWxhdGVkVGFyZ2V0IHx8ICFlLnJlbGF0ZWRUYXJnZXQuY2xvc2VzdCgnLnZhbC10aXAnKSl7CiAgICAgIGlmKHRpcCkgdGlwLnN0eWxlLmRpc3BsYXk9J25vbmUnOwogICAgfQogIH0pOwp9KSgpOwoKPC9zY3JpcHQ+CjxzdHlsZT4KOnJvb3R7LS1iZzojMDUwNzBmOy0tYmcyOiMwZDExMTc7LS1iZzM6IzE2MWIyNDstLWJvcmRlcjpyZ2JhKDI1NSwyNTUsMjU1LDAuMDgpOy0tdGV4dDojZTJlOGYwOy0tbXV0ZWQ6IzRiNTU2MzstLWdyZWVuOiMxMGI5ODE7LS1ncmVlbjI6IzM0ZDM5OTstLXJlZDojZWY0NDQ0Oy0tcmVkMjojZjg3MTcxOy0teWVsbG93OiNmNTllMGI7fQoqe2JveC1zaXppbmc6Ym9yZGVyLWJveDttYXJnaW46MDtwYWRkaW5nOjB9CmJvZHl7YmFja2dyb3VuZDp2YXIoLS1iZyk7Y29sb3I6dmFyKC0tdGV4dCk7Zm9udC1mYW1pbHk6J1NwYWNlIEdyb3Rlc2snLHNhbnMtc2VyaWY7bWluLWhlaWdodDoxMDB2aH0KLmhlYWRlcntiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCgxMzVkZWcsIzBkMTExNywjMTExODI3KTtib3JkZXItYm90dG9tOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO3BhZGRpbmc6MTRweCAyMHB4O3Bvc2l0aW9uOnN0aWNreTt0b3A6MDt6LWluZGV4OjEwMH0KLmhlYWRlci1pbm5lcntkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2ZsZXgtd3JhcDp3cmFwO2dhcDoxMHB4O21heC13aWR0aDoxNDAwcHg7bWFyZ2luOjAgYXV0b30KLmxvZ28tbWFpbntmb250LWZhbWlseTonQmViYXMgTmV1ZScsc2Fucy1zZXJpZjtmb250LXNpemU6MjJweDtsZXR0ZXItc3BhY2luZzo0cHg7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCMxMGI5ODEsIzNiODJmNik7LXdlYmtpdC1iYWNrZ3JvdW5kLWNsaXA6dGV4dDstd2Via2l0LXRleHQtZmlsbC1jb2xvcjp0cmFuc3BhcmVudH0KLnRpbWVzdGFtcHtmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlfQoubGl2ZS1kb3R7d2lkdGg6N3B4O2hlaWdodDo3cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDp2YXIoLS1ncmVlbik7YW5pbWF0aW9uOnB1bHNlIDJzIGluZmluaXRlO2Rpc3BsYXk6aW5saW5lLWJsb2NrO21hcmdpbi1yaWdodDo1cHh9CkBrZXlmcmFtZXMgcHVsc2V7MCUsMTAwJXtvcGFjaXR5OjE7Ym94LXNoYWRvdzowIDAgMCAwIHJnYmEoMTYsMTg1LDEyOSwuNCl9NTAle29wYWNpdHk6Ljc7Ym94LXNoYWRvdzowIDAgMCA2cHggcmdiYSgxNiwxODUsMTI5LDApfX0KLm5hdntkaXNwbGF5OmZsZXg7Z2FwOjRweDtwYWRkaW5nOjEwcHggMjBweDtib3JkZXItYm90dG9tOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmcyKTtvdmVyZmxvdy14OmF1dG87ZmxleC13cmFwOndyYXB9Ci50YWJ7cGFkZGluZzo2cHggMTRweDtib3JkZXItcmFkaXVzOjZweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo1MDA7Ym9yZGVyOjFweCBzb2xpZCB0cmFuc3BhcmVudDtiYWNrZ3JvdW5kOm5vbmU7Y29sb3I6dmFyKC0tbXV0ZWQpO3RyYW5zaXRpb246YWxsIC4yczt3aGl0ZS1zcGFjZTpub3dyYXB9Ci50YWI6aG92ZXJ7Y29sb3I6dmFyKC0tdGV4dCk7YmFja2dyb3VuZDp2YXIoLS1iZzMpfQoudGFiLmFjdGl2ZXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Y29sb3I6dmFyKC0tdGV4dCk7Ym9yZGVyLWNvbG9yOnZhcigtLWJvcmRlcil9Ci50YWIucG9ydC5hY3RpdmV7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXItY29sb3I6cmdiYSgxNiwxODUsMTI5LC4zKX0KLnRmLXJvd3tkaXNwbGF5OmZsZXg7Z2FwOjZweDtwYWRkaW5nOjEwcHggMjBweDtib3JkZXItYm90dG9tOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmcyKTthbGlnbi1pdGVtczpjZW50ZXI7ZmxleC13cmFwOndyYXB9Ci50Zi1idG57cGFkZGluZzo1cHggMTJweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTFweDtjdXJzb3I6cG9pbnRlcjtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLW11dGVkKTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7dHJhbnNpdGlvbjphbGwgLjJzfQoudGYtYnRuLmFjdGl2ZXtiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMTUpO2NvbG9yOiM2MGE1ZmE7Ym9yZGVyLWNvbG9yOnJnYmEoNTksMTMwLDI0NiwuNCl9Ci50Zi1idG4uc3Rhcntwb3NpdGlvbjpyZWxhdGl2ZX0KLnRmLWJ0bi5zdGFyOjphZnRlcntjb250ZW50OifimIUnO3Bvc2l0aW9uOmFic29sdXRlO3RvcDotNXB4O3JpZ2h0Oi00cHg7Zm9udC1zaXplOjhweDtjb2xvcjp2YXIoLS15ZWxsb3cpfQoudGYtaGludHtmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCl9Ci5zdGF0c3tkaXNwbGF5OmZsZXg7Z2FwOjhweDtwYWRkaW5nOjEwcHggMjBweDtib3JkZXItYm90dG9tOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmcyKTtmbGV4LXdyYXA6d3JhcH0KLnBpbGx7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NXB4O3BhZGRpbmc6NHB4IDEwcHg7Ym9yZGVyLXJhZGl1czoyMHB4O2ZvbnQtc2l6ZToxMXB4O2ZvbnQtd2VpZ2h0OjYwMDtib3JkZXI6MXB4IHNvbGlkfQoucGlsbC5ne2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyLWNvbG9yOnJnYmEoMTYsMTg1LDEyOSwuMjUpfQoucGlsbC5ye2JhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjEpO2NvbG9yOnZhcigtLXJlZDIpO2JvcmRlci1jb2xvcjpyZ2JhKDIzOSw2OCw2OCwuMjUpfQoucGlsbC55e2JhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4xKTtjb2xvcjp2YXIoLS15ZWxsb3cpO2JvcmRlci1jb2xvcjpyZ2JhKDI0NSwxNTgsMTEsLjI1KX0KLnBpbGwuYntiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMSk7Y29sb3I6IzYwYTVmYTtib3JkZXItY29sb3I6cmdiYSg1OSwxMzAsMjQ2LC4yNSl9Ci5waWxsLm17YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLW11dGVkKTtib3JkZXItY29sb3I6dmFyKC0tYm9yZGVyKX0KLmRvdHt3aWR0aDo1cHg7aGVpZ2h0OjVweDtib3JkZXItcmFkaXVzOjUwJTtiYWNrZ3JvdW5kOmN1cnJlbnRDb2xvcn0KLm1haW57cGFkZGluZzoxNHB4IDIwcHg7bWF4LXdpZHRoOjE0MDBweDttYXJnaW46MCBhdXRvfQouZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDMwMHB4LDFmcikpO2dhcDoxMHB4fQpAbWVkaWEobWF4LXdpZHRoOjQ4MHB4KXsuZ3JpZHtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyfX0KLmNhcmR7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7b3ZlcmZsb3c6aGlkZGVuO2N1cnNvcjpwb2ludGVyO3RyYW5zaXRpb246YWxsIC4yc30KLmNhcmQ6aG92ZXJ7dHJhbnNmb3JtOnRyYW5zbGF0ZVkoLTJweCk7Ym94LXNoYWRvdzowIDhweCAyNHB4IHJnYmEoMCwwLDAsLjQpfQouYWNjZW50e2hlaWdodDozcHh9Ci5jYm9keXtwYWRkaW5nOjEycHggMTRweH0KLmN0b3B7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmZsZXgtc3RhcnQ7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47bWFyZ2luLWJvdHRvbTo4cHh9Ci50aWNrZXJ7Zm9udC1mYW1pbHk6J0JlYmFzIE5ldWUnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjIwcHg7bGV0dGVyLXNwYWNpbmc6MnB4O2xpbmUtaGVpZ2h0OjF9Ci5jcHJ7dGV4dC1hbGlnbjpyaWdodH0KLnB2YWx7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxNXB4O2ZvbnQtd2VpZ2h0OjYwMH0KLnBjaGd7Zm9udC1zaXplOjExcHg7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO21hcmdpbi10b3A6MnB4fQouYmFkZ2V7ZGlzcGxheTppbmxpbmUtYmxvY2s7cGFkZGluZzoycHggOHB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZToxMHB4O2ZvbnQtd2VpZ2h0OjcwMDtsZXR0ZXItc3BhY2luZzouNXB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tdG9wOjNweH0KLnBvcnQtYmFkZ2V7ZGlzcGxheTppbmxpbmUtZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjNweDtwYWRkaW5nOjJweCA2cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo2MDA7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEyKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjI1KTttYXJnaW4tbGVmdDo1cHh9Ci5zaWdze2Rpc3BsYXk6ZmxleDtmbGV4LXdyYXA6d3JhcDtnYXA6M3B4O21hcmdpbi1ib3R0b206OHB4fQouc3B7Zm9udC1zaXplOjlweDtwYWRkaW5nOjJweCA2cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlfQouc2d7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEpO2NvbG9yOnZhcigtLWdyZWVuMik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpfQouc2J7YmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMSk7Y29sb3I6dmFyKC0tcmVkMik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMil9Ci5zbntiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Y29sb3I6dmFyKC0tbXV0ZWQpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKX0KLmNoYXJ0LXd7aGVpZ2h0Ojc1cHg7bWFyZ2luLXRvcDo4cHh9Ci5sdmxze2Rpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KDMsMWZyKTtnYXA6NXB4O21hcmdpbi10b3A6OHB4fQoubHZ7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6NXB4O3BhZGRpbmc6NnB4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKX0KLmxse2ZvbnQtc2l6ZTo4cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToycHh9Ci5sdmFse2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTFweDtmb250LXdlaWdodDo2MDB9Ci5vdmVybGF5e3Bvc2l0aW9uOmZpeGVkO2luc2V0OjA7YmFja2dyb3VuZDpyZ2JhKDAsMCwwLC44OCk7ei1pbmRleDoxMDAwO2Rpc3BsYXk6bm9uZTthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjtwYWRkaW5nOjE2cHh9Ci5vdmVybGF5Lm9wZW57ZGlzcGxheTpmbGV4fQoubW9kYWx7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjE0cHg7d2lkdGg6MTAwJTttYXgtd2lkdGg6NTIwcHg7bWF4LWhlaWdodDo5MnZoO292ZXJmbG93LXk6YXV0b30KLm1oZWFke3BhZGRpbmc6MThweCAxOHB4IDA7ZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmZsZXgtc3RhcnR9Ci5tdGl0bGV7Zm9udC1mYW1pbHk6J0JlYmFzIE5ldWUnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjMwcHg7bGV0dGVyLXNwYWNpbmc6M3B4fQoubWNsb3Nle2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tbXV0ZWQpO3dpZHRoOjMwcHg7aGVpZ2h0OjMwcHg7Ym9yZGVyLXJhZGl1czo3cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjE1cHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyfQoubWJvZHl7cGFkZGluZzoxNHB4IDE4cHggMThweH0KLm1jaGFydHd7aGVpZ2h0OjE1MHB4O21hcmdpbi1ib3R0b206MTRweH0KLmRncmlke2Rpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyIDFmcjtnYXA6N3B4O21hcmdpbi1ib3R0b206MTJweH0KLmRje2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjdweDtwYWRkaW5nOjlweCAxMXB4O2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKX0KLmRse2ZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTozcHh9Ci5kdntmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwfQouZGJveHtib3JkZXItcmFkaXVzOjlweDtwYWRkaW5nOjEzcHg7bWFyZ2luLWJvdHRvbToxMnB4O2JvcmRlcjoxcHggc29saWR9Ci5kbGJse2ZvbnQtc2l6ZTo5cHg7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjVweH0KLmR2ZXJke2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyNnB4O2xldHRlci1zcGFjaW5nOjJweDttYXJnaW4tYm90dG9tOjhweH0KLmRyb3d7ZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206NHB4O2ZvbnQtc2l6ZToxMnB4fQouZGtleXtjb2xvcjp2YXIoLS1tdXRlZCl9Ci5ycmJhcntoZWlnaHQ6NHB4O2JhY2tncm91bmQ6dmFyKC0tYmcpO2JvcmRlci1yYWRpdXM6MnB4O21hcmdpbi10b3A6N3B4O292ZXJmbG93OmhpZGRlbn0KLnJyZmlsbHtoZWlnaHQ6MTAwJTtib3JkZXItcmFkaXVzOjJweDt0cmFuc2l0aW9uOndpZHRoIC44cyBlYXNlfQoudnBib3h7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6N3B4O3BhZGRpbmc6MTBweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7bWFyZ2luLWJvdHRvbToxMnB4fQoudnB0aXRsZXtmb250LXNpemU6OXB4O2NvbG9yOiM2MGE1ZmE7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjdweH0KLnZwZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgzLDFmcik7Z2FwOjVweH0KLnZwY3tiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyLXJhZGl1czo1cHg7cGFkZGluZzo3cHg7dGV4dC1hbGlnbjpjZW50ZXI7Ym9yZGVyOjFweCBzb2xpZH0KLm1pbmZve2Rpc3BsYXk6aW5saW5lLWZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7d2lkdGg6MTRweDtoZWlnaHQ6MTRweDtib3JkZXItcmFkaXVzOjUwJTtiYWNrZ3JvdW5kOnJnYmEoOTYsMTY1LDI1MCwuMik7Y29sb3I6IzYwYTVmYTtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjcwMDtjdXJzb3I6cG9pbnRlcjttYXJnaW4tbGVmdDo0cHg7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDk2LDE2NSwyNTAsLjMpfQoubWluZm8tcG9wdXB7cG9zaXRpb246Zml4ZWQ7aW5zZXQ6MDtiYWNrZ3JvdW5kOnJnYmEoMCwwLDAsLjg4KTt6LWluZGV4OjIwMDA7ZGlzcGxheTpub25lO2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO3BhZGRpbmc6MTZweH0KLm1pbmZvLXBvcHVwLm9wZW57ZGlzcGxheTpmbGV4fQoubWluZm8tbW9kYWx7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjE0cHg7d2lkdGg6MTAwJTttYXgtd2lkdGg6NDgwcHg7bWF4LWhlaWdodDo4NXZoO292ZXJmbG93LXk6YXV0bztwYWRkaW5nOjIwcHg7cG9zaXRpb246cmVsYXRpdmV9Ci5taW5mby10aXRsZXtmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCk7bWFyZ2luLWJvdHRvbTo0cHh9Ci5taW5mby1zb3VyY2V7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MTJweDtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo2cHg7ZmxleC13cmFwOndyYXB9Ci5taW5mby1yZWx7cGFkZGluZzoycHggN3B4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwfQoubWluZm8tcmVsLmhpZ2h7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtjb2xvcjojMTBiOTgxfQoubWluZm8tcmVsLm1lZGl1bXtiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMTUpO2NvbG9yOiNmNTllMGJ9Ci5taW5mby1yZWwubG93e2JhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtjb2xvcjojZWY0NDQ0fQoubWluZm8tZGVzY3tmb250LXNpemU6MTJweDtjb2xvcjojOTRhM2I4O2xpbmUtaGVpZ2h0OjEuNjttYXJnaW4tYm90dG9tOjE0cHh9Ci5taW5mby13YXJuaW5ne2JhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6NnB4O3BhZGRpbmc6OHB4IDEwcHg7Zm9udC1zaXplOjExcHg7Y29sb3I6I2Y1OWUwYjttYXJnaW4tYm90dG9tOjE0cHh9Ci5taW5mby1yYW5nZXN7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8tcmFuZ2UtdGl0bGV7Zm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweH0KLm1pbmZvLXJhbmdle2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjhweDttYXJnaW4tYm90dG9tOjZweDtwYWRkaW5nOjZweCA4cHg7Ym9yZGVyLXJhZGl1czo2cHg7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wMil9Ci5taW5mby1yYW5nZS1kb3R7d2lkdGg6OHB4O2hlaWdodDo4cHg7Ym9yZGVyLXJhZGl1czo1MCU7ZmxleC1zaHJpbms6MH0KLm1pbmZvLWNhbnNsaW17YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czo2cHg7cGFkZGluZzo4cHggMTBweDtmb250LXNpemU6MTFweDtjb2xvcjojNjBhNWZhfQoubWluZm8tY2xvc2V7cG9zaXRpb246YWJzb2x1dGU7dG9wOjE2cHg7cmlnaHQ6MTZweDtiYWNrZ3JvdW5kOnJnYmEoMjU1LDI1NSwyNTUsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjEpO2NvbG9yOiM5NGEzYjg7d2lkdGg6MjhweDtoZWlnaHQ6MjhweDtib3JkZXItcmFkaXVzOjdweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTRweDtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXJ9Cjo6LXdlYmtpdC1zY3JvbGxiYXJ7d2lkdGg6NHB4O2hlaWdodDo0cHh9Cjo6LXdlYmtpdC1zY3JvbGxiYXItdHJhY2t7YmFja2dyb3VuZDp2YXIoLS1iZyl9Cjo6LXdlYmtpdC1zY3JvbGxiYXItdGh1bWJ7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4xKTtib3JkZXItcmFkaXVzOjJweH0KPC9zdHlsZT4KPC9oZWFkPgo8Ym9keT4KPGRpdiBjbGFzcz0iaGVhZGVyIj4KICA8ZGl2IGNsYXNzPSJoZWFkZXItaW5uZXIiPgogICAgPHNwYW4gY2xhc3M9ImxvZ28tbWFpbiI+Q0FOU0xJTSBTQ0FOTkVSPC9zcGFuPgogICAgPHNwYW4gY2xhc3M9InRpbWVzdGFtcCI+PHNwYW4gY2xhc3M9ImxpdmUtZG90Ij48L3NwYW4+JSVUSU1FU1RBTVAlJTwvc3Bhbj4KICAgIDxidXR0b24gb25jbGljaz0ib3BlbkVkaXRMaXN0KCkiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4zKTtjb2xvcjojNjBhNWZhO3BhZGRpbmc6NXB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1mYW1pbHk6aW5oZXJpdCI+4pyP77iPIExpc3RleWkgRMO8emVubGU8L2J1dHRvbj4KICA8L2Rpdj4KPC9kaXY+CjxkaXYgY2xhc3M9Im5hdiI+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIGFjdGl2ZSIgb25jbGljaz0ic2V0VGFiKCdkYXNoYm9hcmQnLHRoaXMpIj7wn4+gIERhc2hib2FyZDwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdhbGwnLHRoaXMpIj7wn5OKIEhpc3NlbGVyPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIHBvcnQiIG9uY2xpY2s9InNldFRhYigncG9ydCcsdGhpcykiPvCfkrwgUG9ydGbDtnnDvG08L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignZWFybmluZ3MnLHRoaXMpIj7wn5OFIEVhcm5pbmdzPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2hhZnRhbGlrJyx0aGlzKSI+8J+TiCBIYWZ0YWzEsWs8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignc2NyZWVuZXInLHRoaXMpIj7wn5SNIFNjcmVlbmVyPC9idXR0b24+CiAgICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYigndmFsdWF0aW9uJyx0aGlzKSI+8J+SjiBEZcSfZXJsZW1lPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2RpcmVjdGlvbicsdGhpcykiPvCfk4ogUGl5YXNhIFnDtm7DvDwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdtaW5lcnZpbmknLHRoaXMpIj7wn46vIE1pbmVydmluaTwvYnV0dG9uPgo8L2Rpdj4KPGRpdiBjbGFzcz0idGYtcm93IiBpZD0idGZSb3ciIHN0eWxlPSJkaXNwbGF5Om5vbmUiPgogIDxidXR0b24gY2xhc3M9InRmLWJ0biBhY3RpdmUiIGRhdGEtdGY9IjFkIiBvbmNsaWNrPSJzZXRUZignMWQnLHRoaXMpIj4xRzwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRmLWJ0biBzdGFyIiBkYXRhLXRmPSIxd2siIG9uY2xpY2s9InNldFRmKCcxd2snLHRoaXMpIj4xSDwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRmLWJ0biIgZGF0YS10Zj0iMW1vIiBvbmNsaWNrPSJzZXRUZignMW1vJyx0aGlzKSI+MUE8L2J1dHRvbj4KICA8c3BhbiBjbGFzcz0idGYtaGludCI+Q0FOU0xJTSDDtm5lcmlsZW46IDFHICsgMUg8L3NwYW4+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJzdGF0cyIgaWQ9InN0YXRzIj48L2Rpdj4KPGRpdiBjbGFzcz0ibWFpbiI+PGRpdiBjbGFzcz0iZ3JpZCIgaWQ9ImdyaWQiPjwvZGl2PjwvZGl2Pgo8ZGl2IGNsYXNzPSJvdmVybGF5IiBpZD0ib3ZlcmxheSIgb25jbGljaz0iY2xvc2VNKGV2ZW50KSI+CiAgPGRpdiBjbGFzcz0ibW9kYWwiIGlkPSJtb2RhbCI+PC9kaXY+CjwvZGl2PgoKPGRpdiBjbGFzcz0ibWluZm8tcG9wdXAiIGlkPSJlZGl0UG9wdXAiIG9uY2xpY2s9ImNsb3NlRWRpdFBvcHVwKGV2ZW50KSI+CiAgPGRpdiBjbGFzcz0ibWluZm8tbW9kYWwiIHN0eWxlPSJwb3NpdGlvbjpyZWxhdGl2ZTttYXgtd2lkdGg6NTYwcHgiIGlkPSJlZGl0TW9kYWwiPgogICAgPGJ1dHRvbiBjbGFzcz0ibWluZm8tY2xvc2UiIG9uY2xpY2s9ImNsb3NlRWRpdFBvcHVwKCkiPuKclTwvYnV0dG9uPgogICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4Ij7inI/vuI8gTGlzdGV5aSBEw7x6ZW5sZTwvZGl2PgogICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MTZweCI+R2l0SHViIEFQSSBrZXkgZ2VyZWtsaSDigJQgZGXEn2nFn2lrbGlrbGVyIGFuxLFuZGEga2F5ZGVkaWxpcjwvZGl2PgogICAgPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnIgMWZyO2dhcDoxNnB4O21hcmdpbi1ib3R0b206MTZweCI+CiAgICAgIDxkaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPvCfk4sgV2F0Y2hsaXN0PC9kaXY+CiAgICAgICAgPGRpdiBpZD0id2F0Y2hsaXN0RWRpdG9yIj48L2Rpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjZweDttYXJnaW4tdG9wOjhweCI+CiAgICAgICAgICA8aW5wdXQgaWQ9Im5ld1dhdGNoVGlja2VyIiBwbGFjZWhvbGRlcj0iSGlzc2UgZWtsZSAoVFNMQSkiIHN0eWxlPSJmbGV4OjE7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS10ZXh0KTtwYWRkaW5nOjZweCAxMHB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2ZvbnQtZmFtaWx5OmluaGVyaXQ7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlIi8+CiAgICAgICAgICA8YnV0dG9uIG9uY2xpY2s9ImFkZFRpY2tlcignd2F0Y2gnKSIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjMpO2NvbG9yOnZhcigtLWdyZWVuKTtwYWRkaW5nOjZweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2N1cnNvcjpwb2ludGVyIj4rIEVrbGU8L2J1dHRvbj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CiAgICAgIDxkaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPvCfkrwgUG9ydGbDtnk8L2Rpdj4KICAgICAgICA8ZGl2IGlkPSJwb3J0Zm9saW9FZGl0b3IiPjwvZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6NnB4O21hcmdpbi10b3A6OHB4Ij4KICAgICAgICAgIDxpbnB1dCBpZD0ibmV3UG9ydFRpY2tlciIgcGxhY2Vob2xkZXI9Ikhpc3NlIGVrbGUgKEFBUEwpIiBzdHlsZT0iZmxleDoxO2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tdGV4dCk7cGFkZGluZzo2cHggMTBweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtmb250LWZhbWlseTppbmhlcml0O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZSIvPgogICAgICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJhZGRUaWNrZXIoJ3BvcnQnKSIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjMpO2NvbG9yOnZhcigtLWdyZWVuKTtwYWRkaW5nOjZweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2N1cnNvcjpwb2ludGVyIj4rIEVrbGU8L2J1dHRvbj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CiAgICA8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxMnB4O21hcmdpbi1ib3R0b206MTRweDtmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1ncmVlbikiPuKchSBEZcSfacWfaWtsaWtsZXIga2F5ZGVkaWxpbmNlIGJpciBzb25yYWtpIENvbGFiIMOnYWzEscWfdMSxcm1hc8SxbmRhIGFrdGlmIG9sdXIuPC9kaXY+CjxkaXYgc3R5bGU9Im1hcmdpbi1ib3R0b206MTJweCI+CiAgICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjVweCI+R2l0SHViIFRva2VuIChiaXIga2V6IGdpciwgdGFyYXlpY2kgaGF0aXJsYXlhY2FrKTwvZGl2PgogICAgICA8aW5wdXQgaWQ9ImdoVG9rZW5JbnB1dCIgcGxhY2Vob2xkZXI9ImdocF8uLi4iIHN0eWxlPSJ3aWR0aDoxMDAlO2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tdGV4dCk7cGFkZGluZzo4cHggMTBweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTFweDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiLz4KICAgIDwvZGl2PgogICAgPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo4cHgiPgogICAgICA8YnV0dG9uIG9uY2xpY2s9InNhdmVMaXN0VG9HaXRodWIoKSIgc3R5bGU9ImZsZXg6MTtiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6OHB4O2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMDtjdXJzb3I6cG9pbnRlciI+8J+SviBHaXRIdWJhIEtheWRldDwvYnV0dG9uPgogICAgICA8YnV0dG9uIG9uY2xpY2s9ImNsb3NlRWRpdFBvcHVwKCkiIHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTtwYWRkaW5nOjEwcHggMTZweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTNweDtjdXJzb3I6cG9pbnRlciI+xLBwdGFsPC9idXR0b24+CiAgICA8L2Rpdj4KICAgIDxkaXYgaWQ9ImVkaXRTdGF0dXMiIHN0eWxlPSJtYXJnaW4tdG9wOjEwcHg7Zm9udC1zaXplOjEycHg7dGV4dC1hbGlnbjpjZW50ZXIiPjwvZGl2PgogIDwvZGl2Pgo8L2Rpdj4KCjxkaXYgY2xhc3M9Im1pbmZvLXBvcHVwIiBpZD0ibWluZm9Qb3B1cCIgb25jbGljaz0iY2xvc2VJbmZvUG9wdXAoZXZlbnQpIj4KICA8ZGl2IGNsYXNzPSJtaW5mby1tb2RhbCIgaWQ9Im1pbmZvTW9kYWwiPgogICAgPGJ1dHRvbiBjbGFzcz0ibWluZm8tY2xvc2UiIG9uY2xpY2s9ImNsb3NlSW5mb1BvcHVwKCkiPuKclTwvYnV0dG9uPgogICAgPGRpdiBpZD0ibWluZm9Db250ZW50Ij48L2Rpdj4KICA8L2Rpdj4KPC9kaXY+CgoKPHNjcmlwdD4KdmFyIE1FVFJJQ1MgPSB7CiAgLy8gVEVLTsSwSwogICdSU0knOiB7CiAgICB0aXRsZTogJ1JTSSAoR8O2cmVjZWxpIEfDvMOnIEVuZGVrc2kpJywKICAgIGRlc2M6ICdIaXNzZW5pbiBhxZ/EsXLEsSBhbMSxbSB2ZXlhIGHFn8SxcsSxIHNhdMSxbSBiw7ZsZ2VzaW5kZSBvbHVwIG9sbWFkxLHEn8SxbsSxIGfDtnN0ZXJpci4gMTQgZ8O8bmzDvGsgZml5YXQgaGFyZWtldGxlcmluaSBhbmFsaXogZWRlci4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonQcWfxLFyxLEgU2F0xLFtJyxtaW46MCxtYXg6MzAsY29sb3I6J2dyZWVuJyxkZXNjOidGxLFyc2F0IGLDtmxnZXNpIOKAlCBmaXlhdCDDp29rIGTDvMWfbcO8xZ8nfSwKICAgICAge2xhYmVsOidOb3JtYWwnLG1pbjozMCxtYXg6NzAsY29sb3I6J3llbGxvdycsZGVzYzonTsO2dHIgYsO2bGdlJ30sCiAgICAgIHtsYWJlbDonQcWfxLFyxLEgQWzEsW0nLG1pbjo3MCxtYXg6MTAwLGNvbG9yOidyZWQnLGRlc2M6J0Rpa2thdCDigJQgZml5YXQgw6dvayB5w7xrc2VsbWnFnyd9CiAgICBdLAogICAgY2Fuc2xpbTogJ04ga3JpdGVyaSBpbGUgaWxnaWxpIOKAlCBmaXlhdCBtb21lbnR1bXUnCiAgfSwKICAnU01BNTAnOiB7CiAgICB0aXRsZTogJ1NNQSA1MCAoNTAgR8O8bmzDvGsgSGFyZWtldGxpIE9ydGFsYW1hKScsCiAgICBkZXNjOiAnU29uIDUwIGfDvG7DvG4gb3J0YWxhbWEga2FwYW7EscWfIGZpeWF0xLEuIEvEsXNhLW9ydGEgdmFkZWxpIHRyZW5kIGfDtnN0ZXJnZXNpLicsCiAgICBzb3VyY2U6ICdUZWtuaWsgQW5hbGl6JywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOifDnHplcmluZGUnLGNvbG9yOidncmVlbicsZGVzYzonS8Sxc2EgdmFkZWxpIHRyZW5kIHBveml0aWYg4oCUIGfDvMOnbMO8IHNpbnlhbCd9LAogICAgICB7bGFiZWw6J0FsdMSxbmRhJyxjb2xvcjoncmVkJyxkZXNjOidLxLFzYSB2YWRlbGkgdHJlbmQgbmVnYXRpZid9CiAgICBdLAogICAgY2Fuc2xpbTogJ00ga3JpdGVyaSDigJQgcGl5YXNhIHRyZW5kaScKICB9LAogICdTTUEyMDAnOiB7CiAgICB0aXRsZTogJ1NNQSAyMDAgKDIwMCBHw7xubMO8ayBIYXJla2V0bGkgT3J0YWxhbWEpJywKICAgIGRlc2M6ICdTb24gMjAwIGfDvG7DvG4gb3J0YWxhbWEga2FwYW7EscWfIGZpeWF0xLEuIFV6dW4gdmFkZWxpIHRyZW5kIGfDtnN0ZXJnZXNpLiBFbiDDtm5lbWxpIHRla25payBzZXZpeWUuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J8OcemVyaW5kZScsY29sb3I6J2dyZWVuJyxkZXNjOidVenVuIHZhZGVsaSBib8SfYSB0cmVuZGluZGUg4oCUIENBTlNMSU0gacOnaW4gxZ9hcnQnfSwKICAgICAge2xhYmVsOidBbHTEsW5kYScsY29sb3I6J3JlZCcsZGVzYzonVXp1biB2YWRlbGkgYXnEsSB0cmVuZGluZGUg4oCUIENBTlNMSU0gacOnaW4gZ2lybWUnfQogICAgXSwKICAgIGNhbnNsaW06ICdNIGtyaXRlcmkg4oCUIHpvcnVubHUga2/Fn3VsJwogIH0sCiAgJzUyVyc6IHsKICAgIHRpdGxlOiAnNTIgSGFmdGFsxLFrIFBvemlzeW9uJywKICAgIGRlc2M6ICdIaXNzZW5pbiBzb24gMSB5xLFsZGFraSBmaXlhdCBhcmFsxLHEn8SxbmRhIG5lcmVkZSBvbGR1xJ91bnUgZ8O2c3RlcmlyLiAwPXnEsWzEsW4gZGliaSwgMTAwPXnEsWzEsW4gemlydmVzaS4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonMC0zMCUnLGNvbG9yOidncmVlbicsZGVzYzonWcSxbMSxbiBkaWJpbmUgeWFrxLFuIOKAlCBwb3RhbnNpeWVsIGbEsXJzYXQnfSwKICAgICAge2xhYmVsOiczMC03MCUnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGEgYsO2bGdlIOKAlCBuw7Z0cid9LAogICAgICB7bGFiZWw6JzcwLTg1JScsY29sb3I6J3llbGxvdycsZGVzYzonWmlydmV5ZSB5YWtsYcWfxLF5b3Ig4oCUIGl6bGUnfSwKICAgICAge2xhYmVsOic4NS0xMDAlJyxjb2xvcjoncmVkJyxkZXNjOidaaXJ2ZXllIMOnb2sgeWFrxLFuIOKAlCBkaWtrYXRsaSBnaXInfQogICAgXSwKICAgIGNhbnNsaW06ICdOIGtyaXRlcmkg4oCUIHllbmkgemlydmUga8SxcsSxbMSxbcSxIGnDp2luIGlkZWFsIGLDtmxnZSAlODUtMTAwJwogIH0sCiAgJ0hhY2ltJzogewogICAgdGl0bGU6ICdIYWNpbSAoxLDFn2xlbSBNaWt0YXLEsSknLAogICAgZGVzYzogJ0fDvG5sw7xrIGnFn2xlbSBoYWNtaW5pbiBzb24gMjAgZ8O8bmzDvGsgb3J0YWxhbWF5YSBvcmFuxLEuIEfDvMOnbMO8IGhhcmVrZXRsZXJpbiBoYWNpbWxlIGRlc3Rla2xlbm1lc2kgZ2VyZWtpci4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonWcO8a3NlayAoPjEuM3gpJyxjb2xvcjonZ3JlZW4nLGRlc2M6J0t1cnVtc2FsIGlsZ2kgdmFyIOKAlCBnw7zDp2zDvCBzaW55YWwnfSwKICAgICAge2xhYmVsOidOb3JtYWwgKDAuNy0xLjN4KScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YWxhbWEgaWxnaSd9LAogICAgICB7bGFiZWw6J0TDvMWfw7xrICg8MC43eCknLGNvbG9yOidyZWQnLGRlc2M6J8SwbGdpIGF6YWxtxLHFnyDigJQgZGlra2F0J30KICAgIF0sCiAgICBjYW5zbGltOiAnUyBrcml0ZXJpIOKAlCBhcnovdGFsZXAgZGVuZ2VzaScKICB9LAogIC8vIFRFTUVMCiAgJ0ZvcndhcmRQRSc6IHsKICAgIHRpdGxlOiAnRm9yd2FyZCBQL0UgKMSwbGVyaXllIETDtm7DvGsgRml5YXQvS2F6YW7DpyknLAogICAgZGVzYzogJ1NpcmtldGluIG9udW3DvHpkZWtpIDEyIGF5ZGFraSB0YWhtaW5pIGthemFuY2luYSBnb3JlIGZpeWF0aS4gVHJhaWxpbmcgUC9FIGFyYWNpbmEgZ29yZSBnZWxlY2VnZSBvZGFrbGlkaWdpIGljaW4gZGFoYSBvbmVtbGlkaXIuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgQW5hbGlzdCB0YWhtaW5pJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdBbmFsaXN0IHRhaG1pbmxlcmluZSBkYXlhbsSxciwgeWFuxLFsdMSxY8SxIG9sYWJpbGlyJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzwxNScsY29sb3I6J2dyZWVuJyxkZXNjOidVY3V6IOKAlCBiw7x5w7xtZSBiZWtsZW50aXNpIGTDvMWfw7xrIHZleWEgaGlzc2UgZGXEn2VyIGFsdMSxbmRhJ30sCiAgICAgIHtsYWJlbDonMTUtMjUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwg4oCUIMOnb8SfdSBzZWt0w7ZyIGnDp2luIG5vcm1hbCd9LAogICAgICB7bGFiZWw6JzI1LTQwJyxjb2xvcjoneWVsbG93JyxkZXNjOidQYWhhbMSxIGFtYSBiw7x5w7xtZSBwcmltaSDDtmRlbml5b3InfSwKICAgICAge2xhYmVsOic+NDAnLGNvbG9yOidyZWQnLGRlc2M6J8OHb2sgcGFoYWzEsSDigJQgecO8a3NlayBiw7x5w7xtZSBiZWtsZW50aXNpIGZpeWF0bGFubcSxxZ8nfQogICAgXSwKICAgIGNhbnNsaW06ICdDIHZlIEEga3JpdGVybGVyaSBpbGUgaWxnaWxpJwogIH0sCiAgJ1BFRyc6IHsKICAgIHRpdGxlOiAnUEVHIE9yYW7EsSAoRml5YXQvS2F6YW7Dpy9Cw7x5w7xtZSknLAogICAgZGVzYzogJ1AvRSBvcmFuxLFuxLEgYsO8ecO8bWUgaMSxesSxeWxhIGthcsWfxLFsYcWfdMSxcsSxci4gQsO8ecO8eWVuIMWfaXJrZXRsZXIgaWNpbiBQL0VcJ2RlbiBkYWhhIGRvxJ9ydSBkZcSfZXJsZW1lIMO2bMOnw7x0w7wuIFBFRz0xIGFkaWwgZGXEn2VyIGthYnVsIGVkaWxpci4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBBbmFsaXN0IHRhaG1pbmknLAogICAgcmVsaWFiaWxpdHk6ICdtZWRpdW0nLAogICAgd2FybmluZzogJ0FuYWxpc3QgYsO8ecO8bWUgdGFobWlubGVyaW5lIGRheWFuxLFyJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzwxLjAnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgYsO8ecO8bWVzaW5lIGfDtnJlIGRlxJ9lciBhbHTEsW5kYSd9LAogICAgICB7bGFiZWw6JzEuMC0xLjUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwg4oCUIGFkaWwgZml5YXQgY2l2YXLEsSd9LAogICAgICB7bGFiZWw6JzEuNS0yLjAnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J0JpcmF6IHBhaGFsxLEnfSwKICAgICAge2xhYmVsOic+Mi4wJyxjb2xvcjoncmVkJyxkZXNjOidQYWhhbMSxIOKAlCBkaWtrYXRsaSBvbCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQgYsO8ecO8bWUga2FsaXRlc2knCiAgfSwKICAnRVBTR3Jvd3RoJzogewogICAgdGl0bGU6ICdFUFMgQsO8ecO8bWVzaSAow4dleXJla2xpaywgWW9ZKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIGhpc3NlIGJhxZ/EsW5hIGthemFuY8SxbsSxbiBnZcOnZW4gecSxbMSxbiBheW7EsSDDp2V5cmXEn2luZSBnw7ZyZSBhcnTEscWfxLEuIENBTlNMSU1cJ2luIGVuIGtyaXRpayBrcml0ZXJpLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUyNScsY29sb3I6J2dyZWVuJyxkZXNjOidHw7zDp2zDvCBiw7x5w7xtZSDigJQgQ0FOU0xJTSBrcml0ZXJpIGthcsWfxLFsYW5kxLEnfSwKICAgICAge2xhYmVsOiclMTUtMjUnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSBiw7x5w7xtZSd9LAogICAgICB7bGFiZWw6JyUwLTE1Jyxjb2xvcjoneWVsbG93JyxkZXNjOidaYXnEsWYgYsO8ecO8bWUnfSwKICAgICAge2xhYmVsOic8MCcsY29sb3I6J3JlZCcsZGVzYzonS2F6YW7DpyBkw7zFn8O8eW9yIOKAlCBkaWtrYXQnfQogICAgXSwKICAgIGNhbnNsaW06ICdDIGtyaXRlcmkg4oCUIGVuIGtyaXRpayBrcml0ZXIsIG1pbmltdW0gJTI1IG9sbWFsxLEnCiAgfSwKICAnUmV2R3Jvd3RoJzogewogICAgdGl0bGU6ICdHZWxpciBCw7x5w7xtZXNpIChZb1kpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gc2F0xLHFny9nZWxpcmluaW4gZ2XDp2VuIHnEsWxhIGfDtnJlIGFydMSxxZ/EsS4gRVBTIGLDvHnDvG1lc2luaSBkZXN0ZWtsZW1lc2kgZ2VyZWtpciDigJQgc2FkZWNlIG1hbGl5ZXQga2VzaW50aXNpeWxlIGLDvHnDvG1lIHPDvHJkw7xyw7xsZWJpbGlyIGRlxJ9pbC4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMTUnLGNvbG9yOidncmVlbicsZGVzYzonR8O8w6dsw7wgZ2VsaXIgYsO8ecO8bWVzaSd9LAogICAgICB7bGFiZWw6JyU1LTE1Jyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIGLDvHnDvG1lJ30sCiAgICAgIHtsYWJlbDonPDUnLGNvbG9yOidyZWQnLGRlc2M6J0dlbGlyIGLDvHnDvG1lc2kgemF5xLFmJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQSBrcml0ZXJpIOKAlCBzw7xyZMO8csO8bGViaWxpciBiw7x5w7xtZSBpw6dpbiDFn2FydCcKICB9LAogICdOZXRNYXJnaW4nOiB7CiAgICB0aXRsZTogJ05ldCBNYXJqaW4nLAogICAgZGVzYzogJ0hlciAxJCBnZWxpcmRlbiBuZSBrYWRhciBuZXQga8OiciBrYWxkxLHEn8SxbsSxIGfDtnN0ZXJpci4gWcO8a3NlayBtYXJqaW4gPSBnw7zDp2zDvCBpxZ8gbW9kZWxpLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUyMCcsY29sb3I6J2dyZWVuJyxkZXNjOifDh29rIGfDvMOnbMO8IGvDonJsxLFsxLFrJ30sCiAgICAgIHtsYWJlbDonJTEwLTIwJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWkga8OicmzEsWzEsWsnfSwKICAgICAge2xhYmVsOiclNS0xMCcsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSBrw6JybMSxbMSxayd9LAogICAgICB7bGFiZWw6Jzw1Jyxjb2xvcjoncmVkJyxkZXNjOidaYXnEsWYga8OicmzEsWzEsWsnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIGvDonJsxLFsxLFrIGthbGl0ZXNpJwogIH0sCiAgJ1JPRSc6IHsKICAgIHRpdGxlOiAnUk9FICjDlnprYXluYWsgS8OicmzEsWzEscSfxLEpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gw7Z6IHNlcm1heWVzaXlsZSBuZSBrYWRhciBrw6JyIGV0dGnEn2luaSBnw7ZzdGVyaXIuIFnDvGtzZWsgUk9FID0gc2VybWF5ZXlpIHZlcmltbGkga3VsbGFuxLF5b3IuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgR2Vyw6dlayB2ZXJpJywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic+JTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8OHb2sgZ8O8w6dsw7wg4oCUIENBTlNMSU0gaWRlYWwgc2V2aXllc2knfSwKICAgICAge2xhYmVsOiclMTUtMjUnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSd9LAogICAgICB7bGFiZWw6JyU4LTE1Jyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhJ30sCiAgICAgIHtsYWJlbDonPDgnLGNvbG9yOidyZWQnLGRlc2M6J1phecSxZid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQgbWluaW11bSAlMTcgb2xtYWzEsScKICB9LAogICdHcm9zc01hcmdpbic6IHsKICAgIHRpdGxlOiAnQnLDvHQgTWFyamluJywKICAgIGRlc2M6ICdTYXTEscWfIGdlbGlyaW5kZW4gw7xyZXRpbSBtYWxpeWV0aSBkw7zFn8O8bGTDvGt0ZW4gc29ucmEga2FsYW4gb3Jhbi4gU2VrdMO2cmUgZ8O2cmUgZGXEn2nFn2lyLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiU1MCcsY29sb3I6J2dyZWVuJyxkZXNjOifDh29rIGfDvMOnbMO8IOKAlCB5YXrEsWzEsW0vU2FhUyBzZXZpeWVzaSd9LAogICAgICB7bGFiZWw6JyUzMC01MCcsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpJ30sCiAgICAgIHtsYWJlbDonJTE1LTMwJyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIOKAlCBkb25hbsSxbS95YXLEsSBpbGV0a2VuIG5vcm1hbCd9LAogICAgICB7bGFiZWw6JzwxNScsY29sb3I6J3JlZCcsZGVzYzonRMO8xZ/DvGsgbWFyamluJ30KICAgIF0sCiAgICBjYW5zbGltOiAnS8OicmzEsWzEsWsga2FsaXRlc2kgZ8O2c3Rlcmdlc2knCiAgfSwKICAvLyBHxLBSxLDFngogICdFbnRyeVNjb3JlJzogewogICAgdGl0bGU6ICdHaXJpxZ8gS2FsaXRlc2kgU2tvcnUnLAogICAgZGVzYzogJ1JTSSwgU01BIHBvemlzeW9udSwgUC9FLCBQRUcgdmUgRVBTIGLDvHnDvG1lc2luaSBiaXJsZcWfdGlyZW4gYmlsZcWfaWsgc2tvci4gMC0xMDAgYXJhc8SxLicsCiAgICBzb3VyY2U6ICdCaXppbSBoZXNhcGxhbWEnLAogICAgcmVsaWFiaWxpdHk6ICdsb3cnLAogICAgd2FybmluZzogJ0JVIFVZR1VMQU1BIFRBUkFGSU5EQU4gSEVTQVBMQU5BTiBLQUJBIFRBSE3EsE5ExLBSLiBZYXTEsXLEsW0ga2FyYXLEsSBpw6dpbiB0ZWsgYmHFn8SxbmEga3VsbGFubWEuJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jzc1LTEwMCcsY29sb3I6J2dyZWVuJyxkZXNjOidVY3V6IOKAlCBpZGVhbCBnaXJpxZ8gYsO2bGdlc2knfSwKICAgICAge2xhYmVsOic2MC03NScsY29sb3I6J2dyZWVuJyxkZXNjOidNYWt1bCBmaXlhdCd9LAogICAgICB7bGFiZWw6JzQ1LTYwJyxjb2xvcjoneWVsbG93JyxkZXNjOidOw7Z0cid9LAogICAgICB7bGFiZWw6JzMwLTQ1Jyxjb2xvcjoncmVkJyxkZXNjOidQYWhhbMSxIOKAlCBiZWtsZSd9LAogICAgICB7bGFiZWw6JzAtMzAnLGNvbG9yOidyZWQnLGRlc2M6J8OHb2sgcGFoYWzEsSDigJQgZ2lybWUnfQogICAgXSwKICAgIGNhbnNsaW06ICdUw7xtIGtyaXRlcmxlciBiaWxlxZ9pbWknCiAgfSwKICAnUlInOiB7CiAgICB0aXRsZTogJ1Jpc2svw5Zkw7xsIE9yYW7EsSAoUi9SKScsCiAgICBkZXNjOiAnUG90YW5zaXllbCBrYXphbmPEsW4gcmlza2Ugb3JhbsSxLiAxOjIgZGVtZWsgMSQgcmlza2Uga2FyxZ/EsSAyJCBrYXphbsOnIHBvdGFuc2l5ZWxpIHZhciBkZW1lay4nLAogICAgc291cmNlOiAnQml6aW0gaGVzYXBsYW1hJywKICAgIHJlbGlhYmlsaXR5OiAnbG93JywKICAgIHdhcm5pbmc6ICdHaXJpxZ8vaGVkZWYvc3RvcCBzZXZpeWVsZXJpIGZvcm3DvGwgYmF6bMSxIGthYmEgdGFobWluZGlyJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzE6MysnLGNvbG9yOidncmVlbicsZGVzYzonTcO8a2VtbWVsIOKAlCBnw7zDp2zDvCBnaXJpxZ8gc2lueWFsaSd9LAogICAgICB7bGFiZWw6JzE6MicsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpIOKAlCBtaW5pbXVtIGthYnVsIGVkaWxlYmlsaXInfSwKICAgICAge2xhYmVsOicxOjEnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1phecSxZid9LAogICAgICB7bGFiZWw6JzwxOjEnLGNvbG9yOidyZWQnLGRlc2M6J1Jpc2sga2F6YW7Dp3RhbiBiw7x5w7xrIOKAlCBnaXJtZSd9CiAgICBdLAogICAgY2Fuc2xpbTogJ1Jpc2sgecO2bmV0aW1pJwogIH0sCiAgLy8gRUFSTklOR1MKICAnRWFybmluZ3NEYXRlJzogewogICAgdGl0bGU6ICdSYXBvciBUYXJpaGkgKEVhcm5pbmdzIERhdGUpJywKICAgIGRlc2M6ICfFnmlya2V0aW4gw6dleXJlayBmaW5hbnNhbCBzb251w6dsYXLEsW7EsSBhw6fEsWtsYXlhY2HEn8SxIHRhcmloLiBSYXBvciDDtm5jZXNpIHZlIHNvbnJhc8SxIGZpeWF0IHNlcnQgaGFyZWtldCBlZGViaWxpci4nLAogICAgc291cmNlOiAneWZpbmFuY2Ug4oCUIGJhemVuIGhhdGFsxLEgb2xhYmlsaXInLAogICAgcmVsaWFiaWxpdHk6ICdtZWRpdW0nLAogICAgd2FybmluZzogJ1RhcmlobGVyaSByZXNtaSBJUiBzYXlmYXPEsW5kYW4gZG/En3J1bGF5xLFuJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzcgZ8O8biBpw6dpbmRlJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHlha8SxbiDigJQgcG96aXN5b24gYcOnbWFrIHJpc2tsaSd9LAogICAgICB7bGFiZWw6JzgtMTQgZ8O8bicsY29sb3I6J3llbGxvdycsZGVzYzonWWFrxLFuIOKAlCBkaWtrYXRsaSBvbCd9LAogICAgICB7bGFiZWw6JzE0KyBnw7xuJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1lldGVybGkgc8O8cmUgdmFyJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQyBrcml0ZXJpIOKAlCDDp2V5cmVrIHJhcG9yIGthbGl0ZXNpJwogIH0sCiAgJ0F2Z01vdmUnOiB7CiAgICB0aXRsZTogJ09ydGFsYW1hIFJhcG9yIEhhcmVrZXRpJywKICAgIGRlc2M6ICdTb24gNCDDp2V5cmVrIHJhcG9ydW5kYSwgcmFwb3IgZ8O8bsO8IHZlIGVydGVzaSBnw7xuIGZpeWF0xLFuIG9ydGFsYW1hIG5lIGthZGFyIGhhcmVrZXQgZXR0acSfaS4nLAogICAgc291cmNlOiAnQml6aW0gaGVzYXBsYW1hJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J1Bveml0aWYgKD4lNSknLGNvbG9yOidncmVlbicsZGVzYzonxZ5pcmtldCBnZW5lbGxpa2xlIGJla2xlbnRpeWkgYcWfxLF5b3InfSwKICAgICAge2xhYmVsOidOw7Z0ciAoJTAtNSknLGNvbG9yOid5ZWxsb3cnLGRlc2M6J0thcsSxxZ/EsWsgZ2XDp21pxZ8nfSwKICAgICAge2xhYmVsOidOZWdhdGlmJyxjb2xvcjoncmVkJyxkZXNjOidSYXBvciBkw7ZuZW1pbmRlIGZpeWF0IGdlbmVsbGlrbGUgZMO8xZ/DvHlvciDigJQgZGlra2F0J30KICAgIF0sCiAgICBjYW5zbGltOiAnQyBrcml0ZXJpIOKAlCBrYXphbsOnIHPDvHJwcml6aSBnZcOnbWnFn2knCiAgfQp9OwoKZnVuY3Rpb24gc2hvd0luZm8oa2V5LGV2ZW50KXsKICBpZihldmVudCkgZXZlbnQuc3RvcFByb3BhZ2F0aW9uKCk7CiAgdmFyIG09TUVUUklDU1trZXldOyBpZighbSkgcmV0dXJuOwogIHZhciByZWxMYWJlbD1tLnJlbGlhYmlsaXR5PT09ImhpZ2giPyJHw7x2ZW5pbGlyIjptLnJlbGlhYmlsaXR5PT09Im1lZGl1bSI/Ik9ydGEgR8O8dmVuaWxpciI6IkthYmEgVGFobWluIjsKICB2YXIgaD0nPGRpdiBjbGFzcz0ibWluZm8tdGl0bGUiPicrbS50aXRsZSsnPC9kaXY+JzsKICBoKz0nPGRpdiBjbGFzcz0ibWluZm8tc291cmNlIj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj4nK20uc291cmNlKyc8L3NwYW4+PHNwYW4gY2xhc3M9Im1pbmZvLXJlbCAnK20ucmVsaWFiaWxpdHkrJyI+JytyZWxMYWJlbCsnPC9zcGFuPjwvZGl2Pic7CiAgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLWRlc2MiPicrbS5kZXNjKyc8L2Rpdj4nOwogIGlmKG0ud2FybmluZykgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLXdhcm5pbmciPuKaoO+4jyAnK20ud2FybmluZysnPC9kaXY+JzsKICBpZihtLnJhbmdlcyYmbS5yYW5nZXMubGVuZ3RoKXsKICAgIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby1yYW5nZXMiPjxkaXYgY2xhc3M9Im1pbmZvLXJhbmdlLXRpdGxlIj5SZWZlcmFucyBEZWdlcmxlcjwvZGl2Pic7CiAgICBtLnJhbmdlcy5mb3JFYWNoKGZ1bmN0aW9uKHIpe3ZhciBkYz1yLmNvbG9yPT09ImdyZWVuIj8iIzEwYjk4MSI6ci5jb2xvcj09PSJyZWQiPyIjZWY0NDQ0IjoiI2Y1OWUwYiI7aCs9JzxkaXYgY2xhc3M9Im1pbmZvLXJhbmdlIj48ZGl2IGNsYXNzPSJtaW5mby1yYW5nZS1kb3QiIHN0eWxlPSJiYWNrZ3JvdW5kOicrZGMrJyI+PC9kaXY+PGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtmb250LXdlaWdodDo2MDA7Y29sb3I6JytkYysnIj4nK3IubGFiZWwrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytyLmRlc2MrJzwvZGl2PjwvZGl2PjwvZGl2Pic7fSk7CiAgICBoKz0nPC9kaXY+JzsKICB9CiAgaWYobS5jYW5zbGltKSBoKz0nPGRpdiBjbGFzcz0ibWluZm8tY2Fuc2xpbSI+8J+TiiBDQU5TTElNOiAnK20uY2Fuc2xpbSsnPC9kaXY+JzsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWluZm9Db250ZW50IikuaW5uZXJIVE1MPWg7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvUG9wdXAiKS5jbGFzc0xpc3QuYWRkKCJvcGVuIik7Cn0KZnVuY3Rpb24gY2xvc2VJbmZvUG9wdXAoZSl7aWYoIWV8fGUudGFyZ2V0PT09ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvUG9wdXAiKSl7ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvUG9wdXAiKS5jbGFzc0xpc3QucmVtb3ZlKCJvcGVuIik7fX0KCjwvc2NyaXB0Pgo8L3NjcmlwdD4KPHNjcmlwdD4KdmFyIFRGX0RBVEE9JSVURl9EQVRBJSU7CnZhciBQT1JUPSUlUE9SVCUlOwp2YXIgRUFSTklOR1NfREFUQT0lJUVBUk5JTkdTX0RBVEElJTsKdmFyIE1BUktFVF9EQVRBPSUlTUFSS0VUX0RBVEElJTsKdmFyIE5FV1NfREFUQT0lJU5FV1NfREFUQSUlOwp2YXIgQUlfREFUQT0lJUFJX0RBVEElJTsKdmFyIFdFRUtMWV9EQVRBPSUlV0VFS0xZX0RBVEElJTsKdmFyIFNDUkVFTkVSX0RBVEE9JSVTQ1JFRU5FUl9EQVRBJSU7CnZhciBESVJFQ1RJT05fREFUQT0lJURJUkVDVElPTl9EQVRBJSU7CnZhciBjdXJUYWI9ImFsbCIsY3VyVGY9IjFkIixjdXJEYXRhPVRGX0RBVEFbIjFkIl0uc2xpY2UoKTsKdmFyIG1pbmlDaGFydHM9e30sbUNoYXJ0PW51bGw7CnZhciBTUz17CiAgIkdVQ0xVIEFMIjp7Ymc6InJnYmEoMTYsMTg1LDEyOSwuMTIpIixiZDoicmdiYSgxNiwxODUsMTI5LC4zNSkiLHR4OiIjMTBiOTgxIixhYzoiIzEwYjk4MSIsbGJsOiJHVUNMVSBBTCJ9LAogICJBTCI6e2JnOiJyZ2JhKDUyLDIxMSwxNTMsLjEpIixiZDoicmdiYSg1MiwyMTEsMTUzLC4zKSIsdHg6IiMzNGQzOTkiLGFjOiIjMzRkMzk5IixsYmw6IkFMIn0sCiAgIkRJS0tBVCI6e2JnOiJyZ2JhKDI0NSwxNTgsMTEsLjEpIixiZDoicmdiYSgyNDUsMTU4LDExLC4zKSIsdHg6IiNmNTllMGIiLGFjOiIjZjU5ZTBiIixsYmw6IkRJS0tBVCJ9LAogICJaQVlJRiI6e2JnOiJyZ2JhKDEwNywxMTQsMTI4LC4xKSIsYmQ6InJnYmEoMTA3LDExNCwxMjgsLjMpIix0eDoiIzljYTNhZiIsYWM6IiM2YjcyODAiLGxibDoiWkFZSUYifSwKICAiU0FUIjp7Ymc6InJnYmEoMjM5LDY4LDY4LC4xMikiLGJkOiJyZ2JhKDIzOSw2OCw2OCwuMzUpIix0eDoiI2VmNDQ0NCIsYWM6IiNlZjQ0NDQiLGxibDoiU0FUIn0KfTsKCmZ1bmN0aW9uIGliKGtleSxsYWJlbCl7CiAgcmV0dXJuIGxhYmVsKycgPHNwYW4gY2xhc3M9Im1pbmZvIiBvbmNsaWNrPSJzaG93SW5mbyhcJycra2V5KydcJyxldmVudCkiPj88L3NwYW4+JzsKfQoKZnVuY3Rpb24gc2V0VGFiKHQsZWwpewogIGN1clRhYj10OwogIGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoIi50YWIiKS5mb3JFYWNoKGZ1bmN0aW9uKGIpe2IuY2xhc3NMaXN0LnJlbW92ZSgiYWN0aXZlIik7fSk7CiAgZWwuY2xhc3NMaXN0LmFkZCgiYWN0aXZlIik7CiAgdmFyIHRmUm93PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0ZlJvdyIpOwogIGlmKHRmUm93KSB0ZlJvdy5zdHlsZS5kaXNwbGF5PSh0PT09ImRhc2hib2FyZCJ8fHQ9PT0iZWFybmluZ3MifHx0PT09InJ1dGluInx8dD09PSJoYWZ0YWxpayJ8fHQ9PT0ic2NyZWVuZXIifHx0PT09InZhbHVhdGlvbiJ8fHQ9PT0iZGlyZWN0aW9uIik/Im5vbmUiOiJmbGV4IjsKICBpZih0PT09ImRhc2hib2FyZCIpIHJlbmRlckRhc2hib2FyZCgpOwogIGVsc2UgaWYodD09PSJlYXJuaW5ncyIpIHJlbmRlckVhcm5pbmdzKCk7CiAgZWxzZSBpZih0PT09ImhhZnRhbGlrIikgcmVuZGVySGFmdGFsaWsoKTsKICBlbHNlIGlmKHQ9PT0ic2NyZWVuZXIiKSByZW5kZXJTY3JlZW5lcigpOwogIGVsc2UgaWYodD09PSJ2YWx1YXRpb24iKSByZW5kZXJWYWx1YXRpb24oKTsKICBlbHNlIGlmKHQ9PT0iZGlyZWN0aW9uIikgcmVuZGVyRGlyZWN0aW9uKCk7CiAgZWxzZSBpZih0PT09Im1pbmVydmluaSIpIHJlbmRlck1pbmVydmluaSgpOwogIGVsc2UgewogICAgdmFyIGc9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dyaWQnKTsKICAgIGlmKGcpe2cuc3R5bGUuZGlzcGxheT0nJztnLnN0eWxlLndpZHRoPScnO30KICAgIHJlbmRlckdyaWQoKTsKICB9Cn0KCmZ1bmN0aW9uIHNldFRmKHRmLGVsKXsKICBjdXJUZj10ZjsKICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIudGYtYnRuIikuZm9yRWFjaChmdW5jdGlvbihiKXtiLmNsYXNzTGlzdC50b2dnbGUoImFjdGl2ZSIsYi5kYXRhc2V0LnRmPT09dGYpO30pOwogIGN1ckRhdGE9KFRGX0RBVEFbdGZdfHxURl9EQVRBWyIxZCJdKS5zbGljZSgpOwogIHJlbmRlclN0YXRzKCk7CiAgcmVuZGVyR3JpZCgpOwp9CgpmdW5jdGlvbiBmaWx0ZXJlZCgpewogIHZhciBkPWN1ckRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pOwogIGlmKGN1clRhYj09PSJwb3J0IikgcmV0dXJuIGQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiBQT1JULmluY2x1ZGVzKHIudGlja2VyKTt9KTsKICBpZihjdXJUYWI9PT0iYnV5IikgcmV0dXJuIGQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSJHVUNMVSBBTCJ8fHIuc2lueWFsPT09IkFMIjt9KTsKICBpZihjdXJUYWI9PT0ic2VsbCIpIHJldHVybiBkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0iU0FUIjt9KTsKICByZXR1cm4gZDsKfQoKZnVuY3Rpb24gcmVuZGVyU3RhdHMoKXsKICB2YXIgZD1jdXJEYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KTsKICB2YXIgY250PXt9OwogIGQuZm9yRWFjaChmdW5jdGlvbihyKXtjbnRbci5zaW55YWxdPShjbnRbci5zaW55YWxdfHwwKSsxO30pOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJzdGF0cyIpLmlubmVySFRNTD0KICAgICc8ZGl2IGNsYXNzPSJwaWxsIGciPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+R3VjbHUgQWw6ICcrKGNudFsiR1VDTFUgQUwiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCBnIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PkFsOiAnKyhjbnRbIkFMIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgeSI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5EaWtrYXQ6ICcrKGNudFsiRElLS0FUIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgciI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5TYXQ6ICcrKGNudFsiU0FUIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgYiIgc3R5bGU9Im1hcmdpbi1sZWZ0OmF1dG8iPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+UG9ydGZvbHlvOiAnK1BPUlQubGVuZ3RoKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgbSI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj4nK2QubGVuZ3RoKycgYW5hbGl6PC9kaXY+JzsKfQoKZnVuY3Rpb24gcmVuZGVyR3JpZCgpewogIE9iamVjdC52YWx1ZXMobWluaUNoYXJ0cykuZm9yRWFjaChmdW5jdGlvbihjKXtjLmRlc3Ryb3koKTt9KTsKICBtaW5pQ2hhcnRzPXt9OwogIHZhciBmPWZpbHRlcmVkKCk7CiAgdmFyIGdyaWQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdyaWQiKTsKICBpZighZi5sZW5ndGgpe2dyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xO3RleHQtYWxpZ246Y2VudGVyO3BhZGRpbmc6NDBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkhpc3NlIGJ1bHVuYW1hZGk8L2Rpdj4nO3JldHVybjt9CiAgZ3JpZC5pbm5lckhUTUw9Zi5tYXAoZnVuY3Rpb24ocil7cmV0dXJuIGJ1aWxkQ2FyZChyKTt9KS5qb2luKCIiKTsKICBmLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgY3R4PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtYy0iK3IudGlja2VyKTsKICAgIGlmKGN0eCYmci5jaGFydF9jbG9zZXMmJnIuY2hhcnRfY2xvc2VzLmxlbmd0aCl7CiAgICAgIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICAgICAgbWluaUNoYXJ0c1sibSIrci50aWNrZXJdPW5ldyBDaGFydChjdHgse3R5cGU6ImxpbmUiLGRhdGE6e2xhYmVsczpyLmNoYXJ0X2RhdGVzLGRhdGFzZXRzOlt7ZGF0YTpyLmNoYXJ0X2Nsb3Nlcyxib3JkZXJDb2xvcjpzcy5hYyxib3JkZXJXaWR0aDoxLjUsZmlsbDp0cnVlLGJhY2tncm91bmRDb2xvcjpzcy5hYysiMTgiLHBvaW50UmFkaXVzOjAsdGVuc2lvbjowLjR9XX0sb3B0aW9uczp7cGx1Z2luczp7bGVnZW5kOntkaXNwbGF5OmZhbHNlfX0sc2NhbGVzOnt4OntkaXNwbGF5OmZhbHNlfSx5OntkaXNwbGF5OmZhbHNlfX0sYW5pbWF0aW9uOntkdXJhdGlvbjo1MDB9LHJlc3BvbnNpdmU6dHJ1ZSxtYWludGFpbkFzcGVjdFJhdGlvOmZhbHNlfX0pOwogICAgfQogIH0pOwp9CgpmdW5jdGlvbiBidWlsZENhcmQocil7CiAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogIHZhciBkYz1yLmRlZ2lzaW0+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIGRzPShyLmRlZ2lzaW0+PTA/IisiOiIiKStyLmRlZ2lzaW0rIiUiOwogIHZhciBlc2NvbD1yLmVudHJ5X3Njb3JlPj03NT8idmFyKC0tZ3JlZW4pIjpyLmVudHJ5X3Njb3JlPj02MD8idmFyKC0tZ3JlZW4yKSI6ci5lbnRyeV9zY29yZT49NDU/InZhcigtLXllbGxvdykiOnIuZW50cnlfc2NvcmU+PTMwPyJ2YXIoLS1yZWQyKSI6InZhcigtLXJlZCkiOwogIHZhciBwdmNvbD1yLnByaWNlX3ZzX2NvbG9yPT09ImdyZWVuIj8idmFyKC0tZ3JlZW4pIjpyLnByaWNlX3ZzX2NvbG9yPT09InllbGxvdyI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIHNpZ3M9WwogICAge2w6IlRyZW5kIix2OnIudHJlbmQ9PT0iWXVrc2VsZW4iPyJZdWtzZWxpeW9yIjpyLnRyZW5kPT09IkR1c2VuIj8iRHVzdXlvciI6IllhdGF5IixnOnIudHJlbmQ9PT0iWXVrc2VsZW4iP3RydWU6ci50cmVuZD09PSJEdXNlbiI/ZmFsc2U6bnVsbH0sCiAgICB7bDoiU01BNTAiLHY6ci5hYm92ZTUwPyJVemVyaW5kZSI6IkFsdGluZGEiLGc6ci5hYm92ZTUwfSwKICAgIHtsOiJTTUEyMDAiLHY6ci5hYm92ZTIwMD8iVXplcmluZGUiOiJBbHRpbmRhIixnOnIuYWJvdmUyMDB9LAogICAge2w6IlJTSSIsdjpyLnJzaXx8Ij8iLGc6ci5yc2k/ci5yc2k8MzA/dHJ1ZTpyLnJzaT43MD9mYWxzZTpudWxsOm51bGx9LAogICAge2w6IjUyVyIsdjoiJSIrci5wY3RfZnJvbV81MncrIiB1emFrIixnOnIubmVhcl81Mnd9CiAgXS5tYXAoZnVuY3Rpb24ocyl7cmV0dXJuICc8c3BhbiBjbGFzcz0ic3AgJysocy5nPT09dHJ1ZT8ic2ciOnMuZz09PWZhbHNlPyJzYiI6InNuIikrJyI+JytzLmwrIjogIitzLnYrIjwvc3Bhbj4iO30pLmpvaW4oIiIpOwogIHJldHVybiAnPGRpdiBjbGFzcz0iY2FyZCIgc3R5bGU9ImJvcmRlci1jb2xvcjonKyhyLnBvcnRmb2xpbz8icmdiYSgxNiwxODUsMTI5LC4yNSkiOnNzLmJkKSsnIiBvbmNsaWNrPSJvcGVuTShcJycrci50aWNrZXIrJ1wnKSI+JwogICAgKyc8ZGl2IGNsYXNzPSJhY2NlbnQiIHN0eWxlPSJiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCg5MGRlZywnK3NzLmFjKycsJytzcy5hYysnODgpIj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImNib2R5Ij48ZGl2IGNsYXNzPSJjdG9wIj48ZGl2PjxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjRweCI+JwogICAgKyc8c3BhbiBjbGFzcz0idGlja2VyIiBzdHlsZT0iY29sb3I6Jytzcy50eCsnIj4nK3IudGlja2VyKyc8L3NwYW4+JwogICAgKyhyLnBvcnRmb2xpbz8nPHNwYW4gY2xhc3M9InBvcnQtYmFkZ2UiPlA8L3NwYW4+JzonJykrCiAgICAnPC9kaXY+PHNwYW4gY2xhc3M9ImJhZGdlIiBzdHlsZT0iYmFja2dyb3VuZDonK3NzLmJnKyc7Y29sb3I6Jytzcy50eCsnO2JvcmRlcjoxcHggc29saWQgJytzcy5iZCsnIj4nK3NzLmxibCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iY3ByIj48ZGl2IGNsYXNzPSJwdmFsIj4kJytyLmZpeWF0Kyc8L2Rpdj48ZGl2IGNsYXNzPSJwY2hnIiBzdHlsZT0iY29sb3I6JytkYysnIj4nK2RzKyc8L2Rpdj4nCiAgICArKHIucGVfZndkPyc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+RndkUEU6JytyLnBlX2Z3ZC50b0ZpeGVkKDEpKyc8L2Rpdj4nOicnKQogICAgKyc8L2Rpdj48L2Rpdj48ZGl2IGNsYXNzPSJzaWdzIj4nK3NpZ3MrJzwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0ibWFyZ2luLXRvcDo2cHgiPicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206M3B4Ij48c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkdpcmlzIEthbGl0ZXNpPC9zcGFuPjxzcGFuIHN0eWxlPSJmb250LXNpemU6MTFweDtmb250LXdlaWdodDo3MDA7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfc2NvcmUrJy8xMDA8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJoZWlnaHQ6NHB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjJweDtvdmVyZmxvdzpoaWRkZW4iPjxkaXYgc3R5bGU9ImhlaWdodDoxMDAlO3dpZHRoOicrci5lbnRyeV9zY29yZSsnJTtiYWNrZ3JvdW5kOicrZXNjb2wrJztib3JkZXItcmFkaXVzOjJweCI+PC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47bWFyZ2luLXRvcDozcHgiPjxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X2xhYmVsKyc8L3NwYW4+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6JytwdmNvbCsnIj4nK3IucHJpY2VfdnNfaWRlYWwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzwvZGl2PjxkaXYgY2xhc3M9ImNoYXJ0LXciPjxjYW52YXMgaWQ9Im1jLScrci50aWNrZXIrJyI+PC9jYW52YXM+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJsdmxzIj4nCiAgICArJzxkaXYgY2xhc3M9Imx2Ij48ZGl2IGNsYXNzPSJsbCI+SGVtZW4gR2lyPC9kaXY+PGRpdiBjbGFzcz0ibHZhbCIgc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuMikiPiQnK3IuZW50cnlfYWdncmVzc2l2ZSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJsdiI+PGRpdiBjbGFzcz0ibGwiPkhlZGVmPC9kaXY+PGRpdiBjbGFzcz0ibHZhbCIgc3R5bGU9ImNvbG9yOiM2MGE1ZmEiPiQnK3IuaGVkZWYrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0ibHYiPjxkaXYgY2xhc3M9ImxsIj5TdG9wPC9kaXY+PGRpdiBjbGFzcz0ibHZhbCIgc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpIj4kJytyLnN0b3ArJzwvZGl2PjwvZGl2PicKICAgICsnPC9kaXY+PC9kaXY+PC9kaXY+JzsKfQoKZnVuY3Rpb24gcmVuZGVyRGFzaGJvYXJkKCl7CiAgdmFyIGdyaWQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdyaWQiKTsKICB2YXIgbWQ9TUFSS0VUX0RBVEF8fHt9OwogIHZhciBzcD1tZC5TUDUwMHx8e307CiAgdmFyIG5hcz1tZC5OQVNEQVF8fHt9OwogIHZhciB2aXg9bWQuVklYfHx7fTsKICB2YXIgbVNpZ25hbD1tZC5NX1NJR05BTHx8Ik5PVFIiOwogIHZhciBtTGFiZWw9bWQuTV9MQUJFTHx8IlZlcmkgeW9rIjsKICB2YXIgbUNvbG9yPW1TaWduYWw9PT0iR1VDTFUiPyJ2YXIoLS1ncmVlbikiOm1TaWduYWw9PT0iWkFZSUYiPyJ2YXIoLS1yZWQyKSI6InZhcigtLXllbGxvdykiOwogIHZhciBtQmc9bVNpZ25hbD09PSJHVUNMVSI/InJnYmEoMTYsMTg1LDEyOSwuMDgpIjptU2lnbmFsPT09IlpBWUlGIj8icmdiYSgyMzksNjgsNjgsLjA4KSI6InJnYmEoMjQ1LDE1OCwxMSwuMDgpIjsKICB2YXIgbUJvcmRlcj1tU2lnbmFsPT09IkdVQ0xVIj8icmdiYSgxNiwxODUsMTI5LC4yNSkiOm1TaWduYWw9PT0iWkFZSUYiPyJyZ2JhKDIzOSw2OCw2OCwuMjUpIjoicmdiYSgyNDUsMTU4LDExLC4yNSkiOwogIHZhciBtSWNvbj1tU2lnbmFsPT09IkdVQ0xVIj8i4pyFIjptU2lnbmFsPT09IlpBWUlGIj8i4p2MIjoi4pqg77iPIjsKCiAgZnVuY3Rpb24gaW5kZXhDYXJkKG5hbWUsZGF0YSl7CiAgICBpZighZGF0YXx8IWRhdGEucHJpY2UpIHJldHVybiAiIjsKICAgIHZhciBjYz1kYXRhLmNoYW5nZT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICAgIHZhciBjcz0oZGF0YS5jaGFuZ2U+PTA/IisiOiIiKStkYXRhLmNoYW5nZSsiJSI7CiAgICB2YXIgczUwPWRhdGEuYWJvdmU1MD8nPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6MTBweCI+U01BNTAg4pyTPC9zcGFuPic6JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKTtmb250LXNpemU6MTBweCI+U01BNTAg4pyXPC9zcGFuPic7CiAgICB2YXIgczIwMD1kYXRhLmFib3ZlMjAwPyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZToxMHB4Ij5TTUEyMDAg4pyTPC9zcGFuPic6JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKTtmb250LXNpemU6MTBweCI+U01BMjAwIOKclzwvc3Bhbj4nOwogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHggMTZweDtmbGV4OjE7bWluLXdpZHRoOjE1MHB4Ij4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NnB4Ij4nK25hbWUrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpIj4kJytkYXRhLnByaWNlKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxM3B4O2NvbG9yOicrY2MrJzttYXJnaW4tYm90dG9tOjhweCI+JytjcysnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6OHB4Ij4nK3M1MCtzMjAwKyc8L2Rpdj48L2Rpdj4nOwogIH0KCiAgdmFyIHBvcnREYXRhPWN1ckRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhJiZQT1JULmluY2x1ZGVzKHIudGlja2VyKTt9KTsKICB2YXIgcG9ydEh0bWw9IiI7CiAgaWYocG9ydERhdGEubGVuZ3RoKXsKICAgIHBvcnRIdG1sPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMnB4Ij7wn5K8IFBvcnRmw7Z5IMOWemV0aTwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDE0MHB4LDFmcikpO2dhcDo4cHgiPic7CiAgICBwb3J0RGF0YS5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgICB2YXIgZGM9ci5kZWdpc2ltPj0wPyJ2YXIoLS1ncmVlbjIpIjoidmFyKC0tcmVkMikiOwogICAgICB2YXIgc3M9U1Nbci5zaW55YWxdfHxTU1siRElLS0FUIl07CiAgICAgIHBvcnRIdG1sKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgJytzcy5iZCsnO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweDtjdXJzb3I6cG9pbnRlciIgb25jbGljaz0ib3Blbk0oXCcnK3IudGlja2VyKydcJykiPicKICAgICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbTo0cHgiPicKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjE2cHg7bGV0dGVyLXNwYWNpbmc6MnB4O2NvbG9yOicrc3MudHgrJyI+JytyLnRpY2tlcisnPC9zcGFuPicKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2JhY2tncm91bmQ6Jytzcy5iZysnO2NvbG9yOicrc3MudHgrJztwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czoycHgiPicrc3MubGJsKyc8L3NwYW4+PC9kaXY+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMCI+JCcrci5maXlhdCsnPC9kaXY+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMXB4O2NvbG9yOicrZGMrJyI+Jysoci5kZWdpc2ltPj0wPyIrIjoiIikrci5kZWdpc2ltKyclPC9kaXY+PC9kaXY+JzsKICAgIH0pOwogICAgcG9ydEh0bWwrPSc8L2Rpdj48L2Rpdj4nOwogIH0KCiAgdmFyIHVyZ2VudEVhcm5pbmdzPUVBUk5JTkdTX0RBVEEuZmlsdGVyKGZ1bmN0aW9uKGUpe3JldHVybiBlLmFsZXJ0PT09InJlZCJ8fGUuYWxlcnQ9PT0ieWVsbG93Ijt9KTsKICB2YXIgZWFybmluZ3NBbGVydD0iIjsKICBpZih1cmdlbnRFYXJuaW5ncy5sZW5ndGgpewogICAgZWFybmluZ3NBbGVydD0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjQ1LDE1OCwxMSwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTRweCAxNnB4O21hcmdpbi1ib3R0b206MTRweCI+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLXllbGxvdyk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPuKaoO+4jyBZYWtsYcWfYW4gUmFwb3JsYXI8L2Rpdj4nOwogICAgdXJnZW50RWFybmluZ3MuZm9yRWFjaChmdW5jdGlvbihlKXsKICAgICAgdmFyIGljPWUuYWxlcnQ9PT0icmVkIj8i8J+UtCI6IvCfn6EiOwogICAgICBlYXJuaW5nc0FsZXJ0Kz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjZweDtmb250LXNpemU6MTJweCI+JwogICAgICAgICsnPHNwYW4+JytpYysnIDxzdHJvbmc+JytlLnRpY2tlcisnPC9zdHJvbmc+PC9zcGFuPicKICAgICAgICArJzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPicrZS5uZXh0X2RhdGUrJyAoJysoZS5kYXlzX3RvX2Vhcm5pbmdzPT09MD8iQlVHw5xOIjplLmRheXNfdG9fZWFybmluZ3MrIiBnw7xuIikrJyk8L3NwYW4+PC9kaXY+JzsKICAgIH0pOwogICAgZWFybmluZ3NBbGVydCs9JzwvZGl2Pic7CiAgfQoKICB2YXIgbmV3c0h0bWw9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCI+JwogICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEycHgiPvCfk7AgU29uIEhhYmVybGVyPC9kaXY+JzsKICBpZihORVdTX0RBVEEmJk5FV1NfREFUQS5sZW5ndGgpewogICAgTkVXU19EQVRBLnNsaWNlKDAsMTApLmZvckVhY2goZnVuY3Rpb24obil7CiAgICAgIHZhciBwYj1uLnBvcnRmb2xpbz8nPHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xMik7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yNSk7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwIj5QPC9zcGFuPic6IiI7CiAgICAgIHZhciB0YT0iIjsKICAgICAgaWYobi5kYXRldGltZSl7dmFyIGRpZmY9TWF0aC5mbG9vcigoRGF0ZS5ub3coKS8xMDAwLW4uZGF0ZXRpbWUpLzM2MDApO3RhPWRpZmY8MjQ/KGRpZmYrInMgw7ZuY2UiKTooTWF0aC5mbG9vcihkaWZmLzI0KSsiZyDDtm5jZSIpO30KICAgICAgbmV3c0h0bWwrPSc8ZGl2IHN0eWxlPSJwYWRkaW5nOjEwcHggMDtib3JkZXItYm90dG9tOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNCkiPicKICAgICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjZweDttYXJnaW4tYm90dG9tOjRweCI+JwogICAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS15ZWxsb3cpIj4nK24udGlja2VyKyc8L3NwYW4+JytwYgogICAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1sZWZ0OmF1dG8iPicrdGErJzwvc3Bhbj48L2Rpdj4nCiAgICAgICAgKyc8YSBocmVmPSInK24udXJsKyciIHRhcmdldD0iX2JsYW5rIiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tdGV4dCk7dGV4dC1kZWNvcmF0aW9uOm5vbmU7bGluZS1oZWlnaHQ6MS41O2Rpc3BsYXk6YmxvY2siPicrKG4uaGVhZGxpbmVfdHJ8fG4uaGVhZGxpbmUpKyc8L2E+JwogICAgICAgICsobi5zdW1tYXJ5X3RyfHxuLnN1bW1hcnk/JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOiM5Y2EzYWY7bWFyZ2luLXRvcDo0cHg7bGluZS1oZWlnaHQ6MS40Ij4nKyhuLnN1bW1hcnlfdHJ8fG4uc3VtbWFyeSkuc3Vic3RyaW5nKDAsMTUwKSsnLi4uPC9kaXY+JzonJykrJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tdG9wOjNweCI+JytuLnNvdXJjZSsnPC9kaXY+PC9kaXY+JzsKICAgIH0pOwogIH0gZWxzZSB7CiAgICBuZXdzSHRtbCs9JzxkaXYgc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKTtmb250LXNpemU6MTJweCI+SGFiZXIgYnVsdW5hbWFkaTwvZGl2Pic7CiAgfQogIG5ld3NIdG1sKz0nPC9kaXY+JzsKCiAgZ3JpZC5pbm5lckhUTUw9JzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPicKICAgICsnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonK21CZysnO2JvcmRlcjoxcHggc29saWQgJyttQm9yZGVyKyc7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweDtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2ZsZXgtd3JhcDp3cmFwO2dhcDoxMnB4Ij4nCiAgICArJzxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweDttYXJnaW4tYm90dG9tOjRweCI+Q0FOU0xJTSBNIEtSxLBURVLEsDwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrbUNvbG9yKyciPicrbUljb24rJyAnK21MYWJlbCsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7dGV4dC1hbGlnbjpyaWdodCI+VklYOiAnKyh2aXgucHJpY2V8fCI/IikrJzxicj4nCiAgICArJzxzcGFuIHN0eWxlPSJjb2xvcjonKyh2aXgucHJpY2UmJnZpeC5wcmljZT4yNT8idmFyKC0tcmVkMikiOiJ2YXIoLS1ncmVlbikiKSsnIj4nKyh2aXgucHJpY2UmJnZpeC5wcmljZT4yNT8iWcO8a3NlayB2b2xhdGlsaXRlIjoiTm9ybWFsIHZvbGF0aWxpdGUiKSsnPC9zcGFuPjwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2ZsZXgtd3JhcDp3cmFwO21hcmdpbi1ib3R0b206MTRweCI+JytpbmRleENhcmQoIlMmUCA1MDAgKFNQWSkiLHNwKStpbmRleENhcmQoIk5BU0RBUSAoUVFRKSIsbmFzKSsnPC9kaXY+JwogICAgK3BvcnRIdG1sK2Vhcm5pbmdzQWxlcnQrbmV3c0h0bWwKICAgICsnPGRpdiBzdHlsZT0ibWFyZ2luLXRvcDoyMHB4Ij4nK2J1aWxkUnV0aW5IVE1MKCkrJzwvZGl2PicKICAgICsnPC9kaXY+JzsKfQoKZnVuY3Rpb24gcmVuZGVyRWFybmluZ3MoKXsKICB2YXIgZ3JpZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ3JpZCIpOwogIHZhciBzb3J0ZWQ9RUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuIGUubmV4dF9kYXRlO30pLnNvcnQoZnVuY3Rpb24oYSxiKXsKICAgIHZhciBkYT1hLmRheXNfdG9fZWFybmluZ3MhPW51bGw/YS5kYXlzX3RvX2Vhcm5pbmdzOjk5OTsKICAgIHZhciBkYj1iLmRheXNfdG9fZWFybmluZ3MhPW51bGw/Yi5kYXlzX3RvX2Vhcm5pbmdzOjk5OTsKICAgIHJldHVybiBkYS1kYjsKICB9KTsKICB2YXIgbm9EYXRlPUVBUk5JTkdTX0RBVEEuZmlsdGVyKGZ1bmN0aW9uKGUpe3JldHVybiAhZS5uZXh0X2RhdGU7fSk7CiAgaWYoIXNvcnRlZC5sZW5ndGgmJiFub0RhdGUubGVuZ3RoKXtncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMTt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjQwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5FYXJuaW5ncyB2ZXJpc2kgYnVsdW5hbWFkaTwvZGl2Pic7cmV0dXJuO30KICB2YXIgaD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKICBzb3J0ZWQuZm9yRWFjaChmdW5jdGlvbihlKXsKICAgIHZhciBhYj1lLmFsZXJ0PT09InJlZCI/InJnYmEoMjM5LDY4LDY4LC4xMikiOmUuYWxlcnQ9PT0ieWVsbG93Ij8icmdiYSgyNDUsMTU4LDExLC4xKSI6InJnYmEoMjU1LDI1NSwyNTUsLjAyKSI7CiAgICB2YXIgYWJkPWUuYWxlcnQ9PT0icmVkIj8icmdiYSgyMzksNjgsNjgsLjM1KSI6ZS5hbGVydD09PSJ5ZWxsb3ciPyJyZ2JhKDI0NSwxNTgsMTEsLjMpIjoicmdiYSgyNTUsMjU1LDI1NSwuMDcpIjsKICAgIHZhciBhaT1lLmFsZXJ0PT09InJlZCI/IvCflLQiOmUuYWxlcnQ9PT0ieWVsbG93Ij8i8J+foSI6IvCfk4UiOwogICAgdmFyIGR0PWUuZGF5c190b19lYXJuaW5ncyE9bnVsbD8oZS5kYXlzX3RvX2Vhcm5pbmdzPT09MD8iQlVHVU4iOmUuZGF5c190b19lYXJuaW5ncz09PTE/IllhcmluIjplLmRheXNfdG9fZWFybmluZ3MrIiBndW4gc29ucmEiKToiIjsKICAgIHZhciBhbUNvbD1lLmF2Z19tb3ZlX3BjdCE9bnVsbD8oZS5hdmdfbW92ZV9wY3Q+PTA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZDIpIik6InZhcigtLW11dGVkKSI7CiAgICB2YXIgYW1TdHI9ZS5hdmdfbW92ZV9wY3QhPW51bGw/KGUuYXZnX21vdmVfcGN0Pj0wPyIrIjoiIikrZS5hdmdfbW92ZV9wY3QrIiUiOiLigJQiOwogICAgdmFyIHliPWUuYWxlcnQ9PT0icmVkIj8nPHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtjb2xvcjp2YXIoLS1yZWQyKTtwYWRkaW5nOjJweCA4cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjEwcHg7Zm9udC13ZWlnaHQ6NzAwIj5ZQUtJTkRBPC9zcGFuPic6IiI7CiAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonK2FiKyc7Ym9yZGVyOjFweCBzb2xpZCAnK2FiZCsnO2JvcmRlci1yYWRpdXM6MTBweDttYXJnaW4tYm90dG9tOjEwcHg7cGFkZGluZzoxNHB4IDE2cHgiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6OHB4Ij4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjEwcHgiPjxzcGFuPicrYWkrJzwvc3Bhbj48c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyMHB4O2xldHRlci1zcGFjaW5nOjJweDtjb2xvcjp2YXIoLS10ZXh0KSI+JytlLnRpY2tlcisnPC9zcGFuPicreWIrJzwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxNnB4O2ZsZXgtd3JhcDp3cmFwO2FsaWduLWl0ZW1zOmNlbnRlciI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlJBUE9SPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjp2YXIoLS10ZXh0KSI+JysoZS5uZXh0X2RhdGV8fCLigJQiKSsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6JysoZS5hbGVydD09PSJyZWQiPyJ2YXIoLS1yZWQyKSI6ZS5hbGVydD09PSJ5ZWxsb3ciPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tbXV0ZWQpIikrJyI+JytkdCsnPC9kaXY+PC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkVQUyBUQUhNSU48L2Rpdj48ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOiM2MGE1ZmEiPicrKGUuZXBzX2VzdGltYXRlIT1udWxsPyIkIitlLmVwc19lc3RpbWF0ZToi4oCUIikrJzwvZGl2PjwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5PUlQuSEFSRUtFVDwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JythbUNvbCsnIj4nK2FtU3RyKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKSI+c29uIDQgcmFwb3I8L2Rpdj48L2Rpdj4nOwogICAgaCs9JzwvZGl2PjwvZGl2Pic7CiAgICBpZihlLmhpc3RvcnlfZXBzJiZlLmhpc3RvcnlfZXBzLmxlbmd0aCl7CiAgICAgIGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW4tdG9wOjhweDtwYWRkaW5nLXRvcDo4cHg7Ym9yZGVyLXRvcDoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjVweCI+U09OIDQgUkFQT1I8L2Rpdj48ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCg0LDFmcik7Z2FwOjRweCI+JzsKICAgICAgZS5oaXN0b3J5X2Vwcy5mb3JFYWNoKGZ1bmN0aW9uKGhoKXsKICAgICAgICB2YXIgc2M9aGguc3VycHJpc2VfcGN0IT1udWxsPyhoaC5zdXJwcmlzZV9wY3Q+MD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkMikiKToidmFyKC0tbXV0ZWQpIjsKICAgICAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6NHB4O3BhZGRpbmc6NnB4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDUpIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytoaC5kYXRlLnN1YnN0cmluZygwLDcpKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEwcHgiPicrKGhoLmFjdHVhbCE9bnVsbD8iJCIraGguYWN0dWFsOiI/IikrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6JytzYysnIj4nKyhoaC5zdXJwcmlzZV9wY3QhPW51bGw/KGhoLnN1cnByaXNlX3BjdD4wPyIrIjoiIikraGguc3VycHJpc2VfcGN0KyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nOwogICAgICB9KTsKICAgICAgaCs9JzwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBoKz0nPC9kaXY+JzsKICB9KTsKICBpZihub0RhdGUubGVuZ3RoKXtoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi10b3A6NnB4Ij5UYXJpaCBidWx1bmFtYXlhbjogJytub0RhdGUubWFwKGZ1bmN0aW9uKGUpe3JldHVybiBlLnRpY2tlcjt9KS5qb2luKCIsICIpKyc8L2Rpdj4nO30KICBoKz0nPC9kaXY+JzsKICBncmlkLmlubmVySFRNTD1oOwp9CgpmdW5jdGlvbiBvcGVuTSh0aWNrZXIpewogIHZhciByPWN1ckRhdGEuZmluZChmdW5jdGlvbihkKXtyZXR1cm4gZC50aWNrZXI9PT10aWNrZXI7fSk7CiAgaWYoIXJ8fHIuaGF0YSkgcmV0dXJuOwogIGlmKG1DaGFydCl7bUNoYXJ0LmRlc3Ryb3koKTttQ2hhcnQ9bnVsbDt9CiAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogIHZhciByclA9TWF0aC5taW4oKHIucnIvNCkqMTAwLDEwMCk7CiAgdmFyIHJyQz1yLnJyPj0zPyJ2YXIoLS1ncmVlbikiOnIucnI+PTI/InZhcigtLWdyZWVuMikiOnIucnI+PTE/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIGRjPXIuZGVnaXNpbT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICB2YXIga2M9eyJHVUNMVSBBTCI6IiMxMGI5ODEiLCJBTCI6IiMzNGQzOTkiLCJESUtLQVRMSSI6IiNmNTllMGIiLCJHRUNNRSI6IiNmODcxNzEifTsKICB2YXIga2xibD17IkdVQ0xVIEFMIjoiR1VDTFUgQUwiLCJBTCI6IkFMIiwiRElLS0FUTEkiOiJESUtLQVRMSSIsIkdFQ01FIjoiR0VDTUUifTsKICB2YXIgZXNjb2w9ci5lbnRyeV9zY29yZT49NzU/InZhcigtLWdyZWVuKSI6ci5lbnRyeV9zY29yZT49NjA/InZhcigtLWdyZWVuMikiOnIuZW50cnlfc2NvcmU+PTQ1PyJ2YXIoLS15ZWxsb3cpIjpyLmVudHJ5X3Njb3JlPj0zMD8idmFyKC0tcmVkMikiOiJ2YXIoLS1yZWQpIjsKICB2YXIgcHZjb2w9ci5wcmljZV92c19jb2xvcj09PSJncmVlbiI/InZhcigtLWdyZWVuKSI6ci5wcmljZV92c19jb2xvcj09PSJ5ZWxsb3ciPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkMikiOwoKICB2YXIgbWg9JzxkaXYgY2xhc3M9Im1oZWFkIj48ZGl2PjxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjhweDtmbGV4LXdyYXA6d3JhcCI+JwogICAgKyc8c3BhbiBjbGFzcz0ibXRpdGxlIiBzdHlsZT0iY29sb3I6Jytzcy50eCsnIj4nK3IudGlja2VyKyc8L3NwYW4+JwogICAgKyc8c3BhbiBjbGFzcz0iYmFkZ2UiIHN0eWxlPSJiYWNrZ3JvdW5kOicrc3MuYmcrJztjb2xvcjonK3NzLnR4Kyc7Ym9yZGVyOjFweCBzb2xpZCAnK3NzLmJkKyc7Zm9udC1zaXplOjEycHgiPicrc3MubGJsKyc8L3NwYW4+JwogICAgKyhyLnBvcnRmb2xpbz8nPHNwYW4gY2xhc3M9InBvcnQtYmFkZ2UiIHN0eWxlPSJmb250LXNpemU6MTFweDtwYWRkaW5nOjNweCA4cHgiPlBvcnRmb2x5bzwvc3Bhbj4nOicnKQogICAgKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC13ZWlnaHQ6NjAwO21hcmdpbi10b3A6NHB4Ij4kJytyLmZpeWF0CiAgICArJyA8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6JytkYysnIj4nKyhyLmRlZ2lzaW0+PTA/IisiOiIiKStyLmRlZ2lzaW0rJyU8L3NwYW4+PC9kaXY+PC9kaXY+JwogICAgKyc8YnV0dG9uIGNsYXNzPSJtY2xvc2UiIG9uY2xpY2s9ImNsb3NlTSgpIj7inJU8L2J1dHRvbj48L2Rpdj4nOwoKICBtaCs9JzxkaXYgY2xhc3M9Im1ib2R5Ij48ZGl2IGNsYXNzPSJtY2hhcnR3Ij48Y2FudmFzIGlkPSJtY2hhcnQiPjwvY2FudmFzPjwvZGl2Pic7CgogIG1oKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O21hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij4nK2liKCJFbnRyeVNjb3JlIiwiR2lyaXMgS2FsaXRlc2kiKSsnPC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206NnB4Ij4nCiAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X3Njb3JlKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4vMTAwPC9zcGFuPjwvc3Bhbj4nCiAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfbGFiZWwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImhlaWdodDo2cHg7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlci1yYWRpdXM6M3B4O292ZXJmbG93OmhpZGRlbjttYXJnaW4tYm90dG9tOjhweCI+PGRpdiBzdHlsZT0iaGVpZ2h0OjEwMCU7d2lkdGg6JytyLmVudHJ5X3Njb3JlKyclO2JhY2tncm91bmQ6Jytlc2NvbCsnO2JvcmRlci1yYWRpdXM6M3B4Ij48L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2Vlbjtmb250LXNpemU6MTFweCI+JwogICAgKyc8ZGl2PjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPlN1IGFua2kgZml5YXQ6IDwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6JytwdmNvbCsnO2ZvbnQtd2VpZ2h0OjYwMCI+JytyLnByaWNlX3ZzX2lkZWFsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2PjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPklkZWFsIGJvbGdlOiA8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuMik7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmlkZWFsX2VudHJ5X2xvdysnIC0gJCcrci5pZGVhbF9lbnRyeV9oaWdoKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8L2Rpdj48L2Rpdj4nOwoKICBtaCs9JzxkaXYgY2xhc3M9ImRib3giIHN0eWxlPSJiYWNrZ3JvdW5kOicrc3MuYmcrJztib3JkZXItY29sb3I6Jytzcy5iZCsnO21hcmdpbi1ib3R0b206MTJweCI+JwogICAgKyc8ZGl2IGNsYXNzPSJkbGJsIiBzdHlsZT0iY29sb3I6Jytzcy50eCsnIj4nK2liKCJSUiIsIkFsaW0gS2FyYXJpIFIvUiIpKyc8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImR2ZXJkIiBzdHlsZT0iY29sb3I6Jysoa2Nbci5rYXJhcl18fCJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhrbGJsW3Iua2FyYXJdfHxyLmthcmFyKSsnPC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+UmlzayAvIE9kdWw8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOicrcnJDKyc7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+MSA6ICcrci5ycisnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkhlbWVuIEdpcjwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4yKTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuZW50cnlfYWdncmVzc2l2ZSsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkdlcmkgQ2VraWxtZTwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6IzYwYTVmYTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuZW50cnlfbWlkKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkcm93Ij48c3BhbiBjbGFzcz0iZGtleSI+QnV5dWsgRHV6ZWx0bWU8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXllbGxvdyk7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmVudHJ5X2NvbnNlcnZhdGl2ZSsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkhlZGVmPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjojNjBhNWZhO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5oZWRlZisnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPlN0b3AtTG9zczwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMik7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLnN0b3ArJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9InJyYmFyIj48ZGl2IGNsYXNzPSJycmZpbGwiIHN0eWxlPSJ3aWR0aDonK3JyUCsnJTtiYWNrZ3JvdW5kOicrcnJDKyciPjwvZGl2PjwvZGl2PjwvZGl2Pic7CgogIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+VGVrbmlrIEFuYWxpejwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGdyaWQiIHN0eWxlPSJtYXJnaW4tYm90dG9tOjEycHgiPicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJUcmVuZCIsIlRyZW5kIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci50cmVuZD09PSJZdWtzZWxlbiI/InZhcigtLWdyZWVuKSI6ci50cmVuZD09PSJEdXNlbiI/InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nK3IudHJlbmQrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJSU0kiLCJSU0kgMTQiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnJzaT9yLnJzaTwzMD8idmFyKC0tZ3JlZW4pIjpyLnJzaT43MD8idmFyKC0tcmVkKSI6InZhcigtLXllbGxvdykiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnJzaXx8Ij8iKSsoci5yc2k/ci5yc2k8MzA/IiBBc2lyaSBTYXRpbSI6ci5yc2k+NzA/IiBBc2lyaSBBbGltIjoiIE5vdHIiOiIiKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlNNQTUwIiwiU01BIDUwIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5hYm92ZTUwPyJ2YXIoLS1ncmVlbikiOiJ2YXIoLS1yZWQpIikrJyI+Jysoci5hYm92ZTUwPyJVemVyaW5kZSI6IkFsdGluZGEiKSsoci5zbWE1MF9kaXN0IT1udWxsPyIgKCIrci5zbWE1MF9kaXN0KyIlKSI6IiIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiU01BMjAwIiwiU01BIDIwMCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuYWJvdmUyMDA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZCkiKSsnIj4nKyhyLmFib3ZlMjAwPyJVemVyaW5kZSI6IkFsdGluZGEiKSsoci5zbWEyMDBfZGlzdCE9bnVsbD8iICgiK3Iuc21hMjAwX2Rpc3QrIiUpIjoiIikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCI1MlciLCI1MkggUG96LiIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIudzUyX3Bvc2l0aW9uPD0zMD8idmFyKC0tZ3JlZW4pIjpyLnc1Ml9wb3NpdGlvbj49ODU/InZhcigtLXJlZCkiOiJ2YXIoLS15ZWxsb3cpIikrJyI+JytyLnc1Ml9wb3NpdGlvbisnJTwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJIYWNpbSIsIkhhY2ltIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5oYWNpbT09PSJZdWtzZWsiPyJ2YXIoLS1ncmVlbikiOnIuaGFjaW09PT0iRHVzdWsiPyJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+JytyLmhhY2ltKycgKCcrci52b2xfcmF0aW8rJ3gpPC9kaXY+PC9kaXY+JwogICAgKyc8L2Rpdj4nOwoKICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPlRlbWVsIEFuYWxpejwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGdyaWQiIHN0eWxlPSJtYXJnaW4tYm90dG9tOjEycHgiPicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJGb3J3YXJkUEUiLCJGb3J3YXJkIFBFIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5wZV9md2Q/ci5wZV9md2Q8MjU/InZhcigtLWdyZWVuKSI6ci5wZV9md2Q8NDA/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5wZV9md2Q/ci5wZV9md2QudG9GaXhlZCgxKToiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUEVHIiwiUEVHIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5wZWc/ci5wZWc8MT8idmFyKC0tZ3JlZW4pIjpyLnBlZzwyPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucGVnP3IucGVnLnRvRml4ZWQoMik6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIkVQU0dyb3d0aCIsIkVQUyBCw7x5w7xtZSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuZXBzX2dyb3d0aD9yLmVwc19ncm93dGg+PTIwPyJ2YXIoLS1ncmVlbikiOnIuZXBzX2dyb3d0aD49MD8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLmVwc19ncm93dGghPW51bGw/ci5lcHNfZ3Jvd3RoKyIlIjoiPyIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUmV2R3Jvd3RoIiwiR2VsaXIgQsO8ecO8bWUiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnJldl9ncm93dGg/ci5yZXZfZ3Jvd3RoPj0xNT8idmFyKC0tZ3JlZW4pIjpyLnJldl9ncm93dGg+PTA/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5yZXZfZ3Jvd3RoIT1udWxsP3IucmV2X2dyb3d0aCsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIk5ldE1hcmdpbiIsIk5ldCBNYXJqaW4iKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLm5ldF9tYXJnaW4/ci5uZXRfbWFyZ2luPj0xNT8idmFyKC0tZ3JlZW4pIjpyLm5ldF9tYXJnaW4+PTU/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5uZXRfbWFyZ2luIT1udWxsP3IubmV0X21hcmdpbisiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlJPRSIsIlJPRSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucm9lP3Iucm9lPj0xNT8idmFyKC0tZ3JlZW4pIjpyLnJvZT49NT8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnJvZSE9bnVsbD9yLnJvZSsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8L2Rpdj4nOwoKICB2YXIgYWlUZXh0ID0gQUlfREFUQSAmJiBBSV9EQVRBW3RpY2tlcl07CiAgaWYoYWlUZXh0KXsKICAgIG1oKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDttYXJnaW4tYm90dG9tOjEycHgiPic7CiAgICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6IzYwYTVmYTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij7wn6SWIEFJIEFuYWxpeiAoQ2xhdWRlIFNvbm5ldCk8L2Rpdj4nOwogICAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS10ZXh0KTtsaW5lLWhlaWdodDoxLjc7d2hpdGUtc3BhY2U6cHJlLXdyYXAiPicrYWlUZXh0Kyc8L2Rpdj4nOwogICAgbWgrPSc8L2Rpdj4nOwogIH0KICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTt0ZXh0LWFsaWduOmNlbnRlciI+QnUgYXJhYyB5YXRpcmltIHRhdnNpeWVzaSBkZWdpbGRpcjwvZGl2PjwvZGl2Pic7CgogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtb2RhbCIpLmlubmVySFRNTD1taDsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgib3ZlcmxheSIpLmNsYXNzTGlzdC5hZGQoIm9wZW4iKTsKICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7CiAgICB2YXIgY3R4PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtY2hhcnQiKTsKICAgIGlmKGN0eCYmci5jaGFydF9jbG9zZXMpewogICAgICBtQ2hhcnQ9bmV3IENoYXJ0KGN0eCx7dHlwZToibGluZSIsZGF0YTp7bGFiZWxzOnIuY2hhcnRfZGF0ZXMsZGF0YXNldHM6WwogICAgICAgIHtsYWJlbDoiRml5YXQiLGRhdGE6ci5jaGFydF9jbG9zZXMsYm9yZGVyQ29sb3I6c3MuYWMsYm9yZGVyV2lkdGg6MixmaWxsOnRydWUsYmFja2dyb3VuZENvbG9yOnNzLmFjKyIyMCIscG9pbnRSYWRpdXM6MCx0ZW5zaW9uOjAuM30sCiAgICAgICAgci5zbWE1MD97bGFiZWw6IlNNQTUwIixkYXRhOkFycmF5KHIuY2hhcnRfY2xvc2VzLmxlbmd0aCkuZmlsbChyLnNtYTUwKSxib3JkZXJDb2xvcjoiI2Y1OWUwYiIsYm9yZGVyV2lkdGg6MS41LGJvcmRlckRhc2g6WzUsNV0scG9pbnRSYWRpdXM6MCxmaWxsOmZhbHNlfTpudWxsLAogICAgICAgIHIuc21hMjAwP3tsYWJlbDoiU01BMjAwIixkYXRhOkFycmF5KHIuY2hhcnRfY2xvc2VzLmxlbmd0aCkuZmlsbChyLnNtYTIwMCksYm9yZGVyQ29sb3I6IiM4YjVjZjYiLGJvcmRlcldpZHRoOjEuNSxib3JkZXJEYXNoOls1LDVdLHBvaW50UmFkaXVzOjAsZmlsbDpmYWxzZX06bnVsbAogICAgICBdLmZpbHRlcihCb29sZWFuKX0sb3B0aW9uczp7cmVzcG9uc2l2ZTp0cnVlLG1haW50YWluQXNwZWN0UmF0aW86ZmFsc2UsCiAgICAgICAgcGx1Z2luczp7bGVnZW5kOntsYWJlbHM6e2NvbG9yOiIjNmI3MjgwIixmb250OntzaXplOjEwfX19fSwKICAgICAgICBzY2FsZXM6e3g6e2Rpc3BsYXk6dHJ1ZSx0aWNrczp7Y29sb3I6IiMzNzQxNTEiLG1heFRpY2tzTGltaXQ6NSxmb250OntzaXplOjl9fSxncmlkOntjb2xvcjoicmdiYSgyNTUsMjU1LDI1NSwuMDQpIn19LAogICAgICAgICAgeTp7ZGlzcGxheTp0cnVlLHRpY2tzOntjb2xvcjoiIzM3NDE1MSIsZm9udDp7c2l6ZTo5fX0sZ3JpZDp7Y29sb3I6InJnYmEoMjU1LDI1NSwyNTUsLjA0KSJ9fX19fSk7CiAgICB9CiAgfSwxMDApOwp9CgoKLy8g4pSA4pSAIEfDnE5Mw5xLIFJVVMSwTiDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAKdmFyIFJVVElOX0lURU1TID0gewogIHNhYmFoOiB7CiAgICBsYWJlbDogIvCfjIUgU2FiYWgg4oCUIFBpeWFzYSBBw6fEsWxtYWRhbiDDlm5jZSIsCiAgICBpdGVtczogWwogICAgICB7aWQ6InMxIiwgdGV4dDoiRGFzaGJvYXJkxLEgYcOnIOKAlCBNIGtyaXRlcmkgeWXFn2lsIG1pPyAoUyZQNTAwICsgTkFTREFRIFNNQTIwMCDDvHN0w7xuZGUpIn0sCiAgICAgIHtpZDoiczIiLCB0ZXh0OiJFYXJuaW5ncyBzZWttZXNpbmkga29udHJvbCBldCDigJQgYnVnw7xuL2J1IGhhZnRhIHJhcG9yIHZhciBtxLE/In0sCiAgICAgIHtpZDoiczMiLCB0ZXh0OiJWSVggMjUgYWx0xLFuZGEgbcSxPyAoWcO8a3Nla3NlIHllbmkgcG96aXN5b24gYcOnbWEpIn0sCiAgICAgIHtpZDoiczQiLCB0ZXh0OiLDlm5jZWtpIGfDvG5kZW4gYmVrbGV5ZW4gYWxhcm0gbWFpbGkgdmFyIG3EsT8ifQogICAgXQogIH0sCiAgb2dsZW46IHsKICAgIGxhYmVsOiAi8J+TiiDDlsSfbGVkZW4gU29ucmEg4oCUIFBpeWFzYSBBw6fEsWtrZW4iLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJvMSIsIHRleHQ6IlBvcnRmw7Z5w7xtIHNla21lc2luZGUgaGlzc2VsZXJpbWUgYmFrIOKAlCBiZWtsZW5tZWRpayBkw7zFn8O8xZ8gdmFyIG3EsT8ifSwKICAgICAge2lkOiJvMiIsIHRleHQ6IlN0b3Agc2V2aXllc2luZSB5YWtsYcWfYW4gaGlzc2UgdmFyIG3EsT8gKEvEsXJtxLF6xLEgacWfYXJldCkifSwKICAgICAge2lkOiJvMyIsIHRleHQ6IkFsIHNpbnlhbGkgc2VrbWVzaW5kZSB5ZW5pIGbEsXJzYXQgw6fEsWttxLHFnyBtxLE/In0sCiAgICAgIHtpZDoibzQiLCB0ZXh0OiJXYXRjaGxpc3R0ZWtpIGhpc3NlbGVyZGUgZ2lyacWfIGthbGl0ZXNpIDYwKyBvbGFuIHZhciBtxLE/In0sCiAgICAgIHtpZDoibzUiLCB0ZXh0OiJIYWJlcmxlcmRlIHBvcnRmw7Z5w7xtw7wgZXRraWxleWVuIMO2bmVtbGkgZ2VsacWfbWUgdmFyIG3EsT8ifQogICAgXQogIH0sCiAgYWtzYW06IHsKICAgIGxhYmVsOiAi8J+MmSBBa8WfYW0g4oCUIFBpeWFzYSBLYXBhbmTEsWt0YW4gU29ucmEiLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJhMSIsIHRleHQ6IjFIIHNpbnlhbGxlcmluaSBrb250cm9sIGV0IOKAlCBoYWZ0YWzEsWsgdHJlbmQgZGXEn2nFn21pxZ8gbWk/In0sCiAgICAgIHtpZDoiYTIiLCB0ZXh0OiJZYXLEsW4gacOnaW4gcG90YW5zaXllbCBnaXJpxZ8gbm9rdGFsYXLEsW7EsSBub3QgYWwifSwKICAgICAge2lkOiJhMyIsIHRleHQ6IlBvcnRmw7Z5ZGVraSBoZXIgaGlzc2VuaW4gc3RvcCBzZXZpeWVzaW5pIGfDtnpkZW4gZ2XDp2lyIn0sCiAgICAgIHtpZDoiYTQiLCB0ZXh0OiJZYXLEsW4gcmFwb3IgYcOnxLFrbGF5YWNhayBoaXNzZSB2YXIgbcSxPyAoRWFybmluZ3Mgc2VrbWVzaSkifQogICAgXQogIH0sCiAgaGFmdGFsaWs6IHsKICAgIGxhYmVsOiAi8J+ThSBIYWZ0YWzEsWsg4oCUIFBhemFyIEFrxZ9hbcSxIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoiaDEiLCB0ZXh0OiJTdG9jayBSb3ZlcmRhIENBTlNMSU0gc2NyZWVuZXLEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoMiIsIHRleHQ6IlZDUCBNaW5lcnZpbmkgc2NyZWVuZXLEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoMyIsIHRleHQ6IlF1bGxhbWFnZ2llIEJyZWFrb3V0IHNjcmVlbmVyxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDQiLCB0ZXh0OiJGaW52aXpkZSBJbnN0aXR1dGlvbmFsIEJ1eWluZyBzY3JlZW5lcsSxIMOnYWzEscWfdMSxciJ9LAogICAgICB7aWQ6Img1IiwgdGV4dDoiw4dha8SxxZ9hbiBoaXNzZWxlcmkgYnVsIOKAlCBlbiBnw7zDp2zDvCBhZGF5bGFyIn0sCiAgICAgIHtpZDoiaDYiLCB0ZXh0OiJHaXRIdWIgQWN0aW9uc2RhbiBSdW4gV29ya2Zsb3cgYmFzIOKAlCBzaXRlIGfDvG5jZWxsZW5pciJ9LAogICAgICB7aWQ6Img3IiwgdGV4dDoiR2VsZWNlayBoYWZ0YW7EsW4gZWFybmluZ3MgdGFrdmltaW5pIGtvbnRyb2wgZXQifSwKICAgICAge2lkOiJoOCIsIHRleHQ6IlBvcnRmw7Z5IGdlbmVsIGRlxJ9lcmxlbmRpcm1lc2kg4oCUIGhlZGVmbGVyIGhhbGEgZ2XDp2VybGkgbWk/In0KICAgIF0KICB9Cn07CgpmdW5jdGlvbiBnZXRUb2RheUtleSgpewogIHJldHVybiBuZXcgRGF0ZSgpLnRvRGF0ZVN0cmluZygpOwp9CgpmdW5jdGlvbiBsb2FkQ2hlY2tlZCgpewogIHRyeXsKICAgIHZhciBkYXRhID0gbG9jYWxTdG9yYWdlLmdldEl0ZW0oJ3J1dGluX2NoZWNrZWQnKTsKICAgIGlmKCFkYXRhKSByZXR1cm4ge307CiAgICB2YXIgcGFyc2VkID0gSlNPTi5wYXJzZShkYXRhKTsKICAgIC8vIFNhZGVjZSBidWfDvG7DvG4gdmVyaWxlcmluaSBrdWxsYW4KICAgIGlmKHBhcnNlZC5kYXRlICE9PSBnZXRUb2RheUtleSgpKSByZXR1cm4ge307CiAgICByZXR1cm4gcGFyc2VkLml0ZW1zIHx8IHt9OwogIH1jYXRjaChlKXtyZXR1cm4ge307fQp9CgpmdW5jdGlvbiBzYXZlQ2hlY2tlZChjaGVja2VkKXsKICBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgncnV0aW5fY2hlY2tlZCcsIEpTT04uc3RyaW5naWZ5KHsKICAgIGRhdGU6IGdldFRvZGF5S2V5KCksCiAgICBpdGVtczogY2hlY2tlZAogIH0pKTsKfQoKZnVuY3Rpb24gdG9nZ2xlQ2hlY2soaWQpewogIHZhciBjaGVja2VkID0gbG9hZENoZWNrZWQoKTsKICBpZihjaGVja2VkW2lkXSkgZGVsZXRlIGNoZWNrZWRbaWRdOwogIGVsc2UgY2hlY2tlZFtpZF0gPSB0cnVlOwogIHNhdmVDaGVja2VkKGNoZWNrZWQpOwogIHJlbmRlclJ1dGluKCk7Cn0KCmZ1bmN0aW9uIHJlc2V0UnV0aW4oKXsKICBsb2NhbFN0b3JhZ2UucmVtb3ZlSXRlbSgncnV0aW5fY2hlY2tlZCcpOwogIHJlbmRlclJ1dGluKCk7Cn0KCgpmdW5jdGlvbiByZW5kZXJIYWZ0YWxpaygpewogIHZhciBncmlkID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dyaWQnKTsKICB2YXIgd2QgPSBXRUVLTFlfREFUQSB8fCB7fTsKICB2YXIgcG9ydCA9IHdkLnBvcnRmb2xpbyB8fCBbXTsKICB2YXIgd2F0Y2ggPSB3ZC53YXRjaGxpc3QgfHwgW107CiAgdmFyIGJlc3QgPSB3ZC5iZXN0OwogIHZhciB3b3JzdCA9IHdkLndvcnN0OwogIHZhciBtZCA9IE1BUktFVF9EQVRBIHx8IHt9OwogIHZhciBzcCA9IG1kLlNQNTAwIHx8IHt9OwogIHZhciBuYXMgPSBtZC5OQVNEQVEgfHwge307CgogIGZ1bmN0aW9uIGNoZ0NvbG9yKHYpeyByZXR1cm4gdiA+PSAwID8gJ3ZhcigtLWdyZWVuKScgOiAndmFyKC0tcmVkMiknOyB9CiAgZnVuY3Rpb24gY2hnU3RyKHYpeyByZXR1cm4gKHYgPj0gMCA/ICcrJyA6ICcnKSArIHYgKyAnJSc7IH0KCiAgZnVuY3Rpb24gcGVyZkNhcmQoaXRlbSl7CiAgICB2YXIgY2MgPSBjaGdDb2xvcihpdGVtLndlZWtfY2hnKTsKICAgIHZhciBwYiA9IGl0ZW0ucG9ydGZvbGlvID8gJzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTIpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMjUpO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMDttYXJnaW4tbGVmdDo0cHgiPlA8L3NwYW4+JyA6ICcnOwogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxMnB4O2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbTo2cHgiPicKICAgICAgKyAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4Ij48c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToxNnB4O2xldHRlci1zcGFjaW5nOjJweCI+JyArIGl0ZW0udGlja2VyICsgJzwvc3Bhbj4nICsgcGIgKyAnPC9kaXY+JwogICAgICArICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGNjICsgJyI+JyArIGNoZ1N0cihpdGVtLndlZWtfY2hnKSArICc8L2Rpdj4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj7Dlm5jZWtpOiAnICsgY2hnU3RyKGl0ZW0ucHJldl93ZWVrX2NoZykgKyAnPC9kaXY+JwogICAgICArICc8L2Rpdj48L2Rpdj4nOwogIH0KCiAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgLy8gSGVhZGVyCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KTttYXJnaW4tYm90dG9tOjRweCI+8J+TiCBIYWZ0YWzEsWsgUGVyZm9ybWFucyDDlnpldGk8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JyArICh3ZC5nZW5lcmF0ZWQgfHwgJycpICsgJzwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gUGl5YXNhIHZzIFBvcnRmw7Z5CiAgdmFyIHNwQ2hnID0gc3AuY2hhbmdlIHx8IDA7CiAgdmFyIG5hc0NoZyA9IG5hcy5jaGFuZ2UgfHwgMDsKICB2YXIgcG9ydEF2ZyA9IHBvcnQubGVuZ3RoID8gTWF0aC5yb3VuZChwb3J0LnJlZHVjZShmdW5jdGlvbihhLGIpe3JldHVybiBhK2Iud2Vla19jaGc7fSwwKS9wb3J0Lmxlbmd0aCoxMDApLzEwMCA6IDA7CiAgdmFyIGFscGhhID0gTWF0aC5yb3VuZCgocG9ydEF2ZyAtIHNwQ2hnKSoxMDApLzEwMDsKICB2YXIgYWxwaGFDb2wgPSBhbHBoYSA+PSAwID8gJ3ZhcigtLWdyZWVuKScgOiAndmFyKC0tcmVkMiknOwoKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDE0MHB4LDFmcikpO2dhcDoxMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5Qb3J0ZsO2eSBPcnQuPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicgKyBjaGdDb2xvcihwb3J0QXZnKSArICciPicgKyBjaGdTdHIocG9ydEF2ZykgKyAnPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5TJlAgNTAwPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2NvbG9yOicgKyBjaGdDb2xvcihzcENoZykgKyAnIj4nICsgY2hnU3RyKHNwQ2hnKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPk5BU0RBUTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonICsgY2hnQ29sb3IobmFzQ2hnKSArICciPicgKyBjaGdTdHIobmFzQ2hnKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JyArIChhbHBoYT49MD8ncmdiYSgxNiwxODUsMTI5LC4wOCknOidyZ2JhKDIzOSw2OCw2OCwuMDgpJykgKyAnO2JvcmRlcjoxcHggc29saWQgJyArIChhbHBoYT49MD8ncmdiYSgxNiwxODUsMTI5LC4yNSknOidyZ2JhKDIzOSw2OCw2OCwuMjUpJykgKyAnO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5BbHBoYSAodnMgUyZQKTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonICsgYWxwaGFDb2wgKyAnIj4nICsgKGFscGhhPj0wPycrJzonJykgKyBhbHBoYSArICclPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBFbiBpeWkgLyBlbiBrw7Z0w7wKICBpZihiZXN0IHx8IHdvcnN0KXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyIDFmcjtnYXA6MTBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgICBpZihiZXN0KXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tZ3JlZW4pO21hcmdpbi1ib3R0b206NnB4Ij7wn4+GIEJ1IEhhZnRhbsSxbiBFbiDEsHlpc2k8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjI0cHg7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgYmVzdC50aWNrZXIgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPisnICsgYmVzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGlmKHdvcnN0KXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLXJlZDIpO21hcmdpbi1ib3R0b206NnB4Ij7wn5OJIEJ1IEhhZnRhbsSxbiBFbiBLw7Z0w7xzw7w8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjI0cHg7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgd29yc3QudGlja2VyICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicgKyB3b3JzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBQb3J0ZsO2eSBkZXRheQogIGlmKHBvcnQubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkrwgUG9ydGbDtnk8L2Rpdj4nOwogICAgcG9ydC5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0peyBoICs9IHBlcmZDYXJkKGl0ZW0pOyB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBTaW55YWxsZXIgb3pldGkKICB2YXIgYnV5Q291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nR1VDTFUgQUwnfHxyLnNpbnlhbD09PSdBTCc7fSkubGVuZ3RoOwogIHZhciBzZWxsQ291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nU0FUJzt9KS5sZW5ndGg7CiAgdmFyIHdhdGNoQ291bnQgPSAoVEZfREFUQVsnMWQnXXx8W10pLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nRElLS0FUJzt9KS5sZW5ndGg7CgogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5OKIEJ1IEhhZnRha2kgU2lueWFsbGVyPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXAiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPicgKyBidXlDb3VudCArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkFsIFNpbnlhbGk8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0teWVsbG93KSI+JyArIHdhdGNoQ291bnQgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5EaWtrYXQ8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nICsgc2VsbENvdW50ICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+U2F0IFNpbnlhbGk8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzwvZGl2PjwvZGl2Pic7CgogIC8vIFdhdGNobGlzdCBwZXJmb3JtYW5zCiAgaWYod2F0Y2gubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkYEgV2F0Y2hsaXN0PC9kaXY+JzsKICAgIHdhdGNoLmZvckVhY2goZnVuY3Rpb24oaXRlbSl7IGggKz0gcGVyZkNhcmQoaXRlbSk7IH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIGggKz0gJzwvZGl2Pic7CiAgcmV0dXJuIGg7Cn0KCmZ1bmN0aW9uIGJ1aWxkUnV0aW5IVE1MKCl7CiAgdmFyIGNoZWNrZWQgPSBsb2FkQ2hlY2tlZCgpOwogIHZhciB0b2RheSA9IG5ldyBEYXRlKCk7CiAgdmFyIGlzV2Vla2VuZCA9IHRvZGF5LmdldERheSgpID09PSAwIHx8IHRvZGF5LmdldERheSgpID09PSA2OwogIHZhciBkYXlOYW1lID0gWydQYXphcicsJ1BhemFydGVzaScsJ1NhbMSxJywnw4dhcsWfYW1iYScsJ1BlcsWfZW1iZScsJ0N1bWEnLCdDdW1hcnRlc2knXVt0b2RheS5nZXREYXkoKV07CiAgdmFyIGRhdGVTdHIgPSB0b2RheS50b0xvY2FsZURhdGVTdHJpbmcoJ3RyLVRSJywge2RheTonbnVtZXJpYycsbW9udGg6J2xvbmcnLHllYXI6J251bWVyaWMnfSk7CgogIC8vIFByb2dyZXNzIGhlc2FwbGEKICB2YXIgdG90YWxJdGVtcyA9IDA7CiAgdmFyIGRvbmVJdGVtcyA9IDA7CiAgdmFyIHNlY3Rpb25zID0gaXNXZWVrZW5kID8gWydoYWZ0YWxpayddIDogWydzYWJhaCcsJ29nbGVuJywnYWtzYW0nXTsKICBzZWN0aW9ucy5mb3JFYWNoKGZ1bmN0aW9uKGspewogICAgUlVUSU5fSVRFTVNba10uaXRlbXMuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsKICAgICAgdG90YWxJdGVtcysrOwogICAgICBpZihjaGVja2VkW2l0ZW0uaWRdKSBkb25lSXRlbXMrKzsKICAgIH0pOwogIH0pOwogIHZhciBwY3QgPSB0b3RhbEl0ZW1zID4gMCA/IE1hdGgucm91bmQoZG9uZUl0ZW1zL3RvdGFsSXRlbXMqMTAwKSA6IDA7CiAgdmFyIHBjdENvbCA9IHBjdD09PTEwMD8ndmFyKC0tZ3JlZW4pJzpwY3Q+PTUwPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tbXV0ZWQpJzsKCiAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgLy8gSGVhZGVyCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7ZmxleC13cmFwOndyYXA7Z2FwOjEwcHgiPic7CiAgaCArPSAnPGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrZGF5TmFtZSsnIFJ1dGluaTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK2RhdGVTdHIrJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjhweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JytwY3RDb2wrJyI+JytwY3QrJyU8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+Jytkb25lSXRlbXMrJy8nK3RvdGFsSXRlbXMrJyB0YW1hbWxhbmTEsTwvZGl2PjwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iaGVpZ2h0OjZweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czozcHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi10b3A6MTJweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJoZWlnaHQ6MTAwJTt3aWR0aDonK3BjdCsnJTtiYWNrZ3JvdW5kOicrcGN0Q29sKyc7Ym9yZGVyLXJhZGl1czozcHg7dHJhbnNpdGlvbjp3aWR0aCAuNXMgZWFzZSI+PC9kaXY+PC9kaXY+JzsKICBpZihwY3Q9PT0xMDApIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyO21hcmdpbi10b3A6MTBweDtmb250LXNpemU6MTRweDtjb2xvcjp2YXIoLS1ncmVlbikiPvCfjokgVMO8bSBtYWRkZWxlciB0YW1hbWxhbmTEsSE8L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIFNlY3Rpb25zCiAgc2VjdGlvbnMuZm9yRWFjaChmdW5jdGlvbihrKXsKICAgIHZhciBzZWMgPSBSVVRJTl9JVEVNU1trXTsKICAgIHZhciBzZWNEb25lID0gc2VjLml0ZW1zLmZpbHRlcihmdW5jdGlvbihpKXtyZXR1cm4gY2hlY2tlZFtpLmlkXTt9KS5sZW5ndGg7CiAgICB2YXIgc2VjVG90YWwgPSBzZWMuaXRlbXMubGVuZ3RoOwogICAgdmFyIHNlY1BjdCA9IE1hdGgucm91bmQoc2VjRG9uZS9zZWNUb3RhbCoxMDApOwogICAgdmFyIHNlY0NvbCA9IHNlY1BjdD09PTEwMD8ndmFyKC0tZ3JlZW4pJzpzZWNQY3Q+MD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLW11dGVkKSc7CgogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjEycHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrc2VjLmxhYmVsKyc8L2Rpdj4nOwogICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOicrc2VjQ29sKyc7Zm9udC13ZWlnaHQ6NjAwIj4nK3NlY0RvbmUrJy8nK3NlY1RvdGFsKyc8L3NwYW4+PC9kaXY+JzsKCiAgICBzZWMuaXRlbXMuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsKICAgICAgdmFyIGRvbmUgPSAhIWNoZWNrZWRbaXRlbS5pZF07CiAgICAgIHZhciBiZ0NvbG9yID0gZG9uZSA/ICdyZ2JhKDE2LDE4NSwxMjksLjA2KScgOiAncmdiYSgyNTUsMjU1LDI1NSwuMDIpJzsKICAgICAgdmFyIGJvcmRlckNvbG9yID0gZG9uZSA/ICdyZ2JhKDE2LDE4NSwxMjksLjIpJyA6ICdyZ2JhKDI1NSwyNTUsMjU1LC4wNSknOwogICAgICB2YXIgY2hlY2tCb3JkZXIgPSBkb25lID8gJ3ZhcigtLWdyZWVuKScgOiAndmFyKC0tbXV0ZWQpJzsKICAgICAgdmFyIGNoZWNrQmcgPSBkb25lID8gJ3ZhcigtLWdyZWVuKScgOiAndHJhbnNwYXJlbnQnOwogICAgICB2YXIgdGV4dENvbG9yID0gZG9uZSA/ICd2YXIoLS1tdXRlZCknIDogJ3ZhcigtLXRleHQpJzsKICAgICAgdmFyIHRleHREZWNvID0gZG9uZSA/ICdsaW5lLXRocm91Z2gnIDogJ25vbmUnOwogICAgICB2YXIgY2hlY2ttYXJrID0gZG9uZSA/ICc8c3ZnIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cG9seWxpbmUgcG9pbnRzPSIyLDYgNSw5IDEwLDMiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+PC9zdmc+JyA6ICcnOwogICAgICBoICs9ICc8ZGl2IG9uY2xpY2s9InRvZ2dsZUNoZWNrKFwnJyArIGl0ZW0uaWQgKyAnXCcpIiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmZsZXgtc3RhcnQ7Z2FwOjEycHg7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6OHB4O2N1cnNvcjpwb2ludGVyO21hcmdpbi1ib3R0b206NnB4O2JhY2tncm91bmQ6JyArIGJnQ29sb3IgKyAnO2JvcmRlcjoxcHggc29saWQgJyArIGJvcmRlckNvbG9yICsgJyI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZmxleC1zaHJpbms6MDt3aWR0aDoyMHB4O2hlaWdodDoyMHB4O2JvcmRlci1yYWRpdXM6NXB4O2JvcmRlcjoycHggc29saWQgJyArIGNoZWNrQm9yZGVyICsgJztiYWNrZ3JvdW5kOicgKyBjaGVja0JnICsgJztkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7bWFyZ2luLXRvcDoxcHgiPicgKyBjaGVja21hcmsgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2NvbG9yOicgKyB0ZXh0Q29sb3IgKyAnO2xpbmUtaGVpZ2h0OjEuNTt0ZXh0LWRlY29yYXRpb246JyArIHRleHREZWNvICsgJyI+JyArIGl0ZW0udGV4dCArICc8L3NwYW4+JzsKICAgICAgaCArPSAnPC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9KTsKCiAgLy8gSGFmdGEgacOnaSBvbGR1xJ91bmRhIGhhZnRhbMSxayBiw7Zsw7xtw7wgZGUgZ8O2c3RlciAoa2F0bGFuYWJpbGlyKQogIGlmKCFpc1dlZWtlbmQpewogICAgdmFyIGhTZWMgPSBSVVRJTl9JVEVNU1snaGFmdGFsaWsnXTsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wNCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjE1KTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOiM2MGE1ZmE7bWFyZ2luLWJvdHRvbTo0cHgiPicraFNlYy5sYWJlbCsnPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+UGF6YXIgYWvFn2FtxLEgeWFwxLFsYWNha2xhciDigJQgxZ91IGFuIGfDtnN0ZXJpbSBtb2R1bmRhPC9kaXY+PC9kaXY+JzsKICB9CgogIC8vIFJlc2V0IGJ1dG9udQogIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyO21hcmdpbi10b3A6NnB4Ij4nOwogIGggKz0gJzxidXR0b24gb25jbGljaz0icmVzZXRSdXRpbigpIiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS1tdXRlZCk7cGFkZGluZzo4cHggMTZweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTJweDtjdXJzb3I6cG9pbnRlciI+8J+UhCBMaXN0ZXlpIFPEsWbEsXJsYTwvYnV0dG9uPic7CiAgaCArPSAnPC9kaXY+JzsKCiAgaCArPSAnPC9kaXY+JzsKICByZXR1cm4gaDsKfQoKZnVuY3Rpb24gY2xvc2VNKGUpewogIGlmKCFlfHxlLnRhcmdldD09PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJvdmVybGF5IikpewogICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm92ZXJsYXkiKS5jbGFzc0xpc3QucmVtb3ZlKCJvcGVuIik7CiAgICBpZihtQ2hhcnQpe21DaGFydC5kZXN0cm95KCk7bUNoYXJ0PW51bGw7fQogIH0KfQoKcmVuZGVyU3RhdHMoKTsKcmVuZGVyRGFzaGJvYXJkKCk7CgoKCi8vIOKUgOKUgCBMxLBTVEUgRMOcWkVOTEVNRSDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAKdmFyIGVkaXRXYXRjaGxpc3QgPSBbXTsKdmFyIGVkaXRQb3J0Zm9saW8gPSBbXTsKCmZ1bmN0aW9uIG9wZW5FZGl0TGlzdCgpewogIGVkaXRXYXRjaGxpc3QgPSBURl9EQVRBWycxZCddLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KS5tYXAoZnVuY3Rpb24ocil7cmV0dXJuIHIudGlja2VyO30pOwogIGVkaXRQb3J0Zm9saW8gPSBQT1JULnNsaWNlKCk7CiAgcmVuZGVyRWRpdExpc3RzKCk7CiAgLy8gTG9hZCBzYXZlZCB0b2tlbiBmcm9tIGxvY2FsU3RvcmFnZQogIHZhciBzYXZlZCA9IGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdnaF90b2tlbicpOwogIGlmKHNhdmVkKSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ2hUb2tlbklucHV0IikudmFsdWUgPSBzYXZlZDsKICB2YXIgdHM9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInRva2VuU2VjdGlvbiIpOyBpZih0cykgdHMuc3R5bGUuZGlzcGxheT0ibm9uZSI7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImVkaXRQb3B1cCIpLmNsYXNzTGlzdC5hZGQoIm9wZW4iKTsKfQoKCmZ1bmN0aW9uIHRvZ2dsZVRva2VuU2VjdGlvbigpewogIHZhciBzPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0b2tlblNlY3Rpb24iKTsKICBpZihzKSBzLnN0eWxlLmRpc3BsYXk9cy5zdHlsZS5kaXNwbGF5PT09Im5vbmUiPyJibG9jayI6Im5vbmUiOwp9CgpmdW5jdGlvbiBzYXZlVG9rZW4oKXsKICB2YXIgdD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ2hUb2tlbklucHV0IikudmFsdWUudHJpbSgpOwogIGlmKCF0KXthbGVydCgiVG9rZW4gYm9zISIpO3JldHVybjt9CiAgbG9jYWxTdG9yYWdlLnNldEl0ZW0oImdoX3Rva2VuIix0KTsKICB2YXIgdHM9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInRva2VuU2VjdGlvbiIpOyBpZih0cykgdHMuc3R5bGUuZGlzcGxheT0ibm9uZSI7CiAgc2V0RWRpdFN0YXR1cygi4pyFIFRva2VuIGtheWRlZGlsZGkiLCJncmVlbiIpOwp9CgpmdW5jdGlvbiBjbG9zZUVkaXRQb3B1cChlKXsKICBpZighZXx8ZS50YXJnZXQ9PT1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFBvcHVwIikpewogICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImVkaXRQb3B1cCIpLmNsYXNzTGlzdC5yZW1vdmUoIm9wZW4iKTsKICB9Cn0KCmZ1bmN0aW9uIHJlbmRlckVkaXRMaXN0cygpewogIHZhciB3ZSA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ3YXRjaGxpc3RFZGl0b3IiKTsKICB2YXIgcGUgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgicG9ydGZvbGlvRWRpdG9yIik7CiAgaWYoIXdlfHwhcGUpIHJldHVybjsKCiAgd2UuaW5uZXJIVE1MID0gZWRpdFdhdGNobGlzdC5tYXAoZnVuY3Rpb24odCxpKXsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtwYWRkaW5nOjVweCA4cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjVweDttYXJnaW4tYm90dG9tOjRweCI+JwogICAgICArJzxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwIj4nK3QrJzwvc3Bhbj4nCiAgICAgICsnPGJ1dHRvbiBjbGFzcz0icm0td2F0Y2gtYnRuIiBkYXRhLWlkeD0iJytpKyciIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Ym9yZGVyOm5vbmU7Y29sb3I6dmFyKC0tcmVkMik7d2lkdGg6MjBweDtoZWlnaHQ6MjBweDtib3JkZXItcmFkaXVzOjRweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTJweCI+4pyVPC9idXR0b24+JwogICAgICArJzwvZGl2Pic7CiAgfSkuam9pbignJyk7CgogIC8vIEFkZCBjbGljayBoYW5kbGVycwogIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsKICAgIGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJy5ybS13YXRjaC1idG4nKS5mb3JFYWNoKGZ1bmN0aW9uKGJ0bil7CiAgICAgIGJ0bi5vbmNsaWNrPWZ1bmN0aW9uKCl7cmVtb3ZlVGlja2VyKCd3YXRjaCcsK3RoaXMuZGF0YXNldC5pZHgpO307CiAgICB9KTsKICAgIGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJy5ybS1wb3J0LWJ0bicpLmZvckVhY2goZnVuY3Rpb24oYnRuKXsKICAgICAgYnRuLm9uY2xpY2s9ZnVuY3Rpb24oKXtyZW1vdmVUaWNrZXIoJ3BvcnQnLCt0aGlzLmRhdGFzZXQuaWR4KTt9OwogICAgfSk7CiAgfSwwKTsKICBwZS5pbm5lckhUTUwgPSBlZGl0UG9ydGZvbGlvLm1hcChmdW5jdGlvbih0LGkpewogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO3BhZGRpbmc6NXB4IDhweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6NXB4O21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nK3QrJzwvc3Bhbj4nCiAgICAgICsnPGJ1dHRvbiBjbGFzcz0icm0tcG9ydC1idG4iIGRhdGEtaWR4PSInK2krJyIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtib3JkZXI6bm9uZTtjb2xvcjp2YXIoLS1yZWQyKTt3aWR0aDoyMHB4O2hlaWdodDoyMHB4O2JvcmRlci1yYWRpdXM6NHB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxMnB4Ij7inJU8L2J1dHRvbj4nCiAgICAgICsnPC9kaXY+JzsKICB9KS5qb2luKCcnKTsKfQoKZnVuY3Rpb24gYWRkVGlja2VyKGxpc3QpewogIHZhciBpbnB1dElkID0gbGlzdD09PSd3YXRjaCc/Im5ld1dhdGNoVGlja2VyIjoibmV3UG9ydFRpY2tlciI7CiAgdmFyIHZhbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKGlucHV0SWQpLnZhbHVlLnRyaW0oKS50b1VwcGVyQ2FzZSgpOwogIGlmKCF2YWwpIHJldHVybjsKICBpZihsaXN0PT09J3dhdGNoJyAmJiAhZWRpdFdhdGNobGlzdC5pbmNsdWRlcyh2YWwpKSBlZGl0V2F0Y2hsaXN0LnB1c2godmFsKTsKICBpZihsaXN0PT09J3BvcnQnICAmJiAhZWRpdFBvcnRmb2xpby5pbmNsdWRlcyh2YWwpKSBlZGl0UG9ydGZvbGlvLnB1c2godmFsKTsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZChpbnB1dElkKS52YWx1ZSA9ICIiOwogIHJlbmRlckVkaXRMaXN0cygpOwp9CgpmdW5jdGlvbiByZW1vdmVUaWNrZXIobGlzdCwgaWR4KXsKICBpZihsaXN0PT09J3dhdGNoJykgZWRpdFdhdGNobGlzdC5zcGxpY2UoaWR4LDEpOwogIGVsc2UgZWRpdFBvcnRmb2xpby5zcGxpY2UoaWR4LDEpOwogIHJlbmRlckVkaXRMaXN0cygpOwp9CgpmdW5jdGlvbiBzYXZlTGlzdFRvR2l0aHViKCl7CiAgdmFyIHRva2VuID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdoVG9rZW5JbnB1dCIpLnZhbHVlLnRyaW0oKTsKICBpZighdG9rZW4peyBzZXRFZGl0U3RhdHVzKCLinYwgVG9rZW4gZ2VyZWtsaSDigJQga3V0dXlhIGdpciIsInJlZCIpOyByZXR1cm47IH0KICBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgnZ2hfdG9rZW4nLCB0b2tlbik7CgogIHZhciBjb25maWcgPSB7IHdhdGNobGlzdDogZWRpdFdhdGNobGlzdCwgcG9ydGZvbGlvOiBlZGl0UG9ydGZvbGlvIH07CiAgdmFyIGNvbnRlbnQgPSBKU09OLnN0cmluZ2lmeShjb25maWcsIG51bGwsIDIpOwogIHZhciBiNjQgPSBidG9hKHVuZXNjYXBlKGVuY29kZVVSSUNvbXBvbmVudChjb250ZW50KSkpOwoKICBzZXRFZGl0U3RhdHVzKCLwn5K+IEtheWRlZGlsaXlvci4uLiIsInllbGxvdyIpOwoKICB2YXIgYXBpVXJsID0gImh0dHBzOi8vYXBpLmdpdGh1Yi5jb20vcmVwb3MvZ2h1cnp6ei9jYW5zbGltL2NvbnRlbnRzL2NvbmZpZy5qc29uIjsKICB2YXIgaGVhZGVycyA9IHsiQXV0aG9yaXphdGlvbiI6InRva2VuICIrdG9rZW4sIkNvbnRlbnQtVHlwZSI6ImFwcGxpY2F0aW9uL2pzb24ifTsKCiAgLy8gRmlyc3QgZ2V0IGN1cnJlbnQgU0hBIGlmIGV4aXN0cwogIGZldGNoKGFwaVVybCwge2hlYWRlcnM6aGVhZGVyc30pCiAgICAudGhlbihmdW5jdGlvbihyKXsgcmV0dXJuIHIub2sgPyByLmpzb24oKSA6IG51bGw7IH0pCiAgICAudGhlbihmdW5jdGlvbihleGlzdGluZyl7CiAgICAgIHZhciBwYXlsb2FkID0gewogICAgICAgIG1lc3NhZ2U6ICJMaXN0ZSBndW5jZWxsZW5kaSAiICsgbmV3IERhdGUoKS50b0xvY2FsZURhdGVTdHJpbmcoInRyLVRSIiksCiAgICAgICAgY29udGVudDogYjY0CiAgICAgIH07CiAgICAgIGlmKGV4aXN0aW5nICYmIGV4aXN0aW5nLnNoYSkgcGF5bG9hZC5zaGEgPSBleGlzdGluZy5zaGE7CgogICAgICByZXR1cm4gZmV0Y2goYXBpVXJsLCB7CiAgICAgICAgbWV0aG9kOiJQVVQiLAogICAgICAgIGhlYWRlcnM6aGVhZGVycywKICAgICAgICBib2R5OkpTT04uc3RyaW5naWZ5KHBheWxvYWQpCiAgICAgIH0pOwogICAgfSkKICAgIC50aGVuKGZ1bmN0aW9uKHIpewogICAgICBpZihyLm9rIHx8IHIuc3RhdHVzPT09MjAxKXsKICAgICAgICBzZXRFZGl0U3RhdHVzKCLinIUgS2F5ZGVkaWxkaSEgQmlyIHNvbnJha2kgQ29sYWIgw6dhbMSxxZ90xLFybWFzxLFuZGEgYWt0aWYgb2x1ci4iLCJncmVlbiIpOwogICAgICAgIHNldFRpbWVvdXQoZnVuY3Rpb24oKXtjbG9zZUVkaXRQb3B1cCgpO30sMjAwMCk7CiAgICAgIH0gZWxzZSB7CiAgICAgICAgc2V0RWRpdFN0YXR1cygi4p2MIEhhdGE6ICIrci5zdGF0dXMrIiDigJQgVG9rZW7EsSBrb250cm9sIGV0IiwicmVkIik7CiAgICAgIH0KICAgIH0pCiAgICAuY2F0Y2goZnVuY3Rpb24oZSl7IHNldEVkaXRTdGF0dXMoIuKdjCBIYXRhOiAiK2UubWVzc2FnZSwicmVkIik7IH0pOwp9CgpmdW5jdGlvbiBzZXRFZGl0U3RhdHVzKG1zZywgY29sb3IpewogIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0U3RhdHVzIik7CiAgaWYoZWwpewogICAgZWwudGV4dENvbnRlbnQgPSBtc2c7CiAgICBlbC5zdHlsZS5jb2xvciA9IGNvbG9yPT09ImdyZWVuIj8idmFyKC0tZ3JlZW4pIjpjb2xvcj09PSJyZWQiPyJ2YXIoLS1yZWQyKSI6InZhcigtLXllbGxvdykiOwogIH0KfQoKCmZ1bmN0aW9uIHJlbmRlckhhZnRhbGlrKCl7CiAgdmFyIGdyaWQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogIHZhciB3ZCA9IFdFRUtMWV9EQVRBIHx8IHt9OwogIHZhciBwb3J0ID0gd2QucG9ydGZvbGlvIHx8IFtdOwogIHZhciB3YXRjaCA9IHdkLndhdGNobGlzdCB8fCBbXTsKICB2YXIgYmVzdCA9IHdkLmJlc3Q7CiAgdmFyIHdvcnN0ID0gd2Qud29yc3Q7CiAgdmFyIG1kID0gTUFSS0VUX0RBVEEgfHwge307CiAgdmFyIHNwID0gbWQuU1A1MDAgfHwge307CiAgdmFyIG5hcyA9IG1kLk5BU0RBUSB8fCB7fTsKICB2YXIgZGF0YTFkID0gVEZfREFUQVsnMWQnXSB8fCBbXTsKICB2YXIgZGF0YTF3ID0gVEZfREFUQVsnMXdrJ10gfHwgW107CgogIGZ1bmN0aW9uIGNjKHYpeyByZXR1cm4gdj49MD8ndmFyKC0tZ3JlZW4yKSc6J3ZhcigtLXJlZDIpJzsgfQogIGZ1bmN0aW9uIGNzKHYpeyByZXR1cm4gKHY+PTA/JysnOicnKSt2KyclJzsgfQoKICBmdW5jdGlvbiBwZXJmUm93KGl0ZW0pewogICAgdmFyIGNvbCA9IGNjKGl0ZW0ud2Vla19jaGcpOwogICAgdmFyIHBiID0gaXRlbS5wb3J0Zm9saW8gPyAnPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tbGVmdDo0cHgiPlA8L3NwYW4+JyA6ICcnOwogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO3BhZGRpbmc6OHB4IDEycHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6OHB4O21hcmdpbi1ib3R0b206NXB4Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtmb250LXNpemU6MTRweDtsZXR0ZXItc3BhY2luZzoxcHgiPicgKyBpdGVtLnRpY2tlciArIHBiICsgJzwvZGl2PicKICAgICAgKyAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+JwogICAgICArICc8ZGl2IHN0eWxlPSJmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGNvbCArICciPicgKyBjcyhpdGVtLndlZWtfY2hnKSArICc8L2Rpdj4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5PbmNla2k6ICcgKyBjcyhpdGVtLnByZXZfd2Vla19jaGcpICsgJzwvZGl2PicKICAgICAgKyAnPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciBwb3J0QXZnID0gcG9ydC5sZW5ndGggPyBNYXRoLnJvdW5kKHBvcnQucmVkdWNlKGZ1bmN0aW9uKGEsYil7cmV0dXJuIGErYi53ZWVrX2NoZzt9LDApL3BvcnQubGVuZ3RoKjEwMCkvMTAwIDogMDsKICB2YXIgc3BDaGcgPSBzcC5jaGFuZ2UgfHwgMDsKICB2YXIgbmFzQ2hnID0gbmFzLmNoYW5nZSB8fCAwOwogIHZhciBhbHBoYSA9IE1hdGgucm91bmQoKHBvcnRBdmctc3BDaGcpKjEwMCkvMTAwOwogIHZhciBhbHBoYUNvbCA9IGFscGhhPj0wPyd2YXIoLS1ncmVlbiknOid2YXIoLS1yZWQyKSc7CgogIHZhciBoID0gJzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CgogIC8vIEhlYWRlcgogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWJvdHRvbTo0cHgiPvCfk4ggSGFmdGFsxLFrIFBlcmZvcm1hbnMgw5Z6ZXRpPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicgKyAod2QuZ2VuZXJhdGVkfHwnJykgKyAnPC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBQaXlhc2EgdnMgUG9ydGZvbHlvCiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgxMzBweCwxZnIpKTtnYXA6MTBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgWwogICAge2xhYmVsOidQb3J0ZsO2eSBPcnQuJywgdmFsOnBvcnRBdmd9LAogICAge2xhYmVsOidTJlAgNTAwJywgdmFsOnNwQ2hnfSwKICAgIHtsYWJlbDonTkFTREFRJywgdmFsOm5hc0NoZ30sCiAgXS5mb3JFYWNoKGZ1bmN0aW9uKHgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij4nICsgeC5sYWJlbCArICc8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyBjYyh4LnZhbCkgKyAnIj4nICsgY3MoeC52YWwpICsgJzwvZGl2PjwvZGl2Pic7CiAgfSk7CiAgdmFyIGFCZyA9IGFscGhhPj0wPydyZ2JhKDE2LDE4NSwxMjksLjA4KSc6J3JnYmEoMjM5LDY4LDY4LC4wOCknOwogIHZhciBhQmQgPSBhbHBoYT49MD8ncmdiYSgxNiwxODUsMTI5LC4yNSknOidyZ2JhKDIzOSw2OCw2OCwuMjUpJzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicgKyBhQmcgKyAnO2JvcmRlcjoxcHggc29saWQgJyArIGFCZCArICc7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPkFscGhhICh2cyBTJlApPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGFscGhhQ29sICsgJyI+JyArIGNzKGFscGhhKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIEVuIGl5aSAvIGVuIGtvdHUKICBpZihiZXN0fHx3b3JzdCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogICAgaWYoYmVzdCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLWdyZWVuKTttYXJnaW4tYm90dG9tOjZweCI+8J+PhiBFbiDEsHlpPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2xldHRlci1zcGFjaW5nOjJweCI+JyArIGJlc3QudGlja2VyICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPisnICsgYmVzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGlmKHdvcnN0KXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLXJlZDIpO21hcmdpbi1ib3R0b206NnB4Ij7wn5OJIEVuIEvDtnTDvDwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtsZXR0ZXItc3BhY2luZzoycHgiPicgKyB3b3JzdC50aWNrZXIgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nICsgd29yc3Qud2Vla19jaGcgKyAnJTwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gU2lueWFsbGVyCiAgdmFyIGJ1eUMgID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nR1VDTFUgQUwnfHxyLnNpbnlhbD09PSdBTCc7fSkubGVuZ3RoOwogIHZhciB3YXJuQyA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J0RJS0tBVCc7fSkubGVuZ3RoOwogIHZhciBzZWxsQyA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J1NBVCc7fSkubGVuZ3RoOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5OKIFNpbnlhbGxlcjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2ZsZXgtd3JhcDp3cmFwIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nICsgYnV5QyArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkFsPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXllbGxvdykiPicgKyB3YXJuQyArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkRpa2thdDwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicgKyBzZWxsQyArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlNhdDwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPC9kaXY+PC9kaXY+JzsKCiAgLy8gMUcrMUggbW9tZW50dW0KICB2YXIgYm90aEJ1eSA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7CiAgICBpZihyLmhhdGEpIHJldHVybiBmYWxzZTsKICAgIHZhciB3ID0gZGF0YTF3LmZpbmQoZnVuY3Rpb24oeCl7cmV0dXJuIHgudGlja2VyPT09ci50aWNrZXI7fSk7CiAgICByZXR1cm4gKHIuc2lueWFsPT09J0dVQ0xVIEFMJ3x8ci5zaW55YWw9PT0nQUwnKSAmJiB3ICYmICh3LnNpbnlhbD09PSdHVUNMVSBBTCd8fHcuc2lueWFsPT09J0FMJyk7CiAgfSk7CiAgaWYoYm90aEJ1eS5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1ncmVlbik7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPuKaoSAxRyArIDFIIEFsIFNpbnlhbGk8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2ZsZXgtd3JhcDp3cmFwO2dhcDo4cHgiIGlkPSJib3RoQnV5Q29udGFpbmVyIj48L2Rpdj48L2Rpdj4nOwogIH0KCiAgLy8gVG9wIDMgZW50cnkgc2NvcmUKICB2YXIgdG9wRW50cnkgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pLnNvcnQoZnVuY3Rpb24oYSxiKXtyZXR1cm4gYi5lbnRyeV9zY29yZS1hLmVudHJ5X3Njb3JlO30pLnNsaWNlKDAsMyk7CiAgaWYodG9wRW50cnkubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfjq8gRW4gxLB5aSBHaXJpxZ8gS2FsaXRlc2k8L2Rpdj4nOwogICAgdmFyIG1lZGFscyA9IFsn8J+lhycsJ/CfpYgnLCfwn6WJJ107CiAgICB0b3BFbnRyeS5mb3JFYWNoKGZ1bmN0aW9uKHIsaSl7CiAgICAgIHZhciBlc2NvbCA9IHIuZW50cnlfc2NvcmU+PTc1Pyd2YXIoLS1ncmVlbiknOnIuZW50cnlfc2NvcmU+PTYwPyd2YXIoLS1ncmVlbjIpJzondmFyKC0teWVsbG93KSc7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47cGFkZGluZzo4cHggMTJweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo4cHg7bWFyZ2luLWJvdHRvbTo1cHgiIGlkPSJ0ZS0nICsgci50aWNrZXIgKyAnIj4nOwogICAgICBoICs9ICc8c3Bhbj4nICsgbWVkYWxzW2ldICsgJyA8c3Ryb25nPicgKyByLnRpY2tlciArICc8L3N0cm9uZz4gPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JyArIHIuc2lueWFsICsgJzwvc3Bhbj48L3NwYW4+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgZXNjb2wgKyAnIj4nICsgci5lbnRyeV9zY29yZSArICcvMTAwPC9zcGFuPjwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBTdG9wIHlha2luCiAgdmFyIG5lYXJTdG9wID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXsKICAgIGlmKHIuaGF0YXx8IVBPUlQuaW5jbHVkZXMoci50aWNrZXIpfHwhci5zdG9wKSByZXR1cm4gZmFsc2U7CiAgICByZXR1cm4gKHIuZml5YXQtci5zdG9wKS9yLmZpeWF0KjEwMCA8IDg7CiAgfSkuc29ydChmdW5jdGlvbihhLGIpe3JldHVybiAoYS5maXlhdC1hLnN0b3ApL2EuZml5YXQtKGIuZml5YXQtYi5zdG9wKS9iLmZpeWF0O30pOwogIGlmKG5lYXJTdG9wLmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1yZWQyKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+4pqg77iPIFN0b3AgU2V2aXllc2luZSBZYWvEsW48L2Rpdj4nOwogICAgbmVhclN0b3AuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgICAgdmFyIGRpc3QgPSBNYXRoLnJvdW5kKChyLmZpeWF0LXIuc3RvcCkvci5maXlhdCoxMDAwKS8xMDsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCIgaWQ9Im5zLScgKyByLnRpY2tlciArICciPic7CiAgICAgIGggKz0gJzxzdHJvbmc+JyArIHIudGlja2VyICsgJzwvc3Ryb25nPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLXJlZDIpO2ZvbnQtd2VpZ2h0OjYwMCI+U3RvcCAkJyArIHIuc3RvcCArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlV6YWtsxLFrOiAlJyArIGRpc3QgKyAnPC9kaXY+PC9kaXY+PC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIEhlZGVmZSB5YWtpbgogIHZhciBuZWFyVGFyZ2V0ID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXsKICAgIGlmKHIuaGF0YXx8IVBPUlQuaW5jbHVkZXMoci50aWNrZXIpfHwhci5oZWRlZikgcmV0dXJuIGZhbHNlOwogICAgcmV0dXJuIChyLmhlZGVmLXIuZml5YXQpL3IuZml5YXQqMTAwIDwgMTU7CiAgfSkuc29ydChmdW5jdGlvbihhLGIpe3JldHVybiAoYS5oZWRlZi1hLmZpeWF0KS9hLmZpeWF0LShiLmhlZGVmLWIuZml5YXQpL2IuZml5YXQ7fSk7CiAgaWYobmVhclRhcmdldC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn46vIEhlZGVmZSBZYWvEsW48L2Rpdj4nOwogICAgbmVhclRhcmdldC5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgICB2YXIgZGlzdCA9IE1hdGgucm91bmQoKHIuaGVkZWYtci5maXlhdCkvci5maXlhdCoxMDAwKS8xMDsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCI+JzsKICAgICAgaCArPSAnPHN0cm9uZz4nICsgci50aWNrZXIgKyAnPC9zdHJvbmc+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6IzYwYTVmYTtmb250LXdlaWdodDo2MDAiPkhlZGVmICQnICsgci5oZWRlZiArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkthbGRpOiAlJyArIGRpc3QgKyAnPC9kaXY+PC9kaXY+PC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIEVhcm5pbmdzCiAgdmFyIHVyZ2VudEUgPSBFQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gZS5kYXlzX3RvX2Vhcm5pbmdzIT1udWxsJiZlLmRheXNfdG9fZWFybmluZ3M8PTE0O30pLnNvcnQoZnVuY3Rpb24oYSxiKXtyZXR1cm4gYS5kYXlzX3RvX2Vhcm5pbmdzLWIuZGF5c190b19lYXJuaW5nczt9KTsKICBpZih1cmdlbnRFLmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLXllbGxvdyk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfk4UgWWFrbGHFn2FuIFJhcG9ybGFyPC9kaXY+JzsKICAgIHVyZ2VudEUuZm9yRWFjaChmdW5jdGlvbihlKXsKICAgICAgdmFyIGljID0gZS5hbGVydD09PSdyZWQnPyfwn5S0Jzon8J+foSc7CiAgICAgIHZhciBpblBvcnQgPSBQT1JULmluY2x1ZGVzKGUudGlja2VyKTsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCI+JzsKICAgICAgaCArPSAnPHNwYW4+JyArIGljICsgJyA8c3Ryb25nPicgKyBlLnRpY2tlciArICc8L3N0cm9uZz4nICsgKGluUG9ydD8nIDxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjEwcHgiPlA8L3NwYW4+JzonJykgKyAnPC9zcGFuPic7CiAgICAgIGggKz0gJzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1zaXplOjExcHgiPicgKyBlLm5leHRfZGF0ZSArICcgKCcgKyBlLmRheXNfdG9fZWFybmluZ3MgKyAnIGfDvG4pPC9zcGFuPjwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBWSVgKICB2YXIgdml4ID0gbWQuVklYIHx8IHt9OwogIGlmKHZpeC5wcmljZSl7CiAgICB2YXIgdkNvbCA9IHZpeC5wcmljZT4zMD8ndmFyKC0tcmVkMiknOnZpeC5wcmljZT4yMD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLWdyZWVuKSc7CiAgICB2YXIgdkxibCA9IHZpeC5wcmljZT4zMD8nWcO8a3NlayBLb3JrdSDigJQgWWVuaSBwb3ppc3lvbiBhw6dtYSc6dml4LnByaWNlPjIwPydPcnRhIFZvbGF0aWxpdGUg4oCUIERpa2thdGxpIG9sJzonRMO8xZ/DvGsgVm9sYXRpbGl0ZSDigJQgTm9ybWFsIGtvxZ91bGxhcic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE0cHggMTZweDttYXJnaW4tYm90dG9tOjEwcHg7ZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlciI+JzsKICAgIGggKz0gJzxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MnB4Ij5WSVg8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjonICsgdkNvbCArICciPicgKyB2TGJsICsgJzwvZGl2PjwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjhweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIHZDb2wgKyAnIj4nICsgdml4LnByaWNlICsgJzwvZGl2PjwvZGl2Pic7CiAgfQoKICAvLyBQb3J0Zm9seW8gZGV0YXkKICBpZihwb3J0Lmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5K8IFBvcnRmw7Z5PC9kaXY+JzsKICAgIHBvcnQuZm9yRWFjaChmdW5jdGlvbihpdGVtKXtoICs9IHBlcmZSb3coaXRlbSk7fSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gV2F0Y2hsaXN0CiAgaWYod2F0Y2gubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkYEgV2F0Y2hsaXN0PC9kaXY+JzsKICAgIHdhdGNoLmZvckVhY2goZnVuY3Rpb24oaXRlbSl7aCArPSBwZXJmUm93KGl0ZW0pO30pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIGggKz0gJzwvZGl2Pic7CiAgZ3JpZC5pbm5lckhUTUwgPSBoOwoKICAvLyBBZGQgb25jbGljayB2aWEgSlMgKGF2b2lkcyBxdW90ZSBuZXN0aW5nIGlzc3VlcykKICBib3RoQnV5LmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgY250ID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2JvdGhCdXlDb250YWluZXInKTsKICAgIGlmKCFjbnQpIHJldHVybjsKICAgIHZhciBkID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2Jyk7CiAgICBkLnN0eWxlLmNzc1RleHQgPSAnYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjhweCAxNHB4O2N1cnNvcjpwb2ludGVyJzsKICAgIGQuaW5uZXJIVE1MID0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDtsZXR0ZXItc3BhY2luZzoycHg7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nICsgci50aWNrZXIgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5HaXJpczogJyArIHIuZW50cnlfc2NvcmUgKyAnLzEwMDwvZGl2Pic7CiAgICBkLm9uY2xpY2sgPSAoZnVuY3Rpb24odCl7cmV0dXJuIGZ1bmN0aW9uKCl7b3Blbk0odCk7fTt9KShyLnRpY2tlcik7CiAgICBjbnQuYXBwZW5kQ2hpbGQoZCk7CiAgfSk7CiAgdG9wRW50cnkuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCd0ZS0nICsgci50aWNrZXIpOwogICAgaWYoZWwpIGVsLm9uY2xpY2sgPSAoZnVuY3Rpb24odCl7cmV0dXJuIGZ1bmN0aW9uKCl7b3Blbk0odCk7fTt9KShyLnRpY2tlciksIGVsLnN0eWxlLmN1cnNvcj0ncG9pbnRlcic7CiAgfSk7CiAgbmVhclN0b3AuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCducy0nICsgci50aWNrZXIpOwogICAgaWYoZWwpIGVsLm9uY2xpY2sgPSAoZnVuY3Rpb24odCl7cmV0dXJuIGZ1bmN0aW9uKCl7b3Blbk0odCk7fTt9KShyLnRpY2tlciksIGVsLnN0eWxlLmN1cnNvcj0ncG9pbnRlcic7CiAgfSk7Cn0KCgpmdW5jdGlvbiByZW5kZXJTY3JlZW5lcigpewogIHZhciBncmlkID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dyaWQnKTsKICB2YXIgZGF0YSA9IFNDUkVFTkVSX0RBVEEgfHwgW107CiAgdmFyIGNyaXRlcmlhID0gWwogICAge2lkOidlcHNfcW9xJywgICAgbGFiZWw6J0VQUyBRb1EgQsO8ecO8bWUnLCAgICAgbGltaXQ6Jz49MjAlJywgICAgdzozLCBpbXA6J2NyaXRpY2FsJ30sCiAgICB7aWQ6J3NtYTIwMCcsICAgICBsYWJlbDonU01BMjAwIMOcemVyaW5kZScsICAgICBsaW1pdDonUD5TTUEyMDAnLCB3OjMsIGltcDonY3JpdGljYWwnfSwKICAgIHtpZDonbWFya2V0JywgICAgIGxhYmVsOidNIEtyaXRlcmknLCAgICAgICAgICAgbGltaXQ6J0fDvMOnbMO8JywgICAgdzozLCBpbXA6J2NyaXRpY2FsJ30sCiAgICB7aWQ6J2Vwc19hY2NlbCcsICBsYWJlbDonRVBTIEjEsXpsYW5tYXPEsScsICAgICAgbGltaXQ6J0jEsXpsYW7EsXlvcicsdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOidyc19yYXRpbmcnLCAgbGFiZWw6J1JTIFJhdGluZycsICAgICAgICAgICBsaW1pdDonPj03MCcsICAgICB3OjIsIGltcDonaW1wb3J0YW50J30sCiAgICB7aWQ6J3Jldl9ncm93dGgnLCBsYWJlbDonR2VsaXIgQsO8ecO8bWVzaScsICAgICAgbGltaXQ6Jz49MTUlJywgICAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOidyb2UnLCAgICAgICAgbGFiZWw6J1JPRScsICAgICAgICAgICAgICAgICBsaW1pdDonPj0xNSUnLCAgICB3OjIsIGltcDonaW1wb3J0YW50J30sCiAgICB7aWQ6J2dyb3NzX21nJywgICBsYWJlbDonQnLDvHQgTWFyamluJywgICAgICAgICBsaW1pdDonPj00MCUnLCAgICB3OjIsIGltcDonaW1wb3J0YW50J30sCiAgICB7aWQ6J3NtYTUwJywgICAgICBsYWJlbDonU01BNTAgw5x6ZXJpbmRlJywgICAgICBsaW1pdDonUD5TTUE1MCcsICB3OjIsIGltcDonaW1wb3J0YW50J30sCiAgICB7aWQ6JzUydycsICAgICAgICBsYWJlbDonNTJIIFlha8SxbmzEsWsnLCAgICAgICAgbGltaXQ6Jz49NzUlJywgICAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOiduZXRfbWcnLCAgICAgbGFiZWw6J05ldCBNYXJqaW4nLCAgICAgICAgICBsaW1pdDonPj0xMCUnLCAgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidkZScsICAgICAgICAgbGFiZWw6J0JvcsOnL8OWemtheW5haycsICAgICAgIGxpbWl0Oic8PTEuMCcsICAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J2NyJywgICAgICAgICBsYWJlbDonQ3VycmVudCBSYXRpbycsICAgICAgIGxpbWl0Oic+PTEuNScsICAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J3BlJywgICAgICAgICBsYWJlbDonUC9FJywgICAgICAgICAgICAgICAgIGxpbWl0Oic8PTYwJywgICAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J21rdGNhcCcsICAgICBsYWJlbDonUGl5YXNhIERlxJ9lcmknLCAgICAgICBsaW1pdDonPj0xQicsICAgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidyZWxfdm9sJywgICAgbGFiZWw6J0fDtnJlY2VsaSBIYWNpbScsICAgICAgbGltaXQ6Jz49MC44eCcsICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDonYXZnX3ZvbCcsICAgIGxhYmVsOidPcnQuIEhhY2ltJywgICAgICAgICAgbGltaXQ6Jz49NTAwSycsICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDonaW5zdF9vd24nLCAgIGxhYmVsOidLdXJ1bXNhbCBTYWhpcGxpaycsICAgbGltaXQ6Jz49NDAlJywgICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDonaW5zdF90cmVuZCcsIGxhYmVsOidLdXJ1bXNhbCBUcmVuZCcsICAgICAgbGltaXQ6J0FydMSxeW9yJywgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgXTsKICB2YXIgTUFYX1cgPSAzNTsKCiAgaWYoIWRhdGEubGVuZ3RoKXsKICAgIGdyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xO3RleHQtYWxpZ246Y2VudGVyO3BhZGRpbmc6NDBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlNjcmVlbmVyIHZlcmlzaSB5b2sg4oCUIEFjdGlvbnMgUnVuIFdvcmtmbG93PC9kaXY+JzsKICAgIHJldHVybjsKICB9CgogIHZhciBwYXNzZWQgPSBkYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5wYXNzZWQ7fSk7CiAgdmFyIGZhaWxlZCA9IGRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5wYXNzZWQ7fSk7CiAgdmFyIFtleHBhbmRlZFRpY2tlciwgc2V0RXhwYW5kZWRdID0gW251bGwsIG51bGxdOwoKICBmdW5jdGlvbiBpbXBDb2xvcihpbXApewogICAgcmV0dXJuIGltcD09PSdjcml0aWNhbCc/J3ZhcigtLXJlZDIpJzppbXA9PT0naW1wb3J0YW50Jz8ndmFyKC0teWVsbG93KSc6J3ZhcigtLW11dGVkKSc7CiAgfQogIGZ1bmN0aW9uIGltcExhYmVsKGltcCl7CiAgICByZXR1cm4gaW1wPT09J2NyaXRpY2FsJz8n8J+UtCBaT1JVTkxVJzppbXA9PT0naW1wb3J0YW50Jz8n8J+foSDDlk5FTUzEsCc6J/CflLUgREVTVEVLJzsKICB9CgogIGZ1bmN0aW9uIGNyaXRlcmlhRGV0YWlsKHIpewogICAgdmFyIGggPSAnPGRpdiBzdHlsZT0icGFkZGluZzoxMnB4IDE0cHg7Ym9yZGVyLXRvcDoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpO2JhY2tncm91bmQ6dmFyKC0tYmczKSI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPktSxLBURVIgREVUQVlJIOKAlCBBxJ/EsXJsxLFrbMSxIFNrb3I6ICcrci53ZWlnaHRlZF9zY29yZSsnLycrci5tYXhfd2VpZ2h0ZWQrJyAoJScrci5wY3QrJyk8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnIgMWZyO2dhcDo0cHgiPic7CiAgICBjcml0ZXJpYS5mb3JFYWNoKGZ1bmN0aW9uKGMpewogICAgICB2YXIgY3IgPSByLmNyaXRlcmlhICYmIHIuY3JpdGVyaWFbYy5pZF07CiAgICAgIGlmKCFjcikgcmV0dXJuOwogICAgICB2YXIgbm9EYXRhID0gY3IuaGFzX2RhdGEgPT09IGZhbHNlOwogICAgICB2YXIgY29sID0gbm9EYXRhID8gJ3ZhcigtLW11dGVkKScgOiBjci5wYXNzZWQgPyAndmFyKC0tZ3JlZW4pJyA6IGltcENvbG9yKGMuaW1wKTsKICAgICAgdmFyIGJnID0gbm9EYXRhID8gJ3JnYmEoMjU1LDI1NSwyNTUsLjAyKScgOiBjci5wYXNzZWQgPyAncmdiYSgxNiwxODUsMTI5LC4wNiknIDogKGMuaW1wPT09J2NyaXRpY2FsJz8ncmdiYSgyMzksNjgsNjgsLjA4KSc6Yy5pbXA9PT0naW1wb3J0YW50Jz8ncmdiYSgyNDUsMTU4LDExLC4wNiknOidyZ2JhKDI1NSwyNTUsMjU1LC4wMiknKTsKICAgICAgdmFyIGJkID0gbm9EYXRhID8gJ3JnYmEoMjU1LDI1NSwyNTUsLjA1KScgOiBjci5wYXNzZWQgPyAncmdiYSgxNiwxODUsMTI5LC4yKScgOiAoYy5pbXA9PT0nY3JpdGljYWwnPydyZ2JhKDIzOSw2OCw2OCwuMiknOmMuaW1wPT09J2ltcG9ydGFudCc/J3JnYmEoMjQ1LDE1OCwxMSwuMiknOidyZ2JhKDI1NSwyNTUsMjU1LC4wNSknKTsKICAgICAgdmFyIGljb24gPSBub0RhdGEgPyAn4qycJyA6IGNyLnBhc3NlZCA/ICfinIUnIDogJ+KdjCc7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JytiZysnO2JvcmRlcjoxcHggc29saWQgJytiZCsnO2JvcmRlci1yYWRpdXM6NXB4O3BhZGRpbmc6NXB4IDhweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlciI+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6Jytjb2wrJyI+JytpY29uKycgJytjLmxhYmVsKyc8L3NwYW4+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK2ltcExhYmVsKGMuaW1wKS5zcGxpdCgnICcpWzBdKyc8L3NwYW4+PC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOicrKG5vRGF0YT8ndmFyKC0tbXV0ZWQpJzpjci5wYXNzZWQ/J3ZhcigtLXRleHQpJzpjb2wpKyciPicrY3IudmFsKycgPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtd2VpZ2h0OjQwMCI+JysoIW5vRGF0YT8nbGltaXQ6ICc6JycpK2MubGltaXQrJzwvc3Bhbj48L2Rpdj4nOwogICAgICBoICs9ICc8L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj48L2Rpdj4nOwogICAgcmV0dXJuIGg7CiAgfQoKICBmdW5jdGlvbiBzdG9ja1JvdyhyLCBleHBhbmRlZCl7CiAgICB2YXIgcGN0ID0gci5wY3Q7CiAgICB2YXIgY29sID0gcGN0Pj04MD8ndmFyKC0tZ3JlZW4pJzpwY3Q+PTYwPyd2YXIoLS1ncmVlbjIpJzpwY3Q+PTQwPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tcmVkMiknOwogICAgdmFyIHBiID0gci5pbl9wb3J0Zm9saW8/JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWxlZnQ6NHB4Ij5QPC9zcGFuPic6Jyc7CiAgICB2YXIgd2IgPSByLmluX3dhdGNobGlzdD8nPHNwYW4gc3R5bGU9ImNvbG9yOiM2MGE1ZmE7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWxlZnQ6NHB4Ij5XPC9zcGFuPic6Jyc7CiAgICB2YXIgY2hnQ29sID0gci5jaGFuZ2U+PTA/J3ZhcigtLWdyZWVuMiknOid2YXIoLS1yZWQyKSc7CiAgICB2YXIgY3JpdEZhaWwgPSBjcml0ZXJpYS5maWx0ZXIoZnVuY3Rpb24oYyl7cmV0dXJuIHIuY3JpdGVyaWEmJnIuY3JpdGVyaWFbYy5pZF0mJiFyLmNyaXRlcmlhW2MuaWRdLnBhc3NlZCYmYy5pbXA9PT0nY3JpdGljYWwnO30pOwogICAgdmFyIHdhcm5UYWdzID0gY3JpdEZhaWwubWFwKGZ1bmN0aW9uKGMpewogICAgICByZXR1cm4gJzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xKTtjb2xvcjp2YXIoLS1yZWQyKTtwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDttYXJnaW4tcmlnaHQ6M3B4Ij7inYwnK2MubGFiZWwrJzwvc3Bhbj4nOwogICAgfSkuam9pbignJyk7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImJvcmRlci1ib3R0b206MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA0KSIgaWQ9InNjLXJvdy0nK3IudGlja2VyKyciPicKICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjEzMHB4IDFmciA4MHB4IDgwcHg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDoxMHB4O3BhZGRpbmc6MTBweCAxNHB4O2N1cnNvcjpwb2ludGVyIiBpZD0ic2MtJytyLnRpY2tlcisnIj4nCiAgICAgICsnPGRpdj48ZGl2IHN0eWxlPSJmb250LXdlaWdodDo3MDA7Zm9udC1zaXplOjE0cHg7bGV0dGVyLXNwYWNpbmc6MXB4Ij4nK3IudGlja2VyK3BiK3diKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrci5uYW1lLnN1YnN0cmluZygwLDE4KSsnPC9kaXY+PC9kaXY+JwogICAgICArJzxkaXY+PGRpdiBzdHlsZT0iaGVpZ2h0OjRweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czoycHg7b3ZlcmZsb3c6aGlkZGVuIj4nCiAgICAgICsnPGRpdiBzdHlsZT0iaGVpZ2h0OjEwMCU7d2lkdGg6JytwY3QrJyU7YmFja2dyb3VuZDonK2NvbCsnO2JvcmRlci1yYWRpdXM6MnB4Ij48L2Rpdj48L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NHB4O21hcmdpbi10b3A6M3B4Ij4nK3dhcm5UYWdzCiAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK3Iuc2NvcmUrJy8xOTwvc3Bhbj4nCiAgICAgICsnPHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4xNSk7Y29sb3I6IzYwYTVmYTtwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo2MDAiPlJTOicrci5yc19yYXRpbmcrJzwvc3Bhbj4nCiAgICAgICsnPC9kaXY+PC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPjxkaXYgc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK2NvbCsnO2ZvbnQtc2l6ZToxNXB4Ij4nK3BjdCsnJTwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+YcSfxLFybMSxa2zEsTwvZGl2PjwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij48ZGl2IHN0eWxlPSJmb250LXdlaWdodDo2MDAiPiQnK3IucHJpY2UrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjonK2NoZ0NvbCsnIj4nKyhyLmNoYW5nZT49MD8nKyc6JycpK3IuY2hhbmdlKyclPC9kaXY+PC9kaXY+JwogICAgICArJzwvZGl2PicKICAgICAgKyhleHBhbmRlZCA/IGNyaXRlcmlhRGV0YWlsKHIpIDogJycpCiAgICAgICsnPC9kaXY+JzsKICB9CgogIGZ1bmN0aW9uIGJ1aWxkSFRNTCgpewogICAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgICAvLyBTdW1tYXJ5CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWJvdHRvbTo0cHgiPvCflI0gQ0FOU0xJTSBTY3JlZW5lcjwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbToxMnB4Ij4xNiBrcml0ZXIgwrcgMyDDtm5lbSBzZXZpeWVzaSDCtyAnK2RhdGEubGVuZ3RoKycgaGlzc2UgdGFyYW5kxLE8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2ZsZXgtd3JhcDp3cmFwO21hcmdpbi1ib3R0b206MTJweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nK3Bhc3NlZC5sZW5ndGgrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+R2XDp3RpPC9kaXY+PC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nK2ZhaWxlZC5sZW5ndGgrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+R2XDp2VtZWRpPC9kaXY+PC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Y29sb3I6IzYwYTVmYSI+JytkYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5pbl93YXRjaGxpc3R8fHIuaW5fcG9ydGZvbGlvO30pLmxlbmd0aCsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5MaXN0ZW1kZTwvZGl2PjwvZGl2Pic7CiAgICBoICs9ICc8L2Rpdj4nOwogICAgLy8gTGVnZW5kCiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXA7Zm9udC1zaXplOjEwcHgiPic7CiAgICBoICs9ICc8c3Bhbj7wn5S0IDxzdHJvbmc+Wm9ydW5sdTwvc3Ryb25nPiAoM3gpOiBFUFMgUW9RLCBTTUEyMDAsIE0gS3JpdGVyaTwvc3Bhbj4nOwogICAgaCArPSAnPHNwYW4+8J+foSA8c3Ryb25nPsOWbmVtbGk8L3N0cm9uZz4gKDJ4KTogR2VsaXIsIFJPRSwgTWFyamluLCBTTUE1MCwgNTJIPC9zcGFuPic7CiAgICBoICs9ICc8c3Bhbj7wn5S1IDxzdHJvbmc+RGVzdGVrPC9zdHJvbmc+ICgxeCk6IERpxJ9lcmxlcmk8L3NwYW4+JzsKICAgIGggKz0gJzwvZGl2PjwvZGl2Pic7CgogICAgLy8gR2XDp2VubGVyCiAgICBpZihwYXNzZWQubGVuZ3RoKXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjEycHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi1ib3R0b206MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0icGFkZGluZzoxMHB4IDE0cHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpO2ZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLWdyZWVuKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlIj7inIUgQ0FOU0xJTSBHZcOndGkgKCcrcGFzc2VkLmxlbmd0aCsnKTwvZGl2Pic7CiAgICAgIHBhc3NlZC5mb3JFYWNoKGZ1bmN0aW9uKHIpeyBoICs9IHN0b2NrUm93KHIsIHIudGlja2VyPT09ZXhwYW5kZWRUaWNrZXIpOyB9KTsKICAgICAgaCArPSAnPC9kaXY+JzsKICAgIH0KCiAgICAvLyBXYXRjaGxpc3QvUG9ydGZvbGlvIChnZcOnZW1leWVubGVyKQogICAgdmFyIG15RmFpbGVkID0gZmFpbGVkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5pbl93YXRjaGxpc3R8fHIuaW5fcG9ydGZvbGlvO30pOwogICAgaWYobXlGYWlsZWQubGVuZ3RoKXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4yKTtib3JkZXItcmFkaXVzOjEycHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi1ib3R0b206MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0icGFkZGluZzoxMHB4IDE0cHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpO2ZvbnQtc2l6ZToxMXB4O2NvbG9yOiM2MGE1ZmE7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZSI+8J+TiyBMaXN0ZW1kZSAoR2XDp2VtZWRpLCAnK215RmFpbGVkLmxlbmd0aCsnKTwvZGl2Pic7CiAgICAgIG15RmFpbGVkLmZvckVhY2goZnVuY3Rpb24ocil7IGggKz0gc3RvY2tSb3cociwgci50aWNrZXI9PT1leHBhbmRlZFRpY2tlcik7IH0pOwogICAgICBoICs9ICc8L2Rpdj4nOwogICAgfQoKICAgIGggKz0gJzwvZGl2Pic7CiAgICByZXR1cm4gaDsKICB9CgogIGdyaWQuaW5uZXJIVE1MID0gYnVpbGRIVE1MKCk7CgogIC8vIG9uY2xpY2sgaGFuZGxlcnMKICBkYXRhLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgZWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnc2MtJytyLnRpY2tlcik7CiAgICBpZihlbCl7CiAgICAgIGVsLm9uY2xpY2sgPSBmdW5jdGlvbihlKXsKICAgICAgICBlLnN0b3BQcm9wYWdhdGlvbigpOwogICAgICAgIGlmKGV4cGFuZGVkVGlja2VyPT09ci50aWNrZXIpeyBleHBhbmRlZFRpY2tlcj1udWxsOyB9CiAgICAgICAgZWxzZSB7IGV4cGFuZGVkVGlja2VyPXIudGlja2VyOyB9CiAgICAgICAgZ3JpZC5pbm5lckhUTUwgPSBidWlsZEhUTUwoKTsKICAgICAgICAvLyBSZS1hdHRhY2ggaGFuZGxlcnMKICAgICAgICBkYXRhLmZvckVhY2goZnVuY3Rpb24ocjIpewogICAgICAgICAgdmFyIGVsMiA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdzYy0nK3IyLnRpY2tlcik7CiAgICAgICAgICBpZihlbDIpIGVsMi5vbmNsaWNrID0gYXJndW1lbnRzLmNhbGxlZS5iaW5kKHt0aWNrZXI6cjIudGlja2VyfSk7CiAgICAgICAgfSk7CiAgICAgICAgYXR0YWNoSGFuZGxlcnMoKTsKICAgICAgfTsKICAgIH0KICB9KTsKCiAgZnVuY3Rpb24gYXR0YWNoSGFuZGxlcnMoKXsKICAgIGRhdGEuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgICAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3NjLScrci50aWNrZXIpOwogICAgICBpZighZWwpIHJldHVybjsKICAgICAgZWwub25jbGljayA9IChmdW5jdGlvbih0aWNrZXIpewogICAgICAgIHJldHVybiBmdW5jdGlvbihlKXsKICAgICAgICAgIGUuc3RvcFByb3BhZ2F0aW9uKCk7CiAgICAgICAgICBleHBhbmRlZFRpY2tlciA9IGV4cGFuZGVkVGlja2VyPT09dGlja2VyID8gbnVsbCA6IHRpY2tlcjsKICAgICAgICAgIGdyaWQuaW5uZXJIVE1MID0gYnVpbGRIVE1MKCk7CiAgICAgICAgICBhdHRhY2hIYW5kbGVycygpOwogICAgICAgIH07CiAgICAgIH0pKHIudGlja2VyKTsKICAgIH0pOwogIH0KICBhdHRhY2hIYW5kbGVycygpOwp9CgoKZnVuY3Rpb24gcmVuZGVyRGlyZWN0aW9uKCl7CiAgdmFyIGdyaWQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dyaWQnKTsKICBpZihncmlkKXtncmlkLnN0eWxlLmRpc3BsYXk9Jyc7Z3JpZC5zdHlsZS53aWR0aD0nJzt9CiAgdmFyIEQ9RElSRUNUSU9OX0RBVEF8fHt9OwogIHZhciBNRVRBPXsKICAgIHVwdHJlbmQ6e2ljOidcdWQ4M2RcdWRmZTInLGxibDonVGV5aXRsaSBZXHUwMGZja3NlbGlcdTAxNWYnLGFkdjonUGl2b3Qga1x1MDEzMXJhbiBsaWRlcmxlcmUgbm9ybWFsIHBvemlzeW9ubGEgZ2lyaWxlYmlsaXIuJyxjOid2YXIoLS1ncmVlbiknLGJnOidyZ2JhKDE2LDE4NSwxMjksLjA4KScsYmQ6J3JnYmEoMTYsMTg1LDEyOSwuMjUpJ30sCiAgICBwcmVzc3VyZTp7aWM6J1x1ZDgzZFx1ZGZlMScsbGJsOidCYXNrXHUwMTMxIEFsdFx1MDEzMW5kYScsYWR2OidZZW5pIGFsXHUwMTMxbSB5YXBtYS4gU3RvcCBzZXZpeWVsZXJpbmkgc1x1MDEzMWtcdTAxMzFsYVx1MDE1ZnRcdTAxMzFyLCB6YXlcdTAxMzFmIHBvemlzeW9ubGFyXHUwMTMxIGF6YWx0LicsYzondmFyKC0teWVsbG93KScsYmc6J3JnYmEoMjQ1LDE1OCwxMSwuMDgpJyxiZDoncmdiYSgyNDUsMTU4LDExLC4yNSknfSwKICAgIGNvcnJlY3Rpb246e2ljOidcdWQ4M2RcdWRkMzQnLGxibDonRFx1MDBmY3plbHRtZScsYWR2OidOYWtpdHRlIChTR09WKSBiZWtsZS4gV2F0Y2hsaXN0XHUyMDE5aSBnXHUwMGZjbmNlbGxlLCBmb2xsb3ctdGhyb3VnaCBkYXkgc2lueWFsaW5pIGl6bGUuJyxjOid2YXIoLS1yZWQyKScsYmc6J3JnYmEoMjM5LDY4LDY4LC4wOCknLGJkOidyZ2JhKDIzOSw2OCw2OCwuMjUpJ30sCiAgICByYWxseTp7aWM6J1x1ZDgzZFx1ZGZlMCcsbGJsOidUb3Bhcmxhbm1hIERlbmVtZXNpJyxhZHY6J0hlblx1MDBmY3ogZ2lybWUgXHUyMDE0IEZURCBwZW5jZXJlc2kgYVx1MDBlN1x1MDEzMWxcdTAxMzF5b3IuIEhhY2ltbGkgJTEuNSsgeVx1MDBmY2tzZWxpXHUwMTVmIGdcdTAwZmNuXHUwMGZjblx1MDBmYyBiZWtsZS4nLGM6J3ZhcigtLXllbGxvdyknLGJnOidyZ2JhKDI0NSwxNTgsMTEsLjA4KScsYmQ6J3JnYmEoMjQ1LDE1OCwxMSwuMjUpJ30sCiAgICBmdGQ6e2ljOidcdTI2YTEnLGxibDonRk9MTE9XLVRIUk9VR0ggREFZIScsYWR2OidLYWRlbWVsaSBnaXJpXHUwMTVmIGJhXHUwMTVmbGF0OiBrXHUwMGZjXHUwMGU3XHUwMGZjayBwb3ppc3lvbmxhIHRlc3QgZXQsIHBpeWFzYSBoYWtsXHUwMTMxIFx1MDBlN1x1MDEzMWthclx1MDEzMXJzYSBiXHUwMGZjeVx1MDBmY3QuJyxjOid2YXIoLS1ncmVlbiknLGJnOidyZ2JhKDE2LDE4NSwxMjksLjEpJyxiZDoncmdiYSgxNiwxODUsMTI5LC4zNSknfQogIH07CiAgdmFyIGg9JzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CiAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1ib3R0b206NHB4Ij5cdWQ4M2RcdWRjY2EgUGl5YXNhIFlcdTAwZjZuXHUwMGZjIFx1MjAxNCBGVEQgVGFraWJpPC9kaXY+JzsKICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xpbmUtaGVpZ2h0OjEuNiI+Rm9sbG93LXRocm91Z2ggZGF5OiBkaXB0ZW4gNC0xMCBnXHUwMGZjbiBzb25yYSBnZWxlbiBoYWNpbWxpICUxLjUrIHlcdTAwZmNrc2VsaVx1MDE1ZiBnXHUwMGZjblx1MDBmYyBcdTIwMTQgeWVuaSB5XHUwMGZja3NlbGlcdTAxNWYgdHJlbmRpbmkgdGV5aXQgZWRlci4gRGFcdTAxMWZcdTAxMzF0XHUwMTMxbSBnXHUwMGZjblx1MDBmYzogYXJ0YW4gaGFjaW1sZSAlMC4yKyBkXHUwMGZjXHUwMTVmXHUwMGZjXHUwMTVmIFx1MjAxNCBrdXJ1bXNhbCBzYXRcdTAxMzFcdTAxNWYgaXppLiAyNSBnXHUwMGZjbmRlIDUrIGRhXHUwMTFmXHUwMTMxdFx1MDEzMW0gPSBwaXlhc2EgYmFza1x1MDEzMSBhbHRcdTAxMzFuZGEuPC9kaXY+PC9kaXY+JzsKICBbJ1NQNTAwJywnTkFTREFRJ10uZm9yRWFjaChmdW5jdGlvbihuYW1lKXsKICAgIHZhciBkPURbbmFtZV18fHt9OwogICAgaWYoZC5lcnJvcnx8ZC5zdGF0dXM9PT11bmRlZmluZWQpe2grPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytuYW1lKyc6IHZlcmkgeW9rPC9kaXY+JztyZXR1cm47fQogICAgdmFyIG09TUVUQVtkLnN0YXR1c118fE1FVEEucHJlc3N1cmU7CiAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonK20uYmcrJztib3JkZXI6MXB4IHNvbGlkICcrbS5iZCsnO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjEycHgiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtmbGV4LXdyYXA6d3JhcDtnYXA6OHB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGgrPSc8ZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHgiPicrKG5hbWU9PT0nU1A1MDAnPydTJlAgNTAwJzonTkFTREFRJykrJzwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrbS5jKyciPicrbS5pYysnICcrbS5sYmwrJzwvZGl2PjwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlppcnZlZGVuOiA8c3BhbiBzdHlsZT0iZm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrKGQuZHJhd2Rvd248PS04Pyd2YXIoLS1yZWQyKSc6ZC5kcmF3ZG93bjw9LTQ/J3ZhcigtLXllbGxvdyknOid2YXIoLS1ncmVlbiknKSsnIj4lJytkLmRyYXdkb3duKyc8L3NwYW4+PC9kaXY+PC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS10ZXh0KTtiYWNrZ3JvdW5kOnJnYmEoMjU1LDI1NSwyNTUsLjAzKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTJweDttYXJnaW4tYm90dG9tOjEwcHgiPlx1ZDgzZFx1ZGNhMSAnK20uYWR2Kyc8L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMTQwcHgsMWZyKSk7Z2FwOjhweCI+JzsKICAgIHZhciBkY29sPWQuZGlzdF9jb3VudD49NT8ndmFyKC0tcmVkMiknOmQuZGlzdF9jb3VudD49Mz8ndmFyKC0teWVsbG93KSc6J3ZhcigtLWdyZWVuKSc7CiAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweCI+REFcdTAxMWVJVElNIEdcdTAwZGNOXHUwMGRjICgyNUcpPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrZGNvbCsnIj4nK2QuZGlzdF9jb3VudCsnIC8gNTwvZGl2PjwvZGl2Pic7CiAgICBpZihkLmZ0ZCl7CiAgICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjMpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4Ij5GVEQ8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTRweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nK2QuZnRkLmRhdGUrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLWdyZWVuKSI+KyUnK2QuZnRkLmdhaW4rJyAoJytkLmZ0ZC5kYXkrJy4gZ1x1MDBmY24pPC9kaXY+PC9kaXY+JzsKICAgIH0gZWxzZSBpZihkLnJhbGx5X2RheT4wKXsKICAgICAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHgiPlRPUEFSTEFOTUE8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0teWVsbG93KSI+JytkLnJhbGx5X2RheSsnLiBnXHUwMGZjbjwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5GVEQgcGVuY2VyZXNpOiA0LTEwLiBnXHUwMGZjbjwvZGl2PjwvZGl2Pic7CiAgICAgIGlmKGQucmFsbHlfbG93KSBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweCI+XHUwMTMwUFRBTCBTRVZcdTAxMzBZRVNcdTAxMzA8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicrZC5yYWxseV9sb3crJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5kZW5lbWUgZGliaSBrXHUwMTMxclx1MDEzMWxcdTAxMzFyc2Egc2F5YVx1MDBlNyBzXHUwMTMxZlx1MDEzMXJsYW5cdTAxMzFyPC9kaXY+PC9kaXY+JzsKICAgIH0gZWxzZSB7CiAgICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4Ij5UT1BBUkxBTk1BPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLW11dGVkKSI+XHUyMDE0PC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGgrPSc8L2Rpdj4nOwogICAgaWYoZC5kaXN0X2RheXMmJmQuZGlzdF9kYXlzLmxlbmd0aCl7CiAgICAgIGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW4tdG9wOjEwcHg7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5Tb24gZGFcdTAxMWZcdTAxMzF0XHUwMTMxbSBnXHUwMGZjbmxlcmk6ICcrZC5kaXN0X2RheXMubWFwKGZ1bmN0aW9uKHgpe3JldHVybiB4LmRhdGUrJyAoJyt4LmNoZysnJSknO30pLmpvaW4oJyBcdTAwYjcgJykrJzwvZGl2Pic7CiAgICB9CiAgICBoKz0nPC9kaXY+JzsKICB9KTsKICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHgiPic7CiAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+XHVkODNkXHVkY2NiIDMgQWRcdTAxMzFtbFx1MDEzMSBQbGFuPC9kaXY+JzsKICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7bGluZS1oZWlnaHQ6MS44O2NvbG9yOnZhcigtLXRleHQpIj4nOwogIGgrPScxXHVmZTBmXHUyMGUzIDxzdHJvbmc+RFx1MDBmY3plbHRtZWRlOjwvc3Ryb25nPiBOYWtpdCBTR09WXHUyMDE5ZGEgYmVrbGVyLCBtZXZjdXQgcG96aXN5b25sYXJkYSBzdG9wIGRpc2lwbGluaS48YnI+JzsKICBoKz0nMlx1ZmUwZlx1MjBlMyA8c3Ryb25nPkJla2xlcmtlbjo8L3N0cm9uZz4gU2NyZWVuZXIgKyBEZVx1MDExZmVybGVtZSBzZWttZXNpeWxlIFJTXHUyMDE5aSB5XHUwMGZja3NlaywgYmF6IHlhcGFuIGxpZGVybGVyaSBpXHUwMTVmYXJldGxlLjxicj4nOwogIGgrPSczXHVmZTBmXHUyMGUzIDxzdHJvbmc+RlREIGdlbGluY2U6PC9zdHJvbmc+IEthZGVtZWxpIGdpcmlcdTAxNWYgXHUyMDE0IFx1MDBmNm5jZSBrXHUwMGZjXHUwMGU3XHUwMGZjayB0ZXN0IHBvemlzeW9udSwgdGV5aXQgZ2VsaXJzZSBwaXZvdCBrXHUwMTMxcmFubGFybGEgYlx1MDBmY3lcdTAwZmN0Lic7CiAgaCs9JzwvZGl2PjwvZGl2Pic7CiAgaCs9JzwvZGl2Pic7CiAgZ3JpZC5pbm5lckhUTUw9aDsKfQoKCgpmdW5jdGlvbiByZW5kZXJNaW5lcnZpbmkoKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgaWYoZ3JpZCl7IGdyaWQuc3R5bGUuZGlzcGxheT0nYmxvY2snOyBncmlkLnN0eWxlLndpZHRoPScxMDAlJzsgfQogIHZhciBkYXRhMWQgPSAoVEZfREFUQSAmJiBURl9EQVRBWycxZCddKSA/IFRGX0RBVEFbJzFkJ10gOiBbXTsKCiAgZnVuY3Rpb24gY2FsY1RyZW5kVGVtcGxhdGUocil7CiAgICB2YXIgc2NvcmUgPSAwOyB2YXIgZGV0YWlscyA9IFtdOwogICAgdmFyIGMxID0gci5hYm92ZTUwOwogICAgZGV0YWlscy5wdXNoKHtsYWJlbDonRml5YXQgPiBTTUE1MCcsIHBhc3M6YzEsIHZhbDogYzEgPyAnRXZldCcgOiAnSGF5aXInLCB0aXA6J0ZpeWF0IDUwIGd1bmx1ayBvcnRhbGFtYW5pbiB1emVyaW5kZXlzZSBoaXNzZSBraXNhIHZhZGVkZSBndWNsdSBkZW1lay4nfSk7CiAgICBpZihjMSkgc2NvcmUrKzsKICAgIHZhciBjMiA9IHIuc21hMjAwICYmIHIuZml5YXQgPiByLnNtYTIwMCAqIDAuOTc7CiAgICBkZXRhaWxzLnB1c2goe2xhYmVsOidGaXlhdCA+IFNNQTE1MCcsIHBhc3M6YzIsIHZhbDogYzIgPyAnVGFobWluZW4gRXZldCcgOiAnSGF5aXInLCB0aXA6J09ydGEgdmFkZWxpIHRyZW5kLiBTTUEyMDBcJ2UgeWFraW4gZGVnZXIga3VsbGFuaWxpeW9yLid9KTsKICAgIGlmKGMyKSBzY29yZSsrOwogICAgdmFyIGMzID0gci5hYm92ZTIwMDsKICAgIGRldGFpbHMucHVzaCh7bGFiZWw6J0ZpeWF0ID4gU01BMjAwJywgcGFzczpjMywgdmFsOiBjMyA/ICdFdmV0JyA6ICdIYXlpcicsIHRpcDonVXp1biB2YWRlbGkgdHJlbmQg4oCUIGVuIGtyaXRpayBmaWx0cmUuIEJ1IG9sbWFkYW4gaGlzc2UgYWxpbm1hei4nfSk7CiAgICBpZihjMykgc2NvcmUrKzsKICAgIHZhciBjNCA9IHIuc21hNTAgJiYgci5zbWEyMDAgJiYgci5zbWE1MCA+IHIuc21hMjAwOwogICAgZGV0YWlscy5wdXNoKHtsYWJlbDonU01BNTAgPiBTTUEyMDAgKEFsdGluIENhcnBheiknLCBwYXNzOmM0LCB2YWw6IGM0ID8gJ0V2ZXQnIDogJ0hheWlyJywgdGlwOic1MCBndW5sdWsgb3J0YWxhbWEgMjAwIGd1bmx1Z3VuIHV6ZXJpbmRlLiBCb2dhIHBpeWFzYXNpbmluIHRla25payBkb2dydWxhbWFzaS4nfSk7CiAgICBpZihjNCkgc2NvcmUrKzsKICAgIHZhciBjNSA9IHIuc21hMjAwICYmIHIuc21hNTAgJiYgci5zbWEyMDAgPiAwOwogICAgZGV0YWlscy5wdXNoKHtsYWJlbDonU01BMjAwIFl1a3NlbGl5b3InLCBwYXNzOmM1LCB2YWw6IGM1ID8gJ1ZlcmkgdmFyJyA6ICdWZXJpIHlvaycsIHRpcDonU01BMjAwXCd1biBzb24gMSBheWRpciB5dWthcmkgYmFraXlvciBvbG1hc2kgZ2VyZWtpci4gWWFuIGdpZGVuIHZleWEgZHVzZW4gU01BMjAwIHRlaGxpa2UgaXNhcmV0aS4nfSk7CiAgICBpZihjNSkgc2NvcmUrKzsKICAgIHZhciBjNiA9IHIubG93NTJ3ICYmIHIuZml5YXQgJiYgKChyLmZpeWF0IC0gci5sb3c1MncpIC8gci5sb3c1MncgKiAxMDApID49IDMwOwogICAgdmFyIGxvdzUycGN0ID0gci5sb3c1MncgPyBNYXRoLnJvdW5kKChyLmZpeWF0IC0gci5sb3c1MncpIC8gci5sb3c1MncgKiAxMDApIDogMDsKICAgIGRldGFpbHMucHVzaCh7bGFiZWw6JzUySCBEaXAgKyUzMCcsIHBhc3M6YzYsIHZhbDogKHIubG93NTJ3ID8gJyslJytsb3c1MnBjdCA6ICc/JyksIHRpcDonSGlzc2UgeWlsbGlrIGRpYmluZGVuIGVuIGF6ICUzMCB5dWthcmlkYSBvbG1hbGkuIEdlcmNlayBndWMgZ29zdGVyZ2VzaS4nfSk7CiAgICBpZihjNikgc2NvcmUrKzsKICAgIHZhciBjNyA9IHIucGN0X2Zyb21fNTJ3ICE9PSB1bmRlZmluZWQgJiYgci5wY3RfZnJvbV81MncgPD0gMjU7CiAgICBkZXRhaWxzLnB1c2goe2xhYmVsOic1MkggWmlydmV5ZSAtJTI1JywgcGFzczpjNywgdmFsOiAoci5wY3RfZnJvbV81MncgIT09IHVuZGVmaW5lZCA/ICctJScrci5wY3RfZnJvbV81MncrJyB1emFrJyA6ICc/JyksIHRpcDonSGlzc2UgeWlsbGlrIHppcnZlc2luaW4gJTI1XCdpIGljaW5kZSBvbG1hbGkuIFppcnZleWUgeWFraW4gPSBndWNsdSBoaXNzZS4nfSk7CiAgICBpZihjNykgc2NvcmUrKzsKICAgIHZhciBjOCA9IHIuZ2Fpbl82bSAhPT0gdW5kZWZpbmVkICYmIHIuZ2Fpbl82bSA+PSAyMDsKICAgIGRldGFpbHMucHVzaCh7bGFiZWw6J1JTIEd1YyA+JTIwICg2QSknLCBwYXNzOmM4LCB2YWw6IChyLmdhaW5fNm0gIT09IHVuZGVmaW5lZCA/ICc2QTogJScrci5nYWluXzZtIDogJz8nKSwgdGlwOidTb24gNiBheWRhIFMmUDUwMFwnZGVuIGRhaGEgaXlpIHBlcmZvcm1hbnMuIFJTPjcwIGRlbWVrIGVuIGd1Y2x1ICUzMCBpY2luZGUgb2xtYWsuJ30pOwogICAgaWYoYzgpIHNjb3JlKys7CiAgICByZXR1cm4ge3Njb3JlOiBzY29yZSwgZGV0YWlsczogZGV0YWlsc307CiAgfQoKICBmdW5jdGlvbiBjYWxjVkNQKHIpewogICAgdmFyIGF0ciA9IHIuYXRyOyB2YXIgcHJpY2UgPSByLmZpeWF0OwogICAgaWYoIWF0ciB8fCAhcHJpY2UpIHJldHVybiB7aGFzVkNQOiBudWxsLCBub3RlOiAnQVRSIHZlcmlzaSB5b2snfTsKICAgIHZhciBhdHJQY3QgPSAoYXRyIC8gcHJpY2UgKiAxMDApOwogICAgdmFyIGlzTG93Vm9sID0gYXRyUGN0IDwgMy41OwogICAgdmFyIG5lYXJIaWdoID0gci5wY3RfZnJvbV81MncgPD0gMjA7CiAgICB2YXIgYWJvdmVNQXMgPSByLmFib3ZlNTAgJiYgci5hYm92ZTIwMDsKICAgIHZhciBoYXNWQ1AgPSBpc0xvd1ZvbCAmJiBuZWFySGlnaCAmJiBhYm92ZU1BczsKICAgIHJldHVybiB7aGFzVkNQOiBoYXNWQ1AsIGF0clBjdDogYXRyUGN0LnRvRml4ZWQoMSksIG5vdGU6IGhhc1ZDUCA/ICdWQ1AgZm9ybWFzeW9udSBvbGFzaScgOiAnVkNQIGtvc3VsbGFyaSB0YW0gc2FnbGFubWl5b3InfTsKICB9CgogIHZhciBoID0gJzxkaXYgc3R5bGU9InBhZGRpbmc6MTZweDt3aWR0aDoxMDAlO2JveC1zaXppbmc6Ym9yZGVyLWJveCI+JzsKCiAgLy8gw5xzdCBhw6fEsWtsYW1hCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxOHB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxMnB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMCI+8J+OryBNaW5lcnZpbmkgTWV0b2RvbG9qaXNpPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMTIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4zKTtib3JkZXItcmFkaXVzOjZweDtwYWRkaW5nOjNweCAxMHB4O2ZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLXllbGxvdyk7Zm9udC13ZWlnaHQ6NjAwIj5UUkFERSBMSUtFIEEgU1RPQ0sgTUFSS0VUIFdJWkFSRDwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjojOTRhM2I4O2xpbmUtaGVpZ2h0OjEuODttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCArPSAnPHN0cm9uZyBzdHlsZT0iY29sb3I6dmFyKC0tdGV4dCkiPk1hcmsgTWluZXJ2aW5pPC9zdHJvbmc+LCBBQkQgSGlzc2UgU2VuZWRpIFNhbXBpeW9ubHVndW51IGJpcmRlbiBmYXpsYSBrZXoga2F6YW5taXMgdmUgeWlsbGlrIG9ydGFsYW1hIDxzdHJvbmcgc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKSI+JTIyMCsgZ2V0aXJpPC9zdHJvbmc+IHVyZXRtaXMgYmlyIHRyYWRlclwnZGlyLiAnOwogIGggKz0gJ01ldG9kb2xvamlzaSBpa2kgdW5zdXJhIGRheWFuaXI6IDxzdHJvbmcgc3R5bGU9ImNvbG9yOiM2MGE1ZmEiPlRyZW5kIFRlbXBsYXRlPC9zdHJvbmc+IChkb2dydSBoaXNzZXlpIGJ1bCkgKyA8c3Ryb25nIHN0eWxlPSJjb2xvcjojYTc4YmZhIj5WQ1AgKyBTRVBBIEdpcmlzaTwvc3Ryb25nPiAoZG9ncnUgYW5kYSBnaXIpLiAnOwogIGggKz0gJ0FzbGEgZHVzZW4gdmV5YSB6YXlpZiBoaXNzZSBhbG1heiDigJQgc2FkZWNlIGd1Y2x1LCBiYXphIGdpcm1pcyB2ZSBraXJpbGltIG5va3Rhc2luYSB5YWtpbiBsaWRlcmxlcmUgZ2lyZXIuJzsKICBoICs9ICc8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMjIwcHgsMWZyKSk7Z2FwOjEwcHgiPic7CiAgW3tpY29uOifwn5OQJyx0aXRsZTonVHJlbmQgVGVtcGxhdGUnLGRlc2M6Jzgga3JpdGVyaW4gdGFtYW1pbmkga2Fyc2lsYXlhbiBoaXNzZWxlciBzYXRpbiBhbG1heWEgdXlndW4gYm9sZ2VkZWRpci4gMSBrcml0ZXIgYmlsZSBla3Npa3NlIGhpc3NlIGxpc3RleWUgZ2lybWV6Lid9LAogICB7aWNvbjon8J+MgCcsdGl0bGU6J1ZDUCAoVm9sYXRpbGl0ZSBEYXJhbG1hc8SxKScsZGVzYzonRml5YXQga29uc29saWRhc3lvbmEgZ2lyZXIsIGhlciBkYWxnYSBoZW0gZml5YXQgaGVtIGhhY2ltIG9sYXJhayBkYXJhbGlyLiBLdXJ1bXNhbCBzYXRpc8SxbiBiaXR0aWdpbmluIGlzYXJldGlkaXIuJ30sCiAgIHtpY29uOifwn46vJyx0aXRsZTonU0VQQSBHaXJpc2knLGRlc2M6J1Bpdm90IGtpcmlsaW1pbmRhIGhhY2ltbGUgYmlybGlrdGUgY29rIHNwZXNpZmlrIGdpcmlzLiBBc2xhIGVya2VuLCBhc2xhIGdlYy4nfSwKICAge2ljb246J/Cfm6HvuI8nLHRpdGxlOidSaXNrIFnDtm5ldGltaScsZGVzYzonSGVyIGlzbGVtZGUgbWFrcyAlMS0yIHNlcm1heWUgcmlza2kuIFN0b3AtbG9zcyBwaXZvdCBhbHRpbmEga29udXIuIFBvemlzeW9uIGJ1eXVrbHVndSBidW5hIGdvcmUgaGVzYXBsYW5pci4nfQogIF0uZm9yRWFjaChmdW5jdGlvbihjKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMnB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE0cHg7bWFyZ2luLWJvdHRvbTo0cHgiPicrYy5pY29uKycgPHN0cm9uZyBzdHlsZT0iY29sb3I6dmFyKC0tdGV4dCkiPicrYy50aXRsZSsnPC9zdHJvbmc+PC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOiM5NGEzYjg7bGluZS1oZWlnaHQ6MS41Ij4nK2MuZGVzYysnPC9kaXY+PC9kaXY+JzsKICB9KTsKICBoICs9ICc8L2Rpdj48L2Rpdj4nOwoKICAvLyBJcyBha2lzaQogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNjcsMTM5LDI1MCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNjcsMTM5LDI1MCwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjojYTc4YmZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMnB4Ij7wn5OLIERvZ3J1IFNpcmEg4oCUIElzIEFraXNpPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7ZmxleC13cmFwOndyYXA7Z2FwOjhweDthbGlnbi1pdGVtczpjZW50ZXIiPic7CiAgWycx77iP4oOjIENBTlNMSU0gU2NyZWVuZXJcJ2RhIHRlbWVsIGtyaXRlcmxlcicsJ+KGkicsJzLvuI/ig6MgVHJlbmQgVGVtcGxhdGUgKDgvOCB2ZXlhIDcvOCknLCfihpInLCcz77iP4oOjIFZDUCBGb3JtYXN5b251IChUcmFkaW5nVmlldyknLCfihpInLCc077iP4oOjIFBpdm90IGtpcmlsaW1pbmkgYmVrbGUgKyBoYWNpbSBvbmF5xLEnLCfihpInLCc177iP4oOjIFNFUEEgaWxlIGdpciwgc3RvcCBwaXZvdCBhbHTEsW5hJ10uZm9yRWFjaChmdW5jdGlvbihzKXsKICAgIGlmKHM9PT0n4oaSJyl7aCs9JzxkaXYgc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKTtmb250LXNpemU6MTZweCI+4oaSPC9kaXY+Jzt9CiAgICBlbHNle2grPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6NnB4O3BhZGRpbmc6NnB4IDEwcHg7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tdGV4dCkiPicrcysnPC9kaXY+Jzt9CiAgfSk7CiAgaCArPSAnPC9kaXY+PC9kaXY+JzsKCiAgLy8gw5Z6ZXQgaXN0YXRpc3Rpa2xlcgogIHZhciByb3dzID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KTsKICB2YXIgc2NvcmVkID0gcm93cy5tYXAoZnVuY3Rpb24ocil7IHZhciB0dD1jYWxjVHJlbmRUZW1wbGF0ZShyKTsgdmFyIHZjcD1jYWxjVkNQKHIpOyByZXR1cm4ge3I6cix0dDp0dCx2Y3A6dmNwfTsgfSkuc29ydChmdW5jdGlvbihhLGIpe3JldHVybiBiLnR0LnNjb3JlLWEudHQuc2NvcmU7fSk7CiAgdmFyIHBhc3M4PXNjb3JlZC5maWx0ZXIoZnVuY3Rpb24oeCl7cmV0dXJuIHgudHQuc2NvcmU+PTg7fSkubGVuZ3RoOwogIHZhciBwYXNzNz1zY29yZWQuZmlsdGVyKGZ1bmN0aW9uKHgpe3JldHVybiB4LnR0LnNjb3JlPj03O30pLmxlbmd0aDsKICB2YXIgcGFzczY9c2NvcmVkLmZpbHRlcihmdW5jdGlvbih4KXtyZXR1cm4geC50dC5zY29yZT49Njt9KS5sZW5ndGg7CiAgdmFyIHZjcEM9c2NvcmVkLmZpbHRlcihmdW5jdGlvbih4KXtyZXR1cm4geC52Y3AuaGFzVkNQO30pLmxlbmd0aDsKCiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgxNDBweCwxZnIpKTtnYXA6MTBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgW3t2OnBhc3M4LGw6JzgvOCBUYW0gUHVhbicsYzondmFyKC0tZ3JlZW4pJyxiZzoncmdiYSgxNiwxODUsMTI5LC4wOCknLGJkOidyZ2JhKDE2LDE4NSwxMjksLjI1KSd9LAogICB7djpwYXNzNyxsOic3LzggR8O8w6dsw7wnLGM6J3ZhcigtLWdyZWVuMiknLGJnOidyZ2JhKDUyLDIxMSwxNTMsLjA2KScsYmQ6J3JnYmEoNTIsMjExLDE1MywuMiknfSwKICAge3Y6cGFzczYsbDonNi84IMSwemxlJyxjOid2YXIoLS15ZWxsb3cpJyxiZzoncmdiYSgyNDUsMTU4LDExLC4wOCknLGJkOidyZ2JhKDI0NSwxNTgsMTEsLjI1KSd9LAogICB7djp2Y3BDLGw6J1ZDUCBBZGF5xLEnLGM6JyNhNzhiZmEnLGJnOidyZ2JhKDE2NywxMzksMjUwLC4wOCknLGJkOidyZ2JhKDE2NywxMzksMjUwLC4yNSknfQogIF0uZm9yRWFjaChmdW5jdGlvbih4KXsKICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicreC5iZysnO2JvcmRlcjoxcHggc29saWQgJyt4LmJkKyc7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjZweDtmb250LXdlaWdodDo3MDA7Y29sb3I6Jyt4LmMrJyI+Jyt4LnYrJzwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK3gubCsnPC9kaXY+PC9kaXY+JzsKICB9KTsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBUcmVuZCBUZW1wbGF0ZSB0YWJsb3N1CiAgaWYoc2NvcmVkLmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtvdmVyZmxvdzpoaWRkZW47bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0icGFkZGluZzoxMnB4IDE2cHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpO2ZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlIj7wn5OQIFRyZW5kIFRlbXBsYXRlIEFuYWxpemk8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0ib3ZlcmZsb3cteDphdXRvIj48dGFibGUgc3R5bGU9IndpZHRoOjEwMCU7Ym9yZGVyLWNvbGxhcHNlOmNvbGxhcHNlO2ZvbnQtc2l6ZToxMXB4O21pbi13aWR0aDo2MDBweCI+PHRoZWFkPjx0ciBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpIj4nOwogICAgWydIaXNzZScsJ0ZpeWF0JywnVFQgU2tvcnUnLCdTTUE1MCcsJ1NNQTIwMCcsJ0FsdGluIENhcnBheicsJzUySCBEaXAnLCc1MkggWmlydmUnLCdSUyBHdWMnLCdWQ1A/J10uZm9yRWFjaChmdW5jdGlvbihjLGkpewogICAgICBoKz0nPHRoIHN0eWxlPSJ0ZXh0LWFsaWduOicrKGk9PT0wPydsZWZ0JzoncmlnaHQnKSsnO3BhZGRpbmc6OHB4ICcrKGk9PT0wPycxNCc6JzgnKSsncHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtd2VpZ2h0OjYwMDt3aGl0ZS1zcGFjZTpub3dyYXAiPicrYysnPC90aD4nOwogICAgfSk7CiAgICBoICs9ICc8L3RyPjwvdGhlYWQ+PHRib2R5Pic7CiAgICBzY29yZWQuZm9yRWFjaChmdW5jdGlvbihpdGVtLGlkeCl7CiAgICAgIHZhciByPWl0ZW0ucjsgdmFyIHR0PWl0ZW0udHQ7IHZhciB2Y3A9aXRlbS52Y3A7IHZhciBzY29yZT10dC5zY29yZTsKICAgICAgdmFyIHNjb3JlQ29sPXNjb3JlPj04Pyd2YXIoLS1ncmVlbiknOnNjb3JlPj03Pyd2YXIoLS1ncmVlbjIpJzpzY29yZT49Nj8ndmFyKC0teWVsbG93KSc6J3ZhcigtLW11dGVkKSc7CiAgICAgIHZhciBzY29yZUJnPXNjb3JlPj04PydyZ2JhKDE2LDE4NSwxMjksLjE1KSc6c2NvcmU+PTc/J3JnYmEoNTIsMjExLDE1MywuMSknOnNjb3JlPj02PydyZ2JhKDI0NSwxNTgsMTEsLjEpJzondmFyKC0tYmczKSc7CiAgICAgIHZhciBiZz1pZHglMj09PTA/J3ZhcigtLWJnKSc6J3JnYmEoMjU1LDI1NSwyNTUsLjAxNSknOwogICAgICB2YXIgaW5Qb3J0PVBPUlQuaW5jbHVkZXMoci50aWNrZXIpOwogICAgICBoKz0nPHRyIHN0eWxlPSJiYWNrZ3JvdW5kOicrYmcrJztib3JkZXItYm90dG9tOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wMykiPic7CiAgICAgIGgrPSc8dGQgc3R5bGU9InBhZGRpbmc6MTBweCAxNHB4O2ZvbnQtd2VpZ2h0OjcwMCI+PHNwYW4gc3R5bGU9ImNvbG9yOicrKHNjb3JlPj03Pyd2YXIoLS1ncmVlbiknOnNjb3JlPj02Pyd2YXIoLS15ZWxsb3cpJzondmFyKC0tdGV4dCknKSsnIj4nK3IudGlja2VyKyc8L3NwYW4+JzsKICAgICAgaWYoaW5Qb3J0KSBoKz0nPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tbGVmdDo0cHgiPlA8L3NwYW4+JzsKICAgICAgaCs9JzwvdGQ+JzsKICAgICAgdmFyIGRjPXIuZGVnaXNpbT49MD8ndmFyKC0tZ3JlZW4yKSc6J3ZhcigtLXJlZDIpJzsKICAgICAgaCs9Jzx0ZCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjhweCI+PGRpdiBzdHlsZT0iZm9udC13ZWlnaHQ6NjAwIj4kJytyLmZpeWF0Kyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrZGMrJyI+Jysoci5kZWdpc2ltPj0wPycrJzonJykrci5kZWdpc2ltKyclPC9kaXY+PC90ZD4nOwogICAgICBoKz0nPHRkIHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O3BhZGRpbmc6OHB4Ij48c3BhbiBzdHlsZT0iYmFja2dyb3VuZDonK3Njb3JlQmcrJztjb2xvcjonK3Njb3JlQ29sKyc7Ym9yZGVyLXJhZGl1czo0cHg7cGFkZGluZzozcHggOHB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LXNpemU6MTJweCI+JytzY29yZSsnLzg8L3NwYW4+PC90ZD4nOwogICAgICBoKz0nPHRkIHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O3BhZGRpbmc6OHB4O2NvbG9yOicrKHIuYWJvdmU1MD8ndmFyKC0tZ3JlZW4pJzondmFyKC0tcmVkMiknKSsnIj4nKyggci5hYm92ZTUwPyfinJMgVXN0Lic6J+KclyBBbHQuJykrJzwvdGQ+JzsKICAgICAgaCs9Jzx0ZCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjhweDtjb2xvcjonKyhyLmFib3ZlMjAwPyd2YXIoLS1ncmVlbiknOid2YXIoLS1yZWQyKScpKyciPicrKCByLmFib3ZlMjAwPyfinJMgVXN0Lic6J+KclyBBbHQuJykrJzwvdGQ+JzsKICAgICAgdmFyIGdjPXIuc21hNTAmJnIuc21hMjAwJiZyLnNtYTUwPnIuc21hMjAwOwogICAgICBoKz0nPHRkIHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O3BhZGRpbmc6OHB4O2NvbG9yOicrKGdjPyd2YXIoLS1ncmVlbiknOid2YXIoLS1yZWQyKScpKyciPicrKCBnYz8n4pyTJzon4pyXJykrJzwvdGQ+JzsKICAgICAgdmFyIGxwPXIubG93NTJ3P01hdGgucm91bmQoKHIuZml5YXQtci5sb3c1MncpL3IubG93NTJ3KjEwMCk6bnVsbDsKICAgICAgaCs9Jzx0ZCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjhweDtjb2xvcjonKyhscCE9PW51bGwmJmxwPj0zMD8ndmFyKC0tZ3JlZW4pJzpscCE9PW51bGwmJmxwPj0xNT8ndmFyKC0teWVsbG93KSc6J3ZhcigtLXJlZDIpJykrJyI+JysoIGxwIT09bnVsbD8nKyUnK2xwOic/JykrJzwvdGQ+JzsKICAgICAgdmFyIGM3PXIucGN0X2Zyb21fNTJ3IT09dW5kZWZpbmVkJiZyLnBjdF9mcm9tXzUydzw9MjU7CiAgICAgIGgrPSc8dGQgc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7cGFkZGluZzo4cHg7Y29sb3I6JysoYzc/J3ZhcigtLWdyZWVuKSc6ci5wY3RfZnJvbV81Mnc8PTM1Pyd2YXIoLS15ZWxsb3cpJzondmFyKC0tcmVkMiknKSsnIj4nKyggci5wY3RfZnJvbV81MnchPT11bmRlZmluZWQ/Jy0lJytyLnBjdF9mcm9tXzUydzonPycpKyc8L3RkPic7CiAgICAgIHZhciBjOD1yLmdhaW5fNm0hPT11bmRlZmluZWQmJnIuZ2Fpbl82bT49MjA7CiAgICAgIGgrPSc8dGQgc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7cGFkZGluZzo4cHg7Y29sb3I6JysoYzg/J3ZhcigtLWdyZWVuKSc6ci5nYWluXzZtPj01Pyd2YXIoLS15ZWxsb3cpJzondmFyKC0tcmVkMiknKSsnIj4nKyggci5nYWluXzZtIT09dW5kZWZpbmVkPyclJytyLmdhaW5fNm06Jz8nKSsnPC90ZD4nOwogICAgICBoKz0nPHRkIHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O3BhZGRpbmc6OHB4Ij4nKyh2Y3AuaGFzVkNQPT09bnVsbD8nPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+4oCUPC9zcGFuPic6dmNwLmhhc1ZDUD8nPHNwYW4gc3R5bGU9ImNvbG9yOiNhNzhiZmE7Zm9udC13ZWlnaHQ6NjAwIj7inJMgT2xhc2k8L3NwYW4+JzonPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+4oCUPC9zcGFuPicpKyc8L3RkPic7CiAgICAgIGgrPSc8L3RyPic7CiAgICB9KTsKICAgIGggKz0gJzwvdGJvZHk+PC90YWJsZT48L2Rpdj48L2Rpdj4nOwogIH0KCiAgLy8gUmlzayB5w7ZuZXRpbWkKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLXJlZDIpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMnB4Ij7wn5uh77iPIE1pbmVydmluaSBSaXNrIFnDtm5ldGltaSBLdXJhbGxhcsSxPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDIyMHB4LDFmcikpO2dhcDoxMHB4Ij4nOwogIFt7dDonJTEtMiBTZXJtYXllIFJpc2tpJyxkOidIZXIgaXNsZW1kZSB0b3BsYW0gc2VybWF5ZW5pbiBtYWtzaW11bSAlMS0yXCdzaSByaXNrZSBlZGlsaXIuJ30sCiAgIHt0OidTdG9wLUxvc3MgRGlzaXBsaW5pJyxkOidTdG9wIHNldml5ZXNpIGJheiBmb3JtYXN5b251bnVuIGRpYmluaW4gYWx0aW5hIGtvbnVyLiBIZXIgZGVmYXNpbmRhIHV5dWx1ci4nfSwKICAge3Q6J1BvemlzeW9uIEJ1eXVrbHVndScsZDonPSAoU2VybWF5ZSB4ICVSaXNrKSAvIChHaXJpcyAtIFN0b3ApLiBNYXRlbWF0aWtsZSBoZXNhcGxhbmlyLid9LAogICB7dDonRWFybmluZ3MgS3VyYWxpJyxkOidSYXBvciB0YXJpaGluZGVuIDEtMiBoYWZ0YSBvbmNlIHllbmkgcG96aXN5b24gYXNpbG1hei4nfSwKICAge3Q6J1BpcmFtaXRsZW1lJyxkOidJbGsgcG96aXN5b24ga3VjdWsuIEZpeWF0IGRvZ3J1IHlvbmRlIGdpZGVyc2UgZWsgYWxpbSB5YXBpbGlyLid9LAogICB7dDonUGl5YXNhIFlvbnUnLGQ6J0R1emVsdG1lIGRvbmVtaW5kZSB5ZW5pIHBvemlzeW9uIGFzaWxtYXouIFNhZGVjZSBGb2xsb3ctVGhyb3VnaCBEYXkgc29ucmFzaS4nfQogIF0uZm9yRWFjaChmdW5jdGlvbih4KXsKICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTJweCI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tdGV4dCk7bWFyZ2luLWJvdHRvbTo0cHgiPicreC50Kyc8L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOiM5NGEzYjg7bGluZS1oZWlnaHQ6MS41Ij4nK3guZCsnPC9kaXY+PC9kaXY+JzsKICB9KTsKICBoICs9ICc8L2Rpdj48L2Rpdj48L2Rpdj4nOwogIGdyaWQuaW5uZXJIVE1MID0gaDsKfQoKZnVuY3Rpb24gcmVuZGVyVmFsdWF0aW9uKCl7CiAgdmFyIGNvbnRhaW5lciA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgaWYoIWNvbnRhaW5lcikgcmV0dXJuOwogIGNvbnRhaW5lci5zdHlsZS5kaXNwbGF5ID0gJ2Jsb2NrJzsKICBjb250YWluZXIuc3R5bGUud2lkdGggPSAnMTAwJSc7CgogIHZhciBtZXRyaWNzID0gWwogICAge2tleTonZXBzX2dyb3d0aCcsICAgbGFiZWw6J0VQUyUnLCAgICAgICBkZXNjOidTb24gY2V5cmVrIEVQUyBidXl1bWUgb3JhbmkuIENBTlNMSU0gQyBrcml0ZXJpIC0gZW4ga3JpdGlrIG1ldHJpay4nLCAgICAgICAgICBpZGVhbDonMjArIGl5aSwgMzArIGd1Y2x1JywgbG86MjAsIGhpOjEwMCwgZm10OiclJywgaGI6dHJ1ZX0sCiAgICB7a2V5OidyZXZfZ3Jvd3RoJywgICBsYWJlbDonR2VsaXIlJywgICAgICBkZXNjOidTb24gY2V5cmVrIGdlbGlyIGJ1eXVtZS4gQ0FOU0xJTSBBIGtyaXRlcmkuIFBhemFyIHBheWkgdmUgbW9tZW50dW0gZ3VjdW51IGdvc3RlcmlyLicsIGlkZWFsOicxNSsgaXlpLCAyNSsgZ3VjbHUnLCBsbzoxNSwgaGk6MTAwLCBmbXQ6JyUnLCBoYjp0cnVlfSwKICAgIHtrZXk6J3BlX2Z3ZCcsICAgICAgIGxhYmVsOidJbGVyaSBGL0snLCAgIGRlc2M6J09udW3DvHpkZWtpIDEyIGF5IHRhaG1pbmkga2F6YW5jaW5hIGdvcmUgRml5YXQvS2F6YW5jIG9yYW5pLicsICAgICAgICAgICAgICAgICAgaWRlYWw6JzI1IGFsdMSxIGl5aSwgMzUgYWx0xLEga2FidWwnLCBsbzowLCBoaToyNSwgZm10Oid4JywgaGI6ZmFsc2V9LAogICAge2tleToncGVnJywgICAgICAgICAgbGFiZWw6J1BFRycsICAgICAgICAgZGVzYzonRi9LIG9yYW5pbmkgYnV5dW1lIGhpemkgaWxlIGthcnNpbGFzdGlyaXIuIEVuIGRlbmdlbGkgZGVnZXJsZW1lIG1ldHJpZ2kuJywgICAgIGlkZWFsOicxIGFsdMSxIHVjdXosIDEtMiBtYWt1bCwgMiB1c3R1IHBhaGFsaScsIGxvOjAsIGhpOjIsIGZtdDoneCcsIGhiOmZhbHNlfSwKICAgIHtrZXk6J2dyb3NzX21hcmdpbicsIGxhYmVsOidCcnV0JScsICAgICAgIGRlc2M6J0JydXQga2FyIG1hcmppbmkuIFNpcmtldGluIGZpeWF0bGFtYSBndWN1bnUgZ29zdGVyaXIuJywgICAgICAgICAgICAgICAgICAgICAgICBpZGVhbDonWWF6aWxpbSA3MCssIEdlbmVsIDQwKycsIGxvOjQwLCBoaToxMDAsIGZtdDonJScsIGhiOnRydWV9LAogICAge2tleTonbmV0X21hcmdpbicsICAgbGFiZWw6J05ldCUnLCAgICAgICAgZGVzYzonTmV0IGthciBtYXJqaW5pLiBUdW0gZ2lkZXJsZXIgZHVzdWxkdWt0ZW4gc29ucmEga2FsYW4ga2FyIHl1emRlc2kuJywgICAgICAgICAgIGlkZWFsOicxMCsgaXlpLCAyMCsgbXVrZW1tZWwnLCBsbzoxMCwgaGk6MTAwLCBmbXQ6JyUnLCBoYjp0cnVlfSwKICAgIHtrZXk6J3JvZScsICAgICAgICAgIGxhYmVsOidPS0cnLCAgICAgICAgIGRlc2M6J096c2VybWF5ZSBLYXJsaWxpZ2kgKFJPRSkuIFlvbmV0aW1pbiBzZXJtYXlleWkgbmUga2FkYXIgdmVyaW1saSBrdWxsYW5kaWdpLicsICBpZGVhbDonMTUrIGl5aSwgMjUrIG11a2VtbWVsJywgbG86MTUsIGhpOjEwMCwgZm10OiclJywgaGI6dHJ1ZX0sCiAgICB7a2V5OidwZV90dG0nLCAgICAgICBsYWJlbDonRi9LJywgICAgICAgICBkZXNjOidTb24gMTIgYXkgZ2VyY2VrIGthemFuY2luYSBnb3JlIEZpeWF0L0themFuYy4gVGFyaWhpIGthcnNpbGFzdGlybWEgaWNpbi4nLCAgICBpZGVhbDonVGVrbm9sb2ppIDM1IGFsdMSxLCBHZW5lbCAyNSBhbHTEsScsIGxvOjAsIGhpOjM1LCBmbXQ6J3gnLCBoYjpmYWxzZX0sCiAgICB7a2V5OidwcycsICAgICAgICAgICBsYWJlbDonRi9TJywgICAgICAgICBkZXNjOidGaXlhdC9TYXRpc2xhci4gSGVudXoga2Fyc2l6IHZleWEgaGl6bGkgYnV5dXllbiBzaXJrZXRsZXIgaWNpbiBrdWxsYW5pbGlyLicsICBpZGVhbDonVGVrbm9sb2ppIDggYWx0xLEsIEdlbmVsIDMgYWx0xLEnLCBsbzowLCBoaTo4LCBmbXQ6J3gnLCBoYjpmYWxzZX0sCiAgICB7a2V5OidwYicsICAgICAgICAgICBsYWJlbDonRi9ERCcsICAgICAgICBkZXNjOidGaXlhdC9EZWZ0ZXIgRGVnZXJpLiBTaXJrZXRpbiBuZXQgdmFybGlrbGFyxLFuYSBnb3JlIGZpeWF0aS4nLCAgICAgICAgICAgICAgICAgIGlkZWFsOiczIGFsdMSxIHVjdXosIDMtNyBtYWt1bCwgNyB1c3R1IHBhaGFsaScsIGxvOjAsIGhpOjUsIGZtdDoneCcsIGhiOmZhbHNlfSwKICAgIHtrZXk6J2FuYWx5c3RfdGFyZ2V0JywgbGFiZWw6J0hlZGVmJywgICAgIGRlc2M6J0FuYWxpc3Qga29uc2Vuc3VzIGhlZGVmIGZpeWF0aS4gWXVrYXLEsSB5b25sdSBwb3RhbnNpeWVsIGdvc3RlcmlyLicsICAgICAgICAgICAgaWRlYWw6J01ldmN1dCBmaXlhdHRhbiB5dWtzZWsgb2xzdW4nLCBsbzowLCBoaTowLCBmbXQ6JyQnLCBoYjp0cnVlfSwKICBdOwoKICBmdW5jdGlvbiBjb2xPZih2YWwsbG8saGksaGIpewogICAgaWYodmFsPT09bnVsbHx8dmFsPT09dW5kZWZpbmVkKSByZXR1cm4gJ3ZhcigtLW11dGVkKSc7CiAgICB2YXIgbj1wYXJzZUZsb2F0KHZhbCk7IGlmKGlzTmFOKG4pKSByZXR1cm4gJ3ZhcigtLW11dGVkKSc7CiAgICBpZihoYil7IHJldHVybiBuPj1oaSowLjc/J3ZhcigtLWdyZWVuKSc6bj49bG8/J3ZhcigtLXllbGxvdyknOid2YXIoLS1yZWQyKSc7IH0KICAgIGVsc2UgIHsgcmV0dXJuIG48PWxvKjEuMj8ndmFyKC0tZ3JlZW4pJzpuPD1oaT8ndmFyKC0teWVsbG93KSc6J3ZhcigtLXJlZDIpJzsgfQogIH0KICBmdW5jdGlvbiBmbXRWKHZhbCxmbXQscHJpY2UpewogICAgaWYodmFsPT09bnVsbHx8dmFsPT09dW5kZWZpbmVkKSByZXR1cm4gJzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPi08L3NwYW4+JzsKICAgIHZhciBuPXBhcnNlRmxvYXQodmFsKTsgaWYoaXNOYU4obikpIHJldHVybiAnPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+LTwvc3Bhbj4nOwogICAgaWYoZm10PT09J3gnKSByZXR1cm4gbi50b0ZpeGVkKDEpKyd4JzsKICAgIGlmKGZtdD09PSclJykgcmV0dXJuIG4udG9GaXhlZCgxKSsnJSc7CiAgICBpZihmbXQ9PT0nJCcpewogICAgICB2YXIgdXA9cHJpY2U+MD8oKG4tcHJpY2UpL3ByaWNlKjEwMCkudG9GaXhlZCgxKTpudWxsOwogICAgICB2YXIgYz0odXAhPT1udWxsJiZwYXJzZUZsb2F0KHVwKT4wKT8ndmFyKC0tZ3JlZW4pJzondmFyKC0tcmVkMiknOwogICAgICByZXR1cm4gJyQnK24udG9GaXhlZCgwKSsodXAhPT1udWxsPycgPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6JytjKyciPicrKHBhcnNlRmxvYXQodXApPjA/JysnOicnKSt1cCsnJTwvc3Bhbj4nOicnKTsKICAgIH0KICAgIHJldHVybiBTdHJpbmcobik7CiAgfQoKICB2YXIgZGF0YSA9IChURl9EQVRBICYmIFRGX0RBVEFbJzFkJ10pID8gVEZfREFUQVsnMWQnXSA6IFtdOwogIHZhciByb3dzID0gZGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7IHJldHVybiAhci5oYXRhOyB9KTsKCiAgdmFyIGggPSAnJzsKICBoICs9ICc8ZGl2IHN0eWxlPSJwYWRkaW5nOjE2cHg7d2lkdGg6MTAwJTtib3gtc2l6aW5nOmJvcmRlci1ib3giPic7CiAgaCArPSAnPGgyIHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWJvdHRvbTo4cHgiPiYjeDFGNDhFOyBEZSYjMjg3O2VybGVtZSBBbmFsaXppPC9oMj4nOwoKICAvLyDDlnpldCBrdXR1c3UKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoOTYsMTY1LDI1MCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSg5NiwxNjUsMjUwLC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4IDE2cHg7bWFyZ2luLWJvdHRvbToxNnB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjojNjBhNWZhO21hcmdpbi1ib3R0b206MTBweCI+QnUgc2F5ZmF5aSBuYXNpbCBva3VtYWxpeWltPzwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgyNjBweCwxZnIpKTtnYXA6OHB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOiM5NGEzYjg7bGluZS1oZWlnaHQ6MS43Ij4nOwogIGggKz0gJzxkaXY+PHN0cm9uZyBzdHlsZT0iY29sb3I6dmFyKC0tdGV4dCkiPjEuIFJlbmtsZXJlIGJhazo8L3N0cm9uZz4gWWVzaWw9aXlpLCBTYXJpPWRpa2thdCwgS2lybWl6aT16YXlpZi4gU2F0aXIgY29ndW5sdWtsYSB5ZXNpbCA9IGd1Y2x1IGhpc3NlLjwvZGl2Pic7CiAgaCArPSAnPGRpdj48c3Ryb25nIHN0eWxlPSJjb2xvcjp2YXIoLS10ZXh0KSI+Mi4gRVBTIHZlIEdlbGlyIG9uY2VsaWtsaTo8L3N0cm9uZz4gQ0FOU0xJTSBtZXRvZG9sb2ppc2luZGUgZW4ga3JpdGlrIGlraSBtZXRyaWsuIEJ1IGlraXNpIGtpcm1peml5c2EgZGlnZXIgbWV0cmlrbGVyIGlraW5jaSBwbGFuYSBkdXN1eW9yLjwvZGl2Pic7CiAgaCArPSAnPGRpdj48c3Ryb25nIHN0eWxlPSJjb2xvcjp2YXIoLS10ZXh0KSI+My4gUEVHIGVuIGRlbmdlbGk6PC9zdHJvbmc+IDEgYWx0aSB1Y3V6LCAxLTIgbWFrdWwsIDIgdXN0dSBwYWhhbGkuIEhlbSBidXl1bWV5aSBoZW0gZml5YXRpIGJpcmxpa3RlIGRlZ2VybGVuZGlyaXIuPC9kaXY+JzsKICBoICs9ICc8ZGl2PjxzdHJvbmcgc3R5bGU9ImNvbG9yOnZhcigtLXRleHQpIj40LiBBbmFsaXN0IEhlZGVmaTo8L3N0cm9uZz4gTWV2Y3V0IGZpeWF0dGFuIHl1a3Nla3NlIHllc2lsLiBLdXJ1bWxhcsSxbiBiZWtsZW50aXNpbmkgZ29zdGVyaXIsIHRlayBiYXNpbmEgYWxpbSBzaW55YWxpIGRlZ2lsZGlyLjwvZGl2Pic7CiAgaCArPSAnPGRpdj48c3Ryb25nIHN0eWxlPSJjb2xvcjp2YXIoLS10ZXh0KSI+NS4gU3V0dW4gYmFzbGlnaW5hIGdlbDo8L3N0cm9uZz4gSGVyIG1ldHJpayBzdXR1bnVudW4gYmFzbGlnaW5kYWtpIG1hdmkgaWtvbiB1emVyaW5lIGZhcmUgaWxlIGdlbGluY2UgYWNpa2xhbWEgY2lrYXIuPC9kaXY+JzsKICBoICs9ICc8L2Rpdj48L2Rpdj4nOwoKICAvLyBUYWJsbwogIGggKz0gJzxkaXYgc3R5bGU9IndpZHRoOjEwMCU7b3ZlcmZsb3cteDphdXRvOy13ZWJraXQtb3ZlcmZsb3ctc2Nyb2xsaW5nOnRvdWNoIj4nOwogIGggKz0gJzx0YWJsZSBzdHlsZT0id2lkdGg6MTAwJTtib3JkZXItY29sbGFwc2U6Y29sbGFwc2U7Zm9udC1zaXplOjExcHg7bWluLXdpZHRoOjcwMHB4Ij4nOwogIGggKz0gJzx0aGVhZD48dHIgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKSI+JzsKICBoICs9ICc8dGggc3R5bGU9InRleHQtYWxpZ246bGVmdDtwYWRkaW5nOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtd2VpZ2h0OjYwMCI+SGlzc2U8L3RoPic7CiAgaCArPSAnPHRoIHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O3BhZGRpbmc6MTBweCA4cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtd2VpZ2h0OjYwMCI+Rml5YXQ8L3RoPic7CgogIG1ldHJpY3MuZm9yRWFjaChmdW5jdGlvbihtbSl7CiAgICB2YXIgdGlwRGF0YSA9IG1tLmxhYmVsICsgJ3x8JyArIG1tLmRlc2MgKyAnfHwnICsgbW0uaWRlYWw7CiAgICBoICs9ICc8dGggc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7cGFkZGluZzo4cHggNHB4O2NvbG9yOnZhcigtLW11dGVkKTtmb250LXdlaWdodDo2MDA7d2hpdGUtc3BhY2U6bm93cmFwO2ZvbnQtc2l6ZToxMHB4Ij4nOwogICAgaCArPSBtbS5sYWJlbDsKICAgIGggKz0gJzxzcGFuIGNsYXNzPSJ2YWwtdGlwIiBkYXRhLXRpcD0iJyArIHRpcERhdGEgKyAnIiBzdHlsZT0iY3Vyc29yOmhlbHA7d2lkdGg6MTRweDtoZWlnaHQ6MTRweDtib3JkZXItcmFkaXVzOjUwJTtiYWNrZ3JvdW5kOnJnYmEoOTYsMTY1LDI1MCwuMik7Y29sb3I6IzYwYTVmYTtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjcwMDtkaXNwbGF5OmlubGluZS1mbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO21hcmdpbi1sZWZ0OjNweDt2ZXJ0aWNhbC1hbGlnbjptaWRkbGUiPj88L3NwYW4+JzsKICAgIGggKz0gJzwvdGg+JzsKICB9KTsKICBoICs9ICc8L3RyPjwvdGhlYWQ+PHRib2R5Pic7CgogIHJvd3MuZm9yRWFjaChmdW5jdGlvbihyLGkpewogICAgdmFyIGJnPWklMj09PTA/J3ZhcigtLWJnKSc6J3JnYmEoMjU1LDI1NSwyNTUsLjAyKSc7CiAgICB2YXIgaW5QPXIucG9ydGZvbGlvOwogICAgaCArPSAnPHRyIHN0eWxlPSJiYWNrZ3JvdW5kOicrYmcrJztib3JkZXItYm90dG9tOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wMykiPic7CiAgICBoICs9ICc8dGQgc3R5bGU9InBhZGRpbmc6MTBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JysoaW5QPyd2YXIoLS1ncmVlbiknOid2YXIoLS10ZXh0KScpKyciPicrci50aWNrZXI7CiAgICBpZihpblApIGggKz0gJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OHB4O2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6MXB4IDRweDtib3JkZXItcmFkaXVzOjNweDttYXJnaW4tbGVmdDo0cHgiPlA8L3NwYW4+JzsKICAgIGggKz0gJzwvdGQ+JzsKICAgIGggKz0gJzx0ZCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjhweCA0cHg7Zm9udC13ZWlnaHQ6NjAwO2ZvbnQtc2l6ZToxMHB4Ij4kJytyLmZpeWF0Kyc8L3RkPic7CiAgICBtZXRyaWNzLmZvckVhY2goZnVuY3Rpb24obW0pewogICAgICB2YXIgdmFsID0gbW0ua2V5PT09J2FuYWx5c3RfdGFyZ2V0JyA/IHIuZmFpcl9wcmljZV9hbmFseXN0IDogclttbS5rZXldOwogICAgICB2YXIgY29sID0gbW0ua2V5PT09J2FuYWx5c3RfdGFyZ2V0JwogICAgICAgID8gKHIuZmFpcl9wcmljZV9hbmFseXN0JiZyLmZhaXJfcHJpY2VfYW5hbHlzdD5yLmZpeWF0Pyd2YXIoLS1ncmVlbiknOid2YXIoLS1yZWQyKScpCiAgICAgICAgOiBjb2xPZih2YWwsbW0ubG8sbW0uaGksbW0uaGIpOwogICAgICBoICs9ICc8dGQgc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7cGFkZGluZzoxMHB4IDhweDtjb2xvcjonK2NvbCsnIj4nK2ZtdFYodmFsLG1tLmZtdCxyLmZpeWF0KSsnPC90ZD4nOwogICAgfSk7CiAgICBoICs9ICc8L3RyPic7CiAgfSk7CgogIGggKz0gJzwvdGJvZHk+PC90YWJsZT4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTZweDttYXJnaW4tdG9wOjEwcHg7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nOwogIGggKz0gJzxzcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbikiPiYjOTY3OTs8L3NwYW4+IEl5aTwvc3Bhbj4nOwogIGggKz0gJzxzcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS15ZWxsb3cpIj4mIzk2Nzk7PC9zcGFuPiBNYWt1bDwvc3Bhbj4nOwogIGggKz0gJzxzcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKSI+JiM5Njc5Ozwvc3Bhbj4gRGlra2F0PC9zcGFuPic7CiAgaCArPSAnPHNwYW4+LSA9IFZlcmkgeW9rPC9zcGFuPic7CiAgaCArPSAnPHNwYW4gc3R5bGU9Im1hcmdpbi1sZWZ0OmF1dG8iPjxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2NvbG9yOnZhcigtLWdyZWVuKTtwYWRkaW5nOjFweCA0cHg7Ym9yZGVyLXJhZGl1czozcHgiPlA8L3NwYW4+IFBvcnRmb3k8L3NwYW4+JzsKICBoICs9ICc8L2Rpdj48L2Rpdj48L2Rpdj4nOwoKICBjb250YWluZXIuaW5uZXJIVE1MID0gaDsKfQo+"
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
