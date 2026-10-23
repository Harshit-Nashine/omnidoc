import React, { useEffect, useState } from 'react';
import { ExternalLink, Server, Database, BarChart3, Zap, CheckCircle, XCircle, Clock } from 'lucide-react';

const DemoLaunchpad: React.FC = () => {
  const [services, setServices] = useState<any[]>([
    {
      name: 'OmniDoc Frontend',
      url: 'http://localhost:3001',
      status: 'checking',
      icon: '🎨',
      description: 'Main application UI'
    },
    {
      name: 'API Swagger Docs',
      url: '#',
      status: 'checking',
      icon: '📚',
      description: 'All API endpoints',
      onClick: true,
    },
    {
      name: 'Grafana Dashboards',
      url: 'http://localhost:3000',
      status: 'checking',
      icon: '📊',
      description: 'Real-time metrics'
    },
    {
      name: 'Prometheus Metrics',
      url: 'http://localhost:9090',
      status: 'checking',
      icon: '📈',
      description: 'Raw metrics data'
    },
    {
      name: 'MinIO Console',
      url: 'http://localhost:9001',
      status: 'checking',
      icon: '🗂️',
      description: 'File storage'
    },
    
  ]);

  const [credentials, setCredentials] = useState({
    showPasswords: false,
  });

  useEffect(() => {
    // Check all services
    services.forEach((service, idx) => {
      fetch(service.url, { mode: 'no-cors' })
        .then(() => {
          setServices(prev => {
            const updated = [...prev];
            updated[idx].status = 'healthy';
            return updated;
          });
        })
        .catch(() => {
          setServices(prev => {
            const updated = [...prev];
            updated[idx].status = 'down';
            return updated;
          });
        });
    });
  }, []);

  const statusIcon = (status: string) => {
    if (status === 'healthy') return <CheckCircle className="w-5 h-5 text-green-400" />;
    if (status === 'down') return <XCircle className="w-5 h-5 text-red-400" />;
    return <Clock className="w-5 h-5 text-yellow-400 animate-spin" />;
  };

  const credentialsList = [
    { service: 'OmniDoc Login', email: 'admin@testcompany.com', password: 'SecurePass123' },
    { service: 'Grafana', email: 'admin', password: 'admin' },
    { service: 'MinIO', email: 'omnidoc_minio', password: 'MinIO@2025OK' },
    { service: 'PostgreSQL', email: 'omnidoc_user', password: 'OmniDoc2025Secure' },
    { service: 'MongoDB', email: 'omnidoc_mongo', password: 'OmniDoc2025Secure' },
    { service: 'Redis', email: 'N/A', password: 'OmniDoc2025Secure' },
  ];
  const openSwaggerWithAuth = () => {
    const token = localStorage.getItem('access_token') || '';
    
    // If no token, auto-login first
    if (!token) {
      fetch('http://localhost:8000/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'admin@testcompany.com',
          password: 'SecurePass123'
        })
      })
      .then(r => r.json())
      .then(data => {
        localStorage.setItem('access_token', data.access_token);
        // Open Swagger with token copied to clipboard for easy paste
        navigator.clipboard.writeText(`Bearer ${data.access_token}`);
        window.open('http://localhost:8000/docs', '_blank');
        alert('Token copied to clipboard! Paste in Swagger Authorize button.');
      })
      .catch(() => window.open('http://localhost:8000/docs', '_blank'));
    } else {
      navigator.clipboard.writeText(`Bearer ${token}`);
      window.open('http://localhost:8000/docs', '_blank');
      alert('Token copied to clipboard! Paste in Swagger Authorize button.');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-8">
      <div className="max-w-7xl mx-auto">
        
        {/* Header */}
        <div className="mb-12">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-4xl font-bold text-white">OmniDoc Demo Launchpad</h1>
              <p className="text-slate-400 mt-1">All services, credentials, and links in one place</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-8">
          
          {/* Services Grid */}
          <div className="col-span-2">
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <Server className="w-5 h-5 text-blue-400" />
              Services Status
            </h2>
            <div className="space-y-3">
              {services.map((service, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    if (service.onClick) {
                      openSwaggerWithAuth();
                    } else {
                      window.open(service.url, '_blank');
                    }
                  }}
                  className="block bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 hover:bg-slate-700/50 hover:border-blue-500/50 transition group cursor-pointer"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{service.icon}</span>
                      <div>
                        <h3 className="text-white font-medium group-hover:text-blue-400 transition">
                          {service.name}
                        </h3>
                        <p className="text-slate-500 text-sm">{service.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {statusIcon(service.status)}
                      <ExternalLink className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Credentials Sidebar */}
          <div>
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <Database className="w-5 h-5 text-green-400" />
              Credentials
            </h2>
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
              <button
                onClick={() => setCredentials({ ...credentials, showPasswords: !credentials.showPasswords })}
                className="text-xs text-slate-400 hover:text-slate-300 mb-4 underline"
              >
                {credentials.showPasswords ? 'Hide' : 'Show'} passwords
              </button>
              <div className="space-y-4 max-h-96 overflow-y-auto">
                {credentialsList.map((cred, idx) => (
                  <div key={idx} className="border-b border-slate-700/30 pb-3 last:border-0">
                    <p className="text-white text-sm font-medium mb-2">{cred.service}</p>
                    <div className="space-y-1 text-xs">
                      <div>
                        <p className="text-slate-500">Email/User</p>
                        <p className="text-slate-300 font-mono bg-slate-900/50 p-1.5 rounded text-xs truncate">
                          {cred.email}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500">Password</p>
                        <p className="text-slate-300 font-mono bg-slate-900/50 p-1.5 rounded text-xs truncate">
                          {credentials.showPasswords ? cred.password : '••••••••'}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>

        {/* Quick Start Guide */}
        <div className="mt-12 bg-slate-800/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Quick Start</h2>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <h3 className="text-blue-400 font-medium mb-2">1. Test Upload</h3>
              <p className="text-slate-400">
                Click "OmniDoc Frontend" → Upload → Select a PDF or image → Watch it process
              </p>
            </div>
            <div>
              <h3 className="text-blue-400 font-medium mb-2">2. Query Documents</h3>
              <p className="text-slate-400">
                Approve a clean document → Click "Query" → Ask a question about it
              </p>
            </div>
            <div>
              <h3 className="text-blue-400 font-medium mb-2">3. View Metrics</h3>
              <p className="text-slate-400">
                Click "Grafana Dashboards" → See real-time API and RAG performance
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default DemoLaunchpad;