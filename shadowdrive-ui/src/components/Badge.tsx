interface BadgeProps {
  count: number;
  variant?: 'error' | 'warning' | 'primary' | 'default';
  className?: string;
}

const variantClasses = {
  error:
    'bg-error-container text-on-error-container border border-error/20 shadow-[0_0_8px_rgba(239,68,68,0.3)]',
  warning:
    'bg-yellow-500/20 text-yellow-500 border border-yellow-500/20',
  primary:
    'bg-primary/20 text-primary border border-primary/20',
  default:
    'bg-white/10 text-on-surface-variant border border-white/10',
};

export default function Badge({ count, variant = 'default', className = '' }: BadgeProps) {
  if (count <= 0) return null;
  return (
    <span
      className={`ml-auto text-xs px-2 py-0.5 rounded-full font-code-sm text-code-sm ${variantClasses[variant]} ${className}`}
    >
      {count}
    </span>
  );
}
