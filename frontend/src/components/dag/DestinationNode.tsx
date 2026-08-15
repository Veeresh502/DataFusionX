import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Database } from 'lucide-react';

export const DestinationNode: React.FC<NodeProps> = (props) => {
  const data = props.data as any;
  const selected = props.selected;


  return (
    <div className={`p-3.5 rounded-xl bg-slate-900 border-2 transition-all shadow-xl min-w-[190px] ${
      selected ? 'border-emerald-400 ring-2 ring-emerald-400/30' : 'border-emerald-500/40 hover:border-emerald-400/80'
    }`}>
      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 bg-emerald-500 border-2 border-slate-900 shadow-md"
      />

      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] uppercase tracking-wider font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
          Destination
        </span>
        <Database className="w-4 h-4 text-emerald-400" />
      </div>

      <div className="font-bold text-xs text-white block truncate">{data.label || 'PostgreSQL Destination'}</div>
      <div className="text-[10px] text-slate-400 font-mono mt-1 block truncate">
        {data.destination_type === 'WAREHOUSE' || data.destination_type === 'WAREHOUSE_STAR_SCHEMA' ? (
          <span className="text-purple-300 font-semibold">
            Warehouse: {data.warehouse_model_slug ? data.warehouse_model_slug.toUpperCase() : 'SALES'}
          </span>
        ) : (
          <span>Table: <span className="text-emerald-300">{data.table_name || 'transformed_dataset'}</span> ({data.if_exists || 'append'})</span>
        )}
      </div>
    </div>
  );
};


