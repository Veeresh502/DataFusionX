import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, LogOut } from 'lucide-react';

interface NavbarProps {
  onRefresh?: () => void;
  lastChecked?: Date | null;
}

export const Navbar: React.FC<NavbarProps> = ({ onRefresh, lastChecked }) => {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('datafusionx_token');
    navigate('/login');
  };

  return (
    <header className="h-16 glass-panel border-b border-slate-800/80 px-6 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs text-slate-300">
          <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
          <span>System Status Live</span>
        </span>
        {lastChecked && (
          <span className="text-xs text-slate-500 hidden sm:inline">
            Updated {lastChecked.toLocaleTimeString()}
          </span>
        )}
      </div>

      <div className="flex items-center gap-4">
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 font-medium transition-colors"
          >
            Refresh Status
          </button>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-slate-400 hover:text-rose-300 transition-colors"
          title="Sign out / Exit session"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign Out</span>
        </button>
      </div>
    </header>
  );
};
