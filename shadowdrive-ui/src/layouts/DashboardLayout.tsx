import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getToken, apiFetch, setToken, getOrFetchToken, CLIENT_API_URL } from '../lib/api';
import Badge from '../components/Badge';
import Card from '../components/Card';

interface DashboardLayoutProps {
  children: ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [storage, setStorage] = useState({ used: 0, total: 1000 });
  const [conflictsCount, setConflictsCount] = useState(0);
  const [showConfirmLogout, setShowConfirmLogout] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(!getToken());

  useEffect(() => {
    async function verifyAuthAndFetchStats() {
      if (!getToken()) {
        const token = await getOrFetchToken();
        if (!token) {
          navigate('/auth');
          return;
        }
        setCheckingAuth(false);
      }

      try {
        const [metadata, authData] = await Promise.all([
          apiFetch('/sync/metadata'),
          apiFetch('/auth/me')
        ]);

        const totalUsedBytes = metadata.reduce((acc: number, f: any) => acc + (f.size_bytes || 0), 0);
        const conflicts = metadata.filter((f: any) => f.file_path && f.file_path.includes('(Conflicted copy)')).length;

        const usedGB = totalUsedBytes / (1024 * 1024 * 1024);
        const totalGB = authData.storage_quota ? (authData.storage_quota / (1024 * 1024 * 1024)) : 5;

        setStorage({ used: usedGB, total: totalGB });
        setConflictsCount(conflicts);
      } catch (e) {
        console.error('Failed to fetch dashboard stats', e);
      }
    }
    verifyAuthAndFetchStats();
  }, [location.pathname, navigate]);

  const menuItems = [
    { path: '/vault', label: 'Vault', icon: 'folder' },
    { path: '/vault/history', label: 'Version History', icon: 'history' },
    { path: '/transfers', label: 'Transfers', icon: 'swap_vert' },
    { path: '/conflicts', label: 'Conflicts', icon: 'warning', badge: conflictsCount > 0 ? conflictsCount : undefined },
    { path: '/health', label: 'System Health', icon: 'monitoring' },
  ];

  const systemItems = [
    { path: '/nodes', label: 'Nodes & Settings', icon: 'settings_input_component' },
  ];

  const isPathActive = (path: string) => {
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

  if (checkingAuth) {
    return (
      <div className="w-full h-screen flex items-center justify-center bg-background">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="bg-surface-container-lowest text-on-surface min-h-screen flex flex-col md:flex-row overflow-x-hidden antialiased selection:bg-primary selection:text-on-primary">
      <style>{`
        .pulse-dot {
          animation: pulse 2s infinite;
        }
        @keyframes pulse {
          0% { box-shadow: 0 0 0 0 rgba(78, 222, 163, 0.4); }
          70% { box-shadow: 0 0 0 6px rgba(78, 222, 163, 0); }
          100% { box-shadow: 0 0 0 0 rgba(78, 222, 163, 0); }
        }
      `}</style>

      <nav className="md:hidden flex justify-between items-center px-margin-mobile py-4 w-full border-b border-white/5 glass-panel-darker sticky top-0 z-50">
        <div
          className="font-headline-md text-headline-md font-bold tracking-tighter text-on-surface flex items-center gap-2.5 cursor-pointer"
          onClick={() => navigate('/vault')}
        >
          <img src="/logo.png" alt="ShadowDrive Logo" className="w-6 h-6 object-contain" />
          SHADOWDRIVE
        </div>
        <button
          className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer"
          onClick={() => alert("Mobile menu toggle not yet implemented!")}
        >
          <span className="material-symbols-outlined">menu</span>
        </button>
      </nav>

      <aside className="hidden md:flex flex-col w-72 h-screen fixed left-0 top-0 glass-panel-darker border-r border-white/5 p-6 z-40">
        <div
          className="mb-12 flex items-center gap-3 cursor-pointer group"
          onClick={() => navigate('/vault')}
        >
          <img src="/logo.png" alt="ShadowDrive Logo" className="w-8 h-8 object-contain transition-transform group-hover:scale-105 duration-200" />
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
              {item.badge && <Badge count={item.badge} variant="error" />}
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
            <span className="font-code-sm text-code-sm text-primary">
              {storage.used < 0.01 ? '0' : storage.used.toFixed(2)} GB / {storage.total >= 1000 ? `${(storage.total / 1000).toFixed(0)} TB` : `${storage.total} GB`}
            </span>
          </div>
          <div className="w-full h-1.5 bg-surface-container-high rounded-full overflow-hidden mb-6">
            <div className="h-full bg-primary rounded-full shadow-[0_0_8px_rgba(78,222,163,0.6)] pulse-dot" style={{ width: `${(storage.used / storage.total) * 100}%` }} />
          </div>

          <button
            onClick={() => {
              setShowConfirmLogout(true);
            }}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-error hover:bg-error/10 transition-all font-body-md text-body-md cursor-pointer border border-error/20"
          >
            <span className="material-symbols-outlined text-[20px]">logout</span>
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-h-screen md:ml-72 relative w-full overflow-x-hidden">
        <div className="fixed inset-0 pointer-events-none opacity-[0.03] z-0" style={{ backgroundImage: 'radial-gradient(#ffffff 1px, transparent 1px)', backgroundSize: '32px 32px' }} />
        <div className="flex-1 flex flex-col relative z-10 w-full">
          {children}
        </div>
      </div>

      {showConfirmLogout && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <Card variant="glass" className="w-full max-w-sm p-6 border border-white/10 text-center space-y-6">
            <div className="mx-auto w-12 h-12 rounded-full bg-error/10 border border-error/20 flex items-center justify-center text-error">
              <span className="material-symbols-outlined text-2xl">logout</span>
            </div>
            <div className="space-y-2">
              <h3 className="font-headline-sm text-headline-sm text-white font-bold">
                Sign Out Session
              </h3>
              <p className="text-on-surface-variant font-body-md text-sm leading-relaxed">
                Are you sure you want to sign out? This will stop background client sync and watcher services.
              </p>
            </div>
            <div className="flex gap-4">
              <button
                onClick={() => setShowConfirmLogout(false)}
                className="flex-1 py-3 px-4 rounded-lg bg-white/5 hover:bg-white/10 text-white font-label-md text-label-md transition-all cursor-pointer border border-white/5"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  setShowConfirmLogout(false);
                  try {
                    await fetch(`${CLIENT_API_URL}/api/auth/logout`, { method: 'POST' });
                  } catch (e) {
                    console.error('Failed to notify local client of logout:', e);
                  }
                  setToken(null);
                  navigate('/auth');
                }}
                className="flex-1 py-3 px-4 rounded-lg bg-error hover:opacity-90 text-on-error-container font-label-md text-label-md transition-all cursor-pointer font-bold"
              >
                Sign Out
              </button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
