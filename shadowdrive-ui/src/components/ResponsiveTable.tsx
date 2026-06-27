import type { ReactNode } from 'react';

interface Column {
  key: string;
  label: string;
  width?: string;
  mobileHidden?: boolean;
  align?: 'left' | 'center' | 'right';
}

interface ResponsiveTableProps {
  columns: Column[];
  rows: any[];
  renderCell: (row: any, column: Column) => ReactNode;
  onRowClick?: (row: any) => void;
  isLoading?: boolean;
  emptyState?: ReactNode;
  className?: string;
}

export default function ResponsiveTable({
  columns,
  rows,
  renderCell,
  onRowClick,
  isLoading = false,
  emptyState,
  className = '',
}: ResponsiveTableProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="mt-2 font-code-sm text-on-surface-variant">Loading...</span>
        </div>
      </div>
    );
  }

  if (rows.length === 0) {
    return emptyState ? <div>{emptyState}</div> : null;
  }

  return (
    <div className={`w-full overflow-x-auto ${className}`}>
      {/* Desktop Table */}
      <div className="hidden md:block">
        <div className="grid gap-4 px-6 py-4 border-b border-white/10 font-code-sm text-code-sm text-on-surface-variant bg-surface-container-low/50 grid-cols-12">
          {columns.map((col) => (
            !col.mobileHidden && (
              <div key={col.key} className={`text-${col.align || 'left'}`}>
                {col.label}
              </div>
            )
          ))}
        </div>

        <div className="flex flex-col">
          {rows.map((row, idx) => (
            <div
              key={idx}
              className="group grid grid-cols-12 gap-4 px-6 py-4 border-b border-white/5 items-center hover:bg-white/5 transition-colors relative cursor-pointer"
              onClick={() => onRowClick?.(row)}
            >
              {columns.map((col) => (
                !col.mobileHidden && (
                  <div key={col.key} className={`text-${col.align || 'left'}`}>
                    {renderCell(row, col)}
                  </div>
                )
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Mobile Card View */}
      <div className="md:hidden flex flex-col gap-3">
        {rows.map((row, idx) => (
          <div
            key={idx}
            className="bg-surface-container-low/50 border border-white/10 rounded-lg p-4 space-y-3 cursor-pointer hover:bg-surface-container/50 transition-colors"
            onClick={() => onRowClick?.(row)}
          >
            {columns.map((col) => (
              <div key={col.key} className="flex justify-between items-start gap-2">
                <span className="font-label-md text-label-md text-on-surface-variant flex-shrink-0">
                  {col.label}
                </span>
                <div className="text-right flex-1 text-on-surface font-code-sm text-code-sm">
                  {renderCell(row, col)}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
