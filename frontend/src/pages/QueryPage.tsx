import React, { useState, useRef, useEffect } from 'react';
import { queryDocuments } from '../api';
import { Send, Bot, User, FileText, Loader } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  chunks?: any[];
  latency?: number;
}

const QueryPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '0',
      role: 'assistant',
      content: 'Hello! I can answer questions about your approved documents. What would you like to know?',
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
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
      };

      setMessages(prev => [...prev, assistantMessage]);
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

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
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
                    <div key={i} className="bg-slate-900/50 border border-slate-700/30 rounded-xl p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <FileText className="w-3 h-3 text-slate-500" />
                          <span className="text-xs text-slate-500">
                            Doc {chunk.document_id.slice(0, 8)}... · Page {chunk.page}
                          </span>
                        </div>
                        <span className="text-xs text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded-full">
                          {(chunk.score * 100).toFixed(0)}% match
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 line-clamp-3">{chunk.text}</p>
                    </div>
                  ))}
                  {message.latency && (
                    <p className="text-xs text-slate-600 px-1">
                      Retrieved in {message.latency}ms
                    </p>
                  )}
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
        <div className="flex gap-3 max-w-4xl mx-auto">
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