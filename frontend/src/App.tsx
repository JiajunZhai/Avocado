import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ShellActivityProvider } from './context/ShellActivityContext';
import { ProjectProvider } from './context/ProjectContext';
import { MainLayout } from './layout/MainLayout';
import { Lab } from './pages/Lab';
import { OracleIngestion } from './pages/OracleIngestion';
import { Dashboard } from './pages/Dashboard';
import { ComplianceAdmin } from './pages/ComplianceAdmin';
import { ProviderSettings } from './pages/ProviderSettings';
import { EntryPortal } from './pages/EntryPortal';
import { WorkspaceHub } from './pages/WorkspaceHub';

function App() {
  return (
    <Router>
      <ProjectProvider>
      <ShellActivityProvider>
        <Routes>
          <Route path="/" element={<EntryPortal />} />
          <Route path="/hub" element={<WorkspaceHub />} />
          <Route path="/*" element={
            <MainLayout>
              <Routes>
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="generator" element={<Lab />} />
                <Route path="oracle" element={<OracleIngestion />} />
                <Route path="compliance" element={<ComplianceAdmin />} />
                <Route path="settings/providers" element={<ProviderSettings />} />
                <Route path="*" element={<Navigate to="/hub" replace />} />
              </Routes>
            </MainLayout>
          } />
        </Routes>
      </ShellActivityProvider>
      </ProjectProvider>
    </Router>
  );
}

export default App;
