import { useState } from 'react';

interface NetworkEvent {
  id: string;
  timestamp: string;
  node: string;
  type: 'upload' | 'download' | 'sync' | 'error';
  file?: string;
  size?: string;
  message?: string;
}

const MOCK_EVENTS: NetworkEvent[] = [
  { id: '1', timestamp: '14:22:05', node: 'AWS-USEAST-01', type: 'upload', file: 'budget_v2.xlsx', size: '48KB' },
  { id: '2', timestamp: '14:21:30', node: 'MacBook Pro-M3', type: 'sync', message: 'Handshake successful' },
  { id: '3', timestamp: '14:18:12', node: 'Pixel 8 Pro', type: 'error', message: 'Connection timeout (120ms)' },
  { id: '4', timestamp: '14:15:00', node: 'AWS-USEAST-01', type: 'download', file: 'project_nodes.json', size: '132KB' },
];

export default function NetworkActivity() {
  const [events] = useState<NetworkEvent[]>(MOCK_EVENTS);

  return (
    <div className="flex-1 flex flex-col p-margin-mobile md:p-margin-desktop w-full h-full">
      <header className="mb-8">
        <h2 className="font-display-lg text-headline-lg-mobile md:text-display-lg text-on-surface mb-2">Network Activity</h2>
        <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
          Real-time peer-to-peer network transfer logs and system sync events.
        </p>
      </header>

      <section className="flex-1 flex flex-col bg-surface-container-low/50 border border-white/5 rounded-xl overflow-hidden glass-panel">
        <div className="flex justify-between items-center p-4 border-b border-white/10 bg-black/40">
          <div className="flex items-center gap-2 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">
            <span className="material-symbols-outlined text-sm">terminal</span>
            Live Log Stream
          </div>
          <button 
            className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer"
            onClick={() => {
              alert("Filters opened");
            }}
          >
            <span className="material-symbols-outlined text-sm">filter_list</span>
          </button>
        </div>

        <div className="p-4 flex-1 overflow-y-auto space-y-2 font-code-sm text-code-sm">
          {events.map((ev) => (
            <div key={ev.id} className="flex flex-col sm:flex-row sm:items-center gap-2 p-2 hover:bg-white/5 rounded transition-colors">
              <span className="text-on-surface-variant opacity-50 w-20 shrink-0">[{ev.timestamp}]</span>
              <span className={`w-24 shrink-0 font-bold ${
                ev.type === 'error' ? 'text-error' : 
                ev.type === 'sync' ? 'text-primary' : 
                'text-[#22d3ee]'
              }`}>
                [{ev.type.toUpperCase()}]
              </span>
              <span className="text-on-surface truncate">
                {ev.node}: {ev.message || `Transferred ${ev.file} (${ev.size})`}
              </span>
            </div>
          ))}
        </div>
      </section>

      <footer className="mt-8 pt-4 border-t border-white/5 flex flex-col md:flex-row justify-between items-center gap-4 text-outline font-code-sm text-code-sm">
        <p>© {new Date().getFullYear()} SHADOWDRIVE PROTOCOL. ALL RIGHTS RESERVED.</p>
        <div className="flex gap-6">
          <button className="hover:text-primary transition-colors cursor-pointer" onClick={() => alert("Whitepaper clicked")}>Whitepaper</button>
          <button className="hover:text-primary transition-colors cursor-pointer" onClick={() => alert("GitHub clicked")}>GitHub</button>
          <button className="hover:text-primary transition-colors cursor-pointer" onClick={() => alert("Status clicked")}>Status</button>
          <button className="hover:text-primary transition-colors cursor-pointer" onClick={() => alert("Privacy clicked")}>Privacy</button>
        </div>
      </footer>
    </div>
  );
}
