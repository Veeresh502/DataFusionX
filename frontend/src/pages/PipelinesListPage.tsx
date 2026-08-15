import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { pipelineService, dataSourceService } from '../services/api';
import { Pipeline, DataSource } from '../types';
import { 
  GitCommit, 
  Plus, 
  Play, 
  History, 
  Trash2, 
  RefreshCw, 
  Database, 
  Layers, 
  Search,
  Sparkles,
  Copy
} from 'lucide-react';


import { useToast } from '../components/Toast';
import { ConfirmModal } from '../components/ConfirmModal';

export const PipelinesListPage: React.FC = () => {
  const toast = useToast();
  const navigate = useNavigate();
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [sources, setSources] = useState<Record<number, DataSource>>({});
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [deletePipelineId, setDeletePipelineId] = useState<number | null>(null);


  useEffect(() => {
    fetchPipelinesAndSources();
  }, []);

  const fetchPipelinesAndSources = async () => {
    setLoading(true);
    try {
      const [pipeData, sourceData] = await Promise.all([
        pipelineService.listPipelines(),
        dataSourceService.listSources(),
      ]);
      setPipelines(pipeData);

      const sourceMap: Record<number, DataSource> = {};
      sourceData.forEach((s) => {
        sourceMap[s.id] = s;
      });
      setSources(sourceMap);
    } catch (err) {
      console.error('Failed to fetch pipelines', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRunPipeline = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setRunningId(id);
    try {
      const exec = await pipelineService.runPipeline(id);
      if (exec.status === 'SUCCESS') {
        toast.success('Pipeline Execution Completed', `Processed ${exec.records_processed} records successfully.`);
      } else {
        toast.error('Pipeline Execution Failed', `Execution status: ${exec.status}`);
      }
    } catch (err: any) {
      toast.error('Execution Failed', err.response?.data?.detail || 'Pipeline execution failed');
    } finally {
      setRunningId(null);
    }
  };

  const handleClone = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const cloned = await pipelineService.clonePipeline(id);
      toast.success('Pipeline Cloned', `Created clone '${cloned.name}'.`);
      await fetchPipelinesAndSources();
    } catch (err: any) {
      toast.error('Clone Error', err.response?.data?.detail || 'Failed to clone pipeline');
    }
  };

  const handleDeleteClick = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletePipelineId(id);
  };

  const handleConfirmDeletePipeline = async () => {
    if (!deletePipelineId) return;
    try {
      await pipelineService.deletePipeline(deletePipelineId);
      toast.success('Pipeline Deleted', 'The ETL pipeline was removed.');
      setPipelines((prev) => prev.filter((p) => p.id !== deletePipelineId));
      setDeletePipelineId(null);
    } catch (err: any) {
      toast.error('Delete Error', err.response?.data?.detail || 'Failed to delete pipeline');
    }
  };


  const filteredPipelines = pipelines.filter((p) =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (p.description || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <GitCommit className="w-8 h-8 text-indigo-400" />
              <span>ETL Pipelines</span>
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Visual DAG Builder & Linear ETL Engine: Extract dataset sources, apply transformations & validations, and load into PostgreSQL
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/pipelines/new/visual')}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-medium text-xs shadow-lg shadow-indigo-600/20 transition-all"
            >
              <Sparkles className="w-4 h-4 text-cyan-300" />
              <span>Visual DAG Builder</span>
            </button>

            <button
              onClick={() => navigate('/pipelines/new')}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs border border-slate-700 transition-all"
            >
              <Plus className="w-4 h-4" />
              <span>Quick Config</span>
            </button>
          </div>
        </div>

        {/* Search */}
        <div className="flex items-center justify-between gap-4">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search pipelines..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
            />
          </div>

          <button
            onClick={fetchPipelinesAndSources}
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
            title="Refresh List"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Pipelines Table */}
        <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
          {loading ? (
            <div className="py-16 text-center text-xs text-slate-400 flex flex-col items-center gap-2">
              <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
              <span>Loading pipelines...</span>
            </div>
          ) : filteredPipelines.length === 0 ? (
            <div className="py-16 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
              <Layers className="w-10 h-10 text-slate-600" />
              <p className="font-medium text-slate-300">No ETL pipelines configured</p>
              <p className="text-slate-500 text-[11px]">
                Click "Visual DAG Builder" to construct a graph-based Extract-Transform-Validate-Load workflow.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-900/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                    <th className="py-3.5 px-6">Pipeline Name</th>
                    <th className="py-3.5 px-4">Extraction Source</th>
                    <th className="py-3.5 px-4">Graph / Steps</th>
                    <th className="py-3.5 px-4">Destination Table</th>
                    <th className="py-3.5 px-4">Created</th>
                    <th className="py-3.5 px-6 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {filteredPipelines.map((p) => {
                    const src = sources[p.source_id];
                    const targetTable = p.destination_config?.table_name || 'N/A';
                    const stepsCount = (p.steps || []).length;
                    const hasDAG = (p.dag_nodes || []).length > 0;

                    return (
                      <tr
                        key={p.id}
                        onClick={() => navigate(`/pipelines/${p.id}/visual`)}
                        className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                      >
                        <td className="py-4 px-6 font-semibold text-slate-200">
                          <div>
                            <span className="text-sm text-white block">{p.name}</span>
                            {p.description && (
                              <span className="text-[11px] text-slate-500 block truncate max-w-xs">{p.description}</span>
                            )}
                          </div>
                        </td>
                        <td className="py-4 px-4 font-mono text-indigo-300">
                          {src ? `${src.name} (${src.type})` : `Source #${p.source_id}`}
                        </td>
                        <td className="py-4 px-4 font-mono text-slate-300">
                          <span className={`px-2 py-0.5 rounded border text-[11px] ${
                            hasDAG ? 'bg-purple-500/10 text-purple-300 border-purple-500/20' : 'bg-slate-900 border-slate-800'
                          }`}>
                            {hasDAG ? `DAG Graph (${p.dag_nodes?.length} nodes)` : `${stepsCount} steps`}
                          </span>
                        </td>
                        <td className="py-4 px-4 font-mono text-cyan-300 flex items-center gap-1.5 py-5">
                          <Database className="w-3.5 h-3.5 text-cyan-400" />
                          <span>{targetTable}</span>
                        </td>
                        <td className="py-4 px-4 text-slate-400 font-mono text-[11px]">
                          {new Date(p.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-4 px-6 text-right space-x-2">
                          <button
                            onClick={(e) => handleRunPipeline(p.id, e)}
                            disabled={runningId === p.id}
                            className="px-2.5 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 text-[11px] font-semibold inline-flex items-center gap-1 transition-all"
                            title="Run Pipeline Now"
                          >
                            {runningId === p.id ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Play className="w-3.5 h-3.5 fill-current" />
                            )}
                            <span>Run</span>
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/pipelines/${p.id}/visual`);
                            }}
                            className="p-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 transition-colors inline-flex items-center gap-1"
                            title="Visual DAG Builder"
                          >
                            <Sparkles className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => handleClone(p.id, e)}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors inline-flex items-center gap-1"
                            title="Clone Pipeline"
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/pipelines/${p.id}/executions`);
                            }}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors inline-flex items-center gap-1"
                            title="Execution History"
                          >
                            <History className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => handleDeleteClick(p.id, e)}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-900/40 text-rose-400 hover:text-rose-200 transition-colors inline-flex items-center gap-1"
                            title="Delete Pipeline"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <ConfirmModal
          isOpen={deletePipelineId !== null}
          title="Delete ETL Pipeline"
          message="Are you sure you want to delete this pipeline? All execution history will be preserved."
          confirmText="Delete Pipeline"
          cancelText="Cancel"
          type="danger"
          onConfirm={handleConfirmDeletePipeline}
          onCancel={() => setDeletePipelineId(null)}
        />
      </div>
    </MainLayout>
  );
};
