import type { ButtonHTMLAttributes, ReactNode } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: string;
  children?: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-primary text-surface-container-lowest font-bold hover:bg-primary-container transition-colors shadow-[0_0_15px_rgba(16,185,129,0.3)] hover:shadow-[0_0_20px_rgba(16,185,129,0.4)]',
  secondary:
    'bg-surface-container border border-primary/30 text-primary hover:bg-primary hover:text-surface-container-lowest transition-all shadow-[0_0_15px_rgba(16,185,129,0.1)] hover:shadow-[0_0_20px_rgba(16,185,129,0.4)]',
  ghost:
    'text-on-surface-variant hover:text-primary hover:bg-white/5 transition-colors',
  danger:
    'text-error hover:bg-error/10 transition-colors border border-error/20',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-label-sm font-label-sm',
  md: 'px-4 py-2 text-label-md font-label-md',
  lg: 'px-6 py-3 text-label-md font-label-md',
};

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className = '',
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg transition-all duration-300 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : icon ? (
        <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
          {icon}
        </span>
      ) : null}
      {children && <span>{children}</span>}
    </button>
  );
}
