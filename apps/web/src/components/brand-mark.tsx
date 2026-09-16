/** A spoken line becoming a marked-up transcript: three bars and a highlighter stroke. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" aria-hidden className={className}>
      <rect x="2" y="18" width="24" height="6" rx="3" className="fill-highlight" />
      <rect x="5" y="9" width="3" height="12" rx="1.5" className="fill-primary" />
      <rect x="12.5" y="4" width="3" height="17" rx="1.5" className="fill-primary" />
      <rect x="20" y="11" width="3" height="10" rx="1.5" className="fill-primary" />
    </svg>
  );
}
