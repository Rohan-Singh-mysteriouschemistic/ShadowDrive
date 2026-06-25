import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiFetch, getDownloadUrl } from '../lib/api';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Button from '../components/Button';
import EmptyState from '../components/EmptyState';

interface VersionRecord {
  id: string;
  version_number: number;
  hash: string;
  created_at: string;
  device_id: string;
  size_bytes: number;
  storage_path: string;
  file_name?: string;
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
  const [searchParams] = useSearchParams();
  const fileId = searchParams.get('file');
  const filename = searchParams.get('name') || 'File History';

  const { data: versions = [], isLoading } = useQuery<VersionRecord[]>({
    queryKey: ['versions', fileId],
    queryFn: async () => {
      const url = fileId ? `/sync/versions/recent?file_id=${fileId}` : '/sync/versions/recent';
      return apiFetch(url);
    },
  });

  const handleDownload = (e: React.MouseEvent, storagePath: string) => {
    e.stopPropagation();
    const url = getDownloadUrl(storagePath);
    const a = document.createElement('a');
    a.href = url;
    a.download = storagePath.split('/').pop() || 'download';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center h-full w-full">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent items-center justify-center">
        <EmptyState
          icon="history"
          title="No Version History"
          description={fileId ? 'This file has no previous versions yet.' : 'Your vault has no versions yet.'}
          action={
            <Button variant="primary" onClick={() => navigate('/vault')}>
              Return to Vault
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      <PageHeader
        icon="home"
        title={!fileId ? 'All Recent Versions' : filename}
        actions={
          <Button variant="ghost" size="sm" icon="refresh" onClick={() => window.location.reload()} />
        }
      />

      <div className="flex-1 overflow-y-auto p-margin-desktop z-10 flex flex-col items-center">
        <div className="w-full max-w-container-max flex flex-col md:flex-row gap-gutter">
          <div className="w-full md:w-80 shrink-0 flex flex-col gap-gutter">
            <Card variant="glass" className="p-6 flex flex-col items-center text-center border border-white/10">
              <div className="w-20 h-20 bg-primary-container/20 rounded-2xl flex items-center justify-center mb-4 border border-primary/20">
                <span className="material-symbols-outlined text-4xl text-primary">
                  {!fileId ? 'history' : 'description'}
                </span>
              </div>
              <h2 className="font-headline-sm text-headline-sm text-on-surface mb-1 break-all">
                {!fileId ? 'Recent Changes' : filename}
              </h2>
              <p className="font-code-sm text-code-sm text-on-surface-variant mb-4">
                Total Versions: {versions.length}
              </p>
              <div className="w-full flex flex-col gap-2">
                <Button
                  variant="secondary"
                  className="w-full"
                  onClick={(e) => handleDownload(e, versions[0].storage_path)}
                >
                  Download Latest
                </Button>
              </div>
            </Card>
          </div>

          <Card className="flex-1 border border-white/10 overflow-hidden">
            <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-white/10 font-code-sm text-code-sm text-on-surface-variant bg-surface-container-low/50 hidden md:grid">
              {!fileId && <div className="col-span-2">File</div>}
              <div className={!fileId ? "col-span-1" : "col-span-1"}>Ver</div>
              <div className={!fileId ? "col-span-3" : "col-span-4"}>Date / Time</div>
              <div className="col-span-2">Device</div>
              <div className="col-span-2">Size</div>
              <div className="col-span-2 text-right">Actions</div>
            </div>

            <div className="flex flex-col">
              {versions.map((ver, index) => (
                <div key={ver.id} className="version-row group grid grid-cols-1 md:grid-cols-12 gap-4 px-6 py-4 border-b border-white/5 items-center hover:bg-white/5 transition-colors relative cursor-pointer">
                  {!fileId && (
                    <div className="col-span-2 flex flex-col truncate pr-2">
                      <span className="font-code-sm text-code-sm text-on-surface truncate" title={ver.file_name}>
                        {ver.file_name || 'Unknown'}
                      </span>
                    </div>
                  )}

                  <div className={!fileId ? "col-span-1 flex items-center space-x-2" : "col-span-1 flex items-center space-x-2"}>
                    <span className={`font-code-md text-code-md font-bold ${index === 0 && fileId ? 'text-primary' : 'text-on-surface'}`}>
                      v{ver.version_number}
                    </span>
                  </div>

                  <div className={!fileId ? "col-span-3 flex flex-col" : "col-span-4 flex flex-col"}>
                    <span className="font-code-sm text-code-sm text-on-surface">
                      {new Date(ver.created_at).toLocaleString()}
                    </span>
                    <span className="font-code-sm text-[10px] text-on-surface-variant font-mono truncate">
                      {ver.hash}
                    </span>
                  </div>

                  <div className="col-span-2 flex items-center space-x-2 font-code-sm text-code-sm text-on-surface-variant">
                    <span className="material-symbols-outlined text-sm">devices</span>
                    <span className="truncate">{ver.device_id}</span>
                  </div>

                  <div className="col-span-2 font-code-sm text-code-sm text-on-surface-variant">
                    {formatBytes(ver.size_bytes)}
                  </div>

                  <div className="col-span-2 flex justify-end items-center space-x-2 opacity-100 md:opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="sm"
                      icon="download"
                      onClick={(e) => handleDownload(e, ver.storage_path)}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
