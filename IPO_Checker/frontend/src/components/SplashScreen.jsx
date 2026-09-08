import { ShieldCheck, TrendingUp, TrendingDown } from 'lucide-react';

const TICKERS = [
  { sym: 'NIFTY 50', px: '24,318', chg: '+0.84%', up: true },
  { sym: 'SENSEX', px: '80,204', chg: '+0.71%', up: true },
  { sym: 'BANKNIFTY', px: '55,142', chg: '−0.12%', up: false },
  { sym: 'LINK INTIME', px: '—', chg: 'LIVE', up: true },
  { sym: 'KFINTECH', px: '—', chg: 'LIVE', up: true },
  { sym: 'BIGSHARE', px: '—', chg: 'LIVE', up: true },
  { sym: 'MUFG INTIME', px: '—', chg: 'LIVE', up: true },
];

const CANDLES = [
  { h: 34, up: true, d: '0.0s' },
  { h: 52, up: false, d: '0.2s' },
  { h: 44, up: true, d: '0.4s' },
  { h: 62, up: true, d: '0.6s' },
  { h: 28, up: false, d: '0.8s' },
  { h: 58, up: false, d: '1.0s' },
  { h: 40, up: true, d: '1.2s' },
  { h: 66, up: true, d: '1.4s' },
  { h: 36, up: false, d: '1.6s' },
  { h: 48, up: true, d: '1.8s' },
  { h: 30, up: false, d: '2.0s' },
  { h: 56, up: true, d: '2.2s' },
];

/**
 * Full-screen loading state shown while the app verifies the stored session
 * (and lets the Render/Aiven free tier wake up). Styled as a dark trading
 * terminal: ticker tape, candlestick chart and a live status line.
 */
export default function SplashScreen({ status = 'Connecting to markets…' }) {
  return (
    <div className="fixed inset-0 z-[100] flex flex-col overflow-hidden bg-[#08120f] text-white">
      {/* Subtle chart grid + glow */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'linear-gradient(rgba(16,185,129,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(16,185,129,0.05) 1px, transparent 1px)',
          backgroundSize: '44px 44px',
        }}
      />
      <div className="pointer-events-none absolute -top-32 left-1/2 h-72 w-[42rem] -translate-x-1/2 rounded-full bg-emerald-500/10 blur-3xl" />

      {/* Ticker tape */}
      <div className="relative border-b border-emerald-400/10 bg-black/20">
        <div className="flex overflow-hidden whitespace-nowrap py-2">
          <div className="splash-ticker flex shrink-0 items-center gap-8 pr-8">
            {[...TICKERS, ...TICKERS].map((t, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-2 text-xs font-medium tracking-wide text-emerald-100/70"
              >
                <span className="font-semibold text-emerald-50">{t.sym}</span>
                <span className="font-mono">{t.px}</span>
                <span className={t.up ? 'text-emerald-400' : 'text-rose-400'}>
                  {t.up ? (
                    <TrendingUp size={13} className="mr-0.5 inline" />
                  ) : (
                    <TrendingDown size={13} className="mr-0.5 inline" />
                  )}
                  {t.chg}
                </span>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Center */}
      <div className="relative flex flex-1 flex-col items-center justify-center px-6">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-emerald-300/20 bg-white/95 shadow-[0_0_50px_-10px_rgba(16,185,129,0.55)]">
          <img src="/mamatlialogo.png" alt="Matalia" className="h-11 w-auto" draggable={false} />
        </div>

        <p className="mt-6 text-[11px] font-semibold uppercase tracking-[0.35em] text-emerald-300/80">
          Matalia
        </p>
        <h1 className="font-display mt-2 text-center text-3xl font-bold tracking-tight text-white md:text-4xl">
          IPO Allotment Verification
        </h1>
        <p className="mt-3 max-w-md text-center text-sm text-emerald-100/60">
          Connecting to the registrar network and settling market data before opening your dashboard.
        </p>

        {/* Candlestick chart */}
        <div className="mt-10 flex h-24 items-end gap-1.5" aria-hidden="true">
          {CANDLES.map((c, i) => (
            <div
              key={i}
              className={`flex w-3 flex-col items-center justify-end ${c.up ? 'splash-candle-up' : 'splash-candle-down'}`}
              style={{ animationDelay: c.d }}
            >
              <div
                className={`w-full rounded-sm ${c.up ? 'bg-emerald-400' : 'bg-rose-400'}`}
                style={{ height: `${c.h}px`, opacity: 0.9 }}
              />
              <div className={`mt-1 h-6 w-px ${c.up ? 'bg-emerald-400/70' : 'bg-rose-400/70'}`} />
            </div>
          ))}
        </div>

        {/* Live status */}
        <div className="mt-10 flex items-center gap-3 rounded-full border border-emerald-400/20 bg-emerald-400/5 px-5 py-2.5">
          <span className="splash-dot h-2 w-2 rounded-full bg-emerald-400" />
          <span className="font-mono text-sm text-emerald-100/90">{status}</span>
        </div>

        <div className="mt-6 flex items-center gap-2 text-[11px] uppercase tracking-[0.25em] text-emerald-100/40">
          <ShieldCheck size={14} /> Secure session · registrar feeds
        </div>
      </div>

      {/* Bottom strip */}
      <div className="relative border-t border-emerald-400/10 py-4 text-center text-[11px] tracking-[0.2em] text-emerald-100/30">
        IPO ALLOTMENT CHECKER · MATALIA BROKING DESK
      </div>
    </div>
  );
}
