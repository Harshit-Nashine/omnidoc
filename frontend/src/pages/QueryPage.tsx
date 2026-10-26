import React, { useState, useRef, useEffect } from 'react';
import { queryDocuments, getDocuments } from '../api';
import { Send, Bot, User, FileText, Loader } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  chunks?: any[];
  latency?: number;
  question?: string;
}

const QueryPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>(() => {
    // Load from localStorage on first render
    try {
      const saved = localStorage.getItem('omnidoc_query_history');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.length > 0) return parsed;
      }
    } catch {
      // Ignore parse errors
    }
    return [{
      id: '0',
      role: 'assistant' as const,
      content: 'Hello! I can answer questions about your approved documents. What would you like to know?',
    }];
  });
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
    // Map document ID to metadata so sources show filenames, not IDs
  const [docMap, setDocMap] = useState<Record<string, any>>({});

  const loadDocs = () => {
    getDocuments()
      .then((docs: any[]) => {
        const map: Record<string, any> = {};
        docs.forEach(d => { map[d.id] = d; });
        setDocMap(map);
      })
      .catch(() => {});
  };

  useEffect(() => {
    loadDocs();
  }, []);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  // Save last 20 messages to localStorage
  useEffect(() => {
    if (messages.length > 1) {
      const toSave = messages.slice(-20);
      localStorage.setItem('omnidoc_query_history', JSON.stringify(toSave));
    }
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const data = await queryDocuments(input, 5);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.answer || 'Here are the most relevant sections from your documents:',
        chunks: data.chunks,
        latency: data.retrieval_latency_ms,
        question: input,
      };

      setMessages(prev => [...prev, assistantMessage]);
      loadDocs();
    } catch (err: any) {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: err.response?.data?.detail || 'Sorry, something went wrong. Make sure you have approved documents in the knowledge base.',
      }]);
    } finally {
      setLoading(false);
    }
  };
  // Session analytics, computed from the messages already on screen
  const questionCount = messages.filter(m => m.role === 'user').length;
  const allChunks = messages.flatMap(m => m.chunks || []);
  const latencies = messages.filter(m => m.latency).map(m => m.latency as number);
  const avgLatency = latencies.length
    ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)
    : 0;
  const docsHit = new Set(allChunks.map(c => c.document_id)).size;
    // Confidence tier from the similarity score
  const confidenceLabel = (score: number) =>
    score >= 0.8
      ? { text: 'High confidence', cls: 'text-green-400 bg-green-400/10' }
      : score >= 0.7
      ? { text: 'Medium confidence', cls: 'text-yellow-400 bg-yellow-400/10' }
      : { text: 'Low confidence', cls: 'text-orange-400 bg-orange-400/10' };

  // Highlights the question's words inside a passage, so the reader
  // can see why the passage matched
  const highlight = (text: string, query: string = '') => {
    const terms = query
      .split(/\s+/)
      .filter(t => t.length > 3)
      .map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    if (terms.length === 0) return text;
    const splitter = new RegExp(`(${terms.join('|')})`, 'gi');
    const tester = new RegExp(`^(${terms.join('|')})$`, 'i');
    return text.split(splitter).map((part, i) =>
      tester.test(part)
        ? <mark key={i} className="bg-blue-500/30 text-white rounded px-0.5">{part}</mark>
        : part
    );
  };

  // Exports one answer as Markdown with its sources and compliance status
  const exportAnswer = (m: Message) => {
    const lines = [
      '# OmniDoc Answer',
      '',
      `**Question:** ${m.question || ''}`,
      '',
      `**Answer:** ${m.content}`,
      '',
      '## Sources',
      ...(m.chunks || []).map((c: any, i: number) => {
        const d = docMap[c.document_id];
        return `${i + 1}. ${d?.original_filename || c.document_id} · page ${c.page} · ` +
          `${(c.score * 100).toFixed(0)}% match · compliance: ${d?.compliance_status || 'unknown'}\n\n> ${c.text}`;
      }),
      '',
      `_Exported ${new Date().toLocaleString()} from OmniDoc. Sources are approved documents only._`,
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'omnidoc_answer.md';
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
    {/* Session stats */}
      <div className="grid grid-cols-4 gap-3 p-4 border-b border-slate-700/50">
        {[
          { label: 'Questions', value: questionCount },
          { label: 'Avg retrieval', value: `${avgLatency} ms` },
          { label: 'Passages matched', value: allChunks.length },
          { label: 'Documents hit', value: docsHit },
        ].map(s => (
          <div key={s.label} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-3 text-center">
            <p className="text-lg font-semibold text-white">{s.value}</p>
            <p className="text-xs text-slate-500">{s.label}</p>
          </div>
        ))}
      </div>

      {/* What makes this different */}
      <div className="mx-4 mt-3 bg-blue-500/10 border border-blue-500/20 rounded-xl p-3 text-xs text-slate-300">
        <span className="text-blue-300 font-medium">Answers come only from your approved documents.</span>{' '}
        Every answer shows the exact passage it came from, every query is logged, and documents with PII are blocked from the knowledge base.
      </div>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((message) => (
          <div key={message.id} className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {message.role === 'assistant' && (
              <div className="w-8 h-8 bg-blue-600 rounded-xl flex items-center justify-center shrink-0 mt-1">
                <Bot className="w-4 h-4 text-white" />
              </div>
            )}

            <div className={`max-w-2xl ${message.role === 'user' ? 'order-first' : ''}`}>
              <div className={`rounded-2xl px-4 py-3 ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white ml-auto'
                  : 'bg-slate-800/80 border border-slate-700/50 text-slate-200'
              }`}>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
              </div>

              {/* Source chunks */}
              {message.chunks && message.chunks.length > 0 && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs text-slate-500 px-1">Sources:</p>
                  {message.chunks.map((chunk, i) => (
                    <button key={i} onClick={() => window.location.href = `/documents?id=${chunk.document_id}`} className="w-full text-left bg-slate-900/50 border border-slate-700/30 rounded-xl p-3 hover:border-blue-500/50 cursor-pointer transition">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <FileText className="w-3 h-3 text-blue-400" />
                          <span className="text-xs text-slate-500">
                            {docMap[chunk.document_id]?.original_filename || `Doc ${chunk.document_id.slice(0, 8)}...`} · Page {chunk.page}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${confidenceLabel(chunk.score).cls}`}>
                            {confidenceLabel(chunk.score).text}
                          </span>
                          <span className="text-xs text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded-full">
                            {(chunk.score * 100).toFixed(0)}% match
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-slate-400 line-clamp-3">{highlight(chunk.text, message.question)}</p>
                    </button>
                  ))}
                  {message.latency && (
                    <p className="text-xs text-slate-600 px-1">
                      Retrieved in {message.latency}ms
                    </p>
                    
                  )}
                  <button
                    onClick={() => exportAnswer(message)}
                    className="text-xs text-blue-300 hover:text-blue-200 underline px-1"
                  >
                    Export answer with sources (.md)
                  </button>
                </div>
                
              )}
            </div>

            {message.role === 'user' && (
              <div className="w-8 h-8 bg-slate-700 rounded-xl flex items-center justify-center shrink-0 mt-1">
                <User className="w-4 h-4 text-white" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-xl flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-slate-800/80 border border-slate-700/50 rounded-2xl px-4 py-3">
              <Loader className="w-4 h-4 text-slate-400 animate-spin" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-slate-700/50 bg-slate-900/50">
        <div className="flex gap-3 max-w-4xl mx-auto items-center">
          <button
            onClick={() => {
              localStorage.removeItem('omnidoc_query_history');
              setMessages([{
                id: '0',
                role: 'assistant',
                content: 'Hello! I can answer questions about your approved documents. What would you like to know?',
              }]);
            }}
            className="text-slate-600 hover:text-slate-400 transition p-2 rounded-xl hover:bg-slate-800 shrink-0"
            title="Clear history"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="Ask a question about your documents..."
            className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition text-sm"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white p-3 rounded-xl transition shadow-lg shadow-blue-500/25"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default QueryPage;