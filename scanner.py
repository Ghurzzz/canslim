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
    _T = "PCFET0NUWVBFIGh0bWw+CjxodG1sIGxhbmc9InRyIj4KPGhlYWQ+CjxtZXRhIGNoYXJzZXQ9IlVURi04Ii8+CjxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsaW5pdGlhbC1zY2FsZT0xIi8+Cjx0aXRsZT5DQU5TTElNIFNjYW5uZXI8L3RpdGxlPgo8bGluayByZWw9Imljb24iIHR5cGU9ImltYWdlL3N2Zyt4bWwiIGhyZWY9ImRhdGE6aW1hZ2Uvc3ZnK3htbCwlM0NzdmcgeG1sbnM9J2h0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnJyB2aWV3Qm94PScwIDAgMzIgMzInJTNFJTNDcmVjdCB3aWR0aD0nMzInIGhlaWdodD0nMzInIHJ4PSc2JyBmaWxsPSclMjMwZDExMTcnLyUzRSUzQ3BvbHlsaW5lIHBvaW50cz0nNCwyNCAxMCwxNiAxNiwyMCAyMiwxMCAyOCwxNCcgZmlsbD0nbm9uZScgc3Ryb2tlPSclMjMxMGI5ODEnIHN0cm9rZS13aWR0aD0nMi41JyBzdHJva2UtbGluZWNhcD0ncm91bmQnIHN0cm9rZS1saW5lam9pbj0ncm91bmQnLyUzRSUzQy9zdmclM0UiPgo8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PVNwYWNlK0dyb3Rlc2s6d2dodEA0MDA7NTAwOzYwMDs3MDAmZmFtaWx5PUJlYmFzK05ldWUmZmFtaWx5PUpldEJyYWlucytNb25vOndnaHRANDAwOzYwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCIvPgo8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9jaGFydC5qc0A0LjQuMC9kaXN0L2NoYXJ0LnVtZC5taW4uanMiPjwvc2NyaXB0Pgo8c3R5bGU+Cjpyb290ey0tYmc6IzA1MDcwZjstLWJnMjojMGQxMTE3Oy0tYmczOiMxNjFiMjQ7LS1ib3JkZXI6cmdiYSgyNTUsMjU1LDI1NSwwLjA4KTstLXRleHQ6I2UyZThmMDstLW11dGVkOiM0YjU1NjM7LS1ncmVlbjojMTBiOTgxOy0tZ3JlZW4yOiMzNGQzOTk7LS1yZWQ6I2VmNDQ0NDstLXJlZDI6I2Y4NzE3MTstLXllbGxvdzojZjU5ZTBiO30KKntib3gtc2l6aW5nOmJvcmRlci1ib3g7bWFyZ2luOjA7cGFkZGluZzowfQpib2R5e2JhY2tncm91bmQ6dmFyKC0tYmcpO2NvbG9yOnZhcigtLXRleHQpO2ZvbnQtZmFtaWx5OidTcGFjZSBHcm90ZXNrJyxzYW5zLXNlcmlmO21pbi1oZWlnaHQ6MTAwdmh9Ci5oZWFkZXJ7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCMwZDExMTcsIzExMTgyNyk7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtwYWRkaW5nOjE0cHggMjBweDtwb3NpdGlvbjpzdGlja3k7dG9wOjA7ei1pbmRleDoxMDB9Ci5oZWFkZXItaW5uZXJ7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTBweDttYXgtd2lkdGg6MTQwMHB4O21hcmdpbjowIGF1dG99Ci5sb2dvLW1haW57Zm9udC1mYW1pbHk6J0JlYmFzIE5ldWUnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjIycHg7bGV0dGVyLXNwYWNpbmc6NHB4O2JhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZywjMTBiOTgxLCMzYjgyZjYpOy13ZWJraXQtYmFja2dyb3VuZC1jbGlwOnRleHQ7LXdlYmtpdC10ZXh0LWZpbGwtY29sb3I6dHJhbnNwYXJlbnR9Ci50aW1lc3RhbXB7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLmxpdmUtZG90e3dpZHRoOjdweDtoZWlnaHQ6N3B4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6dmFyKC0tZ3JlZW4pO2FuaW1hdGlvbjpwdWxzZSAycyBpbmZpbml0ZTtkaXNwbGF5OmlubGluZS1ibG9jazttYXJnaW4tcmlnaHQ6NXB4fQpAa2V5ZnJhbWVzIHB1bHNlezAlLDEwMCV7b3BhY2l0eToxO2JveC1zaGFkb3c6MCAwIDAgMCByZ2JhKDE2LDE4NSwxMjksLjQpfTUwJXtvcGFjaXR5Oi43O2JveC1zaGFkb3c6MCAwIDAgNnB4IHJnYmEoMTYsMTg1LDEyOSwwKX19Ci5uYXZ7ZGlzcGxheTpmbGV4O2dhcDo0cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7b3ZlcmZsb3cteDphdXRvO2ZsZXgtd3JhcDp3cmFwfQoudGFie3BhZGRpbmc6NnB4IDE0cHg7Ym9yZGVyLXJhZGl1czo2cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NTAwO2JvcmRlcjoxcHggc29saWQgdHJhbnNwYXJlbnQ7YmFja2dyb3VuZDpub25lO2NvbG9yOnZhcigtLW11dGVkKTt0cmFuc2l0aW9uOmFsbCAuMnM7d2hpdGUtc3BhY2U6bm93cmFwfQoudGFiOmhvdmVye2NvbG9yOnZhcigtLXRleHQpO2JhY2tncm91bmQ6dmFyKC0tYmczKX0KLnRhYi5hY3RpdmV7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLXRleHQpO2JvcmRlci1jb2xvcjp2YXIoLS1ib3JkZXIpfQoudGFiLnBvcnQuYWN0aXZle2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyLWNvbG9yOnJnYmEoMTYsMTg1LDEyOSwuMyl9Ci50Zi1yb3d7ZGlzcGxheTpmbGV4O2dhcDo2cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7YWxpZ24taXRlbXM6Y2VudGVyO2ZsZXgtd3JhcDp3cmFwfQoudGYtYnRue3BhZGRpbmc6NXB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Y3Vyc29yOnBvaW50ZXI7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO3RyYW5zaXRpb246YWxsIC4yc30KLnRmLWJ0bi5hY3RpdmV7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtjb2xvcjojNjBhNWZhO2JvcmRlci1jb2xvcjpyZ2JhKDU5LDEzMCwyNDYsLjQpfQoudGYtYnRuLnN0YXJ7cG9zaXRpb246cmVsYXRpdmV9Ci50Zi1idG4uc3Rhcjo6YWZ0ZXJ7Y29udGVudDon4piFJztwb3NpdGlvbjphYnNvbHV0ZTt0b3A6LTVweDtyaWdodDotNHB4O2ZvbnQtc2l6ZTo4cHg7Y29sb3I6dmFyKC0teWVsbG93KX0KLnRmLWhpbnR7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpfQouc3RhdHN7ZGlzcGxheTpmbGV4O2dhcDo4cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7ZmxleC13cmFwOndyYXB9Ci5waWxse2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjVweDtwYWRkaW5nOjRweCAxMHB4O2JvcmRlci1yYWRpdXM6MjBweDtmb250LXNpemU6MTFweDtmb250LXdlaWdodDo2MDA7Ym9yZGVyOjFweCBzb2xpZH0KLnBpbGwuZ3tiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMSk7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlci1jb2xvcjpyZ2JhKDE2LDE4NSwxMjksLjI1KX0KLnBpbGwucntiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xKTtjb2xvcjp2YXIoLS1yZWQyKTtib3JkZXItY29sb3I6cmdiYSgyMzksNjgsNjgsLjI1KX0KLnBpbGwueXtiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMSk7Y29sb3I6dmFyKC0teWVsbG93KTtib3JkZXItY29sb3I6cmdiYSgyNDUsMTU4LDExLC4yNSl9Ci5waWxsLmJ7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjEpO2NvbG9yOiM2MGE1ZmE7Ym9yZGVyLWNvbG9yOnJnYmEoNTksMTMwLDI0NiwuMjUpfQoucGlsbC5te2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Ym9yZGVyLWNvbG9yOnZhcigtLWJvcmRlcil9Ci5kb3R7d2lkdGg6NXB4O2hlaWdodDo1cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpjdXJyZW50Q29sb3J9Ci5tYWlue3BhZGRpbmc6MTRweCAyMHB4O21heC13aWR0aDoxNDAwcHg7bWFyZ2luOjAgYXV0b30KLmdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgzMDBweCwxZnIpKTtnYXA6MTBweH0KQG1lZGlhKG1heC13aWR0aDo0ODBweCl7LmdyaWR7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmcn19Ci5jYXJke2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O292ZXJmbG93OmhpZGRlbjtjdXJzb3I6cG9pbnRlcjt0cmFuc2l0aW9uOmFsbCAuMnN9Ci5jYXJkOmhvdmVye3RyYW5zZm9ybTp0cmFuc2xhdGVZKC0ycHgpO2JveC1zaGFkb3c6MCA4cHggMjRweCByZ2JhKDAsMCwwLC40KX0KLmFjY2VudHtoZWlnaHQ6M3B4fQouY2JvZHl7cGFkZGluZzoxMnB4IDE0cHh9Ci5jdG9we2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpmbGV4LXN0YXJ0O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206OHB4fQoudGlja2Vye2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyMHB4O2xldHRlci1zcGFjaW5nOjJweDtsaW5lLWhlaWdodDoxfQouY3Bye3RleHQtYWxpZ246cmlnaHR9Ci5wdmFse2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTVweDtmb250LXdlaWdodDo2MDB9Ci5wY2hne2ZvbnQtc2l6ZToxMXB4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTttYXJnaW4tdG9wOjJweH0KLmJhZGdle2Rpc3BsYXk6aW5saW5lLWJsb2NrO3BhZGRpbmc6MnB4IDhweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6LjVweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLXRvcDozcHh9Ci5wb3J0LWJhZGdle2Rpc3BsYXk6aW5saW5lLWZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDozcHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwO2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xMik7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yNSk7bWFyZ2luLWxlZnQ6NXB4fQouc2lnc3tkaXNwbGF5OmZsZXg7ZmxleC13cmFwOndyYXA7Z2FwOjNweDttYXJnaW4tYm90dG9tOjhweH0KLnNwe2ZvbnQtc2l6ZTo5cHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLnNne2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbjIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKX0KLnNie2JhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjEpO2NvbG9yOnZhcigtLXJlZDIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpfQouc257YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLW11dGVkKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5jaGFydC13e2hlaWdodDo3NXB4O21hcmdpbi10b3A6OHB4fQoubHZsc3tkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgzLDFmcik7Z2FwOjVweDttYXJnaW4tdG9wOjhweH0KLmx2e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjVweDtwYWRkaW5nOjZweDt0ZXh0LWFsaWduOmNlbnRlcjtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5sbHtmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MnB4fQoubHZhbHtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwfQoub3ZlcmxheXtwb3NpdGlvbjpmaXhlZDtpbnNldDowO2JhY2tncm91bmQ6cmdiYSgwLDAsMCwuODgpO3otaW5kZXg6MTAwMDtkaXNwbGF5Om5vbmU7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7cGFkZGluZzoxNnB4fQoub3ZlcmxheS5vcGVue2Rpc3BsYXk6ZmxleH0KLm1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjUyMHB4O21heC1oZWlnaHQ6OTJ2aDtvdmVyZmxvdy15OmF1dG99Ci5taGVhZHtwYWRkaW5nOjE4cHggMThweCAwO2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpmbGV4LXN0YXJ0fQoubXRpdGxle2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZTozMHB4O2xldHRlci1zcGFjaW5nOjNweH0KLm1jbG9zZXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTt3aWR0aDozMHB4O2hlaWdodDozMHB4O2JvcmRlci1yYWRpdXM6N3B4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxNXB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcn0KLm1ib2R5e3BhZGRpbmc6MTRweCAxOHB4IDE4cHh9Ci5tY2hhcnR3e2hlaWdodDoxNTBweDttYXJnaW4tYm90dG9tOjE0cHh9Ci5kZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjdweDttYXJnaW4tYm90dG9tOjEycHh9Ci5kY3tiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo3cHg7cGFkZGluZzo5cHggMTFweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5kbHtmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206M3B4fQouZHZ7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMH0KLmRib3h7Ym9yZGVyLXJhZGl1czo5cHg7cGFkZGluZzoxM3B4O21hcmdpbi1ib3R0b206MTJweDtib3JkZXI6MXB4IHNvbGlkfQouZGxibHtmb250LXNpemU6OXB4O2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo1cHh9Ci5kdmVyZHtmb250LWZhbWlseTonQmViYXMgTmV1ZScsc2Fucy1zZXJpZjtmb250LXNpemU6MjZweDtsZXR0ZXItc3BhY2luZzoycHg7bWFyZ2luLWJvdHRvbTo4cHh9Ci5kcm93e2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjRweDtmb250LXNpemU6MTJweH0KLmRrZXl7Y29sb3I6dmFyKC0tbXV0ZWQpfQoucnJiYXJ7aGVpZ2h0OjRweDtiYWNrZ3JvdW5kOnZhcigtLWJnKTtib3JkZXItcmFkaXVzOjJweDttYXJnaW4tdG9wOjdweDtvdmVyZmxvdzpoaWRkZW59Ci5ycmZpbGx7aGVpZ2h0OjEwMCU7Ym9yZGVyLXJhZGl1czoycHg7dHJhbnNpdGlvbjp3aWR0aCAuOHMgZWFzZX0KLnZwYm94e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjdweDtwYWRkaW5nOjEwcHg7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO21hcmdpbi1ib3R0b206MTJweH0KLnZwdGl0bGV7Zm9udC1zaXplOjlweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo3cHh9Ci52cGdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoMywxZnIpO2dhcDo1cHh9Ci52cGN7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlci1yYWRpdXM6NXB4O3BhZGRpbmc6N3B4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlcjoxcHggc29saWR9Ci5taW5mb3tkaXNwbGF5OmlubGluZS1mbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO3dpZHRoOjE0cHg7aGVpZ2h0OjE0cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpyZ2JhKDk2LDE2NSwyNTAsLjIpO2NvbG9yOiM2MGE1ZmE7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7Y3Vyc29yOnBvaW50ZXI7bWFyZ2luLWxlZnQ6NHB4O2JvcmRlcjoxcHggc29saWQgcmdiYSg5NiwxNjUsMjUwLC4zKX0KLm1pbmZvLXBvcHVwe3Bvc2l0aW9uOmZpeGVkO2luc2V0OjA7YmFja2dyb3VuZDpyZ2JhKDAsMCwwLC44OCk7ei1pbmRleDoyMDAwO2Rpc3BsYXk6bm9uZTthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjtwYWRkaW5nOjE2cHh9Ci5taW5mby1wb3B1cC5vcGVue2Rpc3BsYXk6ZmxleH0KLm1pbmZvLW1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjQ4MHB4O21heC1oZWlnaHQ6ODV2aDtvdmVyZmxvdy15OmF1dG87cGFkZGluZzoyMHB4O3Bvc2l0aW9uOnJlbGF0aXZlfQoubWluZm8tdGl0bGV7Zm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4fQoubWluZm8tc291cmNle2ZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjEycHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4O2ZsZXgtd3JhcDp3cmFwfQoubWluZm8tcmVse3BhZGRpbmc6MnB4IDdweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMH0KLm1pbmZvLXJlbC5oaWdoe2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Y29sb3I6IzEwYjk4MX0KLm1pbmZvLXJlbC5tZWRpdW17YmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjE1KTtjb2xvcjojZjU5ZTBifQoubWluZm8tcmVsLmxvd3tiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Y29sb3I6I2VmNDQ0NH0KLm1pbmZvLWRlc2N7Zm9udC1zaXplOjEycHg7Y29sb3I6Izk0YTNiODtsaW5lLWhlaWdodDoxLjY7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8td2FybmluZ3tiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjZweDtwYWRkaW5nOjhweCAxMHB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOiNmNTllMGI7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8tcmFuZ2Vze21hcmdpbi1ib3R0b206MTRweH0KLm1pbmZvLXJhbmdlLXRpdGxle2ZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHh9Ci5taW5mby1yYW5nZXtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo4cHg7bWFyZ2luLWJvdHRvbTo2cHg7cGFkZGluZzo2cHggOHB4O2JvcmRlci1yYWRpdXM6NnB4O2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMDIpfQoubWluZm8tcmFuZ2UtZG90e3dpZHRoOjhweDtoZWlnaHQ6OHB4O2JvcmRlci1yYWRpdXM6NTAlO2ZsZXgtc2hyaW5rOjB9Ci5taW5mby1jYW5zbGlte2JhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6NnB4O3BhZGRpbmc6OHB4IDEwcHg7Zm9udC1zaXplOjExcHg7Y29sb3I6IzYwYTVmYX0KLm1pbmZvLWNsb3Nle3Bvc2l0aW9uOmFic29sdXRlO3RvcDoxNnB4O3JpZ2h0OjE2cHg7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4xKTtjb2xvcjojOTRhM2I4O3dpZHRoOjI4cHg7aGVpZ2h0OjI4cHg7Ym9yZGVyLXJhZGl1czo3cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjE0cHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyfQo6Oi13ZWJraXQtc2Nyb2xsYmFye3dpZHRoOjRweDtoZWlnaHQ6NHB4fQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRyYWNre2JhY2tncm91bmQ6dmFyKC0tYmcpfQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRodW1ie2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMSk7Ym9yZGVyLXJhZGl1czoycHh9Cjwvc3R5bGU+CjwvaGVhZD4KPGJvZHk+CjxkaXYgY2xhc3M9ImhlYWRlciI+CiAgPGRpdiBjbGFzcz0iaGVhZGVyLWlubmVyIj4KICAgIDxzcGFuIGNsYXNzPSJsb2dvLW1haW4iPkNBTlNMSU0gU0NBTk5FUjwvc3Bhbj4KICAgIDxzcGFuIGNsYXNzPSJ0aW1lc3RhbXAiPjxzcGFuIGNsYXNzPSJsaXZlLWRvdCI+PC9zcGFuPiUlVElNRVNUQU1QJSU8L3NwYW4+CiAgICA8YnV0dG9uIG9uY2xpY2s9Im9wZW5FZGl0TGlzdCgpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMyk7Y29sb3I6IzYwYTVmYTtwYWRkaW5nOjVweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMXB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtZmFtaWx5OmluaGVyaXQiPuKcj++4jyBMaXN0ZXlpIETDvHplbmxlPC9idXR0b24+CiAgPC9kaXY+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJuYXYiPgogIDxidXR0b24gY2xhc3M9InRhYiBhY3RpdmUiIG9uY2xpY2s9InNldFRhYignZGFzaGJvYXJkJyx0aGlzKSI+8J+PoCBEYXNoYm9hcmQ8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignYWxsJyx0aGlzKSI+8J+TiiBIaXNzZWxlcjwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiBwb3J0IiBvbmNsaWNrPSJzZXRUYWIoJ3BvcnQnLHRoaXMpIj7wn5K8IFBvcnRmw7Z5w7xtPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2Vhcm5pbmdzJyx0aGlzKSI+8J+ThSBFYXJuaW5nczwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdoYWZ0YWxpaycsdGhpcykiPvCfk4ggSGFmdGFsxLFrPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ3NjcmVlbmVyJyx0aGlzKSI+8J+UjSBTY3JlZW5lcjwvYnV0dG9uPgogICAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ3ZhbHVhdGlvbicsdGhpcykiPvCfko4gRGXEn2VybGVtZTwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdkaXJlY3Rpb24nLHRoaXMpIj7wn5OKIFBpeWFzYSBZw7Zuw7w8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignbWluZXJ2aW5pJyx0aGlzKSI+8J+OryBNaW5lcnZpbmk8L2J1dHRvbj4KPC9kaXY+CjxkaXYgY2xhc3M9InRmLXJvdyIgaWQ9InRmUm93IiBzdHlsZT0iZGlzcGxheTpub25lIj4KICA8YnV0dG9uIGNsYXNzPSJ0Zi1idG4gYWN0aXZlIiBkYXRhLXRmPSIxZCIgb25jbGljaz0ic2V0VGYoJzFkJyx0aGlzKSI+MUc8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0Zi1idG4gc3RhciIgZGF0YS10Zj0iMXdrIiBvbmNsaWNrPSJzZXRUZignMXdrJyx0aGlzKSI+MUg8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0Zi1idG4iIGRhdGEtdGY9IjFtbyIgb25jbGljaz0ic2V0VGYoJzFtbycsdGhpcykiPjFBPC9idXR0b24+CiAgPHNwYW4gY2xhc3M9InRmLWhpbnQiPkNBTlNMSU0gw7ZuZXJpbGVuOiAxRyArIDFIPC9zcGFuPgo8L2Rpdj4KPGRpdiBjbGFzcz0ic3RhdHMiIGlkPSJzdGF0cyI+PC9kaXY+CjxkaXYgY2xhc3M9Im1haW4iPjxkaXYgY2xhc3M9ImdyaWQiIGlkPSJncmlkIj48L2Rpdj48L2Rpdj4KPGRpdiBjbGFzcz0ib3ZlcmxheSIgaWQ9Im92ZXJsYXkiIG9uY2xpY2s9ImNsb3NlTShldmVudCkiPgogIDxkaXYgY2xhc3M9Im1vZGFsIiBpZD0ibW9kYWwiPjwvZGl2Pgo8L2Rpdj4KCjxkaXYgY2xhc3M9Im1pbmZvLXBvcHVwIiBpZD0iZWRpdFBvcHVwIiBvbmNsaWNrPSJjbG9zZUVkaXRQb3B1cChldmVudCkiPgogIDxkaXYgY2xhc3M9Im1pbmZvLW1vZGFsIiBzdHlsZT0icG9zaXRpb246cmVsYXRpdmU7bWF4LXdpZHRoOjU2MHB4IiBpZD0iZWRpdE1vZGFsIj4KICAgIDxidXR0b24gY2xhc3M9Im1pbmZvLWNsb3NlIiBvbmNsaWNrPSJjbG9zZUVkaXRQb3B1cCgpIj7inJU8L2J1dHRvbj4KICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KTttYXJnaW4tYm90dG9tOjRweCI+4pyP77iPIExpc3RleWkgRMO8emVubGU8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjE2cHgiPkdpdEh1YiBBUEkga2V5IGdlcmVrbGkg4oCUIGRlxJ9pxZ9pa2xpa2xlciBhbsSxbmRhIGtheWRlZGlsaXI8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyIDFmcjtnYXA6MTZweDttYXJnaW4tYm90dG9tOjE2cHgiPgogICAgICA8ZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij7wn5OLIFdhdGNobGlzdDwvZGl2PgogICAgICAgIDxkaXYgaWQ9IndhdGNobGlzdEVkaXRvciI+PC9kaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo2cHg7bWFyZ2luLXRvcDo4cHgiPgogICAgICAgICAgPGlucHV0IGlkPSJuZXdXYXRjaFRpY2tlciIgcGxhY2Vob2xkZXI9Ikhpc3NlIGVrbGUgKFRTTEEpIiBzdHlsZT0iZmxleDoxO2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tdGV4dCk7cGFkZGluZzo2cHggMTBweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtmb250LWZhbWlseTppbmhlcml0O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZSIvPgogICAgICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJhZGRUaWNrZXIoJ3dhdGNoJykiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzo2cHggMTJweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtjdXJzb3I6cG9pbnRlciI+KyBFa2xlPC9idXR0b24+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgogICAgICA8ZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij7wn5K8IFBvcnRmw7Z5PC9kaXY+CiAgICAgICAgPGRpdiBpZD0icG9ydGZvbGlvRWRpdG9yIj48L2Rpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjZweDttYXJnaW4tdG9wOjhweCI+CiAgICAgICAgICA8aW5wdXQgaWQ9Im5ld1BvcnRUaWNrZXIiIHBsYWNlaG9sZGVyPSJIaXNzZSBla2xlIChBQVBMKSIgc3R5bGU9ImZsZXg6MTtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLXRleHQpO3BhZGRpbmc6NnB4IDEwcHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjEycHg7Zm9udC1mYW1pbHk6aW5oZXJpdDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2UiLz4KICAgICAgICAgIDxidXR0b24gb25jbGljaz0iYWRkVGlja2VyKCdwb3J0JykiIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzo2cHggMTJweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtjdXJzb3I6cG9pbnRlciI+KyBFa2xlPC9idXR0b24+CiAgICAgICAgPC9kaXY+CiAgICAgIDwvZGl2PgogICAgPC9kaXY+CiAgICA8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTJweDttYXJnaW4tYm90dG9tOjE0cHg7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tZ3JlZW4pIj7inIUgRGXEn2nFn2lrbGlrbGVyIGtheWRlZGlsaW5jZSBiaXIgc29ucmFraSBDb2xhYiDDp2FsxLHFn3TEsXJtYXPEsW5kYSBha3RpZiBvbHVyLjwvZGl2Pgo8ZGl2IHN0eWxlPSJtYXJnaW4tYm90dG9tOjEycHgiPgogICAgICA8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo1cHgiPkdpdEh1YiBUb2tlbiAoYmlyIGtleiBnaXIsIHRhcmF5aWNpIGhhdGlybGF5YWNhayk8L2Rpdj4KICAgICAgPGlucHV0IGlkPSJnaFRva2VuSW5wdXQiIHBsYWNlaG9sZGVyPSJnaHBfLi4uIiBzdHlsZT0id2lkdGg6MTAwJTtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLXRleHQpO3BhZGRpbmc6OHB4IDEwcHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIi8+CiAgICA8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6OHB4Ij4KICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJzYXZlTGlzdFRvR2l0aHViKCkiIHN0eWxlPSJmbGV4OjE7YmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6MTBweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDA7Y3Vyc29yOnBvaW50ZXIiPvCfkr4gR2l0SHViYSBLYXlkZXQ8L2J1dHRvbj4KICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJjbG9zZUVkaXRQb3B1cCgpIiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS1tdXRlZCk7cGFkZGluZzoxMHB4IDE2cHg7Ym9yZGVyLXJhZGl1czo4cHg7Zm9udC1zaXplOjEzcHg7Y3Vyc29yOnBvaW50ZXIiPsSwcHRhbDwvYnV0dG9uPgogICAgPC9kaXY+CiAgICA8ZGl2IGlkPSJlZGl0U3RhdHVzIiBzdHlsZT0ibWFyZ2luLXRvcDoxMHB4O2ZvbnQtc2l6ZToxMnB4O3RleHQtYWxpZ246Y2VudGVyIj48L2Rpdj4KICA8L2Rpdj4KPC9kaXY+Cgo8ZGl2IGNsYXNzPSJtaW5mby1wb3B1cCIgaWQ9Im1pbmZvUG9wdXAiIG9uY2xpY2s9ImNsb3NlSW5mb1BvcHVwKGV2ZW50KSI+CiAgPGRpdiBjbGFzcz0ibWluZm8tbW9kYWwiIGlkPSJtaW5mb01vZGFsIj4KICAgIDxidXR0b24gY2xhc3M9Im1pbmZvLWNsb3NlIiBvbmNsaWNrPSJjbG9zZUluZm9Qb3B1cCgpIj7inJU8L2J1dHRvbj4KICAgIDxkaXYgaWQ9Im1pbmZvQ29udGVudCI+PC9kaXY+CiAgPC9kaXY+CjwvZGl2PgoKCjxzY3JpcHQ+CnZhciBNRVRSSUNTID0gewogIC8vIFRFS07EsEsKICAnUlNJJzogewogICAgdGl0bGU6ICdSU0kgKEfDtnJlY2VsaSBHw7zDpyBFbmRla3NpKScsCiAgICBkZXNjOiAnSGlzc2VuaW4gYcWfxLFyxLEgYWzEsW0gdmV5YSBhxZ/EsXLEsSBzYXTEsW0gYsO2bGdlc2luZGUgb2x1cCBvbG1hZMSxxJ/EsW7EsSBnw7ZzdGVyaXIuIDE0IGfDvG5sw7xrIGZpeWF0IGhhcmVrZXRsZXJpbmkgYW5hbGl6IGVkZXIuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J0HFn8SxcsSxIFNhdMSxbScsbWluOjAsbWF4OjMwLGNvbG9yOidncmVlbicsZGVzYzonRsSxcnNhdCBiw7ZsZ2VzaSDigJQgZml5YXQgw6dvayBkw7zFn23DvMWfJ30sCiAgICAgIHtsYWJlbDonTm9ybWFsJyxtaW46MzAsbWF4OjcwLGNvbG9yOid5ZWxsb3cnLGRlc2M6J07DtnRyIGLDtmxnZSd9LAogICAgICB7bGFiZWw6J0HFn8SxcsSxIEFsxLFtJyxtaW46NzAsbWF4OjEwMCxjb2xvcjoncmVkJyxkZXNjOidEaWtrYXQg4oCUIGZpeWF0IMOnb2sgecO8a3NlbG1pxZ8nfQogICAgXSwKICAgIGNhbnNsaW06ICdOIGtyaXRlcmkgaWxlIGlsZ2lsaSDigJQgZml5YXQgbW9tZW50dW11JwogIH0sCiAgJ1NNQTUwJzogewogICAgdGl0bGU6ICdTTUEgNTAgKDUwIEfDvG5sw7xrIEhhcmVrZXRsaSBPcnRhbGFtYSknLAogICAgZGVzYzogJ1NvbiA1MCBnw7xuw7xuIG9ydGFsYW1hIGthcGFuxLHFnyBmaXlhdMSxLiBLxLFzYS1vcnRhIHZhZGVsaSB0cmVuZCBnw7ZzdGVyZ2VzaS4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonw5x6ZXJpbmRlJyxjb2xvcjonZ3JlZW4nLGRlc2M6J0vEsXNhIHZhZGVsaSB0cmVuZCBwb3ppdGlmIOKAlCBnw7zDp2zDvCBzaW55YWwnfSwKICAgICAge2xhYmVsOidBbHTEsW5kYScsY29sb3I6J3JlZCcsZGVzYzonS8Sxc2EgdmFkZWxpIHRyZW5kIG5lZ2F0aWYnfQogICAgXSwKICAgIGNhbnNsaW06ICdNIGtyaXRlcmkg4oCUIHBpeWFzYSB0cmVuZGknCiAgfSwKICAnU01BMjAwJzogewogICAgdGl0bGU6ICdTTUEgMjAwICgyMDAgR8O8bmzDvGsgSGFyZWtldGxpIE9ydGFsYW1hKScsCiAgICBkZXNjOiAnU29uIDIwMCBnw7xuw7xuIG9ydGFsYW1hIGthcGFuxLHFnyBmaXlhdMSxLiBVenVuIHZhZGVsaSB0cmVuZCBnw7ZzdGVyZ2VzaS4gRW4gw7ZuZW1saSB0ZWtuaWsgc2V2aXllLicsCiAgICBzb3VyY2U6ICdUZWtuaWsgQW5hbGl6JywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOifDnHplcmluZGUnLGNvbG9yOidncmVlbicsZGVzYzonVXp1biB2YWRlbGkgYm/En2EgdHJlbmRpbmRlIOKAlCBDQU5TTElNIGnDp2luIMWfYXJ0J30sCiAgICAgIHtsYWJlbDonQWx0xLFuZGEnLGNvbG9yOidyZWQnLGRlc2M6J1V6dW4gdmFkZWxpIGF5xLEgdHJlbmRpbmRlIOKAlCBDQU5TTElNIGnDp2luIGdpcm1lJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTSBrcml0ZXJpIOKAlCB6b3J1bmx1IGtvxZ91bCcKICB9LAogICc1MlcnOiB7CiAgICB0aXRsZTogJzUyIEhhZnRhbMSxayBQb3ppc3lvbicsCiAgICBkZXNjOiAnSGlzc2VuaW4gc29uIDEgecSxbGRha2kgZml5YXQgYXJhbMSxxJ/EsW5kYSBuZXJlZGUgb2xkdcSfdW51IGfDtnN0ZXJpci4gMD15xLFsxLFuIGRpYmksIDEwMD15xLFsxLFuIHppcnZlc2kuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzAtMzAlJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1nEsWzEsW4gZGliaW5lIHlha8SxbiDigJQgcG90YW5zaXllbCBmxLFyc2F0J30sCiAgICAgIHtsYWJlbDonMzAtNzAlJyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIGLDtmxnZSDigJQgbsO2dHInfSwKICAgICAge2xhYmVsOic3MC04NSUnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1ppcnZleWUgeWFrbGHFn8SxeW9yIOKAlCBpemxlJ30sCiAgICAgIHtsYWJlbDonODUtMTAwJScsY29sb3I6J3JlZCcsZGVzYzonWmlydmV5ZSDDp29rIHlha8SxbiDigJQgZGlra2F0bGkgZ2lyJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTiBrcml0ZXJpIOKAlCB5ZW5pIHppcnZlIGvEsXLEsWzEsW3EsSBpw6dpbiBpZGVhbCBiw7ZsZ2UgJTg1LTEwMCcKICB9LAogICdIYWNpbSc6IHsKICAgIHRpdGxlOiAnSGFjaW0gKMSwxZ9sZW0gTWlrdGFyxLEpJywKICAgIGRlc2M6ICdHw7xubMO8ayBpxZ9sZW0gaGFjbWluaW4gc29uIDIwIGfDvG5sw7xrIG9ydGFsYW1heWEgb3JhbsSxLiBHw7zDp2zDvCBoYXJla2V0bGVyaW4gaGFjaW1sZSBkZXN0ZWtsZW5tZXNpIGdlcmVraXIuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J1nDvGtzZWsgKD4xLjN4KScsY29sb3I6J2dyZWVuJyxkZXNjOidLdXJ1bXNhbCBpbGdpIHZhciDigJQgZ8O8w6dsw7wgc2lueWFsJ30sCiAgICAgIHtsYWJlbDonTm9ybWFsICgwLjctMS4zeCknLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGFsYW1hIGlsZ2knfSwKICAgICAge2xhYmVsOidEw7zFn8O8ayAoPDAuN3gpJyxjb2xvcjoncmVkJyxkZXNjOifEsGxnaSBhemFsbcSxxZ8g4oCUIGRpa2thdCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ1Mga3JpdGVyaSDigJQgYXJ6L3RhbGVwIGRlbmdlc2knCiAgfSwKICAvLyBURU1FTAogICdGb3J3YXJkUEUnOiB7CiAgICB0aXRsZTogJ0ZvcndhcmQgUC9FICjEsGxlcml5ZSBEw7Zuw7xrIEZpeWF0L0themFuw6cpJywKICAgIGRlc2M6ICdTaXJrZXRpbiBvbnVtw7x6ZGVraSAxMiBheWRha2kgdGFobWluaSBrYXphbmNpbmEgZ29yZSBmaXlhdGkuIFRyYWlsaW5nIFAvRSBhcmFjaW5hIGdvcmUgZ2VsZWNlZ2Ugb2Rha2xpZGlnaSBpY2luIGRhaGEgb25lbWxpZGlyLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEFuYWxpc3QgdGFobWluaScsCiAgICByZWxpYWJpbGl0eTogJ21lZGl1bScsCiAgICB3YXJuaW5nOiAnQW5hbGlzdCB0YWhtaW5sZXJpbmUgZGF5YW7EsXIsIHlhbsSxbHTEsWPEsSBvbGFiaWxpcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic8MTUnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgYsO8ecO8bWUgYmVrbGVudGlzaSBkw7zFn8O8ayB2ZXlhIGhpc3NlIGRlxJ9lciBhbHTEsW5kYSd9LAogICAgICB7bGFiZWw6JzE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J01ha3VsIOKAlCDDp2/En3Ugc2VrdMO2ciBpw6dpbiBub3JtYWwnfSwKICAgICAge2xhYmVsOicyNS00MCcsY29sb3I6J3llbGxvdycsZGVzYzonUGFoYWzEsSBhbWEgYsO8ecO8bWUgcHJpbWkgw7ZkZW5peW9yJ30sCiAgICAgIHtsYWJlbDonPjQwJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHBhaGFsxLEg4oCUIHnDvGtzZWsgYsO8ecO8bWUgYmVrbGVudGlzaSBmaXlhdGxhbm3EscWfJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQyB2ZSBBIGtyaXRlcmxlcmkgaWxlIGlsZ2lsaScKICB9LAogICdQRUcnOiB7CiAgICB0aXRsZTogJ1BFRyBPcmFuxLEgKEZpeWF0L0themFuw6cvQsO8ecO8bWUpJywKICAgIGRlc2M6ICdQL0Ugb3JhbsSxbsSxIGLDvHnDvG1lIGjEsXrEsXlsYSBrYXLFn8SxbGHFn3TEsXLEsXIuIELDvHnDvHllbiDFn2lya2V0bGVyIGljaW4gUC9FXCdkZW4gZGFoYSBkb8SfcnUgZGXEn2VybGVtZSDDtmzDp8O8dMO8LiBQRUc9MSBhZGlsIGRlxJ9lciBrYWJ1bCBlZGlsaXIuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgQW5hbGlzdCB0YWhtaW5pJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdBbmFsaXN0IGLDvHnDvG1lIHRhaG1pbmxlcmluZSBkYXlhbsSxcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic8MS4wJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1VjdXog4oCUIGLDvHnDvG1lc2luZSBnw7ZyZSBkZcSfZXIgYWx0xLFuZGEnfSwKICAgICAge2xhYmVsOicxLjAtMS41Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J01ha3VsIOKAlCBhZGlsIGZpeWF0IGNpdmFyxLEnfSwKICAgICAge2xhYmVsOicxLjUtMi4wJyxjb2xvcjoneWVsbG93JyxkZXNjOidCaXJheiBwYWhhbMSxJ30sCiAgICAgIHtsYWJlbDonPjIuMCcsY29sb3I6J3JlZCcsZGVzYzonUGFoYWzEsSDigJQgZGlra2F0bGkgb2wnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIGLDvHnDvG1lIGthbGl0ZXNpJwogIH0sCiAgJ0VQU0dyb3d0aCc6IHsKICAgIHRpdGxlOiAnRVBTIELDvHnDvG1lc2kgKMOHZXlyZWtsaWssIFlvWSknLAogICAgZGVzYzogJ8WeaXJrZXRpbiBoaXNzZSBiYcWfxLFuYSBrYXphbmPEsW7EsW4gZ2XDp2VuIHnEsWzEsW4gYXluxLEgw6dleXJlxJ9pbmUgZ8O2cmUgYXJ0xLHFn8SxLiBDQU5TTElNXCdpbiBlbiBrcml0aWsga3JpdGVyaS4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMjUnLGNvbG9yOidncmVlbicsZGVzYzonR8O8w6dsw7wgYsO8ecO8bWUg4oCUIENBTlNMSU0ga3JpdGVyaSBrYXLFn8SxbGFuZMSxJ30sCiAgICAgIHtsYWJlbDonJTE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWkgYsO8ecO8bWUnfSwKICAgICAge2xhYmVsOiclMC0xNScsY29sb3I6J3llbGxvdycsZGVzYzonWmF5xLFmIGLDvHnDvG1lJ30sCiAgICAgIHtsYWJlbDonPDAnLGNvbG9yOidyZWQnLGRlc2M6J0themFuw6cgZMO8xZ/DvHlvciDigJQgZGlra2F0J30KICAgIF0sCiAgICBjYW5zbGltOiAnQyBrcml0ZXJpIOKAlCBlbiBrcml0aWsga3JpdGVyLCBtaW5pbXVtICUyNSBvbG1hbMSxJwogIH0sCiAgJ1Jldkdyb3d0aCc6IHsKICAgIHRpdGxlOiAnR2VsaXIgQsO8ecO8bWVzaSAoWW9ZKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIHNhdMSxxZ8vZ2VsaXJpbmluIGdlw6dlbiB5xLFsYSBnw7ZyZSBhcnTEscWfxLEuIEVQUyBiw7x5w7xtZXNpbmkgZGVzdGVrbGVtZXNpIGdlcmVraXIg4oCUIHNhZGVjZSBtYWxpeWV0IGtlc2ludGlzaXlsZSBiw7x5w7xtZSBzw7xyZMO8csO8bGViaWxpciBkZcSfaWwuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgR2Vyw6dlayB2ZXJpJywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic+JTE1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J0fDvMOnbMO8IGdlbGlyIGLDvHnDvG1lc2knfSwKICAgICAge2xhYmVsOiclNS0xNScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSBiw7x5w7xtZSd9LAogICAgICB7bGFiZWw6Jzw1Jyxjb2xvcjoncmVkJyxkZXNjOidHZWxpciBiw7x5w7xtZXNpIHphecSxZid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQgc8O8cmTDvHLDvGxlYmlsaXIgYsO8ecO8bWUgacOnaW4gxZ9hcnQnCiAgfSwKICAnTmV0TWFyZ2luJzogewogICAgdGl0bGU6ICdOZXQgTWFyamluJywKICAgIGRlc2M6ICdIZXIgMSQgZ2VsaXJkZW4gbmUga2FkYXIgbmV0IGvDonIga2FsZMSxxJ/EsW7EsSBnw7ZzdGVyaXIuIFnDvGtzZWsgbWFyamluID0gZ8O8w6dsw7wgacWfIG1vZGVsaS4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMjAnLGNvbG9yOidncmVlbicsZGVzYzonw4dvayBnw7zDp2zDvCBrw6JybMSxbMSxayd9LAogICAgICB7bGFiZWw6JyUxMC0yMCcsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpIGvDonJsxLFsxLFrJ30sCiAgICAgIHtsYWJlbDonJTUtMTAnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGEga8OicmzEsWzEsWsnfSwKICAgICAge2xhYmVsOic8NScsY29sb3I6J3JlZCcsZGVzYzonWmF5xLFmIGvDonJsxLFsxLFrJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQSBrcml0ZXJpIOKAlCBrw6JybMSxbMSxayBrYWxpdGVzaScKICB9LAogICdST0UnOiB7CiAgICB0aXRsZTogJ1JPRSAow5Z6a2F5bmFrIEvDonJsxLFsxLHEn8SxKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIMO2eiBzZXJtYXllc2l5bGUgbmUga2FkYXIga8OiciBldHRpxJ9pbmkgZ8O2c3RlcmlyLiBZw7xrc2VrIFJPRSA9IHNlcm1heWV5aSB2ZXJpbWxpIGt1bGxhbsSxeW9yLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUyNScsY29sb3I6J2dyZWVuJyxkZXNjOifDh29rIGfDvMOnbMO8IOKAlCBDQU5TTElNIGlkZWFsIHNldml5ZXNpJ30sCiAgICAgIHtsYWJlbDonJTE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWknfSwKICAgICAge2xhYmVsOiclOC0xNScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSd9LAogICAgICB7bGFiZWw6Jzw4Jyxjb2xvcjoncmVkJyxkZXNjOidaYXnEsWYnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIG1pbmltdW0gJTE3IG9sbWFsxLEnCiAgfSwKICAnR3Jvc3NNYXJnaW4nOiB7CiAgICB0aXRsZTogJ0Jyw7x0IE1hcmppbicsCiAgICBkZXNjOiAnU2F0xLHFnyBnZWxpcmluZGVuIMO8cmV0aW0gbWFsaXlldGkgZMO8xZ/DvGxkw7xrdGVuIHNvbnJhIGthbGFuIG9yYW4uIFNla3TDtnJlIGfDtnJlIGRlxJ9pxZ9pci4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lNTAnLGNvbG9yOidncmVlbicsZGVzYzonw4dvayBnw7zDp2zDvCDigJQgeWF6xLFsxLFtL1NhYVMgc2V2aXllc2knfSwKICAgICAge2xhYmVsOiclMzAtNTAnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSd9LAogICAgICB7bGFiZWw6JyUxNS0zMCcsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSDigJQgZG9uYW7EsW0veWFyxLEgaWxldGtlbiBub3JtYWwnfSwKICAgICAge2xhYmVsOic8MTUnLGNvbG9yOidyZWQnLGRlc2M6J0TDvMWfw7xrIG1hcmppbid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0vDonJsxLFsxLFrIGthbGl0ZXNpIGfDtnN0ZXJnZXNpJwogIH0sCiAgLy8gR8SwUsSwxZ4KICAnRW50cnlTY29yZSc6IHsKICAgIHRpdGxlOiAnR2lyacWfIEthbGl0ZXNpIFNrb3J1JywKICAgIGRlc2M6ICdSU0ksIFNNQSBwb3ppc3lvbnUsIFAvRSwgUEVHIHZlIEVQUyBiw7x5w7xtZXNpbmkgYmlybGXFn3RpcmVuIGJpbGXFn2lrIHNrb3IuIDAtMTAwIGFyYXPEsS4nLAogICAgc291cmNlOiAnQml6aW0gaGVzYXBsYW1hJywKICAgIHJlbGlhYmlsaXR5OiAnbG93JywKICAgIHdhcm5pbmc6ICdCVSBVWUdVTEFNQSBUQVJBRklOREFOIEhFU0FQTEFOQU4gS0FCQSBUQUhNxLBORMSwUi4gWWF0xLFyxLFtIGthcmFyxLEgacOnaW4gdGVrIGJhxZ/EsW5hIGt1bGxhbm1hLicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic3NS0xMDAnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgaWRlYWwgZ2lyacWfIGLDtmxnZXNpJ30sCiAgICAgIHtsYWJlbDonNjAtNzUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwgZml5YXQnfSwKICAgICAge2xhYmVsOic0NS02MCcsY29sb3I6J3llbGxvdycsZGVzYzonTsO2dHInfSwKICAgICAge2xhYmVsOiczMC00NScsY29sb3I6J3JlZCcsZGVzYzonUGFoYWzEsSDigJQgYmVrbGUnfSwKICAgICAge2xhYmVsOicwLTMwJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHBhaGFsxLEg4oCUIGdpcm1lJ30KICAgIF0sCiAgICBjYW5zbGltOiAnVMO8bSBrcml0ZXJsZXIgYmlsZcWfaW1pJwogIH0sCiAgJ1JSJzogewogICAgdGl0bGU6ICdSaXNrL8OWZMO8bCBPcmFuxLEgKFIvUiknLAogICAgZGVzYzogJ1BvdGFuc2l5ZWwga2F6YW5jxLFuIHJpc2tlIG9yYW7EsS4gMToyIGRlbWVrIDEkIHJpc2tlIGthcsWfxLEgMiQga2F6YW7DpyBwb3RhbnNpeWVsaSB2YXIgZGVtZWsuJywKICAgIHNvdXJjZTogJ0JpemltIGhlc2FwbGFtYScsCiAgICByZWxpYWJpbGl0eTogJ2xvdycsCiAgICB3YXJuaW5nOiAnR2lyacWfL2hlZGVmL3N0b3Agc2V2aXllbGVyaSBmb3Jtw7xsIGJhemzEsSBrYWJhIHRhaG1pbmRpcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOicxOjMrJyxjb2xvcjonZ3JlZW4nLGRlc2M6J03DvGtlbW1lbCDigJQgZ8O8w6dsw7wgZ2lyacWfIHNpbnlhbGknfSwKICAgICAge2xhYmVsOicxOjInLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSDigJQgbWluaW11bSBrYWJ1bCBlZGlsZWJpbGlyJ30sCiAgICAgIHtsYWJlbDonMToxJyxjb2xvcjoneWVsbG93JyxkZXNjOidaYXnEsWYnfSwKICAgICAge2xhYmVsOic8MToxJyxjb2xvcjoncmVkJyxkZXNjOidSaXNrIGthemFuw6d0YW4gYsO8ecO8ayDigJQgZ2lybWUnfQogICAgXSwKICAgIGNhbnNsaW06ICdSaXNrIHnDtm5ldGltaScKICB9LAogIC8vIEVBUk5JTkdTCiAgJ0Vhcm5pbmdzRGF0ZSc6IHsKICAgIHRpdGxlOiAnUmFwb3IgVGFyaWhpIChFYXJuaW5ncyBEYXRlKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIMOnZXlyZWsgZmluYW5zYWwgc29udcOnbGFyxLFuxLEgYcOnxLFrbGF5YWNhxJ/EsSB0YXJpaC4gUmFwb3Igw7ZuY2VzaSB2ZSBzb25yYXPEsSBmaXlhdCBzZXJ0IGhhcmVrZXQgZWRlYmlsaXIuJywKICAgIHNvdXJjZTogJ3lmaW5hbmNlIOKAlCBiYXplbiBoYXRhbMSxIG9sYWJpbGlyJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdUYXJpaGxlcmkgcmVzbWkgSVIgc2F5ZmFzxLFuZGFuIGRvxJ9ydWxhecSxbicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic3IGfDvG4gacOnaW5kZScsY29sb3I6J3JlZCcsZGVzYzonw4dvayB5YWvEsW4g4oCUIHBvemlzeW9uIGHDp21hayByaXNrbGknfSwKICAgICAge2xhYmVsOic4LTE0IGfDvG4nLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1lha8SxbiDigJQgZGlra2F0bGkgb2wnfSwKICAgICAge2xhYmVsOicxNCsgZ8O8bicsY29sb3I6J2dyZWVuJyxkZXNjOidZZXRlcmxpIHPDvHJlIHZhcid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Mga3JpdGVyaSDigJQgw6dleXJlayByYXBvciBrYWxpdGVzaScKICB9LAogICdBdmdNb3ZlJzogewogICAgdGl0bGU6ICdPcnRhbGFtYSBSYXBvciBIYXJla2V0aScsCiAgICBkZXNjOiAnU29uIDQgw6dleXJlayByYXBvcnVuZGEsIHJhcG9yIGfDvG7DvCB2ZSBlcnRlc2kgZ8O8biBmaXlhdMSxbiBvcnRhbGFtYSBuZSBrYWRhciBoYXJla2V0IGV0dGnEn2kuJywKICAgIHNvdXJjZTogJ0JpemltIGhlc2FwbGFtYScsCiAgICByZWxpYWJpbGl0eTogJ21lZGl1bScsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOidQb3ppdGlmICg+JTUpJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8WeaXJrZXQgZ2VuZWxsaWtsZSBiZWtsZW50aXlpIGHFn8SxeW9yJ30sCiAgICAgIHtsYWJlbDonTsO2dHIgKCUwLTUpJyxjb2xvcjoneWVsbG93JyxkZXNjOidLYXLEscWfxLFrIGdlw6dtacWfJ30sCiAgICAgIHtsYWJlbDonTmVnYXRpZicsY29sb3I6J3JlZCcsZGVzYzonUmFwb3IgZMO2bmVtaW5kZSBmaXlhdCBnZW5lbGxpa2xlIGTDvMWfw7x5b3Ig4oCUIGRpa2thdCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Mga3JpdGVyaSDigJQga2F6YW7DpyBzw7xycHJpemkgZ2XDp21pxZ9pJwogIH0KfTsKCmZ1bmN0aW9uIHNob3dJbmZvKGtleSxldmVudCl7CiAgaWYoZXZlbnQpIGV2ZW50LnN0b3BQcm9wYWdhdGlvbigpOwogIHZhciBtPU1FVFJJQ1Nba2V5XTsgaWYoIW0pIHJldHVybjsKICB2YXIgcmVsTGFiZWw9bS5yZWxpYWJpbGl0eT09PSJoaWdoIj8iR8O8dmVuaWxpciI6bS5yZWxpYWJpbGl0eT09PSJtZWRpdW0iPyJPcnRhIEfDvHZlbmlsaXIiOiJLYWJhIFRhaG1pbiI7CiAgdmFyIGg9JzxkaXYgY2xhc3M9Im1pbmZvLXRpdGxlIj4nK20udGl0bGUrJzwvZGl2Pic7CiAgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLXNvdXJjZSI+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+JyttLnNvdXJjZSsnPC9zcGFuPjxzcGFuIGNsYXNzPSJtaW5mby1yZWwgJyttLnJlbGlhYmlsaXR5KyciPicrcmVsTGFiZWwrJzwvc3Bhbj48L2Rpdj4nOwogIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby1kZXNjIj4nK20uZGVzYysnPC9kaXY+JzsKICBpZihtLndhcm5pbmcpIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby13YXJuaW5nIj7imqDvuI8gJyttLndhcm5pbmcrJzwvZGl2Pic7CiAgaWYobS5yYW5nZXMmJm0ucmFuZ2VzLmxlbmd0aCl7CiAgICBoKz0nPGRpdiBjbGFzcz0ibWluZm8tcmFuZ2VzIj48ZGl2IGNsYXNzPSJtaW5mby1yYW5nZS10aXRsZSI+UmVmZXJhbnMgRGVnZXJsZXI8L2Rpdj4nOwogICAgbS5yYW5nZXMuZm9yRWFjaChmdW5jdGlvbihyKXt2YXIgZGM9ci5jb2xvcj09PSJncmVlbiI/IiMxMGI5ODEiOnIuY29sb3I9PT0icmVkIj8iI2VmNDQ0NCI6IiNmNTllMGIiO2grPSc8ZGl2IGNsYXNzPSJtaW5mby1yYW5nZSI+PGRpdiBjbGFzcz0ibWluZm8tcmFuZ2UtZG90IiBzdHlsZT0iYmFja2dyb3VuZDonK2RjKyciPjwvZGl2PjxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOicrZGMrJyI+JytyLmxhYmVsKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrci5kZXNjKyc8L2Rpdj48L2Rpdj48L2Rpdj4nO30pOwogICAgaCs9JzwvZGl2Pic7CiAgfQogIGlmKG0uY2Fuc2xpbSkgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLWNhbnNsaW0iPvCfk4ogQ0FOU0xJTTogJyttLmNhbnNsaW0rJzwvZGl2Pic7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvQ29udGVudCIpLmlubmVySFRNTD1oOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwp9CmZ1bmN0aW9uIGNsb3NlSW5mb1BvcHVwKGUpe2lmKCFlfHxlLnRhcmdldD09PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikpe2RvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpO319Cgo8L3NjcmlwdD4KPC9zY3JpcHQ+CjxzY3JpcHQ+CnZhciBURl9EQVRBPSUlVEZfREFUQSUlOwp2YXIgUE9SVD0lJVBPUlQlJTsKdmFyIEVBUk5JTkdTX0RBVEE9JSVFQVJOSU5HU19EQVRBJSU7CnZhciBNQVJLRVRfREFUQT0lJU1BUktFVF9EQVRBJSU7CnZhciBORVdTX0RBVEE9JSVORVdTX0RBVEElJTsKdmFyIEFJX0RBVEE9JSVBSV9EQVRBJSU7CnZhciBXRUVLTFlfREFUQT0lJVdFRUtMWV9EQVRBJSU7CnZhciBTQ1JFRU5FUl9EQVRBPSUlU0NSRUVORVJfREFUQSUlOwp2YXIgRElSRUNUSU9OX0RBVEE9JSVESVJFQ1RJT05fREFUQSUlOwp2YXIgY3VyVGFiPSJhbGwiLGN1clRmPSIxZCIsY3VyRGF0YT1URl9EQVRBWyIxZCJdLnNsaWNlKCk7CnZhciBtaW5pQ2hhcnRzPXt9LG1DaGFydD1udWxsOwp2YXIgU1M9ewogICJHVUNMVSBBTCI6e2JnOiJyZ2JhKDE2LDE4NSwxMjksLjEyKSIsYmQ6InJnYmEoMTYsMTg1LDEyOSwuMzUpIix0eDoiIzEwYjk4MSIsYWM6IiMxMGI5ODEiLGxibDoiR1VDTFUgQUwifSwKICAiQUwiOntiZzoicmdiYSg1MiwyMTEsMTUzLC4xKSIsYmQ6InJnYmEoNTIsMjExLDE1MywuMykiLHR4OiIjMzRkMzk5IixhYzoiIzM0ZDM5OSIsbGJsOiJBTCJ9LAogICJESUtLQVQiOntiZzoicmdiYSgyNDUsMTU4LDExLC4xKSIsYmQ6InJnYmEoMjQ1LDE1OCwxMSwuMykiLHR4OiIjZjU5ZTBiIixhYzoiI2Y1OWUwYiIsbGJsOiJESUtLQVQifSwKICAiWkFZSUYiOntiZzoicmdiYSgxMDcsMTE0LDEyOCwuMSkiLGJkOiJyZ2JhKDEwNywxMTQsMTI4LC4zKSIsdHg6IiM5Y2EzYWYiLGFjOiIjNmI3MjgwIixsYmw6IlpBWUlGIn0sCiAgIlNBVCI6e2JnOiJyZ2JhKDIzOSw2OCw2OCwuMTIpIixiZDoicmdiYSgyMzksNjgsNjgsLjM1KSIsdHg6IiNlZjQ0NDQiLGFjOiIjZWY0NDQ0IixsYmw6IlNBVCJ9Cn07CgpmdW5jdGlvbiBpYihrZXksbGFiZWwpewogIHJldHVybiBsYWJlbCsnIDxzcGFuIGNsYXNzPSJtaW5mbyIgb25jbGljaz0ic2hvd0luZm8oXCcnK2tleSsnXCcsZXZlbnQpIj4/PC9zcGFuPic7Cn0KCmZ1bmN0aW9uIHNldFRhYih0LGVsKXsKICBjdXJUYWI9dDsKICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIudGFiIikuZm9yRWFjaChmdW5jdGlvbihiKXtiLmNsYXNzTGlzdC5yZW1vdmUoImFjdGl2ZSIpO30pOwogIGVsLmNsYXNzTGlzdC5hZGQoImFjdGl2ZSIpOwogIHZhciB0ZlJvdz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidGZSb3ciKTsKICBpZih0ZlJvdykgdGZSb3cuc3R5bGUuZGlzcGxheT0odD09PSJkYXNoYm9hcmQifHx0PT09ImVhcm5pbmdzInx8dD09PSJydXRpbiJ8fHQ9PT0iaGFmdGFsaWsifHx0PT09InNjcmVlbmVyInx8dD09PSJ2YWx1YXRpb24ifHx0PT09ImRpcmVjdGlvbiIpPyJub25lIjoiZmxleCI7CiAgaWYodD09PSJkYXNoYm9hcmQiKSByZW5kZXJEYXNoYm9hcmQoKTsKICBlbHNlIGlmKHQ9PT0iZWFybmluZ3MiKSByZW5kZXJFYXJuaW5ncygpOwogIGVsc2UgaWYodD09PSJoYWZ0YWxpayIpIHJlbmRlckhhZnRhbGlrKCk7CiAgZWxzZSBpZih0PT09InNjcmVlbmVyIikgcmVuZGVyU2NyZWVuZXIoKTsKICBlbHNlIGlmKHQ9PT0idmFsdWF0aW9uIikgcmVuZGVyVmFsdWF0aW9uKCk7CiAgZWxzZSBpZih0PT09ImRpcmVjdGlvbiIpIHJlbmRlckRpcmVjdGlvbigpOwogIGVsc2UgaWYodD09PSJtaW5lcnZpbmkiKSByZW5kZXJNaW5lcnZpbmkoKTsKICBlbHNlIHsKICAgIHZhciBnPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgICBpZihnKXtnLnN0eWxlLmRpc3BsYXk9Jyc7Zy5zdHlsZS53aWR0aD0nJzt9CiAgICByZW5kZXJHcmlkKCk7CiAgfQp9CgpmdW5jdGlvbiBzZXRUZih0ZixlbCl7CiAgY3VyVGY9dGY7CiAgZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbCgiLnRmLWJ0biIpLmZvckVhY2goZnVuY3Rpb24oYil7Yi5jbGFzc0xpc3QudG9nZ2xlKCJhY3RpdmUiLGIuZGF0YXNldC50Zj09PXRmKTt9KTsKICBjdXJEYXRhPShURl9EQVRBW3RmXXx8VEZfREFUQVsiMWQiXSkuc2xpY2UoKTsKICByZW5kZXJTdGF0cygpOwogIHJlbmRlckdyaWQoKTsKfQoKZnVuY3Rpb24gZmlsdGVyZWQoKXsKICB2YXIgZD1jdXJEYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KTsKICBpZihjdXJUYWI9PT0icG9ydCIpIHJldHVybiBkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gUE9SVC5pbmNsdWRlcyhyLnRpY2tlcik7fSk7CiAgaWYoY3VyVGFiPT09ImJ1eSIpIHJldHVybiBkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0iR1VDTFUgQUwifHxyLnNpbnlhbD09PSJBTCI7fSk7CiAgaWYoY3VyVGFiPT09InNlbGwiKSByZXR1cm4gZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09IlNBVCI7fSk7CiAgcmV0dXJuIGQ7Cn0KCmZ1bmN0aW9uIHJlbmRlclN0YXRzKCl7CiAgdmFyIGQ9Y3VyRGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSk7CiAgdmFyIGNudD17fTsKICBkLmZvckVhY2goZnVuY3Rpb24ocil7Y250W3Iuc2lueWFsXT0oY250W3Iuc2lueWFsXXx8MCkrMTt9KTsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgic3RhdHMiKS5pbm5lckhUTUw9CiAgICAnPGRpdiBjbGFzcz0icGlsbCBnIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2Pkd1Y2x1IEFsOiAnKyhjbnRbIkdVQ0xVIEFMIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgZyI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5BbDogJysoY250WyJBTCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIHkiPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+RGlra2F0OiAnKyhjbnRbIkRJS0tBVCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIHIiPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+U2F0OiAnKyhjbnRbIlNBVCJdfHwwKSsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIGIiIHN0eWxlPSJtYXJnaW4tbGVmdDphdXRvIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PlBvcnRmb2x5bzogJytQT1JULmxlbmd0aCsnPC9kaXY+JysKICAgICc8ZGl2IGNsYXNzPSJwaWxsIG0iPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+JytkLmxlbmd0aCsnIGFuYWxpejwvZGl2Pic7Cn0KCmZ1bmN0aW9uIHJlbmRlckdyaWQoKXsKICBPYmplY3QudmFsdWVzKG1pbmlDaGFydHMpLmZvckVhY2goZnVuY3Rpb24oYyl7Yy5kZXN0cm95KCk7fSk7CiAgbWluaUNoYXJ0cz17fTsKICB2YXIgZj1maWx0ZXJlZCgpOwogIHZhciBncmlkPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJncmlkIik7CiAgaWYoIWYubGVuZ3RoKXtncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMTt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjQwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5IaXNzZSBidWx1bmFtYWRpPC9kaXY+JztyZXR1cm47fQogIGdyaWQuaW5uZXJIVE1MPWYubWFwKGZ1bmN0aW9uKHIpe3JldHVybiBidWlsZENhcmQocik7fSkuam9pbigiIik7CiAgZi5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgdmFyIGN0eD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWMtIityLnRpY2tlcik7CiAgICBpZihjdHgmJnIuY2hhcnRfY2xvc2VzJiZyLmNoYXJ0X2Nsb3Nlcy5sZW5ndGgpewogICAgICB2YXIgc3M9U1Nbci5zaW55YWxdfHxTU1siRElLS0FUIl07CiAgICAgIG1pbmlDaGFydHNbIm0iK3IudGlja2VyXT1uZXcgQ2hhcnQoY3R4LHt0eXBlOiJsaW5lIixkYXRhOntsYWJlbHM6ci5jaGFydF9kYXRlcyxkYXRhc2V0czpbe2RhdGE6ci5jaGFydF9jbG9zZXMsYm9yZGVyQ29sb3I6c3MuYWMsYm9yZGVyV2lkdGg6MS41LGZpbGw6dHJ1ZSxiYWNrZ3JvdW5kQ29sb3I6c3MuYWMrIjE4Iixwb2ludFJhZGl1czowLHRlbnNpb246MC40fV19LG9wdGlvbnM6e3BsdWdpbnM6e2xlZ2VuZDp7ZGlzcGxheTpmYWxzZX19LHNjYWxlczp7eDp7ZGlzcGxheTpmYWxzZX0seTp7ZGlzcGxheTpmYWxzZX19LGFuaW1hdGlvbjp7ZHVyYXRpb246NTAwfSxyZXNwb25zaXZlOnRydWUsbWFpbnRhaW5Bc3BlY3RSYXRpbzpmYWxzZX19KTsKICAgIH0KICB9KTsKfQoKZnVuY3Rpb24gYnVpbGRDYXJkKHIpewogIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICB2YXIgZGM9ci5kZWdpc2ltPj0wPyJ2YXIoLS1ncmVlbjIpIjoidmFyKC0tcmVkMikiOwogIHZhciBkcz0oci5kZWdpc2ltPj0wPyIrIjoiIikrci5kZWdpc2ltKyIlIjsKICB2YXIgZXNjb2w9ci5lbnRyeV9zY29yZT49NzU/InZhcigtLWdyZWVuKSI6ci5lbnRyeV9zY29yZT49NjA/InZhcigtLWdyZWVuMikiOnIuZW50cnlfc2NvcmU+PTQ1PyJ2YXIoLS15ZWxsb3cpIjpyLmVudHJ5X3Njb3JlPj0zMD8idmFyKC0tcmVkMikiOiJ2YXIoLS1yZWQpIjsKICB2YXIgcHZjb2w9ci5wcmljZV92c19jb2xvcj09PSJncmVlbiI/InZhcigtLWdyZWVuKSI6ci5wcmljZV92c19jb2xvcj09PSJ5ZWxsb3ciPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkMikiOwogIHZhciBzaWdzPVsKICAgIHtsOiJUcmVuZCIsdjpyLnRyZW5kPT09Ill1a3NlbGVuIj8iWXVrc2VsaXlvciI6ci50cmVuZD09PSJEdXNlbiI/IkR1c3V5b3IiOiJZYXRheSIsZzpyLnRyZW5kPT09Ill1a3NlbGVuIj90cnVlOnIudHJlbmQ9PT0iRHVzZW4iP2ZhbHNlOm51bGx9LAogICAge2w6IlNNQTUwIix2OnIuYWJvdmU1MD8iVXplcmluZGUiOiJBbHRpbmRhIixnOnIuYWJvdmU1MH0sCiAgICB7bDoiU01BMjAwIix2OnIuYWJvdmUyMDA/IlV6ZXJpbmRlIjoiQWx0aW5kYSIsZzpyLmFib3ZlMjAwfSwKICAgIHtsOiJSU0kiLHY6ci5yc2l8fCI/IixnOnIucnNpP3IucnNpPDMwP3RydWU6ci5yc2k+NzA/ZmFsc2U6bnVsbDpudWxsfSwKICAgIHtsOiI1MlciLHY6IiUiK3IucGN0X2Zyb21fNTJ3KyIgdXphayIsZzpyLm5lYXJfNTJ3fQogIF0ubWFwKGZ1bmN0aW9uKHMpe3JldHVybiAnPHNwYW4gY2xhc3M9InNwICcrKHMuZz09PXRydWU/InNnIjpzLmc9PT1mYWxzZT8ic2IiOiJzbiIpKyciPicrcy5sKyI6ICIrcy52KyI8L3NwYW4+Ijt9KS5qb2luKCIiKTsKICByZXR1cm4gJzxkaXYgY2xhc3M9ImNhcmQiIHN0eWxlPSJib3JkZXItY29sb3I6Jysoci5wb3J0Zm9saW8/InJnYmEoMTYsMTg1LDEyOSwuMjUpIjpzcy5iZCkrJyIgb25jbGljaz0ib3Blbk0oXCcnK3IudGlja2VyKydcJykiPicKICAgICsnPGRpdiBjbGFzcz0iYWNjZW50IiBzdHlsZT0iYmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoOTBkZWcsJytzcy5hYysnLCcrc3MuYWMrJzg4KSI+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJjYm9keSI+PGRpdiBjbGFzcz0iY3RvcCI+PGRpdj48ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo0cHgiPicKICAgICsnPHNwYW4gY2xhc3M9InRpY2tlciIgc3R5bGU9ImNvbG9yOicrc3MudHgrJyI+JytyLnRpY2tlcisnPC9zcGFuPicKICAgICsoci5wb3J0Zm9saW8/JzxzcGFuIGNsYXNzPSJwb3J0LWJhZGdlIj5QPC9zcGFuPic6JycpKwogICAgJzwvZGl2PjxzcGFuIGNsYXNzPSJiYWRnZSIgc3R5bGU9ImJhY2tncm91bmQ6Jytzcy5iZysnO2NvbG9yOicrc3MudHgrJztib3JkZXI6MXB4IHNvbGlkICcrc3MuYmQrJyI+Jytzcy5sYmwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImNwciI+PGRpdiBjbGFzcz0icHZhbCI+JCcrci5maXlhdCsnPC9kaXY+PGRpdiBjbGFzcz0icGNoZyIgc3R5bGU9ImNvbG9yOicrZGMrJyI+JytkcysnPC9kaXY+JwogICAgKyhyLnBlX2Z3ZD8nPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkZ3ZFBFOicrci5wZV9md2QudG9GaXhlZCgxKSsnPC9kaXY+JzonJykKICAgICsnPC9kaXY+PC9kaXY+PGRpdiBjbGFzcz0ic2lncyI+JytzaWdzKyc8L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9Im1hcmdpbi10b3A6NnB4Ij4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjNweCI+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5HaXJpcyBLYWxpdGVzaTwvc3Bhbj48c3BhbiBzdHlsZT0iZm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X3Njb3JlKycvMTAwPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iaGVpZ2h0OjRweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czoycHg7b3ZlcmZsb3c6aGlkZGVuIj48ZGl2IHN0eWxlPSJoZWlnaHQ6MTAwJTt3aWR0aDonK3IuZW50cnlfc2NvcmUrJyU7YmFja2dyb3VuZDonK2VzY29sKyc7Ym9yZGVyLXJhZGl1czoycHgiPjwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi10b3A6M3B4Ij48c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK2VzY29sKyciPicrci5lbnRyeV9sYWJlbCsnPC9zcGFuPjxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrcHZjb2wrJyI+JytyLnByaWNlX3ZzX2lkZWFsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8L2Rpdj48ZGl2IGNsYXNzPSJjaGFydC13Ij48Y2FudmFzIGlkPSJtYy0nK3IudGlja2VyKyciPjwvY2FudmFzPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0ibHZscyI+JwogICAgKyc8ZGl2IGNsYXNzPSJsdiI+PGRpdiBjbGFzcz0ibGwiPkhlbWVuIEdpcjwvZGl2PjxkaXYgY2xhc3M9Imx2YWwiIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbjIpIj4kJytyLmVudHJ5X2FnZ3Jlc3NpdmUrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0ibHYiPjxkaXYgY2xhc3M9ImxsIj5IZWRlZjwvZGl2PjxkaXYgY2xhc3M9Imx2YWwiIHN0eWxlPSJjb2xvcjojNjBhNWZhIj4kJytyLmhlZGVmKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9Imx2Ij48ZGl2IGNsYXNzPSJsbCI+U3RvcDwvZGl2PjxkaXYgY2xhc3M9Imx2YWwiIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKSI+JCcrci5zdG9wKyc8L2Rpdj48L2Rpdj4nCiAgICArJzwvZGl2PjwvZGl2PjwvZGl2Pic7Cn0KCmZ1bmN0aW9uIHJlbmRlckRhc2hib2FyZCgpewogIHZhciBncmlkPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJncmlkIik7CiAgdmFyIG1kPU1BUktFVF9EQVRBfHx7fTsKICB2YXIgc3A9bWQuU1A1MDB8fHt9OwogIHZhciBuYXM9bWQuTkFTREFRfHx7fTsKICB2YXIgdml4PW1kLlZJWHx8e307CiAgdmFyIG1TaWduYWw9bWQuTV9TSUdOQUx8fCJOT1RSIjsKICB2YXIgbUxhYmVsPW1kLk1fTEFCRUx8fCJWZXJpIHlvayI7CiAgdmFyIG1Db2xvcj1tU2lnbmFsPT09IkdVQ0xVIj8idmFyKC0tZ3JlZW4pIjptU2lnbmFsPT09IlpBWUlGIj8idmFyKC0tcmVkMikiOiJ2YXIoLS15ZWxsb3cpIjsKICB2YXIgbUJnPW1TaWduYWw9PT0iR1VDTFUiPyJyZ2JhKDE2LDE4NSwxMjksLjA4KSI6bVNpZ25hbD09PSJaQVlJRiI/InJnYmEoMjM5LDY4LDY4LC4wOCkiOiJyZ2JhKDI0NSwxNTgsMTEsLjA4KSI7CiAgdmFyIG1Cb3JkZXI9bVNpZ25hbD09PSJHVUNMVSI/InJnYmEoMTYsMTg1LDEyOSwuMjUpIjptU2lnbmFsPT09IlpBWUlGIj8icmdiYSgyMzksNjgsNjgsLjI1KSI6InJnYmEoMjQ1LDE1OCwxMSwuMjUpIjsKICB2YXIgbUljb249bVNpZ25hbD09PSJHVUNMVSI/IuKchSI6bVNpZ25hbD09PSJaQVlJRiI/IuKdjCI6IuKaoO+4jyI7CgogIGZ1bmN0aW9uIGluZGV4Q2FyZChuYW1lLGRhdGEpewogICAgaWYoIWRhdGF8fCFkYXRhLnByaWNlKSByZXR1cm4gIiI7CiAgICB2YXIgY2M9ZGF0YS5jaGFuZ2U+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgICB2YXIgY3M9KGRhdGEuY2hhbmdlPj0wPyIrIjoiIikrZGF0YS5jaGFuZ2UrIiUiOwogICAgdmFyIHM1MD1kYXRhLmFib3ZlNTA/JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjEwcHgiPlNNQTUwIOKckzwvc3Bhbj4nOic8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMik7Zm9udC1zaXplOjEwcHgiPlNNQTUwIOKclzwvc3Bhbj4nOwogICAgdmFyIHMyMDA9ZGF0YS5hYm92ZTIwMD8nPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6MTBweCI+U01BMjAwIOKckzwvc3Bhbj4nOic8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tcmVkMik7Zm9udC1zaXplOjEwcHgiPlNNQTIwMCDinJc8L3NwYW4+JzsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4IDE2cHg7ZmxleDoxO21pbi13aWR0aDoxNTBweCI+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjZweCI+JytuYW1lKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS10ZXh0KSI+JCcrZGF0YS5wcmljZSsnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTNweDtjb2xvcjonK2NjKyc7bWFyZ2luLWJvdHRvbTo4cHgiPicrY3MrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjhweCI+JytzNTArczIwMCsnPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciBwb3J0RGF0YT1jdXJEYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YSYmUE9SVC5pbmNsdWRlcyhyLnRpY2tlcik7fSk7CiAgdmFyIHBvcnRIdG1sPSIiOwogIGlmKHBvcnREYXRhLmxlbmd0aCl7CiAgICBwb3J0SHRtbD0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTRweCI+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTJweCI+8J+SvCBQb3J0ZsO2eSDDlnpldGk8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgxNDBweCwxZnIpKTtnYXA6OHB4Ij4nOwogICAgcG9ydERhdGEuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgICAgdmFyIGRjPXIuZGVnaXNpbT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICAgICAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogICAgICBwb3J0SHRtbCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkICcrc3MuYmQrJztib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHg7Y3Vyc29yOnBvaW50ZXIiIG9uY2xpY2s9Im9wZW5NKFwnJytyLnRpY2tlcisnXCcpIj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToxNnB4O2xldHRlci1zcGFjaW5nOjJweDtjb2xvcjonK3NzLnR4KyciPicrci50aWNrZXIrJzwvc3Bhbj4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtiYWNrZ3JvdW5kOicrc3MuYmcrJztjb2xvcjonK3NzLnR4Kyc7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6MnB4Ij4nK3NzLmxibCsnPC9zcGFuPjwvZGl2PicKICAgICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTNweDtmb250LXdlaWdodDo2MDAiPiQnK3IuZml5YXQrJzwvZGl2PicKICAgICAgICArJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTFweDtjb2xvcjonK2RjKyciPicrKHIuZGVnaXNpbT49MD8iKyI6IiIpK3IuZGVnaXNpbSsnJTwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICAgIHBvcnRIdG1sKz0nPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciB1cmdlbnRFYXJuaW5ncz1FQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gZS5hbGVydD09PSJyZWQifHxlLmFsZXJ0PT09InllbGxvdyI7fSk7CiAgdmFyIGVhcm5pbmdzQWxlcnQ9IiI7CiAgaWYodXJnZW50RWFybmluZ3MubGVuZ3RoKXsKICAgIGVhcm5pbmdzQWxlcnQ9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyNDUsMTU4LDExLC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI0NSwxNTgsMTEsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE0cHggMTZweDttYXJnaW4tYm90dG9tOjE0cHgiPicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS15ZWxsb3cpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7imqDvuI8gWWFrbGHFn2FuIFJhcG9ybGFyPC9kaXY+JzsKICAgIHVyZ2VudEVhcm5pbmdzLmZvckVhY2goZnVuY3Rpb24oZSl7CiAgICAgIHZhciBpYz1lLmFsZXJ0PT09InJlZCI/IvCflLQiOiLwn5+hIjsKICAgICAgZWFybmluZ3NBbGVydCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbTo2cHg7Zm9udC1zaXplOjEycHgiPicKICAgICAgICArJzxzcGFuPicraWMrJyA8c3Ryb25nPicrZS50aWNrZXIrJzwvc3Ryb25nPjwvc3Bhbj4nCiAgICAgICAgKyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj4nK2UubmV4dF9kYXRlKycgKCcrKGUuZGF5c190b19lYXJuaW5ncz09PTA/IkJVR8OcTiI6ZS5kYXlzX3RvX2Vhcm5pbmdzKyIgZ8O8biIpKycpPC9zcGFuPjwvZGl2Pic7CiAgICB9KTsKICAgIGVhcm5pbmdzQWxlcnQrPSc8L2Rpdj4nOwogIH0KCiAgdmFyIG5ld3NIdG1sPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHgiPicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMnB4Ij7wn5OwIFNvbiBIYWJlcmxlcjwvZGl2Pic7CiAgaWYoTkVXU19EQVRBJiZORVdTX0RBVEEubGVuZ3RoKXsKICAgIE5FV1NfREFUQS5zbGljZSgwLDEwKS5mb3JFYWNoKGZ1bmN0aW9uKG4pewogICAgICB2YXIgcGI9bi5wb3J0Zm9saW8/JzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTIpO2NvbG9yOnZhcigtLWdyZWVuKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMjUpO3BhZGRpbmc6MXB4IDVweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMCI+UDwvc3Bhbj4nOiIiOwogICAgICB2YXIgdGE9IiI7CiAgICAgIGlmKG4uZGF0ZXRpbWUpe3ZhciBkaWZmPU1hdGguZmxvb3IoKERhdGUubm93KCkvMTAwMC1uLmRhdGV0aW1lKS8zNjAwKTt0YT1kaWZmPDI0PyhkaWZmKyJzIMO2bmNlIik6KE1hdGguZmxvb3IoZGlmZi8yNCkrImcgw7ZuY2UiKTt9CiAgICAgIG5ld3NIdG1sKz0nPGRpdiBzdHlsZT0icGFkZGluZzoxMHB4IDA7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDQpIj4nCiAgICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo2cHg7bWFyZ2luLWJvdHRvbTo0cHgiPicKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0teWVsbG93KSI+JytuLnRpY2tlcisnPC9zcGFuPicrcGIKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tbGVmdDphdXRvIj4nK3RhKyc8L3NwYW4+PC9kaXY+JwogICAgICAgICsnPGEgaHJlZj0iJytuLnVybCsnIiB0YXJnZXQ9Il9ibGFuayIgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLXRleHQpO3RleHQtZGVjb3JhdGlvbjpub25lO2xpbmUtaGVpZ2h0OjEuNTtkaXNwbGF5OmJsb2NrIj4nKyhuLmhlYWRsaW5lX3RyfHxuLmhlYWRsaW5lKSsnPC9hPicKICAgICAgICArKG4uc3VtbWFyeV90cnx8bi5zdW1tYXJ5Pyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjojOWNhM2FmO21hcmdpbi10b3A6NHB4O2xpbmUtaGVpZ2h0OjEuNCI+Jysobi5zdW1tYXJ5X3RyfHxuLnN1bW1hcnkpLnN1YnN0cmluZygwLDE1MCkrJy4uLjwvZGl2Pic6JycpKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLXRvcDozcHgiPicrbi5zb3VyY2UrJzwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICB9IGVsc2UgewogICAgbmV3c0h0bWwrPSc8ZGl2IHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1zaXplOjEycHgiPkhhYmVyIGJ1bHVuYW1hZGk8L2Rpdj4nOwogIH0KICBuZXdzSHRtbCs9JzwvZGl2Pic7CgogIGdyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nCiAgICArJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JyttQmcrJztib3JkZXI6MXB4IHNvbGlkICcrbUJvcmRlcisnO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTJweCI+JwogICAgKyc8ZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7bWFyZ2luLWJvdHRvbTo0cHgiPkNBTlNMSU0gTSBLUsSwVEVSxLA8L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK21Db2xvcisnIj4nK21JY29uKycgJyttTGFiZWwrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO3RleHQtYWxpZ246cmlnaHQiPlZJWDogJysodml4LnByaWNlfHwiPyIpKyc8YnI+JwogICAgKyc8c3BhbiBzdHlsZT0iY29sb3I6Jysodml4LnByaWNlJiZ2aXgucHJpY2U+MjU/InZhcigtLXJlZDIpIjoidmFyKC0tZ3JlZW4pIikrJyI+Jysodml4LnByaWNlJiZ2aXgucHJpY2U+MjU/IlnDvGtzZWsgdm9sYXRpbGl0ZSI6Ik5vcm1hbCB2b2xhdGlsaXRlIikrJzwvc3Bhbj48L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcDttYXJnaW4tYm90dG9tOjE0cHgiPicraW5kZXhDYXJkKCJTJlAgNTAwIChTUFkpIixzcCkraW5kZXhDYXJkKCJOQVNEQVEgKFFRUSkiLG5hcykrJzwvZGl2PicKICAgICtwb3J0SHRtbCtlYXJuaW5nc0FsZXJ0K25ld3NIdG1sCiAgICArJzxkaXYgc3R5bGU9Im1hcmdpbi10b3A6MjBweCI+JytidWlsZFJ1dGluSFRNTCgpKyc8L2Rpdj4nCiAgICArJzwvZGl2Pic7Cn0KCmZ1bmN0aW9uIHJlbmRlckVhcm5pbmdzKCl7CiAgdmFyIGdyaWQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdyaWQiKTsKICB2YXIgc29ydGVkPUVBUk5JTkdTX0RBVEEuZmlsdGVyKGZ1bmN0aW9uKGUpe3JldHVybiBlLm5leHRfZGF0ZTt9KS5zb3J0KGZ1bmN0aW9uKGEsYil7CiAgICB2YXIgZGE9YS5kYXlzX3RvX2Vhcm5pbmdzIT1udWxsP2EuZGF5c190b19lYXJuaW5nczo5OTk7CiAgICB2YXIgZGI9Yi5kYXlzX3RvX2Vhcm5pbmdzIT1udWxsP2IuZGF5c190b19lYXJuaW5nczo5OTk7CiAgICByZXR1cm4gZGEtZGI7CiAgfSk7CiAgdmFyIG5vRGF0ZT1FQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gIWUubmV4dF9kYXRlO30pOwogIGlmKCFzb3J0ZWQubGVuZ3RoJiYhbm9EYXRlLmxlbmd0aCl7Z3JpZC5pbm5lckhUTUw9JzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTE7dGV4dC1hbGlnbjpjZW50ZXI7cGFkZGluZzo0MHB4O2NvbG9yOnZhcigtLW11dGVkKSI+RWFybmluZ3MgdmVyaXNpIGJ1bHVuYW1hZGk8L2Rpdj4nO3JldHVybjt9CiAgdmFyIGg9JzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CiAgc29ydGVkLmZvckVhY2goZnVuY3Rpb24oZSl7CiAgICB2YXIgYWI9ZS5hbGVydD09PSJyZWQiPyJyZ2JhKDIzOSw2OCw2OCwuMTIpIjplLmFsZXJ0PT09InllbGxvdyI/InJnYmEoMjQ1LDE1OCwxMSwuMSkiOiJyZ2JhKDI1NSwyNTUsMjU1LC4wMikiOwogICAgdmFyIGFiZD1lLmFsZXJ0PT09InJlZCI/InJnYmEoMjM5LDY4LDY4LC4zNSkiOmUuYWxlcnQ9PT0ieWVsbG93Ij8icmdiYSgyNDUsMTU4LDExLC4zKSI6InJnYmEoMjU1LDI1NSwyNTUsLjA3KSI7CiAgICB2YXIgYWk9ZS5hbGVydD09PSJyZWQiPyLwn5S0IjplLmFsZXJ0PT09InllbGxvdyI/IvCfn6EiOiLwn5OFIjsKICAgIHZhciBkdD1lLmRheXNfdG9fZWFybmluZ3MhPW51bGw/KGUuZGF5c190b19lYXJuaW5ncz09PTA/IkJVR1VOIjplLmRheXNfdG9fZWFybmluZ3M9PT0xPyJZYXJpbiI6ZS5kYXlzX3RvX2Vhcm5pbmdzKyIgZ3VuIHNvbnJhIik6IiI7CiAgICB2YXIgYW1Db2w9ZS5hdmdfbW92ZV9wY3QhPW51bGw/KGUuYXZnX21vdmVfcGN0Pj0wPyJ2YXIoLS1ncmVlbikiOiJ2YXIoLS1yZWQyKSIpOiJ2YXIoLS1tdXRlZCkiOwogICAgdmFyIGFtU3RyPWUuYXZnX21vdmVfcGN0IT1udWxsPyhlLmF2Z19tb3ZlX3BjdD49MD8iKyI6IiIpK2UuYXZnX21vdmVfcGN0KyIlIjoi4oCUIjsKICAgIHZhciB5Yj1lLmFsZXJ0PT09InJlZCI/JzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Y29sb3I6dmFyKC0tcmVkMik7cGFkZGluZzoycHggOHB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZToxMHB4O2ZvbnQtd2VpZ2h0OjcwMCI+WUFLSU5EQTwvc3Bhbj4nOiIiOwogICAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JythYisnO2JvcmRlcjoxcHggc29saWQgJythYmQrJztib3JkZXItcmFkaXVzOjEwcHg7bWFyZ2luLWJvdHRvbToxMHB4O3BhZGRpbmc6MTRweCAxNnB4Ij4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47ZmxleC13cmFwOndyYXA7Z2FwOjhweCI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDoxMHB4Ij48c3Bhbj4nK2FpKyc8L3NwYW4+PHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OkJlYmFzIE5ldWUsc2Fucy1zZXJpZjtmb250LXNpemU6MjBweDtsZXR0ZXItc3BhY2luZzoycHg7Y29sb3I6dmFyKC0tdGV4dCkiPicrZS50aWNrZXIrJzwvc3Bhbj4nK3liKyc8L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTZweDtmbGV4LXdyYXA6d3JhcDthbGlnbi1pdGVtczpjZW50ZXIiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5SQVBPUjwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrKGUubmV4dF9kYXRlfHwi4oCUIikrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOicrKGUuYWxlcnQ9PT0icmVkIj8idmFyKC0tcmVkMikiOmUuYWxlcnQ9PT0ieWVsbG93Ij8idmFyKC0teWVsbG93KSI6InZhcigtLW11dGVkKSIpKyciPicrZHQrJzwvZGl2PjwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5FUFMgVEFITUlOPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjojNjBhNWZhIj4nKyhlLmVwc19lc3RpbWF0ZSE9bnVsbD8iJCIrZS5lcHNfZXN0aW1hdGU6IuKAlCIpKyc8L2Rpdj48L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+T1JULkhBUkVLRVQ8L2Rpdj48ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjE0cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrYW1Db2wrJyI+JythbVN0cisnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjhweDtjb2xvcjp2YXIoLS1tdXRlZCkiPnNvbiA0IHJhcG9yPC9kaXY+PC9kaXY+JzsKICAgIGgrPSc8L2Rpdj48L2Rpdj4nOwogICAgaWYoZS5oaXN0b3J5X2VwcyYmZS5oaXN0b3J5X2Vwcy5sZW5ndGgpewogICAgICBoKz0nPGRpdiBzdHlsZT0ibWFyZ2luLXRvcDo4cHg7cGFkZGluZy10b3A6OHB4O2JvcmRlci10b3A6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA2KSI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo1cHgiPlNPTiA0IFJBUE9SPC9kaXY+PGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoNCwxZnIpO2dhcDo0cHgiPic7CiAgICAgIGUuaGlzdG9yeV9lcHMuZm9yRWFjaChmdW5jdGlvbihoaCl7CiAgICAgICAgdmFyIHNjPWhoLnN1cnByaXNlX3BjdCE9bnVsbD8oaGguc3VycHJpc2VfcGN0PjA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZDIpIik6InZhcigtLW11dGVkKSI7CiAgICAgICAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjRweDtwYWRkaW5nOjZweDt0ZXh0LWFsaWduOmNlbnRlcjtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA1KSI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjhweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicraGguZGF0ZS5zdWJzdHJpbmcoMCw3KSsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMHB4Ij4nKyhoaC5hY3R1YWwhPW51bGw/IiQiK2hoLmFjdHVhbDoiPyIpKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrc2MrJyI+JysoaGguc3VycHJpc2VfcGN0IT1udWxsPyhoaC5zdXJwcmlzZV9wY3Q+MD8iKyI6IiIpK2hoLnN1cnByaXNlX3BjdCsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JzsKICAgICAgfSk7CiAgICAgIGgrPSc8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaCs9JzwvZGl2Pic7CiAgfSk7CiAgaWYobm9EYXRlLmxlbmd0aCl7aCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tdG9wOjZweCI+VGFyaWggYnVsdW5hbWF5YW46ICcrbm9EYXRlLm1hcChmdW5jdGlvbihlKXtyZXR1cm4gZS50aWNrZXI7fSkuam9pbigiLCAiKSsnPC9kaXY+Jzt9CiAgaCs9JzwvZGl2Pic7CiAgZ3JpZC5pbm5lckhUTUw9aDsKfQoKZnVuY3Rpb24gb3Blbk0odGlja2VyKXsKICB2YXIgcj1jdXJEYXRhLmZpbmQoZnVuY3Rpb24oZCl7cmV0dXJuIGQudGlja2VyPT09dGlja2VyO30pOwogIGlmKCFyfHxyLmhhdGEpIHJldHVybjsKICBpZihtQ2hhcnQpe21DaGFydC5kZXN0cm95KCk7bUNoYXJ0PW51bGw7fQogIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICB2YXIgcnJQPU1hdGgubWluKChyLnJyLzQpKjEwMCwxMDApOwogIHZhciByckM9ci5ycj49Mz8idmFyKC0tZ3JlZW4pIjpyLnJyPj0yPyJ2YXIoLS1ncmVlbjIpIjpyLnJyPj0xPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkMikiOwogIHZhciBkYz1yLmRlZ2lzaW0+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIGtjPXsiR1VDTFUgQUwiOiIjMTBiOTgxIiwiQUwiOiIjMzRkMzk5IiwiRElLS0FUTEkiOiIjZjU5ZTBiIiwiR0VDTUUiOiIjZjg3MTcxIn07CiAgdmFyIGtsYmw9eyJHVUNMVSBBTCI6IkdVQ0xVIEFMIiwiQUwiOiJBTCIsIkRJS0tBVExJIjoiRElLS0FUTEkiLCJHRUNNRSI6IkdFQ01FIn07CiAgdmFyIGVzY29sPXIuZW50cnlfc2NvcmU+PTc1PyJ2YXIoLS1ncmVlbikiOnIuZW50cnlfc2NvcmU+PTYwPyJ2YXIoLS1ncmVlbjIpIjpyLmVudHJ5X3Njb3JlPj00NT8idmFyKC0teWVsbG93KSI6ci5lbnRyeV9zY29yZT49MzA/InZhcigtLXJlZDIpIjoidmFyKC0tcmVkKSI7CiAgdmFyIHB2Y29sPXIucHJpY2VfdnNfY29sb3I9PT0iZ3JlZW4iPyJ2YXIoLS1ncmVlbikiOnIucHJpY2VfdnNfY29sb3I9PT0ieWVsbG93Ij8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZDIpIjsKCiAgdmFyIG1oPSc8ZGl2IGNsYXNzPSJtaGVhZCI+PGRpdj48ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo4cHg7ZmxleC13cmFwOndyYXAiPicKICAgICsnPHNwYW4gY2xhc3M9Im10aXRsZSIgc3R5bGU9ImNvbG9yOicrc3MudHgrJyI+JytyLnRpY2tlcisnPC9zcGFuPicKICAgICsnPHNwYW4gY2xhc3M9ImJhZGdlIiBzdHlsZT0iYmFja2dyb3VuZDonK3NzLmJnKyc7Y29sb3I6Jytzcy50eCsnO2JvcmRlcjoxcHggc29saWQgJytzcy5iZCsnO2ZvbnQtc2l6ZToxMnB4Ij4nK3NzLmxibCsnPC9zcGFuPicKICAgICsoci5wb3J0Zm9saW8/JzxzcGFuIGNsYXNzPSJwb3J0LWJhZGdlIiBzdHlsZT0iZm9udC1zaXplOjExcHg7cGFkZGluZzozcHggOHB4Ij5Qb3J0Zm9seW88L3NwYW4+JzonJykKICAgICsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtd2VpZ2h0OjYwMDttYXJnaW4tdG9wOjRweCI+JCcrci5maXlhdAogICAgKycgPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOicrZGMrJyI+Jysoci5kZWdpc2ltPj0wPyIrIjoiIikrci5kZWdpc2ltKyclPC9zcGFuPjwvZGl2PjwvZGl2PicKICAgICsnPGJ1dHRvbiBjbGFzcz0ibWNsb3NlIiBvbmNsaWNrPSJjbG9zZU0oKSI+4pyVPC9idXR0b24+PC9kaXY+JzsKCiAgbWgrPSc8ZGl2IGNsYXNzPSJtYm9keSI+PGRpdiBjbGFzcz0ibWNoYXJ0dyI+PGNhbnZhcyBpZD0ibWNoYXJ0Ij48L2NhbnZhcz48L2Rpdj4nOwoKICBtaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDttYXJnaW4tYm90dG9tOjEycHgiPicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+JytpYigiRW50cnlTY29yZSIsIkdpcmlzIEthbGl0ZXNpIikrJzwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjZweCI+JwogICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonK2VzY29sKyciPicrci5lbnRyeV9zY29yZSsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2NvbG9yOnZhcigtLW11dGVkKSI+LzEwMDwvc3Bhbj48L3NwYW4+JwogICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X2xhYmVsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJoZWlnaHQ6NnB4O2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXItcmFkaXVzOjNweDtvdmVyZmxvdzpoaWRkZW47bWFyZ2luLWJvdHRvbTo4cHgiPjxkaXYgc3R5bGU9ImhlaWdodDoxMDAlO3dpZHRoOicrci5lbnRyeV9zY29yZSsnJTtiYWNrZ3JvdW5kOicrZXNjb2wrJztib3JkZXItcmFkaXVzOjNweCI+PC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47Zm9udC1zaXplOjExcHgiPicKICAgICsnPGRpdj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj5TdSBhbmtpIGZpeWF0OiA8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOicrcHZjb2wrJztmb250LXdlaWdodDo2MDAiPicrci5wcmljZV92c19pZGVhbCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj5JZGVhbCBib2xnZTogPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbjIpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5pZGVhbF9lbnRyeV9sb3crJyAtICQnK3IuaWRlYWxfZW50cnlfaGlnaCsnPC9zcGFuPjwvZGl2PicKICAgICsnPC9kaXY+PC9kaXY+JzsKCiAgbWgrPSc8ZGl2IGNsYXNzPSJkYm94IiBzdHlsZT0iYmFja2dyb3VuZDonK3NzLmJnKyc7Ym9yZGVyLWNvbG9yOicrc3MuYmQrJzttYXJnaW4tYm90dG9tOjEycHgiPicKICAgICsnPGRpdiBjbGFzcz0iZGxibCIgc3R5bGU9ImNvbG9yOicrc3MudHgrJyI+JytpYigiUlIiLCJBbGltIEthcmFyaSBSL1IiKSsnPC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkdmVyZCIgc3R5bGU9ImNvbG9yOicrKGtjW3Iua2FyYXJdfHwidmFyKC0tbXV0ZWQpIikrJyI+Jysoa2xibFtyLmthcmFyXXx8ci5rYXJhcikrJzwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPlJpc2sgLyBPZHVsPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjonK3JyQysnO2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPjEgOiAnK3IucnIrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5IZW1lbiBHaXI8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuMik7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmVudHJ5X2FnZ3Jlc3NpdmUrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5HZXJpIENla2lsbWU8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOiM2MGE1ZmE7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmVudHJ5X21pZCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkJ1eXVrIER1emVsdG1lPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS15ZWxsb3cpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5lbnRyeV9jb25zZXJ2YXRpdmUrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5IZWRlZjwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6IzYwYTVmYTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuaGVkZWYrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5TdG9wLUxvc3M8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5zdG9wKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJycmJhciI+PGRpdiBjbGFzcz0icnJmaWxsIiBzdHlsZT0id2lkdGg6JytyclArJyU7YmFja2dyb3VuZDonK3JyQysnIj48L2Rpdj48L2Rpdj48L2Rpdj4nOwoKICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPlRla25payBBbmFsaXo8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRncmlkIiBzdHlsZT0ibWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiVHJlbmQiLCJUcmVuZCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIudHJlbmQ9PT0iWXVrc2VsZW4iPyJ2YXIoLS1ncmVlbikiOnIudHJlbmQ9PT0iRHVzZW4iPyJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+JytyLnRyZW5kKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUlNJIiwiUlNJIDE0IikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5yc2k/ci5yc2k8MzA/InZhcigtLWdyZWVuKSI6ci5yc2k+NzA/InZhcigtLXJlZCkiOiJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5yc2l8fCI/IikrKHIucnNpP3IucnNpPDMwPyIgQXNpcmkgU2F0aW0iOnIucnNpPjcwPyIgQXNpcmkgQWxpbSI6IiBOb3RyIjoiIikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJTTUE1MCIsIlNNQSA1MCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuYWJvdmU1MD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkKSIpKyciPicrKHIuYWJvdmU1MD8iVXplcmluZGUiOiJBbHRpbmRhIikrKHIuc21hNTBfZGlzdCE9bnVsbD8iICgiK3Iuc21hNTBfZGlzdCsiJSkiOiIiKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlNNQTIwMCIsIlNNQSAyMDAiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmFib3ZlMjAwPyJ2YXIoLS1ncmVlbikiOiJ2YXIoLS1yZWQpIikrJyI+Jysoci5hYm92ZTIwMD8iVXplcmluZGUiOiJBbHRpbmRhIikrKHIuc21hMjAwX2Rpc3QhPW51bGw/IiAoIityLnNtYTIwMF9kaXN0KyIlKSI6IiIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiNTJXIiwiNTJIIFBvei4iKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnc1Ml9wb3NpdGlvbjw9MzA/InZhcigtLWdyZWVuKSI6ci53NTJfcG9zaXRpb24+PTg1PyJ2YXIoLS1yZWQpIjoidmFyKC0teWVsbG93KSIpKyciPicrci53NTJfcG9zaXRpb24rJyU8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiSGFjaW0iLCJIYWNpbSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuaGFjaW09PT0iWXVrc2VrIj8idmFyKC0tZ3JlZW4pIjpyLmhhY2ltPT09IkR1c3VrIj8idmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrci5oYWNpbSsnICgnK3Iudm9sX3JhdGlvKyd4KTwvZGl2PjwvZGl2PicKICAgICsnPC9kaXY+JzsKCiAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij5UZW1lbCBBbmFsaXo8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRncmlkIiBzdHlsZT0ibWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiRm9yd2FyZFBFIiwiRm9yd2FyZCBQRSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucGVfZndkP3IucGVfZndkPDI1PyJ2YXIoLS1ncmVlbikiOnIucGVfZndkPDQwPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucGVfZndkP3IucGVfZndkLnRvRml4ZWQoMSk6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlBFRyIsIlBFRyIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucGVnP3IucGVnPDE/InZhcigtLWdyZWVuKSI6ci5wZWc8Mj8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnBlZz9yLnBlZy50b0ZpeGVkKDIpOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJFUFNHcm93dGgiLCJFUFMgQsO8ecO8bWUiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmVwc19ncm93dGg/ci5lcHNfZ3Jvd3RoPj0yMD8idmFyKC0tZ3JlZW4pIjpyLmVwc19ncm93dGg+PTA/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5lcHNfZ3Jvd3RoIT1udWxsP3IuZXBzX2dyb3d0aCsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlJldkdyb3d0aCIsIkdlbGlyIELDvHnDvG1lIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5yZXZfZ3Jvd3RoP3IucmV2X2dyb3d0aD49MTU/InZhcigtLWdyZWVuKSI6ci5yZXZfZ3Jvd3RoPj0wPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucmV2X2dyb3d0aCE9bnVsbD9yLnJldl9ncm93dGgrIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJOZXRNYXJnaW4iLCJOZXQgTWFyamluIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5uZXRfbWFyZ2luP3IubmV0X21hcmdpbj49MTU/InZhcigtLWdyZWVuKSI6ci5uZXRfbWFyZ2luPj01PyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIubmV0X21hcmdpbiE9bnVsbD9yLm5ldF9tYXJnaW4rIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJST0UiLCJST0UiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnJvZT9yLnJvZT49MTU/InZhcigtLWdyZWVuKSI6ci5yb2U+PTU/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5yb2UhPW51bGw/ci5yb2UrIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPC9kaXY+JzsKCiAgdmFyIGFpVGV4dCA9IEFJX0RBVEEgJiYgQUlfREFUQVt0aWNrZXJdOwogIGlmKGFpVGV4dCl7CiAgICBtaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7bWFyZ2luLWJvdHRvbToxMnB4Ij4nOwogICAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOiM2MGE1ZmE7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+8J+kliBBSSBBbmFsaXogKENsYXVkZSBTb25uZXQpPC9kaXY+JzsKICAgIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tdGV4dCk7bGluZS1oZWlnaHQ6MS43O3doaXRlLXNwYWNlOnByZS13cmFwIj4nK2FpVGV4dCsnPC9kaXY+JzsKICAgIG1oKz0nPC9kaXY+JzsKICB9CiAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7dGV4dC1hbGlnbjpjZW50ZXIiPkJ1IGFyYWMgeWF0aXJpbSB0YXZzaXllc2kgZGVnaWxkaXI8L2Rpdj48L2Rpdj4nOwoKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibW9kYWwiKS5pbm5lckhUTUw9bWg7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm92ZXJsYXkiKS5jbGFzc0xpc3QuYWRkKCJvcGVuIik7CiAgc2V0VGltZW91dChmdW5jdGlvbigpewogICAgdmFyIGN0eD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWNoYXJ0Iik7CiAgICBpZihjdHgmJnIuY2hhcnRfY2xvc2VzKXsKICAgICAgbUNoYXJ0PW5ldyBDaGFydChjdHgse3R5cGU6ImxpbmUiLGRhdGE6e2xhYmVsczpyLmNoYXJ0X2RhdGVzLGRhdGFzZXRzOlsKICAgICAgICB7bGFiZWw6IkZpeWF0IixkYXRhOnIuY2hhcnRfY2xvc2VzLGJvcmRlckNvbG9yOnNzLmFjLGJvcmRlcldpZHRoOjIsZmlsbDp0cnVlLGJhY2tncm91bmRDb2xvcjpzcy5hYysiMjAiLHBvaW50UmFkaXVzOjAsdGVuc2lvbjowLjN9LAogICAgICAgIHIuc21hNTA/e2xhYmVsOiJTTUE1MCIsZGF0YTpBcnJheShyLmNoYXJ0X2Nsb3Nlcy5sZW5ndGgpLmZpbGwoci5zbWE1MCksYm9yZGVyQ29sb3I6IiNmNTllMGIiLGJvcmRlcldpZHRoOjEuNSxib3JkZXJEYXNoOls1LDVdLHBvaW50UmFkaXVzOjAsZmlsbDpmYWxzZX06bnVsbCwKICAgICAgICByLnNtYTIwMD97bGFiZWw6IlNNQTIwMCIsZGF0YTpBcnJheShyLmNoYXJ0X2Nsb3Nlcy5sZW5ndGgpLmZpbGwoci5zbWEyMDApLGJvcmRlckNvbG9yOiIjOGI1Y2Y2Iixib3JkZXJXaWR0aDoxLjUsYm9yZGVyRGFzaDpbNSw1XSxwb2ludFJhZGl1czowLGZpbGw6ZmFsc2V9Om51bGwKICAgICAgXS5maWx0ZXIoQm9vbGVhbil9LG9wdGlvbnM6e3Jlc3BvbnNpdmU6dHJ1ZSxtYWludGFpbkFzcGVjdFJhdGlvOmZhbHNlLAogICAgICAgIHBsdWdpbnM6e2xlZ2VuZDp7bGFiZWxzOntjb2xvcjoiIzZiNzI4MCIsZm9udDp7c2l6ZToxMH19fX0sCiAgICAgICAgc2NhbGVzOnt4OntkaXNwbGF5OnRydWUsdGlja3M6e2NvbG9yOiIjMzc0MTUxIixtYXhUaWNrc0xpbWl0OjUsZm9udDp7c2l6ZTo5fX0sZ3JpZDp7Y29sb3I6InJnYmEoMjU1LDI1NSwyNTUsLjA0KSJ9fSwKICAgICAgICAgIHk6e2Rpc3BsYXk6dHJ1ZSx0aWNrczp7Y29sb3I6IiMzNzQxNTEiLGZvbnQ6e3NpemU6OX19LGdyaWQ6e2NvbG9yOiJyZ2JhKDI1NSwyNTUsMjU1LC4wNCkifX19fX0pOwogICAgfQogIH0sMTAwKTsKfQoKCi8vIOKUgOKUgCBHw5xOTMOcSyBSVVTEsE4g4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSACnZhciBSVVRJTl9JVEVNUyA9IHsKICBzYWJhaDogewogICAgbGFiZWw6ICLwn4yFIFNhYmFoIOKAlCBQaXlhc2EgQcOnxLFsbWFkYW4gw5ZuY2UiLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJzMSIsIHRleHQ6IkRhc2hib2FyZMSxIGHDpyDigJQgTSBrcml0ZXJpIHllxZ9pbCBtaT8gKFMmUDUwMCArIE5BU0RBUSBTTUEyMDAgw7xzdMO8bmRlKSJ9LAogICAgICB7aWQ6InMyIiwgdGV4dDoiRWFybmluZ3Mgc2VrbWVzaW5pIGtvbnRyb2wgZXQg4oCUIGJ1Z8O8bi9idSBoYWZ0YSByYXBvciB2YXIgbcSxPyJ9LAogICAgICB7aWQ6InMzIiwgdGV4dDoiVklYIDI1IGFsdMSxbmRhIG3EsT8gKFnDvGtzZWtzZSB5ZW5pIHBvemlzeW9uIGHDp21hKSJ9LAogICAgICB7aWQ6InM0IiwgdGV4dDoiw5ZuY2VraSBnw7xuZGVuIGJla2xleWVuIGFsYXJtIG1haWxpIHZhciBtxLE/In0KICAgIF0KICB9LAogIG9nbGVuOiB7CiAgICBsYWJlbDogIvCfk4ogw5bEn2xlZGVuIFNvbnJhIOKAlCBQaXlhc2EgQcOnxLFra2VuIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoibzEiLCB0ZXh0OiJQb3J0ZsO2ecO8bSBzZWttZXNpbmRlIGhpc3NlbGVyaW1lIGJhayDigJQgYmVrbGVubWVkaWsgZMO8xZ/DvMWfIHZhciBtxLE/In0sCiAgICAgIHtpZDoibzIiLCB0ZXh0OiJTdG9wIHNldml5ZXNpbmUgeWFrbGHFn2FuIGhpc3NlIHZhciBtxLE/IChLxLFybcSxesSxIGnFn2FyZXQpIn0sCiAgICAgIHtpZDoibzMiLCB0ZXh0OiJBbCBzaW55YWxpIHNla21lc2luZGUgeWVuaSBmxLFyc2F0IMOnxLFrbcSxxZ8gbcSxPyJ9LAogICAgICB7aWQ6Im80IiwgdGV4dDoiV2F0Y2hsaXN0dGVraSBoaXNzZWxlcmRlIGdpcmnFnyBrYWxpdGVzaSA2MCsgb2xhbiB2YXIgbcSxPyJ9LAogICAgICB7aWQ6Im81IiwgdGV4dDoiSGFiZXJsZXJkZSBwb3J0ZsO2ecO8bcO8IGV0a2lsZXllbiDDtm5lbWxpIGdlbGnFn21lIHZhciBtxLE/In0KICAgIF0KICB9LAogIGFrc2FtOiB7CiAgICBsYWJlbDogIvCfjJkgQWvFn2FtIOKAlCBQaXlhc2EgS2FwYW5kxLFrdGFuIFNvbnJhIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoiYTEiLCB0ZXh0OiIxSCBzaW55YWxsZXJpbmkga29udHJvbCBldCDigJQgaGFmdGFsxLFrIHRyZW5kIGRlxJ9pxZ9tacWfIG1pPyJ9LAogICAgICB7aWQ6ImEyIiwgdGV4dDoiWWFyxLFuIGnDp2luIHBvdGFuc2l5ZWwgZ2lyacWfIG5va3RhbGFyxLFuxLEgbm90IGFsIn0sCiAgICAgIHtpZDoiYTMiLCB0ZXh0OiJQb3J0ZsO2eWRla2kgaGVyIGhpc3NlbmluIHN0b3Agc2V2aXllc2luaSBnw7Z6ZGVuIGdlw6dpciJ9LAogICAgICB7aWQ6ImE0IiwgdGV4dDoiWWFyxLFuIHJhcG9yIGHDp8Sxa2xheWFjYWsgaGlzc2UgdmFyIG3EsT8gKEVhcm5pbmdzIHNla21lc2kpIn0KICAgIF0KICB9LAogIGhhZnRhbGlrOiB7CiAgICBsYWJlbDogIvCfk4UgSGFmdGFsxLFrIOKAlCBQYXphciBBa8WfYW3EsSIsCiAgICBpdGVtczogWwogICAgICB7aWQ6ImgxIiwgdGV4dDoiU3RvY2sgUm92ZXJkYSBDQU5TTElNIHNjcmVlbmVyxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDIiLCB0ZXh0OiJWQ1AgTWluZXJ2aW5pIHNjcmVlbmVyxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDMiLCB0ZXh0OiJRdWxsYW1hZ2dpZSBCcmVha291dCBzY3JlZW5lcsSxIMOnYWzEscWfdMSxciJ9LAogICAgICB7aWQ6Img0IiwgdGV4dDoiRmludml6ZGUgSW5zdGl0dXRpb25hbCBCdXlpbmcgc2NyZWVuZXLEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoNSIsIHRleHQ6IsOHYWvEscWfYW4gaGlzc2VsZXJpIGJ1bCDigJQgZW4gZ8O8w6dsw7wgYWRheWxhciJ9LAogICAgICB7aWQ6Img2IiwgdGV4dDoiR2l0SHViIEFjdGlvbnNkYW4gUnVuIFdvcmtmbG93IGJhcyDigJQgc2l0ZSBnw7xuY2VsbGVuaXIifSwKICAgICAge2lkOiJoNyIsIHRleHQ6IkdlbGVjZWsgaGFmdGFuxLFuIGVhcm5pbmdzIHRha3ZpbWluaSBrb250cm9sIGV0In0sCiAgICAgIHtpZDoiaDgiLCB0ZXh0OiJQb3J0ZsO2eSBnZW5lbCBkZcSfZXJsZW5kaXJtZXNpIOKAlCBoZWRlZmxlciBoYWxhIGdlw6dlcmxpIG1pPyJ9CiAgICBdCiAgfQp9OwoKZnVuY3Rpb24gZ2V0VG9kYXlLZXkoKXsKICByZXR1cm4gbmV3IERhdGUoKS50b0RhdGVTdHJpbmcoKTsKfQoKZnVuY3Rpb24gbG9hZENoZWNrZWQoKXsKICB0cnl7CiAgICB2YXIgZGF0YSA9IGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdydXRpbl9jaGVja2VkJyk7CiAgICBpZighZGF0YSkgcmV0dXJuIHt9OwogICAgdmFyIHBhcnNlZCA9IEpTT04ucGFyc2UoZGF0YSk7CiAgICAvLyBTYWRlY2UgYnVnw7xuw7xuIHZlcmlsZXJpbmkga3VsbGFuCiAgICBpZihwYXJzZWQuZGF0ZSAhPT0gZ2V0VG9kYXlLZXkoKSkgcmV0dXJuIHt9OwogICAgcmV0dXJuIHBhcnNlZC5pdGVtcyB8fCB7fTsKICB9Y2F0Y2goZSl7cmV0dXJuIHt9O30KfQoKZnVuY3Rpb24gc2F2ZUNoZWNrZWQoY2hlY2tlZCl7CiAgbG9jYWxTdG9yYWdlLnNldEl0ZW0oJ3J1dGluX2NoZWNrZWQnLCBKU09OLnN0cmluZ2lmeSh7CiAgICBkYXRlOiBnZXRUb2RheUtleSgpLAogICAgaXRlbXM6IGNoZWNrZWQKICB9KSk7Cn0KCmZ1bmN0aW9uIHRvZ2dsZUNoZWNrKGlkKXsKICB2YXIgY2hlY2tlZCA9IGxvYWRDaGVja2VkKCk7CiAgaWYoY2hlY2tlZFtpZF0pIGRlbGV0ZSBjaGVja2VkW2lkXTsKICBlbHNlIGNoZWNrZWRbaWRdID0gdHJ1ZTsKICBzYXZlQ2hlY2tlZChjaGVja2VkKTsKICByZW5kZXJSdXRpbigpOwp9CgpmdW5jdGlvbiByZXNldFJ1dGluKCl7CiAgbG9jYWxTdG9yYWdlLnJlbW92ZUl0ZW0oJ3J1dGluX2NoZWNrZWQnKTsKICByZW5kZXJSdXRpbigpOwp9CgoKZnVuY3Rpb24gcmVuZGVySGFmdGFsaWsoKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgdmFyIHdkID0gV0VFS0xZX0RBVEEgfHwge307CiAgdmFyIHBvcnQgPSB3ZC5wb3J0Zm9saW8gfHwgW107CiAgdmFyIHdhdGNoID0gd2Qud2F0Y2hsaXN0IHx8IFtdOwogIHZhciBiZXN0ID0gd2QuYmVzdDsKICB2YXIgd29yc3QgPSB3ZC53b3JzdDsKICB2YXIgbWQgPSBNQVJLRVRfREFUQSB8fCB7fTsKICB2YXIgc3AgPSBtZC5TUDUwMCB8fCB7fTsKICB2YXIgbmFzID0gbWQuTkFTREFRIHx8IHt9OwoKICBmdW5jdGlvbiBjaGdDb2xvcih2KXsgcmV0dXJuIHYgPj0gMCA/ICd2YXIoLS1ncmVlbiknIDogJ3ZhcigtLXJlZDIpJzsgfQogIGZ1bmN0aW9uIGNoZ1N0cih2KXsgcmV0dXJuICh2ID49IDAgPyAnKycgOiAnJykgKyB2ICsgJyUnOyB9CgogIGZ1bmN0aW9uIHBlcmZDYXJkKGl0ZW0pewogICAgdmFyIGNjID0gY2hnQ29sb3IoaXRlbS53ZWVrX2NoZyk7CiAgICB2YXIgcGIgPSBpdGVtLnBvcnRmb2xpbyA/ICc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEyKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjI1KTtwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo2MDA7bWFyZ2luLWxlZnQ6NHB4Ij5QPC9zcGFuPicgOiAnJzsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTJweDtkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206NnB4Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjZweCI+PHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OkJlYmFzIE5ldWUsc2Fucy1zZXJpZjtmb250LXNpemU6MTZweDtsZXR0ZXItc3BhY2luZzoycHgiPicgKyBpdGVtLnRpY2tlciArICc8L3NwYW4+JyArIHBiICsgJzwvZGl2PicKICAgICAgKyAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+JwogICAgICArICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjE0cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyBjYyArICciPicgKyBjaGdTdHIoaXRlbS53ZWVrX2NoZykgKyAnPC9kaXY+JwogICAgICArICc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+w5ZuY2VraTogJyArIGNoZ1N0cihpdGVtLnByZXZfd2Vla19jaGcpICsgJzwvZGl2PicKICAgICAgKyAnPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciBoID0gJzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CgogIC8vIEhlYWRlcgogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCk7bWFyZ2luLWJvdHRvbTo0cHgiPvCfk4ggSGFmdGFsxLFrIFBlcmZvcm1hbnMgw5Z6ZXRpPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicgKyAod2QuZ2VuZXJhdGVkIHx8ICcnKSArICc8L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIFBpeWFzYSB2cyBQb3J0ZsO2eQogIHZhciBzcENoZyA9IHNwLmNoYW5nZSB8fCAwOwogIHZhciBuYXNDaGcgPSBuYXMuY2hhbmdlIHx8IDA7CiAgdmFyIHBvcnRBdmcgPSBwb3J0Lmxlbmd0aCA/IE1hdGgucm91bmQocG9ydC5yZWR1Y2UoZnVuY3Rpb24oYSxiKXtyZXR1cm4gYStiLndlZWtfY2hnO30sMCkvcG9ydC5sZW5ndGgqMTAwKS8xMDAgOiAwOwogIHZhciBhbHBoYSA9IE1hdGgucm91bmQoKHBvcnRBdmcgLSBzcENoZykqMTAwKS8xMDA7CiAgdmFyIGFscGhhQ29sID0gYWxwaGEgPj0gMCA/ICd2YXIoLS1ncmVlbiknIDogJ3ZhcigtLXJlZDIpJzsKCiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgxNDBweCwxZnIpKTtnYXA6MTBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+UG9ydGbDtnkgT3J0LjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonICsgY2hnQ29sb3IocG9ydEF2ZykgKyAnIj4nICsgY2hnU3RyKHBvcnRBdmcpICsgJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+UyZQIDUwMDwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonICsgY2hnQ29sb3Ioc3BDaGcpICsgJyI+JyArIGNoZ1N0cihzcENoZykgKyAnPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5OQVNEQVE8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Y29sb3I6JyArIGNoZ0NvbG9yKG5hc0NoZykgKyAnIj4nICsgY2hnU3RyKG5hc0NoZykgKyAnPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicgKyAoYWxwaGE+PTA/J3JnYmEoMTYsMTg1LDEyOSwuMDgpJzoncmdiYSgyMzksNjgsNjgsLjA4KScpICsgJztib3JkZXI6MXB4IHNvbGlkICcgKyAoYWxwaGE+PTA/J3JnYmEoMTYsMTg1LDEyOSwuMjUpJzoncmdiYSgyMzksNjgsNjgsLjI1KScpICsgJztib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+QWxwaGEgKHZzIFMmUCk8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Y29sb3I6JyArIGFscGhhQ29sICsgJyI+JyArIChhbHBoYT49MD8nKyc6JycpICsgYWxwaGEgKyAnJTwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gRW4gaXlpIC8gZW4ga8O2dMO8CiAgaWYoYmVzdCB8fCB3b3JzdCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogICAgaWYoYmVzdCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLWdyZWVuKTttYXJnaW4tYm90dG9tOjZweCI+8J+PhiBCdSBIYWZ0YW7EsW4gRW4gxLB5aXNpPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyNHB4O2xldHRlci1zcGFjaW5nOjJweCI+JyArIGJlc3QudGlja2VyICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4rJyArIGJlc3Qud2Vla19jaGcgKyAnJTwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBpZih3b3JzdCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4Ij4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1yZWQyKTttYXJnaW4tYm90dG9tOjZweCI+8J+TiSBCdSBIYWZ0YW7EsW4gRW4gS8O2dMO8c8O8PC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyNHB4O2xldHRlci1zcGFjaW5nOjJweCI+JyArIHdvcnN0LnRpY2tlciArICc8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nICsgd29yc3Qud2Vla19jaGcgKyAnJTwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gUG9ydGbDtnkgZGV0YXkKICBpZihwb3J0Lmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5K8IFBvcnRmw7Z5PC9kaXY+JzsKICAgIHBvcnQuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsgaCArPSBwZXJmQ2FyZChpdGVtKTsgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gU2lueWFsbGVyIG96ZXRpCiAgdmFyIGJ1eUNvdW50ID0gKFRGX0RBVEFbJzFkJ118fFtdKS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J0dVQ0xVIEFMJ3x8ci5zaW55YWw9PT0nQUwnO30pLmxlbmd0aDsKICB2YXIgc2VsbENvdW50ID0gKFRGX0RBVEFbJzFkJ118fFtdKS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J1NBVCc7fSkubGVuZ3RoOwogIHZhciB3YXRjaENvdW50ID0gKFRGX0RBVEFbJzFkJ118fFtdKS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J0RJS0tBVCc7fSkubGVuZ3RoOwoKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+TiiBCdSBIYWZ0YWtpIFNpbnlhbGxlcjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2ZsZXgtd3JhcDp3cmFwIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nICsgYnV5Q291bnQgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5BbCBTaW55YWxpPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXllbGxvdykiPicgKyB3YXRjaENvdW50ICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+RGlra2F0PC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1yZWQyKSI+JyArIHNlbGxDb3VudCArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlNhdCBTaW55YWxpPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8L2Rpdj48L2Rpdj4nOwoKICAvLyBXYXRjaGxpc3QgcGVyZm9ybWFucwogIGlmKHdhdGNoLmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5GBIFdhdGNobGlzdDwvZGl2Pic7CiAgICB3YXRjaC5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0peyBoICs9IHBlcmZDYXJkKGl0ZW0pOyB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICBoICs9ICc8L2Rpdj4nOwogIHJldHVybiBoOwp9CgpmdW5jdGlvbiBidWlsZFJ1dGluSFRNTCgpewogIHZhciBjaGVja2VkID0gbG9hZENoZWNrZWQoKTsKICB2YXIgdG9kYXkgPSBuZXcgRGF0ZSgpOwogIHZhciBpc1dlZWtlbmQgPSB0b2RheS5nZXREYXkoKSA9PT0gMCB8fCB0b2RheS5nZXREYXkoKSA9PT0gNjsKICB2YXIgZGF5TmFtZSA9IFsnUGF6YXInLCdQYXphcnRlc2knLCdTYWzEsScsJ8OHYXLFn2FtYmEnLCdQZXLFn2VtYmUnLCdDdW1hJywnQ3VtYXJ0ZXNpJ11bdG9kYXkuZ2V0RGF5KCldOwogIHZhciBkYXRlU3RyID0gdG9kYXkudG9Mb2NhbGVEYXRlU3RyaW5nKCd0ci1UUicsIHtkYXk6J251bWVyaWMnLG1vbnRoOidsb25nJyx5ZWFyOidudW1lcmljJ30pOwoKICAvLyBQcm9ncmVzcyBoZXNhcGxhCiAgdmFyIHRvdGFsSXRlbXMgPSAwOwogIHZhciBkb25lSXRlbXMgPSAwOwogIHZhciBzZWN0aW9ucyA9IGlzV2Vla2VuZCA/IFsnaGFmdGFsaWsnXSA6IFsnc2FiYWgnLCdvZ2xlbicsJ2Frc2FtJ107CiAgc2VjdGlvbnMuZm9yRWFjaChmdW5jdGlvbihrKXsKICAgIFJVVElOX0lURU1TW2tdLml0ZW1zLmZvckVhY2goZnVuY3Rpb24oaXRlbSl7CiAgICAgIHRvdGFsSXRlbXMrKzsKICAgICAgaWYoY2hlY2tlZFtpdGVtLmlkXSkgZG9uZUl0ZW1zKys7CiAgICB9KTsKICB9KTsKICB2YXIgcGN0ID0gdG90YWxJdGVtcyA+IDAgPyBNYXRoLnJvdW5kKGRvbmVJdGVtcy90b3RhbEl0ZW1zKjEwMCkgOiAwOwogIHZhciBwY3RDb2wgPSBwY3Q9PT0xMDA/J3ZhcigtLWdyZWVuKSc6cGN0Pj01MD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLW11dGVkKSc7CgogIHZhciBoID0gJzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CgogIC8vIEhlYWRlcgogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO2ZsZXgtd3JhcDp3cmFwO2dhcDoxMHB4Ij4nOwogIGggKz0gJzxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpIj4nK2RheU5hbWUrJyBSdXRpbmk8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytkYXRlU3RyKyc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjI4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrcGN0Q29sKyciPicrcGN0KyclPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrZG9uZUl0ZW1zKycvJyt0b3RhbEl0ZW1zKycgdGFtYW1sYW5kxLE8L2Rpdj48L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImhlaWdodDo2cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6M3B4O292ZXJmbG93OmhpZGRlbjttYXJnaW4tdG9wOjEycHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iaGVpZ2h0OjEwMCU7d2lkdGg6JytwY3QrJyU7YmFja2dyb3VuZDonK3BjdENvbCsnO2JvcmRlci1yYWRpdXM6M3B4O3RyYW5zaXRpb246d2lkdGggLjVzIGVhc2UiPjwvZGl2PjwvZGl2Pic7CiAgaWYocGN0PT09MTAwKSBoICs9ICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlcjttYXJnaW4tdG9wOjEwcHg7Zm9udC1zaXplOjE0cHg7Y29sb3I6dmFyKC0tZ3JlZW4pIj7wn46JIFTDvG0gbWFkZGVsZXIgdGFtYW1sYW5kxLEhPC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBTZWN0aW9ucwogIHNlY3Rpb25zLmZvckVhY2goZnVuY3Rpb24oayl7CiAgICB2YXIgc2VjID0gUlVUSU5fSVRFTVNba107CiAgICB2YXIgc2VjRG9uZSA9IHNlYy5pdGVtcy5maWx0ZXIoZnVuY3Rpb24oaSl7cmV0dXJuIGNoZWNrZWRbaS5pZF07fSkubGVuZ3RoOwogICAgdmFyIHNlY1RvdGFsID0gc2VjLml0ZW1zLmxlbmd0aDsKICAgIHZhciBzZWNQY3QgPSBNYXRoLnJvdW5kKHNlY0RvbmUvc2VjVG90YWwqMTAwKTsKICAgIHZhciBzZWNDb2wgPSBzZWNQY3Q9PT0xMDA/J3ZhcigtLWdyZWVuKSc6c2VjUGN0PjA/J3ZhcigtLXllbGxvdyknOid2YXIoLS1tdXRlZCknOwoKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbToxMnB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOnZhcigtLXRleHQpIj4nK3NlYy5sYWJlbCsnPC9kaXY+JzsKICAgIGggKz0gJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjonK3NlY0NvbCsnO2ZvbnQtd2VpZ2h0OjYwMCI+JytzZWNEb25lKycvJytzZWNUb3RhbCsnPC9zcGFuPjwvZGl2Pic7CgogICAgc2VjLml0ZW1zLmZvckVhY2goZnVuY3Rpb24oaXRlbSl7CiAgICAgIHZhciBkb25lID0gISFjaGVja2VkW2l0ZW0uaWRdOwogICAgICB2YXIgYmdDb2xvciA9IGRvbmUgPyAncmdiYSgxNiwxODUsMTI5LC4wNiknIDogJ3JnYmEoMjU1LDI1NSwyNTUsLjAyKSc7CiAgICAgIHZhciBib3JkZXJDb2xvciA9IGRvbmUgPyAncmdiYSgxNiwxODUsMTI5LC4yKScgOiAncmdiYSgyNTUsMjU1LDI1NSwuMDUpJzsKICAgICAgdmFyIGNoZWNrQm9yZGVyID0gZG9uZSA/ICd2YXIoLS1ncmVlbiknIDogJ3ZhcigtLW11dGVkKSc7CiAgICAgIHZhciBjaGVja0JnID0gZG9uZSA/ICd2YXIoLS1ncmVlbiknIDogJ3RyYW5zcGFyZW50JzsKICAgICAgdmFyIHRleHRDb2xvciA9IGRvbmUgPyAndmFyKC0tbXV0ZWQpJyA6ICd2YXIoLS10ZXh0KSc7CiAgICAgIHZhciB0ZXh0RGVjbyA9IGRvbmUgPyAnbGluZS10aHJvdWdoJyA6ICdub25lJzsKICAgICAgdmFyIGNoZWNrbWFyayA9IGRvbmUgPyAnPHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiI+PHBvbHlsaW5lIHBvaW50cz0iMiw2IDUsOSAxMCwzIiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPjwvc3ZnPicgOiAnJzsKICAgICAgaCArPSAnPGRpdiBvbmNsaWNrPSJ0b2dnbGVDaGVjayhcJycgKyBpdGVtLmlkICsgJ1wnKSIgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpmbGV4LXN0YXJ0O2dhcDoxMnB4O3BhZGRpbmc6MTBweDtib3JkZXItcmFkaXVzOjhweDtjdXJzb3I6cG9pbnRlcjttYXJnaW4tYm90dG9tOjZweDtiYWNrZ3JvdW5kOicgKyBiZ0NvbG9yICsgJztib3JkZXI6MXB4IHNvbGlkICcgKyBib3JkZXJDb2xvciArICciPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZsZXgtc2hyaW5rOjA7d2lkdGg6MjBweDtoZWlnaHQ6MjBweDtib3JkZXItcmFkaXVzOjVweDtib3JkZXI6MnB4IHNvbGlkICcgKyBjaGVja0JvcmRlciArICc7YmFja2dyb3VuZDonICsgY2hlY2tCZyArICc7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO21hcmdpbi10b3A6MXB4Ij4nICsgY2hlY2ttYXJrICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTNweDtjb2xvcjonICsgdGV4dENvbG9yICsgJztsaW5lLWhlaWdodDoxLjU7dGV4dC1kZWNvcmF0aW9uOicgKyB0ZXh0RGVjbyArICciPicgKyBpdGVtLnRleHQgKyAnPC9zcGFuPic7CiAgICAgIGggKz0gJzwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfSk7CgogIC8vIEhhZnRhIGnDp2kgb2xkdcSfdW5kYSBoYWZ0YWzEsWsgYsO2bMO8bcO8IGRlIGfDtnN0ZXIgKGthdGxhbmFiaWxpcikKICBpZighaXNXZWVrZW5kKXsKICAgIHZhciBoU2VjID0gUlVUSU5fSVRFTVNbJ2hhZnRhbGlrJ107CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMDQpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4xNSk7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjojNjBhNWZhO21hcmdpbi1ib3R0b206NHB4Ij4nK2hTZWMubGFiZWwrJzwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlBhemFyIGFrxZ9hbcSxIHlhcMSxbGFjYWtsYXIg4oCUIMWfdSBhbiBnw7ZzdGVyaW0gbW9kdW5kYTwvZGl2PjwvZGl2Pic7CiAgfQoKICAvLyBSZXNldCBidXRvbnUKICBoICs9ICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlcjttYXJnaW4tdG9wOjZweCI+JzsKICBoICs9ICc8YnV0dG9uIG9uY2xpY2s9InJlc2V0UnV0aW4oKSIgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tbXV0ZWQpO3BhZGRpbmc6OHB4IDE2cHg7Ym9yZGVyLXJhZGl1czo4cHg7Zm9udC1zaXplOjEycHg7Y3Vyc29yOnBvaW50ZXIiPvCflIQgTGlzdGV5aSBTxLFmxLFybGE8L2J1dHRvbj4nOwogIGggKz0gJzwvZGl2Pic7CgogIGggKz0gJzwvZGl2Pic7CiAgcmV0dXJuIGg7Cn0KCmZ1bmN0aW9uIGNsb3NlTShlKXsKICBpZighZXx8ZS50YXJnZXQ9PT1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgib3ZlcmxheSIpKXsKICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJvdmVybGF5IikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpOwogICAgaWYobUNoYXJ0KXttQ2hhcnQuZGVzdHJveSgpO21DaGFydD1udWxsO30KICB9Cn0KCnJlbmRlclN0YXRzKCk7CnJlbmRlckRhc2hib2FyZCgpOwoKCgovLyDilIDilIAgTMSwU1RFIETDnFpFTkxFTUUg4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSACnZhciBlZGl0V2F0Y2hsaXN0ID0gW107CnZhciBlZGl0UG9ydGZvbGlvID0gW107CgpmdW5jdGlvbiBvcGVuRWRpdExpc3QoKXsKICBlZGl0V2F0Y2hsaXN0ID0gVEZfREFUQVsnMWQnXS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSkubWFwKGZ1bmN0aW9uKHIpe3JldHVybiByLnRpY2tlcjt9KTsKICBlZGl0UG9ydGZvbGlvID0gUE9SVC5zbGljZSgpOwogIHJlbmRlckVkaXRMaXN0cygpOwogIC8vIExvYWQgc2F2ZWQgdG9rZW4gZnJvbSBsb2NhbFN0b3JhZ2UKICB2YXIgc2F2ZWQgPSBsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgnZ2hfdG9rZW4nKTsKICBpZihzYXZlZCkgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdoVG9rZW5JbnB1dCIpLnZhbHVlID0gc2F2ZWQ7CiAgdmFyIHRzPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0b2tlblNlY3Rpb24iKTsgaWYodHMpIHRzLnN0eWxlLmRpc3BsYXk9Im5vbmUiOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0UG9wdXAiKS5jbGFzc0xpc3QuYWRkKCJvcGVuIik7Cn0KCgpmdW5jdGlvbiB0b2dnbGVUb2tlblNlY3Rpb24oKXsKICB2YXIgcz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidG9rZW5TZWN0aW9uIik7CiAgaWYocykgcy5zdHlsZS5kaXNwbGF5PXMuc3R5bGUuZGlzcGxheT09PSJub25lIj8iYmxvY2siOiJub25lIjsKfQoKZnVuY3Rpb24gc2F2ZVRva2VuKCl7CiAgdmFyIHQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdoVG9rZW5JbnB1dCIpLnZhbHVlLnRyaW0oKTsKICBpZighdCl7YWxlcnQoIlRva2VuIGJvcyEiKTtyZXR1cm47fQogIGxvY2FsU3RvcmFnZS5zZXRJdGVtKCJnaF90b2tlbiIsdCk7CiAgdmFyIHRzPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0b2tlblNlY3Rpb24iKTsgaWYodHMpIHRzLnN0eWxlLmRpc3BsYXk9Im5vbmUiOwogIHNldEVkaXRTdGF0dXMoIuKchSBUb2tlbiBrYXlkZWRpbGRpIiwiZ3JlZW4iKTsKfQoKZnVuY3Rpb24gY2xvc2VFZGl0UG9wdXAoZSl7CiAgaWYoIWV8fGUudGFyZ2V0PT09ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImVkaXRQb3B1cCIpKXsKICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0UG9wdXAiKS5jbGFzc0xpc3QucmVtb3ZlKCJvcGVuIik7CiAgfQp9CgpmdW5jdGlvbiByZW5kZXJFZGl0TGlzdHMoKXsKICB2YXIgd2UgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgid2F0Y2hsaXN0RWRpdG9yIik7CiAgdmFyIHBlID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInBvcnRmb2xpb0VkaXRvciIpOwogIGlmKCF3ZXx8IXBlKSByZXR1cm47CgogIHdlLmlubmVySFRNTCA9IGVkaXRXYXRjaGxpc3QubWFwKGZ1bmN0aW9uKHQsaSl7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47cGFkZGluZzo1cHggOHB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czo1cHg7bWFyZ2luLWJvdHRvbTo0cHgiPicKICAgICAgKyc8c3BhbiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMCI+Jyt0Kyc8L3NwYW4+JwogICAgICArJzxidXR0b24gY2xhc3M9InJtLXdhdGNoLWJ0biIgZGF0YS1pZHg9IicraSsnIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMTUpO2JvcmRlcjpub25lO2NvbG9yOnZhcigtLXJlZDIpO3dpZHRoOjIwcHg7aGVpZ2h0OjIwcHg7Ym9yZGVyLXJhZGl1czo0cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEycHgiPuKclTwvYnV0dG9uPicKICAgICAgKyc8L2Rpdj4nOwogIH0pLmpvaW4oJycpOwoKICAvLyBBZGQgY2xpY2sgaGFuZGxlcnMKICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7CiAgICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCcucm0td2F0Y2gtYnRuJykuZm9yRWFjaChmdW5jdGlvbihidG4pewogICAgICBidG4ub25jbGljaz1mdW5jdGlvbigpe3JlbW92ZVRpY2tlcignd2F0Y2gnLCt0aGlzLmRhdGFzZXQuaWR4KTt9OwogICAgfSk7CiAgICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCcucm0tcG9ydC1idG4nKS5mb3JFYWNoKGZ1bmN0aW9uKGJ0bil7CiAgICAgIGJ0bi5vbmNsaWNrPWZ1bmN0aW9uKCl7cmVtb3ZlVGlja2VyKCdwb3J0JywrdGhpcy5kYXRhc2V0LmlkeCk7fTsKICAgIH0pOwogIH0sMCk7CiAgcGUuaW5uZXJIVE1MID0gZWRpdFBvcnRmb2xpby5tYXAoZnVuY3Rpb24odCxpKXsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtwYWRkaW5nOjVweCA4cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjVweDttYXJnaW4tYm90dG9tOjRweCI+JwogICAgICArJzxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOnZhcigtLWdyZWVuKSI+Jyt0Kyc8L3NwYW4+JwogICAgICArJzxidXR0b24gY2xhc3M9InJtLXBvcnQtYnRuIiBkYXRhLWlkeD0iJytpKyciIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Ym9yZGVyOm5vbmU7Y29sb3I6dmFyKC0tcmVkMik7d2lkdGg6MjBweDtoZWlnaHQ6MjBweDtib3JkZXItcmFkaXVzOjRweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTJweCI+4pyVPC9idXR0b24+JwogICAgICArJzwvZGl2Pic7CiAgfSkuam9pbignJyk7Cn0KCmZ1bmN0aW9uIGFkZFRpY2tlcihsaXN0KXsKICB2YXIgaW5wdXRJZCA9IGxpc3Q9PT0nd2F0Y2gnPyJuZXdXYXRjaFRpY2tlciI6Im5ld1BvcnRUaWNrZXIiOwogIHZhciB2YWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZChpbnB1dElkKS52YWx1ZS50cmltKCkudG9VcHBlckNhc2UoKTsKICBpZighdmFsKSByZXR1cm47CiAgaWYobGlzdD09PSd3YXRjaCcgJiYgIWVkaXRXYXRjaGxpc3QuaW5jbHVkZXModmFsKSkgZWRpdFdhdGNobGlzdC5wdXNoKHZhbCk7CiAgaWYobGlzdD09PSdwb3J0JyAgJiYgIWVkaXRQb3J0Zm9saW8uaW5jbHVkZXModmFsKSkgZWRpdFBvcnRmb2xpby5wdXNoKHZhbCk7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoaW5wdXRJZCkudmFsdWUgPSAiIjsKICByZW5kZXJFZGl0TGlzdHMoKTsKfQoKZnVuY3Rpb24gcmVtb3ZlVGlja2VyKGxpc3QsIGlkeCl7CiAgaWYobGlzdD09PSd3YXRjaCcpIGVkaXRXYXRjaGxpc3Quc3BsaWNlKGlkeCwxKTsKICBlbHNlIGVkaXRQb3J0Zm9saW8uc3BsaWNlKGlkeCwxKTsKICByZW5kZXJFZGl0TGlzdHMoKTsKfQoKZnVuY3Rpb24gc2F2ZUxpc3RUb0dpdGh1YigpewogIHZhciB0b2tlbiA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaFRva2VuSW5wdXQiKS52YWx1ZS50cmltKCk7CiAgaWYoIXRva2VuKXsgc2V0RWRpdFN0YXR1cygi4p2MIFRva2VuIGdlcmVrbGkg4oCUIGt1dHV5YSBnaXIiLCJyZWQiKTsgcmV0dXJuOyB9CiAgbG9jYWxTdG9yYWdlLnNldEl0ZW0oJ2doX3Rva2VuJywgdG9rZW4pOwoKICB2YXIgY29uZmlnID0geyB3YXRjaGxpc3Q6IGVkaXRXYXRjaGxpc3QsIHBvcnRmb2xpbzogZWRpdFBvcnRmb2xpbyB9OwogIHZhciBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoY29uZmlnLCBudWxsLCAyKTsKICB2YXIgYjY0ID0gYnRvYSh1bmVzY2FwZShlbmNvZGVVUklDb21wb25lbnQoY29udGVudCkpKTsKCiAgc2V0RWRpdFN0YXR1cygi8J+SviBLYXlkZWRpbGl5b3IuLi4iLCJ5ZWxsb3ciKTsKCiAgdmFyIGFwaVVybCA9ICJodHRwczovL2FwaS5naXRodWIuY29tL3JlcG9zL2dodXJ6enovY2Fuc2xpbS9jb250ZW50cy9jb25maWcuanNvbiI7CiAgdmFyIGhlYWRlcnMgPSB7IkF1dGhvcml6YXRpb24iOiJ0b2tlbiAiK3Rva2VuLCJDb250ZW50LVR5cGUiOiJhcHBsaWNhdGlvbi9qc29uIn07CgogIC8vIEZpcnN0IGdldCBjdXJyZW50IFNIQSBpZiBleGlzdHMKICBmZXRjaChhcGlVcmwsIHtoZWFkZXJzOmhlYWRlcnN9KQogICAgLnRoZW4oZnVuY3Rpb24ocil7IHJldHVybiByLm9rID8gci5qc29uKCkgOiBudWxsOyB9KQogICAgLnRoZW4oZnVuY3Rpb24oZXhpc3RpbmcpewogICAgICB2YXIgcGF5bG9hZCA9IHsKICAgICAgICBtZXNzYWdlOiAiTGlzdGUgZ3VuY2VsbGVuZGkgIiArIG5ldyBEYXRlKCkudG9Mb2NhbGVEYXRlU3RyaW5nKCJ0ci1UUiIpLAogICAgICAgIGNvbnRlbnQ6IGI2NAogICAgICB9OwogICAgICBpZihleGlzdGluZyAmJiBleGlzdGluZy5zaGEpIHBheWxvYWQuc2hhID0gZXhpc3Rpbmcuc2hhOwoKICAgICAgcmV0dXJuIGZldGNoKGFwaVVybCwgewogICAgICAgIG1ldGhvZDoiUFVUIiwKICAgICAgICBoZWFkZXJzOmhlYWRlcnMsCiAgICAgICAgYm9keTpKU09OLnN0cmluZ2lmeShwYXlsb2FkKQogICAgICB9KTsKICAgIH0pCiAgICAudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYoci5vayB8fCByLnN0YXR1cz09PTIwMSl7CiAgICAgICAgc2V0RWRpdFN0YXR1cygi4pyFIEtheWRlZGlsZGkhIEJpciBzb25yYWtpIENvbGFiIMOnYWzEscWfdMSxcm1hc8SxbmRhIGFrdGlmIG9sdXIuIiwiZ3JlZW4iKTsKICAgICAgICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7Y2xvc2VFZGl0UG9wdXAoKTt9LDIwMDApOwogICAgICB9IGVsc2UgewogICAgICAgIHNldEVkaXRTdGF0dXMoIuKdjCBIYXRhOiAiK3Iuc3RhdHVzKyIg4oCUIFRva2VuxLEga29udHJvbCBldCIsInJlZCIpOwogICAgICB9CiAgICB9KQogICAgLmNhdGNoKGZ1bmN0aW9uKGUpeyBzZXRFZGl0U3RhdHVzKCLinYwgSGF0YTogIitlLm1lc3NhZ2UsInJlZCIpOyB9KTsKfQoKZnVuY3Rpb24gc2V0RWRpdFN0YXR1cyhtc2csIGNvbG9yKXsKICB2YXIgZWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFN0YXR1cyIpOwogIGlmKGVsKXsKICAgIGVsLnRleHRDb250ZW50ID0gbXNnOwogICAgZWwuc3R5bGUuY29sb3IgPSBjb2xvcj09PSJncmVlbiI/InZhcigtLWdyZWVuKSI6Y29sb3I9PT0icmVkIj8idmFyKC0tcmVkMikiOiJ2YXIoLS15ZWxsb3cpIjsKICB9Cn0KCgpmdW5jdGlvbiByZW5kZXJIYWZ0YWxpaygpewogIHZhciBncmlkID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dyaWQnKTsKICB2YXIgd2QgPSBXRUVLTFlfREFUQSB8fCB7fTsKICB2YXIgcG9ydCA9IHdkLnBvcnRmb2xpbyB8fCBbXTsKICB2YXIgd2F0Y2ggPSB3ZC53YXRjaGxpc3QgfHwgW107CiAgdmFyIGJlc3QgPSB3ZC5iZXN0OwogIHZhciB3b3JzdCA9IHdkLndvcnN0OwogIHZhciBtZCA9IE1BUktFVF9EQVRBIHx8IHt9OwogIHZhciBzcCA9IG1kLlNQNTAwIHx8IHt9OwogIHZhciBuYXMgPSBtZC5OQVNEQVEgfHwge307CiAgdmFyIGRhdGExZCA9IFRGX0RBVEFbJzFkJ10gfHwgW107CiAgdmFyIGRhdGExdyA9IFRGX0RBVEFbJzF3ayddIHx8IFtdOwoKICBmdW5jdGlvbiBjYyh2KXsgcmV0dXJuIHY+PTA/J3ZhcigtLWdyZWVuMiknOid2YXIoLS1yZWQyKSc7IH0KICBmdW5jdGlvbiBjcyh2KXsgcmV0dXJuICh2Pj0wPycrJzonJykrdisnJSc7IH0KCiAgZnVuY3Rpb24gcGVyZlJvdyhpdGVtKXsKICAgIHZhciBjb2wgPSBjYyhpdGVtLndlZWtfY2hnKTsKICAgIHZhciBwYiA9IGl0ZW0ucG9ydGZvbGlvID8gJzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWxlZnQ6NHB4Ij5QPC9zcGFuPicgOiAnJzsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCI+JwogICAgICArICc8ZGl2IHN0eWxlPSJmb250LXdlaWdodDo3MDA7Zm9udC1zaXplOjE0cHg7bGV0dGVyLXNwYWNpbmc6MXB4Ij4nICsgaXRlbS50aWNrZXIgKyBwYiArICc8L2Rpdj4nCiAgICAgICsgJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPicKICAgICAgKyAnPGRpdiBzdHlsZT0iZm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyBjb2wgKyAnIj4nICsgY3MoaXRlbS53ZWVrX2NoZykgKyAnPC9kaXY+JwogICAgICArICc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+T25jZWtpOiAnICsgY3MoaXRlbS5wcmV2X3dlZWtfY2hnKSArICc8L2Rpdj4nCiAgICAgICsgJzwvZGl2PjwvZGl2Pic7CiAgfQoKICB2YXIgcG9ydEF2ZyA9IHBvcnQubGVuZ3RoID8gTWF0aC5yb3VuZChwb3J0LnJlZHVjZShmdW5jdGlvbihhLGIpe3JldHVybiBhK2Iud2Vla19jaGc7fSwwKS9wb3J0Lmxlbmd0aCoxMDApLzEwMCA6IDA7CiAgdmFyIHNwQ2hnID0gc3AuY2hhbmdlIHx8IDA7CiAgdmFyIG5hc0NoZyA9IG5hcy5jaGFuZ2UgfHwgMDsKICB2YXIgYWxwaGEgPSBNYXRoLnJvdW5kKChwb3J0QXZnLXNwQ2hnKSoxMDApLzEwMDsKICB2YXIgYWxwaGFDb2wgPSBhbHBoYT49MD8ndmFyKC0tZ3JlZW4pJzondmFyKC0tcmVkMiknOwoKICB2YXIgaCA9ICc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwoKICAvLyBIZWFkZXIKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1ib3R0b206NHB4Ij7wn5OIIEhhZnRhbMSxayBQZXJmb3JtYW5zIMOWemV0aTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nICsgKHdkLmdlbmVyYXRlZHx8JycpICsgJzwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gUGl5YXNhIHZzIFBvcnRmb2x5bwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMTMwcHgsMWZyKSk7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIFsKICAgIHtsYWJlbDonUG9ydGbDtnkgT3J0LicsIHZhbDpwb3J0QXZnfSwKICAgIHtsYWJlbDonUyZQIDUwMCcsIHZhbDpzcENoZ30sCiAgICB7bGFiZWw6J05BU0RBUScsIHZhbDpuYXNDaGd9LAogIF0uZm9yRWFjaChmdW5jdGlvbih4KXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+JyArIHgubGFiZWwgKyAnPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgY2MoeC52YWwpICsgJyI+JyArIGNzKHgudmFsKSArICc8L2Rpdj48L2Rpdj4nOwogIH0pOwogIHZhciBhQmcgPSBhbHBoYT49MD8ncmdiYSgxNiwxODUsMTI5LC4wOCknOidyZ2JhKDIzOSw2OCw2OCwuMDgpJzsKICB2YXIgYUJkID0gYWxwaGE+PTA/J3JnYmEoMTYsMTg1LDEyOSwuMjUpJzoncmdiYSgyMzksNjgsNjgsLjI1KSc7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonICsgYUJnICsgJztib3JkZXI6MXB4IHNvbGlkICcgKyBhQmQgKyAnO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5BbHBoYSAodnMgUyZQKTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyBhbHBoYUNvbCArICciPicgKyBjcyhhbHBoYSkgKyAnPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBFbiBpeWkgLyBlbiBrb3R1CiAgaWYoYmVzdHx8d29yc3QpewogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnIgMWZyO2dhcDoxMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICAgIGlmKGJlc3QpewogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4Ij4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1ncmVlbik7bWFyZ2luLWJvdHRvbTo2cHgiPvCfj4YgRW4gxLB5aTwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtsZXR0ZXItc3BhY2luZzoycHgiPicgKyBiZXN0LnRpY2tlciArICc8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4rJyArIGJlc3Qud2Vla19jaGcgKyAnJTwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBpZih3b3JzdCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4Ij4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1yZWQyKTttYXJnaW4tYm90dG9tOjZweCI+8J+TiSBFbiBLw7Z0w7w8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nICsgd29yc3QudGlja2VyICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1yZWQyKSI+JyArIHdvcnN0LndlZWtfY2hnICsgJyU8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFNpbnlhbGxlcgogIHZhciBidXlDICA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J0dVQ0xVIEFMJ3x8ci5zaW55YWw9PT0nQUwnO30pLmxlbmd0aDsKICB2YXIgd2FybkMgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdESUtLQVQnO30pLmxlbmd0aDsKICB2YXIgc2VsbEMgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSdTQVQnO30pLmxlbmd0aDsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+TiiBTaW55YWxsZXI8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+JyArIGJ1eUMgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5BbDwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjQ1LDE1OCwxMSwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS15ZWxsb3cpIj4nICsgd2FybkMgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5EaWtrYXQ8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nICsgc2VsbEMgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5TYXQ8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzwvZGl2PjwvZGl2Pic7CgogIC8vIDFHKzFIIG1vbWVudHVtCiAgdmFyIGJvdGhCdXkgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpewogICAgaWYoci5oYXRhKSByZXR1cm4gZmFsc2U7CiAgICB2YXIgdyA9IGRhdGExdy5maW5kKGZ1bmN0aW9uKHgpe3JldHVybiB4LnRpY2tlcj09PXIudGlja2VyO30pOwogICAgcmV0dXJuIChyLnNpbnlhbD09PSdHVUNMVSBBTCd8fHIuc2lueWFsPT09J0FMJykgJiYgdyAmJiAody5zaW55YWw9PT0nR1VDTFUgQUwnfHx3LnNpbnlhbD09PSdBTCcpOwogIH0pOwogIGlmKGJvdGhCdXkubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tZ3JlZW4pO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7imqEgMUcgKyAxSCBBbCBTaW55YWxpPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtmbGV4LXdyYXA6d3JhcDtnYXA6OHB4IiBpZD0iYm90aEJ1eUNvbnRhaW5lciI+PC9kaXY+PC9kaXY+JzsKICB9CgogIC8vIFRvcCAzIGVudHJ5IHNjb3JlCiAgdmFyIHRvcEVudHJ5ID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KS5zb3J0KGZ1bmN0aW9uKGEsYil7cmV0dXJuIGIuZW50cnlfc2NvcmUtYS5lbnRyeV9zY29yZTt9KS5zbGljZSgwLDMpOwogIGlmKHRvcEVudHJ5Lmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn46vIEVuIMSweWkgR2lyacWfIEthbGl0ZXNpPC9kaXY+JzsKICAgIHZhciBtZWRhbHMgPSBbJ/CfpYcnLCfwn6WIJywn8J+liSddOwogICAgdG9wRW50cnkuZm9yRWFjaChmdW5jdGlvbihyLGkpewogICAgICB2YXIgZXNjb2wgPSByLmVudHJ5X3Njb3JlPj03NT8ndmFyKC0tZ3JlZW4pJzpyLmVudHJ5X3Njb3JlPj02MD8ndmFyKC0tZ3JlZW4yKSc6J3ZhcigtLXllbGxvdyknOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO3BhZGRpbmc6OHB4IDEycHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6OHB4O21hcmdpbi1ib3R0b206NXB4IiBpZD0idGUtJyArIHIudGlja2VyICsgJyI+JzsKICAgICAgaCArPSAnPHNwYW4+JyArIG1lZGFsc1tpXSArICcgPHN0cm9uZz4nICsgci50aWNrZXIgKyAnPC9zdHJvbmc+IDxzcGFuIHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicgKyByLnNpbnlhbCArICc8L3NwYW4+PC9zcGFuPic7CiAgICAgIGggKz0gJzxzcGFuIHN0eWxlPSJmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGVzY29sICsgJyI+JyArIHIuZW50cnlfc2NvcmUgKyAnLzEwMDwvc3Bhbj48L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gU3RvcCB5YWtpbgogIHZhciBuZWFyU3RvcCA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7CiAgICBpZihyLmhhdGF8fCFQT1JULmluY2x1ZGVzKHIudGlja2VyKXx8IXIuc3RvcCkgcmV0dXJuIGZhbHNlOwogICAgcmV0dXJuIChyLmZpeWF0LXIuc3RvcCkvci5maXlhdCoxMDAgPCA4OwogIH0pLnNvcnQoZnVuY3Rpb24oYSxiKXtyZXR1cm4gKGEuZml5YXQtYS5zdG9wKS9hLmZpeWF0LShiLmZpeWF0LWIuc3RvcCkvYi5maXlhdDt9KTsKICBpZihuZWFyU3RvcC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tcmVkMik7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPuKaoO+4jyBTdG9wIFNldml5ZXNpbmUgWWFrxLFuPC9kaXY+JzsKICAgIG5lYXJTdG9wLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICAgIHZhciBkaXN0ID0gTWF0aC5yb3VuZCgoci5maXlhdC1yLnN0b3ApL3IuZml5YXQqMTAwMCkvMTA7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7cGFkZGluZzo4cHggMTJweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo4cHg7bWFyZ2luLWJvdHRvbTo1cHgiIGlkPSJucy0nICsgci50aWNrZXIgKyAnIj4nOwogICAgICBoICs9ICc8c3Ryb25nPicgKyByLnRpY2tlciArICc8L3N0cm9uZz4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij48ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjp2YXIoLS1yZWQyKTtmb250LXdlaWdodDo2MDAiPlN0b3AgJCcgKyByLnN0b3AgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5VemFrbMSxazogJScgKyBkaXN0ICsgJzwvZGl2PjwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBIZWRlZmUgeWFraW4KICB2YXIgbmVhclRhcmdldCA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7CiAgICBpZihyLmhhdGF8fCFQT1JULmluY2x1ZGVzKHIudGlja2VyKXx8IXIuaGVkZWYpIHJldHVybiBmYWxzZTsKICAgIHJldHVybiAoci5oZWRlZi1yLmZpeWF0KS9yLmZpeWF0KjEwMCA8IDE1OwogIH0pLnNvcnQoZnVuY3Rpb24oYSxiKXtyZXR1cm4gKGEuaGVkZWYtYS5maXlhdCkvYS5maXlhdC0oYi5oZWRlZi1iLmZpeWF0KS9iLmZpeWF0O30pOwogIGlmKG5lYXJUYXJnZXQubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6IzYwYTVmYTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+OryBIZWRlZmUgWWFrxLFuPC9kaXY+JzsKICAgIG5lYXJUYXJnZXQuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgICAgdmFyIGRpc3QgPSBNYXRoLnJvdW5kKChyLmhlZGVmLXIuZml5YXQpL3IuZml5YXQqMTAwMCkvMTA7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7cGFkZGluZzo4cHggMTJweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo4cHg7bWFyZ2luLWJvdHRvbTo1cHgiPic7CiAgICAgIGggKz0gJzxzdHJvbmc+JyArIHIudGlja2VyICsgJzwvc3Ryb25nPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOiM2MGE1ZmE7Zm9udC13ZWlnaHQ6NjAwIj5IZWRlZiAkJyArIHIuaGVkZWYgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5LYWxkaTogJScgKyBkaXN0ICsgJzwvZGl2PjwvZGl2PjwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBFYXJuaW5ncwogIHZhciB1cmdlbnRFID0gRUFSTklOR1NfREFUQS5maWx0ZXIoZnVuY3Rpb24oZSl7cmV0dXJuIGUuZGF5c190b19lYXJuaW5ncyE9bnVsbCYmZS5kYXlzX3RvX2Vhcm5pbmdzPD0xNDt9KS5zb3J0KGZ1bmN0aW9uKGEsYil7cmV0dXJuIGEuZGF5c190b19lYXJuaW5ncy1iLmRheXNfdG9fZWFybmluZ3M7fSk7CiAgaWYodXJnZW50RS5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjQ1LDE1OCwxMSwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS15ZWxsb3cpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5OFIFlha2xhxZ9hbiBSYXBvcmxhcjwvZGl2Pic7CiAgICB1cmdlbnRFLmZvckVhY2goZnVuY3Rpb24oZSl7CiAgICAgIHZhciBpYyA9IGUuYWxlcnQ9PT0ncmVkJz8n8J+UtCc6J/Cfn6EnOwogICAgICB2YXIgaW5Qb3J0ID0gUE9SVC5pbmNsdWRlcyhlLnRpY2tlcik7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7cGFkZGluZzo4cHggMTJweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo4cHg7bWFyZ2luLWJvdHRvbTo1cHgiPic7CiAgICAgIGggKz0gJzxzcGFuPicgKyBpYyArICcgPHN0cm9uZz4nICsgZS50aWNrZXIgKyAnPC9zdHJvbmc+JyArIChpblBvcnQ/JyA8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZToxMHB4Ij5QPC9zcGFuPic6JycpICsgJzwvc3Bhbj4nOwogICAgICBoICs9ICc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtc2l6ZToxMXB4Ij4nICsgZS5uZXh0X2RhdGUgKyAnICgnICsgZS5kYXlzX3RvX2Vhcm5pbmdzICsgJyBnw7xuKTwvc3Bhbj48L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gVklYCiAgdmFyIHZpeCA9IG1kLlZJWCB8fCB7fTsKICBpZih2aXgucHJpY2UpewogICAgdmFyIHZDb2wgPSB2aXgucHJpY2U+MzA/J3ZhcigtLXJlZDIpJzp2aXgucHJpY2U+MjA/J3ZhcigtLXllbGxvdyknOid2YXIoLS1ncmVlbiknOwogICAgdmFyIHZMYmwgPSB2aXgucHJpY2U+MzA/J1nDvGtzZWsgS29ya3Ug4oCUIFllbmkgcG96aXN5b24gYcOnbWEnOnZpeC5wcmljZT4yMD8nT3J0YSBWb2xhdGlsaXRlIOKAlCBEaWtrYXRsaSBvbCc6J0TDvMWfw7xrIFZvbGF0aWxpdGUg4oCUIE5vcm1hbCBrb8WfdWxsYXInOwogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNHB4IDE2cHg7bWFyZ2luLWJvdHRvbToxMHB4O2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXIiPic7CiAgICBoICs9ICc8ZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjJweCI+VklYPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6JyArIHZDb2wgKyAnIj4nICsgdkxibCArICc8L2Rpdj48L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjI4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyB2Q29sICsgJyI+JyArIHZpeC5wcmljZSArICc8L2Rpdj48L2Rpdj4nOwogIH0KCiAgLy8gUG9ydGZvbHlvIGRldGF5CiAgaWYocG9ydC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+SvCBQb3J0ZsO2eTwvZGl2Pic7CiAgICBwb3J0LmZvckVhY2goZnVuY3Rpb24oaXRlbSl7aCArPSBwZXJmUm93KGl0ZW0pO30pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIFdhdGNobGlzdAogIGlmKHdhdGNoLmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5GBIFdhdGNobGlzdDwvZGl2Pic7CiAgICB3YXRjaC5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0pe2ggKz0gcGVyZlJvdyhpdGVtKTt9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICBoICs9ICc8L2Rpdj4nOwogIGdyaWQuaW5uZXJIVE1MID0gaDsKCiAgLy8gQWRkIG9uY2xpY2sgdmlhIEpTIChhdm9pZHMgcXVvdGUgbmVzdGluZyBpc3N1ZXMpCiAgYm90aEJ1eS5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgdmFyIGNudCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdib3RoQnV5Q29udGFpbmVyJyk7CiAgICBpZighY250KSByZXR1cm47CiAgICB2YXIgZCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgZC5zdHlsZS5jc3NUZXh0ID0gJ2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMyk7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzo4cHggMTRweDtjdXJzb3I6cG9pbnRlcic7CiAgICBkLmlubmVySFRNTCA9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6MnB4O2NvbG9yOnZhcigtLWdyZWVuKSI+JyArIHIudGlja2VyICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+R2lyaXM6ICcgKyByLmVudHJ5X3Njb3JlICsgJy8xMDA8L2Rpdj4nOwogICAgZC5vbmNsaWNrID0gKGZ1bmN0aW9uKHQpe3JldHVybiBmdW5jdGlvbigpe29wZW5NKHQpO307fSkoci50aWNrZXIpOwogICAgY250LmFwcGVuZENoaWxkKGQpOwogIH0pOwogIHRvcEVudHJ5LmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgZWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgndGUtJyArIHIudGlja2VyKTsKICAgIGlmKGVsKSBlbC5vbmNsaWNrID0gKGZ1bmN0aW9uKHQpe3JldHVybiBmdW5jdGlvbigpe29wZW5NKHQpO307fSkoci50aWNrZXIpLCBlbC5zdHlsZS5jdXJzb3I9J3BvaW50ZXInOwogIH0pOwogIG5lYXJTdG9wLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgZWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnbnMtJyArIHIudGlja2VyKTsKICAgIGlmKGVsKSBlbC5vbmNsaWNrID0gKGZ1bmN0aW9uKHQpe3JldHVybiBmdW5jdGlvbigpe29wZW5NKHQpO307fSkoci50aWNrZXIpLCBlbC5zdHlsZS5jdXJzb3I9J3BvaW50ZXInOwogIH0pOwp9CgoKZnVuY3Rpb24gcmVuZGVyU2NyZWVuZXIoKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgdmFyIGRhdGEgPSBTQ1JFRU5FUl9EQVRBIHx8IFtdOwogIHZhciBjcml0ZXJpYSA9IFsKICAgIHtpZDonZXBzX3FvcScsICAgIGxhYmVsOidFUFMgUW9RIELDvHnDvG1lJywgICAgIGxpbWl0Oic+PTIwJScsICAgIHc6MywgaW1wOidjcml0aWNhbCd9LAogICAge2lkOidzbWEyMDAnLCAgICAgbGFiZWw6J1NNQTIwMCDDnHplcmluZGUnLCAgICAgbGltaXQ6J1A+U01BMjAwJywgdzozLCBpbXA6J2NyaXRpY2FsJ30sCiAgICB7aWQ6J21hcmtldCcsICAgICBsYWJlbDonTSBLcml0ZXJpJywgICAgICAgICAgIGxpbWl0OidHw7zDp2zDvCcsICAgIHc6MywgaW1wOidjcml0aWNhbCd9LAogICAge2lkOidlcHNfYWNjZWwnLCAgbGFiZWw6J0VQUyBIxLF6bGFubWFzxLEnLCAgICAgIGxpbWl0OidIxLF6bGFuxLF5b3InLHc6MiwgaW1wOidpbXBvcnRhbnQnfSwKICAgIHtpZDoncnNfcmF0aW5nJywgIGxhYmVsOidSUyBSYXRpbmcnLCAgICAgICAgICAgbGltaXQ6Jz49NzAnLCAgICAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOidyZXZfZ3Jvd3RoJywgbGFiZWw6J0dlbGlyIELDvHnDvG1lc2knLCAgICAgIGxpbWl0Oic+PTE1JScsICAgIHc6MiwgaW1wOidpbXBvcnRhbnQnfSwKICAgIHtpZDoncm9lJywgICAgICAgIGxhYmVsOidST0UnLCAgICAgICAgICAgICAgICAgbGltaXQ6Jz49MTUlJywgICAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOidncm9zc19tZycsICAgbGFiZWw6J0Jyw7x0IE1hcmppbicsICAgICAgICAgbGltaXQ6Jz49NDAlJywgICAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOidzbWE1MCcsICAgICAgbGFiZWw6J1NNQTUwIMOcemVyaW5kZScsICAgICAgbGltaXQ6J1A+U01BNTAnLCAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOic1MncnLCAgICAgICAgbGFiZWw6JzUySCBZYWvEsW5sxLFrJywgICAgICAgIGxpbWl0Oic+PTc1JScsICAgIHc6MiwgaW1wOidpbXBvcnRhbnQnfSwKICAgIHtpZDonbmV0X21nJywgICAgIGxhYmVsOidOZXQgTWFyamluJywgICAgICAgICAgbGltaXQ6Jz49MTAlJywgICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDonZGUnLCAgICAgICAgIGxhYmVsOidCb3LDpy/DlnprYXluYWsnLCAgICAgICBsaW1pdDonPD0xLjAnLCAgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidjcicsICAgICAgICAgbGFiZWw6J0N1cnJlbnQgUmF0aW8nLCAgICAgICBsaW1pdDonPj0xLjUnLCAgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidwZScsICAgICAgICAgbGFiZWw6J1AvRScsICAgICAgICAgICAgICAgICBsaW1pdDonPD02MCcsICAgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidta3RjYXAnLCAgICAgbGFiZWw6J1BpeWFzYSBEZcSfZXJpJywgICAgICAgbGltaXQ6Jz49MUInLCAgICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDoncmVsX3ZvbCcsICAgIGxhYmVsOidHw7ZyZWNlbGkgSGFjaW0nLCAgICAgIGxpbWl0Oic+PTAuOHgnLCAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J2F2Z192b2wnLCAgICBsYWJlbDonT3J0LiBIYWNpbScsICAgICAgICAgIGxpbWl0Oic+PTUwMEsnLCAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J2luc3Rfb3duJywgICBsYWJlbDonS3VydW1zYWwgU2FoaXBsaWsnLCAgIGxpbWl0Oic+PTQwJScsICAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J2luc3RfdHJlbmQnLCBsYWJlbDonS3VydW1zYWwgVHJlbmQnLCAgICAgIGxpbWl0OidBcnTEsXlvcicsICB3OjEsIGltcDonc3VwcG9ydCd9LAogIF07CiAgdmFyIE1BWF9XID0gMzU7CgogIGlmKCFkYXRhLmxlbmd0aCl7CiAgICBncmlkLmlubmVySFRNTD0nPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMTt0ZXh0LWFsaWduOmNlbnRlcjtwYWRkaW5nOjQwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5TY3JlZW5lciB2ZXJpc2kgeW9rIOKAlCBBY3Rpb25zIFJ1biBXb3JrZmxvdzwvZGl2Pic7CiAgICByZXR1cm47CiAgfQoKICB2YXIgcGFzc2VkID0gZGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIucGFzc2VkO30pOwogIHZhciBmYWlsZWQgPSBkYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIucGFzc2VkO30pOwogIHZhciBbZXhwYW5kZWRUaWNrZXIsIHNldEV4cGFuZGVkXSA9IFtudWxsLCBudWxsXTsKCiAgZnVuY3Rpb24gaW1wQ29sb3IoaW1wKXsKICAgIHJldHVybiBpbXA9PT0nY3JpdGljYWwnPyd2YXIoLS1yZWQyKSc6aW1wPT09J2ltcG9ydGFudCc/J3ZhcigtLXllbGxvdyknOid2YXIoLS1tdXRlZCknOwogIH0KICBmdW5jdGlvbiBpbXBMYWJlbChpbXApewogICAgcmV0dXJuIGltcD09PSdjcml0aWNhbCc/J/CflLQgWk9SVU5MVSc6aW1wPT09J2ltcG9ydGFudCc/J/Cfn6Egw5ZORU1MxLAnOifwn5S1IERFU1RFSyc7CiAgfQoKICBmdW5jdGlvbiBjcml0ZXJpYURldGFpbChyKXsKICAgIHZhciBoID0gJzxkaXYgc3R5bGU9InBhZGRpbmc6MTJweCAxNHB4O2JvcmRlci10b3A6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA2KTtiYWNrZ3JvdW5kOnZhcigtLWJnMykiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij5LUsSwVEVSIERFVEFZSSDigJQgQcSfxLFybMSxa2zEsSBTa29yOiAnK3Iud2VpZ2h0ZWRfc2NvcmUrJy8nK3IubWF4X3dlaWdodGVkKycgKCUnK3IucGN0KycpPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6MWZyIDFmcjtnYXA6NHB4Ij4nOwogICAgY3JpdGVyaWEuZm9yRWFjaChmdW5jdGlvbihjKXsKICAgICAgdmFyIGNyID0gci5jcml0ZXJpYSAmJiByLmNyaXRlcmlhW2MuaWRdOwogICAgICBpZighY3IpIHJldHVybjsKICAgICAgdmFyIG5vRGF0YSA9IGNyLmhhc19kYXRhID09PSBmYWxzZTsKICAgICAgdmFyIGNvbCA9IG5vRGF0YSA/ICd2YXIoLS1tdXRlZCknIDogY3IucGFzc2VkID8gJ3ZhcigtLWdyZWVuKScgOiBpbXBDb2xvcihjLmltcCk7CiAgICAgIHZhciBiZyA9IG5vRGF0YSA/ICdyZ2JhKDI1NSwyNTUsMjU1LC4wMiknIDogY3IucGFzc2VkID8gJ3JnYmEoMTYsMTg1LDEyOSwuMDYpJyA6IChjLmltcD09PSdjcml0aWNhbCc/J3JnYmEoMjM5LDY4LDY4LC4wOCknOmMuaW1wPT09J2ltcG9ydGFudCc/J3JnYmEoMjQ1LDE1OCwxMSwuMDYpJzoncmdiYSgyNTUsMjU1LDI1NSwuMDIpJyk7CiAgICAgIHZhciBiZCA9IG5vRGF0YSA/ICdyZ2JhKDI1NSwyNTUsMjU1LC4wNSknIDogY3IucGFzc2VkID8gJ3JnYmEoMTYsMTg1LDEyOSwuMiknIDogKGMuaW1wPT09J2NyaXRpY2FsJz8ncmdiYSgyMzksNjgsNjgsLjIpJzpjLmltcD09PSdpbXBvcnRhbnQnPydyZ2JhKDI0NSwxNTgsMTEsLjIpJzoncmdiYSgyNTUsMjU1LDI1NSwuMDUpJyk7CiAgICAgIHZhciBpY29uID0gbm9EYXRhID8gJ+KsnCcgOiBjci5wYXNzZWQgPyAn4pyFJyA6ICfinYwnOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicrYmcrJztib3JkZXI6MXB4IHNvbGlkICcrYmQrJztib3JkZXItcmFkaXVzOjVweDtwYWRkaW5nOjVweCA4cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXIiPic7CiAgICAgIGggKz0gJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrY29sKyciPicraWNvbisnICcrYy5sYWJlbCsnPC9zcGFuPic7CiAgICAgIGggKz0gJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytpbXBMYWJlbChjLmltcCkuc3BsaXQoJyAnKVswXSsnPC9zcGFuPjwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjonKyhub0RhdGE/J3ZhcigtLW11dGVkKSc6Y3IucGFzc2VkPyd2YXIoLS10ZXh0KSc6Y29sKSsnIj4nK2NyLnZhbCsnIDxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtmb250LXdlaWdodDo0MDAiPicrKCFub0RhdGE/J2xpbWl0OiAnOicnKStjLmxpbWl0Kyc8L3NwYW4+PC9kaXY+JzsKICAgICAgaCArPSAnPC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+PC9kaXY+JzsKICAgIHJldHVybiBoOwogIH0KCiAgZnVuY3Rpb24gc3RvY2tSb3cociwgZXhwYW5kZWQpewogICAgdmFyIHBjdCA9IHIucGN0OwogICAgdmFyIGNvbCA9IHBjdD49ODA/J3ZhcigtLWdyZWVuKSc6cGN0Pj02MD8ndmFyKC0tZ3JlZW4yKSc6cGN0Pj00MD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLXJlZDIpJzsKICAgIHZhciBwYiA9IHIuaW5fcG9ydGZvbGlvPyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1sZWZ0OjRweCI+UDwvc3Bhbj4nOicnOwogICAgdmFyIHdiID0gci5pbl93YXRjaGxpc3Q/JzxzcGFuIHN0eWxlPSJjb2xvcjojNjBhNWZhO2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1sZWZ0OjRweCI+Vzwvc3Bhbj4nOicnOwogICAgdmFyIGNoZ0NvbCA9IHIuY2hhbmdlPj0wPyd2YXIoLS1ncmVlbjIpJzondmFyKC0tcmVkMiknOwogICAgdmFyIGNyaXRGYWlsID0gY3JpdGVyaWEuZmlsdGVyKGZ1bmN0aW9uKGMpe3JldHVybiByLmNyaXRlcmlhJiZyLmNyaXRlcmlhW2MuaWRdJiYhci5jcml0ZXJpYVtjLmlkXS5wYXNzZWQmJmMuaW1wPT09J2NyaXRpY2FsJzt9KTsKICAgIHZhciB3YXJuVGFncyA9IGNyaXRGYWlsLm1hcChmdW5jdGlvbihjKXsKICAgICAgcmV0dXJuICc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMSk7Y29sb3I6dmFyKC0tcmVkMik7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7bWFyZ2luLXJpZ2h0OjNweCI+4p2MJytjLmxhYmVsKyc8L3NwYW4+JzsKICAgIH0pLmpvaW4oJycpOwogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJib3JkZXItYm90dG9tOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNCkiIGlkPSJzYy1yb3ctJytyLnRpY2tlcisnIj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoxMzBweCAxZnIgODBweCA4MHB4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6MTBweDtwYWRkaW5nOjEwcHggMTRweDtjdXJzb3I6cG9pbnRlciIgaWQ9InNjLScrci50aWNrZXIrJyI+JwogICAgICArJzxkaXY+PGRpdiBzdHlsZT0iZm9udC13ZWlnaHQ6NzAwO2ZvbnQtc2l6ZToxNHB4O2xldHRlci1zcGFjaW5nOjFweCI+JytyLnRpY2tlcitwYit3YisnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK3IubmFtZS5zdWJzdHJpbmcoMCwxOCkrJzwvZGl2PjwvZGl2PicKICAgICAgKyc8ZGl2PjxkaXYgc3R5bGU9ImhlaWdodDo0cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6MnB4O292ZXJmbG93OmhpZGRlbiI+JwogICAgICArJzxkaXYgc3R5bGU9ImhlaWdodDoxMDAlO3dpZHRoOicrcGN0KyclO2JhY2tncm91bmQ6Jytjb2wrJztib3JkZXItcmFkaXVzOjJweCI+PC9kaXY+PC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjRweDttYXJnaW4tdG9wOjNweCI+Jyt3YXJuVGFncwogICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytyLnNjb3JlKycvMTk8L3NwYW4+JwogICAgICArJzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMTUpO2NvbG9yOiM2MGE1ZmE7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwIj5SUzonK3IucnNfcmF0aW5nKyc8L3NwYW4+JwogICAgICArJzwvZGl2PjwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij48ZGl2IHN0eWxlPSJmb250LXdlaWdodDo3MDA7Y29sb3I6Jytjb2wrJztmb250LXNpemU6MTVweCI+JytwY3QrJyU8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPmHEn8SxcmzEsWtsxLE8L2Rpdj48L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+PGRpdiBzdHlsZT0iZm9udC13ZWlnaHQ6NjAwIj4kJytyLnByaWNlKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6JytjaGdDb2wrJyI+Jysoci5jaGFuZ2U+PTA/JysnOicnKStyLmNoYW5nZSsnJTwvZGl2PjwvZGl2PicKICAgICAgKyc8L2Rpdj4nCiAgICAgICsoZXhwYW5kZWQgPyBjcml0ZXJpYURldGFpbChyKSA6ICcnKQogICAgICArJzwvZGl2Pic7CiAgfQoKICBmdW5jdGlvbiBidWlsZEhUTUwoKXsKICAgIHZhciBoID0gJzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CgogICAgLy8gU3VtbWFyeQogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1ib3R0b206NHB4Ij7wn5SNIENBTlNMSU0gU2NyZWVuZXI8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MTJweCI+MTYga3JpdGVyIMK3IDMgw7ZuZW0gc2V2aXllc2kgwrcgJytkYXRhLmxlbmd0aCsnIGhpc3NlIHRhcmFuZMSxPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcDttYXJnaW4tYm90dG9tOjEycHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+JytwYXNzZWQubGVuZ3RoKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkdlw6d0aTwvZGl2PjwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1yZWQyKSI+JytmYWlsZWQubGVuZ3RoKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkdlw6dlbWVkaTwvZGl2PjwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOiM2MGE1ZmEiPicrZGF0YS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuaW5fd2F0Y2hsaXN0fHxyLmluX3BvcnRmb2xpbzt9KS5sZW5ndGgrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+TGlzdGVtZGU8L2Rpdj48L2Rpdj4nOwogICAgaCArPSAnPC9kaXY+JzsKICAgIC8vIExlZ2VuZAogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2ZsZXgtd3JhcDp3cmFwO2ZvbnQtc2l6ZToxMHB4Ij4nOwogICAgaCArPSAnPHNwYW4+8J+UtCA8c3Ryb25nPlpvcnVubHU8L3N0cm9uZz4gKDN4KTogRVBTIFFvUSwgU01BMjAwLCBNIEtyaXRlcmk8L3NwYW4+JzsKICAgIGggKz0gJzxzcGFuPvCfn6EgPHN0cm9uZz7Dlm5lbWxpPC9zdHJvbmc+ICgyeCk6IEdlbGlyLCBST0UsIE1hcmppbiwgU01BNTAsIDUySDwvc3Bhbj4nOwogICAgaCArPSAnPHNwYW4+8J+UtSA8c3Ryb25nPkRlc3Rlazwvc3Ryb25nPiAoMXgpOiBEacSfZXJsZXJpPC9zcGFuPic7CiAgICBoICs9ICc8L2Rpdj48L2Rpdj4nOwoKICAgIC8vIEdlw6dlbmxlcgogICAgaWYocGFzc2VkLmxlbmd0aCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O292ZXJmbG93OmhpZGRlbjttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9InBhZGRpbmc6MTBweCAxNHB4O2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA2KTtmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1ncmVlbik7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZSI+4pyFIENBTlNMSU0gR2XDp3RpICgnK3Bhc3NlZC5sZW5ndGgrJyk8L2Rpdj4nOwogICAgICBwYXNzZWQuZm9yRWFjaChmdW5jdGlvbihyKXsgaCArPSBzdG9ja1JvdyhyLCByLnRpY2tlcj09PWV4cGFuZGVkVGlja2VyKTsgfSk7CiAgICAgIGggKz0gJzwvZGl2Pic7CiAgICB9CgogICAgLy8gV2F0Y2hsaXN0L1BvcnRmb2xpbyAoZ2XDp2VtZXllbmxlcikKICAgIHZhciBteUZhaWxlZCA9IGZhaWxlZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuaW5fd2F0Y2hsaXN0fHxyLmluX3BvcnRmb2xpbzt9KTsKICAgIGlmKG15RmFpbGVkLmxlbmd0aCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O292ZXJmbG93OmhpZGRlbjttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9InBhZGRpbmc6MTBweCAxNHB4O2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA2KTtmb250LXNpemU6MTFweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2UiPvCfk4sgTGlzdGVtZGUgKEdlw6dlbWVkaSwgJytteUZhaWxlZC5sZW5ndGgrJyk8L2Rpdj4nOwogICAgICBteUZhaWxlZC5mb3JFYWNoKGZ1bmN0aW9uKHIpeyBoICs9IHN0b2NrUm93KHIsIHIudGlja2VyPT09ZXhwYW5kZWRUaWNrZXIpOyB9KTsKICAgICAgaCArPSAnPC9kaXY+JzsKICAgIH0KCiAgICBoICs9ICc8L2Rpdj4nOwogICAgcmV0dXJuIGg7CiAgfQoKICBncmlkLmlubmVySFRNTCA9IGJ1aWxkSFRNTCgpOwoKICAvLyBvbmNsaWNrIGhhbmRsZXJzCiAgZGF0YS5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3NjLScrci50aWNrZXIpOwogICAgaWYoZWwpewogICAgICBlbC5vbmNsaWNrID0gZnVuY3Rpb24oZSl7CiAgICAgICAgZS5zdG9wUHJvcGFnYXRpb24oKTsKICAgICAgICBpZihleHBhbmRlZFRpY2tlcj09PXIudGlja2VyKXsgZXhwYW5kZWRUaWNrZXI9bnVsbDsgfQogICAgICAgIGVsc2UgeyBleHBhbmRlZFRpY2tlcj1yLnRpY2tlcjsgfQogICAgICAgIGdyaWQuaW5uZXJIVE1MID0gYnVpbGRIVE1MKCk7CiAgICAgICAgLy8gUmUtYXR0YWNoIGhhbmRsZXJzCiAgICAgICAgZGF0YS5mb3JFYWNoKGZ1bmN0aW9uKHIyKXsKICAgICAgICAgIHZhciBlbDIgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnc2MtJytyMi50aWNrZXIpOwogICAgICAgICAgaWYoZWwyKSBlbDIub25jbGljayA9IGFyZ3VtZW50cy5jYWxsZWUuYmluZCh7dGlja2VyOnIyLnRpY2tlcn0pOwogICAgICAgIH0pOwogICAgICAgIGF0dGFjaEhhbmRsZXJzKCk7CiAgICAgIH07CiAgICB9CiAgfSk7CgogIGZ1bmN0aW9uIGF0dGFjaEhhbmRsZXJzKCl7CiAgICBkYXRhLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICAgIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdzYy0nK3IudGlja2VyKTsKICAgICAgaWYoIWVsKSByZXR1cm47CiAgICAgIGVsLm9uY2xpY2sgPSAoZnVuY3Rpb24odGlja2VyKXsKICAgICAgICByZXR1cm4gZnVuY3Rpb24oZSl7CiAgICAgICAgICBlLnN0b3BQcm9wYWdhdGlvbigpOwogICAgICAgICAgZXhwYW5kZWRUaWNrZXIgPSBleHBhbmRlZFRpY2tlcj09PXRpY2tlciA/IG51bGwgOiB0aWNrZXI7CiAgICAgICAgICBncmlkLmlubmVySFRNTCA9IGJ1aWxkSFRNTCgpOwogICAgICAgICAgYXR0YWNoSGFuZGxlcnMoKTsKICAgICAgICB9OwogICAgICB9KShyLnRpY2tlcik7CiAgICB9KTsKICB9CiAgYXR0YWNoSGFuZGxlcnMoKTsKfQoKCmZ1bmN0aW9uIHJlbmRlckRpcmVjdGlvbigpewogIHZhciBncmlkPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgaWYoZ3JpZCl7Z3JpZC5zdHlsZS5kaXNwbGF5PScnO2dyaWQuc3R5bGUud2lkdGg9Jyc7fQogIHZhciBEPURJUkVDVElPTl9EQVRBfHx7fTsKICB2YXIgTUVUQT17CiAgICB1cHRyZW5kOntpYzonXHVkODNkXHVkZmUyJyxsYmw6J1RleWl0bGkgWVx1MDBmY2tzZWxpXHUwMTVmJyxhZHY6J1Bpdm90IGtcdTAxMzFyYW4gbGlkZXJsZXJlIG5vcm1hbCBwb3ppc3lvbmxhIGdpcmlsZWJpbGlyLicsYzondmFyKC0tZ3JlZW4pJyxiZzoncmdiYSgxNiwxODUsMTI5LC4wOCknLGJkOidyZ2JhKDE2LDE4NSwxMjksLjI1KSd9LAogICAgcHJlc3N1cmU6e2ljOidcdWQ4M2RcdWRmZTEnLGxibDonQmFza1x1MDEzMSBBbHRcdTAxMzFuZGEnLGFkdjonWWVuaSBhbFx1MDEzMW0geWFwbWEuIFN0b3Agc2V2aXllbGVyaW5pIHNcdTAxMzFrXHUwMTMxbGFcdTAxNWZ0XHUwMTMxciwgemF5XHUwMTMxZiBwb3ppc3lvbmxhclx1MDEzMSBhemFsdC4nLGM6J3ZhcigtLXllbGxvdyknLGJnOidyZ2JhKDI0NSwxNTgsMTEsLjA4KScsYmQ6J3JnYmEoMjQ1LDE1OCwxMSwuMjUpJ30sCiAgICBjb3JyZWN0aW9uOntpYzonXHVkODNkXHVkZDM0JyxsYmw6J0RcdTAwZmN6ZWx0bWUnLGFkdjonTmFraXR0ZSAoU0dPVikgYmVrbGUuIFdhdGNobGlzdFx1MjAxOWkgZ1x1MDBmY25jZWxsZSwgZm9sbG93LXRocm91Z2ggZGF5IHNpbnlhbGluaSBpemxlLicsYzondmFyKC0tcmVkMiknLGJnOidyZ2JhKDIzOSw2OCw2OCwuMDgpJyxiZDoncmdiYSgyMzksNjgsNjgsLjI1KSd9LAogICAgcmFsbHk6e2ljOidcdWQ4M2RcdWRmZTAnLGxibDonVG9wYXJsYW5tYSBEZW5lbWVzaScsYWR2OidIZW5cdTAwZmN6IGdpcm1lIFx1MjAxNCBGVEQgcGVuY2VyZXNpIGFcdTAwZTdcdTAxMzFsXHUwMTMxeW9yLiBIYWNpbWxpICUxLjUrIHlcdTAwZmNrc2VsaVx1MDE1ZiBnXHUwMGZjblx1MDBmY25cdTAwZmMgYmVrbGUuJyxjOid2YXIoLS15ZWxsb3cpJyxiZzoncmdiYSgyNDUsMTU4LDExLC4wOCknLGJkOidyZ2JhKDI0NSwxNTgsMTEsLjI1KSd9LAogICAgZnRkOntpYzonXHUyNmExJyxsYmw6J0ZPTExPVy1USFJPVUdIIERBWSEnLGFkdjonS2FkZW1lbGkgZ2lyaVx1MDE1ZiBiYVx1MDE1ZmxhdDoga1x1MDBmY1x1MDBlN1x1MDBmY2sgcG96aXN5b25sYSB0ZXN0IGV0LCBwaXlhc2EgaGFrbFx1MDEzMSBcdTAwZTdcdTAxMzFrYXJcdTAxMzFyc2EgYlx1MDBmY3lcdTAwZmN0LicsYzondmFyKC0tZ3JlZW4pJyxiZzoncmdiYSgxNiwxODUsMTI5LC4xKScsYmQ6J3JnYmEoMTYsMTg1LDEyOSwuMzUpJ30KICB9OwogIHZhciBoPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xIj4nOwogIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tYm90dG9tOjRweCI+XHVkODNkXHVkY2NhIFBpeWFzYSBZXHUwMGY2blx1MDBmYyBcdTIwMTQgRlREIFRha2liaTwvZGl2Pic7CiAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsaW5lLWhlaWdodDoxLjYiPkZvbGxvdy10aHJvdWdoIGRheTogZGlwdGVuIDQtMTAgZ1x1MDBmY24gc29ucmEgZ2VsZW4gaGFjaW1saSAlMS41KyB5XHUwMGZja3NlbGlcdTAxNWYgZ1x1MDBmY25cdTAwZmMgXHUyMDE0IHllbmkgeVx1MDBmY2tzZWxpXHUwMTVmIHRyZW5kaW5pIHRleWl0IGVkZXIuIERhXHUwMTFmXHUwMTMxdFx1MDEzMW0gZ1x1MDBmY25cdTAwZmM6IGFydGFuIGhhY2ltbGUgJTAuMisgZFx1MDBmY1x1MDE1Zlx1MDBmY1x1MDE1ZiBcdTIwMTQga3VydW1zYWwgc2F0XHUwMTMxXHUwMTVmIGl6aS4gMjUgZ1x1MDBmY25kZSA1KyBkYVx1MDExZlx1MDEzMXRcdTAxMzFtID0gcGl5YXNhIGJhc2tcdTAxMzEgYWx0XHUwMTMxbmRhLjwvZGl2PjwvZGl2Pic7CiAgWydTUDUwMCcsJ05BU0RBUSddLmZvckVhY2goZnVuY3Rpb24obmFtZSl7CiAgICB2YXIgZD1EW25hbWVdfHx7fTsKICAgIGlmKGQuZXJyb3J8fGQuc3RhdHVzPT09dW5kZWZpbmVkKXtoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrbmFtZSsnOiB2ZXJpIHlvazwvZGl2Pic7cmV0dXJuO30KICAgIHZhciBtPU1FVEFbZC5zdGF0dXNdfHxNRVRBLnByZXNzdXJlOwogICAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JyttLmJnKyc7Ym9yZGVyOjFweCBzb2xpZCAnK20uYmQrJztib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4IDIwcHg7bWFyZ2luLWJvdHRvbToxMnB4Ij4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7ZmxleC13cmFwOndyYXA7Z2FwOjhweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoKz0nPGRpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4Ij4nKyhuYW1lPT09J1NQNTAwJz8nUyZQIDUwMCc6J05BU0RBUScpKyc8L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK20uYysnIj4nK20uaWMrJyAnK20ubGJsKyc8L2Rpdj48L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5aaXJ2ZWRlbjogPHNwYW4gc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonKyhkLmRyYXdkb3duPD0tOD8ndmFyKC0tcmVkMiknOmQuZHJhd2Rvd248PS00Pyd2YXIoLS15ZWxsb3cpJzondmFyKC0tZ3JlZW4pJykrJyI+JScrZC5kcmF3ZG93bisnPC9zcGFuPjwvZGl2PjwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tdGV4dCk7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wMyk7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDEycHg7bWFyZ2luLWJvdHRvbToxMHB4Ij5cdWQ4M2RcdWRjYTEgJyttLmFkdisnPC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDE0MHB4LDFmcikpO2dhcDo4cHgiPic7CiAgICB2YXIgZGNvbD1kLmRpc3RfY291bnQ+PTU/J3ZhcigtLXJlZDIpJzpkLmRpc3RfY291bnQ+PTM/J3ZhcigtLXllbGxvdyknOid2YXIoLS1ncmVlbiknOwogICAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHgiPkRBXHUwMTFlSVRJTSBHXHUwMGRjTlx1MDBkYyAoMjVHKTwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK2Rjb2wrJyI+JytkLmRpc3RfY291bnQrJyAvIDU8L2Rpdj48L2Rpdj4nOwogICAgaWYoZC5mdGQpewogICAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweCI+RlREPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjE0cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLWdyZWVuKSI+JytkLmZ0ZC5kYXRlKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1ncmVlbikiPislJytkLmZ0ZC5nYWluKycgKCcrZC5mdGQuZGF5KycuIGdcdTAwZmNuKTwvZGl2PjwvZGl2Pic7CiAgICB9IGVsc2UgaWYoZC5yYWxseV9kYXk+MCl7CiAgICAgIGgrPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MXB4Ij5UT1BBUkxBTk1BPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXllbGxvdykiPicrZC5yYWxseV9kYXkrJy4gZ1x1MDBmY248L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+RlREIHBlbmNlcmVzaTogNC0xMC4gZ1x1MDBmY248L2Rpdj48L2Rpdj4nOwogICAgICBpZihkLnJhbGx5X2xvdykgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHgiPlx1MDEzMFBUQUwgU0VWXHUwMTMwWUVTXHUwMTMwPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nK2QucmFsbHlfbG93Kyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+ZGVuZW1lIGRpYmkga1x1MDEzMXJcdTAxMzFsXHUwMTMxcnNhIHNheWFcdTAwZTcgc1x1MDEzMWZcdTAxMzFybGFuXHUwMTMxcjwvZGl2PjwvZGl2Pic7CiAgICB9IGVsc2UgewogICAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweCI+VE9QQVJMQU5NQTwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1tdXRlZCkiPlx1MjAxNDwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBoKz0nPC9kaXY+JzsKICAgIGlmKGQuZGlzdF9kYXlzJiZkLmRpc3RfZGF5cy5sZW5ndGgpewogICAgICBoKz0nPGRpdiBzdHlsZT0ibWFyZ2luLXRvcDoxMHB4O2ZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+U29uIGRhXHUwMTFmXHUwMTMxdFx1MDEzMW0gZ1x1MDBmY25sZXJpOiAnK2QuZGlzdF9kYXlzLm1hcChmdW5jdGlvbih4KXtyZXR1cm4geC5kYXRlKycgKCcreC5jaGcrJyUpJzt9KS5qb2luKCcgXHUwMGI3ICcpKyc8L2Rpdj4nOwogICAgfQogICAgaCs9JzwvZGl2Pic7CiAgfSk7CiAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4Ij4nOwogIGgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPlx1ZDgzZFx1ZGNjYiAzIEFkXHUwMTMxbWxcdTAxMzEgUGxhbjwvZGl2Pic7CiAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2xpbmUtaGVpZ2h0OjEuODtjb2xvcjp2YXIoLS10ZXh0KSI+JzsKICBoKz0nMVx1ZmUwZlx1MjBlMyA8c3Ryb25nPkRcdTAwZmN6ZWx0bWVkZTo8L3N0cm9uZz4gTmFraXQgU0dPVlx1MjAxOWRhIGJla2xlciwgbWV2Y3V0IHBvemlzeW9ubGFyZGEgc3RvcCBkaXNpcGxpbmkuPGJyPic7CiAgaCs9JzJcdWZlMGZcdTIwZTMgPHN0cm9uZz5CZWtsZXJrZW46PC9zdHJvbmc+IFNjcmVlbmVyICsgRGVcdTAxMWZlcmxlbWUgc2VrbWVzaXlsZSBSU1x1MjAxOWkgeVx1MDBmY2tzZWssIGJheiB5YXBhbiBsaWRlcmxlcmkgaVx1MDE1ZmFyZXRsZS48YnI+JzsKICBoKz0nM1x1ZmUwZlx1MjBlMyA8c3Ryb25nPkZURCBnZWxpbmNlOjwvc3Ryb25nPiBLYWRlbWVsaSBnaXJpXHUwMTVmIFx1MjAxNCBcdTAwZjZuY2Uga1x1MDBmY1x1MDBlN1x1MDBmY2sgdGVzdCBwb3ppc3lvbnUsIHRleWl0IGdlbGlyc2UgcGl2b3Qga1x1MDEzMXJhbmxhcmxhIGJcdTAwZmN5XHUwMGZjdC4nOwogIGgrPSc8L2Rpdj48L2Rpdj4nOwogIGgrPSc8L2Rpdj4nOwogIGdyaWQuaW5uZXJIVE1MPWg7Cn0KCgoKZnVuY3Rpb24gcmVuZGVyTWluZXJ2aW5pKCl7CiAgdmFyIGdyaWQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogIGlmKGdyaWQpeyBncmlkLnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsgZ3JpZC5zdHlsZS53aWR0aD0nMTAwJSc7IH0KICB2YXIgZGF0YTFkID0gKFRGX0RBVEEgJiYgVEZfREFUQVsnMWQnXSkgPyBURl9EQVRBWycxZCddIDogW107CgogIGZ1bmN0aW9uIGNhbGNUcmVuZFRlbXBsYXRlKHIpewogICAgdmFyIHNjb3JlID0gMDsgdmFyIGRldGFpbHMgPSBbXTsKICAgIHZhciBjMSA9IHIuYWJvdmU1MDsKICAgIGRldGFpbHMucHVzaCh7bGFiZWw6J0ZpeWF0ID4gU01BNTAnLCBwYXNzOmMxLCB2YWw6IGMxID8gJ0V2ZXQnIDogJ0hheWlyJywgdGlwOidGaXlhdCA1MCBndW5sdWsgb3J0YWxhbWFuaW4gdXplcmluZGV5c2UgaGlzc2Uga2lzYSB2YWRlZGUgZ3VjbHUgZGVtZWsuJ30pOwogICAgaWYoYzEpIHNjb3JlKys7CiAgICB2YXIgYzIgPSByLnNtYTIwMCAmJiByLmZpeWF0ID4gci5zbWEyMDAgKiAwLjk3OwogICAgZGV0YWlscy5wdXNoKHtsYWJlbDonRml5YXQgPiBTTUExNTAnLCBwYXNzOmMyLCB2YWw6IGMyID8gJ1RhaG1pbmVuIEV2ZXQnIDogJ0hheWlyJywgdGlwOidPcnRhIHZhZGVsaSB0cmVuZC4gU01BMjAwXCdlIHlha2luIGRlZ2VyIGt1bGxhbmlsaXlvci4nfSk7CiAgICBpZihjMikgc2NvcmUrKzsKICAgIHZhciBjMyA9IHIuYWJvdmUyMDA7CiAgICBkZXRhaWxzLnB1c2goe2xhYmVsOidGaXlhdCA+IFNNQTIwMCcsIHBhc3M6YzMsIHZhbDogYzMgPyAnRXZldCcgOiAnSGF5aXInLCB0aXA6J1V6dW4gdmFkZWxpIHRyZW5kIOKAlCBlbiBrcml0aWsgZmlsdHJlLiBCdSBvbG1hZGFuIGhpc3NlIGFsaW5tYXouJ30pOwogICAgaWYoYzMpIHNjb3JlKys7CiAgICB2YXIgYzQgPSByLnNtYTUwICYmIHIuc21hMjAwICYmIHIuc21hNTAgPiByLnNtYTIwMDsKICAgIGRldGFpbHMucHVzaCh7bGFiZWw6J1NNQTUwID4gU01BMjAwIChBbHRpbiBDYXJwYXopJywgcGFzczpjNCwgdmFsOiBjNCA/ICdFdmV0JyA6ICdIYXlpcicsIHRpcDonNTAgZ3VubHVrIG9ydGFsYW1hIDIwMCBndW5sdWd1biB1emVyaW5kZS4gQm9nYSBwaXlhc2FzaW5pbiB0ZWtuaWsgZG9ncnVsYW1hc2kuJ30pOwogICAgaWYoYzQpIHNjb3JlKys7CiAgICB2YXIgYzUgPSByLnNtYTIwMCAmJiByLnNtYTUwICYmIHIuc21hMjAwID4gMDsKICAgIGRldGFpbHMucHVzaCh7bGFiZWw6J1NNQTIwMCBZdWtzZWxpeW9yJywgcGFzczpjNSwgdmFsOiBjNSA/ICdWZXJpIHZhcicgOiAnVmVyaSB5b2snLCB0aXA6J1NNQTIwMFwndW4gc29uIDEgYXlkaXIgeXVrYXJpIGJha2l5b3Igb2xtYXNpIGdlcmVraXIuIFlhbiBnaWRlbiB2ZXlhIGR1c2VuIFNNQTIwMCB0ZWhsaWtlIGlzYXJldGkuJ30pOwogICAgaWYoYzUpIHNjb3JlKys7CiAgICB2YXIgYzYgPSByLmxvdzUydyAmJiByLmZpeWF0ICYmICgoci5maXlhdCAtIHIubG93NTJ3KSAvIHIubG93NTJ3ICogMTAwKSA+PSAzMDsKICAgIHZhciBsb3c1MnBjdCA9IHIubG93NTJ3ID8gTWF0aC5yb3VuZCgoci5maXlhdCAtIHIubG93NTJ3KSAvIHIubG93NTJ3ICogMTAwKSA6IDA7CiAgICBkZXRhaWxzLnB1c2goe2xhYmVsOic1MkggRGlwICslMzAnLCBwYXNzOmM2LCB2YWw6IChyLmxvdzUydyA/ICcrJScrbG93NTJwY3QgOiAnPycpLCB0aXA6J0hpc3NlIHlpbGxpayBkaWJpbmRlbiBlbiBheiAlMzAgeXVrYXJpZGEgb2xtYWxpLiBHZXJjZWsgZ3VjIGdvc3Rlcmdlc2kuJ30pOwogICAgaWYoYzYpIHNjb3JlKys7CiAgICB2YXIgYzcgPSByLnBjdF9mcm9tXzUydyAhPT0gdW5kZWZpbmVkICYmIHIucGN0X2Zyb21fNTJ3IDw9IDI1OwogICAgZGV0YWlscy5wdXNoKHtsYWJlbDonNTJIIFppcnZleWUgLSUyNScsIHBhc3M6YzcsIHZhbDogKHIucGN0X2Zyb21fNTJ3ICE9PSB1bmRlZmluZWQgPyAnLSUnK3IucGN0X2Zyb21fNTJ3KycgdXphaycgOiAnPycpLCB0aXA6J0hpc3NlIHlpbGxpayB6aXJ2ZXNpbmluICUyNVwnaSBpY2luZGUgb2xtYWxpLiBaaXJ2ZXllIHlha2luID0gZ3VjbHUgaGlzc2UuJ30pOwogICAgaWYoYzcpIHNjb3JlKys7CiAgICB2YXIgYzggPSByLmdhaW5fNm0gIT09IHVuZGVmaW5lZCAmJiByLmdhaW5fNm0gPj0gMjA7CiAgICBkZXRhaWxzLnB1c2goe2xhYmVsOidSUyBHdWMgPiUyMCAoNkEpJywgcGFzczpjOCwgdmFsOiAoci5nYWluXzZtICE9PSB1bmRlZmluZWQgPyAnNkE6ICUnK3IuZ2Fpbl82bSA6ICc/JyksIHRpcDonU29uIDYgYXlkYSBTJlA1MDBcJ2RlbiBkYWhhIGl5aSBwZXJmb3JtYW5zLiBSUz43MCBkZW1layBlbiBndWNsdSAlMzAgaWNpbmRlIG9sbWFrLid9KTsKICAgIGlmKGM4KSBzY29yZSsrOwogICAgcmV0dXJuIHtzY29yZTogc2NvcmUsIGRldGFpbHM6IGRldGFpbHN9OwogIH0KCiAgZnVuY3Rpb24gY2FsY1ZDUChyKXsKICAgIHZhciBhdHIgPSByLmF0cjsgdmFyIHByaWNlID0gci5maXlhdDsKICAgIGlmKCFhdHIgfHwgIXByaWNlKSByZXR1cm4ge2hhc1ZDUDogbnVsbCwgbm90ZTogJ0FUUiB2ZXJpc2kgeW9rJ307CiAgICB2YXIgYXRyUGN0ID0gKGF0ciAvIHByaWNlICogMTAwKTsKICAgIHZhciBpc0xvd1ZvbCA9IGF0clBjdCA8IDMuNTsKICAgIHZhciBuZWFySGlnaCA9IHIucGN0X2Zyb21fNTJ3IDw9IDIwOwogICAgdmFyIGFib3ZlTUFzID0gci5hYm92ZTUwICYmIHIuYWJvdmUyMDA7CiAgICB2YXIgaGFzVkNQID0gaXNMb3dWb2wgJiYgbmVhckhpZ2ggJiYgYWJvdmVNQXM7CiAgICByZXR1cm4ge2hhc1ZDUDogaGFzVkNQLCBhdHJQY3Q6IGF0clBjdC50b0ZpeGVkKDEpLCBub3RlOiBoYXNWQ1AgPyAnVkNQIGZvcm1hc3lvbnUgb2xhc2knIDogJ1ZDUCBrb3N1bGxhcmkgdGFtIHNhZ2xhbm1peW9yJ307CiAgfQoKICB2YXIgaCA9ICc8ZGl2IHN0eWxlPSJwYWRkaW5nOjE2cHg7d2lkdGg6MTAwJTtib3gtc2l6aW5nOmJvcmRlci1ib3giPic7CgogIC8vIMOcc3QgYcOnxLFrbGFtYQogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MThweCAyMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDoxMHB4O21hcmdpbi1ib3R0b206MTJweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDAiPvCfjq8gTWluZXJ2aW5pIE1ldG9kb2xvamlzaTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjEyKTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjQ1LDE1OCwxMSwuMyk7Ym9yZGVyLXJhZGl1czo2cHg7cGFkZGluZzozcHggMTBweDtmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS15ZWxsb3cpO2ZvbnQtd2VpZ2h0OjYwMCI+VFJBREUgTElLRSBBIFNUT0NLIE1BUktFVCBXSVpBUkQ8L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6Izk0YTNiODtsaW5lLWhlaWdodDoxLjg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIGggKz0gJzxzdHJvbmcgc3R5bGU9ImNvbG9yOnZhcigtLXRleHQpIj5NYXJrIE1pbmVydmluaTwvc3Ryb25nPiwgQUJEIEhpc3NlIFNlbmVkaSBTYW1waXlvbmx1Z3VudSBiaXJkZW4gZmF6bGEga2V6IGthemFubWlzIHZlIHlpbGxpayBvcnRhbGFtYSA8c3Ryb25nIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbikiPiUyMjArIGdldGlyaTwvc3Ryb25nPiB1cmV0bWlzIGJpciB0cmFkZXJcJ2Rpci4gJzsKICBoICs9ICdNZXRvZG9sb2ppc2kgaWtpIHVuc3VyYSBkYXlhbmlyOiA8c3Ryb25nIHN0eWxlPSJjb2xvcjojNjBhNWZhIj5UcmVuZCBUZW1wbGF0ZTwvc3Ryb25nPiAoZG9ncnUgaGlzc2V5aSBidWwpICsgPHN0cm9uZyBzdHlsZT0iY29sb3I6I2E3OGJmYSI+VkNQICsgU0VQQSBHaXJpc2k8L3N0cm9uZz4gKGRvZ3J1IGFuZGEgZ2lyKS4gJzsKICBoICs9ICdBc2xhIGR1c2VuIHZleWEgemF5aWYgaGlzc2UgYWxtYXog4oCUIHNhZGVjZSBndWNsdSwgYmF6YSBnaXJtaXMgdmUga2lyaWxpbSBub2t0YXNpbmEgeWFraW4gbGlkZXJsZXJlIGdpcmVyLic7CiAgaCArPSAnPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDIyMHB4LDFmcikpO2dhcDoxMHB4Ij4nOwogIFt7aWNvbjon8J+TkCcsdGl0bGU6J1RyZW5kIFRlbXBsYXRlJyxkZXNjOic4IGtyaXRlcmluIHRhbWFtaW5pIGthcnNpbGF5YW4gaGlzc2VsZXIgc2F0aW4gYWxtYXlhIHV5Z3VuIGJvbGdlZGVkaXIuIDEga3JpdGVyIGJpbGUgZWtzaWtzZSBoaXNzZSBsaXN0ZXllIGdpcm1lei4nfSwKICAge2ljb246J/CfjIAnLHRpdGxlOidWQ1AgKFZvbGF0aWxpdGUgRGFyYWxtYXPEsSknLGRlc2M6J0ZpeWF0IGtvbnNvbGlkYXN5b25hIGdpcmVyLCBoZXIgZGFsZ2EgaGVtIGZpeWF0IGhlbSBoYWNpbSBvbGFyYWsgZGFyYWxpci4gS3VydW1zYWwgc2F0aXPEsW4gYml0dGlnaW5pbiBpc2FyZXRpZGlyLid9LAogICB7aWNvbjon8J+OrycsdGl0bGU6J1NFUEEgR2lyaXNpJyxkZXNjOidQaXZvdCBraXJpbGltaW5kYSBoYWNpbWxlIGJpcmxpa3RlIGNvayBzcGVzaWZpayBnaXJpcy4gQXNsYSBlcmtlbiwgYXNsYSBnZWMuJ30sCiAgIHtpY29uOifwn5uh77iPJyx0aXRsZTonUmlzayBZw7ZuZXRpbWknLGRlc2M6J0hlciBpc2xlbWRlIG1ha3MgJTEtMiBzZXJtYXllIHJpc2tpLiBTdG9wLWxvc3MgcGl2b3QgYWx0aW5hIGtvbnVyLiBQb3ppc3lvbiBidXl1a2x1Z3UgYnVuYSBnb3JlIGhlc2FwbGFuaXIuJ30KICBdLmZvckVhY2goZnVuY3Rpb24oYyl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTJweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNHB4O21hcmdpbi1ib3R0b206NHB4Ij4nK2MuaWNvbisnIDxzdHJvbmcgc3R5bGU9ImNvbG9yOnZhcigtLXRleHQpIj4nK2MudGl0bGUrJzwvc3Ryb25nPjwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjojOTRhM2I4O2xpbmUtaGVpZ2h0OjEuNSI+JytjLmRlc2MrJzwvZGl2PjwvZGl2Pic7CiAgfSk7CiAgaCArPSAnPC9kaXY+PC9kaXY+JzsKCiAgLy8gSXMgYWtpc2kKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMTY3LDEzOSwyNTAsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTY3LDEzOSwyNTAsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6I2E3OGJmYTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTJweCI+8J+TiyBEb2dydSBTaXJhIOKAlCBJcyBBa2lzaTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2ZsZXgtd3JhcDp3cmFwO2dhcDo4cHg7YWxpZ24taXRlbXM6Y2VudGVyIj4nOwogIFsnMe+4j+KDoyBDQU5TTElNIFNjcmVlbmVyXCdkYSB0ZW1lbCBrcml0ZXJsZXInLCfihpInLCcy77iP4oOjIFRyZW5kIFRlbXBsYXRlICg4LzggdmV5YSA3LzgpJywn4oaSJywnM++4j+KDoyBWQ1AgRm9ybWFzeW9udSAoVHJhZGluZ1ZpZXcpJywn4oaSJywnNO+4j+KDoyBQaXZvdCBraXJpbGltaW5pIGJla2xlICsgaGFjaW0gb25hecSxJywn4oaSJywnNe+4j+KDoyBTRVBBIGlsZSBnaXIsIHN0b3AgcGl2b3QgYWx0xLFuYSddLmZvckVhY2goZnVuY3Rpb24ocyl7CiAgICBpZihzPT09J+KGkicpe2grPSc8ZGl2IHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1zaXplOjE2cHgiPuKGkjwvZGl2Pic7fQogICAgZWxzZXtoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjZweDtwYWRkaW5nOjZweCAxMHB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLXRleHQpIj4nK3MrJzwvZGl2Pic7fQogIH0pOwogIGggKz0gJzwvZGl2PjwvZGl2Pic7CgogIC8vIMOWemV0IGlzdGF0aXN0aWtsZXIKICB2YXIgcm93cyA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuICFyLmhhdGE7fSk7CiAgdmFyIHNjb3JlZCA9IHJvd3MubWFwKGZ1bmN0aW9uKHIpeyB2YXIgdHQ9Y2FsY1RyZW5kVGVtcGxhdGUocik7IHZhciB2Y3A9Y2FsY1ZDUChyKTsgcmV0dXJuIHtyOnIsdHQ6dHQsdmNwOnZjcH07IH0pLnNvcnQoZnVuY3Rpb24oYSxiKXtyZXR1cm4gYi50dC5zY29yZS1hLnR0LnNjb3JlO30pOwogIHZhciBwYXNzOD1zY29yZWQuZmlsdGVyKGZ1bmN0aW9uKHgpe3JldHVybiB4LnR0LnNjb3JlPj04O30pLmxlbmd0aDsKICB2YXIgcGFzczc9c2NvcmVkLmZpbHRlcihmdW5jdGlvbih4KXtyZXR1cm4geC50dC5zY29yZT49Nzt9KS5sZW5ndGg7CiAgdmFyIHBhc3M2PXNjb3JlZC5maWx0ZXIoZnVuY3Rpb24oeCl7cmV0dXJuIHgudHQuc2NvcmU+PTY7fSkubGVuZ3RoOwogIHZhciB2Y3BDPXNjb3JlZC5maWx0ZXIoZnVuY3Rpb24oeCl7cmV0dXJuIHgudmNwLmhhc1ZDUDt9KS5sZW5ndGg7CgogIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6Z3JpZDtncmlkLXRlbXBsYXRlLWNvbHVtbnM6cmVwZWF0KGF1dG8tZmlsbCxtaW5tYXgoMTQwcHgsMWZyKSk7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogIFt7djpwYXNzOCxsOic4LzggVGFtIFB1YW4nLGM6J3ZhcigtLWdyZWVuKScsYmc6J3JnYmEoMTYsMTg1LDEyOSwuMDgpJyxiZDoncmdiYSgxNiwxODUsMTI5LC4yNSknfSwKICAge3Y6cGFzczcsbDonNy84IEfDvMOnbMO8JyxjOid2YXIoLS1ncmVlbjIpJyxiZzoncmdiYSg1MiwyMTEsMTUzLC4wNiknLGJkOidyZ2JhKDUyLDIxMSwxNTMsLjIpJ30sCiAgIHt2OnBhc3M2LGw6JzYvOCDEsHpsZScsYzondmFyKC0teWVsbG93KScsYmc6J3JnYmEoMjQ1LDE1OCwxMSwuMDgpJyxiZDoncmdiYSgyNDUsMTU4LDExLC4yNSknfSwKICAge3Y6dmNwQyxsOidWQ1AgQWRhecSxJyxjOicjYTc4YmZhJyxiZzoncmdiYSgxNjcsMTM5LDI1MCwuMDgpJyxiZDoncmdiYSgxNjcsMTM5LDI1MCwuMjUpJ30KICBdLmZvckVhY2goZnVuY3Rpb24oeCl7CiAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonK3guYmcrJztib3JkZXI6MXB4IHNvbGlkICcreC5iZCsnO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjI2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicreC5jKyciPicreC52Kyc8L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+Jyt4LmwrJzwvZGl2PjwvZGl2Pic7CiAgfSk7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gVHJlbmQgVGVtcGxhdGUgdGFibG9zdQogIGlmKHNjb3JlZC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEycHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi1ib3R0b206MTRweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9InBhZGRpbmc6MTJweCAxNnB4O2JvcmRlci1ib3R0b206MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA2KTtmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZSI+8J+TkCBUcmVuZCBUZW1wbGF0ZSBBbmFsaXppPC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9Im92ZXJmbG93LXg6YXV0byI+PHRhYmxlIHN0eWxlPSJ3aWR0aDoxMDAlO2JvcmRlci1jb2xsYXBzZTpjb2xsYXBzZTtmb250LXNpemU6MTFweDttaW4td2lkdGg6NjAwcHgiPjx0aGVhZD48dHIgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKSI+JzsKICAgIFsnSGlzc2UnLCdGaXlhdCcsJ1RUIFNrb3J1JywnU01BNTAnLCdTTUEyMDAnLCdBbHRpbiBDYXJwYXonLCc1MkggRGlwJywnNTJIIFppcnZlJywnUlMgR3VjJywnVkNQPyddLmZvckVhY2goZnVuY3Rpb24oYyxpKXsKICAgICAgaCs9Jzx0aCBzdHlsZT0idGV4dC1hbGlnbjonKyhpPT09MD8nbGVmdCc6J3JpZ2h0JykrJztwYWRkaW5nOjhweCAnKyhpPT09MD8nMTQnOic4JykrJ3B4O2NvbG9yOnZhcigtLW11dGVkKTtmb250LXdlaWdodDo2MDA7d2hpdGUtc3BhY2U6bm93cmFwIj4nK2MrJzwvdGg+JzsKICAgIH0pOwogICAgaCArPSAnPC90cj48L3RoZWFkPjx0Ym9keT4nOwogICAgc2NvcmVkLmZvckVhY2goZnVuY3Rpb24oaXRlbSxpZHgpewogICAgICB2YXIgcj1pdGVtLnI7IHZhciB0dD1pdGVtLnR0OyB2YXIgdmNwPWl0ZW0udmNwOyB2YXIgc2NvcmU9dHQuc2NvcmU7CiAgICAgIHZhciBzY29yZUNvbD1zY29yZT49OD8ndmFyKC0tZ3JlZW4pJzpzY29yZT49Nz8ndmFyKC0tZ3JlZW4yKSc6c2NvcmU+PTY/J3ZhcigtLXllbGxvdyknOid2YXIoLS1tdXRlZCknOwogICAgICB2YXIgc2NvcmVCZz1zY29yZT49OD8ncmdiYSgxNiwxODUsMTI5LC4xNSknOnNjb3JlPj03PydyZ2JhKDUyLDIxMSwxNTMsLjEpJzpzY29yZT49Nj8ncmdiYSgyNDUsMTU4LDExLC4xKSc6J3ZhcigtLWJnMyknOwogICAgICB2YXIgYmc9aWR4JTI9PT0wPyd2YXIoLS1iZyknOidyZ2JhKDI1NSwyNTUsMjU1LC4wMTUpJzsKICAgICAgdmFyIGluUG9ydD1QT1JULmluY2x1ZGVzKHIudGlja2VyKTsKICAgICAgaCs9Jzx0ciBzdHlsZT0iYmFja2dyb3VuZDonK2JnKyc7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDMpIj4nOwogICAgICBoKz0nPHRkIHN0eWxlPSJwYWRkaW5nOjEwcHggMTRweDtmb250LXdlaWdodDo3MDAiPjxzcGFuIHN0eWxlPSJjb2xvcjonKyhzY29yZT49Nz8ndmFyKC0tZ3JlZW4pJzpzY29yZT49Nj8ndmFyKC0teWVsbG93KSc6J3ZhcigtLXRleHQpJykrJyI+JytyLnRpY2tlcisnPC9zcGFuPic7CiAgICAgIGlmKGluUG9ydCkgaCs9JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWxlZnQ6NHB4Ij5QPC9zcGFuPic7CiAgICAgIGgrPSc8L3RkPic7CiAgICAgIHZhciBkYz1yLmRlZ2lzaW0+PTA/J3ZhcigtLWdyZWVuMiknOid2YXIoLS1yZWQyKSc7CiAgICAgIGgrPSc8dGQgc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7cGFkZGluZzo4cHgiPjxkaXYgc3R5bGU9ImZvbnQtd2VpZ2h0OjYwMCI+JCcrci5maXlhdCsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK2RjKyciPicrKHIuZGVnaXNpbT49MD8nKyc6JycpK3IuZGVnaXNpbSsnJTwvZGl2PjwvdGQ+JzsKICAgICAgaCs9Jzx0ZCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjhweCI+PHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6JytzY29yZUJnKyc7Y29sb3I6JytzY29yZUNvbCsnO2JvcmRlci1yYWRpdXM6NHB4O3BhZGRpbmc6M3B4IDhweDtmb250LXdlaWdodDo3MDA7Zm9udC1zaXplOjEycHgiPicrc2NvcmUrJy84PC9zcGFuPjwvdGQ+JzsKICAgICAgaCs9Jzx0ZCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjhweDtjb2xvcjonKyhyLmFib3ZlNTA/J3ZhcigtLWdyZWVuKSc6J3ZhcigtLXJlZDIpJykrJyI+JysoIHIuYWJvdmU1MD8n4pyTIFVzdC4nOifinJcgQWx0LicpKyc8L3RkPic7CiAgICAgIGgrPSc8dGQgc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7cGFkZGluZzo4cHg7Y29sb3I6Jysoci5hYm92ZTIwMD8ndmFyKC0tZ3JlZW4pJzondmFyKC0tcmVkMiknKSsnIj4nKyggci5hYm92ZTIwMD8n4pyTIFVzdC4nOifinJcgQWx0LicpKyc8L3RkPic7CiAgICAgIHZhciBnYz1yLnNtYTUwJiZyLnNtYTIwMCYmci5zbWE1MD5yLnNtYTIwMDsKICAgICAgaCs9Jzx0ZCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjhweDtjb2xvcjonKyhnYz8ndmFyKC0tZ3JlZW4pJzondmFyKC0tcmVkMiknKSsnIj4nKyggZ2M/J+Kckyc6J+KclycpKyc8L3RkPic7CiAgICAgIHZhciBscD1yLmxvdzUydz9NYXRoLnJvdW5kKChyLmZpeWF0LXIubG93NTJ3KS9yLmxvdzUydyoxMDApOm51bGw7CiAgICAgIGgrPSc8dGQgc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7cGFkZGluZzo4cHg7Y29sb3I6JysobHAhPT1udWxsJiZscD49MzA/J3ZhcigtLWdyZWVuKSc6bHAhPT1udWxsJiZscD49MTU/J3ZhcigtLXllbGxvdyknOid2YXIoLS1yZWQyKScpKyciPicrKCBscCE9PW51bGw/JyslJytscDonPycpKyc8L3RkPic7CiAgICAgIHZhciBjNz1yLnBjdF9mcm9tXzUydyE9PXVuZGVmaW5lZCYmci5wY3RfZnJvbV81Mnc8PTI1OwogICAgICBoKz0nPHRkIHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O3BhZGRpbmc6OHB4O2NvbG9yOicrKGM3Pyd2YXIoLS1ncmVlbiknOnIucGN0X2Zyb21fNTJ3PD0zNT8ndmFyKC0teWVsbG93KSc6J3ZhcigtLXJlZDIpJykrJyI+JysoIHIucGN0X2Zyb21fNTJ3IT09dW5kZWZpbmVkPyctJScrci5wY3RfZnJvbV81Mnc6Jz8nKSsnPC90ZD4nOwogICAgICB2YXIgYzg9ci5nYWluXzZtIT09dW5kZWZpbmVkJiZyLmdhaW5fNm0+PTIwOwogICAgICBoKz0nPHRkIHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O3BhZGRpbmc6OHB4O2NvbG9yOicrKGM4Pyd2YXIoLS1ncmVlbiknOnIuZ2Fpbl82bT49NT8ndmFyKC0teWVsbG93KSc6J3ZhcigtLXJlZDIpJykrJyI+JysoIHIuZ2Fpbl82bSE9PXVuZGVmaW5lZD8nJScrci5nYWluXzZtOic/JykrJzwvdGQ+JzsKICAgICAgaCs9Jzx0ZCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjhweCI+JysodmNwLmhhc1ZDUD09PW51bGw/JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPuKAlDwvc3Bhbj4nOnZjcC5oYXNWQ1A/JzxzcGFuIHN0eWxlPSJjb2xvcjojYTc4YmZhO2ZvbnQtd2VpZ2h0OjYwMCI+4pyTIE9sYXNpPC9zcGFuPic6JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPuKAlDwvc3Bhbj4nKSsnPC90ZD4nOwogICAgICBoKz0nPC90cj4nOwogICAgfSk7CiAgICBoICs9ICc8L3Rib2R5PjwvdGFibGU+PC9kaXY+PC9kaXY+JzsKICB9CgogIC8vIFJpc2sgecO2bmV0aW1pCiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1yZWQyKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTJweCI+8J+boe+4jyBNaW5lcnZpbmkgUmlzayBZw7ZuZXRpbWkgS3VyYWxsYXLEsTwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgyMjBweCwxZnIpKTtnYXA6MTBweCI+JzsKICBbe3Q6JyUxLTIgU2VybWF5ZSBSaXNraScsZDonSGVyIGlzbGVtZGUgdG9wbGFtIHNlcm1heWVuaW4gbWFrc2ltdW0gJTEtMlwnc2kgcmlza2UgZWRpbGlyLid9LAogICB7dDonU3RvcC1Mb3NzIERpc2lwbGluaScsZDonU3RvcCBzZXZpeWVzaSBiYXogZm9ybWFzeW9udW51biBkaWJpbmluIGFsdGluYSBrb251ci4gSGVyIGRlZmFzaW5kYSB1eXVsdXIuJ30sCiAgIHt0OidQb3ppc3lvbiBCdXl1a2x1Z3UnLGQ6Jz0gKFNlcm1heWUgeCAlUmlzaykgLyAoR2lyaXMgLSBTdG9wKS4gTWF0ZW1hdGlrbGUgaGVzYXBsYW5pci4nfSwKICAge3Q6J0Vhcm5pbmdzIEt1cmFsaScsZDonUmFwb3IgdGFyaWhpbmRlbiAxLTIgaGFmdGEgb25jZSB5ZW5pIHBvemlzeW9uIGFzaWxtYXouJ30sCiAgIHt0OidQaXJhbWl0bGVtZScsZDonSWxrIHBvemlzeW9uIGt1Y3VrLiBGaXlhdCBkb2dydSB5b25kZSBnaWRlcnNlIGVrIGFsaW0geWFwaWxpci4nfSwKICAge3Q6J1BpeWFzYSBZb251JyxkOidEdXplbHRtZSBkb25lbWluZGUgeWVuaSBwb3ppc3lvbiBhc2lsbWF6LiBTYWRlY2UgRm9sbG93LVRocm91Z2ggRGF5IHNvbnJhc2kuJ30KICBdLmZvckVhY2goZnVuY3Rpb24oeCl7CiAgICBoKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEycHgiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4Ij4nK3gudCsnPC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjojOTRhM2I4O2xpbmUtaGVpZ2h0OjEuNSI+Jyt4LmQrJzwvZGl2PjwvZGl2Pic7CiAgfSk7CiAgaCArPSAnPC9kaXY+PC9kaXY+PC9kaXY+JzsKICBncmlkLmlubmVySFRNTCA9IGg7Cn0KCmZ1bmN0aW9uIHJlbmRlclZhbHVhdGlvbigpewogIHZhciBjb250YWluZXIgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogIGlmKCFjb250YWluZXIpIHJldHVybjsKICBjb250YWluZXIuc3R5bGUuZGlzcGxheSA9ICdibG9jayc7CiAgY29udGFpbmVyLnN0eWxlLndpZHRoID0gJzEwMCUnOwoKICAvLyBUb29sdGlwIHBvcHVwIEpTICh0aXRsZSB5ZXJpbmUpCiAgZnVuY3Rpb24gc2hvd1RpcChlLCB0eHQpewogICAgdmFyIHRpcCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCd2YWwtdG9vbHRpcCcpOwogICAgaWYoIXRpcCl7IHRpcD1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsgdGlwLmlkPSd2YWwtdG9vbHRpcCc7CiAgICAgIHRpcC5zdHlsZS5jc3NUZXh0PSdwb3NpdGlvbjpmaXhlZDtiYWNrZ3JvdW5kOiMxZTI5M2I7Ym9yZGVyOjFweCBzb2xpZCAjMzc0MTUxO2NvbG9yOiNlMmU4ZjA7cGFkZGluZzoxMHB4IDE0cHg7Ym9yZGVyLXJhZGl1czo4cHg7Zm9udC1zaXplOjExcHg7bGluZS1oZWlnaHQ6MS42O21heC13aWR0aDoyNjBweDt6LWluZGV4Ojk5OTk7cG9pbnRlci1ldmVudHM6bm9uZTtib3gtc2hhZG93OjAgNHB4IDIwcHggcmdiYSgwLDAsMCwuNCknOwogICAgICBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKHRpcCk7IH0KICAgIHRpcC5pbm5lckhUTUwgPSB0eHQ7CiAgICB0aXAuc3R5bGUuZGlzcGxheSA9ICdibG9jayc7CiAgICB0aXAuc3R5bGUubGVmdCA9IE1hdGgubWluKGUuY2xpZW50WCsxMiwgd2luZG93LmlubmVyV2lkdGgtMjgwKSsncHgnOwogICAgdGlwLnN0eWxlLnRvcCA9IChlLmNsaWVudFktMTApKydweCc7CiAgfQogIGZ1bmN0aW9uIGhpZGVUaXAoKXsgdmFyIHQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3ZhbC10b29sdGlwJyk7IGlmKHQpIHQuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH0KCiAgdmFyIGNvbnRhaW5lciA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgaWYoIWNvbnRhaW5lcikgcmV0dXJuOwogIC8vIE92ZXJyaWRlIGdyaWQgbGF5b3V0IHNvIHRhYmxlIHNwYW5zIGZ1bGwgd2lkdGgKICBjb250YWluZXIuc3R5bGUuZGlzcGxheSA9ICdibG9jayc7CiAgY29udGFpbmVyLnN0eWxlLndpZHRoID0gJzEwMCUnOwogIGNvbnRhaW5lci5pbm5lckhUTUwgPSAnPGRpdiBzdHlsZT0icGFkZGluZzoxNnB4O3dpZHRoOjEwMCU7Ym94LXNpemluZzpib3JkZXItYm94Ij4nCiAgICArJzxoMiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO21hcmdpbi1ib3R0b206OHB4Ij7wn5KOIERlxJ9lcmxlbWUgQW5hbGl6aTwvaDI+JwogICAgKyc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoOTYsMTY1LDI1MCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSg5NiwxNjUsMjUwLC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4IDE2cHg7bWFyZ2luLWJvdHRvbToxNnB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOiM5NGEzYjg7bGluZS1oZWlnaHQ6MS45Ij4nCiAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjojNjBhNWZhO21hcmdpbi1ib3R0b206OHB4Ij7wn5OWIEJ1IFNheWZhecSxIE5hc8SxbCBPa3VtYWzEsXPEsW4/PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDI4MHB4LDFmcikpO2dhcDo4cHgiPicKICAgICsnPGRpdj48c3Ryb25nIHN0eWxlPSJjb2xvcjp2YXIoLS10ZXh0KSI+MS4gw5ZuY2UgcmVua2xlcmUgYmFrOjwvc3Ryb25nPiBZZcWfaWwgPSBpeWksIFNhcsSxID0gZGlra2F0IGV0LCBLxLFybcSxesSxID0gemF5xLFmLiBIaXNzZW5pbiBzYXTEsXLEsSDDp2/En3VubHVrbGEgeWXFn2lsc2UgZ8O8w6dsw7wsIGvEsXJtxLF6xLF5c2Egc29ydW5sdSBkZW1la3Rpci48L2Rpdj4nCiAgICArJzxkaXY+PHN0cm9uZyBzdHlsZT0iY29sb3I6dmFyKC0tdGV4dCkiPjIuIEVQUyUgdmUgR2VsaXIlIGtyaXRpazo8L3N0cm9uZz4gQ0FOU0xJTSBtZXRvZG9sb2ppc2luZGUga2F6YW7DpyB2ZSBnZWxpciBiw7x5w7xtZXNpIGVuIMO2bmVtbGkgaWtpIGZha3TDtnJkw7xyLiBCdSBpa2lzaSB5ZcWfaWwgZGXEn2lsc2UgZGnEn2VybGVyaSBpa2luY2kgcGxhbmRhZMSxci48L2Rpdj4nCiAgICArJzxkaXY+PHN0cm9uZyBzdHlsZT0iY29sb3I6dmFyKC0tdGV4dCkiPjMuIFBFRyBlbiBkZW5nZWxpIG1ldHJpazo8L3N0cm9uZz4gMSBhbHTEsSB1Y3V6LCAxLTIgbWFrdWwsIDIgw7xzdMO8IHBhaGFsxLEuIEhlbSBiw7x5w7xtZXlpIGhlbSBmaXlhdMSxIGJpciBhcmFkYSBkZcSfZXJsZW5kaXJpci48L2Rpdj4nCiAgICArJzxkaXY+PHN0cm9uZyBzdHlsZT0iY29sb3I6dmFyKC0tdGV4dCkiPjQuIEFuYWxpc3QgSGVkZWZpIHNvbiBrb250cm9sOjwvc3Ryb25nPiBNZXZjdXQgZml5YXR0YW4gecO8a3Nla3NlIHllxZ9pbCDigJQga3VydW1sYXLEsW4gYmVrbGVudGlzaW5pIGfDtnN0ZXJpci4gVGVrIGJhxZ/EsW5hIGFsxLFtIHNpbnlhbGkgZGXEn2lsZGlyLjwvZGl2PicKICAgICsnPGRpdj48c3Ryb25nIHN0eWxlPSJjb2xvcjp2YXIoLS10ZXh0KSI+NS4gU29ydSBpxZ9hcmV0aW5lIHTEsWtsYTo8L3N0cm9uZz4gSGVyIHPDvHR1biBiYcWfbMSxxJ/EsW5kYWtpIDxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoOTYsMTY1LDI1MCwuMik7Y29sb3I6IzYwYTVmYTtib3JkZXItcmFkaXVzOjUwJTt3aWR0aDoxNHB4O2hlaWdodDoxNHB4O2Rpc3BsYXk6aW5saW5lLWZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDAiPj88L3NwYW4+IGlrb251bmEgZmFyZSBpbGUgZ2VsIOKAlCBvIG1ldHJpxJ9pbiBuZSBhbmxhbWEgZ2VsZGnEn2luaSB2ZSBpZGVhbCBkZcSfZXIgYXJhbMSxxJ/EsW7EsSBnw7Zyw7xyc8O8bi48L2Rpdj4nCiAgICArJzwvZGl2PicKICAgICsnPC9kaXY+JwogICAgKyc8ZGl2IGlkPSJ2YWx1YXRpb24tZ3JpZCIgc3R5bGU9IndpZHRoOjEwMCU7b3ZlcmZsb3cteDphdXRvOy13ZWJraXQtb3ZlcmZsb3ctc2Nyb2xsaW5nOnRvdWNoIj48L2Rpdj48L2Rpdj4nOwogIHZhciBjb250YWluZXIgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgndmFsdWF0aW9uLWdyaWQnKTsKICBpZighY29udGFpbmVyKSByZXR1cm47CiAgdmFyIGRhdGEgPSAoVEZfREFUQSAmJiBURl9EQVRBWycxZCddKSA/IFRGX0RBVEFbJzFkJ10gOiBbXTsKICBpZighZGF0YS5sZW5ndGgpe2NvbnRhaW5lci5pbm5lckhUTUw9JzxwIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCk7cGFkZGluZzoyMHB4Ij5WZXJpIHlvazwvcD4nO3JldHVybjt9CgogIHZhciBtZXRyaWNzID0gWwogICAge2tleTonZXBzX2dyb3d0aCcsICAgbGFiZWw6J0VQUyUnLCAgICBkZXNjOidTb24gY2V5cmVrIEVQUyBidXl1bWUgb3JhbmkgKHlpbGxpaykuIENBTlNMSU0gQyBrcml0ZXJpIOKAlCBlbiBrcml0aWsgbWV0cmlrLiBTZWt0b3J1bmRlIGxpZGVyIGthemFuYyBhcnRpc2kgbGF6aW0uJywgIGlkZWFsOic+MjAlIGlkZWFsLCA+MzAlIGd1Y2x1JywgICAgICAgICBsbzoyMCwgaGk6MTAwLCBmbXQ6JyUnLCBoYjp0cnVlfSwKICAgIHtrZXk6J3Jldl9ncm93dGgnLCAgIGxhYmVsOidHZWxpciUnLCAgZGVzYzonU29uIGNleXJlayBnZWxpciBidXl1bWUgb3JhbmkuIENBTlNMSU0gQSBrcml0ZXJpLiBTaXJrZXRpbiBwYXphciBwYXlpbmkgdmUgbW9tZW50dW0gZ3VjdW51IGdvc3RlcmlyLicsICAgICAgICAgICAgICAgIGlkZWFsOic+MTUlIGl5aSwgPjI1JSBndWNsdScsICAgICAgICAgICBsbzoxNSwgaGk6MTAwLCBmbXQ6JyUnLCBoYjp0cnVlfSwKICAgIHtrZXk6J3BlX2Z3ZCcsICAgIGxhYmVsOidJbGVyaSBGL0snLCAgZGVzYzonT251bcO8emRla2kgMTIgYXkgdGFobWluaSBrYXphbmNpbmEgZ29yZSBGL0suIFBpeWFzYW5pbiBidXl1bWUgYmVrbGVudGlzaW5pIHlhbnNpdGlyLiBCdXl1bWV5bGUga2Fyc2lsYXN0aXJtYWsgb25lbWxpLicsIGlkZWFsOic8MjUgaWRlYWwsIDwzNSBrYWJ1bCcsICAgICAgICAgIGxvOjAsICBoaToyNSwgIGZtdDoneCcsIGhiOmZhbHNlfSwKICAgIHtrZXk6J3BlZycsICAgICAgIGxhYmVsOidQRUcnLCAgICAgICAgZGVzYzonRi9LIG9yYW5pbmkgRVBTIGJ1eXVtZSBoaXppIGlsZSBrYXJzaWxhc3RpcmlyLiBFbiBkZW5nZWxpIGRlZ2VybGVtZSBtZXRyacSfaTogMSBhbHRpbmRhIHVjdXosIDEtMiBtYWt1bCwgMiB1c3R1IHBhaGFsaS4nLCBpZGVhbDonPDEgVWN1eiwgMS0yIE1ha3VsLCA+MiBQYWhhbGknLCBsbzowLCBoaToyLCAgIGZtdDoneCcsIGhiOmZhbHNlfSwKICAgIHtrZXk6J2dyb3NzX21hcmdpbicsIGxhYmVsOidCcnV0JScsICAgZGVzYzonQnJ1dCBrYXIgbWFyamluaS4gU2lya2V0aW4gZml5YXRsYW1hIGd1Y3VudSB2ZSB1cnVuIGthbGl0ZXNpbmkgZ29zdGVyaXIuIFl1a3NlayBtYXJqaW4gcmVrYWJldCB1c3R1bmx1Z3UgaXNhcmV0bGVyLicsICAgaWRlYWw6J1lhemlsaW0gPjcwJSwgR2VuZWwgPjQwJScsICAgICAgIGxvOjQwLCBoaToxMDAsIGZtdDonJScsIGhiOnRydWV9LAogICAge2tleTonbmV0X21hcmdpbicsICAgbGFiZWw6J05ldCUnLCAgICBkZXNjOidOZXQga2FyIG1hcmppbmkuIFR1bSBnaWRlcmxlciBkdXN1bGR1a3RlbiBzb25yYSBrYWxhbiBrYXIgeXV6ZGVzaS4gT3BlcmFzeW9uZWwgdmVyaW1saWxpZ2kgZ29zdGVyaXIuJywgICAgICAgICAgICAgICAgICBpZGVhbDonPjEwJSBpeWksID4yMCUgbXVrZW1tZWwnLCAgICAgICAgbG86MTAsIGhpOjEwMCwgZm10OiclJywgaGI6dHJ1ZX0sCiAgICB7a2V5Oidyb2UnLCAgICAgICAgICBsYWJlbDonT0tHJywgICAgIGRlc2M6J096c2VybWF5ZSBLYXJsaWxpZ2kgKFJPRSkuIENBTlNMSU0gTiBrcml0ZXJpOiB5b25ldGltaW4gc2VybWF5ZXlpIG5lIGthZGFyIHZlcmltbGkga3VsbGFuZGlnaW5pIG9sY2VyLicsICAgICAgICAgICAgICAgaWRlYWw6Jz4xNSUgaXlpLCA+MjUlIG11a2VtbWVsJywgICAgICAgIGxvOjE1LCBoaToxMDAsIGZtdDonJScsIGhiOnRydWV9LAogICAge2tleToncGVfdHRtJywgICAgbGFiZWw6J0YvSycsICAgICAgICBkZXNjOidTb24gMTIgYXkgZ2VyY2VrIGthemFuY2luYSBnb3JlIGZpeWF0L2themFuYyBvcmFuaS4gVGFyaWhpIGthcnNpbGFzdGlybWEgaWNpbiBrdWxsYW5pbGlyLicsICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlkZWFsOidUZWtub2xvamkgPDM1LCBHZW5lbCA8MjUnLCAgICAgICBsbzowLCAgaGk6MzUsICBmbXQ6J3gnLCBoYjpmYWxzZX0sCiAgICB7a2V5OidwcycsICAgICAgICBsYWJlbDonRi9TJywgICAgICAgIGRlc2M6J0ZpeWF0IC8gU2F0aXNsYXIuIEhlbnV6IGthcnNpeiB2ZXlhIGhpemxpIGJ1eXV5ZW4gc2lya2V0bGVyaSBkZWdlcmxlbmRpcm1layBpY2luIGt1bGxhbmlsaXIuJywgICAgICAgICAgICAgICAgICAgICAgICAgaWRlYWw6J1Rla25vbG9qaSA8OCwgR2VuZWwgPDMnLCAgICAgICAgIGxvOjAsICBoaTo4LCAgIGZtdDoneCcsIGhiOmZhbHNlfSwKICAgIHtrZXk6J3BiJywgICAgICAgIGxhYmVsOidGL0REJywgICAgICAgZGVzYzonRml5YXQgLyBEZWZ0ZXIgRGVnZXJpLiBTaXJrZXRpbiBuZXQgdmFybGlrbGFyaW5hIGdvcmUgZml5YXRpbmkgZ29zdGVyaXIuIE5lZ2F0aWYgb3pzZXJtYXllZGUgYW5sYW1zaXpkaXIuJywgICAgICAgICAgICBpZGVhbDonPDMgVWN1eiwgMy03IE1ha3VsLCA+NyBQYWhhbGknLCBsbzowLCAgaGk6NSwgICBmbXQ6J3gnLCBoYjpmYWxzZX0sCiAgICB7a2V5OidhbmFseXN0X3RhcmdldCcsIGxhYmVsOidIZWRlZicsIGRlc2M6J0FuYWxpc3Qga29uc2Vuc3VzIGhlZGVmIGZpeWF0aS4gWXV6ZGUgdXBzaWRlIG1ldmN1dCBmaXlhdGEgZ29yZSBoZXNhcGxhbm1pc3Rpci4gU29uIGtvbnRyb2wgbm9rdGFzaS4nLCAgICAgICAgICAgICAgICAgaWRlYWw6J01ldmN1dCBmaXlhdHRhbiB5dWtzZWsgb2xzdW4nLCAgIGxvOjAsICBoaTowLCAgIGZtdDonJCcsIGhiOnRydWV9LAogIF07CgogIGZ1bmN0aW9uIHRpcChsYmwsZGVzYyxpZGVhbCl7CiAgICB2YXIgdGlwVHh0ID0gJzxzdHJvbmc+JytsYmwrJzwvc3Ryb25nPjxicj4nK2Rlc2MrJzxicj48YnI+PHNwYW4gc3R5bGU9ImNvbG9yOiNmNTllMGIiPsSwZGVhbDogJytpZGVhbCsnPC9zcGFuPic7CiAgICB2YXIgdGlwRW5jID0gdGlwVHh0LnJlcGxhY2UoLycvZywnJiMzOTsnKTsKICAgIHJldHVybiBsYmwrJzxzcGFuIG9ubW91c2VlbnRlcj0ic2hvd1RpcChldmVudCxcJycgKyB0aXBFbmMgKyAnXCcpIiBvbm1vdXNlbGVhdmU9ImhpZGVUaXAoKSIgc3R5bGU9ImN1cnNvcjpoZWxwO3dpZHRoOjE0cHg7aGVpZ2h0OjE0cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpyZ2JhKDk2LDE2NSwyNTAsLjIpO2NvbG9yOiM2MGE1ZmE7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7ZGlzcGxheTppbmxpbmUtZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjttYXJnaW4tbGVmdDozcHg7ZmxleC1zaHJpbms6MDt2ZXJ0aWNhbC1hbGlnbjptaWRkbGUiPj88L3NwYW4+JzsKICB9CiAgZnVuY3Rpb24gY29sT2YodmFsLGxvLGhpLGhiKXsKICAgIGlmKHZhbD09PW51bGx8fHZhbD09PXVuZGVmaW5lZClyZXR1cm4gJ3ZhcigtLW11dGVkKSc7CiAgICB2YXIgbj1wYXJzZUZsb2F0KHZhbCk7aWYoaXNOYU4obikpcmV0dXJuICd2YXIoLS1tdXRlZCknOwogICAgaWYoaGIpe3JldHVybiBuPj1oaSowLjc/J3ZhcigtLWdyZWVuKSc6bj49bG8/J3ZhcigtLXllbGxvdyknOid2YXIoLS1yZWQyKSc7fQogICAgZWxzZSAge3JldHVybiBuPD1sbyoxLjI/J3ZhcigtLWdyZWVuKSc6bjw9aGk/J3ZhcigtLXllbGxvdyknOid2YXIoLS1yZWQyKSc7fQogIH0KICBmdW5jdGlvbiBmbXRWKHZhbCxmbXQscHJpY2UpewogICAgaWYodmFsPT09bnVsbHx8dmFsPT09dW5kZWZpbmVkKXJldHVybiAnPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+4oCUPC9zcGFuPic7CiAgICB2YXIgbj1wYXJzZUZsb2F0KHZhbCk7aWYoaXNOYU4obikpcmV0dXJuICc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj7igJQ8L3NwYW4+JzsKICAgIGlmKGZtdD09PSd4JylyZXR1cm4gbi50b0ZpeGVkKDEpKyd4JzsKICAgIGlmKGZtdD09PSclJylyZXR1cm4gbi50b0ZpeGVkKDEpKyclJzsKICAgIGlmKGZtdD09PSckJyl7CiAgICAgIHZhciB1cD1wcmljZT4wPygobi1wcmljZSkvcHJpY2UqMTAwKS50b0ZpeGVkKDEpOm51bGw7CiAgICAgIHZhciBjPSh1cCE9PW51bGwmJnBhcnNlRmxvYXQodXApPjApPyd2YXIoLS1ncmVlbiknOid2YXIoLS1yZWQyKSc7CiAgICAgIHJldHVybiAnJCcrbi50b0ZpeGVkKDApKyh1cCE9PW51bGw/JyA8c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjonK2MrJyI+JysocGFyc2VGbG9hdCh1cCk+MD8nKyc6JycpK3VwKyclPC9zcGFuPic6JycpOwogICAgfQogICAgcmV0dXJuIFN0cmluZyhuKTsKICB9CgogIHZhciByb3dzPWRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pOwogIHZhciBodG1sPSc8dGFibGUgc3R5bGU9IndpZHRoOjEwMCU7Ym9yZGVyLWNvbGxhcHNlOmNvbGxhcHNlO2ZvbnQtc2l6ZToxMXB4O21pbi13aWR0aDo3MDBweCI+JzsKICBodG1sKz0nPHRoZWFkPjx0ciBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpIj4nOwogIGh0bWwrPSc8dGggc3R5bGU9InRleHQtYWxpZ246bGVmdDtwYWRkaW5nOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtd2VpZ2h0OjYwMCI+SGlzc2U8L3RoPic7CiAgaHRtbCs9Jzx0aCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjEwcHggOHB4O2NvbG9yOnZhcigtLW11dGVkKTtmb250LXdlaWdodDo2MDAiPkZpeWF0PC90aD4nOwogIG1ldHJpY3MuZm9yRWFjaChmdW5jdGlvbihtbSl7aHRtbCs9Jzx0aCBzdHlsZT0idGV4dC1hbGlnbjpyaWdodDtwYWRkaW5nOjhweCA0cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtd2VpZ2h0OjYwMDt3aGl0ZS1zcGFjZTpub3dyYXA7Zm9udC1zaXplOjEwcHgiPicrdGlwKG1tLmxhYmVsLG1tLmRlc2MsbW0uaWRlYWwpKyc8L3RoPic7fSk7CiAgaHRtbCs9JzwvdHI+PC90aGVhZD48dGJvZHk+JzsKCiAgcm93cy5mb3JFYWNoKGZ1bmN0aW9uKHIsaSl7CiAgICB2YXIgYmc9aSUyPT09MD8ndmFyKC0tYmcpJzoncmdiYSgyNTUsMjU1LDI1NSwuMDIpJzsKICAgIHZhciBpblA9ci5wb3J0Zm9saW87CiAgICBodG1sKz0nPHRyIHN0eWxlPSJiYWNrZ3JvdW5kOicrYmcrJztib3JkZXItYm90dG9tOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wMykiPic7CiAgICBodG1sKz0nPHRkIHN0eWxlPSJwYWRkaW5nOjEwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrKGluUD8ndmFyKC0tZ3JlZW4pJzondmFyKC0tdGV4dCknKSsnIj4nK3IudGlja2VyKyhpblA/JzxzcGFuIHN0eWxlPSJmb250LXNpemU6OHB4O2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6MXB4IDRweDtib3JkZXItcmFkaXVzOjNweDttYXJnaW4tbGVmdDo0cHgiPlA8L3NwYW4+JzonJykrJzwvdGQ+JzsKICAgIGh0bWwrPSc8dGQgc3R5bGU9InRleHQtYWxpZ246cmlnaHQ7cGFkZGluZzo4cHggNHB4O2NvbG9yOnZhcigtLXRleHQpO2ZvbnQtd2VpZ2h0OjYwMDtmb250LXNpemU6MTBweCI+JCcrci5maXlhdCsnPC90ZD4nOwogICAgbWV0cmljcy5mb3JFYWNoKGZ1bmN0aW9uKG1tKXsKICAgICAgdmFyIHZhbD1tbS5rZXk9PT0nYW5hbHlzdF90YXJnZXQnP3IuZmFpcl9wcmljZV9hbmFseXN0OnJbbW0ua2V5XTsKICAgICAgdmFyIGNvbD1tbS5rZXk9PT0nYW5hbHlzdF90YXJnZXQnPyhyLmZhaXJfcHJpY2VfYW5hbHlzdCYmci5mYWlyX3ByaWNlX2FuYWx5c3Q+ci5maXlhdD8ndmFyKC0tZ3JlZW4pJzondmFyKC0tcmVkMiknKTpjb2xPZih2YWwsbW0ubG8sbW0uaGksbW0uaGIpOwogICAgICBodG1sKz0nPHRkIHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0O3BhZGRpbmc6MTBweCA4cHg7Y29sb3I6Jytjb2wrJyI+JytmbXRWKHZhbCxtbS5mbXQsci5maXlhdCkrJzwvdGQ+JzsKICAgIH0pOwogICAgaHRtbCs9JzwvdHI+JzsKICB9KTsKCiAgaHRtbCs9JzwvdGJvZHk+PC90YWJsZT4nOwogIGh0bWwrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjE2cHg7bWFyZ2luLXRvcDoxMHB4O2ZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+JzsKICBodG1sKz0nPHNwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKSI+4pePPC9zcGFuPiBJeWk8L3NwYW4+JzsKICBodG1sKz0nPHNwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXllbGxvdykiPuKXjzwvc3Bhbj4gTWFrdWw8L3NwYW4+JzsKICBodG1sKz0nPHNwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpIj7il488L3NwYW4+IERpa2thdDwvc3Bhbj4nOwogIGh0bWwrPSc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj7igJQgPSBWZXJpIHlvazwvc3Bhbj4nOwogIGh0bWwrPSc8c3BhbiBzdHlsZT0ibWFyZ2luLWxlZnQ6YXV0byI+PHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Y29sb3I6dmFyKC0tZ3JlZW4pO3BhZGRpbmc6MXB4IDRweDtib3JkZXItcmFkaXVzOjNweCI+UDwvc3Bhbj4gUG9ydGZveTwvc3Bhbj48L2Rpdj4nOwogIGNvbnRhaW5lci5pbm5lckhUTUw9aHRtbDsKfQo8L3NjcmlwdD4KCjwvYm9keT4KPC9odG1sPg=="
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
