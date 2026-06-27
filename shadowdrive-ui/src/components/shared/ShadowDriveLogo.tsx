import { useId } from 'react';

interface ShadowDriveLogoProps {
  size?: number;
  className?: string;
  animated?: boolean;
}

export function ShadowDriveLogo({ size = 24, className = '', animated = true }: ShadowDriveLogoProps) {
  const id = useId();
  const filterId = `glow-${id}`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 120"
      fill="none"
      className={`${className} ${animated ? 'animate-[logo-glow_3s_ease-in-out_infinite]' : ''}`}
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
      style={animated ? {} : { filter: `drop-shadow(0 0 10px rgba(0, 255, 136, 0.4))` }}
    >
      <defs>
        <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="8" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
        <style>{`
          @keyframes logo-glow {
            0%, 100% { filter: drop-shadow(0 0 10px rgba(0, 255, 136, 0.4)); transform: scale(1); }
            50% { filter: drop-shadow(0 0 20px rgba(0, 255, 136, 0.8)); transform: scale(1.02); }
          }
        `}</style>
      </defs>
      {/* Front facets - electric emerald */}
      <path d="M50 0 L85 20 L85 50 L50 70 L15 50 L15 20 Z" fill="#00ff88" />
      {/* Shadow/depth facets - darker greens */}
      <path d="M50 70 L85 50 L85 80 L50 100 Z" fill="#00cc6a" />
      <path d="M50 70 L15 50 L15 80 L50 100 Z" fill="#00994d" />
    </svg>
  );
}
