import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { pipelineService, dataSourceService, warehouseService } from '../services/api';
import { DataSource, ETLStep, WarehouseModel } from '../types';
import { 
  ArrowLeft, 
  GitCommit, 
  Trash2, 
  Play, 
  Save, 
  RefreshCw
} from 'lucide-react';

import { useToast } from '../components/Toast';

export const PipelineConfigPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const isNew = id === 'new' || !id;


  const [sources, setSources] = useState<DataSource[]>([]);
  const [warehouseModels, setWarehouseModels] = useState<WarehouseModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Form State
  const [pipelineName, setPipelineName] = useState('');
  const [pipelineDesc, setPipelineDesc] = useState('');
  const [selectedSourceId, setSelectedSourceId] = useState<number | ''>('');
  const [steps, setSteps] = useState<ETLStep[]>([]);
  const [destinationType, setDestinationType] = useState<'POSTGRES_TABLE' | 'WAREHOUSE'>('POSTGRES_TABLE');
  const [selectedWarehouseModelId, setSelectedWarehouseModelId] = useState<number | ''>('');
  const [targetTable, setTargetTable] = useState('transformed_dataset');
  const [ifExists, setIfExists] = useState<'append' | 'replace' | 'fail'>('append');

  useEffect(() => {
    loadSourcesAndPipeline();
  }, [id]);

  const loadSourcesAndPipeline = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [srcList, modelsList] = await Promise.all([
        dataSourceService.listSources(),
        warehouseService.listModels(),
      ]);
      setSources(srcList);
      setWarehouseModels(modelsList);

      if (srcList.length > 0 && !selectedSourceId) {
        setSelectedSourceId(srcList[0].id);
      }

      if (modelsList.length > 0 && !selectedWarehouseModelId) {
        setSelectedWarehouseModelId(modelsList[0].id);
      }

      if (!isNew && id) {
        const pipeData = await pipelineService.getPipeline(Number(id));
        setPipelineName(pipeData.name);
        setPipelineDesc(pipeData.description || '');
        setSelectedSourceId(pipeData.source_id);
        setSteps(pipeData.steps || []);
        
        const destConfig = pipeData.destination_config || {};
        const isWh = destConfig.destination_type === 'WAREHOUSE' || destConfig.destination_type === 'WAREHOUSE_STAR_SCHEMA' || Boolean(destConfig.warehouse_model_id || destConfig.warehouse_model_slug);

        if (isWh) {
          setDestinationType('WAREHOUSE');
          if (destConfig.warehouse_model_id) {
            setSelectedWarehouseModelId(Number(destConfig.warehouse_model_id));
          } else if (destConfig.warehouse_model_slug) {
            const matched = modelsList.find(m => m.slug.toLowerCase() === String(destConfig.warehouse_model_slug).toLowerCase());
            if (matched) setSelectedWarehouseModelId(matched.id);
          }
        } else {
          setDestinationType('POSTGRES_TABLE');
          setTargetTable(destConfig.table_name || 'transformed_dataset');
        }

        setIfExists(destConfig.if_exists || 'append');
      }
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to load pipeline configuration');
    } finally {
      setLoading(false);
    }
  };


  const buildDestinationConfig = () => {
    if (destinationType === 'WAREHOUSE') {
      const selectedWm = warehouseModels.find(m => m.id === Number(selectedWarehouseModelId));
      return {
        destination_type: 'WAREHOUSE',
        warehouse_model_id: selectedWm ? selectedWm.id : (selectedWarehouseModelId ? Number(selectedWarehouseModelId) : undefined),
        warehouse_model_slug: selectedWm ? selectedWm.slug : 'sales',
        table_name: selectedWm ? selectedWm.slug : 'sales',
        if_exists: ifExists,
      };
    } else {
      return {
        destination_type: 'POSTGRES_TABLE',
        table_name: targetTable || 'transformed_dataset',
        if_exists: ifExists,
      };
    }
  };

  const handleAddTransformationStep = (type: string) => {
    const newStep: ETLStep = { category: 'transformation', type };
    if (type === 'trim_text') newStep.columns = [];
    if (type === 'normalize_text') { newStep.columns = []; newStep.mode = 'lower'; }
    if (type === 'fill_null') { newStep.columns = []; newStep.fill_value = 'N/A'; }
    if (type === 'calculate_column') { newStep.target_column = 'derived_col'; newStep.formula = 'col1 * col2'; }
    if (type === 'filter_rows') { newStep.condition = 'age >= 18'; }
    setSteps([...steps, newStep]);
  };

  const handleAddValidationRule = (ruleType: string) => {
    const newStep: ETLStep = { 
      category: 'validation', 
      rule_type: ruleType,
      column: '',
    };
    if (ruleType === 'RANGE') { newStep.min_val = 0; newStep.max_val = 1000; }
    if (ruleType === 'REGEX') { newStep.pattern = '^.+$'; }
    setSteps([...steps, newStep]);
  };

  const handleRemoveStep = (index: number) => {
    setSteps(steps.filter((_, i) => i !== index));
  };

  const handleUpdateStep = (index: number, updatedFields: Partial<ETLStep>) => {
    const updated = [...steps];
    updated[index] = { ...updated[index], ...updatedFields };
    setSteps(updated);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pipelineName || !selectedSourceId) {
      setErrorMsg('Pipeline Name and Source Dataset are required');
      toast.warning('Missing Required Fields', 'Pipeline Name and Source Dataset are required.');
      return;
    }
    if (destinationType === 'POSTGRES_TABLE' && !targetTable) {
      setErrorMsg('Destination Table Name is required for Flat PostgreSQL Table');
      toast.warning('Missing Target Table', 'Destination Table Name is required.');
      return;
    }

    setSaving(true);
    setErrorMsg(null);

    const payload = {
      name: pipelineName,
      description: pipelineDesc,
      source_id: Number(selectedSourceId),
      steps: steps,
      destination_config: buildDestinationConfig(),
    };

    try {
      if (isNew) {
        const created = await pipelineService.createPipeline(payload);
        toast.success('Pipeline Created', `Pipeline '${created.name}' created successfully.`);
        navigate(`/pipelines/${created.id}`);
      } else {
        await pipelineService.updatePipeline(Number(id), payload);
        toast.success('Pipeline Updated', 'Pipeline configuration saved successfully.');
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to save pipeline';
      setErrorMsg(msg);
      toast.error('Save Failed', msg);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAndRun = async () => {
    if (!pipelineName || !selectedSourceId) {
      setErrorMsg('Pipeline Name and Source Dataset are required');
      toast.warning('Missing Required Fields', 'Pipeline Name and Source Dataset are required.');
      return;
    }
    if (destinationType === 'POSTGRES_TABLE' && !targetTable) {
      setErrorMsg('Destination Table Name is required for Flat PostgreSQL Table');
      toast.warning('Missing Target Table', 'Destination Table Name is required.');
      return;
    }

    setRunning(true);
    setErrorMsg(null);

    const payload = {
      name: pipelineName,
      description: pipelineDesc,
      source_id: Number(selectedSourceId),
      steps: steps,
      destination_config: buildDestinationConfig(),
    };

    try {
      let pipeId = Number(id);
      if (isNew) {
        const created = await pipelineService.createPipeline(payload);
        pipeId = created.id;
      } else {
        await pipelineService.updatePipeline(pipeId, payload);
      }

      const exec = await pipelineService.runPipeline(pipeId);
      if (exec.status === 'SUCCESS') {
        toast.success('Pipeline Execution Complete', `Status: ${exec.status} | Read: ${exec.records_read} | Processed: ${exec.records_processed} | Loaded: ${exec.records_loaded ?? 0}`);
      } else {
        toast.error('Pipeline Execution Failed', `Status: ${exec.status} | ${exec.error || 'Validation or execution failed'}`);
      }

      navigate(`/pipelines/${pipeId}/executions`);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Pipeline run failed';
      setErrorMsg(msg);
      toast.error('Pipeline Run Failed', msg);
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="py-24 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
          <span>Loading pipeline configurator...</span>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="max-w-5xl mx-auto space-y-8">
        
        {/* Navigation & Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <Link
              to="/pipelines"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-white mb-2 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Pipelines</span>
            </Link>
            <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <GitCommit className="w-7 h-7 text-indigo-400" />
              <span>{isNew ? 'Configure New ETL Pipeline' : `Edit Pipeline: ${pipelineName}`}</span>
            </h1>
            <p className="text-slate-400 text-xs mt-1">
              Linear step-based configuration: Extract dataset -&gt; Transformations -&gt; Validations -&gt; Load to {destinationType === 'WAREHOUSE' ? 'Data Warehouse' : 'PostgreSQL Table'}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 flex items-center gap-2 border border-slate-700"
            >
              <Save className="w-4 h-4" />
              <span>{saving ? 'Saving...' : 'Save Config'}</span>
            </button>
            <button
              onClick={handleSaveAndRun}
              disabled={running}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white text-xs font-medium flex items-center gap-2 shadow-lg shadow-emerald-600/20"
            >
              {running ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>{running ? 'Running Pipeline...' : 'Run Pipeline Now'}</span>
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
            {errorMsg}
          </div>
        )}

        {/* Step 1: Basic & Extract Source Config */}
        <section className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-bold">1</span>
            <span>Extraction Source Configuration</span>
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Pipeline Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Enterprise ETL Pipeline"
                value={pipelineName}
                onChange={(e) => setPipelineName(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Select Source Dataset</label>
              <select
                value={selectedSourceId}
                onChange={(e) => setSelectedSourceId(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none font-mono"
              >
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.type}) - {s.configuration?.row_count ?? 'N/A'} rows
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        {/* Step 2: Linear Transformations & Validation Builder */}
        <section className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-bold">2</span>
              <span>Transformation & Validation Steps ({steps.length})</span>
            </h2>

            {/* Quick Add Step Dropdowns */}
            <div className="flex items-center gap-2">
              <select
                onChange={(e) => {
                  if (e.target.value) {
                    handleAddTransformationStep(e.target.value);
                    e.target.value = '';
                  }
                }}
                className="px-3 py-1.5 rounded-xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-300 text-xs font-medium focus:outline-none"
              >
                <option value="">+ Add Transformation</option>
                <option value="remove_duplicates">Remove Duplicates</option>
                <option value="fill_null">Fill NULL Values</option>
                <option value="drop_null">Drop NULL Values</option>
                <option value="trim_text">Trim Whitespace Text</option>
                <option value="normalize_text">Normalize Text (lower/upper)</option>
                <option value="calculate_column">Calculate Derived Column</option>
                <option value="filter_rows">Filter Rows</option>
              </select>

              <select
                onChange={(e) => {
                  if (e.target.value) {
                    handleAddValidationRule(e.target.value);
                    e.target.value = '';
                  }
                }}
                className="px-3 py-1.5 rounded-xl bg-purple-600/20 border border-purple-500/30 text-purple-300 text-xs font-medium focus:outline-none"
              >
                <option value="">+ Add Validation Rule</option>
                <option value="NOT_NULL">NOT NULL Rule</option>
                <option value="UNIQUE">UNIQUE / Primary Key</option>
                <option value="RANGE">RANGE Rule (min/max)</option>
                <option value="REGEX">REGEX Pattern Rule</option>
              </select>
            </div>
          </div>

          {steps.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
              No transformation or validation steps configured yet. Use the buttons above to add steps.
            </div>
          ) : (
            <div className="space-y-3">
              {steps.map((step, idx) => {
                const isValidation = step.category === 'validation';
                return (
                  <div
                    key={idx}
                    className={`p-4 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                      isValidation
                        ? 'bg-purple-950/20 border-purple-800/40 text-purple-200'
                        : 'bg-slate-900/60 border-slate-800 text-slate-200'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-slate-500 text-xs w-6">{idx + 1}.</span>
                      <span className={`px-2.5 py-0.5 rounded text-[11px] font-mono font-semibold uppercase ${
                        isValidation ? 'bg-purple-500/20 text-purple-300' : 'bg-indigo-500/20 text-indigo-300'
                      }`}>
                        {isValidation ? `VALIDATE: ${step.rule_type}` : step.type}
                      </span>
                    </div>

                    {/* Dynamic Step Configuration Fields */}
                    <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                      {step.type === 'calculate_column' && (
                        <>
                          <input
                            type="text"
                            placeholder="Target Column Name"
                            value={step.target_column || ''}
                            onChange={(e) => handleUpdateStep(idx, { target_column: e.target.value })}
                            className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono"
                          />
                          <input
                            type="text"
                            placeholder="Formula: quantity * unit_price - discount"
                            value={step.formula || ''}
                            onChange={(e) => handleUpdateStep(idx, { formula: e.target.value })}
                            className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono"
                          />
                        </>
                      )}

                      {step.type === 'fill_null' && (
                        <>
                          <input
                            type="text"
                            placeholder="Fill Value"
                            value={step.fill_value || ''}
                            onChange={(e) => handleUpdateStep(idx, { fill_value: e.target.value })}
                            className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs"
                          />
                        </>
                      )}

                      {isValidation && (
                        <input
                          type="text"
                          placeholder="Column Name to Validate"
                          value={step.column || ''}
                          onChange={(e) => handleUpdateStep(idx, { column: e.target.value })}
                          className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono"
                        />
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => handleRemoveStep(idx)}
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-900/40 text-rose-400 hover:text-rose-200 transition-colors self-end md:self-center"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Step 3: Generic Destination Config */}
        <section className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-bold">3</span>
            <span>DESTINATION</span>
          </h2>

          <div className="space-y-4">
            <div>
              <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Destination Type</label>
              <select
                value={destinationType}
                onChange={(e) => setDestinationType(e.target.value as any)}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none font-mono font-semibold"
              >
                <option value="POSTGRES_TABLE">Flat PostgreSQL Table</option>
                <option value="WAREHOUSE">Data Warehouse</option>
              </select>
            </div>

            {destinationType === 'POSTGRES_TABLE' ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Destination Table Name</label>
                  <input
                    type="text"
                    required={destinationType === 'POSTGRES_TABLE'}
                    placeholder="e.g. target_sales_orders"
                    value={targetTable}
                    onChange={(e) => setTargetTable(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Table Write Mode (If Exists)</label>
                  <select
                    value={ifExists}
                    onChange={(e) => setIfExists(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none"
                  >
                    <option value="append">Append (Insert records into existing table)</option>
                    <option value="replace">Replace (Drop & recreate table)</option>
                    <option value="fail">Fail (Error if table exists)</option>
                  </select>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Warehouse Model</label>
                  <select
                    value={selectedWarehouseModelId}
                    onChange={(e) => setSelectedWarehouseModelId(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-indigo-500/40 text-xs text-indigo-300 font-mono font-bold focus:outline-none"
                  >
                    {warehouseModels.length > 0 ? (
                      warehouseModels.map((wm) => (
                        <option key={wm.id} value={wm.id}>
                          {wm.name} ({wm.domain})
                        </option>
                      ))
                    ) : (
                      <>
                        <option value={1}>Generic Warehouse (GENERIC)</option>
                        <option value={2}>Sales Analytics (SALES)</option>
                        <option value={3}>Manufacturing Analytics (MANUFACTURING)</option>
                      </>

                    )}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase font-mono">Fact Load Mode</label>
                  <select
                    value={ifExists}
                    onChange={(e) => setIfExists(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none font-mono"
                  >
                    <option value="append">Append (Star Schema Surrogate Upsert)</option>
                  </select>
                </div>
              </div>
            )}
          </div>
        </section>

      </div>
    </MainLayout>
  );
};
