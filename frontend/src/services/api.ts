import axios from 'axios';
import { 
  HealthResponse, 
  DatabaseHealthResponse, 
  User, 
  Project, 
  TokenResponse,
  DataSource,
  ConnectionTestResponse,
  DataProfile,
  Pipeline,
  PipelineExecution,
  WarehouseTableSummary,
  WarehouseTableDetail,
  RevenueMetrics,
  WarehouseModel,
  GenericWarehouseAnalytics,
  ManufacturingMetrics,
  DAGValidationResponse,
  PipelineSchedule,
  CronValidationResponse
} from '../types';




const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 5000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Automatically inject Authorization token if available in localStorage
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('datafusionx_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export const healthService = {
  getApiHealth: async (): Promise<HealthResponse> => {
    const response = await apiClient.get<HealthResponse>('/health');
    return response.data;
  },

  getDatabaseHealth: async (): Promise<DatabaseHealthResponse> => {
    const response = await apiClient.get<DatabaseHealthResponse>('/api/health/database');
    return response.data;
  },
};

export const authService = {
  register: async (userData: any): Promise<User> => {
    const response = await apiClient.post<User>('/api/auth/register', userData);
    return response.data;
  },

  login: async (credentials: any): Promise<TokenResponse> => {
    const response = await apiClient.post<TokenResponse>('/api/auth/login', credentials);
    return response.data;
  },

  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/api/auth/me');
    return response.data;
  },
};

export const projectService = {
  getProjects: async (): Promise<Project[]> => {
    const response = await apiClient.get<Project[]>('/api/projects');
    return response.data;
  },

  createProject: async (projectData: { name: string }): Promise<Project> => {
    const response = await apiClient.post<Project>('/api/projects', projectData);
    return response.data;
  },
};

export const dataSourceService = {
  listSources: async (): Promise<DataSource[]> => {
    const response = await apiClient.get<DataSource[]>('/api/sources');
    return response.data;
  },

  getSource: async (id: number): Promise<DataSource> => {
    const response = await apiClient.get<DataSource>(`/api/sources/${id}`);
    return response.data;
  },

  uploadFile: async (formData: FormData): Promise<DataSource> => {
    const response = await apiClient.post<DataSource>('/api/sources/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  createSource: async (data: any): Promise<DataSource> => {
    const response = await apiClient.post<DataSource>('/api/sources', data);
    return response.data;
  },

  deleteSource: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/sources/${id}`);
  },

  testRESTConnection: async (data: any): Promise<ConnectionTestResponse> => {
    const response = await apiClient.post<ConnectionTestResponse>('/api/sources/test-connection/rest', data);
    return response.data;
  },

  testPostgresConnection: async (data: any): Promise<ConnectionTestResponse> => {
    const response = await apiClient.post<ConnectionTestResponse>('/api/sources/test-connection/postgres', data);
    return response.data;
  },

  getDatasetProfile: async (id: number): Promise<DataProfile> => {
    const response = await apiClient.get<DataProfile>(`/api/datasets/${id}/profile`);
    return response.data;
  },
};

export const pipelineService = {
  listPipelines: async (): Promise<Pipeline[]> => {
    const response = await apiClient.get<Pipeline[]>('/api/pipelines');
    return response.data;
  },

  getPipeline: async (id: number): Promise<Pipeline> => {
    const response = await apiClient.get<Pipeline>(`/api/pipelines/${id}`);
    return response.data;
  },

  createPipeline: async (data: any): Promise<Pipeline> => {
    const response = await apiClient.post<Pipeline>('/api/pipelines', data);
    return response.data;
  },

  updatePipeline: async (id: number, data: any): Promise<Pipeline> => {
    const response = await apiClient.put<Pipeline>(`/api/pipelines/${id}`, data);
    return response.data;
  },

  deletePipeline: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/pipelines/${id}`);
  },

  clonePipeline: async (id: number): Promise<Pipeline> => {
    const response = await apiClient.post<Pipeline>(`/api/pipelines/${id}/clone`);
    return response.data;
  },

  validateDAG: async (data: { dag_nodes: any[]; dag_edges: any[] }): Promise<DAGValidationResponse> => {
    const response = await apiClient.post<DAGValidationResponse>('/api/pipelines/validate-dag', data);
    return response.data;
  },

  runPipeline: async (id: number): Promise<PipelineExecution> => {
    const response = await apiClient.post<PipelineExecution>(`/api/pipelines/${id}/run`);
    return response.data;
  },

  getExecutions: async (pipelineId: number): Promise<PipelineExecution[]> => {
    const response = await apiClient.get<PipelineExecution[]>(`/api/pipelines/${pipelineId}/executions`);
    return response.data;
  },

  getExecution: async (executionId: number): Promise<PipelineExecution> => {
    const response = await apiClient.get<PipelineExecution>(`/api/pipelines/executions/${executionId}`);
    return response.data;
  },
};


