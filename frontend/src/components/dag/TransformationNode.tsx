import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Filter, Calculator, Sparkles } from 'lucide-react';

export const TransformationNode: React.FC<NodeProps> = (props) => {
  const data = props.data as any;
  const selected = props.selected;
  const stepType = String(data.step_type || data.type || 'remove_duplicates');


  const getIcon = () => {
    if (stepType === 'calculate_column') return <Calculator className="w-4 h-4 text-indigo-400" />;
    if (stepType === 'filter_rows') return <Filter className="w-4 h-4 text-indigo-400" />;
    return <Sparkles className="w-4 h-4 text-indigo-400" />;
  };

  return (
    <div className={`p-3.5 rounded-xl bg-slate-900 border-2 transition-all shadow-xl min-w-[190px] ${
      selected ? 'border-indigo-400 ring-2 ring-indigo-400/30' : 'border-indigo-500/40 hover:border-indigo-400/80'
    }`}>
      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 bg-indigo-500 border-2 border-slate-900 shadow-md"
      />

      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] uppercase tracking-wider font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300">
          Transform
        </span>
        {getIcon()}
      </div>

      <div className="font-bold text-xs text-white block truncate">{data.label || stepType}</div>
      <div className="text-[10px] text-slate-400 font-mono mt-1 block truncate">
        {stepType === 'calculate_column' ? `${data.target_column || 'col'} = ${data.formula || 'formula'}` :
         stepType === 'filter_rows' ? `query: ${data.condition || 'all'}` :
         stepType === 'remove_duplicates' ? `cols: ${(data.columns && data.columns.length > 0) ? data.columns.join(', ') : 'entire row'} (${data.keep || 'first'})` :
         `Step: ${stepType}`}
      </div>


      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-indigo-500 border-2 border-slate-900 shadow-md"
      />
    </div>
  );
};
