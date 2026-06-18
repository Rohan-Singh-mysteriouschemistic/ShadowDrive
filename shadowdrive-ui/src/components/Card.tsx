import type { HTMLAttributes, ReactNode } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'glass' | 'glass-darker' | 'bordered' | 'elevated';
  hover?: boolean;
  glow?: 'primary' | 'error' | 'none';
  children: ReactNode;
}

const variantClasses = {
  glass: 'glass-panel',
  'glass-darker': 'glass-panel-darker',
  bordered: 'border border-white/10 bg-surface-container-low/50',
  elevated: 'bg-surface-container border border-white/5 shadow-lg',
};

const hoverClasses = 'hover:border-white/20 hover:translate-y-[-2px] hover:shadow-[0_10px_30px_-10px_rgba(0,0,0,0.5)] transition-all';

const glowClasses = {
  primary: 'shadow-[0_0_15px_rgba(16,185,129,0.3)]',
  error: 'shadow-[0_0_15px_rgba(239,68,68,0.3)]',
  none: '',
};

export default function Card({
  variant = 'glass',
  hover = false,
  glow = 'none',
  children,
  className = '',
  ...rest
}: CardProps) {
  return (
    <div
      className={`rounded-xl overflow-hidden ${variantClasses[variant]} ${hover ? hoverClasses : ''} ${glowClasses[glow]} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}
