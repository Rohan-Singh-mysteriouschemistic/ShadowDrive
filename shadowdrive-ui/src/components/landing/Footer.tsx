import { ShadowDriveLogo } from '../shared/ShadowDriveLogo';

export default function Footer() {
  return (
    <footer className="border-t border-[rgba(0,255,136,0.08)] py-6 px-6 md:px-12 flex items-center justify-between text-[var(--ink-muted)] text-[13px]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
      <div className="flex items-center gap-2">
        <ShadowDriveLogo size={20} />
        <span className="font-bold tracking-[0.08em] uppercase text-[var(--ink)]" style={{ fontFamily: 'Space Grotesk, system-ui, sans-serif' }}>
          Shadow Drive
        </span>
      </div>
      <span>© 2026</span>
    </footer>
  );
}
