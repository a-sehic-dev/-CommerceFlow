export function Logo({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="4" y="13" width="3.5" height="7" rx="1" fill="currentColor" opacity="0.45" />
      <rect x="10.25" y="9" width="3.5" height="11" rx="1" fill="currentColor" opacity="0.7" />
      <rect x="16.5" y="5" width="3.5" height="15" rx="1" fill="currentColor" />
      <path
        d="M5.5 16.5 L11 11 L14.5 13.5 L19 7"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="19" cy="7" r="1.35" fill="currentColor" />
    </svg>
  );
}
