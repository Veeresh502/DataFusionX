import React, { useState, useEffect } from 'react';
import { DataSource, WarehouseModel } from '../../types';
import { warehouseService } from '../../services/api';
import { X, Trash2, Settings } from 'lucide-react';

interface NodeConfigDrawerProps {
  node: any;
  nodes?: any[];
  sources: DataSource[];
  onClose: () => void;
  onUpdate: (nodeId: string, updatedData: any) => void;
  onDelete: (nodeId: string) => void;
}

export const NodeConfigDrawer: React.FC<NodeConfigDrawerProps> = ({
  node,
  nodes,
  sources,
  onClose,
  onUpdate,
  onDelete,
}) => {
  const [warehouseModels, setWarehouseModels] = useState<WarehouseModel[]>([]);

  useEffect(() => {
    fetchModels();
  }, []);

  const fetchModels = async () => {
    try {
      const modelsList = await warehouseService.listModels();
      setWarehouseModels(modelsList);
    } catch (err) {
      console.error('Failed to load warehouse models', err);
    }
  };

  if (!node) return null;

  const { id, data } = node;
  const category = data.category || 'transformation';
  const nodeType = data.node_type || data.step_type || data.type || '';

  const activeSourceNode = (nodes || []).find(
    (n: any) => n.category === 'source' || n.type?.includes('source') || n.data?.node_type?.includes('source')
  );
  const activeSourceId = data.source_id || activeSourceNode?.data?.source_id;
  const activeSource = sources.find((s) => s.id === Number(activeSourceId));

  let availableColumns: string[] = activeSource?.configuration?.columns || [];
  if (availableColumns.length === 0) {
    const allColsSet = new Set<string>();
    sources.forEach((s) => {
      (s.configuration?.columns || []).forEach((c) => allColsSet.add(c));
    });
    availableColumns = Array.from(allColsSet);
  }



  const handleChange = (field: string, value: any) => {
    onUpdate(id, { [field]: value });
  };

  return (
    <div className="fixed right-0 top-0 bottom-0 w-80 glass-panel border-l border-slate-800 p-6 z-40 flex flex-col justify-between shadow-2xl overflow-y-auto">
      <div className="space-y-6">
        {/* Drawer Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-indigo-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Configure Node</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Node Label Name */}
        <div>
          <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Node Title</label>
          <input
            type="text"
            value={data.label || ''}
            onChange={(e) => handleChange('label', e.target.value)}
            className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none"
          />
        </div>

        {/* Category Specific Form Fields */}
        {category === 'source' && (
          <div className="space-y-4">
            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Select Source Dataset</label>
              <select
                value={data.source_id || ''}
                onChange={(e) => handleChange('source_id', Number(e.target.value))}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none font-mono"
              >
                <option value="">-- Choose Data Source --</option>
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.type})
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {category === 'transformation' && (
          <div className="space-y-4">
            {nodeType === 'remove_duplicates' && (
              <div className="space-y-4">
                {/* 1. Duplicate Detection Mode */}
                <div>
                  <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1.5">
                    Duplicate Detection Mode
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        onUpdate(id, { detection_mode: 'entire_row', columns: [] });
                      }}
                      className={`px-3 py-2 rounded-xl text-xs font-semibold border transition-all ${
                        (data.detection_mode === 'entire_row' || (!data.detection_mode && (!data.columns || data.columns.length === 0)))
                          ? 'bg-indigo-600/30 text-indigo-200 border-indigo-500'
                          : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
                      }`}
                    >
                      Entire Row
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        onUpdate(id, { detection_mode: 'selected_columns' });
                      }}
                      className={`px-3 py-2 rounded-xl text-xs font-semibold border transition-all ${
                        (data.detection_mode === 'selected_columns' || (data.columns && data.columns.length > 0))
                          ? 'bg-indigo-600/30 text-indigo-200 border-indigo-500'
                          : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
                      }`}
                    >
                      Selected Columns
                    </button>
                  </div>
                </div>

                {/* 2. Column Selection Checkboxes when Selected Columns is active */}
                {(data.detection_mode === 'selected_columns' || (data.columns && data.columns.length > 0)) && (
                  <div>
                    <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1.5">
                      Select Columns to Match Duplicates
                    </label>

                    {availableColumns.length > 0 ? (
                      <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1 border border-slate-800 rounded-xl p-2 bg-slate-900/60">
                        {availableColumns.map((col) => {
                          const selectedCols: string[] = Array.isArray(data.columns) ? data.columns : [];
                          const isChecked = selectedCols.includes(col);

                          const toggleColumn = () => {
                            const newCols = isChecked
                              ? selectedCols.filter((c) => c !== col)
                              : [...selectedCols, col];
                            onUpdate(id, { columns: newCols, detection_mode: 'selected_columns' });
                          };

                          return (
                            <label
                              key={col}
                              className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-slate-800/80 cursor-pointer text-xs transition-colors"
                            >
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={toggleColumn}
                                className="w-3.5 h-3.5 rounded bg-slate-800 border-slate-700 text-indigo-600 focus:ring-indigo-500"
                              />
                              <span className="font-mono text-slate-200">{col}</span>
                            </label>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="text-[11px] text-amber-400 bg-amber-500/10 border border-amber-500/20 p-2.5 rounded-xl">
                        No source schema columns detected. Type column names manually below:
                      </div>
                    )}

                    <div className="mt-2">
                      <input
                        type="text"
                        placeholder="Comma-separated column names e.g. order_id"
                        value={Array.isArray(data.columns) ? data.columns.join(', ') : ''}
                        onChange={(e) => {
                          const val = e.target.value;
                          const cols = val.split(',').map((c) => c.trim()).filter(Boolean);
                          onUpdate(id, { columns: cols, detection_mode: 'selected_columns' });
                        }}
                        className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                      />
                    </div>
                  </div>
                )}

                {/* 3. Keep Strategy */}
                <div>
                  <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">
                    Keep Duplicate Strategy
                  </label>
                  <select
                    value={data.keep || 'first'}
                    onChange={(e) => handleChange('keep', e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                  >
                    <option value="first">Keep First Occurrence (first)</option>
                    <option value="last">Keep Last Occurrence (last)</option>
                  </select>
                </div>
              </div>
            )}

            {nodeType === 'calculate_column' && (
              <>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Target Derived Column</label>
                  <input
                    type="text"
                    placeholder="e.g. total_revenue"
                    value={data.target_column || ''}
                    onChange={(e) => handleChange('target_column', e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Formula Expression</label>
                  <input
                    type="text"
                    placeholder="e.g. quantity * unit_price - discount"
                    value={data.formula || ''}
                    onChange={(e) => handleChange('formula', e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                  />
                </div>
              </>
            )}


            {nodeType === 'fill_null' && (
              <div>
                <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Fill Value</label>
                <input
                  type="text"
                  placeholder="e.g. Unknown or 0"
                  value={data.fill_value || ''}
                  onChange={(e) => handleChange('fill_value', e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200"
                />
              </div>
            )}

            {nodeType === 'normalize_text' && (
              <div>
                <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Casing Mode</label>
                <select
                  value={data.mode || 'lower'}
                  onChange={(e) => handleChange('mode', e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                >
                  <option value="lower">lowercase</option>
                  <option value="upper">UPPERCASE</option>
                  <option value="title">Title Case</option>
                </select>
              </div>
            )}

            {nodeType === 'filter_rows' && (
              <div>
                <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Filter Query Condition</label>
                <input
                  type="text"
                  placeholder="e.g. age >= 18 and status == 'active'"
                  value={data.condition || ''}
                  onChange={(e) => handleChange('condition', e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                />
              </div>
            )}
          </div>
        )}

        {category === 'validation' && (
          <div className="space-y-4">
            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Column to Validate</label>
              <input
                type="text"
                placeholder="Column name"
                value={data.column || ''}
                onChange={(e) => handleChange('column', e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
              />
            </div>

            {data.rule_type === 'RANGE' && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Min Value</label>
                  <input
                    type="number"
                    value={data.min_val ?? ''}
                    onChange={(e) => handleChange('min_val', Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Max Value</label>
                  <input
                    type="number"
                    value={data.max_val ?? ''}
                    onChange={(e) => handleChange('max_val', Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200"
                  />
                </div>
              </div>
            )}

            {data.rule_type === 'REGEX' && (
              <div>
                <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Regex Pattern</label>
                <input
                  type="text"
                  placeholder="e.g. ^[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+$"
                  value={data.pattern || ''}
                  onChange={(e) => handleChange('pattern', e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                />
              </div>
            )}
          </div>
        )}

        {category === 'destination' && (
          <div className="space-y-4">
            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Destination Target Type</label>
              <select
                value={data.destination_type === 'WAREHOUSE_STAR_SCHEMA' ? 'WAREHOUSE' : (data.destination_type || 'POSTGRES_TABLE')}
                onChange={(e) => {
                  const val = e.target.value;
                  onUpdate(id, {
                    destination_type: val,
                    warehouse_model_slug: val === 'WAREHOUSE' ? (data.warehouse_model_slug || 'sales') : undefined,
                    label: val === 'WAREHOUSE' ? `Data Warehouse (${data.warehouse_model_slug || 'Sales Analytics'})` : `Flat Table (${data.table_name || 'output'})`
                  });
                }}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
              >
                <option value="POSTGRES_TABLE">Flat PostgreSQL Table</option>
                <option value="WAREHOUSE">Data Warehouse Model</option>
              </select>
            </div>

            {(data.destination_type === 'WAREHOUSE' || data.destination_type === 'WAREHOUSE_STAR_SCHEMA') && (
              <div>
                <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Warehouse Model</label>
                <select
                  value={data.warehouse_model_id || data.warehouse_model_slug || 'sales'}
                  onChange={(e) => {
                    const val = e.target.value;
                    const selectedWm = warehouseModels.find((m) => String(m.id) === val || m.slug === val);
                    const slug = selectedWm ? selectedWm.slug : val;
                    const modelName = selectedWm ? selectedWm.name : val;
                    onUpdate(id, {
                      warehouse_model_id: selectedWm ? selectedWm.id : undefined,
                      warehouse_model_slug: slug,
                      warehouse_model: slug,
                      label: `Warehouse: ${modelName}`
                    });
                  }}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-indigo-500/40 text-xs text-indigo-300 font-mono font-semibold"
                >
                  {warehouseModels.length > 0 ? (
                    warehouseModels.map((wm) => (
                      <option key={wm.id} value={wm.id}>
                        {wm.name} ({wm.domain})
                      </option>
                    ))
                  ) : (
                    <>
                      <option value="sales">Sales Analytics (SALES)</option>
                      <option value="manufacturing">Manufacturing Analytics (MANUFACTURING)</option>
                    </>
                  )}
                </select>
              </div>
            )}

            {data.destination_type !== 'WAREHOUSE' && data.destination_type !== 'WAREHOUSE_STAR_SCHEMA' && (
              <div>
                <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Destination Table Name</label>
                <input
                  type="text"
                  placeholder="e.g. target_sales_orders"
                  value={data.table_name || ''}
                  onChange={(e) => handleChange('table_name', e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                />
              </div>
            )}


            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Table Write Mode (If Exists)</label>
              <select
                value={data.if_exists || 'append'}
                onChange={(e) => handleChange('if_exists', e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
              >
                <option value="append">Append (Insert records into table)</option>
                <option value="replace">Replace (Drop & recreate table)</option>
                <option value="fail">Fail (Error if table exists)</option>
              </select>
            </div>
          </div>
        )}

      </div>

      {/* Footer Delete Button */}
      <div className="pt-6 border-t border-slate-800">
        <button
          onClick={() => {
            onDelete(id);
            onClose();
          }}
          className="w-full py-2.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 text-xs font-semibold flex items-center justify-center gap-2 transition-all"
        >
          <Trash2 className="w-4 h-4" />
          <span>Delete Node</span>
        </button>
      </div>
    </div>
  );
};
