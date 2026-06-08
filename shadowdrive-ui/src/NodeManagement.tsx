import { useState, useEffect } from 'react';
import { apiFetch } from './lib/api';

interface SystemNode {
  id: string;
  name: string;
  type: string;
  status: 'Online' | 'Offline';
  lastSeen: string;
  lastSync: string;
  storageUsed: string;
}

export default function NodeManagement() {
  const [nodes, setNodes] = useState<SystemNode[]>([]);

  // Modal State
  const [isConfigureOpen, setIsConfigureOpen] = useState(false);
  const [configureNode, setConfigureNode] = useState<SystemNode | null>(null);
  const [newNodeName, setNewNodeName] = useState('');

  // Dropdown State
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);

  const loadNodes = async () => {
    try {
      const data = await apiFetch('/system/nodes');
      const formattedNodes = data.map((d: any) => ({
        id: d.id.toString(),
        name: d.device_name,
        type: 'Client Node',
        status: d.is_online ? 'Online' : 'Offline',
        lastSeen: d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : 'Never',
        lastSync: 'N/A',
        storageUsed: 'N/A'
      }));
      setNodes(formattedNodes);
    } catch (err) {
      console.error('Failed to load nodes:', err);
    }
  };

  useEffect(() => {
    loadNodes();
    const interval = setInterval(loadNodes, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleConfigure = (node: SystemNode) => {
    setConfigureNode(node);
    setNewNodeName(node.name);
    setIsConfigureOpen(true);
  };

  const handleSaveConfiguration = async () => {
    if (!configureNode) return;
    try {
      await apiFetch(`/devices/${configureNode.id}`, {
        method: 'PUT',
        body: JSON.stringify({ device_name: newNodeName })
      });
      setIsConfigureOpen(false);
      loadNodes();
    } catch (err) {
      console.error('Failed to rename device:', err);
    }
  };

  const sendCommand = async (deviceId: string, command: string) => {
    try {
      await apiFetch(`/devices/${deviceId}/command?command=${command}`, {
        method: 'POST'
      });
      alert(`Command ${command} sent to ${deviceId}!`);
    } catch (err) {
      console.error(`Failed to send ${command}:`, err);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      {/* Header Actions */}
      <header className="h-20 border-b border-white/5 flex items-center justify-between px-margin-desktop shrink-0 z-10 glass-panel border-l-0 border-r-0 border-t-0" style={{ backgroundColor: 'rgba(17, 17, 17, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}>
        <div className="flex items-center space-x-2 font-code-sm text-code-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-sm text-primary">settings_ethernet</span>
          <span className="text-on-surface font-bold tracking-wider uppercase">Connected Nodes</span>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-margin-desktop no-scrollbar">
        <div className="max-w-[1400px] mx-auto w-full">
          
          <div className="mb-8">
            <h1 className="font-display-sm text-display-sm text-on-surface mb-2 font-bold tracking-tight">Node Management</h1>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
              Monitor and configure the devices connected to your ShadowDrive network. 
            </p>
          </div>

          {/* High-Level Overview */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
            <div className="glass-panel border border-white/5 rounded-xl p-6 relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl -mr-10 -mt-10 group-hover:bg-primary/10 transition-colors"></div>
              <p className="font-code-sm text-code-sm text-on-surface-variant mb-4 uppercase tracking-wider">TOTAL NODES</p>
              <div className="flex items-end gap-3">
                <span className="text-display-sm font-display-sm font-bold text-on-surface leading-none">{nodes.length}</span>
                <span className="text-primary font-label-md mb-1 flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-primary animate-pulse-emerald"></span>
                  {nodes.filter(n => n.status === 'Online').length} Active
                </span>
              </div>
            </div>

            <div className="glass-panel border border-white/5 rounded-xl p-6 relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl -mr-10 -mt-10 group-hover:bg-primary/10 transition-colors"></div>
              <p className="font-code-sm text-code-sm text-on-surface-variant mb-4 uppercase tracking-wider">NETWORK HEALTH</p>
              <div className="flex items-end gap-3">
                <span className="text-headline-md font-headline-md font-bold text-on-surface leading-none flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">verified_user</span>
                  Optimal
                </span>
              </div>
              <p className="text-on-surface-variant text-label-sm mt-2">All endpoints secured</p>
            </div>
          </div>

          {/* Nodes Grid */}
          {nodes.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {nodes.map(node => (
                <div key={node.id} className="glass-panel border border-white/10 rounded-xl p-6 relative overflow-hidden group hover:border-white/20 transition-all hover:translate-y-[-2px] hover:shadow-[0_10px_30px_-10px_rgba(0,0,0,0.5)]">
                  <div className={`absolute top-0 left-0 bottom-0 w-1 ${
                    node.status === 'Online' ? 'bg-primary' : 'bg-on-surface-variant/50'
                  }`}></div>
                  
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center">
                        <span className="material-symbols-outlined text-on-surface-variant">
                          computer
                        </span>
                      </div>
                      <div>
                        <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold">{node.name}</h3>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`w-2 h-2 rounded-full ${
                            node.status === 'Online' ? 'bg-primary' : 'bg-on-surface-variant/50'
                          }`}></span>
                          <span className="font-label-md text-label-md text-on-surface-variant">{node.status}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="relative">
                      <button 
                        className="text-on-surface-variant hover:text-on-surface transition-colors cursor-pointer"
                        onClick={() => setOpenDropdown(openDropdown === node.id ? null : node.id)}
                      >
                        <span className="material-symbols-outlined">more_vert</span>
                      </button>
                      
                      {openDropdown === node.id && (
                        <div className="absolute right-0 mt-2 w-48 bg-surface-container rounded-md shadow-lg border border-white/10 z-20 overflow-hidden">
                          <button 
                            className="w-full text-left px-4 py-2 text-sm text-error hover:bg-error/10 flex items-center gap-2 transition-colors cursor-pointer"
                            onClick={() => {
                              sendCommand(node.id, 'REVOKE');
                              setOpenDropdown(null);
                            }}
                          >
                            <span className="material-symbols-outlined text-sm">block</span>
                            Revoke Access
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="space-y-3 mt-6">
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <span className="font-label-md text-label-md text-on-surface-variant">Last Seen</span>
                      <span className="font-code-sm text-code-sm text-on-surface">{node.lastSeen}</span>
                    </div>
                    <div className="flex justify-between items-center pb-1">
                      <span className="font-label-md text-label-md text-on-surface-variant">Storage Used</span>
                      <span className="font-code-sm text-code-sm text-on-surface">{node.storageUsed}</span>
                    </div>
                  </div>
                  
                  <div className="mt-6 flex gap-3">
                    <button 
                      className="flex-1 bg-white/5 border border-white/10 hover:border-white/30 hover:bg-white/10 text-on-surface font-label-md text-label-md py-2 rounded transition-colors cursor-pointer"
                      onClick={() => handleConfigure(node)}
                    >
                      Configure
                    </button>
                    {node.status !== 'Online' && (
                      <button 
                        className="flex-1 bg-primary/10 text-primary border border-primary/30 hover:bg-primary/20 font-label-md text-label-md py-2 rounded transition-colors cursor-pointer"
                        onClick={() => sendCommand(node.id, 'WAKE')}
                      >
                        Wake
                      </button>
                    )}
                  </div>
                </div>
              ))}
              
            </div>
          ) : (
            <div className="w-full glass-panel border border-white/10 rounded-xl p-12 flex flex-col items-center justify-center text-center">
              <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center border border-white/10 mb-6">
                <span className="material-symbols-outlined text-5xl text-on-surface-variant">dns</span>
              </div>
              <h2 className="font-headline-md text-headline-md text-on-surface mb-2 font-bold">No Nodes Connected</h2>
              <p className="font-body-md text-body-md text-on-surface-variant max-w-md mb-8">
                You haven't connected any devices to your ShadowDrive network yet. Run the desktop client and log in to automatically register your first device.
              </p>
            </div>
          )}
          
        </div>
      </div>

      {/* Configuration Modal */}
      {isConfigureOpen && configureNode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-surface-container w-full max-w-md rounded-xl border border-white/10 overflow-hidden shadow-2xl">
            <div className="p-6 border-b border-white/10 flex justify-between items-center">
              <h2 className="text-headline-sm font-bold text-on-surface">Configure Device</h2>
              <button className="text-on-surface-variant hover:text-on-surface cursor-pointer" onClick={() => setIsConfigureOpen(false)}>
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-label-md text-on-surface-variant mb-2">Device Name</label>
                <input 
                  type="text" 
                  value={newNodeName}
                  onChange={e => setNewNodeName(e.target.value)}
                  className="w-full bg-surface border border-white/10 rounded-md px-4 py-2 text-on-surface focus:border-primary outline-none focus:ring-1 focus:ring-primary transition-all"
                  placeholder="e.g. My MacBook Pro"
                />
              </div>
              <div className="p-4 bg-primary/10 border border-primary/20 rounded-md">
                <div className="flex gap-3">
                  <span className="material-symbols-outlined text-primary">info</span>
                  <p className="text-body-sm text-on-surface-variant">
                    Selective sync configurations will be added here in a future update. For now, you can rename your device.
                  </p>
                </div>
              </div>
            </div>
            
            <div className="p-4 border-t border-white/10 flex justify-end gap-3 bg-white/5">
              <button 
                className="px-4 py-2 rounded-md font-label-md text-on-surface-variant hover:bg-white/10 transition-colors cursor-pointer"
                onClick={() => setIsConfigureOpen(false)}
              >
                Cancel
              </button>
              <button 
                className="bg-primary text-surface-container-lowest px-4 py-2 rounded-md font-label-md font-bold hover:bg-primary-container transition-colors cursor-pointer shadow-[0_0_10px_rgba(16,185,129,0.2)]"
                onClick={handleSaveConfiguration}
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
