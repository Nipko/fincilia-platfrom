import Link from 'next/link';

export function BrandMark() {
  return (
    <Link
      aria-label="Fincilia, ir al inicio"
      className="brand-lockup"
      href="/"
    >
      <svg
        aria-hidden="true"
        className="brand-mark"
        focusable="false"
        viewBox="0 0 96 80"
      >
        <path
          className="brand-mark__sheet"
          d="M38 65H9V8h31v17M58 16h29v56H56V56"
        />
        <path
          className="brand-mark__detail"
          d="M18 21h13M18 51h13M65 30h13M65 61h13"
        />
        <path
          className="brand-mark__match"
          d="M17 35h29v13h33"
        />
      </svg>
      <span className="brand-lockup__copy">
        <strong>Fincilia</strong>
        <small>Conciliación clara</small>
      </span>
    </Link>
  );
}
