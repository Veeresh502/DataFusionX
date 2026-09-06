import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { dataSourceService, aiService } from '../services/api';
import { DataSource } from '../types';
import { useToast } from '../components/Toast';
import { formatPercentage, formatNumber } from '../utils/formatters';
import { 
  ShieldAlert, 
  Sparkles, 
  Database, 
  Layers, 
  RefreshCw, 
  AlertTriangle, 
  AlertCircle, 
  CheckCircle2, 
  Info, 
  Wand2, 
  Table as TableIcon, 
  TrendingUp, 
  Filter,
  BarChart3
} from 'lucide-react';

interface FindingItem {
  id: string;
  column: string;
  category: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  penalty?: number;
  finding: string;
  evidence: string[];
  metric: Record<string, any>;
  explanation: string;
  recommendation: string;
  suggested_pipeline_prompt?: string;
}

interface DataQualityData {
  source_id: number;
  source_name: string;
  source_type: string;
  target_warehouse_model: string;
  row_count: number;
  column_count: number;
  quality_score: {
    score: number;
    max_score: number;
    status: string;
    overall_severity: 'INFO' | 'WARNING' | 'CRITICAL';
    completeness: number;
    uniqueness: number;
    validity: number;
    components?: {
      completeness?: { value: number; weight: number; contribution: number };
      uniqueness?: { value: number; weight: number; contribution: number };
      validity?: { value: number; weight: number; contribution: number };
      base_weighted_score?: number;
      anomaly_penalty?: number;
      schema_penalty?: number;
      total_penalties?: number;
      findings_penalties?: {
        critical_findings_count: number;
        critical_penalty: number;
        warning_findings_count: number;
        warning_penalty: number;
      };
      formula_description?: string;
    };
    breakdown?: {
      base_weighted_score: number;
      critical_finding_penalty: number;
      warning_finding_penalty: number;
      total_penalties: number;
      anomaly_penalty: number;
      schema_penalty: number;
    };
  };
  summary_counts: {
    critical: number;
    warning: number;
    info: number;
  };
  findings: FindingItem[];
  quality_issues?: Array<{
    severity: string;
    category: string;
    column: string;
    count: number;
    percentage: number;
    penalty?: number;
    description: string;
    evidence?: string[];
  }>;
  column_profiles: any[];
  historical_comparison: Array<{
    metric_name: string;
    current_value: any;
    previous_value: any;
    change_description: string;
    has_history: boolean;
  }>;
  ai_explanation_available: boolean;
  ai_summary: string;
}

