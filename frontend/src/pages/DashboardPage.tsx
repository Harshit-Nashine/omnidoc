import React, { useEffect, useState } from 'react';
import { useAuth } from '../AuthContext';
import { getDocuments, getHealth } from '../api';
import { FileText, CheckCircle, AlertTriangle, Clock, Database } from 'lucide-react';
import { Link } from 'react-router-dom';

const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getDocuments(), getHealth()])
      .then(([docs, h]) => {
        setDocuments(docs);
        setHealth(h);
      })
      .finally(() => setLoading(false));
  }, []);

  const stats = {
    total: documents.length,
    completed: documents.filter(d => d.processing_status === 'completed').length,
    flagged: documents.filter(d => d.compliance_status === 'flagged').length,
    pending: documents.filter(d => d.processing_status === 'uploaded' || d.processing_status === 'processing').length,
  };

  const statusColor = (status: string) => {
    const colors: Record<string, string> = {
      completed: 'text-green-400 bg-green-400/10',
      processed: 'text-blue-400 bg-blue-400/10',
      processing: 'text-yellow-400 bg-yellow-400/10',
      uploaded: 'text-slate-400 bg-slate-400/10',
      failed: 'text-red-400 bg-red-400/10',
      embedding: 'text-purple-400 bg-purple-400/10',
    };
    return colors[status] || 'text-slate-400 bg-slate-400/10';
  };

  const complianceColor = (status: string) => {
    const colors: Record<string, string> = {
      clean: 'text-green-400',
      approved: 'text-blue-400',
      flagged: 'text-yellow-400',
      quarantined: 'text-red-400',
      pending: 'text-slate-400',
    };
    return colors[status] || 'text-slate-400';
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">
          Welcome back, {user?.full_name || user?.email} 👋
        </h1>
        <p className="text-slate-400 mt-1">
          Role: <span className="text-blue-400 capitalize">{user?.role}</span>
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Total Documents', value: stats.total, icon: FileText, color: 'blue' },
          { label: 'In Knowledge Base', value: stats.completed, icon: CheckCircle, color: 'green' },
          { label: 'Flagged for Review', value: stats.flagged, icon: AlertTriangle, color: 'yellow' },
          { label: 'Processing', value: stats.pending, icon: Clock, color: 'purple' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
            <div className={`inline-flex p-2 rounded-xl bg-${color}-500/10 mb-3`}>
              <Icon className={`w-5 h-5 text-${color}-400`} />
            </div>
            <div className="text-2xl font-bold text-white">{value}</div>
            <div className="text-sm text-slate-400 mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Database health */}
      {health && (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5 mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-5 h-5 text-slate-400" />
            <h2 className="font-semibold text-white">System Health</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(health.databases).map(([db, status]) => (
              <div key={db} className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${status === 'healthy' ? 'bg-green-400' : 'bg-red-400'}`} />
                <span className="text-slate-300 capitalize text-sm">{db}</span>
                <span className={`text-xs ${status === 'healthy' ? 'text-green-400' : 'text-red-400'}`}>
                  {status as string}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent documents */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl">
        <div className="flex items-center justify-between p-5 border-b border-slate-700/50">
          <h2 className="font-semibold text-white">Recent Documents</h2>
          <Link to="/upload" className="text-sm text-blue-400 hover:text-blue-300 transition">
            + Upload New
          </Link>
        </div>

        {loading ? (
          <div className="p-8 text-center text-slate-500">Loading...</div>
        ) : documents.length === 0 ? (
          <div className="p-8 text-center">
            <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400">No documents yet</p>
            <Link to="/upload" className="text-blue-400 text-sm hover:underline mt-1 inline-block">
              Upload your first document
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-slate-700/50">
            {documents.slice(0, 10).map((doc) => (
              <div key={doc.id} className="flex items-center justify-between p-4 hover:bg-slate-700/20 transition">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 bg-blue-500/10 rounded-xl flex items-center justify-center">
                    <FileText className="w-4 h-4 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-white text-sm font-medium truncate max-w-xs">
                      {doc.original_filename}
                    </p>
                    <p className="text-slate-500 text-xs capitalize">
                      {doc.file_type} · {(doc.file_size_bytes / 1024).toFixed(1)} KB
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs px-2 py-1 rounded-lg capitalize ${complianceColor(doc.compliance_status)}`}>
                    {doc.compliance_status}
                  </span>
                  <span className={`text-xs px-2 py-1 rounded-lg capitalize ${statusColor(doc.processing_status)}`}>
                    {doc.processing_status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardPage;