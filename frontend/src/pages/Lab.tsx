import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Beaker, Layers, Network, Database, Target, Lock, Play, Activity, Globe, MonitorPlay, BrainCircuit, RefreshCw, Eye, Info } from 'lucide-react';
import axios from 'axios';
import { API_BASE } from '../config/apiBase';
import { useProjectContext } from '../context/ProjectContext';
import { useShellActivity } from '../context/ShellActivityContext';
import { ProSelect } from '../components/ProSelect';
import { useTranslation } from 'react-i18next';
import { ResultDashboardView } from '../components/ResultDashboardView';

export const Lab: React.FC = () => {
  const { t } = useTranslation();
  const { currentProject } = useProjectContext();
  const { setGeneratorShell } = useShellActivity();

  // State
  const [metadata, setMetadata] = useState<any>({ regions: [], platforms: [], angles: [] });
  const [regionId, setRegionId] = useState<string>('');
  const [platformId, setPlatformId] = useState<string>('');
  const [angleId, setAngleId] = useState<string>('');
  const [outputType, setOutputType] = useState<'full_sop' | 'quick_copy'>(() => {
    const saved = localStorage.getItem('sop_output_type');
    return saved === 'quick_copy' ? 'quick_copy' : 'full_sop';
  });
  const [copyQuantity, setCopyQuantity] = useState<number>(() => {
    const raw = Number(localStorage.getItem('sop_copy_quantity') || '20');
    return Number.isFinite(raw) && raw > 0 ? Math.min(Math.max(raw, 10), 200) : 20;
  });
  const [copyTones, setCopyTones] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem('sop_copy_tones');
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch {
      return [];
    }
  });
  const [copyLocales, setCopyLocales] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem('sop_copy_locales');
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch {
      return [];
    }
  });
  const [copyRegionIds, setCopyRegionIds] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem('sop_copy_region_ids');
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch {
      return [];
    }
  });
  const [outputMode, setOutputMode] = useState<'cn' | 'en'>(() => {
    const saved = localStorage.getItem('sop_output_mode');
    return saved === 'en' ? 'en' : 'cn';
  });
  const [synthesisMode, setSynthesisMode] = useState<'auto' | 'draft' | 'director'>(() => {
    const saved = localStorage.getItem('sop_synthesis_mode');
    return saved === 'draft' || saved === 'director' ? saved : 'auto';
  });
  const [baseScriptId, setBaseScriptId] = useState<string>(() => {
    return String(localStorage.getItem('sop_base_script_id') || '');
  });
  const [complianceSuggest, setComplianceSuggest] = useState<boolean>(() => {
    return localStorage.getItem('sop_compliance_suggest') === '1';
  });
  
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [synthesisResult, setSynthesisResult] = useState<any>(null);
  const [isSyncingFeed, setIsSyncingFeed] = useState(false);
  const [dashboardOpen, setDashboardOpen] = useState(false);

  // Syncing simulation hook
  useEffect(() => {
    if (regionId || platformId || angleId) {
      setIsSyncingFeed(true);
      const timer = setTimeout(() => setIsSyncingFeed(false), 600);
      return () => clearTimeout(timer);
    }
  }, [regionId, platformId, angleId]);

  useEffect(() => {
    localStorage.setItem('sop_output_mode', outputMode);
  }, [outputMode]);
  useEffect(() => {
    localStorage.setItem('sop_synthesis_mode', synthesisMode);
  }, [synthesisMode]);
  useEffect(() => {
    localStorage.setItem('sop_output_type', outputType);
  }, [outputType]);
  useEffect(() => {
    localStorage.setItem('sop_copy_quantity', String(copyQuantity));
  }, [copyQuantity]);
  useEffect(() => {
    localStorage.setItem('sop_copy_tones', JSON.stringify(copyTones));
  }, [copyTones]);
  useEffect(() => {
    localStorage.setItem('sop_copy_locales', JSON.stringify(copyLocales));
  }, [copyLocales]);
  useEffect(() => {
    localStorage.setItem('sop_copy_region_ids', JSON.stringify(copyRegionIds));
  }, [copyRegionIds]);
  useEffect(() => {
    localStorage.setItem('sop_base_script_id', baseScriptId);
  }, [baseScriptId]);
  useEffect(() => {
    localStorage.setItem('sop_compliance_suggest', complianceSuggest ? '1' : '0');
  }, [complianceSuggest]);

  useEffect(() => {
    if (outputType === 'quick_copy' && regionId && copyRegionIds.length === 0) {
      setCopyRegionIds([regionId]);
    }
  }, [outputType, regionId, copyRegionIds.length]);

  // Fetch DB
  useEffect(() => {
    axios.get(`${API_BASE}/api/insights/metadata`).then(res => {
      setMetadata(res.data);
      if (res.data.regions.length > 0) setRegionId(res.data.regions[0].id);
      if (res.data.platforms.length > 0) setPlatformId(res.data.platforms[0].id);
      if (res.data.angles.length > 0) setAngleId(res.data.angles[0].id);
    }).catch(err => console.error("Failed to fetch insights metadata:", err));
  }, []);

  useEffect(() => {
    setGeneratorShell(isSynthesizing, isSynthesizing ? t('lab.synthesis_status') : '');
    return () => setGeneratorShell(false, '');
  }, [isSynthesizing, setGeneratorShell, t]);

  const activeRegion = metadata.regions.find((r: any) => r.id === regionId);
  const activePlatform = metadata.platforms.find((p: any) => p.id === platformId);
  const activeAngle = metadata.angles.find((a: any) => a.id === angleId);

  const handleSynthesize = async () => {
    if (!currentProject) {
        alert(t('lab.alert_no_project'));
        return;
    }
    setIsSynthesizing(true);
    setSynthesisResult(null);
    try {
      const engine = "cloud";
      const payloadBase = {
        project_id: currentProject.id,
        region_id: regionId,
        platform_id: platformId,
        angle_id: angleId,
        engine,
        output_mode: outputMode,
        compliance_suggest: complianceSuggest,
      };
      const response = outputType === 'quick_copy'
        ? await axios.post(`${API_BASE}/api/quick-copy`, {
            ...payloadBase,
            quantity: copyQuantity,
            tones: copyTones,
            locales: copyLocales,
            region_ids: copyRegionIds,
          })
        : await axios.post(`${API_BASE}/api/generate`, {
            ...payloadBase,
            mode: synthesisMode,
          });
      setSynthesisResult(response.data);
      setDashboardOpen(true);
    } catch (e) {
      console.error(e);
      alert(t('lab.errors.synthesis_failed'));
    } finally {
      setIsSynthesizing(false);
    }
  };

  // Result Dashboard behavior (body scroll lock / markdown fetch) is handled inside ResultDashboardView.

  // Markdown/PDF/Open-folder exports are handled inside ResultDashboardView.

  const handleRefreshCopy = async () => {
    if (!currentProject) return;
    const sid = (baseScriptId || '').trim();
    if (!sid) return;
    setIsSynthesizing(true);
    setSynthesisResult(null);
    try {
      const engine = "cloud";
      const resp = await axios.post(`${API_BASE}/api/quick-copy/refresh`, {
        project_id: currentProject.id,
        base_script_id: sid,
        engine,
        output_mode: outputMode,
        quantity: copyQuantity,
        tones: copyTones,
        locales: copyLocales,
        compliance_suggest: complianceSuggest,
      });
      setSynthesisResult(resp.data);
      setDashboardOpen(true);
    } catch (e) {
      console.error(e);
      alert(t('lab.errors.refresh_failed'));
    } finally {
      setIsSynthesizing(false);
    }
  };

  // Compliance rendering moved into ResultDashboardView.

  const toOptions = (items: any[]) => items.map(i => ({ value: i.id, label: i.name || i.id }));
  const outputModeOptions = useMemo(
    () => [
      { value: 'cn', label: t('lab.output_mode.cn') },
      { value: 'en', label: t('lab.output_mode.en') },
    ],
    [t]
  );
  const synthesisModeOptions = useMemo(
    () => [
      { value: 'auto', label: t('lab.console.gen_mode_auto') },
      { value: 'draft', label: t('lab.console.gen_mode_draft') },
      { value: 'director', label: t('lab.console.gen_mode_director') },
    ],
    [t]
  );

  const copyToneOptions = useMemo(
    () => [
      { id: 'humor', label: t('lab.console.tones.humor') },
      { id: 'pro', label: t('lab.console.tones.pro') },
      { id: 'clickbait', label: t('lab.console.tones.clickbait') },
      { id: 'benefit', label: t('lab.console.tones.benefit') },
      { id: 'fomo', label: t('lab.console.tones.fomo') },
    ],
    [t]
  );
  const copyLocaleOptions = useMemo(
    () => [
      { id: 'en', label: 'English (EN)' },
      { id: 'ja', label: '日本語 (JA)' },
      { id: 'ar', label: 'العربية (AR)' },
      { id: 'es', label: 'Español (ES)' },
      { id: 'pt', label: 'Português (PT)' },
      { id: 'fr', label: 'Français (FR)' },
      { id: 'de', label: 'Deutsch (DE)' },
      { id: 'id', label: 'Bahasa (ID)' },
      { id: 'th', label: 'ไทย (TH)' },
    ],
    []
  );

  const isQuickCopyResult = synthesisResult && synthesisResult.ad_copy_matrix && !Array.isArray(synthesisResult.script);
  const downloadCsv = (locale: string, rows: { primary_text: string; headline: string; hashtag_pack: string }[]) => {
    const header = ['locale', 'headline', 'primary_text', 'hashtags'];
    const escape = (v: string) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const body = rows
      .map((r) => [locale, r.headline, r.primary_text, r.hashtag_pack].map(escape).join(','))
      .join('\n');
    const csv = `${header.join(',')}\n${body}\n`;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `copy_matrix_${locale}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  // XLSX export is handled inside ResultDashboardView.

  return (
    <div className="w-full h-full flex flex-col bg-background text-on-background relative overflow-x-hidden page-pad">
      {/* Sleek Light/Ambient Gradients */}
      <div className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] bg-primary/5 rounded-full blur-[100px] pointer-events-none -z-10" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] bg-secondary/5 rounded-full blur-[100px] pointer-events-none -z-10" />

      <ResultDashboardView open={dashboardOpen} onClose={() => setDashboardOpen(false)} result={synthesisResult} />

      <div className="max-w-[1600px] w-full mx-auto h-full flex flex-col min-h-0 card-base shadow-sm border border-outline-variant/30 p-6 lg:p-8 relative z-10">
        
        {/* Header Block */}
        <motion.header
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex items-start justify-between shrink-0 mb-6 border-b border-outline-variant/30 pb-6"
        >
          <div className="flex items-center gap-5">
             <div className="w-14 h-14 bg-gradient-to-br from-surface-container-lowest to-surface-container rounded-2xl flex items-center justify-center border border-outline-variant/40 shadow-sm shrink-0">
               <Beaker className="w-7 h-7 text-primary" />
             </div>
             
             <div>
               <div className="flex items-center gap-2 text-primary font-bold text-[11px] uppercase tracking-[0.2em] mb-1 opacity-90">
                 <Layers className="w-3.5 h-3.5" /> {t('lab.pipeline_title')}
               </div>
               <h1 className="text-3xl lg:text-[2rem] font-black tracking-tight text-on-surface leading-tight">
                 {t('lab.title')}
               </h1>
             </div>
          </div>
        </motion.header>

        {/* 1-2-1 Flow Architecture */}
        <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-6 relative overflow-x-hidden">
           
           {/* Column 1: Source */}
           <div className="w-full lg:w-[280px] xl:w-[320px] shrink-0 flex flex-col min-h-0 lg:border-r border-outline-variant/30 lg:pr-6">
             <div className="flex items-center justify-between pb-3 shrink-0">
               <span className="text-[11px] uppercase font-bold tracking-[0.1em] text-on-surface-variant flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5" /> {t('lab.slot_a.header')}
               </span>
               {currentProject?.name ? (
                 <span
                   className="text-[10px] font-black text-on-surface-variant/80 truncate max-w-[55%] text-right"
                   title={currentProject.name}
                 >
                   {currentProject.name}
                 </span>
               ) : null}
             </div>
             
             <div
               className="flex-1 min-h-0 flex flex-col gap-4 overflow-y-auto custom-scrollbar pb-4 pr-1"
               style={{ scrollbarGutter: 'stable' }}
             >
               {/* Project Card */}
               <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="bg-surface-container-low border border-outline-variant/40 rounded-2xl p-5 relative overflow-hidden shadow-sm">
                 <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl -z-10" />
                 <div className="text-[10px] uppercase font-bold tracking-widest text-on-surface-variant flex items-center gap-1.5 mb-3">
                    <Lock className="w-3 h-3 text-secondary"/> {t('lab.slot_a.title')}
                 </div>
                 <div className="text-lg font-black text-on-surface leading-tight break-words mb-3">
                   {currentProject?.name || t('lab.empty.select_project')}
                 </div>
                 <div className="text-[9px] font-mono text-on-surface-variant bg-surface-container-high px-2 py-1 rounded inline-block border border-outline-variant/30">
                   ID: {currentProject?.id || 'null'}
                 </div>
               </motion.div>

               {/* Gameplay Data */}
               <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="flex flex-col flex-1">
                  <div className="text-[10px] uppercase font-bold tracking-widest text-on-surface-variant mb-2 px-1">
                     {t('lab.slot_a.base_params')}
                  </div>
                  <div className="flex-1 bg-surface-container-lowest border border-outline-variant/40 rounded-2xl p-3 text-[12px] text-on-surface/80 overflow-y-auto custom-scrollbar shadow-inner leading-relaxed">
                     {currentProject?.game_info ? (
                        <div className="space-y-3">
                          <details className="rounded-xl border border-outline-variant/25 bg-surface-container-high/70 px-3 py-2">
                            <summary className="cursor-pointer select-none flex items-center justify-between gap-2 list-none [&::-webkit-details-marker]:hidden">
                              <span className="font-bold text-primary text-[10px] uppercase tracking-wider">{t('lab.slot_a.core_gameplay')}</span>
                              <span className="text-[10px] text-on-surface-variant">{t('lab.slot_a.expand')}</span>
                            </summary>
                            <div className="pt-2 text-[12px] text-on-surface/80 leading-relaxed whitespace-pre-wrap">
                              {currentProject.game_info.core_gameplay}
                            </div>
                          </details>

                          <details className="rounded-xl border border-outline-variant/25 bg-surface-container-high/70 px-3 py-2">
                            <summary className="cursor-pointer select-none flex items-center justify-between gap-2 list-none [&::-webkit-details-marker]:hidden">
                              <span className="font-bold text-secondary text-[10px] uppercase tracking-wider">{t('lab.slot_a.usp_extracted')}</span>
                              <span className="text-[10px] text-on-surface-variant">{t('lab.slot_a.expand')}</span>
                            </summary>
                            <div className="pt-2 text-[12px] text-on-surface/80 leading-relaxed whitespace-pre-wrap">
                              {currentProject.game_info.core_usp}
                            </div>
                          </details>
                        </div>
                     ) : (
                        <div className="flex flex-col items-center justify-center h-full text-on-surface-variant opacity-50 space-y-2">
                           <Info className="w-6 h-6" />
                           <span>{t('lab.empty.select_project')}</span>
                        </div>
                     )}
                  </div>
               </motion.div>
             </div>
           </div>

           {/* Column 2: Mixing Console */}
           <div className="flex-1 min-w-0 shrink flex flex-col min-h-0 relative z-10 pb-4">
             <div className="flex items-center justify-between pb-3 shrink-0">
               <span className="text-[11px] uppercase font-bold tracking-[0.1em] text-on-surface-variant flex items-center gap-1.5">
                  <Network className="w-3.5 h-3.5 text-primary" /> {t('lab.mixing_console')}
               </span>
               <span className="text-[9px] font-bold tracking-[0.1em] text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  {t('lab.db_synced')}
               </span>
             </div>

             <div className="flex-1 overflow-visible w-full max-w-[720px] mx-auto relative pb-2 px-1">
               <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                 {/* OUTPUT TYPE (spans) */}
                 <div className="sm:col-span-2 w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-3 shadow-sm hover:shadow-md transition-shadow relative flex flex-col">
                   <div className="flex items-center gap-2 mb-2">
                     <div className="w-5 h-5 rounded-md bg-secondary/10 flex items-center justify-center shrink-0">
                       <BrainCircuit className="w-3 h-3 text-secondary" />
                     </div>
                     <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.console.output_type')}</div>
                   </div>
                   <div className="flex items-center gap-2">
                     <button
                       type="button"
                       onClick={() => setOutputType('full_sop')}
                       className={`flex-1 rounded-lg px-2.5 py-2 text-[11px] font-bold border transition-colors ${
                         outputType === 'full_sop'
                           ? 'bg-primary text-on-primary border-primary'
                           : 'bg-surface-container-high text-on-surface border-outline-variant/35 hover:border-primary/30'
                       }`}
                     >
                       {t('lab.console.full_sop')}
                     </button>
                     <button
                       type="button"
                       onClick={() => setOutputType('quick_copy')}
                       className={`flex-1 rounded-lg px-2.5 py-2 text-[11px] font-bold border transition-colors ${
                         outputType === 'quick_copy'
                           ? 'bg-secondary text-on-primary border-secondary'
                           : 'bg-surface-container-high text-on-surface border-outline-variant/35 hover:border-secondary/30'
                       }`}
                     >
                       {t('lab.console.quick_copy')}
                     </button>
                   </div>
                 </div>

                 {/* Region */}
                 <div className="w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-2 shadow-sm hover:shadow-md transition-shadow relative flex flex-col">
                   <div className="flex items-center gap-2 mb-1.5">
                     <div className="w-5 h-5 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
                       <Globe className="w-3 h-3 text-primary" />
                     </div>
                     <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.slot_b.label')}</div>
                   </div>
                   {regionId && <ProSelect value={regionId} onChange={setRegionId} options={toOptions(metadata.regions)} />}
                 </div>

                 {/* Platform */}
                 <div className="w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-2 shadow-sm hover:shadow-md transition-shadow relative flex flex-col">
                   <div className="flex items-center gap-2 mb-1.5">
                     <div className="w-5 h-5 rounded-md bg-secondary/10 flex items-center justify-center shrink-0">
                       <MonitorPlay className="w-3 h-3 text-secondary" />
                     </div>
                     <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.slot_c.label')}</div>
                   </div>
                   {platformId && <ProSelect value={platformId} onChange={setPlatformId} options={toOptions(metadata.platforms)} />}
                 </div>

                 {/* Angle */}
                 <div className="w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-2 shadow-sm hover:shadow-md transition-shadow relative flex flex-col">
                   <div className="flex items-center gap-2 mb-1.5">
                     <div className="w-5 h-5 rounded-md bg-emerald-50 flex items-center justify-center shrink-0">
                       <Target className="w-3 h-3 text-emerald-600" />
                     </div>
                     <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.slot_d.label')}</div>
                   </div>
                   {angleId && <ProSelect value={angleId} onChange={setAngleId} options={toOptions(metadata.angles)} dropUp={true} />}
                 </div>

                 {/* Output Language */}
                 <div className="w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-2 shadow-sm hover:shadow-md transition-shadow relative flex flex-col">
                   <div className="flex items-center gap-2 mb-1.5">
                     <div className="w-5 h-5 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
                       <Globe className="w-3 h-3 text-primary" />
                     </div>
                     <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.output_mode.label')}</div>
                   </div>
                   <ProSelect
                     value={outputMode}
                     onChange={(v) => setOutputMode((v === 'en' ? 'en' : 'cn'))}
                     options={outputModeOptions}
                     dropUp={true}
                   />
                 </div>

                {/* Compliance Suggest */}
                <div className="sm:col-span-2 w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-3 shadow-sm hover:shadow-md transition-shadow relative flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.console.compliance_suggest')}</div>
                    <div className="text-[10px] text-on-surface-variant mt-1">{t('lab.console.compliance_suggest_hint')}</div>
                  </div>
                  <label className="shrink-0 inline-flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={complianceSuggest}
                      onChange={(e) => setComplianceSuggest(e.target.checked)}
                      className="sr-only"
                    />
                    <span
                      className={`w-11 h-6 rounded-full border transition-colors relative ${
                        complianceSuggest ? 'bg-secondary border-secondary/40' : 'bg-surface-container-high border-outline-variant/40'
                      }`}
                      aria-hidden
                    >
                      <span
                        className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-surface shadow-sm transition-transform ${
                          complianceSuggest ? 'translate-x-5' : ''
                        }`}
                      />
                    </span>
                    <span className="text-[10px] font-bold text-on-surface-variant">{complianceSuggest ? 'ON' : 'OFF'}</span>
                  </label>
                </div>

                 {/* Full SOP: Gen Mode */}
                 {outputType === 'full_sop' ? (
                   <div className="sm:col-span-2 w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-2 shadow-sm hover:shadow-md transition-shadow relative flex flex-col">
                     <div className="flex items-center gap-2 mb-1.5">
                       <div className="w-5 h-5 rounded-md bg-secondary/10 flex items-center justify-center shrink-0">
                         <BrainCircuit className="w-3 h-3 text-secondary" />
                       </div>
                       <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.console.gen_mode')}</div>
                     </div>
                     <ProSelect
                       value={synthesisMode}
                       onChange={(v) => setSynthesisMode((v === 'draft' || v === 'director') ? v : 'auto')}
                       options={synthesisModeOptions}
                       dropUp={true}
                     />
                   </div>
                 ) : (
                   <details className="sm:col-span-2 w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-3 shadow-sm hover:shadow-md transition-shadow">
                     <summary className="cursor-pointer select-none list-none flex items-center justify-between">
                       <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.console.quick_copy_config')}</div>
                       <div className="text-[10px] font-mono text-on-surface-variant">{t('lab.console.expand')}</div>
                     </summary>
                     <div className="pt-3 space-y-3">
                       <div className="space-y-2">
                         <div className="flex items-center justify-between text-[11px] font-semibold text-on-surface">
                           <span>{t('lab.console.regions_multi')}</span>
                           <span className="font-mono text-secondary">{copyRegionIds.length || 0}</span>
                         </div>
                         <div className="flex flex-wrap gap-2 max-h-[92px] overflow-y-auto custom-scrollbar pr-1">
                           {(metadata.regions || []).map((r: any) => {
                             const id = String(r?.id || '');
                             const label = String(r?.short_name || r?.name || id);
                             const checked = copyRegionIds.includes(id);
                             return (
                               <button
                                 key={id}
                                 type="button"
                                 onClick={() => {
                                   if (!id) return;
                                   setCopyRegionIds((prev) => checked ? prev.filter((x) => x !== id) : [...prev, id]);
                                 }}
                                 className={`rounded-full px-2.5 py-1 text-[10px] font-bold border transition-colors ${
                                   checked
                                     ? 'bg-secondary/15 text-secondary border-secondary/30'
                                     : 'bg-surface-container-high text-on-surface-variant border-outline-variant/35 hover:border-secondary/30'
                                 }`}
                                 title={String(r?.name || id)}
                               >
                                 {label}
                               </button>
                             );
                           })}
                         </div>
                         <div className="text-[10px] text-on-surface-variant">{t('lab.console.empty_region_hint')}</div>
                       </div>

                       <div className="space-y-1">
                         <div className="flex items-center justify-between text-[11px] font-semibold text-on-surface">
                           <span>{t('lab.console.quantity_headlines')}</span>
                           <span className="font-mono text-secondary">{copyQuantity}</span>
                         </div>
                         <input
                           type="range"
                           min={10}
                           max={100}
                           step={10}
                           value={copyQuantity}
                           onChange={(e) => setCopyQuantity(Number(e.target.value))}
                           className="w-full accent-secondary"
                         />
                         <div className="text-[10px] text-on-surface-variant">10 / 20 / 50</div>
                       </div>

                       <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                         <div className="space-y-2">
                           <div className="text-[11px] font-semibold text-on-surface">{t('lab.console.tone')}</div>
                           <div className="grid grid-cols-2 gap-2">
                             {copyToneOptions.map((opt) => {
                               const checked = copyTones.includes(opt.id);
                               return (
                                 <button
                                   key={opt.id}
                                   type="button"
                                   onClick={() => {
                                     setCopyTones((prev) => checked ? prev.filter((x) => x !== opt.id) : [...prev, opt.id]);
                                   }}
                                   className={`rounded-lg px-2 py-1.5 text-[11px] font-bold border transition-colors ${
                                     checked
                                       ? 'bg-secondary/15 text-secondary border-secondary/30'
                                       : 'bg-surface-container-high text-on-surface border-outline-variant/35 hover:border-secondary/30'
                                   }`}
                                 >
                                   {opt.label}
                                 </button>
                               );
                             })}
                           </div>
                         </div>
                         <div className="space-y-2">
                           <div className="text-[11px] font-semibold text-on-surface">{t('lab.console.localization')}</div>
                           <div className="flex flex-wrap gap-2">
                             {copyLocaleOptions.map((opt) => {
                               const checked = copyLocales.includes(opt.id);
                               return (
                                 <button
                                   key={opt.id}
                                   type="button"
                                   onClick={() => {
                                     setCopyLocales((prev) => checked ? prev.filter((x) => x !== opt.id) : [...prev, opt.id]);
                                   }}
                                   className={`rounded-full px-2.5 py-1 text-[10px] font-bold border transition-colors ${
                                     checked
                                       ? 'bg-primary/15 text-primary border-primary/30'
                                       : 'bg-surface-container-high text-on-surface-variant border-outline-variant/35 hover:border-primary/30'
                                   }`}
                                 >
                                   {opt.label}
                                 </button>
                               );
                             })}
                           </div>
                           <div className="text-[10px] text-on-surface-variant">{t('lab.console.empty_locale_hint')}</div>
                         </div>
                       </div>

                       <div className="space-y-2 pt-1">
                         <div className="text-[11px] font-semibold text-on-surface">{t('lab.console.copy_refresher')}</div>
                         <input
                           value={baseScriptId}
                           onChange={(e) => setBaseScriptId(e.target.value)}
                           placeholder={t('lab.console.base_script_placeholder')}
                           className="w-full bg-surface-container-high text-[11px] text-on-surface px-3 py-2 rounded-lg border border-outline-variant/35 focus:outline-none focus:border-secondary/50 focus:ring-1 focus:ring-secondary/30 placeholder:text-on-surface-variant/50 font-mono"
                         />
                         <button
                           type="button"
                           onClick={handleRefreshCopy}
                           disabled={isSynthesizing || !currentProject || !baseScriptId.trim()}
                           className={`btn-director-secondary w-full py-2 text-[11px] font-bold uppercase tracking-widest flex items-center justify-center gap-2 ${isSynthesizing ? 'opacity-70 cursor-wait' : ''}`}
                         >
                           <RefreshCw className={`w-4 h-4 ${isSynthesizing ? 'animate-spin' : ''}`} />
                           {t('lab.console.refresh_copy_btn')}
                         </button>
                         <div className="text-[10px] text-on-surface-variant">{t('lab.console.refresh_copy_hint')}</div>
                       </div>
                     </div>
                   </details>
                 )}

                 {/* Generate */}
                 <div className="sm:col-span-2 w-full shrink-0 pt-1">
                   <motion.button
                     whileHover={!(isSynthesizing || !currentProject || !regionId) ? { scale: 1.02 } : {}}
                     whileTap={!(isSynthesizing || !currentProject || !regionId) ? { scale: 0.98 } : {}}
                     onClick={handleSynthesize}
                     disabled={isSynthesizing || !currentProject || !regionId}
                     className={`btn-director-primary w-full py-3 text-xs font-bold uppercase tracking-widest flex items-center justify-center gap-2 shadow-md ${isSynthesizing ? 'opacity-70 cursor-wait' : ''}`}
                   >
                     {isSynthesizing ? (
                       <><RefreshCw className="w-4 h-4 animate-spin" /> SYNTHESIZING...</>
                     ) : (
                       <><Play className="w-4 h-4" /> {t('nav.initiate')}</>
                     )}
                   </motion.button>
                 </div>
               </div>
             </div>
           </div>

           {/* Column 3: Output Feed */}
           <div className="w-full lg:w-[320px] xl:w-[380px] shrink-0 flex flex-col min-h-0 lg:border-l border-outline-variant/30 lg:pl-6 pb-4">
              <div className="flex items-center justify-between pb-3 shrink-0">
                 <span className="text-[11px] uppercase font-bold tracking-[0.1em] text-on-surface-variant flex items-center gap-1.5">
                    {synthesisResult ? <Eye className="w-3.5 h-3.5 text-primary" /> : <Activity className={`w-3.5 h-3.5 ${isSyncingFeed ? 'text-primary animate-pulse' : ''}`} />}
                    {synthesisResult ? t('lab.feed.compiled_blueprint') : t('lab.feed.resonance_feed')}
                 </span>
                 <span className={`text-[9px] font-bold tracking-[0.1em] px-2 py-0.5 rounded border ${synthesisResult ? 'bg-primary/10 text-primary border-primary/20' : (isSyncingFeed ? 'bg-primary/5 text-primary border-primary/20 animate-pulse' : 'bg-surface-container-high text-on-surface-variant border-outline-variant/30')}`}>
                    {synthesisResult ? t('lab.feed.secure') : (isSyncingFeed ? t('lab.feed.syncing') : t('lab.feed.standby'))}
                 </span>
              </div>

              <div
                className="flex-1 min-h-0 overflow-y-auto custom-scrollbar pr-1 bg-surface-container-lowest/50 rounded-2xl border border-outline-variant/20 p-2 relative"
                style={{ scrollbarGutter: 'stable' }}
              >
                 <AnimatePresence mode="wait">
                    {!synthesisResult ? (
                      <motion.div key="feed" initial={{ opacity: 0 }} animate={{ opacity: isSyncingFeed ? 0.5 : 1, filter: isSyncingFeed ? 'blur(2px)' : 'blur(0px)' }} exit={{ opacity: 0 }} className="flex flex-col gap-3 p-1 h-fit">
                         {activeRegion && (
                           <motion.div layout initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}} className="bg-surface-container-lowest border border-outline-variant/40 shadow-sm rounded-2xl p-3 shrink-0">
                             <details open>
                               <summary className="cursor-pointer select-none list-none flex items-center justify-between gap-2">
                                 <div className="text-[10px] font-bold uppercase tracking-widest text-primary flex items-center gap-1.5">
                                   <Globe className="w-3 h-3" /> {t('lab.feed.region_node')}
                                 </div>
                                 <span className="text-[10px] font-mono text-on-surface-variant truncate max-w-[140px]">{activeRegion.id}</span>
                               </summary>
                               <div className="pt-2 text-[11px] text-on-surface/80 leading-relaxed space-y-1.5">
                                 <div className="line-clamp-2">
                                   <span className="font-semibold text-on-surface">{t('lab.feed.constraint')}:</span> {activeRegion.culture_notes?.[0]}
                                 </div>
                                 <div className="truncate">
                                   <span className="font-semibold text-on-surface">{t('lab.feed.bgm')}:</span> {activeRegion.preferred_bgm}
                                 </div>
                               </div>
                             </details>
                           </motion.div>
                         )}
                         {activePlatform && (
                           <motion.div layout initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}} className="bg-surface-container-lowest border border-outline-variant/40 shadow-sm rounded-2xl p-3 shrink-0">
                             <details open>
                               <summary className="cursor-pointer select-none list-none flex items-center justify-between gap-2">
                                 <div className="text-[10px] font-bold uppercase tracking-widest text-secondary flex items-center gap-1.5">
                                   <MonitorPlay className="w-3 h-3" /> {t('lab.feed.platform_node')}
                                 </div>
                                 <span className="text-[10px] font-mono text-on-surface-variant truncate max-w-[140px]">{activePlatform.id}</span>
                               </summary>
                               <div className="pt-2 text-[11px] text-on-surface/80 leading-relaxed">
                                 <div className="line-clamp-3">
                                   <span className="font-semibold text-on-surface">{t('lab.feed.rules')}:</span> {(activePlatform.specs?.[0] ?? '') as any}
                                 </div>
                               </div>
                             </details>
                           </motion.div>
                         )}
                         {activeAngle && (
                           <motion.div layout initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}} className="bg-surface-container-lowest border border-outline-variant/40 shadow-sm rounded-2xl p-3 shrink-0">
                             <details open>
                               <summary className="cursor-pointer select-none list-none flex items-center justify-between gap-2">
                                 <div className="text-[10px] font-bold uppercase tracking-widest text-emerald-600 flex items-center gap-1.5">
                                   <Target className="w-3 h-3" /> {t('lab.feed.angle_node')}
                                 </div>
                                 <span className="text-[10px] font-mono text-on-surface-variant truncate max-w-[140px]">{activeAngle.id}</span>
                               </summary>
                               <div className="pt-2 text-[11px] text-on-surface/80 leading-relaxed space-y-1.5">
                                 <div className="truncate">
                                   <span className="font-semibold text-on-surface">{t('lab.feed.emotion')}:</span> {activeAngle.core_emotion}
                                 </div>
                                 <div className="line-clamp-3">
                                   <span className="font-semibold text-on-surface">{t('lab.feed.logic')}:</span> {(activeAngle.logic_steps?.[0] ?? '') as any}
                                 </div>
                               </div>
                             </details>
                           </motion.div>
                         )}
                      </motion.div>
                    ) : (
                      <motion.div key="result" variants={{ hidden: {}, show: { transition: { staggerChildren: 0.1 } } }} initial="hidden" animate="show" className="flex flex-col gap-4 p-1 h-fit">
                         <motion.div variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }} className="bg-primary/5 border border-primary/20 rounded-xl p-4 shrink-0">
                           <div className="flex justify-between items-center mb-3 border-b border-primary/10 pb-2">
                              <div className="text-[10px] uppercase font-bold text-primary tracking-widest flex items-center gap-2"><BrainCircuit className="w-4 h-4" /> PSY-INSIGHT</div>
                              {synthesisResult.script_id && (
                                 <div className="text-[9px] font-mono text-primary bg-primary/10 px-2 py-0.5 rounded flex items-center gap-1.5">
                                   ID: {synthesisResult.script_id}
                                 </div>
                              )}
                           </div>
                           <div className="text-[12px] text-on-surface/90 leading-relaxed font-medium">
                            {isQuickCopyResult ? t('lab.result.quick_copy_ready') : synthesisResult.psychology_insight}
                           </div>
                         </motion.div>
                         <motion.div variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }} className="bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-3 shrink-0 flex items-center justify-between gap-2">
                           <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.dashboard.title')}</div>
                           <button
                             type="button"
                             onClick={() => setDashboardOpen(true)}
                             className="btn-director-secondary px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-widest flex items-center gap-2"
                           >
                             <Eye className="w-4 h-4" /> {t('lab.result.open_dashboard')}
                           </button>
                         </motion.div>
                        {synthesisResult.review && (
                          <motion.div variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }} className="bg-amber-50 border border-amber-200 rounded-xl p-4 shrink-0">
                            <div className="text-[10px] uppercase font-bold text-amber-700 tracking-widest mb-2">AUTO REVIEW</div>
                            <div className="text-[12px] text-amber-900 mb-2">
                              Score: {synthesisResult.review?.score_breakdown?.overall ?? 'N/A'}
                            </div>
                            {Array.isArray(synthesisResult.review?.issues) && synthesisResult.review.issues.length > 0 && (
                              <div className="text-[11px] text-red-700 mb-1">
                                Issues: {synthesisResult.review.issues.map((i: any) => i.message).join(' | ')}
                              </div>
                            )}
                            {Array.isArray(synthesisResult.review?.warnings) && synthesisResult.review.warnings.length > 0 && (
                              <div className="text-[11px] text-amber-700">
                                Warnings: {synthesisResult.review.warnings.map((i: any) => i.message).join(' | ')}
                              </div>
                            )}
                          </motion.div>
                        )}
                        {Array.isArray(synthesisResult.drafts) && synthesisResult.drafts.length > 0 && (
                          <motion.div variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }} className="bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-3 shrink-0">
                            <div className="text-[10px] uppercase font-bold tracking-widest text-on-surface-variant mb-2">Draft Candidates</div>
                            <div className="space-y-1">
                              {synthesisResult.drafts.slice(0, 3).map((d: any, i: number) => (
                                <div key={i} className="text-[11px] text-on-surface">
                                  {d.id || `D${i + 1}`}: {d.title || d.hook || 'Untitled'}
                                </div>
                              ))}
                            </div>
                          </motion.div>
                        )}

                         {synthesisResult.markdown_path && (
                           <div className="rounded-xl border border-outline-variant/35 bg-surface-container-high/80 px-3 py-2 text-[10px] font-mono text-on-surface-variant break-all">
                             {t('lab.markdown_saved', { path: synthesisResult.markdown_path })}
                           </div>
                         )}

                         {isQuickCopyResult ? (
                           <div className="flex flex-col gap-3 pt-1">
                             {(() => {
                               const acm = synthesisResult.ad_copy_matrix;
                               const locales: string[] = Array.isArray(acm?.locales) ? acm.locales : [acm?.default_locale || 'en'];
                               const variants = acm?.variants || {};
                               return locales.map((loc: string) => {
                                 const v = variants?.[loc] || {};
                                 const headlines: string[] = Array.isArray(v?.headlines) ? v.headlines : [];
                                 const primary: string[] = Array.isArray(v?.primary_texts) ? v.primary_texts : [];
                                 const hashtags: string[] = Array.isArray(v?.hashtags) ? v.hashtags : [];
                                 const rows = headlines.map((h: string, i: number) => ({
                                   headline: h,
                                   primary_text: primary[i % Math.max(primary.length, 1)] || '',
                                   hashtag_pack: hashtags.slice(0, 20).join(' '),
                                 }));
                                 return (
                                   <motion.div
                                     key={loc}
                                     variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }}
                                     className="bg-surface-container-lowest border border-outline-variant/40 shadow-sm rounded-xl p-3 shrink-0"
                                   >
                                     <div className="flex items-center justify-between mb-2">
                                       <div className="text-[10px] font-black tracking-widest text-secondary uppercase">COPY MARKET · {loc}</div>
                                       <button
                                         type="button"
                                         onClick={() => downloadCsv(loc, rows)}
                                         className="btn-director-secondary px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-widest"
                                       >
                                         Export CSV
                                       </button>
                                     </div>
                                     <div className="space-y-2">
                                       <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Headlines</div>
                                       <div className="space-y-1">
                                         {headlines.slice(0, 20).map((h: string, i: number) => (
                                           <div key={i} className="bg-surface-container-high border border-outline-variant/25 rounded-lg px-2.5 py-2 text-[12px] text-on-surface">
                                             <div
                                               contentEditable
                                               suppressContentEditableWarning
                                               className="outline-none"
                                               onBlur={(e) => {
                                                 const next = e.currentTarget.textContent || '';
                                                 setSynthesisResult((prev: any) => {
                                                   const nextObj = { ...(prev || {}) };
                                                   const nextAcm = { ...(nextObj.ad_copy_matrix || {}) };
                                                   const nextVariants = { ...(nextAcm.variants || {}) };
                                                   const nextV = { ...(nextVariants[loc] || {}) };
                                                   const nextHeadlines = Array.isArray(nextV.headlines) ? [...nextV.headlines] : [];
                                                   nextHeadlines[i] = next;
                                                   nextV.headlines = nextHeadlines;
                                                   nextVariants[loc] = nextV;
                                                   nextAcm.variants = nextVariants;
                                                   nextObj.ad_copy_matrix = nextAcm;
                                                   return nextObj;
                                                 });
                                               }}
                                             >
                                               {h}
                                             </div>
                                           </div>
                                         ))}
                                       </div>
                                       <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest pt-2">Primary Texts</div>
                                       <div className="space-y-1">
                                         {primary.slice(0, 5).map((p: string, i: number) => (
                                           <div key={i} className="bg-surface-container-high border border-outline-variant/25 rounded-lg px-2.5 py-2 text-[11px] text-on-surface-variant leading-relaxed">
                                             {p}
                                           </div>
                                         ))}
                                       </div>
                                       <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest pt-2">Hashtags</div>
                                       <div className="bg-surface-container-high border border-outline-variant/25 rounded-lg px-2.5 py-2 text-[10px] font-mono text-on-surface-variant break-words">
                                         {hashtags.slice(0, 20).join(' ')}
                                       </div>
                                     </div>
                                   </motion.div>
                                 );
                               });
                             })()}
                           </div>
                         ) : (
                           <div className="flex flex-col gap-3 pt-2">
                             {synthesisResult.script.map((line: any, idx: number) => (
                                <motion.div variants={{ hidden: { opacity: 0, x: 10 }, show: { opacity: 1, x: 0 } }} key={idx} className="bg-surface-container-lowest border border-outline-variant/40 shadow-sm rounded-xl p-3 hover:border-primary/30 transition-colors shrink-0">
                                  <div className="text-[10px] font-bold text-primary mb-1">[{line.time}]</div>
                                  <div className="text-[12px] text-on-surface leading-relaxed mb-3">{line.visual}</div>
                                  <div className="text-[11px] font-medium text-on-surface-variant bg-surface-container p-2 rounded-lg border border-outline-variant/20 flex gap-2">
                                    <span className="text-secondary font-bold">V/O:</span> 
                                    {line.audio_content}
                                  </div>
                                </motion.div>
                             ))}
                           </div>
                         )}
                         
                        <motion.button variants={{ hidden: { opacity: 0 }, show: { opacity: 1 } }} onClick={() => setSynthesisResult(null)} className="mt-4 w-full py-3 rounded-xl border border-outline-variant/40 text-xs font-bold text-on-surface-variant uppercase tracking-widest hover:bg-surface-container transition-colors">
                           Reset Parameters
                         </motion.button>
                      </motion.div>
                    )}
                 </AnimatePresence>
              </div>
           </div>
        </div>
      </div>
    </div>
  );
};
