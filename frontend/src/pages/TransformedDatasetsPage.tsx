import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { warehouseService } from '../services/api';
import { WarehouseTableSummary } from '../types';
import { 
  Database, 
  RefreshCw, 
  Search, 
  Eye, 
  Layers,
  CheckCircle2
} from 'lucide-react';

export const TransformedDatasetsPage: React.FC = () => {
  const navigate = useNavigate();
  const [datasets, setDatasets] = useState<WarehouseTableSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchDatasets();
  }, []);

  const fetchDatasets = async () => {
    setLoading(true);
    try {
      const data = await warehouseService.getFlatDatasets();
      setDatasets(data);
    } catch (err) {
      console.error('Failed to fetch flat transformed datasets', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredDatasets = datasets.filter((d) =>
    d.table_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <Database className="w-8 h-8 text-emerald-400" />
              <span>Transformed Output Datasets</span>
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Explore and inspect all output datasets created & written directly to PostgreSQL flat tables by generic ETL pipelines
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="px-3.5 py-1.5 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-mono font-bold flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4" />
              <span>{datasets.length} Transformed Table{datasets.length === 1 ? '' : 's'}</span>
            </span>
            <button
              onClick={fetchDatasets}
              className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition-colors"
              title="Refresh Datasets"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="flex items-center justify-between gap-4">
          <div className="relative w-full sm:w-96">
            <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search transformed dataset by table name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/50"
            />
          </div>
        </div>

        {/* Datasets Grid */}
        {loading ? (
          <div className="py-20 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
            <RefreshCw className="w-8 h-8 animate-spin text-emerald-400" />
            <span>Scanning PostgreSQL for transformed output tables...</span>
          </div>
        ) : filteredDatasets.length === 0 ? (
          <div className="glass-panel p-12 rounded-2xl border border-slate-800 text-center space-y-3">
            <Layers className="w-10 h-10 text-slate-600 mx-auto" />
            <h3 className="text-base font-bold text-white">No Transformed Datasets Found</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              {datasets.length === 0
                ? 'Run an ETL pipeline with PostgreSQL destination to write your first transformed dataset.'
                : 'No transformed datasets match your search query.'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
            {filteredDatasets.map((fd) => (
              <div
                key={fd.table_name}
                onClick={() => navigate(`/warehouse/${fd.table_name}`)}
                className="glass-panel p-5 rounded-2xl border border-emerald-500/20 hover:border-emerald-400/60 bg-slate-900/80 hover:bg-slate-800/90 cursor-pointer transition-all flex flex-col justify-between group shadow-xl hover:shadow-emerald-500/5"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-base text-emerald-300 group-hover:text-emerald-200 transition-colors truncate">
                      {fd.table_name}
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      POSTGRES TABLE
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                    <div>
                      <span className="text-slate-500 block text-[10px] uppercase">Columns</span>
                      <span className="text-slate-200 font-bold text-sm">{fd.column_count}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px] uppercase">Rows Loaded</span>
                      <span className="text-emerald-400 font-bold text-sm">{fd.row_count.toLocaleString()}</span>
                    </div>
                  </div>

                  {fd.primary_keys.length > 0 && (
                    <div className="text-[11px] font-mono text-slate-400">
                      Primary Key: <span className="text-amber-300 font-semibold">{fd.primary_keys.join(', ')}</span>
                    </div>
                  )}
                </div>

                <div className="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-emerald-400 group-hover:translate-x-1 transition-transform font-semibold">
                  <span>Inspect Schema & Records</span>
                  <Eye className="w-4 h-4" />
                </div>
              </div>
            ))}
          </div>
        )}

      </div>
    </MainLayout>
  );
};
