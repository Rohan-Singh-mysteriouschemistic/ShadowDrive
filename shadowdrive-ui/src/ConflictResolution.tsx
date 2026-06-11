import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from './lib/api';
import { useEventStream } from './lib/useEventStream';

interface ConflictRecord {
  id: string;
  filename: string;
  path: string;
  timeDetected: string;
  status: 'Needs Resolution' | 'Resolved';
  original_file_id: number;
  conflict_file_id: number;
  optionA: {
    device: string;
    timestamp: string;
    size: string;
    hash: string;
  };
  optionB: {
    device: string;
    timestamp: string;
    size: string;
    hash: string;
  };
}

export default function ConflictResolution() {
  const [conflicts, setConflicts] = useState<ConflictRecord[]>([]);
  const [logs, setLogs] = useState<{ id: number; time: string; msg: string; type: string }[]>([]);
  const fetchConflicts = useCallback(async () => {
    try {
      const data = await apiFetch('/sync/conflicts');
      setConflicts(data);
    } catch (error) {
      console.error('Failed to fetch conflicts', error);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchConflicts();
  }, [fetchConflicts]);

  useEventStream(useCallback((event) => {
    if (event.type === 'conflict_detected') {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      fetchConflicts();
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLogs(prev => [{
        id: Date.now(),
        time: new Date().toLocaleTimeString(),
        msg: `Conflict detected on file: ${event.data.file_path}`,
        type: 'warning'
      }, ...prev]);
    }
  }, [fetchConflicts]));

  const resolveConflict = async (resolution: 'keep_original' | 'keep_conflict' | 'keep_both') => {
    if (!conflicts.length) return;
    const currentConflict = conflicts[0];
    
    try {
      await apiFetch('/sync/resolve_conflict', {
        method: 'POST',
        body: JSON.stringify({
          original_file_id: currentConflict.original_file_id,
          conflict_file_id: currentConflict.conflict_file_id,
          resolution_choice: resolution
        })
      });
      setLogs(prev => [{
        id: Date.now(),
        time: new Date().toLocaleTimeString(),
        msg: `Conflict resolved successfully`,
        type: 'success'
      }, ...prev]);
      fetchConflicts();
    } catch (error) {
      console.error('Failed to resolve conflict', error);
      setLogs(prev => [{
        id: Date.now(),
        time: new Date().toLocaleTimeString(),
        msg: `Error resolving conflict`,
        type: 'error'
      }, ...prev]);
    }
  };

  const conflict = conflicts[0];

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      {/* Header Actions */}
      <header className="h-20 border-b border-white/5 flex items-center justify-between px-margin-desktop shrink-0 z-10 glass-panel border-l-0 border-r-0 border-t-0" style={{ backgroundColor: 'rgba(17, 17, 17, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}>
        {/* Breadcrumbs */}
        <div className="flex items-center space-x-2 font-code-sm text-code-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-sm text-error">warning</span>
          <span className="text-error font-bold tracking-wider uppercase">Active Conflict</span>
        </div>
        
        {/* Actions Row */}
        <div className="flex items-center space-x-gutter">
          <button 
            className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer flex items-center gap-2 px-3 py-1.5 rounded bg-surface-container hover:bg-surface-container-high" 
            onClick={() => alert("Auto-resolve all not implemented")}
          >
            <span className="material-symbols-outlined text-sm">auto_fix_high</span>
            <span className="font-label-md text-label-md">Auto-Resolve All</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-margin-desktop z-10 flex flex-col items-center">
        <div className="w-full max-w-container-max flex flex-col gap-6">
          
          {!conflict ? (
            <div className="w-full glass-panel border border-primary/30 rounded-2xl p-12 flex flex-col items-center justify-center text-center bg-primary/5 mt-8">
              <div className="w-20 h-20 bg-primary/20 rounded-full flex items-center justify-center border border-primary/30 mb-6">
                <span className="material-symbols-outlined text-5xl text-primary animate-pulse">verified_user</span>
              </div>
              <h2 className="font-display-sm text-display-sm text-on-surface mb-2 font-bold">No Active Conflicts</h2>
              <p className="font-body-md text-body-md text-on-surface-variant max-w-md">
                Your ShadowDrive network is fully synchronized. All files are up to date across your connected devices with no detected version mismatches.
              </p>
            </div>
          ) : (
            <>
              <div className="bg-error-container/10 border border-error/30 rounded-xl p-6 glass-panel flex flex-col md:flex-row justify-between items-start md:items-center gap-4 relative overflow-hidden">
                <div className="absolute top-0 left-0 bottom-0 w-1 bg-error animate-pulse"></div>
                <div>
                  <h2 className="font-headline-md text-headline-md text-on-surface font-bold flex items-center gap-3">
                    {conflict.filename}
                    <span className="bg-error/20 text-error font-label-md text-code-sm px-2 py-0.5 rounded border border-error/30">Needs Resolution</span>
                  </h2>
                  <p className="font-code-sm text-code-sm text-on-surface-variant mt-1">{conflict.path}</p>
                </div>
                <div className="text-right">
                  <div className="font-label-md text-label-md text-on-surface-variant">Detected: {conflict.timeDetected}</div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Option A */}
                <div className="glass-panel border border-white/10 rounded-xl overflow-hidden hover:border-primary/50 transition-colors group">
                  <div className="bg-surface-container-high p-4 border-b border-white/5 flex justify-between items-center">
                    <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold flex items-center gap-2">
                      <span className="bg-primary/20 text-primary w-6 h-6 rounded flex items-center justify-center font-mono text-sm">A</span>
                      Local Version
                    </h3>
                    <span className="material-symbols-outlined text-on-surface-variant group-hover:text-primary transition-colors">computer</span>
                  </div>
                  <div className="p-6 flex flex-col gap-4">
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <span className="font-label-md text-label-md text-on-surface-variant">Device</span>
                      <span className="font-code-sm text-code-sm text-on-surface font-bold">{conflict.optionA.device}</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <span className="font-label-md text-label-md text-on-surface-variant">Modified</span>
                      <span className="font-code-sm text-code-sm text-on-surface">{conflict.optionA.timestamp}</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <span className="font-label-md text-label-md text-on-surface-variant">Size</span>
                      <span className="font-code-sm text-code-sm text-on-surface">{conflict.optionA.size}</span>
                    </div>
                    <div className="flex justify-between items-center pb-2">
                      <span className="font-label-md text-label-md text-on-surface-variant">Hash</span>
                      <span className="font-code-sm text-code-sm text-on-surface-variant font-mono">{conflict.optionA.hash}</span>
                    </div>
                    
                    <div className="mt-4 flex gap-3">
                      <button 
                        className="flex-1 bg-primary text-surface-container-lowest font-label-md text-label-md py-2 rounded font-bold hover:bg-primary-container transition-colors shadow-[0_0_15px_rgba(16,185,129,0.3)] cursor-pointer"
                        onClick={() => resolveConflict('keep_original')}
                      >
                        Keep A
                      </button>
                      <button 
                        className="flex-1 border border-white/20 text-on-surface font-label-md text-label-md py-2 rounded hover:bg-white/5 transition-colors flex items-center justify-center gap-2 cursor-pointer"
                        onClick={() => alert("Preview Option A")}
                      >
                        <span className="material-symbols-outlined text-sm">visibility</span> Preview
                      </button>
                    </div>
                  </div>
                </div>

                {/* Option B */}
                <div className="glass-panel border border-white/10 rounded-xl overflow-hidden hover:border-[#3b82f6]/50 transition-colors group relative">
                  <div className="absolute inset-0 bg-gradient-to-br from-[#3b82f6]/5 to-transparent pointer-events-none"></div>
                  <div className="bg-surface-container-high p-4 border-b border-white/5 flex justify-between items-center relative z-10">
                    <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold flex items-center gap-2">
                      <span className="bg-[#3b82f6]/20 text-[#3b82f6] w-6 h-6 rounded flex items-center justify-center font-mono text-sm">B</span>
                      Remote Version
                    </h3>
                    <span className="material-symbols-outlined text-on-surface-variant group-hover:text-[#3b82f6] transition-colors">cloud</span>
                  </div>
                  <div className="p-6 flex flex-col gap-4 relative z-10">
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <span className="font-label-md text-label-md text-on-surface-variant">Device</span>
                      <span className="font-code-sm text-code-sm text-on-surface font-bold">{conflict.optionB.device}</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <span className="font-label-md text-label-md text-on-surface-variant">Modified</span>
                      <span className="font-code-sm text-code-sm text-on-surface">{conflict.optionB.timestamp}</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <span className="font-label-md text-label-md text-on-surface-variant">Size</span>
                      <span className="font-code-sm text-code-sm text-primary">{conflict.optionB.size} (+3 KB)</span>
                    </div>
                    <div className="flex justify-between items-center pb-2">
                      <span className="font-label-md text-label-md text-on-surface-variant">Hash</span>
                      <span className="font-code-sm text-code-sm text-on-surface-variant font-mono">{conflict.optionB.hash}</span>
                    </div>
                    
                    <div className="mt-4 flex gap-3">
                      <button 
                        className="flex-1 bg-[#3b82f6] text-white font-label-md text-label-md py-2 rounded font-bold hover:bg-[#2563eb] transition-colors shadow-[0_0_15px_rgba(59,130,246,0.3)] cursor-pointer"
                        onClick={() => resolveConflict('keep_conflict')}
                      >
                        Keep B
                      </button>
                      <button 
                        className="flex-1 border border-white/20 text-on-surface font-label-md text-label-md py-2 rounded hover:bg-white/5 transition-colors flex items-center justify-center gap-2 cursor-pointer"
                        onClick={() => alert("Preview Option B")}
                      >
                        <span className="material-symbols-outlined text-sm">visibility</span> Preview
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex justify-center my-2">
                <button 
                  className="bg-surface-container-high border border-white/10 hover:border-white/30 text-on-surface font-label-md text-label-md py-3 px-8 rounded-full transition-all hover:bg-white/5 flex items-center gap-2 shadow-lg cursor-pointer"
                  onClick={() => resolveConflict('keep_both')}
                >
                  <span className="material-symbols-outlined text-sm">call_split</span>
                  Keep Both (Rename B to "Resolved Copy")
                </button>
              </div>
            </>
          )}

          <div className="glass-panel border border-white/10 rounded-xl overflow-hidden mt-4">
            <div className="bg-surface-container-high p-3 border-b border-white/5">
              <h3 className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Sync Activity Log</h3>
            </div>
            <div className="p-4 font-code-sm text-code-sm space-y-2">
              {logs.length === 0 ? (
                <div className="text-on-surface-variant italic text-center py-4">No recent sync activity</div>
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
          </div>
          
        </div>
      </div>
    </div>
  );
}
