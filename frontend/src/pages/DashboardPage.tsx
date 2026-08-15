import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useHealth } from '../hooks/useHealth';
import { MainLayout } from '../layouts/MainLayout';
import { StatusCard } from '../components/StatusCard';
import { authService, projectService } from '../services/api';
import { User, Project } from '../types';
import { 
  RefreshCw, 
  Server, 
  AlertTriangle, 
  Plus, 
  Folder, 
  UserCheck, 
  Building, 
  Lock, 
  Unlock 
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { healthState, checkHealth } = useHealth();
  
  // Authentication & State
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [newProjectName, setNewProjectName] = useState('');
  
  // Loading & Error States
  const [authLoading, setAuthLoading] = useState(true);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(null);

  // Check Auth & Fetch user data
  useEffect(() => {
    const fetchUserData = async () => {
      const token = localStorage.getItem('datafusionx_token');
      if (!token) {
        navigate('/login');
        return;
      }
      
      try {
        const user = await authService.getMe();
        setCurrentUser(user);
        setAuthLoading(false);
        
        // Fetch Tenant projects
        fetchProjects();
      } catch (err) {
        // Clear token on auth error and redirect
        localStorage.removeItem('datafusionx_token');
        navigate('/login');
      }
    };
    
    fetchUserData();
  }, [navigate]);

  const fetchProjects = async () => {
    setProjectsLoading(true);
    try {
      const data = await projectService.getProjects();
      setProjects(data);
    } catch (err: any) {
      console.error('Failed to fetch projects', err);
    } finally {
      setProjectsLoading(false);
    }
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    
    setActionLoading(true);
    setProjectError(null);
    
    try {
      const project = await projectService.createProject({ name: newProjectName });
      setProjects((prev) => [...prev, project]);
      setNewProjectName('');
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to create project';
      setProjectError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setActionLoading(false);
    }
  };

  if (authLoading || !currentUser) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-indigo-500" />
          <span>Validating Session & Loading Workspace...</span>
        </div>
      </div>
    );
  }

  // Permission Check
  const hasWriteAccess = currentUser.role === 'ADMIN' || currentUser.role === 'DATA_ENGINEER';

  const isAnyUnhealthy =
    healthState.api.status === 'unhealthy' ||
    healthState.database.status === 'unhealthy';

  return (
    <MainLayout onRefresh={checkHealth} lastChecked={healthState.lastChecked}>
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header containing User Profile Summary */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6 border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <span>Platform Health & Tenant Dashboard</span>
            </h1>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-2 text-xs text-slate-400">
              <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-900 border border-slate-800">
                <Building className="w-3.5 h-3.5 text-indigo-400" />
                <span className="font-semibold text-slate-200">Org:</span> {currentUser.organization?.name}
              </span>
              <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-900 border border-slate-800">
                <UserCheck className="w-3.5 h-3.5 text-cyan-400" />
                <span className="font-semibold text-slate-200">User:</span> {currentUser.name} ({currentUser.email})
              </span>
              <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-indigo-950/40 text-indigo-300 border border-indigo-500/20">
                <span className="font-semibold">Role:</span> {currentUser.role}
              </span>
            </div>
          </div>
          <button
            onClick={checkHealth}
            className="self-start md:self-center inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition-colors shadow-lg shadow-indigo-600/20"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Check Status</span>
          </button>
        </div>

        {/* Global Warning Banner if any backend service is unavailable */}
        {isAnyUnhealthy && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-start gap-3 text-rose-300 text-sm">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-rose-200">System Connection Warning</p>
              <p className="text-rose-300/80 text-xs mt-0.5">
                One or more backend components are unreachable. Ensure FastAPI backend and PostgreSQL database containers are running.
              </p>
            </div>
          </div>
        )}

        {/* Multi-Tenant Resource Demonstration Section */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-8">
          
          {/* Projects List Panel */}
          <div className="md:col-span-2 glass-panel p-6 rounded-2xl border border-slate-800 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
                  <Folder className="w-5 h-5 text-indigo-400" />
                  <span>Tenant Projects ({currentUser.organization?.name})</span>
                </h2>
                <button 
                  onClick={fetchProjects}
                  className="p-1.5 rounded-lg hover:bg-slate-800 border border-transparent hover:border-slate-700 text-slate-400 hover:text-slate-200 transition-all"
                  title="Refresh Projects List"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>
              <p className="text-xs text-slate-400 mb-4">
                These projects are isolated strictly to your organization. Users from other organizations cannot see or access them.
              </p>

              {projectsLoading ? (
                <div className="py-8 text-center text-xs text-slate-500">Loading projects...</div>
              ) : projects.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
                  No projects created yet. Use the project panel to add projects.
                </div>
              ) : (
                <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                  {projects.map((project) => (
                    <div 
                      key={project.id}
                      className="px-4 py-3 rounded-xl bg-slate-900/60 border border-slate-800/80 hover:border-slate-700 flex items-center justify-between transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
                        <span className="text-sm font-medium text-slate-200">{project.name}</span>
                      </div>
                      <span className="text-[10px] font-mono text-slate-500">ID: {project.id}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-500">
              Isolation type: <span className="font-mono text-indigo-400">organization_id</span> tenant filter.
            </div>
          </div>

          {/* Project Management & RBAC Panel */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-semibold text-slate-200">Project Console</h2>
                {hasWriteAccess ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-medium">
                    <Unlock className="w-3 h-3" /> Write Access
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 text-[10px] font-medium">
                    <Lock className="w-3 h-3" /> Read Only
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mb-4">
                Creating new projects is restricted to <span className="text-indigo-300 font-medium">ADMIN</span> and <span className="text-indigo-300 font-medium">DATA_ENGINEER</span> roles.
              </p>

              {hasWriteAccess ? (
                <form onSubmit={handleCreateProject} className="space-y-3">
                  <div>
                    <label className="block text-[10px] font-semibold text-slate-500 mb-1 uppercase">Project Name</label>
                    <input
                      type="text"
                      placeholder="e.g. Sales Pipeline Data"
                      value={newProjectName}
                      onChange={(e) => setNewProjectName(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-indigo-500/40"
                    />
                  </div>
                  
                  {projectError && (
                    <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[11px]">
                      {projectError}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={actionLoading}
                    className="w-full py-2 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Create Project</span>
                  </button>
                </form>
              ) : (
                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-center text-xs text-slate-500">
                  Your current role (<span className="text-rose-300 font-mono font-medium">{currentUser.role}</span>) does not allow project creation.
                </div>
              )}
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-500">
              RBAC Check: enforced on server.
            </div>
          </div>

        </section>

        {/* Live Service Indicators (from Milestone 1) */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
              <Server className="w-5 h-5 text-indigo-400" />
              <span>Core Service Status</span>
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <StatusCard
              title="API Service"
              type="api"
              status={healthState.api.status}
              message={healthState.api.message}
              endpoint="GET /health"
            />
            <StatusCard
              title="Database Service"
              type="database"
              status={healthState.database.status}
              message={healthState.database.message}
              endpoint="GET /api/health/database"
            />
            <StatusCard
              title="Frontend Shell"
              type="frontend"
              status={healthState.frontend.status}
              message={healthState.frontend.message}
              endpoint="React Client"
            />
          </div>
        </section>

      </div>
    </MainLayout>
  );
};
