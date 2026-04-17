import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import {
  BrainCircuit,
  Check,
  ChevronDown,
  Eye,
  EyeOff,
  KeyRound,
  Link2,
  Plus,
  Plug,
  RefreshCw,
  Save,
  Search,
  Trash2,
  X,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  Info,
} from 'lucide-react';
import { API_BASE } from '../config/apiBase';

type ProviderEntry = {
  id: string;
  label: string;
  available: boolean;
  default_model: string;
  resolved_model: string;
  supports_json_mode: boolean;
  note: string;
  base_url: string;
  base_url_source: 'db' | 'env' | 'default';
  model_choices: string[];
  extra_models: string[];
  has_api_key: boolean;
  api_key_source: 'db' | 'env' | 'none';
  api_key_mask: string;
  default_model_source: 'db' | 'env' | 'default';
  last_tested_at?: string | null;
  last_test_ok?: boolean | null;
  last_test_note?: string | null;
  api_key_env: string;
  base_url_env: string;
  model_env: string;
  price: { prompt_cny_per_1k: number; completion_cny_per_1k: number };
};

type CatalogResp = {
  default_provider_id: string;
  providers: ProviderEntry[];
};

interface DraftState {
  apiKey: string;
  touchedKey: boolean;
  showKey: boolean;
  baseUrl: string;
  defaultModel: string;
  extraInput: string;
  extras: string[];
  saving: boolean;
  testing: boolean;
  fetching: boolean;
  toast?: { ok: boolean; text: string };
}

const emptyDraft = (p: ProviderEntry): DraftState => ({
  apiKey: '',
  touchedKey: false,
  showKey: false,
  baseUrl: p.base_url_source === 'db' ? p.base_url : '',
  defaultModel: p.default_model_source === 'db' ? p.resolved_model : '',
  extraInput: '',
  extras: Array.isArray(p.extra_models) ? [...p.extra_models] : [],
  saving: false,
  testing: false,
  fetching: false,
});

// Phase 27 / F7 — custom combobox for the "默认模型" field. Replaces the
// native <datalist> which can't filter, group, or scroll well when a
// provider (e.g. Bailian) exposes dozens of extras.
interface ModelComboboxProps {
  value: string;
  placeholder: string;
  hardcoded: string[];
  extras: string[];
  onChange: (v: string) => void;
  onRemoveExtra?: (v: string) => void;
  labels: {
    group_hardcoded: string;
    group_extras: string;
    search_placeholder: string;
    empty: string;
    remove_model?: string;
    clear: string;
  };
}

