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
    _T = "PCFET0NUWVBFIGh0bWw+CjxodG1sIGxhbmc9InRyIj4KPGhlYWQ+CjxtZXRhIGNoYXJzZXQ9IlVURi04Ii8+CjxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsaW5pdGlhbC1zY2FsZT0xIi8+Cjx0aXRsZT5DQU5TTElNIFNjYW5uZXI8L3RpdGxlPgo8bGluayByZWw9Imljb24iIHR5cGU9ImltYWdlL3N2Zyt4bWwiIGhyZWY9ImRhdGE6aW1hZ2Uvc3ZnK3htbCwlM0NzdmcgeG1sbnM9J2h0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnJyB2aWV3Qm94PScwIDAgMzIgMzInJTNFJTNDcmVjdCB3aWR0aD0nMzInIGhlaWdodD0nMzInIHJ4PSc2JyBmaWxsPSclMjMwZDExMTcnLyUzRSUzQ3BvbHlsaW5lIHBvaW50cz0nNCwyNCAxMCwxNiAxNiwyMCAyMiwxMCAyOCwxNCcgZmlsbD0nbm9uZScgc3Ryb2tlPSclMjMxMGI5ODEnIHN0cm9rZS13aWR0aD0nMi41JyBzdHJva2UtbGluZWNhcD0ncm91bmQnIHN0cm9rZS1saW5lam9pbj0ncm91bmQnLyUzRSUzQy9zdmclM0UiPgo8bGluayBocmVmPSJodHRwczovL2ZvbnRzLmdvb2dsZWFwaXMuY29tL2NzczI/ZmFtaWx5PVNwYWNlK0dyb3Rlc2s6d2dodEA0MDA7NTAwOzYwMDs3MDAmZmFtaWx5PUJlYmFzK05ldWUmZmFtaWx5PUpldEJyYWlucytNb25vOndnaHRANDAwOzYwMCZkaXNwbGF5PXN3YXAiIHJlbD0ic3R5bGVzaGVldCIvPgo8c2NyaXB0IHNyYz0iaHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9jaGFydC5qc0A0LjQuMC9kaXN0L2NoYXJ0LnVtZC5taW4uanMiPjwvc2NyaXB0Pgo8c3R5bGU+Cjpyb290ey0tYmc6IzA1MDcwZjstLWJnMjojMGQxMTE3Oy0tYmczOiMxNjFiMjQ7LS1ib3JkZXI6cmdiYSgyNTUsMjU1LDI1NSwwLjA4KTstLXRleHQ6I2UyZThmMDstLW11dGVkOiM0YjU1NjM7LS1ncmVlbjojMTBiOTgxOy0tZ3JlZW4yOiMzNGQzOTk7LS1yZWQ6I2VmNDQ0NDstLXJlZDI6I2Y4NzE3MTstLXllbGxvdzojZjU5ZTBiO30KKntib3gtc2l6aW5nOmJvcmRlci1ib3g7bWFyZ2luOjA7cGFkZGluZzowfQpib2R5e2JhY2tncm91bmQ6dmFyKC0tYmcpO2NvbG9yOnZhcigtLXRleHQpO2ZvbnQtZmFtaWx5OidTcGFjZSBHcm90ZXNrJyxzYW5zLXNlcmlmO21pbi1oZWlnaHQ6MTAwdmh9Ci5oZWFkZXJ7YmFja2dyb3VuZDpsaW5lYXItZ3JhZGllbnQoMTM1ZGVnLCMwZDExMTcsIzExMTgyNyk7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtwYWRkaW5nOjE0cHggMjBweDtwb3NpdGlvbjpzdGlja3k7dG9wOjA7ei1pbmRleDoxMDB9Ci5oZWFkZXItaW5uZXJ7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtmbGV4LXdyYXA6d3JhcDtnYXA6MTBweDttYXgtd2lkdGg6MTQwMHB4O21hcmdpbjowIGF1dG99Ci5sb2dvLW1haW57Zm9udC1mYW1pbHk6J0JlYmFzIE5ldWUnLHNhbnMtc2VyaWY7Zm9udC1zaXplOjIycHg7bGV0dGVyLXNwYWNpbmc6NHB4O2JhY2tncm91bmQ6bGluZWFyLWdyYWRpZW50KDEzNWRlZywjMTBiOTgxLCMzYjgyZjYpOy13ZWJraXQtYmFja2dyb3VuZC1jbGlwOnRleHQ7LXdlYmtpdC10ZXh0LWZpbGwtY29sb3I6dHJhbnNwYXJlbnR9Ci50aW1lc3RhbXB7Zm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLmxpdmUtZG90e3dpZHRoOjdweDtoZWlnaHQ6N3B4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6dmFyKC0tZ3JlZW4pO2FuaW1hdGlvbjpwdWxzZSAycyBpbmZpbml0ZTtkaXNwbGF5OmlubGluZS1ibG9jazttYXJnaW4tcmlnaHQ6NXB4fQpAa2V5ZnJhbWVzIHB1bHNlezAlLDEwMCV7b3BhY2l0eToxO2JveC1zaGFkb3c6MCAwIDAgMCByZ2JhKDE2LDE4NSwxMjksLjQpfTUwJXtvcGFjaXR5Oi43O2JveC1zaGFkb3c6MCAwIDAgNnB4IHJnYmEoMTYsMTg1LDEyOSwwKX19Ci5uYXZ7ZGlzcGxheTpmbGV4O2dhcDo0cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7b3ZlcmZsb3cteDphdXRvO2ZsZXgtd3JhcDp3cmFwfQoudGFie3BhZGRpbmc6NnB4IDE0cHg7Ym9yZGVyLXJhZGl1czo2cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NTAwO2JvcmRlcjoxcHggc29saWQgdHJhbnNwYXJlbnQ7YmFja2dyb3VuZDpub25lO2NvbG9yOnZhcigtLW11dGVkKTt0cmFuc2l0aW9uOmFsbCAuMnM7d2hpdGUtc3BhY2U6bm93cmFwfQoudGFiOmhvdmVye2NvbG9yOnZhcigtLXRleHQpO2JhY2tncm91bmQ6dmFyKC0tYmczKX0KLnRhYi5hY3RpdmV7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLXRleHQpO2JvcmRlci1jb2xvcjp2YXIoLS1ib3JkZXIpfQoudGFiLnBvcnQuYWN0aXZle2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyLWNvbG9yOnJnYmEoMTYsMTg1LDEyOSwuMyl9Ci50Zi1yb3d7ZGlzcGxheTpmbGV4O2dhcDo2cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7YWxpZ24taXRlbXM6Y2VudGVyO2ZsZXgtd3JhcDp3cmFwfQoudGYtYnRue3BhZGRpbmc6NXB4IDEycHg7Ym9yZGVyLXJhZGl1czo2cHg7Zm9udC1zaXplOjExcHg7Y3Vyc29yOnBvaW50ZXI7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO3RyYW5zaXRpb246YWxsIC4yc30KLnRmLWJ0bi5hY3RpdmV7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtjb2xvcjojNjBhNWZhO2JvcmRlci1jb2xvcjpyZ2JhKDU5LDEzMCwyNDYsLjQpfQoudGYtYnRuLnN0YXJ7cG9zaXRpb246cmVsYXRpdmV9Ci50Zi1idG4uc3Rhcjo6YWZ0ZXJ7Y29udGVudDon4piFJztwb3NpdGlvbjphYnNvbHV0ZTt0b3A6LTVweDtyaWdodDotNHB4O2ZvbnQtc2l6ZTo4cHg7Y29sb3I6dmFyKC0teWVsbG93KX0KLnRmLWhpbnR7Zm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpfQouc3RhdHN7ZGlzcGxheTpmbGV4O2dhcDo4cHg7cGFkZGluZzoxMHB4IDIwcHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tYm9yZGVyKTtiYWNrZ3JvdW5kOnZhcigtLWJnMik7ZmxleC13cmFwOndyYXB9Ci5waWxse2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjVweDtwYWRkaW5nOjRweCAxMHB4O2JvcmRlci1yYWRpdXM6MjBweDtmb250LXNpemU6MTFweDtmb250LXdlaWdodDo2MDA7Ym9yZGVyOjFweCBzb2xpZH0KLnBpbGwuZ3tiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMSk7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlci1jb2xvcjpyZ2JhKDE2LDE4NSwxMjksLjI1KX0KLnBpbGwucntiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xKTtjb2xvcjp2YXIoLS1yZWQyKTtib3JkZXItY29sb3I6cmdiYSgyMzksNjgsNjgsLjI1KX0KLnBpbGwueXtiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMSk7Y29sb3I6dmFyKC0teWVsbG93KTtib3JkZXItY29sb3I6cmdiYSgyNDUsMTU4LDExLC4yNSl9Ci5waWxsLmJ7YmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjEpO2NvbG9yOiM2MGE1ZmE7Ym9yZGVyLWNvbG9yOnJnYmEoNTksMTMwLDI0NiwuMjUpfQoucGlsbC5te2JhY2tncm91bmQ6dmFyKC0tYmczKTtjb2xvcjp2YXIoLS1tdXRlZCk7Ym9yZGVyLWNvbG9yOnZhcigtLWJvcmRlcil9Ci5kb3R7d2lkdGg6NXB4O2hlaWdodDo1cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpjdXJyZW50Q29sb3J9Ci5tYWlue3BhZGRpbmc6MTRweCAyMHB4O21heC13aWR0aDoxNDAwcHg7bWFyZ2luOjAgYXV0b30KLmdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgzMDBweCwxZnIpKTtnYXA6MTBweH0KQG1lZGlhKG1heC13aWR0aDo0ODBweCl7LmdyaWR7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmcn19Ci5jYXJke2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O292ZXJmbG93OmhpZGRlbjtjdXJzb3I6cG9pbnRlcjt0cmFuc2l0aW9uOmFsbCAuMnN9Ci5jYXJkOmhvdmVye3RyYW5zZm9ybTp0cmFuc2xhdGVZKC0ycHgpO2JveC1zaGFkb3c6MCA4cHggMjRweCByZ2JhKDAsMCwwLC40KX0KLmFjY2VudHtoZWlnaHQ6M3B4fQouY2JvZHl7cGFkZGluZzoxMnB4IDE0cHh9Ci5jdG9we2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpmbGV4LXN0YXJ0O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206OHB4fQoudGlja2Vye2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyMHB4O2xldHRlci1zcGFjaW5nOjJweDtsaW5lLWhlaWdodDoxfQouY3Bye3RleHQtYWxpZ246cmlnaHR9Ci5wdmFse2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTVweDtmb250LXdlaWdodDo2MDB9Ci5wY2hne2ZvbnQtc2l6ZToxMXB4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTttYXJnaW4tdG9wOjJweH0KLmJhZGdle2Rpc3BsYXk6aW5saW5lLWJsb2NrO3BhZGRpbmc6MnB4IDhweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6MTBweDtmb250LXdlaWdodDo3MDA7bGV0dGVyLXNwYWNpbmc6LjVweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLXRvcDozcHh9Ci5wb3J0LWJhZGdle2Rpc3BsYXk6aW5saW5lLWZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDozcHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwO2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xMik7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yNSk7bWFyZ2luLWxlZnQ6NXB4fQouc2lnc3tkaXNwbGF5OmZsZXg7ZmxleC13cmFwOndyYXA7Z2FwOjNweDttYXJnaW4tYm90dG9tOjhweH0KLnNwe2ZvbnQtc2l6ZTo5cHg7cGFkZGluZzoycHggNnB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZX0KLnNne2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xKTtjb2xvcjp2YXIoLS1ncmVlbjIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKX0KLnNie2JhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjEpO2NvbG9yOnZhcigtLXJlZDIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpfQouc257YmFja2dyb3VuZDp2YXIoLS1iZzMpO2NvbG9yOnZhcigtLW11dGVkKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5jaGFydC13e2hlaWdodDo3NXB4O21hcmdpbi10b3A6OHB4fQoubHZsc3tkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdCgzLDFmcik7Z2FwOjVweDttYXJnaW4tdG9wOjhweH0KLmx2e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjVweDtwYWRkaW5nOjZweDt0ZXh0LWFsaWduOmNlbnRlcjtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5sbHtmb250LXNpemU6OHB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MnB4fQoubHZhbHtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwfQoub3ZlcmxheXtwb3NpdGlvbjpmaXhlZDtpbnNldDowO2JhY2tncm91bmQ6cmdiYSgwLDAsMCwuODgpO3otaW5kZXg6MTAwMDtkaXNwbGF5Om5vbmU7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpjZW50ZXI7cGFkZGluZzoxNnB4fQoub3ZlcmxheS5vcGVue2Rpc3BsYXk6ZmxleH0KLm1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjUyMHB4O21heC1oZWlnaHQ6OTJ2aDtvdmVyZmxvdy15OmF1dG99Ci5taGVhZHtwYWRkaW5nOjE4cHggMThweCAwO2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpmbGV4LXN0YXJ0fQoubXRpdGxle2ZvbnQtZmFtaWx5OidCZWJhcyBOZXVlJyxzYW5zLXNlcmlmO2ZvbnQtc2l6ZTozMHB4O2xldHRlci1zcGFjaW5nOjNweH0KLm1jbG9zZXtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTt3aWR0aDozMHB4O2hlaWdodDozMHB4O2JvcmRlci1yYWRpdXM6N3B4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxNXB4O2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcn0KLm1ib2R5e3BhZGRpbmc6MTRweCAxOHB4IDE4cHh9Ci5tY2hhcnR3e2hlaWdodDoxNTBweDttYXJnaW4tYm90dG9tOjE0cHh9Ci5kZ3JpZHtkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjdweDttYXJnaW4tYm90dG9tOjEycHh9Ci5kY3tiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo3cHg7cGFkZGluZzo5cHggMTFweDtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcil9Ci5kbHtmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoxcHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206M3B4fQouZHZ7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMH0KLmRib3h7Ym9yZGVyLXJhZGl1czo5cHg7cGFkZGluZzoxM3B4O21hcmdpbi1ib3R0b206MTJweDtib3JkZXI6MXB4IHNvbGlkfQouZGxibHtmb250LXNpemU6OXB4O2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo1cHh9Ci5kdmVyZHtmb250LWZhbWlseTonQmViYXMgTmV1ZScsc2Fucy1zZXJpZjtmb250LXNpemU6MjZweDtsZXR0ZXItc3BhY2luZzoycHg7bWFyZ2luLWJvdHRvbTo4cHh9Ci5kcm93e2Rpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjRweDtmb250LXNpemU6MTJweH0KLmRrZXl7Y29sb3I6dmFyKC0tbXV0ZWQpfQoucnJiYXJ7aGVpZ2h0OjRweDtiYWNrZ3JvdW5kOnZhcigtLWJnKTtib3JkZXItcmFkaXVzOjJweDttYXJnaW4tdG9wOjdweDtvdmVyZmxvdzpoaWRkZW59Ci5ycmZpbGx7aGVpZ2h0OjEwMCU7Ym9yZGVyLXJhZGl1czoycHg7dHJhbnNpdGlvbjp3aWR0aCAuOHMgZWFzZX0KLnZwYm94e2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjdweDtwYWRkaW5nOjEwcHg7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO21hcmdpbi1ib3R0b206MTJweH0KLnZwdGl0bGV7Zm9udC1zaXplOjlweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo3cHh9Ci52cGdyaWR7ZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoMywxZnIpO2dhcDo1cHh9Ci52cGN7YmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlci1yYWRpdXM6NXB4O3BhZGRpbmc6N3B4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlcjoxcHggc29saWR9Ci5taW5mb3tkaXNwbGF5OmlubGluZS1mbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO3dpZHRoOjE0cHg7aGVpZ2h0OjE0cHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDpyZ2JhKDk2LDE2NSwyNTAsLjIpO2NvbG9yOiM2MGE1ZmE7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7Y3Vyc29yOnBvaW50ZXI7bWFyZ2luLWxlZnQ6NHB4O2JvcmRlcjoxcHggc29saWQgcmdiYSg5NiwxNjUsMjUwLC4zKX0KLm1pbmZvLXBvcHVwe3Bvc2l0aW9uOmZpeGVkO2luc2V0OjA7YmFja2dyb3VuZDpyZ2JhKDAsMCwwLC44OCk7ei1pbmRleDoyMDAwO2Rpc3BsYXk6bm9uZTthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjtwYWRkaW5nOjE2cHh9Ci5taW5mby1wb3B1cC5vcGVue2Rpc3BsYXk6ZmxleH0KLm1pbmZvLW1vZGFse2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxNHB4O3dpZHRoOjEwMCU7bWF4LXdpZHRoOjQ4MHB4O21heC1oZWlnaHQ6ODV2aDtvdmVyZmxvdy15OmF1dG87cGFkZGluZzoyMHB4O3Bvc2l0aW9uOnJlbGF0aXZlfQoubWluZm8tdGl0bGV7Zm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4fQoubWluZm8tc291cmNle2ZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjEycHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NnB4O2ZsZXgtd3JhcDp3cmFwfQoubWluZm8tcmVse3BhZGRpbmc6MnB4IDdweDtib3JkZXItcmFkaXVzOjNweDtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjYwMH0KLm1pbmZvLXJlbC5oaWdoe2JhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Y29sb3I6IzEwYjk4MX0KLm1pbmZvLXJlbC5tZWRpdW17YmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjE1KTtjb2xvcjojZjU5ZTBifQoubWluZm8tcmVsLmxvd3tiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Y29sb3I6I2VmNDQ0NH0KLm1pbmZvLWRlc2N7Zm9udC1zaXplOjEycHg7Y29sb3I6Izk0YTNiODtsaW5lLWhlaWdodDoxLjY7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8td2FybmluZ3tiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjZweDtwYWRkaW5nOjhweCAxMHB4O2ZvbnQtc2l6ZToxMXB4O2NvbG9yOiNmNTllMGI7bWFyZ2luLWJvdHRvbToxNHB4fQoubWluZm8tcmFuZ2Vze21hcmdpbi1ib3R0b206MTRweH0KLm1pbmZvLXJhbmdlLXRpdGxle2ZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHh9Ci5taW5mby1yYW5nZXtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo4cHg7bWFyZ2luLWJvdHRvbTo2cHg7cGFkZGluZzo2cHggOHB4O2JvcmRlci1yYWRpdXM6NnB4O2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMDIpfQoubWluZm8tcmFuZ2UtZG90e3dpZHRoOjhweDtoZWlnaHQ6OHB4O2JvcmRlci1yYWRpdXM6NTAlO2ZsZXgtc2hyaW5rOjB9Ci5taW5mby1jYW5zbGlte2JhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6NnB4O3BhZGRpbmc6OHB4IDEwcHg7Zm9udC1zaXplOjExcHg7Y29sb3I6IzYwYTVmYX0KLm1pbmZvLWNsb3Nle3Bvc2l0aW9uOmFic29sdXRlO3RvcDoxNnB4O3JpZ2h0OjE2cHg7YmFja2dyb3VuZDpyZ2JhKDI1NSwyNTUsMjU1LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4xKTtjb2xvcjojOTRhM2I4O3dpZHRoOjI4cHg7aGVpZ2h0OjI4cHg7Ym9yZGVyLXJhZGl1czo3cHg7Y3Vyc29yOnBvaW50ZXI7Zm9udC1zaXplOjE0cHg7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyfQo6Oi13ZWJraXQtc2Nyb2xsYmFye3dpZHRoOjRweDtoZWlnaHQ6NHB4fQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRyYWNre2JhY2tncm91bmQ6dmFyKC0tYmcpfQo6Oi13ZWJraXQtc2Nyb2xsYmFyLXRodW1ie2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMSk7Ym9yZGVyLXJhZGl1czoycHh9Cjwvc3R5bGU+CjwvaGVhZD4KPGJvZHk+CjxkaXYgY2xhc3M9ImhlYWRlciI+CiAgPGRpdiBjbGFzcz0iaGVhZGVyLWlubmVyIj4KICAgIDxzcGFuIGNsYXNzPSJsb2dvLW1haW4iPkNBTlNMSU0gU0NBTk5FUjwvc3Bhbj4KICAgIDxzcGFuIGNsYXNzPSJ0aW1lc3RhbXAiPjxzcGFuIGNsYXNzPSJsaXZlLWRvdCI+PC9zcGFuPiUlVElNRVNUQU1QJSU8L3NwYW4+CiAgICA8YnV0dG9uIG9uY2xpY2s9Im9wZW5FZGl0TGlzdCgpIiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjE1KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMyk7Y29sb3I6IzYwYTVmYTtwYWRkaW5nOjVweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMXB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtZmFtaWx5OmluaGVyaXQiPuKcj++4jyBMaXN0ZXlpIETDvHplbmxlPC9idXR0b24+CiAgPC9kaXY+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJuYXYiPgogIDxidXR0b24gY2xhc3M9InRhYiBhY3RpdmUiIG9uY2xpY2s9InNldFRhYignZGFzaGJvYXJkJyx0aGlzKSI+8J+PoCBEYXNoYm9hcmQ8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignYWxsJyx0aGlzKSI+8J+TiiBIaXNzZWxlcjwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiBwb3J0IiBvbmNsaWNrPSJzZXRUYWIoJ3BvcnQnLHRoaXMpIj7wn5K8IFBvcnRmw7Z5w7xtPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2J1eScsdGhpcykiPvCfk4ggQWw8L2J1dHRvbj4KICA8YnV0dG9uIGNsYXNzPSJ0YWIiIG9uY2xpY2s9InNldFRhYignc2VsbCcsdGhpcykiPvCfk4kgU2F0PC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ2Vhcm5pbmdzJyx0aGlzKSI+8J+ThSBFYXJuaW5nczwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdydXRpbicsdGhpcykiPuKchSBSdXRpbjwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRhYiIgb25jbGljaz0ic2V0VGFiKCdoYWZ0YWxpaycsdGhpcykiPvCfk4ggSGFmdGFsxLFrPC9idXR0b24+CiAgPGJ1dHRvbiBjbGFzcz0idGFiIiBvbmNsaWNrPSJzZXRUYWIoJ3NjcmVlbmVyJyx0aGlzKSI+8J+UjSBTY3JlZW5lcjwvYnV0dG9uPgo8L2Rpdj4KPGRpdiBjbGFzcz0idGYtcm93IiBpZD0idGZSb3ciIHN0eWxlPSJkaXNwbGF5Om5vbmUiPgogIDxidXR0b24gY2xhc3M9InRmLWJ0biBhY3RpdmUiIGRhdGEtdGY9IjFkIiBvbmNsaWNrPSJzZXRUZignMWQnLHRoaXMpIj4xRzwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRmLWJ0biBzdGFyIiBkYXRhLXRmPSIxd2siIG9uY2xpY2s9InNldFRmKCcxd2snLHRoaXMpIj4xSDwvYnV0dG9uPgogIDxidXR0b24gY2xhc3M9InRmLWJ0biIgZGF0YS10Zj0iMW1vIiBvbmNsaWNrPSJzZXRUZignMW1vJyx0aGlzKSI+MUE8L2J1dHRvbj4KICA8c3BhbiBjbGFzcz0idGYtaGludCI+Q0FOU0xJTSDDtm5lcmlsZW46IDFHICsgMUg8L3NwYW4+CjwvZGl2Pgo8ZGl2IGNsYXNzPSJzdGF0cyIgaWQ9InN0YXRzIj48L2Rpdj4KPGRpdiBjbGFzcz0ibWFpbiI+PGRpdiBjbGFzcz0iZ3JpZCIgaWQ9ImdyaWQiPjwvZGl2PjwvZGl2Pgo8ZGl2IGNsYXNzPSJvdmVybGF5IiBpZD0ib3ZlcmxheSIgb25jbGljaz0iY2xvc2VNKGV2ZW50KSI+CiAgPGRpdiBjbGFzcz0ibW9kYWwiIGlkPSJtb2RhbCI+PC9kaXY+CjwvZGl2PgoKPGRpdiBjbGFzcz0ibWluZm8tcG9wdXAiIGlkPSJlZGl0UG9wdXAiIG9uY2xpY2s9ImNsb3NlRWRpdFBvcHVwKGV2ZW50KSI+CiAgPGRpdiBjbGFzcz0ibWluZm8tbW9kYWwiIHN0eWxlPSJwb3NpdGlvbjpyZWxhdGl2ZTttYXgtd2lkdGg6NTYwcHgiIGlkPSJlZGl0TW9kYWwiPgogICAgPGJ1dHRvbiBjbGFzcz0ibWluZm8tY2xvc2UiIG9uY2xpY2s9ImNsb3NlRWRpdFBvcHVwKCkiPuKclTwvYnV0dG9uPgogICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjE2cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpO21hcmdpbi1ib3R0b206NHB4Ij7inI/vuI8gTGlzdGV5aSBEw7x6ZW5sZTwvZGl2PgogICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MTZweCI+R2l0SHViIEFQSSBrZXkgZ2VyZWtsaSDigJQgZGXEn2nFn2lrbGlrbGVyIGFuxLFuZGEga2F5ZGVkaWxpcjwvZGl2PgogICAgPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnIgMWZyO2dhcDoxNnB4O21hcmdpbi1ib3R0b206MTZweCI+CiAgICAgIDxkaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPvCfk4sgV2F0Y2hsaXN0PC9kaXY+CiAgICAgICAgPGRpdiBpZD0id2F0Y2hsaXN0RWRpdG9yIj48L2Rpdj4KICAgICAgICA8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjZweDttYXJnaW4tdG9wOjhweCI+CiAgICAgICAgICA8aW5wdXQgaWQ9Im5ld1dhdGNoVGlja2VyIiBwbGFjZWhvbGRlcj0iSGlzc2UgZWtsZSAoVFNMQSkiIHN0eWxlPSJmbGV4OjE7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtjb2xvcjp2YXIoLS10ZXh0KTtwYWRkaW5nOjZweCAxMHB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2ZvbnQtZmFtaWx5OmluaGVyaXQ7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlIi8+CiAgICAgICAgICA8YnV0dG9uIG9uY2xpY2s9ImFkZFRpY2tlcignd2F0Y2gnKSIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjMpO2NvbG9yOnZhcigtLWdyZWVuKTtwYWRkaW5nOjZweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2N1cnNvcjpwb2ludGVyIj4rIEVrbGU8L2J1dHRvbj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CiAgICAgIDxkaXY+CiAgICAgICAgPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPvCfkrwgUG9ydGbDtnk8L2Rpdj4KICAgICAgICA8ZGl2IGlkPSJwb3J0Zm9saW9FZGl0b3IiPjwvZGl2PgogICAgICAgIDxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6NnB4O21hcmdpbi10b3A6OHB4Ij4KICAgICAgICAgIDxpbnB1dCBpZD0ibmV3UG9ydFRpY2tlciIgcGxhY2Vob2xkZXI9Ikhpc3NlIGVrbGUgKEFBUEwpIiBzdHlsZT0iZmxleDoxO2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tdGV4dCk7cGFkZGluZzo2cHggMTBweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTJweDtmb250LWZhbWlseTppbmhlcml0O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZSIvPgogICAgICAgICAgPGJ1dHRvbiBvbmNsaWNrPSJhZGRUaWNrZXIoJ3BvcnQnKSIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xNSk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjMpO2NvbG9yOnZhcigtLWdyZWVuKTtwYWRkaW5nOjZweCAxMnB4O2JvcmRlci1yYWRpdXM6NnB4O2ZvbnQtc2l6ZToxMnB4O2N1cnNvcjpwb2ludGVyIj4rIEVrbGU8L2J1dHRvbj4KICAgICAgICA8L2Rpdj4KICAgICAgPC9kaXY+CiAgICA8L2Rpdj4KICAgIDxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxMnB4O21hcmdpbi1ib3R0b206MTRweDtmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1ncmVlbikiPuKchSBEZcSfacWfaWtsaWtsZXIga2F5ZGVkaWxpbmNlIGJpciBzb25yYWtpIENvbGFiIMOnYWzEscWfdMSxcm1hc8SxbmRhIGFrdGlmIG9sdXIuPC9kaXY+CjxkaXYgc3R5bGU9Im1hcmdpbi1ib3R0b206MTJweCI+CiAgICAgIDxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjVweCI+R2l0SHViIFRva2VuIChiaXIga2V6IGdpciwgdGFyYXlpY2kgaGF0aXJsYXlhY2FrKTwvZGl2PgogICAgICA8aW5wdXQgaWQ9ImdoVG9rZW5JbnB1dCIgcGxhY2Vob2xkZXI9ImdocF8uLi4iIHN0eWxlPSJ3aWR0aDoxMDAlO2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tdGV4dCk7cGFkZGluZzo4cHggMTBweDtib3JkZXItcmFkaXVzOjZweDtmb250LXNpemU6MTFweDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiLz4KICAgIDwvZGl2PgogICAgPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDo4cHgiPgogICAgICA8YnV0dG9uIG9uY2xpY2s9InNhdmVMaXN0VG9HaXRodWIoKSIgc3R5bGU9ImZsZXg6MTtiYWNrZ3JvdW5kOnJnYmEoMTYsMTg1LDEyOSwuMTUpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtjb2xvcjp2YXIoLS1ncmVlbik7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6OHB4O2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMDtjdXJzb3I6cG9pbnRlciI+8J+SviBHaXRIdWJhIEtheWRldDwvYnV0dG9uPgogICAgICA8YnV0dG9uIG9uY2xpY2s9ImNsb3NlRWRpdFBvcHVwKCkiIHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2NvbG9yOnZhcigtLW11dGVkKTtwYWRkaW5nOjEwcHggMTZweDtib3JkZXItcmFkaXVzOjhweDtmb250LXNpemU6MTNweDtjdXJzb3I6cG9pbnRlciI+xLBwdGFsPC9idXR0b24+CiAgICA8L2Rpdj4KICAgIDxkaXYgaWQ9ImVkaXRTdGF0dXMiIHN0eWxlPSJtYXJnaW4tdG9wOjEwcHg7Zm9udC1zaXplOjEycHg7dGV4dC1hbGlnbjpjZW50ZXIiPjwvZGl2PgogIDwvZGl2Pgo8L2Rpdj4KCjxkaXYgY2xhc3M9Im1pbmZvLXBvcHVwIiBpZD0ibWluZm9Qb3B1cCIgb25jbGljaz0iY2xvc2VJbmZvUG9wdXAoZXZlbnQpIj4KICA8ZGl2IGNsYXNzPSJtaW5mby1tb2RhbCIgaWQ9Im1pbmZvTW9kYWwiPgogICAgPGJ1dHRvbiBjbGFzcz0ibWluZm8tY2xvc2UiIG9uY2xpY2s9ImNsb3NlSW5mb1BvcHVwKCkiPuKclTwvYnV0dG9uPgogICAgPGRpdiBpZD0ibWluZm9Db250ZW50Ij48L2Rpdj4KICA8L2Rpdj4KPC9kaXY+CjxzY3JpcHQ+CnZhciBNRVRSSUNTID0gewogIC8vIFRFS07EsEsKICAnUlNJJzogewogICAgdGl0bGU6ICdSU0kgKEfDtnJlY2VsaSBHw7zDpyBFbmRla3NpKScsCiAgICBkZXNjOiAnSGlzc2VuaW4gYcWfxLFyxLEgYWzEsW0gdmV5YSBhxZ/EsXLEsSBzYXTEsW0gYsO2bGdlc2luZGUgb2x1cCBvbG1hZMSxxJ/EsW7EsSBnw7ZzdGVyaXIuIDE0IGfDvG5sw7xrIGZpeWF0IGhhcmVrZXRsZXJpbmkgYW5hbGl6IGVkZXIuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J0HFn8SxcsSxIFNhdMSxbScsbWluOjAsbWF4OjMwLGNvbG9yOidncmVlbicsZGVzYzonRsSxcnNhdCBiw7ZsZ2VzaSDigJQgZml5YXQgw6dvayBkw7zFn23DvMWfJ30sCiAgICAgIHtsYWJlbDonTm9ybWFsJyxtaW46MzAsbWF4OjcwLGNvbG9yOid5ZWxsb3cnLGRlc2M6J07DtnRyIGLDtmxnZSd9LAogICAgICB7bGFiZWw6J0HFn8SxcsSxIEFsxLFtJyxtaW46NzAsbWF4OjEwMCxjb2xvcjoncmVkJyxkZXNjOidEaWtrYXQg4oCUIGZpeWF0IMOnb2sgecO8a3NlbG1pxZ8nfQogICAgXSwKICAgIGNhbnNsaW06ICdOIGtyaXRlcmkgaWxlIGlsZ2lsaSDigJQgZml5YXQgbW9tZW50dW11JwogIH0sCiAgJ1NNQTUwJzogewogICAgdGl0bGU6ICdTTUEgNTAgKDUwIEfDvG5sw7xrIEhhcmVrZXRsaSBPcnRhbGFtYSknLAogICAgZGVzYzogJ1NvbiA1MCBnw7xuw7xuIG9ydGFsYW1hIGthcGFuxLHFnyBmaXlhdMSxLiBLxLFzYS1vcnRhIHZhZGVsaSB0cmVuZCBnw7ZzdGVyZ2VzaS4nLAogICAgc291cmNlOiAnVGVrbmlrIEFuYWxpeicsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonw5x6ZXJpbmRlJyxjb2xvcjonZ3JlZW4nLGRlc2M6J0vEsXNhIHZhZGVsaSB0cmVuZCBwb3ppdGlmIOKAlCBnw7zDp2zDvCBzaW55YWwnfSwKICAgICAge2xhYmVsOidBbHTEsW5kYScsY29sb3I6J3JlZCcsZGVzYzonS8Sxc2EgdmFkZWxpIHRyZW5kIG5lZ2F0aWYnfQogICAgXSwKICAgIGNhbnNsaW06ICdNIGtyaXRlcmkg4oCUIHBpeWFzYSB0cmVuZGknCiAgfSwKICAnU01BMjAwJzogewogICAgdGl0bGU6ICdTTUEgMjAwICgyMDAgR8O8bmzDvGsgSGFyZWtldGxpIE9ydGFsYW1hKScsCiAgICBkZXNjOiAnU29uIDIwMCBnw7xuw7xuIG9ydGFsYW1hIGthcGFuxLHFnyBmaXlhdMSxLiBVenVuIHZhZGVsaSB0cmVuZCBnw7ZzdGVyZ2VzaS4gRW4gw7ZuZW1saSB0ZWtuaWsgc2V2aXllLicsCiAgICBzb3VyY2U6ICdUZWtuaWsgQW5hbGl6JywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOifDnHplcmluZGUnLGNvbG9yOidncmVlbicsZGVzYzonVXp1biB2YWRlbGkgYm/En2EgdHJlbmRpbmRlIOKAlCBDQU5TTElNIGnDp2luIMWfYXJ0J30sCiAgICAgIHtsYWJlbDonQWx0xLFuZGEnLGNvbG9yOidyZWQnLGRlc2M6J1V6dW4gdmFkZWxpIGF5xLEgdHJlbmRpbmRlIOKAlCBDQU5TTElNIGnDp2luIGdpcm1lJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTSBrcml0ZXJpIOKAlCB6b3J1bmx1IGtvxZ91bCcKICB9LAogICc1MlcnOiB7CiAgICB0aXRsZTogJzUyIEhhZnRhbMSxayBQb3ppc3lvbicsCiAgICBkZXNjOiAnSGlzc2VuaW4gc29uIDEgecSxbGRha2kgZml5YXQgYXJhbMSxxJ/EsW5kYSBuZXJlZGUgb2xkdcSfdW51IGfDtnN0ZXJpci4gMD15xLFsxLFuIGRpYmksIDEwMD15xLFsxLFuIHppcnZlc2kuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6JzAtMzAlJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1nEsWzEsW4gZGliaW5lIHlha8SxbiDigJQgcG90YW5zaXllbCBmxLFyc2F0J30sCiAgICAgIHtsYWJlbDonMzAtNzAlJyxjb2xvcjoneWVsbG93JyxkZXNjOidPcnRhIGLDtmxnZSDigJQgbsO2dHInfSwKICAgICAge2xhYmVsOic3MC04NSUnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1ppcnZleWUgeWFrbGHFn8SxeW9yIOKAlCBpemxlJ30sCiAgICAgIHtsYWJlbDonODUtMTAwJScsY29sb3I6J3JlZCcsZGVzYzonWmlydmV5ZSDDp29rIHlha8SxbiDigJQgZGlra2F0bGkgZ2lyJ30KICAgIF0sCiAgICBjYW5zbGltOiAnTiBrcml0ZXJpIOKAlCB5ZW5pIHppcnZlIGvEsXLEsWzEsW3EsSBpw6dpbiBpZGVhbCBiw7ZsZ2UgJTg1LTEwMCcKICB9LAogICdIYWNpbSc6IHsKICAgIHRpdGxlOiAnSGFjaW0gKMSwxZ9sZW0gTWlrdGFyxLEpJywKICAgIGRlc2M6ICdHw7xubMO8ayBpxZ9sZW0gaGFjbWluaW4gc29uIDIwIGfDvG5sw7xrIG9ydGFsYW1heWEgb3JhbsSxLiBHw7zDp2zDvCBoYXJla2V0bGVyaW4gaGFjaW1sZSBkZXN0ZWtsZW5tZXNpIGdlcmVraXIuJywKICAgIHNvdXJjZTogJ1Rla25payBBbmFsaXonLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6J1nDvGtzZWsgKD4xLjN4KScsY29sb3I6J2dyZWVuJyxkZXNjOidLdXJ1bXNhbCBpbGdpIHZhciDigJQgZ8O8w6dsw7wgc2lueWFsJ30sCiAgICAgIHtsYWJlbDonTm9ybWFsICgwLjctMS4zeCknLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGFsYW1hIGlsZ2knfSwKICAgICAge2xhYmVsOidEw7zFn8O8ayAoPDAuN3gpJyxjb2xvcjoncmVkJyxkZXNjOifEsGxnaSBhemFsbcSxxZ8g4oCUIGRpa2thdCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ1Mga3JpdGVyaSDigJQgYXJ6L3RhbGVwIGRlbmdlc2knCiAgfSwKICAvLyBURU1FTAogICdGb3J3YXJkUEUnOiB7CiAgICB0aXRsZTogJ0ZvcndhcmQgUC9FICjEsGxlcml5ZSBEw7Zuw7xrIEZpeWF0L0themFuw6cpJywKICAgIGRlc2M6ICdTaXJrZXRpbiBvbnVtw7x6ZGVraSAxMiBheWRha2kgdGFobWluaSBrYXphbmNpbmEgZ29yZSBmaXlhdGkuIFRyYWlsaW5nIFAvRSBhcmFjaW5hIGdvcmUgZ2VsZWNlZ2Ugb2Rha2xpZGlnaSBpY2luIGRhaGEgb25lbWxpZGlyLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEFuYWxpc3QgdGFobWluaScsCiAgICByZWxpYWJpbGl0eTogJ21lZGl1bScsCiAgICB3YXJuaW5nOiAnQW5hbGlzdCB0YWhtaW5sZXJpbmUgZGF5YW7EsXIsIHlhbsSxbHTEsWPEsSBvbGFiaWxpcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic8MTUnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgYsO8ecO8bWUgYmVrbGVudGlzaSBkw7zFn8O8ayB2ZXlhIGhpc3NlIGRlxJ9lciBhbHTEsW5kYSd9LAogICAgICB7bGFiZWw6JzE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J01ha3VsIOKAlCDDp2/En3Ugc2VrdMO2ciBpw6dpbiBub3JtYWwnfSwKICAgICAge2xhYmVsOicyNS00MCcsY29sb3I6J3llbGxvdycsZGVzYzonUGFoYWzEsSBhbWEgYsO8ecO8bWUgcHJpbWkgw7ZkZW5peW9yJ30sCiAgICAgIHtsYWJlbDonPjQwJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHBhaGFsxLEg4oCUIHnDvGtzZWsgYsO8ecO8bWUgYmVrbGVudGlzaSBmaXlhdGxhbm3EscWfJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQyB2ZSBBIGtyaXRlcmxlcmkgaWxlIGlsZ2lsaScKICB9LAogICdQRUcnOiB7CiAgICB0aXRsZTogJ1BFRyBPcmFuxLEgKEZpeWF0L0themFuw6cvQsO8ecO8bWUpJywKICAgIGRlc2M6ICdQL0Ugb3JhbsSxbsSxIGLDvHnDvG1lIGjEsXrEsXlsYSBrYXLFn8SxbGHFn3TEsXLEsXIuIELDvHnDvHllbiDFn2lya2V0bGVyIGljaW4gUC9FXCdkZW4gZGFoYSBkb8SfcnUgZGXEn2VybGVtZSDDtmzDp8O8dMO8LiBQRUc9MSBhZGlsIGRlxJ9lciBrYWJ1bCBlZGlsaXIuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgQW5hbGlzdCB0YWhtaW5pJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdBbmFsaXN0IGLDvHnDvG1lIHRhaG1pbmxlcmluZSBkYXlhbsSxcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic8MS4wJyxjb2xvcjonZ3JlZW4nLGRlc2M6J1VjdXog4oCUIGLDvHnDvG1lc2luZSBnw7ZyZSBkZcSfZXIgYWx0xLFuZGEnfSwKICAgICAge2xhYmVsOicxLjAtMS41Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J01ha3VsIOKAlCBhZGlsIGZpeWF0IGNpdmFyxLEnfSwKICAgICAge2xhYmVsOicxLjUtMi4wJyxjb2xvcjoneWVsbG93JyxkZXNjOidCaXJheiBwYWhhbMSxJ30sCiAgICAgIHtsYWJlbDonPjIuMCcsY29sb3I6J3JlZCcsZGVzYzonUGFoYWzEsSDigJQgZGlra2F0bGkgb2wnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIGLDvHnDvG1lIGthbGl0ZXNpJwogIH0sCiAgJ0VQU0dyb3d0aCc6IHsKICAgIHRpdGxlOiAnRVBTIELDvHnDvG1lc2kgKMOHZXlyZWtsaWssIFlvWSknLAogICAgZGVzYzogJ8WeaXJrZXRpbiBoaXNzZSBiYcWfxLFuYSBrYXphbmPEsW7EsW4gZ2XDp2VuIHnEsWzEsW4gYXluxLEgw6dleXJlxJ9pbmUgZ8O2cmUgYXJ0xLHFn8SxLiBDQU5TTElNXCdpbiBlbiBrcml0aWsga3JpdGVyaS4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMjUnLGNvbG9yOidncmVlbicsZGVzYzonR8O8w6dsw7wgYsO8ecO8bWUg4oCUIENBTlNMSU0ga3JpdGVyaSBrYXLFn8SxbGFuZMSxJ30sCiAgICAgIHtsYWJlbDonJTE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWkgYsO8ecO8bWUnfSwKICAgICAge2xhYmVsOiclMC0xNScsY29sb3I6J3llbGxvdycsZGVzYzonWmF5xLFmIGLDvHnDvG1lJ30sCiAgICAgIHtsYWJlbDonPDAnLGNvbG9yOidyZWQnLGRlc2M6J0themFuw6cgZMO8xZ/DvHlvciDigJQgZGlra2F0J30KICAgIF0sCiAgICBjYW5zbGltOiAnQyBrcml0ZXJpIOKAlCBlbiBrcml0aWsga3JpdGVyLCBtaW5pbXVtICUyNSBvbG1hbMSxJwogIH0sCiAgJ1Jldkdyb3d0aCc6IHsKICAgIHRpdGxlOiAnR2VsaXIgQsO8ecO8bWVzaSAoWW9ZKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIHNhdMSxxZ8vZ2VsaXJpbmluIGdlw6dlbiB5xLFsYSBnw7ZyZSBhcnTEscWfxLEuIEVQUyBiw7x5w7xtZXNpbmkgZGVzdGVrbGVtZXNpIGdlcmVraXIg4oCUIHNhZGVjZSBtYWxpeWV0IGtlc2ludGlzaXlsZSBiw7x5w7xtZSBzw7xyZMO8csO8bGViaWxpciBkZcSfaWwuJywKICAgIHNvdXJjZTogJ1RlbWVsIEFuYWxpeiDigJQgR2Vyw6dlayB2ZXJpJywKICAgIHJlbGlhYmlsaXR5OiAnaGlnaCcsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic+JTE1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J0fDvMOnbMO8IGdlbGlyIGLDvHnDvG1lc2knfSwKICAgICAge2xhYmVsOiclNS0xNScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSBiw7x5w7xtZSd9LAogICAgICB7bGFiZWw6Jzw1Jyxjb2xvcjoncmVkJyxkZXNjOidHZWxpciBiw7x5w7xtZXNpIHphecSxZid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Ega3JpdGVyaSDigJQgc8O8cmTDvHLDvGxlYmlsaXIgYsO8ecO8bWUgacOnaW4gxZ9hcnQnCiAgfSwKICAnTmV0TWFyZ2luJzogewogICAgdGl0bGU6ICdOZXQgTWFyamluJywKICAgIGRlc2M6ICdIZXIgMSQgZ2VsaXJkZW4gbmUga2FkYXIgbmV0IGvDonIga2FsZMSxxJ/EsW7EsSBnw7ZzdGVyaXIuIFnDvGtzZWsgbWFyamluID0gZ8O8w6dsw7wgacWfIG1vZGVsaS4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lMjAnLGNvbG9yOidncmVlbicsZGVzYzonw4dvayBnw7zDp2zDvCBrw6JybMSxbMSxayd9LAogICAgICB7bGFiZWw6JyUxMC0yMCcsY29sb3I6J2dyZWVuJyxkZXNjOifEsHlpIGvDonJsxLFsxLFrJ30sCiAgICAgIHtsYWJlbDonJTUtMTAnLGNvbG9yOid5ZWxsb3cnLGRlc2M6J09ydGEga8OicmzEsWzEsWsnfSwKICAgICAge2xhYmVsOic8NScsY29sb3I6J3JlZCcsZGVzYzonWmF5xLFmIGvDonJsxLFsxLFrJ30KICAgIF0sCiAgICBjYW5zbGltOiAnQSBrcml0ZXJpIOKAlCBrw6JybMSxbMSxayBrYWxpdGVzaScKICB9LAogICdST0UnOiB7CiAgICB0aXRsZTogJ1JPRSAow5Z6a2F5bmFrIEvDonJsxLFsxLHEn8SxKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIMO2eiBzZXJtYXllc2l5bGUgbmUga2FkYXIga8OiciBldHRpxJ9pbmkgZ8O2c3RlcmlyLiBZw7xrc2VrIFJPRSA9IHNlcm1heWV5aSB2ZXJpbWxpIGt1bGxhbsSxeW9yLicsCiAgICBzb3VyY2U6ICdUZW1lbCBBbmFsaXog4oCUIEdlcsOnZWsgdmVyaScsCiAgICByZWxpYWJpbGl0eTogJ2hpZ2gnLAogICAgcmFuZ2VzOiBbCiAgICAgIHtsYWJlbDonPiUyNScsY29sb3I6J2dyZWVuJyxkZXNjOifDh29rIGfDvMOnbMO8IOKAlCBDQU5TTElNIGlkZWFsIHNldml5ZXNpJ30sCiAgICAgIHtsYWJlbDonJTE1LTI1Jyxjb2xvcjonZ3JlZW4nLGRlc2M6J8SweWknfSwKICAgICAge2xhYmVsOiclOC0xNScsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSd9LAogICAgICB7bGFiZWw6Jzw4Jyxjb2xvcjoncmVkJyxkZXNjOidaYXnEsWYnfQogICAgXSwKICAgIGNhbnNsaW06ICdBIGtyaXRlcmkg4oCUIG1pbmltdW0gJTE3IG9sbWFsxLEnCiAgfSwKICAnR3Jvc3NNYXJnaW4nOiB7CiAgICB0aXRsZTogJ0Jyw7x0IE1hcmppbicsCiAgICBkZXNjOiAnU2F0xLHFnyBnZWxpcmluZGVuIMO8cmV0aW0gbWFsaXlldGkgZMO8xZ/DvGxkw7xrdGVuIHNvbnJhIGthbGFuIG9yYW4uIFNla3TDtnJlIGfDtnJlIGRlxJ9pxZ9pci4nLAogICAgc291cmNlOiAnVGVtZWwgQW5hbGl6IOKAlCBHZXLDp2VrIHZlcmknLAogICAgcmVsaWFiaWxpdHk6ICdoaWdoJywKICAgIHJhbmdlczogWwogICAgICB7bGFiZWw6Jz4lNTAnLGNvbG9yOidncmVlbicsZGVzYzonw4dvayBnw7zDp2zDvCDigJQgeWF6xLFsxLFtL1NhYVMgc2V2aXllc2knfSwKICAgICAge2xhYmVsOiclMzAtNTAnLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSd9LAogICAgICB7bGFiZWw6JyUxNS0zMCcsY29sb3I6J3llbGxvdycsZGVzYzonT3J0YSDigJQgZG9uYW7EsW0veWFyxLEgaWxldGtlbiBub3JtYWwnfSwKICAgICAge2xhYmVsOic8MTUnLGNvbG9yOidyZWQnLGRlc2M6J0TDvMWfw7xrIG1hcmppbid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0vDonJsxLFsxLFrIGthbGl0ZXNpIGfDtnN0ZXJnZXNpJwogIH0sCiAgLy8gR8SwUsSwxZ4KICAnRW50cnlTY29yZSc6IHsKICAgIHRpdGxlOiAnR2lyacWfIEthbGl0ZXNpIFNrb3J1JywKICAgIGRlc2M6ICdSU0ksIFNNQSBwb3ppc3lvbnUsIFAvRSwgUEVHIHZlIEVQUyBiw7x5w7xtZXNpbmkgYmlybGXFn3RpcmVuIGJpbGXFn2lrIHNrb3IuIDAtMTAwIGFyYXPEsS4nLAogICAgc291cmNlOiAnQml6aW0gaGVzYXBsYW1hJywKICAgIHJlbGlhYmlsaXR5OiAnbG93JywKICAgIHdhcm5pbmc6ICdCVSBVWUdVTEFNQSBUQVJBRklOREFOIEhFU0FQTEFOQU4gS0FCQSBUQUhNxLBORMSwUi4gWWF0xLFyxLFtIGthcmFyxLEgacOnaW4gdGVrIGJhxZ/EsW5hIGt1bGxhbm1hLicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic3NS0xMDAnLGNvbG9yOidncmVlbicsZGVzYzonVWN1eiDigJQgaWRlYWwgZ2lyacWfIGLDtmxnZXNpJ30sCiAgICAgIHtsYWJlbDonNjAtNzUnLGNvbG9yOidncmVlbicsZGVzYzonTWFrdWwgZml5YXQnfSwKICAgICAge2xhYmVsOic0NS02MCcsY29sb3I6J3llbGxvdycsZGVzYzonTsO2dHInfSwKICAgICAge2xhYmVsOiczMC00NScsY29sb3I6J3JlZCcsZGVzYzonUGFoYWzEsSDigJQgYmVrbGUnfSwKICAgICAge2xhYmVsOicwLTMwJyxjb2xvcjoncmVkJyxkZXNjOifDh29rIHBhaGFsxLEg4oCUIGdpcm1lJ30KICAgIF0sCiAgICBjYW5zbGltOiAnVMO8bSBrcml0ZXJsZXIgYmlsZcWfaW1pJwogIH0sCiAgJ1JSJzogewogICAgdGl0bGU6ICdSaXNrL8OWZMO8bCBPcmFuxLEgKFIvUiknLAogICAgZGVzYzogJ1BvdGFuc2l5ZWwga2F6YW5jxLFuIHJpc2tlIG9yYW7EsS4gMToyIGRlbWVrIDEkIHJpc2tlIGthcsWfxLEgMiQga2F6YW7DpyBwb3RhbnNpeWVsaSB2YXIgZGVtZWsuJywKICAgIHNvdXJjZTogJ0JpemltIGhlc2FwbGFtYScsCiAgICByZWxpYWJpbGl0eTogJ2xvdycsCiAgICB3YXJuaW5nOiAnR2lyacWfL2hlZGVmL3N0b3Agc2V2aXllbGVyaSBmb3Jtw7xsIGJhemzEsSBrYWJhIHRhaG1pbmRpcicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOicxOjMrJyxjb2xvcjonZ3JlZW4nLGRlc2M6J03DvGtlbW1lbCDigJQgZ8O8w6dsw7wgZ2lyacWfIHNpbnlhbGknfSwKICAgICAge2xhYmVsOicxOjInLGNvbG9yOidncmVlbicsZGVzYzonxLB5aSDigJQgbWluaW11bSBrYWJ1bCBlZGlsZWJpbGlyJ30sCiAgICAgIHtsYWJlbDonMToxJyxjb2xvcjoneWVsbG93JyxkZXNjOidaYXnEsWYnfSwKICAgICAge2xhYmVsOic8MToxJyxjb2xvcjoncmVkJyxkZXNjOidSaXNrIGthemFuw6d0YW4gYsO8ecO8ayDigJQgZ2lybWUnfQogICAgXSwKICAgIGNhbnNsaW06ICdSaXNrIHnDtm5ldGltaScKICB9LAogIC8vIEVBUk5JTkdTCiAgJ0Vhcm5pbmdzRGF0ZSc6IHsKICAgIHRpdGxlOiAnUmFwb3IgVGFyaWhpIChFYXJuaW5ncyBEYXRlKScsCiAgICBkZXNjOiAnxZ5pcmtldGluIMOnZXlyZWsgZmluYW5zYWwgc29udcOnbGFyxLFuxLEgYcOnxLFrbGF5YWNhxJ/EsSB0YXJpaC4gUmFwb3Igw7ZuY2VzaSB2ZSBzb25yYXPEsSBmaXlhdCBzZXJ0IGhhcmVrZXQgZWRlYmlsaXIuJywKICAgIHNvdXJjZTogJ3lmaW5hbmNlIOKAlCBiYXplbiBoYXRhbMSxIG9sYWJpbGlyJywKICAgIHJlbGlhYmlsaXR5OiAnbWVkaXVtJywKICAgIHdhcm5pbmc6ICdUYXJpaGxlcmkgcmVzbWkgSVIgc2F5ZmFzxLFuZGFuIGRvxJ9ydWxhecSxbicsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOic3IGfDvG4gacOnaW5kZScsY29sb3I6J3JlZCcsZGVzYzonw4dvayB5YWvEsW4g4oCUIHBvemlzeW9uIGHDp21hayByaXNrbGknfSwKICAgICAge2xhYmVsOic4LTE0IGfDvG4nLGNvbG9yOid5ZWxsb3cnLGRlc2M6J1lha8SxbiDigJQgZGlra2F0bGkgb2wnfSwKICAgICAge2xhYmVsOicxNCsgZ8O8bicsY29sb3I6J2dyZWVuJyxkZXNjOidZZXRlcmxpIHPDvHJlIHZhcid9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Mga3JpdGVyaSDigJQgw6dleXJlayByYXBvciBrYWxpdGVzaScKICB9LAogICdBdmdNb3ZlJzogewogICAgdGl0bGU6ICdPcnRhbGFtYSBSYXBvciBIYXJla2V0aScsCiAgICBkZXNjOiAnU29uIDQgw6dleXJlayByYXBvcnVuZGEsIHJhcG9yIGfDvG7DvCB2ZSBlcnRlc2kgZ8O8biBmaXlhdMSxbiBvcnRhbGFtYSBuZSBrYWRhciBoYXJla2V0IGV0dGnEn2kuJywKICAgIHNvdXJjZTogJ0JpemltIGhlc2FwbGFtYScsCiAgICByZWxpYWJpbGl0eTogJ21lZGl1bScsCiAgICByYW5nZXM6IFsKICAgICAge2xhYmVsOidQb3ppdGlmICg+JTUpJyxjb2xvcjonZ3JlZW4nLGRlc2M6J8WeaXJrZXQgZ2VuZWxsaWtsZSBiZWtsZW50aXlpIGHFn8SxeW9yJ30sCiAgICAgIHtsYWJlbDonTsO2dHIgKCUwLTUpJyxjb2xvcjoneWVsbG93JyxkZXNjOidLYXLEscWfxLFrIGdlw6dtacWfJ30sCiAgICAgIHtsYWJlbDonTmVnYXRpZicsY29sb3I6J3JlZCcsZGVzYzonUmFwb3IgZMO2bmVtaW5kZSBmaXlhdCBnZW5lbGxpa2xlIGTDvMWfw7x5b3Ig4oCUIGRpa2thdCd9CiAgICBdLAogICAgY2Fuc2xpbTogJ0Mga3JpdGVyaSDigJQga2F6YW7DpyBzw7xycHJpemkgZ2XDp21pxZ9pJwogIH0KfTsKCmZ1bmN0aW9uIHNob3dJbmZvKGtleSxldmVudCl7CiAgaWYoZXZlbnQpIGV2ZW50LnN0b3BQcm9wYWdhdGlvbigpOwogIHZhciBtPU1FVFJJQ1Nba2V5XTsgaWYoIW0pIHJldHVybjsKICB2YXIgcmVsTGFiZWw9bS5yZWxpYWJpbGl0eT09PSJoaWdoIj8iR8O8dmVuaWxpciI6bS5yZWxpYWJpbGl0eT09PSJtZWRpdW0iPyJPcnRhIEfDvHZlbmlsaXIiOiJLYWJhIFRhaG1pbiI7CiAgdmFyIGg9JzxkaXYgY2xhc3M9Im1pbmZvLXRpdGxlIj4nK20udGl0bGUrJzwvZGl2Pic7CiAgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLXNvdXJjZSI+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKSI+JyttLnNvdXJjZSsnPC9zcGFuPjxzcGFuIGNsYXNzPSJtaW5mby1yZWwgJyttLnJlbGlhYmlsaXR5KyciPicrcmVsTGFiZWwrJzwvc3Bhbj48L2Rpdj4nOwogIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby1kZXNjIj4nK20uZGVzYysnPC9kaXY+JzsKICBpZihtLndhcm5pbmcpIGgrPSc8ZGl2IGNsYXNzPSJtaW5mby13YXJuaW5nIj7imqDvuI8gJyttLndhcm5pbmcrJzwvZGl2Pic7CiAgaWYobS5yYW5nZXMmJm0ucmFuZ2VzLmxlbmd0aCl7CiAgICBoKz0nPGRpdiBjbGFzcz0ibWluZm8tcmFuZ2VzIj48ZGl2IGNsYXNzPSJtaW5mby1yYW5nZS10aXRsZSI+UmVmZXJhbnMgRGVnZXJsZXI8L2Rpdj4nOwogICAgbS5yYW5nZXMuZm9yRWFjaChmdW5jdGlvbihyKXt2YXIgZGM9ci5jb2xvcj09PSJncmVlbiI/IiMxMGI5ODEiOnIuY29sb3I9PT0icmVkIj8iI2VmNDQ0NCI6IiNmNTllMGIiO2grPSc8ZGl2IGNsYXNzPSJtaW5mby1yYW5nZSI+PGRpdiBjbGFzcz0ibWluZm8tcmFuZ2UtZG90IiBzdHlsZT0iYmFja2dyb3VuZDonK2RjKyciPjwvZGl2PjxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOicrZGMrJyI+JytyLmxhYmVsKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrci5kZXNjKyc8L2Rpdj48L2Rpdj48L2Rpdj4nO30pOwogICAgaCs9JzwvZGl2Pic7CiAgfQogIGlmKG0uY2Fuc2xpbSkgaCs9JzxkaXYgY2xhc3M9Im1pbmZvLWNhbnNsaW0iPvCfk4ogQ0FOU0xJTTogJyttLmNhbnNsaW0rJzwvZGl2Pic7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1pbmZvQ29udGVudCIpLmlubmVySFRNTD1oOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikuY2xhc3NMaXN0LmFkZCgib3BlbiIpOwp9CmZ1bmN0aW9uIGNsb3NlSW5mb1BvcHVwKGUpe2lmKCFlfHxlLnRhcmdldD09PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikpe2RvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtaW5mb1BvcHVwIikuY2xhc3NMaXN0LnJlbW92ZSgib3BlbiIpO319Cgo8L3NjcmlwdD4KPC9zY3JpcHQ+CjxzY3JpcHQ+CnZhciBURl9EQVRBPSUlVEZfREFUQSUlOwp2YXIgUE9SVD0lJVBPUlQlJTsKdmFyIEVBUk5JTkdTX0RBVEE9JSVFQVJOSU5HU19EQVRBJSU7CnZhciBNQVJLRVRfREFUQT0lJU1BUktFVF9EQVRBJSU7CnZhciBORVdTX0RBVEE9JSVORVdTX0RBVEElJTsKdmFyIEFJX0RBVEE9JSVBSV9EQVRBJSU7CnZhciBXRUVLTFlfREFUQT0lJVdFRUtMWV9EQVRBJSU7CnZhciBTQ1JFRU5FUl9EQVRBPSUlU0NSRUVORVJfREFUQSUlOwp2YXIgY3VyVGFiPSJhbGwiLGN1clRmPSIxZCIsY3VyRGF0YT1URl9EQVRBWyIxZCJdLnNsaWNlKCk7CnZhciBtaW5pQ2hhcnRzPXt9LG1DaGFydD1udWxsOwp2YXIgU1M9ewogICJHVUNMVSBBTCI6e2JnOiJyZ2JhKDE2LDE4NSwxMjksLjEyKSIsYmQ6InJnYmEoMTYsMTg1LDEyOSwuMzUpIix0eDoiIzEwYjk4MSIsYWM6IiMxMGI5ODEiLGxibDoiR1VDTFUgQUwifSwKICAiQUwiOntiZzoicmdiYSg1MiwyMTEsMTUzLC4xKSIsYmQ6InJnYmEoNTIsMjExLDE1MywuMykiLHR4OiIjMzRkMzk5IixhYzoiIzM0ZDM5OSIsbGJsOiJBTCJ9LAogICJESUtLQVQiOntiZzoicmdiYSgyNDUsMTU4LDExLC4xKSIsYmQ6InJnYmEoMjQ1LDE1OCwxMSwuMykiLHR4OiIjZjU5ZTBiIixhYzoiI2Y1OWUwYiIsbGJsOiJESUtLQVQifSwKICAiWkFZSUYiOntiZzoicmdiYSgxMDcsMTE0LDEyOCwuMSkiLGJkOiJyZ2JhKDEwNywxMTQsMTI4LC4zKSIsdHg6IiM5Y2EzYWYiLGFjOiIjNmI3MjgwIixsYmw6IlpBWUlGIn0sCiAgIlNBVCI6e2JnOiJyZ2JhKDIzOSw2OCw2OCwuMTIpIixiZDoicmdiYSgyMzksNjgsNjgsLjM1KSIsdHg6IiNlZjQ0NDQiLGFjOiIjZWY0NDQ0IixsYmw6IlNBVCJ9Cn07CgpmdW5jdGlvbiBpYihrZXksbGFiZWwpewogIHJldHVybiBsYWJlbCsnIDxzcGFuIGNsYXNzPSJtaW5mbyIgb25jbGljaz0ic2hvd0luZm8oXCcnK2tleSsnXCcsZXZlbnQpIj4/PC9zcGFuPic7Cn0KCmZ1bmN0aW9uIHNldFRhYih0LGVsKXsKICBjdXJUYWI9dDsKICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIudGFiIikuZm9yRWFjaChmdW5jdGlvbihiKXtiLmNsYXNzTGlzdC5yZW1vdmUoImFjdGl2ZSIpO30pOwogIGVsLmNsYXNzTGlzdC5hZGQoImFjdGl2ZSIpOwogIHZhciB0ZlJvdz1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidGZSb3ciKTsKICBpZih0ZlJvdykgdGZSb3cuc3R5bGUuZGlzcGxheT0odD09PSJkYXNoYm9hcmQifHx0PT09ImVhcm5pbmdzInx8dD09PSJydXRpbiJ8fHQ9PT0iaGFmdGFsaWsifHx0PT09InNjcmVlbmVyIik/Im5vbmUiOiJmbGV4IjsKICBpZih0PT09ImRhc2hib2FyZCIpIHJlbmRlckRhc2hib2FyZCgpOwogIGVsc2UgaWYodD09PSJlYXJuaW5ncyIpIHJlbmRlckVhcm5pbmdzKCk7CiAgZWxzZSBpZih0PT09InJ1dGluIikgcmVuZGVyUnV0aW4oKTsKICBlbHNlIGlmKHQ9PT0iaGFmdGFsaWsiKSByZW5kZXJIYWZ0YWxpaygpOwogIGVsc2UgaWYodD09PSJzY3JlZW5lciIpIHJlbmRlclNjcmVlbmVyKCk7CiAgZWxzZSByZW5kZXJHcmlkKCk7Cn0KCmZ1bmN0aW9uIHNldFRmKHRmLGVsKXsKICBjdXJUZj10ZjsKICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIudGYtYnRuIikuZm9yRWFjaChmdW5jdGlvbihiKXtiLmNsYXNzTGlzdC50b2dnbGUoImFjdGl2ZSIsYi5kYXRhc2V0LnRmPT09dGYpO30pOwogIGN1ckRhdGE9KFRGX0RBVEFbdGZdfHxURl9EQVRBWyIxZCJdKS5zbGljZSgpOwogIHJlbmRlclN0YXRzKCk7CiAgcmVuZGVyR3JpZCgpOwp9CgpmdW5jdGlvbiBmaWx0ZXJlZCgpewogIHZhciBkPWN1ckRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pOwogIGlmKGN1clRhYj09PSJwb3J0IikgcmV0dXJuIGQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiBQT1JULmluY2x1ZGVzKHIudGlja2VyKTt9KTsKICBpZihjdXJUYWI9PT0iYnV5IikgcmV0dXJuIGQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiByLnNpbnlhbD09PSJHVUNMVSBBTCJ8fHIuc2lueWFsPT09IkFMIjt9KTsKICBpZihjdXJUYWI9PT0ic2VsbCIpIHJldHVybiBkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0iU0FUIjt9KTsKICByZXR1cm4gZDsKfQoKZnVuY3Rpb24gcmVuZGVyU3RhdHMoKXsKICB2YXIgZD1jdXJEYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KTsKICB2YXIgY250PXt9OwogIGQuZm9yRWFjaChmdW5jdGlvbihyKXtjbnRbci5zaW55YWxdPShjbnRbci5zaW55YWxdfHwwKSsxO30pOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJzdGF0cyIpLmlubmVySFRNTD0KICAgICc8ZGl2IGNsYXNzPSJwaWxsIGciPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+R3VjbHUgQWw6ICcrKGNudFsiR1VDTFUgQUwiXXx8MCkrJzwvZGl2PicrCiAgICAnPGRpdiBjbGFzcz0icGlsbCBnIj48ZGl2IGNsYXNzPSJkb3QiPjwvZGl2PkFsOiAnKyhjbnRbIkFMIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgeSI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5EaWtrYXQ6ICcrKGNudFsiRElLS0FUIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgciI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj5TYXQ6ICcrKGNudFsiU0FUIl18fDApKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgYiIgc3R5bGU9Im1hcmdpbi1sZWZ0OmF1dG8iPjxkaXYgY2xhc3M9ImRvdCI+PC9kaXY+UG9ydGZvbHlvOiAnK1BPUlQubGVuZ3RoKyc8L2Rpdj4nKwogICAgJzxkaXYgY2xhc3M9InBpbGwgbSI+PGRpdiBjbGFzcz0iZG90Ij48L2Rpdj4nK2QubGVuZ3RoKycgYW5hbGl6PC9kaXY+JzsKfQoKZnVuY3Rpb24gcmVuZGVyR3JpZCgpewogIE9iamVjdC52YWx1ZXMobWluaUNoYXJ0cykuZm9yRWFjaChmdW5jdGlvbihjKXtjLmRlc3Ryb3koKTt9KTsKICBtaW5pQ2hhcnRzPXt9OwogIHZhciBmPWZpbHRlcmVkKCk7CiAgdmFyIGdyaWQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdyaWQiKTsKICBpZighZi5sZW5ndGgpe2dyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xO3RleHQtYWxpZ246Y2VudGVyO3BhZGRpbmc6NDBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkhpc3NlIGJ1bHVuYW1hZGk8L2Rpdj4nO3JldHVybjt9CiAgZ3JpZC5pbm5lckhUTUw9Zi5tYXAoZnVuY3Rpb24ocil7cmV0dXJuIGJ1aWxkQ2FyZChyKTt9KS5qb2luKCIiKTsKICBmLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgY3R4PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtYy0iK3IudGlja2VyKTsKICAgIGlmKGN0eCYmci5jaGFydF9jbG9zZXMmJnIuY2hhcnRfY2xvc2VzLmxlbmd0aCl7CiAgICAgIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICAgICAgbWluaUNoYXJ0c1sibSIrci50aWNrZXJdPW5ldyBDaGFydChjdHgse3R5cGU6ImxpbmUiLGRhdGE6e2xhYmVsczpyLmNoYXJ0X2RhdGVzLGRhdGFzZXRzOlt7ZGF0YTpyLmNoYXJ0X2Nsb3Nlcyxib3JkZXJDb2xvcjpzcy5hYyxib3JkZXJXaWR0aDoxLjUsZmlsbDp0cnVlLGJhY2tncm91bmRDb2xvcjpzcy5hYysiMTgiLHBvaW50UmFkaXVzOjAsdGVuc2lvbjowLjR9XX0sb3B0aW9uczp7cGx1Z2luczp7bGVnZW5kOntkaXNwbGF5OmZhbHNlfX0sc2NhbGVzOnt4OntkaXNwbGF5OmZhbHNlfSx5OntkaXNwbGF5OmZhbHNlfX0sYW5pbWF0aW9uOntkdXJhdGlvbjo1MDB9LHJlc3BvbnNpdmU6dHJ1ZSxtYWludGFpbkFzcGVjdFJhdGlvOmZhbHNlfX0pOwogICAgfQogIH0pOwp9CgpmdW5jdGlvbiBidWlsZENhcmQocil7CiAgdmFyIHNzPVNTW3Iuc2lueWFsXXx8U1NbIkRJS0tBVCJdOwogIHZhciBkYz1yLmRlZ2lzaW0+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIGRzPShyLmRlZ2lzaW0+PTA/IisiOiIiKStyLmRlZ2lzaW0rIiUiOwogIHZhciBlc2NvbD1yLmVudHJ5X3Njb3JlPj03NT8idmFyKC0tZ3JlZW4pIjpyLmVudHJ5X3Njb3JlPj02MD8idmFyKC0tZ3JlZW4yKSI6ci5lbnRyeV9zY29yZT49NDU/InZhcigtLXllbGxvdykiOnIuZW50cnlfc2NvcmU+PTMwPyJ2YXIoLS1yZWQyKSI6InZhcigtLXJlZCkiOwogIHZhciBwdmNvbD1yLnByaWNlX3ZzX2NvbG9yPT09ImdyZWVuIj8idmFyKC0tZ3JlZW4pIjpyLnByaWNlX3ZzX2NvbG9yPT09InllbGxvdyI/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIHNpZ3M9WwogICAge2w6IlRyZW5kIix2OnIudHJlbmQ9PT0iWXVrc2VsZW4iPyJZdWtzZWxpeW9yIjpyLnRyZW5kPT09IkR1c2VuIj8iRHVzdXlvciI6IllhdGF5IixnOnIudHJlbmQ9PT0iWXVrc2VsZW4iP3RydWU6ci50cmVuZD09PSJEdXNlbiI/ZmFsc2U6bnVsbH0sCiAgICB7bDoiU01BNTAiLHY6ci5hYm92ZTUwPyJVemVyaW5kZSI6IkFsdGluZGEiLGc6ci5hYm92ZTUwfSwKICAgIHtsOiJTTUEyMDAiLHY6ci5hYm92ZTIwMD8iVXplcmluZGUiOiJBbHRpbmRhIixnOnIuYWJvdmUyMDB9LAogICAge2w6IlJTSSIsdjpyLnJzaXx8Ij8iLGc6ci5yc2k/ci5yc2k8MzA/dHJ1ZTpyLnJzaT43MD9mYWxzZTpudWxsOm51bGx9LAogICAge2w6IjUyVyIsdjoiJSIrci5wY3RfZnJvbV81MncrIiB1emFrIixnOnIubmVhcl81Mnd9CiAgXS5tYXAoZnVuY3Rpb24ocyl7cmV0dXJuICc8c3BhbiBjbGFzcz0ic3AgJysocy5nPT09dHJ1ZT8ic2ciOnMuZz09PWZhbHNlPyJzYiI6InNuIikrJyI+JytzLmwrIjogIitzLnYrIjwvc3Bhbj4iO30pLmpvaW4oIiIpOwogIHJldHVybiAnPGRpdiBjbGFzcz0iY2FyZCIgc3R5bGU9ImJvcmRlci1jb2xvcjonKyhyLnBvcnRmb2xpbz8icmdiYSgxNiwxODUsMTI5LC4yNSkiOnNzLmJkKSsnIiBvbmNsaWNrPSJvcGVuTShcJycrci50aWNrZXIrJ1wnKSI+JwogICAgKyc8ZGl2IGNsYXNzPSJhY2NlbnQiIHN0eWxlPSJiYWNrZ3JvdW5kOmxpbmVhci1ncmFkaWVudCg5MGRlZywnK3NzLmFjKycsJytzcy5hYysnODgpIj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImNib2R5Ij48ZGl2IGNsYXNzPSJjdG9wIj48ZGl2PjxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjRweCI+JwogICAgKyc8c3BhbiBjbGFzcz0idGlja2VyIiBzdHlsZT0iY29sb3I6Jytzcy50eCsnIj4nK3IudGlja2VyKyc8L3NwYW4+JwogICAgKyhyLnBvcnRmb2xpbz8nPHNwYW4gY2xhc3M9InBvcnQtYmFkZ2UiPlA8L3NwYW4+JzonJykrCiAgICAnPC9kaXY+PHNwYW4gY2xhc3M9ImJhZGdlIiBzdHlsZT0iYmFja2dyb3VuZDonK3NzLmJnKyc7Y29sb3I6Jytzcy50eCsnO2JvcmRlcjoxcHggc29saWQgJytzcy5iZCsnIj4nK3NzLmxibCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iY3ByIj48ZGl2IGNsYXNzPSJwdmFsIj4kJytyLmZpeWF0Kyc8L2Rpdj48ZGl2IGNsYXNzPSJwY2hnIiBzdHlsZT0iY29sb3I6JytkYysnIj4nK2RzKyc8L2Rpdj4nCiAgICArKHIucGVfZndkPyc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+RndkUEU6JytyLnBlX2Z3ZC50b0ZpeGVkKDEpKyc8L2Rpdj4nOicnKQogICAgKyc8L2Rpdj48L2Rpdj48ZGl2IGNsYXNzPSJzaWdzIj4nK3NpZ3MrJzwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0ibWFyZ2luLXRvcDo2cHgiPicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO21hcmdpbi1ib3R0b206M3B4Ij48c3BhbiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkdpcmlzIEthbGl0ZXNpPC9zcGFuPjxzcGFuIHN0eWxlPSJmb250LXNpemU6MTFweDtmb250LXdlaWdodDo3MDA7Y29sb3I6Jytlc2NvbCsnIj4nK3IuZW50cnlfc2NvcmUrJy8xMDA8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJoZWlnaHQ6NHB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjJweDtvdmVyZmxvdzpoaWRkZW4iPjxkaXYgc3R5bGU9ImhlaWdodDoxMDAlO3dpZHRoOicrci5lbnRyeV9zY29yZSsnJTtiYWNrZ3JvdW5kOicrZXNjb2wrJztib3JkZXItcmFkaXVzOjJweCI+PC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47bWFyZ2luLXRvcDozcHgiPjxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X2xhYmVsKyc8L3NwYW4+PHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6JytwdmNvbCsnIj4nK3IucHJpY2VfdnNfaWRlYWwrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzwvZGl2PjxkaXYgY2xhc3M9ImNoYXJ0LXciPjxjYW52YXMgaWQ9Im1jLScrci50aWNrZXIrJyI+PC9jYW52YXM+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJsdmxzIj4nCiAgICArJzxkaXYgY2xhc3M9Imx2Ij48ZGl2IGNsYXNzPSJsbCI+SGVtZW4gR2lyPC9kaXY+PGRpdiBjbGFzcz0ibHZhbCIgc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuMikiPiQnK3IuZW50cnlfYWdncmVzc2l2ZSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJsdiI+PGRpdiBjbGFzcz0ibGwiPkhlZGVmPC9kaXY+PGRpdiBjbGFzcz0ibHZhbCIgc3R5bGU9ImNvbG9yOiM2MGE1ZmEiPiQnK3IuaGVkZWYrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0ibHYiPjxkaXYgY2xhc3M9ImxsIj5TdG9wPC9kaXY+PGRpdiBjbGFzcz0ibHZhbCIgc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpIj4kJytyLnN0b3ArJzwvZGl2PjwvZGl2PicKICAgICsnPC9kaXY+PC9kaXY+PC9kaXY+JzsKfQoKZnVuY3Rpb24gcmVuZGVyRGFzaGJvYXJkKCl7CiAgdmFyIGdyaWQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdyaWQiKTsKICB2YXIgbWQ9TUFSS0VUX0RBVEF8fHt9OwogIHZhciBzcD1tZC5TUDUwMHx8e307CiAgdmFyIG5hcz1tZC5OQVNEQVF8fHt9OwogIHZhciB2aXg9bWQuVklYfHx7fTsKICB2YXIgbVNpZ25hbD1tZC5NX1NJR05BTHx8Ik5PVFIiOwogIHZhciBtTGFiZWw9bWQuTV9MQUJFTHx8IlZlcmkgeW9rIjsKICB2YXIgbUNvbG9yPW1TaWduYWw9PT0iR1VDTFUiPyJ2YXIoLS1ncmVlbikiOm1TaWduYWw9PT0iWkFZSUYiPyJ2YXIoLS1yZWQyKSI6InZhcigtLXllbGxvdykiOwogIHZhciBtQmc9bVNpZ25hbD09PSJHVUNMVSI/InJnYmEoMTYsMTg1LDEyOSwuMDgpIjptU2lnbmFsPT09IlpBWUlGIj8icmdiYSgyMzksNjgsNjgsLjA4KSI6InJnYmEoMjQ1LDE1OCwxMSwuMDgpIjsKICB2YXIgbUJvcmRlcj1tU2lnbmFsPT09IkdVQ0xVIj8icmdiYSgxNiwxODUsMTI5LC4yNSkiOm1TaWduYWw9PT0iWkFZSUYiPyJyZ2JhKDIzOSw2OCw2OCwuMjUpIjoicmdiYSgyNDUsMTU4LDExLC4yNSkiOwogIHZhciBtSWNvbj1tU2lnbmFsPT09IkdVQ0xVIj8i4pyFIjptU2lnbmFsPT09IlpBWUlGIj8i4p2MIjoi4pqg77iPIjsKCiAgZnVuY3Rpb24gaW5kZXhDYXJkKG5hbWUsZGF0YSl7CiAgICBpZighZGF0YXx8IWRhdGEucHJpY2UpIHJldHVybiAiIjsKICAgIHZhciBjYz1kYXRhLmNoYW5nZT49MD8idmFyKC0tZ3JlZW4yKSI6InZhcigtLXJlZDIpIjsKICAgIHZhciBjcz0oZGF0YS5jaGFuZ2U+PTA/IisiOiIiKStkYXRhLmNoYW5nZSsiJSI7CiAgICB2YXIgczUwPWRhdGEuYWJvdmU1MD8nPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6MTBweCI+U01BNTAg4pyTPC9zcGFuPic6JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKTtmb250LXNpemU6MTBweCI+U01BNTAg4pyXPC9zcGFuPic7CiAgICB2YXIgczIwMD1kYXRhLmFib3ZlMjAwPyc8c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tZ3JlZW4pO2ZvbnQtc2l6ZToxMHB4Ij5TTUEyMDAg4pyTPC9zcGFuPic6JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1yZWQyKTtmb250LXNpemU6MTBweCI+U01BMjAwIOKclzwvc3Bhbj4nOwogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHggMTZweDtmbGV4OjE7bWluLXdpZHRoOjE1MHB4Ij4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NnB4Ij4nK25hbWUrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpIj4kJytkYXRhLnByaWNlKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxM3B4O2NvbG9yOicrY2MrJzttYXJnaW4tYm90dG9tOjhweCI+JytjcysnPC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6OHB4Ij4nK3M1MCtzMjAwKyc8L2Rpdj48L2Rpdj4nOwogIH0KCiAgdmFyIHBvcnREYXRhPWN1ckRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhJiZQT1JULmluY2x1ZGVzKHIudGlja2VyKTt9KTsKICB2YXIgcG9ydEh0bWw9IiI7CiAgaWYocG9ydERhdGEubGVuZ3RoKXsKICAgIHBvcnRIdG1sPSc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMnB4Ij7wn5K8IFBvcnRmw7Z5IMOWemV0aTwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOnJlcGVhdChhdXRvLWZpbGwsbWlubWF4KDE0MHB4LDFmcikpO2dhcDo4cHgiPic7CiAgICBwb3J0RGF0YS5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgICB2YXIgZGM9ci5kZWdpc2ltPj0wPyJ2YXIoLS1ncmVlbjIpIjoidmFyKC0tcmVkMikiOwogICAgICB2YXIgc3M9U1Nbci5zaW55YWxdfHxTU1siRElLS0FUIl07CiAgICAgIHBvcnRIdG1sKz0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgJytzcy5iZCsnO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweDtjdXJzb3I6cG9pbnRlciIgb25jbGljaz0ib3Blbk0oXCcnK3IudGlja2VyKydcJykiPicKICAgICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbTo0cHgiPicKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpCZWJhcyBOZXVlLHNhbnMtc2VyaWY7Zm9udC1zaXplOjE2cHg7bGV0dGVyLXNwYWNpbmc6MnB4O2NvbG9yOicrc3MudHgrJyI+JytyLnRpY2tlcisnPC9zcGFuPicKICAgICAgICArJzxzcGFuIHN0eWxlPSJmb250LXNpemU6OXB4O2JhY2tncm91bmQ6Jytzcy5iZysnO2NvbG9yOicrc3MudHgrJztwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czoycHgiPicrc3MubGJsKyc8L3NwYW4+PC9kaXY+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMCI+JCcrci5maXlhdCsnPC9kaXY+JwogICAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMXB4O2NvbG9yOicrZGMrJyI+Jysoci5kZWdpc2ltPj0wPyIrIjoiIikrci5kZWdpc2ltKyclPC9kaXY+PC9kaXY+JzsKICAgIH0pOwogICAgcG9ydEh0bWwrPSc8L2Rpdj48L2Rpdj4nOwogIH0KCiAgdmFyIHVyZ2VudEVhcm5pbmdzPUVBUk5JTkdTX0RBVEEuZmlsdGVyKGZ1bmN0aW9uKGUpe3JldHVybiBlLmFsZXJ0PT09InJlZCJ8fGUuYWxlcnQ9PT0ieWVsbG93Ijt9KTsKICB2YXIgZWFybmluZ3NBbGVydD0iIjsKICBpZih1cmdlbnRFYXJuaW5ncy5sZW5ndGgpewogICAgZWFybmluZ3NBbGVydD0nPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDI0NSwxNTgsMTEsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjQ1LDE1OCwxMSwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTRweCAxNnB4O21hcmdpbi1ib3R0b206MTRweCI+JwogICAgICArJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLXllbGxvdyk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPuKaoO+4jyBZYWtsYcWfYW4gUmFwb3JsYXI8L2Rpdj4nOwogICAgdXJnZW50RWFybmluZ3MuZm9yRWFjaChmdW5jdGlvbihlKXsKICAgICAgdmFyIGljPWUuYWxlcnQ9PT0icmVkIj8i8J+UtCI6IvCfn6EiOwogICAgICBlYXJuaW5nc0FsZXJ0Kz0nPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjttYXJnaW4tYm90dG9tOjZweDtmb250LXNpemU6MTJweCI+JwogICAgICAgICsnPHNwYW4+JytpYysnIDxzdHJvbmc+JytlLnRpY2tlcisnPC9zdHJvbmc+PC9zcGFuPicKICAgICAgICArJzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCkiPicrZS5uZXh0X2RhdGUrJyAoJysoZS5kYXlzX3RvX2Vhcm5pbmdzPT09MD8iQlVHw5xOIjplLmRheXNfdG9fZWFybmluZ3MrIiBnw7xuIikrJyk8L3NwYW4+PC9kaXY+JzsKICAgIH0pOwogICAgZWFybmluZ3NBbGVydCs9JzwvZGl2Pic7CiAgfQoKICB2YXIgbmV3c0h0bWw9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCI+JwogICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEycHgiPvCfk7AgU29uIEhhYmVybGVyPC9kaXY+JzsKICBpZihORVdTX0RBVEEmJk5FV1NfREFUQS5sZW5ndGgpewogICAgTkVXU19EQVRBLnNsaWNlKDAsMTApLmZvckVhY2goZnVuY3Rpb24obil7CiAgICAgIHZhciBwYj1uLnBvcnRmb2xpbz8nPHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4xMik7Y29sb3I6dmFyKC0tZ3JlZW4pO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yNSk7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZTo5cHg7Zm9udC13ZWlnaHQ6NjAwIj5QPC9zcGFuPic6IiI7CiAgICAgIHZhciB0YT0iIjsKICAgICAgaWYobi5kYXRldGltZSl7dmFyIGRpZmY9TWF0aC5mbG9vcigoRGF0ZS5ub3coKS8xMDAwLW4uZGF0ZXRpbWUpLzM2MDApO3RhPWRpZmY8MjQ/KGRpZmYrInMgw7ZuY2UiKTooTWF0aC5mbG9vcihkaWZmLzI0KSsiZyDDtm5jZSIpO30KICAgICAgbmV3c0h0bWwrPSc8ZGl2IHN0eWxlPSJwYWRkaW5nOjEwcHggMDtib3JkZXItYm90dG9tOjFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNCkiPicKICAgICAgICArJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjZweDttYXJnaW4tYm90dG9tOjRweCI+JwogICAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS15ZWxsb3cpIj4nK24udGlja2VyKyc8L3NwYW4+JytwYgogICAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1sZWZ0OmF1dG8iPicrdGErJzwvc3Bhbj48L2Rpdj4nCiAgICAgICAgKyc8YSBocmVmPSInK24udXJsKyciIHRhcmdldD0iX2JsYW5rIiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tdGV4dCk7dGV4dC1kZWNvcmF0aW9uOm5vbmU7bGluZS1oZWlnaHQ6MS41O2Rpc3BsYXk6YmxvY2siPicrKG4uaGVhZGxpbmVfdHJ8fG4uaGVhZGxpbmUpKyc8L2E+JwogICAgICAgICsobi5zdW1tYXJ5X3RyfHxuLnN1bW1hcnk/JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOiM5Y2EzYWY7bWFyZ2luLXRvcDo0cHg7bGluZS1oZWlnaHQ6MS40Ij4nKyhuLnN1bW1hcnlfdHJ8fG4uc3VtbWFyeSkuc3Vic3RyaW5nKDAsMTUwKSsnLi4uPC9kaXY+JzonJykrJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tdG9wOjNweCI+JytuLnNvdXJjZSsnPC9kaXY+PC9kaXY+JzsKICAgIH0pOwogIH0gZWxzZSB7CiAgICBuZXdzSHRtbCs9JzxkaXYgc3R5bGU9ImNvbG9yOnZhcigtLW11dGVkKTtmb250LXNpemU6MTJweCI+SGFiZXIgYnVsdW5hbWFkaTwvZGl2Pic7CiAgfQogIG5ld3NIdG1sKz0nPC9kaXY+JzsKCiAgZ3JpZC5pbm5lckhUTUw9JzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPicKICAgICsnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDonK21CZysnO2JvcmRlcjoxcHggc29saWQgJyttQm9yZGVyKyc7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweDtkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2ZsZXgtd3JhcDp3cmFwO2dhcDoxMnB4Ij4nCiAgICArJzxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjFweDttYXJnaW4tYm90dG9tOjRweCI+Q0FOU0xJTSBNIEtSxLBURVLEsDwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrbUNvbG9yKyciPicrbUljb24rJyAnK21MYWJlbCsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7dGV4dC1hbGlnbjpyaWdodCI+VklYOiAnKyh2aXgucHJpY2V8fCI/IikrJzxicj4nCiAgICArJzxzcGFuIHN0eWxlPSJjb2xvcjonKyh2aXgucHJpY2UmJnZpeC5wcmljZT4yNT8idmFyKC0tcmVkMikiOiJ2YXIoLS1ncmVlbikiKSsnIj4nKyh2aXgucHJpY2UmJnZpeC5wcmljZT4yNT8iWcO8a3NlayB2b2xhdGlsaXRlIjoiTm9ybWFsIHZvbGF0aWxpdGUiKSsnPC9zcGFuPjwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2ZsZXgtd3JhcDp3cmFwO21hcmdpbi1ib3R0b206MTRweCI+JytpbmRleENhcmQoIlMmUCA1MDAgKFNQWSkiLHNwKStpbmRleENhcmQoIk5BU0RBUSAoUVFRKSIsbmFzKSsnPC9kaXY+JwogICAgK3BvcnRIdG1sK2Vhcm5pbmdzQWxlcnQrbmV3c0h0bWwrJzwvZGl2Pic7Cn0KCmZ1bmN0aW9uIHJlbmRlckVhcm5pbmdzKCl7CiAgdmFyIGdyaWQ9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdyaWQiKTsKICB2YXIgc29ydGVkPUVBUk5JTkdTX0RBVEEuZmlsdGVyKGZ1bmN0aW9uKGUpe3JldHVybiBlLm5leHRfZGF0ZTt9KS5zb3J0KGZ1bmN0aW9uKGEsYil7CiAgICB2YXIgZGE9YS5kYXlzX3RvX2Vhcm5pbmdzIT1udWxsP2EuZGF5c190b19lYXJuaW5nczo5OTk7CiAgICB2YXIgZGI9Yi5kYXlzX3RvX2Vhcm5pbmdzIT1udWxsP2IuZGF5c190b19lYXJuaW5nczo5OTk7CiAgICByZXR1cm4gZGEtZGI7CiAgfSk7CiAgdmFyIG5vRGF0ZT1FQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gIWUubmV4dF9kYXRlO30pOwogIGlmKCFzb3J0ZWQubGVuZ3RoJiYhbm9EYXRlLmxlbmd0aCl7Z3JpZC5pbm5lckhUTUw9JzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTE7dGV4dC1hbGlnbjpjZW50ZXI7cGFkZGluZzo0MHB4O2NvbG9yOnZhcigtLW11dGVkKSI+RWFybmluZ3MgdmVyaXNpIGJ1bHVuYW1hZGk8L2Rpdj4nO3JldHVybjt9CiAgdmFyIGg9JzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CiAgc29ydGVkLmZvckVhY2goZnVuY3Rpb24oZSl7CiAgICB2YXIgYWI9ZS5hbGVydD09PSJyZWQiPyJyZ2JhKDIzOSw2OCw2OCwuMTIpIjplLmFsZXJ0PT09InllbGxvdyI/InJnYmEoMjQ1LDE1OCwxMSwuMSkiOiJyZ2JhKDI1NSwyNTUsMjU1LC4wMikiOwogICAgdmFyIGFiZD1lLmFsZXJ0PT09InJlZCI/InJnYmEoMjM5LDY4LDY4LC4zNSkiOmUuYWxlcnQ9PT0ieWVsbG93Ij8icmdiYSgyNDUsMTU4LDExLC4zKSI6InJnYmEoMjU1LDI1NSwyNTUsLjA3KSI7CiAgICB2YXIgYWk9ZS5hbGVydD09PSJyZWQiPyLwn5S0IjplLmFsZXJ0PT09InllbGxvdyI/IvCfn6EiOiLwn5OFIjsKICAgIHZhciBkdD1lLmRheXNfdG9fZWFybmluZ3MhPW51bGw/KGUuZGF5c190b19lYXJuaW5ncz09PTA/IkJVR1VOIjplLmRheXNfdG9fZWFybmluZ3M9PT0xPyJZYXJpbiI6ZS5kYXlzX3RvX2Vhcm5pbmdzKyIgZ3VuIHNvbnJhIik6IiI7CiAgICB2YXIgYW1Db2w9ZS5hdmdfbW92ZV9wY3QhPW51bGw/KGUuYXZnX21vdmVfcGN0Pj0wPyJ2YXIoLS1ncmVlbikiOiJ2YXIoLS1yZWQyKSIpOiJ2YXIoLS1tdXRlZCkiOwogICAgdmFyIGFtU3RyPWUuYXZnX21vdmVfcGN0IT1udWxsPyhlLmF2Z19tb3ZlX3BjdD49MD8iKyI6IiIpK2UuYXZnX21vdmVfcGN0KyIlIjoi4oCUIjsKICAgIHZhciB5Yj1lLmFsZXJ0PT09InJlZCI/JzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Y29sb3I6dmFyKC0tcmVkMik7cGFkZGluZzoycHggOHB4O2JvcmRlci1yYWRpdXM6M3B4O2ZvbnQtc2l6ZToxMHB4O2ZvbnQtd2VpZ2h0OjcwMCI+WUFLSU5EQTwvc3Bhbj4nOiIiOwogICAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JythYisnO2JvcmRlcjoxcHggc29saWQgJythYmQrJztib3JkZXItcmFkaXVzOjEwcHg7bWFyZ2luLWJvdHRvbToxMHB4O3BhZGRpbmc6MTRweCAxNnB4Ij4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47ZmxleC13cmFwOndyYXA7Z2FwOjhweCI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDoxMHB4Ij48c3Bhbj4nK2FpKyc8L3NwYW4+PHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OkJlYmFzIE5ldWUsc2Fucy1zZXJpZjtmb250LXNpemU6MjBweDtsZXR0ZXItc3BhY2luZzoycHg7Y29sb3I6dmFyKC0tdGV4dCkiPicrZS50aWNrZXIrJzwvc3Bhbj4nK3liKyc8L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtnYXA6MTZweDtmbGV4LXdyYXA6d3JhcDthbGlnbi1pdGVtczpjZW50ZXIiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5SQVBPUjwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tdGV4dCkiPicrKGUubmV4dF9kYXRlfHwi4oCUIikrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOicrKGUuYWxlcnQ9PT0icmVkIj8idmFyKC0tcmVkMikiOmUuYWxlcnQ9PT0ieWVsbG93Ij8idmFyKC0teWVsbG93KSI6InZhcigtLW11dGVkKSIpKyciPicrZHQrJzwvZGl2PjwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5FUFMgVEFITUlOPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMnB4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjojNjBhNWZhIj4nKyhlLmVwc19lc3RpbWF0ZSE9bnVsbD8iJCIrZS5lcHNfZXN0aW1hdGU6IuKAlCIpKyc8L2Rpdj48L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9InRleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+T1JULkhBUkVLRVQ8L2Rpdj48ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjE0cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrYW1Db2wrJyI+JythbVN0cisnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjhweDtjb2xvcjp2YXIoLS1tdXRlZCkiPnNvbiA0IHJhcG9yPC9kaXY+PC9kaXY+JzsKICAgIGgrPSc8L2Rpdj48L2Rpdj4nOwogICAgaWYoZS5oaXN0b3J5X2VwcyYmZS5oaXN0b3J5X2Vwcy5sZW5ndGgpewogICAgICBoKz0nPGRpdiBzdHlsZT0ibWFyZ2luLXRvcDo4cHg7cGFkZGluZy10b3A6OHB4O2JvcmRlci10b3A6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA2KSI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo1cHgiPlNPTiA0IFJBUE9SPC9kaXY+PGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoNCwxZnIpO2dhcDo0cHgiPic7CiAgICAgIGUuaGlzdG9yeV9lcHMuZm9yRWFjaChmdW5jdGlvbihoaCl7CiAgICAgICAgdmFyIHNjPWhoLnN1cnByaXNlX3BjdCE9bnVsbD8oaGguc3VycHJpc2VfcGN0PjA/InZhcigtLWdyZWVuKSI6InZhcigtLXJlZDIpIik6InZhcigtLW11dGVkKSI7CiAgICAgICAgaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjRweDtwYWRkaW5nOjZweDt0ZXh0LWFsaWduOmNlbnRlcjtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA1KSI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjhweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicraGguZGF0ZS5zdWJzdHJpbmcoMCw3KSsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtc2l6ZToxMHB4Ij4nKyhoaC5hY3R1YWwhPW51bGw/IiQiK2hoLmFjdHVhbDoiPyIpKyc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOicrc2MrJyI+JysoaGguc3VycHJpc2VfcGN0IT1udWxsPyhoaC5zdXJwcmlzZV9wY3Q+MD8iKyI6IiIpK2hoLnN1cnByaXNlX3BjdCsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JzsKICAgICAgfSk7CiAgICAgIGgrPSc8L2Rpdj48L2Rpdj4nOwogICAgfQogICAgaCs9JzwvZGl2Pic7CiAgfSk7CiAgaWYobm9EYXRlLmxlbmd0aCl7aCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tdG9wOjZweCI+VGFyaWggYnVsdW5hbWF5YW46ICcrbm9EYXRlLm1hcChmdW5jdGlvbihlKXtyZXR1cm4gZS50aWNrZXI7fSkuam9pbigiLCAiKSsnPC9kaXY+Jzt9CiAgaCs9JzwvZGl2Pic7CiAgZ3JpZC5pbm5lckhUTUw9aDsKfQoKZnVuY3Rpb24gb3Blbk0odGlja2VyKXsKICB2YXIgcj1jdXJEYXRhLmZpbmQoZnVuY3Rpb24oZCl7cmV0dXJuIGQudGlja2VyPT09dGlja2VyO30pOwogIGlmKCFyfHxyLmhhdGEpIHJldHVybjsKICBpZihtQ2hhcnQpe21DaGFydC5kZXN0cm95KCk7bUNoYXJ0PW51bGw7fQogIHZhciBzcz1TU1tyLnNpbnlhbF18fFNTWyJESUtLQVQiXTsKICB2YXIgcnJQPU1hdGgubWluKChyLnJyLzQpKjEwMCwxMDApOwogIHZhciByckM9ci5ycj49Mz8idmFyKC0tZ3JlZW4pIjpyLnJyPj0yPyJ2YXIoLS1ncmVlbjIpIjpyLnJyPj0xPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkMikiOwogIHZhciBkYz1yLmRlZ2lzaW0+PTA/InZhcigtLWdyZWVuMikiOiJ2YXIoLS1yZWQyKSI7CiAgdmFyIGtjPXsiR1VDTFUgQUwiOiIjMTBiOTgxIiwiQUwiOiIjMzRkMzk5IiwiRElLS0FUTEkiOiIjZjU5ZTBiIiwiR0VDTUUiOiIjZjg3MTcxIn07CiAgdmFyIGtsYmw9eyJHVUNMVSBBTCI6IkdVQ0xVIEFMIiwiQUwiOiJBTCIsIkRJS0tBVExJIjoiRElLS0FUTEkiLCJHRUNNRSI6IkdFQ01FIn07CiAgdmFyIGVzY29sPXIuZW50cnlfc2NvcmU+PTc1PyJ2YXIoLS1ncmVlbikiOnIuZW50cnlfc2NvcmU+PTYwPyJ2YXIoLS1ncmVlbjIpIjpyLmVudHJ5X3Njb3JlPj00NT8idmFyKC0teWVsbG93KSI6ci5lbnRyeV9zY29yZT49MzA/InZhcigtLXJlZDIpIjoidmFyKC0tcmVkKSI7CiAgdmFyIHB2Y29sPXIucHJpY2VfdnNfY29sb3I9PT0iZ3JlZW4iPyJ2YXIoLS1ncmVlbikiOnIucHJpY2VfdnNfY29sb3I9PT0ieWVsbG93Ij8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZDIpIjsKCiAgdmFyIG1oPSc8ZGl2IGNsYXNzPSJtaGVhZCI+PGRpdj48ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDo4cHg7ZmxleC13cmFwOndyYXAiPicKICAgICsnPHNwYW4gY2xhc3M9Im10aXRsZSIgc3R5bGU9ImNvbG9yOicrc3MudHgrJyI+JytyLnRpY2tlcisnPC9zcGFuPicKICAgICsnPHNwYW4gY2xhc3M9ImJhZGdlIiBzdHlsZT0iYmFja2dyb3VuZDonK3NzLmJnKyc7Y29sb3I6Jytzcy50eCsnO2JvcmRlcjoxcHggc29saWQgJytzcy5iZCsnO2ZvbnQtc2l6ZToxMnB4Ij4nK3NzLmxibCsnPC9zcGFuPicKICAgICsoci5wb3J0Zm9saW8/JzxzcGFuIGNsYXNzPSJwb3J0LWJhZGdlIiBzdHlsZT0iZm9udC1zaXplOjExcHg7cGFkZGluZzozcHggOHB4Ij5Qb3J0Zm9seW88L3NwYW4+JzonJykKICAgICsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlO2ZvbnQtd2VpZ2h0OjYwMDttYXJnaW4tdG9wOjRweCI+JCcrci5maXlhdAogICAgKycgPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOicrZGMrJyI+Jysoci5kZWdpc2ltPj0wPyIrIjoiIikrci5kZWdpc2ltKyclPC9zcGFuPjwvZGl2PjwvZGl2PicKICAgICsnPGJ1dHRvbiBjbGFzcz0ibWNsb3NlIiBvbmNsaWNrPSJjbG9zZU0oKSI+4pyVPC9idXR0b24+PC9kaXY+JzsKCiAgbWgrPSc8ZGl2IGNsYXNzPSJtYm9keSI+PGRpdiBjbGFzcz0ibWNoYXJ0dyI+PGNhbnZhcyBpZD0ibWNoYXJ0Ij48L2NhbnZhcz48L2Rpdj4nOwoKICBtaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDttYXJnaW4tYm90dG9tOjEycHgiPicKICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+JytpYigiRW50cnlTY29yZSIsIkdpcmlzIEthbGl0ZXNpIikrJzwvZGl2PicKICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjttYXJnaW4tYm90dG9tOjZweCI+JwogICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonK2VzY29sKyciPicrci5lbnRyeV9zY29yZSsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2NvbG9yOnZhcigtLW11dGVkKSI+LzEwMDwvc3Bhbj48L3NwYW4+JwogICAgKyc8c3BhbiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOicrZXNjb2wrJyI+JytyLmVudHJ5X2xhYmVsKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJoZWlnaHQ6NnB4O2JhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXItcmFkaXVzOjNweDtvdmVyZmxvdzpoaWRkZW47bWFyZ2luLWJvdHRvbTo4cHgiPjxkaXYgc3R5bGU9ImhlaWdodDoxMDAlO3dpZHRoOicrci5lbnRyeV9zY29yZSsnJTtiYWNrZ3JvdW5kOicrZXNjb2wrJztib3JkZXItcmFkaXVzOjNweCI+PC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47Zm9udC1zaXplOjExcHgiPicKICAgICsnPGRpdj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj5TdSBhbmtpIGZpeWF0OiA8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOicrcHZjb2wrJztmb250LXdlaWdodDo2MDAiPicrci5wcmljZV92c19pZGVhbCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdj48c3BhbiBzdHlsZT0iY29sb3I6dmFyKC0tbXV0ZWQpIj5JZGVhbCBib2xnZTogPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbjIpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5pZGVhbF9lbnRyeV9sb3crJyAtICQnK3IuaWRlYWxfZW50cnlfaGlnaCsnPC9zcGFuPjwvZGl2PicKICAgICsnPC9kaXY+PC9kaXY+JzsKCiAgbWgrPSc8ZGl2IGNsYXNzPSJkYm94IiBzdHlsZT0iYmFja2dyb3VuZDonK3NzLmJnKyc7Ym9yZGVyLWNvbG9yOicrc3MuYmQrJzttYXJnaW4tYm90dG9tOjEycHgiPicKICAgICsnPGRpdiBjbGFzcz0iZGxibCIgc3R5bGU9ImNvbG9yOicrc3MudHgrJyI+JytpYigiUlIiLCJBbGltIEthcmFyaSBSL1IiKSsnPC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkdmVyZCIgc3R5bGU9ImNvbG9yOicrKGtjW3Iua2FyYXJdfHwidmFyKC0tbXV0ZWQpIikrJyI+Jysoa2xibFtyLmthcmFyXXx8ci5rYXJhcikrJzwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPlJpc2sgLyBPZHVsPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjonK3JyQysnO2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPjEgOiAnK3IucnIrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5IZW1lbiBHaXI8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuMik7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmVudHJ5X2FnZ3Jlc3NpdmUrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5HZXJpIENla2lsbWU8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOiM2MGE1ZmE7Zm9udC1mYW1pbHk6SmV0QnJhaW5zIE1vbm8sbW9ub3NwYWNlIj4kJytyLmVudHJ5X21pZCsnPC9zcGFuPjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZHJvdyI+PHNwYW4gY2xhc3M9ImRrZXkiPkJ1eXVrIER1emVsdG1lPC9zcGFuPjxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS15ZWxsb3cpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5lbnRyeV9jb25zZXJ2YXRpdmUrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5IZWRlZjwvc3Bhbj48c3BhbiBzdHlsZT0iY29sb3I6IzYwYTVmYTtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2UiPiQnK3IuaGVkZWYrJzwvc3Bhbj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRyb3ciPjxzcGFuIGNsYXNzPSJka2V5Ij5TdG9wLUxvc3M8L3NwYW4+PHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLXJlZDIpO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZSI+JCcrci5zdG9wKyc8L3NwYW4+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJycmJhciI+PGRpdiBjbGFzcz0icnJmaWxsIiBzdHlsZT0id2lkdGg6JytyclArJyU7YmFja2dyb3VuZDonK3JyQysnIj48L2Rpdj48L2Rpdj48L2Rpdj4nOwoKICBtaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPlRla25payBBbmFsaXo8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRncmlkIiBzdHlsZT0ibWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiVHJlbmQiLCJUcmVuZCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIudHJlbmQ9PT0iWXVrc2VsZW4iPyJ2YXIoLS1ncmVlbikiOnIudHJlbmQ9PT0iRHVzZW4iPyJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+JytyLnRyZW5kKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiUlNJIiwiUlNJIDE0IikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5yc2k/ci5yc2k8MzA/InZhcigtLWdyZWVuKSI6ci5yc2k+NzA/InZhcigtLXJlZCkiOiJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5yc2l8fCI/IikrKHIucnNpP3IucnNpPDMwPyIgQXNpcmkgU2F0aW0iOnIucnNpPjcwPyIgQXNpcmkgQWxpbSI6IiBOb3RyIjoiIikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJTTUE1MCIsIlNNQSA1MCIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuYWJvdmU1MD8idmFyKC0tZ3JlZW4pIjoidmFyKC0tcmVkKSIpKyciPicrKHIuYWJvdmU1MD8iVXplcmluZGUiOiJBbHRpbmRhIikrKHIuc21hNTBfZGlzdCE9bnVsbD8iICgiK3Iuc21hNTBfZGlzdCsiJSkiOiIiKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlNNQTIwMCIsIlNNQSAyMDAiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmFib3ZlMjAwPyJ2YXIoLS1ncmVlbikiOiJ2YXIoLS1yZWQpIikrJyI+Jysoci5hYm92ZTIwMD8iVXplcmluZGUiOiJBbHRpbmRhIikrKHIuc21hMjAwX2Rpc3QhPW51bGw/IiAoIityLnNtYTIwMF9kaXN0KyIlKSI6IiIpKyc8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiNTJXIiwiNTJIIFBvei4iKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnc1Ml9wb3NpdGlvbjw9MzA/InZhcigtLWdyZWVuKSI6ci53NTJfcG9zaXRpb24+PTg1PyJ2YXIoLS1yZWQpIjoidmFyKC0teWVsbG93KSIpKyciPicrci53NTJfcG9zaXRpb24rJyU8L2Rpdj48L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiSGFjaW0iLCJIYWNpbSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIuaGFjaW09PT0iWXVrc2VrIj8idmFyKC0tZ3JlZW4pIjpyLmhhY2ltPT09IkR1c3VrIj8idmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrci5oYWNpbSsnICgnK3Iudm9sX3JhdGlvKyd4KTwvZGl2PjwvZGl2PicKICAgICsnPC9kaXY+JzsKCiAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Ij5UZW1lbCBBbmFsaXo8L2Rpdj4nCiAgICArJzxkaXYgY2xhc3M9ImRncmlkIiBzdHlsZT0ibWFyZ2luLWJvdHRvbToxMnB4Ij4nCiAgICArJzxkaXYgY2xhc3M9ImRjIj48ZGl2IGNsYXNzPSJkbCI+JytpYigiRm9yd2FyZFBFIiwiRm9yd2FyZCBQRSIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucGVfZndkP3IucGVfZndkPDI1PyJ2YXIoLS1ncmVlbikiOnIucGVfZndkPDQwPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucGVfZndkP3IucGVfZndkLnRvRml4ZWQoMSk6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlBFRyIsIlBFRyIpKyc8L2Rpdj48ZGl2IGNsYXNzPSJkdiIgc3R5bGU9ImNvbG9yOicrKHIucGVnP3IucGVnPDE/InZhcigtLWdyZWVuKSI6ci5wZWc8Mj8idmFyKC0teWVsbG93KSI6InZhcigtLXJlZCkiOiJ2YXIoLS1tdXRlZCkiKSsnIj4nKyhyLnBlZz9yLnBlZy50b0ZpeGVkKDIpOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJFUFNHcm93dGgiLCJFUFMgQsO8ecO8bWUiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLmVwc19ncm93dGg/ci5lcHNfZ3Jvd3RoPj0yMD8idmFyKC0tZ3JlZW4pIjpyLmVwc19ncm93dGg+PTA/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5lcHNfZ3Jvd3RoIT1udWxsP3IuZXBzX2dyb3d0aCsiJSI6Ij8iKSsnPC9kaXY+PC9kaXY+JwogICAgKyc8ZGl2IGNsYXNzPSJkYyI+PGRpdiBjbGFzcz0iZGwiPicraWIoIlJldkdyb3d0aCIsIkdlbGlyIELDvHnDvG1lIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5yZXZfZ3Jvd3RoP3IucmV2X2dyb3d0aD49MTU/InZhcigtLWdyZWVuKSI6ci5yZXZfZ3Jvd3RoPj0wPyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIucmV2X2dyb3d0aCE9bnVsbD9yLnJldl9ncm93dGgrIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJOZXRNYXJnaW4iLCJOZXQgTWFyamluIikrJzwvZGl2PjxkaXYgY2xhc3M9ImR2IiBzdHlsZT0iY29sb3I6Jysoci5uZXRfbWFyZ2luP3IubmV0X21hcmdpbj49MTU/InZhcigtLWdyZWVuKSI6ci5uZXRfbWFyZ2luPj01PyJ2YXIoLS15ZWxsb3cpIjoidmFyKC0tcmVkKSI6InZhcigtLW11dGVkKSIpKyciPicrKHIubmV0X21hcmdpbiE9bnVsbD9yLm5ldF9tYXJnaW4rIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPGRpdiBjbGFzcz0iZGMiPjxkaXYgY2xhc3M9ImRsIj4nK2liKCJST0UiLCJST0UiKSsnPC9kaXY+PGRpdiBjbGFzcz0iZHYiIHN0eWxlPSJjb2xvcjonKyhyLnJvZT9yLnJvZT49MTU/InZhcigtLWdyZWVuKSI6ci5yb2U+PTU/InZhcigtLXllbGxvdykiOiJ2YXIoLS1yZWQpIjoidmFyKC0tbXV0ZWQpIikrJyI+Jysoci5yb2UhPW51bGw/ci5yb2UrIiUiOiI/IikrJzwvZGl2PjwvZGl2PicKICAgICsnPC9kaXY+JzsKCiAgdmFyIGFpVGV4dCA9IEFJX0RBVEEgJiYgQUlfREFUQVt0aWNrZXJdOwogIGlmKGFpVGV4dCl7CiAgICBtaCs9JzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7bWFyZ2luLWJvdHRvbToxMnB4Ij4nOwogICAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOiM2MGE1ZmE7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjhweCI+8J+kliBBSSBBbmFsaXogKENsYXVkZSBTb25uZXQpPC9kaXY+JzsKICAgIG1oKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6dmFyKC0tdGV4dCk7bGluZS1oZWlnaHQ6MS43O3doaXRlLXNwYWNlOnByZS13cmFwIj4nK2FpVGV4dCsnPC9kaXY+JzsKICAgIG1oKz0nPC9kaXY+JzsKICB9CiAgbWgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7dGV4dC1hbGlnbjpjZW50ZXIiPkJ1IGFyYWMgeWF0aXJpbSB0YXZzaXllc2kgZGVnaWxkaXI8L2Rpdj48L2Rpdj4nOwoKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibW9kYWwiKS5pbm5lckhUTUw9bWg7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm92ZXJsYXkiKS5jbGFzc0xpc3QuYWRkKCJvcGVuIik7CiAgc2V0VGltZW91dChmdW5jdGlvbigpewogICAgdmFyIGN0eD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgibWNoYXJ0Iik7CiAgICBpZihjdHgmJnIuY2hhcnRfY2xvc2VzKXsKICAgICAgbUNoYXJ0PW5ldyBDaGFydChjdHgse3R5cGU6ImxpbmUiLGRhdGE6e2xhYmVsczpyLmNoYXJ0X2RhdGVzLGRhdGFzZXRzOlsKICAgICAgICB7bGFiZWw6IkZpeWF0IixkYXRhOnIuY2hhcnRfY2xvc2VzLGJvcmRlckNvbG9yOnNzLmFjLGJvcmRlcldpZHRoOjIsZmlsbDp0cnVlLGJhY2tncm91bmRDb2xvcjpzcy5hYysiMjAiLHBvaW50UmFkaXVzOjAsdGVuc2lvbjowLjN9LAogICAgICAgIHIuc21hNTA/e2xhYmVsOiJTTUE1MCIsZGF0YTpBcnJheShyLmNoYXJ0X2Nsb3Nlcy5sZW5ndGgpLmZpbGwoci5zbWE1MCksYm9yZGVyQ29sb3I6IiNmNTllMGIiLGJvcmRlcldpZHRoOjEuNSxib3JkZXJEYXNoOls1LDVdLHBvaW50UmFkaXVzOjAsZmlsbDpmYWxzZX06bnVsbCwKICAgICAgICByLnNtYTIwMD97bGFiZWw6IlNNQTIwMCIsZGF0YTpBcnJheShyLmNoYXJ0X2Nsb3Nlcy5sZW5ndGgpLmZpbGwoci5zbWEyMDApLGJvcmRlckNvbG9yOiIjOGI1Y2Y2Iixib3JkZXJXaWR0aDoxLjUsYm9yZGVyRGFzaDpbNSw1XSxwb2ludFJhZGl1czowLGZpbGw6ZmFsc2V9Om51bGwKICAgICAgXS5maWx0ZXIoQm9vbGVhbil9LG9wdGlvbnM6e3Jlc3BvbnNpdmU6dHJ1ZSxtYWludGFpbkFzcGVjdFJhdGlvOmZhbHNlLAogICAgICAgIHBsdWdpbnM6e2xlZ2VuZDp7bGFiZWxzOntjb2xvcjoiIzZiNzI4MCIsZm9udDp7c2l6ZToxMH19fX0sCiAgICAgICAgc2NhbGVzOnt4OntkaXNwbGF5OnRydWUsdGlja3M6e2NvbG9yOiIjMzc0MTUxIixtYXhUaWNrc0xpbWl0OjUsZm9udDp7c2l6ZTo5fX0sZ3JpZDp7Y29sb3I6InJnYmEoMjU1LDI1NSwyNTUsLjA0KSJ9fSwKICAgICAgICAgIHk6e2Rpc3BsYXk6dHJ1ZSx0aWNrczp7Y29sb3I6IiMzNzQxNTEiLGZvbnQ6e3NpemU6OX19LGdyaWQ6e2NvbG9yOiJyZ2JhKDI1NSwyNTUsMjU1LC4wNCkifX19fX0pOwogICAgfQogIH0sMTAwKTsKfQoKCi8vIOKUgOKUgCBHw5xOTMOcSyBSVVTEsE4g4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSA4pSACnZhciBSVVRJTl9JVEVNUyA9IHsKICBzYWJhaDogewogICAgbGFiZWw6ICLwn4yFIFNhYmFoIOKAlCBQaXlhc2EgQcOnxLFsbWFkYW4gw5ZuY2UiLAogICAgaXRlbXM6IFsKICAgICAge2lkOiJzMSIsIHRleHQ6IkRhc2hib2FyZMSxIGHDpyDigJQgTSBrcml0ZXJpIHllxZ9pbCBtaT8gKFMmUDUwMCArIE5BU0RBUSBTTUEyMDAgw7xzdMO8bmRlKSJ9LAogICAgICB7aWQ6InMyIiwgdGV4dDoiRWFybmluZ3Mgc2VrbWVzaW5pIGtvbnRyb2wgZXQg4oCUIGJ1Z8O8bi9idSBoYWZ0YSByYXBvciB2YXIgbcSxPyJ9LAogICAgICB7aWQ6InMzIiwgdGV4dDoiVklYIDI1IGFsdMSxbmRhIG3EsT8gKFnDvGtzZWtzZSB5ZW5pIHBvemlzeW9uIGHDp21hKSJ9LAogICAgICB7aWQ6InM0IiwgdGV4dDoiw5ZuY2VraSBnw7xuZGVuIGJla2xleWVuIGFsYXJtIG1haWxpIHZhciBtxLE/In0KICAgIF0KICB9LAogIG9nbGVuOiB7CiAgICBsYWJlbDogIvCfk4ogw5bEn2xlZGVuIFNvbnJhIOKAlCBQaXlhc2EgQcOnxLFra2VuIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoibzEiLCB0ZXh0OiJQb3J0ZsO2ecO8bSBzZWttZXNpbmRlIGhpc3NlbGVyaW1lIGJhayDigJQgYmVrbGVubWVkaWsgZMO8xZ/DvMWfIHZhciBtxLE/In0sCiAgICAgIHtpZDoibzIiLCB0ZXh0OiJTdG9wIHNldml5ZXNpbmUgeWFrbGHFn2FuIGhpc3NlIHZhciBtxLE/IChLxLFybcSxesSxIGnFn2FyZXQpIn0sCiAgICAgIHtpZDoibzMiLCB0ZXh0OiJBbCBzaW55YWxpIHNla21lc2luZGUgeWVuaSBmxLFyc2F0IMOnxLFrbcSxxZ8gbcSxPyJ9LAogICAgICB7aWQ6Im80IiwgdGV4dDoiV2F0Y2hsaXN0dGVraSBoaXNzZWxlcmRlIGdpcmnFnyBrYWxpdGVzaSA2MCsgb2xhbiB2YXIgbcSxPyJ9LAogICAgICB7aWQ6Im81IiwgdGV4dDoiSGFiZXJsZXJkZSBwb3J0ZsO2ecO8bcO8IGV0a2lsZXllbiDDtm5lbWxpIGdlbGnFn21lIHZhciBtxLE/In0KICAgIF0KICB9LAogIGFrc2FtOiB7CiAgICBsYWJlbDogIvCfjJkgQWvFn2FtIOKAlCBQaXlhc2EgS2FwYW5kxLFrdGFuIFNvbnJhIiwKICAgIGl0ZW1zOiBbCiAgICAgIHtpZDoiYTEiLCB0ZXh0OiIxSCBzaW55YWxsZXJpbmkga29udHJvbCBldCDigJQgaGFmdGFsxLFrIHRyZW5kIGRlxJ9pxZ9tacWfIG1pPyJ9LAogICAgICB7aWQ6ImEyIiwgdGV4dDoiWWFyxLFuIGnDp2luIHBvdGFuc2l5ZWwgZ2lyacWfIG5va3RhbGFyxLFuxLEgbm90IGFsIn0sCiAgICAgIHtpZDoiYTMiLCB0ZXh0OiJQb3J0ZsO2eWRla2kgaGVyIGhpc3NlbmluIHN0b3Agc2V2aXllc2luaSBnw7Z6ZGVuIGdlw6dpciJ9LAogICAgICB7aWQ6ImE0IiwgdGV4dDoiWWFyxLFuIHJhcG9yIGHDp8Sxa2xheWFjYWsgaGlzc2UgdmFyIG3EsT8gKEVhcm5pbmdzIHNla21lc2kpIn0KICAgIF0KICB9LAogIGhhZnRhbGlrOiB7CiAgICBsYWJlbDogIvCfk4UgSGFmdGFsxLFrIOKAlCBQYXphciBBa8WfYW3EsSIsCiAgICBpdGVtczogWwogICAgICB7aWQ6ImgxIiwgdGV4dDoiU3RvY2sgUm92ZXJkYSBDQU5TTElNIHNjcmVlbmVyxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDIiLCB0ZXh0OiJWQ1AgTWluZXJ2aW5pIHNjcmVlbmVyxLEgw6dhbMSxxZ90xLFyIn0sCiAgICAgIHtpZDoiaDMiLCB0ZXh0OiJRdWxsYW1hZ2dpZSBCcmVha291dCBzY3JlZW5lcsSxIMOnYWzEscWfdMSxciJ9LAogICAgICB7aWQ6Img0IiwgdGV4dDoiRmludml6ZGUgSW5zdGl0dXRpb25hbCBCdXlpbmcgc2NyZWVuZXLEsSDDp2FsxLHFn3TEsXIifSwKICAgICAge2lkOiJoNSIsIHRleHQ6IsOHYWvEscWfYW4gaGlzc2VsZXJpIGJ1bCDigJQgZW4gZ8O8w6dsw7wgYWRheWxhciJ9LAogICAgICB7aWQ6Img2IiwgdGV4dDoiR2l0SHViIEFjdGlvbnNkYW4gUnVuIFdvcmtmbG93IGJhcyDigJQgc2l0ZSBnw7xuY2VsbGVuaXIifSwKICAgICAge2lkOiJoNyIsIHRleHQ6IkdlbGVjZWsgaGFmdGFuxLFuIGVhcm5pbmdzIHRha3ZpbWluaSBrb250cm9sIGV0In0sCiAgICAgIHtpZDoiaDgiLCB0ZXh0OiJQb3J0ZsO2eSBnZW5lbCBkZcSfZXJsZW5kaXJtZXNpIOKAlCBoZWRlZmxlciBoYWxhIGdlw6dlcmxpIG1pPyJ9CiAgICBdCiAgfQp9OwoKZnVuY3Rpb24gZ2V0VG9kYXlLZXkoKXsKICByZXR1cm4gbmV3IERhdGUoKS50b0RhdGVTdHJpbmcoKTsKfQoKZnVuY3Rpb24gbG9hZENoZWNrZWQoKXsKICB0cnl7CiAgICB2YXIgZGF0YSA9IGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdydXRpbl9jaGVja2VkJyk7CiAgICBpZighZGF0YSkgcmV0dXJuIHt9OwogICAgdmFyIHBhcnNlZCA9IEpTT04ucGFyc2UoZGF0YSk7CiAgICAvLyBTYWRlY2UgYnVnw7xuw7xuIHZlcmlsZXJpbmkga3VsbGFuCiAgICBpZihwYXJzZWQuZGF0ZSAhPT0gZ2V0VG9kYXlLZXkoKSkgcmV0dXJuIHt9OwogICAgcmV0dXJuIHBhcnNlZC5pdGVtcyB8fCB7fTsKICB9Y2F0Y2goZSl7cmV0dXJuIHt9O30KfQoKZnVuY3Rpb24gc2F2ZUNoZWNrZWQoY2hlY2tlZCl7CiAgbG9jYWxTdG9yYWdlLnNldEl0ZW0oJ3J1dGluX2NoZWNrZWQnLCBKU09OLnN0cmluZ2lmeSh7CiAgICBkYXRlOiBnZXRUb2RheUtleSgpLAogICAgaXRlbXM6IGNoZWNrZWQKICB9KSk7Cn0KCmZ1bmN0aW9uIHRvZ2dsZUNoZWNrKGlkKXsKICB2YXIgY2hlY2tlZCA9IGxvYWRDaGVja2VkKCk7CiAgaWYoY2hlY2tlZFtpZF0pIGRlbGV0ZSBjaGVja2VkW2lkXTsKICBlbHNlIGNoZWNrZWRbaWRdID0gdHJ1ZTsKICBzYXZlQ2hlY2tlZChjaGVja2VkKTsKICByZW5kZXJSdXRpbigpOwp9CgpmdW5jdGlvbiByZXNldFJ1dGluKCl7CiAgbG9jYWxTdG9yYWdlLnJlbW92ZUl0ZW0oJ3J1dGluX2NoZWNrZWQnKTsKICByZW5kZXJSdXRpbigpOwp9CgoKZnVuY3Rpb24gcmVuZGVySGFmdGFsaWsoKXsKICB2YXIgZ3JpZCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdncmlkJyk7CiAgdmFyIHdkID0gV0VFS0xZX0RBVEEgfHwge307CiAgdmFyIHBvcnQgPSB3ZC5wb3J0Zm9saW8gfHwgW107CiAgdmFyIHdhdGNoID0gd2Qud2F0Y2hsaXN0IHx8IFtdOwogIHZhciBiZXN0ID0gd2QuYmVzdDsKICB2YXIgd29yc3QgPSB3ZC53b3JzdDsKICB2YXIgbWQgPSBNQVJLRVRfREFUQSB8fCB7fTsKICB2YXIgc3AgPSBtZC5TUDUwMCB8fCB7fTsKICB2YXIgbmFzID0gbWQuTkFTREFRIHx8IHt9OwoKICBmdW5jdGlvbiBjaGdDb2xvcih2KXsgcmV0dXJuIHYgPj0gMCA/ICd2YXIoLS1ncmVlbiknIDogJ3ZhcigtLXJlZDIpJzsgfQogIGZ1bmN0aW9uIGNoZ1N0cih2KXsgcmV0dXJuICh2ID49IDAgPyAnKycgOiAnJykgKyB2ICsgJyUnOyB9CgogIGZ1bmN0aW9uIHBlcmZDYXJkKGl0ZW0pewogICAgdmFyIGNjID0gY2hnQ29sb3IoaXRlbS53ZWVrX2NoZyk7CiAgICB2YXIgcGIgPSBpdGVtLnBvcnRmb2xpbyA/ICc8c3BhbiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjEyKTtjb2xvcjp2YXIoLS1ncmVlbik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjI1KTtwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo2MDA7bWFyZ2luLWxlZnQ6NHB4Ij5QPC9zcGFuPicgOiAnJzsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTJweDtkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO21hcmdpbi1ib3R0b206NnB4Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7Z2FwOjZweCI+PHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OkJlYmFzIE5ldWUsc2Fucy1zZXJpZjtmb250LXNpemU6MTZweDtsZXR0ZXItc3BhY2luZzoycHgiPicgKyBpdGVtLnRpY2tlciArICc8L3NwYW4+JyArIHBiICsgJzwvZGl2PicKICAgICAgKyAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+JwogICAgICArICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjE0cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyBjYyArICciPicgKyBjaGdTdHIoaXRlbS53ZWVrX2NoZykgKyAnPC9kaXY+JwogICAgICArICc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+w5ZuY2VraTogJyArIGNoZ1N0cihpdGVtLnByZXZfd2Vla19jaGcpICsgJzwvZGl2PicKICAgICAgKyAnPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciBoID0gJzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CgogIC8vIEhlYWRlcgogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tdGV4dCk7bWFyZ2luLWJvdHRvbTo0cHgiPvCfk4ggSGFmdGFsxLFrIFBlcmZvcm1hbnMgw5Z6ZXRpPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicgKyAod2QuZ2VuZXJhdGVkIHx8ICcnKSArICc8L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIFBpeWFzYSB2cyBQb3J0ZsO2eQogIHZhciBzcENoZyA9IHNwLmNoYW5nZSB8fCAwOwogIHZhciBuYXNDaGcgPSBuYXMuY2hhbmdlIHx8IDA7CiAgdmFyIHBvcnRBdmcgPSBwb3J0Lmxlbmd0aCA/IE1hdGgucm91bmQocG9ydC5yZWR1Y2UoZnVuY3Rpb24oYSxiKXtyZXR1cm4gYStiLndlZWtfY2hnO30sMCkvcG9ydC5sZW5ndGgqMTAwKS8xMDAgOiAwOwogIHZhciBhbHBoYSA9IE1hdGgucm91bmQoKHBvcnRBdmcgLSBzcENoZykqMTAwKS8xMDA7CiAgdmFyIGFscGhhQ29sID0gYWxwaGEgPj0gMCA/ICd2YXIoLS1ncmVlbiknIDogJ3ZhcigtLXJlZDIpJzsKCiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgxNDBweCwxZnIpKTtnYXA6MTBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+UG9ydGbDtnkgT3J0LjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonICsgY2hnQ29sb3IocG9ydEF2ZykgKyAnIj4nICsgY2hnU3RyKHBvcnRBdmcpICsgJzwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+UyZQIDUwMDwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2ZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtjb2xvcjonICsgY2hnQ29sb3Ioc3BDaGcpICsgJyI+JyArIGNoZ1N0cihzcENoZykgKyAnPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHg7dGV4dC1hbGlnbjpjZW50ZXIiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij5OQVNEQVE8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Y29sb3I6JyArIGNoZ0NvbG9yKG5hc0NoZykgKyAnIj4nICsgY2hnU3RyKG5hc0NoZykgKyAnPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicgKyAoYWxwaGE+PTA/J3JnYmEoMTYsMTg1LDEyOSwuMDgpJzoncmdiYSgyMzksNjgsNjgsLjA4KScpICsgJztib3JkZXI6MXB4IHNvbGlkICcgKyAoYWxwaGE+PTA/J3JnYmEoMTYsMTg1LDEyOSwuMjUpJzoncmdiYSgyMzksNjgsNjgsLjI1KScpICsgJztib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKTttYXJnaW4tYm90dG9tOjRweCI+QWxwaGEgKHZzIFMmUCk8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Y29sb3I6JyArIGFscGhhQ29sICsgJyI+JyArIChhbHBoYT49MD8nKyc6JycpICsgYWxwaGEgKyAnJTwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPC9kaXY+JzsKCiAgLy8gRW4gaXlpIC8gZW4ga8O2dMO8CiAgaWYoYmVzdCB8fCB3b3JzdCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogICAgaWYoYmVzdCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLWdyZWVuKTttYXJnaW4tYm90dG9tOjZweCI+8J+PhiBCdSBIYWZ0YW7EsW4gRW4gxLB5aXNpPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyNHB4O2xldHRlci1zcGFjaW5nOjJweCI+JyArIGJlc3QudGlja2VyICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MThweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4rJyArIGJlc3Qud2Vla19jaGcgKyAnJTwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBpZih3b3JzdCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4Ij4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1yZWQyKTttYXJnaW4tYm90dG9tOjZweCI+8J+TiSBCdSBIYWZ0YW7EsW4gRW4gS8O2dMO8c8O8PC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1mYW1pbHk6QmViYXMgTmV1ZSxzYW5zLXNlcmlmO2ZvbnQtc2l6ZToyNHB4O2xldHRlci1zcGFjaW5nOjJweCI+JyArIHdvcnN0LnRpY2tlciArICc8L2Rpdj4nOwogICAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nICsgd29yc3Qud2Vla19jaGcgKyAnJTwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gUG9ydGbDtnkgZGV0YXkKICBpZihwb3J0Lmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5K8IFBvcnRmw7Z5PC9kaXY+JzsKICAgIHBvcnQuZm9yRWFjaChmdW5jdGlvbihpdGVtKXsgaCArPSBwZXJmQ2FyZChpdGVtKTsgfSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gU2lueWFsbGVyIG96ZXRpCiAgdmFyIGJ1eUNvdW50ID0gKFRGX0RBVEFbJzFkJ118fFtdKS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J0dVQ0xVIEFMJ3x8ci5zaW55YWw9PT0nQUwnO30pLmxlbmd0aDsKICB2YXIgc2VsbENvdW50ID0gKFRGX0RBVEFbJzFkJ118fFtdKS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J1NBVCc7fSkubGVuZ3RoOwogIHZhciB3YXRjaENvdW50ID0gKFRGX0RBVEFbJzFkJ118fFtdKS5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J0RJS0tBVCc7fSkubGVuZ3RoOwoKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+8J+TiiBCdSBIYWZ0YWtpIFNpbnlhbGxlcjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2ZsZXgtd3JhcDp3cmFwIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nICsgYnV5Q291bnQgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5BbCBTaW55YWxpPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXllbGxvdykiPicgKyB3YXRjaENvdW50ICsgJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+RGlra2F0PC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czo4cHg7cGFkZGluZzoxMHB4IDE2cHg7dGV4dC1hbGlnbjpjZW50ZXIiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1yZWQyKSI+JyArIHNlbGxDb3VudCArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlNhdCBTaW55YWxpPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8L2Rpdj48L2Rpdj4nOwoKICAvLyBXYXRjaGxpc3QgcGVyZm9ybWFucwogIGlmKHdhdGNoLmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5GBIFdhdGNobGlzdDwvZGl2Pic7CiAgICB3YXRjaC5mb3JFYWNoKGZ1bmN0aW9uKGl0ZW0peyBoICs9IHBlcmZDYXJkKGl0ZW0pOyB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICBoICs9ICc8L2Rpdj4nOwogIGdyaWQuaW5uZXJIVE1MID0gaDsKfQoKCmZ1bmN0aW9uIHJlbmRlclJ1dGluKCl7CiAgdmFyIGdyaWQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogIHZhciBjaGVja2VkID0gbG9hZENoZWNrZWQoKTsKICB2YXIgdG9kYXkgPSBuZXcgRGF0ZSgpOwogIHZhciBpc1dlZWtlbmQgPSB0b2RheS5nZXREYXkoKSA9PT0gMCB8fCB0b2RheS5nZXREYXkoKSA9PT0gNjsKICB2YXIgZGF5TmFtZSA9IFsnUGF6YXInLCdQYXphcnRlc2knLCdTYWzEsScsJ8OHYXLFn2FtYmEnLCdQZXLFn2VtYmUnLCdDdW1hJywnQ3VtYXJ0ZXNpJ11bdG9kYXkuZ2V0RGF5KCldOwogIHZhciBkYXRlU3RyID0gdG9kYXkudG9Mb2NhbGVEYXRlU3RyaW5nKCd0ci1UUicsIHtkYXk6J251bWVyaWMnLG1vbnRoOidsb25nJyx5ZWFyOidudW1lcmljJ30pOwoKICAvLyBQcm9ncmVzcyBoZXNhcGxhCiAgdmFyIHRvdGFsSXRlbXMgPSAwOwogIHZhciBkb25lSXRlbXMgPSAwOwogIHZhciBzZWN0aW9ucyA9IGlzV2Vla2VuZCA/IFsnaGFmdGFsaWsnXSA6IFsnc2FiYWgnLCdvZ2xlbicsJ2Frc2FtJ107CiAgc2VjdGlvbnMuZm9yRWFjaChmdW5jdGlvbihrKXsKICAgIFJVVElOX0lURU1TW2tdLml0ZW1zLmZvckVhY2goZnVuY3Rpb24oaXRlbSl7CiAgICAgIHRvdGFsSXRlbXMrKzsKICAgICAgaWYoY2hlY2tlZFtpdGVtLmlkXSkgZG9uZUl0ZW1zKys7CiAgICB9KTsKICB9KTsKICB2YXIgcGN0ID0gdG90YWxJdGVtcyA+IDAgPyBNYXRoLnJvdW5kKGRvbmVJdGVtcy90b3RhbEl0ZW1zKjEwMCkgOiAwOwogIHZhciBwY3RDb2wgPSBwY3Q9PT0xMDA/J3ZhcigtLWdyZWVuKSc6cGN0Pj01MD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLW11dGVkKSc7CgogIHZhciBoID0gJzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CgogIC8vIEhlYWRlcgogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO2ZsZXgtd3JhcDp3cmFwO2dhcDoxMHB4Ij4nOwogIGggKz0gJzxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXRleHQpIj4nK2RheU5hbWUrJyBSdXRpbmk8L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLW11dGVkKSI+JytkYXRlU3RyKyc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjI4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicrcGN0Q29sKyciPicrcGN0KyclPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrZG9uZUl0ZW1zKycvJyt0b3RhbEl0ZW1zKycgdGFtYW1sYW5kxLE8L2Rpdj48L2Rpdj48L2Rpdj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImhlaWdodDo2cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6M3B4O292ZXJmbG93OmhpZGRlbjttYXJnaW4tdG9wOjEycHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iaGVpZ2h0OjEwMCU7d2lkdGg6JytwY3QrJyU7YmFja2dyb3VuZDonK3BjdENvbCsnO2JvcmRlci1yYWRpdXM6M3B4O3RyYW5zaXRpb246d2lkdGggLjVzIGVhc2UiPjwvZGl2PjwvZGl2Pic7CiAgaWYocGN0PT09MTAwKSBoICs9ICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlcjttYXJnaW4tdG9wOjEwcHg7Zm9udC1zaXplOjE0cHg7Y29sb3I6dmFyKC0tZ3JlZW4pIj7wn46JIFTDvG0gbWFkZGVsZXIgdGFtYW1sYW5kxLEhPC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBTZWN0aW9ucwogIHNlY3Rpb25zLmZvckVhY2goZnVuY3Rpb24oayl7CiAgICB2YXIgc2VjID0gUlVUSU5fSVRFTVNba107CiAgICB2YXIgc2VjRG9uZSA9IHNlYy5pdGVtcy5maWx0ZXIoZnVuY3Rpb24oaSl7cmV0dXJuIGNoZWNrZWRbaS5pZF07fSkubGVuZ3RoOwogICAgdmFyIHNlY1RvdGFsID0gc2VjLml0ZW1zLmxlbmd0aDsKICAgIHZhciBzZWNQY3QgPSBNYXRoLnJvdW5kKHNlY0RvbmUvc2VjVG90YWwqMTAwKTsKICAgIHZhciBzZWNDb2wgPSBzZWNQY3Q9PT0xMDA/J3ZhcigtLWdyZWVuKSc6c2VjUGN0PjA/J3ZhcigtLXllbGxvdyknOid2YXIoLS1tdXRlZCknOwoKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbToxMnB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEzcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOnZhcigtLXRleHQpIj4nK3NlYy5sYWJlbCsnPC9kaXY+JzsKICAgIGggKz0gJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjonK3NlY0NvbCsnO2ZvbnQtd2VpZ2h0OjYwMCI+JytzZWNEb25lKycvJytzZWNUb3RhbCsnPC9zcGFuPjwvZGl2Pic7CgogICAgc2VjLml0ZW1zLmZvckVhY2goZnVuY3Rpb24oaXRlbSl7CiAgICAgIHZhciBkb25lID0gISFjaGVja2VkW2l0ZW0uaWRdOwogICAgICB2YXIgYmdDb2xvciA9IGRvbmUgPyAncmdiYSgxNiwxODUsMTI5LC4wNiknIDogJ3JnYmEoMjU1LDI1NSwyNTUsLjAyKSc7CiAgICAgIHZhciBib3JkZXJDb2xvciA9IGRvbmUgPyAncmdiYSgxNiwxODUsMTI5LC4yKScgOiAncmdiYSgyNTUsMjU1LDI1NSwuMDUpJzsKICAgICAgdmFyIGNoZWNrQm9yZGVyID0gZG9uZSA/ICd2YXIoLS1ncmVlbiknIDogJ3ZhcigtLW11dGVkKSc7CiAgICAgIHZhciBjaGVja0JnID0gZG9uZSA/ICd2YXIoLS1ncmVlbiknIDogJ3RyYW5zcGFyZW50JzsKICAgICAgdmFyIHRleHRDb2xvciA9IGRvbmUgPyAndmFyKC0tbXV0ZWQpJyA6ICd2YXIoLS10ZXh0KSc7CiAgICAgIHZhciB0ZXh0RGVjbyA9IGRvbmUgPyAnbGluZS10aHJvdWdoJyA6ICdub25lJzsKICAgICAgdmFyIGNoZWNrbWFyayA9IGRvbmUgPyAnPHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiI+PHBvbHlsaW5lIHBvaW50cz0iMiw2IDUsOSAxMCwzIiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPjwvc3ZnPicgOiAnJzsKICAgICAgaCArPSAnPGRpdiBvbmNsaWNrPSJ0b2dnbGVDaGVjayhcJycgKyBpdGVtLmlkICsgJ1wnKSIgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpmbGV4LXN0YXJ0O2dhcDoxMnB4O3BhZGRpbmc6MTBweDtib3JkZXItcmFkaXVzOjhweDtjdXJzb3I6cG9pbnRlcjttYXJnaW4tYm90dG9tOjZweDtiYWNrZ3JvdW5kOicgKyBiZ0NvbG9yICsgJztib3JkZXI6MXB4IHNvbGlkICcgKyBib3JkZXJDb2xvciArICciPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZsZXgtc2hyaW5rOjA7d2lkdGg6MjBweDtoZWlnaHQ6MjBweDtib3JkZXItcmFkaXVzOjVweDtib3JkZXI6MnB4IHNvbGlkICcgKyBjaGVja0JvcmRlciArICc7YmFja2dyb3VuZDonICsgY2hlY2tCZyArICc7ZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6Y2VudGVyO21hcmdpbi10b3A6MXB4Ij4nICsgY2hlY2ttYXJrICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxzcGFuIHN0eWxlPSJmb250LXNpemU6MTNweDtjb2xvcjonICsgdGV4dENvbG9yICsgJztsaW5lLWhlaWdodDoxLjU7dGV4dC1kZWNvcmF0aW9uOicgKyB0ZXh0RGVjbyArICciPicgKyBpdGVtLnRleHQgKyAnPC9zcGFuPic7CiAgICAgIGggKz0gJzwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfSk7CgogIC8vIEhhZnRhIGnDp2kgb2xkdcSfdW5kYSBoYWZ0YWzEsWsgYsO2bMO8bcO8IGRlIGfDtnN0ZXIgKGthdGxhbmFiaWxpcikKICBpZighaXNXZWVrZW5kKXsKICAgIHZhciBoU2VjID0gUlVUSU5fSVRFTVNbJ2hhZnRhbGlrJ107CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoNTksMTMwLDI0NiwuMDQpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4xNSk7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxM3B4O2ZvbnQtd2VpZ2h0OjYwMDtjb2xvcjojNjBhNWZhO21hcmdpbi1ib3R0b206NHB4Ij4nK2hTZWMubGFiZWwrJzwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlBhemFyIGFrxZ9hbcSxIHlhcMSxbGFjYWtsYXIg4oCUIMWfdSBhbiBnw7ZzdGVyaW0gbW9kdW5kYTwvZGl2PjwvZGl2Pic7CiAgfQoKICAvLyBSZXNldCBidXRvbnUKICBoICs9ICc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOmNlbnRlcjttYXJnaW4tdG9wOjZweCI+JzsKICBoICs9ICc8YnV0dG9uIG9uY2xpY2s9InJlc2V0UnV0aW4oKSIgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Y29sb3I6dmFyKC0tbXV0ZWQpO3BhZGRpbmc6OHB4IDE2cHg7Ym9yZGVyLXJhZGl1czo4cHg7Zm9udC1zaXplOjEycHg7Y3Vyc29yOnBvaW50ZXIiPvCflIQgTGlzdGV5aSBTxLFmxLFybGE8L2J1dHRvbj4nOwogIGggKz0gJzwvZGl2Pic7CgogIGggKz0gJzwvZGl2Pic7CiAgZ3JpZC5pbm5lckhUTUwgPSBoOwp9CgoKZnVuY3Rpb24gY2xvc2VNKGUpewogIGlmKCFlfHxlLnRhcmdldD09PWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJvdmVybGF5IikpewogICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm92ZXJsYXkiKS5jbGFzc0xpc3QucmVtb3ZlKCJvcGVuIik7CiAgICBpZihtQ2hhcnQpe21DaGFydC5kZXN0cm95KCk7bUNoYXJ0PW51bGw7fQogIH0KfQoKcmVuZGVyU3RhdHMoKTsKcmVuZGVyRGFzaGJvYXJkKCk7CgoKCi8vIOKUgOKUgCBMxLBTVEUgRMOcWkVOTEVNRSDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIDilIAKdmFyIGVkaXRXYXRjaGxpc3QgPSBbXTsKdmFyIGVkaXRQb3J0Zm9saW8gPSBbXTsKCmZ1bmN0aW9uIG9wZW5FZGl0TGlzdCgpewogIGVkaXRXYXRjaGxpc3QgPSBURl9EQVRBWycxZCddLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gIXIuaGF0YTt9KS5tYXAoZnVuY3Rpb24ocil7cmV0dXJuIHIudGlja2VyO30pOwogIGVkaXRQb3J0Zm9saW8gPSBQT1JULnNsaWNlKCk7CiAgcmVuZGVyRWRpdExpc3RzKCk7CiAgLy8gTG9hZCBzYXZlZCB0b2tlbiBmcm9tIGxvY2FsU3RvcmFnZQogIHZhciBzYXZlZCA9IGxvY2FsU3RvcmFnZS5nZXRJdGVtKCdnaF90b2tlbicpOwogIGlmKHNhdmVkKSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ2hUb2tlbklucHV0IikudmFsdWUgPSBzYXZlZDsKICB2YXIgdHM9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInRva2VuU2VjdGlvbiIpOyBpZih0cykgdHMuc3R5bGUuZGlzcGxheT0ibm9uZSI7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImVkaXRQb3B1cCIpLmNsYXNzTGlzdC5hZGQoIm9wZW4iKTsKfQoKCmZ1bmN0aW9uIHRvZ2dsZVRva2VuU2VjdGlvbigpewogIHZhciBzPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0b2tlblNlY3Rpb24iKTsKICBpZihzKSBzLnN0eWxlLmRpc3BsYXk9cy5zdHlsZS5kaXNwbGF5PT09Im5vbmUiPyJibG9jayI6Im5vbmUiOwp9CgpmdW5jdGlvbiBzYXZlVG9rZW4oKXsKICB2YXIgdD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ2hUb2tlbklucHV0IikudmFsdWUudHJpbSgpOwogIGlmKCF0KXthbGVydCgiVG9rZW4gYm9zISIpO3JldHVybjt9CiAgbG9jYWxTdG9yYWdlLnNldEl0ZW0oImdoX3Rva2VuIix0KTsKICB2YXIgdHM9ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInRva2VuU2VjdGlvbiIpOyBpZih0cykgdHMuc3R5bGUuZGlzcGxheT0ibm9uZSI7CiAgc2V0RWRpdFN0YXR1cygi4pyFIFRva2VuIGtheWRlZGlsZGkiLCJncmVlbiIpOwp9CgpmdW5jdGlvbiBjbG9zZUVkaXRQb3B1cChlKXsKICBpZighZXx8ZS50YXJnZXQ9PT1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZWRpdFBvcHVwIikpewogICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImVkaXRQb3B1cCIpLmNsYXNzTGlzdC5yZW1vdmUoIm9wZW4iKTsKICB9Cn0KCmZ1bmN0aW9uIHJlbmRlckVkaXRMaXN0cygpewogIHZhciB3ZSA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ3YXRjaGxpc3RFZGl0b3IiKTsKICB2YXIgcGUgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgicG9ydGZvbGlvRWRpdG9yIik7CiAgaWYoIXdlfHwhcGUpIHJldHVybjsKCiAgd2UuaW5uZXJIVE1MID0gZWRpdFdhdGNobGlzdC5tYXAoZnVuY3Rpb24odCxpKXsKICAgIHJldHVybiAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtqdXN0aWZ5LWNvbnRlbnQ6c3BhY2UtYmV0d2VlbjtwYWRkaW5nOjVweCA4cHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjVweDttYXJnaW4tYm90dG9tOjRweCI+JwogICAgICArJzxzcGFuIHN0eWxlPSJmb250LWZhbWlseTpKZXRCcmFpbnMgTW9ubyxtb25vc3BhY2U7Zm9udC1zaXplOjEycHg7Zm9udC13ZWlnaHQ6NjAwIj4nK3QrJzwvc3Bhbj4nCiAgICAgICsnPGJ1dHRvbiBjbGFzcz0icm0td2F0Y2gtYnRuIiBkYXRhLWlkeD0iJytpKyciIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xNSk7Ym9yZGVyOm5vbmU7Y29sb3I6dmFyKC0tcmVkMik7d2lkdGg6MjBweDtoZWlnaHQ6MjBweDtib3JkZXItcmFkaXVzOjRweDtjdXJzb3I6cG9pbnRlcjtmb250LXNpemU6MTJweCI+4pyVPC9idXR0b24+JwogICAgICArJzwvZGl2Pic7CiAgfSkuam9pbignJyk7CgogIC8vIEFkZCBjbGljayBoYW5kbGVycwogIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsKICAgIGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJy5ybS13YXRjaC1idG4nKS5mb3JFYWNoKGZ1bmN0aW9uKGJ0bil7CiAgICAgIGJ0bi5vbmNsaWNrPWZ1bmN0aW9uKCl7cmVtb3ZlVGlja2VyKCd3YXRjaCcsK3RoaXMuZGF0YXNldC5pZHgpO307CiAgICB9KTsKICAgIGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJy5ybS1wb3J0LWJ0bicpLmZvckVhY2goZnVuY3Rpb24oYnRuKXsKICAgICAgYnRuLm9uY2xpY2s9ZnVuY3Rpb24oKXtyZW1vdmVUaWNrZXIoJ3BvcnQnLCt0aGlzLmRhdGFzZXQuaWR4KTt9OwogICAgfSk7CiAgfSwwKTsKICBwZS5pbm5lckhUTUwgPSBlZGl0UG9ydGZvbGlvLm1hcChmdW5jdGlvbih0LGkpewogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7YWxpZ24taXRlbXM6Y2VudGVyO2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO3BhZGRpbmc6NXB4IDhweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6NXB4O21hcmdpbi1ib3R0b206NHB4Ij4nCiAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtZmFtaWx5OkpldEJyYWlucyBNb25vLG1vbm9zcGFjZTtmb250LXNpemU6MTJweDtmb250LXdlaWdodDo2MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nK3QrJzwvc3Bhbj4nCiAgICAgICsnPGJ1dHRvbiBjbGFzcz0icm0tcG9ydC1idG4iIGRhdGEtaWR4PSInK2krJyIgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjE1KTtib3JkZXI6bm9uZTtjb2xvcjp2YXIoLS1yZWQyKTt3aWR0aDoyMHB4O2hlaWdodDoyMHB4O2JvcmRlci1yYWRpdXM6NHB4O2N1cnNvcjpwb2ludGVyO2ZvbnQtc2l6ZToxMnB4Ij7inJU8L2J1dHRvbj4nCiAgICAgICsnPC9kaXY+JzsKICB9KS5qb2luKCcnKTsKfQoKZnVuY3Rpb24gYWRkVGlja2VyKGxpc3QpewogIHZhciBpbnB1dElkID0gbGlzdD09PSd3YXRjaCc/Im5ld1dhdGNoVGlja2VyIjoibmV3UG9ydFRpY2tlciI7CiAgdmFyIHZhbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKGlucHV0SWQpLnZhbHVlLnRyaW0oKS50b1VwcGVyQ2FzZSgpOwogIGlmKCF2YWwpIHJldHVybjsKICBpZihsaXN0PT09J3dhdGNoJyAmJiAhZWRpdFdhdGNobGlzdC5pbmNsdWRlcyh2YWwpKSBlZGl0V2F0Y2hsaXN0LnB1c2godmFsKTsKICBpZihsaXN0PT09J3BvcnQnICAmJiAhZWRpdFBvcnRmb2xpby5pbmNsdWRlcyh2YWwpKSBlZGl0UG9ydGZvbGlvLnB1c2godmFsKTsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZChpbnB1dElkKS52YWx1ZSA9ICIiOwogIHJlbmRlckVkaXRMaXN0cygpOwp9CgpmdW5jdGlvbiByZW1vdmVUaWNrZXIobGlzdCwgaWR4KXsKICBpZihsaXN0PT09J3dhdGNoJykgZWRpdFdhdGNobGlzdC5zcGxpY2UoaWR4LDEpOwogIGVsc2UgZWRpdFBvcnRmb2xpby5zcGxpY2UoaWR4LDEpOwogIHJlbmRlckVkaXRMaXN0cygpOwp9CgpmdW5jdGlvbiBzYXZlTGlzdFRvR2l0aHViKCl7CiAgdmFyIHRva2VuID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdoVG9rZW5JbnB1dCIpLnZhbHVlLnRyaW0oKTsKICBpZighdG9rZW4peyBzZXRFZGl0U3RhdHVzKCLinYwgVG9rZW4gZ2VyZWtsaSDigJQga3V0dXlhIGdpciIsInJlZCIpOyByZXR1cm47IH0KICBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgnZ2hfdG9rZW4nLCB0b2tlbik7CgogIHZhciBjb25maWcgPSB7IHdhdGNobGlzdDogZWRpdFdhdGNobGlzdCwgcG9ydGZvbGlvOiBlZGl0UG9ydGZvbGlvIH07CiAgdmFyIGNvbnRlbnQgPSBKU09OLnN0cmluZ2lmeShjb25maWcsIG51bGwsIDIpOwogIHZhciBiNjQgPSBidG9hKHVuZXNjYXBlKGVuY29kZVVSSUNvbXBvbmVudChjb250ZW50KSkpOwoKICBzZXRFZGl0U3RhdHVzKCLwn5K+IEtheWRlZGlsaXlvci4uLiIsInllbGxvdyIpOwoKICB2YXIgYXBpVXJsID0gImh0dHBzOi8vYXBpLmdpdGh1Yi5jb20vcmVwb3MvZ2h1cnp6ei9jYW5zbGltL2NvbnRlbnRzL2NvbmZpZy5qc29uIjsKICB2YXIgaGVhZGVycyA9IHsiQXV0aG9yaXphdGlvbiI6InRva2VuICIrdG9rZW4sIkNvbnRlbnQtVHlwZSI6ImFwcGxpY2F0aW9uL2pzb24ifTsKCiAgLy8gRmlyc3QgZ2V0IGN1cnJlbnQgU0hBIGlmIGV4aXN0cwogIGZldGNoKGFwaVVybCwge2hlYWRlcnM6aGVhZGVyc30pCiAgICAudGhlbihmdW5jdGlvbihyKXsgcmV0dXJuIHIub2sgPyByLmpzb24oKSA6IG51bGw7IH0pCiAgICAudGhlbihmdW5jdGlvbihleGlzdGluZyl7CiAgICAgIHZhciBwYXlsb2FkID0gewogICAgICAgIG1lc3NhZ2U6ICJMaXN0ZSBndW5jZWxsZW5kaSAiICsgbmV3IERhdGUoKS50b0xvY2FsZURhdGVTdHJpbmcoInRyLVRSIiksCiAgICAgICAgY29udGVudDogYjY0CiAgICAgIH07CiAgICAgIGlmKGV4aXN0aW5nICYmIGV4aXN0aW5nLnNoYSkgcGF5bG9hZC5zaGEgPSBleGlzdGluZy5zaGE7CgogICAgICByZXR1cm4gZmV0Y2goYXBpVXJsLCB7CiAgICAgICAgbWV0aG9kOiJQVVQiLAogICAgICAgIGhlYWRlcnM6aGVhZGVycywKICAgICAgICBib2R5OkpTT04uc3RyaW5naWZ5KHBheWxvYWQpCiAgICAgIH0pOwogICAgfSkKICAgIC50aGVuKGZ1bmN0aW9uKHIpewogICAgICBpZihyLm9rIHx8IHIuc3RhdHVzPT09MjAxKXsKICAgICAgICBzZXRFZGl0U3RhdHVzKCLinIUgS2F5ZGVkaWxkaSEgQmlyIHNvbnJha2kgQ29sYWIgw6dhbMSxxZ90xLFybWFzxLFuZGEgYWt0aWYgb2x1ci4iLCJncmVlbiIpOwogICAgICAgIHNldFRpbWVvdXQoZnVuY3Rpb24oKXtjbG9zZUVkaXRQb3B1cCgpO30sMjAwMCk7CiAgICAgIH0gZWxzZSB7CiAgICAgICAgc2V0RWRpdFN0YXR1cygi4p2MIEhhdGE6ICIrci5zdGF0dXMrIiDigJQgVG9rZW7EsSBrb250cm9sIGV0IiwicmVkIik7CiAgICAgIH0KICAgIH0pCiAgICAuY2F0Y2goZnVuY3Rpb24oZSl7IHNldEVkaXRTdGF0dXMoIuKdjCBIYXRhOiAiK2UubWVzc2FnZSwicmVkIik7IH0pOwp9CgpmdW5jdGlvbiBzZXRFZGl0U3RhdHVzKG1zZywgY29sb3IpewogIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJlZGl0U3RhdHVzIik7CiAgaWYoZWwpewogICAgZWwudGV4dENvbnRlbnQgPSBtc2c7CiAgICBlbC5zdHlsZS5jb2xvciA9IGNvbG9yPT09ImdyZWVuIj8idmFyKC0tZ3JlZW4pIjpjb2xvcj09PSJyZWQiPyJ2YXIoLS1yZWQyKSI6InZhcigtLXllbGxvdykiOwogIH0KfQoKCmZ1bmN0aW9uIHJlbmRlckhhZnRhbGlrKCl7CiAgdmFyIGdyaWQgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnZ3JpZCcpOwogIHZhciB3ZCA9IFdFRUtMWV9EQVRBIHx8IHt9OwogIHZhciBwb3J0ID0gd2QucG9ydGZvbGlvIHx8IFtdOwogIHZhciB3YXRjaCA9IHdkLndhdGNobGlzdCB8fCBbXTsKICB2YXIgYmVzdCA9IHdkLmJlc3Q7CiAgdmFyIHdvcnN0ID0gd2Qud29yc3Q7CiAgdmFyIG1kID0gTUFSS0VUX0RBVEEgfHwge307CiAgdmFyIHNwID0gbWQuU1A1MDAgfHwge307CiAgdmFyIG5hcyA9IG1kLk5BU0RBUSB8fCB7fTsKICB2YXIgZGF0YTFkID0gVEZfREFUQVsnMWQnXSB8fCBbXTsKICB2YXIgZGF0YTF3ID0gVEZfREFUQVsnMXdrJ10gfHwgW107CgogIGZ1bmN0aW9uIGNjKHYpeyByZXR1cm4gdj49MD8ndmFyKC0tZ3JlZW4yKSc6J3ZhcigtLXJlZDIpJzsgfQogIGZ1bmN0aW9uIGNzKHYpeyByZXR1cm4gKHY+PTA/JysnOicnKSt2KyclJzsgfQoKICBmdW5jdGlvbiBwZXJmUm93KGl0ZW0pewogICAgdmFyIGNvbCA9IGNjKGl0ZW0ud2Vla19jaGcpOwogICAgdmFyIHBiID0gaXRlbS5wb3J0Zm9saW8gPyAnPHNwYW4gc3R5bGU9ImNvbG9yOnZhcigtLWdyZWVuKTtmb250LXNpemU6OXB4O2ZvbnQtd2VpZ2h0OjcwMDttYXJnaW4tbGVmdDo0cHgiPlA8L3NwYW4+JyA6ICcnOwogICAgcmV0dXJuICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47YWxpZ24taXRlbXM6Y2VudGVyO3BhZGRpbmc6OHB4IDEycHg7YmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlci1yYWRpdXM6OHB4O21hcmdpbi1ib3R0b206NXB4Ij4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtmb250LXNpemU6MTRweDtsZXR0ZXItc3BhY2luZzoxcHgiPicgKyBpdGVtLnRpY2tlciArIHBiICsgJzwvZGl2PicKICAgICAgKyAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+JwogICAgICArICc8ZGl2IHN0eWxlPSJmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGNvbCArICciPicgKyBjcyhpdGVtLndlZWtfY2hnKSArICc8L2Rpdj4nCiAgICAgICsgJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5PbmNla2k6ICcgKyBjcyhpdGVtLnByZXZfd2Vla19jaGcpICsgJzwvZGl2PicKICAgICAgKyAnPC9kaXY+PC9kaXY+JzsKICB9CgogIHZhciBwb3J0QXZnID0gcG9ydC5sZW5ndGggPyBNYXRoLnJvdW5kKHBvcnQucmVkdWNlKGZ1bmN0aW9uKGEsYil7cmV0dXJuIGErYi53ZWVrX2NoZzt9LDApL3BvcnQubGVuZ3RoKjEwMCkvMTAwIDogMDsKICB2YXIgc3BDaGcgPSBzcC5jaGFuZ2UgfHwgMDsKICB2YXIgbmFzQ2hnID0gbmFzLmNoYW5nZSB8fCAwOwogIHZhciBhbHBoYSA9IE1hdGgucm91bmQoKHBvcnRBdmctc3BDaGcpKjEwMCkvMTAwOwogIHZhciBhbHBoYUNvbCA9IGFscGhhPj0wPyd2YXIoLS1ncmVlbiknOid2YXIoLS1yZWQyKSc7CgogIHZhciBoID0gJzxkaXYgc3R5bGU9ImdyaWQtY29sdW1uOjEvLTEiPic7CgogIC8vIEhlYWRlcgogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweCAyMHB4O21hcmdpbi1ib3R0b206MTRweCI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWJvdHRvbTo0cHgiPvCfk4ggSGFmdGFsxLFrIFBlcmZvcm1hbnMgw5Z6ZXRpPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicgKyAod2QuZ2VuZXJhdGVkfHwnJykgKyAnPC9kaXY+JzsKICBoICs9ICc8L2Rpdj4nOwoKICAvLyBQaXlhc2EgdnMgUG9ydGZvbHlvCiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczpyZXBlYXQoYXV0by1maWxsLG1pbm1heCgxMzBweCwxZnIpKTtnYXA6MTBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgWwogICAge2xhYmVsOidQb3J0ZsO2eSBPcnQuJywgdmFsOnBvcnRBdmd9LAogICAge2xhYmVsOidTJlAgNTAwJywgdmFsOnNwQ2hnfSwKICAgIHtsYWJlbDonTkFTREFRJywgdmFsOm5hc0NoZ30sCiAgXS5mb3JFYWNoKGZ1bmN0aW9uKHgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgdmFyKC0tYm9yZGVyKTtib3JkZXItcmFkaXVzOjEwcHg7cGFkZGluZzoxNHB4O3RleHQtYWxpZ246Y2VudGVyIj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206NHB4Ij4nICsgeC5sYWJlbCArICc8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOicgKyBjYyh4LnZhbCkgKyAnIj4nICsgY3MoeC52YWwpICsgJzwvZGl2PjwvZGl2Pic7CiAgfSk7CiAgdmFyIGFCZyA9IGFscGhhPj0wPydyZ2JhKDE2LDE4NSwxMjksLjA4KSc6J3JnYmEoMjM5LDY4LDY4LC4wOCknOwogIHZhciBhQmQgPSBhbHBoYT49MD8ncmdiYSgxNiwxODUsMTI5LC4yNSknOidyZ2JhKDIzOSw2OCw2OCwuMjUpJzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOicgKyBhQmcgKyAnO2JvcmRlcjoxcHggc29saWQgJyArIGFCZCArICc7Ym9yZGVyLXJhZGl1czoxMHB4O3BhZGRpbmc6MTRweDt0ZXh0LWFsaWduOmNlbnRlciI+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbTo0cHgiPkFscGhhICh2cyBTJlApPC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIGFscGhhQ29sICsgJyI+JyArIGNzKGFscGhhKSArICc8L2Rpdj48L2Rpdj4nOwogIGggKz0gJzwvZGl2Pic7CgogIC8vIEVuIGl5aSAvIGVuIGtvdHUKICBpZihiZXN0fHx3b3JzdCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjFmciAxZnI7Z2FwOjEwcHg7bWFyZ2luLWJvdHRvbToxNHB4Ij4nOwogICAgaWYoYmVzdCl7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLWdyZWVuKTttYXJnaW4tYm90dG9tOjZweCI+8J+PhiBFbiDEsHlpPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2xldHRlci1zcGFjaW5nOjJweCI+JyArIGJlc3QudGlja2VyICsgJzwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxOHB4O2ZvbnQtd2VpZ2h0OjcwMDtjb2xvcjp2YXIoLS1ncmVlbikiPisnICsgYmVzdC53ZWVrX2NoZyArICclPC9kaXY+PC9kaXY+JzsKICAgIH0KICAgIGlmKHdvcnN0KXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjE0cHgiPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLXJlZDIpO21hcmdpbi1ib3R0b206NnB4Ij7wn5OJIEVuIEvDtnTDvDwvZGl2Pic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyMnB4O2ZvbnQtd2VpZ2h0OjcwMDtsZXR0ZXItc3BhY2luZzoycHgiPicgKyB3b3JzdC50aWNrZXIgKyAnPC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjE4cHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nICsgd29yc3Qud2Vla19jaGcgKyAnJTwvZGl2PjwvZGl2Pic7CiAgICB9CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gU2lueWFsbGVyCiAgdmFyIGJ1eUMgID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5zaW55YWw9PT0nR1VDTFUgQUwnfHxyLnNpbnlhbD09PSdBTCc7fSkubGVuZ3RoOwogIHZhciB3YXJuQyA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J0RJS0tBVCc7fSkubGVuZ3RoOwogIHZhciBzZWxsQyA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7cmV0dXJuIHIuc2lueWFsPT09J1NBVCc7fSkubGVuZ3RoOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5OKIFNpbnlhbGxlcjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2ZsZXgtd3JhcDp3cmFwIj4nOwogIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nICsgYnV5QyArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkFsPC9kaXY+PC9kaXY+JzsKICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIwcHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXllbGxvdykiPicgKyB3YXJuQyArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkRpa2thdDwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDIzOSw2OCw2OCwuMDgpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyMzksNjgsNjgsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjBweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tcmVkMikiPicgKyBzZWxsQyArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlNhdDwvZGl2PjwvZGl2Pic7CiAgaCArPSAnPC9kaXY+PC9kaXY+JzsKCiAgLy8gMUcrMUggbW9tZW50dW0KICB2YXIgYm90aEJ1eSA9IGRhdGExZC5maWx0ZXIoZnVuY3Rpb24ocil7CiAgICBpZihyLmhhdGEpIHJldHVybiBmYWxzZTsKICAgIHZhciB3ID0gZGF0YTF3LmZpbmQoZnVuY3Rpb24oeCl7cmV0dXJuIHgudGlja2VyPT09ci50aWNrZXI7fSk7CiAgICByZXR1cm4gKHIuc2lueWFsPT09J0dVQ0xVIEFMJ3x8ci5zaW55YWw9PT0nQUwnKSAmJiB3ICYmICh3LnNpbnlhbD09PSdHVUNMVSBBTCd8fHcuc2lueWFsPT09J0FMJyk7CiAgfSk7CiAgaWYoYm90aEJ1eS5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDE2LDE4NSwxMjksLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMTYsMTg1LDEyOSwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1ncmVlbik7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPuKaoSAxRyArIDFIIEFsIFNpbnlhbGk8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2ZsZXgtd3JhcDp3cmFwO2dhcDo4cHgiIGlkPSJib3RoQnV5Q29udGFpbmVyIj48L2Rpdj48L2Rpdj4nOwogIH0KCiAgLy8gVG9wIDMgZW50cnkgc2NvcmUKICB2YXIgdG9wRW50cnkgPSBkYXRhMWQuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5oYXRhO30pLnNvcnQoZnVuY3Rpb24oYSxiKXtyZXR1cm4gYi5lbnRyeV9zY29yZS1hLmVudHJ5X3Njb3JlO30pLnNsaWNlKDAsMyk7CiAgaWYodG9wRW50cnkubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfjq8gRW4gxLB5aSBHaXJpxZ8gS2FsaXRlc2k8L2Rpdj4nOwogICAgdmFyIG1lZGFscyA9IFsn8J+lhycsJ/CfpYgnLCfwn6WJJ107CiAgICB0b3BFbnRyeS5mb3JFYWNoKGZ1bmN0aW9uKHIsaSl7CiAgICAgIHZhciBlc2NvbCA9IHIuZW50cnlfc2NvcmU+PTc1Pyd2YXIoLS1ncmVlbiknOnIuZW50cnlfc2NvcmU+PTYwPyd2YXIoLS1ncmVlbjIpJzondmFyKC0teWVsbG93KSc7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImRpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW47cGFkZGluZzo4cHggMTJweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czo4cHg7bWFyZ2luLWJvdHRvbTo1cHgiIGlkPSJ0ZS0nICsgci50aWNrZXIgKyAnIj4nOwogICAgICBoICs9ICc8c3Bhbj4nICsgbWVkYWxzW2ldICsgJyA8c3Ryb25nPicgKyByLnRpY2tlciArICc8L3N0cm9uZz4gPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLW11dGVkKSI+JyArIHIuc2lueWFsICsgJzwvc3Bhbj48L3NwYW4+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonICsgZXNjb2wgKyAnIj4nICsgci5lbnRyeV9zY29yZSArICcvMTAwPC9zcGFuPjwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBTdG9wIHlha2luCiAgdmFyIG5lYXJTdG9wID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXsKICAgIGlmKHIuaGF0YXx8IVBPUlQuaW5jbHVkZXMoci50aWNrZXIpfHwhci5zdG9wKSByZXR1cm4gZmFsc2U7CiAgICByZXR1cm4gKHIuZml5YXQtci5zdG9wKS9yLmZpeWF0KjEwMCA8IDg7CiAgfSkuc29ydChmdW5jdGlvbihhLGIpe3JldHVybiAoYS5maXlhdC1hLnN0b3ApL2EuZml5YXQtKGIuZml5YXQtYi5zdG9wKS9iLmZpeWF0O30pOwogIGlmKG5lYXJTdG9wLmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4wNik7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDIzOSw2OCw2OCwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1yZWQyKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206MTBweCI+4pqg77iPIFN0b3AgU2V2aXllc2luZSBZYWvEsW48L2Rpdj4nOwogICAgbmVhclN0b3AuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgICAgdmFyIGRpc3QgPSBNYXRoLnJvdW5kKChyLmZpeWF0LXIuc3RvcCkvci5maXlhdCoxMDAwKS8xMDsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCIgaWQ9Im5zLScgKyByLnRpY2tlciArICciPic7CiAgICAgIGggKz0gJzxzdHJvbmc+JyArIHIudGlja2VyICsgJzwvc3Ryb25nPic7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMnB4O2NvbG9yOnZhcigtLXJlZDIpO2ZvbnQtd2VpZ2h0OjYwMCI+U3RvcCAkJyArIHIuc3RvcCArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlV6YWtsxLFrOiAlJyArIGRpc3QgKyAnPC9kaXY+PC9kaXY+PC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIEhlZGVmZSB5YWtpbgogIHZhciBuZWFyVGFyZ2V0ID0gZGF0YTFkLmZpbHRlcihmdW5jdGlvbihyKXsKICAgIGlmKHIuaGF0YXx8IVBPUlQuaW5jbHVkZXMoci50aWNrZXIpfHwhci5oZWRlZikgcmV0dXJuIGZhbHNlOwogICAgcmV0dXJuIChyLmhlZGVmLXIuZml5YXQpL3IuZml5YXQqMTAwIDwgMTU7CiAgfSkuc29ydChmdW5jdGlvbihhLGIpe3JldHVybiAoYS5oZWRlZi1hLmZpeWF0KS9hLmZpeWF0LShiLmhlZGVmLWIuZml5YXQpL2IuZml5YXQ7fSk7CiAgaWYobmVhclRhcmdldC5sZW5ndGgpewogICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDpyZ2JhKDU5LDEzMCwyNDYsLjA2KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoNTksMTMwLDI0NiwuMik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjojNjBhNWZhO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn46vIEhlZGVmZSBZYWvEsW48L2Rpdj4nOwogICAgbmVhclRhcmdldC5mb3JFYWNoKGZ1bmN0aW9uKHIpewogICAgICB2YXIgZGlzdCA9IE1hdGgucm91bmQoKHIuaGVkZWYtci5maXlhdCkvci5maXlhdCoxMDAwKS8xMDsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCI+JzsKICAgICAgaCArPSAnPHN0cm9uZz4nICsgci50aWNrZXIgKyAnPC9zdHJvbmc+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0idGV4dC1hbGlnbjpyaWdodCI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEycHg7Y29sb3I6IzYwYTVmYTtmb250LXdlaWdodDo2MDAiPkhlZGVmICQnICsgci5oZWRlZiArICc8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPkthbGRpOiAlJyArIGRpc3QgKyAnPC9kaXY+PC9kaXY+PC9kaXY+JzsKICAgIH0pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIC8vIEVhcm5pbmdzCiAgdmFyIHVyZ2VudEUgPSBFQVJOSU5HU19EQVRBLmZpbHRlcihmdW5jdGlvbihlKXtyZXR1cm4gZS5kYXlzX3RvX2Vhcm5pbmdzIT1udWxsJiZlLmRheXNfdG9fZWFybmluZ3M8PTE0O30pLnNvcnQoZnVuY3Rpb24oYSxiKXtyZXR1cm4gYS5kYXlzX3RvX2Vhcm5pbmdzLWIuZGF5c190b19lYXJuaW5nczt9KTsKICBpZih1cmdlbnRFLmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjQ1LDE1OCwxMSwuMDYpO2JvcmRlcjoxcHggc29saWQgcmdiYSgyNDUsMTU4LDExLC4yKTtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxNnB4O21hcmdpbi1ib3R0b206MTBweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLXllbGxvdyk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfk4UgWWFrbGHFn2FuIFJhcG9ybGFyPC9kaXY+JzsKICAgIHVyZ2VudEUuZm9yRWFjaChmdW5jdGlvbihlKXsKICAgICAgdmFyIGljID0gZS5hbGVydD09PSdyZWQnPyfwn5S0Jzon8J+foSc7CiAgICAgIHZhciBpblBvcnQgPSBQT1JULmluY2x1ZGVzKGUudGlja2VyKTsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlcjtwYWRkaW5nOjhweCAxMnB4O2JhY2tncm91bmQ6dmFyKC0tYmczKTtib3JkZXItcmFkaXVzOjhweDttYXJnaW4tYm90dG9tOjVweCI+JzsKICAgICAgaCArPSAnPHNwYW4+JyArIGljICsgJyA8c3Ryb25nPicgKyBlLnRpY2tlciArICc8L3N0cm9uZz4nICsgKGluUG9ydD8nIDxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjEwcHgiPlA8L3NwYW4+JzonJykgKyAnPC9zcGFuPic7CiAgICAgIGggKz0gJzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1tdXRlZCk7Zm9udC1zaXplOjExcHgiPicgKyBlLm5leHRfZGF0ZSArICcgKCcgKyBlLmRheXNfdG9fZWFybmluZ3MgKyAnIGfDvG4pPC9zcGFuPjwvZGl2Pic7CiAgICB9KTsKICAgIGggKz0gJzwvZGl2Pic7CiAgfQoKICAvLyBWSVgKICB2YXIgdml4ID0gbWQuVklYIHx8IHt9OwogIGlmKHZpeC5wcmljZSl7CiAgICB2YXIgdkNvbCA9IHZpeC5wcmljZT4zMD8ndmFyKC0tcmVkMiknOnZpeC5wcmljZT4yMD8ndmFyKC0teWVsbG93KSc6J3ZhcigtLWdyZWVuKSc7CiAgICB2YXIgdkxibCA9IHZpeC5wcmljZT4zMD8nWcO8a3NlayBLb3JrdSDigJQgWWVuaSBwb3ppc3lvbiBhw6dtYSc6dml4LnByaWNlPjIwPydPcnRhIFZvbGF0aWxpdGUg4oCUIERpa2thdGxpIG9sJzonRMO8xZ/DvGsgVm9sYXRpbGl0ZSDigJQgTm9ybWFsIGtvxZ91bGxhcic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE0cHggMTZweDttYXJnaW4tYm90dG9tOjEwcHg7ZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlciI+JzsKICAgIGggKz0gJzxkaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO21hcmdpbi1ib3R0b206MnB4Ij5WSVg8L2Rpdj48ZGl2IHN0eWxlPSJmb250LXNpemU6MTJweDtjb2xvcjonICsgdkNvbCArICciPicgKyB2TGJsICsgJzwvZGl2PjwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjhweDtmb250LXdlaWdodDo3MDA7Y29sb3I6JyArIHZDb2wgKyAnIj4nICsgdml4LnByaWNlICsgJzwvZGl2PjwvZGl2Pic7CiAgfQoKICAvLyBQb3J0Zm9seW8gZGV0YXkKICBpZihwb3J0Lmxlbmd0aCl7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHg7bWFyZ2luLWJvdHRvbToxMHB4Ij4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjExcHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbToxMHB4Ij7wn5K8IFBvcnRmw7Z5PC9kaXY+JzsKICAgIHBvcnQuZm9yRWFjaChmdW5jdGlvbihpdGVtKXtoICs9IHBlcmZSb3coaXRlbSk7fSk7CiAgICBoICs9ICc8L2Rpdj4nOwogIH0KCiAgLy8gV2F0Y2hsaXN0CiAgaWYod2F0Y2gubGVuZ3RoKXsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6dmFyKC0tYmcyKTtib3JkZXI6MXB4IHNvbGlkIHZhcigtLWJvcmRlcik7Ym9yZGVyLXJhZGl1czoxMnB4O3BhZGRpbmc6MTZweDttYXJnaW4tYm90dG9tOjEwcHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZTttYXJnaW4tYm90dG9tOjEwcHgiPvCfkYEgV2F0Y2hsaXN0PC9kaXY+JzsKICAgIHdhdGNoLmZvckVhY2goZnVuY3Rpb24oaXRlbSl7aCArPSBwZXJmUm93KGl0ZW0pO30pOwogICAgaCArPSAnPC9kaXY+JzsKICB9CgogIGggKz0gJzwvZGl2Pic7CiAgZ3JpZC5pbm5lckhUTUwgPSBoOwoKICAvLyBBZGQgb25jbGljayB2aWEgSlMgKGF2b2lkcyBxdW90ZSBuZXN0aW5nIGlzc3VlcykKICBib3RoQnV5LmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgY250ID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2JvdGhCdXlDb250YWluZXInKTsKICAgIGlmKCFjbnQpIHJldHVybjsKICAgIHZhciBkID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2Jyk7CiAgICBkLnN0eWxlLmNzc1RleHQgPSAnYmFja2dyb3VuZDp2YXIoLS1iZzMpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4zKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjhweCAxNHB4O2N1cnNvcjpwb2ludGVyJzsKICAgIGQuaW5uZXJIVE1MID0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNnB4O2ZvbnQtd2VpZ2h0OjcwMDtsZXR0ZXItc3BhY2luZzoycHg7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nICsgci50aWNrZXIgKyAnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5HaXJpczogJyArIHIuZW50cnlfc2NvcmUgKyAnLzEwMDwvZGl2Pic7CiAgICBkLm9uY2xpY2sgPSAoZnVuY3Rpb24odCl7cmV0dXJuIGZ1bmN0aW9uKCl7b3Blbk0odCk7fTt9KShyLnRpY2tlcik7CiAgICBjbnQuYXBwZW5kQ2hpbGQoZCk7CiAgfSk7CiAgdG9wRW50cnkuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCd0ZS0nICsgci50aWNrZXIpOwogICAgaWYoZWwpIGVsLm9uY2xpY2sgPSAoZnVuY3Rpb24odCl7cmV0dXJuIGZ1bmN0aW9uKCl7b3Blbk0odCk7fTt9KShyLnRpY2tlciksIGVsLnN0eWxlLmN1cnNvcj0ncG9pbnRlcic7CiAgfSk7CiAgbmVhclN0b3AuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgIHZhciBlbCA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCducy0nICsgci50aWNrZXIpOwogICAgaWYoZWwpIGVsLm9uY2xpY2sgPSAoZnVuY3Rpb24odCl7cmV0dXJuIGZ1bmN0aW9uKCl7b3Blbk0odCk7fTt9KShyLnRpY2tlciksIGVsLnN0eWxlLmN1cnNvcj0ncG9pbnRlcic7CiAgfSk7Cn0KCgpmdW5jdGlvbiByZW5kZXJTY3JlZW5lcigpewogIHZhciBncmlkID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ2dyaWQnKTsKICB2YXIgZGF0YSA9IFNDUkVFTkVSX0RBVEEgfHwgW107CiAgdmFyIGNyaXRlcmlhID0gWwogICAge2lkOidlcHNfcW9xJywgICAgbGFiZWw6J0VQUyBRb1EgQsO8ecO8bWUnLCAgICAgbGltaXQ6Jz49MjAlJywgICAgdzozLCBpbXA6J2NyaXRpY2FsJ30sCiAgICB7aWQ6J3NtYTIwMCcsICAgICBsYWJlbDonU01BMjAwIMOcemVyaW5kZScsICAgICBsaW1pdDonUD5TTUEyMDAnLCB3OjMsIGltcDonY3JpdGljYWwnfSwKICAgIHtpZDonbWFya2V0JywgICAgIGxhYmVsOidNIEtyaXRlcmknLCAgICAgICAgICAgbGltaXQ6J0fDvMOnbMO8JywgICAgdzozLCBpbXA6J2NyaXRpY2FsJ30sCiAgICB7aWQ6J2Vwc19hY2NlbCcsICBsYWJlbDonRVBTIEjEsXpsYW5tYXPEsScsICAgICAgbGltaXQ6J0jEsXpsYW7EsXlvcicsdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOidyc19yYXRpbmcnLCAgbGFiZWw6J1JTIFJhdGluZycsICAgICAgICAgICBsaW1pdDonPj03MCcsICAgICB3OjIsIGltcDonaW1wb3J0YW50J30sCiAgICB7aWQ6J3Jldl9ncm93dGgnLCBsYWJlbDonR2VsaXIgQsO8ecO8bWVzaScsICAgICAgbGltaXQ6Jz49MTUlJywgICAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOidyb2UnLCAgICAgICAgbGFiZWw6J1JPRScsICAgICAgICAgICAgICAgICBsaW1pdDonPj0xNSUnLCAgICB3OjIsIGltcDonaW1wb3J0YW50J30sCiAgICB7aWQ6J2dyb3NzX21nJywgICBsYWJlbDonQnLDvHQgTWFyamluJywgICAgICAgICBsaW1pdDonPj00MCUnLCAgICB3OjIsIGltcDonaW1wb3J0YW50J30sCiAgICB7aWQ6J3NtYTUwJywgICAgICBsYWJlbDonU01BNTAgw5x6ZXJpbmRlJywgICAgICBsaW1pdDonUD5TTUE1MCcsICB3OjIsIGltcDonaW1wb3J0YW50J30sCiAgICB7aWQ6JzUydycsICAgICAgICBsYWJlbDonNTJIIFlha8SxbmzEsWsnLCAgICAgICAgbGltaXQ6Jz49NzUlJywgICAgdzoyLCBpbXA6J2ltcG9ydGFudCd9LAogICAge2lkOiduZXRfbWcnLCAgICAgbGFiZWw6J05ldCBNYXJqaW4nLCAgICAgICAgICBsaW1pdDonPj0xMCUnLCAgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidkZScsICAgICAgICAgbGFiZWw6J0JvcsOnL8OWemtheW5haycsICAgICAgIGxpbWl0Oic8PTEuMCcsICAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J2NyJywgICAgICAgICBsYWJlbDonQ3VycmVudCBSYXRpbycsICAgICAgIGxpbWl0Oic+PTEuNScsICAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J3BlJywgICAgICAgICBsYWJlbDonUC9FJywgICAgICAgICAgICAgICAgIGxpbWl0Oic8PTYwJywgICAgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgICB7aWQ6J21rdGNhcCcsICAgICBsYWJlbDonUGl5YXNhIERlxJ9lcmknLCAgICAgICBsaW1pdDonPj0xQicsICAgICB3OjEsIGltcDonc3VwcG9ydCd9LAogICAge2lkOidyZWxfdm9sJywgICAgbGFiZWw6J0fDtnJlY2VsaSBIYWNpbScsICAgICAgbGltaXQ6Jz49MC44eCcsICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDonYXZnX3ZvbCcsICAgIGxhYmVsOidPcnQuIEhhY2ltJywgICAgICAgICAgbGltaXQ6Jz49NTAwSycsICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDonaW5zdF9vd24nLCAgIGxhYmVsOidLdXJ1bXNhbCBTYWhpcGxpaycsICAgbGltaXQ6Jz49NDAlJywgICAgdzoxLCBpbXA6J3N1cHBvcnQnfSwKICAgIHtpZDonaW5zdF90cmVuZCcsIGxhYmVsOidLdXJ1bXNhbCBUcmVuZCcsICAgICAgbGltaXQ6J0FydMSxeW9yJywgIHc6MSwgaW1wOidzdXBwb3J0J30sCiAgXTsKICB2YXIgTUFYX1cgPSAzNTsKCiAgaWYoIWRhdGEubGVuZ3RoKXsKICAgIGdyaWQuaW5uZXJIVE1MPSc8ZGl2IHN0eWxlPSJncmlkLWNvbHVtbjoxLy0xO3RleHQtYWxpZ246Y2VudGVyO3BhZGRpbmc6NDBweDtjb2xvcjp2YXIoLS1tdXRlZCkiPlNjcmVlbmVyIHZlcmlzaSB5b2sg4oCUIEFjdGlvbnMgUnVuIFdvcmtmbG93PC9kaXY+JzsKICAgIHJldHVybjsKICB9CgogIHZhciBwYXNzZWQgPSBkYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5wYXNzZWQ7fSk7CiAgdmFyIGZhaWxlZCA9IGRhdGEuZmlsdGVyKGZ1bmN0aW9uKHIpe3JldHVybiAhci5wYXNzZWQ7fSk7CiAgdmFyIFtleHBhbmRlZFRpY2tlciwgc2V0RXhwYW5kZWRdID0gW251bGwsIG51bGxdOwoKICBmdW5jdGlvbiBpbXBDb2xvcihpbXApewogICAgcmV0dXJuIGltcD09PSdjcml0aWNhbCc/J3ZhcigtLXJlZDIpJzppbXA9PT0naW1wb3J0YW50Jz8ndmFyKC0teWVsbG93KSc6J3ZhcigtLW11dGVkKSc7CiAgfQogIGZ1bmN0aW9uIGltcExhYmVsKGltcCl7CiAgICByZXR1cm4gaW1wPT09J2NyaXRpY2FsJz8n8J+UtCBaT1JVTkxVJzppbXA9PT0naW1wb3J0YW50Jz8n8J+foSDDlk5FTUzEsCc6J/CflLUgREVTVEVLJzsKICB9CgogIGZ1bmN0aW9uIGNyaXRlcmlhRGV0YWlsKHIpewogICAgdmFyIGggPSAnPGRpdiBzdHlsZT0icGFkZGluZzoxMnB4IDE0cHg7Ym9yZGVyLXRvcDoxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpO2JhY2tncm91bmQ6dmFyKC0tYmczKSI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2xldHRlci1zcGFjaW5nOjJweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHgiPktSxLBURVIgREVUQVlJIOKAlCBBxJ/EsXJsxLFrbMSxIFNrb3I6ICcrci53ZWlnaHRlZF9zY29yZSsnLycrci5tYXhfd2VpZ2h0ZWQrJyAoJScrci5wY3QrJyk8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpncmlkO2dyaWQtdGVtcGxhdGUtY29sdW1uczoxZnIgMWZyO2dhcDo0cHgiPic7CiAgICBjcml0ZXJpYS5mb3JFYWNoKGZ1bmN0aW9uKGMpewogICAgICB2YXIgY3IgPSByLmNyaXRlcmlhICYmIHIuY3JpdGVyaWFbYy5pZF07CiAgICAgIGlmKCFjcikgcmV0dXJuOwogICAgICB2YXIgbm9EYXRhID0gY3IuaGFzX2RhdGEgPT09IGZhbHNlOwogICAgICB2YXIgY29sID0gbm9EYXRhID8gJ3ZhcigtLW11dGVkKScgOiBjci5wYXNzZWQgPyAndmFyKC0tZ3JlZW4pJyA6IGltcENvbG9yKGMuaW1wKTsKICAgICAgdmFyIGJnID0gbm9EYXRhID8gJ3JnYmEoMjU1LDI1NSwyNTUsLjAyKScgOiBjci5wYXNzZWQgPyAncmdiYSgxNiwxODUsMTI5LC4wNiknIDogKGMuaW1wPT09J2NyaXRpY2FsJz8ncmdiYSgyMzksNjgsNjgsLjA4KSc6Yy5pbXA9PT0naW1wb3J0YW50Jz8ncmdiYSgyNDUsMTU4LDExLC4wNiknOidyZ2JhKDI1NSwyNTUsMjU1LC4wMiknKTsKICAgICAgdmFyIGJkID0gbm9EYXRhID8gJ3JnYmEoMjU1LDI1NSwyNTUsLjA1KScgOiBjci5wYXNzZWQgPyAncmdiYSgxNiwxODUsMTI5LC4yKScgOiAoYy5pbXA9PT0nY3JpdGljYWwnPydyZ2JhKDIzOSw2OCw2OCwuMiknOmMuaW1wPT09J2ltcG9ydGFudCc/J3JnYmEoMjQ1LDE1OCwxMSwuMiknOidyZ2JhKDI1NSwyNTUsMjU1LC4wNSknKTsKICAgICAgdmFyIGljb24gPSBub0RhdGEgPyAn4qycJyA6IGNyLnBhc3NlZCA/ICfinIUnIDogJ+KdjCc7CiAgICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6JytiZysnO2JvcmRlcjoxcHggc29saWQgJytiZCsnO2JvcmRlci1yYWRpdXM6NXB4O3BhZGRpbmc6NXB4IDhweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2p1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuO2FsaWduLWl0ZW1zOmNlbnRlciI+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6Jytjb2wrJyI+JytpY29uKycgJytjLmxhYmVsKyc8L3NwYW4+JzsKICAgICAgaCArPSAnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK2ltcExhYmVsKGMuaW1wKS5zcGxpdCgnICcpWzBdKyc8L3NwYW4+PC9kaXY+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Zm9udC13ZWlnaHQ6NjAwO2NvbG9yOicrKG5vRGF0YT8ndmFyKC0tbXV0ZWQpJzpjci5wYXNzZWQ/J3ZhcigtLXRleHQpJzpjb2wpKyciPicrY3IudmFsKycgPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpO2ZvbnQtd2VpZ2h0OjQwMCI+JysoIW5vRGF0YT8nbGltaXQ6ICc6JycpK2MubGltaXQrJzwvc3Bhbj48L2Rpdj4nOwogICAgICBoICs9ICc8L2Rpdj4nOwogICAgfSk7CiAgICBoICs9ICc8L2Rpdj48L2Rpdj4nOwogICAgcmV0dXJuIGg7CiAgfQoKICBmdW5jdGlvbiBzdG9ja1JvdyhyLCBleHBhbmRlZCl7CiAgICB2YXIgcGN0ID0gci5wY3Q7CiAgICB2YXIgY29sID0gcGN0Pj04MD8ndmFyKC0tZ3JlZW4pJzpwY3Q+PTYwPyd2YXIoLS1ncmVlbjIpJzpwY3Q+PTQwPyd2YXIoLS15ZWxsb3cpJzondmFyKC0tcmVkMiknOwogICAgdmFyIHBiID0gci5pbl9wb3J0Zm9saW8/JzxzcGFuIHN0eWxlPSJjb2xvcjp2YXIoLS1ncmVlbik7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWxlZnQ6NHB4Ij5QPC9zcGFuPic6Jyc7CiAgICB2YXIgd2IgPSByLmluX3dhdGNobGlzdD8nPHNwYW4gc3R5bGU9ImNvbG9yOiM2MGE1ZmE7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWxlZnQ6NHB4Ij5XPC9zcGFuPic6Jyc7CiAgICB2YXIgY2hnQ29sID0gci5jaGFuZ2U+PTA/J3ZhcigtLWdyZWVuMiknOid2YXIoLS1yZWQyKSc7CiAgICB2YXIgY3JpdEZhaWwgPSBjcml0ZXJpYS5maWx0ZXIoZnVuY3Rpb24oYyl7cmV0dXJuIHIuY3JpdGVyaWEmJnIuY3JpdGVyaWFbYy5pZF0mJiFyLmNyaXRlcmlhW2MuaWRdLnBhc3NlZCYmYy5pbXA9PT0nY3JpdGljYWwnO30pOwogICAgdmFyIHdhcm5UYWdzID0gY3JpdEZhaWwubWFwKGZ1bmN0aW9uKGMpewogICAgICByZXR1cm4gJzxzcGFuIHN0eWxlPSJiYWNrZ3JvdW5kOnJnYmEoMjM5LDY4LDY4LC4xKTtjb2xvcjp2YXIoLS1yZWQyKTtwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDttYXJnaW4tcmlnaHQ6M3B4Ij7inYwnK2MubGFiZWwrJzwvc3Bhbj4nOwogICAgfSkuam9pbignJyk7CiAgICByZXR1cm4gJzxkaXYgc3R5bGU9ImJvcmRlci1ib3R0b206MXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA0KSIgaWQ9InNjLXJvdy0nK3IudGlja2VyKyciPicKICAgICAgKyc8ZGl2IHN0eWxlPSJkaXNwbGF5OmdyaWQ7Z3JpZC10ZW1wbGF0ZS1jb2x1bW5zOjEzMHB4IDFmciA4MHB4IDgwcHg7YWxpZ24taXRlbXM6Y2VudGVyO2dhcDoxMHB4O3BhZGRpbmc6MTBweCAxNHB4O2N1cnNvcjpwb2ludGVyIiBpZD0ic2MtJytyLnRpY2tlcisnIj4nCiAgICAgICsnPGRpdj48ZGl2IHN0eWxlPSJmb250LXdlaWdodDo3MDA7Zm9udC1zaXplOjE0cHg7bGV0dGVyLXNwYWNpbmc6MXB4Ij4nK3IudGlja2VyK3BiK3diKyc8L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZm9udC1zaXplOjlweDtjb2xvcjp2YXIoLS1tdXRlZCkiPicrci5uYW1lLnN1YnN0cmluZygwLDE4KSsnPC9kaXY+PC9kaXY+JwogICAgICArJzxkaXY+PGRpdiBzdHlsZT0iaGVpZ2h0OjRweDtiYWNrZ3JvdW5kOnZhcigtLWJnMyk7Ym9yZGVyLXJhZGl1czoycHg7b3ZlcmZsb3c6aGlkZGVuIj4nCiAgICAgICsnPGRpdiBzdHlsZT0iaGVpZ2h0OjEwMCU7d2lkdGg6JytwY3QrJyU7YmFja2dyb3VuZDonK2NvbCsnO2JvcmRlci1yYWRpdXM6MnB4Ij48L2Rpdj48L2Rpdj4nCiAgICAgICsnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtnYXA6NHB4O21hcmdpbi10b3A6M3B4Ij4nK3dhcm5UYWdzCiAgICAgICsnPHNwYW4gc3R5bGU9ImZvbnQtc2l6ZTo5cHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj4nK3Iuc2NvcmUrJy8xOTwvc3Bhbj4nCiAgICAgICsnPHNwYW4gc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4xNSk7Y29sb3I6IzYwYTVmYTtwYWRkaW5nOjFweCA1cHg7Ym9yZGVyLXJhZGl1czozcHg7Zm9udC1zaXplOjlweDtmb250LXdlaWdodDo2MDAiPlJTOicrci5yc19yYXRpbmcrJzwvc3Bhbj4nCiAgICAgICsnPC9kaXY+PC9kaXY+JwogICAgICArJzxkaXYgc3R5bGU9InRleHQtYWxpZ246cmlnaHQiPjxkaXYgc3R5bGU9ImZvbnQtd2VpZ2h0OjcwMDtjb2xvcjonK2NvbCsnO2ZvbnQtc2l6ZToxNXB4Ij4nK3BjdCsnJTwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6OXB4O2NvbG9yOnZhcigtLW11dGVkKSI+YcSfxLFybMSxa2zEsTwvZGl2PjwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJ0ZXh0LWFsaWduOnJpZ2h0Ij48ZGl2IHN0eWxlPSJmb250LXdlaWdodDo2MDAiPiQnK3IucHJpY2UrJzwvZGl2PicKICAgICAgKyc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjonK2NoZ0NvbCsnIj4nKyhyLmNoYW5nZT49MD8nKyc6JycpK3IuY2hhbmdlKyclPC9kaXY+PC9kaXY+JwogICAgICArJzwvZGl2PicKICAgICAgKyhleHBhbmRlZCA/IGNyaXRlcmlhRGV0YWlsKHIpIDogJycpCiAgICAgICsnPC9kaXY+JzsKICB9CgogIGZ1bmN0aW9uIGJ1aWxkSFRNTCgpewogICAgdmFyIGggPSAnPGRpdiBzdHlsZT0iZ3JpZC1jb2x1bW46MS8tMSI+JzsKCiAgICAvLyBTdW1tYXJ5CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJiYWNrZ3JvdW5kOnZhcigtLWJnMik7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1ib3JkZXIpO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjE2cHggMjBweDttYXJnaW4tYm90dG9tOjE0cHgiPic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTZweDtmb250LXdlaWdodDo3MDA7bWFyZ2luLWJvdHRvbTo0cHgiPvCflI0gQ0FOU0xJTSBTY3JlZW5lcjwvZGl2Pic7CiAgICBoICs9ICc8ZGl2IHN0eWxlPSJmb250LXNpemU6MTFweDtjb2xvcjp2YXIoLS1tdXRlZCk7bWFyZ2luLWJvdHRvbToxMnB4Ij4xNiBrcml0ZXIgwrcgMyDDtm5lbSBzZXZpeWVzaSDCtyAnK2RhdGEubGVuZ3RoKycgaGlzc2UgdGFyYW5kxLE8L2Rpdj4nOwogICAgaCArPSAnPGRpdiBzdHlsZT0iZGlzcGxheTpmbGV4O2dhcDoxMHB4O2ZsZXgtd3JhcDp3cmFwO21hcmdpbi1ib3R0b206MTJweCI+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgxNiwxODUsMTI5LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDE2LDE4NSwxMjksLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Y29sb3I6dmFyKC0tZ3JlZW4pIj4nK3Bhc3NlZC5sZW5ndGgrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+R2XDp3RpPC9kaXY+PC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSgyMzksNjgsNjgsLjA4KTtib3JkZXI6MXB4IHNvbGlkIHJnYmEoMjM5LDY4LDY4LC4yKTtib3JkZXItcmFkaXVzOjhweDtwYWRkaW5nOjEwcHggMTZweDt0ZXh0LWFsaWduOmNlbnRlciI+PGRpdiBzdHlsZT0iZm9udC1zaXplOjIycHg7Zm9udC13ZWlnaHQ6NzAwO2NvbG9yOnZhcigtLXJlZDIpIj4nK2ZhaWxlZC5sZW5ndGgrJzwvZGl2PjxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxMHB4O2NvbG9yOnZhcigtLW11dGVkKSI+R2XDp2VtZWRpPC9kaXY+PC9kaXY+JzsKICAgIGggKz0gJzxkaXYgc3R5bGU9ImJhY2tncm91bmQ6cmdiYSg1OSwxMzAsMjQ2LC4wOCk7Ym9yZGVyOjFweCBzb2xpZCByZ2JhKDU5LDEzMCwyNDYsLjIpO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6MTBweCAxNnB4O3RleHQtYWxpZ246Y2VudGVyIj48ZGl2IHN0eWxlPSJmb250LXNpemU6MjJweDtmb250LXdlaWdodDo3MDA7Y29sb3I6IzYwYTVmYSI+JytkYXRhLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5pbl93YXRjaGxpc3R8fHIuaW5fcG9ydGZvbGlvO30pLmxlbmd0aCsnPC9kaXY+PGRpdiBzdHlsZT0iZm9udC1zaXplOjEwcHg7Y29sb3I6dmFyKC0tbXV0ZWQpIj5MaXN0ZW1kZTwvZGl2PjwvZGl2Pic7CiAgICBoICs9ICc8L2Rpdj4nOwogICAgLy8gTGVnZW5kCiAgICBoICs9ICc8ZGl2IHN0eWxlPSJkaXNwbGF5OmZsZXg7Z2FwOjEwcHg7ZmxleC13cmFwOndyYXA7Zm9udC1zaXplOjEwcHgiPic7CiAgICBoICs9ICc8c3Bhbj7wn5S0IDxzdHJvbmc+Wm9ydW5sdTwvc3Ryb25nPiAoM3gpOiBFUFMgUW9RLCBTTUEyMDAsIE0gS3JpdGVyaTwvc3Bhbj4nOwogICAgaCArPSAnPHNwYW4+8J+foSA8c3Ryb25nPsOWbmVtbGk8L3N0cm9uZz4gKDJ4KTogR2VsaXIsIFJPRSwgTWFyamluLCBTTUE1MCwgNTJIPC9zcGFuPic7CiAgICBoICs9ICc8c3Bhbj7wn5S1IDxzdHJvbmc+RGVzdGVrPC9zdHJvbmc+ICgxeCk6IERpxJ9lcmxlcmk8L3NwYW4+JzsKICAgIGggKz0gJzwvZGl2PjwvZGl2Pic7CgogICAgLy8gR2XDp2VubGVyCiAgICBpZihwYXNzZWQubGVuZ3RoKXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgcmdiYSgxNiwxODUsMTI5LC4yKTtib3JkZXItcmFkaXVzOjEycHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi1ib3R0b206MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0icGFkZGluZzoxMHB4IDE0cHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpO2ZvbnQtc2l6ZToxMXB4O2NvbG9yOnZhcigtLWdyZWVuKTtsZXR0ZXItc3BhY2luZzoycHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlIj7inIUgQ0FOU0xJTSBHZcOndGkgKCcrcGFzc2VkLmxlbmd0aCsnKTwvZGl2Pic7CiAgICAgIHBhc3NlZC5mb3JFYWNoKGZ1bmN0aW9uKHIpeyBoICs9IHN0b2NrUm93KHIsIHIudGlja2VyPT09ZXhwYW5kZWRUaWNrZXIpOyB9KTsKICAgICAgaCArPSAnPC9kaXY+JzsKICAgIH0KCiAgICAvLyBXYXRjaGxpc3QvUG9ydGZvbGlvIChnZcOnZW1leWVubGVyKQogICAgdmFyIG15RmFpbGVkID0gZmFpbGVkLmZpbHRlcihmdW5jdGlvbihyKXtyZXR1cm4gci5pbl93YXRjaGxpc3R8fHIuaW5fcG9ydGZvbGlvO30pOwogICAgaWYobXlGYWlsZWQubGVuZ3RoKXsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0iYmFja2dyb3VuZDp2YXIoLS1iZzIpO2JvcmRlcjoxcHggc29saWQgcmdiYSg1OSwxMzAsMjQ2LC4yKTtib3JkZXItcmFkaXVzOjEycHg7b3ZlcmZsb3c6aGlkZGVuO21hcmdpbi1ib3R0b206MTRweCI+JzsKICAgICAgaCArPSAnPGRpdiBzdHlsZT0icGFkZGluZzoxMHB4IDE0cHg7Ym9yZGVyLWJvdHRvbToxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpO2ZvbnQtc2l6ZToxMXB4O2NvbG9yOiM2MGE1ZmE7bGV0dGVyLXNwYWNpbmc6MnB4O3RleHQtdHJhbnNmb3JtOnVwcGVyY2FzZSI+8J+TiyBMaXN0ZW1kZSAoR2XDp2VtZWRpLCAnK215RmFpbGVkLmxlbmd0aCsnKTwvZGl2Pic7CiAgICAgIG15RmFpbGVkLmZvckVhY2goZnVuY3Rpb24ocil7IGggKz0gc3RvY2tSb3cociwgci50aWNrZXI9PT1leHBhbmRlZFRpY2tlcik7IH0pOwogICAgICBoICs9ICc8L2Rpdj4nOwogICAgfQoKICAgIGggKz0gJzwvZGl2Pic7CiAgICByZXR1cm4gaDsKICB9CgogIGdyaWQuaW5uZXJIVE1MID0gYnVpbGRIVE1MKCk7CgogIC8vIG9uY2xpY2sgaGFuZGxlcnMKICBkYXRhLmZvckVhY2goZnVuY3Rpb24ocil7CiAgICB2YXIgZWwgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgnc2MtJytyLnRpY2tlcik7CiAgICBpZihlbCl7CiAgICAgIGVsLm9uY2xpY2sgPSBmdW5jdGlvbihlKXsKICAgICAgICBlLnN0b3BQcm9wYWdhdGlvbigpOwogICAgICAgIGlmKGV4cGFuZGVkVGlja2VyPT09ci50aWNrZXIpeyBleHBhbmRlZFRpY2tlcj1udWxsOyB9CiAgICAgICAgZWxzZSB7IGV4cGFuZGVkVGlja2VyPXIudGlja2VyOyB9CiAgICAgICAgZ3JpZC5pbm5lckhUTUwgPSBidWlsZEhUTUwoKTsKICAgICAgICAvLyBSZS1hdHRhY2ggaGFuZGxlcnMKICAgICAgICBkYXRhLmZvckVhY2goZnVuY3Rpb24ocjIpewogICAgICAgICAgdmFyIGVsMiA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCdzYy0nK3IyLnRpY2tlcik7CiAgICAgICAgICBpZihlbDIpIGVsMi5vbmNsaWNrID0gYXJndW1lbnRzLmNhbGxlZS5iaW5kKHt0aWNrZXI6cjIudGlja2VyfSk7CiAgICAgICAgfSk7CiAgICAgICAgYXR0YWNoSGFuZGxlcnMoKTsKICAgICAgfTsKICAgIH0KICB9KTsKCiAgZnVuY3Rpb24gYXR0YWNoSGFuZGxlcnMoKXsKICAgIGRhdGEuZm9yRWFjaChmdW5jdGlvbihyKXsKICAgICAgdmFyIGVsID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoJ3NjLScrci50aWNrZXIpOwogICAgICBpZighZWwpIHJldHVybjsKICAgICAgZWwub25jbGljayA9IChmdW5jdGlvbih0aWNrZXIpewogICAgICAgIHJldHVybiBmdW5jdGlvbihlKXsKICAgICAgICAgIGUuc3RvcFByb3BhZ2F0aW9uKCk7CiAgICAgICAgICBleHBhbmRlZFRpY2tlciA9IGV4cGFuZGVkVGlja2VyPT09dGlja2VyID8gbnVsbCA6IHRpY2tlcjsKICAgICAgICAgIGdyaWQuaW5uZXJIVE1MID0gYnVpbGRIVE1MKCk7CiAgICAgICAgICBhdHRhY2hIYW5kbGVycygpOwogICAgICAgIH07CiAgICAgIH0pKHIudGlja2VyKTsKICAgIH0pOwogIH0KICBhdHRhY2hIYW5kbGVycygpOwp9Cjwvc2NyaXB0Pgo8L2JvZHk+CjwvaHRtbD4="
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
