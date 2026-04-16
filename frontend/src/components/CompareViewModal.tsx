import { useEffect, useMemo } from 'react';
import { X, GitCompare, Copy } from 'lucide-react';
import { useTranslation } from 'react-i18next';

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

function uniq(arr: string[]) {
  return Array.from(new Set(arr.filter(Boolean)));
}

function getTilesFromRecord(r: AnyObj | null): Array<{ locale: string; kind: string; text: string }> {
  if (!r) return [];
  const tiles = r.ad_copy_tiles;
  if (Array.isArray(tiles)) {
    return tiles
      .map((t: any) => ({ locale: String(t?.locale || 'default'), kind: String(t?.kind || 'copy'), text: String(t?.text || '') }))
      .filter((x) => x.text);
  }
  const acm = r.ad_copy_matrix;
  if (!acm || typeof acm !== 'object') return [];
  const variants = (acm as any).variants;
  const out: Array<{ locale: string; kind: string; text: string }> = [];
  if (variants && typeof variants === 'object') {
    const locales: string[] = Array.isArray((acm as any).locales) ? (acm as any).locales : [(acm as any).default_locale || 'en'];
    locales.forEach((loc) => {
      const v = (variants as any)[loc] || {};
      (Array.isArray(v.headlines) ? v.headlines : []).forEach((h: string) => out.push({ locale: loc, kind: 'headline', text: String(h) }));
      (Array.isArray(v.primary_texts) ? v.primary_texts : []).forEach((p: string) => out.push({ locale: loc, kind: 'primary_text', text: String(p) }));
      (Array.isArray(v.hashtags) ? v.hashtags : []).forEach((tag: string) => out.push({ locale: loc, kind: 'hashtag', text: String(tag) }));
    });
  }
  return out.filter((x) => x.text);
}

function diffSet(a: string[], b: string[]) {
  const A = new Set(a);
  const B = new Set(b);
  const added = b.filter((x) => !A.has(x));
  const removed = a.filter((x) => !B.has(x));
  return { added, removed };
}

