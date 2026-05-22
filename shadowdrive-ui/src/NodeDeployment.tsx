import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function NodeDeployment() {
  const navigate = useNavigate();
  const [platform, setPlatform] = useState<'windows' | 'mac' | 'linux'>('windows');
  const [copied, setCopied] = useState(false);

  const getPlatformCommand = () => {
    switch(platform) {
      case 'windows': return 'irm https://shadowdrive.net/install.ps1 | iex';
      case 'mac': return 'curl -sL https://shadowdrive.net/install.sh | bash';
      case 'linux': return 'wget -qO- https://shadowdrive.net/install.sh | bash';
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(getPlatformCommand());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      {/* Header Actions */}
      <header className="h-20 border-b border-white/5 flex items-center justify-between px-margin-desktop shrink-0 z-10 glass-panel border-l-0 border-r-0 border-t-0" style={{ backgroundColor: 'rgba(17, 17, 17, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}>
        {/* Breadcrumbs */}
        <div className="flex items-center space-x-2 font-code-sm text-code-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-sm text-primary">add_circle</span>
          <span className="text-on-surface font-bold tracking-wider uppercase">Deploy Node</span>
        </div>
        
        {/* Actions Row */}
        <div className="flex items-center space-x-gutter">
          <button 
            className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer flex items-center gap-2 px-3 py-1.5"
            onClick={() => navigate('/nodes')}
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span>
            <span className="font-label-md text-label-md">Back to Nodes</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-margin-desktop z-10 flex flex-col items-center justify-center">
        <div className="w-full max-w-2xl flex flex-col gap-8">
          
          <div className="text-center mb-4">
            <div className="w-20 h-20 bg-primary-container/20 rounded-full flex items-center justify-center mx-auto mb-6 border border-primary/20 shadow-[0_0_30px_rgba(16,185,129,0.15)]">
              <span className="material-symbols-outlined text-4xl text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>add_to_queue</span>
            </div>
            <h2 className="font-display-sm text-display-sm text-on-surface mb-2 font-bold tracking-tight">Deploy a New Node</h2>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-md mx-auto">
              Add a new device to your ShadowDrive network to increase storage capacity and redundancy.
            </p>
          </div>

          <div className="glass-panel border border-white/10 rounded-2xl p-8 relative overflow-hidden">
            {/* Background Glow */}
            <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary/5 rounded-full blur-3xl pointer-events-none"></div>
            
            <div className="relative z-10">
              <h3 className="font-headline-sm text-headline-sm text-on-surface mb-6 flex items-center gap-2">
                <span className="bg-white/10 w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold">1</span>
                Select Target Platform
              </h3>
              
              <div className="grid grid-cols-3 gap-4 mb-8">
                <button 
                  className={`flex flex-col items-center justify-center gap-3 p-4 rounded-xl border transition-all cursor-pointer ${platform === 'windows' ? 'bg-primary/10 border-primary text-primary shadow-[0_0_15px_rgba(16,185,129,0.2)]' : 'bg-surface-container hover:bg-white/5 border-white/5 text-on-surface-variant'}`}
                  onClick={() => setPlatform('windows')}
                >
                  <span className="material-symbols-outlined text-3xl">window</span>
                  <span className="font-label-md text-label-md">Windows</span>
                </button>
                <button 
                  className={`flex flex-col items-center justify-center gap-3 p-4 rounded-xl border transition-all cursor-pointer ${platform === 'mac' ? 'bg-primary/10 border-primary text-primary shadow-[0_0_15px_rgba(16,185,129,0.2)]' : 'bg-surface-container hover:bg-white/5 border-white/5 text-on-surface-variant'}`}
                  onClick={() => setPlatform('mac')}
                >
                  <span className="material-symbols-outlined text-3xl">laptop_mac</span>
                  <span className="font-label-md text-label-md">macOS</span>
                </button>
                <button 
                  className={`flex flex-col items-center justify-center gap-3 p-4 rounded-xl border transition-all cursor-pointer ${platform === 'linux' ? 'bg-primary/10 border-primary text-primary shadow-[0_0_15px_rgba(16,185,129,0.2)]' : 'bg-surface-container hover:bg-white/5 border-white/5 text-on-surface-variant'}`}
                  onClick={() => setPlatform('linux')}
                >
                  <span className="material-symbols-outlined text-3xl">terminal</span>
                  <span className="font-label-md text-label-md">Linux</span>
                </button>
              </div>

              <h3 className="font-headline-sm text-headline-sm text-on-surface mb-4 flex items-center gap-2">
                <span className="bg-white/10 w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold">2</span>
                Run Installation Command
              </h3>
              
              <p className="font-body-md text-body-md text-on-surface-variant mb-4">
                Open your terminal or command prompt and paste the following command to securely download and initialize the ShadowDrive daemon.
              </p>

              <div className="bg-black/50 border border-white/10 rounded-lg p-4 flex items-center justify-between group relative">
                <code className="font-code-md text-code-md text-primary font-mono select-all overflow-x-auto whitespace-nowrap scrollbar-hide pr-12">
                  {getPlatformCommand()}
                </code>
                <button 
                  className="absolute right-2 bg-surface-container-high hover:bg-white/20 p-2 rounded transition-colors text-on-surface cursor-pointer"
                  onClick={handleCopy}
                  title="Copy to clipboard"
                >
                  <span className="material-symbols-outlined text-sm">{copied ? 'check' : 'content_copy'}</span>
                </button>
              </div>
              {copied && <p className="text-primary text-xs mt-2 absolute">Copied to clipboard!</p>}
            </div>
          </div>

          <div className="glass-panel border border-white/5 rounded-xl p-6 bg-surface-container/30 text-center">
            <span className="material-symbols-outlined text-primary mb-2 text-3xl animate-pulse">radar</span>
            <h4 className="font-label-md text-label-md text-on-surface mb-1">Waiting for connection...</h4>
            <p className="font-code-sm text-code-sm text-on-surface-variant">The node will automatically appear in your dashboard once initialized.</p>
          </div>
          
        </div>
      </div>
    </div>
  );
}