export const warehouseService = {
  listModels: async (): Promise<WarehouseModel[]> => {
    const response = await apiClient.get<WarehouseModel[]>('/api/warehouse/models');
    return response.data;
  },

  getModelDetail: async (modelIdOrSlug: string | number): Promise<WarehouseModel> => {
    const response = await apiClient.get<WarehouseModel>(`/api/warehouse/models/${modelIdOrSlug}`);
    return response.data;
  },

  getModelTables: async (modelIdOrSlug: string | number): Promise<WarehouseTableSummary[]> => {
    const response = await apiClient.get<WarehouseTableSummary[]>(`/api/warehouse/models/${modelIdOrSlug}/tables`);
    return response.data;
  },

  getGenericAnalytics: async (modelIdOrSlug: string | number): Promise<GenericWarehouseAnalytics> => {
    const response = await apiClient.get<GenericWarehouseAnalytics>(`/api/warehouse/models/${modelIdOrSlug}/analytics`);
    return response.data;
  },

  getSalesAnalytics: async (modelIdOrSlug: string | number): Promise<RevenueMetrics> => {
    const response = await apiClient.get<RevenueMetrics>(`/api/warehouse/models/${modelIdOrSlug}/sales-analytics`);
    return response.data;
  },

  getManufacturingAnalytics: async (modelIdOrSlug: string | number): Promise<ManufacturingMetrics> => {
    const response = await apiClient.get<ManufacturingMetrics>(`/api/warehouse/models/${modelIdOrSlug}/manufacturing-analytics`);
    return response.data;
  },

  seedSampleManufacturing: async (): Promise<{ message: string; inserted_facts: number }> => {
    const response = await apiClient.post<{ message: string; inserted_facts: number }>('/api/warehouse/seed-sample-manufacturing');
    return response.data;
  },

  resetManufacturingData: async (): Promise<{ message: string; deleted: any }> => {
    const response = await apiClient.post<{ message: string; deleted: any }>('/api/warehouse/reset-manufacturing');
    return response.data;
  },

  listTables: async (): Promise<WarehouseTableSummary[]> => {
    const response = await apiClient.get<WarehouseTableSummary[]>('/api/warehouse/tables');
    return response.data;
  },

  getTablesSummary: async (): Promise<WarehouseTableSummary[]> => {
    const response = await apiClient.get<WarehouseTableSummary[]>('/api/warehouse/tables');
    return response.data;
  },

  getFlatDatasets: async (): Promise<WarehouseTableSummary[]> => {
    const response = await apiClient.get<WarehouseTableSummary[]>('/api/warehouse/flat-datasets');
    return response.data;
  },



  getTableDetail: async (tableName: string): Promise<WarehouseTableDetail> => {
    const response = await apiClient.get<WarehouseTableDetail>(`/api/warehouse/tables/${tableName}`);
    return response.data;
  },

  getAnalytics: async (): Promise<RevenueMetrics> => {
    const response = await apiClient.get<RevenueMetrics>('/api/warehouse/analytics');
    return response.data;
  },

  seedSampleSales: async (): Promise<{ message: string; inserted_facts: number }> => {
    const response = await apiClient.post<{ message: string; inserted_facts: number }>('/api/warehouse/seed-sample-sales');
    return response.data;
  },

  resetWarehouseData: async (): Promise<{ message: string; deleted: any }> => {
    const response = await apiClient.post<{ message: string; deleted: any }>('/api/warehouse/reset');
    return response.data;
  },
};

