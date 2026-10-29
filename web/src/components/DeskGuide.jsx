import { useEffect, useRef, useState } from 'react'
import { useDesk } from '../store'

const GUIDES = {
  volume: {
    title: 'Volume',
    blurb:
      'ChartSchool lookbacks on the selected interval’s bars. Recent listings: periods shrink · Score P/T = partial/thin. Bullish ≥+30 · Bearish ≤−30.',
    params: [
      {
        id: 'Score',
        tip: 'Bias ±30. Recent listings tagged P/T — lookbacks shrink to available bars. ±25 dir · ±25 RVOL · spike/quiet · OBV·CMF·MFI·Break·E/R → ±100',
      },
      {
        id: 'RVOL',
        tip: 'V ÷ SMA(prior 50 bars of selected chip). Intraday=15m/1H/4H bars · Swing=1D/1W/1M · Long 3M–1Y=daily (same as 1D) · 5Y/Max=weekly. Not time-of-day RVOL.',
      },
      { id: 'VolZ', tip: 'Z-score vs same prior RVOL window; ≥2σ = Spike' },
      { id: 'CMF', tip: 'Chaikin Money Flow over CMF bars (incl. current)' },
      { id: 'MFI', tip: 'Money Flow Index — volume-weighted RSI (default 14 bars)' },
      { id: 'Force', tip: 'Elder Force EMA — (ΔClose×Vol), EMA seeded with SMA (default 13)' },
      { id: 'EMV', tip: 'Arms Ease of Movement — SMA of 1-period EMV (default 14)' },
      { id: 'VOsc', tip: 'Volume Oscillator % — SMA(V,short) vs SMA(V,long) (default 5/20)' },
      { id: 'ChOsc', tip: 'Chaikin Oscillator — EMA(ADL,3) − EMA(ADL,10); >0 buying momentum' },
      { id: 'PVO', tip: 'PVO hist — EMA(V,12/26) % then − EMA signal(9); volume MACD' },
      {
        id: 'E/R',
        tip: 'Wyckoff Effort vs Result: Effort=RVOL · Result=spread vs avg + close. Confirm↑/↓ · Absorb · NoDemand/NoSupply',
      },
      {
        id: 'Break',
        tip: 'Correct/False breakout vs Donchian(20) of selected chip + RVOL≥1.5 + strong close. False = wick reject or weak volume',
      },
      { id: 'UV/DV', tip: 'Up-bar ÷ down-bar volume over CMF window' },
      { id: 'OBV', tip: 'On-Balance Volume Δ over CMF window — rising = accumulation' },
      { id: 'A/D', tip: 'Chaikin A/D slope over CMF window' },
      { id: 'VPT', tip: 'Volume Price Trend — cumulative volume × % price change' },
    ],
  },
  tech: {
    title: 'Technical',
    blurb:
      'ChartSchool bar-counts on the selected chip. Recent listings: periods shrink · Score uses available Signals only · Thin/Partial tagged.',
    params: [
      { id: 'Score', tip: '(Σ votes)/(2×N)×100 · skip missing lookbacks · P/T = partial/thin history · Bias ±30' },
      { id: 'Setup', tip: 'Thin (<8 bars) · Trend↑/↓ · Momentum↑/↓ · Overbought/Oversold · Range' },
      { id: 'RSI', tip: 'Wilder RSI(14) on this TF’s bars' },
      { id: 'MACD', tip: 'MACD(12/26/9) hist — hist>0 and line>signal = bullish' },
      { id: 'PPO', tip: 'PPO(12/26/9) hist — % form of MACD; better for comparing stocks (ChartSchool)' },
      { id: 'SMA', tip: 'SMA(20) vs SMA(50) — 20>50 uptrend stack' },
      { id: '50/200', tip: 'SMA50 vs SMA200 — Gold/Death Cross bias (needs ≥200 bars)' },
      { id: 'EMA', tip: 'Close vs EMA(20) — above = short-term bullish' },
      { id: 'Stoch', tip: 'Full Stochastic(14/3/3) %K — ≥50 bull · ≤20/≥80 extremes' },
      { id: 'ADX', tip: 'ADX(14) + DI — ADX≥25 = strong trend; +DI vs −DI = direction' },
      { id: 'Aroon', tip: 'Aroon Osc(25) — Up−Down; ≥50 strong up · ≤−50 strong down (Chande)' },
      { id: '%B', tip: 'Bollinger %B(20,2) — ≥0.8 upper · ≤0.2 lower' },
      { id: 'ROC', tip: 'ROC(12) % — rate of change over 12 bars of this TF' },
      { id: 'CCI', tip: 'CCI(20) — >0 up lean · ≥100/≤−100 strong' },
      { id: '%R', tip: 'Williams %R(14) — >−50 bull · ≤−80/≥−20 extremes' },
      { id: 'ATR%', tip: 'ATR(14)/Close % — volatility of selected interval' },
    ],
  },
  sci: {
    title: 'Lab',
    blurb:
      'ChartSchool bar-counts on the selected chip. Donchian(20) · RVOL(50 prior) · CMF/OBV(20) · BB+ATR squeeze. Recent listings shrink · P/T on score.',
    params: [
      { id: 'Breakout', tip: 'Close > prior HH_N + RVOL≥1.5× + close near highs (N = Donchian on this TF)' },
      { id: 'Bull base', tip: 'Coil + accumulation (CMF>0.05 or OBV↑ or higher lows)' },
      { id: 'Coil', tip: 'Tight Range% + BandWidth/ATR% squeeze + volume dry-up in base' },
      { id: 'Range%', tip: '100×(prior HH−LL)/mid over Donchian N bars of this TF' },
      { id: 'RVOL', tip: 'V ÷ SMA(prior RVOL bars) — current excluded · ≥1.5× confirms break' },
      { id: 'CMF', tip: 'Chaikin CMF over Donchian/base bars — buying in the coil' },
      { id: 'OBV', tip: 'OBV Δ over base bars — rising = quiet accumulation' },
      { id: 'HL', tip: 'Higher pivot lows (3, or 2 if thin) — bullish structure' },
      { id: 'ATR%', tip: 'Wilder ATR(14)/Close % — squeeze when contracting vs prior box' },
      { id: 'Squeeze', tip: 'BandWidth or ATR% < 85% of prior N-bar reading' },
    ],
  },
  chart: {
    title: 'Chart',
    blurb:
      'Daily: 126 · 252 · 504 · 756 · 1008 · 1260 · 2520 sessions. Swing: 104 and 260 weeks. Long: 60 months and 520 weeks. Each chip uses RVOL(50), S/R base(20), trend ≥3. IPO: shrink · dampen · T/P.',
    params: [
      { id: 'S/R', tip: 'Sup/Res from pivots (or HH/LL if few pivots) · near ≤1.25% (wider on IPO)' },
      { id: 'Range%', tip: '100×(Res−Sup)/mid over adapted S/R look' },
      { id: 'Trend line', tip: '≥3 touches when history allows · 2 touches on thin · HL/LH structure' },
      { id: 'Gap', tip: 'low>prior high / high<prior low · breakaway needs congestion + RVOL≥1.4 prior' },
      { id: 'RVOL', tip: 'V ÷ SMA(prior RVOL bars, shrunk if short) — confirms gaps/breaks' },
      { id: 'Pattern', tip: 'Rectangle · triangles · double · flag — gaps shrink on short history' },
      { id: 'Fib', tip: 'Alert ≤1% of 38.2/50/61.8 · off until ≥24 bars (IPO-safe)' },
      { id: 'Candle', tip: 'Hammer/star need context at S/R · engulfing wraps prior body' },
      {
        id: 'IPO / Thin',
        tip: 'Recent listings: all available bars · lookbacks shrink · near zone wider · score pulled toward 50 · High edge off when thin',
      },
      {
        id: 'High edge',
        tip: 'Top ChartSchool edges on full/partial history — not claimed on thin IPOs',
      },
      {
        id: 'Score',
        tip: 'Projected 0…100 · dampened on thin (×0.45) / partial (×0.70) · T/P tag · bullish ≥60',
      },
    ],
  },
  spurts: {
    title: 'Spurts',
    blurb:
      'Live NSE + BSE table. Vol× is the exchange multiple (NSE 1-week, BSE 2-week). 2W× is the NSE 2-week multiple. Archive holds By date and Reappeared.',
    params: [
      { id: 'Live table', tip: 'Default · Rank · Exch · Stock · Chg · Vol× · Volume · LTP…' },
      { id: 'Date', tip: 'Toolbar · Live today, or load any saved day’s table' },
      { id: 'Archive', tip: 'Collapsed on demand · By date table + Reappeared table' },
      { id: 'Save day', tip: 'Write today’s list to data/spurts_history/ (also auto after 15:30 IST)' },
      { id: 'Vol×', tip: 'Session volume ÷ exchange reference average' },
    ],
  },
}

