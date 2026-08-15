import React, { useState } from 'react';
import { X, Upload, Globe, Database, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { dataSourceService } from '../services/api';
import { DataSource } from '../types';

interface AddDataSourceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (source: DataSource) => void;
}

export const AddDataSourceModal: React.FC<AddDataSourceModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [activeTab, setActiveTab] = useState<'file' | 'rest' | 'postgres'>('file');
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // File Form State
  const [file, setFile] = useState<File | null>(null);
  const [fileNameInput, setFileNameInput] = useState('');
  const [fileDesc, setFileDesc] = useState('');

  // REST Form State
  const [restForm, setRestForm] = useState({
    name: '',
    description: '',
    url: '',
    method: 'GET',
    authToken: '',
  });

  // Postgres Form State
  const [postgresForm, setPostgresForm] = useState({
    name: '',
    description: '',
    host: 'localhost',
    port: 5432,
    database: 'datafusionx',
    username: 'postgres',
    password: '',
    schema_name: 'public',
    table: '',
  });

  if (!isOpen) return null;

  const handleFileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setErrorMsg('Please select a file to upload (.csv, .xlsx, .xls, .json)');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    const formData = new FormData();
    formData.append('file', file);
    if (fileNameInput.trim()) formData.append('name', fileNameInput);
    if (fileDesc.trim()) formData.append('description', fileDesc);

    try {
      const source = await dataSourceService.uploadFile(formData);
      onSuccess(source);
      onClose();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to upload and ingest file';
      setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  const handleTestREST = async () => {
    if (!restForm.url) {
      setErrorMsg('REST URL is required for testing connection');
      return;
    }
    setTesting(true);
    setTestResult(null);
    setErrorMsg(null);

    try {
      const res = await dataSourceService.testRESTConnection({
        url: restForm.url,
        method: restForm.method,
        auth_token: restForm.authToken || undefined,
      });
      setTestResult({ success: res.success, message: res.message });
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.response?.data?.detail || 'REST Connection Test Failed',
      });
    } finally {
      setTesting(false);
    }
  };

  const handleRESTSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!restForm.name || !restForm.url) {
      setErrorMsg('Name and URL are required');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      const source = await dataSourceService.createSource({
        name: restForm.name,
        type: 'REST_API',
        description: restForm.description,
        configuration: {
          url: restForm.url,
          method: restForm.method,
        },
        credentials: restForm.authToken ? { auth_token: restForm.authToken } : undefined,

      });
      onSuccess(source);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to save REST API source');
    } finally {
      setLoading(false);
    }
  };

  const handleTestPostgres = async () => {
    if (!postgresForm.host || !postgresForm.database || !postgresForm.username) {
      setErrorMsg('Host, Database, and Username are required');
      return;
    }
    setTesting(true);
    setTestResult(null);
    setErrorMsg(null);

    try {
      const res = await dataSourceService.testPostgresConnection({
        host: postgresForm.host,
        port: Number(postgresForm.port),
        database: postgresForm.database,
        username: postgresForm.username,
        password: postgresForm.password,
        schema_name: postgresForm.schema_name,
        table: postgresForm.table || undefined,
      });
      setTestResult({ success: res.success, message: res.message });
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.response?.data?.detail || 'PostgreSQL Connection Test Failed',
      });
    } finally {
      setTesting(false);
    }
  };

  const handlePostgresSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!postgresForm.name || !postgresForm.host || !postgresForm.database || !postgresForm.table) {
      setErrorMsg('Name, Host, Database, and Table name are required');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      const source = await dataSourceService.createSource({
        name: postgresForm.name,
        type: 'POSTGRESQL',
        description: postgresForm.description,
        configuration: {
          host: postgresForm.host,
          port: Number(postgresForm.port),
          database: postgresForm.database,
          schema: postgresForm.schema_name,
          table: postgresForm.table,
        },
        credentials: {
          username: postgresForm.username,
          password: postgresForm.password,
        },
      });
      onSuccess(source);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to save PostgreSQL source');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="w-full max-w-xl glass-panel p-6 rounded-2xl border border-slate-800 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <h2 className="text-xl font-bold text-white mb-1">Add Data Source</h2>
        <p className="text-xs text-slate-400 mb-6">
          Register CSV/Excel/JSON files, REST endpoints, or PostgreSQL databases
        </p>

        {/* Tab Selection */}
        <div className="flex border-b border-slate-800 mb-6 gap-2">
          <button
            onClick={() => { setActiveTab('file'); setErrorMsg(null); setTestResult(null); }}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold border-b-2 transition-all ${
              activeTab === 'file'
                ? 'border-indigo-500 text-indigo-400 bg-indigo-500/10 rounded-t-lg'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Upload className="w-4 h-4" />
            <span>File Upload (CSV/Excel/JSON)</span>
          </button>
          <button
            onClick={() => { setActiveTab('rest'); setErrorMsg(null); setTestResult(null); }}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold border-b-2 transition-all ${
              activeTab === 'rest'
                ? 'border-indigo-500 text-indigo-400 bg-indigo-500/10 rounded-t-lg'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Globe className="w-4 h-4" />
            <span>REST API</span>
          </button>
          <button
            onClick={() => { setActiveTab('postgres'); setErrorMsg(null); setTestResult(null); }}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold border-b-2 transition-all ${
              activeTab === 'postgres'
                ? 'border-indigo-500 text-indigo-400 bg-indigo-500/10 rounded-t-lg'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Database className="w-4 h-4" />
            <span>PostgreSQL</span>
          </button>
        </div>

        {errorMsg && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {testResult && (
          <div
            className={`mb-4 p-3 rounded-xl border text-xs flex items-center gap-2 ${
              testResult.success
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                : 'bg-rose-500/10 border-rose-500/20 text-rose-300'
            }`}
          >
            {testResult.success ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            <span>{testResult.message}</span>
          </div>
        )}

        {/* Tab 1: File Upload */}
        {activeTab === 'file' && (
          <form onSubmit={handleFileSubmit} className="space-y-4">
            <div>
              <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Select File</label>
              <input
                type="file"
                accept=".csv, .xlsx, .xls, .json"
                required
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-500 bg-slate-900 rounded-xl p-2 border border-slate-800"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Source Name (Optional)</label>
              <input
                type="text"
                placeholder="Defaults to filename"
                value={fileNameInput}
                onChange={(e) => setFileNameInput(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Description</label>
              <textarea
                placeholder="Dataset description..."
                value={fileDesc}
                onChange={(e) => setFileDesc(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
              />
            </div>
            <div className="pt-2 flex justify-end gap-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white shadow-lg shadow-indigo-600/20"
              >
                {loading ? 'Ingesting File...' : 'Upload & Process File'}
              </button>
            </div>
          </form>
        )}

        {/* Tab 2: REST API */}
        {activeTab === 'rest' && (
          <form onSubmit={handleRESTSubmit} className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Source Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Weather REST API"
                  value={restForm.name}
                  onChange={(e) => setRestForm({ ...restForm, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Method</label>
                <select
                  value={restForm.method}
                  onChange={(e) => setRestForm({ ...restForm, method: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none"
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Endpoint URL</label>
              <input
                type="url"
                required
                placeholder="https://api.example.com/v1/data"
                value={restForm.url}
                onChange={(e) => setRestForm({ ...restForm, url: e.target.value })}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none font-mono"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase">Bearer Auth Token (Encrypted AES-256)</label>
              <input
                type="password"
                placeholder="Secret bearer token..."
                value={restForm.authToken}
                onChange={(e) => setRestForm({ ...restForm, authToken: e.target.value })}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none font-mono"
              />
            </div>

            <div className="pt-2 flex items-center justify-between">
              <button
                type="button"
                onClick={handleTestREST}
                disabled={testing}
                className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-medium text-indigo-300 flex items-center gap-1.5"
              >
                {testing && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Test Connection</span>
              </button>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white shadow-lg shadow-indigo-600/20"
                >
                  {loading ? 'Saving...' : 'Save REST Source'}
                </button>
              </div>
            </div>
          </form>
        )}

        {/* Tab 3: PostgreSQL */}
        {activeTab === 'postgres' && (
          <form onSubmit={handlePostgresSubmit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-semibold text-slate-400 mb-1 uppercase">Source Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Analytics Postgres DB"
                  value={postgresForm.name}
                  onChange={(e) => setPostgresForm({ ...postgresForm, name: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200"
                />
              </div>
              <div>
                <label className="block text-[10px] font-semibold text-slate-400 mb-1 uppercase">Table Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. orders"
                  value={postgresForm.table}
                  onChange={(e) => setPostgresForm({ ...postgresForm, table: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label className="block text-[10px] font-semibold text-slate-400 mb-1 uppercase">Host</label>
                <input
                  type="text"
                  required
                  placeholder="localhost or db.host.com"
                  value={postgresForm.host}
                  onChange={(e) => setPostgresForm({ ...postgresForm, host: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                />
              </div>
              <div>
                <label className="block text-[10px] font-semibold text-slate-400 mb-1 uppercase">Port</label>
                <input
                  type="number"
                  required
                  value={postgresForm.port}
                  onChange={(e) => setPostgresForm({ ...postgresForm, port: Number(e.target.value) })}
                  className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-semibold text-slate-400 mb-1 uppercase">Database</label>
                <input
                  type="text"
                  required
                  value={postgresForm.database}
                  onChange={(e) => setPostgresForm({ ...postgresForm, database: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                />
              </div>
              <div>
                <label className="block text-[10px] font-semibold text-slate-400 mb-1 uppercase">Username</label>
                <input
                  type="text"
                  required
                  value={postgresForm.username}
                  onChange={(e) => setPostgresForm({ ...postgresForm, username: e.target.value })}
                  className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-semibold text-slate-400 mb-1 uppercase">Password (AES-256 Encrypted)</label>
              <input
                type="password"
                placeholder="Database user password..."
                value={postgresForm.password}
                onChange={(e) => setPostgresForm({ ...postgresForm, password: e.target.value })}
                className="w-full px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono"
              />
            </div>

            <div className="pt-2 flex items-center justify-between">
              <button
                type="button"
                onClick={handleTestPostgres}
                disabled={testing}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-medium text-cyan-300 flex items-center gap-1.5"
              >
                {testing && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Test Connection</span>
              </button>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white shadow-lg shadow-indigo-600/20"
                >
                  {loading ? 'Saving...' : 'Save Postgres Source'}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
