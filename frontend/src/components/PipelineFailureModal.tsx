import React, { useState, useEffect } from 'react';
import { aiService } from '../services/api';
import { 
  Bot, 
  Sparkles, 
  AlertTriangle, 
  X, 
  RefreshCw, 
  Wrench, 
  ShieldAlert
} from 'lucide-react';


interface PipelineFailureModalProps {
  executionId: number | null;
  pipelineName?: string;
  onClose: () => void;
}

export const PipelineFailureModal: React.FC<PipelineFailureModalProps> = ({
  executionId,
  pipelineName,
  onClose,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<{
    summary: string;
    root_cause: string;
    suggested_fix: string;
    stage: string;
  } | null>(null);

  useEffect(() => {
    if (executionId) {
      fetchAnalysis(executionId);
    }
  }, [executionId]);

  const fetchAnalysis = async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await aiService.explainPipelineFailure(id);
      setAnalysis(res);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to generate AI failure explanation';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (!executionId) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="glass-panel max-w-2xl w-full rounded-2xl border border-red-500/30 bg-slate-900 shadow-2xl space-y-5 overflow-hidden animate-in fade-in zoom-in duration-200">
        
        {/* Header */}
        <div className="p-5 bg-gradient-to-r from-red-950/40 via-slate-900 to-slate-900 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 flex items-center justify-center">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <span>AI Pipeline Failure Assistant</span>
              </h2>
              <p className="text-xs text-slate-400">
                Execution #{executionId} {pipelineName ? `— ${pipelineName}` : ''}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-5">
          {loading ? (
            <div className="py-12 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
              <RefreshCw className="w-8 h-8 animate-spin text-purple-400" />
              <span>Analyzing failed execution logs & schema context...</span>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
              <div>
                <div className="font-bold mb-0.5">Analysis Failed</div>
                <div>{error}</div>
              </div>
            </div>
          ) : analysis ? (
            <div className="space-y-4 text-xs">
              
              {/* Summary & Failed Stage Badge */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-slate-950 border border-slate-800">
                <div>
                  <span className="text-[10px] font-mono text-slate-500 uppercase block">Failure Overview</span>
                  <span className="text-slate-200 font-semibold">{analysis.summary}</span>
                </div>

                <span className="px-3 py-1 rounded-full font-mono font-bold text-[10px] bg-red-500/20 text-red-300 border border-red-500/30 uppercase">
                  Failed Stage: {analysis.stage}
                </span>
              </div>

              {/* Probable Root Cause */}
              <div className="p-4 rounded-xl bg-red-950/20 border border-red-500/20 space-y-1.5">
                <div className="flex items-center gap-2 font-bold text-red-300">
                  <ShieldAlert className="w-4 h-4 text-red-400" />
                  <span>Probable Root Cause</span>
                </div>
                <p className="text-slate-300 leading-relaxed font-mono">
                  {analysis.root_cause}
                </p>
              </div>

              {/* Suggested Fix */}
              <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/20 space-y-1.5">
                <div className="flex items-center gap-2 font-bold text-emerald-300">
                  <Wrench className="w-4 h-4 text-emerald-400" />
                  <span>Recommended Fix</span>
                </div>
                <p className="text-slate-300 leading-relaxed font-mono">
                  {analysis.suggested_fix}
                </p>
              </div>

              {/* Safety Safeguard Note */}
              <div className="p-3 rounded-xl bg-slate-950 text-slate-400 text-[11px] flex items-center gap-2 border border-slate-800 font-mono">
                <Sparkles className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                <span>AI Assistant provides read-only recommendations. Pipeline parameters and databases are never automatically mutated.</span>
              </div>

            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-950 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors"
          >
            Close Analysis
          </button>
        </div>

      </div>
    </div>
  );
};
