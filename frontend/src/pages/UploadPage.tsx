import React, { useState, useCallback, useEffect, useRef } from 'react';
import { uploadDocument, approveDocument, getDocument } from '../api';
import { Upload, CheckCircle, XCircle, Clock, FileText, AlertTriangle } from 'lucide-react';

const UploadPage: React.FC = () => {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [approving, setApproving] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  
// Poll document status every 3 seconds while processing
  useEffect(() => {
    const docId = result?.document?.id;
    const status = result?.document?.processing_status;
    const isProcessing = status === 'uploaded' || status === 'processing' || status === 'embedding';

    if (docId && isProcessing) {
      pollingRef.current = setInterval(async () => {
        try {
          const updated = await getDocument(docId);
          setResult((prev: any) => ({ ...prev, document: updated }));

          // Stop polling when processing is done
          const done = ['processed', 'completed', 'failed'].includes(updated.processing_status);
          if (done && pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
        } catch {
          // Silently ignore polling errors
        }
      }, 3000);
    }

    // Cleanup on unmount or when status changes
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [result?.document?.id, result?.document?.processing_status]); 

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) await handleUpload(file);
  }, []);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) await handleUpload(file);
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError('');
    setResult(null);
    try {
      const data = await uploadDocument(file);
      setResult(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleApprove = async () => {
    if (!result?.document?.id) return;
    setApproving(true);
    try {
      const updated = await approveDocument(result.document.id);
      setResult((prev: any) => ({ ...prev, document: updated }));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Approval failed');
    } finally {
      setApproving(false);
    }
  };

  const canApprove = result?.document?.compliance_status === 'clean' &&
                     result?.document?.processing_status === 'processed';

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-2">Upload Document</h1>
      <p className="text-slate-400 mb-8">
        Supported: PDF, images (JPEG, PNG), audio (MP3, WAV), text files
      </p>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        className={`border-2 border-dashed rounded-2xl p-12 text-center transition-all ${
          dragging
            ? 'border-blue-500 bg-blue-500/5'
            : 'border-slate-700 hover:border-slate-500 bg-slate-800/30'
        }`}
      >
        {uploading ? (
          <div>
            <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-slate-300">Uploading and processing...</p>
          </div>
        ) : (
          <>
            <Upload className="w-12 h-12 text-slate-500 mx-auto mb-4" />
            <p className="text-slate-300 font-medium mb-2">
              Drag and drop a file here
            </p>
            <p className="text-slate-500 text-sm mb-4">or</p>
            <label className="cursor-pointer bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition shadow-lg shadow-blue-500/25">
              Browse Files
              <input
                type="file"
                className="hidden"
                onChange={handleFileSelect}
                accept=".pdf,.jpg,.jpeg,.png,.tiff,.mp3,.wav,.ogg,.txt,.docx,.xlsx,.pptx"
              />
            </label>
          </>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mt-4 bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3">
          <XCircle className="w-5 h-5 text-red-400 shrink-0" />
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="mt-6 bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-5">
            <CheckCircle className="w-6 h-6 text-green-400" />
            <h2 className="font-semibold text-white">Upload Successful</h2>
          </div>

          <div className="space-y-3">
            {[
              { label: 'File', value: result.document.original_filename },
              { label: 'Type', value: result.document.file_type },
              { label: 'Size', value: `${(result.document.file_size_bytes / 1024).toFixed(1)} KB` },
              { label: 'Processing Status', value: result.document.processing_status },
              { label: 'Compliance Status', value: result.document.compliance_status },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between py-2 border-b border-slate-700/50">
                <span className="text-slate-400 text-sm">{label}</span>
                <span className="text-white text-sm capitalize">{value}</span>
              </div>
            ))}
          </div>

          {/* Status indicator */}
          <div className="mt-5 p-4 rounded-xl bg-slate-900/50">
            {result.document.compliance_status === 'flagged' && (
              <div className="flex items-center gap-2 text-yellow-400">
                <AlertTriangle className="w-5 h-5" />
                <span className="text-sm">PII detected — document flagged for review</span>
              </div>
            )}
            {result.document.compliance_status === 'clean' && result.document.processing_status === 'processed' && (
              <div className="flex items-center gap-2 text-green-400">
                <CheckCircle className="w-5 h-5" />
                <span className="text-sm">Document clean — ready for approval</span>
              </div>
            )}
            {(result.document.processing_status === 'uploaded' || result.document.processing_status === 'processing') && (
              <div className="flex items-center gap-2 text-blue-400">
                <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm">Processing... checking status automatically</span>
              </div>
            )}
            {result.document.processing_status === 'embedding' && (
              <div className="flex items-center gap-2 text-purple-400">
                <div className="w-4 h-4 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm">Embedding into knowledge base...</span>
              </div>
            )}

            {result.document.compliance_status === 'approved' && (
              <div className="flex items-center gap-2 text-blue-400">
                <CheckCircle className="w-5 h-5" />
                <span className="text-sm">Approved — being embedded into knowledge base</span>
              </div>
            )}
          </div>

          {/* Approve button */}
          {canApprove && (
            <button
              onClick={handleApprove}
              disabled={approving}
              className="mt-4 w-full bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-xl transition"
            >
              {approving ? 'Approving...' : 'Approve for Knowledge Base'}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default UploadPage;