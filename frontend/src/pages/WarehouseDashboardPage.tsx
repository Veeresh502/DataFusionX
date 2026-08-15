import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { warehouseService } from '../services/api';
import {
  WarehouseModel,
  WarehouseTableSummary,
  RevenueMetrics,
  ManufacturingMetrics,
  GenericWarehouseAnalytics,
} from '../types';
import { StarSchemaDiagram } from '../components/StarSchemaDiagram';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import {
  Database,
  TrendingUp,
  ShoppingBag,
  DollarSign,
  RefreshCw,
  Sparkles,
  Eye,
  Table as TableIcon,
  Layers,
  Activity,
  AlertTriangle,
  Factory,
  Cpu,
} from 'lucide-react';

export const WarehouseDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [models, setModels] = useState<WarehouseModel[]>([]);
  const [selectedModelSlug, setSelectedModelSlug] = useState<string>('sales');
  const [tables, setTables] = useState<WarehouseTableSummary[]>([]);
  const [salesAnalytics, setSalesAnalytics] = useState<RevenueMetrics | null>(null);
  const [mfgAnalytics, setMfgAnalytics] = useState<ManufacturingMetrics | null>(null);
  const [genericAnalytics, setGenericAnalytics] = useState<GenericWarehouseAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  useEffect(() => {
    fetchModels();
  }, []);

  useEffect(() => {
    if (selectedModelSlug) {
      fetchModelData(selectedModelSlug);
    }
  }, [selectedModelSlug]);

  const fetchModels = async () => {
    try {
      const modelList = await warehouseService.listModels();
      setModels(modelList);
      if (modelList.length > 0 && !modelList.some((m) => m.slug === selectedModelSlug)) {
        setSelectedModelSlug(modelList[0].slug);
      }
    } catch (err) {
      console.error('Failed to list warehouse models', err);
    }
  };

  const fetchModelData = async (slug: string) => {
    setLoading(true);
    try {
      const [tableList, genMetrics] = await Promise.all([
        warehouseService.getModelTables(slug),
        warehouseService.getGenericAnalytics(slug),
      ]);
      setTables(tableList);
      setGenericAnalytics(genMetrics);

      const activeModel = models.find((m) => m.slug === slug);
      const domain = activeModel ? activeModel.domain : (slug.includes('mfg') || slug.includes('manufacturing') ? 'MANUFACTURING' : 'SALES');

      if (domain === 'SALES') {
        try {
          const salesMetrics = await warehouseService.getSalesAnalytics(slug);
          setSalesAnalytics(salesMetrics);
        } catch {
          setSalesAnalytics(null);
        }
        setMfgAnalytics(null);
      } else if (domain === 'MANUFACTURING') {
        try {
          const mfgMetrics = await warehouseService.getManufacturingAnalytics(slug);
          setMfgAnalytics(mfgMetrics);
        } catch {
          setMfgAnalytics(null);
        }
        setSalesAnalytics(null);
      } else {
        setSalesAnalytics(null);
        setMfgAnalytics(null);
      }
    } catch (err) {
      console.error(`Failed to fetch warehouse data for model ${slug}`, err);
    } finally {
      setLoading(false);
    }
  };

  const activeModel = models.find((m) => m.slug === selectedModelSlug) || {
    id: 1,
    name: selectedModelSlug === 'manufacturing' ? 'Manufacturing Analytics' : 'Sales Analytics',
    slug: selectedModelSlug,
    domain: selectedModelSlug === 'manufacturing' ? 'MANUFACTURING' : 'SALES',
    description: 'Enterprise Data Warehouse Model',
  };

  const handleSeedSample = async () => {
    setSeeding(true);
    try {
      if (activeModel.domain === 'MANUFACTURING') {
        const res = await warehouseService.seedSampleManufacturing();
        alert(`Successfully loaded ${res.inserted_facts} sample manufacturing batch run records!`);
      } else {
        const res = await warehouseService.seedSampleSales();
        alert(`Successfully loaded ${res.inserted_facts} sample sales records into Kimball Star Schema!`);
      }
      await fetchModelData(selectedModelSlug);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to seed sample data');
    } finally {
      setSeeding(false);
    }
  };

  const handleResetWarehouse = async () => {
    const isMfg = activeModel.domain === 'MANUFACTURING';
    const confirmMsg = isMfg
      ? 'Reset/Clear all Manufacturing Star Schema tables (fact_production, dim_machine, dim_plant)?'
      : 'Reset/Clear all Sales Star Schema tables (fact_sales, dim_customer, dim_product, dim_location)?';

    if (!window.confirm(confirmMsg)) return;

    setLoading(true);
    try {
      if (isMfg) {
        await warehouseService.resetManufacturingData();
      } else {
        await warehouseService.resetWarehouseData();
      }
      alert('Warehouse model data cleared successfully!');
      await fetchModelData(selectedModelSlug);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to reset warehouse data');
    } finally {
      setLoading(false);
    }
  };

  const tableMap = tables.reduce((acc, t) => {
    acc[t.table_name] = { row_count: t.row_count, column_count: t.column_count };
    return acc;
  }, {} as Record<string, { row_count: number; column_count: number }>);

  if (loading && tables.length === 0) {
    return (
      <MainLayout>
        <div className="py-24 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
          <span>Loading Enterprise Data Warehouse & model metrics...</span>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
                <Database className="w-8 h-8 text-indigo-400" />
                <span>Enterprise Data Warehouse</span>
              </h1>
              <span className="px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                {activeModel.domain}
              </span>
            </div>
            <p className="text-slate-400 text-sm mt-1">
              Model: <span className="text-white font-semibold">{activeModel.name}</span> — Kimball Star Schema Architecture
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Warehouse Model Selector */}
            <div className="flex items-center gap-2 bg-slate-900 px-3 py-1.5 rounded-xl border border-slate-800">
              <Layers className="w-4 h-4 text-indigo-400" />
              <label className="text-xs text-slate-400 font-medium">Model:</label>
              <select
                value={selectedModelSlug}
                onChange={(e) => setSelectedModelSlug(e.target.value)}
                className="bg-transparent text-xs font-mono font-bold text-indigo-300 focus:outline-none cursor-pointer"
              >
                {models.length > 0 ? (
                  models.map((m) => (
                    <option key={m.id} value={m.slug} className="bg-slate-900 text-slate-200">
                      {m.name} ({m.domain})
                    </option>
                  ))
                ) : (
                  <>
                    <option value="sales" className="bg-slate-900 text-slate-200">
                      Sales Analytics (SALES)
                    </option>
                    <option value="manufacturing" className="bg-slate-900 text-slate-200">
                      Manufacturing Analytics (MANUFACTURING)
                    </option>
                  </>
                )}
              </select>
            </div>

            <button
              onClick={handleSeedSample}
              disabled={seeding}
              className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-1.5 shadow-lg shadow-indigo-500/20 transition-all disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{seeding ? 'Seeding...' : 'Seed Sample Data'}</span>
            </button>

            <button
              onClick={handleResetWarehouse}
              className="px-3.5 py-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-300 border border-red-500/30 text-xs font-medium flex items-center gap-1.5 transition-all"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Reset Data</span>
            </button>
          </div>
        </div>

        {/* DOMAIN-SPECIFIC KPI CARDS */}
        {activeModel.domain === 'SALES' && salesAnalytics && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-2 relative overflow-hidden">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-xs font-medium uppercase tracking-wider">Total Revenue</span>
                <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400">
                  <DollarSign className="w-5 h-5" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                ${salesAnalytics.total_revenue.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-emerald-400 flex items-center gap-1 font-mono">
                <TrendingUp className="w-3 h-3" />
                Agregated from fact_sales revenue measure
              </p>
            </div>

            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-2 relative overflow-hidden">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-xs font-medium uppercase tracking-wider">Total Units Sold</span>
                <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
                  <ShoppingBag className="w-5 h-5" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                {salesAnalytics.total_quantity.toLocaleString()}
              </div>
              <p className="text-[11px] text-slate-400 font-mono">Total product units loaded in warehouse</p>
            </div>

            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-2 relative overflow-hidden">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-xs font-medium uppercase tracking-wider">Average Order Value</span>
                <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
                  <TrendingUp className="w-5 h-5" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                ${salesAnalytics.average_order_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-slate-400 font-mono">Revenue per distinct order_id</p>
            </div>
          </div>
        )}

        {activeModel.domain === 'MANUFACTURING' && mfgAnalytics && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-xs font-medium uppercase tracking-wider">Batches Recorded</span>
                <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400">
                  <Factory className="w-5 h-5" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                {mfgAnalytics.total_production_batches}
              </div>
              <p className="text-[11px] text-cyan-400 font-mono">fact_production run records</p>
            </div>

            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-xs font-medium uppercase tracking-wider">Units Produced</span>
                <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400">
                  <Cpu className="w-5 h-5" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                {mfgAnalytics.total_units_produced.toLocaleString()}
              </div>
              <p className="text-[11px] text-emerald-400 font-mono">Sum of units_produced</p>
            </div>

            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-xs font-medium uppercase tracking-wider">Defect Count</span>
                <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400">
                  <AlertTriangle className="w-5 h-5" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                {mfgAnalytics.total_defect_count.toLocaleString()}
              </div>
              <p className="text-[11px] text-amber-400 font-mono">Defect Rate: {mfgAnalytics.defect_rate_percentage}%</p>
            </div>

            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-xs font-medium uppercase tracking-wider">Operating Hours</span>
                <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
                  <Activity className="w-5 h-5" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                {mfgAnalytics.total_operating_hours} hrs
              </div>
              <p className="text-[11px] text-purple-400 font-mono">Total machine runtime</p>
            </div>
          </div>
        )}

        {/* GENERIC MODEL OVERVIEW IF DOMAIN SPECIFIC ANALYTICS NOT AVAILABLE */}
        {genericAnalytics && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-slate-900/60 p-4 rounded-2xl border border-slate-800 text-xs">
            <div>
              <span className="text-slate-400 block">Fact Tables:</span>
              <span className="text-white font-bold font-mono text-sm">{genericAnalytics.fact_table_count} tables ({genericAnalytics.total_fact_rows} rows)</span>
            </div>
            <div>
              <span className="text-slate-400 block">Dimension Tables:</span>
              <span className="text-white font-bold font-mono text-sm">{genericAnalytics.dimension_table_count} tables ({genericAnalytics.total_dimension_rows} rows)</span>
            </div>
            <div>
              <span className="text-slate-400 block">Warehouse Model:</span>
              <span className="text-indigo-300 font-bold font-mono">{genericAnalytics.model_name}</span>
            </div>
            <div>
              <span className="text-slate-400 block">Freshness:</span>
              <span className="text-emerald-400 font-mono">Live Sync Active</span>
            </div>
          </div>
        )}

        {/* STAR SCHEMA ARCHITECTURE DIAGRAM */}
        <StarSchemaDiagram tables={tableMap} domain={activeModel.domain} />

        {/* DOMAIN ANALYTICS CHARTS */}
        {activeModel.domain === 'SALES' && salesAnalytics && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono flex items-center justify-between">
                <span>Revenue by Product</span>
                <span className="text-xs text-indigo-400 font-normal">fact_sales ⨝ dim_product</span>
              </h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={salesAnalytics.revenue_by_product}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="product_name" stroke="#64748b" fontSize={10} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem' }}
                      formatter={(val: any) => [`$${Number(val).toLocaleString()}`, 'Revenue']}
                    />
                    <Bar dataKey="revenue" fill="#6366f1" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono flex items-center justify-between">
                <span>Revenue by Customer</span>
                <span className="text-xs text-emerald-400 font-normal">fact_sales ⨝ dim_customer</span>
              </h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={salesAnalytics.revenue_by_customer}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="customer_name" stroke="#64748b" fontSize={10} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem' }}
                      formatter={(val: any) => [`$${Number(val).toLocaleString()}`, 'Revenue']}
                    />
                    <Bar dataKey="revenue" fill="#10b981" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {activeModel.domain === 'MANUFACTURING' && mfgAnalytics && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono flex items-center justify-between">
                <span>Units Produced by Machine</span>
                <span className="text-xs text-cyan-400 font-normal">fact_production ⨝ dim_machine</span>
              </h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={mfgAnalytics.production_by_machine}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="machine_name" stroke="#64748b" fontSize={10} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem' }}
                      formatter={(val: any) => [Number(val).toLocaleString(), 'Units Produced']}
                    />
                    <Bar dataKey="units_produced" fill="#06b6d4" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono flex items-center justify-between">
                <span>Defects by Plant</span>
                <span className="text-xs text-amber-400 font-normal">fact_production ⨝ dim_plant</span>
              </h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={mfgAnalytics.defects_by_plant}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="plant_name" stroke="#64748b" fontSize={10} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem' }}
                      formatter={(val: any) => [Number(val).toLocaleString(), 'Defect Count']}
                    />
                    <Bar dataKey="defect_count" fill="#f59e0b" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {/* WAREHOUSE TABLES SUMMARY LIST */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <TableIcon className="w-5 h-5 text-indigo-400" />
            <span>Warehouse Tables Explorer — {activeModel.name}</span>
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {tables.map((t) => {
              const isFact = t.table_name.startsWith('fact');
              return (
                <div
                  key={t.table_name}
                  onClick={() => navigate(`/warehouse/${t.table_name}`)}
                  className="p-4 rounded-xl bg-slate-900 hover:bg-slate-800/80 border border-slate-800 hover:border-indigo-500/40 cursor-pointer transition-all flex flex-col justify-between group shadow-md"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono font-bold text-sm text-white group-hover:text-indigo-300 transition-colors">
                        {t.table_name}
                      </span>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold ${
                          isFact
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                            : 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                        }`}
                      >
                        {isFact ? 'FACT' : 'DIM'}
                      </span>
                    </div>

                    <div className="text-xs text-slate-400 space-y-1 font-mono">
                      <div>Columns: <span className="text-slate-200">{t.column_count}</span></div>
                      <div>Rows: <span className="text-slate-200">{t.row_count}</span></div>
                      {t.primary_keys.length > 0 && (
                        <div className="text-[10px] text-slate-500 truncate">PK: {t.primary_keys.join(', ')}</div>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-indigo-400 group-hover:translate-x-1 transition-transform">
                    <span>Inspect Table</span>
                    <Eye className="w-3.5 h-3.5" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </MainLayout>
  );
};
