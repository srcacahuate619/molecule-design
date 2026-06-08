"use client";

import React, { useState, useEffect, useMemo } from "react";
import { 
  Activity, 
  ShieldCheck, 
  Database, 
  Sliders, 
  Layers, 
  Play, 
  RefreshCw, 
  Save, 
  FileText, 
  Download, 
  CheckSquare, 
  Square,
  ChevronRight,
  Info,
  Maximize2,
  Search
} from "lucide-react";
import { KetcherEditor } from "../../KetcherEditor";
import { ScoreCard } from "../../ScoreCard";
import AdvancedMolstarViewer from "./AdvancedMolstarViewer";
import TargetSelectorModal from "./TargetSelectorModal";
import type { Target } from "../../../lib/api";
import type { JobStatus, MolecularSuggestion, ValidationResult } from "../../../lib/types";

interface ProEvaluationProps {
  smiles: string;
  setSmiles: (smiles: string) => void;
  target: string;
  setTarget: (target: string) => void;
  targets: Target[];
  loadingTargets: boolean;
  validation: ValidationResult | null;
  setValidation: (validation: ValidationResult | null) => void;
  taskId: string | null;
  setTaskId: (taskId: string | null) => void;
  status: JobStatus | null;
  setStatus: (status: JobStatus | null) => void;
  busy: boolean;
  setBusy: (busy: boolean) => void;
  error: string | null;
  setError: (error: string | null) => void;
  isControl: boolean;
  setIsControl: (isControl: boolean) => void;
  isSaved: boolean;
  setIsSaved: (isSaved: boolean) => void;
  proteinData: string | null;
  poseData: string | null;
  suggestions: MolecularSuggestion[];
  loadingSuggestions: boolean;
  handleSave: (customName?: string) => Promise<void>;
  handleCertify: (walletOverride?: string) => Promise<void>;
  handleDownloadCertificate: () => Promise<void>;
  handleDownloadComplex: () => Promise<void>;
  handleValidate: () => Promise<void>;
  handleSubmit: (
    gridCenter?: [number, number, number],
    gridSize?: [number, number, number],
    customHotspots?: string[],
    peptideDockingEngine?: "diffpepdock" | "colabfold"
  ) => Promise<void>;
  handleReset: () => void;
  handleUseSuggestion: (sug: MolecularSuggestion) => Promise<void>;
  startPolling: (tid: string) => void;
  stopPolling: () => void;
  showWalletInput: boolean;
  setShowWalletInput: (show: boolean) => void;
  customWallet: string;
  setCustomWallet: (wallet: string) => void;
}

