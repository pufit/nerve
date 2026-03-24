import { create } from 'zustand';
import { api } from '../api/client';

export interface HoaPipeline {
  id: string;
  name: string;
  description: string;
}

export interface HoaStatus {
  enabled: boolean;
  available: boolean;
  version: string | null;
  default_mode: string;
  default_agents: string[];
}

interface HoaState {
  status: HoaStatus | null;
  pipelines: HoaPipeline[];
  selectedPipeline: { id: string; name: string; content: string; description: string } | null;
  loading: boolean;
  installing: boolean;

  loadStatus: () => Promise<void>;
  loadPipelines: () => Promise<void>;
  loadPipeline: (id: string) => Promise<void>;
  savePipeline: (id: string, content: string) => Promise<void>;
  deletePipeline: (id: string) => Promise<void>;
  installBinary: () => Promise<void>;
  clearSelectedPipeline: () => void;
}

export const useHoaStore = create<HoaState>((set, get) => ({
  status: null,
  pipelines: [],
  selectedPipeline: null,
  loading: true,
  installing: false,

  loadStatus: async () => {
    try {
      const status = await api.getHoaStatus();
      set({ status });
    } catch (e) {
      console.error('Failed to load HoA status:', e);
    }
  },

  loadPipelines: async () => {
    set({ loading: true });
    try {
      const { pipelines } = await api.listHoaPipelines();
      set({ pipelines, loading: false });
    } catch (e) {
      console.error('Failed to load pipelines:', e);
      set({ loading: false });
    }
  },

  loadPipeline: async (id: string) => {
    try {
      const pipeline = await api.getHoaPipeline(id);
      set({ selectedPipeline: pipeline });
    } catch (e) {
      console.error('Failed to load pipeline:', e);
    }
  },

  savePipeline: async (id: string, content: string) => {
    try {
      await api.saveHoaPipeline(id, content);
      get().loadPipelines();
    } catch (e) {
      console.error('Failed to save pipeline:', e);
    }
  },

  deletePipeline: async (id: string) => {
    try {
      await api.deleteHoaPipeline(id);
      if (get().selectedPipeline?.id === id) {
        set({ selectedPipeline: null });
      }
      get().loadPipelines();
    } catch (e) {
      console.error('Failed to delete pipeline:', e);
    }
  },

  installBinary: async () => {
    set({ installing: true });
    try {
      await api.installHoaBinary();
      await get().loadStatus();
    } catch (e) {
      console.error('Failed to install HoA binary:', e);
    } finally {
      set({ installing: false });
    }
  },

  clearSelectedPipeline: () => set({ selectedPipeline: null }),
}));
