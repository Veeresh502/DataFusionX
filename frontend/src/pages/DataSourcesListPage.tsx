import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { dataSourceService } from '../services/api';
import { DataSource } from '../types';
import { AddDataSourceModal } from '../components/AddDataSourceModal';
import { 
  Database, 
  Plus, 
  Trash2, 
  Eye, 
  RefreshCw, 
  Search,
  Layers,
  Activity,
  ShieldAlert
} from 'lucide-react';
import { useToast } from '../components/Toast';



export const DataSourcesListPage: React.FC = () => {
  const navigate = useNavigate();
  const toast = useToast();
  const [sources, setSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('ALL');

  useEffect(() => {
    fetchSources();
  }, []);

  const fetchSources = async () => {
    setLoading(true);
    try {
      const data = await dataSourceService.listSources();
      setSources(data);
    } catch (err: any) {
      toast.error('Failed to load data sources', err.response?.data?.detail || 'Unexpected error');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this data source?')) return;
    try {
      await dataSourceService.deleteSource(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
      toast.success('Data Source Deleted', 'Data source removed successfully');
    } catch (err: any) {
      toast.error('Failed to delete data source', err.response?.data?.detail || 'Unexpected error');
    }
  };

  const handleSourceAdded = (newSource: DataSource) => {
    setSources((prev) => [newSource, ...prev]);
  };

  const getTypeBadge = (type: string) => {
    switch (type) {
      case 'CSV':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">CSV</span>;
      case 'EXCEL':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-green-500/10 text-green-400 border border-green-500/20">EXCEL</span>;
      case 'JSON':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">JSON</span>;
      case 'REST_API':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">REST</span>;
      case 'POSTGRESQL':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">POSTGRES</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400">{type}</span>;
    }
  };

  const filteredSources = sources.filter((source) => {
    const matchesSearch = source.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (source.description && source.description.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesType = typeFilter === 'ALL' || source.type === typeFilter;
    return matchesSearch && matchesType;
  });

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <Database className="w-8 h-8 text-indigo-400" />
              <span>Data Sources & Ingestion</span>
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Ingest and manage CSV, Excel, JSON datasets, REST endpoints, and PostgreSQL tables
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/data-quality')}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-bold text-xs shadow-lg shadow-cyan-500/20 transition-all"
            >
              <ShieldAlert className="w-4 h-4" />
              <span>AI Data Quality →</span>
            </button>
            <button
              onClick={() => setIsModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-medium text-sm shadow-lg shadow-indigo-600/20 transition-all"
            >
              <Plus className="w-4 h-4" />
              <span>Add Data Source</span>
            </button>
          </div>
        </div>

        {/* Filters & Search */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search sources by name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <span className="text-xs text-slate-500">Filter Type:</span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 focus:outline-none"
            >
              <option value="ALL">All Types</option>
              <option value="CSV">CSV</option>
              <option value="EXCEL">Excel</option>
              <option value="JSON">JSON</option>
              <option value="REST_API">REST API</option>
              <option value="POSTGRESQL">PostgreSQL</option>
            </select>
            <button
              onClick={fetchSources}
              className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
              title="Refresh Sources"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Data Sources Table */}
        <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
          {loading ? (
            <div className="py-16 text-center text-xs text-slate-400 flex flex-col items-center gap-2">
              <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
              <span>Loading data sources...</span>
            </div>
          ) : filteredSources.length === 0 ? (
            <div className="py-16 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
              <Layers className="w-10 h-10 text-slate-600" />
              <p className="font-medium text-slate-300">No data sources found</p>
              <p className="text-slate-500 text-[11px]">
                {sources.length === 0 ? 'Click "Add Data Source" to ingest your first CSV, Excel, JSON, REST API or DB table.' : 'Try adjusting your search query or filter.'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-900/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                    <th className="py-3.5 px-6">Name</th>
                    <th className="py-3.5 px-4">Type</th>
                    <th className="py-3.5 px-4">Rows</th>
                    <th className="py-3.5 px-4">Columns</th>
                    <th className="py-3.5 px-4">Created</th>
                    <th className="py-3.5 px-4">Last Updated</th>
                    <th className="py-3.5 px-6 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {filteredSources.map((source) => {
                    const rowCount = source.configuration?.row_count ?? 'N/A';
                    const colCount = source.configuration?.column_count ?? 'N/A';
                    const createdDate = new Date(source.created_at).toLocaleDateString();
                    const updatedDate = new Date(source.updated_at).toLocaleDateString();

                    return (
                      <tr
                        key={source.id}
                        onClick={() => navigate(`/data-sources/${source.id}`)}
                        className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                      >
                        <td className="py-4 px-6 font-semibold text-slate-200">
                          <div>
                            <span className="text-sm text-white block">{source.name}</span>
                            {source.description && (
                              <span className="text-[11px] text-slate-500 block truncate max-w-xs">{source.description}</span>
                            )}
                          </div>
                        </td>
                        <td className="py-4 px-4">{getTypeBadge(source.type)}</td>
                        <td className="py-4 px-4 font-mono text-slate-300">{rowCount}</td>
                        <td className="py-4 px-4 font-mono text-slate-300">{colCount}</td>
                        <td className="py-4 px-4 text-slate-400 font-mono text-[11px]">{createdDate}</td>
                        <td className="py-4 px-4 text-slate-400 font-mono text-[11px]">{updatedDate}</td>
                        <td className="py-4 px-6 text-right space-x-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/datasets/${source.id}/profile`);
                            }}
                            className="p-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 transition-colors inline-flex items-center gap-1"
                            title="View Data Profile & Quality"
                          >
                            <Activity className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/data-sources/${source.id}`);
                            }}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors inline-flex items-center gap-1"
                            title="View Details"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => handleDelete(source.id, e)}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-900/40 text-rose-400 hover:text-rose-200 transition-colors inline-flex items-center gap-1"
                            title="Delete Source"
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

        {/* Modal */}
        <AddDataSourceModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSuccess={handleSourceAdded}
        />
      </div>
    </MainLayout>
  );
};
