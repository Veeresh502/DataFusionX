import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Layers, Database, GitCommit, Server, Calendar } from 'lucide-react';


export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 glass-panel border-r border-slate-800 flex flex-col h-screen sticky top-0 z-30">
      {/* Brand Header */}
      <div className="p-6 flex items-center gap-3 border-b border-slate-800/80">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/30">
          <Layers className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="font-bold text-lg tracking-wider bg-gradient-to-r from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">
            DataFusionX
          </h1>
          <span className="text-[10px] font-medium tracking-widest text-indigo-400 uppercase">
            Platform v0.6
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        <div className="px-3 py-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
          Main Menu
        </div>
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
              isActive
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 shadow-inner'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`
          }
        >
          <LayoutDashboard className="w-4 h-4 text-indigo-400" />
          <span>Dashboard</span>
        </NavLink>
        <NavLink
          to="/data-sources"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
              isActive
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 shadow-inner'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`
          }
        >
          <Database className="w-4 h-4 text-cyan-400" />
          <span>Data Sources</span>
        </NavLink>
        <NavLink
          to="/pipelines"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
              isActive
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 shadow-inner'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`
          }
        >
          <GitCommit className="w-4 h-4 text-emerald-400" />
          <span>ETL Pipelines</span>
        </NavLink>
        <NavLink
          to="/schedules"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
              isActive
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 shadow-inner'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`
          }
        >
          <Calendar className="w-4 h-4 text-amber-400" />
          <span>Schedules</span>
        </NavLink>

        <NavLink
          to="/warehouse"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
              isActive
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 shadow-inner'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`
          }
        >
          <Server className="w-4 h-4 text-purple-400" />
          <span>Data Warehouse</span>
        </NavLink>
      </nav>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-800/80 text-xs text-slate-500 flex items-center justify-between">
        <span>Milestone 6</span>
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-indigo-950/60 text-indigo-400 border border-indigo-800/40 font-mono text-[10px]">
          Data Warehouse
        </span>
      </div>
    </aside>
  );
};
