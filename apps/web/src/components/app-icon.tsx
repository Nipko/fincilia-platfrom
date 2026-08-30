export type AppIconName =
  | 'portfolio'
  | 'reviews'
  | 'cycles'
  | 'quality'
  | 'reports'
  | 'close'
  | 'audit'
  | 'account'
  | 'platform';

export function AppIcon({ name }: { name: AppIconName }) {
  const common = {
    fill: 'none',
    stroke: 'currentColor',
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    strokeWidth: 1.8,
  };

  return (
    <svg aria-hidden="true" className="app-icon" focusable="false" viewBox="0 0 24 24">
      {name === 'portfolio' ? <>
        <rect {...common} height="15" rx="2.5" width="18" x="3" y="6" />
        <path {...common} d="M8 6V4.5A1.5 1.5 0 0 1 9.5 3h5A1.5 1.5 0 0 1 16 4.5V6M3 11h18" />
      </> : null}
      {name === 'reviews' ? <>
        <path {...common} d="M9 11.5 11 14l4.5-5M7 3h10a2 2 0 0 1 2 2v16l-7-3-7 3V5a2 2 0 0 1 2-2Z" />
      </> : null}
      {name === 'cycles' ? <>
        <circle {...common} cx="12" cy="12" r="8.5" />
        <path {...common} d="M12 7v5l3.2 2M18.5 5.5 20 4" />
      </> : null}
      {name === 'quality' ? <>
        <path {...common} d="m12 3 2.1 4.6L19 9.7l-4 3.1.5 5.2-3.5-2-3.5 2 .5-5.2-4-3.1 4.9-2.1L12 3Z" />
      </> : null}
      {name === 'reports' ? <>
        <path {...common} d="M5 20V10m7 10V4m7 16v-7" />
        <path {...common} d="M3 20h18" />
      </> : null}
      {name === 'close' ? <>
        <circle {...common} cx="12" cy="12" r="8.5" />
        <path {...common} d="m8.5 12 2.3 2.3 4.9-5.1" />
      </> : null}
      {name === 'audit' ? <>
        <path {...common} d="M5 4h14v16H5zM8 8h8M8 12h5M8 16h7" />
      </> : null}
      {name === 'account' ? <>
        <circle {...common} cx="12" cy="8" r="3.2" />
        <path {...common} d="M5.5 20a6.5 6.5 0 0 1 13 0" />
      </> : null}
      {name === 'platform' ? <>
        <path {...common} d="M4 6.5h16v11H4zM8 17.5v2m8-2v2M7 21h10" />
        <path {...common} d="m9 12 2 2 4-4" />
      </> : null}
    </svg>
  );
}
