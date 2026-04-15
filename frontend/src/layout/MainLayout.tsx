import React, { useCallback, useRef, useState } from 'react';
import { Clapperboard, LayoutDashboard, Sparkles, Settings, LifeBuoy, Compass, ChevronsUpDown, ChevronRight, Check, Activity } from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import { useReducedMotion } from 'framer-motion';
import axios from 'axios';
import { API_BASE } from '../config/apiBase';
import { useShellActivity } from '../context/ShellActivityContext';
import { useProjectContext } from '../context/ProjectContext';
import { ThemeAppearanceControl } from '../components/ThemeAppearanceControl';
import { LiveMarketDrawer } from '../components/LiveMarketDrawer';
import { ProjectSetupModal } from '../components/ProjectSetupModal';
import { ParameterManagerModal } from '../components/ParameterManagerModal';
import { useTranslation } from 'react-i18next';
import systemLogo from '../assets/logo.png';

interface MainLayoutProps {
  children: React.ReactNode;
}

interface UsageSummary {
  reset_utc_date: string;
  tokens_budget_today: number;
  tokens_used_today: number;
  tokens_used_today_estimate: number;
  tokens_from_provider_today: number;
  tokens_from_estimate_today: number;
  tokens_remaining_today_estimate: number;
  script_generations_today: number;
  avg_tokens_per_script_today: number;
  avg_provider_tokens_per_script_today: number;
  avg_estimate_tokens_per_script_today: number;
  last_script_tokens: number;
  script_generations_provider_today: number;
  script_generations_estimate_today: number;
  billing_quality: 'provider' | 'mixed' | 'estimate_only';
  oracle_retrievals_today: number;
  oracle_ingests_today: number;
  token_note: string;
  oracle_note: string;
}

const USAGE_CACHE_MS = 45_000;

