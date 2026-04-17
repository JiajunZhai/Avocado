import React, { useEffect, useState } from 'react';
import { Compass, FileSearch, RefreshCw, AlertCircle, CheckCircle2, Database, Share2, CornerDownRight, Zap, Target, SearchCode, DatabaseZap } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import { API_BASE } from '../config/apiBase';
import { useShellActivity } from '../context/ShellActivityContext';
import { useTranslation } from 'react-i18next';

// MOCK_INTEL removed, fetching directly from Vector Store

export const OracleIngestion: React.FC = () => {
  const { t } = useTranslation();
  const { setOracleShell } = useShellActivity();
  const [sourceUrl, setSourceUrl] = useState('');
  const [rawText, setRawText] = useState('');
  const [yearQuarter, setYearQuarter] = useState('2026-Q2');
  const [isIngesting, setIsIngesting] = useState(false);
  const [status, setStatus] = useState<{ type: 'idle' | 'success' | 'error'; message: string }>({ type: 'idle', message: '' });

  const [totalRules, setTotalRules] = useState<number>(0);
  const [intelList, setIntelList] = useState<any[]>([]);
  // Phase 26/E — retrieval pipeline status for the Refinery panel.
  const [retrievalBackend, setRetrievalBackend] = useState<string>('hybrid');
  const [ftsEnabled, setFtsEnabled] = useState<boolean>(false);
  const [vectorsCount, setVectorsCount] = useState<number>(0);
  const [rerankStatus, setRerankStatus] = useState<string>('off');
  const [isReindexing, setIsReindexing] = useState<boolean>(false);

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/refinery/stats`);
      setTotalRules(res.data.total_rules || 0);
      setIntelList(res.data.recent_intel || []);
      if (res.data.retrieval_backend) setRetrievalBackend(res.data.retrieval_backend);
      setFtsEnabled(Boolean(res.data.fts5));
      setVectorsCount(res.data.vectors || 0);
      setRerankStatus(res.data.rerank || 'off');
    } catch (e) {
      console.error("Failed to fetch refinery stats", e);
    }
  };

  const handleReindex = async () => {
    setIsReindexing(true);
    try {
      await axios.post(`${API_BASE}/api/knowledge/reindex`, {});
      await fetchStats();
    } catch (e) {
      console.error('reindex failed', e);
    } finally {
      setIsReindexing(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  // For RAG fake loading sequence
  const [loadingStep, setLoadingStep] = useState(0);

  useEffect(() => {
    setOracleShell(isIngesting, isIngesting ? t('oracle.siphoning') : '');

    let interval: any;
    if (isIngesting) {
      setLoadingStep(0);
      interval = setInterval(() => {
        setLoadingStep(prev => prev < 4 ? prev + 1 : prev);
      }, 800);
    }
    return () => {
      setOracleShell(false, '');
      if (interval) clearInterval(interval);
    };
  }, [isIngesting, setOracleShell, t]);

  const handleIngest = async () => {
    if (!sourceUrl && !rawText) {
      setStatus({ type: 'error', message: '无投料：请提供来源 URL 或原始内容提取核心因子。' });
      return;
    }

    setIsIngesting(true);
    setStatus({ type: 'idle', message: '' });

    try {
      // Intentionally slow down to show the cool RAG UI
      await new Promise(r => setTimeout(r, 3500));

      const response = await axios.post(`${API_BASE}/api/refinery/ingest`, {
        raw_text: rawText,
        source_url: sourceUrl,
        year_quarter: yearQuarter
      });

      if (response.data.success) {
        setStatus({ type: 'success', message: `虹吸完成！从报告中成功离析出 ${response.data.extracted_count} 条深层转化策略特征。` });
        setRawText('');
        setSourceUrl('');
        fetchStats();
      } else {
        setStatus({ type: 'error', message: response.data.error || '后端 RAG 炼金管道堵塞，向量离析失败。' });
      }
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : 'API 神经递质传送异常';
      setStatus({ type: 'error', message: msg });
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <div className="w-full h-full flex flex-col bg-background text-on-background page-pad overflow-hidden">
      <div className="max-w-[1600px] w-full mx-auto h-full flex flex-col min-h-0 card-base shadow-sm p-4 md:p-6 lg:p-8">

        {/* Header - Fixed Height */}
        <motion.header
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="flex items-start justify-between shrink-0 border-b border-outline-variant/30 pb-6 relative"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/5 to-transparent blur-3xl -z-10 rounded-full opacity-50" />
          <div className="flex gap-5 items-center">
            <div className="w-14 h-14 bg-gradient-to-br from-surface-container to-surface-container-high rounded-2xl flex items-center justify-center border border-outline-variant/40 shadow-sm shrink-0 relative overflow-hidden group hover:border-secondary/30 transition-all duration-300">
              <div className="absolute inset-0 bg-secondary/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <Compass className="w-7 h-7 text-secondary drop-shadow-sm group-hover:scale-110 transition-transform duration-500" />
            </div>
            <div>
              <div className="flex items-center gap-2 text-secondary font-bold text-[11px] uppercase tracking-[0.25em] mb-1.5 opacity-90">
                <Database className="w-3.5 h-3.5" /> {t('oracle.matrix')}
              </div>
              <h1 className="text-3xl lg:text-[2rem] font-black tracking-tight bg-clip-text text-transparent bg-gradient-to-br from-on-surface to-on-surface-variant leading-tight drop-shadow-sm flex items-center gap-4">
                {t('oracle.title')}
                <span className="mt-1 text-[11px] font-bold bg-surface-container-high/80 text-on-surface-variant px-2.5 py-1 rounded-md border border-outline-variant/50 shadow-sm backdrop-blur-md uppercase tracking-wider">
                  {t('oracle.global_db')}
                </span>
              </h1>
            </div>
          </div>
          <p className="text-on-surface-variant/80 text-xs mt-2 max-w-sm font-medium leading-relaxed hidden md:block text-right border-r-2 border-secondary/40 pr-4">
            {t('oracle.desc_1')}<span className="text-secondary font-black drop-shadow-sm">{t('oracle.desc_2')}</span>{t('oracle.desc_3')}
          </p>
        </motion.header>

        {/* Main Split (Zero-Scroll Architecture) */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
          className="flex-1 min-h-0 flex flex-col lg:flex-row gap-6 mt-6 overflow-hidden"
        >
          {/* Left Pane: Siphon Console (30%) */}
          <div className="w-full lg:w-80 xl:w-[26rem] shrink-0 flex flex-col h-full overflow-hidden">

            <div className="flex items-center justify-between border-b border-outline-variant/20 pb-2 mb-4 shrink-0">
              <span className="text-[10px] uppercase font-bold tracking-[0.15em] text-on-surface-variant flex items-center gap-1.5"><DatabaseZap className="w-3.5 h-3.5" /> {t('oracle.ingestion')}</span>
              <span className="text-[9px] font-mono tracking-widest bg-emerald-500/10 text-emerald-600 px-1.5 rounded border border-emerald-500/20">{t('oracle.ready')}</span>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar pr-2 pb-2 flex flex-col gap-6">
              <div className="p-5 bg-surface-container/30 rounded-[1.25rem] border-[0.5px] border-outline-variant/30 flex flex-col gap-5 shadow-[inset_0_1px_3px_rgba(255,255,255,0.02)] relative overflow-hidden shrink-0">
                <div className="absolute top-0 right-0 w-32 h-32 bg-secondary/5 blur-3xl rounded-full pointer-events-none" />
                <div className="relative z-10">
                  <label className="flex items-center gap-1.5 text-[10px] font-bold text-on-surface-variant uppercase tracking-wider mb-2">
                    <Share2 className="w-3.5 h-3.5 text-secondary" /> {t('oracle.source_url')}
                  </label>
                  <input
                    type="url"
                    placeholder="https://sensortower.com/..."
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                    className="input-surface px-4 h-11 w-full font-medium tracking-wide bg-surface-container-lowest/50 focus:border-secondary/50 transition-colors text-sm shadow-sm"
                  />
                </div>

                <div className="relative z-10">
                  <label className="flex items-center gap-1.5 text-[10px] font-bold text-on-surface-variant uppercase tracking-wider mb-2">
                    {t('oracle.time_horizon')}
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="2026-Q2"
                      value={yearQuarter}
                      onChange={(e) => setYearQuarter(e.target.value)}
                      className="input-surface pl-4 pr-10 h-11 w-full font-bold bg-surface-container-lowest/50 uppercase tracking-widest focus:border-secondary/50 transition-colors text-[13px] shadow-sm"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[9px] font-black text-secondary tracking-widest bg-secondary/10 px-1.5 py-0.5 rounded shadow-sm">{t('oracle.utc')}</span>
                  </div>
                </div>
              </div>

              <div className="flex flex-col">
                <div className="flex items-center justify-between mb-2 px-1">
                  <label className="flex items-center gap-1.5 text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">{t('oracle.raw_override')}</label>
                  <span className="text-[9px] text-on-surface-variant/60 tracking-widest bg-surface-container px-1.5 rounded">{t('oracle.empty_hint')}</span>
                </div>
                <textarea
                  placeholder={t('oracle.raw_override_ph')}
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  className="w-full min-h-[140px] resize-none input-surface p-4 text-[12px] leading-[1.8] font-mono custom-scrollbar bg-surface-container/30 border-[0.5px] border-outline-variant/30 focus:border-secondary/50 shadow-sm"
                />
              </div>
            </div>

            <div className="pt-4 shrink-0 border-t border-outline-variant/20 mt-2 mb-2 pr-2">
              <button
                type="button"
                onClick={handleIngest}
                disabled={isIngesting || (!sourceUrl && !rawText)}
                className={`w-full py-3.5 text-[13px] tracking-widest uppercase font-black gap-2 relative overflow-hidden transition-all duration-300 rounded-xl shadow-lg border-[0.5px] ${isIngesting ? 'bg-surface-container text-on-surface-variant cursor-not-allowed border-outline-variant/30' : 'bg-gradient-to-r from-secondary to-secondary-fixed text-on-secondary hover:shadow-xl hover:shadow-secondary/20 hover:-translate-y-0.5 border-secondary-fixed-dim/50 active:scale-[0.98]'}`}
              >
                <span className="relative z-10 flex items-center justify-center gap-2">
                  {isIngesting ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin text-secondary" />
                      RAG 炼金重组中...
                    </>
                  ) : (
                    <>
                      <FileSearch className="w-4 h-4" />
                      高压萃取归档 (Siphon)
                    </>
                  )}
                </span>
                {!isIngesting && <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/10 to-white/0 opacity-0 hover:opacity-100 hover:translate-x-full transition-all duration-700 ease-out" />}
              </button>
            </div>

            {status.type !== 'idle' && (
              <div
                className={`shrink-0 p-3 rounded-lg flex items-start gap-2.5 border text-xs shadow-sm animate-in fade-in slide-in-from-bottom-2 ${status.type === 'success'
                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30'
                  : 'bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/30'
                  }`}
              >
                {status.type === 'success' ? <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" /> : <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />}
                <div className="flex-1">
                  <p className="font-bold mb-0.5 tracking-wide">{status.type === 'success' ? t('oracle.alchemy_complete') : t('oracle.pipeline_fault')}</p>
                  <p className="text-[11px] opacity-80 leading-snug">{status.message}</p>
                </div>
              </div>
            )}
          </div>

          {/* Right Pane: Intelligence Feed / RAG Ritual (70%) */}
          <div className="flex-1 min-h-0 flex flex-col surface-panel border border-outline-variant/30 rounded-2xl overflow-hidden shadow-inner relative bg-surface-container-low/40">

            <div className="px-5 py-3.5 border-b border-outline-variant/30 bg-surface-container/80 flex items-center justify-between shadow-sm shrink-0 backdrop-blur-md relative z-20">
              <div className="flex items-center gap-2.5">
                <Target className="w-4 h-4 text-secondary-fixed-dim" />
                <h3 className="text-sm font-black text-on-surface uppercase tracking-wide">{t('oracle.intel_feed')}</h3>
              </div>
              <div className="flex items-center gap-2 flex-wrap justify-end">
                <span className="flex items-center gap-1.5 text-[10px] font-mono font-bold uppercase text-on-surface-variant bg-surface-container px-2 py-1 rounded-md border border-outline-variant/20 shadow-inner">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_5px_rgba(16,185,129,0.8)]" /> {t('oracle.retrieval_backend', { backend: retrievalBackend })}
                </span>
                <span className={`text-[10px] font-mono font-bold uppercase px-2 py-1 rounded-md border shadow-inner ${ftsEnabled ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20' : 'bg-surface-container text-on-surface-variant/60 border-outline-variant/20'}`}>
                  {t('oracle.fts_tag', { state: ftsEnabled ? 'ON' : 'OFF' })}
                </span>
                <span className={`text-[10px] font-mono font-bold uppercase px-2 py-1 rounded-md border shadow-inner ${rerankStatus === 'on' ? 'bg-secondary/10 text-secondary border-secondary/20' : 'bg-surface-container text-on-surface-variant/60 border-outline-variant/20'}`}>
                  {t('oracle.rerank_tag', { state: (rerankStatus || 'off').toUpperCase() })}
                </span>
                <span className="text-[10px] font-mono font-bold uppercase text-on-surface-variant bg-surface-container px-2 py-1 rounded-md border border-outline-variant/20 shadow-inner">
                  {t('oracle.vectors_tag', { count: vectorsCount })}
                </span>
                <span className="text-[10px] flex items-center gap-1 text-on-surface-variant font-bold opacity-80">
                  {t('oracle.rag_rules', { count: totalRules })}
                </span>
                <button
                  type="button"
                  onClick={handleReindex}
                  disabled={isReindexing}
                  className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded-md border border-secondary/30 text-secondary bg-secondary/10 hover:bg-secondary/20 disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
                >
                  {isReindexing ? t('oracle.reindexing') : t('oracle.reindex')}
                </button>
              </div>
            </div>

            {/* FEED VAULT */}
            <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-5 flex flex-col gap-4 relative z-10">
              {intelList.length === 0 && !isIngesting && (
                <div className="flex-1 flex flex-col items-center justify-center text-center opacity-70 mt-10">
                  <DatabaseZap className="w-10 h-10 text-on-surface-variant mb-4 opacity-30" />
                  <h4 className="text-sm font-bold text-on-surface-variant uppercase tracking-wider mb-2">Vault is Empty</h4>
                  <p className="text-[11px] text-on-surface-variant max-w-xs">{t('oracle.empty_hint')}</p>
                </div>
              )}
              {intelList.map((intel, idx) => (
                <motion.div
                  key={intel.id}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.1, duration: 0.3 }}
                  className="group bg-gradient-to-br from-surface-container-lowest to-surface-container/30 border-[0.5px] border-outline-variant/30 rounded-[1.25rem] p-5 flex flex-col gap-4 hover:border-secondary/40 hover:shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1)] hover:shadow-secondary/5 transition-all cursor-pointer relative overflow-hidden shrink-0"
                >
                  <div className="absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />

                  <div className="absolute left-0 top-0 bottom-0 w-1 bg-outline-variant/20 group-hover:bg-secondary transition-colors" />

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] px-2 py-1 rounded bg-surface-container-high/80 shadow-sm font-extrabold text-on-surface uppercase tracking-widest border-[0.5px] border-outline-variant/30 backdrop-blur-md">{intel.region}</span>
                      <span className="text-[9px] px-2 py-1 rounded bg-secondary/10 text-secondary font-black tracking-widest uppercase border-[0.5px] border-secondary/20 backdrop-blur-md">{intel.tag}</span>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-on-surface-variant bg-surface-container-high px-2 py-1 rounded-md tracking-widest shadow-inner">{intel.time}</span>
                  </div>

                  <div className="pl-1">
                    <h4 className="text-[14px] font-bold text-on-surface leading-[1.6] mb-3 group-hover:text-secondary-fixed transition-colors line-clamp-3">{intel.title}</h4>
                    <div className="flex items-center gap-4 text-[10px] text-on-surface-variant font-bold uppercase tracking-widest">
                      <span className="flex items-center gap-1.5 opacity-80">
                        <CornerDownRight className="w-3.5 h-3.5 text-outline drop-shadow-sm" /> {intel.source}
                      </span>
                      <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded shadow-sm border-[0.5px] border-emerald-500/20">
                        <Zap className="w-3 h-3" /> {intel.stat}
                      </span>
                    </div>
                  </div>
                </motion.div>
              ))}
              <div className="w-full text-center mt-4">
                <span className="text-[10px] uppercase font-bold text-on-surface-variant tracking-[0.2em] opacity-40">{t('oracle.end_updates')}</span>
              </div>
            </div>

            {/* RAG LOADING OVERLAY RITUAL */}
            <AnimatePresence>
              {isIngesting && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 z-30 bg-surface-container-low/70 backdrop-blur-[8px] flex flex-col items-center justify-center p-8 border-t border-outline-variant/20"
                >
                  <div className="max-w-md w-full bg-black/90 dark:bg-black rounded-2xl border border-secondary/30 p-6 flex flex-col gap-4 shadow-[0_0_50px_rgba(34,211,238,0.15)] relative overflow-hidden">

                    {/* Cyber scanning line */}
                    <motion.div
                      animate={{ top: ['0%', '100%', '0%'] }}
                      transition={{ duration: 2, ease: "linear", repeat: Infinity }}
                      className="absolute left-0 right-0 h-10 w-full bg-gradient-to-b from-secondary/0 via-secondary/20 to-secondary/0 pointer-events-none"
                    />

                    <div className="flex items-center gap-3 border-b border-white/10 pb-4 shrink-0 relative z-10">
                      <div className="w-10 h-10 rounded-xl bg-secondary/20 flex flex-col items-center justify-center border border-secondary/30">
                        <SearchCode className="w-5 h-5 text-secondary animate-pulse" />
                      </div>
                      <div>
                        <h2 className="text-secondary font-black tracking-widest text-sm uppercase text-shadow-glow">{t('oracle.refinery')}</h2>
                        <p className="text-[10px] font-mono text-secondary-fixed/70 mt-0.5">VDB Engine · 3.0</p>
                      </div>
                    </div>

                    <div className="flex-1 min-h-0 flex flex-col gap-2 font-mono text-[10px] uppercase tracking-wider relative z-10">
                      <p className="text-white/50 mb-2">正在通过 RAG 引擎抽丝剥茧，提取该源素材的 12 项潜在买量因子...</p>

                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: loadingStep >= 1 ? 1 : 0 }} className="flex items-center justify-between text-secondary/80">
                        <span>[SYS] Parsing Text Chunks & Embeddings...</span>
                        <span>{loadingStep >= 2 ? 'OK' : '///'}</span>
                      </motion.div>

                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: loadingStep >= 2 ? 1 : 0 }} className="flex items-center justify-between text-emerald-400">
                        <span>[RAG] Scanning for "Whale Gameplay Hook"...</span>
                        <span>{loadingStep >= 3 ? 'FOUND: 3' : '///'}</span>
                      </motion.div>

                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: loadingStep >= 3 ? 1 : 0 }} className="flex items-center justify-between text-orange-400">
                        <span>[RAG] Isolating Cultural Blindspots...</span>
                        <span>{loadingStep >= 4 ? 'ISOLATED' : '///'}</span>
                      </motion.div>

                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: loadingStep >= 4 ? 1 : 0 }} className="flex items-center justify-between text-primary-dim">
                        <span>[SYS] Injecting into Global Vector Store...</span>
                        <span className="animate-pulse">_</span>
                      </motion.div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

          </div>
        </motion.div>
      </div>
    </div>
  );
};
