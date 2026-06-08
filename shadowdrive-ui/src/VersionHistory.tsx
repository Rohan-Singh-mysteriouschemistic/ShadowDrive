import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from './lib/api';

interface VersionRecord {
  id: string;
  version_number: number;
  hash: string;
  created_at: string;
  device_id: string;
  size_bytes: number;
  storage_path: string;
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
  const [loading, setLoading] = useState(true);
  
  // Get fileId and filename from query params
  const searchParams = new URLSearchParams(window.location.search);
  const fileId = searchParams.get('file');
  const filename = searchParams.get('name') || 'File History';

  useEffect(() => {
    fetchVersions();
  }, [fileId]);

  const fetchVersions = async () => {
    try {
      setLoading(true);
      const url = fileId ? `/sync/versions/recent?file_id=${fileId}` : '/sync/versions/recent';
      const data = await apiFetch(url);
      setVersions(data);
    } catch (err) {
      console.error('Failed to load version history:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = (e: React.MouseEvent, storagePath: string) => {
    e.stopPropagation();
    const url = `http://127.0.0.1:8000/sync/download?storage_path=${encodeURIComponent(storagePath)}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = storagePath.split('/').pop() || 'download';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center h-full w-full">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent items-center justify-center">
        <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold mb-2">No Version History</h3>
        <p className="font-code-sm text-on-surface-variant max-w-sm mb-6">
          {fileId ? 'This file has no previous versions yet.' : 'Your vault has no versions yet.'}
        </p>
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
          <span className="text-on-surface">{!fileId ? 'All Recent Versions' : filename}</span>
        </div>
        
        {/* Actions Row */}
        <div className="flex items-center space-x-gutter">
          <button 
            className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer" 
            title="Refresh"
            onClick={fetchVersions}
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
                <span className="material-symbols-outlined text-4xl text-primary">{!fileId ? 'history' : 'description'}</span>
              </div>
              <h2 className="font-headline-sm text-headline-sm text-on-surface mb-1 break-all">{!fileId ? 'Recent Changes' : filename}</h2>
              <p className="font-code-sm text-code-sm text-on-surface-variant mb-4">Total Versions: {versions.length}</p>
              
              <div className="w-full flex flex-col gap-2">
                <button 
                  className="w-full bg-surface-container-high hover:bg-white/10 text-on-surface font-label-md text-label-md py-2 rounded transition-colors border border-white/5 cursor-pointer"
                  onClick={(e) => handleDownload(e, versions[0].storage_path)}
                >
                  Download Latest
                </button>
              </div>
            </div>
          </div>

          {/* Right Column: Version Timeline */}
          <div className="flex-1 glass-panel rounded-xl overflow-hidden border border-white/10">
            {/* Table Header */}
            <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-white/10 font-code-sm text-code-sm text-on-surface-variant bg-surface-container-low/50 hidden md:grid">
              {!fileId && <div className="col-span-2">File</div>}
              <div className={!fileId ? "col-span-1" : "col-span-1"}>Ver</div>
              <div className={!fileId ? "col-span-3" : "col-span-4"}>Date / Time</div>
              <div className="col-span-2">Device</div>
              <div className="col-span-2">Size</div>
              <div className="col-span-2 text-right">Actions</div>
            </div>
            
            {/* Table Body */}
            <div className="flex flex-col">
              {versions.map((ver, index) => (
                <div key={ver.id} className="version-row group grid grid-cols-1 md:grid-cols-12 gap-4 px-6 py-4 border-b border-white/5 items-center hover:bg-white/5 transition-colors relative cursor-pointer">
                  
                  {!fileId && (
                    <div className="col-span-2 flex flex-col truncate pr-2">
                      <span className="font-code-sm text-code-sm text-on-surface truncate" title={(ver as any).file_name}>
                        {(ver as any).file_name || 'Unknown'}
                      </span>
                    </div>
                  )}

                  <div className={!fileId ? "col-span-1 flex items-center space-x-2" : "col-span-1 flex items-center space-x-2"}>
                    <span className={`font-code-md text-code-md font-bold ${index === 0 && fileId ? 'text-primary' : 'text-on-surface'}`}>
                      v{ver.version_number}
                    </span>
                  </div>
                  
                  <div className={!fileId ? "col-span-3 flex flex-col" : "col-span-4 flex flex-col"}>
                    <span className="font-code-sm text-code-sm text-on-surface">{new Date(ver.created_at).toLocaleString()}</span>
                    <span className="font-code-sm text-[10px] text-on-surface-variant font-mono truncate">{ver.hash}</span>
                  </div>
                  
                  <div className="col-span-2 flex items-center space-x-2 font-code-sm text-code-sm text-on-surface-variant">
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
                      onClick={(e) => handleDownload(e, ver.storage_path)}
                    >
                      <span className="material-symbols-outlined text-sm">download</span>
                    </button>
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
