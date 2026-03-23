import { create } from 'zustand';
import { api } from '../api/client';

export interface SourceMessage {
  id: string;
  source: string;
  record_type: string;
  summary: string;
  timestamp: string;
  run_session_id: string | null;
  created_at: string;
  // Full detail fields (only on getSourceMessage)
  content?: string;
  processed_content?: string;
  raw_content?: string | null;
  metadata?: Record<string, any>;
}

export interface SourceOverviewEntry {
  message_count: number;
  storage_bytes: number;
  cursor: string | null;
  last_run_at: string | null;
  last_error: string | null;
  stats_1h: { runs: number; fetched: number; processed: number; errors: number };
  stats_24h: { runs: number; fetched: number; processed: number; errors: number };
}

export interface SourceOverview {
  sources: Record<string, SourceOverviewEntry>;
  total_messages: number;
  total_storage_bytes: number;
}

export interface SourceRun {
  id: number;
  source: string;
  ran_at: string;
  records_fetched: number;
  records_processed: number;
  error: string | null;
  session_id: string | null;
}

export interface SourceHealthEntry {
  state: 'healthy' | 'degraded' | 'open';
  consecutive_failures: number;
  last_error: string | null;
  last_error_at: string | null;
  last_success_at: string | null;
  backoff_until: string | null;
}

export interface ConsumerCursor {
  consumer: string;
  source: string;
  cursor_seq: number;
  session_id: string | null;
  updated_at: string;
  expires_at: string | null;
  unread: number;
}

interface SourcesState {
  messages: SourceMessage[];
  selectedMessage: SourceMessage | null;
  overview: SourceOverview | null;
  runs: SourceRun[];
  selectedRun: SourceRun | null;
  selectedRunMessages: SourceMessage[];
  consumers: ConsumerCursor[];
  sourceHealth: Record<string, SourceHealthEntry> | null;
  activeSource: string | null;
  activeTab: 'inbox' | 'runs' | 'consumers';
  hasMore: boolean;
  loading: boolean;
  detailLoading: boolean;

  loadOverview: () => Promise<void>;
  loadMessages: (reset?: boolean) => Promise<void>;
  loadMore: () => Promise<void>;
  selectMessage: (source: string, id: string) => Promise<void>;
  clearSelection: () => void;
  setActiveSource: (source: string | null) => void;
  setActiveTab: (tab: 'inbox' | 'runs' | 'consumers') => void;
  loadRuns: () => Promise<void>;
  selectRun: (run: SourceRun) => Promise<void>;
  loadConsumers: () => Promise<void>;
  fetchSourceHealth: () => Promise<void>;
  syncSource: (source: string) => Promise<void>;
  syncAll: () => Promise<void>;
  purgeMessages: (source?: string) => Promise<void>;
  refresh: () => Promise<void>;
}

export const useSourcesStore = create<SourcesState>((set, get) => ({
  messages: [],
  selectedMessage: null,
  overview: null,
  runs: [],
  selectedRun: null,
  selectedRunMessages: [],
  consumers: [],
  sourceHealth: null,
  activeSource: null,
  activeTab: 'inbox',
  hasMore: false,
  loading: false,
  detailLoading: false,

  loadOverview: async () => {
    try {
      const data = await api.getSourceOverview();
      set({ overview: data });
    } catch (e) {
      console.error('Failed to load source overview:', e);
    }
  },

  loadMessages: async (reset = true) => {
    const { activeSource } = get();
    set({ loading: true });
    try {
      const data = await api.getSourceMessages({
        source: activeSource || undefined,
        limit: 50,
      });
      set({
        messages: data.messages,
        hasMore: data.has_more,
        loading: false,
      });
      if (reset) set({ selectedMessage: null });
    } catch (e) {
      console.error('Failed to load messages:', e);
      set({ loading: false });
    }
  },

  loadMore: async () => {
    const { messages, activeSource, hasMore, loading } = get();
    if (!hasMore || loading || messages.length === 0) return;

    const lastTs = messages[messages.length - 1]?.timestamp;
    if (!lastTs) return;

    set({ loading: true });
    try {
      const data = await api.getSourceMessages({
        source: activeSource || undefined,
        limit: 50,
        before: lastTs,
      });
      set({
        messages: [...messages, ...data.messages],
        hasMore: data.has_more,
        loading: false,
      });
    } catch (e) {
      console.error('Failed to load more messages:', e);
      set({ loading: false });
    }
  },

  selectMessage: async (source: string, id: string) => {
    set({ detailLoading: true });
    try {
      const msg = await api.getSourceMessage(source, id);
      set({ selectedMessage: msg, detailLoading: false });
    } catch (e) {
      console.error('Failed to load message detail:', e);
      set({ detailLoading: false });
    }
  },

  clearSelection: () => set({ selectedMessage: null }),

  setActiveSource: (source: string | null) => {
    set({ activeSource: source, selectedMessage: null });
    get().loadMessages();
    if (get().activeTab === 'runs') get().loadRuns();
  },

  setActiveTab: (tab: 'inbox' | 'runs' | 'consumers') => {
    set({ activeTab: tab, selectedMessage: null, selectedRun: null, selectedRunMessages: [] });
    if (tab === 'runs') get().loadRuns();
    else if (tab === 'consumers') get().loadConsumers();
    else get().loadMessages();
  },

  loadRuns: async () => {
    const { activeSource } = get();
    set({ loading: true });
    try {
      const data = await api.getSourceRuns({
        source: activeSource || undefined,
        limit: 100,
      });
      set({ runs: data.runs, loading: false });
    } catch (e) {
      console.error('Failed to load runs:', e);
      set({ loading: false });
    }
  },

  selectRun: async (run: SourceRun) => {
    set({ selectedRun: run, detailLoading: true, selectedRunMessages: [] });
    if (run.session_id) {
      try {
        const data = await api.getSourceMessages({ session: run.session_id, limit: 100 });
        set({ selectedRunMessages: data.messages, detailLoading: false });
      } catch (e) {
        console.error('Failed to load run messages:', e);
        set({ detailLoading: false });
      }
    } else {
      set({ detailLoading: false });
    }
  },

  loadConsumers: async () => {
    set({ loading: true });
    try {
      const data = await api.getConsumerCursors();
      set({ consumers: data.consumers, loading: false });
    } catch (e) {
      console.error('Failed to load consumer cursors:', e);
      set({ loading: false });
    }
  },

  fetchSourceHealth: async () => {
    try {
      const data = await api.getSourceHealth();
      set({ sourceHealth: data.health });
    } catch (e) {
      console.error('Failed to fetch source health:', e);
    }
  },

  syncSource: async (source: string) => {
    try {
      await api.triggerSourceSync(source);
      // Refresh after sync
      await get().refresh();
    } catch (e) {
      console.error('Failed to sync source:', e);
    }
  },

  syncAll: async () => {
    try {
      await api.triggerAllSourcesSync();
      await get().refresh();
    } catch (e) {
      console.error('Failed to sync all:', e);
    }
  },

  purgeMessages: async (source?: string) => {
    try {
      await api.deleteSourceMessages(source);
      await get().refresh();
    } catch (e) {
      console.error('Failed to purge messages:', e);
    }
  },

  refresh: async () => {
    const { activeTab } = get();
    await get().loadOverview();
    if (activeTab === 'inbox') await get().loadMessages(false);
    else if (activeTab === 'runs') await get().loadRuns();
    else if (activeTab === 'consumers') await get().loadConsumers();
  },
}));
