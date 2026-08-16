import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { monitoringService } from '../services/api';
import {
  MonitoringOverview,
  PipelineFailureItem,
  PipelinePerformanceInfo,
} from '../types';
import {
  Activity,
  Server,
  RefreshCw,
  AlertCircle,
  Clock,
  TrendingUp,
  ExternalLink,
  ShieldCheck,
  Calendar,
  ArrowUpRight,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

export const MonitoringDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [overview, setOverview] = useState<MonitoringOverview | null>(null);
  const [failures, setFailures] = useState<PipelineFailureItem[]>([]);
  const [performance, setPerformance] = useState<PipelinePerformanceInfo | null>(null);

  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchMonitoringData();
    const interval = setInterval(fetchMonitoringData, 10000); // Auto-refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const fetchMonitoringData = async () => {
    try {
      const [over, fail, perf] = await Promise.all([
        monitoringService.getOverview(),
        monitoringService.getFailures(),
        monitoringService.getPerformance(),
      ]);
      setOverview(over);
      setFailures(fail);
      setPerformance(perf);
    } catch (err) {
      console.error('Failed to load monitoring data', err);
    } finally {
      setRefreshing(false);
    }

  };

  const handleManualRefresh = () => {
    setRefreshing(true);
    fetchMonitoringData();
  };

  const getHealthBadge = (statusStr: string) => {
    const s = (statusStr || '').toUpperCase();
    if (s === 'HEALTHY' || s === 'CONNECTED') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-bold font-mono">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          HEALTHY
        </span>
      );
    } else if (s === 'DEGRADED' || s === 'WARNING') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs font-bold font-mono">
          <span className="w-2 h-2 rounded-full bg-amber-400" />
          WARNING
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 text-xs font-bold font-mono">
        <span className="w-2 h-2 rounded-full bg-rose-400" />
        CRITICAL
      </span>
    );
  };

  return (
    <MainLayout>
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <Activity className="w-8 h-8 text-indigo-400" />
              <span>Observability & Monitoring</span>
            </h1>
            <p className="text-slate-400 text-xs mt-1">
              Production system metrics, pipeline execution performance, data quality scores, and infrastructure status.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <a
              href="http://localhost:3001"
              target="_blank"
              rel="noreferrer"
              className="px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-2 transition-colors"
            >
              <span>Grafana Dashboard</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>

            <a
              href="http://localhost:8000/metrics"
              target="_blank"
              rel="noreferrer"
              className="px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-2 transition-colors font-mono"
            >
              <span>/metrics</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>

            <button
              onClick={handleManualRefresh}
              className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-2 shadow-lg shadow-indigo-600/20 transition-colors"
              title="Refresh Metrics"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* SECTION 1: SYSTEM HEALTH CARDS */}
        <div>
          <h2 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
            <Server className="w-4 h-4 text-indigo-400" />
            <span>Infrastructure System Health</span>
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* API Health */}
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 flex items-center justify-between shadow-lg">
              <div className="space-y-1">
                <span className="text-xs text-slate-400 font-medium">FastAPI Engine</span>
                <h3 className="text-base font-bold text-white font-mono">HTTP API</h3>
                <span className="text-[11px] text-slate-500 font-mono">v{overview?.system_health.version || '0.6.0'}</span>
              </div>
              <div>{getHealthBadge(overview?.system_health.api || 'HEALTHY')}</div>
            </div>

            {/* PostgreSQL Health */}
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 flex items-center justify-between shadow-lg">
              <div className="space-y-1">
                <span className="text-xs text-slate-400 font-medium">Database Store</span>
                <h3 className="text-base font-bold text-white font-mono">PostgreSQL</h3>
                <span className="text-[11px] text-slate-500 font-mono">Port 5432</span>
              </div>
              <div>{getHealthBadge(overview?.system_health.database || 'HEALTHY')}</div>
            </div>

            {/* Redis Health */}
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 flex items-center justify-between shadow-lg">
              <div className="space-y-1">
                <span className="text-xs text-slate-400 font-medium">Message Broker</span>
                <h3 className="text-base font-bold text-white font-mono">Redis Queue</h3>
                <span className="text-[11px] text-slate-500 font-mono">Port 6379</span>
              </div>
              <div>{getHealthBadge(overview?.system_health.redis || 'HEALTHY')}</div>
            </div>

            {/* Celery Worker Health */}
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 flex items-center justify-between shadow-lg">
              <div className="space-y-1">
                <span className="text-xs text-slate-400 font-medium">Execution Engine</span>
                <h3 className="text-base font-bold text-white font-mono">Celery Worker</h3>
                <span className="text-[11px] text-slate-500 font-mono">Distributed Workers</span>
              </div>
              <div>{getHealthBadge(overview?.system_health.celery || 'HEALTHY')}</div>
            </div>
          </div>
        </div>

        {/* SECTION 2: PIPELINE HEALTH SUMMARY METRICS */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="glass-panel p-4 rounded-2xl border border-slate-800 space-y-1">
            <span className="text-[11px] text-slate-400 font-medium">Executions Today</span>
            <div className="text-2xl font-bold text-white font-mono">
              {overview?.pipeline_overview.total_executions_today ?? 0}
            </div>
            <span className="text-[10px] text-indigo-400 font-semibold font-mono">
              {overview?.pipeline_overview.running_today ? `${overview.pipeline_overview.running_today} Running` : 'Idle'}
            </span>
          </div>

          <div className="glass-panel p-4 rounded-2xl border border-slate-800 space-y-1">
            <span className="text-[11px] text-slate-400 font-medium">Success Rate</span>
            <div className="text-2xl font-bold text-emerald-400 font-mono">
              {overview?.pipeline_overview.success_rate ?? 100}%
            </div>
            <span className="text-[10px] text-slate-500 font-mono">
              {overview?.pipeline_overview.successful_today ?? 0} Passed
            </span>
          </div>

          <div className="glass-panel p-4 rounded-2xl border border-slate-800 space-y-1">
            <span className="text-[11px] text-slate-400 font-medium">Executions Failed</span>
            <div className="text-2xl font-bold text-rose-400 font-mono">
              {overview?.pipeline_overview.failed_today ?? 0}
            </div>
            <span className="text-[10px] text-rose-400/80 font-mono">
              {overview?.pipeline_overview.retrying_today ? `${overview.pipeline_overview.retrying_today} Retrying` : '0 Retrying'}
            </span>
          </div>

          <div className="glass-panel p-4 rounded-2xl border border-slate-800 space-y-1">
            <span className="text-[11px] text-slate-400 font-medium">Avg Execution Duration</span>
            <div className="text-2xl font-bold text-indigo-300 font-mono">
              {overview?.pipeline_overview.average_duration_seconds ?? 0}s
            </div>
            <span className="text-[10px] text-slate-500 font-mono">
              Min: {overview?.pipeline_overview.min_duration_seconds ?? 0}s | Max: {overview?.pipeline_overview.max_duration_seconds ?? 0}s
            </span>
          </div>

          <div className="glass-panel p-4 rounded-2xl border border-slate-800 space-y-1">
            <span className="text-[11px] text-slate-400 font-medium">Records Processed</span>
            <div className="text-2xl font-bold text-cyan-400 font-mono">
              {(overview?.pipeline_overview.total_records_processed ?? 0).toLocaleString()}
            </div>
            <span className="text-[10px] text-slate-500 font-mono">
              Loaded: {(overview?.pipeline_overview.total_records_loaded ?? 0).toLocaleString()}
            </span>
          </div>

          <div className="glass-panel p-4 rounded-2xl border border-slate-800 space-y-1">
            <span className="text-[11px] text-slate-400 font-medium">Avg Throughput</span>
            <div className="text-2xl font-bold text-amber-400 font-mono">
              {overview?.pipeline_overview.throughput_records_per_sec ?? 0}
            </div>
            <span className="text-[10px] text-amber-400/80 font-mono">Records / sec</span>
          </div>
        </div>

        {/* SECTION 3: PERFORMANCE CHARTS & SLOWEST PIPELINES */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Execution Timeline Chart */}
          <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-indigo-400" />
                  <span>Execution Duration & Record Volume Trends</span>
                </h3>
                <p className="text-[11px] text-slate-400">Recent pipeline execution timeline performance</p>
              </div>
            </div>

            <div className="h-64 w-full">
              {performance?.execution_timeline && performance.execution_timeline.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={performance.execution_timeline}>
                    <defs>
                      <linearGradient id="durationColor" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="execution_id" stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={(val) => `#${val}`} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '11px' }}
                    />
                    <Area type="monotone" dataKey="duration_seconds" stroke="#6366f1" fillOpacity={1} fill="url(#durationColor)" name="Duration (s)" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-xs text-slate-500">
                  No execution history available for timeline charting.
                </div>
              )}
            </div>
          </div>

          {/* Slowest Pipelines Panel */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-400" />
              <span>Slowest Pipelines</span>
            </h3>

            <div className="space-y-3">
              {performance?.slowest_pipelines && performance.slowest_pipelines.length > 0 ? (
                performance.slowest_pipelines.map((sp) => (
                  <div
                    key={sp.pipeline_id}
                    onClick={() => navigate(`/pipelines/${sp.pipeline_id}`)}
                    className="p-3 rounded-xl bg-slate-900/60 border border-slate-800/80 hover:border-indigo-500/40 cursor-pointer transition-colors flex items-center justify-between"
                  >
                    <div>
                      <h4 className="text-xs font-bold text-slate-200">{sp.pipeline_name}</h4>
                      <span className="text-[10px] text-slate-500 font-mono">{sp.executions_count} Executions</span>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-bold text-amber-400 font-mono">{sp.avg_duration}s avg</span>
                      <div className="text-[10px] text-slate-500 font-mono">Max {sp.max_duration}s</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="py-8 text-center text-xs text-slate-500">No slow pipeline bottlenecks identified.</div>
              )}
            </div>
          </div>
        </div>

        {/* SECTION 4: PIPELINE FAILURES & DATA QUALITY VIEWS */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Failure Rankings */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400" />
              <span>Pipeline Failure Analysis</span>
            </h3>

            <div className="overflow-x-auto">
              {failures && failures.length > 0 ? (
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                      <th className="py-2.5 px-3">Pipeline</th>
                      <th className="py-2.5 px-3 text-center">Execs</th>
                      <th className="py-2.5 px-3 text-center">Failures</th>
                      <th className="py-2.5 px-3 text-right">Failure Rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {failures.map((f) => (
                      <tr
                        key={f.pipeline_id}
                        onClick={() => navigate(`/pipelines/${f.pipeline_id}/executions`)}
                        className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                      >
                        <td className="py-3 px-3 font-sans font-bold text-slate-200">{f.pipeline_name}</td>
                        <td className="py-3 px-3 text-center text-slate-400">{f.total_executions}</td>
                        <td className="py-3 px-3 text-center text-rose-400 font-bold">{f.failed_executions}</td>
                        <td className="py-3 px-3 text-right">
                          <span
                            className={`px-2 py-0.5 rounded font-bold ${
                              f.failure_rate_pct > 20
                                ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                                : 'bg-slate-800 text-slate-300'
                            }`}
                          >
                            {f.failure_rate_pct}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="py-8 text-center text-xs text-slate-500">0 pipeline failures recorded.</div>
              )}
            </div>
          </div>

          {/* Data Quality Overview */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Data Quality Observability</span>
            </h3>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
                <span className="text-[11px] text-slate-400">Average Data Quality Score</span>
                <div className="text-3xl font-bold text-emerald-400 font-mono">
                  {overview?.quality_summary.average_quality_score ?? 100}%
                </div>
                <span className="text-[10px] text-slate-500 font-mono">
                  Across {overview?.quality_summary.total_profiles_analyzed ?? 0} analyzed profiles
                </span>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
                <span className="text-[11px] text-slate-400">Total Invalid Records</span>
                <div className="text-3xl font-bold text-amber-400 font-mono">
                  {(overview?.quality_summary.total_invalid_records ?? 0).toLocaleString()}
                </div>
                <span className="text-[10px] text-amber-400/80 font-mono">
                  {overview?.quality_summary.total_quality_warnings ?? 0} Quality Warnings
                </span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-slate-200">Data Profiling & Quality Rules</h4>
                <p className="text-[11px] text-slate-400">Inspect dataset profiles and validation constraints</p>
              </div>
              <button
                onClick={() => navigate('/datasets')}
                className="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-medium flex items-center gap-1.5"
              >
                <span>View Datasets</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* SECTION 5: SCHEDULING HEALTH VIEW */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Calendar className="w-4 h-4 text-indigo-400" />
                <span>Scheduling Observability</span>
              </h3>
              <p className="text-[11px] text-slate-400">Celery Beat automated schedule execution status</p>
            </div>
            <button
              onClick={() => navigate('/schedules')}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1.5"
            >
              <span>Manage Schedules</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400">Active Schedules</span>
              <div className="text-xl font-bold text-white font-mono">
                {overview?.schedule_summary.enabled_schedules ?? 0} / {overview?.schedule_summary.total_schedules ?? 0}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400">Scheduled Runs Today</span>
              <div className="text-xl font-bold text-indigo-300 font-mono">
                {overview?.schedule_summary.scheduled_executions_today ?? 0}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400">Scheduled Passed</span>
              <div className="text-xl font-bold text-emerald-400 font-mono">
                {overview?.schedule_summary.successful_scheduled_today ?? 0}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
              <span className="text-[11px] text-slate-400">Scheduled Failed</span>
              <div className="text-xl font-bold text-rose-400 font-mono">
                {overview?.schedule_summary.failed_scheduled_today ?? 0}
              </div>
            </div>
          </div>
        </div>

      </div>
    </MainLayout>
  );
};
