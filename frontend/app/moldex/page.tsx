"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getMoldex, getProteinFile, getPoseFile, certifyMolecule } from "@/lib/api";
import { API_URL } from "@/lib/config";
import { MoleculeViewer3D } from "@/components/MoleculeViewer3D";
import MoldexCard from "@/components/MoldexCard";
import MolecularComparison from "@/components/MolecularComparison";
import { Search, ShieldCheck, Activity, Info, BarChart3, ChevronRight, Binary, Database, Box, FlaskConical, AlertCircle } from "lucide-react";
import { useInterface } from "@/context/InterfaceContext";
import dynamic from "next/dynamic";

const ProMoldex = dynamic(() => import("@/components/interfaces/pro/ProMoldex"), {
  ssr: false,
  loading: () => (
    <div className="flex h-screen items-center justify-center bg-[#02050b] text-indigo-400 font-sans p-6">
      <div className="text-center">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent mx-auto mb-4" />
        <span className="text-[10px] font-black uppercase tracking-[0.2em] animate-pulse">Cargando workbench pro...</span>
      </div>
    </div>
  )
});

export default function MoldexPage() {
  const { interfaceMode } = useInterface();

  const [molecules, setMolecules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [targetFilter, setTargetFilter] = useState("ALL");
  
  // Panel States
  const [showLeftPanel, setShowLeftPanel] = useState(true);
  const [showRightPanel, setShowRightPanel] = useState(true);

  // Comparison state
  const [compareMode, setCompareMode] = useState(false);
  const [selectionForCompare, setSelectionForCompare] = useState<string[]>([]);

  // 3D View state
  const [proteinData, setProteinData] = useState<string | null>(null);
  const [poseData, setPoseData] = useState<string | null>(null);
  const [loading3D, setLoading3D] = useState(false);
  const [activeView, setActiveView] = useState<'LIST' | '3D' | 'INFO'>('LIST');
  const [windowHeight, setWindowHeight] = useState(1000);
  const [certifying, setCertifying] = useState(false);

  const handleCertify = async () => {
    if (!selectedId) return;
    try {
      setCertifying(true);
      const res = await certifyMolecule(selectedId);
      setMolecules(prev => prev.map(m => {
        if (m.id === selectedId) {
          return {
            ...m,
            blockchain: {
              ...m.blockchain,
              certified: true,
              tx_signature: res.signature
            }
          };
        }
        return m;
      }));
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setCertifying(false);
    }
  };

  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    setWindowHeight(window.innerHeight);
    const handleResize = () => {
      setWindowHeight(window.innerHeight);
      setIsMobile(window.innerWidth < 768);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMoldex()
      .then((data) => {
        setMolecules(data.results);
        if (data.results.length > 0) {
          setSelectedId(data.results[0].id);
        }
      })
      .catch((err) => {
        console.error("Error al cargar la bioteca:", err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  const selectedMolecule = useMemo(() => 
    molecules.find(m => m.id === selectedId), 
  [selectedId, molecules]);

  useEffect(() => {
    if (selectedMolecule) {
      setLoading3D(true);
      setPoseData(null); // Clear previous pose to show loading
      
      Promise.all([
        getProteinFile(selectedMolecule.id),
        getPoseFile(selectedMolecule.id)
      ]).then(([protein, pose]) => {
        setProteinData(protein);
        setPoseData(pose);
      }).catch(err => {
        console.error("Error loading 3D data:", err);
      }).finally(() => setLoading3D(false));
    }
  }, [selectedMolecule]);

  const filteredMolecules = useMemo(() => {
    return molecules.filter(m => {
      const name = m.name?.toLowerCase() || "";
      const smiles = m.smiles || "";
      const matchesSearch = name.includes(search.toLowerCase()) || 
                           smiles.includes(search);
      const matchesTarget = targetFilter === "ALL" || m.target?.pdb_id === targetFilter;
      return matchesSearch && matchesTarget;
    });
  }, [molecules, search, targetFilter]);

  const targets = useMemo(() => {
    const t = new Set(molecules.map(m => m.target?.pdb_id).filter(Boolean));
    return ["ALL", ...Array.from(t)];
  }, [molecules]);

  const handleToggleCompare = (id: string) => {
    setSelectionForCompare(prev => {
      const next = prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id].slice(-2);
      if (next.length === 2) {
        setTimeout(() => setCompareMode(true), 0);
      }
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#05080f] text-indigo-500">
        <div className="text-center">
          <motion.div
            animate={{ rotate: 360, scale: [1, 1.1, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
            className="mb-4 inline-block"
          >
            <Activity size={64} className="text-indigo-500 filter drop-shadow-[0_0_15px_rgba(99,102,241,0.5)]" />
          </motion.div>
          <p className="text-xs font-black tracking-[0.3em] text-slate-500 animate-pulse">SINCRONIZANDO BIOTECA...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#05080f] text-slate-300 font-sans p-6">
        <div className="max-w-md w-full rounded-2xl border border-red-500/20 bg-red-950/20 p-8 text-center backdrop-blur-xl shadow-2xl">
          <div className="mb-4 inline-block p-3 rounded-full bg-red-500/10 border border-red-500/30">
            <AlertCircle size={32} className="text-red-500" />
          </div>
          <h2 className="text-lg font-black text-white uppercase tracking-wider mb-2">Error de Conexión</h2>
          <p className="text-xs text-slate-400 leading-relaxed mb-6">
            {error}
          </p>
          <button 
            onClick={() => window.location.reload()}
            className="w-full text-[10px] font-black text-white bg-red-600 hover:bg-red-500 py-3.5 rounded-xl transition-all uppercase tracking-widest"
          >
            Reintentar Conexión
          </button>
        </div>
      </div>
    );
  }

  if (interfaceMode === "PRO") {
    return (
      <ProMoldex 
        molecules={molecules}
        selectedId={selectedId}
        setSelectedId={setSelectedId}
        search={search}
        setSearch={setSearch}
        targetFilter={targetFilter}
        setTargetFilter={setTargetFilter}
        selectedMolecule={selectedMolecule}
        proteinData={proteinData}
        poseData={poseData}
        loading3D={loading3D}
        certifying={certifying}
        handleCertify={handleCertify}
        targets={targets}
      />
    );
  }

  return (
    <div className="fixed inset-x-0 bottom-0 top-[57px] z-50 bg-[#05080f] text-slate-300 font-sans selection:bg-indigo-500/30 overflow-hidden">
      
      {/* 3D Viewport: El Protagonista (Full Background) */}
      <div className="absolute inset-0 z-0">
        <MoleculeViewer3D 
          proteinData={proteinData ?? undefined}
          poseData={poseData ?? undefined}
          height={windowHeight - 57}
          hotspots={(selectedMolecule?.target?.hotspots || []).map((h: any) => h.name)}
          hotspotsHit={selectedMolecule?.hotspots_hit || []}
          mobileTopOffset={true}
        />
      </div>

      {/* Capa de Interfaz (Overlays Flotantes) */}
      <div className="absolute inset-0 z-10 pointer-events-none flex flex-col md:flex-row">
        
        {/* Mobile Navigation Header */}
        <div className="h-[60px] flex md:hidden items-center justify-between px-6 bg-[#0a0f1d] border-b border-slate-800/50 z-50 pointer-events-auto w-full">
          <h1 className="text-sm font-black tracking-tighter text-white flex items-center gap-2">
            <FlaskConical size={16} className="text-indigo-500" />
            MOLDEX <span className="text-[8px] bg-indigo-500/15 text-indigo-400 px-1.5 py-0.5 rounded-full border border-indigo-500/35 tracking-widest uppercase font-black">Bioteca</span>
          </h1>
          <div className="flex gap-1">
            {[
              { id: 'LIST', icon: <Database size={14} /> },
              { id: '3D', icon: <Box size={14} /> },
              { id: 'INFO', icon: <Info size={14} /> }
            ].map((btn) => (
              <button
                key={btn.id}
                onClick={() => setActiveView(btn.id as any)}
                className={`p-2 rounded-lg transition-all ${
                  activeView === btn.id 
                    ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/20' 
                    : 'bg-slate-900 text-slate-500'
                }`}
              >
                {btn.icon}
              </button>
            ))}
          </div>
        </div>

        {/* Sidebar Left: Biblioteca (Collapsible) */}
        <motion.aside 
          initial={false}
          animate={isMobile ? {
            width: activeView === 'LIST' ? "100%" : 0,
            opacity: activeView === 'LIST' ? 1 : 0,
            x: activeView === 'LIST' ? 0 : -800
          } : { 
            width: showLeftPanel ? 320 : 0,
            opacity: showLeftPanel ? 1 : 0,
            x: showLeftPanel ? 0 : -320
          }}
          transition={{ type: "spring", stiffness: 300, damping: 35 }}
          className={`border-r border-white/5 bg-[#0a0f1d]/95 md:bg-[#0a0f1d]/40 backdrop-blur-xl pointer-events-auto overflow-hidden flex flex-col ${isMobile ? 'absolute inset-x-0 bottom-0 top-[60px] z-40' : 'h-full'} ${isMobile && activeView !== 'LIST' ? 'pointer-events-none' : ''}`}
        >
          <div className="p-8 border-b border-white/5 min-w-[320px]">
            <h1 className="text-xl font-black tracking-tighter text-white flex items-center gap-2 mb-8">
              <FlaskConical size={24} className="text-indigo-500" />
              MOLDEX <span className="text-[10px] bg-indigo-500/15 text-indigo-400 px-2 py-0.5 rounded-full border border-indigo-500/35 tracking-widest uppercase font-black">Bioteca</span>
            </h1>
            
            <div className="space-y-4">
              <div className="relative group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
                <input 
                  type="text"
                  placeholder="Buscar molécula..."
                  className="w-full rounded-2xl bg-black/40 border border-white/10 py-3 pl-10 pr-4 text-xs text-slate-200 outline-none focus:border-indigo-500/50 transition-all"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="flex items-center gap-2 overflow-x-auto pb-2 no-scrollbar">
                {targets.map(t => (
                  <button
                    key={t}
                    onClick={() => setTargetFilter(t)}
                    className={`flex-shrink-0 rounded-full px-4 py-2 text-[9px] font-black uppercase tracking-widest border transition-all ${
                      targetFilter === t ? 'bg-indigo-500 border-indigo-400 text-white' : 'bg-black/40 border-white/5 text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar min-w-[320px]">
            <AnimatePresence mode="popLayout">
              {filteredMolecules.map((m) => (
                <MoldexCard 
                  key={m.id}
                  molecule={m}
                  isSelected={selectedId === m.id}
                  onClick={(id) => {
                    setSelectedId(id);
                    if (window.innerWidth < 768) setActiveView('3D');
                  }}
                  onCompareToggle={() => handleToggleCompare(m.id)}
                  isComparing={selectionForCompare.includes(m.id)}
                />
              ))}
            </AnimatePresence>
          </div>
        </motion.aside>

        {/* Toggle Left Button */}
        <div className="hidden md:flex items-center z-50 pointer-events-auto">
          <button 
            onClick={() => setShowLeftPanel(!showLeftPanel)}
            className="h-16 w-6 bg-indigo-600/20 backdrop-blur-md border border-indigo-500/30 rounded-r-xl flex items-center justify-center text-indigo-400 hover:text-white transition-colors shadow-lg"
          >
            <ChevronRight size={14} className={`transition-transform ${showLeftPanel ? 'rotate-180' : ''}`} />
          </button>
        </div>

        {/* Espacio Central del Visor */}
        <div className="flex-1 relative pointer-events-none">
          {/* HUD Superior */}
          {!isMobile && (
            <div className="absolute top-8 left-8 right-8 flex items-start justify-between">
              <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-4 pointer-events-auto">
                <div className="h-14 w-14 rounded-2xl bg-black/60 border border-white/10 flex items-center justify-center backdrop-blur-xl shadow-2xl">
                   <Box className="text-indigo-500" size={24} />
                </div>
                <div>
                  <p className="text-[10px] font-black text-indigo-500 uppercase tracking-[0.3em] mb-1">PROTAGONISTA 3D</p>
                  <h2 className="text-2xl font-black text-white tracking-tighter">ESTÁNDAR CIENTÍFICO</h2>
                </div>
              </motion.div>
            </div>
          )}

          {/* HUD Inferior (Info de Molécula) */}
          <AnimatePresence mode="wait">
            {((!isMobile && selectedId) || (isMobile && activeView === '3D' && selectedId)) && (
              <motion.div 
                key={selectedId}
                initial={{ y: 50, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 50, opacity: 0 }}
                className={`absolute bottom-4 left-4 right-4 md:bottom-12 transition-all duration-300 ${
                  !isMobile 
                    ? `${showLeftPanel ? 'left-[340px]' : 'left-12'} ${showRightPanel ? 'right-[420px]' : 'right-12'}` 
                    : 'left-4 right-4'
                } pointer-events-auto`}
              >
                <div className="rounded-2xl md:rounded-[3rem] border border-white/10 bg-black/80 md:bg-black/60 px-6 py-4 md:px-10 md:py-6 backdrop-blur-2xl shadow-2xl max-w-sm md:max-w-6xl mx-auto flex flex-col md:flex-row items-center gap-4 md:gap-16">
                  <div className="flex-1 min-w-0 w-full text-center md:text-left">
                    <div className="flex flex-col md:flex-row items-center gap-2 md:gap-4 mb-1 md:mb-2">
                      <span className="bg-indigo-500 text-white text-[8px] md:text-[10px] font-black px-2 py-0.5 md:px-3 md:py-1 rounded-full tracking-widest uppercase">Target Pocket</span>
                      <h3 className="text-xl md:text-3xl font-black text-white tracking-tighter truncate w-full md:w-auto">{selectedMolecule?.name || "Molécula"}</h3>
                    </div>
                    <p className="hidden md:block text-sm font-mono text-slate-500 truncate">{selectedMolecule?.smiles}</p>
                  </div>
                  <div className="flex items-center justify-between md:justify-end gap-8 md:gap-12 w-full md:w-auto border-t md:border-t-0 md:border-l border-white/10 pt-3 md:pt-0 md:pl-12">
                    <div className="text-left md:text-right">
                      <p className="text-[8px] md:text-[10px] font-black text-slate-500 uppercase tracking-widest mb-0.5 md:mb-1">AFINIDAD</p>
                      <div className="text-2xl md:text-4xl font-black text-indigo-400 tabular-nums">
                        {selectedMolecule?.metrics?.affinity?.toFixed(1)} <span className="text-xs font-bold text-slate-600">kcal</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-[8px] md:text-[10px] font-black text-slate-500 uppercase tracking-widest mb-0.5 md:mb-1">GLOBAL SCORE</p>
                      <div className={`text-2xl md:text-4xl font-black tabular-nums ${
                        (selectedMolecule?.metrics?.score || 0) >= 95 ? 'text-yellow-400 italic' :
                        (selectedMolecule?.metrics?.score || 0) >= 80 ? 'text-fuchsia-400' :
                        (selectedMolecule?.metrics?.score || 0) >= 60 ? 'text-emerald-400' :
                        (selectedMolecule?.metrics?.score || 0) >= 40 ? 'text-amber-400' :
                        'text-rose-400'
                      }`}>
                        {selectedMolecule?.metrics?.score?.toFixed(1) || "0.0"}
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Toggle Right Button */}
        <div className="hidden md:flex items-center z-50 pointer-events-auto">
          <button 
            onClick={() => setShowRightPanel(!showRightPanel)}
            className="h-16 w-6 bg-indigo-600/20 backdrop-blur-md border border-indigo-500/30 rounded-l-xl flex items-center justify-center text-indigo-400 hover:text-white transition-colors shadow-lg"
          >
            <ChevronRight size={14} className={`transition-transform ${showRightPanel ? '' : 'rotate-180'}`} />
          </button>
        </div>

        {/* Sidebar Right: Perfil Farmacocinético (Collapsible) */}
        <motion.aside 
          initial={false}
          animate={isMobile ? {
            width: activeView === 'INFO' ? "100%" : 0,
            opacity: activeView === 'INFO' ? 1 : 0,
            x: activeView === 'INFO' ? 0 : 1000
          } : { 
            width: showRightPanel ? 400 : 0,
            opacity: showRightPanel ? 1 : 0,
            x: showRightPanel ? 0 : 400
          }}
          transition={{ type: "spring", stiffness: 300, damping: 35 }}
          className={`border-l border-white/5 bg-[#0a0f1d]/95 md:bg-[#0a0f1d]/60 backdrop-blur-3xl p-6 md:p-10 overflow-y-auto custom-scrollbar pointer-events-auto flex flex-col ${isMobile ? 'absolute inset-x-0 bottom-0 top-[60px] z-40' : 'h-full'} ${isMobile && activeView !== 'INFO' ? 'pointer-events-none' : ''}`}
        >
          <AnimatePresence mode="wait">
            <motion.div key={selectedId} initial={{ x: 30, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="space-y-10 min-w-[320px]">
              
              {/* MÓDULO 1: CONTEXTO DEL TARGET */}
              <section className="rounded-3xl bg-indigo-500/5 border border-indigo-500/20 p-6">
                <h4 className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.3em] text-indigo-400 mb-4">
                  <Database size={14} /> CONTEXTO DEL TARGET
                </h4>
                <div className="space-y-3">
                  <div>
                    <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Proteína Receptora</p>
                    <p className="text-sm font-black text-white leading-tight">{selectedMolecule?.target?.name || "Sin Nombre"}</p>
                  </div>
                  <div className="flex items-center justify-between pt-2 border-t border-white/5">
                    <div>
                      <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Fiabilidad del Modelo</p>
                      <p className="text-xs font-mono text-emerald-400">Spearman ρ = {selectedMolecule?.target?.spearman_rho?.toFixed(3) || "N/A"}</p>
                    </div>
                    <div className="h-10 w-10 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
                      <ShieldCheck size={18} className="text-emerald-500" />
                    </div>
                  </div>
                </div>
              </section>

              {/* MÓDULO 2: AUDITORÍA CIENTÍFICA (DINÁMICO) */}
              <section>
                <h4 className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.3em] text-slate-400 mb-6">
                  <AlertCircle size={16} className="text-amber-500" /> AUDITORÍA CIENTÍFICA
                </h4>
                <div className="space-y-3">
                  {selectedMolecule?.scientific_warnings?.length > 0 ? (
                    selectedMolecule.scientific_warnings.map((warning: string, i: number) => (
                      <div key={i} className="flex gap-3 p-4 rounded-2xl bg-amber-500/5 border border-amber-500/10 text-[11px] leading-relaxed text-amber-200/70">
                        <div className="mt-1 flex-shrink-0 h-1.5 w-1.5 rounded-full bg-amber-500" />
                        {warning}
                      </div>
                    ))
                  ) : (
                    <div className="p-4 rounded-2xl bg-emerald-500/5 border border-emerald-500/10 text-[11px] text-emerald-400/70 italic text-center">
                      Sin alertas críticas detectadas.
                    </div>
                  )}
                </div>
              </section>

              {/* MÓDULO 3: PERFIL FARMACOCINÉTICO (INTERPRETADO) */}
              <section>
                <div className="flex items-center justify-between mb-6">
                  <h4 className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.3em] text-slate-400">
                    <Activity size={16} className="text-indigo-500" /> FARMACOCINÉTICA
                  </h4>
                  <div className="flex gap-1">
                    {selectedMolecule?.metrics?.lipinski_pass && (
                      <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">LIPINSKI</span>
                    )}
                    {selectedMolecule?.metrics?.veber_pass && (
                      <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">VEBER</span>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: "Lipofilia", value: selectedMolecule?.metrics?.log_p?.toFixed(2), unit: "LogP" },
                    { label: "Masa", value: selectedMolecule?.metrics?.mw?.toFixed(0), unit: "Da" },
                    { label: "Polaridad", value: selectedMolecule?.metrics?.tpsa?.toFixed(1), unit: "Å²" },
                    { label: "Hotspots", value: `${selectedMolecule?.hotspots_hit?.length || 0}/${selectedMolecule?.target?.hotspots?.length || 0}`, unit: "HITS" },
                    { label: "GNN 3D", value: selectedMolecule?.metrics?.gnn_score !== null && selectedMolecule?.metrics?.gnn_score !== undefined ? selectedMolecule.metrics.gnn_score.toFixed(1) : "N/A", unit: "PTS" },
                    { label: "Lipinski", value: selectedMolecule?.metrics?.lipinski_pass ? "Apto" : "No Apto", unit: "RULE" },
                  ].map(stat => (
                    <div key={stat.label} className="rounded-2xl bg-black/40 p-4 border border-white/5 group hover:border-indigo-500/30 transition-all">
                      <p className="text-[8px] font-black text-slate-600 uppercase mb-1 tracking-widest">{stat.label}</p>
                      <p className="text-lg font-black text-slate-200">{stat.value} <span className="text-[10px] text-slate-600 ml-1">{stat.unit}</span></p>
                    </div>
                  ))}
                </div>
              </section>

              {/* MÓDULO 4: EVIDENCIA BLOCKCHAIN */}
              <section>
                <div className="rounded-[2.5rem] bg-gradient-to-br from-indigo-600/20 to-transparent border border-indigo-500/20 p-8 text-center">
                  <p className="text-[9px] font-black text-indigo-400 uppercase tracking-[0.4em] mb-4">Evidencia Digital</p>
                  
                  {selectedMolecule?.blockchain?.tx_signature ? (
                    <>
                      <div className="bg-black/60 rounded-xl p-3 mb-6 border border-white/5 font-mono text-[8px] text-slate-500 break-all leading-tight">
                        {selectedMolecule.blockchain.tx_signature}
                      </div>
                      <a 
                        href={`https://explorer.solana.com/tx/${selectedMolecule.blockchain.tx_signature}?cluster=devnet`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="w-full text-[10px] font-black text-white bg-indigo-600 py-4 rounded-2xl shadow-xl shadow-indigo-500/20 hover:bg-indigo-500 transition-all uppercase tracking-widest flex items-center justify-center gap-2 mb-3"
                      >
                        <FlaskConical size={14} /> VERIFICAR EN SOLANA
                      </a>
                    </>
                  ) : (
                    <>
                      <div className="bg-black/60 rounded-xl p-3 mb-6 border border-white/5 font-mono text-[8px] text-slate-500 break-all leading-tight">
                        SYSTEM_AUTHENTICATED_LOCAL
                      </div>
                      <button 
                        onClick={handleCertify}
                        disabled={certifying}
                        className={`w-full text-[10px] font-black text-white bg-gradient-to-r from-[#9945FF] to-[#14F195] py-4 rounded-2xl shadow-xl shadow-[#14F195]/20 hover:opacity-90 transition-all uppercase tracking-widest flex items-center justify-center gap-2 mb-3 ${certifying ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        <Database size={14} /> {certifying ? 'CERTIFICANDO...' : 'CERTIFICAR EN SOLANA'}
                      </button>
                    </>
                  )}
                  
                  <a 
                    href={`${API_URL}/blockchain/certificate/${selectedId}`}
                    download
                    className="w-full text-[10px] font-black text-slate-400 bg-slate-800/50 py-3 rounded-2xl hover:bg-slate-800 transition-all uppercase tracking-widest flex items-center justify-center gap-2"
                  >
                    DESCARGAR REPORTE CIENTÍFICO
                  </a>
                  
                  <a 
                    href={`${API_URL}/evaluation/files/complex/${selectedId}`}
                    download={`complex_${selectedId}.pdb`}
                    className="w-full mt-3 text-[10px] font-black text-slate-400 bg-slate-800/50 py-3 rounded-2xl hover:bg-slate-800 transition-all uppercase tracking-widest flex items-center justify-center gap-2"
                  >
                    <Box size={14} /> DESCARGAR COMPLEJO 3D (PDB)
                  </a>
                </div>
              </section>

            </motion.div>
          </AnimatePresence>
        </motion.aside>
      </div>

      {/* Comparador Modal */}
      {compareMode && selectionForCompare.length === 2 && (
        <MolecularComparison 
          molA={molecules.find(m => m.id === selectionForCompare[0])}
          molB={molecules.find(m => m.id === selectionForCompare[1])}
          onClose={() => { setCompareMode(false); setSelectionForCompare([]); }}
        />
      )}
    </div>
  );
}