export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const reduceMotion = useReducedMotion();
  const { generator, oracle } = useShellActivity();

  const [usageSummary, setUsageSummary] = useState<UsageSummary | null>(null);
  const usageSummaryRef = useRef<UsageSummary | null>(null);
  usageSummaryRef.current = usageSummary;
  const [usageError, setUsageError] = useState(false);
  const [usageLoading, setUsageLoading] = useState(false);
  const usageFetchedAt = useRef(0);

  const [quotaHover, setQuotaHover] = useState(false);
  const [quotaFocusWithin, setQuotaFocusWithin] = useState(false);
  
  const [isMarketDrawerOpen, setMarketDrawerOpen] = useState(false);
  const { projects, currentProject, setCurrentProject, isLoading: projLoading } = useProjectContext();
  const [showProjectDropdown, setShowProjectDropdown] = useState(false);
  const [showSetupModal, setShowSetupModal] = useState(false);
  const [showParameterManager, setShowParameterManager] = useState(false);

  const handleOpenSetup = () => {
     setShowProjectDropdown(false);
     setShowSetupModal(true);
  };

  const showQuotaCard = quotaHover || quotaFocusWithin;

  const loadUsageSummary = useCallback(async () => {
    const now = Date.now();
    const hasData = usageSummaryRef.current !== null;
    if (hasData && now - usageFetchedAt.current < USAGE_CACHE_MS) {
      return;
    }
    setUsageLoading(true);
    setUsageError(false);
    try {
      const { data } = await axios.get<UsageSummary>(`${API_BASE}/api/usage/summary`);
      setUsageSummary(data);
      usageFetchedAt.current = Date.now();
    } catch {
      setUsageError(true);
    } finally {
      setUsageLoading(false);
    }
  }, []);

  const openQuotaContext = useCallback(() => {
    void loadUsageSummary();
  }, [loadUsageSummary]);

  const navItems = [
    { to: '/dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
    { to: '/generator', label: t('nav.lab'), icon: Sparkles },
    { to: '/oracle', label: t('nav.oracle'), icon: Compass }
  ];

  return (
    <div className="h-screen flex bg-background text-on-background">
      <aside className="hidden lg:flex h-screen w-64 fixed left-0 top-0 border-r border-outline-variant/20 bg-surface-container-low flex-col py-6 z-50 overflow-visible layout-sidebar-edge">
        <div className="px-6 mb-8 mt-1 group cursor-pointer flex items-center gap-3" onClick={() => window.location.href = '/'}>
          <div className="relative flex items-center justify-center shrink-0">
            <div className="absolute inset-0 bg-primary/20 rounded-full blur-md opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <img src={systemLogo} alt="System Logo" className="relative h-[34px] w-auto object-contain transition-transform duration-300 group-hover:scale-105 drop-shadow-sm" />
          </div>
          <div className="flex flex-col justify-center overflow-hidden">
            <span className="text-[14px] font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-br from-on-surface to-on-surface-variant leading-tight truncate">
              AdCreative AI
            </span>
            <span className="text-[8.5px] font-bold tracking-[0.2em] text-primary/80 uppercase mt-0.5 truncate">
              SOP Engine
            </span>
          </div>
        </div>

        <div className="px-6 mb-8 relative z-[60]">
          <div className="flex items-center justify-between mb-2.5">
            <h2 className="text-[10px] font-black tracking-widest uppercase text-on-surface-variant/80 flex items-center gap-1.5">
              {t('nav.workspace_label')}
            </h2>
            <div
              className="relative flex items-center"
              onMouseEnter={() => {
                setQuotaHover(true);
                openQuotaContext();
              }}
              onMouseLeave={() => setQuotaHover(false)}
              onFocusCapture={() => {
                setQuotaFocusWithin(true);
                openQuotaContext();
              }}
              onBlurCapture={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
                  setQuotaFocusWithin(false);
                }
              }}
            >
              <button
                type="button"
                onClick={() => {
                  openQuotaContext();
                }}
                className="text-[9px] font-bold uppercase tracking-widest text-secondary hover:text-secondary-fixed-dim transition-colors px-1"
                aria-expanded={showQuotaCard}
                aria-controls="sidebar-quota-panel"
                id="sidebar-pro-plan-trigger"
              >
                {t('nav.quota')}
              </button>
            </div>
          </div>

          <div className="relative">
            <button
              onClick={() => {
                if (!projLoading && projects.length === 0) {
                  handleOpenSetup();
                } else {
                  setShowProjectDropdown(!showProjectDropdown);
                }
              }}
              className="w-full flex items-center justify-between p-2.5 rounded-xl bg-gradient-to-b from-surface-container/50 to-surface-container-high/50 hover:from-surface-container hover:to-surface-container-high border border-outline-variant/30 hover:border-primary/30 shadow-sm hover:shadow-elev-1 transition-all duration-300 group"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-7 h-7 rounded-lg bg-primary/10 border border-primary/20 text-primary flex items-center justify-center shrink-0 group-hover:bg-primary group-hover:text-on-primary group-hover:border-primary transition-all duration-300 shadow-sm">
                  <Clapperboard className="w-4 h-4" />
                </div>
                <span className="text-[13px] font-bold text-on-surface truncate group-hover:text-primary transition-colors pr-2 title={projLoading ? t('nav.loading') : currentProject ? currentProject.name : t('nav.create_workspace')}">
                  {projLoading ? t('nav.loading') : currentProject ? currentProject.name : t('nav.create_profile')}
                </span>
              </div>
              <ChevronsUpDown className="w-4 h-4 text-on-surface-variant shrink-0 group-hover:text-primary/70 transition-colors" />
            </button>

            {showProjectDropdown && (
              <div className="absolute top-[3.25rem] left-0 w-full bg-surface-container-high border border-outline-variant/30 shadow-elev-2 rounded-xl p-1 z-[70] origin-top animate-in fade-in duration-150">
                {!projLoading && projects.length > 0 ? projects.map(proj => (
                  <button
                    key={proj.id}
                    onClick={() => {
                      setCurrentProject(proj);
                      setShowProjectDropdown(false);
                    }}
                    className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-surface-container-low transition-colors text-left"
                  >
                    <div className="w-4 h-4 flex items-center justify-center shrink-0">
                      {currentProject && proj.id === currentProject.id && <Check className="w-3.5 h-3.5 text-primary" />}
                    </div>
                    <span className={`text-xs truncate ${currentProject && proj.id === currentProject.id ? 'font-bold text-on-surface' : 'font-medium text-on-surface-variant'}`}>{proj.name}</span>
                  </button>
                )) : (
                  <div className="p-2 text-xs text-on-surface-variant text-center border border-dashed border-outline-variant/30 rounded-lg hidden"></div>
                )}
                
                <div className="border-t border-outline-variant/20 my-1 mx-1"></div>
                <button 
                   onClick={handleOpenSetup}
                   className="w-full text-left p-2 text-xs font-bold text-primary hover:bg-primary/10 rounded-lg transition-colors flex items-center gap-1.5"
                >
                   {t('nav.create_profile')}
                </button>
              </div>
            )}
          </div>

          <div
            id="sidebar-quota-panel"
            role="region"
            aria-labelledby="sidebar-pro-plan-trigger"
            aria-hidden={!showQuotaCard}
            className={`absolute left-full top-0 ml-3 w-[15.5rem] z-[60] rounded-ui border border-outline-variant/35 bg-surface-container-high/95 backdrop-blur-xl shadow-elev-1 p-3 text-left transition-director-transform pointer-events-auto ${
              showQuotaCard ? 'opacity-100 visible translate-x-0' : 'opacity-0 invisible translate-x-1 pointer-events-none'
            }`}
            onMouseEnter={() => {
              setQuotaHover(true);
            }}
            onMouseLeave={() => setQuotaHover(false)}
            onFocusCapture={() => {
              setQuotaFocusWithin(true);
            }}
            onBlurCapture={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
                setQuotaFocusWithin(false);
              }
            }}
          >
            <p className="text-[10px] font-bold uppercase tracking-widest text-secondary mb-2">{t('quota.title')}</p>
            {usageLoading && !usageSummary ? (
              <p className="text-xs text-on-surface-variant">{t('quota.syncing')}</p>
            ) : usageError ? (
              <p className="text-xs text-on-surface-variant">{t('quota.error')} ({API_BASE}).</p>
            ) : usageSummary ? (
              <dl className="space-y-2 text-xs text-on-surface">
                <div className="flex justify-between gap-2">
                  <dt className="text-on-surface-variant shrink-0">{t('quota.tokens_remaining')}</dt>
                  <dd className="font-mono tabular-nums text-right">
                    {usageSummary.tokens_remaining_today_estimate.toLocaleString()}
                    <span className="text-on-surface-variant font-sans text-[10px] ml-1">/ {usageSummary.tokens_budget_today.toLocaleString()}</span>
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-on-surface-variant shrink-0">{t('quota.tokens_used')}</dt>
                  <dd className="font-mono tabular-nums text-right">
                    {usageSummary.tokens_used_today.toLocaleString()} tok
                  </dd>
                </div>
                {(usageSummary.billing_quality === 'provider' || usageSummary.billing_quality === 'mixed') && (
                  <div className="flex justify-between gap-2 text-[10px] text-on-surface-variant">
                    <span>{t('quota.provider_billed')}</span>
                    <span className="font-mono tabular-nums">
                      {usageSummary.tokens_from_provider_today.toLocaleString()} tok
                    </span>
                  </div>
                )}
                {usageSummary.billing_quality !== 'provider' && usageSummary.tokens_from_estimate_today > 0 && (
                  <div className="flex justify-between gap-2 text-[10px] text-on-surface-variant">
                    <span>{t('quota.estimate_padding')}</span>
                    <span className="font-mono tabular-nums">
                      {usageSummary.tokens_from_estimate_today.toLocaleString()} tok
                    </span>
                  </div>
                )}
                <div className="pt-1 border-t border-outline-variant/20 mt-1 space-y-1">
                  <div className="flex justify-between gap-2">
                    <dt className="text-on-surface-variant shrink-0">{t('quota.last_script')}</dt>
                    <dd className="font-mono tabular-nums text-right">
                      {usageSummary.last_script_tokens.toLocaleString()} tok
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-on-surface-variant shrink-0">{t('quota.avg_script')}</dt>
                    <dd className="font-mono tabular-nums text-right">
                      {usageSummary.avg_tokens_per_script_today.toLocaleString()} tok
                    </dd>
                  </div>
                  {usageSummary.script_generations_today > 0 && (
                    <div className="flex justify-between gap-2 text-[10px] text-on-surface-variant">
                      <span>{t('quota.sample_count')}</span>
                      <span className="font-mono tabular-nums">
                        {usageSummary.script_generations_today} ({usageSummary.script_generations_provider_today}/{usageSummary.script_generations_estimate_today})
                      </span>
                    </div>
                  )}
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-on-surface-variant shrink-0">{t('quota.oracle_searches')}</dt>
                  <dd className="font-mono tabular-nums">{usageSummary.oracle_retrievals_today}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-on-surface-variant shrink-0">{t('quota.oracle_ingests')}</dt>
                  <dd className="font-mono tabular-nums">{usageSummary.oracle_ingests_today}</dd>
                </div>
                <p className="text-[10px] text-on-surface-variant leading-snug pt-1 border-t border-outline-variant/25 mt-2">
                  UTC 日切 {usageSummary.reset_utc_date}。{usageSummary.token_note}
                </p>
              </dl>
            ) : (
              <p className="text-xs text-on-surface-variant">{t('quota.hover_hint')}</p>
            )}
          </div>
        </div>

        <nav className="flex-grow space-y-1 px-3 overflow-y-auto overflow-x-visible" aria-label="主导航">
          {navItems.map(({ to, label, icon: Icon }) => {
            const isGen = to === '/generator';
            const isOra = to === '/oracle';
            const shellBusy = (isGen && generator.busy) || (isOra && oracle.busy);
            const shellLabel = isGen ? generator.label : isOra ? oracle.label : '';
            const linkTitle = shellBusy && shellLabel ? `${label}：${shellLabel}` : undefined;
            const ariaLabel = shellBusy && shellLabel ? `${label}，${shellLabel}` : undefined;

            return (
              <NavLink
                key={to}
                to={to}
                title={linkTitle}
                aria-label={ariaLabel}
                aria-busy={shellBusy}
                className={({ isActive }) =>
                  `group flex items-center gap-4 px-4 py-3 font-medium text-sm rounded-ui border transition-director-colors ${
                    isActive
                      ? 'nav-director-link--active text-on-surface'
                      : 'border-transparent text-on-surface-variant hover:bg-surface-container-high/80 hover:text-on-surface hover:border-outline-variant/15'
                  }`
                }
              >
                <span className="relative flex items-center justify-center w-4 h-4 shrink-0" aria-hidden>
                  <Icon
                    className={`w-4 h-4 transition-director-transform ${location.pathname.startsWith(to) ? 'text-secondary-fixed-dim' : 'text-on-surface-variant group-hover:text-on-surface'}`}
                  />
                  {shellBusy ? (
                    <span
                      className={`absolute -right-1 -top-0.5 h-1.5 w-1.5 rounded-full bg-secondary shadow-[0_0_8px_rgba(0,227,253,0.75)] ${reduceMotion ? '' : 'shell-activity-dot'}`}
                    />
                  ) : null}
                </span>
                <span>{label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="mt-auto px-6 space-y-4">
          <div className="space-y-2">
            {/* Cyber Segmented Language Switcher */}
            <div className="flex bg-surface-container-high/50 p-1 rounded-lg border border-outline-variant/30 relative shadow-inner mb-2">
               <button
                  onClick={() => { i18n.changeLanguage('en'); localStorage.setItem('sop_engine_lang', 'en') }}
                  className={`flex-1 text-[10px] font-black uppercase tracking-widest py-1.5 rounded-md relative z-10 transition-colors duration-300 ${i18n.language === 'en' ? 'text-on-primary' : 'text-on-surface-variant hover:text-on-surface'}`}
               >
                  EN
               </button>
               <button
                  onClick={() => { i18n.changeLanguage('zh'); localStorage.setItem('sop_engine_lang', 'zh') }}
                  className={`flex-1 text-[10px] font-black uppercase tracking-widest py-1.5 rounded-md relative z-10 transition-colors duration-300 ${i18n.language === 'zh' ? 'text-on-primary' : 'text-on-surface-variant hover:text-on-surface'}`}
               >
                  中
               </button>
               <div 
                  className={`absolute top-1 bottom-1 w-[calc(50%-4px)] bg-primary rounded-md shadow-sm transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${i18n.language === 'zh' ? 'translate-x-[calc(100%+4px)]' : 'translate-x-0'}`}
               />
            </div>

            <button type="button" onClick={() => setShowParameterManager(true)} className="btn-director-ghost">
              <Settings className="w-4 h-4 shrink-0" />
              <span>{t('nav.settings')}</span>
            </button>
            <button type="button" className="btn-director-ghost">
              <LifeBuoy className="w-4 h-4 shrink-0" />
              <span>{t('nav.support')}</span>
            </button>
          </div>
        </div>
      </aside>

      <div className="lg:ml-64 flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-40 bg-background/85 backdrop-blur-xl border-b border-outline-variant/20 flex justify-between items-center px-6 h-14">
          <div className="flex items-center gap-1.5 min-w-0 text-sm">
            <span className="text-on-surface-variant font-medium hidden sm:block">{t('nav.my_projects')}</span>
            <ChevronRight className="w-3.5 h-3.5 text-outline-variant hidden sm:block" />
            <span className="text-on-surface-variant font-medium truncate max-w-[120px] sm:max-w-[180px]">
               {currentProject ? currentProject.name : t('nav.loading')}
            </span>
            <ChevronRight className="w-3.5 h-3.5 text-outline-variant" />
            <span className="text-on-surface font-bold truncate">
              {location.pathname.startsWith('/generator') ? t('nav.lab') :
               location.pathname.startsWith('/dashboard') ? t('nav.dashboard') : 
               location.pathname.startsWith('/oracle') ? t('nav.oracle') : t('nav.overview')}
            </span>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={() => setMarketDrawerOpen(true)}
              title="Live Market Intelligence"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-outline-variant/30 bg-surface-container-low hover:bg-surface-container hover:border-emerald-500/40 transition-all group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.8)] animate-pulse" />
              <Activity className="w-4 h-4 text-on-surface-variant group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant group-hover:text-on-surface hidden sm:block transition-colors">{t('nav.intel')}</span>
            </button>
            <ThemeAppearanceControl />
          </div>
        </header>
        <main className="flex-1 min-h-0 overflow-hidden">
          {children}
        </main>
      </div>
      <LiveMarketDrawer isOpen={isMarketDrawerOpen} onClose={() => setMarketDrawerOpen(false)} />
      <ProjectSetupModal isOpen={showSetupModal} onClose={() => setShowSetupModal(false)} />
      <ParameterManagerModal isOpen={showParameterManager} onClose={() => setShowParameterManager(false)} />
    </div>
  );
};
