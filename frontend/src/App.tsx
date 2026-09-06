// DataFusionX Master App Router (Updated for M13 AI Data Quality /data-quality)
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { DashboardPage } from './pages/DashboardPage';
import { DataSourcesListPage } from './pages/DataSourcesListPage';
import { DataSourceDetailPage } from './pages/DataSourceDetailPage';
import { DataProfilePage } from './pages/DataProfilePage';
import { PipelinesListPage } from './pages/PipelinesListPage';
import { PipelineConfigPage } from './pages/PipelineConfigPage';
import { VisualPipelineBuilderPage } from './pages/VisualPipelineBuilderPage';
import { PipelineExecutionsPage } from './pages/PipelineExecutionsPage';
import { WarehouseDashboardPage } from './pages/WarehouseDashboardPage';
import { WarehouseTableDetailPage } from './pages/WarehouseTableDetailPage';
import { TransformedDatasetsPage } from './pages/TransformedDatasetsPage';
import { AICopilotPage } from './pages/AICopilotPage';
import { AIDataQualityPage } from './pages/AIDataQualityPage';
import { PipelineSchedulesPage } from './pages/PipelineSchedulesPage';

import { MonitoringDashboardPage } from './pages/MonitoringDashboardPage';




const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = localStorage.getItem('datafusionx_token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/data-sources"
          element={
            <ProtectedRoute>
              <DataSourcesListPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/datasets"
          element={
            <ProtectedRoute>
              <DataSourcesListPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/data-sources/:id"
          element={
            <ProtectedRoute>
              <DataSourceDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/datasets/:id"
          element={
            <ProtectedRoute>
              <DataSourceDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/datasets/:id/profile"
          element={
            <ProtectedRoute>
              <DataProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/data-sources/:id/profile"
          element={
            <ProtectedRoute>
              <DataProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pipelines"
          element={
            <ProtectedRoute>
              <PipelinesListPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pipelines/:id/visual"
          element={
            <ProtectedRoute>
              <VisualPipelineBuilderPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pipelines/:id"
          element={
            <ProtectedRoute>
              <PipelineConfigPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pipelines/:id/executions"
          element={
            <ProtectedRoute>
              <PipelineExecutionsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/schedules"
          element={
            <ProtectedRoute>
              <PipelineSchedulesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/transformed-datasets"
          element={
            <ProtectedRoute>
              <TransformedDatasetsPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/monitoring"
          element={
            <ProtectedRoute>
              <MonitoringDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ai-copilot"
          element={
            <ProtectedRoute>
              <AICopilotPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/data-quality"
          element={
            <ProtectedRoute>
              <AIDataQualityPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/warehouse"
          element={
            <ProtectedRoute>
              <WarehouseDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/warehouse/:table"
          element={
            <ProtectedRoute>
              <WarehouseTableDetailPage />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Router>
  );
};

export default App;
