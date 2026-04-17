import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { Plus, Clapperboard, MoreVertical } from 'lucide-react';
import { useProjectContext } from '../context/ProjectContext';
import { ProjectSetupModal } from '../components/ProjectSetupModal';
import { ThemeAppearanceControl } from '../components/ThemeAppearanceControl';
import systemLogo from '../assets/logo.png';

import { ProviderSettings } from './ProviderSettings';
import { Settings2 } from 'lucide-react';

export const WorkspaceHub: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { projects, setCurrentProject, isLoading } = useProjectContext();
  const [isSetupModalOpen, setIsSetupModalOpen] = useState(false);
  const [editProject, setEditProject] = useState<any>(null);
  const [showProviderModal, setShowProviderModal] = useState(false);

  const handleEnterProject = (project: any) => {
    setCurrentProject(project);
    navigate('/dashboard');
  };

  const openSetupModal = (project: any = null) => {
    setEditProject(project);
    setIsSetupModalOpen(true);
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { 
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } }
  };

  return (
    <div className="min-h-screen bg-background text-on-background flex flex-col relative overflow-hidden">
      
      {/* Background Decor */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
         <div className="absolute top-[-20%] right-[-10%] w-[50vw] h-[50vw] bg-emerald-500/10 rounded-full blur-[120px] mix-blend-normal"></div>
         <div className="absolute bottom-[-10%] left-[-10%] w-[40vw] h-[40vw] bg-lime-500/10 rounded-full blur-[100px] mix-blend-normal"></div>
      </div>

      {/* Header */}
      <header className="relative z-10 w-full px-8 py-5 flex items-center justify-between border-b border-outline-variant/10 bg-surface-container-low/30 backdrop-blur-md">
        <div className="flex items-center gap-6">
           <div className="flex items-center gap-2.5">
             <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-surface border border-outline-variant/30 shadow-sm">
               <img src={systemLogo} alt="Avocado Logo" className="h-[22px] w-auto object-contain drop-shadow-[0_2px_4px_rgba(0,0,0,0.1)] transition-transform hover:scale-105 duration-500" />
             </div>
             <div className="flex flex-col">
               <span className="text-[14px] font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-br from-emerald-800 to-emerald-600 dark:from-emerald-300 dark:to-emerald-100 leading-[1.1]">
                 Avocado
               </span>
               <span className="text-[9px] font-bold tracking-[0.2em] text-emerald-600/70 dark:text-emerald-400/70 uppercase leading-none">
                 Workspace Hub
               </span>
             </div>
           </div>
           
           <div className="h-6 w-[1px] bg-outline-variant/30"></div>
           
           <button 
             onClick={() => setShowProviderModal(true)}
             className="flex items-center gap-2 group px-3 py-1.5 rounded-lg bg-surface hover:bg-surface-container border border-outline-variant/40 hover:border-emerald-500/30 transition-all focus:outline-none"
             title="Configure AI Providers"
           >
             <Settings2 className="w-4 h-4 text-on-surface-variant group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors" />
             <span className="text-[11px] font-bold uppercase tracking-wider text-on-surface-variant group-hover:text-emerald-700 dark:group-hover:text-emerald-400 transition-colors">
                Models
             </span>
           </button>
        </div>
        <div className="flex items-center gap-4">
           <ThemeAppearanceControl />
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 flex-1 w-full max-w-7xl mx-auto px-8 py-12 flex flex-col">
         
         <div className="mb-10 flex items-end justify-between">
            <div>
               <h1 className="text-3xl font-black tracking-tight text-on-surface mb-2">My Workspaces</h1>
               <p className="text-sm font-medium text-on-surface-variant">Manage your game archives, assets, and SOP engines.</p>
            </div>
         </div>

         {isLoading ? (
            <div className="flex-1 flex items-center justify-center">
               <div className="flex flex-col items-center gap-4 text-on-surface-variant">
                  <div className="w-8 h-8 rounded-full border-2 border-emerald-500/30 border-t-emerald-500 animate-spin"></div>
                  <span className="text-xs font-bold tracking-widest uppercase">Loading Matrix...</span>
               </div>
            </div>
         ) : (
            <motion.div 
               className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-5"
               variants={containerVariants}
               initial="hidden"
               animate="visible"
            >
               {/* Create New Card */}
               <motion.button
                  variants={cardVariants}
                  onClick={() => openSetupModal()}
                  className="group relative flex flex-col items-center justify-center min-h-[11rem] rounded-xl border-2 border-dashed border-outline-variant/60 bg-surface-container/30 hover:bg-surface-container hover:border-emerald-500/50 hover:shadow-elev-1 transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-background"
               >
                  <div className="w-12 h-12 rounded-[1rem] bg-surface drop-shadow-sm flex items-center justify-center group-hover:bg-emerald-100 group-hover:scale-110 transition-all duration-300 mb-3 dark:bg-surface-container-high dark:group-hover:bg-emerald-900/40">
                     <Plus className="w-5 h-5 text-on-surface-variant group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors" />
                  </div>
                  <span className="text-[13px] font-bold tracking-wide text-on-surface-variant group-hover:text-emerald-700 dark:group-hover:text-emerald-400 transition-colors">
                     Create Workspace
                  </span>
                  <span className="text-[10px] text-on-surface-variant/70 mt-1 uppercase tracking-wider">Initialize archive</span>
               </motion.button>

               {/* Project Cards */}
               {projects.map((project) => (
                  <motion.div
                     key={project.id}
                     variants={cardVariants}
                     onClick={() => handleEnterProject(project)}
                     className="group relative flex flex-col min-h-[11rem] rounded-xl border border-outline-variant/50 bg-surface hover:bg-surface-container-lowest shadow-sm hover:shadow-elev-2 hover:border-emerald-500/50 hover:-translate-y-1 transition-all duration-300 cursor-pointer overflow-hidden p-5"
                  >
                     {/* Hover Liquid Gradient effect */}
                     <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/0 to-lime-500/0 group-hover:from-emerald-500/5 group-hover:to-lime-500/5 transition-colors duration-500 pointer-events-none"></div>
                     
                     <div className="flex justify-between items-start w-full relative z-10 mb-4">
                        <div className="flex items-center gap-3">
                           <div className="w-10 h-10 rounded-[0.85rem] bg-gradient-to-br from-surface-container to-surface-container-high border border-outline-variant/50 shadow-sm flex items-center justify-center shrink-0">
                              <span className="text-lg font-black text-on-surface uppercase group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">{project.name.substring(0, 1)}</span>
                           </div>
                           <div className="flex flex-col">
                              <span className="text-[9px] font-mono font-bold text-emerald-600/60 dark:text-emerald-400/60">
                                 #AX-{project.id.substring(0, 6).toUpperCase()}
                              </span>
                              <span className="text-[10px] text-on-surface-variant/70 font-medium">
                                 {new Date(project.created_at).toLocaleDateString()}
                              </span>
                           </div>
                        </div>
                        
                        <div className="flex items-center gap-1">
                           <button 
                              onClick={(e) => { e.stopPropagation(); openSetupModal(project); }} 
                              className="p-1.5 rounded-md text-on-surface-variant/40 hover:text-emerald-500 hover:bg-surface-container transition-colors"
                              title="Configure Workspace"
                           >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                           </button>
                           <div className="p-1 rounded-md text-on-surface-variant/30 group-hover:text-emerald-500/60 transition-colors">
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                           </div>
                        </div>
                     </div>

                     <div className="relative z-10 flex flex-col flex-1">
                        <h3 className="text-[15px] font-black text-on-surface mb-3 truncate leading-tight group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                           {project.name}
                        </h3>
                        {/* Generated Asset Statistics (SOP vs Copy) */}
                        <div className="mt-auto">
                           {(() => {
                              const sopCount = project.history_log?.filter((h: any) => h.output_kind === 'sop').length || 0;
                              const copyCount = project.history_log?.filter((h: any) => h.output_kind === 'copy').length || 0;
                              const maxGen = Math.max(10, sopCount + copyCount);
                              const sopPercent = Math.min((sopCount / maxGen) * 100, 100);
                              const copyPercent = Math.min((copyCount / maxGen) * 100, 100);

                              return (
                                 <div className="flex flex-col gap-1.5">
                                    <div className="flex justify-between items-end text-[9px] font-bold uppercase tracking-wider text-on-surface-variant">
                                       <span>分镜脚本 (SOP): <span className="text-emerald-600 dark:text-emerald-400 font-mono">{sopCount}</span></span>
                                       <span>文案 (COPY): <span className="text-lime-600 dark:text-lime-400 font-mono">{copyCount}</span></span>
                                    </div>
                                    <div className="h-1.5 w-full bg-surface-container-high rounded-full overflow-hidden flex shadow-inner">
                                       <div className="h-full bg-emerald-500 transition-all duration-1000 ease-out" style={{ width: `${sopPercent}%` }} />
                                       <div className="h-full bg-lime-400 transition-all duration-1000 ease-out" style={{ width: `${copyPercent}%` }} />
                                    </div>
                                 </div>
                              );
                           })()}
                        </div>
                     </div>
                  </motion.div>
               ))}
            </motion.div>
         )}
      </main>

      {/* Handle specific Provider Settings Modal */}
      {showProviderModal && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 md:p-8 animate-in fade-in duration-200">
           <div className="relative card-base shadow-2xl rounded-2xl w-full max-w-6xl h-[90vh] flex flex-col overflow-hidden bg-background">
             <div className="flex-1 overflow-y-auto">
               <ProviderSettings onClose={() => setShowProviderModal(false)} />
             </div>
           </div>
        </div>
      )}

      {/* Render the modal at this level so it mounts */}
      <ProjectSetupModal isOpen={isSetupModalOpen} onClose={() => setIsSetupModalOpen(false)} editTarget={editProject} />
    </div>
  );
};
