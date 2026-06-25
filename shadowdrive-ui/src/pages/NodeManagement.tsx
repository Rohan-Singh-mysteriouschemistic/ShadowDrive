import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNodes, useRenameNode, useSendCommand } from '../hooks/useNodes';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Button from '../components/Button';
import Modal from '../components/Modal';
import EmptyState from '../components/EmptyState';

export default function NodeManagement() {
  const navigate = useNavigate();
  const { data: nodes = [] } = useNodes();
  const renameNode = useRenameNode();
  const sendCommand = useSendCommand();

  const [isConfigureOpen, setIsConfigureOpen] = useState(false);
  const [configureNodeId, setConfigureNodeId] = useState<string | null>(null);
  const [configureNodeName, setConfigureNodeName] = useState('');
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);

  const handleConfigure = (id: string, name: string) => {
    setConfigureNodeId(id);
    setConfigureNodeName(name);
    setIsConfigureOpen(true);
  };

  const handleSaveConfiguration = async () => {
    if (!configureNodeId) return;
    try {
      await renameNode.mutateAsync({ id: configureNodeId, name: configureNodeName });
      setIsConfigureOpen(false);
    } catch (err) {
      console.error('Failed to rename device:', err);
    }
  };

  const handleSendCommand = async (deviceId: string, command: string) => {
    try {
      await sendCommand.mutateAsync({ deviceId, command });
      alert(`Command ${command} sent to ${deviceId}!`);
    } catch (err) {
      console.error(`Failed to send ${command}:`, err);
    }
  };

  const onlineNodes = nodes.filter(n => n.status === 'Online').length;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      <PageHeader
        icon="settings_ethernet"
        title="Connected Nodes"
        iconColor="text-primary"
        actions={
          <Button
            variant="ghost"
            size="sm"
            icon="add"
            onClick={() => navigate('/nodes/deploy')}
          >
            Deploy New Node
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto p-margin-desktop no-scrollbar">
        <div className="max-w-[1400px] mx-auto w-full">
          <div className="mb-8">
            <h1 className="font-display-sm text-display-sm text-on-surface mb-2 font-bold tracking-tight">
              Node Management
            </h1>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
              Monitor and configure the devices connected to your ShadowDrive network.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
            <Card variant="glass" hover className="p-6 border border-white/5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl -mr-10 -mt-10 group-hover:bg-primary/10 transition-colors" />
              <p className="font-code-sm text-code-sm text-on-surface-variant mb-4 uppercase tracking-wider">
                TOTAL NODES
              </p>
              <div className="flex items-end gap-3">
                <span className="text-display-sm font-display-sm font-bold text-on-surface leading-none">
                  {nodes.length}
                </span>
                <span className="text-primary font-label-md mb-1 flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-primary pulse-dot" />
                  {onlineNodes} Active
                </span>
              </div>
            </Card>

            <Card variant="glass" hover className="p-6 border border-white/5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl -mr-10 -mt-10 group-hover:bg-primary/10 transition-colors" />
              <p className="font-code-sm text-code-sm text-on-surface-variant mb-4 uppercase tracking-wider">
                NETWORK HEALTH
              </p>
              <div className="flex items-end gap-3">
                <span className="text-headline-md font-headline-md font-bold text-on-surface leading-none flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">verified_user</span>
                  Optimal
                </span>
              </div>
              <p className="text-on-surface-variant text-label-sm mt-2">All endpoints secured</p>
            </Card>
          </div>

          {nodes.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {nodes.map((node) => (
                <Card key={node.id} variant="glass" hover className="border border-white/10 p-6 relative overflow-hidden">
                  <div className={`absolute top-0 left-0 bottom-0 w-1 ${
                    node.status === 'Online' ? 'bg-primary' : 'bg-on-surface-variant/50'
                  }`} />

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
                          }`} />
                          <span className="font-label-md text-label-md text-on-surface-variant">{node.status}</span>
                        </div>
                      </div>
                    </div>

                    <div className="relative">
                      <Button
                        variant="ghost"
                        size="sm"
                        icon="more_vert"
                        onClick={() => setOpenDropdown(openDropdown === node.id ? null : node.id)}
                      />
                      {openDropdown === node.id && (
                        <div className="absolute right-0 mt-2 w-48 bg-surface-container rounded-md shadow-lg border border-white/10 z-20 overflow-hidden">
                          <button
                            className="w-full text-left px-4 py-2 text-sm text-error hover:bg-error/10 flex items-center gap-2 transition-colors cursor-pointer"
                            onClick={() => {
                              handleSendCommand(node.id, 'REVOKE');
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
                  </div>

                  <div className="mt-6 flex gap-3">
                    <Button
                      variant="secondary"
                      size="sm"
                      className="flex-1"
                      onClick={() => handleConfigure(node.id, node.name)}
                    >
                      Configure
                    </Button>
                    {node.status !== 'Online' && (
                      <Button
                        variant="primary"
                        size="sm"
                        icon="power_settings_new"
                        className="flex-1"
                        onClick={() => handleSendCommand(node.id, 'WAKE')}
                      >
                        Wake
                      </Button>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="border border-white/10 p-12 flex flex-col items-center justify-center text-center">
              <EmptyState
                icon="dns"
                title="No Nodes Connected"
                description="You haven't connected any devices to your ShadowDrive network yet. Run the desktop client and log in to automatically register your first device."
              />
            </Card>
          )}
        </div>
      </div>

      <Modal
        open={isConfigureOpen}
        onClose={() => setIsConfigureOpen(false)}
        title="Configure Device"
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsConfigureOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleSaveConfiguration}>Save Changes</Button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-label-md text-on-surface-variant mb-2">Device Name</label>
            <input
              type="text"
              value={configureNodeName}
              onChange={(e) => setConfigureNodeName(e.target.value)}
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
      </Modal>
    </div>
  );
}
