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
