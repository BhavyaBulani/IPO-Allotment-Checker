import { Link } from 'react-router-dom';

/**
 * Persistent top bar with the agency logo in the top-left corner.
 * The logo is served from /public so it works on both the Vite dev server
 * and the Vercel production build.
 */
export default function AppHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-stone-200 bg-[#fbfaf7]/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-3" aria-label="Mamatla home">
          <img
            src="/mamatlialogo.png"
            alt="Mamatla"
            className="h-9 w-auto"
            draggable={false}
          />
        </Link>
        <span className="hidden text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400 sm:block">
          IPO Allotment Verification
        </span>
      </div>
    </header>
  );
}
