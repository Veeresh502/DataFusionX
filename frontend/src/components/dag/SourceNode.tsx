import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Database, FileText, Globe } from 'lucide-react';

export const SourceNode: React.FC<NodeProps> = (props) => {
  const data = props.data as any;
  const selected = props.selected;
  const nodeType = String(data.node_type || 'csv_source').toLowerCase();

  
  const getIcon = () => {
    if (nodeType.includes('excel') || nodeType.includes('csv')) return <FileText className="w-4 h-4 text-blue-400" />;
    if (nodeType.includes('rest')) return <Globe className="w-4 h-4 text-blue-400" />;
    return <Database className="w-4 h-4 text-blue-400" />;
  };

  return (
    <div className={`p-3.5 rounded-xl bg-slate-900 border-2 transition-all shadow-xl min-w-[180px] ${
      selected ? 'border-blue-400 ring-2 ring-blue-400/30' : 'border-blue-500/40 hover:border-blue-400/80'
    }`}>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] uppercase tracking-wider font-mono font-bold px-2 py-0.5 rounded bg-blue-500/20 text-blue-300">
          Source Node
        </span>
        {getIcon()}
      </div>

      <div className="font-bold text-xs text-white block truncate">{data.label || 'Data Source'}</div>
      <div className="text-[10px] text-slate-400 font-mono mt-1">
        {data.source_id ? `Source #${data.source_id}` : 'Select dataset...'}
      </div>

      {/* Target Handle: Source nodes only output data */}
      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-blue-500 border-2 border-slate-900 shadow-md"
      />
    </div>
  );
};