const FORMULA_ORDER = [
  'timeframe',
  'history',
  'score',
  'bias',
  'high_edge',
  'confluence',
  'setup',
  'support',
  'resistance',
  'dist',
  'range_width',
  'trend',
  'rvol',
  'gap',
  'pattern',
  'rectangle',
  'asc_triangle',
  'desc_triangle',
  'sym_triangle',
  'double_bottom',
  'double_top',
  'flag',
  'fib',
  'candle',
  'hammer',
  'engulfing',
  'reappear',
  'rsi',
  'macd',
  'ppo',
  'sma',
  'sma200',
  'ema',
  'bb',
  'stoch',
  'cci',
  'willr',
  'adx',
  'aroon',
  'roc',
  'atr',
  'vol_z',
  'cmf',
  'mfi',
  'force',
  'emv',
  'vol_osc',
  'chaikin',
  'pvo',
  'effort_result',
  'breakout',
  'obv',
  'range',
  'squeeze',
  'structure',
  'gap_up',
  'gap_down',
  'breakaway_gap',
  'bull_breakout',
  'vol_x',
  'nse',
  'bse',
  'bullish',
  'bearish',
]

export default function DeskGuide() {
  const desk = useDesk((s) => s.desk)
  const board = useDesk((s) => s.board)
  const guide = GUIDES[desk] || GUIDES.volume
  const names = guide.params.map((p) => p.id).join(' · ')
  const formulas = board?.formulas || null
  const tfMeta = board?.tf_meta && desk !== 'spurts' ? board.tf_meta : null
  const formulaKeys = formulas
    ? FORMULA_ORDER.filter((k) => formulas[k]).concat(
        Object.keys(formulas).filter((k) => !FORMULA_ORDER.includes(k)),
      )
    : []

  const detailsRef = useRef(null)
  const bodyRef = useRef(null)
  const [open, setOpen] = useState(false)
  const [canUp, setCanUp] = useState(false)
  const [canDown, setCanDown] = useState(false)

  useEffect(() => {
    const el = bodyRef.current
    if (!open || !el) {
      setCanUp(false)
      setCanDown(false)
      return undefined
    }

    function sync() {
      const top = el.scrollTop
      const max = el.scrollHeight - el.clientHeight
      setCanUp(top > 4)
      setCanDown(max > 8 && top < max - 4)
    }

    sync()
    el.addEventListener('scroll', sync, { passive: true })
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(sync) : null
    ro?.observe(el)
    if (el.firstElementChild) ro?.observe(el.firstElementChild)
    window.addEventListener('resize', sync)
    // Layout settles after open animation / fonts
    const t = window.setTimeout(sync, 50)
    return () => {
      el.removeEventListener('scroll', sync)
      ro?.disconnect()
      window.removeEventListener('resize', sync)
      window.clearTimeout(t)
    }
  }, [open, desk, guide.params.length, formulaKeys.length])

  const step = () => {
    const el = bodyRef.current
    return el ? Math.max(120, el.clientHeight * 0.7) : 140
  }

  return (
    <details
      ref={detailsRef}
      className="desk-guide"
      aria-label={`${guide.title} parameters`}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary className="desk-guide-summary">
        <span className="desk-guide-title">{guide.title}</span>
        <span className="desk-guide-mini" title={guide.blurb}>
          {names}
        </span>
        <span className="desk-guide-toggle" aria-hidden="true">
          {open ? '−' : '+'}
        </span>
      </summary>
      <div className="desk-guide-shell">
        <div className="desk-guide-body" ref={bodyRef} tabIndex={0}>
          {guide.blurb ? <p className="desk-guide-blurb">{guide.blurb}</p> : null}
          {tfMeta ? (
            <p className="desk-guide-tf">
              {tfMeta.label} · {tfMeta.resolution_label}
              {desk === 'volume' && tfMeta.volume
                ? ` · RVOL=${tfMeta.volume.rvol} · CMF=${tfMeta.volume.cmf} · MFI=${tfMeta.volume.mfi} · Force=${tfMeta.volume.force} · EMV=${tfMeta.volume.emv} · VOsc=${tfMeta.volume.vol_osc} · ChOsc=${tfMeta.volume.chaikin} · PVO=${tfMeta.volume.pvo}`
                : desk === 'tech' && tfMeta.tech
                  ? ` · RSI=${tfMeta.tech.rsi} · MACD=${tfMeta.tech.macd} · SMA=${tfMeta.tech.sma} · EMA=${tfMeta.tech.ema} · Stoch=${tfMeta.tech.stoch} · ADX=${tfMeta.tech.adx} · BB=${tfMeta.tech.bb} · ATR=${tfMeta.tech.atr}`
                  : desk === 'sci' && tfMeta.lab
                    ? ` · Donchian=${tfMeta.lab.donchian} · RVOL=${tfMeta.lab.rvol} · CMF=${tfMeta.lab.cmf} · BB=${tfMeta.lab.bb} · ATR=${tfMeta.lab.atr} · break≥${tfMeta.lab.break_rvol}×`
                    : desk === 'chart' && tfMeta.chart
                      ? ` · S/R=${tfMeta.chart.sr} · look≤${tfMeta.chart.sr_look} · RVOL=${tfMeta.chart.rvol} · near≤${tfMeta.chart.near_pct}% · gap≥${tfMeta.chart.gap_rvol}× · trend≥${tfMeta.chart.trend_touches}`
                      : `${tfMeta.avg_window != null ? ` · CMF=${tfMeta.avg_window}` : ''}${tfMeta.rvol_window != null ? ` · RVOL=${tfMeta.rvol_window}` : ''}`}
            </p>
          ) : null}
          <div className="desk-guide-params">
            {guide.params.map((p) => {
              const vol = tfMeta?.volume
              let tip = p.tip
              if (desk === 'volume' && vol) {
                if (p.id === 'RVOL') tip = `ChartSchool RVOL(${vol.rvol}) on ${tfMeta.resolution_label} — V ÷ SMA(prior ${vol.rvol}); ≥${vol.spike_rvol}× = Spike`
                else if (p.id === 'VolZ') tip = `Z-score vs prior ${vol.vol_z} bars; ≥${vol.spike_vol_z}σ = Spike`
                else if (p.id === 'CMF') tip = `Chaikin CMF(${vol.cmf}) on ${tfMeta.resolution_label}`
                else if (p.id === 'MFI') tip = `MFI(${vol.mfi}) — volume-weighted RSI`
                else if (p.id === 'Force') tip = `Elder Force EMA(${vol.force}) — seeded with SMA of first ${vol.force}`
                else if (p.id === 'EMV') tip = `Arms EMV SMA(${vol.emv})`
                else if (p.id === 'VOsc') tip = `VolOsc ${vol.vol_osc} — SMA short vs long %`
                else if (p.id === 'ChOsc') tip = `Chaikin Osc(${vol.chaikin}) — EMA(ADL) fast − slow`
                else if (p.id === 'PVO') tip = `PVO(${vol.pvo}) hist — volume MACD confirmation`
              else if (p.id === 'E/R')
                tip = `Effort vs Result on ${tfMeta.resolution_label} — spread vs prior ${vol.spread ?? vol.cmf} bars · Effort from RVOL(${vol.rvol})`
              else if (p.id === 'Break')
                tip = `Donchian(${vol.donchian ?? vol.cmf}) on ${tfMeta.resolution_label} + RVOL≥${vol.spike_rvol}× for Correct break`
              else if (p.id === 'UV/DV' || p.id === 'OBV' || p.id === 'A/D')
                tip = `${p.tip.split('—')[0] || p.id} over ${vol.cmf} bars`
            }
            if (desk === 'tech' && tfMeta?.tech) {
              const t = tfMeta.tech
              if (p.id === 'RSI') tip = `Wilder RSI(${t.rsi}) on ${tfMeta.resolution_label}`
              else if (p.id === 'MACD') tip = `MACD(${t.macd}) on ${tfMeta.resolution_label}`
              else if (p.id === 'PPO') tip = `PPO(${t.ppo || t.macd}) hist on ${tfMeta.resolution_label}`
              else if (p.id === 'SMA') tip = `SMA(${t.sma}) stack on ${tfMeta.resolution_label}`
              else if (p.id === '50/200') tip = `SMA(${t.sma200 || '50/200'}) Gold/Death on ${tfMeta.resolution_label}`
              else if (p.id === 'EMA') tip = `Close vs EMA(${t.ema}) on ${tfMeta.resolution_label}`
              else if (p.id === 'Stoch') tip = `Full Stochastic(${t.stoch}) on ${tfMeta.resolution_label}`
              else if (p.id === 'ADX') tip = `ADX(${t.adx}) + DI on ${tfMeta.resolution_label}`
              else if (p.id === 'Aroon') tip = `Aroon Osc(${t.aroon}) on ${tfMeta.resolution_label}`
              else if (p.id === '%B') tip = `Bollinger %B(${t.bb}) on ${tfMeta.resolution_label}`
              else if (p.id === 'ROC') tip = `ROC(${t.roc}) on ${tfMeta.resolution_label}`
              else if (p.id === 'CCI') tip = `CCI(${t.cci}) on ${tfMeta.resolution_label}`
              else if (p.id === '%R') tip = `Williams %R(${t.willr}) on ${tfMeta.resolution_label}`
              else if (p.id === 'ATR%') tip = `ATR(${t.atr})/Close % on ${tfMeta.resolution_label}`
            }
            if (desk === 'sci' && tfMeta?.lab) {
              const lab = tfMeta.lab
              if (p.id === 'Breakout')
                tip = `Close > prior HH_${lab.donchian} + RVOL≥${lab.break_rvol}× on ${tfMeta.resolution_label}`
              else if (p.id === 'Bull base')
                tip = `Coil + CMF(${lab.cmf})/OBV(${lab.obv})/HL accumulation on ${tfMeta.resolution_label}`
              else if (p.id === 'Range%') tip = `Donchian(${lab.donchian}) Range% on ${tfMeta.resolution_label}`
              else if (p.id === 'RVOL') tip = `ChartSchool RVOL(${lab.rvol}) prior bars on ${tfMeta.resolution_label}`
              else if (p.id === 'CMF') tip = `CMF(${lab.cmf}) in base on ${tfMeta.resolution_label}`
              else if (p.id === 'OBV') tip = `OBV Δ over ${lab.obv} bars on ${tfMeta.resolution_label}`
              else if (p.id === 'HL') tip = `Higher pivot lows on ${tfMeta.resolution_label}`
              else if (p.id === 'ATR%') tip = `ATR(${lab.atr})/Close % on ${tfMeta.resolution_label}`
              else if (p.id === 'Squeeze') tip = `BB(${lab.bb}) BandWidth or ATR(${lab.atr}) contraction`
              else if (p.id === 'Coil') tip = `Range%≤${lab.coil_range_pct} lean + squeeze + vol dry-up`
            }
            if (desk === 'chart' && tfMeta?.chart) {
              const c = tfMeta.chart
              if (p.id === 'S/R')
                tip = `Pivot S/R on last ≤${c.sr_look} bars · base ${c.sr} · near≤${c.near_pct}% · zone ${c.zone_pct}% on ${tfMeta.resolution_label}`
              else if (p.id === 'Range%')
                tip = `S/R range width on look≤${c.sr_look} · base ${c.sr} on ${tfMeta.resolution_label}`
              else if (p.id === 'Trend line')
                tip = `≥${c.trend_touches} touches when history allows · 2 on thin · HL/LH on ${tfMeta.resolution_label}`
              else if (p.id === 'Gap')
                tip = `Gap + RVOL≥${c.gap_rvol}× (prior ${c.rvol}) on ${tfMeta.resolution_label}`
              else if (p.id === 'RVOL')
                tip = `ChartSchool RVOL(${c.rvol}) prior bars · gap confirm ≥${c.gap_rvol}× on ${tfMeta.resolution_label}`
              else if (p.id === 'Fib')
                tip = `Fib swing ≥${c.fib_swing} bars · alert ≤1% of 38.2/50/61.8 on ${tfMeta.resolution_label}`
              else if (p.id === 'Candle')
                tip = `Hammer/star stronger at S/R or Fib · engulfing wraps prior body on ${tfMeta.resolution_label}`
              else if (p.id === 'IPO / Thin')
                tip = `Recent listings on ${tfMeta.resolution_label}: lookbacks shrink to available bars · near wider · score dampened · T/P`
              else if (p.id === 'High edge')
                tip = `High-success edges on ${tfMeta.resolution_label} — vol break RVOL≥${c.gap_rvol}× · not claimed on thin IPOs`
              else if (p.id === 'Score')
                tip = `Projected from ChartSchool edges · thin×0.45 / partial×0.70 · bullish ≥60 · P/T = short history`
            }
              return (
                <div key={p.id} className="guide-chip" title={tip}>
                  <em>{p.id}</em>
                  <span>{tip}</span>
                </div>
              )
            })}
          </div>
          {formulas ? (
            <details className="desk-guide-formulas">
              <summary>Formulas ({formulaKeys.length})</summary>
              <ul>
                {formulaKeys.map((key) => (
                  <li key={key}>
                    <strong>{key}</strong>
                    <span> — {formulas[key]}</span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
        {open && (canUp || canDown) ? (
          <div className="desk-guide-scroll" aria-label="Scroll Volume description">
            <button
              type="button"
              title="Scroll up"
              aria-label="Scroll up"
              disabled={!canUp}
              onClick={() => bodyRef.current?.scrollBy({ top: -step(), behavior: 'smooth' })}
            >
              ↑
            </button>
            <button
              type="button"
              title="Scroll down"
              aria-label="Scroll down"
              disabled={!canDown}
              onClick={() => bodyRef.current?.scrollBy({ top: step(), behavior: 'smooth' })}
            >
              ↓
            </button>
          </div>
        ) : null}
      </div>
    </details>
  )
}
