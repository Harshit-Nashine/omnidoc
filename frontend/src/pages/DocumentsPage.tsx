import React, { useEffect, useState } from 'react';
import { getDocuments, getDocument, approveDocument } from '../api';
import {
  FileText, CheckCircle, AlertTriangle, Clock,
  RefreshCw, ChevronRight, X, Shield
} from 'lucide-react';

const statusColors: Record<string, string> = {
  completed:  'text-green-400 bg-green-400/10 border-green-400/20',
  processed:  'text-blue-400 bg-blue-400/10 border-blue-400/20',
  processing: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
  uploaded:   'text-slate-400 bg-slate-400/10 border-slate-400/20',
  failed:     'text-red-400 bg-red-400/10 border-red-400/20',
  embedding:  'text-purple-400 bg-purple-400/10 border-purple-400/20',
};

const complianceColors: Record<string, string> = {
  clean:       'text-green-400 bg-green-400/10 border-green-400/20',
  approved:    'text-blue-400 bg-blue-400/10 border-blue-400/20',
  flagged:     'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
  quarantined: 'text-red-400 bg-red-400/10 border-red-400/20',
  pending:     'text-slate-400 bg-slate-400/10 border-slate-400/20',
};

const DocumentsPage: React.FC = () => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState('');

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const docs = await getDocuments();
      setDocuments(docs);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleSelect = async (doc: any) => {
    const full = await getDocument(doc.id);
    setSelected(full);
    setError('');
  };

  const handleApprove = async () => {
    if (!selected) return;
    setApproving(true);
    setError('');
    try {
      const updated = await approveDocument(selected.id);
      setSelected(updated);
      setDocuments(prev =>
        prev.map(d => d.id === updated.id ? updated : d)
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Approval failed');
    } finally {
      setApproving(false);
    }
  };

  const filtered = filter === 'all'
    ? documents
    : documents.filter(d =>
        filter === 'flagged'
          ? d.compliance_status === 'flagged'
          : filter === 'completed'
          ? d.processing_status === 'completed'
          : filter === 'pending'
          ? ['uploaded', 'processing'].includes(d.processing_status)
          : true
      );

  const canApprove = selected?.compliance_status === 'clean' &&
                     selected?.processing_status === 'processed';

  return (
    <div className="flex h-full">
      {/* Document list */}
      <div className="w-full lg:w-1/2 border-r border-slate-700/50 flex flex-col">
        {/* Header */}
        <div className="p-5 border-b border-slate-700/50">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold text-white">Documents</h1>
            <button
              onClick={fetchDocuments}
              className="text-slate-400 hover:text-white transition p-2 rounded-xl hover:bg-slate-700/50"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          {/* Filter tabs */}
          <div className="flex gap-2 flex-wrap">
            {[
              { key: 'all', label: 'All', count: documents.length },
              { key: 'completed', label: 'In KB', count: documents.filter(d => d.processing_status === 'completed').length },
              { key: 'flagged', label: 'Flagged', count: documents.filter(d => d.compliance_status === 'flagged').length },
              { key: 'pending', label: 'Processing', count: documents.filter(d => ['uploaded','processing'].includes(d.processing_status)).length },
            ].map(({ key, label, count }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition ${
                  filter === key
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                {label} ({count})
              </button>
            ))}
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto divide-y divide-slate-700/30">
          {loading ? (
            <div className="p-8 text-center text-slate-500">Loading...</div>
          ) : filtered.length === 0 ? (
            <div className="p-8 text-center">
              <FileText className="w-10 h-10 text-slate-600 mx-auto mb-2" />
              <p className="text-slate-500 text-sm">No documents found</p>
            </div>
          ) : (
            filtered.map((doc) => (
              <div
                key={doc.id}
                onClick={() => handleSelect(doc)}
                className={`flex items-center gap-3 p-4 cursor-pointer transition hover:bg-slate-700/20 ${
                  selected?.id === doc.id ? 'bg-blue-600/5 border-l-2 border-blue-500' : ''
                }`}
              >
                <div className="w-9 h-9 bg-blue-500/10 rounded-xl flex items-center justify-center shrink-0">
                  <FileText className="w-4 h-4 text-blue-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm font-medium truncate">
                    {doc.original_filename}
                  </p>
                  <p className="text-slate-500 text-xs capitalize mt-0.5">
                    {doc.file_type} · {(doc.file_size_bytes / 1024).toFixed(1)} KB
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded-lg border capitalize ${complianceColors[doc.compliance_status]}`}>
                    {doc.compliance_status}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-lg border capitalize ${statusColors[doc.processing_status]}`}>
                    {doc.processing_status}
                  </span>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-600 shrink-0" />
              </div>
            ))
          )}
        </div>
      </div>

      {/* Detail panel */}
      <div className="hidden lg:flex flex-1 flex-col">
        {!selected ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <FileText className="w-12 h-12 text-slate-700 mx-auto mb-3" />
              <p className="text-slate-500">Select a document to view details</p>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-6">
            {/* Detail header */}
            <div className="flex items-start justify-between mb-6">
              <div>
                <h2 className="text-white font-semibold text-lg">
                  {selected.original_filename}
                </h2>
                <p className="text-slate-500 text-sm mt-1 capitalize">
                  {selected.file_type} · {(selected.file_size_bytes / 1024).toFixed(1)} KB
                </p>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="text-slate-500 hover:text-white p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Status badges */}
            <div className="flex gap-3 mb-6">
              <span className={`px-3 py-1 rounded-xl text-sm border capitalize ${complianceColors[selected.compliance_status]}`}>
                {selected.compliance_status}
              </span>
              <span className={`px-3 py-1 rounded-xl text-sm border capitalize ${statusColors[selected.processing_status]}`}>
                {selected.processing_status}
              </span>
            </div>

            {/* Details */}
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5 mb-4">
              <h3 className="text-white font-medium mb-4">Document Details</h3>
              <div className="space-y-3">
                {[
                  { label: 'Document ID', value: selected.id },
                  { label: 'Uploaded', value: new Date(selected.created_at).toLocaleString() },
                  { label: 'File Type', value: selected.file_type },
                  { label: 'Size', value: `${(selected.file_size_bytes / 1024).toFixed(1)} KB` },
                  { label: 'Chunk Count', value: selected.chunk_count ?? 'Not embedded' },
                  { label: 'Storage Path', value: selected.storage_path },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between py-2 border-b border-slate-700/30 gap-4">
                    <span className="text-slate-400 text-sm shrink-0">{label}</span>
                    <span className="text-white text-sm text-right truncate max-w-xs">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Error message */}
            {selected.error_message && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-4">
                <p className="text-red-400 text-sm">{selected.error_message}</p>
              </div>
            )}

            {/* API error */}
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-4">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            {/* Approve button */}
            {canApprove && (
              <button
                onClick={handleApprove}
                disabled={approving}
                className="w-full bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-medium py-3 rounded-xl transition flex items-center justify-center gap-2"
              >
                <CheckCircle className="w-5 h-5" />
                {approving ? 'Approving...' : 'Approve for Knowledge Base'}
              </button>
            )}

            {/* Status messages */}
            {selected.compliance_status === 'flagged' && (
              <div className="flex items-center gap-3 bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-4 mt-3">
                <AlertTriangle className="w-5 h-5 text-yellow-400 shrink-0" />
                <div>
                  <p className="text-yellow-400 text-sm font-medium">PII Detected</p>
                  <p className="text-slate-400 text-xs mt-0.5">
                    This document contains sensitive information and has been quarantined.
                  </p>
                </div>
              </div>
            )}

            {selected.compliance_status === 'approved' && (
              <div className="flex items-center gap-3 bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 mt-3">
                <Shield className="w-5 h-5 text-blue-400 shrink-0" />
                <div>
                  <p className="text-blue-400 text-sm font-medium">Approved</p>
                  <p className="text-slate-400 text-xs mt-0.5">
                    Document is approved and {selected.processing_status === 'completed' ? 'in the knowledge base' : 'being embedded'}.
                  </p>
                </div>
              </div>
            )}

            {['uploaded', 'processing', 'embedding'].includes(selected.processing_status) && (
              <div className="flex items-center gap-3 bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 mt-3">
                <Clock className="w-5 h-5 text-blue-400 shrink-0 animate-pulse" />
                <p className="text-blue-400 text-sm">
                  Processing in background...
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentsPage;