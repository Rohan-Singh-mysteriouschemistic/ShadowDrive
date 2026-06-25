import { useState, useRef, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFiles, useUploadFile, useDeleteFile } from '../hooks/useFiles';
import { useEventInvalidation } from '../hooks/useEvents';
import { getDownloadUrl, apiFetch } from '../lib/api';
import { useQuery } from '@tanstack/react-query';
import Button from '../components/Button';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Modal from '../components/Modal';
import EmptyState from '../components/EmptyState';

function formatBytes(bytes: number, decimals = 2) {
  if (!+bytes) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export default function FileExplorer() {
  const navigate = useNavigate();
  const { data: files = [], isLoading, error } = useFiles();
  const uploadMutation = useUploadFile();
  const deleteMutation = useDeleteFile();
  useEventInvalidation();

  const [fileToDelete, setFileToDelete] = useState<{id: string | number, name: string} | null>(null);
  const [editingFile, setEditingFile] = useState<{id: string | number, name: string, storage_path?: string, content: string} | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [transfers, setTransfers] = useState<any[]>([]);

  useEffect(() => {
    const fetchTransfers = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8001/api/transfers');
        if (res.ok) {
          const data = await res.json();
          setTransfers(data.transfers || []);
        }
      } catch (err) {
        console.error('Failed to fetch transfers for file explorer', err);
      }
    };
    fetchTransfers();
    const interval = setInterval(fetchTransfers, 1000);
    return () => clearInterval(interval);
  }, []);

  const combinedFiles = useMemo(() => {
    const activeUploads = transfers
      .filter((t: any) => t.direction === 'upload' && (t.status === 'active' || t.status === 'queued'))
      .map((t: any, idx: number) => {
        const fileExists = files.some((f: any) => f.file_path === t.filename);
        if (fileExists) return null;
        
        return {
          id: `transfer-${t.id || idx}`,
          file_path: t.filename,
          size_bytes: parseInt(t.size.replace(/[^0-9.]/g, '')) * 1024 || 0,
          updated_at: new Date().toISOString(),
          upload_status: 'uploading',
          is_conflict_copy: false,
        };
      })
      .filter(Boolean) as any[];

    const mappedFiles = files.map((f: any) => {
      const activeT = transfers.find((t: any) => t.filename === f.file_path && t.direction === 'upload' && (t.status === 'active' || t.status === 'queued'));
      if (activeT) {
        return { ...f, upload_status: 'uploading' };
      }
      return f;
    });

    return [...activeUploads, ...mappedFiles];
  }, [files, transfers]);

  const { data: userData } = useQuery<{ id: number; username: string; email: string; storage_quota: number }>({
    queryKey: ['user-me'],
    queryFn: () => apiFetch('/auth/me'),
    staleTime: 60_000,
  });

  const storageUsed = useMemo(() => {
    return files.reduce((acc: number, f: any) => acc + (f.size_bytes || 0), 0);
  }, [files]);

  const storageQuota = userData?.storage_quota ?? 0;
  const usagePercent = storageQuota > 0 ? Math.min(100, (storageUsed / storageQuota) * 100) : 0;

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await uploadMutation.mutateAsync({ file, remotePath: file.name });
    } catch (err) {
      console.error('Upload failed', err);
      alert('Upload failed. Check console for details.');
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const confirmDelete = async (id: string | number) => {
    try {
      await deleteMutation.mutateAsync(id.toString());
      setFileToDelete(null);
    } catch (err) {
      console.error('Delete failed', err);
      alert('Delete failed');
    }
  };

  const isTextFile = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    return ['txt', 'md', 'json', 'js', 'ts', 'jsx', 'tsx', 'csv', 'html', 'css'].includes(ext || '');
  };

  const handleRowClick = async (e: React.MouseEvent, file: { id: string | number; file_path: string; storage_path?: string; is_conflict_copy?: boolean }) => {
    if (file.is_conflict_copy || file.file_path.includes('(Conflicted copy)')) {
      navigate('/conflicts');
      return;
    }
    if (isTextFile(file.file_path)) {
      try {
        const res = await fetch(`http://127.0.0.1:8001/api/download?file_path=${encodeURIComponent(file.file_path)}`);
        if (res.ok) {
          const text = await res.text();
          setEditingFile({ id: file.id, name: file.file_path, storage_path: file.storage_path, content: text });
        } else {
          handleDownload(e, file.storage_path);
        }
      } catch (err) {
        handleDownload(e, file.storage_path);
      }
    } else {
      handleDownload(e, file.storage_path);
    }
  };

  const handleDownload = (e: React.MouseEvent, storagePath?: string) => {
    e.stopPropagation();
    if (!storagePath) {
      alert('Download failed: No storage path available on server.');
      return;
    }
    const url = getDownloadUrl(storagePath);
    const a = document.createElement('a');
    a.href = url;
    a.download = storagePath.split('/').pop() || 'download';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const getStatusDot = (status: string, isConflict?: boolean) => {
    if (isConflict) return <span className="material-symbols-outlined text-sm text-error" title="Conflict">warning</span>;
    switch (status) {
      case 'complete': return <span className="material-symbols-outlined text-sm text-primary" title="Synced">check_circle</span>;
      case 'uploading':
      case 'processing':
      case 'pending': return <span className="material-symbols-outlined text-sm text-yellow-500 animate-spin" title={status}>progress_activity</span>;
      case 'failed': return <span className="material-symbols-outlined text-sm text-error" title="Failed">error</span>;
      default: return null;
    }
  };

  const getFileIcon = (filename: string) => {
    if (filename.endsWith('.pdf')) return 'description';
    if (filename.endsWith('.sqlite')) return 'database';
    if (filename.endsWith('.pem')) return 'key';
    if (filename.endsWith('.json')) return 'code';
    if (filename.endsWith('.bin')) return 'lock';
    return 'insert_drive_file';
  };

  const filteredFiles = searchQuery
    ? combinedFiles.filter(f => f.file_path.toLowerCase().includes(searchQuery.toLowerCase()))
    : combinedFiles;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      <PageHeader
        icon="home"
        title="root"
        iconColor="text-on-surface-variant"
        actions={
          <>
            <div className="relative group">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant group-focus-within:text-primary transition-colors text-sm">search</span>
              <input
                className="bg-surface-container-low border border-white/10 rounded-DEFAULT py-2 pl-9 pr-4 font-code-sm text-code-sm text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/50 transition-all w-64 placeholder:text-on-surface-variant"
                placeholder="Search Vault..."
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            {storageQuota > 0 && (
              <div className="flex items-center gap-3 px-3 py-1.5 bg-surface-container-low border border-white/10 rounded-DEFAULT" title={`${formatBytes(storageUsed)} / ${formatBytes(storageQuota)}`}>
                <span className="material-symbols-outlined text-on-surface-variant text-sm">cloud</span>
                <div className="flex flex-col gap-0.5 min-w-[120px]">
                  <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${usagePercent > 90 ? 'bg-error' : usagePercent > 70 ? 'bg-yellow-500' : 'bg-primary'}`}
                      style={{ width: `${usagePercent}%` }}
                    />
                  </div>
                  <span className="font-code-sm text-[10px] text-on-surface-variant leading-none">
                    {formatBytes(storageUsed)} / {formatBytes(storageQuota)}
                  </span>
                </div>
              </div>
            )}
            <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" />
            <Button variant="primary" size="md" icon="upload" onClick={handleUploadClick}>
              Upload File
            </Button>
          </>
        }
      />

      <div className="flex-1 overflow-y-auto p-margin-desktop z-10">
        <div className="w-full max-w-container-max mx-auto">
          {uploadMutation.isPending && (
            <div className="flex items-center gap-2 p-4 mb-4 bg-primary/10 border border-primary/20 rounded text-primary font-code-sm">
              <span className="material-symbols-outlined animate-spin text-sm">progress_activity</span>
              <span>Adding file to local watch folder and syncing...</span>
            </div>
          )}
          <Card className="w-full">
          <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-white/10 font-code-sm text-code-sm text-on-surface-variant bg-surface-container-low/50">
            <div className="col-span-5">Name</div>
            <div className="col-span-2">Size</div>
            <div className="col-span-3">Last Modified</div>
            <div className="col-span-2 text-right">Status</div>
          </div>

          <div className="flex flex-col relative min-h-[200px]">
            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-surface-container-low/50 z-20">
                <div className="flex flex-col items-center">
                  <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  <span className="mt-2 font-code-sm text-on-surface-variant">Loading vault...</span>
                </div>
              </div>
            )}
            {!isLoading && error && (
              <div className="p-4 text-center text-red-500 font-code-sm border-b border-white/5 bg-red-500/5">
                {error instanceof Error ? error.message : 'Failed to load files'}
              </div>
            )}
            {filteredFiles.length === 0 && !isLoading && !error && (
              <EmptyState
                icon="folder_open"
                title="Vault Empty"
                description="You don't have any files in your ShadowDrive yet. Upload a file to get started."
                action={
                  <Button variant="primary" icon="upload" onClick={handleUploadClick}>Upload File</Button>
                }
              />
            )}
            {filteredFiles.map(file => (
              <div key={file.id} className="file-row group grid grid-cols-12 gap-4 px-6 py-4 border-b border-white/5 items-center hover:bg-white/5 transition-colors relative cursor-pointer" onClick={(e) => handleRowClick(e, file)}>
                <div className="col-span-5 flex items-center space-x-3 font-code-sm text-code-sm text-on-surface">
                  <span className="material-symbols-outlined text-on-surface-variant group-hover:text-primary transition-colors">{getFileIcon(file.file_path)}</span>
                  <span className="truncate">{file.file_path}</span>
                </div>
                <div className="col-span-2 font-code-sm text-code-sm text-on-surface-variant">{formatBytes(file.size_bytes)}</div>
                <div className="col-span-3 font-code-sm text-code-sm text-on-surface-variant">
                  {new Date(file.updated_at).toLocaleString()}
                </div>
                <div className="col-span-2 flex items-center justify-end space-x-4">
                  {getStatusDot(file.upload_status, file.is_conflict_copy)}
                  <div className="opacity-0 group-hover:opacity-100 flex items-center gap-2 transition-all">
                    <Button
                      variant="ghost"
                      size="sm"
                      icon="history"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/vault/history?file=${file.id}&name=${encodeURIComponent(file.file_path)}`);
                      }}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      icon="download"
                      onClick={(e) => handleDownload(e, file.storage_path)}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      icon="delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        setFileToDelete({ id: file.id, name: file.file_path });
                      }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>

      <Modal
        open={!!fileToDelete}
        onClose={() => setFileToDelete(null)}
        title="Delete File"
        footer={
          <>
            <Button variant="ghost" onClick={() => setFileToDelete(null)}>Cancel</Button>
            <Button variant="danger" onClick={() => fileToDelete && confirmDelete(fileToDelete.id)}>
              Delete
            </Button>
          </>
        }
      >
        <p className="text-on-surface-variant font-code-sm">
          Are you sure you want to delete <span className="text-primary">{fileToDelete?.name}</span>? This action cannot be undone.
        </p>
      </Modal>

      <Modal
        open={!!editingFile}
        onClose={() => setEditingFile(null)}
        title={editingFile?.name || 'Edit File'}
        maxWidth="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditingFile(null)} disabled={isSaving}>Cancel</Button>
            <Button
              variant="primary"
              loading={isSaving}
              onClick={async () => {
                if (!editingFile) return;
                setIsSaving(true);
                setSaveError(null);
                try {
                  const blob = new Blob([editingFile.content], { type: 'text/plain' });
                  const fileObj = new File([blob], editingFile.name, { type: 'text/plain' });
                  await uploadMutation.mutateAsync({ file: fileObj, remotePath: editingFile.name });
                  setEditingFile(null);
                } catch (err) {
                  console.error("Failed to save file", err);
                  setSaveError("Failed to save changes. Network error.");
                } finally {
                  setIsSaving(false);
                }
              }}
            >
              {isSaving ? 'Saving...' : 'Save Changes'}
            </Button>
          </>
        }
      >
        {editingFile && (
          <>
            <textarea
              className="flex-1 w-full bg-surface-container-low text-on-surface border border-white/10 rounded-lg p-4 font-mono text-sm resize-none focus:outline-none focus:border-primary/50 transition-colors min-h-[50vh]"
              value={editingFile.content}
              onChange={(e) => setEditingFile({ ...editingFile, content: e.target.value })}
              disabled={isSaving}
            />
            {saveError && <div className="text-red-500 font-code-sm mt-2">{saveError}</div>}
          </>
        )}
      </Modal>
    </div>
  );
}
