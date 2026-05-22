import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getToken, apiFetch } from './lib/api';

interface DashboardLayoutProps {
  children: ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [storage, setStorage] = useState({ used: 0, total: 1000 });
  const [conflictsCount, setConflictsCount] = useState(0);

  useEffect(() => {
    if (!getToken()) {
      navigate('/auth');
      return;
    }
    
    async function fetchStats() {
      try {
        const data = await apiFetch('/sync/metadata');
        const totalUsedBytes = data.reduce((acc: number, f: any) => acc + (f.size_bytes || 0), 0);
        const conflicts = data.filter((f: any) => f.file_path && f.file_path.includes('(Conflicted copy)')).length;
        
        const usedGB = totalUsedBytes / (1024 * 1024 * 1024);
        setStorage({ used: usedGB, total: 1000 });
        setConflictsCount(conflicts);
      } catch (e) {
        console.error('Failed to fetch dashboard stats', e);
      }
    }
    fetchStats();
  }, [location.pathname, navigate]);

  const menuItems = [
    { path: '/vault', label: 'Vault', icon: 'folder' },
    { path: '/vault/history', label: 'Version History', icon: 'history' },
    { path: '/conflicts', label: 'Conflicts', icon: 'warning', badge: conflictsCount > 0 ? conflictsCount : undefined },
    { path: '/health', label: 'System Health', icon: 'monitoring' },
  ];

  const systemItems = [
    { path: '/nodes', label: 'Nodes & Settings', icon: 'settings_input_component' },
  ];

  const isPathActive = (path: string) => {
    // Exact match for vault, prefix match for others to keep active state on subpages (e.g. /nodes/deploy)
    if (path === '/vault') {
      return location.pathname === '/vault';
    }
    return location.pathname.startsWith(path);
  };

  const navItemClass = (path: string) => {
    const active = isPathActive(path);
    if (active) {
      return "flex items-center gap-3 px-4 py-3 rounded-lg bg-primary-container/10 border-l-2 border-primary text-primary font-bold transition-all font-body-md text-body-md";
    }
    return "flex items-center gap-3 px-4 py-3 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container transition-all font-body-md text-body-md cursor-pointer";
  };

  return (
    <div className="bg-surface-container-lowest text-on-surface min-h-screen flex flex-col md:flex-row overflow-x-hidden antialiased selection:bg-primary selection:text-on-primary">
      <style>{`
        .glass-panel {
          background-color: rgba(17, 17, 17, 0.8);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .pulse-dot {
          animation: pulse 2s infinite;
        }
        @keyframes pulse {
          0% { box-shadow: 0 0 0 0 rgba(78, 222, 163, 0.4); }
          70% { box-shadow: 0 0 0 6px rgba(78, 222, 163, 0); }
          100% { box-shadow: 0 0 0 0 rgba(78, 222, 163, 0); }
        }
      `}</style>

      {/* TopNavBar for Mobile */}
      <nav className="md:hidden flex justify-between items-center px-margin-mobile py-4 w-full border-b border-white/5 glass-panel sticky top-0 z-50">
        <div 
          className="font-headline-md text-headline-md font-bold tracking-tighter text-on-surface flex items-center gap-2 cursor-pointer"
          onClick={() => navigate('/vault')}
        >
          <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>dns</span>
          SHADOWDRIVE
        </div>
        <button 
          className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer"
          onClick={() => alert("Mobile menu toggle not yet implemented!")}
        >
          <span className="material-symbols-outlined">menu</span>
        </button>
      </nav>

      {/* Sidebar (Desktop) */}
      <aside className="hidden md:flex flex-col w-72 h-screen fixed left-0 top-0 glass-panel border-r border-white/5 p-6 z-40">
        <div 
          className="mb-12 flex items-center gap-3 cursor-pointer group"
          onClick={() => navigate('/vault')}
        >
          <div className="w-8 h-8 rounded bg-primary-container/20 flex items-center justify-center border border-primary/30 group-hover:bg-primary/20 transition-colors">
            <span className="material-symbols-outlined text-primary text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>dns</span>
          </div>
          <h1 className="font-headline-md text-headline-md font-bold tracking-tighter text-on-surface group-hover:text-primary transition-colors" style={{ textShadow: '0 0 15px rgba(16, 185, 129, 0.3)' }}>SHADOWDRIVE</h1>
        </div>

        <nav className="flex-1 flex flex-col gap-2">
          {menuItems.map((item) => (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={navItemClass(item.path)}
            >
              <span className="material-symbols-outlined text-[20px]" style={isPathActive(item.path) ? { fontVariationSettings: "'FILL' 1" } : {}}>{item.icon}</span>
              <span className="flex-1 text-left">{item.label}</span>
              {item.badge && (
                <span className="ml-auto bg-error-container text-on-error-container text-xs px-2 py-0.5 rounded-full font-code-sm text-code-sm border border-error/20 shadow-[0_0_8px_rgba(239,68,68,0.3)]">
                  {item.badge}
                </span>
              )}
            </button>
          ))}

          <div className="mt-4 mb-2 px-4 font-label-md text-label-md text-outline uppercase tracking-wider">System</div>
          
          {systemItems.map((item) => (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={navItemClass(item.path)}
            >
              <span className="material-symbols-outlined text-[20px]" style={isPathActive(item.path) ? { fontVariationSettings: "'FILL' 1" } : {}}>{item.icon}</span>
              <span className="flex-1 text-left">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="mt-auto pt-6 border-t border-white/5">
          <div className="flex justify-between items-end mb-2">
            <span className="font-label-md text-label-md text-on-surface-variant">Storage</span>
            <span className="font-code-sm text-code-sm text-primary">{storage.used < 0.01 ? '0' : storage.used.toFixed(2)} GB / {storage.total >= 1000 ? `${(storage.total/1000).toFixed(0)} TB` : `${storage.total} GB`}</span>
          </div>
          <div className="w-full h-1.5 bg-surface-container-high rounded-full overflow-hidden">
            <div className="h-full bg-primary rounded-full shadow-[0_0_8px_rgba(78,222,163,0.6)] animate-[pulse_2s_ease-in-out_infinite]" style={{ width: `${(storage.used / storage.total) * 100}%` }}></div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      {/* We add md:ml-72 to account for the fixed sidebar */}
      <div className="flex-1 flex flex-col min-h-screen md:ml-72 relative w-full overflow-x-hidden">
        {/* Abstract Tech Background Pattern (Subtle) */}
        <div className="fixed inset-0 pointer-events-none opacity-[0.03] z-0" style={{ backgroundImage: 'radial-gradient(#ffffff 1px, transparent 1px)', backgroundSize: '32px 32px' }}></div>
        
        {/* Render children inside a container that takes up the remaining space */}
        <div className="flex-1 flex flex-col relative z-10 w-full">
          {children}
        </div>
      </div>
    </div>
  );
}
