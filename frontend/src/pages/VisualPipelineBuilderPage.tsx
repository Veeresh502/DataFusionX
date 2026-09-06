import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';

import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  NodeTypes,
  BackgroundVariant
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { MainLayout } from '../layouts/MainLayout';
import { pipelineService, dataSourceService } from '../services/api';
import { Pipeline, DataSource, DAGValidationResponse } from '../types';

import { SourceNode } from '../components/dag/SourceNode';
import { TransformationNode } from '../components/dag/TransformationNode';
import { ValidationNode } from '../components/dag/ValidationNode';
import { DestinationNode } from '../components/dag/DestinationNode';
import { NodeConfigDrawer } from '../components/dag/NodeConfigDrawer';

import { 
  ArrowLeft, 
  Save, 
  Play, 
  Copy, 
  AlertCircle, 
  RefreshCw, 
  Layers,
  Database,
  ShieldCheck,
  Sparkles
} from 'lucide-react';
import { useToast } from '../components/Toast';


export const VisualPipelineBuilderPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const isNew = id === 'new' || !id;

  const [sources, setSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [validating, setValidating] = useState(false);

  const [pipelineName, setPipelineName] = useState('');
  const [pipelineDesc, setPipelineDesc] = useState('');
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [validationResult, setValidationResult] = useState<DAGValidationResponse | null>(null);

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const nodeTypes: NodeTypes = useMemo(() => ({
    sourceNode: SourceNode,
    transformationNode: TransformationNode,
    validationNode: ValidationNode,
    destinationNode: DestinationNode,
  }), []);


  useEffect(() => {
    loadSourcesAndPipeline();
  }, [id]);

  const loadSourcesAndPipeline = async () => {
    setLoading(true);
    try {
      const srcList = await dataSourceService.listSources();
      setSources(srcList);

      const locationState = location.state as any;
      if (locationState?.dag_nodes && locationState.dag_nodes.length > 0) {
        if (locationState.proposed_name) setPipelineName(locationState.proposed_name);
        else if (locationState.pipeline_name) setPipelineName(locationState.pipeline_name);
        else setPipelineName('AI Generated Pipeline');

        setNodes(locationState.dag_nodes);
        setEdges(locationState.dag_edges || []);
      } else if (!isNew && id) {
        const pipeData = await pipelineService.getPipeline(Number(id));
        setPipelineName(pipeData.name);
        setPipelineDesc(pipeData.description || '');

        if (pipeData.dag_nodes && pipeData.dag_nodes.length > 0) {
          const flowNodes: Node[] = pipeData.dag_nodes.map((n: any) => ({
            id: strId(n.id),
            type: n.type || getNodeType(n.category),
            position: n.position || { x: 250, y: 150 },
            data: n.data || { label: 'Node', category: 'transformation' },
          }));
          setNodes(flowNodes);

          const flowEdges: Edge[] = (pipeData.dag_edges || []).map((e: any) => ({
            id: e.id || `e-${e.source}-${e.target}`,
            source: strId(e.source),
            target: strId(e.target),
            animated: true,
            style: { stroke: '#6366f1', strokeWidth: 2 },
          }));
          setEdges(flowEdges);
        } else {
          // Initialize default starter nodes if no DAG stored yet
          initDefaultDAG(pipeData, srcList);
        }
      } else {
        // Initialize new pipeline default DAG
        initNewDAG(srcList);
      }
    } catch (err) {

      console.error('Failed to load visual builder data', err);
    } finally {
      setLoading(false);
    }
  };

  const strId = (val: any) => String(val);

  const getNodeType = (category: string) => {
    if (category === 'source') return 'sourceNode';
    if (category === 'validation') return 'validationNode';
    if (category === 'destination') return 'destinationNode';
    return 'transformationNode';
  };

  const initDefaultDAG = (pipeData: Pipeline, srcList: DataSource[]) => {
    const srcId = pipeData.source_id || (srcList[0]?.id ?? 1);
    const initialNodes: Node[] = [
      {
        id: 'node-src-1',
        type: 'sourceNode',
        position: { x: 100, y: 150 },
        data: { label: 'CSV Source Dataset', category: 'source', node_type: 'csv_source', source_id: srcId },
      },
      {
        id: 'node-tf-1',
        type: 'transformationNode',
        position: { x: 380, y: 150 },
        data: { label: 'Remove Duplicates', category: 'transformation', step_type: 'remove_duplicates' },
      },
      {
        id: 'node-dest-1',
        type: 'destinationNode',
        position: { x: 680, y: 150 },
        data: { label: 'PostgreSQL Warehouse', category: 'destination', table_name: pipeData.destination_config?.table_name || 'transformed_dataset', if_exists: 'append' },
      },
    ];

    const initialEdges: Edge[] = [
      { id: 'e1-2', source: 'node-src-1', target: 'node-tf-1', animated: true, style: { stroke: '#6366f1', strokeWidth: 2 } },
      { id: 'e2-3', source: 'node-tf-1', target: 'node-dest-1', animated: true, style: { stroke: '#6366f1', strokeWidth: 2 } },
    ];

    setNodes(initialNodes);
    setEdges(initialEdges);
  };

  const initNewDAG = (srcList: DataSource[]) => {
    setPipelineName('New Visual Pipeline');
    const srcId = srcList[0]?.id ?? 1;

    const initialNodes: Node[] = [
      {
        id: 'node-src-1',
        type: 'sourceNode',
        position: { x: 100, y: 150 },
        data: { label: 'Source Dataset', category: 'source', node_type: 'csv_source', source_id: srcId },
      },
      {
        id: 'node-tf-1',
        type: 'transformationNode',
        position: { x: 380, y: 150 },
        data: { label: 'Remove Duplicates', category: 'transformation', step_type: 'remove_duplicates' },
      },
      {
        id: 'node-dest-1',
        type: 'destinationNode',
        position: { x: 680, y: 150 },
        data: { label: 'PostgreSQL Warehouse', category: 'destination', table_name: 'target_dataset', if_exists: 'append' },
      },
    ];

    const initialEdges: Edge[] = [
      { id: 'e1-2', source: 'node-src-1', target: 'node-tf-1', animated: true, style: { stroke: '#6366f1', strokeWidth: 2 } },
      { id: 'e2-3', source: 'node-tf-1', target: 'node-dest-1', animated: true, style: { stroke: '#6366f1', strokeWidth: 2 } },
    ];

    setNodes(initialNodes);
    setEdges(initialEdges);
  };

  const onConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) => addEdge({ ...params, animated: true, style: { stroke: '#6366f1', strokeWidth: 2 } }, eds)),
    [setEdges]
  );


  const onNodeClick = (_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  };

  const handleUpdateNodeData = (nodeId: string, updatedFields: any) => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === nodeId) {
          return {
            ...n,
            data: {
              ...n.data,
              ...updatedFields,
            },
          };
        }
        return n;
      })
    );

    if (selectedNode && selectedNode.id === nodeId) {
      setSelectedNode((prev: any) => ({
        ...prev,
        data: {
          ...prev.data,
          ...updatedFields,
        },
      }));
    }
  };

  const handleDeleteNode = (nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    setSelectedNode(null);
  };

  const handleAddNode = (category: string, type: string, label: string) => {
    const newId = `node-${Date.now()}`;
    const flowType = getNodeType(category);

    const newNode: Node = {
      id: newId,
      type: flowType,
      position: { x: 300 + Math.random() * 50, y: 150 + Math.random() * 50 },
      data: {
        label,
        category,
        step_type: type,
        node_type: type,
        rule_type: type,
        table_name: 'target_table',
        if_exists: 'append',
        source_id: sources[0]?.id ?? 1,
      },
    };

    setNodes((nds) => [...nds, newNode]);
  };

  const handleValidateDAG = async () => {
    setValidating(true);
    try {
      const payload = {
        dag_nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type,
          category: n.data.category,
          position: n.position,
          data: n.data,
        })),
        dag_edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
        })),
      };

      const res = await pipelineService.validateDAG(payload);
      setValidationResult(res);
      if (res.valid) {
        toast.success('DAG Validation Successful', 'Graph has 0 cycles, 0 orphan nodes, and valid connections.');
      } else {
        toast.warning('DAG Validation Warnings', res.errors?.[0] || 'Graph topology issues detected');
      }
    } catch (err: any) {
      setValidationResult({
        valid: false,
        errors: [err.response?.data?.detail || 'DAG Validation error'],
      });
      toast.error('DAG Validation Error', err.response?.data?.detail || 'DAG Validation failed');
    } finally {
      setValidating(false);
    }
  };

  const validateNodeConfigurations = (): string[] => {
    const configErrors: string[] = [];
    nodes.forEach((n) => {
      const data = n.data || {};
      const cat = data.category || 'transformation';
      const type = data.step_type || data.rule_type || data.node_type || n.type || '';
      const label = data.label || type || n.id;

      if (cat === 'transformation') {
        if (type === 'filter_rows' && (!data.condition || !String(data.condition).trim())) {
          configErrors.push(`Node '${label}': Filter condition is required.`);
        }
        if ((type === 'calculate_column' || type === 'derived_column') && (!data.target_column || !data.formula)) {
          configErrors.push(`Node '${label}': Destination column and formula expression are required.`);
        }
      } else if (cat === 'validation') {
        if (!data.column || !String(data.column).trim()) {
          configErrors.push(`Node '${label}': Target column to validate is required.`);
        }
        if (data.rule_type === 'RANGE' && data.min_val === undefined && data.max_val === undefined && data.min_value === undefined && data.max_value === undefined) {
          configErrors.push(`Node '${label}': Minimum or maximum value is required for Range Validation.`);
        }
        if (data.rule_type === 'REGEX' && (!data.pattern || !String(data.pattern).trim())) {
          configErrors.push(`Node '${label}': Regex pattern is required.`);
        }
      }
    });
    return configErrors;
  };

  const handleSavePipeline = async () => {
    const configErrors = validateNodeConfigurations();
    if (configErrors.length > 0) {
      toast.error('Configuration Error', configErrors[0]);
      return;
    }

    setSaving(true);

    try {
      const dagNodesPayload = nodes.map((n) => ({
        id: n.id,
        type: n.type,
        category: n.data.category,
        position: n.position,
        data: n.data,
      }));

      const dagEdgesPayload = edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
      }));

      const payload = {
        name: pipelineName || 'Visual Pipeline',
        description: pipelineDesc,
        dag_nodes: dagNodesPayload,
        dag_edges: dagEdgesPayload,
      };

      if (isNew) {
        const created = await pipelineService.createPipeline(payload);
        toast.success('Pipeline Created', `Visual DAG Pipeline '${created.name}' created.`);
        navigate(`/pipelines/${created.id}`);
      } else {
        await pipelineService.updatePipeline(Number(id), payload);
        toast.success('Pipeline Saved', 'Visual DAG Pipeline saved successfully.');
      }
    } catch (err: any) {
      toast.error('Save Failed', err.response?.data?.detail || 'Failed to save pipeline');
    } finally {
      setSaving(false);
    }
  };

  const handleClonePipeline = async () => {
    if (isNew || !id) return;
    try {
      const cloned = await pipelineService.clonePipeline(Number(id));
      toast.success('Pipeline Cloned', `Pipeline cloned successfully as '${cloned.name}'.`);
      navigate(`/pipelines/${cloned.id}`);
    } catch (err: any) {
      toast.error('Clone Failed', err.response?.data?.detail || 'Failed to clone pipeline');
    }
  };

  const handleRunNow = async () => {
    if (!id || isNew) return;
    setRunning(true);
    try {
      await handleSavePipeline();
      const exec = await pipelineService.runPipeline(Number(id));
      if (exec.status === 'SUCCESS') {
        toast.success('Execution Complete', `Status: SUCCESS | Read: ${exec.records_read} | Processed: ${exec.records_processed}`);
      } else {
        toast.error('Execution Failed', `Status: FAILED | ${exec.error || 'Validation or execution error'}`);
      }
      navigate(`/pipelines/${id}/executions`);
    } catch (err: any) {
      toast.error('Execution Failed', err.response?.data?.detail || 'Pipeline execution failed');
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="py-24 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
          <span>Loading Visual DAG Canvas...</span>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="h-[calc(100vh-6rem)] flex flex-col space-y-4">
        
        {/* Top Header Controls Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4 shrink-0">
          <div className="flex items-center gap-3">
            <Link
              to="/pipelines"
              className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div>
              <input
                type="text"
                value={pipelineName}
                onChange={(e) => setPipelineName(e.target.value)}
                placeholder="Pipeline Name..."
                className="text-xl font-bold bg-transparent text-white focus:outline-none border-b border-transparent focus:border-indigo-500 font-sans"
              />
              <p className="text-[11px] text-slate-400">
                Visual DAG Builder — Drag, connect, configure nodes & compile into linear ETL engine
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleValidateDAG}
              disabled={validating}
              className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-purple-300 text-xs font-semibold flex items-center gap-1.5 border border-purple-500/30"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Validate DAG</span>
            </button>

            {!isNew && (
              <button
                onClick={handleClonePipeline}
                className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 border border-slate-700"
                title="Clone Pipeline"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>Clone</span>
              </button>
            )}

            <button
              onClick={handleSavePipeline}
              disabled={saving}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-indigo-600/20"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{saving ? 'Saving...' : 'Save DAG'}</span>
            </button>

            {!isNew && (
              <button
                onClick={handleRunNow}
                disabled={running}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-emerald-600/20"
              >
                {running ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                <span>Run Now</span>
              </button>
            )}
          </div>
        </div>

        {/* Validation Errors Alert Banner */}
        {validationResult && !validationResult.valid && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span><strong>DAG Validation Error:</strong> {validationResult.errors.join(' | ')}</span>
            </div>
            <button onClick={() => setValidationResult(null)} className="text-slate-400 hover:text-white text-xs">Dismiss</button>
          </div>
        )}

        {/* Main Canvas Body: Left Palette + Canvas */}
        <div className="flex-1 flex gap-4 overflow-hidden relative rounded-2xl border border-slate-800 glass-panel">
          
          {/* Left Node Palette Sidebar */}
          <div className="w-56 bg-slate-950/80 border-r border-slate-800 p-4 space-y-5 overflow-y-auto shrink-0 text-xs">
            <div className="font-bold text-slate-300 uppercase tracking-wider text-[10px]">Add DAG Nodes</div>

            {/* Sources Group */}
            <div className="space-y-2">
              <div className="text-[10px] font-semibold text-blue-400 uppercase tracking-wider flex items-center gap-1">
                <Database className="w-3 h-3" /> Sources
              </div>
              <button
                onClick={() => handleAddNode('source', 'csv_source', 'CSV Source')}
                className="w-full p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-left font-mono flex items-center justify-between"
              >
                <span>+ CSV Source</span>
              </button>
              <button
                onClick={() => handleAddNode('source', 'postgres_source', 'PostgreSQL Source')}
                className="w-full p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-left font-mono flex items-center justify-between"
              >
                <span>+ Postgres Source</span>
              </button>
            </div>

            {/* Transformations Group */}
            <div className="space-y-2">
              <div className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider flex items-center gap-1">
                <Sparkles className="w-3 h-3" /> Transformations
              </div>
              <button
                onClick={() => handleAddNode('transformation', 'remove_duplicates', 'Remove Duplicates')}
                className="w-full p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-left text-[11px]"
              >
                + Remove Duplicates
              </button>
              <button
                onClick={() => handleAddNode('transformation', 'calculate_column', 'Calculate Column')}
                className="w-full p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-left text-[11px]"
              >
                + Derived Column
              </button>
              <button
                onClick={() => handleAddNode('transformation', 'fill_null', 'Fill NULL')}
                className="w-full p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-left text-[11px]"
              >
                + Fill NULL Values
              </button>
              <button
                onClick={() => handleAddNode('transformation', 'normalize_text', 'Normalize Text')}
                className="w-full p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-left text-[11px]"
              >
                + Normalize Text
              </button>
              <button
                onClick={() => handleAddNode('transformation', 'filter_rows', 'Filter Rows')}
                className="w-full p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-left text-[11px]"
              >
                + Filter Rows
              </button>
            </div>

            {/* Validations Group */}
            <div className="space-y-2">
              <div className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" /> Validations
              </div>
              <button
                onClick={() => handleAddNode('validation', 'NOT_NULL', 'NOT NULL Rule')}
                className="w-full p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-left text-[11px]"
              >
                + NOT NULL Rule
              </button>
              <button
                onClick={() => handleAddNode('validation', 'UNIQUE', 'UNIQUE Rule')}
                className="w-full p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-left text-[11px]"
              >
                + UNIQUE Rule
              </button>
              <button
                onClick={() => handleAddNode('validation', 'RANGE', 'RANGE Rule')}
                className="w-full p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-left text-[11px]"
              >
                + RANGE Rule
              </button>
            </div>

            {/* Destinations Group */}
            <div className="space-y-2">
              <div className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1">
                <Layers className="w-3 h-3" /> Destinations
              </div>
              <button
                onClick={() => handleAddNode('destination', 'postgres_destination', 'PostgreSQL Target')}
                className="w-full p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-left font-mono text-[11px]"
              >
                + Postgres Target
              </button>
            </div>
          </div>

          {/* React Flow Graph Canvas */}
          <div className="flex-1 h-full bg-slate-950 relative">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              nodeTypes={nodeTypes}
              fitView
            >
              <Background variant={BackgroundVariant.Dots} color="#334155" gap={20} size={1} />
              <Controls className="bg-slate-900 border border-slate-800 fill-white" />
              <MiniMap
                nodeColor={(node: any) => {
                  if (node.type === 'sourceNode') return '#3b82f6';
                  if (node.type === 'validationNode') return '#a855f7';
                  if (node.type === 'destinationNode') return '#10b981';
                  return '#6366f1';
                }}
                className="bg-slate-900/90 border border-slate-800"
              />
            </ReactFlow>
          </div>
        </div>

        {/* Slide-over Node Config Drawer */}
        {selectedNode && (
          <NodeConfigDrawer
            node={selectedNode}
            nodes={nodes}
            sources={sources}
            onClose={() => setSelectedNode(null)}
            onUpdate={handleUpdateNodeData}
            onDelete={handleDeleteNode}
          />
        )}


      </div>
    </MainLayout>
  );
};
