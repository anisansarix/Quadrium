import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import type { ApiResponse } from './client';

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  gpu_available: boolean;
  gpu_name: string | null;
  gpu_memory_mb: number | null;
  sqlite_connected: boolean;
  duckdb_connected: boolean;
}

export interface RawData {
  id: string;
  instrument: string;
  timeframe: string;
  date_start: string;
  date_end: string;
  source: string;
  row_count: number;
}

export interface Dataset {
  id: string;
  version: string;
  features: string[];
  date_start: string;
  date_end: string;
  instrument: string;
  timeframe: string;
  row_count: number;
}

export interface Experiment {
  id: string;
  name: string;
  status: string;
  instrument: string;
  timeframe: string;
  agent_type: string;
  created_at: string;
}

export const useSystemHealth = () => {
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<HealthResponse>>('/system/health');
      return data.data;
    },
    refetchInterval: 5000,
  });
};

export const useRawData = () => {
  return useQuery({
    queryKey: ['data', 'raw'],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<RawData[]>>('/data/raw');
      return data.data || [];
    },
  });
};

export const useDatasets = () => {
  return useQuery({
    queryKey: ['datasets'],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Dataset[]>>('/datasets');
      return data.data || [];
    },
  });
};

export const useExperiments = () => {
  return useQuery({
    queryKey: ['experiments'],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Experiment[]>>('/experiments');
      return data.data || [];
    },
  });
};

export const useTrainingJobs = () => {
  return useQuery({
    queryKey: ['training', 'jobs'],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<unknown[]>>('/training/jobs');
      return data.data || [];
    },
  });
};

export interface FetchDataPayload {
  symbol: string;
  timeframe: string;
  start: string;
  end: string;
  source: string;
}

export const useFetchData = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: FetchDataPayload) => {
      const { data } = await apiClient.post<ApiResponse<unknown>>('/data/fetch', payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['data', 'raw'] });
    },
  });
};

export interface StartTrainingPayload {
  dataset_id: string;
  experiment_id: string;
  agent_type?: string;
  total_timesteps?: number;
}

export const useStartTraining = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: StartTrainingPayload) => {
      const { data } = await apiClient.post<ApiResponse<{job_id: string}>>('/training/start', payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['training', 'jobs'] });
    },
  });
};

export interface Mt5Account {
  login: number;
  server: string;
  balance: number;
  equity: number;
  margin: number;
  margin_free: number;
  currency: string;
  name: string;
  leverage: number;
}

export const useMt5Account = () => {
  return useQuery({
    queryKey: ['mt5', 'account'],
    queryFn: async () => {
      const { data } = await apiClient.get<Mt5Account>('/live/mt5/account');
      return data;
    },
    refetchInterval: 5000,
    retry: false, // Don't keep retrying if MT5 isn't connected
  });
};

export interface LiveSession {
  id: string;
  experiment_id: string;
  symbol: string;
  timeframe: string;
  status: string;
  current_equity: number;
  current_balance: number;
  created_at: string;
  config: any;
}

export const useLiveSessions = () => {
  return useQuery({
    queryKey: ['live', 'sessions'],
    queryFn: async () => {
      const { data } = await apiClient.get<LiveSession[]>('/live/');
      return data || [];
    },
    refetchInterval: 5000,
  });
};

export interface StartLiveSessionPayload {
  experiment_id: string;
  symbol: string;
  timeframe: string;
  config: any;
}

export const useStartLiveSession = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: StartLiveSessionPayload) => {
      const { data } = await apiClient.post<{status: string, session_id: string}>('/live/start', payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['live', 'sessions'] });
    },
  });
};

export const useStopLiveSession = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (sessionId: string) => {
      const { data } = await apiClient.post<{status: string}>(`/live/${sessionId}/stop`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['live', 'sessions'] });
    },
  });
};

export interface Mt5Position {
  ticket: number;
  symbol: string;
  type: string;
  volume: number;
  price_open: number;
  price_current: number;
  sl: number;
  tp: number;
  profit: number;
  time: number;
}

export const useMt5Positions = (sessionId: string = "default") => {
  return useQuery({
    queryKey: ['live', 'positions', sessionId],
    queryFn: async () => {
      const { data } = await apiClient.get<{positions: Mt5Position[]}>(`/live/${sessionId}/positions`);
      return data.positions || [];
    },
    refetchInterval: 5000,
    retry: false,
  });
};

export const useSystemLogs = () => {
  return useQuery({
    queryKey: ['system', 'logs'],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<string[]>>('/system/logs');
      return data.data || [];
    },
    refetchInterval: 2000,
  });
};

