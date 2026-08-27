import Link from 'next/link';

export function BrandMark() {
  return (
    <Link
      aria-label="Fincilia, ir al portafolio"
      className="brand-lockup"
      href="/empresas"
    >
      <svg
        aria-hidden="true"
        className="brand-mark"
        focusable="false"
        viewBox="0 0 40 40"
      >
        <rect height="40" rx="12" width="40" />
        <path d="M10 13h11l3 3 6-6" />
        <path d="M30 27H19l-3-3-6 6" />
        <path d="M10 20h20" />
      </svg>
      <span className="brand-lockup__copy">
        <strong>Fincilia</strong>
        <small>Conciliacion clara</small>
      </span>
    </Link>
  );
}
