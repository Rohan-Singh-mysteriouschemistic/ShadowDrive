import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Button from '../components/Button';

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

  const platforms = [
    { key: 'windows' as const, icon: 'window', label: 'Windows' },
    { key: 'mac' as const, icon: 'laptop_mac', label: 'macOS' },
    { key: 'linux' as const, icon: 'terminal', label: 'Linux' },
  ];

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      <PageHeader
        title="Deploy Node"
        icon="add_circle"
        actions={
          <Button variant="ghost" icon="arrow_back" onClick={() => navigate('/nodes')}>
            Back to Nodes
          </Button>
        }
      />

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

          <Card variant="glass" className="p-8 relative">
            <div className="relative z-10">
              <h3 className="font-headline-sm text-headline-sm text-on-surface mb-6 flex items-center gap-2">
                <span className="bg-white/10 w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold">1</span>
                Select Target Platform
              </h3>

              <div className="grid grid-cols-3 gap-4 mb-8">
                {platforms.map((p) => (
                  <button
                    key={p.key}
                    className={`flex flex-col items-center justify-center gap-3 p-4 rounded-xl border transition-all cursor-pointer ${platform === p.key ? 'bg-primary/10 border-primary text-primary shadow-[0_0_15px_rgba(16,185,129,0.2)]' : 'bg-surface-container hover:bg-white/5 border-white/5 text-on-surface-variant'}`}
                    onClick={() => setPlatform(p.key)}
                  >
                    <span className="material-symbols-outlined text-3xl">{p.icon}</span>
                    <span className="font-label-md text-label-md">{p.label}</span>
                  </button>
                ))}
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
              {copied && <p className="text-primary text-xs mt-2">Copied to clipboard!</p>}
            </div>
          </Card>

          <Card variant="glass" className="p-6 text-center">
            <span className="material-symbols-outlined text-primary mb-2 text-3xl animate-pulse">radar</span>
            <h4 className="font-label-md text-label-md text-on-surface mb-1">Waiting for connection...</h4>
            <p className="font-code-sm text-code-sm text-on-surface-variant">The node will automatically appear in your dashboard once initialized.</p>
          </Card>

        </div>
      </div>
    </div>
  );
}
