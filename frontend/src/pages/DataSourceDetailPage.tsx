import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { dataSourceService } from '../services/api';
import { DataSource } from '../types';
import { 
  ArrowLeft, 
  Table as TableIcon, 
  Layers, 
  RefreshCw, 
  Trash2,
  Activity
} from 'lucide-react';
import { useToast } from '../components/Toast';


export const DataSourceDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const [source, setSource] = useState<DataSource | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'preview' | 'schema'>('preview');

  useEffect(() => {
    if (id) {
      fetchSourceDetail(Number(id));
    }
  }, [id]);

  const fetchSourceDetail = async (sourceId: number) => {
    setLoading(true);
    try {
      const data = await dataSourceService.getSource(sourceId);
      setSource(data);
    } catch (err: any) {
      console.error('Failed to fetch data source details', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!source || !window.confirm(`Delete data source "${source.name}"?`)) return;
    try {
      await dataSourceService.deleteSource(source.id);
      toast.success('Data Source Deleted', `Data source "${source.name}" removed successfully.`);
      navigate('/data-sources');
    } catch (err: any) {
      toast.error('Delete Failed', err.response?.data?.detail || 'Failed to delete data source');
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="py-24 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
          <span>Loading data source preview & metadata...</span>
        </div>
      </MainLayout>
    );
  }

  if (!source) {
    return (
      <MainLayout>
        <div className="max-w-4xl mx-auto py-16 text-center space-y-4">
          <p className="text-slate-300 font-semibold text-lg">Data Source Not Found</p>
          <p className="text-slate-500 text-xs">The requested data source may have been removed or belongs to another organization.</p>
          <Link to="/data-sources" className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-medium">
            <ArrowLeft className="w-4 h-4" /> Back to Data Sources
          </Link>
        </div>
      </MainLayout>
    );
  }

  const config = source.configuration || {};
  const previewRows = config.preview || [];
  const columns = config.columns || (previewRows.length > 0 ? Object.keys(previewRows[0]) : []);
  const dataTypes = config.data_types || {};

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Navigation Back Header */}
        <div className="flex items-center justify-between">
          <Link
            to="/data-sources"
            className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Data Sources</span>
          </Link>

          <div className="flex items-center gap-3">
            <Link
              to={`/datasets/${source.id}/profile`}
              className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-indigo-600/20 transition-all"
            >
              <Activity className="w-3.5 h-3.5" />
              <span>View Data Profile</span>
            </Link>

            <button
              onClick={handleDelete}
              className="px-3 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-300 text-xs font-medium flex items-center gap-1.5 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete Source</span>
            </button>
          </div>
        </div>

        {/* Source Header Info Card */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-white tracking-tight">{source.name}</h1>
                <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-xs font-mono font-semibold">
                  {source.type}
                </span>
              </div>
              {source.description && (
                <p className="text-slate-400 text-xs mt-1">{source.description}</p>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs">
              <div className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-300">
                <span className="text-slate-500 block text-[10px] uppercase">Row Count</span>
                <span className="font-mono font-semibold text-indigo-300">{config.row_count ?? 'N/A'}</span>
              </div>
              <div className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-300">
                <span className="text-slate-500 block text-[10px] uppercase">Columns</span>
                <span className="font-mono font-semibold text-cyan-300">{config.column_count ?? columns.length}</span>
              </div>
              <div className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-300">
                <span className="text-slate-500 block text-[10px] uppercase">Created</span>
                <span className="font-mono text-slate-400">{new Date(source.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs: Preview vs Schema */}
        <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
          <div className="flex border-b border-slate-800 px-6 pt-4 gap-4">
            <button
              onClick={() => setActiveTab('preview')}
              className={`flex items-center gap-2 pb-3 px-2 text-xs font-semibold border-b-2 transition-all ${
                activeTab === 'preview'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <TableIcon className="w-4 h-4" />
              <span>Data Preview (First 20 Rows)</span>
            </button>
            <button
              onClick={() => setActiveTab('schema')}
              className={`flex items-center gap-2 pb-3 px-2 text-xs font-semibold border-b-2 transition-all ${
                activeTab === 'schema'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>Column Schema & Types ({columns.length})</span>
            </button>
          </div>

          <div className="p-6">
            {activeTab === 'preview' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                  <span>Displaying top {previewRows.length} ingested sample rows</span>
                  <span className="font-mono text-[11px] text-slate-500">Source ID: {source.id}</span>
                </div>

                {previewRows.length === 0 ? (
                  <div className="py-12 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
                    No preview data available for this data source.
                  </div>
                ) : (
                  <div className="overflow-x-auto max-h-[460px] border border-slate-800 rounded-xl">
                    <table className="w-full text-left text-xs border-collapse font-mono">
                      <thead className="bg-slate-900 sticky top-0 border-b border-slate-800 z-10">
                        <tr>
                          <th className="py-3 px-4 text-slate-500 font-semibold border-r border-slate-800 text-center w-12">#</th>
                          {columns.map((col: string) => (
                            <th key={col} className="py-3 px-4 text-slate-300 font-semibold border-r border-slate-800 whitespace-nowrap">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {previewRows.map((row: any, idx: number) => (
                          <tr key={idx} className="hover:bg-slate-900/50 transition-colors">
                            <td className="py-2.5 px-4 text-slate-500 text-center border-r border-slate-800/60">{idx + 1}</td>
                            {columns.map((col: string) => {
                              const val = row[col];
                              return (
                                <td key={col} className="py-2.5 px-4 text-slate-300 border-r border-slate-800/60 whitespace-nowrap">
                                  {val === null || val === undefined ? (
                                    <span className="text-slate-600 italic">null</span>
                                  ) : typeof val === 'object' ? (
                                    JSON.stringify(val)
                                  ) : (
                                    String(val)
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'schema' && (
              <div className="space-y-4">
                <div className="border border-slate-800 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 font-semibold">
                      <tr>
                        <th className="py-3 px-6">Column Name</th>
                        <th className="py-3 px-6">Detected Data Type</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {columns.map((col: string) => (
                        <tr key={col} className="hover:bg-slate-900/40">
                          <td className="py-3 px-6 font-semibold text-slate-200">{col}</td>
                          <td className="py-3 px-6 text-indigo-300">
                            {dataTypes[col] || 'string / inferred'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>
    </MainLayout>
  );
};
