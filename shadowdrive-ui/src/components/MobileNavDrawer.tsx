import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Badge from './Badge';
import { ShadowDriveLogo } from './shared/ShadowDriveLogo';

interface NavItem {
  path: string;
  label: string;
  icon: string;
  badge?: number;
}

interface MobileNavDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  menuItems: NavItem[];
  systemItems: NavItem[];
  currentPath: string;
  onNavigate?: () => void;
  storage?: { used: number; total: number };
  onLogout?: () => void;
}

export default function MobileNavDrawer({
  isOpen,
  onClose,
  menuItems,
  systemItems,
  currentPath,
  onNavigate,
  storage,
  onLogout,
}: MobileNavDrawerProps) {
  const navigate = useNavigate();

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const isPathActive = (path: string) => {
    if (path === '/vault') {
      return currentPath === '/vault';
    }
    return currentPath.startsWith(path);
  };

  const navItemClass = (path: string) => {
    const active = isPathActive(path);
    if (active) {
      return "flex items-center gap-3 px-4 py-3 rounded-lg bg-primary-container/10 border-l-2 border-primary text-primary font-bold transition-all font-body-md text-body-md";
    }
    return "flex items-center gap-3 px-4 py-3 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container transition-all font-body-md text-body-md cursor-pointer";
  };

  const handleNavigation = (path: string) => {
    navigate(path);
    onNavigate?.();
    onClose();
  };

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <nav
        className={`fixed left-0 top-0 h-screen w-72 glass-panel-darker border-r border-white/5 p-6 z-40 md:hidden transform transition-transform duration-300 ease-out overflow-y-auto ${
          isOpen ? 'translate-x-0 drawer-enter' : '-translate-x-full drawer-exit'
        }`}
      >
        <div className="flex items-center justify-between mb-12">
          <div className="flex items-center gap-3 cursor-pointer group" onClick={() => handleNavigation('/vault')}>
            <ShadowDriveLogo size={32} />
            <h1 className="font-headline-md text-headline-md font-bold tracking-tighter text-on-surface group-hover:text-primary transition-colors" style={{ textShadow: '0 0 15px rgba(0, 255, 136, 0.3)' }}>
              SHADOWDRIVE
            </h1>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-on-surface-variant hover:text-primary transition-colors"
            aria-label="Close menu"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        <nav className="flex-1 flex flex-col gap-2">
          {menuItems.map((item) => (
            <button
              key={item.path}
              onClick={() => handleNavigation(item.path)}
              className={navItemClass(item.path)}
            >
              <span
                className="material-symbols-outlined text-[20px]"
                style={isPathActive(item.path) ? { fontVariationSettings: "'FILL' 1" } : {}}
              >
                {item.icon}
              </span>
              <span className="flex-1 text-left">{item.label}</span>
              {item.badge && <Badge count={item.badge} variant="error" />}
            </button>
          ))}

          <div className="mt-4 mb-2 px-4 font-label-md text-label-md text-outline uppercase tracking-wider">
            System
          </div>

          {systemItems.map((item) => (
            <button
              key={item.path}
              onClick={() => handleNavigation(item.path)}
              className={navItemClass(item.path)}
            >
              <span
                className="material-symbols-outlined text-[20px]"
                style={isPathActive(item.path) ? { fontVariationSettings: "'FILL' 1" } : {}}
              >
                {item.icon}
              </span>
              <span className="flex-1 text-left">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="mt-auto pt-6 border-t border-white/5">
          {storage && (
            <>
              <div className="flex justify-between items-end mb-2">
                <span className="font-label-md text-label-md text-on-surface-variant">Storage</span>
                <span className="font-code-sm text-code-sm text-primary">
                  {storage.used < 0.01 ? '0' : storage.used.toFixed(2)} GB / {storage.total >= 1000 ? `${(storage.total / 1000).toFixed(0)} TB` : `${storage.total} GB`}
                </span>
              </div>
              <div className="w-full h-1.5 bg-surface-container-high rounded-full overflow-hidden mb-6">
                <div
                  className="h-full bg-primary rounded-full shadow-[0_0_8px_rgba(0,255,136,0.6)] pulse-dot"
                  style={{ width: `${(storage.used / storage.total) * 100}%` }}
                />
              </div>
            </>
          )}

          {onLogout && (
            <button
              onClick={() => {
                onClose();
                onLogout();
              }}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-error hover:bg-error/10 transition-all font-body-md text-body-md cursor-pointer border border-error/20"
            >
              <span className="material-symbols-outlined text-[20px]">logout</span>
              <span>Sign Out</span>
            </button>
          )}
        </div>
      </nav>
    </>
  );
}
