"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getPokedex, getProteinFile, getPoseFile } from "@/lib/api";
import { MoleculeViewer3D } from "@/components/MoleculeViewer3D";
import PokedexCard from "@/components/PokedexCard";
import MolecularComparison from "@/components/MolecularComparison";
import { Search, ShieldCheck, Activity, Info, BarChart3, ChevronRight, Binary, Database, Box, FlaskConical, AlertCircle } from "lucide-react";

export default function PokedexPage() {
  const [molecules, setMolecules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [targetFilter, setTargetFilter] = useState("ALL");
  
  // Comparison state
  const [compareMode, setCompareMode] = useState(false);
  const [selectionForCompare, setSelectionForCompare] = useState<string[]>([]);

  // 3D View state
  const [proteinData, setProteinData] = useState<string | null>(null);
  const [poseData, setPoseData] = useState<string | null>(null);
  const [loading3D, setLoading3D] = useState(false);

  useEffect(() => {
    getPokedex()
      .then((data) => {
        setMolecules(data.results);
        if (data.results.length > 0) {
          setSelectedId(data.results[0].id);
        }
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
        getProteinFile(selectedMolecule.target.pdb_id),
        getPoseFile(selectedMolecule.smiles_hash, selectedMolecule.target.pdb_id)
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
      const matchesSearch = m.name.toLowerCase().includes(search.toLowerCase()) || 
                           m.smiles.includes(search);
      const matchesTarget = targetFilter === "ALL" || m.target.pdb_id === targetFilter;
      return matchesSearch && matchesTarget;
    });
  }, [molecules, search, targetFilter]);

  const targets = useMemo(() => {
    const t = new Set(molecules.map(m => m.target.pdb_id));
    return ["ALL", ...Array.from(t)];
  }, [molecules]);

  const handleToggleCompare = (id: string) => {
    setSelectionForCompare(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id].slice(-2)
    );
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

  return (
    <div className="flex h-screen bg-[#05080f] text-slate-300 font-sans selection:bg-indigo-500/30 overflow-hidden">
      {/* Sidebar: Biblioteca de Especies Moleculares */}
      <aside className="w-80 flex flex-col border-r border-slate-800/50 bg-[#0a0f1d]/80 backdrop-blur-xl z-20">
        <div className="p-6 border-b border-slate-800/30">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-xl font-black tracking-tighter text-white flex items-center gap-2">
              <FlaskConical size={20} className="text-indigo-500" />
              POKEDEX <span className="text-[10px] bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded-full border border-indigo-500/30">V5.0</span>
            </h1>
          </div>
          
          <div className="space-y-4">
            <div className="relative group">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-indigo-400 transition-colors" size={14} />
              <input 
                type="text"
                placeholder="Filtrar por nombre o SMILES..."
                className="w-full rounded-xl bg-slate-900/50 border border-slate-800 py-2.5 pl-10 pr-4 text-xs text-slate-200 outline-none focus:border-indigo-500/50 focus:bg-slate-900 transition-all"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            
            <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide no-scrollbar">
              {targets.map(t => (
                <button
                  key={t}
                  onClick={() => setTargetFilter(t)}
                  className={`whitespace-nowrap rounded-full px-3 py-1 text-[9px] font-black uppercase tracking-widest transition-all border ${
                    targetFilter === t 
                      ? 'bg-indigo-500 border-indigo-400 text-white shadow-[0_0_15px_rgba(99,102,241,0.3)]' 
                      : 'bg-slate-900/50 border-slate-800 text-slate-500 hover:border-slate-600 hover:text-slate-300'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
          <AnimatePresence mode="popLayout">
            {filteredMolecules.map((m) => (
              <PokedexCard 
                key={m.id}
                molecule={m}
                isSelected={selectedId === m.id}
                onClick={setSelectedId}
                onCompareToggle={() => handleToggleCompare(m.id)}
                isComparing={selectionForCompare.includes(m.id)}
              />
            ))}
          </AnimatePresence>
          {filteredMolecules.length === 0 && (
            <div className="py-20 text-center opacity-20">
              <AlertCircle size={48} className="mx-auto mb-4" />
              <p className="text-xs font-bold uppercase tracking-widest">Sin coincidencias</p>
            </div>
          )}
        </div>
      </aside>

      {/* Main Stage: El Estándar Científico (Docked SDF) */}
      <main className="flex-1 relative bg-[#020408]">
        {/* Header HUD */}
        <div className="absolute top-6 left-6 right-6 flex items-start justify-between z-10 pointer-events-none">
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-4 pointer-events-auto"
          >
            <div className="rounded-2xl bg-slate-950/80 border border-slate-800 p-3 backdrop-blur-md">
               <Box className="text-indigo-500" size={24} />
            </div>
            <div>
              <p className="text-[10px] font-black text-indigo-500 uppercase tracking-[0.2em] mb-0.5">Visualización de Pose Acoplada</p>
              <h2 className="text-xl font-black text-white tracking-tight flex items-center gap-2">
                ESTÁNDAR CIENTÍFICO <span className="text-[10px] font-bold text-slate-500">FORMATO SDF</span>
              </h2>
            </div>
          </motion.div>

          <div className="flex gap-2 pointer-events-auto">
            {selectionForCompare.length === 2 && (
              <button 
                onClick={() => setCompareMode(true)}
                className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-[10px] font-black tracking-widest shadow-lg shadow-indigo-600/20 transition-all flex items-center gap-2"
              >
                COMPARAR SELECCIÓN <ChevronRight size={14} />
              </button>
            )}
          </div>
        </div>

        {/* 3D Viewport */}
        <div className="absolute inset-0">
          <MoleculeViewer3D 
            proteinData={proteinData}
            poseData={poseData}
            height={window.innerHeight}
            hotspots={selectedMolecule?.hotspots_hit}
            hotspotsHit={selectedMolecule?.hotspots_hit}
          />
        </div>

        {/* Info HUD Overlay */}
        <AnimatePresence mode="wait">
          <motion.div 
            key={selectedId}
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 100, opacity: 0 }}
            className="absolute bottom-8 left-8 right-8 z-10"
          >
            <div className="rounded-[2.5rem] border border-slate-800/50 bg-[#0a0f1d]/60 p-8 backdrop-blur-2xl shadow-2xl overflow-hidden relative group">
              {/* Background gradient subtle */}
              <div className="absolute -inset-24 bg-gradient-to-br from-indigo-500/10 to-transparent opacity-50 blur-3xl pointer-events-none" />
              
              <div className="relative flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-4 mb-4">
                    <span className="bg-indigo-500 text-white text-[9px] font-black px-3 py-1 rounded-full tracking-widest">
                      DOCKING EXITOSO
                    </span>
                    <div className="h-1 w-1 rounded-full bg-slate-700" />
                    <span className="text-slate-500 text-[10px] font-bold uppercase tracking-widest flex items-center gap-1">
                      <Database size={12} /> {selectedMolecule?.target.pdb_id} Pocket
                    </span>
                  </div>
                  <h3 className="text-4xl font-black text-white tracking-tighter mb-2 group-hover:text-indigo-400 transition-colors">
                    {selectedMolecule?.name}
                  </h3>
                  <p className="text-xs font-mono text-slate-500 truncate max-w-lg">
                    {selectedMolecule?.smiles}
                  </p>
                </div>

                <div className="flex items-stretch gap-8">
                  <div className="flex flex-col justify-center border-l border-slate-800 pl-8">
                    <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em] mb-2 text-right">AFINIDAD (ΔG)</p>
                    <div className="text-4xl font-black text-indigo-400 tabular-nums">
                      {selectedMolecule?.metrics.affinity.toFixed(2)}
                      <span className="text-sm font-bold text-slate-600 ml-1 italic">kcal/mol</span>
                    </div>
                  </div>
                  <div className="flex flex-col justify-center border-l border-slate-800 pl-8">
                    <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em] mb-2 text-right">GLOBAL SCORE</p>
                    <div className="text-4xl font-black text-emerald-400 tabular-nums">
                      {selectedMolecule?.metrics.score.toFixed(1)}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Right Panel: Ficha de Especie Farmacológica */}
      <aside className="w-96 border-l border-slate-800/50 bg-[#0a0f1d]/90 p-8 overflow-y-auto custom-scrollbar z-20">
        <AnimatePresence mode="wait">
          <motion.div
            key={selectedId}
            initial={{ x: 30, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -30, opacity: 0 }}
            className="space-y-10"
          >
            <section>
              <div className="flex items-center justify-between mb-6">
                <h4 className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.3em] text-slate-500">
                  <BarChart3 size={14} className="text-indigo-500" /> PERFIL FARMACOCINÉTICO
                </h4>
                <div className="h-[1px] flex-1 bg-slate-800 ml-4" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "LIPOPHILICITY", value: selectedMolecule?.metrics.log_p.toFixed(2), sub: "LogP" },
                  { label: "MOLECULAR WEIGHT", value: `${selectedMolecule?.metrics.mw.toFixed(1)}`, sub: "Daltons" },
                  { label: "SURFACE AREA", value: `${selectedMolecule?.metrics.tpsa.toFixed(1)}`, sub: "Å² (TPSA)" },
                  { label: "POCKET IMPACT", value: `${selectedMolecule?.hotspots_hit.length}`, sub: "Hotspots" },
                ].map(stat => (
                  <div key={stat.label} className="rounded-2xl bg-slate-900/50 p-4 border border-slate-800/50 hover:border-slate-700 transition-colors group">
                    <p className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-1 group-hover:text-indigo-400 transition-colors">{stat.label}</p>
                    <div className="flex items-baseline gap-1">
                      <p className="text-lg font-black text-slate-200">{stat.value}</p>
                      <p className="text-[9px] font-bold text-slate-600">{stat.sub}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <div className="flex items-center justify-between mb-6">
                <h4 className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.3em] text-slate-500">
                  <ShieldCheck size={14} className="text-emerald-500" /> CERTIFICACIÓN BLOCKCHAIN
                </h4>
                <div className="h-[1px] flex-1 bg-slate-800 ml-4" />
              </div>
              <div className="rounded-3xl bg-gradient-to-br from-indigo-500/10 to-transparent border border-indigo-500/20 p-6 relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                  <Binary size={64} />
                </div>
                <div className="relative z-10">
                  <div className="flex items-center gap-2 mb-4">
                    <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">VERIFIED ON SOLANA</span>
                  </div>
                  <div className="bg-black/40 rounded-xl p-3 mb-4 border border-white/5">
                    <p className="text-[9px] font-mono text-slate-400 break-all leading-relaxed">
                      {selectedMolecule?.blockchain.tx_signature || "AUTHENTICATING MOLECULE ON-CHAIN..."}
                    </p>
                  </div>
                  <button className="w-full flex items-center justify-center gap-2 text-[10px] font-black text-indigo-400 bg-indigo-500/10 py-3 rounded-xl hover:bg-indigo-500/20 transition-all border border-indigo-500/20">
                    EXPLORAR EVIDENCIA <ShieldCheck size={12} />
                  </button>
                </div>
              </div>
            </section>

            <section>
              <div className="flex items-center justify-between mb-6">
                <h4 className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.3em] text-slate-500">
                  <Info size={14} className="text-indigo-500" /> ANÁLISIS ESTRUCTURAL
                </h4>
                <div className="h-[1px] flex-1 bg-slate-800 ml-4" />
              </div>
              <div className="rounded-3xl bg-slate-900/50 p-6 border border-slate-800 space-y-4">
                <div className="flex items-center gap-4">
                  <div className="h-12 w-12 rounded-2xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-black">
                    {selectedMolecule?.target.pdb_id.substring(0, 2)}
                  </div>
                  <div>
                    <p className="text-sm font-black text-white">{selectedMolecule?.target.pdb_id}</p>
                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{selectedMolecule?.target.family}</p>
                  </div>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed italic">
                  "El ligando presenta una conformación optimizada en el bolsillo catalítico, interactuando con {selectedMolecule?.hotspots_hit.length} residuos críticos definidos en la ontología del target."
                </p>
              </div>
            </section>

            <div className="pt-4">
              <button className="w-full rounded-[1.5rem] bg-indigo-600 py-5 font-black text-white shadow-[0_20px_50px_rgba(79,70,229,0.3)] hover:bg-indigo-500 hover:-translate-y-1 transition-all flex items-center justify-center gap-3 group">
                DESCARGAR REPORTE TÉCNICO <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </button>
              <p className="text-[9px] text-center text-slate-600 mt-4 font-bold uppercase tracking-widest">
                Protocolo de Ingesta MolDesign v4.7.1 - 2026
              </p>
            </div>
          </motion.div>
        </AnimatePresence>
      </aside>

      {/* Comparison Modal Overlay */}
      {compareMode && selectionForCompare.length === 2 && (
        <MolecularComparison 
          molA={molecules.find(m => m.id === selectionForCompare[0])}
          molB={molecules.find(m => m.id === selectionForCompare[1])}
          onClose={() => setCompareMode(false)}
        />
      )}
    </div>
  );
}
