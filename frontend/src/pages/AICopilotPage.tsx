import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { aiService, warehouseService, dataSourceService, pipelineService } from '../services/api';
import { WarehouseModel, DataSource, AIPipelineProposal } from '../types';
import { useToast } from '../components/Toast';
import { 
  Bot, 
  Sparkles, 
  Wand2,
  Code, 
  Copy, 
  Check, 
  RefreshCw, 
  AlertTriangle, 
  Trash2,
  Table as TableIcon,
  ShieldCheck,
  Layers,
  ArrowRight,
  Edit3,
  CheckCircle2,
  XCircle,
  Database,
  FileText,
  AlertCircle,
  Filter,
  Clock,
  Ban
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

export interface AIPipelineProposalHistoryItem {
  id: string;
  timestamp: string;
  source_id: number;
  source_name: string;
  source_type: string;
  user_prompt: string;
  status: 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED';
  created_pipeline_id?: number;
  created_pipeline_name?: string;
  proposal: AIPipelineProposal;
}


export const AICopilotPage: React.FC = () => {
  const navigate = useNavigate();
  const routerLocation = useLocation() as any;
  const toast = useToast();
  const promptInputRef = useRef<HTMLTextAreaElement>(null);

  const [activeTab, setActiveTab] = useState<'copilot' | 'sql'>('copilot');

  // M11 SQL Assistant State
  const [question, setQuestion] = useState('');
  const [selectedModel, setSelectedModel] = useState('generic');
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

  // M12 Pipeline Copilot State
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<number | string>('');
  const [copilotPrompt, setCopilotPrompt] = useState('');
  const [generatingProposal, setGeneratingProposal] = useState(false);
  const [creatingPipelineId, setCreatingPipelineId] = useState<string | null>(null);
  const [proposalError, setProposalError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<'ALL' | 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED'>('ALL');

  // Persistent Proposal History in localStorage
  const [proposalHistory, setProposalHistory] = useState<AIPipelineProposalHistoryItem[]>(() => {
    try {
      const saved = localStorage.getItem('datafusionx_ai_pipeline_copilot_proposals');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    fetchModels();
    fetchAIHealth();
    fetchDataSources();
  }, []);

  useEffect(() => {
    if (routerLocation.state?.initialPrompt) {
      setCopilotPrompt(routerLocation.state.initialPrompt);
      if (routerLocation.state.sourceId) {
        setSelectedSourceId(routerLocation.state.sourceId);
      }
      setActiveTab('copilot');
    }
  }, [routerLocation.state]);

  // Persist SQL Results History
  useEffect(() => {
    try {
      localStorage.setItem('datafusionx_ai_copilot_results', JSON.stringify(results));
    } catch (err) {
      console.error('Failed to persist AI SQL Copilot history', err);
    }
  }, [results]);

  // Persist Proposal History
  useEffect(() => {
    try {
      localStorage.setItem('datafusionx_ai_pipeline_copilot_proposals', JSON.stringify(proposalHistory));
    } catch (err) {
      console.error('Failed to persist AI Pipeline Copilot proposal history', err);
    }
  }, [proposalHistory]);

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

  const fetchDataSources = async () => {
    try {
      const list = await dataSourceService.listSources();
      setDataSources(list);
      if (list.length > 0) {
        setSelectedSourceId(list[0].id);
      }
    } catch (err) {
      console.error('Failed to load datasets for AI Copilot', err);
    }
  };

  const handleClearSQLHistory = () => {
    setResults([]);
    try {
      localStorage.removeItem('datafusionx_ai_copilot_results');
    } catch (err) {
      console.error('Failed to clear AI SQL Copilot history', err);
    }
  };

  const handleClearProposalHistory = () => {
    setProposalHistory([]);
    try {
      localStorage.removeItem('datafusionx_ai_pipeline_copilot_proposals');
    } catch (err) {
      console.error('Failed to clear AI Pipeline proposal history', err);
    }
  };

  // M11 SQL Query Submission
  const handleSubmitSQL = async (e?: React.FormEvent) => {
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

  // M12 Pipeline Copilot Submission (Adds to Persistent History)
  const handleGenerateProposal = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!selectedSourceId || !copilotPrompt.trim() || generatingProposal) return;

    setGeneratingProposal(true);
    setProposalError(null);

    try {
      const sourceObj = dataSources.find(ds => ds.id === Number(selectedSourceId));
      const res: AIPipelineProposal = await aiService.generatePipelineProposal(
        Number(selectedSourceId),
        copilotPrompt.trim()
      );

      const historyItem: AIPipelineProposalHistoryItem = {
        id: `prop-${Date.now()}`,
        timestamp: new Date().toLocaleTimeString(),
        source_id: Number(selectedSourceId),
        source_name: sourceObj?.name || res.source_name,
        source_type: sourceObj?.type || res.source_type,
        user_prompt: copilotPrompt.trim(),
        status: 'PENDING_REVIEW',
        proposal: res
      };

      setProposalHistory(prev => [historyItem, ...prev]);

      if (res.status === 'INVALID' || res.can_approve === false || !res.is_valid) {
        const errDetail = res.errors && res.errors.length > 0 ? res.errors[0].message : 'Requested transformation or parameter is unsupported.';
        toast.error('Invalid Pipeline Proposal', errDetail);
      } else if (res.warnings && res.warnings.length > 0) {
        toast.warning('Pipeline Proposal Generated with Warnings', res.warnings.join(' | '));
      } else {
        toast.success('Pipeline Proposal Generated', 'Proposal added to history. Review and approve when ready.');
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to generate pipeline proposal';
      setProposalError(msg);
      toast.error('Generation Failed', msg);
    } finally {
      setGeneratingProposal(false);
    }
  };

  // Human Approval: Approve & Create Pipeline for a specific history item
  const handleApproveAndCreate = async (item: AIPipelineProposalHistoryItem) => {
    const prop = item.proposal;
    if (creatingPipelineId || prop.status === 'INVALID' || prop.can_approve === false || !prop.is_valid) {
      toast.error('Cannot Approve Proposal', 'This proposal is invalid or incomplete and cannot be created.');
      return;
    }

    setCreatingPipelineId(item.id);
    try {
      const payload = {
        name: prop.proposed_name,
        description: `AI Generated Pipeline based on requirement: "${item.user_prompt}"`,
        source_id: prop.source_id,
        steps: prop.steps,
        destination_config: prop.destination_config,
        dag_nodes: prop.dag_nodes,
        dag_edges: prop.dag_edges,
      };

      const created = await pipelineService.createPipeline(payload);

      // Update persistent history status to APPROVED
      setProposalHistory(prev =>
        prev.map(p =>
          p.id === item.id
            ? {
                ...p,
                status: 'APPROVED',
                created_pipeline_id: created.id,
                created_pipeline_name: created.name
              }
            : p
        )
      );

      toast.success(
        'Pipeline Approved & Created',
        `Pipeline '${created.name}' created in your workspace! You can now execute it manually.`
      );
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to create pipeline';
      toast.error('Pipeline Creation Failed', msg);
    } finally {
      setCreatingPipelineId(null);
    }
  };

  // Human Rejection: Decline/Reject a proposal
  const handleRejectProposal = (itemId: string) => {
    setProposalHistory(prev =>
      prev.map(p =>
        p.id === itemId
          ? { ...p, status: 'REJECTED' }
          : p
      )
    );
    toast.info('Proposal Declined', 'Proposal marked as declined in history.');
  };

  // Interactive step parameter update for incomplete proposals
  const handleUpdateStepParameter = (itemId: string, stepIndex: number, field: string, value: string) => {
    setProposalHistory(prev =>
      prev.map(p => {
        if (p.id !== itemId) return p;
        const updatedSteps = [...p.proposal.steps];
        const currentStep = { ...updatedSteps[stepIndex], [field]: value };
        
        if (currentStep.column && currentStep.expression) {
          delete currentStep.is_incomplete;
        }
        updatedSteps[stepIndex] = currentStep;

        const stillIncomplete = updatedSteps.some(s =>
          (s.type === 'calculate_column' || s.type === 'derived_column') && (!s.column || !s.expression)
        );
        const isUnsupported = (p.proposal.unsupported_operations || []).length > 0;
        const hasBlockingErrors = (p.proposal.errors || []).length > 0;

        const isValidProposal = !isUnsupported && !hasBlockingErrors && !stillIncomplete;
        const newStatus: 'VALID' | 'INVALID' | 'INCOMPLETE' | 'WARNING' = isUnsupported || hasBlockingErrors ? 'INVALID' : (stillIncomplete ? 'INCOMPLETE' : 'VALID');

        return {
          ...p,
          proposal: {
            ...p.proposal,
            steps: updatedSteps,
            status: newStatus,
            can_approve: isValidProposal,
            is_valid: isValidProposal
          }
        };
      })
    );
  };

  // Edit Pipeline in Visual Builder (M7) - REUSES EXISTING M7 ROUTE: /pipelines/new/visual
  const handleEditInVisualBuilder = (item: AIPipelineProposalHistoryItem) => {
    navigate('/pipelines/new/visual', {
      state: {
        proposed_name: item.proposal.proposed_name,
        source_id: item.proposal.source_id,
        dag_nodes: item.proposal.dag_nodes,
        dag_edges: item.proposal.dag_edges,
        destination_config: item.proposal.destination_config,
      }
    });
  };

  const handleEditRequirementPrompt = (promptText: string) => {
    setCopilotPrompt(promptText);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    setTimeout(() => {
      promptInputRef.current?.focus();
    }, 300);
  };

  const samplePromptsSQL = [
    { text: "What are the top 5 products by revenue?", model: "sales" },
    { text: "Which customers generated the highest total revenue?", model: "sales" },
    { text: "Which machines produced the most units?", model: "manufacturing" },
    { text: "Show defect count by plant facility", model: "manufacturing" },
    { text: "Query top records from generic transformed datasets", model: "generic" },
  ];

  const samplePromptsCopilot = [
    "Clean this employee dataset, remove duplicate employees, fill missing values, normalize department names, validate employee_id, and load it into the Generic Warehouse.",
    "Filter employees where age is greater than 30.",
    "Create a calculated column for the employee data.",
    "Load this CSV into Generic Warehouse without applying any transformations.",
    "{\"transformation\": \"magic_clean\"}"
  ];

  const filteredProposalHistory = proposalHistory.filter(item => {
    if (filterStatus === 'ALL') return true;
    return item.status === filterStatus;
  });

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
                  Natural language ETL pipeline copilot & read-only warehouse SQL engine
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
            {activeTab === 'copilot' && proposalHistory.length > 0 && (
              <button
                onClick={handleClearProposalHistory}
                className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white border border-slate-800 text-xs font-medium flex items-center gap-1.5 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear Proposal History ({proposalHistory.length})</span>
              </button>
            )}
            {activeTab === 'sql' && results.length > 0 && (
              <button
                onClick={handleClearSQLHistory}
                className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white border border-slate-800 text-xs font-medium flex items-center gap-1.5 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear History ({results.length})</span>
              </button>
            )}
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-3 bg-slate-900 p-1.5 rounded-2xl border border-slate-800 w-fit">
          <button
            onClick={() => setActiveTab('copilot')}
            className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-all ${
              activeTab === 'copilot'
                ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Wand2 className="w-4 h-4" />
            <span>AI Pipeline Copilot (M12)</span>
          </button>
          <button
            onClick={() => setActiveTab('sql')}
            className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-all ${
              activeTab === 'sql'
                ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Code className="w-4 h-4" />
            <span>AI SQL Assistant (M11)</span>
          </button>
        </div>

        {/* TAB 1: AI PIPELINE COPILOT (M12) */}
        {activeTab === 'copilot' && (
          <div className="space-y-8">
            
            {/* Proposal Generator Input Card */}
            <div className="glass-panel p-6 rounded-2xl border border-indigo-500/30 bg-slate-900/90 shadow-2xl space-y-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <Sparkles className="w-5 h-5 text-indigo-400" />
                  <h2 className="text-base font-bold text-white tracking-wide uppercase font-mono">
                    Natural Language ETL Pipeline Generator
                  </h2>
                </div>
                <span className="px-2.5 py-1 rounded-lg bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 text-[10px] font-mono uppercase">
                  Human-in-the-Loop Review
                </span>
              </div>

              <form onSubmit={handleGenerateProposal} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="sm:col-span-1">
                    <label className="block text-xs text-slate-300 font-semibold uppercase tracking-wider mb-1.5 flex items-center gap-2">
                      <Database className="w-3.5 h-3.5 text-indigo-400" />
                      Select Dataset Source:
                    </label>
                    <select
                      value={selectedSourceId}
                      onChange={(e) => setSelectedSourceId(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono font-bold text-indigo-300 focus:outline-none focus:border-indigo-500/50"
                    >
                      {dataSources.length > 0 ? (
                        dataSources.map((ds) => (
                          <option key={ds.id} value={ds.id}>
                            {ds.name} ({ds.type})
                          </option>
                        ))
                      ) : (
                        <option value="">No Datasets Available</option>
                      )}
                    </select>
                  </div>

                  <div className="sm:col-span-2">
                    <label className="block text-xs text-slate-300 font-semibold uppercase tracking-wider mb-1.5 flex items-center gap-2">
                      <FileText className="w-3.5 h-3.5 text-indigo-400" />
                      Describe your ETL requirement:
                    </label>
                    <textarea
                      ref={promptInputRef}
                      rows={3}
                      placeholder="e.g. Clean this employee dataset, remove duplicate employees, fill missing values, normalize department names, validate employee_id, and load it into the Generic Warehouse."
                      value={copilotPrompt}
                      onChange={(e) => setCopilotPrompt(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500/60 shadow-inner resize-none font-mono"
                    />
                  </div>
                </div>

                {/* Sample Requirement Prompt Chips */}
                <div className="space-y-1.5">
                  <span className="text-[11px] text-slate-400 font-medium flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-indigo-400" /> Try Sample Requirement Prompts:
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {samplePromptsCopilot.map((sample, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setCopilotPrompt(sample)}
                        className="px-2.5 py-1 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 text-[11px] text-slate-300 hover:text-indigo-300 transition-colors text-left font-mono"
                      >
                        {sample.length > 75 ? sample.substring(0, 75) + '...' : sample}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={generatingProposal || !selectedSourceId || !copilotPrompt.trim()}
                    className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-indigo-500/25 transition-all disabled:opacity-40"
                  >
                    {generatingProposal ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>Inspecting Schema & Generating Proposal...</span>
                      </>
                    ) : (
                      <>
                        <Wand2 className="w-4 h-4" />
                        <span>Generate Pipeline Proposal</span>
                      </>
                    )}
                  </button>
                </div>
              </form>

              {proposalError && (
                <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-3">
                  <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
                  <div>
                    <span className="font-bold block">Generation Error</span>
                    <span>{proposalError}</span>
                  </div>
                </div>
              )}
            </div>

            {/* PERSISTENT PROPOSAL HISTORY LIST */}
            <div className="space-y-6">
              
              {/* History Controls Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-3">
                <div className="flex items-center gap-3">
                  <h3 className="text-base font-bold text-white flex items-center gap-2 font-mono">
                    <Clock className="w-4 h-4 text-indigo-400" />
                    <span>AI Proposal History ({proposalHistory.length})</span>
                  </h3>
                </div>

                {/* Filter Pills */}
                {proposalHistory.length > 0 && (
                  <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
                    <Filter className="w-3.5 h-3.5 text-slate-500 ml-1.5" />
                    {(['ALL', 'PENDING_REVIEW', 'APPROVED', 'REJECTED'] as const).map((st) => (
                      <button
                        key={st}
                        onClick={() => setFilterStatus(st)}
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-bold font-mono transition-colors ${
                          filterStatus === st
                            ? 'bg-indigo-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {st.replace('_', ' ')}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* History Cards */}
              {filteredProposalHistory.length > 0 ? (
                filteredProposalHistory.map((item) => {
                  const prop = item.proposal;
                  const isInvalid = prop.status === 'INVALID' || (prop.unsupported_operations && prop.unsupported_operations.length > 0) || prop.can_approve === false && prop.status !== 'INCOMPLETE' && !prop.is_valid;
                  const isIncomplete = prop.status === 'INCOMPLETE';

                  return (
                    <div
                      key={item.id}
                      className={`glass-panel p-6 rounded-2xl border transition-all space-y-6 animate-fadeIn ${
                        item.status === 'APPROVED'
                          ? 'border-emerald-500/40 bg-slate-900/90'
                          : item.status === 'REJECTED'
                          ? 'border-rose-500/30 bg-slate-900/70 opacity-75'
                          : isInvalid
                          ? 'border-rose-500/60 bg-slate-900/95 shadow-rose-500/10'
                          : isIncomplete
                          ? 'border-amber-500/50 bg-slate-900/95 shadow-amber-500/10'
                          : 'border-indigo-500/40 bg-slate-900/95 shadow-xl'
                      }`}
                    >
                      {/* Proposal Card Status Header */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
                        <div className="flex items-center gap-3 flex-wrap">
                          
                          {/* Status Pill */}
                          {item.status === 'APPROVED' ? (
                            <span className="px-3 py-1 rounded-xl bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-bold font-mono flex items-center gap-1.5 shadow-sm">
                              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                              <span>APPROVED & CREATED</span>
                              {item.created_pipeline_id && (
                                <span className="text-[10px] text-emerald-400/80 font-normal">
                                  (Pipeline #{item.created_pipeline_id})
                                </span>
                              )}
                            </span>
                          ) : item.status === 'REJECTED' ? (
                            <span className="px-3 py-1 rounded-xl bg-rose-500/20 text-rose-300 border border-rose-500/40 text-xs font-bold font-mono flex items-center gap-1.5 shadow-sm">
                              <XCircle className="w-4 h-4 text-rose-400" />
                              <span>DECLINED / REJECTED</span>
                            </span>
                          ) : isInvalid ? (
                            <span className="px-3 py-1 rounded-xl bg-rose-500/20 text-rose-300 border border-rose-500/50 text-xs font-bold font-mono flex items-center gap-1.5 shadow-sm">
                              <Ban className="w-4 h-4 text-rose-400" />
                              <span>INVALID PIPELINE REQUEST</span>
                            </span>
                          ) : isIncomplete ? (
                            <span className="px-3 py-1 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-bold font-mono flex items-center gap-1.5 shadow-sm">
                              <AlertTriangle className="w-4 h-4 text-amber-400" />
                              <span>INCOMPLETE PROPOSAL (Parameters Missing)</span>
                            </span>
                          ) : (
                            <span className="px-3 py-1 rounded-xl bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 text-xs font-bold font-mono flex items-center gap-1.5 shadow-sm">
                              <AlertTriangle className="w-4 h-4 text-indigo-400" />
                              <span>PENDING HUMAN REVIEW</span>
                            </span>
                          )}

                          <span className="px-2.5 py-1 rounded-xl bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 text-[11px] font-mono">
                            Generated at {item.timestamp}
                          </span>
                        </div>

                        <div className="text-right">
                          <span className="text-[11px] text-slate-400 block font-mono">Confidence Score</span>
                          <span className={`text-xs font-bold font-mono ${prop.confidence_score > 0.7 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {(prop.confidence_score * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>

                      {/* Prompt & Title */}
                      <div>
                        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 mb-3">
                          <span className="text-indigo-400 font-bold block mb-0.5">Requirement Prompt:</span>
                          "{item.user_prompt}"
                        </div>
                        <h3 className="text-lg font-bold text-white">{prop.proposed_name}</h3>
                        <p className="text-xs text-slate-400 mt-1">{prop.explanation}</p>
                      </div>

                      {/* EXPLICIT INVALID PIPELINE REQUEST BANNER (TEST 15 REQUIREMENT) */}
                      {isInvalid && (
                        <div className="p-5 rounded-2xl bg-rose-500/10 border border-rose-500/40 text-rose-200 space-y-3">
                          <div className="flex items-center gap-2 font-bold uppercase tracking-wider text-rose-300 text-xs">
                            <Ban className="w-4 h-4 text-rose-400 shrink-0" />
                            <span>INVALID PIPELINE REQUEST — UNSUPPORTED OPERATION</span>
                          </div>
                          
                          <p className="text-xs text-rose-200 leading-relaxed font-mono">
                            {prop.errors && prop.errors.length > 0
                              ? prop.errors[0].message
                              : `Requested transformation is not supported by the DataFusionX ETL engine.`}
                          </p>

                          <div className="space-y-1.5 pt-2 border-t border-rose-500/20">
                            <span className="text-[11px] text-rose-300 font-semibold block uppercase tracking-wider">
                              Available Transformations Supported by DataFusionX:
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                              {['Remove Duplicates', 'Fill NULL', 'Trim Text', 'Normalize Text', 'Filter Rows', 'Calculate Column', 'Derived Column', 'NOT NULL Validation', 'UNIQUE Validation'].map((t, idx) => (
                                <span key={idx} className="px-2 py-0.5 rounded bg-slate-950 border border-rose-500/30 text-[10px] font-mono text-slate-300">
                                  {t}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Detected Dataset Columns Chips */}
                      <div className="space-y-2 bg-slate-950 p-4 rounded-xl border border-slate-800">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider flex items-center gap-2">
                            <TableIcon className="w-3.5 h-3.5 text-indigo-400" />
                            Detected Source Columns ({prop.detected_columns?.length || 0}):
                          </span>
                          <span className="text-[11px] text-slate-500 font-mono">
                            Source: {item.source_name} ({item.source_type})
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {prop.detected_columns?.map((col, idx) => (
                            <span key={idx} className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono text-indigo-300">
                              {col}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* WARNINGS BANNER */}
                      {prop.warnings && prop.warnings.length > 0 && !isInvalid && (
                        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/40 text-amber-200 text-xs space-y-2">
                          <div className="flex items-center gap-2 font-bold uppercase tracking-wider text-amber-300">
                            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                            <span>Pipeline Proposal Warnings ({prop.warnings.length}):</span>
                          </div>
                          <ul className="list-disc list-inside space-y-1 pl-1 font-mono text-[11px]">
                            {prop.warnings.map((warn, idx) => (
                              <li key={idx} className="text-amber-200">{warn}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* VISUAL STEP FLOW OR NO VALID PIPELINE GENERATED (TEST 15 REQUIREMENT) */}
                      <div className="space-y-3">
                        <h4 className="text-xs text-slate-400 font-bold uppercase tracking-wider font-mono">
                          Proposed Visual Pipeline Flow:
                        </h4>

                        {isInvalid ? (
                          <div className="p-6 rounded-2xl bg-slate-950 border border-rose-500/30 text-center space-y-2">
                            <XCircle className="w-8 h-8 text-rose-400 mx-auto" />
                            <p className="text-sm font-bold text-rose-300 uppercase tracking-wider font-mono">
                              NO VALID PIPELINE GENERATED
                            </p>
                            <p className="text-xs text-slate-400 max-w-md mx-auto font-mono">
                              Reason: {prop.errors && prop.errors.length > 0 ? prop.errors[0].message : 'Requested transformation is unsupported.'}
                            </p>
                          </div>
                        ) : (
                          <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3 overflow-x-auto p-4 rounded-2xl bg-slate-950 border border-slate-800">
                            
                            {/* Source Node */}
                            <div className="p-3.5 rounded-xl bg-slate-900 border border-indigo-500/40 min-w-[180px] space-y-1">
                              <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider block">SOURCE</span>
                              <span className="text-xs font-bold text-white block">{item.source_name}</span>
                              <span className="text-[10px] text-slate-400 font-mono block">Format: {item.source_type}</span>
                            </div>

                            {prop.steps && prop.steps.length > 0 ? (
                              prop.steps.map((step, idx) => {
                                const stepIsIncomplete = step.is_incomplete || ((step.type === 'calculate_column' || step.type === 'derived_column') && (!step.column || !step.expression));
                                return (
                                  <React.Fragment key={idx}>
                                    <ArrowRight className="w-5 h-5 text-indigo-500 hidden md:block shrink-0" />
                                    <div className={`p-3.5 rounded-xl bg-slate-900 border min-w-[220px] space-y-2 transition-all ${stepIsIncomplete ? 'border-rose-500/60 shadow-lg shadow-rose-500/10' : 'border-slate-800 hover:border-indigo-500/50'}`}>
                                      <div className="flex items-center justify-between">
                                        <span className={`text-[10px] font-bold uppercase tracking-wider block ${step.category === 'validation' ? 'text-amber-400' : 'text-purple-400'}`}>
                                          {(step.category || 'step').toUpperCase()}
                                        </span>
                                        {stepIsIncomplete && (
                                          <span className="text-[9px] font-bold text-rose-400 uppercase bg-rose-500/20 px-1.5 py-0.5 rounded border border-rose-500/30">
                                            Required Field Missing
                                          </span>
                                        )}
                                      </div>

                                      <span className="text-xs font-bold text-white block">
                                        {step.type || step.rule_type}
                                      </span>

                                      {/* Interactive Parameter Editor for Incomplete Calculate Column */}
                                      {(step.type === 'calculate_column' || step.type === 'derived_column') ? (
                                        <div className="space-y-1.5 pt-1">
                                          <div>
                                            <label className="text-[9px] text-slate-400 font-mono uppercase block">Destination Column *</label>
                                            <input
                                              type="text"
                                              placeholder="e.g. total_val"
                                              value={step.column || ''}
                                              onChange={(e) => handleUpdateStepParameter(item.id, idx, 'column', e.target.value)}
                                              className="w-full px-2 py-1 rounded bg-slate-950 border border-slate-800 text-[11px] text-indigo-300 font-mono focus:outline-none focus:border-indigo-500"
                                            />
                                          </div>
                                          <div>
                                            <label className="text-[9px] text-slate-400 font-mono uppercase block">Expression *</label>
                                            <input
                                              type="text"
                                              placeholder="e.g. quantity * unit_price"
                                              value={step.expression || ''}
                                              onChange={(e) => handleUpdateStepParameter(item.id, idx, 'expression', e.target.value)}
                                              className="w-full px-2 py-1 rounded bg-slate-950 border border-slate-800 text-[11px] text-indigo-300 font-mono focus:outline-none focus:border-indigo-500"
                                            />
                                          </div>
                                        </div>
                                      ) : (
                                        <span className="text-[10px] text-slate-400 font-mono block truncate">
                                          {step.column ? `Col: ${step.column}` : (step.columns?.length ? `Cols: ${step.columns.join(', ')}` : 'Dataset-wide')}
                                        </span>
                                      )}
                                    </div>
                                  </React.Fragment>
                                );
                              })
                            ) : (
                              <div className="px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-xl text-[11px] text-slate-400 font-mono">
                                Direct Pass-through (Zero transformations requested)
                              </div>
                            )}

                            <ArrowRight className="w-5 h-5 text-indigo-500 hidden md:block shrink-0" />

                            {/* Destination Node */}
                            <div className="p-3.5 rounded-xl bg-slate-900 border border-emerald-500/40 min-w-[200px] space-y-1">
                              <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider block">DESTINATION</span>
                              <span className="text-xs font-bold text-white block truncate">
                                {prop.destination_config?.label || 'Data Warehouse'}
                              </span>
                              <span className="text-[10px] text-slate-400 font-mono block">
                                Mode: {prop.destination_config?.warehouse_model_slug?.toUpperCase() || 'GENERIC'}
                              </span>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* STEP REASONS / AI EXPLANATIONS */}
                      {prop.step_reasons && prop.step_reasons.length > 0 && !isInvalid && (
                        <div className="space-y-3 bg-slate-950 p-4 rounded-xl border border-slate-800">
                          <h4 className="text-xs text-slate-300 font-bold uppercase tracking-wider font-mono">
                            AI Step Reasoning & Recommendations:
                          </h4>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            {prop.step_reasons.map((sr, idx) => (
                              <div key={idx} className="p-3 rounded-lg bg-slate-900 border border-slate-800/80 space-y-1">
                                <span className="text-xs font-bold text-indigo-300 block">{sr.step}</span>
                                <span className="text-[11px] text-slate-400 block">{sr.reason}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* ACTION BAR */}
                      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-slate-800 pt-5">
                        <div className="text-xs text-slate-400">
                          {item.status === 'APPROVED' ? (
                            <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
                              <CheckCircle2 className="w-4 h-4" />
                              Pipeline created in workspace. You can execute it manually from the Pipelines dashboard.
                            </span>
                          ) : item.status === 'REJECTED' ? (
                            <span className="text-rose-400 font-semibold flex items-center gap-1.5">
                              <XCircle className="w-4 h-4" />
                              Proposal was declined. You can still review or edit it if needed.
                            </span>
                          ) : isInvalid ? (
                            <span className="text-rose-400 font-semibold flex items-center gap-1.5">
                              <Ban className="w-4 h-4 text-rose-400 shrink-0" />
                              Pipeline creation blocked. Please edit your ETL requirement prompt to use supported operations.
                            </span>
                          ) : isIncomplete ? (
                            <span className="text-amber-300 font-semibold flex items-center gap-1.5">
                              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                              Fill in missing parameters before approving this proposal.
                            </span>
                          ) : (
                            <span>
                              <strong className="text-slate-300">Human Approval Mandatory:</strong> Approving will create the pipeline without executing automatically.
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-3 w-full sm:w-auto">
                          {isInvalid && (
                            <button
                              type="button"
                              onClick={() => handleEditRequirementPrompt(item.user_prompt)}
                              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-indigo-500/20 transition-all"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                              <span>Edit Requirement</span>
                            </button>
                          )}

                          {item.status !== 'REJECTED' && item.status !== 'APPROVED' && (
                            <button
                              type="button"
                              onClick={() => handleRejectProposal(item.id)}
                              className="px-4 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                            >
                              <XCircle className="w-3.5 h-3.5" />
                              <span>Decline / Reject</span>
                            </button>
                          )}

                          {!isInvalid && (
                            <button
                              type="button"
                              onClick={() => handleEditInVisualBuilder(item)}
                              className="px-4 py-2 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 text-xs font-bold flex items-center gap-1.5 transition-all"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                              <span>Edit Pipeline (Visual Builder)</span>
                            </button>
                          )}

                          {item.status !== 'APPROVED' && !isInvalid && (
                            <button
                              type="button"
                              onClick={() => handleApproveAndCreate(item)}
                              disabled={creatingPipelineId === item.id || !prop.is_valid || prop.can_approve === false}
                              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-emerald-500/25 transition-all disabled:opacity-40"
                            >
                              {creatingPipelineId === item.id ? (
                                <>
                                  <RefreshCw className="w-4 h-4 animate-spin" />
                                  <span>Creating Pipeline...</span>
                                </>
                              ) : (
                                <>
                                  <CheckCircle2 className="w-4 h-4" />
                                  <span>Approve & Create Pipeline</span>
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      </div>

                    </div>
                  );
                })
              ) : (
                <div className="p-8 rounded-2xl bg-slate-900/60 border border-slate-800 text-center space-y-2">
                  <Wand2 className="w-8 h-8 text-indigo-400/50 mx-auto" />
                  <p className="text-sm font-bold text-white">No AI Pipeline Proposals Found</p>
                  <p className="text-xs text-slate-400 max-w-md mx-auto">
                    {proposalHistory.length > 0
                      ? 'No proposals match the selected filter status.'
                      : 'Describe your ETL data engineering requirement above to generate your first AI pipeline proposal.'}
                  </p>
                </div>
              )}
            </div>

          </div>
        )}

        {/* TAB 2: AI SQL ASSISTANT (M11) */}
        {activeTab === 'sql' && (
          <div className="space-y-6">
            <div className="glass-panel p-6 rounded-2xl border border-indigo-500/30 bg-slate-900/90 shadow-2xl space-y-4">
              <form onSubmit={handleSubmitSQL} className="space-y-4">
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
                    <option value="generic">Generic Warehouse (GENERIC)</option>
                    <option value="sales">Sales Analytics (SALES)</option>
                    <option value="manufacturing">Manufacturing Analytics (MANUFACTURING)</option>
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
                        handleSubmitSQL();
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
                        <span>Run Query</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Sample Prompt Chips */}
                <div className="flex flex-wrap gap-2 pt-1">
                  {samplePromptsSQL.map((sample, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        setQuestion(sample.text);
                        setSelectedModel(sample.model);
                      }}
                      className="px-2.5 py-1 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 text-xs text-slate-400 hover:text-indigo-300 transition-colors"
                    >
                      {sample.text}
                    </button>
                  ))}
                </div>
              </form>

              {error && (
                <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-3">
                  <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
                  <div>
                    <span className="font-bold block">AI Query Rejection / Error</span>
                    <span>{error}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Results History */}
            <div className="space-y-6">
              {results.map((res) => (
                <div key={res.id} className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4 animate-fadeIn">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-400" />
                      <h3 className="text-sm font-bold text-white">{res.question}</h3>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-slate-400 font-mono">
                      <span>Model: {res.warehouse_model?.toUpperCase()}</span>
                      <span>Time: {res.execution_time_ms}ms</span>
                    </div>
                  </div>

                  {/* Generated SQL Accordion */}
                  <div className="rounded-xl bg-slate-950 border border-slate-800/80 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-2 bg-slate-900/60 border-b border-slate-800/60 text-xs">
                      <span className="font-mono text-indigo-400 font-semibold flex items-center gap-1.5">
                        <Code className="w-3.5 h-3.5" /> Generated Read-Only SQL
                      </span>
                      <button
                        onClick={() => handleCopySQL(res.sql, res.id)}
                        className="text-[11px] text-slate-400 hover:text-white flex items-center gap-1"
                      >
                        {copiedId === res.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                        <span>{copiedId === res.id ? 'Copied' : 'Copy'}</span>
                      </button>
                    </div>
                    <pre className="p-4 text-xs font-mono text-emerald-300 overflow-x-auto leading-relaxed">
                      {res.sql}
                    </pre>
                  </div>

                  {/* AI Explanation */}
                  <div className="p-3.5 rounded-xl bg-indigo-500/5 border border-indigo-500/20 text-xs text-indigo-200">
                    <span className="font-bold text-indigo-400 block mb-1">AI Explanation:</span>
                    <span>{res.explanation}</span>
                  </div>

                  {/* Query Result Table */}
                  {res.rows && res.rows.length > 0 ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                        <span>Query Results ({res.row_count} rows)</span>
                      </div>
                      <div className="overflow-x-auto rounded-xl border border-slate-800">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-900 text-slate-300 font-mono border-b border-slate-800">
                            <tr>
                              {res.columns.map((col) => (
                                <th key={col} className="px-4 py-2.5 font-semibold">{col}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 text-slate-200">
                            {res.rows.map((row, idx) => (
                              <tr key={idx} className="hover:bg-slate-900/40">
                                {res.columns.map((col) => (
                                  <td key={col} className="px-4 py-2.5 font-mono text-[11px]">
                                    {row[col] !== null ? String(row[col]) : <span className="text-slate-600 italic">null</span>}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : (
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-center text-xs text-slate-400">
                      No records matched the query criteria.
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </MainLayout>
  );
};
