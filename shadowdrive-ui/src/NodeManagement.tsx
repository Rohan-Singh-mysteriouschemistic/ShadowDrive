import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface SystemNode {
  id: string;
  name: string;
  type: string;
  status: 'Online' | 'Sleeping' | 'Offline' | 'Syncing';
  lastSeen: string;
  lastSync: string;
  storageUsed: string;
}

export default function NodeManagement() {
  const navigate = useNavigate();
  const [nodes] = useState<SystemNode[]>([]);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      {/* Header Actions */}
      <header className="h-20 border-b border-white/5 flex items-center justify-between px-margin-desktop shrink-0 z-10 glass-panel border-l-0 border-r-0 border-t-0" style={{ backgroundColor: 'rgba(17, 17, 17, 0.6)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}>
        {/* Breadcrumbs */}
        <div className="flex items-center space-x-2 font-code-sm text-code-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-sm text-primary">settings_ethernet</span>
          <span className="text-on-surface font-bold tracking-wider uppercase">Connected Nodes</span>
        </div>
        
        {/* Actions Row */}
        <div className="flex items-center space-x-gutter">
          <button 
            className="bg-primary-container text-surface-container-lowest font-label-md text-label-md px-4 py-2 rounded-DEFAULT flex items-center space-x-2 hover:bg-primary transition-colors hover:shadow-[0_0_15px_rgba(16,185,129,0.4)] cursor-pointer"
            onClick={() => navigate('/nodes/deploy')}
          >
            <span className="material-symbols-outlined text-sm">add</span>
            <span>Deploy New Node</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-margin-desktop z-10 flex flex-col items-center">
        <div className="w-full max-w-container-max flex flex-col gap-8">
          
          {/* Network Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="glass-panel border border-white/10 rounded-xl p-6 flex flex-col gap-2 relative overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-1 bg-primary"></div>
              <span className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Total Nodes</span>
              <div className="flex items-end gap-3">
                <span className="font-display-md text-display-md text-on-surface">{nodes.length}</span>
                <span className="font-label-md text-label-md text-primary mb-1">Active</span>
              </div>
            </div>
            
            <div className="glass-panel border border-white/10 rounded-xl p-6 flex flex-col gap-2 relative overflow-hidden">
              <span className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Global Storage</span>
              <div className="flex items-end gap-3 mb-2">
                <span className="font-display-md text-display-md text-on-surface">0.0</span>
                <span className="font-label-md text-label-md text-on-surface-variant mb-1">GB Used</span>
              </div>
              <div className="h-1.5 w-full bg-surface-container-high rounded-full overflow-hidden">
                <div className="h-full bg-primary w-[0%]" style={{ boxShadow: '0 0 10px rgba(16, 185, 129, 0.5)' }}></div>
              </div>
            </div>

            <div className="glass-panel border border-white/10 rounded-xl p-6 flex flex-col gap-2 relative overflow-hidden">
              <span className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Network Health</span>
              <div className="flex items-center gap-3 mt-2">
                <span className="material-symbols-outlined text-primary text-3xl">verified_user</span>
                <div>
                  <div className="font-headline-sm text-headline-sm text-on-surface">Optimal</div>
                  <div className="font-code-sm text-code-sm text-on-surface-variant">All endpoints secured</div>
                </div>
              </div>
            </div>
          </div>

          {/* Nodes Grid */}
          {nodes.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {nodes.map(node => (
                <div key={node.id} className="glass-panel border border-white/10 rounded-xl p-6 relative overflow-hidden group hover:border-white/20 transition-all hover:translate-y-[-2px] hover:shadow-[0_10px_30px_-10px_rgba(0,0,0,0.5)]">
                  <div className={`absolute top-0 left-0 bottom-0 w-1 ${
                    node.status === 'Online' ? 'bg-primary' : 
                    node.status === 'Syncing' ? 'bg-[#3b82f6] animate-pulse' : 'bg-on-surface-variant/50'
                  }`}></div>
                  
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center">
                        <span className="material-symbols-outlined text-on-surface-variant">
                          {node.type === 'primary' ? 'computer' : 
                           node.type === 'secondary' ? 'laptop_mac' : 'dns'}
                        </span>
                      </div>
                      <div>
                        <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold">{node.name}</h3>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`w-2 h-2 rounded-full ${
                            node.status === 'Online' ? 'bg-primary' : 
                            node.status === 'Syncing' ? 'bg-[#3b82f6]' : 'bg-on-surface-variant/50'
                          }`}></span>
                          <span className="font-label-md text-label-md text-on-surface-variant">{node.status}</span>
                        </div>
                      </div>
                    </div>
                    
                    <button className="text-on-surface-variant hover:text-on-surface transition-colors opacity-0 group-hover:opacity-100 cursor-pointer">
                      <span className="material-symbols-outlined">more_vert</span>
                    </button>
                  </div>
                  
                  <div className="space-y-3 mt-6">
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <span className="font-label-md text-label-md text-on-surface-variant">Storage Used</span>
                      <span className="font-code-sm text-code-sm text-on-surface">{node.storageUsed}</span>
                    </div>
                    <div className="flex justify-between items-center pb-1">
                      <span className="font-label-md text-label-md text-on-surface-variant">Last Sync</span>
                      <span className="font-code-sm text-code-sm text-on-surface">{node.lastSync}</span>
                    </div>
                  </div>
                  
                  <div className="mt-6 flex gap-3">
                    <button className="flex-1 bg-white/5 border border-white/10 hover:border-white/30 hover:bg-white/10 text-on-surface font-label-md text-label-md py-2 rounded transition-colors cursor-pointer">
                      Configure
                    </button>
                    {node.status !== 'Online' && (
                      <button className="flex-1 bg-primary/10 text-primary border border-primary/30 hover:bg-primary/20 font-label-md text-label-md py-2 rounded transition-colors cursor-pointer">
                        Wake
                      </button>
                    )}
                  </div>
                </div>
              ))}
              
              {/* Add Node Card */}
              <div 
                className="border-2 border-dashed border-white/10 rounded-xl p-6 flex flex-col items-center justify-center text-center hover:border-primary/50 hover:bg-primary/5 transition-all group cursor-pointer"
                onClick={() => navigate('/nodes/deploy')}
              >
                <div className="w-14 h-14 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined text-3xl text-on-surface-variant group-hover:text-primary transition-colors">add</span>
                </div>
                <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold mb-1">Add New Node</h3>
                <p className="font-label-md text-label-md text-on-surface-variant">Connect another device to your ShadowDrive network</p>
              </div>
            </div>
          ) : (
            <div className="w-full glass-panel border border-white/10 rounded-xl p-12 flex flex-col items-center justify-center text-center">
              <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center border border-white/10 mb-6">
                <span className="material-symbols-outlined text-5xl text-on-surface-variant">dns</span>
              </div>
              <h2 className="font-headline-md text-headline-md text-on-surface mb-2 font-bold">No Nodes Deployed</h2>
              <p className="font-body-md text-body-md text-on-surface-variant max-w-md mb-8">
                You haven't connected any devices to your ShadowDrive network yet. Add a node to start syncing files.
              </p>
              <button 
                className="bg-primary text-surface-container-lowest font-label-md text-label-md py-3 px-6 rounded font-bold hover:bg-primary-container transition-colors shadow-[0_0_15px_rgba(16,185,129,0.3)] cursor-pointer flex items-center gap-2"
                onClick={() => navigate('/nodes/deploy')}
              >
                <span className="material-symbols-outlined text-sm">add</span> Add New Node
              </button>
            </div>
          )}
          
        </div>
      </div>
    </div>
  );
}
