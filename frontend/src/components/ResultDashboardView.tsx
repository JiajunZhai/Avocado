import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Copy, Download, FileText, FolderOpen, X } from 'lucide-react';
import { AnimatePresence } from 'framer-motion';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useTranslation } from 'react-i18next';
import { API_BASE } from '../config/apiBase';
import * as XLSX from 'xlsx';

type AnyObj = Record<string, any>;

function copyToClipboard(text: string) {
  const body = String(text ?? '');
  return navigator.clipboard.writeText(body).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = body;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  });
}

function downloadText(filename: string, body: string, mime: string) {
  const blob = new Blob([body], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function ResultDashboardView({
  open,
  onClose,
  result,
}: {
  open: boolean;
  onClose: () => void;
  result: AnyObj | null;
}) {
  const { t } = useTranslation();
  const [markdownText, setMarkdownText] = useState('');
  const [isMarkdownLoading, setIsMarkdownLoading] = useState(false);
  const [isPackaging, setIsPackaging] = useState(false);
  const [complianceOpen, setComplianceOpen] = useState(false);

  const compliance = result?.compliance as AnyObj | undefined;
  const complianceHits = useMemo(() => (Array.isArray(compliance?.hits) ? compliance?.hits : []), [compliance]);
  const complianceSuggestions = useMemo(() => (Array.isArray(compliance?.suggestions) ? compliance?.suggestions : []), [compliance]);

  const adCopyTiles = useMemo(() => {
    const tiles = result?.ad_copy_tiles;
    if (Array.isArray(tiles)) return tiles;
    const acm = result?.ad_copy_matrix;
    if (!acm || typeof acm !== 'object') return [];
    const out: any[] = [];
    const variants = (acm as any).variants;
    if (variants && typeof variants === 'object') {
      const locales: string[] = Array.isArray((acm as any).locales) ? (acm as any).locales : [(acm as any).default_locale || 'en'];
      locales.forEach((loc) => {
        const v = (variants as any)[loc] || {};
        (Array.isArray(v.headlines) ? v.headlines : []).forEach((h: string) =>
          out.push({ id: `${loc}:headline:${out.length}`, locale: loc, kind: 'headline', text: String(h) }),
        );
        (Array.isArray(v.primary_texts) ? v.primary_texts : []).forEach((p: string) =>
          out.push({ id: `${loc}:primary_text:${out.length}`, locale: loc, kind: 'primary_text', text: String(p) }),
        );
        (Array.isArray(v.hashtags) ? v.hashtags : []).forEach((tag: string) =>
          out.push({ id: `${loc}:hashtag:${out.length}`, locale: loc, kind: 'hashtag', text: String(tag) }),
        );
      });
      return out;
    }
    return out;
  }, [result]);

  const tilesById = useMemo(() => {
    const m = new Map<string, any>();
    adCopyTiles.forEach((t: any) => {
      const id = String(t?.id || '');
      if (id) m.set(id, t);
    });
    return m;
  }, [adCopyTiles]);

  const riskyTileIds = useMemo(() => {
    if (!Array.isArray(compliance?.hits)) return new Set<string>();
    return new Set<string>(compliance!.hits.map((h: any) => String(h?.tile_id || '')).filter(Boolean));
  }, [compliance]);

  useEffect(() => {
    const prev = document.body.style.overflow;
    if (open) document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  useEffect(() => {
    const path = result?.markdown_path as string | undefined;
    if (!open || !path) return;
    setIsMarkdownLoading(true);
    setMarkdownText('');
    axios
      .get(`${API_BASE}/api/out/markdown`, { params: { path } })
      .then((res) => setMarkdownText(String(res.data?.markdown ?? '')))
      .catch(() => setMarkdownText(''))
      .finally(() => setIsMarkdownLoading(false));
  }, [open, result?.markdown_path]);

  const downloadMarkdown = () => downloadText(`${String(result?.script_id || 'output')}.md`, markdownText || '', 'text/markdown;charset=utf-8;');

  const openOutFolder = async () => {
    const path = result?.markdown_path;
    if (!path) return;
    try {
      await axios.post(`${API_BASE}/api/out/open-folder`, { path });
    } catch {
      // localhost-gated in backend
    }
  };

  const exportPdf = async () => {
    if (!result || !Array.isArray((result as any).script)) return;
    setIsPackaging(true);
    try {
      const resp = await axios.post(`${API_BASE}/api/export/pdf`, { data: result });
      const b64 = String(resp.data?.pdf_base64 || '');
      if (!b64) return;
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const blob = new Blob([bytes], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${String(result?.script_id || 'output')}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setIsPackaging(false);
    }
  };

  const exportXlsx = () => {
    const acm = result?.ad_copy_matrix;
    if (!acm || typeof acm !== 'object') return;
    const locales: string[] = Array.isArray((acm as any)?.locales) ? (acm as any).locales : [(acm as any)?.default_locale || 'en'];
    const variants = (acm as any)?.variants || {};
    const wb = XLSX.utils.book_new();
    locales.forEach((loc: string) => {
      const v = variants?.[loc] || {};
      const headlines: string[] = Array.isArray(v?.headlines) ? v.headlines : [];
      const primary: string[] = Array.isArray(v?.primary_texts) ? v.primary_texts : [];
      const hashtags: string[] = Array.isArray(v?.hashtags) ? v.hashtags : [];
      const rows = headlines.map((h: string, i: number) => ({
        locale: loc,
        headline: h,
        primary_text: primary[i % Math.max(primary.length, 1)] || '',
        hashtags: hashtags.slice(0, 20).join(' '),
      }));
      const ws = XLSX.utils.json_to_sheet(rows.length ? rows : [{ locale: loc, headline: '', primary_text: '', hashtags: '' }]);
      const safeName = String(loc).slice(0, 31) || 'sheet';
      XLSX.utils.book_append_sheet(wb, ws, safeName);
    });
    const name = `${String(result?.script_id || 'copy_matrix')}.xlsx`;
    XLSX.writeFile(wb, name);
  };

  const renderHighlighted = (text: string, spans: Array<[number, number]>) => {
    const safe = String(text || '');
    const normalized = spans
      .filter((x) => Array.isArray(x) && x.length === 2)
      .map(([s, e]) => [Math.max(0, Number(s) || 0), Math.max(0, Number(e) || 0)] as [number, number])
      .filter(([s, e]) => e > s)
      .sort((a, b) => a[0] - b[0])
      .slice(0, 6);
    if (normalized.length === 0) return <>{safe}</>;
    const out: React.ReactNode[] = [];
    let cur = 0;
    normalized.forEach(([s, e], i) => {
      if (s > cur) out.push(<span key={`t-${i}-a`}>{safe.slice(cur, s)}</span>);
      out.push(
        <mark key={`t-${i}-m`} className="bg-red-200/80 text-red-900 rounded px-1 py-0.5">
          {safe.slice(s, e)}
        </mark>,
      );
      cur = e;
    });
    if (cur < safe.length) out.push(<span key="t-end">{safe.slice(cur)}</span>);
    return <>{out}</>;
  };

  if (!open || !result) return null;

  return (
    <div className="fixed inset-0 z-[200] bg-black/55 backdrop-blur-md flex items-center justify-center p-3 lg:p-6">
      <div className="w-full max-w-[1400px] h-[88vh] bg-surface border border-outline-variant/40 rounded-2xl shadow-elev-2 overflow-hidden flex flex-col">
        <div className="shrink-0 px-4 py-3 border-b border-outline-variant/30 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[10px] uppercase font-bold tracking-widest text-on-surface-variant">{t('lab.dashboard.title')}</div>
            <div className="text-[13px] font-black text-on-surface truncate">
              {String(result?.script_id || 'OUTPUT')}
              {result?.markdown_path ? <span className="ml-2 text-[10px] font-mono text-on-surface-variant">{String(result.markdown_path)}</span> : null}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {isPackaging && (
              <div className="text-[10px] font-bold tracking-widest uppercase text-secondary flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
                {t('lab.dashboard.packaging')}
              </div>
            )}
            <button type="button" onClick={downloadMarkdown} className="btn-director-secondary px-3 py-1.5 text-[11px] font-bold flex items-center gap-2">
              <FileText className="w-4 h-4" /> {t('lab.dashboard.btn_markdown')}
            </button>
            {result?.ad_copy_matrix && (
              <button type="button" onClick={exportXlsx} className="btn-director-secondary px-3 py-1.5 text-[11px] font-bold flex items-center gap-2">
                <Download className="w-4 h-4" /> {t('lab.dashboard.btn_xlsx')}
              </button>
            )}
            {Array.isArray((result as any).script) && (
              <button type="button" onClick={exportPdf} className="btn-director-secondary px-3 py-1.5 text-[11px] font-bold flex items-center gap-2">
                <Download className="w-4 h-4" /> {t('lab.dashboard.btn_pdf')}
              </button>
            )}
            <button type="button" onClick={openOutFolder} className="btn-director-secondary px-3 py-1.5 text-[11px] font-bold flex items-center gap-2">
              <FolderOpen className="w-4 h-4" /> {t('lab.dashboard.btn_open_folder')}
            </button>
            <button type="button" onClick={onClose} className="rounded-lg px-2.5 py-2 border border-outline-variant/40 hover:bg-surface-container transition-colors" aria-label={t('lab.dashboard.close')}>
              <X className="w-4 h-4 text-on-surface-variant" />
            </button>
          </div>
        </div>

        <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-2">
          <div className="min-h-0 border-b lg:border-b-0 lg:border-r border-outline-variant/25 flex flex-col">
            <div className="shrink-0 px-4 py-2 border-b border-outline-variant/20 flex items-center justify-between">
              <div className="text-[10px] font-black tracking-widest text-primary uppercase">{t('lab.dashboard.storyboard_viewer')}</div>
              <button type="button" onClick={() => copyToClipboard(markdownText || '')} className="text-[10px] font-bold text-on-surface-variant hover:text-on-surface flex items-center gap-1.5">
                <Copy className="w-3.5 h-3.5" /> {t('lab.dashboard.copy_markdown')}
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4" style={{ scrollbarGutter: 'stable' }}>
              {isMarkdownLoading ? (
                <div className="text-[12px] text-on-surface-variant">{t('lab.dashboard.loading_markdown')}</div>
              ) : markdownText ? (
                <div className="prose prose-sm max-w-none prose-headings:tracking-tight prose-a:text-primary">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdownText}</ReactMarkdown>
                </div>
              ) : (
                <div className="text-[12px] text-on-surface-variant">{t('lab.dashboard.no_markdown')}</div>
              )}
            </div>
          </div>

          <div className="min-h-0 flex flex-col">
            <div className="shrink-0 px-4 py-2 border-b border-outline-variant/20 flex items-center justify-between gap-3">
              <div className="text-[10px] font-black tracking-widest text-secondary uppercase">{t('lab.dashboard.ad_copy_hub')}</div>
              {compliance && (
                <button
                  type="button"
                  onClick={() => setComplianceOpen(true)}
                  className={`text-[10px] font-bold flex items-center gap-1.5 rounded-full px-2 py-1 border transition-colors ${
                    compliance?.risk_level === 'block'
                      ? 'text-red-700 border-red-200 bg-red-50 hover:bg-red-100/70'
                      : compliance?.risk_level === 'warn'
                        ? 'text-amber-700 border-amber-200 bg-amber-50 hover:bg-amber-100/70'
                        : 'text-emerald-700 border-emerald-200 bg-emerald-50 hover:bg-emerald-100/70'
                  }`}
                  title={t('lab.compliance.open')}
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  {String(compliance?.risk_level || 'ok').toUpperCase()} · {complianceHits.length} {t('lab.dashboard.hits_suffix')}
                </button>
              )}
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 space-y-4" style={{ scrollbarGutter: 'stable' }}>
              {(() => {
                const byLocale: Record<string, any[]> = {};
                adCopyTiles.forEach((t: any) => {
                  const loc = String(t?.locale || 'default');
                  byLocale[loc] = byLocale[loc] || [];
                  byLocale[loc].push(t);
                });
                const locales = Object.keys(byLocale);
                if (locales.length === 0) return <div className="text-[12px] text-on-surface-variant">{t('lab.dashboard.no_tiles')}</div>;
                return locales.map((loc) => {
                  const tiles = byLocale[loc] || [];
                  const headlines = tiles.filter((x) => x.kind === 'headline').slice(0, 50);
                  const primary = tiles.filter((x) => x.kind === 'primary_text').slice(0, 20);
                  const hashtags = tiles.filter((x) => x.kind === 'hashtag').slice(0, 40);
                  return (
                    <div key={loc} className="bg-surface-container-lowest border border-outline-variant/35 rounded-2xl p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-[10px] font-black tracking-widest text-on-surface-variant uppercase">{loc}</div>
                        <button
                          type="button"
                          onClick={() =>
                            copyToClipboard(
                              [...headlines.map((h: any) => String(h.text || '')), '', ...primary.map((p: any) => String(p.text || '')), '', hashtags.map((h: any) => String(h.text || '')).join(' ')].join('\n'),
                            )
                          }
                          className="text-[10px] font-bold text-on-surface-variant hover:text-on-surface flex items-center gap-1.5"
                        >
                          <Copy className="w-3.5 h-3.5" /> {t('lab.dashboard.copy_all')}
                        </button>
                      </div>
                      <div className="grid grid-cols-1 gap-3">
                        {headlines.length > 0 && (
                          <div>
                            <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-2">{t('lab.dashboard.headlines')}</div>
                            <div className="space-y-2">
                              {headlines.map((h: any) => {
                                const risky = riskyTileIds.has(String(h?.id || ''));
                                return (
                                  <div
                                    key={String(h.id)}
                                    className={`rounded-xl border px-3 py-2 text-[12px] text-on-surface flex items-start justify-between gap-2 ${
                                      risky ? 'border-red-400 bg-red-50/70' : 'border-outline-variant/30 bg-surface-container-high'
                                    }`}
                                  >
                                    <div className="min-w-0 flex-1 leading-relaxed">{String(h.text || '')}</div>
                                    <button type="button" onClick={() => copyToClipboard(String(h.text || ''))} className="shrink-0 text-on-surface-variant hover:text-on-surface">
                                      <Copy className="w-4 h-4" />
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                        {primary.length > 0 && (
                          <div>
                            <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-2">{t('lab.dashboard.primary_texts')}</div>
                            <div className="space-y-2">
                              {primary.map((p: any) => {
                                const risky = riskyTileIds.has(String(p?.id || ''));
                                return (
                                  <div
                                    key={String(p.id)}
                                    className={`rounded-xl border px-3 py-2 text-[11px] text-on-surface-variant flex items-start justify-between gap-2 ${
                                      risky ? 'border-red-400 bg-red-50/70' : 'border-outline-variant/30 bg-surface-container-high'
                                    }`}
                                  >
                                    <div className="min-w-0 flex-1 leading-relaxed whitespace-pre-wrap">{String(p.text || '')}</div>
                                    <button type="button" onClick={() => copyToClipboard(String(p.text || ''))} className="shrink-0 text-on-surface-variant hover:text-on-surface">
                                      <Copy className="w-4 h-4" />
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                        {hashtags.length > 0 && (
                          <div>
                            <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-2">{t('lab.dashboard.hashtags')}</div>
                            <div className="rounded-xl border border-outline-variant/30 bg-surface-container-high px-3 py-2 text-[10px] font-mono text-on-surface-variant break-words flex items-start justify-between gap-2">
                              <div className="min-w-0 flex-1">{hashtags.map((h: any) => String(h.text || '')).join(' ')}</div>
                              <button type="button" onClick={() => copyToClipboard(hashtags.map((h: any) => String(h.text || '')).join(' '))} className="shrink-0 text-on-surface-variant hover:text-on-surface">
                                <Copy className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
          </div>
        </div>

        <AnimatePresence>
          {complianceOpen && (
            <div className="absolute inset-0 z-[5] bg-black/40 backdrop-blur-sm flex items-center justify-center p-3">
              <div className="w-full max-w-[980px] h-[78vh] bg-surface border border-outline-variant/40 rounded-2xl shadow-elev-2 overflow-hidden flex flex-col">
                <div className="shrink-0 px-4 py-3 border-b border-outline-variant/30 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[10px] uppercase font-bold tracking-widest text-on-surface-variant">{t('lab.compliance.title')}</div>
                    <div className="text-[12px] font-black text-on-surface truncate">
                      {String(compliance?.risk_level || 'ok').toUpperCase()} · {complianceHits.length} {t('lab.dashboard.hits_suffix')}
                    </div>
                  </div>
                  <button type="button" onClick={() => setComplianceOpen(false)} className="rounded-lg px-2.5 py-2 border border-outline-variant/40 hover:bg-surface-container transition-colors" aria-label={t('lab.compliance.close')}>
                    <X className="w-4 h-4 text-on-surface-variant" />
                  </button>
                </div>
                <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-2">
                  <div className="min-h-0 border-b lg:border-b-0 lg:border-r border-outline-variant/25 flex flex-col">
                    <div className="shrink-0 px-4 py-2 border-b border-outline-variant/20 text-[10px] font-black tracking-widest text-on-surface-variant uppercase">{t('lab.compliance.hits')}</div>
                    <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 space-y-3" style={{ scrollbarGutter: 'stable' }}>
                      {complianceHits.length === 0 ? (
                        <div className="text-[12px] text-on-surface-variant">{t('lab.compliance.no_hits')}</div>
                      ) : (
                        (() => {
                          const grouped: Record<string, any[]> = {};
                          complianceHits.forEach((h: any) => {
                            const tid = String(h?.tile_id || '');
                            if (!tid) return;
                            grouped[tid] = grouped[tid] || [];
                            grouped[tid].push(h);
                          });
                          const ids = Object.keys(grouped);
                          return ids.map((tid) => {
                            const tile = tilesById.get(tid);
                            const text = String(tile?.text || '');
                            const spans = (grouped[tid] || []).map((x: any) => x?.span).filter(Boolean) as Array<[number, number]>;
                            return (
                              <div key={tid} className="rounded-2xl border border-outline-variant/35 bg-surface-container-lowest p-3">
                                <div className="flex items-center justify-between gap-2 mb-2">
                                  <div className="text-[10px] font-black tracking-widest text-on-surface-variant uppercase">
                                    {String(tile?.kind || 'copy')} · {String(tile?.locale || '')}
                                  </div>
                                  <button type="button" onClick={() => copyToClipboard(text)} className="text-[10px] font-bold text-on-surface-variant hover:text-on-surface flex items-center gap-1.5">
                                    <Copy className="w-3.5 h-3.5" /> {t('lab.compliance.copy_original')}
                                  </button>
                                </div>
                                <div className="text-[12px] text-on-surface leading-relaxed">{renderHighlighted(text, spans)}</div>
                              </div>
                            );
                          });
                        })()
                      )}
                    </div>
                  </div>
                  <div className="min-h-0 flex flex-col">
                    <div className="shrink-0 px-4 py-2 border-b border-outline-variant/20 text-[10px] font-black tracking-widest text-on-surface-variant uppercase">{t('lab.compliance.suggestions')}</div>
                    <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 space-y-3" style={{ scrollbarGutter: 'stable' }}>
                      {complianceSuggestions.length === 0 ? (
                        <div className="text-[12px] text-on-surface-variant">{t('lab.compliance.no_suggestions')}</div>
                      ) : (
                        complianceSuggestions.slice(0, 20).map((s: any, idx: number) => (
                          <div key={idx} className="rounded-2xl border border-outline-variant/35 bg-surface-container-lowest p-3">
                            <div className="flex items-center justify-between gap-2 mb-2">
                              <div className="text-[10px] font-black tracking-widest text-on-surface-variant uppercase">{String(tilesById.get(String(s?.tile_id || ''))?.kind || 'copy')}</div>
                              <button type="button" onClick={() => copyToClipboard(String(s?.suggested || ''))} className="text-[10px] font-bold text-on-surface-variant hover:text-on-surface flex items-center gap-1.5">
                                <Copy className="w-3.5 h-3.5" /> {t('lab.compliance.copy_suggested')}
                              </button>
                            </div>
                            <div className="text-[11px] text-on-surface-variant mb-2">
                              <span className="font-bold text-on-surface">{t('lab.compliance.reason')}</span> {String(s?.reason || '')}
                            </div>
                            <div className="text-[12px] text-on-surface leading-relaxed whitespace-pre-wrap">{String(s?.suggested || '')}</div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

