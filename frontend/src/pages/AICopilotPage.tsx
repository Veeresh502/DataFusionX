import React, { useState, useEffect } from 'react';
import { MainLayout } from '../layouts/MainLayout';
import { aiService, warehouseService } from '../services/api';
import { WarehouseModel } from '../types';
import { 
  Bot, 
  Sparkles, 
  Code, 
  Copy, 
  Check, 
  RefreshCw, 
  AlertTriangle, 
  Clock, 
  Trash2,
  Table as TableIcon,
  Lightbulb,
  ShieldCheck,
  Layers
} from 'lucide-react';

interface AIResult {
  id: string;
  question: string;
  sql: string;
  columns: string[];
  rows: Record<string, any>[];
  row_count: number;
  explanation: string;
  execution_time_ms: number;
  warehouse_model: string;
  timestamp: string;
}


export const AICopilotPage: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [selectedModel, setSelectedModel] = useState('sales');
  const [models, setModels] = useState<WarehouseModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<AIResult[]>(() => {
    try {
      const saved = localStorage.getItem('datafusionx_ai_copilot_results');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [aiHealth, setAiHealth] = useState<{ status: string; provider: string; model: string } | null>(null);
  const [expandedSql, setExpandedSql] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetchModels();
    fetchAIHealth();
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem('datafusionx_ai_copilot_results', JSON.stringify(results));
    } catch (err) {
      console.error('Failed to persist AI Copilot history', err);
    }
  }, [results]);

  const handleClearHistory = () => {
    setResults([]);
    try {
      localStorage.removeItem('datafusionx_ai_copilot_results');
    } catch (err) {
      console.error('Failed to clear AI Copilot history', err);
    }
  };


  const fetchModels = async () => {
    try {
      const data = await warehouseService.listModels();
      setModels(data);
    } catch (err) {
      console.error('Failed to load warehouse models', err);
    }
  };

  const fetchAIHealth = async () => {
    try {
      const health = await aiService.getAIHealth();
      setAiHealth(health);
    } catch (err) {
      console.error('Failed to check AI health', err);
    }
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!question.trim() || loading) return;

    const currentQ = question.trim();
    setQuestion('');
    setLoading(true);
    setError(null);

    try {
      const res = await aiService.queryAI(currentQ, selectedModel);
      const newResult: AIResult = {
        id: `ai-res-${Date.now()}`,
        ...res,
        timestamp: new Date().toLocaleTimeString(),
      };

      setResults((prev) => [newResult, ...prev]);
      setExpandedSql((prev) => ({ ...prev, [newResult.id]: true }));
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to generate SQL query';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleCopySQL = (sqlText: string, id: string) => {
    navigator.clipboard.writeText(sqlText);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const samplePrompts = [
    { text: "What are the top 5 products by revenue?", model: "sales" },
    { text: "Which customers generated the highest total revenue?", model: "sales" },
    { text: "Which machines produced the most units?", model: "manufacturing" },
    { text: "Show defect count by plant facility", model: "manufacturing" },
    { text: "Query top records from generic transformed datasets", model: "generic" },
  ];


  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
                <Bot className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
                  <span>DataFusionX AI Copilot</span>
                </h1>
                <p className="text-slate-400 text-xs mt-0.5">
                  Natural language warehouse analytics engine with read-only SQL safety validation
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {aiHealth && (
              <span className="px-3 py-1.5 rounded-xl bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 text-xs font-mono font-semibold flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Provider: {aiHealth.provider.toUpperCase()} ({aiHealth.model})</span>
              </span>
            )}
            {results.length > 0 && (
              <button
                onClick={handleClearHistory}
                className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white border border-slate-800 text-xs font-medium flex items-center gap-1.5 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear History</span>
              </button>
            )}

          </div>
        </div>

        {/* Query Input Panel */}
        <div className="glass-panel p-6 rounded-2xl border border-indigo-500/30 bg-slate-900/90 shadow-2xl space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" />
                <label className="text-xs text-slate-300 font-semibold uppercase tracking-wider">
                  Target Warehouse Model:
                </label>
              </div>

              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="px-3.5 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono font-bold text-indigo-300 focus:outline-none focus:border-indigo-500/50"
              >
                <option value="sales">Sales Analytics (SALES)</option>
                <option value="manufacturing">Manufacturing Analytics (MANUFACTURING)</option>
                <option value="generic">Generic Transformed Datasets (GENERIC)</option>
                {models.filter(m => !['sales', 'manufacturing', 'generic'].includes(m.slug)).map((m) => (
                  <option key={m.id} value={m.slug}>{m.name} ({m.domain})</option>
                ))}
              </select>

            </div>

            <div className="relative">
              <textarea
                rows={3}
                placeholder="Ask your warehouse a natural language question (e.g. 'Show top 5 products by revenue')..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                className="w-full pl-4 pr-24 py-3 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500/60 shadow-inner resize-none"
              />

              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="absolute right-3 bottom-4 px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-indigo-500/25 transition-all disabled:opacity-40"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Ask AI</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Sample Prompts */}
          <div className="pt-2 border-t border-slate-800/80">
            <span className="text-[11px] font-semibold text-slate-400 block mb-2">Sample Natural Language Questions:</span>
            <div className="flex flex-wrap gap-2">
              {samplePrompts.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setQuestion(p.text);
                    setSelectedModel(p.model);
                  }}
                  className="px-3 py-1 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-indigo-300 text-xs transition-colors flex items-center gap-1.5"
                >
                  <Sparkles className="w-3 h-3 text-indigo-400" />
                  <span>{p.text}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-bold mb-0.5">AI Request Error</div>
              <div>{error}</div>
            </div>
          </div>
        )}

        {/* AI Results Stream */}
        <div className="space-y-6">
          {results.map((res) => (
            <div key={res.id} className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-5 bg-slate-900/90 shadow-xl">
              
              {/* Question Header */}
              <div className="flex items-start justify-between gap-4 border-b border-slate-800/80 pb-4">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 flex items-center justify-center">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-white">{res.question}</h3>
                    <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400 mt-0.5">
                      <span>Model: <strong className="text-indigo-300">{res.warehouse_model}</strong></span>
                      <span>•</span>
                      <span>{res.timestamp}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3" />
                    <span>READ-ONLY SELECT</span>
                  </span>
                  <span className="px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1">
                    <Clock className="w-3 h-3 text-indigo-400" />
                    <span>{res.execution_time_ms} ms</span>
                  </span>
                </div>
              </div>

              {/* Generated SQL Accordion */}
              <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden">
                <div 
                  onClick={() => setExpandedSql(prev => ({ ...prev, [res.id]: !prev[res.id] }))}
                  className="px-4 py-2.5 bg-slate-900/90 flex items-center justify-between cursor-pointer hover:bg-slate-850"
                >
                  <div className="flex items-center gap-2 text-xs font-mono font-bold text-slate-300">
                    <Code className="w-4 h-4 text-indigo-400" />
                    <span>Generated SQL Query</span>
                  </div>

                  <div className="flex items-center gap-3" onClick={e => e.stopPropagation()}>
                    <button
                      onClick={() => handleCopySQL(res.sql, res.id)}
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-mono flex items-center gap-1.5 transition-colors"
                    >
                      {copiedId === res.id ? (
                        <>
                          <Check className="w-3 h-3 text-emerald-400" />
                          <span className="text-emerald-400">Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3 text-slate-400" />
                          <span>Copy SQL</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {expandedSql[res.id] && (
                  <pre className="p-4 text-xs font-mono text-indigo-300 overflow-x-auto bg-slate-950/90 whitespace-pre-wrap">
                    {res.sql}
                  </pre>
                )}
              </div>

              {/* Query Results Table */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                    <TableIcon className="w-4 h-4 text-indigo-400" />
                    <span>Query Results</span>
                  </h4>
                  <span className="text-[11px] font-mono text-slate-400">
                    Showing <strong className="text-white">{res.row_count}</strong> record{res.row_count === 1 ? '' : 's'}
                  </span>
                </div>

                {res.rows.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl bg-slate-950/40">
                    Query returned 0 matching records.
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-800">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-950 text-slate-300 uppercase tracking-wider font-mono border-b border-slate-800">
                        <tr>
                          {res.columns.map((col) => (
                            <th key={col} className="px-4 py-2.5 font-bold">{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 bg-slate-900/60 font-mono">
                        {res.rows.map((row, idx) => (
                          <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                            {res.columns.map((col) => (
                              <td key={col} className="px-4 py-2.5 text-slate-200 whitespace-nowrap">
                                {row[col] !== null && row[col] !== undefined ? String(row[col]) : <span className="text-slate-600">null</span>}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* AI Explanation Box */}
              <div className="p-4 rounded-xl bg-indigo-950/20 border border-indigo-500/20 text-xs text-slate-300 flex items-start gap-3">
                <Lightbulb className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-indigo-300 block mb-0.5">AI Explanation:</span>
                  <span>{res.explanation}</span>
                </div>
              </div>

            </div>
          ))}
        </div>

      </div>
    </MainLayout>
  );
};
