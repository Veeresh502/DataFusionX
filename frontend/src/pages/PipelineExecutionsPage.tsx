import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { pipelineService } from '../services/api';
import { PipelineExecution, Pipeline } from '../types';
import { 
  ArrowLeft, 
  History, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Terminal, 
  X,
  Play,
  Layers,
  Activity,
  RotateCcw,
  Minimize2,
  Maximize2
} from 'lucide-react';

export const PipelineExecutionsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [executions, setExecutions] = useState<PipelineExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedExecution, setSelectedExecution] = useState<PipelineExecution | null>(null);
  const [running, setRunning] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (id) {
      fetchExecutions(Number(id));
    }
  }, [id]);

  const fetchExecutions = async (pipelineId: number) => {
    try {
      const [pipeData, execList] = await Promise.all([
        pipelineService.getPipeline(pipelineId),
        pipelineService.getExecutions(pipelineId),
      ]);
      setPipeline(pipeData);
      setExecutions(execList);

      // Keep selectedExecution updated with the latest data from server
      setSelectedExecution((prev) => {
        if (!prev) {
          return execList.length > 0 ? execList[0] : null;
        }
        const match = execList.find((e) => e.id === prev.id);
        return match || prev;
      });
    } catch (err) {
      console.error('Failed to fetch pipeline execution history', err);
    } finally {
      setLoading(false);
    }
  };

  // Poll active executions every 2s
  useEffect(() => {
    if (!id) return;
    const hasActive = executions.some((e) => ['PENDING', 'RUNNING', 'RETRYING'].includes(e.status));
    if (!hasActive && selectedExecution && !['PENDING', 'RUNNING', 'RETRYING'].includes(selectedExecution.status)) {
      return;
    }

    const interval = setInterval(() => {
      fetchExecutions(Number(id));
    }, 2000);

    return () => clearInterval(interval);
  }, [id, executions, selectedExecution?.status]);

  // WebSocket Subscription for Real-Time Execution Streaming
  useEffect(() => {
    if (!selectedExecution || ['SUCCESS', 'FAILED', 'CANCELLED'].includes(selectedExecution.status)) {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      return;
    }

    const token = localStorage.getItem('token');
    if (!token) return;

    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    const wsProtocol = baseUrl.startsWith('https') ? 'wss' : 'ws';
    const wsHost = baseUrl.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProtocol}://${wsHost}/ws/executions/${selectedExecution.id}?token=${token}`;

    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        
        setSelectedExecution((prev) => {
          if (!prev || prev.id !== selectedExecution.id) return prev;
          
          const updated = { ...prev };
          if (payload.status) updated.status = payload.status;
          if (payload.current_stage) updated.current_stage = payload.current_stage;
          if (payload.records_read !== undefined) updated.records_read = payload.records_read;
          if (payload.records_processed !== undefined) updated.records_processed = payload.records_processed;
          if (payload.records_failed !== undefined) updated.records_failed = payload.records_failed;
          if (payload.records_loaded !== undefined) updated.records_loaded = payload.records_loaded;
          if (payload.retry_count !== undefined) updated.retry_count = payload.retry_count;
          if (payload.duration_seconds !== undefined) updated.duration_seconds = payload.duration_seconds;
          if (payload.error) updated.error = payload.error;
          if (payload.logs) updated.logs = payload.logs;

          return updated;
        });

        // If execution finished, refresh execution table list
        if (payload.event === 'EXECUTION_SUCCESS' || payload.event === 'EXECUTION_FAILED' || payload.event === 'EXECUTION_COMPLETE') {
          if (id) fetchExecutions(Number(id));
        }
      } catch (e) {
        console.error('Error parsing WebSocket message', e);
      }
    };

    ws.onerror = (e) => {
      console.warn('WebSocket error:', e);
    };

    return () => {
      ws.close();
      socketRef.current = null;
    };
  }, [selectedExecution?.id, selectedExecution?.status]);


  const handleRunNow = async () => {
    if (!id) return;
    setRunning(true);
    try {
      const newExecution = await pipelineService.runPipeline(Number(id));
      setExecutions((prev) => [newExecution, ...prev]);
      setSelectedExecution(newExecution);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Pipeline execution failed');
    } finally {
      setRunning(false);
    }
  };

  const getStatusBadge = (status: string, stage?: string, retryCount?: number) => {
    switch (status) {
      case 'SUCCESS':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[11px] font-medium font-mono">
            <CheckCircle2 className="w-3 h-3" /> SUCCESS
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 text-[11px] font-medium font-mono">
            <AlertCircle className="w-3 h-3" /> FAILED
          </span>
        );
      case 'RETRYING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[11px] font-medium font-mono">
            <RotateCcw className="w-3 h-3 animate-spin" /> RETRYING ({retryCount ?? 1}/3)
          </span>
        );
      case 'RUNNING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-[11px] font-medium font-mono">
            <RefreshCw className="w-3 h-3 animate-spin" /> RUNNING {stage ? `[${stage}]` : ''}
          </span>
        );
      case 'PENDING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20 text-[11px] font-medium font-mono">
            <Activity className="w-3 h-3 animate-pulse" /> PENDING (QUEUED)
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 text-[11px] font-medium font-mono">
            {status}
          </span>
        );
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="py-24 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
          <span>Loading execution history & logs...</span>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-8 relative">
        
        {/* Navigation Back Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <Link
              to="/pipelines"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-white mb-2 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Pipelines</span>
            </Link>
            <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <History className="w-7 h-7 text-indigo-400" />
              <span>Execution Logs & History</span>
            </h1>
            <p className="text-slate-400 text-xs mt-1">
              Pipeline: <span className="text-slate-200 font-semibold">{pipeline?.name}</span> (Target: {pipeline?.destination_config?.table_name || pipeline?.destination_config?.warehouse_model_slug})
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleRunNow}
              disabled={running}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white text-xs font-medium flex items-center gap-2 shadow-lg shadow-emerald-600/20"
            >
              {running ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>{running ? 'Dispatching...' : 'Run Pipeline Now'}</span>
            </button>
          </div>
        </div>

        {/* Executions List Table */}
        <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
          {executions.length === 0 ? (
            <div className="py-16 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
              <Layers className="w-10 h-10 text-slate-600" />
              <p className="font-medium text-slate-300">No execution history found</p>
              <p className="text-slate-500 text-[11px]">Click "Run Pipeline Now" to trigger your first execution.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-900/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                    <th className="py-3.5 px-6">Execution ID</th>
                    <th className="py-3.5 px-4">Trigger</th>
                    <th className="py-3.5 px-4">Status</th>
                    <th className="py-3.5 px-4">Stage</th>
                    <th className="py-3.5 px-4">Started At</th>
                    <th className="py-3.5 px-4">Duration</th>
                    <th className="py-3.5 px-4">Read</th>
                    <th className="py-3.5 px-4">Processed</th>
                    <th className="py-3.5 px-4">Loaded</th>
                    <th className="py-3.5 px-4">Failed</th>
                    <th className="py-3.5 px-6 text-right">Logs</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {executions.map((exec) => (
                    <tr
                      key={exec.id}
                      onClick={() => {
                        setSelectedExecution(exec);
                        setIsMinimized(false);
                      }}
                      className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                    >
                      <td className="py-4 px-6 font-bold text-slate-200">#{exec.id}</td>
                      <td className="py-4 px-4 font-sans">
                        {exec.trigger_type === 'SCHEDULED' ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[10px] font-bold">
                            SCHEDULED
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] font-bold">
                            MANUAL
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-4">{getStatusBadge(exec.status, exec.current_stage, exec.retry_count)}</td>

                      <td className="py-4 px-4 text-indigo-300 font-bold text-[11px]">{exec.current_stage || 'PENDING'}</td>
                      <td className="py-4 px-4 text-slate-400 text-[11px]">
                        {new Date(exec.started_at).toLocaleString()}
                      </td>
                      <td className="py-4 px-4 text-slate-300">
                        {exec.duration_seconds ? `${exec.duration_seconds}s` : '-'}
                      </td>
                      <td className="py-4 px-4 text-slate-300">{exec.records_read}</td>
                      <td className="py-4 px-4 text-emerald-400 font-bold">{exec.records_processed}</td>
                      <td className="py-4 px-4 text-indigo-400 font-bold">{exec.records_loaded ?? 0}</td>
                      <td className="py-4 px-4 text-rose-400">{exec.records_failed}</td>
                      <td className="py-4 px-6 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedExecution(exec);
                            setIsMinimized(false);
                          }}
                          className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-indigo-300 font-sans text-xs inline-flex items-center gap-1.5"
                        >
                          <Terminal className="w-3.5 h-3.5" />
                          <span>Logs</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Execution Live Monitor Modal Viewer (Full Centered Overlay View) */}
        {selectedExecution && !isMinimized && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <div className="w-full max-w-3xl glass-panel p-6 rounded-2xl border border-slate-800 shadow-2xl relative max-h-[85vh] flex flex-col">
              <div className="absolute top-4 right-4 flex items-center gap-1.5 z-10">
                <button
                  onClick={() => setIsMinimized(true)}
                  title="Minimize to Floating Dock (Multitasking Mode)"
                  className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <Minimize2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setSelectedExecution(null)}
                  title="Close Console"
                  className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="mb-4 space-y-1 pr-20">
                <div className="flex items-center gap-3">
                  <h3 className="text-lg font-bold text-white">Execution #{selectedExecution.id} Live Monitor</h3>
                  {getStatusBadge(selectedExecution.status, selectedExecution.current_stage, selectedExecution.retry_count)}
                </div>
                <div className="flex items-center gap-4 text-xs font-mono text-slate-400 pt-1">
                  <span>Stage: <strong className="text-indigo-300">{selectedExecution.current_stage || 'PENDING'}</strong></span>
                  <span>Read: <strong className="text-slate-200">{selectedExecution.records_read}</strong></span>
                  <span>Processed: <strong className="text-emerald-400">{selectedExecution.records_processed}</strong></span>
                  <span>Loaded: <strong className="text-indigo-400">{selectedExecution.records_loaded ?? 0}</strong></span>
                  <span>Failed: <strong className="text-rose-400">{selectedExecution.records_failed}</strong></span>
                </div>
              </div>

              {/* Log Output Box */}
              <div className="flex-1 overflow-y-auto bg-slate-950 p-4 rounded-xl border border-slate-900 font-mono text-xs space-y-2 max-h-[60vh]">
                {selectedExecution.logs && selectedExecution.logs.length > 0 ? (
                  selectedExecution.logs.map((log, i) => (
                    <div key={i} className="flex items-start gap-3 border-b border-slate-900/50 pb-1.5">
                      <span className="text-slate-600 text-[10px] shrink-0">{new Date(log.timestamp).toLocaleTimeString()}</span>
                      <span className={`px-1.5 py-0.2 rounded text-[10px] shrink-0 ${
                        log.level === 'ERROR' ? 'bg-rose-500/20 text-rose-400' :
                        log.level === 'WARNING' ? 'bg-amber-500/20 text-amber-400' :
                        'bg-indigo-500/20 text-indigo-300'
                      }`}>
                        {log.level}
                      </span>
                      <span className="text-slate-300">{log.message}</span>
                    </div>
                  ))
                ) : (
                  <div className="text-slate-600 italic flex items-center gap-2">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-400" />
                    <span>Waiting for worker execution events...</span>
                  </div>
                )}

                {selectedExecution.error && (
                  <div className="mt-4 p-3 rounded-lg bg-rose-950/40 border border-rose-800 text-rose-300 font-sans text-xs">
                    <strong>Error:</strong> {selectedExecution.error}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Floating Mini Live Monitor Dock (Non-Blocking Multitasking View) */}
        {selectedExecution && isMinimized && (
          <div className="fixed bottom-6 right-6 z-40 w-96 glass-panel p-4 rounded-2xl border border-indigo-500/30 shadow-2xl bg-slate-950/95 backdrop-blur-md animate-in slide-in-from-bottom-5">
            <div className="flex items-center justify-between gap-2 border-b border-slate-800/80 pb-3 mb-3">
              <div className="flex items-center gap-2 min-w-0">
                <Terminal className="w-4 h-4 text-indigo-400 shrink-0" />
                <h4 className="text-xs font-bold text-white truncate">Exec #{selectedExecution.id} Live Dock</h4>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => setIsMinimized(false)}
                  title="Expand to Full Console"
                  className="p-1 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setSelectedExecution(null)}
                  title="Close Console"
                  className="p-1 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-slate-400">Status:</span>
                {getStatusBadge(selectedExecution.status, selectedExecution.current_stage, selectedExecution.retry_count)}
              </div>
              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                <span>Stage: <strong className="text-indigo-300">{selectedExecution.current_stage || 'PENDING'}</strong></span>
                <span>Loaded: <strong className="text-emerald-400">{selectedExecution.records_loaded ?? 0}</strong></span>
              </div>

              {/* Latest log preview */}
              <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800 font-mono text-[11px] text-slate-300 max-h-28 overflow-y-auto space-y-1.5">
                {selectedExecution.logs && selectedExecution.logs.length > 0 ? (
                  selectedExecution.logs.slice(-3).map((log, idx) => (
                    <div key={idx} className="truncate text-slate-300 flex items-center gap-1.5">
                      <span className="text-slate-500 text-[10px] shrink-0">{new Date(log.timestamp).toLocaleTimeString()}</span>
                      <span className="truncate">{log.message}</span>
                    </div>
                  ))
                ) : (
                  <div className="text-slate-500 italic text-[10px] flex items-center gap-1.5 py-1">
                    <RefreshCw className="w-3 h-3 animate-spin text-indigo-400" />
                    <span>Streaming live events...</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

      </div>
    </MainLayout>
  );
};

