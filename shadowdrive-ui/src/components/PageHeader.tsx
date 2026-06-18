import type { ReactNode } from 'react';

interface PageHeaderProps {
  icon?: string;
  title: string;
  iconColor?: string;
  actions?: ReactNode;
}

export default function PageHeader({
  icon,
  title,
  iconColor = 'text-primary',
  actions,
}: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="flex items-center space-x-2 font-code-sm text-code-sm text-on-surface-variant">
        {icon && (
          <span className={`material-symbols-outlined text-sm ${iconColor}`}>
            {icon}
          </span>
        )}
        <span className="text-on-surface font-bold tracking-wider uppercase">
          {title}
        </span>
      </div>
      {actions && (
        <div className="flex items-center space-x-gutter">
          {actions}
        </div>
      )}
    </header>
  );
}
