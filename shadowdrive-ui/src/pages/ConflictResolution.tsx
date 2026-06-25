import { useState, useCallback } from 'react';
import { useConflicts, useResolveConflict } from '../hooks/useConflicts';
import { useEventInvalidation } from '../hooks/useEvents';
import { CLIENT_API_URL } from '../lib/api';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Button from '../components/Button';
import Modal from '../components/Modal';

export default function ConflictResolution() {
  const { data: conflicts = [], isLoading } = useConflicts();
  const resolveMutation = useResolveConflict();
  useEventInvalidation();

  const [logs, setLogs] = useState<{ id: number; time: string; msg: string; type: string }[]>([]);
  const [previewContent, setPreviewContent] = useState<{ title: string; content: string; isLoading: boolean } | null>(null);
  const [showNoConflictsModal, setShowNoConflictsModal] = useState(false);

  const handlePreview = useCallback(async (filePath: string, label: string) => {
    setPreviewContent({ title: `Preview — ${label}`, content: '', isLoading: true });
    try {
      const res = await fetch(`${CLIENT_API_URL}/api/download?file_path=${encodeURIComponent(filePath)}`);
      if (res.ok) {
        const contentType = res.headers.get('content-type') || '';
        if (contentType.includes('text') || contentType.includes('json')) {
          const text = await res.text();
          setPreviewContent({ title: `Preview — ${label}`, content: text, isLoading: false });
        } else {
          const blob = await res.blob();
          setPreviewContent({
            title: `Preview — ${label}`,
            content: `[Binary file]\nSize: ${blob.size} bytes\nType: ${contentType || 'unknown'}`,
            isLoading: false,
          });
        }
      } else {
        setPreviewContent({ title: `Preview — ${label}`, content: `Failed to load preview (HTTP ${res.status})`, isLoading: false });
      }
    } catch (err) {
      setPreviewContent({ title: `Preview — ${label}`, content: 'Failed to load preview: Network error', isLoading: false });
    }
  }, []);

  const addLog = (msg: string, type: string) => {
    setLogs(prev => [{
      id: Date.now(),
      time: new Date().toLocaleTimeString(),
      msg,
      type,
    }, ...prev]);
  };

  const resolveConflict = async (
    original_file_id: number,
    conflict_file_id: number,
    resolution_choice: 'keep_original' | 'keep_conflict' | 'keep_both',
  ) => {
    try {
      await resolveMutation.mutateAsync({ original_file_id, conflict_file_id, resolution_choice });
      addLog(`Conflict resolved (${resolution_choice})`, 'success');
    } catch (error) {
      console.error('Failed to resolve conflict', error);
      addLog(`Error resolving conflict`, 'error');
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center h-full w-full">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      <PageHeader
        icon="warning"
        title="Active Conflicts"
        iconColor="text-error"
        actions={
          <Button
            variant="ghost"
            size="sm"
            icon="auto_fix_high"
            onClick={() => {
              if (!conflicts.length) {
                setShowNoConflictsModal(true);
                return;
              }
              resolveConflict(
                conflicts[0].original_file_id,
                conflicts[0].conflict_file_id,
                'keep_both',
              );
            }}
          >
            Auto-Resolve All
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto p-margin-desktop z-10 flex flex-col items-center">
        <div className="w-full max-w-container-max flex flex-col gap-6">
          {conflicts.length === 0 ? (
            <Card variant="glass" glow="primary" className="p-12 flex flex-col items-center justify-center text-center bg-primary/5 mt-8">
              <div className="w-20 h-20 bg-primary/20 rounded-full flex items-center justify-center border border-primary/30 mb-6">
                <span className="material-symbols-outlined text-5xl text-primary animate-pulse">
                  verified_user
                </span>
              </div>
              <h2 className="font-display-sm text-display-sm text-on-surface mb-2 font-bold">
                No Active Conflicts
              </h2>
              <p className="font-body-md text-body-md text-on-surface-variant max-w-md">
                Your ShadowDrive network is fully synchronized. All files are up to date
                across your connected devices with no detected version mismatches.
              </p>
            </Card>
          ) : (
            <>
              {conflicts.map((conflict) => (
                <div key={conflict.id}>
                  <div className="bg-error-container/10 border border-error/30 rounded-xl p-6 glass-panel flex flex-col md:flex-row justify-between items-start md:items-center gap-4 relative overflow-hidden mb-6">
                    <div className="absolute top-0 left-0 bottom-0 w-1 bg-error animate-pulse" />
                    <div>
                      <h2 className="font-headline-md text-headline-md text-on-surface font-bold flex items-center gap-3">
                        {conflict.filename}
                        <span className="bg-error/20 text-error font-label-md text-code-sm px-2 py-0.5 rounded border border-error/30">
                          Needs Resolution
                        </span>
                      </h2>
                      <p className="font-code-sm text-code-sm text-on-surface-variant mt-1">
                        {conflict.path}
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="font-label-md text-label-md text-on-surface-variant">
                        Detected: {conflict.timeDetected}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-4">
                    <Card variant="glass" hover className="border border-white/10 hover:border-primary/50">
                      <div className="bg-surface-container-high p-4 border-b border-white/5 flex justify-between items-center">
                        <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold flex items-center gap-2">
                          <span className="bg-primary/20 text-primary w-6 h-6 rounded flex items-center justify-center font-mono text-sm">A</span>
                          Local Version
                        </h3>
                        <span className="material-symbols-outlined text-on-surface-variant">computer</span>
                      </div>
                      <div className="p-6 flex flex-col gap-4">
                        <InfoRow label="Device" value={conflict.optionA.device} />
                        <InfoRow label="Modified" value={conflict.optionA.timestamp} />
                        <InfoRow label="Size" value={conflict.optionA.size} />
                        <InfoRow label="Hash" value={conflict.optionA.hash} mono />
                        <div className="mt-4 flex gap-3">
                          <Button
                            variant="primary"
                            size="sm"
                            className="flex-1"
                            onClick={() => resolveConflict(conflict.original_file_id, conflict.conflict_file_id, 'keep_original')}
                          >
                            Keep A
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            icon="visibility"
                            className="flex-1"
                            onClick={() => handlePreview(conflict.path, `Option A — ${conflict.optionA.device}`)}
                          >
                            Preview
                          </Button>
                        </div>
                      </div>
                    </Card>

                    <Card variant="glass" hover className="border border-white/10 hover:border-[#3b82f6]/50 relative">
                      <div className="absolute inset-0 bg-gradient-to-br from-[#3b82f6]/5 to-transparent pointer-events-none" />
                      <div className="bg-surface-container-high p-4 border-b border-white/5 flex justify-between items-center relative z-10">
                        <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold flex items-center gap-2">
                          <span className="bg-[#3b82f6]/20 text-[#3b82f6] w-6 h-6 rounded flex items-center justify-center font-mono text-sm">B</span>
                          Remote Version
                        </h3>
                        <span className="material-symbols-outlined text-on-surface-variant">cloud</span>
                      </div>
                      <div className="p-6 flex flex-col gap-4 relative z-10">
                        <InfoRow label="Device" value={conflict.optionB.device} />
                        <InfoRow label="Modified" value={conflict.optionB.timestamp} />
                        <InfoRow label="Size" value={conflict.optionB.size} />
                        <InfoRow label="Hash" value={conflict.optionB.hash} mono />
                        <div className="mt-4 flex gap-3">
                          <Button
                            variant="primary"
                            size="sm"
                            className="flex-1"
                            onClick={() => resolveConflict(conflict.original_file_id, conflict.conflict_file_id, 'keep_conflict')}
                          >
                            Keep B
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            icon="visibility"
                            className="flex-1"
                            onClick={() => handlePreview(conflict.path, `Option B — ${conflict.optionB.device}`)}
                          >
                            Preview
                          </Button>
                        </div>
                      </div>
                    </Card>
                  </div>

                  <div className="flex justify-center mb-6">
                    <Button
                      variant="secondary"
                      icon="call_split"
                      onClick={() => resolveConflict(conflict.original_file_id, conflict.conflict_file_id, 'keep_both')}
                    >
                      Keep Both (Rename B to "Resolved Copy")
                    </Button>
                  </div>
                </div>
              ))}
            </>
          )}

          <Card className="border border-white/10 overflow-hidden mt-4">
            <div className="bg-surface-container-high p-3 border-b border-white/5">
              <h3 className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">
                Sync Activity Log
              </h3>
            </div>
            <div className="p-4 font-code-sm text-code-sm space-y-2">
              {logs.length === 0 ? (
                <div className="text-on-surface-variant italic text-center py-4">
                  No recent sync activity
                </div>
              ) : (
                logs.map((log) => (
                  <div key={log.id} className="flex items-start gap-3">
                    <span className="text-on-surface-variant w-20 shrink-0">[{log.time}]</span>
                    <span className={
                      log.type === 'error' ? 'text-error' :
                      log.type === 'warning' ? 'text-yellow-500' : 'text-primary'
                    }>
                      {log.type === 'error' ? 'ERROR' : log.type === 'warning' ? 'WARN' : 'INFO '}
                    </span>
                    <span className="text-on-surface">{log.msg}</span>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>

      <Modal
        open={!!previewContent}
        onClose={() => setPreviewContent(null)}
        title={previewContent?.title || 'Preview'}
        maxWidth="lg"
        footer={
          <Button variant="ghost" onClick={() => setPreviewContent(null)}>Close</Button>
        }
      >
        {previewContent?.isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <pre className="bg-surface-container-low text-on-surface border border-white/10 rounded-lg p-4 font-mono text-sm whitespace-pre-wrap break-words max-h-[60vh] overflow-y-auto">
            {previewContent?.content || 'No content available'}
          </pre>
        )}
      </Modal>

      <Modal
        open={showNoConflictsModal}
        onClose={() => setShowNoConflictsModal(false)}
        title="Conflict Resolver"
        footer={
          <Button variant="primary" onClick={() => setShowNoConflictsModal(false)}>Acknowledge</Button>
        }
      >
        <p className="text-on-surface-variant font-code-sm">
          No active conflicts found. System is fully synchronized.
        </p>
      </Modal>

    </div>
  );
}

function InfoRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between items-center border-b border-white/5 pb-2">
      <span className="font-label-md text-label-md text-on-surface-variant">{label}</span>
      <span className={`font-code-sm text-code-sm ${mono ? 'text-on-surface-variant font-mono truncate ml-2' : 'text-on-surface font-bold'}`}>
        {value}
      </span>
    </div>
  );
}
