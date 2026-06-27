interface ShadowDriveLogoProps {
  size?: number;
  className?: string;
}

export function ShadowDriveLogo({ size = 24, className }: ShadowDriveLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 120"
      fill="none"
      className={className}
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Front facets - accent green */}
      <path d="M50 0 L85 20 L85 50 L50 70 L15 50 L15 20 Z" fill="var(--accent, #10b981)" />
      {/* Shadow/depth facets - darker green */}
      <path d="M50 70 L85 50 L85 80 L50 100 Z" fill="var(--accent-dim, #059669)" />
      <path d="M50 70 L15 50 L15 80 L50 100 Z" fill="#047857" />
    </svg>
  );
}
