import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { dataSourceService } from '../services/api';
import { DataProfile, DataSource, ColumnProfile } from '../types';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer, 
  CartesianGrid, 
  LineChart, 
  Line 
} from 'recharts';
import { 
  ArrowLeft, 
  Activity, 
  Layers, 
  ShieldCheck, 
  RefreshCw, 
  PieChart as PieChartIcon,
  BarChart2
} from 'lucide-react';


export const DataProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<DataProfile | null>(null);
  const [source, setSource] = useState<DataSource | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedColumn, setSelectedColumn] = useState<ColumnProfile | null>(null);

  useEffect(() => {
    if (id) {
      fetchProfileData(Number(id));
    }
  }, [id]);

  const fetchProfileData = async (datasetId: number) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [profData, sourceData] = await Promise.all([
        dataSourceService.getDatasetProfile(datasetId),
        dataSourceService.getSource(datasetId),
      ]);
      setProfile(profData);
      setSource(sourceData);
      if (profData.column_profiles.length > 0) {
        setSelectedColumn(profData.column_profiles[0]);
      }
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to generate dataset profile');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="py-24 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
          <span>Computing dataset profile & quality metrics with Pandas...</span>
        </div>
      </MainLayout>
    );
  }

  if (errorMsg || !profile || !source) {
    return (
      <MainLayout>
        <div className="max-w-4xl mx-auto py-16 text-center space-y-4">
          <p className="text-slate-300 font-semibold text-lg">Unable to Profile Dataset</p>
          <p className="text-rose-400 text-xs">{errorMsg || 'Dataset profile unavailable'}</p>
          <Link to="/data-sources" className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-medium">
            <ArrowLeft className="w-4 h-4" /> Back to Data Sources
          </Link>
        </div>
      </MainLayout>
    );
  }

  const { summary, quality_scores, column_profiles } = profile;

  // Chart Data Preparation: Null % and Unique % per column
  const columnOverviewChartData = column_profiles.map((col) => ({
    name: col.name.length > 12 ? col.name.substring(0, 10) + '...' : col.name,
    fullName: col.name,
    'Null %': col.null_percentage,
    'Unique %': col.unique_percentage,
  }));

  const getQualityBadgeColor = (score: number) => {
    if (score >= 85) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
    if (score >= 60) return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
    return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
  };

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Navigation & Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <Link
              to={`/data-sources/${source.id}`}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-white mb-2 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Dataset Details</span>
            </Link>
            <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <Activity className="w-7 h-7 text-indigo-400" />
              <span>Dataset Profiling & Quality Analytics</span>
            </h1>
            <p className="text-slate-400 text-xs mt-1">
              Source: <span className="text-slate-200 font-semibold">{source.name}</span> ({source.type})
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className={`px-3 py-1.5 rounded-xl border text-xs font-bold font-mono flex items-center gap-2 ${getQualityBadgeColor(quality_scores.overall)}`}>
              <ShieldCheck className="w-4 h-4" />
              <span>Quality Score: {quality_scores.overall}%</span>
            </span>
          </div>
        </div>

        {/* Dataset Summary Cards */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="glass-card p-5 rounded-2xl border border-slate-800">
            <span className="text-[11px] text-slate-500 font-medium uppercase tracking-wider block">Total Rows</span>
            <span className="text-2xl font-bold font-mono text-white mt-1 block">{summary.row_count.toLocaleString()}</span>
          </div>
          <div className="glass-card p-5 rounded-2xl border border-slate-800">
            <span className="text-[11px] text-slate-500 font-medium uppercase tracking-wider block">Total Columns</span>
            <span className="text-2xl font-bold font-mono text-indigo-300 mt-1 block">{summary.column_count}</span>
          </div>
          <div className="glass-card p-5 rounded-2xl border border-slate-800">
            <span className="text-[11px] text-slate-500 font-medium uppercase tracking-wider block">Duplicate Rows</span>
            <span className={`text-2xl font-bold font-mono mt-1 block ${summary.duplicate_rows > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
              {summary.duplicate_rows}
            </span>
          </div>
          <div className="glass-card p-5 rounded-2xl border border-slate-800">
            <span className="text-[11px] text-slate-500 font-medium uppercase tracking-wider block">Estimated Memory</span>
            <span className="text-2xl font-bold font-mono text-cyan-300 mt-1 block">
              {(summary.memory_bytes / 1024).toFixed(1)} KB
            </span>
          </div>
        </section>

        {/* Quality Indicator Scores */}
        <section className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Data Quality Preview Indicator</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-400 font-medium">Completeness</span>
                <span className="font-mono font-bold text-emerald-400">{quality_scores.completeness}%</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div className="bg-emerald-500 h-full transition-all duration-500" style={{ width: `${quality_scores.completeness}%` }} />
              </div>
              <p className="text-[11px] text-slate-500">Ratio of non-null populated cells across all columns</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-400 font-medium">Uniqueness</span>
                <span className="font-mono font-bold text-indigo-400">{quality_scores.uniqueness}%</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div className="bg-indigo-500 h-full transition-all duration-500" style={{ width: `${quality_scores.uniqueness}%` }} />
              </div>
              <p className="text-[11px] text-slate-500">Percentage of non-duplicate records in dataset</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-400 font-medium">Validity</span>
                <span className="font-mono font-bold text-cyan-400">{quality_scores.validity}%</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div className="bg-cyan-500 h-full transition-all duration-500" style={{ width: `${quality_scores.validity}%` }} />
              </div>
              <p className="text-[11px] text-slate-500">Parsed without schema errors or structural violations</p>
            </div>
          </div>
        </section>

        {/* Charts Section */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-8">
          
          {/* Chart 1: Column Null & Unique Percentages */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-indigo-400" />
              <span>Column Null % & Unique % Overview</span>
            </h3>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={columnOverviewChartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 10 }} interval={0} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 10 }} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }}
                    itemStyle={{ color: '#e2e8f0' }}
                  />
                  <Bar dataKey="Null %" fill="#f43f5e" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Unique %" fill="#6366f1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 2: Selected Column Value Frequency or Time Series */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <PieChartIcon className="w-4 h-4 text-cyan-400" />
                <span>Column Inspector: {selectedColumn?.name}</span>
              </h3>
              <select
                value={selectedColumn?.name || ''}
                onChange={(e) => {
                  const col = column_profiles.find((c) => c.name === e.target.value);
                  if (col) setSelectedColumn(col);
                }}
                className="px-2.5 py-1 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 focus:outline-none"
              >
                {column_profiles.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name} ({c.data_type})
                  </option>
                ))}
              </select>
            </div>

            <div className="h-64 w-full flex items-center justify-center">
              {selectedColumn?.top_values && selectedColumn.top_values.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={selectedColumn.top_values} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="value" stroke="#64748b" tick={{ fontSize: 10 }} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }}
                    />
                    <Bar dataKey="count" fill="#22d3ee" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : selectedColumn?.date_distribution && selectedColumn.date_distribution.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={selectedColumn.date_distribution} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="period" stroke="#64748b" tick={{ fontSize: 10 }} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }} />
                    <Line type="monotone" dataKey="count" stroke="#a855f7" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="text-center text-xs text-slate-500">
                  Numeric column metrics: Min {selectedColumn?.min ?? 'N/A'}, Max {selectedColumn?.max ?? 'N/A'}, Mean {selectedColumn?.mean ?? 'N/A'}, Outliers: {selectedColumn?.outlier_count ?? 0}
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Detailed Column Profiling Table */}
        <section className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <h2 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-400" />
            <span>Column Level Profiling Statistics</span>
          </h2>

          <div className="overflow-x-auto border border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs border-collapse font-mono">
              <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 font-semibold text-[11px]">
                <tr>
                  <th className="py-3 px-4">Column Name</th>
                  <th className="py-3 px-4">Data Type</th>
                  <th className="py-3 px-4">Null Count (%)</th>
                  <th className="py-3 px-4">Unique Count (%)</th>
                  <th className="py-3 px-4">Min / Max</th>
                  <th className="py-3 px-4">Mean / Median</th>
                  <th className="py-3 px-4">Outliers</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {column_profiles.map((col) => (
                  <tr
                    key={col.name}
                    onClick={() => setSelectedColumn(col)}
                    className={`hover:bg-slate-800/40 cursor-pointer transition-colors ${
                      selectedColumn?.name === col.name ? 'bg-indigo-600/10' : ''
                    }`}
                  >
                    <td className="py-3 px-4 font-semibold text-slate-200 font-sans">{col.name}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-indigo-300 text-[11px]">
                        {col.data_type}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={col.null_count > 0 ? 'text-rose-400' : 'text-slate-400'}>
                        {col.null_count} ({col.null_percentage}%)
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      {col.unique_count} ({col.unique_percentage}%)
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      {col.min !== undefined && col.max !== undefined
                        ? `${col.min} / ${col.max}`
                        : col.min_date
                        ? `${col.min_date} .. ${col.max_date}`
                        : 'N/A'}
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      {col.mean !== undefined ? `${col.mean} / ${col.median}` : 'N/A'}
                    </td>
                    <td className="py-3 px-4">
                      {col.outlier_count !== undefined ? (
                        <span className={col.outlier_count > 0 ? 'text-amber-400 font-bold' : 'text-slate-500'}>
                          {col.outlier_count}
                        </span>
                      ) : (
                        'N/A'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

      </div>
    </MainLayout>
  );
};
