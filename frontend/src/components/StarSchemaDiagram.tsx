import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Database, UserCheck, Package, Calendar, MapPin } from 'lucide-react';



interface StarSchemaDiagramProps {
  tables: Record<string, { row_count: number; column_count: number }>;
  domain?: string;
}

export const StarSchemaDiagram: React.FC<StarSchemaDiagramProps> = ({ tables, domain = 'SALES' }) => {
  const navigate = useNavigate();
  const activeDomain = domain.toUpperCase();

  const getRowCount = (name: string) => tables[name]?.row_count ?? 0;

  if (activeDomain === 'MANUFACTURING') {
    return (
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Database className="w-5 h-5 text-indigo-400" />
              <span>Kimball Star Schema Architecture</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Domain: <span className="text-slate-200 font-semibold uppercase font-mono">MANUFACTURING</span> — Click any dimension or fact table to inspect
            </p>
          </div>
          <span className="px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 text-xs font-mono font-semibold">
            Manufacturing Star Schema
          </span>
        </div>

        <div className="relative py-8 px-4 bg-slate-950/60 rounded-2xl border border-slate-900 overflow-x-auto min-w-[640px]">
          <div className="grid grid-cols-3 grid-rows-3 gap-6 items-center justify-items-center max-w-2xl mx-auto">
            
            {/* Top: dim_machine */}
            <div className="col-start-2 row-start-1 w-full">
              <div
                onClick={() => navigate('/warehouse/dim_machine')}
                className="p-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-cyan-500/40 cursor-pointer shadow-lg transition-all hover:scale-105 group"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-cyan-300 font-mono flex items-center gap-1.5">
                    <Package className="w-3.5 h-3.5 text-cyan-400" />
                    dim_machine
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono">DIM</span>
                </div>
                <p className="text-[10px] text-slate-400">machine_key (PK), machine_id, machine_name</p>
                <span className="text-[10px] text-slate-500 font-mono mt-1 block">{getRowCount('dim_machine')} records</span>
              </div>
            </div>

            {/* Left: dim_plant */}
            <div className="col-start-1 row-start-2 w-full">
              <div
                onClick={() => navigate('/warehouse/dim_plant')}
                className="p-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-emerald-500/40 cursor-pointer shadow-lg transition-all hover:scale-105 group"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-emerald-300 font-mono flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-emerald-400" />
                    dim_plant
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">DIM</span>
                </div>
                <p className="text-[10px] text-slate-400">plant_key (PK), plant_id, plant_name</p>
                <span className="text-[10px] text-slate-500 font-mono mt-1 block">{getRowCount('dim_plant')} records</span>
              </div>
            </div>

            {/* Center: fact_production */}
            <div className="col-start-2 row-start-2 w-full">
              <div
                onClick={() => navigate('/warehouse/fact_production')}
                className="p-4 rounded-xl bg-gradient-to-br from-cyan-900/80 via-slate-900 to-indigo-950 hover:from-cyan-800 border-2 border-cyan-500 cursor-pointer shadow-2xl transition-all hover:scale-105 text-center relative"
              >
                <div className="flex items-center justify-center gap-2 mb-1">
                  <Database className="w-4 h-4 text-cyan-400" />
                  <span className="text-sm font-extrabold text-white font-mono tracking-wide">fact_production</span>
                </div>
                <p className="text-[10px] text-cyan-200 font-sans">Grain: 1 batch run per machine</p>
                <div className="mt-2 text-[10px] font-mono text-cyan-300 bg-cyan-500/10 py-1 rounded border border-cyan-500/20">
                  {getRowCount('fact_production')} Batches Recorded
                </div>
              </div>
            </div>

            {/* Right: dim_date */}
            <div className="col-start-3 row-start-2 w-full">
              <div
                onClick={() => navigate('/warehouse/dim_date')}
                className="p-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-purple-500/40 cursor-pointer shadow-lg transition-all hover:scale-105 group"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-purple-300 font-mono flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-purple-400" />
                    dim_date
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono">DIM</span>
                </div>
                <p className="text-[10px] text-slate-400">date_key (PK YYYYMMDD), quarter, year</p>
                <span className="text-[10px] text-slate-500 font-mono mt-1 block">{getRowCount('dim_date')} records</span>
              </div>
            </div>

          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-400" />
            <span>Kimball Star Schema Architecture</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Domain: <span className="text-slate-200 font-semibold uppercase font-mono">SALES</span> — Click any dimension or fact table to inspect
          </p>
        </div>
        <span className="px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 text-xs font-mono font-semibold">
          Sales Star Schema
        </span>
      </div>

      {/* Visual Star Diagram Layout */}
      <div className="relative py-8 px-4 bg-slate-950/60 rounded-2xl border border-slate-900 overflow-x-auto min-w-[640px]">
        <div className="grid grid-cols-3 grid-rows-3 gap-6 items-center justify-items-center max-w-2xl mx-auto">
          
          {/* Top: dim_customer */}
          <div className="col-start-2 row-start-1 w-full">
            <div
              onClick={() => navigate('/warehouse/dim_customer')}
              className="p-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-indigo-500/40 cursor-pointer shadow-lg transition-all hover:scale-105 group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-indigo-300 font-mono flex items-center gap-1.5">
                  <UserCheck className="w-3.5 h-3.5 text-indigo-400" />
                  dim_customer
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono">SCD Type 2</span>
              </div>
              <p className="text-[10px] text-slate-400">customer_key (PK), customer_id, is_current</p>
              <span className="text-[10px] text-slate-500 font-mono mt-1 block">{getRowCount('dim_customer')} records</span>
            </div>
          </div>

          {/* Left: dim_product */}
          <div className="col-start-1 row-start-2 w-full">
            <div
              onClick={() => navigate('/warehouse/dim_product')}
              className="p-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-cyan-500/40 cursor-pointer shadow-lg transition-all hover:scale-105 group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-cyan-300 font-mono flex items-center gap-1.5">
                  <Package className="w-3.5 h-3.5 text-cyan-400" />
                  dim_product
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono">DIM</span>
              </div>
              <p className="text-[10px] text-slate-400">product_key (PK), product_id, category</p>
              <span className="text-[10px] text-slate-500 font-mono mt-1 block">{getRowCount('dim_product')} records</span>
            </div>
          </div>

          {/* Center: fact_sales */}
          <div className="col-start-2 row-start-2 w-full">
            <div
              onClick={() => navigate('/warehouse/fact_sales')}
              className="p-4 rounded-xl bg-gradient-to-br from-indigo-900/80 via-slate-900 to-indigo-950 hover:from-indigo-800 border-2 border-indigo-500 cursor-pointer shadow-2xl transition-all hover:scale-105 text-center relative"
            >
              <div className="flex items-center justify-center gap-2 mb-1">
                <Database className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-extrabold text-white font-mono tracking-wide">fact_sales</span>
              </div>
              <p className="text-[10px] text-indigo-200 font-sans">Grain: 1 order line per customer</p>
              <div className="mt-2 text-[10px] font-mono text-emerald-300 bg-emerald-500/10 py-1 rounded border border-emerald-500/20">
                {getRowCount('fact_sales')} Facts Recorded
              </div>
            </div>
          </div>

          {/* Right: dim_date */}
          <div className="col-start-3 row-start-2 w-full">
            <div
              onClick={() => navigate('/warehouse/dim_date')}
              className="p-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-purple-500/40 cursor-pointer shadow-lg transition-all hover:scale-105 group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-purple-300 font-mono flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-purple-400" />
                  dim_date
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono">DIM</span>
              </div>
              <p className="text-[10px] text-slate-400">date_key (PK YYYYMMDD), quarter, year</p>
              <span className="text-[10px] text-slate-500 font-mono mt-1 block">{getRowCount('dim_date')} records</span>
            </div>
          </div>

          {/* Bottom: dim_location */}
          <div className="col-start-2 row-start-3 w-full">
            <div
              onClick={() => navigate('/warehouse/dim_location')}
              className="p-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-emerald-500/40 cursor-pointer shadow-lg transition-all hover:scale-105 group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-emerald-300 font-mono flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-emerald-400" />
                  dim_location
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">DIM</span>
              </div>
              <p className="text-[10px] text-slate-400">location_key (PK), city, region, country</p>
              <span className="text-[10px] text-slate-500 font-mono mt-1 block">{getRowCount('dim_location')} records</span>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

