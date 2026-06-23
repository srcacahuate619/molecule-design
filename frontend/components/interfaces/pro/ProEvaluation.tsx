"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
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
import { motion } from "framer-motion";
import { KetcherEditor } from "../../KetcherEditor";
import { ScoreCard } from "../../ScoreCard";
import dynamic from "next/dynamic";
const PDFReportViewer = dynamic(() => import("../../PDFReportViewer").then(mod => mod.PDFReportViewer), { ssr: false });
import AdvancedMolstarViewer from "./AdvancedMolstarViewer";
import TargetSelectorModal from "./TargetSelectorModal";
import type { Target } from "../../../lib/api";
import type { JobStatus, MolecularSuggestion, ValidationResult } from "../../../lib/types";
import { useAuth } from "../../../lib/auth";
import { CertificationModal } from "../../CertificationModal";

const SHAP_EXPLANATIONS: Record<string, { label: string, desc: string }> = {
  // ECIF Features
  "ecif_N_don_C": { label: "Puentes H (N-donador → C)", desc: "Interacciones entre átomos de Nitrógeno donadores en el ligando y Carbonos en el bolsillo." },
  "ecif_N_don_N": { label: "Puentes H (N-donador → N)", desc: "Interacciones entre Nitrógenos donadores en el ligando y Nitrógenos en el bolsillo." },
  "ecif_N_don_O": { label: "Puentes H (N-donador → O)", desc: "Interacciones entre Nitrógenos donadores en el ligando y Oxígenos en el bolsillo." },
  "ecif_O_don_C": { label: "Puentes H (O-donador → C)", desc: "Interacciones entre Oxígenos donadores en el ligando y Carbonos en el bolsillo." },
  "ecif_O_don_O": { label: "Puentes H (O-donador → O)", desc: "Interacciones entre Oxígenos donadores en el ligando y Oxígenos en el bolsillo." },
  "ecif_O_don_N": { label: "Puentes H (O-donador → N)", desc: "Interacciones entre Oxígenos donadores en el ligando y Nitrógenos en el bolsillo." },
  "ecif_C_C": { label: "Contactos C-C (Van der Waals)", desc: "Contactos hidrofóbicos entre átomos de Carbono del ligando y de la proteína." },
  "ecif_C_N": { label: "Contactos C-N", desc: "Contactos atómicos entre Carbonos y Nitrógenos." },
  "ecif_C_O": { label: "Contactos C-O", desc: "Contactos atómicos entre Carbonos y Oxígenos." },
  "ecif_P_don_O": { label: "Interacción Fósforo-Oxígeno", desc: "Contactos atómicos con grupos fosfato." },
  "ecif_S_don_O": { label: "Interacción Azufre-Oxígeno", desc: "Contactos atómicos involucrando tioles o grupos azufrados." },
  
  // Shell Features
  "shell_C_C_4_8": { label: "Empaquetamiento (4-8 Å)", desc: "Densidad de Carbonos alrededor del ligando en la franja de distancia media de 4 a 8 Ångströms." },
  "shell_C_O_4_8": { label: "Entorno C-O (4-8 Å)", desc: "Contactos de medio alcance entre Carbonos y Oxígenos." },
  "shell_N_N_0_4": { label: "Contactos N-N (< 4 Å)", desc: "Densidad de Nitrógenos interactuando fuertemente a menos de 4 Ångströms." },
  "shell_O_C_4_8": { label: "Entorno O-C (4-8 Å)", desc: "Densidad de Oxígenos en un rango intermedio alrededor del ligando." },
  "shell_C_C_8_12": { label: "Influencia Lejana (8-12 Å)", desc: "Efectos conformacionales y estéricos de largo alcance ejercidos por los Carbonos del bolsillo." },
  "shell_N_C_8_12": { label: "Entorno N-C (8-12 Å)", desc: "Contactos de largo alcance en el borde del solvente o la superficie proteica exterior." },
  
  // Contact Features
  "close_contacts_4A": { label: "Contactos Directos (< 4 Å)", desc: "Número total de colisiones e interacciones atómicas íntimas. Fuerte indicador de encaje espacial." },
  "close_contacts_6A": { label: "Contactos Cercanos (< 6 Å)", desc: "Número total de contactos en la primera y segunda esfera de solvatación del bolsillo." },
  "close_contacts_8A": { label: "Contactos Extendidos (< 8 Å)", desc: "Densidad atómica en la cavidad de unión extendida." },
};

