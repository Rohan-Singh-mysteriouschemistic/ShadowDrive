import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface VersionRecord {
  id: string;
  version_number: number;
  hash: string;
  created_at: string;
  device_id: string;
  size_bytes: number;
}


function formatBytes(bytes: number, decimals = 2) {
  if (!+bytes) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export default function VersionHistory() {
  const navigate = useNavigate();
  const [versions, setVersions] = useState<VersionRecord[]>([]);

  if (versions.length === 0) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent items-center justify-center">
        <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold mb-2">No Version History</h3>
        <p className="font-code-sm text-on-surface-variant max-w-sm mb-6">Select a file from the vault to view its history.</p>
        <button 
          className="bg-primary text-surface-container-lowest font-label-md text-label-md py-2 px-6 rounded font-bold hover:bg-primary-container transition-colors shadow-[0_0_15px_rgba(16,185,129,0.3)] cursor-pointer"
          onClick={() => navigate('/vault')}
        >
          Return to Vault
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      {/* Header Actions */}
      <header className="h-20 border-b border-white/5 flex items-center justify-between px-margin-desktop shrink-0 z-10 glass-panel border-l-0 border-r-0 border-t-0" style={{ backgroundColor: 'rgba(17, 17, 17, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}>
        {/* Breadcrumbs */}
        <div className="flex items-center space-x-2 font-code-sm text-code-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-sm">home</span>
          <span>/</span>
          <span className="hover:text-primary cursor-pointer transition-colors" onClick={() => navigate('/vault')}>root</span>
          <span>/</span>
          <span className="text-on-surface">system_architecture.pdf</span>
        </div>
        
        {/* Actions Row */}
        <div className="flex items-center space-x-gutter">
          <button 
            className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer" 
            title="Refresh"
            onClick={() => alert("Refreshing history...")}
          >
            <span className="material-symbols-outlined text-sm">refresh</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-margin-desktop z-10 flex flex-col items-center">
        <div className="w-full max-w-container-max flex flex-col md:flex-row gap-gutter">
          
          {/* Left Column: File Info Card */}
          <div className="w-full md:w-80 shrink-0 flex flex-col gap-gutter">
            <div className="glass-panel p-6 rounded-xl border border-white/10 flex flex-col items-center text-center">
              <div className="w-20 h-20 bg-primary-container/20 rounded-2xl flex items-center justify-center mb-4 border border-primary/20">
                <span className="material-symbols-outlined text-4xl text-primary">description</span>
              </div>
              <h2 className="font-headline-sm text-headline-sm text-on-surface mb-1 break-all">system_architecture.pdf</h2>
              <p className="font-code-sm text-code-sm text-on-surface-variant mb-4">Total Versions: {versions.length}</p>
              
              <div className="w-full flex flex-col gap-2">
                <button 
                  className="w-full bg-surface-container-high hover:bg-white/10 text-on-surface font-label-md text-label-md py-2 rounded transition-colors border border-white/5 cursor-pointer"
                  onClick={() => alert("Downloading current version...")}
                >
                  Download Current
                </button>
                <button 
                  className="w-full bg-error-container/20 hover:bg-error-container/40 text-error font-label-md text-label-md py-2 rounded transition-colors border border-error/20 cursor-pointer"
                  onClick={() => alert("Deleting file...")}
                >
                  Delete File
                </button>
              </div>
            </div>
          </div>

          {/* Right Column: Version Timeline */}
          <div className="flex-1 glass-panel rounded-xl overflow-hidden border border-white/10">
            {/* Table Header */}
            <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-white/10 font-code-sm text-code-sm text-on-surface-variant bg-surface-container-low/50 hidden md:grid">
              <div className="col-span-1">Ver</div>
              <div className="col-span-4">Date / Time</div>
              <div className="col-span-3">Device</div>
              <div className="col-span-2">Size</div>
              <div className="col-span-2 text-right">Actions</div>
            </div>
            
            {/* Table Body */}
            <div className="flex flex-col">
              {versions.map((ver, index) => (
                <div key={ver.id} className="version-row group grid grid-cols-1 md:grid-cols-12 gap-4 px-6 py-4 border-b border-white/5 items-center hover:bg-white/5 transition-colors relative cursor-pointer" onClick={() => alert(`View details for version v${ver.version_number}`)}>
                  {/* Current Version Indicator (for the first row) */}
                  {index === 0 && (
                    <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary shadow-[0_0_8px_rgba(78,222,163,0.6)]"></div>
                  )}

                  <div className="col-span-1 flex items-center space-x-2">
                    <span className={`font-code-md text-code-md font-bold ${index === 0 ? 'text-primary' : 'text-on-surface'}`}>
                      v{ver.version_number}
                    </span>
                    {index === 0 && <span className="md:hidden ml-2 text-xs bg-primary/20 text-primary px-2 py-0.5 rounded">Current</span>}
                  </div>
                  
                  <div className="col-span-4 flex flex-col">
                    <span className="font-code-sm text-code-sm text-on-surface">{ver.created_at}</span>
                    <span className="font-code-sm text-[10px] text-on-surface-variant font-mono truncate">{ver.hash}</span>
                  </div>
                  
                  <div className="col-span-3 flex items-center space-x-2 font-code-sm text-code-sm text-on-surface-variant">
                    <span className="material-symbols-outlined text-sm">devices</span>
                    <span className="truncate">{ver.device_id}</span>
                  </div>
                  
                  <div className="col-span-2 font-code-sm text-code-sm text-on-surface-variant">
                    {formatBytes(ver.size_bytes)}
                  </div>
                  
                  <div className="col-span-2 flex justify-end items-center space-x-2 opacity-100 md:opacity-0 group-hover:opacity-100 transition-opacity">
                    <button 
                      className="p-2 text-on-surface-variant hover:text-primary hover:bg-white/10 rounded transition-colors cursor-pointer" 
                      title="Download this version"
                      onClick={(e) => {
                        e.stopPropagation();
                        alert(`Downloading version v${ver.version_number}`);
                      }}
                    >
                      <span className="material-symbols-outlined text-sm">download</span>
                    </button>
                    {index !== 0 && (
                      <button 
                        className="p-2 text-on-surface-variant hover:text-primary hover:bg-white/10 rounded transition-colors cursor-pointer" 
                        title="Restore this version"
                        onClick={(e) => {
                          e.stopPropagation();
                          alert(`Restoring version v${ver.version_number}`);
                        }}
                      >
                        <span className="material-symbols-outlined text-sm">restore</span>
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}
