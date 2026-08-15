import { useState, useEffect, useCallback } from 'react';
import { healthService } from '../services/api';
import { SystemHealthState } from '../types';

export const useHealth = () => {
  const [healthState, setHealthState] = useState<SystemHealthState>({
    api: { status: 'loading' },
    database: { status: 'loading' },
    frontend: { status: 'healthy', message: 'Operational' },
    lastChecked: null,
  });

  const checkHealth = useCallback(async () => {
    setHealthState((prev) => ({
      ...prev,
      api: { status: 'loading' },
      database: { status: 'loading' },
    }));

    // 1. Check API Health
    let apiHealthy = false;
    let apiMsg = 'Connected';
    try {
      const apiRes = await healthService.getApiHealth();
      if (apiRes.status === 'healthy') {
        apiHealthy = true;
      } else {
        apiMsg = `Unusual status: ${apiRes.status}`;
      }
    } catch (err: any) {
      apiHealthy = false;
      apiMsg = err.message || 'Backend service unreachable';
    }

    // 2. Check DB Health
    let dbHealthy = false;
    let dbMsg = 'Connected';
    try {
      const dbRes = await healthService.getDatabaseHealth();
      if (dbRes.status === 'healthy' && dbRes.database === 'connected') {
        dbHealthy = true;
      } else {
        dbMsg = dbRes.database || 'Database issue';
      }
    } catch (err: any) {
      dbHealthy = false;
      dbMsg = err.response?.data?.detail?.database || err.message || 'Database connection error';
    }

    setHealthState({
      api: {
        status: apiHealthy ? 'healthy' : 'unhealthy',
        message: apiMsg,
      },
      database: {
        status: dbHealthy ? 'healthy' : 'unhealthy',
        message: dbMsg,
      },
      frontend: {
        status: 'healthy',
        message: 'Operational',
      },
      lastChecked: new Date(),
    });
  }, []);

  useEffect(() => {
    checkHealth();
    // Auto refresh every 30 seconds
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  return { healthState, checkHealth };
};
