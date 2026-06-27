import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import QueryPage from './pages/QueryPage';
import AuditPage from './pages/AuditPage';
import DocumentsPage from './pages/DocumentsPage';
import ErrorBoundary from './components/ErrorBoundary';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token, loading } = useAuth();
  if (loading) return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
  if (!token) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
};

const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={
            <ProtectedRoute><ErrorBoundary><DashboardPage /></ErrorBoundary></ProtectedRoute>
          } />
          <Route path="/upload" element={
            <ProtectedRoute><ErrorBoundary><UploadPage /></ErrorBoundary></ProtectedRoute>
          } />
          <Route path="/query" element={
            <ProtectedRoute><ErrorBoundary><QueryPage /></ErrorBoundary></ProtectedRoute>
          } />
          <Route path="/audit" element={
            <ProtectedRoute><ErrorBoundary><AuditPage /></ErrorBoundary></ProtectedRoute>
          } />
          <Route path="/documents" element={
            <ProtectedRoute><ErrorBoundary><DocumentsPage /></ErrorBoundary></ProtectedRoute>
          } />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;