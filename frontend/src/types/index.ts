export interface HealthResponse {
  status: string;
}

export interface DatabaseHealthResponse {
  status: string;
  database: string;
}

export type ComponentStatus = 'loading' | 'healthy' | 'unhealthy' | 'offline';

export interface SystemHealthState {
  api: {
    status: ComponentStatus;
    message?: string;
  };
  database: {
    status: ComponentStatus;
    message?: string;
  };
  frontend: {
    status: ComponentStatus;
    message?: string;
  };
  lastChecked: Date | null;
}

export interface Organization {
  id: number;
  name: string;
}

export interface User {
  id: number;
  organization_id: number;
  name: string;
  email: string;
  role: 'ADMIN' | 'DATA_ENGINEER' | 'ANALYST' | 'VIEWER';
  organization?: Organization;
}

export interface Project {
  id: number;
  name: string;
  organization_id: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface DataSourceConfiguration {
  row_count?: number;
  column_count?: number;
  columns?: string[];
  data_types?: Record<string, string>;
  preview?: Record<string, any>[];
  filename?: string;
  url?: string;
  method?: string;
  host?: string;
  port?: number;
  database?: string;
  table?: string;
  schema?: string;
  [key: string]: any;
}

export interface DataSource {
  id: number;
  organization_id: number;
  name: string;
  type: 'CSV' | 'EXCEL' | 'JSON' | 'REST_API' | 'POSTGRESQL';
  description?: string;
  configuration?: DataSourceConfiguration;
  created_by?: number;
  created_at: string;
  updated_at: string;
}

export interface ConnectionTestResponse {
  success: boolean;
  message: string;
  details?: Record<string, any>;
}

export interface ColumnProfile {
  name: string;
  data_type: string;
  null_count: number;
  null_percentage: number;
  unique_count: number;
  unique_percentage: number;
  min?: number;
  max?: number;
  mean?: number;
  median?: number;
  std?: number;
  outlier_count?: number;
  outliers?: number[];
  cardinality?: number;
  top_values?: { value: any; count: number; percentage: number }[];
  min_date?: string;
  max_date?: string;
  date_distribution?: { period: string; count: number }[];
}

export interface ProfileSummary {
  row_count: number;
  column_count: number;
  duplicate_rows: number;
  memory_bytes: number;
}

export interface QualityScores {
  completeness: number;
  uniqueness: number;
  validity: number;
  overall: number;
}

export interface DataProfile {
  id: number;
  data_source_id: number;
  organization_id: number;
  summary: ProfileSummary;
  column_profiles: ColumnProfile[];
  quality_scores: QualityScores;
  created_at: string;
  updated_at: string;
}


export interface ETLStep {

  type?: string;
  category?: 'transformation' | 'validation';
  rule_type?: string;
  column?: string;
  columns?: string[];
  subset?: string[];
  fill_value?: any;
  mode?: 'lower' | 'upper' | 'title';
  mapping?: Record<string, string>;
  condition?: string;
  target_column?: string;
  formula?: string;
  min_val?: number;
  max_val?: number;
  pattern?: string;
  [key: string]: any;
}

export interface PipelineDestinationConfig {
  table_name: string;
  if_exists?: 'append' | 'replace' | 'fail';
  [key: string]: any;
}

export interface DAGNodeData {
  label: string;
  category: 'source' | 'transformation' | 'validation' | 'destination';
  node_type?: string;
  step_type?: string;
  source_id?: number;
  table_name?: string;
  if_exists?: 'append' | 'replace' | 'fail';
  columns?: string[];
  column?: string;
  subset?: string[];
  fill_value?: any;
  mode?: 'lower' | 'upper' | 'title';
  target_column?: string;
  formula?: string;
  min_val?: number;
  max_val?: number;
  pattern?: string;
  rule_type?: string;
  [key: string]: any;
}

export interface DAGNode {
  id: string;
  type?: string;
  category?: 'source' | 'transformation' | 'validation' | 'destination';
  position: { x: number; y: number };
  data: DAGNodeData;
}

export interface DAGEdge {
  id: string;
  source: string;
  target: string;
  animated?: boolean;
  style?: Record<string, any>;
}

export interface Pipeline {
  id: number;
  organization_id: number;
  name: string;
  description?: string;
  source_id: number;
  steps: ETLStep[];
  destination_config: PipelineDestinationConfig;
  dag_nodes?: DAGNode[];
  dag_edges?: DAGEdge[];
  created_by?: number;
  created_at: string;
  updated_at: string;
}

export interface DAGValidationResponse {
  valid: boolean;
  errors: string[];
  execution_order?: string[];
  source_id?: number;
  destination_config?: PipelineDestinationConfig;
  steps?: ETLStep[];
}


export interface LogEntry {
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR';
  message: string;
}

export interface PipelineExecution {
  id: number;
  pipeline_id: number;
  organization_id: number;
  status: 'PENDING' | 'RUNNING' | 'RETRYING' | 'SUCCESS' | 'FAILED' | 'CANCELLED';
  current_stage?: string;
  celery_task_id?: string;
  retry_count?: number;
  trigger_type?: 'MANUAL' | 'SCHEDULED';
  schedule_id?: number;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  records_read: number;
  records_processed: number;
  records_failed: number;
  records_loaded?: number;
  logs: LogEntry[];
  error?: string;
}

export interface PipelineSchedule {
  id: number;
  organization_id: number;
  pipeline_id: number;
  name: string;
  cron_expression: string;
  timezone: string;
  enabled: boolean;
  next_run_at?: string;
  last_run_at?: string;
  created_at: string;
  updated_at: string;
  pipeline_name?: string;
}

export interface CronValidationRequest {
  cron_expression: string;
  timezone?: string;
}


export interface CronValidationResponse {
  valid: boolean;
  cron_expression: string;
  timezone: string;
  next_run_at?: string;
  error?: string;
}




export interface TableColumnInfo {
  name: string;
  type: string;
  is_primary_key: boolean;
  is_foreign_key: boolean;
}

export interface WarehouseTableSummary {
  table_name: string;
  column_count: number;
  row_count: number;
  primary_keys: string[];
  foreign_keys: string[];
}

export interface WarehouseTableDetail {
  table_name: string;
  columns: TableColumnInfo[];
  primary_keys: string[];
  foreign_keys: string[];
  row_count: number;
  sample_records: Record<string, any>[];
}

export interface RevenueMetrics {
  total_revenue: number;
  total_quantity: number;
  average_order_value: number;
  revenue_by_product: { product_name: string; revenue: number; quantity: number }[];
  revenue_by_category: { category: string; revenue: number }[];
  revenue_by_customer: { customer_name: string; revenue: number }[];
  revenue_by_city: { city: string; revenue: number }[];
  revenue_by_month: { month: string; revenue: number }[];
  top_products: { product_name: string; revenue: number; quantity: number }[];
}

export interface WarehouseTable {
  id: number;
  warehouse_model_id: number;
  table_name: string;
  table_type: 'FACT' | 'DIMENSION';
  description?: string;
  grain?: string;
  primary_keys: string[];
  foreign_keys: string[];
  created_at: string;
  updated_at: string;
}

export interface WarehouseModel {
  id: number;
  organization_id: number;
  name: string;
  slug: string;
  domain: string;
  description?: string;
  is_active: boolean;
  tables: WarehouseTable[];
  created_at: string;
  updated_at: string;
}

export interface GenericWarehouseAnalytics {
  model_id: number;
  model_name: string;
  domain: string;
  total_fact_rows: number;
  total_dimension_rows: number;
  fact_table_count: number;
  dimension_table_count: number;
  tables_summary: WarehouseTableSummary[];
  last_updated?: string;
}

export interface ManufacturingMetrics {
  total_production_batches: number;
  total_units_produced: number;
  total_defect_count: number;
  defect_rate_percentage: number;
  total_operating_hours: number;
  production_by_machine: { machine_name: string; units_produced: number; defect_count: number }[];
  defects_by_plant: { plant_name: string; defect_count: number; units_produced: number }[];
}


export interface SystemHealthInfo {

