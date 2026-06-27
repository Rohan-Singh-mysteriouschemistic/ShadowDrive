import type { ReactNode } from 'react';

interface PageHeaderMobileProps {
  icon?: string;
  title: string;
  iconColor?: string;
  actions?: ReactNode;
  onMenuToggle?: () => void;
}

export default function PageHeaderMobile({
  icon,
  title,
  iconColor = 'text-primary',
  actions,
  onMenuToggle,
}: PageHeaderMobileProps) {
  return (
    <header className="page-header">
      <div className="flex items-center space-x-2 font-code-sm text-code-sm text-on-surface-variant min-w-0 flex-1">
        {icon && (
          <span className={`material-symbols-outlined text-sm ${iconColor} shrink-0`}>
            {icon}
          </span>
        )}
        <span className="text-on-surface font-bold tracking-wider uppercase truncate">
          {title}
        </span>
      </div>
      {actions && (
        <div className="header-actions flex items-center space-x-gutter md:space-x-gutter ml-auto shrink-0">
          {actions}
        </div>
      )}
      {onMenuToggle && (
        <button
          onClick={onMenuToggle}
          className="md:hidden ml-2 p-2 text-on-surface-variant hover:text-primary transition-colors"
          aria-label="Toggle menu"
        >
          <span className="material-symbols-outlined text-[20px]">menu</span>
        </button>
      )}
    </header>
  );
}
