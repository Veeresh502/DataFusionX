import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { warehouseService } from '../services/api';
import { WarehouseTableDetail } from '../types';
import { 
  ArrowLeft, 
  Database, 
  RefreshCw, 
  Table as TableIcon,
  Search
} from 'lucide-react';


export const WarehouseTableDetailPage: React.FC = () => {
  const { table } = useParams<{ table: string }>();
  const [detail, setDetail] = useState<WarehouseTableDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (table) {
      fetchTableDetail(table);
    }
  }, [table]);

  const fetchTableDetail = async (tableName: string) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await warehouseService.getTableDetail(tableName);
      setDetail(data);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to inspect table detail');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="py-24 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
          <span>Inspecting table schema & sample records...</span>
        </div>
      </MainLayout>
    );
  }

  if (errorMsg || !detail) {
    return (
      <MainLayout>
        <div className="max-w-4xl mx-auto py-12 space-y-4">
          <Link to="/warehouse" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white">
            <ArrowLeft className="w-4 h-4" /> Back to Warehouse
          </Link>
          <div className="p-6 rounded-2xl bg-rose-950/40 border border-rose-800 text-rose-300 text-sm">
            {errorMsg || 'Table not found'}
          </div>
        </div>
      </MainLayout>
    );
  }

  const filteredSampleRecords = detail.sample_records.filter((rec) =>
    Object.values(rec).some((val) =>
      String(val).toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Navigation & Header */}
        <div className="border-b border-slate-800 pb-6">
          <Link
            to="/warehouse"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-white mb-3 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Data Warehouse</span>
          </Link>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3 font-mono">
                <Database className="w-8 h-8 text-indigo-400" />
                <span>{detail.table_name}</span>
              </h1>
              <p className="text-slate-400 text-xs mt-1">
                Schema inspection and live sample record preview for analytical warehouse table
              </p>
            </div>

            <div className="flex items-center gap-3">
              <span className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300">
                Rows: <strong className="text-emerald-400">{detail.row_count.toLocaleString()}</strong>
              </span>
              <span className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300">
                Columns: <strong className="text-indigo-400">{detail.columns.length}</strong>
              </span>
            </div>
          </div>
        </div>

        {/* Column Schema Section */}
        <section className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
            <TableIcon className="w-4 h-4 text-indigo-400" />
            <span>Column Schema Definitions</span>
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {detail.columns.map((col) => (
              <div
                key={col.name}
                className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between"
              >
                <div>
                  <span className="text-xs font-mono font-bold text-slate-200 block">{col.name}</span>
                  <span className="text-[10px] font-mono text-slate-500">{col.type}</span>
                </div>
                <div className="flex items-center gap-1">
                  {col.is_primary_key && (
                    <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[9px] font-mono font-bold" title="Primary Key">
                      PK
                    </span>
                  )}
                  {col.is_foreign_key && (
                    <span className="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[9px] font-mono font-bold" title="Foreign Key">
                      FK
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Sample Records Section */}
        <section className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Database className="w-4 h-4 text-emerald-400" />
              <span>Sample Records (Top {detail.sample_records.length})</span>
            </h2>

            <div className="relative w-full sm:w-72">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Filter sample data..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none"
              />
            </div>
          </div>

          {filteredSampleRecords.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
              No records match your filter query.
            </div>
          ) : (
            <div className="overflow-x-auto border border-slate-800 rounded-xl">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-900/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px] font-mono">
                    {detail.columns.map((c) => (
                      <th key={c.name} className="py-3 px-4 whitespace-nowrap">
                        {c.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                  {filteredSampleRecords.map((row, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                      {detail.columns.map((c) => (
                        <td key={c.name} className="py-3 px-4 whitespace-nowrap text-slate-300">
                          {row[c.name] === null || row[c.name] === undefined ? (
                            <span className="text-slate-600 italic">null</span>
                          ) : typeof row[c.name] === 'boolean' ? (
                            <span className={row[c.name] ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
                              {String(row[c.name])}
                            </span>
                          ) : (
                            String(row[c.name])
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

      </div>
    </MainLayout>
  );
};
