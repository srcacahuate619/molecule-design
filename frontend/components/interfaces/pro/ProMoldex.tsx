"use client";

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import AdvancedMolstarViewer from "./AdvancedMolstarViewer";
import { Search, Database, Box, Info, BarChart3, Binary, ShieldCheck, AlertTriangle, FileDown, Layers, Crosshair, ChevronRight } from "lucide-react";
import { API_URL } from "../../../lib/config";

type Props = {
  molecules: any[];
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
  search: string;
  setSearch: (search: string) => void;
  targetFilter: string;
  setTargetFilter: (filter: string) => void;
  selectedMolecule: any;
  proteinData: string | null;
  poseData: string | null;
  loading3D: boolean;
  certifying: boolean;
  handleCertify: () => Promise<void>;
  targets: string[];
};

export default function ProMoldex({
  molecules,
  selectedId,
  setSelectedId,
  search,
  setSearch,
  targetFilter,
  setTargetFilter,
  selectedMolecule,
  proteinData,
  poseData,
  loading3D,
  certifying,
  handleCertify,
  targets,
}: Props) {
  const [activeView, setActiveView] = useState<"LIST" | "3D" | "INFO">("3D");
  const [activeTab, setActiveTab] = useState<"THERMO" | "GRID" | "ALERTS">("THERMO");

  // Filtrado de moléculas
  const filteredMolecules = useMemo(() => {
    return molecules.filter((m) => {
      const name = m.name?.toLowerCase() || "";
      const smiles = m.smiles || "";
      const matchesSearch = name.includes(search.toLowerCase()) || smiles.includes(search);
      const matchesTarget = targetFilter === "ALL" || m.target?.pdb_id === targetFilter;
      return matchesSearch && matchesTarget;
    });
  }, [molecules, search, targetFilter]);

  // Eficiencia Lipofílica (LLE) termodinámica corregida: LLE = (-Affinity / 1.36) - LogP
  const computedLLE = useMemo(() => {
    if (!selectedMolecule?.metrics) return null;
    const affinity = selectedMolecule.metrics.affinity || 0;
    const logp = selectedMolecule.metrics.log_p || 0;
    return -affinity / 1.36 - logp;
  }, [selectedMolecule]);

  return (
    <div className="fixed inset-x-0 bottom-0 top-[57px] z-50 bg-[#02050b] text-[#8e9bb4] font-sans overflow-hidden flex flex-col md:flex-row border-t border-white/5">
      
      {/* Mobile Navigation Header */}
      <div className="h-[52px] flex md:hidden items-center justify-between px-6 bg-[#040813] border-b border-white/5 z-50 w-full">
        <h1 className="text-xs font-black tracking-[0.2em] text-white flex items-center gap-2">
          <Layers size={14} className="text-indigo-400" />
          WORKBENCH PRO
        </h1>
        <div className="flex gap-1.5">
          {[
            { id: "LIST", icon: <Database size={12} />, label: "Datos" },
            { id: "3D", icon: <Box size={12} />, label: "Mol*" },
            { id: "INFO", icon: <Info size={12} />, label: "Ficha" },
          ].map((btn) => (
            <button
              key={btn.id}
              onClick={() => setActiveView(btn.id as any)}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-bold transition-all ${
                activeView === btn.id
                  ? "bg-indigo-600/20 border border-indigo-500/30 text-indigo-300"
                  : "bg-transparent border border-transparent text-slate-500"
              }`}
            >
              {btn.icon}
              <span>{btn.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 1. COLUMN LEFT: Hoja de cálculo de Bioteca (Spreadsheet) */}
      <aside
        className={`w-full md:w-[340px] flex-shrink-0 border-r border-white/5 bg-[#03060c] flex flex-col transition-all duration-300 ${
          activeView === "LIST" ? "block absolute inset-x-0 bottom-0 top-[52px] z-40" : "hidden md:flex h-full"
        }`}
      >
        <div className="p-5 border-b border-white/5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-[10px] font-black uppercase tracking-[0.25em] text-white flex items-center gap-2">
              <Database size={12} className="text-indigo-500" /> Bioteca Científica
            </h2>
            <span className="text-[9px] font-bold text-slate-500 font-mono">{filteredMolecules.length} REGs</span>
          </div>

          {/* Search Input */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={12} />
            <input
              type="text"
              placeholder="Buscar molécula / SMILES..."
              className="w-full rounded-xl bg-[#080d1a] border border-white/5 py-2 pl-9 pr-3 text-[11px] text-slate-300 outline-none focus:border-indigo-500/30 transition-all font-mono"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {/* Target Filter Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
            {targets.map((t) => (
              <button
                key={t}
                onClick={() => setTargetFilter(t)}
                className={`flex-shrink-0 rounded-lg px-2.5 py-1 text-[8px] font-bold uppercase tracking-wider border transition-all ${
                  targetFilter === t
                    ? "bg-indigo-600/10 border-indigo-500/30 text-indigo-400"
                    : "bg-[#080d1a] border-white/5 text-slate-500 hover:text-slate-300"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Spreadsheet Table Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/5 text-[8px] font-black uppercase tracking-wider text-slate-500">
                <th className="py-2 px-3">Estructura</th>
                <th className="py-2 px-3 text-right">Score</th>
                <th className="py-2 px-3 text-center">Target</th>
              </tr>
            </thead>
            <tbody className="text-[10px] font-mono">
              {filteredMolecules.map((m) => {
                const isSelected = selectedId === m.id;
                const score = m.metrics?.score || 0;
                return (
                  <tr
                    key={m.id}
                    onClick={() => {
                      setSelectedId(m.id);
                      if (window.innerWidth < 768) setActiveView("3D");
                    }}
                    className={`cursor-pointer border-b border-white/5 transition-all ${
                      isSelected
                        ? "bg-indigo-600/10 text-indigo-300 border-l-2 border-l-indigo-500"
                        : "hover:bg-[#070b15]/40 text-slate-400"
                    }`}
                  >
                    <td className="py-2.5 px-3 truncate max-w-[140px] font-sans font-medium text-slate-200">
                      {m.name || `Ligando ${m.id.substring(0, 4)}`}
                    </td>
                    <td className={`py-2.5 px-3 text-right font-bold ${
                      score >= 80 ? "text-emerald-400" : score >= 60 ? "text-amber-400" : "text-rose-400"
                    }`}>
                      {score.toFixed(1)}
                    </td>
                    <td className="py-2.5 px-3 text-center text-slate-500 uppercase font-black text-[9px]">
                      {m.target?.pdb_id || "N/A"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </aside>

      {/* 2. COLUMN CENTER: Visor Molstar (WebGL2) */}
      <main
        className={`flex-1 relative bg-[#020408] transition-all duration-300 ${
          activeView === "3D" ? "block absolute inset-x-0 bottom-0 top-[52px] z-30" : "hidden md:block h-full"
        }`}
      >
        <div className="absolute inset-0">
          <AdvancedMolstarViewer
            proteinData={proteinData ?? undefined}
            poseData={poseData ?? undefined}
            height={window.innerHeight - 57}
            hotspots={(selectedMolecule?.target?.hotspots || []).map((h: any) => h.name)}
            hotspotsHit={selectedMolecule?.hotspots_hit || []}
          />
        </div>

        {/* Floating Molecule HUD Card (Bottom) */}
        {selectedMolecule && (
          <div className="absolute bottom-4 left-4 right-4 md:bottom-6 pointer-events-none z-10">
            <div className="max-w-2xl mx-auto rounded-2xl border border-white/10 bg-black/70 backdrop-blur-md p-4 flex flex-col md:flex-row justify-between items-center gap-3 shadow-2xl pointer-events-auto">
              <div className="min-w-0 w-full text-center md:text-left">
                <div className="flex items-center gap-2 justify-center md:justify-start mb-0.5">
                  <span className="bg-indigo-500/20 border border-indigo-500/30 text-indigo-400 text-[8px] font-black px-2 py-0.5 rounded uppercase tracking-wider">
                    {selectedMolecule?.target?.pdb_id || "TARGET"} Pocket
                  </span>
                  <h3 className="text-sm font-black text-white truncate max-w-[200px]">
                    {selectedMolecule?.name || "Molécula"}
                  </h3>
                </div>
                <p className="text-[9px] font-mono text-slate-500 truncate w-full">
                  SMILES: {selectedMolecule?.smiles}
                </p>
              </div>

              <div className="flex gap-6 border-t md:border-t-0 md:border-l border-white/5 pt-2.5 md:pt-0 md:pl-6 w-full md:w-auto justify-center">
                <div className="text-center md:text-right">
                  <p className="text-[7px] font-black text-slate-500 uppercase tracking-widest mb-0.5">KCAL/MOL (VINA)</p>
                  <span className="text-lg font-black text-indigo-300 font-mono tabular-nums">
                    {selectedMolecule?.metrics?.affinity?.toFixed(1) || "0.0"}
                  </span>
                </div>
                <div className="text-center md:text-right">
                  <p className="text-[7px] font-black text-slate-500 uppercase tracking-widest mb-0.5">SCORE GLOBAL</p>
                  <span className={`text-lg font-black font-mono tabular-nums ${
                    (selectedMolecule?.metrics?.score || 0) >= 80 ? "text-emerald-400" : "text-amber-400"
                  }`}>
                    {selectedMolecule?.metrics?.score?.toFixed(1) || "0.0"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* 3. COLUMN RIGHT: Ficha de Análisis Científico */}
      <aside
        className={`w-full md:w-[380px] flex-shrink-0 border-l border-white/5 bg-[#03060c] flex flex-col p-5 md:p-6 overflow-y-auto custom-scrollbar transition-all duration-300 ${
          activeView === "INFO" ? "block absolute inset-x-0 bottom-0 top-[52px] z-40" : "hidden md:flex h-full"
        }`}
      >
        <AnimatePresence mode="wait">
          {selectedMolecule ? (
            <motion.div
              key={selectedMolecule.id}
              initial={{ x: 20, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 20, opacity: 0 }}
              className="space-y-6"
            >
              {/* Sección A: Target Context */}
              <section className="rounded-xl border border-indigo-500/10 bg-[#050914] p-4 space-y-3">
                <h4 className="flex items-center gap-2 text-[9px] font-black uppercase tracking-[0.2em] text-indigo-400">
                  <Layers size={12} /> CONTEXTO ESTRUCTURAL DEL RECEPTOR
                </h4>
                <div>
                  <p className="text-[8px] font-bold text-slate-500 uppercase tracking-wider">Complejo Proteico</p>
                  <p className="text-xs font-black text-white leading-tight">{selectedMolecule.target?.name}</p>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-white/5">
                  <div>
                    <p className="text-[8px] font-bold text-slate-500 uppercase tracking-wider">Correlación de Benchmark</p>
                    <p className="text-xs font-mono text-emerald-400 font-bold">Spearman ρ = {selectedMolecule.target?.spearman_rho?.toFixed(3) || "N/A"}</p>
                  </div>
                  <div className="h-8 w-8 rounded-full bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400">
                    <ShieldCheck size={16} />
                  </div>
                </div>
              </section>

              {/* Sub-Tabs: Termodinámica vs Grid Box vs Alertas */}
              <div className="flex border-b border-white/5 p-0.5">
                {[
                  { id: "THERMO", label: "Termodinámica" },
                  { id: "GRID", label: "Grid Box" },
                  { id: "ALERTS", label: "Alertas" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`flex-1 py-1.5 text-[9px] font-black uppercase tracking-wider transition-all border-b-2 ${
                      activeTab === tab.id
                        ? "border-indigo-500 text-indigo-400"
                        : "border-transparent text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Contenidos de las Sub-Tabs */}
              <div className="space-y-4">
                {activeTab === "THERMO" && (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-2.5">
                      {[
                        { label: "Afinidad Vina", value: `${selectedMolecule.metrics?.affinity?.toFixed(2)} kcal/mol`, desc: "Fuerza de unión primaria" },
                        { label: "LLE Corregido", value: computedLLE?.toFixed(2) || "N/A", desc: "Eficiencia lipofílica (-Aff/1.36) - LogP" },
                        { label: "Lipofilia (LogP)", value: selectedMolecule.metrics?.log_p?.toFixed(2), desc: "Logaritmo de partición octanol/agua" },
                        { label: "Masa Molecular", value: `${selectedMolecule.metrics?.mw?.toFixed(1)} Da`, desc: "Peso molecular de la entidad" },
                        { label: "Área Polar (TPSA)", value: `${selectedMolecule.metrics?.tpsa?.toFixed(1)} Å²`, desc: "Superficie polar topológica" },
                        { label: "Hotspots Hits", value: `${selectedMolecule.hotspots_hit?.length || 0} / ${selectedMolecule.target?.hotspots?.length || 0}`, desc: "Residuos críticos contactados" },
                      ].map((card) => (
                        <div key={card.label} className="p-3 rounded-xl border border-white/5 bg-[#060a12] group hover:border-indigo-500/20 transition-all">
                          <p className="text-[8px] font-black text-slate-500 uppercase tracking-widest mb-0.5">{card.label}</p>
                          <p className="text-xs font-black text-slate-200 font-mono">{card.value}</p>
                          <p className="text-[7px] text-slate-600 mt-1 font-sans">{card.desc}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {activeTab === "GRID" && (
                  <div className="space-y-4">
                    {/* Grid Box coordinates */}
                    <div className="rounded-xl border border-white/5 bg-[#060a12] p-4 space-y-3">
                      <div className="flex items-center gap-2 text-[9px] font-black text-indigo-400 uppercase tracking-widest">
                        <Crosshair size={12} /> Bounding Box de Docking
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-[10px] font-mono">
                        <div>
                          <p className="text-[8px] text-slate-500 uppercase">Centroide (X, Y, Z)</p>
                          <p className="text-slate-300">
                            {selectedMolecule.target?.grid_center_x?.toFixed(2) || "0.00"}, {selectedMolecule.target?.grid_center_y?.toFixed(2) || "0.00"}, {selectedMolecule.target?.grid_center_z?.toFixed(2) || "0.00"}
                          </p>
                        </div>
                        <div>
                          <p className="text-[8px] text-slate-500 uppercase">Dimensiones (X, Y, Z)</p>
                          <p className="text-slate-300">
                            {selectedMolecule.target?.box_size_x || "28"}Å, {selectedMolecule.target?.box_size_y || "28"}Å, {selectedMolecule.target?.box_size_z || "28"}Å
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Residuos Hotspots */}
                    <div className="space-y-2">
                      <p className="text-[8px] font-black text-slate-500 uppercase tracking-widest">Residuos Hotspots Definidos</p>
                      <div className="flex flex-wrap gap-1.5">
                        {(selectedMolecule.target?.hotspots || []).map((h: any) => {
                          const isHit = selectedMolecule.hotspots_hit?.includes(h.name);
                          return (
                            <span
                              key={h.name}
                              className={`text-[9px] font-black px-2.5 py-1 rounded-lg border font-mono ${
                                isHit
                                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                                  : "bg-[#060a12] border-white/5 text-slate-500"
                              }`}
                            >
                              🎯 {h.name}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === "ALERTS" && (
                  <div className="space-y-3">
                    {/* Alertas Científicas PAINS */}
                    {selectedMolecule.scientific_warnings?.length > 0 ? (
                      selectedMolecule.scientific_warnings.map((warn: string, idx: number) => (
                        <div key={idx} className="flex gap-3 p-4 rounded-xl bg-rose-500/5 border border-rose-500/15 text-[10px] leading-relaxed text-rose-200/70">
                          <AlertTriangle size={14} className="text-rose-500 mt-0.5 flex-shrink-0" />
                          <div>{warn}</div>
                        </div>
                      ))
                    ) : (
                      <div className="flex flex-col items-center justify-center p-6 border border-emerald-500/10 bg-emerald-500/5 rounded-xl text-center gap-2 text-emerald-400">
                        <ShieldCheck size={28} />
                        <span className="text-[9px] font-black uppercase tracking-wider">Filtro PAINS Aprobado</span>
                        <p className="text-[8px] text-emerald-500/70 font-medium">No se detectaron grupos reactivos propensos a falsos positivos.</p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Botón de Fusión y Descargas (Exportación Cruda) */}
              <section className="pt-4 border-t border-white/5 space-y-3">
                <p className="text-[8px] font-black text-slate-500 uppercase tracking-widest">Descargas y Evidencia</p>
                <div className="space-y-2">
                  <a
                    href={`${API_URL}/evaluation/files/complex/${selectedMolecule.id}`}
                    download={`complex_${selectedMolecule.id}.pdb`}
                    className="w-full text-[10px] font-black text-white bg-indigo-600 hover:bg-indigo-500 py-3 rounded-xl shadow-lg shadow-indigo-500/10 transition-all uppercase tracking-widest flex items-center justify-center gap-2"
                  >
                    <FileDown size={14} /> Descargar Complejo 3D (PDB)
                  </a>
                  <a
                    href={`${API_URL}/blockchain/certificate/${selectedMolecule.id}`}
                    download
                    className="w-full text-[10px] font-black text-slate-400 hover:text-white bg-[#080d19] border border-white/5 py-3 rounded-xl transition-all uppercase tracking-widest flex items-center justify-center gap-2"
                  >
                    <Binary size={14} /> Descargar Certificado Científico (PDF)
                  </a>
                </div>
              </section>
            </motion.div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-600 gap-2">
              <Info size={28} />
              <p className="text-xs">Selecciona un ligando de la bioteca para desplegar su ficha técnica.</p>
            </div>
          )}
        </AnimatePresence>
      </aside>
    </div>
  );
}
