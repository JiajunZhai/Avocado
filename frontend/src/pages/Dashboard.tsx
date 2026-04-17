import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Folder, Activity, Trash2, FolderPlus, Settings2, PlaySquare, Eye, RefreshCw, GitCompare, Filter, Trophy, ThumbsDown, Minus, Search, X } from 'lucide-react';
import { motion } from 'framer-motion';
import { useProjectContext } from '../context/ProjectContext';
import { ProjectSetupModal } from '../components/ProjectSetupModal';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { API_BASE } from '../config/apiBase';
import { ResultDashboardView } from '../components/ResultDashboardView';
import { CompareViewModal } from '../components/CompareViewModal';

// Removed mock stats

const getGradient = (id: string) => {
   const colors = [
     'from-indigo-500 to-purple-500',
     'from-emerald-400 to-cyan-500',
     'from-amber-400 to-orange-500',
     'from-rose-400 to-red-500',
     'from-blue-500 to-indigo-600',
     'from-pink-500 to-rose-500'
   ];
   return colors[id.charCodeAt(0) % colors.length];
};

interface ProjectCardProps {
  proj: any;
  regions: string[];
  delay: number;
  handleEnterWorkspace: (proj: any) => void;
  handleEditWorkspace: (proj: any) => void;
  handleDeleteWorkspace: (id: string) => void;
}

const ProjectCard: React.FC<ProjectCardProps> = ({ proj, regions, delay, handleEnterWorkspace, handleEditWorkspace, handleDeleteWorkspace }) => {
  const { t } = useTranslation();
  const [confirming, setConfirming] = React.useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      className="relative flex flex-col p-5 bg-gradient-to-b from-surface-container-high/80 to-surface-container-low/40 border-[0.5px] border-outline-variant/50 rounded-[1.25rem] hover:-translate-y-1 hover:shadow-elev-2 hover:border-primary/40 transition-all duration-300 group overflow-hidden backdrop-blur-md"
    >
      {/* Decorative Glow */}
      <div className="absolute -top-10 -right-10 w-40 h-40 bg-gradient-to-br from-primary/10 to-secondary/10 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-0 pointer-events-none" />
      
      {/* Content Header */}
      <div className="flex items-start gap-4 mb-3 relative z-10">
         <div className={`w-12 h-12 shrink-0 rounded-2xl bg-gradient-to-br ${getGradient(proj.id)} flex items-center justify-center text-white font-black text-xl shadow-[inset_0px_1px_4px_rgba(255,255,255,0.4)] ring-1 ring-black/5`}>
            {proj.name.charAt(0).toUpperCase()}
         </div>
         <div className="min-w-0 flex-1 pt-0.5 max-w-[80%]">
            <h2 className="text-[15px] font-black text-on-surface truncate tracking-tight mb-1 aspect-auto">
               {proj.name}
            </h2>
            <p className="text-[11px] font-medium text-on-surface-variant opacity-80 line-clamp-2 leading-relaxed">
               {proj.game_info?.core_usp || proj.game_info?.core_gameplay || t('dashboard.card_missing_base')}
            </p>
         </div>
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-4 mb-5 relative z-10">
         <div className="bg-surface-container/50 rounded-lg px-2.5 py-1.5 border-[0.5px] border-outline-variant/30 flex items-center gap-2">
             <div className="text-[9px] uppercase tracking-widest text-on-surface-variant font-bold">{t('lab.slot_a.scripts')}</div>
             <div className="text-xs font-black font-mono text-on-surface">{((proj.history_log && proj.history_log.length) || 0).toString().padStart(3, '0')}</div>
         </div>
         {regions.length > 0 && (
            <div className="flex gap-1 overflow-hidden">
               {regions.slice(0, 2).map((r: string) => (
                  <span key={r} className="text-[9px] font-semibold bg-surface-container-high text-on-surface-variant px-1.5 py-0.5 rounded border border-outline-variant/30 font-mono tracking-tight">
                    {r.toUpperCase()}
                  </span>
               ))}
               {regions.length > 2 && <span className="text-[9px] text-on-surface-variant">+{regions.length - 2}</span>}
            </div>
         )}
      </div>

      {/* Action Deck */}
      <div className="mt-auto pt-4 border-t border-outline-variant/20 flex gap-2 relative z-10">
         <button 
           onClick={() => handleEnterWorkspace(proj)}
           className="flex-1 flex items-center justify-center gap-1.5 bg-primary/10 hover:bg-primary/20 text-primary font-bold text-xs py-2 rounded-xl transition-colors"
         >
           <PlaySquare className="w-3.5 h-3.5" /> {t('dashboard.btn_launch_lab')}
         </button>
         
         <button 
           onClick={() => handleEditWorkspace(proj)}
           className="px-3 flex items-center justify-center bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface rounded-xl transition-colors border-[0.5px] border-outline-variant/30"
           title={t('dashboard.btn_edit')}
         >
           <Settings2 className="w-4 h-4" />
         </button>

         {confirming ? (
             <div className="absolute right-0 bottom-0 top-4 w-full bg-red-500/10 border border-red-500/30 rounded-xl backdrop-blur-xl shadow-lg flex items-center justify-end px-2 gap-2 z-20">
                <button 
                  onClick={() => setConfirming(false)} 
                  className="px-3 py-1.5 bg-surface-container text-on-surface-variant hover:text-on-surface font-bold text-[10px] rounded-lg"
                >
                  CANCEL
                </button>
                <button 
                  onClick={() => { handleDeleteWorkspace(proj.id); setConfirming(false); }} 
                  className="px-3 py-1.5 bg-red-500 text-white font-bold text-[10px] rounded-lg hover:bg-red-400"
                >
                  PURGE
                </button>
             </div>
          ) : (
             <button 
              onClick={() => setConfirming(true)}
              className="px-3 flex items-center justify-center bg-surface-container hover:bg-red-500/10 text-on-surface-variant hover:text-red-500 rounded-xl transition-colors border-[0.5px] border-outline-variant/30"
              title={t('dashboard.btn_delete')}
             >
               <Trash2 className="w-4 h-4" />
             </button>
          )}
      </div>
    </motion.div>
  );
};

