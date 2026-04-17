import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { AlertTriangle, ShieldCheck, Search, ListTree, BarChart3, ChevronRight, Eye, EyeOff } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { API_BASE } from '../config/apiBase';

type RiskTerm = {
  term: string;
  severity?: string;
  note?: string;
};

type RulesResp = {
  rules: {
    global: RiskTerm[];
    platform_overrides: Record<string, RiskTerm[]>;
    region_overrides: Record<string, RiskTerm[]>;
  };
  summary: {
    total_global: number;
    total_platform_overrides: number;
    total_region_overrides: number;
    by_severity: Record<string, number>;
  };
};

type StatsResp = {
  total_records: number;
  risky_records: number;
  severity_counts: Record<string, number>;
  top_terms: Array<{ term: string; count: number }>;
  recent_hits: Array<{ project_id?: string; script_id?: string; term?: string; severity?: string; timestamp?: string }>;
  avoid_terms_preview: string[];
  rules_path: string;
};

export const ComplianceAdmin: React.FC = () => {
  const { t } = useTranslation();
  const [rules, setRules] = useState<RulesResp | null>(null);
  const [stats, setStats] = useState<StatsResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [search, setSearch] = useState('');
  const [severity, setSeverity] = useState<string>('');
  const [showOverrides, setShowOverrides] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.allSettled([
      axios.get<RulesResp>(`${API_BASE}/api/compliance/rules`),
      axios.get<StatsResp>(`${API_BASE}/api/compliance/stats`),
    ])
      .then(([r, s]) => {
        if (cancelled) return;
        if (r.status === 'fulfilled') setRules(r.value.data);
        else setError(String(r.reason?.message || 'rules load failed'));
        if (s.status === 'fulfilled') setStats(s.value.data);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredGlobal = useMemo(() => {
    const list = rules?.rules?.global || [];
    const q = search.trim().toLowerCase();
    return list.filter((r) => {
      if (severity && String(r.severity || 'warn').toLowerCase() !== severity) return false;
      if (q && !String(r.term || '').toLowerCase().includes(q) && !String(r.note || '').toLowerCase().includes(q)) return false;
      return true;
    });
  }, [rules, search, severity]);

  const severityBadge = (sev?: string) => {
    const s = String(sev || 'warn').toLowerCase();
    if (s === 'block') return 'bg-red-50 text-red-700 border-red-200';
    return 'bg-amber-50 text-amber-700 border-amber-200';
  };

  return (
    <div className="w-full h-full flex flex-col bg-background text-on-background page-pad overflow-hidden">
      <div className="max-w-[1600px] w-full mx-auto h-full flex flex-col min-h-0 card-base p-4 md:p-6 lg:p-8">
        <motion.header
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="flex flex-col gap-3 shrink-0 border-b border-outline-variant/30 pb-6 relative"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-primary font-bold text-[11px] uppercase tracking-[0.25em] mb-1.5 opacity-90">
                <ShieldCheck className="w-3.5 h-3.5" /> {t('compliance.control_center')}
              </div>
              <h1 className="text-3xl lg:text-[2rem] font-black tracking-tight">{t('compliance.title')}</h1>
              <p className="text-on-surface-variant/80 text-xs mt-1 max-w-xl">{t('compliance.subtitle')}</p>
            </div>
            {stats && (
              <div className="hidden md:grid grid-cols-3 gap-2 text-[11px]">
                <div className="rounded-xl border border-outline-variant/30 bg-surface-container px-3 py-2">
                  <div className="text-on-surface-variant uppercase tracking-widest font-bold text-[9px]">
                    {t('compliance.stat_records')}
                  </div>
                  <div className="font-mono tabular-nums font-black text-on-surface text-[16px]">{stats.total_records}</div>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50/60 px-3 py-2">
                  <div className="text-amber-700 uppercase tracking-widest font-bold text-[9px]">
                    {t('compliance.stat_risky')}
                  </div>
                  <div className="font-mono tabular-nums font-black text-amber-800 text-[16px]">{stats.risky_records}</div>
                </div>
                <div className="rounded-xl border border-red-200 bg-red-50/60 px-3 py-2">
                  <div className="text-red-700 uppercase tracking-widest font-bold text-[9px]">
                    {t('compliance.stat_block')}
                  </div>
                  <div className="font-mono tabular-nums font-black text-red-800 text-[16px]">
                    {stats.severity_counts?.block ?? 0}
                  </div>
                </div>
              </div>
            )}
          </div>
        </motion.header>

        <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-5 mt-5 overflow-hidden">
          <section className="flex-1 min-w-0 flex flex-col bg-surface-container border border-outline-variant/30 rounded-xl overflow-hidden">
            <div className="shrink-0 px-4 py-3 border-b border-outline-variant/20 flex items-center justify-between gap-3 flex-wrap">
              <div className="text-[10px] font-black tracking-widest text-primary uppercase flex items-center gap-2">
                <ListTree className="w-3.5 h-3.5" /> {t('compliance.rules_title')}
                {rules && (
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full border border-outline-variant/40 text-on-surface-variant">
                    {filteredGlobal.length}/{rules.rules.global.length}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 rounded-full border border-outline-variant/40 bg-surface-container-high px-2 py-1 text-[11px]">
                  <Search className="w-3.5 h-3.5 text-on-surface-variant" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder={t('compliance.search_placeholder') as string}
                    className="bg-transparent outline-none w-36 md:w-56 text-on-surface placeholder:text-on-surface-variant"
                  />
                </div>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  className="rounded-full border border-outline-variant/40 bg-surface-container-high px-2 py-1 text-[11px]"
                >
                  <option value="">{t('compliance.all_severities')}</option>
                  <option value="warn">WARN</option>
                  <option value="block">BLOCK</option>
                </select>
                <button
                  type="button"
                  onClick={() => setShowOverrides((v) => !v)}
                  className="text-[10px] font-bold text-on-surface-variant hover:text-on-surface flex items-center gap-1"
                  title={t('compliance.toggle_overrides') as string}
                >
                  {showOverrides ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}{' '}
                  {t('compliance.overrides_short')}
                </button>
              </div>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 space-y-4">
              {loading ? (
                <div className="text-[12px] text-on-surface-variant">{t('compliance.loading')}</div>
              ) : error ? (
                <div className="text-[12px] text-red-700 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" /> {error}
                </div>
              ) : !rules ? (
                <div className="text-[12px] text-on-surface-variant">{t('compliance.no_rules')}</div>
              ) : (
                <>
                  <div className="rounded-xl border border-outline-variant/30 bg-surface-container-high/30 overflow-hidden">
                    <div className="px-3 py-2 border-b border-outline-variant/20 flex items-center justify-between">
                      <div className="text-[10px] font-black tracking-widest uppercase text-on-surface-variant">
                        {t('compliance.global_rules')}
                      </div>
                      <div className="text-[10px] font-mono text-on-surface-variant truncate max-w-[55%]" title={stats?.rules_path}>
                        {stats?.rules_path}
                      </div>
                    </div>
                    {filteredGlobal.length === 0 ? (
                      <div className="px-3 py-6 text-center text-[12px] text-on-surface-variant">
                        {t('compliance.rules_empty')}
                      </div>
                    ) : (
                      <table className="min-w-full text-[12px]">
                        <thead className="bg-surface-container-high/60">
                          <tr>
                            <th className="text-left px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
                              {t('compliance.col_term')}
                            </th>
                            <th className="text-left px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-on-surface-variant w-24">
                              {t('compliance.col_severity')}
                            </th>
                            <th className="text-left px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
                              {t('compliance.col_note')}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredGlobal.map((r, i) => (
                            <tr key={`${r.term}-${i}`} className="border-t border-outline-variant/20 hover:bg-surface-container-high/30">
                              <td className="align-top px-3 py-1.5 font-mono">{r.term}</td>
                              <td className="align-top px-3 py-1.5">
                                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full border ${severityBadge(r.severity)}`}>
                                  {String(r.severity || 'warn').toUpperCase()}
                                </span>
                              </td>
                              <td className="align-top px-3 py-1.5 text-on-surface-variant">{r.note || ''}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>

                  {showOverrides && (
                    <>
                      {Object.entries(rules.rules.platform_overrides || {}).length > 0 && (
                        <div className="rounded-xl border border-outline-variant/30 bg-surface-container-high/30 p-3">
                          <div className="text-[10px] font-black tracking-widest uppercase text-on-surface-variant mb-2">
                            {t('compliance.platform_overrides')}
                          </div>
                          <div className="space-y-2">
                            {Object.entries(rules.rules.platform_overrides).map(([plat, list]) => (
                              <div key={plat} className="text-[11px]">
                                <div className="font-bold text-on-surface flex items-center gap-1">
                                  <ChevronRight className="w-3 h-3" /> {plat} ({list.length})
                                </div>
                                <div className="ml-4 text-on-surface-variant">
                                  {list.map((t) => `"${t.term}"`).join(', ')}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {Object.entries(rules.rules.region_overrides || {}).length > 0 && (
                        <div className="rounded-xl border border-outline-variant/30 bg-surface-container-high/30 p-3">
                          <div className="text-[10px] font-black tracking-widest uppercase text-on-surface-variant mb-2">
                            {t('compliance.region_overrides')}
                          </div>
                          <div className="space-y-2">
                            {Object.entries(rules.rules.region_overrides).map(([reg, list]) => (
                              <div key={reg} className="text-[11px]">
                                <div className="font-bold text-on-surface flex items-center gap-1">
                                  <ChevronRight className="w-3 h-3" /> {reg} ({list.length})
                                </div>
                                <div className="ml-4 text-on-surface-variant">
                                  {list.map((t) => `"${t.term}"`).join(', ')}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  <div className="text-[10px] text-on-surface-variant italic">{t('compliance.readonly_notice')}</div>
                </>
              )}
            </div>
          </section>

          <section className="w-full lg:w-[420px] shrink-0 flex flex-col gap-4">
            <div className="bg-surface-container border border-outline-variant/30 rounded-xl p-4 flex flex-col">
              <div className="text-[10px] font-black tracking-widest text-secondary uppercase flex items-center gap-2 mb-3">
                <BarChart3 className="w-3.5 h-3.5" /> {t('compliance.leaderboard_title')}
              </div>
              {loading ? (
                <div className="text-[12px] text-on-surface-variant">{t('compliance.loading')}</div>
              ) : stats && stats.top_terms.length > 0 ? (
                <div className="space-y-1.5 max-h-[320px] overflow-y-auto custom-scrollbar pr-1">
                  {stats.top_terms.slice(0, 25).map((item) => {
                    const pct = stats.top_terms[0].count > 0 ? Math.round((item.count / stats.top_terms[0].count) * 100) : 0;
                    return (
                      <div key={item.term} className="flex items-center gap-2 text-[11px]">
                        <div className="w-40 truncate font-mono" title={item.term}>
                          {item.term}
                        </div>
                        <div className="flex-1 h-2 rounded-full bg-surface-container-high overflow-hidden">
                          <div className="h-full bg-red-400/60" style={{ width: `${pct}%` }} />
                        </div>
                        <div className="w-8 text-right font-mono tabular-nums text-on-surface-variant">{item.count}</div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-[12px] text-on-surface-variant">{t('compliance.leaderboard_empty')}</div>
              )}
            </div>

            <div className="bg-surface-container border border-outline-variant/30 rounded-xl p-4 flex flex-col">
              <div className="text-[10px] font-black tracking-widest text-secondary uppercase flex items-center gap-2 mb-3">
                <ShieldCheck className="w-3.5 h-3.5" /> {t('compliance.avoid_preview_title')}
              </div>
              {stats && stats.avoid_terms_preview.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {stats.avoid_terms_preview.map((term) => (
                    <span
                      key={term}
                      className="text-[10px] font-bold px-2 py-0.5 rounded-full border border-amber-200 bg-amber-50 text-amber-800 font-mono"
                    >
                      {term}
                    </span>
                  ))}
                </div>
              ) : (
                <div className="text-[12px] text-on-surface-variant">{t('compliance.avoid_preview_empty')}</div>
              )}
              <div className="mt-2 text-[10px] text-on-surface-variant italic">{t('compliance.avoid_preview_hint')}</div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default ComplianceAdmin;
