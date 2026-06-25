import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import { Agentation } from 'agentation';

const LandingPage = lazy(() => import('./pages/LandingPage'));
const AuthScreen = lazy(() => import('./pages/AuthScreen'));
const FileExplorer = lazy(() => import('./pages/FileExplorer'));
const VersionHistory = lazy(() => import('./pages/VersionHistory'));
const ConflictResolution = lazy(() => import('./pages/ConflictResolution'));
const NodeManagement = lazy(() => import('./pages/NodeManagement'));
const NodeDeployment = lazy(() => import('./pages/NodeDeployment'));
const SystemHealth = lazy(() => import('./pages/SystemHealth'));
const NetworkActivity = lazy(() => import('./pages/NetworkActivity'));
const TransferQueue = lazy(() => import('./pages/TransferQueue'));
const DashboardLayout = lazy(() => import('./layouts/DashboardLayout'));

function DashboardFallback() {
  return (
    <div className="flex-1 flex items-center justify-center bg-surface-container-lowest">
      <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function LoadingFallback() {
  return (
    <div className="w-full h-screen flex items-center justify-center bg-background">
      <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<LoadingFallback />}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/auth" element={<AuthScreen />} />
            <Route path="/vault" element={<Suspense fallback={<DashboardFallback />}><DashboardLayout><FileExplorer /></DashboardLayout></Suspense>} />
            <Route path="/vault/history" element={<Suspense fallback={<DashboardFallback />}><DashboardLayout><VersionHistory /></DashboardLayout></Suspense>} />
            <Route path="/conflicts" element={<Suspense fallback={<DashboardFallback />}><DashboardLayout><ConflictResolution /></DashboardLayout></Suspense>} />
            <Route path="/nodes" element={<Suspense fallback={<DashboardFallback />}><DashboardLayout><NodeManagement /></DashboardLayout></Suspense>} />
            <Route path="/nodes/deploy" element={<Suspense fallback={<DashboardFallback />}><DashboardLayout><NodeDeployment /></DashboardLayout></Suspense>} />
            <Route path="/health" element={<Suspense fallback={<DashboardFallback />}><DashboardLayout><SystemHealth /></DashboardLayout></Suspense>} />
            <Route path="/network" element={<Suspense fallback={<DashboardFallback />}><DashboardLayout><NetworkActivity /></DashboardLayout></Suspense>} />
            <Route path="/transfers" element={<Suspense fallback={<DashboardFallback />}><DashboardLayout><TransferQueue /></DashboardLayout></Suspense>} />
          </Routes>
        </Suspense>
      </BrowserRouter>
      {import.meta.env.DEV && <Agentation />}
    </QueryClientProvider>
  );
}
