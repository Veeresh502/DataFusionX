import React, { useState, useEffect } from 'react';
import { MainLayout } from '../layouts/MainLayout';
import { useToast } from '../components/Toast';
import { ConfirmModal } from '../components/ConfirmModal';


import { scheduleService, pipelineService } from '../services/api';
import { PipelineSchedule, Pipeline, CronValidationResponse } from '../types';
import {
  Calendar,
  Clock,
  Plus,
  Trash2,
  Edit2,
  Power,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Globe,
  Check,
  X,
  Search,
} from 'lucide-react';


const COMMON_TIMEZONES = [
  'UTC',
  'Asia/Kolkata',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Asia/Tokyo',
  'Asia/Singapore',
  'Australia/Sydney',
];

const CRON_PRESETS = [
  { label: 'Every 5 Minutes', cron: '*/5 * * * *' },
  { label: 'Every 15 Minutes', cron: '*/15 * * * *' },
  { label: 'Every Hour', cron: '0 * * * *' },
  { label: 'Daily at Midnight', cron: '0 0 * * *' },
  { label: 'Daily at 9:00 AM', cron: '0 9 * * *' },
  { label: 'Mon-Fri at 9:00 AM', cron: '0 9 * * 1-5' },
];

export const PipelineSchedulesPage: React.FC = () => {
  const toast = useToast();
  const [schedules, setSchedules] = useState<PipelineSchedule[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  // Modal State
  const [showModal, setShowModal] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<PipelineSchedule | null>(null);
  
  // Form State
  const [name, setName] = useState('');
  const [pipelineId, setPipelineId] = useState<number | ''>('');
  const [cronExpr, setCronExpr] = useState('0 9 * * *');
  const [timezone, setTimezone] = useState('UTC');
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Confirm Modal Delete State
  const [deleteTargetId, setDeleteTargetId] = useState<number | null>(null);

  // Live Validation Preview State
  const [validation, setValidation] = useState<CronValidationResponse | null>(null);
  const [validating, setValidating] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [schedList, pipeList] = await Promise.all([
        scheduleService.getSchedules(),
        pipelineService.listPipelines(),
      ]);
      setSchedules(schedList);
      setPipelines(pipeList);
      if (pipeList.length > 0 && !pipelineId) {
        setPipelineId(pipeList[0].id);
      }
    } catch (err) {
      console.error('Failed to load schedules or pipelines', err);
    } finally {
      setLoading(false);
    }
  };

  // Live Cron Validation Effect
  useEffect(() => {
    if (!cronExpr) {
      setValidation(null);
      return;
    }
    const timer = setTimeout(async () => {
      setValidating(true);
      try {
        const res = await scheduleService.validateCron(cronExpr, timezone);
        setValidation(res);
      } catch (err) {
        setValidation({
          valid: false,
          cron_expression: cronExpr,
          timezone,
          error: 'Failed to validate cron expression',
        });
      } finally {
        setValidating(false);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [cronExpr, timezone]);

  const handleOpenCreateModal = async () => {
    setEditingSchedule(null);
    setName('');
    setCronExpr('0 9 * * *');
    setTimezone('UTC');
    setEnabled(true);
    setFormError(null);
    
    try {
      const pipeList = await pipelineService.listPipelines();
      setPipelines(pipeList);
      if (pipeList.length > 0) {
        setPipelineId(pipeList[0].id);
      } else {
        setPipelineId('');
      }
    } catch (err) {
      console.error('Failed to load pipelines', err);
    }
    
    setShowModal(true);
  };

  const handleOpenEditModal = (sched: PipelineSchedule) => {
    setEditingSchedule(sched);
    setName(sched.name);
    setPipelineId(sched.pipeline_id);
    setCronExpr(sched.cron_expression);
    setTimezone(sched.timezone);
    setEnabled(sched.enabled);
    setFormError(null);
    setShowModal(true);
  };

  const handleSaveSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!name || !pipelineId || !cronExpr) {
      setFormError('Please fill out all required schedule fields.');
      return;
    }
    if (validation && !validation.valid) {
      setFormError(validation.error || 'Please fix invalid cron expression or timezone before saving.');
      return;
    }

    setSaving(true);
    try {
      if (editingSchedule) {
        await scheduleService.updateSchedule(editingSchedule.id, {
          name,
          cron_expression: cronExpr,
          timezone,
          enabled,
        });
        toast.success('Schedule Updated', `Schedule '${name}' has been updated.`);
      } else {
        await scheduleService.createSchedule({
          name,
          pipeline_id: Number(pipelineId),
          cron_expression: cronExpr,
          timezone,
          enabled,
        });
        toast.success('Schedule Created', `Schedule '${name}' has been created successfully.`);
      }
      setShowModal(false);
      fetchData();
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || 'Failed to save schedule';
      setFormError(errMsg);
      toast.error('Schedule Error', errMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (sched: PipelineSchedule) => {
    try {
      if (sched.enabled) {
        await scheduleService.disableSchedule(sched.id);
        toast.info('Schedule Disabled', `Schedule '${sched.name}' is now disabled.`);
      } else {
        await scheduleService.enableSchedule(sched.id);
        toast.success('Schedule Enabled', `Schedule '${sched.name}' is now active.`);
      }
      fetchData();
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || 'Failed to toggle schedule state';
      toast.error('Toggle Error', errMsg);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTargetId) return;
    try {
      await scheduleService.deleteSchedule(deleteTargetId);
      toast.success('Schedule Deleted', 'The schedule was removed.');
      setDeleteTargetId(null);
      fetchData();
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || 'Failed to delete schedule';
      toast.error('Delete Error', errMsg);
    }
  };


  const filteredSchedules = schedules.filter((s) => {
    const term = searchTerm.toLowerCase();
    return (
      s.name.toLowerCase().includes(term) ||
      (s.pipeline_name && s.pipeline_name.toLowerCase().includes(term)) ||
      s.cron_expression.toLowerCase().includes(term) ||
      s.timezone.toLowerCase().includes(term)
    );
  });

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <Calendar className="w-8 h-8 text-indigo-400" />
              <span>Pipeline Schedules</span>
            </h1>
            <p className="text-slate-400 text-xs mt-1">
              Automate pipeline execution using timezone-aware cron schedules backed by Celery Beat.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleOpenCreateModal}
              className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-2 shadow-lg shadow-indigo-600/20 transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Create Schedule</span>
            </button>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div className="flex items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-500" />
            <input
              type="text"
              placeholder="Search schedules by name, pipeline, or cron..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <button
            onClick={fetchData}
            title="Refresh Schedules"
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Schedules Table */}
        <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
          {loading ? (
            <div className="py-20 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
              <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
              <span>Loading schedules...</span>
            </div>
          ) : filteredSchedules.length === 0 ? (
            <div className="py-20 text-center text-xs text-slate-400 flex flex-col items-center gap-3">
              <Clock className="w-10 h-10 text-slate-600" />
              <p className="font-semibold text-slate-300">No schedules configured</p>
              <p className="text-slate-500 text-[11px]">Click "Create Schedule" to configure automatic pipeline runs.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-900/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                    <th className="py-3.5 px-6">Schedule Name</th>
                    <th className="py-3.5 px-4">Pipeline</th>
                    <th className="py-3.5 px-4">Cron Expression</th>
                    <th className="py-3.5 px-4">Timezone</th>
                    <th className="py-3.5 px-4">Status</th>
                    <th className="py-3.5 px-4">Next Run</th>
                    <th className="py-3.5 px-4">Last Run</th>
                    <th className="py-3.5 px-6 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {filteredSchedules.map((sched) => (
                    <tr key={sched.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-4 px-6 font-bold text-white font-sans">{sched.name}</td>
                      <td className="py-4 px-4 font-sans text-indigo-300 font-medium">
                        {sched.pipeline_name || `Pipeline #${sched.pipeline_id}`}
                      </td>
                      <td className="py-4 px-4 font-mono text-emerald-400 font-bold bg-slate-950/40 rounded px-2 py-1 border border-slate-900">
                        {sched.cron_expression}
                      </td>
                      <td className="py-4 px-4 text-slate-300 font-sans text-[11px] flex items-center gap-1.5 pt-5">
                        <Globe className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                        <span>{sched.timezone}</span>
                      </td>
                      <td className="py-4 px-4">
                        {sched.enabled ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[11px] font-medium font-sans">
                            <CheckCircle2 className="w-3 h-3" /> ACTIVE
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-400 text-[11px] font-medium font-sans">
                            <X className="w-3 h-3" /> DISABLED
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-4 text-indigo-300 font-semibold">
                        {sched.next_run_at ? new Date(sched.next_run_at).toLocaleString() : '-'}
                      </td>
                      <td className="py-4 px-4 text-slate-400">
                        {sched.last_run_at ? new Date(sched.last_run_at).toLocaleString() : 'Never'}
                      </td>
                      <td className="py-4 px-6 text-right font-sans">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => handleToggle(sched)}
                            title={sched.enabled ? 'Disable Schedule' : 'Enable Schedule'}
                            className={`p-1.5 rounded-lg border transition-colors ${
                              sched.enabled
                                ? 'bg-emerald-950/40 border-emerald-800 text-emerald-400 hover:bg-emerald-900/60'
                                : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-white'
                            }`}
                          >
                            <Power className="w-3.5 h-3.5" />
                          </button>

                          <button
                            onClick={() => handleOpenEditModal(sched)}
                            title="Edit Schedule"
                            className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700 transition-colors"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>

                          <button
                            onClick={() => setDeleteTargetId(sched.id)}
                            title="Delete Schedule"
                            className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 text-rose-400 hover:bg-rose-950/40 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Create / Edit Schedule Modal */}
        {showModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <div className="w-full max-w-lg glass-panel p-6 rounded-2xl border border-slate-800 shadow-2xl relative">
              <button
                onClick={() => setShowModal(false)}
                className="absolute top-4 right-4 p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200"
              >
                <X className="w-5 h-5" />
              </button>

              <h3 className="text-lg font-bold text-white mb-4">
                {editingSchedule ? 'Edit Schedule' : 'Configure New Schedule'}
              </h3>

              {formError && (
                <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                  <span>{formError}</span>
                </div>
              )}

              <form onSubmit={handleSaveSchedule} className="space-y-4 text-xs">

                <div>
                  <label className="block font-medium text-slate-300 mb-1">Schedule Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Daily Sales Warehouse Load"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block font-medium text-slate-300 mb-1">Target Pipeline</label>
                  <select
                    disabled={!!editingSchedule}
                    value={pipelineId}
                    onChange={(e) => setPipelineId(e.target.value ? Number(e.target.value) : '')}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                  >
                    {pipelines.length === 0 ? (
                      <option value="">No pipelines available. Create a pipeline first.</option>
                    ) : (
                      pipelines.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} (Target: {p.destination_config?.table_name || p.destination_config?.warehouse_model_slug || p.destination_config?.destination_type || 'Table'})
                        </option>
                      ))
                    )}
                  </select>

                </div>

                {/* Cron Presets */}
                <div>
                  <label className="block font-medium text-slate-300 mb-1">Quick Cron Presets</label>
                  <div className="flex flex-wrap gap-1.5">
                    {CRON_PRESETS.map((preset) => (
                      <button
                        key={preset.cron}
                        type="button"
                        onClick={() => setCronExpr(preset.cron)}
                        className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono transition-colors ${
                          cronExpr === preset.cron
                            ? 'bg-indigo-600/20 border-indigo-500 text-indigo-300 font-bold'
                            : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Cron Expression Input */}
                <div>
                  <label className="block font-medium text-slate-300 mb-1">Cron Expression (5-field standard)</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 0 9 * * *"
                    value={cronExpr}
                    onChange={(e) => setCronExpr(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>

                {/* Timezone Selector */}
                <div>
                  <label className="block font-medium text-slate-300 mb-1">Timezone</label>
                  <select
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-indigo-500"
                  >
                    {COMMON_TIMEZONES.map((tz) => (
                      <option key={tz} value={tz}>
                        {tz}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Enabled Toggle */}
                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="enabled-chk"
                    checked={enabled}
                    onChange={(e) => setEnabled(e.target.checked)}
                    className="rounded border-slate-800 bg-slate-950 text-indigo-600 focus:ring-0"
                  />
                  <label htmlFor="enabled-chk" className="text-slate-300 cursor-pointer">
                    Enable Schedule immediately after saving
                  </label>
                </div>

                {/* Live Validation & Next Run Preview Box */}
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-slate-400">Validation Status:</span>
                    {validating ? (
                      <span className="text-indigo-400 flex items-center gap-1">
                        <RefreshCw className="w-3 h-3 animate-spin" /> Checking...
                      </span>
                    ) : validation?.valid ? (
                      <span className="text-emerald-400 flex items-center gap-1 font-bold">
                        <Check className="w-3.5 h-3.5" /> Valid Cron Expression
                      </span>
                    ) : (
                      <span className="text-rose-400 flex items-center gap-1 font-bold">
                        <AlertCircle className="w-3.5 h-3.5" /> Invalid Cron Expression
                      </span>
                    )}
                  </div>

                  {validation?.next_run_at && (
                    <div className="text-[11px] font-mono text-slate-300 pt-1">
                      <span className="text-slate-400">Calculated Next Run ({timezone}): </span>
                      <strong className="text-indigo-300">{new Date(validation.next_run_at).toLocaleString()}</strong>
                    </div>
                  )}

                  {validation?.error && (
                    <div className="text-[11px] text-rose-400 pt-1 font-sans">
                      {validation.error}
                    </div>
                  )}
                </div>

                {/* Form Buttons */}
                <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={saving || (validation ? !validation.valid : false)}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium disabled:opacity-50 flex items-center gap-2"
                  >
                    {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : null}
                    <span>{saving ? 'Saving...' : editingSchedule ? 'Save Changes' : 'Create Schedule'}</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Confirm Delete Modal */}
        <ConfirmModal
          isOpen={deleteTargetId !== null}
          title="Delete Schedule"
          message="Are you sure you want to delete this pipeline schedule? Active recurring dispatches will stop immediately."
          confirmText="Delete Schedule"
          cancelText="Cancel"
          type="danger"
          onConfirm={handleConfirmDelete}
          onCancel={() => setDeleteTargetId(null)}
        />


      </div>
    </MainLayout>
  );
};

