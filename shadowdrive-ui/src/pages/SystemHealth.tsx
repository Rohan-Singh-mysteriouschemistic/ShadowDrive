import { useTelemetry } from '../hooks/useTelemetry';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Button from '../components/Button';

export default function SystemHealth() {
  const { data, isLoading, error } = useTelemetry();
  const metrics = data?.metrics ?? [];

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      <PageHeader
        icon="monitoring"
        title="System Health"
        iconColor="text-primary"
        actions={
          <Button variant="ghost" size="sm" icon="troubleshoot" onClick={() => alert("Running diagnostics...")}>
            Run Diagnostics
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto p-margin-desktop z-10 flex flex-col items-center">
        <div className="w-full max-w-container-max flex flex-col gap-8">
          {error && (
            <div className="p-4 rounded-xl text-center text-red-500 font-code-sm border border-red-500/20 bg-red-500/5">
              Telemetry endpoint unreachable. Showing fallback data.
            </div>
          )}

          <Card variant="glass" glow="primary" className="p-8 flex flex-col md:flex-row items-center justify-between gap-6 relative overflow-hidden bg-primary/5 border border-primary/30 rounded-2xl">
            <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-transparent pointer-events-none" />
            <div className="flex items-center gap-6 relative z-10">
              <div className="w-20 h-20 bg-primary/20 rounded-full flex items-center justify-center border border-primary/30">
                <span className="material-symbols-outlined text-5xl text-primary animate-pulse">
                  check_circle
                </span>
              </div>
              <div>
                <h2 className="font-display-sm text-display-sm text-on-surface mb-1 font-bold">
                  All Systems Operational
                </h2>
                <p className="font-body-md text-body-md text-on-surface-variant">
                  Your ShadowDrive network is stable and fully synchronized.
                </p>
              </div>
            </div>
            <div className="relative z-10 flex gap-4">
              {isLoading ? (
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  <span className="font-code-sm text-on-surface-variant">Fetching...</span>
                </div>
              ) : (
                <>
                  <div className="text-center">
                    <div className="font-display-md text-display-md text-on-surface font-mono">
                      {data?.syncRate ?? 0}<span className="text-sm text-on-surface-variant">%</span>
                    </div>
                    <div className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">
                      Global Sync Rate
                    </div>
                  </div>
                  <div className="w-px bg-white/10 mx-2" />
                  <div className="text-center">
                    <div className="font-display-md text-display-md text-on-surface font-mono">
                      {data?.totalNodes ?? 0}
                    </div>
                    <div className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">
                      Total Nodes
                    </div>
                  </div>
                </>
              )}
            </div>
          </Card>

          {metrics.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {metrics.map((metric) => (
                <Card key={metric.id} variant="glass" hover className="border border-white/10 p-6 relative overflow-hidden group cursor-pointer" onClick={() => alert(`View details for ${metric.name}`)}>
                  <div className={`absolute top-0 left-0 right-0 h-1 ${
                    metric.status === 'Healthy' ? 'bg-primary' :
                    metric.status === 'Warning' ? 'bg-yellow-500' : 'bg-error'
                  }`} />
                  <h3 className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider mb-2">
                    {metric.name}
                  </h3>
                  <div className="flex items-end justify-between">
                    <span className="font-headline-lg-mobile md:text-headline-lg text-on-surface font-bold">
                      {metric.value}
                    </span>
                    <div className="flex items-end gap-1 h-8 opacity-50 group-hover:opacity-100 transition-opacity">
                      {metric.history.map((val: number, i: number) => (
                        <div
                          key={i}
                          className={`w-1.5 rounded-t-sm ${
                            metric.status === 'Warning' ? 'bg-yellow-500' : 'bg-primary'
                          }`}
                          style={{ height: `${(val / Math.max(...metric.history)) * 100}%` }}
                        />
                      ))}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="border border-white/10 p-12 flex flex-col items-center justify-center text-center">
              <span className="material-symbols-outlined text-4xl text-on-surface-variant mb-4">
                monitoring
              </span>
              <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold mb-2">
                No Metrics Data
              </h3>
              <p className="font-code-sm text-on-surface-variant max-w-md">
                Detailed metrics are currently unavailable or there are no active connections to report on.
              </p>
            </Card>
          )}

          <Card className="border border-white/10 overflow-hidden flex flex-col h-96">
            <div className="bg-surface-container-high p-4 border-b border-white/5 flex justify-between items-center">
              <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold">
                Network Throughput (24h)
              </h3>
              <div className="flex gap-2">
                <button className="px-3 py-1 rounded bg-white/10 text-on-surface font-label-md text-label-md cursor-pointer hover:bg-white/20 transition-colors">
                  1D
                </button>
                <button className="px-3 py-1 rounded text-on-surface-variant font-label-md text-label-md cursor-pointer hover:bg-white/5 transition-colors">
                  1W
                </button>
                <button className="px-3 py-1 rounded text-on-surface-variant font-label-md text-label-md cursor-pointer hover:bg-white/5 transition-colors">
                  1M
                </button>
              </div>
            </div>
            <div className="flex-1 p-6 relative flex items-center justify-center bg-black/20">
              <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiPjxkZWZzPjxsaW5lYXJHcmFkaWVudCBpZD0iZyIgeDE9IjAlIiB5MT0iMTAwJSIgeDI9IjAlIiB5Mj0iMCUiPjxzdG9wIG9mZnNldD0iMCUiIHN0b3AtY29sb3I9InRyYW5zcGFyZW50Ii8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSJyZ2JhKDE2LCAxODUsIDEyOSwgMC4yKSIvPjwvbGluZWFyR3JhZGllbnQ+PC9kZWZzPjxwYXRoIGQ9Ik0wLDMwMCBMMTAwLDI1MCBMMjAwLDI4MCBMMzAwLDIwMCBMNDAwLDIyMCBMNTAwLDE1MCBMNjAwLDE4MCBMNzAwLDEwMCBMODAwLDEzMCBMOTAwLDUwIEwxMDAwLDgwIEwxMjAwLDMwIEwxMjAwLDQwMCBMMCw0MDBaIiBmaWxsPSJ1cmwoI2cpIi8+PHBhdGggZD0iTTAsMzAwIEwxMDAsMjUwIEwyMDAsMjgwIEwzMDAsMjAwIEw0MD0sMjIwIEw1MDAsMTUwIEw2MDAsMTgwIEw3MDAsMTAwIEw4MDAsMTMwIEw5MDAsNTAgTDEwMDAsODAgTDEyMDAsMzAiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzEwYjk4MSIgc3Ryb2tlLXdpZHRoPSIyIi8+PC9zdmc+')] bg-cover bg-bottom opacity-70" />
              <div className="absolute inset-0 flex flex-col justify-between p-6 pointer-events-none">
                <div className="w-full border-b border-white/5 border-dashed" />
                <div className="w-full border-b border-white/5 border-dashed" />
                <div className="w-full border-b border-white/5 border-dashed" />
                <div className="w-full border-b border-white/5 border-dashed" />
                <div className="w-full border-b border-white/5 border-dashed" />
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
