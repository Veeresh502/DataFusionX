import React from 'react';
import { CheckCircle2, XCircle, Loader2, Server, Database, Monitor } from 'lucide-react';
import { ComponentStatus } from '../types';

interface StatusCardProps {
  title: string;
  type: 'api' | 'database' | 'frontend';
  status: ComponentStatus;
  message?: string;
  endpoint?: string;
}

export const StatusCard: React.FC<StatusCardProps> = ({
  title,
  type,
  status,
  message,
  endpoint,
}) => {
  const getIcon = () => {
    switch (type) {
      case 'api':
        return <Server className="w-5 h-5 text-indigo-400" />;
      case 'database':
        return <Database className="w-5 h-5 text-cyan-400" />;
      case 'frontend':
        return <Monitor className="w-5 h-5 text-purple-400" />;
    }
  };

  const renderBadge = () => {
    switch (status) {
      case 'loading':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs font-medium">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Checking
          </span>
        );
      case 'healthy':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Healthy
          </span>
        );
      case 'unhealthy':
      case 'offline':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 text-xs font-medium">
            <XCircle className="w-3.5 h-3.5" />
            Unhealthy
          </span>
        );
    }
  };

  return (
    <div className="glass-card p-6 rounded-2xl border border-slate-800 shadow-xl transition-all duration-200 hover:border-slate-700/80">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
            {getIcon()}
          </div>
          <div>
            <h3 className="font-semibold text-slate-100">{title}</h3>
            {endpoint && (
              <span className="text-[11px] font-mono text-slate-500 block">
                {endpoint}
              </span>
            )}
          </div>
        </div>
        {renderBadge()}
      </div>

      <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs">
        <span className="text-slate-400 font-medium">Details:</span>
        <span
          className={`font-mono ${
            status === 'healthy'
              ? 'text-emerald-300'
              : status === 'loading'
              ? 'text-amber-300'
              : 'text-rose-300'
          }`}
        >
          {message || (status === 'healthy' ? 'Operational' : 'Unavailable')}
        </span>
      </div>
    </div>
  );
};