export const scheduleService = {
  getSchedules: async (pipelineId?: number): Promise<PipelineSchedule[]> => {
    const params = pipelineId ? { pipeline_id: pipelineId } : {};
    const response = await apiClient.get<PipelineSchedule[]>('/api/schedules', { params });
    return response.data;
  },

  getSchedule: async (id: number): Promise<PipelineSchedule> => {
    const response = await apiClient.get<PipelineSchedule>(`/api/schedules/${id}`);
    return response.data;
  },

  createSchedule: async (data: {
    name: string;
    pipeline_id: number;
    cron_expression: string;
    timezone?: string;
    enabled?: boolean;
  }): Promise<PipelineSchedule> => {
    const response = await apiClient.post<PipelineSchedule>('/api/schedules', data);
    return response.data;
  },

  updateSchedule: async (id: number, data: Partial<PipelineSchedule>): Promise<PipelineSchedule> => {
    const response = await apiClient.put<PipelineSchedule>(`/api/schedules/${id}`, data);
    return response.data;
  },

  enableSchedule: async (id: number): Promise<PipelineSchedule> => {
    const response = await apiClient.patch<PipelineSchedule>(`/api/schedules/${id}/enable`);
    return response.data;
  },

  disableSchedule: async (id: number): Promise<PipelineSchedule> => {
    const response = await apiClient.patch<PipelineSchedule>(`/api/schedules/${id}/disable`);
    return response.data;
  },

  deleteSchedule: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/schedules/${id}`);
  },

  validateCron: async (cron_expression: string, timezone: string = 'UTC'): Promise<CronValidationResponse> => {
    const response = await apiClient.post<CronValidationResponse>('/api/schedules/validate-cron', {
      cron_expression,
      timezone,
    });
    return response.data;
  },

  getScheduleExecutions: async (scheduleId: number): Promise<PipelineExecution[]> => {
    const response = await apiClient.get<PipelineExecution[]>(`/api/schedules/${scheduleId}/executions`);
    return response.data;
  },
};

export const monitoringService = {
  getOverview: async () => {
    const response = await apiClient.get('/api/monitoring/overview');
    return response.data;
  },

  getSystemHealth: async () => {
    const response = await apiClient.get('/api/monitoring/system-health');
    return response.data;
  },

  getFailures: async () => {
    const response = await apiClient.get('/api/monitoring/failures');
    return response.data;
  },

  getPerformance: async () => {
    const response = await apiClient.get('/api/monitoring/performance');
    return response.data;
  },

  getDataQuality: async () => {
    const response = await apiClient.get('/api/monitoring/data-quality');
    return response.data;
  },

  getSchedules: async () => {
    const response = await apiClient.get('/api/monitoring/schedules');
    return response.data;
  },
};

export const aiService = {
  queryAI: async (question: string, warehouseModel: string = 'sales') => {
    const response = await apiClient.post('/api/ai/query', {
      question,
      warehouse_model: warehouseModel,
    });
    return response.data;
  },

  explainPipelineFailure: async (executionId: number) => {
    const response = await apiClient.post('/api/ai/explain-pipeline', {
      execution_id: executionId,
    });
    return response.data;
  },

  getAIHealth: async () => {
    const response = await apiClient.get('/api/ai/health');
    return response.data;
  },
};









