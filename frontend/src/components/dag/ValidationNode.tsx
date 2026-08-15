import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { ShieldCheck } from 'lucide-react';

export const ValidationNode: React.FC<NodeProps> = (props) => {
  const data = props.data as any;
  const selected = props.selected;
  const ruleType = String(data.rule_type || data.type || 'NOT_NULL');


  return (
    <div className={`p-3.5 rounded-xl bg-slate-900 border-2 transition-all shadow-xl min-w-[180px] ${
      selected ? 'border-purple-400 ring-2 ring-purple-400/30' : 'border-purple-500/40 hover:border-purple-400/80'
    }`}>
      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 bg-purple-500 border-2 border-slate-900 shadow-md"
      />

      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] uppercase tracking-wider font-mono font-bold px-2 py-0.5 rounded bg-purple-500/20 text-purple-300">
          Validate
        </span>
        <ShieldCheck className="w-4 h-4 text-purple-400" />
      </div>

      <div className="font-bold text-xs text-white block truncate">{data.label || `RULE: ${ruleType}`}</div>
      <div className="text-[10px] text-purple-300 font-mono mt-1 block truncate">
        Col: {data.column || 'Select column...'}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-purple-500 border-2 border-slate-900 shadow-md"
      />
    </div>
  );
};