export const AIDataQualityPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();

  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<number | string>('');
  const [targetModelSlug, setTargetModelSlug] = useState<string>('generic');

  const [loading, setLoading] = useState(false);
  const [qualityData, setQualityData] = useState<DataQualityData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'findings' | 'issues' | 'columns' | 'history' | 'breakdown'>('findings');
  const [severityFilter, setSeverityFilter] = useState<'ALL' | 'CRITICAL' | 'WARNING' | 'INFO'>('ALL');
  const [showScoreBreakdown, setShowScoreBreakdown] = useState<boolean>(true);
  const [selectedColName, setSelectedColName] = useState<string | null>(null);

  // Request sequence counter to eliminate race conditions during rapid dataset switching
  const activeRequestId = useRef<number>(0);

  useEffect(() => {
    fetchDataSources();
  }, []);

  useEffect(() => {
    if (selectedSourceId) {
      loadQualityAnalysis(Number(selectedSourceId), targetModelSlug);
    }
  }, [selectedSourceId, targetModelSlug]);

  const fetchDataSources = async () => {
    try {
      const list = await dataSourceService.listSources();
      setDataSources(list);
      if (list.length > 0) {
        // If passed in location state, select that source
        const initialSourceId = location.state?.sourceId || list[0].id;
        setSelectedSourceId(initialSourceId);
      }
    } catch (err) {
      console.error('Failed to load datasets for Data Quality', err);
    }
  };

  const loadQualityAnalysis = async (sourceId: number, modelSlug: string) => {
    const reqId = ++activeRequestId.current;
    // 1. Invalidate previous dataset state immediately
    setLoading(true);
    setError(null);
    setQualityData(null);
    setSelectedColName(null);
    setSeverityFilter('ALL');

    try {
      const res = await aiService.analyzeDataQuality(sourceId, modelSlug);
      // 2. Only accept response if it matches the latest in-flight request ID
      if (reqId === activeRequestId.current) {
        setQualityData(res);
      }
    } catch (err: any) {
      if (reqId === activeRequestId.current) {
        const msg = err.response?.data?.detail || err.message || 'Failed to analyze data quality';
        setError(msg);
        toast.error('Data Quality Analysis Failed', msg);
      }
    } finally {
      if (reqId === activeRequestId.current) {
        setLoading(false);
      }
    }
  };

  const handleCreateSuggestedPipeline = (prompt: string) => {
    navigate('/ai-copilot', {
      state: {
        initialPrompt: prompt,
        sourceId: selectedSourceId
      }
    });
  };

  const filteredFindings = qualityData?.findings.filter((f) => {
    if (severityFilter === 'ALL') return true;
    return f.severity === severityFilter;
  }) || [];

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10';
    if (score >= 70) return 'text-amber-400 border-amber-500/40 bg-amber-500/10';
    return 'text-rose-400 border-rose-500/40 bg-rose-500/10';
  };

  const getSeverityBadge = (severity: 'INFO' | 'WARNING' | 'CRITICAL') => {
    if (severity === 'CRITICAL') {
      return (
        <span className="px-2.5 py-1 rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/40 text-[10px] font-bold font-mono flex items-center gap-1">
          <AlertCircle className="w-3 h-3 text-rose-400" />
          <span>CRITICAL</span>
        </span>
      );
    }
    if (severity === 'WARNING') {
      return (
        <span className="px-2.5 py-1 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-bold font-mono flex items-center gap-1">
          <AlertTriangle className="w-3 h-3 text-amber-400" />
          <span>WARNING</span>
        </span>
      );
    }
    return (
      <span className="px-2.5 py-1 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-[10px] font-bold font-mono flex items-center gap-1">
        <Info className="w-3 h-3 text-cyan-400" />
        <span>INFO</span>
      </span>
    );
  };

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-cyan-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <ShieldAlert className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
                <span>AI Data Quality & Anomaly Intelligence</span>
              </h1>
              <p className="text-slate-400 text-xs mt-0.5">
                Deterministic dataset profiling, IQR outlier detection, casing anomaly analysis & AI explanations
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => selectedSourceId && loadQualityAnalysis(Number(selectedSourceId), targetModelSlug)}
              disabled={loading || !selectedSourceId}
              className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-xs font-medium flex items-center gap-2 transition-colors disabled:opacity-40"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>Re-analyze Dataset</span>
            </button>
          </div>
        </div>

        {/* Dataset & Target Warehouse Selector Control Panel */}
        <div className="glass-panel p-5 rounded-2xl border border-indigo-500/30 bg-slate-900/90 shadow-xl space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-300 font-semibold uppercase tracking-wider mb-1.5 flex items-center gap-2">
                <Database className="w-3.5 h-3.5 text-cyan-400" />
                Select Dataset Source:
              </label>
              <select
                value={selectedSourceId}
                onChange={(e) => setSelectedSourceId(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono font-bold text-cyan-300 focus:outline-none focus:border-cyan-500/50"
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

            <div>
              <label className="block text-xs text-slate-300 font-semibold uppercase tracking-wider mb-1.5 flex items-center gap-2">
                <Layers className="w-3.5 h-3.5 text-purple-400" />
                Target Warehouse Destination Model:
              </label>
              <select
                value={targetModelSlug}
                onChange={(e) => setTargetModelSlug(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono font-bold text-purple-300 focus:outline-none focus:border-purple-500/50"
              >
                <option value="generic">Generic Warehouse (GENERIC)</option>
                <option value="sales">Sales Analytics (SALES)</option>
                <option value="manufacturing">Manufacturing Analytics (MANUFACTURING)</option>
              </select>
            </div>
          </div>
        </div>

        {/* LOADING STATE */}
        {loading && (
          <div className="glass-panel p-12 rounded-2xl border border-indigo-500/30 bg-slate-900/80 text-center space-y-4">
            <RefreshCw className="w-10 h-10 text-indigo-400 animate-spin mx-auto" />
            <div>
              <h3 className="text-base font-bold text-white">Running Deterministic Profiling & Anomaly Intelligence...</h3>
              <p className="text-xs text-slate-400 mt-1">Calculating row metrics, IQR numeric outliers, casing variants, and formatting errors</p>
            </div>
          </div>
        )}

        {/* ERROR STATE */}
        {error && !loading && (
          <div className="p-6 rounded-2xl bg-rose-500/10 border border-rose-500/40 text-rose-200 text-sm flex items-center gap-3">
            <AlertCircle className="w-6 h-6 text-rose-400 shrink-0" />
            <div>
              <span className="font-bold block text-rose-300">Data Quality Analysis Error</span>
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* EMPTY DATASETS STATE */}
        {!loading && !error && dataSources.length === 0 && (
          <div className="glass-panel p-12 rounded-2xl border border-slate-800 text-center space-y-4">
            <Database className="w-12 h-12 text-slate-600 mx-auto" />
            <h3 className="text-base font-bold text-white">No Datasets Available to Analyze</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              Please ingest a CSV, JSON, Excel, or PostgreSQL dataset before running Data Quality intelligence.
            </p>
            <button
              onClick={() => navigate('/data-sources')}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold inline-flex items-center gap-2"
            >
              <span>Go to Data Sources & Ingestion</span>
            </button>
          </div>
        )}

        {/* QUALITY DATA DISPLAY */}
        {qualityData && !loading && (
          <div className="space-y-8">
            {qualityData.row_count === 0 && (
              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
                <span>Empty Dataset Notice: This dataset currently contains 0 records. Scoring and metric calculations reflect an empty schema.</span>
              </div>
            )}
            
            {/* EXECUTIVE SUMMARY & QUALITY SCORE BANNER */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
              
              {/* Score Badge */}
              <div className={`p-6 rounded-2xl border flex flex-col justify-between space-y-3 ${getScoreColor(qualityData.quality_score.score)}`}>
                <span className="text-xs font-mono font-bold uppercase tracking-wider block">Deterministic Quality Score</span>
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-extrabold font-mono tracking-tight">
                    {qualityData.quality_score.score}
                  </span>
                  <span className="text-sm font-mono opacity-75">/ 100</span>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-white/10 text-xs font-mono font-bold">
                  <span>Status: {qualityData.quality_score.status}</span>
                  <button 
                    onClick={() => setShowScoreBreakdown(!showScoreBreakdown)}
                    className="underline hover:text-white transition-colors cursor-pointer text-[11px]"
                  >
                    {showScoreBreakdown ? 'Hide Breakdown ▲' : 'Score Breakdown ▼'}
                  </button>
                </div>
              </div>

              {/* AI Executive Summary Card */}
              <div className="lg:col-span-3 glass-panel p-6 rounded-2xl border border-indigo-500/30 bg-slate-900/90 shadow-xl space-y-3 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-indigo-400 font-mono uppercase tracking-wider flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-indigo-400" />
                      AI Executive Quality Summary
                    </span>
                    {!qualityData.ai_explanation_available && (
                      <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-mono">
                        AI Offline (Deterministic Results Shown)
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-slate-200 leading-relaxed font-mono">
                    "{qualityData.ai_summary}"
                  </p>
                </div>

                <div className="flex items-center gap-6 pt-3 border-t border-slate-800 text-xs text-slate-400 font-mono">
                  <span>Dataset: <strong className="text-white">{qualityData.source_name}</strong></span>
                  <span>Rows: <strong className="text-white">{qualityData.row_count.toLocaleString()}</strong></span>
                  <span>Columns: <strong className="text-white">{qualityData.column_count}</strong></span>
                  <span>Critical: <strong className="text-rose-400">{qualityData.summary_counts.critical}</strong></span>
                  <span>Warnings: <strong className="text-amber-400">{qualityData.summary_counts.warning}</strong></span>
                </div>
              </div>

            </div>

            {/* EXPANDABLE DETERMINISTIC SCORE BREAKDOWN CARD */}
            {showScoreBreakdown && (
              <div className="glass-panel p-6 rounded-2xl border border-indigo-500/30 bg-slate-900/90 shadow-xl space-y-4 font-mono">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <h3 className="text-xs font-bold text-indigo-400 uppercase tracking-wider flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-indigo-400" />
                    <span>Deterministic Quality Score Breakdown & Weighting Model</span>
                  </h3>
                  <span className="text-[11px] text-slate-400">Formula: max(0, min(100, Base Weighted Score - Penalties))</span>
                </div>

                {/* Formula Components Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-400">Completeness (35% weight)</span>
                      <span className="font-bold text-emerald-400">
                        {formatPercentage(qualityData.quality_score.components?.completeness?.value ?? qualityData.quality_score.completeness)}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-500 flex justify-between">
                      <span>Contribution:</span>
                      <strong className="text-emerald-300">
                        +{formatNumber(qualityData.quality_score.components?.completeness?.contribution ?? ((qualityData.quality_score.completeness || 0) * 0.35))} pts
                      </strong>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-400">Uniqueness (35% weight)</span>
                      <span className="font-bold text-indigo-400">
                        {formatPercentage(qualityData.quality_score.components?.uniqueness?.value ?? qualityData.quality_score.uniqueness)}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-500 flex justify-between">
                      <span>Contribution:</span>
                      <strong className="text-indigo-300">
                        +{formatNumber(qualityData.quality_score.components?.uniqueness?.contribution ?? ((qualityData.quality_score.uniqueness || 0) * 0.35))} pts
                      </strong>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-400">Validity (30% weight)</span>
                      <span className="font-bold text-cyan-400">
                        {formatPercentage(qualityData.quality_score.components?.validity?.value ?? qualityData.quality_score.validity)}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-500 flex justify-between">
                      <span>Contribution:</span>
                      <strong className="text-cyan-300">
                        +{formatNumber(qualityData.quality_score.components?.validity?.contribution ?? ((qualityData.quality_score.validity || 0) * 0.30))} pts
                      </strong>
                    </div>
                  </div>
                </div>

                {/* Deductions & Final Calculation */}
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800/80 flex flex-col md:flex-row md:items-center justify-between gap-4 text-xs">
                  <div className="space-y-1">
                    <span className="text-slate-400 block font-bold uppercase text-[10px]">Applied Deductions & Penalties:</span>
                    <div className="flex items-center gap-4 text-slate-300">
                      <span>Critical Findings: <strong className="text-rose-400">-{formatNumber(qualityData.quality_score.components?.findings_penalties?.critical_penalty ?? qualityData.quality_score.breakdown?.critical_finding_penalty ?? 0)} pts</strong></span>
                      <span>Warnings: <strong className="text-amber-400">-{formatNumber(qualityData.quality_score.components?.findings_penalties?.warning_penalty ?? qualityData.quality_score.breakdown?.warning_finding_penalty ?? 0)} pts</strong></span>
                    </div>
                  </div>

                  <div className="text-right border-t md:border-t-0 md:border-l border-slate-800 pt-2 md:pt-0 md:pl-4">
                    <span className="text-slate-400 block text-[10px] uppercase font-bold">Final Calculated Score:</span>
                    <span className="text-xl font-extrabold text-white">
                      {qualityData.quality_score.score} / 100
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* TAB SWITCHER */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab('findings')}
                  className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-all ${
                    activeTab === 'findings'
                      ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                      : 'bg-slate-900 text-slate-400 hover:text-white'
                  }`}
                >
                  <ShieldAlert className="w-4 h-4" />
                  <span>Anomaly Findings ({qualityData.findings.length})</span>
                </button>
                <button
                  onClick={() => setActiveTab('issues')}
                  className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-all ${
                    activeTab === 'issues'
                      ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                      : 'bg-slate-900 text-slate-400 hover:text-white'
                  }`}
                >
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span>Quality Issues ({qualityData.quality_issues?.length ?? 0})</span>
                </button>
                <button
                  onClick={() => setActiveTab('columns')}
                  className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-all ${
                    activeTab === 'columns'
                      ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                      : 'bg-slate-900 text-slate-400 hover:text-white'
                  }`}
                >
                  <TableIcon className="w-4 h-4" />
                  <span>Column Profiles ({qualityData.column_profiles.length})</span>
                </button>
                <button
                  onClick={() => setActiveTab('history')}
                  className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-all ${
                    activeTab === 'history'
                      ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                      : 'bg-slate-900 text-slate-400 hover:text-white'
                  }`}
                >
                  <TrendingUp className="w-4 h-4" />
                  <span>Historical Trends</span>
                </button>
                <button
                  onClick={() => setActiveTab('breakdown')}
                  className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-all ${
                    activeTab === 'breakdown'
                      ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20'
                      : 'bg-slate-900 text-slate-400 hover:text-white'
                  }`}
                >
                  <BarChart3 className="w-4 h-4" />
                  <span>Score Deductions</span>
                </button>
              </div>

              {activeTab === 'findings' && (
                <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
                  <Filter className="w-3.5 h-3.5 text-slate-500 ml-1.5" />
                  {(['ALL', 'CRITICAL', 'WARNING', 'INFO'] as const).map((st) => (
                    <button
                      key={st}
                      onClick={() => setSeverityFilter(st)}
                      className={`px-2.5 py-1 rounded-lg text-[11px] font-bold font-mono transition-colors ${
                        severityFilter === st
                          ? 'bg-indigo-600 text-white shadow-sm'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {st}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* TAB 1: ANOMALY FINDINGS */}
            {activeTab === 'findings' && (
              <div className="space-y-4">
                {filteredFindings.length > 0 ? (
                  filteredFindings.map((f) => (
                    <div
                      key={f.id}
                      className={`glass-panel p-6 rounded-2xl border transition-all space-y-4 animate-fadeIn ${
                        f.severity === 'CRITICAL'
                          ? 'border-rose-500/50 bg-slate-900/95 shadow-rose-500/10'
                          : f.severity === 'WARNING'
                          ? 'border-amber-500/50 bg-slate-900/95 shadow-amber-500/10'
                          : 'border-cyan-500/40 bg-slate-900/95'
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                        <div className="flex items-center gap-3">
                          {getSeverityBadge(f.severity)}
                          <span className="text-xs font-bold text-white font-mono uppercase bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
                            Col: {f.column}
                          </span>
                          <span className="text-xs font-semibold text-indigo-300 font-mono">
                            [{f.category}]
                          </span>
                        </div>
                      </div>

                      <div>
                        <h3 className="text-base font-bold text-white mb-1">{f.finding}</h3>
                        <p className="text-xs text-slate-300 leading-relaxed font-mono bg-slate-950 p-3 rounded-xl border border-slate-800">
                          <strong className="text-indigo-400 block mb-0.5">AI Explanation:</strong>
                          {f.explanation}
                        </p>
                      </div>

                      {/* Evidence List */}
                      {f.evidence && f.evidence.length > 0 && (
                        <div className="space-y-1 text-xs text-slate-400 font-mono">
                          <span className="text-[11px] font-bold text-slate-500 uppercase">Deterministic Evidence:</span>
                          <ul className="list-disc list-inside space-y-0.5 text-slate-300 pl-1">
                            {f.evidence.map((ev, idx) => (
                              <li key={idx}>{ev}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Recommended Action & M12 Pipeline Trigger */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-slate-800">
                        <div className="text-xs text-slate-300 font-mono">
                          <span className="text-emerald-400 font-bold">Recommended Action: </span>
                          "{f.recommendation}"
                        </div>

                        {f.suggested_pipeline_prompt && (
                          <button
                            onClick={() => handleCreateSuggestedPipeline(f.suggested_pipeline_prompt!)}
                            className="px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-indigo-500/20 transition-all shrink-0"
                          >
                            <Wand2 className="w-3.5 h-3.5" />
                            <span>Create Suggested Pipeline (M12)</span>
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="p-8 rounded-2xl bg-slate-900/60 border border-slate-800 text-center space-y-2">
                    <CheckCircle2 className="w-8 h-8 text-emerald-400/60 mx-auto" />
                    <p className="text-sm font-bold text-white">No Anomaly Findings Detected</p>
                    <p className="text-xs text-slate-400 max-w-md mx-auto">
                      No findings match the selected severity filter. The dataset exhibits clean data quality.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* TAB: DATA QUALITY ISSUES TABLE */}
            {activeTab === 'issues' && (
              <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-slate-900 text-slate-300 border-b border-slate-800">
                      <tr>
                        <th className="px-4 py-3 font-semibold">Severity</th>
                        <th className="px-4 py-3 font-semibold">Category</th>
                        <th className="px-4 py-3 font-semibold">Target Column</th>
                        <th className="px-4 py-3 font-semibold">Affected Count</th>
                        <th className="px-4 py-3 font-semibold">Affected %</th>
                        <th className="px-4 py-3 font-semibold">Issue Description</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 text-slate-200">
                      {(qualityData.quality_issues || []).map((issue, idx) => (
                        <tr key={idx} className="hover:bg-slate-900/40">
                          <td className="px-4 py-3 font-bold">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                              issue.severity === 'CRITICAL' || issue.severity === 'HIGH'
                                ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                                : issue.severity === 'WARNING' || issue.severity === 'MEDIUM'
                                ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                                : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
                            }`}>
                              {issue.severity}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-bold text-indigo-300">{issue.category}</td>
                          <td className="px-4 py-3 text-slate-300 font-bold">{issue.column}</td>
                          <td className="px-4 py-3 text-white font-mono">{formatNumber(issue.count)}</td>
                          <td className="px-4 py-3 font-mono">
                            <span className={(issue.percentage || 0) > 0 ? 'text-amber-400 font-bold' : 'text-slate-400'}>
                              {formatPercentage(issue.percentage)}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-slate-300">{issue.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* TAB 2: COLUMN PROFILES TABLE & COLUMN INSPECTOR DRILLDOWN */}
            {activeTab === 'columns' && (
              <div className="space-y-6">
                <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden">
                  <div className="p-3 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between text-xs text-slate-400 font-mono">
                    <span>Click any column row below for interactive IQR quartile bounds & anomaly drilldown</span>
                    {selectedColName && (
                      <span className="text-indigo-400 font-bold">Active Drilldown: {selectedColName}</span>
                    )}
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-900 text-slate-300 font-mono border-b border-slate-800">
                        <tr>
                          <th className="px-4 py-3 font-semibold">Column Name</th>
                          <th className="px-4 py-3 font-semibold">Data Type</th>
                          <th className="px-4 py-3 font-semibold">Null Count (%)</th>
                          <th className="px-4 py-3 font-semibold">Unique Count (%)</th>
                          <th className="px-4 py-3 font-semibold">Stats (Min / Max / Outliers)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 text-slate-200">
                        {qualityData.column_profiles.map((col, idx) => (
                          <tr 
                            key={idx} 
                            onClick={() => setSelectedColName(col.name)}
                            className={`hover:bg-slate-900/60 cursor-pointer transition-colors ${selectedColName === col.name ? 'bg-indigo-950/40 border-l-2 border-indigo-500' : ''}`}
                          >
                            <td className="px-4 py-3 font-mono font-bold text-indigo-300 flex items-center gap-2">
                              <span>{col.name}</span>
                              {selectedColName === col.name && <span className="text-[10px] text-indigo-400">🔍</span>}
                            </td>
                            <td className="px-4 py-3 font-mono">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
                                (col.detected_type || col.data_type).includes('date')
                                  ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                                  : (col.detected_type || col.data_type) === 'email'
                                  ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
                                  : (col.detected_type || col.data_type) === 'numeric' || col.min !== undefined
                                  ? 'bg-purple-500/10 text-purple-300 border-purple-500/30'
                                  : 'bg-slate-800 text-slate-400 border-slate-700'
                              }`}>
                                {col.detected_type || col.data_type}
                              </span>
                            </td>
                            <td className="px-4 py-3 font-mono">
                              <span className={(col.null_percentage || 0) > 0 ? 'text-amber-400 font-bold' : 'text-slate-300'}>
                                {formatNumber(col.null_count)} ({formatPercentage(col.null_percentage)})
                              </span>
                            </td>
                            <td className="px-4 py-3 font-mono">
                              {formatNumber(col.unique_count)} ({formatPercentage(col.unique_percentage)})
                            </td>
                            <td className="px-4 py-3 font-mono text-[11px] text-slate-300">
                              {col.detected_type === 'date' || col.min_date ? (
                                <span>
                                  Min: <strong className="text-emerald-300">{col.min_date || 'N/A'}</strong> | Max: <strong className="text-emerald-300">{col.max_date || 'N/A'}</strong> | Valid: <strong className="text-emerald-400">{col.valid_date_count ?? col.non_null_count}</strong> / Invalid: <strong className={(col.invalid_date_count || 0) > 0 ? 'text-rose-400' : 'text-slate-400'}>{col.invalid_date_count || 0}</strong>
                                </span>
                              ) : col.detected_type === 'email' || col.detected_format === 'email' ? (
                                <span>
                                  Format: <strong className="text-cyan-300">Email</strong> | Valid: <strong className="text-emerald-400">{col.valid_format_count}</strong> / Invalid: <strong className={(col.invalid_format_count || 0) > 0 ? 'text-rose-400' : 'text-slate-400'}>{col.invalid_format_count}</strong> ({col.format_validity_percentage}%)
                                </span>
                              ) : col.min !== undefined ? (
                                <span>
                                  Min: {String(col.min)} | Max: {String(col.max)} | Outliers: <strong className={(col.outlier_count || 0) > 0 ? 'text-amber-400' : 'text-slate-400'}>{col.outlier_count || 0}</strong> ({formatPercentage(col.outlier_percentage)})
                                </span>
                              ) : (
                                <span>
                                  Cardinality: <strong className="text-indigo-300">{col.cardinality ?? col.unique_count}</strong> | Top Val: <strong className="text-slate-200">"{col.top_values?.[0]?.value ?? 'N/A'}"</strong>
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* COLUMN INSPECTOR / ANOMALY DRILLDOWN PANEL */}
                {selectedColName && (
                  <div className="glass-panel p-6 rounded-2xl border border-indigo-500/40 bg-slate-900/95 space-y-4 font-mono animate-fadeIn">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <div className="flex items-center gap-3">
                        <Database className="w-5 h-5 text-indigo-400" />
                        <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                          Column Inspector & Outlier Bounds: <span className="text-indigo-300">{selectedColName}</span>
                        </h3>
                      </div>
                      <button 
                        onClick={() => setSelectedColName(null)}
                        className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs transition-colors"
                      >
                        Close Drilldown ✕
                      </button>
                    </div>

                    {(() => {
                      const activeCol = qualityData.column_profiles.find(c => c.name === selectedColName);
                      if (!activeCol) return null;

                      const isNum = activeCol.detected_type === 'numeric' || activeCol.min !== undefined;
                      const isDate = activeCol.detected_type === 'date' || activeCol.min_date;

                      return (
                        <div className="space-y-4">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                              <span className="text-slate-500 uppercase text-[10px] block font-bold">Detected Data Type</span>
                              <span className="text-indigo-300 font-bold block mt-1 uppercase">{activeCol.detected_type || activeCol.data_type}</span>
                            </div>
                            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                              <span className="text-slate-500 uppercase text-[10px] block font-bold">NULL Freq / Count (%)</span>
                              <span className="text-amber-400 font-bold block mt-1">{formatNumber(activeCol.null_count)} ({formatPercentage(activeCol.null_percentage)})</span>
                            </div>
                            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                              <span className="text-slate-500 uppercase text-[10px] block font-bold">Unique Values (%)</span>
                              <span className="text-emerald-400 font-bold block mt-1">{formatNumber(activeCol.unique_count)} ({formatPercentage(activeCol.unique_percentage)})</span>
                            </div>
                            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                              <span className="text-slate-500 uppercase text-[10px] block font-bold">Non-Null Completeness</span>
                              <span className="text-cyan-400 font-bold block mt-1">{formatPercentage(activeCol.completeness_percentage)}</span>
                            </div>
                          </div>

                          {/* Numeric Outlier & IQR Quartile Section */}
                          {isNum && (
                            <div className="p-4 rounded-xl bg-slate-950/90 border border-purple-500/30 space-y-3">
                              <span className="text-xs font-bold text-purple-300 uppercase tracking-wider block border-b border-slate-800 pb-2">
                                IQR Quartiles & Statistical Outlier Analysis
                              </span>
                              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
                                <div>
                                  <span className="text-slate-500 text-[10px] block">Min / Max</span>
                                  <span className="text-white font-bold">{String(activeCol.min)} / {String(activeCol.max)}</span>
                                </div>
                                <div>
                                  <span className="text-slate-500 text-[10px] block">Mean / Median</span>
                                  <span className="text-white font-bold">{String(activeCol.mean)} / {String(activeCol.median)}</span>
                                </div>
                                <div>
                                  <span className="text-slate-500 text-[10px] block">Q1 (25th) / Q3 (75th)</span>
                                  <span className="text-purple-300 font-bold">{activeCol.q1 ?? 'N/A'} / {activeCol.q3 ?? 'N/A'}</span>
                                </div>
                                <div>
                                  <span className="text-slate-500 text-[10px] block">IQR Bounds</span>
                                  <span className="text-cyan-300 font-bold">[{activeCol.lower_bound ?? 'N/A'}, {activeCol.upper_bound ?? 'N/A'}]</span>
                                </div>
                                <div>
                                  <span className="text-slate-500 text-[10px] block">Potential Outliers</span>
                                  <span className={`font-bold ${(activeCol.outlier_count || 0) > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
                                    {formatNumber(activeCol.outlier_count)} ({formatPercentage(activeCol.outlier_percentage)})
                                  </span>
                                </div>
                              </div>

                              {activeCol.affected_row_indices && activeCol.affected_row_indices.length > 0 && (
                                <div className="pt-2 border-t border-slate-800/80 text-xs text-slate-300">
                                  <span className="text-amber-400 font-bold">Affected Row Indices: </span>
                                  <span className="font-mono bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-amber-300">
                                    [{activeCol.affected_row_indices.join(', ')}]
                                  </span>
                                  {activeCol.outliers && (
                                    <span className="ml-3 text-slate-400">
                                      Sample Outliers: [{activeCol.outliers.join(', ')}]
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Date Section */}
                          {isDate && (
                            <div className="p-4 rounded-xl bg-slate-950/90 border border-emerald-500/30 space-y-3">
                              <span className="text-xs font-bold text-emerald-300 uppercase tracking-wider block border-b border-slate-800 pb-2">
                                Date Pattern & Time Range Analysis
                              </span>
                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                                <div>
                                  <span className="text-slate-500 text-[10px] block">Earliest (Min Date)</span>
                                  <span className="text-emerald-300 font-bold">{activeCol.min_date || 'N/A'}</span>
                                </div>
                                <div>
                                  <span className="text-slate-500 text-[10px] block">Latest (Max Date)</span>
                                  <span className="text-emerald-300 font-bold">{activeCol.max_date || 'N/A'}</span>
                                </div>
                                <div>
                                  <span className="text-slate-500 text-[10px] block">Detected Pattern</span>
                                  <span className="text-white font-bold">{activeCol.detected_date_format || 'Mixed / ISO-8601'}</span>
                                </div>
                                <div>
                                  <span className="text-slate-500 text-[10px] block">Valid / Invalid Dates</span>
                                  <span className="text-white font-bold">{activeCol.valid_date_count ?? activeCol.non_null_count} / <strong className={(activeCol.invalid_date_count || 0) > 0 ? 'text-rose-400' : 'text-slate-400'}>{activeCol.invalid_date_count || 0}</strong></span>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: HISTORICAL TRENDS */}
            {activeTab === 'history' && (
              <div className="space-y-4">
                {qualityData.historical_comparison.map((item, idx) => (
                  <div key={idx} className="glass-panel p-5 rounded-2xl border border-slate-800 flex items-center justify-between">
                    <div>
                      <span className="text-xs font-bold text-indigo-400 font-mono block mb-1">
                        {item.metric_name}
                      </span>
                      <p className="text-xs text-slate-300 font-mono">
                        {item.change_description}
                      </p>
                    </div>

                    <div className="text-right font-mono">
                      {item.has_history ? (
                        <div>
                          <span className="text-xs text-slate-400 block">Current: <strong className="text-white">{String(item.current_value)}</strong></span>
                          <span className="text-[11px] text-slate-500 block">Baseline: {String(item.previous_value)}</span>
                        </div>
                      ) : (
                        <span className="px-2.5 py-1 rounded bg-slate-950 text-slate-500 border border-slate-800 text-xs">
                          No Baseline
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* TAB 4: SCORE DEDUCTIONS BREAKDOWN */}
            {activeTab === 'breakdown' && (
              <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
                <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider">
                  Deterministic Score Deduction Breakdown
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {Object.entries(qualityData.quality_score.breakdown || {}).map(([k, val]) => (
                    <div key={k} className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1 font-mono">
                      <span className="text-[11px] text-slate-400 uppercase block">{k.replace(/_/g, ' ')}</span>
                      <span className={`text-xl font-bold ${k.includes('penalty') ? 'text-rose-400' : 'text-indigo-400'}`}>
                        {k.includes('penalty') ? `-${val} pts` : `${val} pts`}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        )}

      </div>
    </MainLayout>
  );
};