export default function ProEvaluation({
  smiles,
  setSmiles,
  target,
  setTarget,
  targets,
  loadingTargets,
  validation,
  setValidation,
  taskId,
  setTaskId,
  status,
  setStatus,
  busy,
  setBusy,
  error,
  setError,
  isControl,
  setIsControl,
  isSaved,
  setIsSaved,
  proteinData,
  poseData,
  suggestions,
  loadingSuggestions,
  handleSave,
  handleCertify,
  handleDownloadCertificate,
  handleDownloadComplex,
  handleValidate,
  handleSubmit,
  handleReset,
  handleUseSuggestion,
  startPolling,
  stopPolling,
  showWalletInput,
  setShowWalletInput,
  customWallet,
  setCustomWallet
}: ProEvaluationProps) {
  
  // --- Target Selector Modal state ---
  const [isTargetModalOpen, setIsTargetModalOpen] = useState(false);

  // --- Grid Box override states ---
  const [gridCenterX, setGridCenterX] = useState<string>("");
  const [gridCenterY, setGridCenterY] = useState<string>("");
  const [gridCenterZ, setGridCenterZ] = useState<string>("");
  
  const [gridSizeX, setGridSizeX] = useState<string>("");
  const [gridSizeY, setGridSizeY] = useState<string>("");
  const [gridSizeZ, setGridSizeZ] = useState<string>("");

  // --- Hotspots toggles state ---
  const [selectedHotspots, setSelectedHotspots] = useState<Record<string, boolean>>({});

  // --- Active pose index inside Molstar ---
  const [selectedPoseIndex, setSelectedPoseIndex] = useState<number>(0);

  // --- Active results tab ---
  const [activeTab, setActiveTab] = useState<"visualizer" | "parameters" | "warnings">("visualizer");

  // --- Peptide docking engine state (Nivel 3) ---
  const [peptideDockingEngine, setPeptideDockingEngine] = useState<"diffpepdock" | "colabfold">("diffpepdock");

  // --- Peptide detector ---
  const isPeptide = useMemo(() => {
    if (!validation) return false;
    if (validation.heavy_atom_count && validation.heavy_atom_count > 60) return true;
    if (validation.canonical_smiles) {
      const matches = validation.canonical_smiles.match(/C\(=O\)N/gi);
      if (matches && matches.length >= 3) return true;
    }
    return false;
  }, [validation]);

  // Get currently selected target object
  const activeTargetObj = useMemo(() => {
    return targets.find(t => t.pdb_id === target);
  }, [targets, target]);

  // Sync grid box defaults when target changes
  useEffect(() => {
    if (activeTargetObj) {
      setGridCenterX(activeTargetObj.grid_center_x?.toString() || "0");
      setGridCenterY(activeTargetObj.grid_center_y?.toString() || "0");
      setGridCenterZ(activeTargetObj.grid_center_z?.toString() || "0");
      
      setGridSizeX(activeTargetObj.grid_size_x?.toString() || "20");
      setGridSizeY(activeTargetObj.grid_size_y?.toString() || "20");
      setGridSizeZ(activeTargetObj.grid_size_z?.toString() || "20");

      // Enable all hotspots by default
      const toggles: Record<string, boolean> = {};
      if (activeTargetObj.hotspots) {
        activeTargetObj.hotspots.forEach(h => {
          toggles[h.name] = true;
        });
      }
      setSelectedHotspots(toggles);
    } else {
      setGridCenterX("");
      setGridCenterY("");
      setGridCenterZ("");
      setGridSizeX("");
      setGridSizeY("");
      setGridSizeZ("");
      setSelectedHotspots({});
    }
    setSelectedPoseIndex(0);
  }, [activeTargetObj]);

  // Toggle hotspot checkbox
  const handleToggleHotspot = (name: string) => {
    setSelectedHotspots(prev => ({
      ...prev,
      [name]: !prev[name]
    }));
  };

  // Smart Centroid Auto-detector from selected hotspots
  const handleAutoDetectCentroid = () => {
    if (!activeTargetObj) return;

    // Filter active hotspots that have coordinate data
    const activeHotspotCoords = (activeTargetObj.hotspots || [])
      .filter(h => selectedHotspots[h.name] && h.x !== undefined && h.y !== undefined && h.z !== undefined)
      .map(h => ({ x: h.x!, y: h.y!, z: h.z! }));

    if (activeHotspotCoords.length === 0) {
      if (activeTargetObj.grid_center_x !== undefined) {
        setGridCenterX(activeTargetObj.grid_center_x.toString());
        setGridCenterY(activeTargetObj.grid_center_y?.toString() || "0");
        setGridCenterZ(activeTargetObj.grid_center_z?.toString() || "0");
        
        setGridSizeX(activeTargetObj.grid_size_x?.toString() || "20.0");
        setGridSizeY(activeTargetObj.grid_size_y?.toString() || "20.0");
        setGridSizeZ(activeTargetObj.grid_size_z?.toString() || "20.0");
        
        alert("Aviso: Los residuos críticos seleccionados no están resueltos estructuralmente en este PDB. Se ha restaurado la caja de grid predeterminada del receptor.");
      } else {
        alert("Error: No se pudieron detectar coordenadas de hotspots ni valores predeterminados para este receptor.");
      }
      return;
    }

    // Calculate average coordinate (centroid)
    const count = activeHotspotCoords.length;
    const avgX = activeHotspotCoords.reduce((sum, c) => sum + c.x, 0) / count;
    const avgY = activeHotspotCoords.reduce((sum, c) => sum + c.y, 0) / count;
    const avgZ = activeHotspotCoords.reduce((sum, c) => sum + c.z, 0) / count;

    setGridCenterX(avgX.toFixed(3));
    setGridCenterY(avgY.toFixed(3));
    setGridCenterZ(avgZ.toFixed(3));

    // Smart box sizing: enclose all selected hotspots with padding
    if (count > 1) {
      const minX = Math.min(...activeHotspotCoords.map(c => c.x));
      const maxX = Math.max(...activeHotspotCoords.map(c => c.x));
      const minY = Math.min(...activeHotspotCoords.map(c => c.y));
      const maxY = Math.max(...activeHotspotCoords.map(c => c.y));
      const minZ = Math.min(...activeHotspotCoords.map(c => c.z));
      const maxZ = Math.max(...activeHotspotCoords.map(c => c.z));

      // size = max - min + padding (e.g. 10.0 Å)
      const padding = 12.0;
      const sizeX = Math.max(16.0, Math.min(36.0, (maxX - minX) + padding));
      const sizeY = Math.max(16.0, Math.min(36.0, (maxY - minY) + padding));
      const sizeZ = Math.max(16.0, Math.min(36.0, (maxZ - minZ) + padding));

      setGridSizeX(sizeX.toFixed(1));
      setGridSizeY(sizeY.toFixed(1));
      setGridSizeZ(sizeZ.toFixed(1));
    } else {
      // For single hotspot, set a standard small pocket size
      setGridSizeX("18.0");
      setGridSizeY("18.0");
      setGridSizeZ("18.0");
    }
  };

  // Submit trigger with overrides
  const handleLaunchEvaluation = async () => {
    // Collect coordinates override if valid
    const cx = parseFloat(gridCenterX);
    const cy = parseFloat(gridCenterY);
    const cz = parseFloat(gridCenterZ);
    const sx = parseFloat(gridSizeX);
    const sy = parseFloat(gridSizeY);
    const sz = parseFloat(gridSizeZ);

    let centerOverride: [number, number, number] | undefined = undefined;
    let sizeOverride: [number, number, number] | undefined = undefined;

    if (!isNaN(cx) && !isNaN(cy) && !isNaN(cz)) {
      centerOverride = [cx, cy, cz];
    }
    if (!isNaN(sx) && !isNaN(sy) && !isNaN(sz) && sx > 0 && sy > 0 && sz > 0) {
      sizeOverride = [sx, sy, sz];
    }

    // Collect list of custom hotspots (only active ones)
    const customHotspotsList = Object.keys(selectedHotspots).filter(k => selectedHotspots[k]);

    await handleSubmit(centerOverride, sizeOverride, customHotspotsList, peptideDockingEngine);
  };

  // Extract currently active pose file data
  const activePoseData = useMemo(() => {
    if (!poseData) return undefined;
    const poses = poseData.split("$$$$");
    const p = poses[selectedPoseIndex] || poses[0];
    return p + "\n$$$$\n";
  }, [poseData, selectedPoseIndex]);

  const isTerminal = status?.status === "SUCCESS" || status?.status === "FAILURE";
  const canEvaluate = !!validation?.is_valid && target.length >= 4;

  // Render job progress steps
  const renderWorkflowProgress = () => {
    if (!status || isTerminal) return null;

    const progress = status.progress || 0;
    const currentStatus = status.status || "";

    const isColabFold = status?.result?.vina_version?.includes("COLABFOLD") || (isPeptide && peptideDockingEngine === "colabfold");
    const dockingLabel = isPeptide
      ? (isColabFold ? "Plegado y Docking (ColabFold)" : "Docking por Difusión (DiffPepDock)")
      : "Acoplamiento molecular (Vina)";

    const stages = [
      { id: "validation", label: "Validación Estructural", min: 0, active: progress >= 0 },
      { id: "conformation", label: "Generación de Conforme 3D", min: 20, active: progress >= 20 },
      { id: "docking", label: dockingLabel, min: 55, active: progress >= 55 },
      { id: "scoring", label: "Cerebro Espacial ML (Rescoring)", min: 80, active: progress >= 80 }
    ];

    return (
      <div className="rounded-2xl border border-indigo-500/10 bg-indigo-950/5 p-4 backdrop-blur-xl animate-in fade-in slide-in-from-top-3">
        <div className="flex justify-between items-center mb-3">
          <span className="text-[10px] font-black tracking-widest text-indigo-400 uppercase">
            PROGRESO DEL DOCKING ASÍNCRONO
          </span>
          <span className="text-[10px] font-mono text-white bg-indigo-950 px-2 py-0.5 rounded-md border border-indigo-500/20">
            {progress}%
          </span>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden border border-white/5 mb-4">
          <div 
            className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500 ease-out shadow-[0_0_10px_rgba(99,102,241,0.5)]" 
            style={{ width: `${progress}%` }} 
          />
        </div>

        {/* Steps Grid */}
        <div className="space-y-2">
          {stages.map((stage, idx) => {
            const isCompleted = progress > stage.min && (idx === stages.length - 1 ? progress === 100 : progress >= stages[idx+1].min);
            const isProcessing = progress >= stage.min && !isCompleted;
            
            return (
              <div 
                key={stage.id} 
                className={`flex items-center justify-between text-xs px-3 py-2 rounded-xl border transition-all duration-300 ${
                  isCompleted 
                    ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-400" 
                    : isProcessing
                      ? "bg-indigo-500/5 border-indigo-500/30 text-indigo-300 shadow-[0_0_10px_rgba(99,102,241,0.05)]"
                      : "bg-black/20 border-white/5 text-slate-500"
                }`}
              >
                <div className="flex items-center gap-2 font-medium">
                  {isCompleted ? (
                    <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.8)]" />
                  ) : isProcessing ? (
                    <div className="h-1.5 w-1.5 rounded-full bg-indigo-500 animate-ping" />
                  ) : (
                    <div className="h-1.5 w-1.5 rounded-full bg-slate-800" />
                  )}
                  <span>{stage.label}</span>
                </div>
                <span className="text-[10px] font-mono opacity-80">
                  {isCompleted ? "Completado" : isProcessing ? "Procesando..." : "En espera"}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="text-slate-300 font-sans min-h-screen pb-16 space-y-6">
      
      {/* Title section */}
      <section className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-5">
        <div>
          <h1 className="text-2xl font-black text-white uppercase tracking-wider flex items-center gap-2">
            <Layers className="text-indigo-400" size={24} />
            Evaluación Molecular Avanzada
          </h1>
          <p className="text-[10px] text-slate-500 font-medium uppercase tracking-widest mt-1">
            Capa 1: Cribado Físico y Químico con Grid Overrides y Rescoring ML
          </p>
        </div>
        
        {/* State Indicators */}
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-indigo-500/10 bg-indigo-950/20 px-3 py-1.5 flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />
            <span className="text-[9px] font-black uppercase tracking-widest text-indigo-400">Modo Profesional</span>
          </div>
          {isTerminal && (
            <button 
              onClick={handleReset} 
              className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl px-3.5 py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors duration-200"
            >
              <RefreshCw size={12} /> Nuevo
            </button>
          )}
        </div>
      </section>

      {/* Primary vertical layout */}
      <div className="flex flex-col gap-6 items-stretch">
        
        {/* MODULE 1: CONFIGURATION */}
        <div className="space-y-5">
          <div className="rounded-2xl border border-white/5 bg-slate-900/60 p-5 space-y-4 shadow-xl">
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
              <Sliders size={14} className="text-indigo-400" />
              1. Configuración de Caja (Grid Box)
            </h3>
            
            {/* Target Select */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                Objetivo Biológico (Target)
              </label>
              {loadingTargets ? (
                <div className="w-full rounded-xl border border-white/5 bg-black/40 px-3 py-2.5 text-xs text-slate-500 animate-pulse">
                  Cargando catálogo de receptores...
                </div>
              ) : (
                <button
                  onClick={() => setIsTargetModalOpen(true)}
                  disabled={busy || (!!taskId && !isTerminal)}
                  className={`relative w-full group overflow-hidden rounded-xl border p-4 text-left transition-all duration-300 ${
                    activeTargetObj 
                      ? "border-indigo-500/50 bg-indigo-950/20 hover:bg-indigo-900/30 hover:border-indigo-400" 
                      : "border-indigo-500/30 bg-black/40 hover:bg-indigo-950/20 hover:border-indigo-400/80"
                  }`}
                >
                  {/* Premium animated glow effect if no target selected */}
                  {!activeTargetObj && (
                    <div className="absolute inset-0 bg-gradient-to-r from-indigo-600/0 via-indigo-500/10 to-indigo-600/0 opacity-0 group-hover:opacity-100 animate-pulse transition-opacity duration-700" />
                  )}
                  
                  <div className="relative flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg flex-shrink-0 transition-colors duration-300 ${
                        activeTargetObj ? "bg-indigo-500/20 text-indigo-400" : "bg-white/5 text-slate-400 group-hover:bg-indigo-500/20 group-hover:text-indigo-400"
                      }`}>
                        {activeTargetObj ? <Database size={18} /> : <Search size={18} />}
                      </div>
                      
                      <div className="flex flex-col">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-0.5">
                          {activeTargetObj ? "Receptor Seleccionado" : "Catálogo de Receptores"}
                        </span>
                        <span className={`text-sm font-black tracking-wider ${activeTargetObj ? "text-white" : "text-indigo-400"}`}>
                          {activeTargetObj 
                            ? `${activeTargetObj.pdb_id} - ${activeTargetObj.name}` 
                            : "Explorar Catálogo 3D"}
                        </span>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      {activeTargetObj && (
                        <span className="hidden sm:inline-block px-2 py-1 rounded bg-black/40 border border-white/10 text-[9px] font-bold text-slate-400 uppercase">
                          {activeTargetObj.structural_family || "Desconocido"}
                        </span>
                      )}
                      <div className={`p-1.5 rounded-md transition-colors duration-300 ${
                        activeTargetObj ? "bg-white/5" : "bg-indigo-500/10 text-indigo-400"
                      }`}>
                        <ChevronRight size={14} className={activeTargetObj ? "text-slate-500" : "text-indigo-400 group-hover:translate-x-0.5 transition-transform"} />
                      </div>
                    </div>
                  </div>
                </button>
              )}
            </div>

            <TargetSelectorModal 
              isOpen={isTargetModalOpen}
              onClose={() => setIsTargetModalOpen(false)}
              targets={targets}
              onSelect={(pdbId) => setTarget(pdbId)}
              selectedTargetId={target}
            />

            {activeTargetObj && (
              <div className="rounded-xl bg-black/40 border border-white/5 p-3 text-[10px] space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-500 font-bold uppercase">Familia Estructural:</span>
                  <span className="text-indigo-300 font-mono font-bold uppercase">{activeTargetObj.structural_family || "N/A"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-bold uppercase">Resolución:</span>
                  <span className="text-indigo-300 font-mono font-bold">{activeTargetObj.resolution ? `${activeTargetObj.resolution.toFixed(2)} Å` : "N/A"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-bold uppercase">Spearman Global (ρ):</span>
                  <span className="text-indigo-300 font-mono font-bold">{activeTargetObj.spearman_rho ? activeTargetObj.spearman_rho.toFixed(3) : "0.512"}</span>
                </div>
              </div>
            )}

            {/* Coordinates override form */}
            <div className="space-y-3 pt-2">
              <div className="flex justify-between items-center">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Coordenadas del Centro (X, Y, Z)
                </label>
                {activeTargetObj?.hotspots && (
                  <button 
                    onClick={handleAutoDetectCentroid}
                    disabled={busy || (!!taskId && !isTerminal)}
                    className="text-[9px] font-black uppercase tracking-wider text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition-colors duration-150"
                  >
                    <Maximize2 size={10} /> Auto-Calcular Centroide
                  </button>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <span className="text-[9px] text-slate-500 font-mono uppercase block mb-1">X</span>
                  <input
                    type="text"
                    value={gridCenterX}
                    onChange={(e) => setGridCenterX(e.target.value)}
                    disabled={busy || (!!taskId && !isTerminal) || !activeTargetObj}
                    placeholder="0.0"
                    className="w-full text-center rounded-lg border border-white/5 bg-[#03060c] text-white px-2 py-2 text-xs font-mono outline-none focus:border-indigo-500/40"
                  />
                </div>
                <div>
                  <span className="text-[9px] text-slate-500 font-mono uppercase block mb-1">Y</span>
                  <input
                    type="text"
                    value={gridCenterY}
                    onChange={(e) => setGridCenterY(e.target.value)}
                    disabled={busy || (!!taskId && !isTerminal) || !activeTargetObj}
                    placeholder="0.0"
                    className="w-full text-center rounded-lg border border-white/5 bg-[#03060c] text-white px-2 py-2 text-xs font-mono outline-none focus:border-indigo-500/40"
                  />
                </div>
                <div>
                  <span className="text-[9px] text-slate-500 font-mono uppercase block mb-1">Z</span>
                  <input
                    type="text"
                    value={gridCenterZ}
                    onChange={(e) => setGridCenterZ(e.target.value)}
                    disabled={busy || (!!taskId && !isTerminal) || !activeTargetObj}
                    placeholder="0.0"
                    className="w-full text-center rounded-lg border border-white/5 bg-[#03060c] text-white px-2 py-2 text-xs font-mono outline-none focus:border-indigo-500/40"
                  />
                </div>
              </div>

              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 pt-1">
                Dimensiones de Caja (dX, dY, dZ) - Ångström
              </label>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <span className="text-[9px] text-slate-500 font-mono uppercase block mb-1">dX</span>
                  <input
                    type="text"
                    value={gridSizeX}
                    onChange={(e) => setGridSizeX(e.target.value)}
                    disabled={busy || (!!taskId && !isTerminal) || !activeTargetObj}
                    placeholder="20"
                    className="w-full text-center rounded-lg border border-white/5 bg-[#03060c] text-white px-2 py-2 text-xs font-mono outline-none focus:border-indigo-500/40"
                  />
                </div>
                <div>
                  <span className="text-[9px] text-slate-500 font-mono uppercase block mb-1">dY</span>
                  <input
                    type="text"
                    value={gridSizeY}
                    onChange={(e) => setGridSizeY(e.target.value)}
                    disabled={busy || (!!taskId && !isTerminal) || !activeTargetObj}
                    placeholder="20"
                    className="w-full text-center rounded-lg border border-white/5 bg-[#03060c] text-white px-2 py-2 text-xs font-mono outline-none focus:border-indigo-500/40"
                  />
                </div>
                <div>
                  <span className="text-[9px] text-slate-500 font-mono uppercase block mb-1">dZ</span>
                  <input
                    type="text"
                    value={gridSizeZ}
                    onChange={(e) => setGridSizeZ(e.target.value)}
                    disabled={busy || (!!taskId && !isTerminal) || !activeTargetObj}
                    placeholder="20"
                    className="w-full text-center rounded-lg border border-white/5 bg-[#03060c] text-white px-2 py-2 text-xs font-mono outline-none focus:border-indigo-500/40"
                  />
                </div>
              </div>
            </div>

            {/* Hotspots fine selection list */}
            {activeTargetObj?.hotspots && activeTargetObj.hotspots.length > 0 && (
              <div className="space-y-2.5 pt-3 border-t border-white/5">
                <div className="flex justify-between items-center">
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Residuos Críticos (Hotspots)
                  </label>
                  <span className="text-[8px] text-slate-500 font-bold uppercase">
                    SELECCIONADOS: {Object.values(selectedHotspots).filter(Boolean).length}
                  </span>
                </div>
                <div className="space-y-1.5 max-h-[140px] overflow-y-auto pr-1">
                  {activeTargetObj.hotspots.map(h => {
                    const isChecked = !!selectedHotspots[h.name];
                    return (
                      <button
                        key={h.name}
                        onClick={() => handleToggleHotspot(h.name)}
                        disabled={busy || (!!taskId && !isTerminal)}
                        className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg border text-left text-xs transition-all duration-200 ${
                          isChecked 
                            ? "bg-indigo-500/5 border-indigo-500/20 text-indigo-300 font-bold" 
                            : "bg-black/35 border-white/5 text-slate-500"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          {isChecked ? <CheckSquare size={13} className="text-indigo-400" /> : <Square size={13} />}
                          <span className="font-mono">{h.name}</span>
                        </div>
                        {h.x !== undefined ? (
                          <span className="text-[9px] font-mono text-slate-500">
                            ({h.x.toFixed(1)}, {h.y?.toFixed(1)}, {h.z?.toFixed(1)})
                          </span>
                        ) : (
                          <span className="text-[8px] uppercase tracking-tighter opacity-55">Sin Coords</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* COLUMN 2: MOLECULAR EDITOR (CENTER) */}
        <div className="space-y-5 lg:col-span-1">
          <div className="rounded-2xl border border-white/5 bg-slate-900/60 p-5 space-y-4 shadow-xl">
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
              <Database size={14} className="text-indigo-400" />
              2. Estructura del Ligando
            </h3>

            {/* Ketcher 2D Editor */}
            <div>
              <KetcherEditor
                initialSmiles={smiles}
                onSmilesChange={setSmiles}
              />
            </div>

            {/* Chemical validation status */}
            {validation && (
              <div className={`rounded-xl border p-3 flex flex-col gap-1 text-[11px] animate-in fade-in duration-200 ${
                validation.is_valid 
                  ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-400" 
                  : "bg-rose-500/5 border-rose-500/20 text-rose-400"
              }`}>
                <div className="flex justify-between font-bold">
                  <span>Validación RDKit:</span>
                  <span className="uppercase">{validation.is_valid ? "✓ Válida" : "✗ Inválida"}</span>
                </div>
                {validation.canonical_smiles && (
                  <div className="text-[10px] text-slate-400 truncate mt-1">
                    SMILES: <code className="font-mono text-indigo-300">{validation.canonical_smiles}</code>
                  </div>
                )}
                {validation.molecular_formula && (
                  <div className="text-[10px] text-slate-400">
                    Fórmula Molecular: <span className="font-semibold text-slate-300">{validation.molecular_formula}</span>
                  </div>
                )}
              </div>
            )}

            {/* API Error Box */}
            {error && (
              <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-3.5 text-xs text-rose-400 animate-in shake duration-300">
                <span className="font-bold block uppercase mb-1">Error de Servidor</span>
                <p className="font-mono text-[10px] leading-relaxed break-words">{error}</p>
              </div>
            )}

            {/* Peptide Engine Selector */}
            {isPeptide && (
              <div className="rounded-xl border border-indigo-500/10 bg-indigo-950/10 p-4 space-y-3 animate-in fade-in duration-300">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-black tracking-widest text-indigo-400 uppercase">
                    Configuración Peptídica (Nivel 3)
                  </span>
                </div>
                <p className="text-[10px] text-slate-400 leading-normal">
                  Se ha detectado una macromolécula/péptido. Selecciona el motor de plegado y acoplamiento:
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 pt-1">
                  <label className={`flex flex-col p-3 rounded-xl border cursor-pointer transition-all duration-200 ${
                    peptideDockingEngine === "diffpepdock"
                      ? "bg-indigo-500/10 border-indigo-500/50 text-indigo-300 shadow-[0_0_10px_rgba(99,102,241,0.1)]"
                      : "bg-black/35 border-white/5 text-slate-500 hover:border-white/10"
                  }`}>
                    <div className="flex items-center gap-2 mb-1">
                      <input
                        type="radio"
                        name="peptideDockingEngine"
                        value="diffpepdock"
                        checked={peptideDockingEngine === "diffpepdock"}
                        onChange={() => setPeptideDockingEngine("diffpepdock")}
                        className="sr-only"
                      />
                      <div className={`h-3.5 w-3.5 rounded-full border flex items-center justify-center ${
                        peptideDockingEngine === "diffpepdock" ? "border-indigo-500" : "border-slate-600"
                      }`}>
                        {peptideDockingEngine === "diffpepdock" && <div className="h-1.5 w-1.5 rounded-full bg-indigo-500" />}
                      </div>
                      <span className="text-xs font-bold text-white">DiffPepDock</span>
                    </div>
                    <span className="text-[9px] leading-tight text-slate-400 font-medium">
                      (Recomendado) Inferencia rápida por difusión de IA (&lt;60s). Ideal para iteración ágil.
                    </span>
                  </label>
                  
                  <label className={`flex flex-col p-3 rounded-xl border cursor-pointer transition-all duration-200 ${
                    peptideDockingEngine === "colabfold"
                      ? "bg-indigo-500/10 border-indigo-500/50 text-indigo-300 shadow-[0_0_10px_rgba(99,102,241,0.1)]"
                      : "bg-black/35 border-white/5 text-slate-500 hover:border-white/10"
                  }`}>
                    <div className="flex items-center gap-2 mb-1">
                      <input
                        type="radio"
                        name="peptideDockingEngine"
                        value="colabfold"
                        checked={peptideDockingEngine === "colabfold"}
                        onChange={() => setPeptideDockingEngine("colabfold")}
                        className="sr-only"
                      />
                      <div className={`h-3.5 w-3.5 rounded-full border flex items-center justify-center ${
                        peptideDockingEngine === "colabfold" ? "border-indigo-500" : "border-slate-600"
                      }`}>
                        {peptideDockingEngine === "colabfold" && <div className="h-1.5 w-1.5 rounded-full bg-indigo-500" />}
                      </div>
                      <span className="text-xs font-bold text-white">ColabFold</span>
                    </div>
                    <span className="text-[9px] leading-tight text-slate-400 font-medium">
                      Plegado completo receptor-péptido por co-evolución (5-15 min). Computacionalmente costoso.
                    </span>
                  </label>
                </div>
              </div>
            )}

            {/* Actions triggers */}
            <div className="space-y-2 pt-2">
              <button
                onClick={handleValidate}
                disabled={busy || (!!taskId && !isTerminal) || !smiles.trim()}
                className="w-full rounded-xl border border-white/10 bg-slate-800 hover:bg-slate-700/80 px-4 py-2.5 text-xs font-black uppercase tracking-wider text-slate-200 transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Validar Estructura Química
              </button>

              <button
                onClick={handleLaunchEvaluation}
                disabled={busy || !canEvaluate || (!!taskId && !isTerminal)}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 px-4 py-3 text-xs font-black uppercase tracking-widest text-white transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(99,102,241,0.2)] hover:shadow-[0_0_20px_rgba(99,102,241,0.35)]"
              >
                <Play size={13} className="fill-white" />
                Ejecutar Docking Avanzado
              </button>
            </div>
          </div>

          {/* Celery Pipeline monitor */}
          {renderWorkflowProgress()}
        </div>

        {/* COLUMN 3: ANALYSIS & 3D VIEWER (RIGHT) */}
        <div className="space-y-5">
          <div className={status?.result ? "grid gap-5 lg:grid-cols-2" : "space-y-5"}>
            {status?.result && (
              <ScoreCard
                totalScore={status.result.total_score}
                affinity={status.result.affinity_score}
                affinityKcal={status.result.affinity_kcal}
                adme={status.result.adme_score}
                druglikeness={status.result.druglikeness_score}
                ligandEfficiency={status.result.ligand_efficiency}
                onCertify={handleCertify}
                onSave={handleSave}
                isSaved={isSaved}
                solanaSignature={status.result.blockchain_tx_id}
                onDownloadCertificate={handleDownloadCertificate}
                onDownloadComplex={handleDownloadComplex}
                isControl={status.result.is_control}
                saScore={status.result.sa_score}
                saReasons={status.result.sa_reasons}
                rawVinaKcal={(status.result.docking_poses?.[0] as any)?.affinity ?? null}
                rawXgboostKcal={status.result.affinity_kcal}
                lipophilicEfficiency={status.result.ligand_lipophilicity_efficiency}
                specificity={status.result.specificity_score}
                affinityMultiplier={status.result.affinity_multiplier}
                specificityMultiplier={status.result.specificity_multiplier}
                gnnScore={status.result.gnn_score}
              />
            )}
            <div className="rounded-2xl border border-white/5 bg-slate-900/60 p-5 space-y-4 shadow-xl">
              <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
                <ShieldCheck size={14} className="text-indigo-400" />
                3. Resultados e Inspección 3D
              </h3>

            {/* Tabbed view selector */}
            <div className="grid grid-cols-3 border-b border-white/5 pb-1 gap-1">
              <button
                onClick={() => setActiveTab("visualizer")}
                className={`pb-2 text-[10px] font-black uppercase tracking-wider text-center border-b-2 transition-all duration-200 ${
                  activeTab === "visualizer"
                    ? "border-indigo-500 text-indigo-400"
                    : "border-transparent text-slate-500 hover:text-slate-400"
                }`}
              >
                Estructura 3D
              </button>
              <button
                onClick={() => setActiveTab("parameters")}
                className={`pb-2 text-[10px] font-black uppercase tracking-wider text-center border-b-2 transition-all duration-200 ${
                  activeTab === "parameters"
                    ? "border-indigo-500 text-indigo-400"
                    : "border-transparent text-slate-500 hover:text-slate-400"
                }`}
              >
                Parámetros
              </button>
              <button
                onClick={() => setActiveTab("warnings")}
                className={`pb-2 text-[10px] font-black uppercase tracking-wider text-center border-b-2 transition-all duration-200 ${
                  activeTab === "warnings"
                    ? "border-indigo-500 text-indigo-400"
                    : "border-transparent text-slate-500 hover:text-slate-400"
                }`}
              >
                Alertas ({status?.result?.scientific_warnings?.length || 0})
              </button>
            </div>

            {/* Tab Content: Visualizer */}
            {activeTab === "visualizer" && (
              <div className="space-y-4">
                <div className="h-[280px] w-full">
                  <AdvancedMolstarViewer
                    poseData={activePoseData}
                    proteinData={proteinData || undefined}
                    height={280}
                    hotspots={status?.result?.target_hotspots?.map(h => h.name) || []}
                    hotspotsHit={status?.result?.hotspots_hit || []}
                  />
                </div>

                {/* Poses selection list */}
                {status?.result?.docking_poses && status.result.docking_poses.length > 0 ? (
                  <div className="space-y-2">
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500">
                      Poses Encontradas (AutoDock Vina)
                    </label>
                    <div className="rounded-xl border border-white/5 overflow-hidden">
                      <table className="w-full text-left border-collapse text-[10px] font-mono">
                        <thead>
                          <tr className="bg-black/40 border-b border-white/5 uppercase text-slate-500 font-sans font-bold">
                            <th className="px-3 py-2">Rank</th>
                            <th className="px-3 py-2 text-right">Afinidad (kcal)</th>
                            <th className="px-3 py-2 text-right">RMSD l.b.</th>
                          </tr>
                        </thead>
                        <tbody>
                          {status.result.docking_poses.map((pose: any, idx: number) => {
                            const isSelected = selectedPoseIndex === idx;
                            return (
                              <tr
                                key={idx}
                                onClick={() => setSelectedPoseIndex(idx)}
                                className={`cursor-pointer border-b border-white/5/30 transition-all duration-150 ${
                                  isSelected
                                    ? "bg-indigo-500/10 text-indigo-400 font-bold"
                                    : "hover:bg-white/5 text-slate-300"
                                }`}
                              >
                                <td className="px-3 py-2 flex items-center gap-1.5">
                                  {isSelected && <ChevronRight size={10} />}
                                  Pose {pose.rank || idx + 1}
                                </td>
                                <td className="px-3 py-2 text-right text-indigo-300 font-bold">{pose.affinity?.toFixed(2)}</td>
                                <td className="px-3 py-2 text-right opacity-60">{pose.rmsd_lb?.toFixed(2) || "0.00"}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl bg-black/30 border border-white/5 p-8 text-center text-slate-500 text-xs">
                    Completa una simulación para ver la tabla de conformaciones moleculares y poses.
                  </div>
                )}
              </div>
            )}

            {/* Tab Content: Parameters */}
            {activeTab === "parameters" && (
              <div className="space-y-3 animate-in fade-in duration-200">
                {status?.result ? (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
                      <div className="bg-black/30 p-2.5 rounded-xl border border-white/5">
                        <span className="text-slate-500 block uppercase font-sans font-semibold mb-0.5">QED Score:</span>
                        <span className="text-white text-xs font-bold">{status.result.qed?.toFixed(3) || "N/A"}</span>
                      </div>
                      <div className="bg-black/30 p-2.5 rounded-xl border border-white/5">
                        <span className="text-slate-500 block uppercase font-sans font-semibold mb-0.5">SA Score:</span>
                        <span className="text-white text-xs font-bold">{status.result.sa_score?.toFixed(2) || "N/A"}</span>
                      </div>
                      <div className="bg-black/30 p-2.5 rounded-xl border border-white/5">
                        <span className="text-slate-500 block uppercase font-sans font-semibold mb-0.5">Peso Mol:</span>
                        <span className="text-white text-xs font-bold">{status.result.molecular_weight?.toFixed(1) || "N/A"} g/mol</span>
                      </div>
                      <div className="bg-black/30 p-2.5 rounded-xl border border-white/5">
                        <span className="text-slate-500 block uppercase font-sans font-semibold mb-0.5">LogP:</span>
                        <span className="text-white text-xs font-bold">{status.result.log_p?.toFixed(2) || "N/A"}</span>
                      </div>
                    </div>
                    {status.result.sa_reasons && status.result.sa_reasons.length > 0 && (
                      <div className="bg-black/30 p-3 rounded-xl border border-white/5 text-[10px] space-y-1">
                        <span className="text-slate-500 uppercase font-sans font-bold block mb-1">Restricciones SA:</span>
                        {status.result.sa_reasons.map((r: string, idx: number) => (
                          <div key={idx} className="text-rose-400 font-medium">• {r}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center text-slate-500 text-xs py-8">
                    Sin datos. Ejecuta una simulación para extraer los coeficientes fisicoquímicos detallados.
                  </div>
                )}
              </div>
            )}

            {/* Tab Content: Warnings */}
            {activeTab === "warnings" && (
              <div className="space-y-2 animate-in fade-in duration-200 max-h-[360px] overflow-y-auto pr-1">
                {status?.result?.scientific_warnings && status.result.scientific_warnings.length > 0 ? (
                  status.result.scientific_warnings.map((warn: string, idx: number) => (
                    <div key={idx} className="rounded-xl border border-rose-500/10 bg-rose-500/5 p-3 text-xs text-rose-300 leading-relaxed flex gap-2">
                      <Info size={14} className="text-rose-400 shrink-0 mt-0.5" />
                      <span>{warn}</span>
                    </div>
                  ))
                ) : (
                  <div className="text-center text-slate-500 text-xs py-8">
                    No se han registrado advertencias ni fallos de selectividad para esta simulación.
                  </div>
                )}
              </div>
            )}

            {/* Action Buttons: Save & On-Chain Certification */}
            {status?.result && (
              <div className="space-y-2 pt-3 border-t border-white/5">
                {isSaved ? (
                  <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/25 p-3 text-center text-xs font-bold text-emerald-400">
                    ¡Complejo guardado exitosamente en tu Moldex!
                  </div>
                ) : (
                  <button
                    onClick={() => handleSave()}
                    disabled={busy}
                    className="w-full flex items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-slate-800 hover:bg-slate-700/80 px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-200 transition-colors duration-150 disabled:opacity-50"
                  >
                    <Save size={13} />
                    Guardar Complejo en Moldex
                  </button>
                )}

                {status.result.blockchain_tx_id ? (
                  <div className="rounded-xl bg-indigo-500/10 border border-indigo-500/20 p-3 text-center text-xs">
                    <span className="font-bold text-indigo-400 uppercase block mb-1">Certificado Solana On-Chain</span>
                    <span className="font-mono text-[9px] block text-slate-400 break-all">{status.result.blockchain_tx_id}</span>
                    <button
                      onClick={handleDownloadCertificate}
                      disabled={busy}
                      className="mt-2.5 inline-flex items-center gap-1 bg-indigo-600/30 hover:bg-indigo-600/40 text-indigo-300 border border-indigo-500/30 rounded-lg px-3 py-1.5 text-[9px] font-black uppercase tracking-wider transition-colors duration-150"
                    >
                      <FileText size={10} /> Descargar PDF
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {showWalletInput ? (
                      <div className="rounded-xl bg-black/40 border border-white/5 p-3 space-y-2">
                        <label className="block text-[8px] font-black uppercase tracking-widest text-slate-500">
                          DIRECCIÓN WALLET SOLANA (DEJAR VACÍO PARA MOCK)
                        </label>
                        <input
                          type="text"
                          value={customWallet}
                          onChange={(e) => setCustomWallet(e.target.value)}
                          placeholder="Ex: Ht...3m"
                          className="w-full rounded-lg border border-white/5 bg-[#03060c] text-white px-2 py-1.5 text-xs font-mono outline-none focus:border-indigo-500/40"
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleCertify()}
                            disabled={busy}
                            className="flex-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider"
                          >
                            Firmar
                          </button>
                          <button
                            onClick={() => setShowWalletInput(false)}
                            className="rounded-lg border border-white/10 text-slate-400 px-3 py-1.5 text-[10px]"
                          >
                            Cancelar
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleCertify()}
                        disabled={busy}
                        className="w-full flex items-center justify-center gap-1.5 rounded-xl border border-indigo-500/20 bg-indigo-600/10 hover:bg-indigo-600/20 px-4 py-2.5 text-xs font-black uppercase tracking-wider text-indigo-400 transition-colors duration-150 disabled:opacity-50"
                      >
                        <ShieldCheck size={13} />
                        Certificar en Blockchain
                      </button>
                    )}
                  </div>
                )}

                <button
                  onClick={handleDownloadComplex}
                  disabled={busy}
                  className="w-full flex items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-slate-800 hover:bg-slate-700/80 px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-200 transition-colors duration-150 disabled:opacity-50"
                >
                  <Download size={13} />
                  Descargar Complejo (.PDB)
                </button>
              </div>
            )}
          </div>
          </div>
        </div>
        
      </div>
      
    </div>
  );
}
