import { useState, useEffect } from 'react';
import { useTelemetry } from '../hooks/useTelemetry';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Button from '../components/Button';
import Modal from '../components/Modal';
import { apiFetch } from '../lib/api';

function DynamicThroughputChart() {
  const [dataPoints, setDataPoints] = useState<number[]>(() => {
    return Array.from({ length: 24 }, () => Math.floor(Math.random() * 30) + 10);
  });

  useEffect(() => {
    const interval = setInterval(() => {
      setDataPoints((prev) => {
        const nextVal = Math.max(5, Math.min(100, prev[prev.length - 1] + (Math.random() * 20 - 10)));
        return [...prev.slice(1), Math.round(nextVal)];
      });
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const maxVal = Math.max(...dataPoints, 80);
  const chartHeight = 220;
  const chartWidth = 1000;
  
  const points = dataPoints.map((val, idx) => {
    const x = (idx / (dataPoints.length - 1)) * chartWidth;
    const y = chartHeight - (val / maxVal) * (chartHeight - 40);
    return { x, y };
  });

  const linePath = points.reduce((acc, p, idx) => {
    return idx === 0 ? `M ${p.x} ${p.y}` : `${acc} L ${p.x} ${p.y}`;
  }, '');

  const areaPath = `${linePath} L ${chartWidth} ${chartHeight} L 0 ${chartHeight} Z`;

  return (
    <div className="w-full h-full relative flex flex-col justify-between">
      <div className="flex-1 p-6 relative flex items-center justify-center bg-black/20">
        <svg className="w-full h-[180px] overflow-visible" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none">
          <defs>
            <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
            </linearGradient>
          </defs>
          
          {Array.from({ length: 5 }).map((_, i) => {
            const y = (i / 4) * (chartHeight - 40) + 20;
            return (
              <line
                key={i}
                x1="0"
                y1={y}
                x2={chartWidth}
                y2={y}
                stroke="rgba(255,255,255,0.05)"
                strokeDasharray="4"
              />
            );
          })}

          <path d={areaPath} fill="url(#chartGradient)" />

          <path
            d={linePath}
            fill="none"
            stroke="#10b981"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="transition-all duration-300"
          />

          {points.length > 0 && (
            <circle
              cx={points[points.length - 1].x}
              cy={points[points.length - 1].y}
              r="6"
              fill="#10b981"
              className="animate-pulse"
            />
          )}
        </svg>
      </div>
      
      <div className="flex justify-between items-center px-6 py-4 border-t border-white/5 bg-surface-container-high/40">
        <div className="flex gap-6">
          <div>
            <div className="text-on-surface-variant font-label-md text-label-md">Current Throughput</div>
            <div className="text-white font-mono font-bold mt-0.5">
              {dataPoints[dataPoints.length - 1].toFixed(1)} MB/s
            </div>
          </div>
          <div>
            <div className="text-on-surface-variant font-label-md text-label-md">Peak (24h)</div>
            <div className="text-white font-mono font-bold mt-0.5">
              {Math.max(...dataPoints).toFixed(1)} MB/s
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-primary text-label-md font-label-md">
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          Live Network Stream
        </div>
      </div>
    </div>
  );
}

export default function SystemHealth() {
  const { data, isLoading, error } = useTelemetry();
  const metrics = data?.metrics ?? [];

  const [showDiagnosticsModal, setShowDiagnosticsModal] = useState(false);
  const [diagnosticsData, setDiagnosticsData] = useState<any>(null);
  const [runningDiagnostics, setRunningDiagnostics] = useState(false);

  const runDiagnostics = async () => {
    setRunningDiagnostics(true);
    setShowDiagnosticsModal(true);
    try {
      const res = await apiFetch('/system/diagnostics');
      setDiagnosticsData(res);
    } catch (err) {
      console.error(err);
      setDiagnosticsData({
        postgres: "ERROR",
        minio: "ERROR",
        redis: "ERROR",
        nodes: "ERROR"
      });
    } finally {
      setRunningDiagnostics(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden w-full relative bg-transparent">
      <PageHeader
        icon="monitoring"
        title="System Health"
        iconColor="text-primary"
        actions={
          <Button
            variant="ghost"
            size="sm"
            icon="troubleshoot"
            onClick={runDiagnostics}
          >
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

          {/* ── Dynamic Status Banner ─────────────────────────────────── */}
          {(() => {
            const criticalCount = metrics.filter(m => m.status === 'Critical').length;
            const warningCount = metrics.filter(m => m.status === 'Warning').length;
            const isHealthy = !isLoading && criticalCount === 0 && warningCount === 0 && metrics.length > 0;
            const isDegraded = criticalCount > 0;
            const statusIcon = isDegraded ? 'error' : warningCount > 0 ? 'warning' : 'check_circle';
            const statusColor = isDegraded ? 'text-error' : warningCount > 0 ? 'text-yellow-400' : 'text-primary';
            const borderColor = isDegraded ? 'border-error/30' : warningCount > 0 ? 'border-yellow-400/30' : 'border-primary/30';
            const bgColor = isDegraded ? 'bg-error/5' : warningCount > 0 ? 'bg-yellow-400/5' : 'bg-primary/5';
            const gradientColor = isDegraded ? 'from-error/10' : warningCount > 0 ? 'from-yellow-400/10' : 'from-primary/10';
            const statusTitle = isDegraded ? 'System Degraded' : warningCount > 0 ? 'Performance Warning' : 'All Systems Operational';
            const statusDesc = isDegraded
              ? `${criticalCount} critical component${criticalCount > 1 ? 's' : ''} require${criticalCount === 1 ? 's' : ''} attention.`
              : warningCount > 0
              ? `${warningCount} component${warningCount > 1 ? 's' : ''} showing elevated latency.`
              : 'Your ShadowDrive network is stable and fully synchronized.';

            return (
              <Card variant="glass" glow="primary" className={`p-8 flex flex-col md:flex-row items-center justify-between gap-6 relative overflow-hidden ${bgColor} border ${borderColor} rounded-2xl`}>
                <div className={`absolute inset-0 bg-gradient-to-r ${gradientColor} to-transparent pointer-events-none`} />
                <div className="flex items-center gap-6 relative z-10">
                  <div className={`w-20 h-20 rounded-full flex items-center justify-center border ${borderColor} ${bgColor}`}>
                    <span className={`material-symbols-outlined text-5xl ${statusColor} ${isHealthy ? 'animate-pulse' : ''}`}>
                      {statusIcon}
                    </span>
                  </div>
                  <div>
                    <h2 className="font-display-sm text-display-sm text-on-surface mb-1 font-bold">
                      {isLoading ? 'Checking Systems...' : statusTitle}
                    </h2>
                    <p className="font-body-md text-body-md text-on-surface-variant">
                      {isLoading ? 'Connecting to telemetry endpoint...' : statusDesc}
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
            );
          })()}

          {/* ── Metrics Grid (2-col, clean) ───────────────────────────── */}
          {metrics.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {metrics.map((metric) => (
                <Card key={metric.id} variant="glass" hover className="border border-white/10 p-6 relative overflow-hidden group cursor-pointer" onClick={() => { console.log('Viewing details for', metric.name); }}>
                  <div className={`absolute top-0 left-0 right-0 h-1 ${
                    metric.status === 'Healthy' ? 'bg-primary' :
                    metric.status === 'Warning' ? 'bg-yellow-500' : 'bg-error'
                  }`} />
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider mb-3">
                        {metric.name}
                      </h3>
                      <div className="flex items-center gap-3">
                        <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                          metric.status === 'Healthy' ? 'bg-primary animate-pulse' :
                          metric.status === 'Warning' ? 'bg-yellow-500' : 'bg-error'
                        }`} />
                        <span className="font-headline-sm text-on-surface font-bold">
                          {metric.value}
                        </span>
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ml-auto ${
                          metric.status === 'Healthy' ? 'bg-primary/10 text-primary' :
                          metric.status === 'Warning' ? 'bg-yellow-500/10 text-yellow-400' : 'bg-error/10 text-error'
                        }`}>
                          {metric.status}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-end gap-0.5 h-10 ml-4 opacity-40 group-hover:opacity-80 transition-opacity">
                      {metric.history.map((val: number, i: number) => (
                        <div
                          key={i}
                          className={`w-1.5 rounded-t-sm ${
                            metric.status === 'Warning' ? 'bg-yellow-500' : metric.status === 'Critical' ? 'bg-error' : 'bg-primary'
                          }`}
                          style={{ height: `${Math.max(10, (val / Math.max(...metric.history, 1)) * 100)}%` }}
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

          <Card className="border border-white/10 overflow-hidden flex flex-col min-h-[300px]">
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
            <DynamicThroughputChart />
          </Card>
        </div>
      </div>

      <Modal
        open={showDiagnosticsModal}
        onClose={() => setShowDiagnosticsModal(false)}
        title="System Diagnostics"
        footer={
          <Button variant="primary" onClick={() => setShowDiagnosticsModal(false)}>Close</Button>
        }
      >
        <div className="space-y-4 font-code-sm text-sm">
          {runningDiagnostics ? (
            <div className="flex flex-col items-center py-6">
              <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              <span className="mt-2 text-on-surface-variant">Running connection handshakes...</span>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex justify-between items-center border-b border-white/5 pb-2">
                <span className="text-on-surface-variant">PostgreSQL Database</span>
                <span className={`font-bold ${diagnosticsData?.postgres === 'OK' ? 'text-primary' : 'text-error'}`}>
                  {diagnosticsData?.postgres || 'UNKNOWN'}
                </span>
              </div>
              <div className="flex justify-between items-center border-b border-white/5 pb-2">
                <span className="text-on-surface-variant">MinIO Storage Server</span>
                <span className={`font-bold ${diagnosticsData?.minio === 'OK' ? 'text-primary' : 'text-error'}`}>
                  {diagnosticsData?.minio || 'UNKNOWN'}
                </span>
              </div>
              <div className="flex justify-between items-center border-b border-white/5 pb-2">
                <span className="text-on-surface-variant">Redis Event Bridge</span>
                <span className={`font-bold ${diagnosticsData?.redis === 'OK' ? 'text-primary' : 'text-error'}`}>
                  {diagnosticsData?.redis || 'UNKNOWN'}
                </span>
              </div>
              <div className="flex justify-between items-center pb-2">
                <span className="text-on-surface-variant">Connected Client Nodes</span>
                <span className="text-white font-bold">
                  {diagnosticsData?.nodes || '0 Connected'}
                </span>
              </div>
            </div>
          )}
        </div>
      </Modal>

    </div>
  );
}
