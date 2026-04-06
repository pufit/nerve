import { create } from 'zustand';

type ThemePreference = 'system' | 'light' | 'dark';

interface ThemeState {
  preference: ThemePreference;
  setTheme: (pref: ThemePreference) => void;
  cycleTheme: () => void;
}

const STORAGE_KEY = 'nerve-theme';
const CYCLE_ORDER: ThemePreference[] = ['dark', 'light', 'system'];

function applyTheme(pref: ThemePreference) {
  const el = document.documentElement;
  if (pref === 'system') {
    el.removeAttribute('data-theme');
  } else {
    el.setAttribute('data-theme', pref);
  }
}

function getInitialPreference(): ThemePreference {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark' || stored === 'system') return stored;
  return 'dark';
}

export const useThemeStore = create<ThemeState>((set, get) => {
  // Apply initial theme
  const initial = getInitialPreference();
  applyTheme(initial);

  return {
    preference: initial,

    setTheme: (pref) => {
      localStorage.setItem(STORAGE_KEY, pref);
      applyTheme(pref);
      set({ preference: pref });
    },

    cycleTheme: () => {
      const current = get().preference;
      const idx = CYCLE_ORDER.indexOf(current);
      const next = CYCLE_ORDER[(idx + 1) % CYCLE_ORDER.length];
      get().setTheme(next);
    },
  };
});