export const Dashboard: React.FC = () => {
  const { t } = useTranslation();
  const { projects = [], currentProject, setCurrentProject, deleteProject, refreshProjects } = useProjectContext();
  const navigate = useNavigate();
  const [showSetupModal, setShowSetupModal] = React.useState(false);
  const [editingProject, setEditingProject] = React.useState<any>(null);
  const [selectedProjectId, setSelectedProjectId] = React.useState<string>('');
  const [activeRecordId, setActiveRecordId] = React.useState<string>('');
  const [compareIds, setCompareIds] = React.useState<string[]>([]);
  const [compareOpen, setCompareOpen] = React.useState(false);
  const [isRefreshingCopy, setIsRefreshingCopy] = React.useState(false);
  const [decisionBusyId, setDecisionBusyId] = React.useState<string>('');

  // Phase 24 / C2 — History search & filters (persisted to localStorage).
  type HistoryFilterState = {
    q: string;
    region: string;
    platform: string;
    angle: string;
    decision: string;
    dateFrom: string;
    dateTo: string;
    kind: string;
  };
  const FILTER_STORAGE_KEY = 'dashboard.history_filter.v1';
  const loadFilters = (): HistoryFilterState => {
    try {
      const raw = localStorage.getItem(FILTER_STORAGE_KEY);
      if (!raw) throw new Error('empty');
      const parsed = JSON.parse(raw);
      return {
        q: String(parsed.q || ''),
        region: String(parsed.region || ''),
        platform: String(parsed.platform || ''),
        angle: String(parsed.angle || ''),
        decision: String(parsed.decision || ''),
        dateFrom: String(parsed.dateFrom || ''),
        dateTo: String(parsed.dateTo || ''),
        kind: String(parsed.kind || ''),
      };
    } catch {
      return { q: '', region: '', platform: '', angle: '', decision: '', dateFrom: '', dateTo: '', kind: '' };
    }
  };
  const [historyFilter, setHistoryFilter] = React.useState<HistoryFilterState>(loadFilters);
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  React.useEffect(() => {
    try {
      localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(historyFilter));
    } catch {
      // localStorage may be unavailable (private mode); ignore.
    }
  }, [historyFilter]);

  const resetHistoryFilter = () =>
    setHistoryFilter({ q: '', region: '', platform: '', angle: '', decision: '', dateFrom: '', dateTo: '', kind: '' });

  const activeFilterCount = React.useMemo(() => {
    return ['q', 'region', 'platform', 'angle', 'decision', 'dateFrom', 'dateTo', 'kind'].reduce(
      (n, k) => n + (historyFilter[k as keyof HistoryFilterState] ? 1 : 0),
      0,
    );
  }, [historyFilter]);

  const setDecision = async (scriptId: string, decision: 'winner' | 'loser' | 'neutral' | 'pending') => {
    const pid = selectedProject?.id;
    if (!pid || !scriptId) return;
    setDecisionBusyId(scriptId);
    try {
      await axios.post(`${API_BASE}/api/history/decision`, {
        project_id: pid,
        script_id: scriptId,
        decision,
      });
      await refreshProjects();
    } catch (e) {
      // best-effort; keep UI responsive even if the request fails
      console.warn('decision update failed', e);
    } finally {
      setDecisionBusyId('');
    }
  };

  const handleEnterWorkspace = (proj: any) => {
     setCurrentProject(proj);
     navigate('/generator');
  };

  const handleEditWorkspace = (proj: any) => {
     setEditingProject(proj);
     setShowSetupModal(true);
  };

  // Note: We now focus on per-project records in the right panel.

  const projectOptions = React.useMemo(() => {
    return projects.map((p: any) => ({ id: String(p.id || ''), name: String(p.name || p.id || '') })).filter((x) => x.id);
  }, [projects]);

  React.useEffect(() => {
    const id = selectedProjectId || currentProject?.id || '';
    if (!selectedProjectId && id) setSelectedProjectId(id);
  }, [currentProject?.id, selectedProjectId]);

  const selectedProject = React.useMemo(() => {
    const pid = selectedProjectId || currentProject?.id || '';
    return projects.find((p: any) => String(p.id) === String(pid)) || null;
  }, [projects, selectedProjectId, currentProject?.id]);

  const projectHistory = React.useMemo(() => {
    const h = selectedProject?.history_log;
    return Array.isArray(h) ? [...h].sort((a: any, b: any) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()) : [];
  }, [selectedProject]);

  const historyFilterOptions = React.useMemo(() => {
    const regions = new Set<string>();
    const platforms = new Set<string>();
    const angles = new Set<string>();
    const kinds = new Set<string>();
    projectHistory.forEach((log: any) => {
      const reg = log?.request?.region_id || log?.region_id || (Array.isArray(log?.request?.region_ids) ? log.request.region_ids.join('|') : '');
      if (reg) regions.add(String(reg));
      const plat = log?.request?.platform_id || log?.platform_id;
      if (plat) platforms.add(String(plat));
      const ang = log?.request?.angle_id || log?.angle_id;
      if (ang) angles.add(String(ang));
      const kind = log?.output_kind;
      if (kind) kinds.add(String(kind));
    });
    return {
      regions: [...regions].sort(),
      platforms: [...platforms].sort(),
      angles: [...angles].sort(),
      kinds: [...kinds].sort(),
    };
  }, [projectHistory]);

  const filteredHistory = React.useMemo(() => {
    const q = historyFilter.q.trim().toLowerCase();
    const toMs = (s: string) => {
      if (!s) return NaN;
      const d = new Date(s);
      return isNaN(d.getTime()) ? NaN : d.getTime();
    };
    const fromMs = toMs(historyFilter.dateFrom);
    const toMsVal = (() => {
      const v = toMs(historyFilter.dateTo);
      return isNaN(v) ? NaN : v + 24 * 3600 * 1000 - 1;
    })();
    return projectHistory.filter((log: any) => {
      if (historyFilter.region) {
        const reg =
          log?.request?.region_id ||
          log?.region_id ||
          (Array.isArray(log?.request?.region_ids) ? log.request.region_ids.join('|') : '');
        if (String(reg || '') !== historyFilter.region) return false;
      }
      if (historyFilter.platform) {
        const plat = log?.request?.platform_id || log?.platform_id;
        if (String(plat || '') !== historyFilter.platform) return false;
      }
      if (historyFilter.angle) {
        const ang = log?.request?.angle_id || log?.angle_id;
        if (String(ang || '') !== historyFilter.angle) return false;
      }
      if (historyFilter.kind) {
        if (String(log?.output_kind || '') !== historyFilter.kind) return false;
      }
      if (historyFilter.decision) {
        const dec = String(log?.decision || 'pending').toLowerCase();
        if (dec !== historyFilter.decision) return false;
      }
      const ts = new Date(log?.timestamp || 0).getTime();
      if (!isNaN(fromMs) && ts < fromMs) return false;
      if (!isNaN(toMsVal) && ts > toMsVal) return false;
      if (q) {
        const haystack = [
          log?.id,
          log?.output_kind,
          log?.lang,
          log?.output_mode,
          log?.request?.region_id,
          log?.request?.platform_id,
          log?.request?.angle_id,
          log?.parent_script_id,
          ...(Array.isArray(log?.compliance?.hits) ? log.compliance.hits.map((h: any) => h?.term) : []),
        ]
          .filter(Boolean)
          .map((x: any) => String(x).toLowerCase())
          .join(' ');
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [projectHistory, historyFilter]);

  const activeRecord = React.useMemo(() => {
    if (!activeRecordId) return null;
    return projectHistory.find((x: any) => String(x?.id || '') === String(activeRecordId)) || null;
  }, [projectHistory, activeRecordId]);

  const compareA = React.useMemo(() => (compareIds[0] ? projectHistory.find((x: any) => String(x?.id || '') === String(compareIds[0])) || null : null), [projectHistory, compareIds]);
  const compareB = React.useMemo(() => (compareIds[1] ? projectHistory.find((x: any) => String(x?.id || '') === String(compareIds[1])) || null : null), [projectHistory, compareIds]);

  const toggleCompare = (id: string) => {
    setCompareIds((prev) => {
      const has = prev.includes(id);
      if (has) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  };

  const runRefreshCopy = async (baseScriptId: string) => {
    const pid = selectedProject?.id;
    if (!pid || !baseScriptId) return;
    setIsRefreshingCopy(true);
    try {
      await axios.post(`${API_BASE}/api/quick-copy/refresh`, {
        project_id: pid,
        base_script_id: baseScriptId,
        engine: 'cloud',
        output_mode: 'cn',
        quantity: 20,
        tones: [],
        locales: ['en'],
      });
      await refreshProjects();
    } finally {
      setIsRefreshingCopy(false);
    }
  };

  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    if (isNaN(diff)) return '';
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return t('dashboard.history.time.just_now');
    if (minutes < 60) return t('dashboard.history.time.minutes_ago', { minutes });
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return t('dashboard.history.time.hours_ago', { hours });
    return t('dashboard.history.time.days_ago', { days: Math.floor(hours / 24) });
  };

  return (
    <div className="w-full h-full flex flex-col bg-background text-on-background page-pad overflow-hidden">
      <ResultDashboardView open={!!activeRecord} onClose={() => setActiveRecordId('')} result={activeRecord} />
      <CompareViewModal open={compareOpen && compareIds.length === 2} onClose={() => setCompareOpen(false)} a={compareA} b={compareB} />
      <div className="max-w-[1600px] w-full mx-auto h-full flex flex-col min-h-0 card-base p-4 md:p-6 lg:p-8">
        
        {/* Header - Fixed Height */}
        <motion.header
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="flex flex-col gap-3 shrink-0 border-b border-outline-variant/30 pb-6 relative"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-primary/5 to-transparent blur-3xl -z-10 rounded-full opacity-50" />
          <div className="flex items-center justify-between">
              <div className="flex flex-col">
               <div className="flex items-center gap-2 text-primary font-bold text-[11px] uppercase tracking-[0.25em] mb-1.5 opacity-90">
                 <Folder className="w-3.5 h-3.5" /> {t('dashboard.matrix_control')}
               </div>
               <h1 className="text-3xl lg:text-[2rem] font-black tracking-tight flex items-center gap-4 bg-clip-text text-transparent bg-gradient-to-br from-on-surface to-on-surface-variant leading-tight">
                 {t('dashboard.title')}
                 <span className="mt-1 text-[11px] font-bold bg-surface-container-high/80 text-on-surface-variant px-2.5 py-1 rounded-md border border-outline-variant/50 shadow-sm backdrop-blur-md uppercase tracking-wider">
                    {projects.length} {t('dashboard.pipelines')}
                 </span>
               </h1>
             </div>
             <p className="text-on-surface-variant/80 text-xs mt-2 max-w-sm font-medium leading-relaxed hidden md:block text-right">
                {t('dashboard.subtitle')}
             </p>
          </div>
        </motion.header>

        {/* Main Split: Left Gallery, Right Sidebar */}
        <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-6 mt-6 overflow-hidden">
           
           {/* LEFT GALLERY (Independent Scroll) */}
           <div className="flex-1 flex flex-col min-h-0 min-w-0">
            <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 pb-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 auto-rows-max content-start" style={{ scrollbarGutter: 'stable' }}>
                 {projects.length === 0 ? (
                   <button 
                     onClick={() => setShowSetupModal(true)} 
                     className="col-span-full py-20 flex flex-col items-center justify-center text-primary opacity-80 border-2 border-dashed border-primary/40 rounded-2xl hover:bg-primary/5 hover:opacity-100 transition-all cursor-pointer group"
                   >
                     <FolderPlus className="w-10 h-10 mb-4 opacity-70 group-hover:scale-110 group-hover:opacity-100 transition-all duration-300" />
                     <p className="text-[15px] font-black tracking-tight">{t('dashboard.empty.title')}</p>
                     <p className="text-xs font-semibold mt-1.5 opacity-70 break-words w-2/3">{t('dashboard.empty.description')}</p>
                   </button>
                 ) : (
                   projects.map((proj, i) => {
                     const regions = Array.from(new Set(proj.market_targets?.map(t => t.region) || []));
                     return (
                       <ProjectCard 
                         key={proj.id}
                         proj={proj}
                         regions={regions}
                         delay={0.02 * i}
                         handleEnterWorkspace={handleEnterWorkspace}
                         handleEditWorkspace={handleEditWorkspace}
                         handleDeleteWorkspace={deleteProject}
                       />
                     );
                   })
                 )}
              </div>
           </div>

           {/* RIGHT SIDEBAR FEED: Global Generation History */}
           <div className="w-full lg:w-72 xl:w-80 shrink-0 flex flex-col gap-4 overflow-y-auto custom-scrollbar pr-2 pb-4" style={{ scrollbarGutter: 'stable' }}>
              
              <div className="bg-surface-container border border-outline-variant/30 rounded-xl p-5 flex flex-col min-h-0 flex-1 shadow-sm">
                 <div className="flex items-center justify-between gap-3 mb-3 border-b border-outline-variant/20 pb-3">
                   <h3 className="text-[10px] font-bold text-on-surface uppercase tracking-widest flex items-center gap-2">
                     <Activity className="w-4 h-4 text-primary" /> {t('dashboard.history.title')}
                     <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full border border-outline-variant/40 text-on-surface-variant">
                       {filteredHistory.length}/{projectHistory.length}
                     </span>
                   </h3>
                   <div className="flex items-center gap-2">
                     <Filter className="w-4 h-4 text-on-surface-variant" />
                     <select
                       value={selectedProjectId}
                       onChange={(e) => {
                         setSelectedProjectId(e.target.value);
                         setActiveRecordId('');
                         setCompareIds([]);
                       }}
                       className="bg-surface-container-high border border-outline-variant/30 rounded-lg px-2 py-1 text-[10px] font-bold text-on-surface-variant"
                     >
                       {projectOptions.map((p) => (
                         <option key={p.id} value={p.id}>{p.name}</option>
                       ))}
                     </select>
                   </div>
                 </div>

                 <div className="mb-2">
                   <div className="flex items-center gap-2">
                     <div className="flex items-center gap-1.5 flex-1 rounded-lg border border-outline-variant/40 bg-surface-container-high px-2 py-1 text-[11px]">
                       <Search className="w-3.5 h-3.5 text-on-surface-variant" />
                       <input
                         type="text"
                         value={historyFilter.q}
                         onChange={(e) => setHistoryFilter((s) => ({ ...s, q: e.target.value }))}
                         placeholder={t('dashboard.history.search_placeholder') as string}
                         className="bg-transparent outline-none flex-1 min-w-0 text-on-surface placeholder:text-on-surface-variant"
                       />
                       {historyFilter.q && (
                         <button
                           type="button"
                           onClick={() => setHistoryFilter((s) => ({ ...s, q: '' }))}
                           className="text-on-surface-variant hover:text-on-surface"
                         >
                           <X className="w-3 h-3" />
                         </button>
                       )}
                     </div>
                     <button
                       type="button"
                       onClick={() => setFiltersOpen((v) => !v)}
                       className={`text-[10px] font-bold rounded-lg border px-2 py-1 flex items-center gap-1.5 transition-colors ${
                         activeFilterCount > 0
                           ? 'border-primary/50 text-primary bg-primary/10'
                           : 'border-outline-variant/40 text-on-surface-variant hover:text-on-surface'
                       }`}
                       title={t('dashboard.history.toggle_filters') as string}
                     >
                       <Filter className="w-3 h-3" /> {activeFilterCount > 0 ? activeFilterCount : t('dashboard.history.filters')}
                     </button>
                   </div>
                   {filtersOpen && (
                     <div className="mt-2 grid grid-cols-2 gap-2 rounded-lg border border-outline-variant/30 bg-surface-container-high/40 p-2">
                       <select
                         value={historyFilter.region}
                         onChange={(e) => setHistoryFilter((s) => ({ ...s, region: e.target.value }))}
                         className="bg-surface-container-high border border-outline-variant/30 rounded px-1.5 py-1 text-[10px] text-on-surface-variant"
                       >
                         <option value="">{t('dashboard.history.all_regions')}</option>
                         {historyFilterOptions.regions.map((r) => (
                           <option key={r} value={r}>{r}</option>
                         ))}
                       </select>
                       <select
                         value={historyFilter.platform}
                         onChange={(e) => setHistoryFilter((s) => ({ ...s, platform: e.target.value }))}
                         className="bg-surface-container-high border border-outline-variant/30 rounded px-1.5 py-1 text-[10px] text-on-surface-variant"
                       >
                         <option value="">{t('dashboard.history.all_platforms')}</option>
                         {historyFilterOptions.platforms.map((p) => (
                           <option key={p} value={p}>{p}</option>
                         ))}
                       </select>
                       <select
                         value={historyFilter.angle}
                         onChange={(e) => setHistoryFilter((s) => ({ ...s, angle: e.target.value }))}
                         className="bg-surface-container-high border border-outline-variant/30 rounded px-1.5 py-1 text-[10px] text-on-surface-variant"
                       >
                         <option value="">{t('dashboard.history.all_angles')}</option>
                         {historyFilterOptions.angles.map((a) => (
                           <option key={a} value={a}>{a}</option>
                         ))}
                       </select>
                       <select
                         value={historyFilter.kind}
                         onChange={(e) => setHistoryFilter((s) => ({ ...s, kind: e.target.value }))}
                         className="bg-surface-container-high border border-outline-variant/30 rounded px-1.5 py-1 text-[10px] text-on-surface-variant"
                       >
                         <option value="">{t('dashboard.history.all_kinds')}</option>
                         {historyFilterOptions.kinds.map((k) => (
                           <option key={k} value={k}>{k.toUpperCase()}</option>
                         ))}
                       </select>
                       <select
                         value={historyFilter.decision}
                         onChange={(e) => setHistoryFilter((s) => ({ ...s, decision: e.target.value }))}
                         className="bg-surface-container-high border border-outline-variant/30 rounded px-1.5 py-1 text-[10px] text-on-surface-variant col-span-2"
                       >
                         <option value="">{t('dashboard.history.all_decisions')}</option>
                         <option value="winner">{t('dashboard.history.decision_winner')}</option>
                         <option value="loser">{t('dashboard.history.decision_loser')}</option>
                         <option value="neutral">{t('dashboard.history.decision_neutral')}</option>
                         <option value="pending">{t('dashboard.history.decision_pending')}</option>
                       </select>
                       <input
                         type="date"
                         value={historyFilter.dateFrom}
                         onChange={(e) => setHistoryFilter((s) => ({ ...s, dateFrom: e.target.value }))}
                         className="bg-surface-container-high border border-outline-variant/30 rounded px-1.5 py-1 text-[10px] text-on-surface-variant"
                       />
                       <input
                         type="date"
                         value={historyFilter.dateTo}
                         onChange={(e) => setHistoryFilter((s) => ({ ...s, dateTo: e.target.value }))}
                         className="bg-surface-container-high border border-outline-variant/30 rounded px-1.5 py-1 text-[10px] text-on-surface-variant"
                       />
                       <button
                         type="button"
                         onClick={resetHistoryFilter}
                         disabled={activeFilterCount === 0}
                         className="col-span-2 text-[10px] font-bold text-on-surface-variant hover:text-on-surface flex items-center justify-center gap-1.5 py-1 rounded border border-outline-variant/30 disabled:opacity-50"
                       >
                         <X className="w-3 h-3" /> {t('dashboard.history.reset_filters')}
                       </button>
                     </div>
                   )}
                 </div>

                 <div className="space-y-0 overflow-y-auto custom-scrollbar pr-1 flex-1" style={{ scrollbarGutter: 'stable' }}>
                   {compareIds.length === 2 && (
                     <div className="sticky top-0 z-[2] pb-2">
                       <div className="rounded-xl border border-outline-variant/25 bg-surface-container-high/80 backdrop-blur px-3 py-2 flex items-center justify-between gap-2">
                         <div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest truncate">
                           {t('dashboard.history.compare_picked')} · {compareIds[0]} ↔ {compareIds[1]}
                         </div>
                         <button
                           type="button"
                           onClick={() => setCompareOpen(true)}
                           className="btn-director-secondary px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-widest flex items-center gap-2"
                         >
                           <GitCompare className="w-4 h-4" /> {t('dashboard.history.compare')}
                         </button>
                       </div>
                     </div>
                   )}
                   {projectHistory.length === 0 ? (
                      <div className="text-xs text-on-surface-variant opacity-70 text-center py-10 flex flex-col items-center gap-2">
                         <Folder className="w-8 h-8 opacity-30" />
                         {t('dashboard.history.empty')}
                      </div>
                   ) : filteredHistory.length === 0 ? (
                      <div className="text-xs text-on-surface-variant opacity-70 text-center py-10 flex flex-col items-center gap-2">
                         <Search className="w-8 h-8 opacity-30" />
                         {t('dashboard.history.filtered_empty')}
                         <button
                           type="button"
                           onClick={resetHistoryFilter}
                           className="text-[10px] font-bold text-primary hover:underline mt-1"
                         >
                           {t('dashboard.history.reset_filters')}
                         </button>
                      </div>
                   ) : (
                     filteredHistory.map((log: any, idx: number) => {
                       const id = String(log?.id || idx);
                       const kind = String(log?.output_kind || '').toUpperCase();
                       const rl = String(log?.compliance?.risk_level || 'ok').toUpperCase();
                       const lang = String(log?.lang || log?.output_mode || '').toUpperCase();
                       const parentId = String(log?.parent_script_id || '');
                       const draftStatus = String(log?.draft_status || '');
                       // Phase 25 / D3 — show which LLM provider + model produced
                       // this entry. Pre-D2 entries don't carry this metadata.
                       const providerId = String(log?.provider || '');
                       const modelId = String(log?.model || '');
                       const decision = String(log?.decision || 'pending').toLowerCase();
                       const isSelected = activeRecordId === id;
                       const isCompare = compareIds.includes(id);
                       const isBusy = decisionBusyId === id;
                       const decisionStyle = (() => {
                         if (decision === 'winner') return 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30';
                         if (decision === 'loser') return 'bg-red-500/10 text-red-600 border-red-500/30';
                         if (decision === 'neutral') return 'bg-zinc-500/10 text-zinc-600 border-zinc-500/30';
                         return '';
                       })();
                       return (
                         <div key={id} className={`rounded-xl border p-3 mb-2 transition-colors ${isSelected ? 'border-primary/40 bg-primary/5' : 'border-outline-variant/20 bg-surface-container-lowest/40 hover:bg-surface-container-low/40'}`}>
                           <div className="flex items-start justify-between gap-2">
                             <div className="min-w-0">
                               <div className="flex items-center gap-2 flex-wrap">
                                 <span className="text-[10px] font-black tracking-widest text-on-surface-variant uppercase">{kind || 'SOP'}</span>
                                 <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                                   rl === 'BLOCK' ? 'bg-red-50 text-red-700 border-red-200' : rl === 'WARN' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                 }`}>{rl}</span>
                                {lang && (
                                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant/80 border border-outline-variant/30">{lang}</span>
                                )}
                                {providerId && (
                                  <span
                                    className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/30 font-mono"
                                    title={modelId ? `${providerId} · ${modelId}` : providerId}
                                  >
                                    {providerId}{modelId ? ` · ${modelId}` : ''}
                                  </span>
                                )}
                                 {draftStatus === 'fallback' && (
                                   <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200" title={t('dashboard.history.draft_fallback') as string}>
                                     {t('dashboard.history.draft_fallback')}
                                   </span>
                                 )}
                                 {decision !== 'pending' && decisionStyle && (
                                   <span className={`text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded-full border ${decisionStyle}`}>
                                     {t(`dashboard.history.decision_${decision}`)}
                                   </span>
                                 )}
                               </div>
                               <div className="text-[11px] font-black text-on-surface truncate mt-1">{String(log?.id || '')}</div>
                               <div className="text-[10px] text-on-surface-variant font-mono mt-1">
                                 {String(log?.recipe?.region || '-')} · {String(log?.recipe?.platform || '-')} · {String(log?.recipe?.angle || '-')}
                               </div>
                               {parentId && (
                                 <div className="text-[9px] text-on-surface-variant/70 font-mono mt-1">
                                   {t('dashboard.history.parent_of')} <span className="text-primary/80">{parentId}</span>
                                 </div>
                               )}
                             </div>
                             <div className="text-[9px] font-mono text-on-surface-variant/70 shrink-0">{timeAgo(String(log?.timestamp || ''))}</div>
                           </div>
                           <div className="flex items-center justify-between gap-2 mt-3">
                             <div className="flex items-center gap-2">
                               <button
                                 type="button"
                                 onClick={() => setActiveRecordId(id)}
                                 className="text-[10px] font-bold text-on-surface-variant hover:text-on-surface flex items-center gap-1.5"
                                 title="Open"
                               >
                                 <Eye className="w-4 h-4" /> {t('dashboard.history.open')}
                               </button>
                               <button
                                 type="button"
                                 onClick={() => toggleCompare(id)}
                                 className={`text-[10px] font-bold flex items-center gap-1.5 ${isCompare ? 'text-primary' : 'text-on-surface-variant hover:text-on-surface'}`}
                                 title="Compare"
                               >
                                 <GitCompare className="w-4 h-4" /> {isCompare ? t('dashboard.history.picked') : t('dashboard.history.compare')}
                               </button>
                             </div>
                             {String(log?.output_kind || '') === 'sop' && (
                               <button
                                 type="button"
                                 onClick={() => runRefreshCopy(String(log?.id || ''))}
                                 disabled={isRefreshingCopy}
                                 className={`text-[10px] font-bold text-secondary flex items-center gap-1.5 ${isRefreshingCopy ? 'opacity-60 cursor-wait' : 'hover:text-secondary/80'}`}
                                 title="Refresh Copy"
                               >
                                 <RefreshCw className={`w-4 h-4 ${isRefreshingCopy ? 'animate-spin' : ''}`} /> {t('dashboard.history.refresh')}
                               </button>
                             )}
                           </div>
                           <div className="flex items-center gap-1 mt-2 pt-2 border-t border-outline-variant/15">
                             <span className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant/70 mr-1">{t('dashboard.history.decision_title')}:</span>
                             <button
                               type="button"
                               disabled={isBusy}
                               onClick={() => setDecision(id, decision === 'winner' ? 'pending' : 'winner')}
                               className={`text-[9px] font-bold flex items-center gap-1 px-1.5 py-0.5 rounded-md border transition-colors ${
                                 decision === 'winner'
                                   ? 'bg-emerald-500/15 text-emerald-600 border-emerald-500/40'
                                   : 'border-outline-variant/30 text-on-surface-variant hover:text-emerald-600 hover:border-emerald-500/40'
                               } ${isBusy ? 'opacity-60 cursor-wait' : ''}`}
                               title={t('dashboard.history.mark_winner') as string}
                             >
                               <Trophy className="w-3 h-3" /> {t('dashboard.history.decision_winner')}
                             </button>
                             <button
                               type="button"
                               disabled={isBusy}
                               onClick={() => setDecision(id, decision === 'loser' ? 'pending' : 'loser')}
                               className={`text-[9px] font-bold flex items-center gap-1 px-1.5 py-0.5 rounded-md border transition-colors ${
                                 decision === 'loser'
                                   ? 'bg-red-500/15 text-red-600 border-red-500/40'
                                   : 'border-outline-variant/30 text-on-surface-variant hover:text-red-600 hover:border-red-500/40'
                               } ${isBusy ? 'opacity-60 cursor-wait' : ''}`}
                               title={t('dashboard.history.mark_loser') as string}
                             >
                               <ThumbsDown className="w-3 h-3" /> {t('dashboard.history.decision_loser')}
                             </button>
                             <button
                               type="button"
                               disabled={isBusy}
                               onClick={() => setDecision(id, decision === 'neutral' ? 'pending' : 'neutral')}
                               className={`text-[9px] font-bold flex items-center gap-1 px-1.5 py-0.5 rounded-md border transition-colors ${
                                 decision === 'neutral'
                                   ? 'bg-zinc-500/15 text-zinc-600 border-zinc-500/40'
                                   : 'border-outline-variant/30 text-on-surface-variant hover:text-zinc-600 hover:border-zinc-500/40'
                               } ${isBusy ? 'opacity-60 cursor-wait' : ''}`}
                               title={t('dashboard.history.mark_neutral') as string}
                             >
                               <Minus className="w-3 h-3" /> {t('dashboard.history.decision_neutral')}
                             </button>
                           </div>
                         </div>
                       );
                     })
                   )}
                 </div>
              </div>

           </div>
           
        </div>
      </div>
      
      <ProjectSetupModal 
         isOpen={showSetupModal}
         onClose={() => { setShowSetupModal(false); setEditingProject(null); }}
         editTarget={editingProject}
      />
    </div>
  );
};
