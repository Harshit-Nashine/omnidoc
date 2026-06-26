import React, { useEffect, useState } from 'react';
import { getAuditLog } from '../api';
import { Shield, FileText, CheckCircle, AlertTriangle, Upload, Brain } from 'lucide-react';

const eventIcons: Record<string, any> = {
  'document.uploaded': Upload,
  'document.processed': FileText,
  'document.approved': CheckCircle,
  'document.flagged': AlertTriangle,
  'document.embedded': Brain,
};

const eventColors: Record<string, string> = {
  'document.uploaded': 'text-blue-400 bg-blue-400/10',
  'document.processed': 'text-green-400 bg-green-400/10',
  'document.approved': 'text-purple-400 bg-purple-400/10',
  'document.flagged': 'text-yellow-400 bg-yellow-400/10',
  'document.embedded': 'text-indigo-400 bg-indigo-400/10',
};

const AuditPage: React.FC = () => {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getAuditLog()
      .then(setEntries)
      .catch(err => setError(err.response?.data?.detail || 'Failed to load audit log'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Shield className="w-6 h-6 text-blue-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">Audit Log</h1>
          <p className="text-slate-400 text-sm">Immutable record of all document events</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm mb-6">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-slate-500">Loading audit log...</div>
      ) : entries.length === 0 ? (
        <div className="text-center py-12">
          <Shield className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">No audit events yet</p>
        </div>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-6 top-0 bottom-0 w-px bg-slate-700/50" />

          <div className="space-y-4">
            {entries.map((entry, i) => {
              const Icon = eventIcons[entry.event_type] || FileText;
              const colorClass = eventColors[entry.event_type] || 'text-slate-400 bg-slate-400/10';
              const payload = typeof entry.payload === 'string'
                ? JSON.parse(entry.payload)
                : entry.payload;

              return (
                <div key={entry.id} className="flex gap-4 pl-2">
                  {/* Icon */}
                  <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 z-10 ${colorClass}`}>
                    <Icon className="w-4 h-4" />
                  </div>

                  {/* Content */}
                  <div className="flex-1 bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 mb-0">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <span className="text-white text-sm font-medium capitalize">
                          {entry.event_type.replace('.', ' → ')}
                        </span>
                        {payload?.filename && (
                          <p className="text-slate-400 text-xs mt-0.5">{payload.filename}</p>
                        )}
                        {payload?.compliance_status && (
                          <p className="text-slate-500 text-xs mt-0.5">
                            Compliance: <span className="capitalize">{payload.compliance_status}</span>
                          </p>
                        )}
                      </div>
                      <span className="text-slate-600 text-xs shrink-0">
                        {new Date(entry.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div className="flex gap-4 mt-2">
                      {entry.document_id && (
                        <span className="text-xs text-slate-600">
                          Doc: {entry.document_id.slice(0, 8)}...
                        </span>
                      )}
                      {entry.user_id && (
                        <span className="text-xs text-slate-600">
                          User: {entry.user_id.slice(0, 8)}...
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default AuditPage;