  overall: string;
  api: string;
  database: string;
  redis: string;
  celery: string;
  active_schedules: number;
  version: string;
}

export interface PipelineOverviewInfo {
  total_executions_today: number;
  successful_today: number;
  failed_today: number;
  retrying_today: number;
  running_today: number;
  success_rate: number;
  average_duration_seconds: number;
  min_duration_seconds: number;
  max_duration_seconds: number;
  total_records_read: number;
  total_records_processed: number;
  total_records_loaded: number;
  total_failed_records: number;
  throughput_records_per_sec: number;
}

export interface PipelineFailureItem {
  pipeline_id: number;
  pipeline_name: string;
  total_executions: number;
  failed_executions: number;
  failure_rate_pct: number;
  last_execution_time: string | null;
}

export interface PipelinePerformanceInfo {
  slowest_pipelines: {
    pipeline_id: number;
    pipeline_name: string;
    avg_duration: number;
    max_duration: number;
    executions_count: number;
  }[];
  highest_volume_pipelines: {
    pipeline_id: number;
    pipeline_name: string;
    total_records_processed: number;
  }[];
  execution_timeline: {
    execution_id: number;
    pipeline_id: number;
    status: string;
    duration_seconds: number;
    records_processed: number;
    records_loaded: number;
    started_at: string | null;
  }[];
}

export interface DataQualitySummaryInfo {
  average_quality_score: number;
  total_profiles_analyzed: number;
  total_quality_warnings: number;
  total_critical_errors: number;
  total_invalid_records: number;
}

export interface ScheduleMonitoringInfo {
  total_schedules: number;
  enabled_schedules: number;
  scheduled_executions_today: number;
  successful_scheduled_today: number;
  failed_scheduled_today: number;
}

export interface MonitoringOverview {
  system_health: SystemHealthInfo;
  pipeline_overview: PipelineOverviewInfo;
  quality_summary: DataQualitySummaryInfo;
  schedule_summary: ScheduleMonitoringInfo;
}

export interface ProposalErrorItem {
  type: string;
  value?: string;
  message: string;
}

export interface AIPipelineProposal {
  proposed_name: string;
  source_id: number;
  source_name: string;
  source_type: string;
  detected_columns: string[];
  steps: ETLStep[];
  destination_config: PipelineDestinationConfig;
  dag_nodes: DAGNode[];
  dag_edges: DAGEdge[];
  explanation: string;
  step_reasons: { step: string; reason: string }[];
  warnings: string[];
  errors?: ProposalErrorItem[];
  requested_operations?: string[];
  resolved_operations?: string[];
  unsupported_operations?: string[];
  status?: 'VALID' | 'INVALID' | 'INCOMPLETE' | 'WARNING';
  can_approve?: boolean;
  confidence_score: number;
  is_valid: boolean;
}










