import { useState, useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Button from '../components/Button';
import EmptyState from '../components/EmptyState';
import { CLIENT_API_URL } from '../lib/api';

interface TransferItem {
  id: string;
  filename: string;
  direction: 'upload' | 'download';
  progress: number;
  speed: string;
  status: 'active' | 'queued' | 'paused' | 'complete' | 'failed';
  size: string;
  transferred: string;
}

type FilterType = 'all' | 'active' | 'complete' | 'failed';

export default function TransferQueue() {
  const [transfers, setTransfers] = useState<TransferItem[]>([]);
  const [filter, setFilter] = useState<FilterType>('all');

  useEffect(() => {
    const fetchTransfers = async () => {
      try {
        const res = await fetch(`${CLIENT_API_URL}/api/transfers`);
        if (res.ok) {
          const data = await res.json();
          setTransfers(data.transfers || []);
        }
      } catch {
        // API not yet implemented — show empty state
      }
    };

    fetchTransfers();
    const interval = setInterval(fetchTransfers, 2000);
    return () => clearInterval(interval);
  }, []);

  const filteredTransfers = filter === 'all'
    ? transfers
    : transfers.filter(t => t.status === filter);

  const activeCount = transfers.filter(t => t.status === 'active').length;
  const queuedCount = transfers.filter(t => t.status === 'queued').length;

  const filters: FilterType[] = ['all', 'active', 'complete', 'failed'];

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      <PageHeader
        icon="swap_vert"
        title="Transfer Queue"
        iconColor="text-primary"
        actions={
          <div className="flex items-center gap-2">
            {filters.map((f) => (
              <Button
                key={f}
                variant="ghost"
                size="sm"
                className={filter === f ? 'bg-primary/20 text-primary border border-primary/30' : ''}
                onClick={() => setFilter(f)}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </Button>
            ))}
          </div>
        }
      />

      <div className="flex-1 overflow-y-auto p-margin-desktop z-10 flex flex-col items-center">
        <div className="w-full max-w-container-max flex flex-col gap-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card variant="glass" className="p-6 border border-white/5">
              <p className="font-code-sm text-on-surface-variant uppercase tracking-wider mb-2">Active</p>
              <span className="text-display-sm font-display-sm font-bold text-on-surface">{activeCount}</span>
            </Card>
            <Card variant="glass" className="p-6 border border-white/5">
              <p className="font-code-sm text-on-surface-variant uppercase tracking-wider mb-2">Queued</p>
              <span className="text-display-sm font-display-sm font-bold text-on-surface">{queuedCount}</span>
            </Card>
            <Card variant="glass" className="p-6 border border-white/5">
              <p className="font-code-sm text-on-surface-variant uppercase tracking-wider mb-2">Total Today</p>
              <span className="text-display-sm font-display-sm font-bold text-on-surface">{transfers.length}</span>
            </Card>
          </div>

          {filteredTransfers.length === 0 ? (
            <EmptyState
              icon="swap_vert"
              title="No Transfers"
              description={
                filter === 'all'
                  ? "No active file transfers. Files will appear here when syncing."
                  : `No ${filter} transfers found.`
              }
            />
          ) : (
            <Card className="border border-white/10 overflow-hidden">
              <div className="flex flex-col">
                {filteredTransfers.map((transfer) => (
                  <div key={transfer.id} className="flex items-center gap-4 px-6 py-4 border-b border-white/5 hover:bg-white/5 transition-colors group">
                    <span className={`material-symbols-outlined text-lg ${
                      transfer.direction === 'upload' ? 'text-primary' : 'text-[#3b82f6]'
                    }`}>
                      {transfer.direction === 'upload' ? 'cloud_upload' : 'cloud_download'}
                    </span>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-code-sm text-on-surface truncate">{transfer.filename}</span>
                        <span className="font-code-sm text-on-surface-variant ml-2 shrink-0">
                          {transfer.transferred} / {transfer.size}
                        </span>
                      </div>
                      <div className="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${
                            transfer.status === 'failed' ? 'bg-error' :
                            transfer.status === 'complete' ? 'bg-primary' :
                            'bg-primary animate-pulse'
                          }`}
                          style={{ width: `${transfer.progress}%` }}
                        />
                      </div>
                    </div>

                    <span className={`font-label-md text-label-md px-2 py-0.5 rounded ${
                      transfer.status === 'active' ? 'bg-primary/20 text-primary' :
                      transfer.status === 'complete' ? 'bg-primary/10 text-primary/80' :
                      transfer.status === 'failed' ? 'bg-error/20 text-error' :
                      'bg-white/5 text-on-surface-variant'
                    }`}>
                      {transfer.status}
                    </span>

                    <span className="font-code-sm text-on-surface-variant w-16 text-right">
                      {transfer.speed}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