export function CompareViewModal({
  open,
  onClose,
  a,
  b,
}: {
  open: boolean;
  onClose: () => void;
  a: AnyObj | null;
  b: AnyObj | null;
}) {
  const { t } = useTranslation();
  useEffect(() => {
    const prev = document.body.style.overflow;
    if (open) document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  const aRecipe = a?.recipe || {};
  const bRecipe = b?.recipe || {};

  const aTiles = useMemo(() => getTilesFromRecord(a), [a]);
  const bTiles = useMemo(() => getTilesFromRecord(b), [b]);

  const aHeads = useMemo(() => uniq(aTiles.filter((x) => x.kind === 'headline').map((x) => x.text)), [aTiles]);
  const bHeads = useMemo(() => uniq(bTiles.filter((x) => x.kind === 'headline').map((x) => x.text)), [bTiles]);
  const aPrim = useMemo(() => uniq(aTiles.filter((x) => x.kind === 'primary_text').map((x) => x.text)), [aTiles]);
  const bPrim = useMemo(() => uniq(bTiles.filter((x) => x.kind === 'primary_text').map((x) => x.text)), [bTiles]);

  const headsDiff = useMemo(() => diffSet(aHeads, bHeads), [aHeads, bHeads]);
  const primDiff = useMemo(() => diffSet(aPrim, bPrim), [aPrim, bPrim]);

  const aRisk = String(a?.compliance?.risk_level || 'unknown').toUpperCase();
  const bRisk = String(b?.compliance?.risk_level || 'unknown').toUpperCase();
  const aHitTerms = useMemo(
    () => uniq(((a?.compliance?.hits as any[]) || []).map((h: any) => String(h?.term || '')).filter(Boolean)),
    [a?.compliance],
  );
  const bHitTerms = useMemo(
    () => uniq(((b?.compliance?.hits as any[]) || []).map((h: any) => String(h?.term || '')).filter(Boolean)),
    [b?.compliance],
  );
  const hitDiff = useMemo(() => diffSet(aHitTerms, bHitTerms), [aHitTerms, bHitTerms]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[210] bg-black/55 backdrop-blur-md flex items-center justify-center p-3 lg:p-6">
      <div className="w-full max-w-[1200px] h-[86vh] bg-surface border border-outline-variant/40 rounded-2xl shadow-elev-2 overflow-hidden flex flex-col">
        <div className="shrink-0 px-4 py-3 border-b border-outline-variant/30 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[10px] uppercase font-bold tracking-widest text-on-surface-variant flex items-center gap-2">
              <GitCompare className="w-4 h-4 text-primary" /> {t('dashboard.compare.title')}
            </div>
            <div className="text-[12px] font-black text-on-surface truncate">
              {String(a?.id || '')} ↔ {String(b?.id || '')}
            </div>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg px-2.5 py-2 border border-outline-variant/40 hover:bg-surface-container transition-colors" aria-label={t('dashboard.compare.close')}>
            <X className="w-4 h-4 text-on-surface-variant" />
          </button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 space-y-4" style={{ scrollbarGutter: 'stable' }}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div className="rounded-2xl border border-outline-variant/35 bg-surface-container-lowest p-3">
              <div className="text-[10px] font-black tracking-widest text-on-surface-variant uppercase mb-2">{t('dashboard.compare.params_a')}</div>
              <div className="text-[11px] text-on-surface-variant font-mono space-y-1">
                <div>region: <span className="text-on-surface">{String(aRecipe.region || '-')}</span></div>
                <div>platform: <span className="text-on-surface">{String(aRecipe.platform || '-')}</span></div>
                <div>angle: <span className="text-on-surface">{String(aRecipe.angle || '-')}</span></div>
                <div>kind: <span className="text-on-surface">{String(a?.output_kind || '-')}</span></div>
                <div>mode: <span className="text-on-surface">{String(a?.output_mode || '-')}</span></div>
                <div>risk: <span className="text-on-surface">{aRisk}</span></div>
              </div>
            </div>
            <div className="rounded-2xl border border-outline-variant/35 bg-surface-container-lowest p-3">
              <div className="text-[10px] font-black tracking-widest text-on-surface-variant uppercase mb-2">{t('dashboard.compare.params_b')}</div>
              <div className="text-[11px] text-on-surface-variant font-mono space-y-1">
                <div>region: <span className="text-on-surface">{String(bRecipe.region || '-')}</span></div>
                <div>platform: <span className="text-on-surface">{String(bRecipe.platform || '-')}</span></div>
                <div>angle: <span className="text-on-surface">{String(bRecipe.angle || '-')}</span></div>
                <div>kind: <span className="text-on-surface">{String(b?.output_kind || '-')}</span></div>
                <div>mode: <span className="text-on-surface">{String(b?.output_mode || '-')}</span></div>
                <div>risk: <span className="text-on-surface">{bRisk}</span></div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-outline-variant/35 bg-surface-container-lowest p-3">
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="text-[10px] font-black tracking-widest text-on-surface-variant uppercase">{t('dashboard.compare.copy_diff_headlines')}</div>
              <button type="button" className="text-[10px] font-bold text-on-surface-variant hover:text-on-surface flex items-center gap-1.5" onClick={() => copyToClipboard([...headsDiff.added.map((x) => `+ ${x}`), ...headsDiff.removed.map((x) => `- ${x}`)].join('\n'))}>
                <Copy className="w-3.5 h-3.5" /> {t('dashboard.compare.copy_diff_btn')}
              </button>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-3">
                <div className="text-[10px] font-bold text-emerald-700 uppercase tracking-widest mb-2">{t('dashboard.compare.added_in_b')}</div>
                <div className="space-y-2">
                  {headsDiff.added.slice(0, 40).map((x) => (
                    <div key={x} className="text-[12px] text-emerald-950">{x}</div>
                  ))}
                  {headsDiff.added.length === 0 && <div className="text-[12px] text-emerald-900/70">{t('dashboard.compare.none')}</div>}
                </div>
              </div>
              <div className="rounded-xl border border-red-200 bg-red-50/60 p-3">
                <div className="text-[10px] font-bold text-red-700 uppercase tracking-widest mb-2">{t('dashboard.compare.removed_from_a')}</div>
                <div className="space-y-2">
                  {headsDiff.removed.slice(0, 40).map((x) => (
                    <div key={x} className="text-[12px] text-red-950">{x}</div>
                  ))}
                  {headsDiff.removed.length === 0 && <div className="text-[12px] text-red-900/70">{t('dashboard.compare.none')}</div>}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-outline-variant/35 bg-surface-container-lowest p-3">
            <div className="text-[10px] font-black tracking-widest text-on-surface-variant uppercase mb-2">{t('dashboard.compare.compliance_diff_terms')}</div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-3">
                <div className="text-[10px] font-bold text-emerald-700 uppercase tracking-widest mb-2">{t('dashboard.compare.new_terms_in_b')}</div>
                <div className="flex flex-wrap gap-2">
                  {hitDiff.added.slice(0, 40).map((x) => (
                    <span key={x} className="text-[10px] font-bold px-2 py-0.5 rounded-full border bg-white/70 border-emerald-200 text-emerald-800">{x}</span>
                  ))}
                  {hitDiff.added.length === 0 && <div className="text-[12px] text-emerald-900/70">{t('dashboard.compare.none')}</div>}
                </div>
              </div>
              <div className="rounded-xl border border-red-200 bg-red-50/60 p-3">
                <div className="text-[10px] font-bold text-red-700 uppercase tracking-widest mb-2">{t('dashboard.compare.gone_terms_from_a')}</div>
                <div className="flex flex-wrap gap-2">
                  {hitDiff.removed.slice(0, 40).map((x) => (
                    <span key={x} className="text-[10px] font-bold px-2 py-0.5 rounded-full border bg-white/70 border-red-200 text-red-800">{x}</span>
                  ))}
                  {hitDiff.removed.length === 0 && <div className="text-[12px] text-red-900/70">{t('dashboard.compare.none')}</div>}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-outline-variant/35 bg-surface-container-lowest p-3">
            <div className="text-[10px] font-black tracking-widest text-on-surface-variant uppercase mb-2">{t('dashboard.compare.copy_diff_primary')}</div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-3">
                <div className="text-[10px] font-bold text-emerald-700 uppercase tracking-widest mb-2">{t('dashboard.compare.added_in_b')}</div>
                <div className="space-y-2">
                  {primDiff.added.slice(0, 12).map((x) => (
                    <div key={x} className="text-[12px] text-emerald-950 whitespace-pre-wrap">{x}</div>
                  ))}
                  {primDiff.added.length === 0 && <div className="text-[12px] text-emerald-900/70">{t('dashboard.compare.none')}</div>}
                </div>
              </div>
              <div className="rounded-xl border border-red-200 bg-red-50/60 p-3">
                <div className="text-[10px] font-bold text-red-700 uppercase tracking-widest mb-2">{t('dashboard.compare.removed_from_a')}</div>
                <div className="space-y-2">
                  {primDiff.removed.slice(0, 12).map((x) => (
                    <div key={x} className="text-[12px] text-red-950 whitespace-pre-wrap">{x}</div>
                  ))}
                  {primDiff.removed.length === 0 && <div className="text-[12px] text-red-900/70">{t('dashboard.compare.none')}</div>}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