const ModelCombobox: React.FC<ModelComboboxProps> = ({
  value,
  placeholder,
  hardcoded,
  extras,
  onChange,
  onRemoveExtra,
  labels,
}) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onEsc);
    window.setTimeout(() => searchRef.current?.focus(), 20);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onEsc);
    };
  }, [open]);

  const norm = query.trim().toLowerCase();
  const match = (s: string) => (norm ? s.toLowerCase().includes(norm) : true);
  const hcFiltered = hardcoded.filter(match);
  const exFiltered = extras.filter((m) => !hardcoded.includes(m)).filter(match);
  const total = hcFiltered.length + exFiltered.length;

  const commit = (v: string) => {
    onChange(v);
    setQuery('');
    setOpen(false);
  };

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="w-full inline-flex items-center justify-between gap-2 rounded-lg border border-outline-variant/60 bg-surface-container-low px-2.5 py-1.5 text-[13px] font-mono hover:border-primary/40 focus:outline-none focus:border-primary/60"
      >
        <span className={`truncate ${value ? '' : 'text-on-surface-variant'}`}>
          {value || placeholder}
        </span>
        <span className="flex items-center gap-1 shrink-0">
          {value && (
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation();
                onChange('');
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  e.stopPropagation();
                  onChange('');
                }
              }}
              className="text-on-surface-variant hover:text-on-surface"
              title={labels.clear}
            >
              <X className="w-3.5 h-3.5" />
            </span>
          )}
          <ChevronDown className={`w-4 h-4 text-on-surface-variant transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full mt-1 z-50 rounded-lg border border-outline-variant/60 bg-surface-container-highest shadow-elev-2 overflow-hidden">
          <div className="p-1.5 border-b border-outline-variant/30 flex items-center gap-1.5">
            <Search className="w-3.5 h-3.5 text-on-surface-variant ml-1" />
            <input
              ref={searchRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={labels.search_placeholder}
              className="flex-1 bg-transparent text-[12px] px-1 py-0.5 focus:outline-none"
              spellCheck={false}
              autoComplete="off"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && query.trim()) {
                  e.preventDefault();
                  commit(query.trim());
                }
              }}
            />
          </div>

          <div className="max-h-[260px] overflow-y-auto py-1">
            {total === 0 && (
              <div className="px-3 py-2 text-[12px] text-on-surface-variant">{labels.empty}</div>
            )}

            {hcFiltered.length > 0 && (
              <>
                <div className="px-3 pt-1 pb-0.5 text-[10px] font-bold tracking-widest uppercase text-on-surface-variant/80">
                  {labels.group_hardcoded}
                </div>
                {hcFiltered.map((m) => (
                  <button
                    key={`hc-${m}`}
                    type="button"
                    onClick={() => commit(m)}
                    className="w-full flex items-center gap-2 px-3 py-1 text-[12px] font-mono text-left hover:bg-surface-container-low"
                  >
                    <span className="w-3 shrink-0">
                      {m === value && <Check className="w-3 h-3 text-primary" />}
                    </span>
                    <span className="truncate">{m}</span>
                  </button>
                ))}
              </>
            )}

            {exFiltered.length > 0 && (
              <>
                <div className="px-3 pt-1.5 pb-0.5 text-[10px] font-bold tracking-widest uppercase text-on-surface-variant/80 border-t border-outline-variant/20 mt-1">
                  {labels.group_extras} ({exFiltered.length})
                </div>
                {exFiltered.map((m) => (
                  <div
                    key={`ex-${m}`}
                    className="group flex items-center gap-2 pl-3 pr-1 py-1 text-[12px] font-mono hover:bg-surface-container-low"
                  >
                    <button
                      type="button"
                      onClick={() => commit(m)}
                      className="flex-1 min-w-0 flex items-center gap-2 text-left"
                    >
                      <span className="w-3 shrink-0">
                        {m === value && <Check className="w-3 h-3 text-primary" />}
                      </span>
                      <span className="truncate">{m}</span>
                    </button>
                    {onRemoveExtra && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRemoveExtra(m);
                        }}
                        className="opacity-0 group-hover:opacity-100 px-1.5 text-on-surface-variant hover:text-red-600 transition-opacity"
                        title={labels.remove_model}
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

interface ProviderSettingsProps {
  onClose?: () => void;
}

export const ProviderSettings: React.FC<ProviderSettingsProps> = ({ onClose }) => {
  const { t } = useTranslation();
  const [catalog, setCatalog] = useState<ProviderEntry[]>([]);
  const [drafts, setDrafts] = useState<Record<string, DraftState>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  // Tab-style selection: exactly one provider card is rendered at a time.
  // `null` means "not yet decided" — the first refresh() picks a default.
  const [activeId, setActiveId] = useState<string | null>(null);
  const [globalDefaultId, setGlobalDefaultId] = useState<string | null>(null);
  const [showSecurity, setShowSecurity] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await axios.get<CatalogResp>(`${API_BASE}/api/providers`);
      const items = Array.isArray(res.data?.providers) ? res.data.providers : [];
      setCatalog(items);
      setGlobalDefaultId(res.data?.default_provider_id || null);
      setDrafts((prev) => {
        const next: Record<string, DraftState> = {};
        for (const p of items) {
          const old = prev[p.id];
          next[p.id] = old
            ? {
                ...old,
                // Keep the user's in-flight input for API key / base URL /
                // default model — only the authoritative "extras" list and
                // any ephemeral flags get refreshed on server data.
                extras: Array.isArray(p.extra_models) ? [...p.extra_models] : [],
                saving: false,
                testing: false,
                fetching: false,
              }
            : emptyDraft(p);
        }
        return next;
      });
      // Pick a sensible default the first time we see the catalog: prefer
      // the first READY provider, fall back to the first one in the list.
      // On later refreshes we keep whatever the user has selected, unless
      // that provider disappeared from the catalog.
      setActiveId((prev) => {
        if (prev && items.some((p) => p.id === prev)) return prev;
        const ready = items.find((p) => p.available);
        return (ready || items[0] || null)?.id ?? null;
      });
      setError('');
    } catch (e: any) {
      setError(String(e?.message || 'load failed'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleSave = async (pid: string) => {
    const d = drafts[pid];
    if (!d) return;
    setDrafts((prev) => ({ ...prev, [pid]: { ...prev[pid], saving: true, toast: undefined } }));
    try {
      const payload: Record<string, unknown> = {
        base_url: d.baseUrl,
        default_model: d.defaultModel,
        extra_models: d.extras,
      };
      if (d.touchedKey) {
        payload.api_key = d.apiKey;
      }
      const res = await axios.put(`${API_BASE}/api/providers/settings/${pid}`, payload);
      const provider: ProviderEntry | undefined = res.data?.provider;
      if (provider) {
        setCatalog((c) => c.map((p) => (p.id === pid ? provider : p)));
      } else {
        await refresh();
      }
      setDrafts((prev) => ({
        ...prev,
        [pid]: {
          ...prev[pid],
          saving: false,
          apiKey: '',
          touchedKey: false,
          toast: { ok: true, text: t('providers.toast_saved') },
        },
      }));

      // Automatically fetch models if the key was just setup/updated
      if (d.touchedKey) {
        // give it a brief tick for the UI to show saved State
        setTimeout(() => handleFetchModels(pid), 500);
      }
    } catch (e: any) {
      setDrafts((prev) => ({
        ...prev,
        [pid]: {
          ...prev[pid],
          saving: false,
          toast: { ok: false, text: String(e?.response?.data?.detail || e?.message || 'save failed') },
        },
      }));
    }
  };

  const handleClearKey = async (pid: string) => {
    if (!window.confirm(t('providers.confirm_clear_key'))) return;
    setDrafts((prev) => ({ ...prev, [pid]: { ...prev[pid], saving: true, toast: undefined } }));
    try {
      const res = await axios.put(`${API_BASE}/api/providers/settings/${pid}`, {
        clear_api_key: true,
      });
      const provider: ProviderEntry | undefined = res.data?.provider;
      if (provider) setCatalog((c) => c.map((p) => (p.id === pid ? provider : p)));
      setDrafts((prev) => ({
        ...prev,
        [pid]: {
          ...prev[pid],
          saving: false,
          apiKey: '',
          touchedKey: false,
          toast: { ok: true, text: t('providers.toast_key_cleared') },
        },
      }));
    } catch (e: any) {
      setDrafts((prev) => ({
        ...prev,
        [pid]: { ...prev[pid], saving: false, toast: { ok: false, text: String(e?.message || 'clear failed') } },
      }));
    }
  };

  const handleReset = async (pid: string) => {
    if (!window.confirm(t('providers.confirm_reset'))) return;
    try {
      await axios.delete(`${API_BASE}/api/providers/settings/${pid}`);
      await refresh();
    } catch (e: any) {
      setError(String(e?.message || 'reset failed'));
    }
  };

  const handleTest = async (pid: string) => {
    setDrafts((prev) => ({ ...prev, [pid]: { ...prev[pid], testing: true, toast: undefined } }));
    try {
      const res = await axios.post(`${API_BASE}/api/providers/${pid}/test`);
      const ok = Boolean(res.data?.ok);
      setDrafts((prev) => ({
        ...prev,
        [pid]: {
          ...prev[pid],
          testing: false,
          toast: {
            ok,
            text: ok
              ? `${t('providers.toast_test_ok')} · ${res.data?.method || ''}`
              : String(res.data?.error || t('providers.toast_test_fail')),
          },
        },
      }));
      await refresh();
    } catch (e: any) {
      setDrafts((prev) => ({
        ...prev,
        [pid]: { ...prev[pid], testing: false, toast: { ok: false, text: String(e?.message || 'test failed') } },
      }));
    }
  };

  const handleFetchModels = async (pid: string) => {
    setDrafts((prev) => ({ ...prev, [pid]: { ...prev[pid], fetching: true, toast: undefined } }));
    try {
      const res = await axios.post(`${API_BASE}/api/providers/${pid}/fetch-models`);
      const fetched: string[] = Array.isArray(res.data?.fetched) ? res.data.fetched : [];
      const dropped: number = Number(res.data?.dropped_count) || 0;
      setDrafts((prev) => ({
        ...prev,
        [pid]: {
          ...prev[pid],
          fetching: false,
          toast: {
            ok: true,
            text:
              dropped > 0
                ? t('providers.toast_models_fetched_filtered', { n: fetched.length, dropped })
                : t('providers.toast_models_fetched', { n: fetched.length }),
          },
        },
      }));
      await refresh();
    } catch (e: any) {
      setDrafts((prev) => ({
        ...prev,
        [pid]: {
          ...prev[pid],
          fetching: false,
          toast: { ok: false, text: String(e?.response?.data?.detail || e?.message || 'fetch failed') },
        },
      }));
    }
  };

  const handleClearModels = async (pid: string) => {
    if (!window.confirm("确定要清空所有在此服务商下拉取的大模型列表吗？")) return;
    try {
      const res = await axios.put(`${API_BASE}/api/providers/settings/${pid}`, {
        extra_models: []
      });
      await refresh();
    } catch (e: any) {
      setError(String(e?.message || 'clear failed'));
    }
  };

  const handleSetGlobalDefault = async (pid: string) => {
    try {
      const res = await axios.put(`${API_BASE}/api/providers/set-default`, {
        provider_id: pid
      });
      if (res.data?.success) {
         setGlobalDefaultId(res.data.default_provider_id);
         await refresh();
      }
    } catch (e: any) {
      setError(String(e?.message || 'set default failed'));
    }
  };

  const updateDraft = (pid: string, patch: Partial<DraftState>) =>

    setDrafts((prev) => ({ ...prev, [pid]: { ...prev[pid], ...patch } }));

  const sourceBadge = useCallback(
    (source: string) => {
      if (source === 'db') return { label: t('providers.src_db'), cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
      if (source === 'env') return { label: t('providers.src_env'), cls: 'bg-sky-50 text-sky-700 border-sky-200' };
      if (source === 'default') return { label: t('providers.src_default'), cls: 'bg-slate-50 text-slate-700 border-slate-200' };
      return { label: t('providers.src_none'), cls: 'bg-slate-50 text-slate-500 border-slate-200' };
    },
    [t],
  );

  const cards = useMemo(() => catalog, [catalog]);

  return (
    <div className="h-full overflow-y-auto bg-background text-on-background">
      <div className="max-w-6xl mx-auto px-6 py-5 pb-8">
        {/* Page title — compact single row with clickable security pill */}
        <div className="flex items-center justify-between gap-3 mb-2">
          <h1 className="text-lg font-bold flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-primary" />
            {t('providers.page_title')}
          </h1>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowSecurity((v) => !v)}
              aria-expanded={showSecurity}
              aria-controls="provider-security-panel"
              className={`hidden md:inline-flex items-center gap-1.5 text-[11px] text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-full px-2.5 py-1 transition-colors ${
                showSecurity ? 'ring-1 ring-amber-300' : ''
              }`}
            >
              <ShieldAlert className="w-3 h-3" />
              {t('providers.security_title')}
            </button>
            
            {onClose && (
              <button 
                type="button" 
                onClick={onClose} 
                className="ml-2 p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-outline-variant/20 rounded-lg transition-colors bg-surface-container"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {showSecurity && (
          <div
            id="provider-security-panel"
            className="mb-3 rounded-lg border border-amber-200 bg-amber-50 text-amber-900 px-3 py-2 flex items-start gap-2 text-[12px] leading-relaxed"
          >
            <ShieldAlert className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            <div>
              <div className="font-semibold">{t('providers.security_title')}</div>
              <div className="text-amber-800/85 mt-0.5">{t('providers.security_body')}</div>
            </div>
          </div>
        )}

        {/* Global Active Indicator */}
        {!loading && globalDefaultId && (
          <div className="mb-4 rounded-xl border-2 border-emerald-500/30 bg-emerald-500/5 px-4 py-3 flex items-center justify-between gap-3 shadow-sm ring-1 ring-emerald-500/20">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div className="flex flex-col">
                <span className="text-[11px] font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider">
                  当前系统生效模型 (Active Engine)
                </span>
                <span className="text-sm font-black text-on-surface">
                  {catalog.find((p) => p.id === globalDefaultId)?.label || globalDefaultId}
                  <span className="ml-2 font-mono text-[11.5px] font-medium text-on-surface-variant">
                    {catalog.find((p) => p.id === globalDefaultId)?.resolved_model}
                  </span>
                </span>
              </div>
            </div>
            <div className="text-[10px] text-emerald-600/70 dark:text-emerald-400/70 border border-emerald-500/20 rounded-md px-2 py-1 bg-emerald-50 dark:bg-emerald-500/10">
              优先级最高且已配置
            </div>
          </div>
        )}

        {loading && <div className="text-sm text-on-surface-variant">{t('providers.loading')}</div>}
        {error && <div className="text-sm text-red-600">{error}</div>}

        {cards.length > 0 && (
          <div
            className="mb-3 flex flex-wrap gap-1.5"
            role="tablist"
            aria-label={t('providers.quick_jump')}
          >
            {cards.map((p) => {
              const isActive = p.id === activeId;
              return (
                <button
                  key={p.id}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setActiveId(p.id)}
                  className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full border transition-colors ${
                    isActive
                      ? 'bg-primary text-on-primary border-primary shadow-sm'
                      : p.available
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                      : 'bg-surface-container text-on-surface-variant border-outline-variant/60 hover:bg-surface-container-high'
                  }`}
                  title={p.available ? t('providers.last_test_ok') : t('providers.status_no_key')}
                >
                  <span
                    className={`inline-block w-1.5 h-1.5 rounded-full ${
                      isActive
                        ? 'bg-on-primary'
                        : p.available
                        ? 'bg-emerald-500'
                        : 'bg-slate-400'
                    }`}
                  />
                  {p.label}
                </button>
              );
            })}
          </div>
        )}

        <div>
          {(() => {
            const p = cards.find((c) => c.id === activeId);
            if (!p) return null;
            const d = drafts[p.id] || emptyDraft(p);
            const keyBadge = sourceBadge(p.api_key_source);
            const urlBadge = sourceBadge(p.base_url_source);
            const modelBadge = sourceBadge(p.default_model_source);
            const testedAt = p.last_tested_at ? new Date(p.last_tested_at) : null;
            const hardcodedList = p.model_choices.filter((m) => !d.extras.includes(m));
            return (
              <div
                key={p.id}
                id={`provider-card-${p.id}`}
                className="rounded-xl border border-outline-variant/40 bg-surface-container-lowest shadow-sm p-4"
              >
                {/* Card header — single row */}
                <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
                  <div className="flex items-center gap-2 flex-wrap min-w-0">
                    <h2 className="text-base font-semibold">{p.label}</h2>
                    <span
                      className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full border ${
                        p.available ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'
                      }`}
                    >
                      {p.available ? 'READY' : 'NO KEY'}
                    </span>
                    {p.note && (
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full border bg-slate-50 text-slate-700 border-slate-200">
                        {p.note.toUpperCase()}
                      </span>
                    )}
                    {p.last_test_ok === true && (
                      <span
                        className="inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full border bg-emerald-50 text-emerald-700 border-emerald-200"
                        title={testedAt ? t('providers.tested_at', { at: testedAt.toLocaleString() }) : ''}
                      >
                        <CheckCircle2 className="w-3 h-3" /> {t('providers.last_test_ok')}
                      </span>
                    )}
                    {p.last_test_ok === false && (
                      <span
                        className="inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full border bg-red-50 text-red-700 border-red-200"
                        title={p.last_test_note || ''}
                      >
                        <AlertTriangle className="w-3 h-3" /> {t('providers.last_test_fail')}
                      </span>
                    )}
                  </div>

                </div>

                {/* Row 1: API Key | Base URL | Default Model */}
                <div className="grid md:grid-cols-3 gap-3 mb-3">
                  {/* API key */}
                  <div className="space-y-1">
                    <label className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                      <KeyRound className="w-3 h-3" /> {t('providers.field_api_key')}
                      <span className={`ml-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full border ${keyBadge.cls}`}>{keyBadge.label}</span>
                    </label>
                    <div className="flex items-stretch gap-1.5">
                      <div className="flex-1 min-w-0 flex items-center rounded-lg border border-outline-variant/60 bg-surface-container-low overflow-hidden">
                        <input
                          type={d.showKey ? 'text' : 'password'}
                          value={d.apiKey}
                          placeholder={
                            p.has_api_key && p.api_key_source === 'db'
                              ? p.api_key_mask || t('providers.placeholder_stored')
                              : p.api_key_source === 'env'
                              ? t('providers.placeholder_env', { env: p.api_key_env })
                              : t('providers.placeholder_new_key', { env: p.api_key_env })
                          }
                          title={
                            p.api_key_source === 'env'
                              ? t('providers.hint_env_priority', { env: p.api_key_env })
                              : t('providers.hint_paste_key')
                          }
                          onChange={(e) => updateDraft(p.id, { apiKey: e.target.value, touchedKey: true })}
                          className="flex-1 min-w-0 bg-transparent px-2.5 py-1.5 text-[13px] focus:outline-none font-mono"
                          spellCheck={false}
                          autoComplete="off"
                        />
                        <button
                          type="button"
                          onClick={() => updateDraft(p.id, { showKey: !d.showKey })}
                          className="px-2 text-on-surface-variant hover:text-on-surface"
                          title={d.showKey ? t('providers.hide_key') : t('providers.show_key')}
                        >
                          {d.showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                      {p.api_key_source === 'db' && p.has_api_key && (
                        <button
                          type="button"
                          onClick={() => void handleClearKey(p.id)}
                          className="px-2 rounded-lg border border-outline-variant/60 hover:bg-surface-container"
                          title={t('providers.clear_key')}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Base URL */}
                  <div className="space-y-1">
                    <label className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                      <Link2 className="w-3 h-3" /> {t('providers.field_base_url')}
                      <span className={`ml-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full border ${urlBadge.cls}`}>{urlBadge.label}</span>
                    </label>
                    <input
                      type="text"
                      value={d.baseUrl}
                      placeholder={p.base_url}
                      title={t('providers.hint_base_url')}
                      onChange={(e) => updateDraft(p.id, { baseUrl: e.target.value })}
                      className="w-full rounded-lg border border-outline-variant/60 bg-surface-container-low px-2.5 py-1.5 text-[13px] font-mono focus:outline-none focus:border-primary/60"
                      spellCheck={false}
                      autoComplete="off"
                    />
                  </div>

                  {/* Default model */}
                  <div className="space-y-1">
                    <label className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                      <Info className="w-3 h-3" /> {t('providers.field_default_model')}
                      <span className={`ml-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full border ${modelBadge.cls}`}>{modelBadge.label}</span>
                    </label>
                    <ModelCombobox
                      value={d.defaultModel}
                      placeholder={p.default_model}
                      hardcoded={p.model_choices.filter((m) => !d.extras.includes(m))}
                      extras={d.extras}
                      onChange={(v) => updateDraft(p.id, { defaultModel: v })}
                      onRemoveExtra={(m) =>
                        updateDraft(p.id, { extras: d.extras.filter((x) => x !== m) })
                      }
                      labels={{
                        group_hardcoded: t('providers.group_hardcoded'),
                        group_extras: t('providers.group_extras'),
                        search_placeholder: t('providers.combobox_search'),
                        empty: t('providers.combobox_empty'),
                        remove_model: t('providers.remove_model'),
                        clear: t('providers.combobox_clear'),
                      }}
                    />
                  </div>
                </div>

                {/* Row 2: Extra models */}
                <div className="space-y-2 mb-4">
                  <div className="flex items-center justify-between gap-2 border-b border-outline-variant/30 pb-2">
                    <label className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-on-surface-variant">
                      <span>模型库 (Model Library)</span>
                      <span className="bg-surface-container text-[9px] px-1.5 py-0.5 rounded-full border border-outline-variant/40">
                         {d.extras.length}
                      </span>
                    </label>
                    <div className="flex items-center gap-2">
                      {d.extras.length > 0 && (
                        <button
                          type="button"
                          onClick={() => void handleClearModels(p.id)}
                          className="text-[11px] text-red-600/70 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10 px-2 py-0.5 rounded transition-colors"
                        >
                           清空库
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => void handleFetchModels(p.id)}
                        disabled={!p.has_api_key || d.fetching}
                        className="inline-flex items-center gap-1.5 text-[11px] font-bold px-2 py-1 rounded border border-outline-variant/60 bg-surface-container hover:bg-surface-container-high transition-colors disabled:opacity-40"
                      >
                        <RefreshCw className={`w-3 h-3 ${d.fetching ? 'animate-spin' : ''}`} />
                        {d.fetching ? t('providers.fetching_models') : t('providers.fetch_models')}
                      </button>
                    </div>
                  </div>
                  
                  <div className="flex flex-col md:flex-row gap-3 items-start w-full">
                    <div className="flex items-stretch gap-1.5 w-full md:w-1/3 shrink-0">
                      <input
                        type="text"
                        value={d.extraInput}
                        placeholder={t('providers.placeholder_new_model')}
                        onChange={(e) => updateDraft(p.id, { extraInput: e.target.value })}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            const v = (d.extraInput || '').trim();
                            if (!v) return;
                            if (d.extras.includes(v)) return;
                            updateDraft(p.id, { extras: [...d.extras, v], extraInput: '' });
                          }
                        }}
                        className="flex-1 rounded-lg border border-outline-variant/60 bg-surface-container-low px-2.5 py-1.5 text-[13px] font-mono focus:outline-none focus:border-primary/60"
                        spellCheck={false}
                        autoComplete="off"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          const v = (d.extraInput || '').trim();
                          if (!v || d.extras.includes(v)) return;
                          updateDraft(p.id, { extras: [...d.extras, v], extraInput: '' });
                        }}
                        className="px-2.5 rounded-lg border border-outline-variant/60 hover:bg-surface-container"
                      >
                        <Plus className="w-4 h-4" />
                      </button>
                    </div>
                    
                    <div className="flex-1 w-full h-[180px] overflow-y-auto custom-scrollbar border border-outline-variant/30 rounded-lg bg-surface-container-lowest divide-y divide-outline-variant/20 shadow-inner">
                        {d.extras.length === 0 ? (
                           <div className="p-4 text-center text-[12px] text-on-surface-variant/60">
                             暂无模型。你可以在左侧手动输入，或者点击上方“拉取模型”。
                           </div>
                        ) : (
                           d.extras.map((m) => (
                              <div key={m} className="group flex items-center justify-between px-3 py-1.5 hover:bg-surface-container-low transition-colors">
                                 <div className="flex items-center gap-2 min-w-0">
                                   <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/60"></div>
                                   <span className="text-[12px] font-mono truncate text-on-surface/90" title={m}>{m}</span>
                                 </div>
                                 <button
                                  type="button"
                                  onClick={() =>
                                    updateDraft(p.id, {
                                      extras: d.extras.filter((x) => x !== m),
                                    })
                                  }
                                  className="opacity-0 group-hover:opacity-100 p-1 text-on-surface-variant/60 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded transition-all shrink-0"
                                  title={t('providers.remove_model')}
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                           ))
                        )}
                    </div>
                  </div>
                </div>

                {/* Row 3: actions — compact, inline with toast */}
                <div className="pt-3 border-t border-outline-variant/25 flex flex-wrap items-center gap-2 justify-between">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => void handleSave(p.id)}
                      disabled={d.saving}
                      className="inline-flex items-center gap-1.5 text-[12px] font-bold tracking-wide px-4 py-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 shadow-sm disabled:opacity-50 transition-colors"
                    >
                      <Save className="w-3.5 h-3.5" />
                      {d.saving ? t('providers.saving') : t('providers.save')}
                    </button>
                    {p.id !== globalDefaultId && (
                       <button
                         type="button"
                         onClick={() => void handleSetGlobalDefault(p.id)}
                         disabled={!p.has_api_key}
                         className="inline-flex items-center gap-1.5 text-[12px] font-bold px-4 py-1.5 rounded-lg border-2 border-emerald-500 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 disabled:opacity-30 disabled:border-outline-variant disabled:text-on-surface-variant transition-colors"
                         title={!p.has_api_key ? "需要先配置 API Key" : "强制系统优先使用此服务商"}
                       >
                         <CheckCircle2 className="w-3.5 h-3.5" />
                         设为系统默认引擎
                       </button>
                    )}
                    
                    <div className="w-px h-5 bg-outline-variant/40 mx-1"></div>

                    <button
                      type="button"
                      onClick={() => void handleTest(p.id)}
                      disabled={d.testing || !p.has_api_key}
                      className="inline-flex items-center gap-1.5 text-[12px] font-semibold px-3 py-1.5 rounded-lg border border-outline-variant/60 hover:bg-surface-container disabled:opacity-50"
                      title={p.has_api_key ? '' : t('providers.test_needs_key')}
                    >
                      <Plug className="w-3.5 h-3.5" />
                      {d.testing ? t('providers.testing') : t('providers.test_connection')}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleReset(p.id)}
                      className="inline-flex items-center gap-1.5 text-[12px] font-semibold px-3 py-1.5 rounded-lg border border-outline-variant/60 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      清空设置
                    </button>
                  </div>
                  {d.toast && (
                    <div
                      className={`text-[11px] px-2 py-1 rounded-md border ${
                        d.toast.ok
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-red-50 text-red-700 border-red-200'
                      }`}
                    >
                      {d.toast.text}
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
};

export default ProviderSettings;