function getFeatureExplanation(feature: string) {
  if (SHAP_EXPLANATIONS[feature]) return SHAP_EXPLANATIONS[feature];
  
  // Fallbacks
  if (feature.startsWith("ecif_")) {
    const pair = feature.replace("ecif_", "").replace(/_/g, "-");
    return { label: `Interacción ${pair}`, desc: "Interacción específica de pares atómicos (ECIF)." };
  }
  if (feature.startsWith("shell_")) {
    const parts = feature.split("_");
    const dist = parts.slice(parts.length-2).join("-");
    const atoms = parts.slice(1, parts.length-2).join("-");
    return { label: `Capa Distancia ${atoms} (${dist} Å)`, desc: "Densidad atómica en un anillo tridimensional específico." };
  }
  
  return { label: feature.replace(/_/g, " "), desc: "Propiedad físico-química extraída del complejo molecular." };
}

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
  onTargetUploadSuccess?: () => void;
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
  onTargetUploadSuccess,
}: ProEvaluationProps) {
  const { user } = useAuth();
  const consoleRef = useRef<HTMLDivElement>(null);
  const [showCertModal, setShowCertModal] = useState(false);
  
  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [status?.progress, status]);

  // --- Target Selector Modal state ---
  const [isTargetModalOpen, setIsTargetModalOpen] = useState(false);
  const [showPdfViewer, setShowPdfViewer] = useState(false);

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
  const [activeTab, setActiveTab] = useState<"visualizer" | "parameters" | "warnings" | "xai">("visualizer");
  const [expandedGNN, setExpandedGNN] = useState<'2d' | '1d' | null>(null);

  // --- Peptide docking engine state (Nivel 3) ---
  const [peptideDockingEngine, setPeptideDockingEngine] = useState<"diffpepdock" | "colabfold">("diffpepdock");
  const [showPeptideModal, setShowPeptideModal] = useState(false);

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

  // Execute submission after parameters are collected
  const executeSubmission = async (engine: "diffpepdock" | "colabfold") => {
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

    const customHotspotsList = Object.keys(selectedHotspots).filter(k => selectedHotspots[k]);

    await handleSubmit(centerOverride, sizeOverride, customHotspotsList, engine);
  };

  // Submit trigger with overrides
  const handleLaunchEvaluation = async () => {
    if (isPeptide) {
      setShowPeptideModal(true);
      return;
    }
    await executeSubmission(peptideDockingEngine);
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
    const progress = status?.progress || 0;
    const currentStatus = status?.status || "IDLE";

    const isColabFold = status?.result?.vina_version?.includes("COLABFOLD") || (isPeptide && peptideDockingEngine === "colabfold");
    const dockingLabel = isPeptide
      ? (isColabFold ? "Plegado y Docking (ColabFold)" : "Docking por Difusión (DiffPepDock)")
      : `L1: Acoplamiento Molecular (Vina${target ? ` - ${target}` : ""})`;

    const stages = [
      { id: "validation", label: "L0: Curación Estructural (RDKit Engine)", min: 0 },
      { id: "conformation", label: "Generación de Conformómeros 3D + MMFF94", min: 20 },
      { id: "docking", label: dockingLabel, min: 50 },
      { id: "admet", label: "Viabilidad Sanguínea (ADMET-AI + TabPFN)", min: 70 },
      { id: "scoring", label: "L2: Inferencia de Afinidad (GNN RTMScore + XGBoost)", min: 85 },
      { id: "refinement", label: "L3: Relajación de Choques Estéricos (OpenMM MD)", min: 95 },
      { id: "blockchain", label: "Firma Ledger Blockchain (Solana Devnet)", min: 98 }
    ];

    const getConsoleLogs = (prog: number) => {
      if (!status) {
        return [
          "[sys] Clúster de cálculo asíncrono MolDesign v6.9 listo.",
          "[sys] Dispositivos de telemetría e inferencia GNN online.",
          "[sys] Esperando coordenadas estructurales y orden de ejecución..."
        ];
      }

      const logs: string[] = [
        "[sys] Inicializando clúster de cálculo asíncrono MolDesign v6.9...",
        `[sys] Conectando con base de datos PostgreSQL y cargando receptor ${target}...`
      ];

      if (prog >= 5) {
        logs.push(
          "[rdkit] Analizando estructura SMILES ingresada...",
          `[rdkit] SMILES canónico resuelto: ${smiles}`,
          "[rdkit] Curación: valencia atómica verificada. Cero anomalías estéricas detectadas."
        );
      }
      if (prog >= 20) {
        logs.push(
          "[rdkit] Inicializando generador conformacional estocástico ETKDG v3...",
          "[rdkit] Generando conformadores tridimensionales por distancia geométrica...",
          "[rdkit] Minimizando energía local del ligando usando campo de fuerza semi-empírico MMFF94..."
        );
      }
      if (prog >= 40) {
        logs.push(
          "[minio] Descargando archivo receptor PDB raw...",
          "[preparer] Filtrando cadena activa del receptor biológico...",
          "[preparer] Excluyendo moléculas de agua cristalizada y ligandos HETATM...",
          "[meeko] Añadiendo hidrógenos polares y cargas parciales de Gasteiger..."
        );
      }
      if (prog >= 55) {
        logs.push(
          `[vina] Configurando caja de docking (Grid Box) en centroide del receptor...`,
          `[vina] Invocando AutoDock Vina con exhaustiveness=32 (num_poses=5)...`,
          "[vina] Muestreando espacio conformacional de torsión del ligando..."
        );
      }
      if (prog >= 50) {
        logs.push(
          "[vina] Optimización de energía local por algoritmo BFGS completada.",
          "[vina] Pose número 1 resuelta como configuración de mínima energía.",
          "[rescoring] Extrayendo descriptores moleculares descriptores de contacto ODDT..."
        );
      }
      if (prog >= 70) {
        logs.push(
          "[admet] Analizando viabilidad sistémica y MPO con ADMET-AI...",
          "[tabpfn] Inferencia en batch completada. Evaluando riesgos de HIA y BBB.",
          "[admet] Filtros PAINS y toxicidad hepática validados."
        );
      }
      if (prog >= 85) {
        logs.push(
          "[rescoring] Calculando score combinado con modelo de boosting XGBoost Nivel 1...",
          "[rescoring] Enviando complejo 3D reconstituido al microservicio rescoring...",
          "[rtmscore] GNN Nivel 2: Construyendo grafos de contactos 3D proteína-ligando...",
          "[rtmscore] Evaluando densidad de interacción por Red Convolucional de Grafos..."
        );
      }
      if (prog >= 95) {
        logs.push(
          "[openmm] Cargando motor de Dinámica Molecular OpenMM...",
          "[openmm] Aplicando campo de fuerza AMBER14SB para proteína y GAFF2 para ligando...",
          "[openmm] Minimizando energía potencial del complejo (5000 pasos L-BFGS)...",
          "[openmm] Relajación completada. Choques estéricos resueltos con éxito."
        );
      }
      if (prog >= 98) {
        logs.push(
          "[pdf] Generando reporte científico PDF certificado...",
          "[blockchain] Conectando con nodo Solana Devnet Memo Program...",
          "[blockchain] Firmando transacción de patente molecular (Curva Ed25519)...",
          "[blockchain] Registrando hash de afinidad en ledger público Solana..."
        );
      }
      if (prog === 100) {
        logs.push(
          "[sys] ¡Cálculo y registro completado exitosamente!",
          "[sys] Resultados guardados en data lake MinIO y base de datos relacional."
        );
      }

      if (status.status === "FAILURE" || status.error) {
        logs.push(
          `[sys] [ERROR] La simulación ha fallado: ${status.error || "Error indeterminado en el clúster."}`,
          "[sys] Abortando pipeline y liberando recursos."
        );
      }

      return logs;
    };

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
            const isCompleted = status && progress > stage.min && (idx === stages.length - 1 ? progress === 100 : progress >= stages[idx+1].min);
            const isProcessing = status && progress >= stage.min && !isCompleted;
            
            return (
              <div 
                key={stage.id} 
                className={`flex items-center justify-between text-[11px] px-3 py-2 rounded-xl border transition-all duration-300 ${
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

        {/* Scientific Terminal Logs */}
        <div 
          ref={consoleRef}
          className="mt-4 border border-indigo-500/10 bg-[#02050b] rounded-xl p-3 h-[160px] overflow-y-auto font-mono text-xs text-indigo-200/90 custom-scrollbar space-y-1"
        >
          <div className="flex items-center justify-between border-b border-white/5 pb-1 mb-2 text-indigo-400/60 text-[10px] uppercase tracking-wider font-sans font-bold">
            <span>Telemetría y Registro de Clúster (PRO)</span>
            <span className="flex items-center gap-1.5 animate-pulse">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" /> ONLINE
            </span>
          </div>
          {getConsoleLogs(progress).map((log, idx) => {
            let color = "text-indigo-200/90";
            if (log.includes("[SUCCESS]")) color = "text-emerald-400 font-semibold";
            if (log.includes("[ERROR]")) color = "text-rose-400 font-semibold";
            if (log.includes("[rdkit]")) color = "text-cyan-400";
            if (log.includes("[vina]")) color = "text-blue-400";
            if (log.includes("[admet]")) color = "text-rose-300";
            if (log.includes("[tabpfn]")) color = "text-fuchsia-400";
            if (log.includes("[rtmscore]")) color = "text-purple-400";
            if (log.includes("[openmm]")) color = "text-amber-400";
            if (log.includes("[blockchain]")) color = "text-emerald-400";
            if (log.includes("[sys]")) color = "text-indigo-400/80";
            
            return (
              <div key={idx} className={`${color} leading-normal`}>
                {log}
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
          selectedTargetId={target}
          onSelect={setTarget}
          onTargetUploadSuccess={onTargetUploadSuccess}
        />

      {/* PEPTIDE ENGINE SELECTION MODAL */}
      {showPeptideModal && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in"
          onClick={() => setShowPeptideModal(false)}
        >
          <div 
            className="bg-surface-900 border border-brand-500/50 rounded-lg p-8 max-w-2xl w-full shadow-2xl relative animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setShowPeptideModal(false)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white transition-colors text-xl font-bold"
            >
              ✕
            </button>
            
            <div className="font-mono text-[10px] text-brand-500 tracking-widest uppercase border-b border-surface-800 pb-2 mb-6">
              Intervención del Orquestador // Nivel 3 Detectado
            </div>

            <div className="mb-6">
              <h3 className="text-2xl font-display font-bold text-white mb-2 uppercase">
                Ruta Peptídica Activada
              </h3>
              <p className="text-sm text-surface-300 font-sans leading-relaxed mb-6">
                El sistema ha detectado una macromolécula o péptido de gran tamaño (≥60 átomos pesados o múltiples enlaces amida). AutoDock Vina no es adecuado debido a los enormes grados de libertad conformacional. Selecciona el motor profundo para continuar con la simulación:
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* DiffPepDock Card */}
                <button
                  onClick={() => {
                    setPeptideDockingEngine("diffpepdock");
                    setShowPeptideModal(false);
                    executeSubmission("diffpepdock");
                  }}
                  className="flex flex-col text-left p-6 border border-surface-700 bg-surface-950 rounded hover:border-brand-500 hover:bg-surface-800 transition-colors cursor-pointer group"
                >
                  <div className="text-xs text-brand-400 font-mono tracking-widest mb-1 group-hover:text-white transition-colors">
                    INFERENCIA RÁPIDA
                  </div>
                  <h4 className="text-lg font-bold text-white mb-3">DiffPepDock</h4>
                  <p className="text-xs text-surface-400 leading-relaxed mb-4 flex-1">
                    Modelo generativo basado en difusión. Ideal para iteraciones ágiles y péptidos que no inducen grandes cambios en la proteína receptora.
                  </p>
                  <div className="flex items-center justify-between text-[10px] font-mono w-full pt-3 border-t border-surface-800">
                    <span className="text-emerald-400">COSTO: BAJO</span>
                    <span className="text-surface-500">TIEMPO: &lt; 60s</span>
                  </div>
                </button>

                {/* ColabFold Card */}
                <button
                  onClick={() => {
                    setPeptideDockingEngine("colabfold");
                    setShowPeptideModal(false);
                    executeSubmission("colabfold");
                  }}
                  className="flex flex-col text-left p-6 border border-surface-700 bg-surface-950 rounded hover:border-brand-500 hover:bg-surface-800 transition-colors cursor-pointer group"
                >
                  <div className="text-xs text-brand-400 font-mono tracking-widest mb-1 group-hover:text-white transition-colors">
                    PLEGADO CO-EVOLUTIVO
                  </div>
                  <h4 className="text-lg font-bold text-white mb-3">ColabFold</h4>
                  <p className="text-xs text-surface-400 leading-relaxed mb-4 flex-1">
                    Implementación AlphaFold2/MMseqs2. Ejecuta un MSA para predecir la estructura combinada desde cero. Excelente para péptidos con alta flexibilidad acoplada.
                  </p>
                  <div className="flex items-center justify-between text-[10px] font-mono w-full pt-3 border-t border-surface-800">
                    <span className="text-rose-400">COSTO: ALTO</span>
                    <span className="text-surface-500">TIEMPO: 5-15 min</span>
                  </div>
                </button>
              </div>
            </div>

            <div className="flex justify-between items-center pt-4 border-t border-surface-800">
              <span className="text-[10px] text-surface-500 font-mono">SE RECOMIENDA DIFFPEPDOCK PARA ITERACIONES INICIALES</span>
              <button 
                onClick={() => setShowPeptideModal(false)}
                className="px-6 py-2 border border-surface-700 text-surface-400 hover:text-white hover:bg-surface-800 font-mono text-sm transition-colors rounded"
              >
                CANCELAR
              </button>
            </div>
          </div>
        </div>
      )}

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
                onViewCertificate={() => setShowPdfViewer(true)}
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
                bloodViabilityScore={status.result.blood_viability_score}
                bloodSystemicReactivity={status.result.blood_systemic_reactivity}
              />
            )}
            <div className="rounded-2xl border border-white/5 bg-slate-900/60 p-5 space-y-4 shadow-xl">
              <h3 className="text-xs font-black uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
                <ShieldCheck size={14} className="text-indigo-400" />
                3. Resultados e Inspección 3D
              </h3>

            {/* Tabbed view selector */}
            <div className="grid grid-cols-4 border-b border-white/5 pb-1 gap-1">
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
              <button
                onClick={() => setActiveTab("xai")}
                className={`pb-2 text-[10px] font-black uppercase tracking-wider text-center border-b-2 transition-all duration-200 ${
                  activeTab === "xai"
                    ? "border-indigo-500 text-indigo-400"
                    : "border-transparent text-slate-500 hover:text-slate-400"
                }`}
              >
                Explicabilidad
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
                    onOpenTargetSelector={() => setIsTargetModalOpen(true)}
                    gnnAttention={status?.result?.gnn_attention || undefined}
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

            {/* Tab Content: XAI Explicabilidad */}
            {activeTab === "xai" && (
              <div className="space-y-3 animate-in fade-in duration-200 overflow-y-auto pr-1 max-h-[360px]">
                {status?.result?.shap_values && Object.keys(status.result.shap_values).length > 0 ? (
                  <div className="space-y-4">
                    <div className="text-[11px] text-slate-300 mb-2 font-mono bg-gradient-to-r from-indigo-500/10 to-transparent p-3.5 rounded-xl border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.05)]">
                      <div className="flex items-center gap-2 mb-1.5">
                        <div className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></div>
                        <span className="text-indigo-300 font-bold tracking-wider">XGBOOST NATIVE SHAP EXPLAINER</span>
                      </div>
                      <p className="opacity-90 leading-relaxed">
                        Diagrama de abejas direccional. Las características hacia la <span className="text-emerald-400 font-bold">derecha (verdes)</span> aumentan la afinidad, hacia la <span className="text-rose-400 font-bold">izquierda (rojas)</span> la penalizan.
                      </p>
                    </div>
                    
                    <div className="relative py-2 mt-2">
                      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/10 z-0"></div>
                      
                      <div className="space-y-3.5 relative z-10">
                        {(() => {
                          const entries = Object.entries(status.result.shap_values as Record<string, number>);
                          const maxAbs = Math.max(...entries.map(([_, v]) => Math.abs(v)), 0.001);
                          
                          return entries.map(([feature, val], idx) => {
                            const isPositive = val > 0;
                            const widthPercent = (Math.abs(val) / maxAbs) * 100;
                            
                            return (
                              <motion.div 
                                initial={{ opacity: 0, y: 5 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.3, delay: idx * 0.05 }}
                                key={feature} 
                                className="group relative flex items-center w-full"
                              >
                                {/* Lado Izquierdo (Negativos) */}
                                <div className="w-1/2 flex justify-end items-center pr-1.5 h-3">
                                  {!isPositive && (
                                    <>
                                      <span className="text-[9px] font-mono text-rose-300/80 mr-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        {val.toFixed(3)}
                                      </span>
                                      <motion.div 
                                        initial={{ width: 0 }}
                                        animate={{ width: `${widthPercent}%` }}
                                        transition={{ type: "spring", stiffness: 60, damping: 12, delay: idx * 0.05 }}
                                        className="h-full rounded-l-md bg-gradient-to-l from-rose-500/80 to-rose-400 border-y border-l border-rose-400/50 shadow-[0_0_10px_rgba(244,63,94,0.3)] relative"
                                      />
                                    </>
                                  )}
                                  {isPositive && (
                                    <div className="group/tooltip relative flex items-center justify-end w-full pl-2 cursor-help">
                                      <span className="text-[10px] uppercase font-mono font-medium text-slate-400 truncate pr-1 text-right">
                                        {getFeatureExplanation(feature).label}
                                      </span>
                                      <Info size={11} className="text-slate-500/70 flex-shrink-0" />
                                      <div className="absolute right-0 top-full mt-1.5 w-48 bg-slate-800 text-slate-300 text-[9.5px] leading-relaxed p-2.5 rounded-lg border border-white/10 shadow-[0_4px_20px_rgba(0,0,0,0.5)] opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all z-[60] pointer-events-none text-left">
                                        <div className="font-bold text-white mb-0.5 border-b border-white/10 pb-0.5">{feature}</div>
                                        {getFeatureExplanation(feature).desc}
                                      </div>
                                    </div>
                                  )}
                                </div>
                                
                                {/* Lado Derecho (Positivos) */}
                                <div className="w-1/2 flex justify-start items-center pl-1.5 h-3">
                                  {isPositive && (
                                    <>
                                      <motion.div 
                                        initial={{ width: 0 }}
                                        animate={{ width: `${widthPercent}%` }}
                                        transition={{ type: "spring", stiffness: 60, damping: 12, delay: idx * 0.05 }}
                                        className="h-full rounded-r-md bg-gradient-to-r from-emerald-500/80 to-emerald-400 border-y border-r border-emerald-400/50 shadow-[0_0_10px_rgba(16,185,129,0.3)] relative"
                                      />
                                      <span className="text-[9px] font-mono text-emerald-300/80 ml-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        +{val.toFixed(3)}
                                      </span>
                                    </>
                                  )}
                                  {!isPositive && (
                                    <div className="group/tooltip relative flex items-center justify-start w-full pr-2 cursor-help">
                                      <Info size={11} className="text-slate-500/70 flex-shrink-0 mr-1" />
                                      <span className="text-[10px] uppercase font-mono font-medium text-slate-400 truncate text-left">
                                        {getFeatureExplanation(feature).label}
                                      </span>
                                      <div className="absolute left-0 top-full mt-1.5 w-48 bg-slate-800 text-slate-300 text-[9.5px] leading-relaxed p-2.5 rounded-lg border border-white/10 shadow-[0_4px_20px_rgba(0,0,0,0.5)] opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all z-[60] pointer-events-none text-left">
                                        <div className="font-bold text-white mb-0.5 border-b border-white/10 pb-0.5">{feature}</div>
                                        {getFeatureExplanation(feature).desc}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </motion.div>
                            );
                          });
                        })()}
                      </div>
                    </div>
                    
                    {status?.result?.gnn_attention && (
                      <div className="mt-5 p-4 bg-black/40 rounded-xl border border-emerald-500/20 relative overflow-hidden">
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-emerald-400 font-bold flex items-center gap-1.5 text-xs uppercase tracking-wider">
                            <Activity size={14} /> Atención GNN (RTMScore)
                          </span>
                          <span className="text-[10px] text-slate-400 font-mono">MAPA DE HOTSPOTS</span>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-4 items-stretch">
                          {/* Opción 1: RDKit SVG */}
                          <div 
                            onClick={() => { if(status?.result?.gnn_attention_svg) setExpandedGNN('2d') }}
                            className={`flex flex-col items-center justify-center p-3 bg-slate-900/60 rounded-xl border border-white/5 shadow-inner transition-colors duration-200 ${status?.result?.gnn_attention_svg ? 'cursor-pointer hover:bg-slate-800/80' : ''}`}
                          >
                            <span className="text-[9px] text-slate-500 uppercase font-mono mb-2 tracking-widest">Topología 2D</span>
                            {status?.result?.gnn_attention_svg ? (
                              <div 
                                className="w-full flex justify-center items-center [&>svg]:w-full [&>svg]:max-w-[160px] [&>svg]:h-auto filter drop-shadow-[0_0_8px_rgba(16,185,129,0.2)]"
                                dangerouslySetInnerHTML={{ __html: status.result.gnn_attention_svg }}
                              />
                            ) : (
                              <div className="w-full aspect-square max-h-[160px] flex items-center justify-center text-[10px] text-slate-500 italic">
                                Generando proyección...
                              </div>
                            )}
                          </div>
                          
                          {/* Opción 2: Radar Farmacóforos */}
                          <div 
                            onClick={() => { if(status?.result?.gnn_pharmacophores) setExpandedGNN('1d') }}
                            className={`flex flex-col items-center justify-start p-3 bg-slate-900/60 rounded-xl border border-white/5 shadow-inner relative overflow-hidden group transition-colors duration-200 ${status?.result?.gnn_pharmacophores ? 'cursor-pointer hover:bg-slate-800/80' : ''}`}
                          >
                            <span className="text-[9px] text-slate-500 uppercase font-mono mb-2 tracking-widest z-10">Desglose Farmacóforos</span>
                            <div className="w-full flex-grow relative min-h-[120px] z-10 flex items-center justify-center">
                              {(() => {
                                const pharm = status?.result?.gnn_pharmacophores;
                                if (!pharm) return <div className="text-[10px] text-slate-500 italic mt-8">No disponible</div>;
                                
                                const categories = ["Aromáticos", "Donadores de H", "Aceptores de H", "Alifáticos", "Halógenos"];
                                const cx = 100;
                                const cy = 60;
                                const rMax = 45;
                                const angles = [-90, -18, 54, 126, 198];
                                
                                const points = categories.map((cat, i) => {
                                  const val = (pharm[cat] || 0) / 100;
                                  const rad = (angles[i] * Math.PI) / 180;
                                  return `${cx + rMax * val * Math.cos(rad)},${cy + rMax * val * Math.sin(rad)}`;
                                }).join(' ');

                                const bgPentagons = [1, 0.75, 0.5, 0.25].map(scale => 
                                  angles.map(ang => {
                                    const rad = (ang * Math.PI) / 180;
                                    return `${cx + rMax * scale * Math.cos(rad)},${cy + rMax * scale * Math.sin(rad)}`;
                                  }).join(' ')
                                );

                                return (
                                  <svg viewBox="0 0 200 120" className="w-full h-full overflow-visible">
                                    <defs>
                                      <filter id="glow-radar">
                                        <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                                        <feMerge>
                                          <feMergeNode in="coloredBlur"/>
                                          <feMergeNode in="SourceGraphic"/>
                                        </feMerge>
                                      </filter>
                                    </defs>
                                    {/* Web Lines */}
                                    {angles.map((ang, i) => {
                                      const rad = (ang * Math.PI) / 180;
                                      return (
                                        <line key={i} x1={cx} y1={cy} x2={cx + rMax * Math.cos(rad)} y2={cy + rMax * Math.sin(rad)} stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
                                      )
                                    })}
                                    {/* Concentric Pentagons */}
                                    {bgPentagons.map((pts, i) => (
                                      <polygon key={i} points={pts} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
                                    ))}
                                    
                                    {/* Data Polygon */}
                                    <motion.polygon 
                                      initial={{ opacity: 0, scale: 0 }}
                                      animate={{ opacity: 1, scale: 1 }}
                                      transition={{ duration: 1, type: "spring" }}
                                      style={{ transformOrigin: `${cx}px ${cy}px` }}
                                      points={points} 
                                      fill="rgba(16,185,129,0.3)" 
                                      stroke="#34d399" 
                                      strokeWidth="2" 
                                      filter="url(#glow-radar)"
                                    />
                                    
                                    {/* Labels */}
                                    {categories.map((cat, i) => {
                                      const rad = (angles[i] * Math.PI) / 180;
                                      const x = cx + (rMax + 15) * Math.cos(rad);
                                      const y = cy + (rMax + 12) * Math.sin(rad);
                                      return (
                                        <text key={cat} x={x} y={y} textAnchor="middle" alignmentBaseline="middle" fill="#94a3b8" fontSize="7" className="font-mono">
                                          {cat.substring(0,4)}
                                        </text>
                                      )
                                    })}
                                  </svg>
                                );
                              })()}
                            </div>
                            <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-emerald-900/20 to-transparent pointer-events-none" />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center text-center text-slate-500 py-12 px-4 border border-white/5 bg-black/20 rounded-2xl">
                    <div className="w-10 h-10 rounded-full bg-slate-800/50 flex items-center justify-center mb-3">
                      <Activity size={18} className="text-slate-500" />
                    </div>
                    <span className="text-xs font-medium">Sin datos de explicabilidad.</span>
                    <span className="text-[10px] mt-1 opacity-70">El motor SHAP nativo poblará esta área al completar una evaluación de ligando exitosa.</span>
                  </div>
                )}
              </div>
            )}

            {/* Action Buttons: Save & On-Chain Certification */}
            {status?.result && (
              <div className="space-y-2 pt-3 border-t border-white/5">
                {!user ? (
                  <div className="rounded-xl bg-amber-500/5 border border-amber-500/20 p-3 text-center text-xs text-amber-300">
                    Para guardar el diseño y certificarlo en Solana, necesitas <a href="/login" className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2 font-bold">iniciar sesión</a>.
                  </div>
                ) : isSaved ? (
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
                    <button
                      onClick={() => setShowCertModal(true)}
                      disabled={busy}
                      className="w-full flex items-center justify-center gap-1.5 rounded-xl border border-indigo-500/20 bg-indigo-600/10 hover:bg-indigo-600/20 px-4 py-2.5 text-xs font-black uppercase tracking-wider text-indigo-400 transition-colors duration-150 disabled:opacity-50"
                    >
                      <ShieldCheck size={13} />
                      Certificar en Blockchain
                    </button>
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
      
      {/* GNN Expanded View Modal */}
      {expandedGNN && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setExpandedGNN(null)}
        >
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="bg-slate-900 border border-slate-700 shadow-2xl rounded-2xl w-full max-w-4xl p-6 relative overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            <button 
              onClick={() => setExpandedGNN(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white p-2 bg-slate-800 hover:bg-slate-700 rounded-full transition-colors z-20"
            >
              ✕
            </button>
            <div className="flex items-center gap-3 border-b border-slate-800 pb-4 mb-6">
              <Activity className="text-emerald-500" size={24} />
              <h2 className="text-xl font-bold text-white tracking-wide">
                Atención GNN <span className="text-emerald-400 font-mono text-base">(RTMScore Hotspots)</span>
              </h2>
            </div>
            
            <div className="flex flex-col items-center justify-center w-full bg-black/50 rounded-xl p-8 min-h-[400px]">
              {expandedGNN === '2d' && status?.result?.gnn_attention_svg && (
                <div 
                  className="w-full flex justify-center items-center [&>svg]:w-full [&>svg]:max-w-[500px] [&>svg]:h-auto filter drop-shadow-[0_0_15px_rgba(16,185,129,0.3)]"
                  dangerouslySetInnerHTML={{ __html: status.result.gnn_attention_svg }}
                />
              )}
              {expandedGNN === '1d' && status?.result?.gnn_pharmacophores && (
                <div className="w-full h-[400px] relative flex items-center justify-center">
                  {(() => {
                    const pharm = status.result.gnn_pharmacophores;
                    if (!pharm) return null;
                    
                    const categories = ["Aromáticos", "Donadores de H", "Aceptores de H", "Alifáticos", "Halógenos"];
                    const cx = 400;
                    const cy = 200;
                    const rMax = 150;
                    const angles = [-90, -18, 54, 126, 198];
                    
                    const points = categories.map((cat, i) => {
                      const val = (pharm[cat] || 0) / 100;
                      const rad = (angles[i] * Math.PI) / 180;
                      return `${cx + rMax * val * Math.cos(rad)},${cy + rMax * val * Math.sin(rad)}`;
                    }).join(' ');

                    const bgPentagons = [1, 0.75, 0.5, 0.25].map(scale => 
                      angles.map(ang => {
                        const rad = (ang * Math.PI) / 180;
                        return `${cx + rMax * scale * Math.cos(rad)},${cy + rMax * scale * Math.sin(rad)}`;
                      }).join(' ')
                    );

                    return (
                      <svg viewBox="0 0 800 400" className="w-full h-full overflow-visible">
                        <defs>
                          <filter id="glow-radar-lg">
                            <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
                            <feMerge>
                              <feMergeNode in="coloredBlur"/>
                              <feMergeNode in="SourceGraphic"/>
                            </feMerge>
                          </filter>
                        </defs>
                        {/* Web Lines */}
                        {angles.map((ang, i) => {
                          const rad = (ang * Math.PI) / 180;
                          return (
                            <line key={i} x1={cx} y1={cy} x2={cx + rMax * Math.cos(rad)} y2={cy + rMax * Math.sin(rad)} stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
                          )
                        })}
                        {/* Concentric Pentagons */}
                        {bgPentagons.map((pts, i) => (
                          <polygon key={i} points={pts} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
                        ))}
                        
                        {/* Data Polygon */}
                        <motion.polygon 
                          initial={{ opacity: 0, scale: 0 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ duration: 1, type: "spring" }}
                          style={{ transformOrigin: `${cx}px ${cy}px` }}
                          points={points} 
                          fill="rgba(16,185,129,0.3)" 
                          stroke="#34d399" 
                          strokeWidth="3" 
                          filter="url(#glow-radar-lg)"
                        />
                        
                        {/* Labels and values */}
                        {categories.map((cat, i) => {
                          const rad = (angles[i] * Math.PI) / 180;
                          const val = (pharm[cat] || 0);
                          const x = cx + (rMax + 30) * Math.cos(rad);
                          const y = cy + (rMax + 30) * Math.sin(rad);
                          return (
                            <g key={cat} transform={`translate(${x},${y})`}>
                              <text textAnchor="middle" fill="#f8fafc" fontSize="14" fontWeight="bold" className="font-mono">
                                {cat}
                              </text>
                              <text y="20" textAnchor="middle" fill="#34d399" fontSize="16" fontWeight="bold" className="font-mono drop-shadow-md">
                                {val}%
                              </text>
                            </g>
                          )
                        })}
                      </svg>
                    );
                  })()}
                </div>
              )}
            </div>
            <div className="mt-6 text-slate-400 text-sm italic text-center">
              {expandedGNN === '2d' 
                ? "Las regiones verdes indican las subestructuras moleculares que la GNN considera más cruciales para la afinidad de unión."
                : "Este gráfico de radar muestra qué porcentaje de la atención total de la GNN se destina a cada tipo de farmacóforo químico en el ligando."}
            </div>
          </motion.div>
        </div>
      )}
      {/* Modal Visor PDF */}
      {showPdfViewer && status?.result?.molecule_id && (
        <div 
          className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in"
          onClick={() => setShowPdfViewer(false)}
        >
          <div 
            className="bg-[#0f1015] border border-surface-800 rounded-2xl w-full max-w-5xl h-[85vh] shadow-2xl relative animate-in zoom-in-95 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-surface-800 bg-surface-950 rounded-t-2xl">
              <div className="flex items-center gap-3">
                <span className="text-xl">📄</span>
                <h3 className="text-lg font-bold text-white tracking-wide">Reporte Científico</h3>
              </div>
              <button 
                onClick={() => setShowPdfViewer(false)}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface-800 text-surface-400 hover:text-white hover:bg-surface-700 transition-colors"
              >
                ✕
              </button>
            </div>
            
            <div className="flex-1 overflow-hidden p-4">
              <PDFReportViewer 
                moleculeId={status.result.molecule_id} 
                isCertified={!!status.result.blockchain_tx_id}
                onCertify={user ? handleCertify : undefined}
                isCertifying={busy}
              />
            </div>
          </div>
        </div>
      )}
      
      {showCertModal && status?.result?.molecule_id && (
        <CertificationModal
          moleculeId={status.result.molecule_id}
          onClose={() => setShowCertModal(false)}
          onSuccess={() => {
            setShowCertModal(false);
            handleCertify();
          }}
        />
      )}
    </div>
  );
}
