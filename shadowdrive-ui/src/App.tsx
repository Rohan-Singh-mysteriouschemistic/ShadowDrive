import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LandingPage from './LandingPage'
import AuthScreen from './AuthScreen'
import FileExplorer from './FileExplorer'
import VersionHistory from './VersionHistory'
import ConflictResolution from './ConflictResolution'
import NodeManagement from './NodeManagement'
import NodeDeployment from './NodeDeployment'
import SystemHealth from './SystemHealth'
import NetworkActivity from './NetworkActivity'
import DashboardLayout from './DashboardLayout'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/auth" element={<AuthScreen />} />
        <Route path="/vault" element={<DashboardLayout><FileExplorer /></DashboardLayout>} />
        <Route path="/vault/history" element={<DashboardLayout><VersionHistory /></DashboardLayout>} />
        <Route path="/conflicts" element={<DashboardLayout><ConflictResolution /></DashboardLayout>} />
        <Route path="/nodes" element={<DashboardLayout><NodeManagement /></DashboardLayout>} />
        <Route path="/nodes/deploy" element={<DashboardLayout><NodeDeployment /></DashboardLayout>} />
        <Route path="/health" element={<DashboardLayout><SystemHealth /></DashboardLayout>} />
        <Route path="/network" element={<DashboardLayout><NetworkActivity /></DashboardLayout>} />
      </Routes>
    </BrowserRouter>
  )
}
