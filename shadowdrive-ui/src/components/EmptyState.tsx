import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon: string;
  title: string;
  description: string;
  action?: ReactNode;
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-24 px-8 w-full">
      <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center border border-white/10 mb-4">
        <span className="material-symbols-outlined text-4xl text-on-surface-variant">
          {icon}
        </span>
      </div>
      <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold mb-2">
        {title}
      </h3>
      <p className="font-code-sm text-on-surface-variant max-w-sm mb-6">
        {description}
      </p>
      {action}
    </div>
  );
}
