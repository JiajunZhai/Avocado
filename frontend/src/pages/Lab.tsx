import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Beaker, Layers, Network, Database, Target, Lock, Play, Activity, Globe, MonitorPlay, BrainCircuit, RefreshCw, Eye, Info } from 'lucide-react';
import axios from 'axios';
import { API_BASE } from '../config/apiBase';
import { useProjectContext } from '../context/ProjectContext';
import { useShellActivity } from '../context/ShellActivityContext';
import { ProSelect } from '../components/ProSelect';
import { useTranslation } from 'react-i18next';

export const Lab: React.FC = () => {
  const { t } = useTranslation();
  const { currentProject } = useProjectContext();
  const { setGeneratorShell } = useShellActivity();

  // State
  const [metadata, setMetadata] = useState<any>({ regions: [], platforms: [], angles: [] });
  const [regionId, setRegionId] = useState<string>('');
  const [platformId, setPlatformId] = useState<string>('');
  const [angleId, setAngleId] = useState<string>('');
  const [outputMode, setOutputMode] = useState<'cn' | 'en'>(() => {
    const saved = localStorage.getItem('sop_output_mode');
    return saved === 'en' ? 'en' : 'cn';
  });
  
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [synthesisResult, setSynthesisResult] = useState<any>(null);
  const [isSyncingFeed, setIsSyncingFeed] = useState(false);

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
      const payload = {
        project_id: currentProject.id,
        region_id: regionId,
        platform_id: platformId,
        angle_id: angleId,
        engine: "cloud",
        output_mode: outputMode
      };
      const response = await axios.post(`${API_BASE}/api/generate`, payload);
      setSynthesisResult(response.data);
    } catch (e) {
      console.error(e);
      alert("Synthesis Failed via API");
    } finally {
      setIsSynthesizing(false);
    }
  };

  const toOptions = (items: any[]) => items.map(i => ({ value: i.id, label: i.name || i.id }));
  const outputModeOptions = useMemo(
    () => [
      { value: 'cn', label: t('lab.output_mode.cn') },
      { value: 'en', label: t('lab.output_mode.en') },
    ],
    [t]
  );

  return (
    <div className="w-full h-full flex flex-col bg-background text-on-background relative overflow-hidden page-pad">
      {/* Sleek Light/Ambient Gradients */}
      <div className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] bg-primary/5 rounded-full blur-[100px] pointer-events-none -z-10" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] bg-secondary/5 rounded-full blur-[100px] pointer-events-none -z-10" />

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
        <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-6 relative overflow-hidden">
           
           {/* Column 1: Source */}
           <div className="w-full lg:w-[280px] xl:w-[320px] shrink-0 flex flex-col min-h-0 lg:border-r border-outline-variant/30 lg:pr-6">
             <div className="flex items-center justify-between pb-3 shrink-0">
               <span className="text-[11px] uppercase font-bold tracking-[0.1em] text-on-surface-variant flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5" /> {t('lab.slot_a.header')}
               </span>
             </div>
             
             <div className="flex-1 min-h-0 flex flex-col gap-4 overflow-y-auto custom-scrollbar pb-4 pr-1">
               {/* Project Card */}
               <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="bg-surface-container-low border border-outline-variant/40 rounded-2xl p-5 relative overflow-hidden shadow-sm">
                 <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl -z-10" />
                 <div className="text-[10px] uppercase font-bold tracking-widest text-on-surface-variant flex items-center gap-1.5 mb-3">
                    <Lock className="w-3 h-3 text-secondary"/> {t('lab.slot_a.title')}
                 </div>
                 <div className="text-lg font-black text-on-surface leading-tight break-words mb-3">
                    {currentProject?.name || 'No Project Selected'}
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
                  <div className="flex-1 bg-surface-container-lowest border border-outline-variant/40 rounded-2xl p-4 text-[12px] text-on-surface/80 overflow-y-auto custom-scrollbar shadow-inner leading-relaxed">
                     {currentProject?.game_info ? (
                        <div className="space-y-4">
                           <div>
                              <div className="font-bold text-primary text-[10px] uppercase tracking-wider mb-1">Core Gameplay</div>
                              {currentProject.game_info.core_gameplay}
                           </div>
                           <div>
                              <div className="font-bold text-secondary text-[10px] uppercase tracking-wider mb-1">USP Extracted</div>
                              {currentProject.game_info.core_usp}
                           </div>
                        </div>
                     ) : (
                        <div className="flex flex-col items-center justify-center h-full text-on-surface-variant opacity-50 space-y-2">
                           <Info className="w-6 h-6" />
                           <span>Select project from sidebar</span>
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

             <div className="flex-1 overflow-visible flex flex-col items-center w-full max-w-[380px] mx-auto gap-3 relative pb-2 px-1">
                 {/* Decorative connecting line */}
                 <div className="absolute left-6 top-6 bottom-16 w-[2px] bg-outline-variant/30 z-0 hidden sm:block" />

                 <div className="w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-2 shadow-sm hover:shadow-md transition-shadow relative flex flex-col">
                    <div className="flex items-center gap-2 mb-1.5">
                       <div className="w-5 h-5 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
                          <Globe className="w-3 h-3 text-primary" />
                       </div>
                       <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.slot_b.label')}</div>
                    </div>
                    {regionId && <ProSelect value={regionId} onChange={setRegionId} options={toOptions(metadata.regions)} />}
                 </div>

                 <div className="w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-2 shadow-sm hover:shadow-md transition-shadow relative flex flex-col">
                    <div className="flex items-center gap-2 mb-1.5">
                       <div className="w-5 h-5 rounded-md bg-secondary/10 flex items-center justify-center shrink-0">
                          <MonitorPlay className="w-3 h-3 text-secondary" />
                       </div>
                       <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.slot_c.label')}</div>
                    </div>
                    {platformId && <ProSelect value={platformId} onChange={setPlatformId} options={toOptions(metadata.platforms)} />}
                 </div>

                 <div className="w-full bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-2 shadow-sm hover:shadow-md transition-shadow relative flex flex-col">
                    <div className="flex items-center gap-2 mb-1.5">
                       <div className="w-5 h-5 rounded-md bg-emerald-50 flex items-center justify-center shrink-0">
                          <Target className="w-3 h-3 text-emerald-600" />
                       </div>
                       <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('lab.slot_d.label')}</div>
                    </div>
                    {angleId && <ProSelect value={angleId} onChange={setAngleId} options={toOptions(metadata.angles)} dropUp={true} />}
                 </div>

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

                 <div className="w-full shrink-0 mt-auto pt-4">
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

           {/* Column 3: Output Feed */}
           <div className="w-full lg:w-[320px] xl:w-[380px] shrink-0 flex flex-col min-h-0 lg:border-l border-outline-variant/30 lg:pl-6 pb-4">
              <div className="flex items-center justify-between pb-3 shrink-0">
                 <span className="text-[11px] uppercase font-bold tracking-[0.1em] text-on-surface-variant flex items-center gap-1.5">
                    {synthesisResult ? <Eye className="w-3.5 h-3.5 text-primary" /> : <Activity className={`w-3.5 h-3.5 ${isSyncingFeed ? 'text-primary animate-pulse' : ''}`} />}
                    {synthesisResult ? 'Compiled Blueprint' : 'Resonance Feed'}
                 </span>
                 <span className={`text-[9px] font-bold tracking-[0.1em] px-2 py-0.5 rounded border ${synthesisResult ? 'bg-primary/10 text-primary border-primary/20' : (isSyncingFeed ? 'bg-primary/5 text-primary border-primary/20 animate-pulse' : 'bg-surface-container-high text-on-surface-variant border-outline-variant/30')}`}>
                    {synthesisResult ? 'SECURE' : (isSyncingFeed ? 'SYNCING...' : 'STANDBY')}
                 </span>
              </div>

              <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar pr-1 bg-surface-container-lowest/50 rounded-2xl border border-outline-variant/20 p-2 relative">
                 <AnimatePresence mode="wait">
                    {!synthesisResult ? (
                      <motion.div key="feed" initial={{ opacity: 0 }} animate={{ opacity: isSyncingFeed ? 0.5 : 1, filter: isSyncingFeed ? 'blur(2px)' : 'blur(0px)' }} exit={{ opacity: 0 }} className="flex flex-col gap-3 p-1 h-fit">
                         {activeRegion && (
                           <motion.div layout initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}} className="bg-surface-container-lowest border border-outline-variant/40 shadow-sm rounded-xl p-4 shrink-0">
                              <div className="text-[10px] font-bold uppercase tracking-widest text-primary flex items-center justify-between mb-3 border-b border-outline-variant/20 pb-2">
                                <span className="flex items-center gap-1.5"><Globe className="w-3 h-3"/> Region Node</span>
                                <span className="opacity-70 truncate max-w-[120px] text-right">{activeRegion.id}</span>
                              </div>
                              <div className="text-[11px] text-on-surface/80 leading-relaxed space-y-2">
                                 <div><span className="font-semibold text-on-surface">Constraint:</span> {activeRegion.culture_notes[0]}</div>
                                 <div className="truncate"><span className="font-semibold text-on-surface">BGM:</span> {activeRegion.preferred_bgm}</div>
                              </div>
                           </motion.div>
                         )}
                         {activePlatform && (
                           <motion.div layout initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}} className="bg-surface-container-lowest border border-outline-variant/40 shadow-sm rounded-xl p-4 shrink-0">
                              <div className="text-[10px] font-bold uppercase tracking-widest text-secondary flex items-center justify-between mb-3 border-b border-outline-variant/20 pb-2">
                                <span className="flex items-center gap-1.5"><MonitorPlay className="w-3 h-3"/> Platform Node</span>
                                <span className="opacity-70 truncate max-w-[120px] text-right">{activePlatform.id}</span>
                              </div>
                              <div className="text-[11px] text-on-surface/80 leading-relaxed overflow-hidden">
                                 <div className="line-clamp-2"><span className="font-semibold text-on-surface">Rules:</span> {activePlatform.specs[0]}</div>
                              </div>
                           </motion.div>
                         )}
                         {activeAngle && (
                           <motion.div layout initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}} className="bg-surface-container-lowest border border-outline-variant/40 shadow-sm rounded-xl p-4 shrink-0">
                              <div className="text-[10px] font-bold uppercase tracking-widest text-emerald-600 flex items-center justify-between mb-3 border-b border-outline-variant/20 pb-2">
                                <span className="flex items-center gap-1.5"><Target className="w-3 h-3"/> Angle Node</span>
                                <span className="opacity-70 truncate max-w-[120px] text-right">{activeAngle.id}</span>
                              </div>
                              <div className="text-[11px] text-on-surface/80 leading-relaxed space-y-2">
                                 <div className="truncate"><span className="font-semibold text-on-surface">Emotion:</span> {activeAngle.core_emotion}</div>
                                 <div className="line-clamp-3"><span className="font-semibold text-on-surface">Logic:</span> {activeAngle.logic_steps[0]}</div>
                              </div>
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
                           <div className="text-[12px] text-on-surface/90 leading-relaxed font-medium">{synthesisResult.psychology_insight}</div>
                         </motion.div>

                         {synthesisResult.markdown_path && (
                           <div className="rounded-xl border border-outline-variant/35 bg-surface-container-high/80 px-3 py-2 text-[10px] font-mono text-on-surface-variant break-all">
                             {t('lab.markdown_saved', { path: synthesisResult.markdown_path })}
                           </div>
                         )}

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
