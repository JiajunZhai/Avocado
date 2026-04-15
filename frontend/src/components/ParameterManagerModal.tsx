import React, { useState, useEffect } from 'react';
import { X, Plus, Trash2, Save, FileJson, Check, AlertCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { API_BASE } from '../config/apiBase';
import { motion } from 'framer-motion';

interface ParameterManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ParameterManagerModal: React.FC<ParameterManagerModalProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  
  const [activeTab, setActiveTab] = useState<'regions' | 'platforms' | 'angles'>('regions');
  const [metadata, setMetadata] = useState<{ regions: any[], platforms: any[], angles: any[] }>({ regions: [], platforms: [], angles: [] });
  // Selected item for editing
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState<string>('');
  const [errorObj, setErrorObj] = useState<string | null>(null);
  const [successStatus, setSuccessStatus] = useState(false);

  const fetchMetadata = async () => {
    try {
      const { data } = await axios.get(`${API_BASE}/api/insights/metadata`);
      setMetadata(data);
      // Auto-select first if none
      if (!selectedId && data[activeTab].length > 0) {
         handleSelect(data[activeTab][0]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchMetadata();
    }
  }, [isOpen]);

  useEffect(() => {
     if (metadata[activeTab]) {
        const found = metadata[activeTab].find((i) => i.id === selectedId);
        if (!found && metadata[activeTab].length > 0) {
           handleSelect(metadata[activeTab][0]);
        } else if (!found) {
           setSelectedId(null);
           setEditContent('');
        }
     }
  }, [activeTab, metadata]);

  const handleSelect = (item: any) => {
     setSelectedId(item.id);
     setEditContent(JSON.stringify(item, null, 4));
     setErrorObj(null);
     setSuccessStatus(false);
  };

  const handleSave = async () => {
     setErrorObj(null);
     setSuccessStatus(false);
     let parsed;
     try {
        parsed = JSON.parse(editContent);
     } catch (e) {
        setErrorObj(t('param_manager.err_json'));
        return;
     }

     if (!parsed.id || !parsed.category) {
        setErrorObj(t('param_manager.err_missing'));
        return;
     }

     try {
        await axios.post(`${API_BASE}/api/insights/manage/update`, {
           category: activeTab,
           insight_id: parsed.id,
           content: parsed
        });
        setSuccessStatus(true);
        setTimeout(() => setSuccessStatus(false), 2000);
        fetchMetadata();
     } catch (e: any) {
        setErrorObj(e.message || "Failed to save.");
     }
  };

  const handleDelete = async (id: string) => {
     if (!confirm(t('param_manager.confirm_delete'))) return;
     try {
        await axios.post(`${API_BASE}/api/insights/manage/delete`, {
           category: activeTab,
           insight_id: id
        });
        fetchMetadata();
     } catch (e) {
        console.error("Delete failed", e);
     }
  };

  const handleAddNew = () => {
     const newId = `new_${activeTab.slice(0, -1)}_${Date.now().toString().slice(-4)}`;
     const template = {
        id: newId,
        category: activeTab.slice(0, -1),
        name: t('param_manager.new_entry'),
        description: "",
     };
     setSelectedId(newId);
     setEditContent(JSON.stringify(template, null, 4));
     setErrorObj(null);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center pointer-events-auto">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        className="relative w-[90vw] max-w-5xl h-[85vh] bg-surface-container shadow-elev-4 rounded-3xl border border-outline-variant/30 flex flex-col overflow-hidden text-on-surface"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant/20 bg-surface-container-low">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
              <FileJson className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-black tracking-widest uppercase text-on-surface">{t('param_manager.hub_title')}</h2>
              <p className="text-[10px] text-on-surface-variant font-medium tracking-wide uppercase">{t('param_manager.hub_subtitle')}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-surface-container-high rounded-full transition-colors">
            <X className="w-5 h-5 text-on-surface-variant" />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 min-h-0">
          {/* Navigation Sidebar */}
          <div className="w-64 border-r border-outline-variant/20 bg-surface-container-lowest flex flex-col">
            <div className="p-4 space-y-2">
              <button
                onClick={() => setActiveTab('regions')}
                className={`w-full flex items-center justify-between p-3 rounded-xl border transition-all ${activeTab === 'regions' ? 'bg-primary/10 border-primary/30 text-primary' : 'bg-transparent border-transparent text-on-surface-variant hover:bg-surface-container'}`}
              >
                <span className="text-xs font-bold uppercase tracking-widest">{t('param_manager.tab_regions')}</span>
                <span className="text-[10px] bg-surface-container-high px-2 py-0.5 rounded-full">{metadata.regions.length}</span>
              </button>
              <button
                onClick={() => setActiveTab('platforms')}
                 className={`w-full flex items-center justify-between p-3 rounded-xl border transition-all ${activeTab === 'platforms' ? 'bg-primary/10 border-primary/30 text-primary' : 'bg-transparent border-transparent text-on-surface-variant hover:bg-surface-container'}`}
              >
                <span className="text-xs font-bold uppercase tracking-widest">{t('param_manager.tab_platforms')}</span>
                <span className="text-[10px] bg-surface-container-high px-2 py-0.5 rounded-full">{metadata.platforms.length}</span>
              </button>
              <button
                onClick={() => setActiveTab('angles')}
                 className={`w-full flex items-center justify-between p-3 rounded-xl border transition-all ${activeTab === 'angles' ? 'bg-primary/10 border-primary/30 text-primary' : 'bg-transparent border-transparent text-on-surface-variant hover:bg-surface-container'}`}
              >
                <span className="text-xs font-bold uppercase tracking-widest">{t('param_manager.tab_angles')}</span>
                <span className="text-[10px] bg-surface-container-high px-2 py-0.5 rounded-full">{metadata.angles.length}</span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-2 border-t border-outline-variant/20">
               <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{t('param_manager.active_atoms')}</span>
                  <button onClick={handleAddNew} className="p-1 hover:bg-primary/10 hover:text-primary rounded text-on-surface-variant transition-colors">
                     <Plus className="w-4 h-4" />
                  </button>
               </div>
               
               <div className="space-y-1 pb-4">
                  {metadata[activeTab].map((item) => (
                     <div key={item.id} className={`group flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors ${selectedId === item.id ? 'bg-surface-container-high border-l-2 border-primary' : 'hover:bg-surface-container-low border-l-2 border-transparent'}`} onClick={() => handleSelect(item)}>
                        <div className="truncate pr-2">
                           <div className={`text-xs font-bold truncate ${selectedId === item.id ? 'text-on-surface' : 'text-on-surface-variant'}`}>{item.name || item.id}</div>
                           <div className="text-[9px] text-on-surface-variant opacity-70 truncate">{item.id}</div>
                        </div>
                        <button 
                           onClick={(e) => { e.stopPropagation(); handleDelete(item.id); }}
                           className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/10 text-red-400 hover:text-red-500 rounded transition-all"
                        >
                           <Trash2 className="w-3 h-3" />
                        </button>
                     </div>
                  ))}
               </div>
            </div>
          </div>

          {/* Editor Area */}
          <div className="flex-1 flex flex-col bg-surface-container-lowest">
            {selectedId ? (
               <>
                  <div className="p-4 border-b border-outline-variant/20 flex justify-between items-center bg-surface-container-low">
                     <div className="flex flex-col">
                        <span className="text-sm font-bold text-on-surface">{selectedId}</span>
                        <span className="text-[10px] text-on-surface-variant uppercase tracking-widest">{t(`param_manager.tab_${activeTab}`)} {t('param_manager.document_suffix')}</span>
                     </div>
                     <div className="flex items-center gap-3">
                        {errorObj && <div className="text-xs text-red-400 flex items-center gap-1"><AlertCircle className="w-3 h-3" /> {errorObj}</div>}
                        {successStatus && <div className="text-xs text-emerald-400 flex items-center gap-1"><Check className="w-3 h-3" /> {t('param_manager.saved_success')}</div>}
                        
                        <button onClick={handleSave} className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg text-xs font-bold tracking-widest uppercase hover:bg-primary/90 transition-colors shadow-sm">
                           <Save className="w-3.5 h-3.5" />
                           {t('param_manager.commit_btn')}
                        </button>
                     </div>
                  </div>
                  <div className="flex-1 p-4 overflow-hidden flex flex-col">
                     <textarea 
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        spellCheck={false}
                        className="flex-1 w-full bg-[#1e1e1e] text-[#d4d4d4] p-4 rounded-xl font-mono text-[13px] resize-none outline-none focus:ring-1 focus:ring-primary/50 shadow-inner"
                        placeholder={t('param_manager.json_placeholder')}
                     />
                  </div>
               </>
            ) : (
               <div className="flex-1 flex flex-col items-center justify-center text-on-surface-variant">
                  <FileJson className="w-12 h-12 mb-4 opacity-20" />
                  <p className="text-sm font-medium">{t('param_manager.select_placeholder')}</p>
               </div>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
};
