import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Layers, ArrowRight, ShieldCheck, AlertCircle, CheckCircle2 } from 'lucide-react';
import { authService } from '../services/api';

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    organization_name: '',
  });

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    setErrorMsg(null);
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);

    // Simple client side checks
    if (formData.password.length < 8) {
      setErrorMsg('Password must be at least 8 characters long');
      setLoading(false);
      return;
    }
    if (!/[A-Za-z]/.test(formData.password) || !/\d/.test(formData.password)) {
      setErrorMsg('Password must contain at least one letter and one number');
      setLoading(false);
      return;
    }

    try {
      await authService.register(formData);
      setSuccessMsg('Account and Organization registered successfully! Redirecting...');
      setTimeout(() => {
        navigate('/login');
      }, 2000);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setErrorMsg(
        typeof detail === 'string' 
          ? detail 
          : Array.isArray(detail) 
          ? detail[0]?.msg 
          : 'Registration failed. Try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 relative overflow-hidden">
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/3 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md glass-panel p-8 rounded-2xl shadow-2xl border border-slate-800 relative z-10">
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-xl shadow-indigo-500/30 mb-3">
            <Layers className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">
            Create DataFusionX Workspace
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Register your organization and administrative account
          </p>
        </div>

        {errorMsg && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 flex items-start gap-2.5 text-rose-300 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-start gap-2.5 text-emerald-300 text-xs">
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{successMsg}</span>
          </div>
        )}

        <form onSubmit={handleRegister} className="space-y-4">
          <div>
            <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase tracking-wider">
              Organization Name
            </label>
            <input
              type="text"
              name="organization_name"
              required
              placeholder="e.g. Acme Corporation"
              value={formData.organization_name}
              onChange={handleChange}
              className="w-full px-4 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-slate-200 text-sm focus:border-indigo-500/50 focus:outline-none transition-colors"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase tracking-wider">
              Admin Name
            </label>
            <input
              type="text"
              name="name"
              required
              placeholder="e.g. John Doe"
              value={formData.name}
              onChange={handleChange}
              className="w-full px-4 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-slate-200 text-sm focus:border-indigo-500/50 focus:outline-none transition-colors"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase tracking-wider">
              Email Address
            </label>
            <input
              type="email"
              name="email"
              required
              placeholder="admin@example.com"
              value={formData.email}
              onChange={handleChange}
              className="w-full px-4 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-slate-200 text-sm focus:border-indigo-500/50 focus:outline-none transition-colors"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-400 mb-1 uppercase tracking-wider">
              Password
            </label>
            <input
              type="password"
              name="password"
              required
              placeholder="Min 8 characters (letters & numbers)"
              value={formData.password}
              onChange={handleChange}
              className="w-full px-4 py-2 rounded-xl bg-slate-900/80 border border-slate-800 text-slate-200 text-sm focus:border-indigo-500/50 focus:outline-none transition-colors"
            />
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 disabled:opacity-50 text-white font-semibold text-sm shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 transition-all duration-200"
            >
              <span>{loading ? 'Registering...' : 'Register Workspace'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </form>

        <div className="mt-5 text-center text-xs text-slate-400">
          Already have a workspace?{' '}
          <Link to="/login" className="text-indigo-400 hover:text-indigo-300 font-medium">
            Sign In
          </Link>
        </div>

        <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center justify-center gap-2 text-[10px] text-slate-500">
          <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
          <span>Milestone 2 — Tenant Access Controls</span>
        </div>
      </div>
    </div>
  );
};
