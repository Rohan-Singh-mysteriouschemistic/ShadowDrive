import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, uploadFile, deleteFile, getDownloadUrl } from './lib/api';

type UploadStatus = 'pending' | 'uploading' | 'processing' | 'complete' | 'failed';

interface FileRecord {
  id: string | number;
  file_path: string;
  size_bytes: number;
  updated_at: string;
  upload_status: UploadStatus;
  is_conflict_copy?: boolean;
  storage_path?: string;
}



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
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fileToDelete, setFileToDelete] = useState<{id: string | number, name: string} | null>(null);
  const [editingFile, setEditingFile] = useState<{id: string | number, name: string, storage_path?: string, content: string} | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    async function loadFiles() {
      try {
        const data = await apiFetch('/sync/metadata');
        // Map backend response to FileRecord format
        const mappedFiles = data.map((f: any, idx: number) => ({
          id: f.id || f.hash || idx,
          file_path: f.file_path,
          size_bytes: f.size_bytes,
          updated_at: new Date().toLocaleString(), // Backend doesn't provide updated_at yet
          upload_status: 'complete',
          is_conflict_copy: f.file_path.includes('(Conflicted copy)'),
          storage_path: f.storage_path,
        }));
        setFiles(mappedFiles);
      } catch (err: any) {
        console.error('Failed to fetch files:', err);
        setError('Failed to load files. Backend may be unreachable.');
        // Ensure files are empty on error
        setFiles([]);
      } finally {
        setLoading(false);
      }
    }
    loadFiles();
  }, []);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const result = await uploadFile(file, file.name);
      
      setFiles(prev => [...prev, {
        id: result.version_id || Date.now(),
        file_path: file.name,
        size_bytes: file.size,
        updated_at: new Date().toLocaleString(),
        upload_status: 'complete'
      }]);
    } catch (err) {
      console.error('Upload failed', err);
      alert('Upload failed. Check console for details.');
    }
    
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDeleteClick = (e: React.MouseEvent, id: string | number, name: string) => {
    e.stopPropagation();
    setFileToDelete({ id, name });
  };

  const confirmDelete = async (id: string | number) => {
    try {
      await deleteFile(id.toString());
      setFiles(prev => prev.filter(f => f.id !== id));
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

  const handleRowClick = async (e: React.MouseEvent, file: FileRecord) => {
    if (isTextFile(file.file_path)) {
      try {
        const res = await fetch(`http://127.0.0.1:8001/api/download?file_path=${encodeURIComponent(file.file_path)}`);
        if (res.ok) {
          const text = await res.text();
          setEditingFile({ id: file.id, name: file.file_path, storage_path: file.storage_path, content: text });
        } else {
          // If local fetch fails, fallback to standard encrypted download from central server
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

  const getStatusDot = (status: UploadStatus, isConflict?: boolean) => {
    if (isConflict) return <div className="status-dot conflict w-2 h-2 rounded-full bg-red-500 animate-pulse" title="Conflict"></div>;
    switch (status) {
      case 'complete': return <div className="status-dot synced w-2 h-2 rounded-full bg-primary animate-pulse-emerald" title="Synced"></div>;
      case 'uploading': 
      case 'processing': return <div className="status-dot syncing w-2 h-2 rounded-full bg-yellow-500 animate-pulse" title="Syncing"></div>;
      case 'failed': return <div className="status-dot w-2 h-2 rounded-full bg-red-500" title="Failed"></div>;
      default: return <div className="status-dot w-2 h-2 rounded-full bg-gray-500" title="Pending"></div>;
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

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      {/* Header Actions */}
      <header className="h-20 border-b border-white/5 flex items-center justify-between px-margin-desktop shrink-0 z-10 glass-panel border-l-0 border-r-0 border-t-0" style={{ backgroundColor: 'rgba(17, 17, 17, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}>
        {/* Breadcrumbs */}
        <div className="flex items-center space-x-2 font-code-sm text-code-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-sm">home</span>
          <span>/</span>
          <span className="hover:text-primary cursor-pointer transition-colors" onClick={() => alert("Navigate to root folder")}>root</span>
        </div>
        
        {/* Actions Row */}
        <div className="flex items-center space-x-gutter">
          {/* Search */}
          <div className="relative group">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant group-focus-within:text-primary transition-colors text-sm">search</span>
            <input className="bg-surface-container-low border border-white/10 rounded-DEFAULT py-2 pl-9 pr-4 font-code-sm text-code-sm text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/50 transition-all w-64 placeholder:text-on-surface-variant" placeholder="Search Vault..." type="text" onChange={() => console.log("Searching...")} />
          </div>
          {/* Upload Button */}
          {/* Upload Button */}
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            className="hidden" 
          />
          <button 
            className="bg-primary-container text-surface-container-lowest font-label-md text-label-md px-4 py-2 rounded-DEFAULT flex items-center space-x-2 hover:bg-primary transition-colors hover:shadow-[0_0_15px_rgba(16,185,129,0.4)] cursor-pointer"
            onClick={handleUploadClick}
          >
            <span className="material-symbols-outlined text-sm">upload</span>
            <span>Upload File</span>
          </button>
        </div>
      </header>

      {/* File Table Area */}
      <div className="flex-1 overflow-y-auto p-margin-desktop z-10">
        <div className="w-full max-w-container-max mx-auto glass-panel rounded-xl overflow-hidden" style={{ backgroundColor: 'rgba(17, 17, 17, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
          {/* Table Header */}
          <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-white/10 font-code-sm text-code-sm text-on-surface-variant bg-surface-container-low/50">
            <div className="col-span-5">Name</div>
            <div className="col-span-2">Size</div>
            <div className="col-span-3">Last Modified</div>
            <div className="col-span-2 text-right">Status</div>
          </div>
          
          {/* Table Body */}
          <div className="flex flex-col relative min-h-[200px]">
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-surface-container-low/50 z-20">
                <div className="flex flex-col items-center">
                  <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
                  <span className="mt-2 font-code-sm text-on-surface-variant">Loading vault...</span>
                </div>
              </div>
            )}
            {!loading && error && (
              <div className="p-4 text-center text-red-500 font-code-sm border-b border-white/5 bg-red-500/5">
                {error}
              </div>
            )}
            {files.length === 0 && !loading && !error && (
              <div className="flex flex-col items-center justify-center text-center py-24 px-8 z-10 w-full">
                <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center border border-white/10 mb-4">
                  <span className="material-symbols-outlined text-4xl text-on-surface-variant">folder_open</span>
                </div>
                <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold mb-2">Vault Empty</h3>
                <p className="font-code-sm text-on-surface-variant max-w-sm mb-6">You don't have any files in your ShadowDrive yet. Upload a file to get started.</p>
                <button 
                  className="bg-primary text-surface-container-lowest font-label-md text-label-md py-2 px-6 rounded font-bold hover:bg-primary-container transition-colors shadow-[0_0_15px_rgba(16,185,129,0.3)] cursor-pointer flex items-center gap-2"
                  onClick={handleUploadClick}
                >
                  <span className="material-symbols-outlined text-sm">upload</span> Upload File
                </button>
              </div>
            )}
            {files.map(file => (
              <div key={file.id} className="file-row group grid grid-cols-12 gap-4 px-6 py-4 border-b border-white/5 items-center hover:bg-white/5 transition-colors relative cursor-pointer" onClick={(e) => handleRowClick(e, file)}>
                <div className="col-span-5 flex items-center space-x-3 font-code-sm text-code-sm text-on-surface">
                  <span className="material-symbols-outlined text-on-surface-variant group-hover:text-primary transition-colors">{getFileIcon(file.file_path)}</span>
                  <span className="truncate">{file.file_path}</span>
                </div>
                <div className="col-span-2 font-code-sm text-code-sm text-on-surface-variant">{formatBytes(file.size_bytes)}</div>
                <div className="col-span-3 font-code-sm text-code-sm text-on-surface-variant">{file.updated_at}</div>
                <div className="col-span-2 flex items-center justify-end space-x-4">
                  {getStatusDot(file.upload_status, file.is_conflict_copy)}
                  
                  {/* Actions Menu */}
                  <div className="opacity-0 group-hover:opacity-100 flex items-center gap-2 transition-all">
                    <button 
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/vault/history?file=${file.id}&name=${encodeURIComponent(file.file_path)}`);
                      }}
                      className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer" 
                      title="View History"
                    >
                      <span className="material-symbols-outlined text-sm">history</span>
                    </button>
                    <button 
                      onClick={(e) => handleDownload(e, file.storage_path)}
                      className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer"
                      title="Download"
                    >
                      <span className="material-symbols-outlined text-sm">download</span>
                    </button>
                    <button 
                      onClick={(e) => handleDeleteClick(e, file.id, file.file_path)}
                      className="text-on-surface-variant hover:text-error transition-colors cursor-pointer"
                      title="Delete"
                    >
                      <span className="material-symbols-outlined text-sm">delete</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {fileToDelete && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background/80 backdrop-blur-sm" onClick={() => setFileToDelete(null)}>
          <div className="bg-surface-container-high border border-white/10 p-6 rounded-xl shadow-2xl max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-headline-sm font-headline-sm font-bold text-on-surface mb-2">Delete File</h3>
            <p className="text-on-surface-variant font-code-sm mb-6">
              Are you sure you want to delete <span className="text-primary">{fileToDelete.name}</span>? This action cannot be undone.
            </p>
            <div className="flex justify-end space-x-4">
              <button 
                onClick={() => setFileToDelete(null)} 
                className="px-4 py-2 font-label-md text-on-surface-variant hover:text-on-surface transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button 
                onClick={() => confirmDelete(fileToDelete.id)} 
                className="px-4 py-2 bg-error text-on-error rounded font-label-md hover:bg-red-600 transition-colors shadow-[0_0_10px_rgba(239,68,68,0.3)] cursor-pointer"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Text Editor Modal */}
      {editingFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-surface-container-lowest border border-white/10 rounded-2xl p-6 w-full max-w-4xl shadow-2xl flex flex-col h-[80vh]">
            <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold mb-4 flex items-center justify-between">
              <span>{editingFile.name}</span>
              <button onClick={() => setEditingFile(null)} className="text-on-surface-variant hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </h3>
            
            <textarea
              className="flex-1 w-full bg-surface-container-low text-on-surface border border-white/10 rounded-lg p-4 font-mono text-sm resize-none focus:outline-none focus:border-primary/50 transition-colors"
              value={editingFile.content}
              onChange={(e) => setEditingFile({ ...editingFile, content: e.target.value })}
              disabled={isSaving}
            />

            <div className="flex justify-end space-x-4 mt-6">
              <button 
                className="px-6 py-2 rounded font-label-md text-label-md text-on-surface hover:bg-white/5 transition-colors cursor-pointer"
                onClick={() => setEditingFile(null)}
                disabled={isSaving}
              >
                Cancel
              </button>
              <button 
                className="bg-primary text-surface-container-lowest font-label-md text-label-md py-2 px-6 rounded font-bold hover:bg-primary-container transition-colors shadow-[0_0_15px_rgba(16,185,129,0.3)] cursor-pointer disabled:opacity-50"
                onClick={async () => {
                  setIsSaving(true);
                  try {
                    const blob = new Blob([editingFile.content], { type: 'text/plain' });
                    const fileObj = new File([blob], editingFile.name, { type: 'text/plain' });
                    await uploadFile(fileObj, editingFile.name);
                    
                    // Refresh files
                    const data = await apiFetch('/sync/metadata');
                    const mappedFiles = data.map((f: any, idx: number) => ({
                      id: f.id || f.hash || idx,
                      file_path: f.file_path,
                      size_bytes: f.size_bytes,
                      updated_at: new Date().toLocaleString(),
                      upload_status: 'complete',
                      is_conflict_copy: f.file_path.includes('(Conflicted copy)'),
                      storage_path: f.storage_path,
                    }));
                    setFiles(mappedFiles);
                    setEditingFile(null);
                  } catch (err) {
                    console.error("Failed to save file", err);
                    alert("Failed to save changes.");
                  } finally {
                    setIsSaving(false);
                  }
                }}
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
