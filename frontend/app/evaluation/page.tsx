"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { KetcherEditor } from "../../components/KetcherEditor";
import { MethodDisclaimer } from "../../components/MethodDisclaimer";
import { MoleculeViewer3D } from "../../components/MoleculeViewer3D";
import { ProgressBar } from "../../components/ProgressBar";
import { PropertiesPanel } from "../../components/PropertiesPanel";
import { ReproducibilityInfo } from "../../components/ReproducibilityInfo";
import { ScoreCard } from "../../components/ScoreCard";
import { ScientificWarnings } from "../../components/ScientificWarnings";
import { MolecularInsight } from "../../components/MolecularInsight";

import { getAiReport, getJobStatus, getPoseFile, getProteinFile, getSuggestions, submitEvaluation, validateSmiles, certifyMolecule, downloadCertificate, saveMolecule, getLimitStatus, getTargets, Target } from "../../lib/api";
import type { JobStatus, MolecularSuggestion, ValidationResult } from "../../lib/types";
import { useAuth } from "../../lib/auth";
import { useRouter } from "next/navigation";
import { API_URL } from "../../lib/config";
import { useInterface } from "../../context/InterfaceContext";
import dynamic from "next/dynamic";

const PDFReportViewer = dynamic(() => import("../../components/PDFReportViewer").then(mod => mod.PDFReportViewer), { ssr: false });

const ProEvaluation = dynamic(() => import("../../components/interfaces/pro/ProEvaluation"), {
  ssr: false,
  loading: () => (
    <div className="flex h-screen items-center justify-center bg-[#02050b] text-indigo-400 font-sans p-6">
      <div className="text-center">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent mx-auto mb-4" />
        <span className="text-[10px] font-black uppercase tracking-[0.2em] animate-pulse">Cargando evaluación pro...</span>
      </div>
    </div>
  )
});

const POLL_INTERVAL_MS = 2000;

const PIPELINE_STEPS = [
  {
    index: 0,
    step: "LEVEL 0",
    title: "Curación Estructural",
    tech: "RDKit Engine",
    desc: "El primer paso consiste en asegurar que el diseño dibujado sea químicamente posible en el mundo real. RDKit, nuestro motor de quimioinformática, verifica que los átomos tengan la valencia correcta (por ejemplo, que el carbono no tenga más de 4 enlaces), define el estado de protonación adecuado a pH fisiológico, y establece la quiralidad tridimensional (la 'orientación' geométrica). Si la molécula falla aquí o es inestable, el proceso se detiene antes de gastar valiosos recursos computacionales.",
    icon: "🔬",
    colors: {
      COMPLETED: "border-emerald-500/30 bg-emerald-500/5 text-emerald-400",
      ACTIVE: "border-brand-500 bg-brand-500/10 text-brand-300 shadow-[0_0_12px_rgba(20,241,149,0.1)] animate-pulse",
      IDLE: "border-surface-800/80 bg-surface-950/40 text-surface-500 opacity-60"
    }
  },
  {
    index: 1,
    step: "LEVEL 1",
    title: "Screening Virtual",
    tech: "AutoDock Vina + XGBoost",
    desc: "En esta etapa simulamos físicamente cómo la molécula 3D encaja dentro de la proteína. AutoDock Vina prueba miles de posiciones y ángulos para encontrar el acoplamiento perfecto. Después, los resultados pasan por XGBoost, un algoritmo de Machine Learning que corrige estadísticamente el puntaje de afinidad aprendiendo de miles de estructuras cristalinas reales, eliminando así los falsos positivos típicos de los motores puramente físicos.",
    icon: "🤖",
    colors: {
      COMPLETED: "border-emerald-500/30 bg-emerald-500/5 text-emerald-400",
      ACTIVE: "border-brand-500 bg-brand-500/10 text-brand-300 shadow-[0_0_12px_rgba(20,241,149,0.1)] animate-pulse",
      IDLE: "border-surface-800/80 bg-surface-950/40 text-surface-500 opacity-60"
    }
  },
  {
    index: 2,
    step: "LEVEL 2",
    title: "Viabilidad Sanguínea (MPO)",
    tech: "ADMET-AI + TabPFN",
    desc: "Nivel toxicológico impulsado por redes neuronales y machine learning tabular. Evalúa en milisegundos la probabilidad de absorción intestinal (HIA), el cruce de la barrera hematoencefálica (BBB), y el riesgo sistémico (PAINS/Alertas Médicas). Descarta drogas tóxicas antes del análisis de grafos.",
    icon: "🩸",
    colors: {
      COMPLETED: "border-cyan-500/30 bg-cyan-500/5 text-cyan-400",
      ACTIVE: "border-cyan-400 bg-cyan-500/10 text-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.15)] animate-pulse",
      IDLE: "border-surface-800/80 bg-surface-950/40 text-surface-500 opacity-60"
    }
  },
  {
    index: 3,
    step: "LEVEL 3",
    title: "Análisis Topológico",
    tech: "GNN RTMScore",
    desc: "Aquí usamos Redes Neuronales de Grafos (RTMScore) de aprendizaje profundo para evaluar la topología y forma de la molécula como si fuera un 'grafo' espacial. La IA analiza cómo interactúa cada átomo de tu fármaco con cada aminoácido de la proteína receptora en 3D. Esto nos permite descartar moléculas que 'parecen' encajar matemáticamente, pero que en un entorno biológico real sufrirían choques estéricos severos o serían incompatibles.",
    icon: "🧠",
    colors: {
      COMPLETED: "border-emerald-500/30 bg-emerald-500/5 text-emerald-400",
      ACTIVE: "border-brand-500 bg-brand-500/10 text-brand-300 shadow-[0_0_12px_rgba(20,241,149,0.1)] animate-pulse",
      IDLE: "border-surface-800/80 bg-surface-950/40 text-surface-500 opacity-60"
    }
  },
  {
    index: 4,
    step: "LEVEL 4",
    title: "Refinamiento Dinámico",
    tech: "OpenMM MD Engine",
    desc: "A través del motor OpenMM, sometemos el complejo proteína-fármaco a dinámica molecular y minimización de gradientes conjugados. Imagina esto como 'agitar' suavemente la molécula dentro del bolsillo de la proteína para disipar cualquier tensión física acumulada. Este paso microscópico relaja la estructura, optimiza la formación de puentes de hidrógeno clave y asegura que el acoplamiento sea termodinámicamente estable a largo plazo.",
    icon: "⚡",
    colors: {
      COMPLETED: "border-emerald-500/30 bg-emerald-500/5 text-emerald-400",
      ACTIVE: "border-brand-500 bg-brand-500/10 text-brand-300 shadow-[0_0_12px_rgba(20,241,149,0.1)] animate-pulse",
      IDLE: "border-surface-800/80 bg-surface-950/40 text-surface-500 opacity-60"
    }
  },
  {
    index: 5,
    step: "SECURE",
    title: "Consenso Ledger",
    tech: "Solana Devnet",
    desc: "Finalmente, para proteger la propiedad intelectual de tu descubrimiento de forma transparente, creamos un 'Hash SHA-256' único que actúa como la huella digital matemática de tu molécula. Esta huella se inscribe de manera inmutable en la Blockchain de Solana (Devnet), otorgándote un certificado descentralizado permanente con sello de tiempo criptográfico que demuestra tu autoría en el diseño molecular.",
    icon: "⛓️",
    colors: {
      COMPLETED: "border-emerald-500/30 bg-emerald-500/5 text-emerald-400",
      ACTIVE: "border-brand-500 bg-brand-500/10 text-brand-300 shadow-[0_0_12px_rgba(20,241,149,0.1)] animate-pulse",
      IDLE: "border-surface-800/80 bg-surface-950/40 text-surface-500 opacity-60"
    }
  }
];

export default function EvaluationPage() {
  const { interfaceMode } = useInterface();
  const [showTutorial, setShowTutorial] = useState(true);
  const [selectedPipelineStep, setSelectedPipelineStep] = useState<typeof PIPELINE_STEPS[0] | null>(null);
  const [selectedBiologicalLabel, setSelectedBiologicalLabel] = useState<{title: string, desc: string, icon?: string} | null>(null);
  const [selectedTutorialStep, setSelectedTutorialStep] = useState<{title: string, desc: string, step: number} | null>(null);

  // --- Input state ---
  const [smiles, setSmiles] = useState("CC(=O)Oc1ccccc1C(=O)O");
  const [target, setTarget] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<"HUMANOS" | "PATOGENOS" | "">("");
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [activeSubcategory, setActiveSubcategory] = useState<string>("");
  const [targets, setTargets] = useState<Target[]>([]);
  const [loadingTargets, setLoadingTargets] = useState(true);

  const loadTargets = () => {
    setLoadingTargets(true);
    getTargets()
      .then((data) => {
        setTargets(data);
      })
      .catch((err) => console.error("Error loading targets:", err))
      .finally(() => setLoadingTargets(false));
  };

  useEffect(() => {
    loadTargets();
  }, []);

  // --- Pipeline state ---
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isControl, setIsControl] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // --- 3D viewer state ---
  const [proteinData, setProteinData] = useState<string | null>(null);
  const [poseData, setPoseData] = useState<string | null>(null);

  // --- Suggestions state ---
  const [suggestions, setSuggestions] = useState<MolecularSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  // --- AI Report state (async, decoupled from main pipeline) ---
  const [aiReport, setAiReport] = useState<string | null>(null);
  const [displayedReport, setDisplayedReport] = useState("");
  const [loadingAiReport, setLoadingAiReport] = useState(false);

  // --- Derived State ---
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const isTerminal = status?.status === "SUCCESS" || status?.status === "FAILURE";
  const canEvaluate = !!validation?.is_valid && target.length >= 4;

  const getStepState = (stepIndex: number) => {
    if (!status) return "IDLE";
    if (isTerminal) {
      if (status.status === "SUCCESS") {
        return "COMPLETED";
      }
      return "IDLE";
    }

    const progress = status.progress;
    if (stepIndex === 0) { // RDKit
      if (progress > 20) return "COMPLETED";
      if (progress >= 1 && progress <= 20) return "ACTIVE";
      return "IDLE";
    }
    if (stepIndex === 1) { // Vina + XGBoost
      if (progress > 50) return "COMPLETED";
      if (progress > 20 && progress <= 50) return "ACTIVE";
      return "IDLE";
    }
    if (stepIndex === 2) { // ADMET-AI + TabPFN
      if (progress > 70) return "COMPLETED";
      if (progress > 50 && progress <= 70) return "ACTIVE";
      return "IDLE";
    }
    if (stepIndex === 3) { // GNN RTMScore
      if (progress > 85) return "COMPLETED";
      if (progress > 70 && progress <= 85) return "ACTIVE";
      return "IDLE";
    }
    if (stepIndex === 4) { // OpenMM
      if (progress > 95) return "COMPLETED";
      if (progress > 85 && progress <= 95) return "ACTIVE";
      return "IDLE";
    }
    if (stepIndex === 5) { // Solana
      if (progress === 100 || status.status === "done") return "COMPLETED";
      if (progress > 95 && progress < 100) return "ACTIVE";
      return "IDLE";
    }
    return "IDLE";
  };

  const { user } = useAuth();
  const router = useRouter();

  const handleSave = useCallback(async (customName?: string) => {
    if (!status?.result?.molecule_id) return;
    try {
      setBusy(true);
      await saveMolecule(status.result.molecule_id, customName);
      setIsSaved(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }, [status]);

  const handleCertify = useCallback(async () => {
    if (!status?.result?.molecule_id) return;

    setStatus((prev) => {
      if (!prev || !prev.result) return prev;
      return {
        ...prev,
        result: { ...prev.result, blockchain_tx_id: "certified_via_modal" },
      };
    });
    setIsSaved(true);
  }, [status]);

  const handleDownloadCertificate = useCallback(async () => {
    if (!status?.result?.molecule_id) return;
    try {
      setBusy(true);
      await downloadCertificate(status.result.molecule_id);
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setBusy(false);
    }
  }, [status]);

  const handleDownloadComplex = useCallback(async () => {
    if (!status?.result?.molecule_id) return;
    try {
      setBusy(true);
      const url = `${API_URL}/evaluation/files/complex/${status.result.molecule_id}`;
      const a = document.createElement("a");
      a.href = url;
      a.download = `complex_${status.result.molecule_id}.pdb`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setBusy(false);
    }
  }, [status]);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (tid: string) => {
      stopPolling();
      pollingRef.current = setInterval(async () => {
        try {
          const polled = await getJobStatus(tid);
          setStatus(polled);
          if (polled.status === "SUCCESS" || polled.status === "FAILURE") {
            stopPolling();
          }
        } catch {
          // silently retry
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling],
  );

  useEffect(() => () => stopPolling(), [stopPolling]);

  useEffect(() => {
    if (!status?.result?.molecule_id) return;
    const moleculeId = status.result.molecule_id;
    getProteinFile(moleculeId).then((protein) => setProteinData(protein));
    getPoseFile(moleculeId).then((pose) => setPoseData(pose));
  }, [status?.result?.molecule_id]);

  useEffect(() => {
    // NOTA: El módulo de interpretación de IA se encuentra inactivo en producción.
    // Se prioriza el Reporte Científico PDF que contiene datos moleculares de grado clínico.
    return;

    const moleculeId = status?.result?.molecule_id;
    if (!moleculeId) return;
    setAiReport(null);
    setLoadingAiReport(true);

    let isMounted = true;
    const fetchStream = async () => {
      try {
        // Necesitamos importar API_URL y getAuthHeaders si no están en scope,
        // pero podemos usar window.location.origin o importarlos.
        // wait, api.ts is usually imported as `import * as api from "@/lib/api";`
        // so we can use api.API_URL
      } catch (e) {
      }
    };
    // We will use native fetch to the stream endpoint
    
    // Attempt to get the correct URL from api module if we could import it, 
    // but we can just hardcode the logic for token parsing:
    const headers: Record<string, string> = {};
    try {
      const stored = localStorage.getItem("moldesign_auth");
      if (stored) {
        const parsed = JSON.parse(stored as string);
        if (parsed.token) headers["Authorization"] = `Bearer ${parsed.token}`;
      }
    } catch (e) {}

    const fetchAiStream = async () => {
      try {
        let url = process.env.NEXT_PUBLIC_API_URL;
        if (!url) {
           url = window.location.hostname === "localhost" ? "http://localhost:8010" : `${window.location.protocol}//${window.location.hostname}:8010`;
        }
        
        const res = await fetch(`${url}/evaluation/ai-report/${moleculeId}/stream`, {
          headers
        });
        
        if (!res.ok) throw new Error("Network error");
        if (!res.body) throw new Error("No body in response");
        
        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        
        if (isMounted) {
          setLoadingAiReport(false);
          setAiReport("");
        }

        let done = false;
        while (!done) {
          const { value, done: readerDone } = await reader.read();
          done = readerDone;
          if (value) {
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split("\n\n");
            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try {
                  const tokenText = JSON.parse(line.slice(6));
                  if (isMounted) {
                    setAiReport((prev) => (prev || "") + tokenText);
                  }
                } catch (e) {
                  // ignore JSON parse errors for incomplete chunks, though SSE chunks should be complete
                }
              }
            }
          }
        }
      } catch (error) {
        if (isMounted) {
          setAiReport("No se pudo generar la interpretación. Revisa el servidor local.");
          setLoadingAiReport(false);
        }
      }
    };
    
    fetchAiStream();

    return () => {
      isMounted = false;
    };
  }, [status?.result?.molecule_id]);

  useEffect(() => {
    if (!aiReport) {
      setDisplayedReport("");
      return;
    }
    // Removemos el typewriter effect (ya que el streaming es en tiempo real real)
    setDisplayedReport(aiReport);
  }, [aiReport]);

  useEffect(() => {
    if (!status?.result?.total_score) return;
    const r = status.result;
    setLoadingSuggestions(true);
    getSuggestions(
      smiles,
      {
        molecular_weight: r.molecular_weight,
        log_p: r.log_p,
        tpsa: r.tpsa,
        hbd: r.hbd,
        hba: r.hba,
        rotatable_bonds: r.rotatable_bonds,
        qed: r.qed,
      },
      {
        total_score: r.total_score,
        affinity_kcal: r.affinity_kcal,
        adme_score: r.adme_score,
        druglikeness_score: r.druglikeness_score,
      },
    )
      .then((data) => setSuggestions(data.suggestions))
      .catch(() => setSuggestions([]))
      .finally(() => setLoadingSuggestions(false));
  }, [status?.result?.total_score]);

  const handleValidate = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await validateSmiles(smiles);
      setValidation(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = async (
    gridCenter?: [number, number, number],
    gridSize?: [number, number, number],
    customHotspots?: string[],
    peptideDockingEngine?: "diffpepdock" | "colabfold"
  ) => {
    setBusy(true);
    setError(null);
    setStatus(null);
    setTaskId(null);
    setSuggestions([]);
    try {
      if (!target || target.length < 4) {
        setError("Selección inválida: Debes elegir un Objetivo Biológico (Target) del catálogo antes de evaluar.");
        setBusy(false);
        return;
      }
      const limitInfo = await getLimitStatus();
      if (limitInfo.is_limited && limitInfo.remaining <= 0) {
        setError(`Has alcanzado el límite de ${limitInfo.max} evaluaciones gratuitas. Regístrate para continuar diseñando.`);
        setBusy(false);
        return;
      }

      const result = await submitEvaluation(smiles, target, isControl, gridCenter, gridSize, customHotspots, peptideDockingEngine);
      setTaskId(result.task_id);
      setStatus({
        task_id: result.task_id,
        status: "submitted",
        progress: 0,
        result: null,
        error: null,
        started_at: null,
        finished_at: null,
      });
      startPolling(result.task_id);
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("403")) {
        try {
          const jsonError = JSON.parse(msg.split(": ")[1]);
          setError(jsonError.detail);
        } catch {
          setError("Límite de prueba alcanzado. Regístrate gratis para continuar.");
        }
      } else {
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  const handleReset = () => {
    stopPolling();
    setValidation(null);
    setTaskId(null);
    setStatus(null);
    setError(null);
    setSuggestions([]);
    setPoseData(null);
    setProteinData(null);
    setIsSaved(false);
  };

  const handleUseSuggestion = async (sug: MolecularSuggestion) => {
    if (!sug.smiles) {
      setError("La sugerencia no contiene una estructura SMILES válida.");
      return;
    }
    setSmiles(sug.smiles);
    handleReset();
    setBusy(true);
    try {
      const result = await validateSmiles(sug.smiles);
      setValidation(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (interfaceMode === "PRO") {
    return (
      <ProEvaluation 
        smiles={smiles}
        setSmiles={setSmiles}
        target={target}
        setTarget={setTarget}
        targets={targets}
        loadingTargets={loadingTargets}
        onTargetUploadSuccess={loadTargets}
        validation={validation}
        setValidation={setValidation}
        taskId={taskId}
        setTaskId={setTaskId}
        status={status}
        setStatus={setStatus}
        busy={busy}
        setBusy={setBusy}
        error={error}
        setError={setError}
        isControl={isControl}
        setIsControl={setIsControl}
        isSaved={isSaved}
        setIsSaved={setIsSaved}
        proteinData={proteinData}
        poseData={poseData}
        suggestions={suggestions}
        loadingSuggestions={loadingSuggestions}
        handleSave={handleSave}
        handleCertify={handleCertify}
        handleDownloadCertificate={handleDownloadCertificate}
        handleDownloadComplex={handleDownloadComplex}
        handleValidate={handleValidate}
        handleSubmit={handleSubmit}
        handleReset={handleReset}
        handleUseSuggestion={handleUseSuggestion}
        startPolling={startPolling}
        stopPolling={stopPolling}
      />
    );
  }

  return (
    <main className="pb-12 bg-[#0b0f19] text-white min-h-screen">
      {/* Title */}
      <div className="mb-6 border-b border-indigo-900/50 pb-4 bg-surface-950 p-6 rounded-b-3xl shadow-xl">
        <div className="max-w-[1400px] mx-auto px-4 md:px-8">
          <h1 className="text-3xl font-bold uppercase text-white flex items-center gap-3 tracking-wide">
            <span className="text-4xl">🎓</span> MolDesign Campus Virtual
          </h1>
          <p className="mt-2 text-xs text-indigo-400 font-mono tracking-widest uppercase">
            [ Entorno de Pruebas Académico ]
          </p>
        </div>
      </div>

      {/* PIPELINE HORIZONTAL SUPERIOR */}
      <div className="px-4 md:px-8 max-w-[1400px] mx-auto mb-8">
        <h3 className="text-sm font-bold text-indigo-400 uppercase mb-4 tracking-widest border-b border-indigo-900/50 pb-2">
          Pipeline de Evaluación
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {PIPELINE_STEPS.map((s) => {
            const stepState = getStepState(s.index);
            const cardStyle = s.colors[stepState];
            
            return (
              <button
                key={s.step}
                onClick={() => setSelectedPipelineStep(s)}
                className={`rounded-xl border p-3 transition-all duration-300 relative overflow-hidden flex flex-col justify-between text-left hover:scale-105 hover:shadow-[0_0_15px_rgba(99,102,241,0.2)] hover:border-indigo-500/50 cursor-pointer ${cardStyle}`}
              >
                {stepState === "ACTIVE" && (
                  <span className="absolute top-0 left-0 w-full h-[2px] bg-brand-500 animate-pulse" />
                )}
                
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[9px] font-black uppercase tracking-widest font-mono opacity-60 truncate pr-1">
                      {s.tech}
                    </span>
                    <span className="text-sm">{s.icon}</span>
                  </div>
                  <h3 className="text-[10px] sm:text-xs font-black text-white uppercase tracking-wider mb-1">
                    {s.title}
                  </h3>
                </div>
                
                <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between">
                  <span className="text-[9px] font-black tracking-widest opacity-40 font-mono">
                    {s.step}
                  </span>
                  <span className="text-[9px] font-bold uppercase tracking-wider font-mono">
                    {stepState === "COMPLETED" && <span className="text-emerald-400 flex items-center gap-0.5">✓ Listo</span>}
                    {stepState === "ACTIVE" && <span className="text-brand-400 flex items-center gap-1 animate-pulse"><span className="h-1.5 w-1.5 rounded-full bg-brand-400 animate-ping inline-block" />Corriendo</span>}
                    {stepState === "IDLE" && <span className="text-surface-600">Espera</span>}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* CONTENIDO PRINCIPAL (Una sola columna) */}
      <div className="flex flex-col gap-6 px-4 md:px-8 max-w-[1400px] mx-auto">
        
        {/* Toggle Tutorial Button */}
        <div className="flex justify-end">
          <button 
            onClick={() => setShowTutorial(!showTutorial)}
            className="flex items-center gap-2 text-xs font-bold text-indigo-400 hover:text-indigo-300 transition-colors bg-indigo-950/30 px-3 py-1.5 rounded-lg border border-indigo-500/30"
          >
            {showTutorial ? "Ocultar Guía de Práctica" : "Mostrar Guía de Práctica"}
          </button>
        </div>

        {/* Guía de Práctica (Colapsable) */}
        {showTutorial && (
          <section className="border border-indigo-500/30 bg-indigo-950/20 p-6 relative group rounded-xl animate-in fade-in slide-in-from-top-2">
            <div className="absolute top-0 right-0 bg-indigo-500 text-white font-bold text-[10px] px-3 py-1 uppercase tracking-widest rounded-bl-lg rounded-tr-xl">Tutorial</div>
            <h2 className="text-xl font-bold text-indigo-400 uppercase mb-5 flex items-center gap-2">
              📋 Guía de Práctica
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-sans text-xs text-slate-300">
              <button 
                onClick={() => setSelectedTutorialStep({
                  step: 1,
                  title: "Diseño Molecular",
                  desc: "Utiliza el editor químico inferior para esbozar tu candidato a fármaco. Puedes dibujar la estructura átomo por átomo usando la interfaz 2D, o pegar un código SMILES si ya conoces la representación en texto de tu molécula. ¡Experimenta añadiendo diferentes grupos funcionales para mejorar las propiedades!"
                })}
                className="text-left bg-surface-950/50 p-4 border border-surface-800 hover:border-indigo-500/50 hover:bg-surface-900 transition-colors rounded-xl shadow-lg hover:scale-[1.02]"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-400 font-bold font-mono">1</span>
                  <strong className="text-white">Diseño Molecular</strong>
                </div>
                Utiliza el editor químico inferior para esbozar tu candidato a fármaco.
              </button>
              
              <button 
                onClick={() => setSelectedTutorialStep({
                  step: 2,
                  title: "Selección de Diana",
                  desc: "Elige la proteína objetivo del catálogo según el área terapéutica. Las proteínas son las 'cerraduras' de las enfermedades. Al seleccionar un target (ej. receptores neuronales o paredes celulares bacterianas), el modelo de IA evaluará si tu molécula ('la llave') encaja perfectamente en esa cerradura específica."
                })}
                className="text-left bg-surface-950/50 p-4 border border-surface-800 hover:border-indigo-500/50 hover:bg-surface-900 transition-colors rounded-xl shadow-lg hover:scale-[1.02]"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-400 font-bold font-mono">2</span>
                  <strong className="text-white">Selección de Diana</strong>
                </div>
                Elige la proteína objetivo del catálogo según el área terapéutica.
              </button>
              
              <button 
                onClick={() => setSelectedTutorialStep({
                  step: 3,
                  title: "Simulación",
                  desc: "Inicia la evaluación haciendo clic en 'Ejecutar Docking'. Nuestro pipeline de inteligencia artificial procesará las propiedades fisicoquímicas, realizará simulación de docking con AutoDock Vina, ajustará la afinidad espacialmente con XGBoost, y finalmente evaluará la topología 3D con Redes Neuronales de Grafos (GNN) para obtener un Score Compuesto definitivo."
                })}
                className="text-left bg-surface-950/50 p-4 border border-surface-800 hover:border-indigo-500/50 hover:bg-surface-900 transition-colors rounded-xl shadow-lg hover:scale-[1.02]"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-400 font-bold font-mono">3</span>
                  <strong className="text-white">Simulación</strong>
                </div>
                Inicia la evaluación. Nuestro pipeline de IA procesará el score.
              </button>
            </div>
          </section>
        )}

      <section className="space-y-4 rounded-2xl border border-surface-800 bg-surface-900 p-5">
        <div className="grid gap-5 md:grid-cols-3">
          <div className="md:col-span-2">
            <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-surface-400">
              Molécula (SMILES)
            </label>
            <KetcherEditor
              initialSmiles={smiles}
              onSmilesChange={(s) => setSmiles(s)}
            />
          </div>

          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-surface-400">
                Objetivo Biológico (Target)
              </label>
              {loadingTargets ? (
                <div className="w-full rounded-xl border border-surface-700 bg-surface-950 px-4 py-3 font-mono text-sm text-surface-500">
                  Cargando catálogo...
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Origen del Target: Humanos vs Patógenos */}
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedCategory("HUMANOS");
                          setActiveCategory("");
                          setActiveSubcategory("");
                          setTarget("");
                        }}
                        disabled={!!taskId && !isTerminal}
                        className={`px-3 py-2.5 rounded-xl border text-xs font-semibold uppercase tracking-wider transition-all duration-200 ${
                          selectedCategory === "HUMANOS"
                            ? "bg-brand-500/10 border-brand-500 text-brand-400 shadow-[0_0_15px_rgba(20,241,149,0.1)]"
                            : "bg-surface-950 border-surface-800 text-surface-400 hover:border-surface-700 hover:text-surface-300"
                        }`}
                      >
                        🧬 Humano (H. sapiens)
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedCategory("PATOGENOS");
                          setActiveCategory("");
                          setActiveSubcategory("");
                          setTarget("");
                        }}
                        disabled={!!taskId && !isTerminal}
                        className={`px-3 py-2.5 rounded-xl border text-xs font-semibold uppercase tracking-wider transition-all duration-200 ${
                          selectedCategory === "PATOGENOS"
                            ? "bg-brand-500/10 border-brand-500 text-brand-400 shadow-[0_0_15px_rgba(20,241,149,0.1)]"
                            : "bg-surface-950 border-surface-800 text-surface-400 hover:border-surface-700 hover:text-surface-300"
                        }`}
                      >
                        🦠 Patógenos
                      </button>
                    </div>

                    {/* Categorías Principales */}
                    {selectedCategory === "HUMANOS" && (
                      <div className="grid grid-cols-2 gap-2 mt-2">
                        {[
                          { id: "neurologia", name: "Neurología", icon: "🧠" },
                          { id: "oncologia", name: "Oncología", icon: "🧬" },
                          { id: "cardiologia", name: "Cardiología", icon: "❤️" },
                          { id: "endocrinologia", name: "Endocrinología", icon: "🩸" },
                          { id: "nutricion", name: "Nutrición", icon: "🥑" }
                        ].map((cat) => (
                          <button
                            key={cat.id}
                            type="button"
                            onClick={() => {
                              setActiveCategory(cat.id);
                              setActiveSubcategory("");
                              setTarget("");
                            }}
                            disabled={!!taskId && !isTerminal}
                            className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border text-xs font-medium transition-all duration-200 ${
                              cat.id === "nutricion" ? "col-span-2" : ""
                            } ${
                              activeCategory === cat.id
                                ? "bg-brand-500/5 border-brand-500/60 text-brand-300"
                                : "bg-surface-950 border-surface-800/80 text-surface-300 hover:border-surface-700"
                            }`}
                          >
                            <span>{cat.icon}</span>
                            <span className="truncate">{cat.name}</span>
                          </button>
                        ))}
                      </div>
                    )}

                    {selectedCategory === "PATOGENOS" && (
                      <div className="grid grid-cols-1 gap-2 mt-2">
                        {[
                          { id: "bacterias_pared", name: "Pared Celular Bacteriana", icon: "🦠" },
                          { id: "bacterias_replicacion", name: "Replicación de ADN", icon: "🧬" },
                          { id: "bacterias_resistencia", name: "Resistencia a Antibióticos", icon: "🛡️" }
                        ].map((cat) => (
                          <button
                            key={cat.id}
                            type="button"
                            onClick={() => {
                              setActiveCategory(cat.id);
                              setActiveSubcategory(cat.id); // Para patógenos la subcategoría es la misma
                              setTarget("");
                            }}
                            disabled={!!taskId && !isTerminal}
                            className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border text-xs font-medium transition-all duration-200 ${
                              activeCategory === cat.id
                                ? "bg-brand-500/5 border-brand-500/60 text-brand-300"
                                : "bg-surface-950 border-surface-800/80 text-surface-300 hover:border-surface-700"
                            }`}
                          >
                            <span>{cat.icon}</span>
                            <span className="truncate">{cat.name}</span>
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Subcategorías (Ej: dentro de Oncología) */}
                    {selectedCategory === "HUMANOS" && activeCategory === "oncologia" && (
                      <div className="grid grid-cols-2 gap-2 mt-2 border-t border-surface-800/60 pt-2 animate-in fade-in slide-in-from-top-1">
                        {[
                          { id: "cancer_mama", name: "Cáncer de Mama", icon: "🎀" },
                          { id: "inmunoterapia", name: "Inmunoterapia", icon: "🛡️" }
                        ].map((sub) => (
                          <button
                            key={sub.id}
                            type="button"
                            onClick={() => {
                              setActiveSubcategory(sub.id);
                              setTarget("");
                            }}
                            disabled={!!taskId && !isTerminal}
                            className={`w-full flex items-center justify-center gap-1 px-2 py-2 rounded-lg border text-[10px] sm:text-[11px] font-semibold uppercase tracking-wider transition-all duration-200 min-w-0 truncate ${
                              activeSubcategory === sub.id
                                ? "bg-brand-500/10 border-brand-500/80 text-brand-300"
                                : "bg-surface-950 border-surface-850 text-surface-400 hover:border-surface-800"
                            }`}
                          >
                            <span>{sub.icon}</span>
                            <span className="truncate">{sub.name}</span>
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Receptores desglosados (Botones finales de targets) */}
                    {((selectedCategory === "HUMANOS" && activeCategory) || (selectedCategory === "PATOGENOS" && activeCategory)) && (
                      <div className="mt-3 space-y-2 border-t border-surface-800/60 pt-3 animate-in fade-in slide-in-from-top-2">
                        <label className="block text-[10px] font-semibold uppercase tracking-wider text-surface-400">
                          Seleccionar Receptor Específico
                        </label>
                        
                        <div className="grid gap-1.5 max-h-[220px] overflow-y-auto pr-1">
                          {(() => {
                            let filteredTargets: Target[] = [];
                            
                            if (selectedCategory === "HUMANOS") {
                              if (activeCategory === "neurologia") {
                                filteredTargets = targets.filter(t => t.pdb_id === "7E2Y");
                              } else if (activeCategory === "oncologia") {
                                if (activeSubcategory === "cancer_mama") {
                                  // Los 10 targets de cáncer de mama (activos e inactivos)
                                  const breastCancerPdbIds = ["3ERT", "1ERE", "5L2I", "2W96", "4JPS", "3O96", "4EKL", "3PP0", "4ZZZ", "1HVY"];
                                  filteredTargets = targets.filter(t => breastCancerPdbIds.includes(t.pdb_id));
                                } else if (activeSubcategory === "inmunoterapia") {
                                  filteredTargets = targets.filter(t => t.pdb_id === "3OSK");
                                }
                              } else if (activeCategory === "cardiologia") {
                                filteredTargets = targets.filter(t => t.pdb_id === "2P4E" || t.pdb_id === "6U26");
                              } else if (activeCategory === "endocrinologia") {
                                filteredTargets = targets.filter(t => t.name.toUpperCase().includes("GLP"));
                              } else if (activeCategory === "nutricion") {
                                const nutritionPdbIds = ["4I5I", "6D8X", "5IKR", "4RER"];
                                filteredTargets = targets.filter(t => nutritionPdbIds.includes(t.pdb_id));
                              }
                            } else if (selectedCategory === "PATOGENOS") {
                              if (activeCategory === "bacterias_pared") {
                                filteredTargets = targets.filter(t => t.pdb_id.includes("PBP"));
                              } else if (activeCategory === "bacterias_replicacion") {
                                filteredTargets = targets.filter(t => t.name.toLowerCase().includes("girasa"));
                              } else if (activeCategory === "bacterias_resistencia") {
                                filteredTargets = targets.filter(t => t.name.toLowerCase().includes("lactamasa"));
                              }
                            }

                            if (filteredTargets.length === 0) {
                              return (
                                <div className="text-xs text-surface-500 py-2 italic">
                                  Próximamente: Más receptores en esta categoría
                                </div>
                              );
                            }

                            // Ordenar alfabéticamente por PDB ID para consistencia visual
                            const sortedTargets = [...filteredTargets].sort((a, b) => a.pdb_id.localeCompare(b.pdb_id));

                            return sortedTargets.map((t) => {
                              const isSelected = target === t.pdb_id;
                              
                              // Subtítulo clínico/nutricional en el botón para guiar al usuario
                              let targetSubtype = "";
                              if (t.pdb_id === "3ERT") targetSubtype = "Receptor Estrogénico Inactivo (ER-α)";
                              else if (t.pdb_id === "1ERE") targetSubtype = "Receptor Estrogénico Activo (ER-α)";
                              else if (t.pdb_id === "3O96") targetSubtype = "Vía AKT Inactiva (AKT1)";
                              else if (t.pdb_id === "4EKL") targetSubtype = "Vía AKT Activa (AKT1)";
                              else if (t.pdb_id === "5L2I") targetSubtype = "Ciclo Celular (CDK6)";
                              else if (t.pdb_id === "2W96") targetSubtype = "Ciclo Celular (CDK4)";
                              else if (t.pdb_id === "4JPS") targetSubtype = "Vía PI3K (PIK3CA WT)";
                              else if (t.pdb_id === "3PP0") targetSubtype = "Receptor RTK (HER2)";
                              else if (t.pdb_id === "4ZZZ") targetSubtype = "Reparación ADN (PARP1)";
                              else if (t.pdb_id === "1HVY") targetSubtype = "Quimioterapia (TS)";
                              else if (t.pdb_id === "7E2Y") targetSubtype = "Receptor de Serotonina (5-HT1A)";
                              else if (t.pdb_id === "3OSK") targetSubtype = "Inhibidor Checkpoint (CTLA-4)";
                              else if (t.pdb_id === "2P4E") targetSubtype = "PCSK9 Sitio Ortostérico";
                              else if (t.pdb_id === "6U26") targetSubtype = "PCSK9 Sitio Alostérico";
                              else if (t.pdb_id === "6B3J") targetSubtype = "GLP-1R Extracelular Activo (ECD)";
                              else if (t.pdb_id === "6X1A") targetSubtype = "GLP-1R Transmembrana Activo (TMD)";
                              else if (t.pdb_id === "5VEW") targetSubtype = "GLP-1R Transmembrana Inactivo (TMD)";
                              else if (t.pdb_id === "4I5I") targetSubtype = "Sirtuina SIRT1 Activa (Longevidad)";
                              else if (t.pdb_id === "6D8X") targetSubtype = "Receptor PPAR-γ Activo (Metabolismo)";
                              else if (t.pdb_id === "5IKR") targetSubtype = "Enzima COX-2 Inhibida (Antiinflamatorio)";
                              else if (t.pdb_id === "4RER") targetSubtype = "Complejo AMPK Activo (Energía Celular)";

                              return (
                                <button
                                  key={t.pdb_id}
                                  type="button"
                                  onClick={() => setTarget(t.pdb_id)}
                                  disabled={!!taskId && !isTerminal}
                                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl border text-left transition-all duration-200 min-w-0 ${
                                    isSelected
                                      ? "bg-brand-500/10 border-brand-500 text-brand-300 shadow-[0_0_12px_rgba(20,241,149,0.12)] font-semibold"
                                      : "bg-surface-950/80 border-surface-850/80 text-surface-300 hover:border-surface-800 hover:bg-surface-950"
                                  }`}
                                >
                                  <div className="flex flex-col min-w-0 pr-2 overflow-hidden">
                                    <div className="flex items-center gap-1.5 min-w-0">
                                      <span className="font-mono text-xs text-brand-400 font-bold">{t.pdb_id}</span>
                                      <span className="text-xs truncate">{t.name}</span>
                                    </div>
                                    {targetSubtype && (
                                      <span className="text-[10px] text-surface-400 font-medium mt-0.5">{targetSubtype}</span>
                                    )}
                                  </div>
                                  {t.is_hot && (
                                    <span className="text-xs animate-pulse">🔥</span>
                                  )}
                                </button>
                              );
                            });
                          })()}
                        </div>
                      </div>
                    )}
                  </div>
              )}
              {(() => {
                const selected = targets.find((t) => t.pdb_id === target);
                if (!selected) return null;
                return (
                  <div className="mt-3 flex flex-wrap gap-2 items-center">
                    <button 
                      onClick={() => setSelectedBiologicalLabel({
                        title: "Familia Estructural",
                        desc: "Clasificación biológica de la proteína. Determina los parámetros del modelo de scoring ML v4.0.",
                        icon: "🧬"
                      })}
                      className="px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/20 text-[10px] uppercase tracking-tighter font-semibold hover:bg-brand-500/20 hover:scale-105 transition-all"
                    >
                      {selected.structural_family || "Other"}
                    </button>
                    
                    <button
                      onClick={() => setSelectedBiologicalLabel({
                        title: "Requerimiento CNS",
                        desc: selected.requires_cns 
                          ? "Este target reside en el Sistema Nervioso Central (Cerebro). El sistema aplicará penalizaciones si la molécula diseñada no es capaz de cruzar la Barrera Hematoencefálica (BBB)."
                          : "Target periférico. No requiere cruzar la Barrera Hematoencefálica para su efectividad terapéutica.",
                        icon: selected.requires_cns ? "🧠" : "🛡️"
                      })}
                      className={`px-2 py-0.5 rounded-full border text-[10px] tracking-tighter uppercase font-semibold hover:scale-105 transition-all ${
                        selected.requires_cns ? "bg-purple-500/10 text-purple-400 border-purple-500/20 hover:bg-purple-500/20" : "bg-blue-500/10 text-blue-400 border-blue-500/20 hover:bg-blue-500/20"
                      }`}
                    >
                      {selected.requires_cns ? "🧠 CNS Active" : "🛡️ Peripheral"}
                    </button>

                    {selected.is_hot && (
                      <button
                        onClick={() => setSelectedBiologicalLabel({
                          title: "Hot Target (Trending)",
                          desc: "Esta proteína es de altísima relevancia farmacéutica actual. Muchas investigaciones y startups biotecnológicas están buscando fármacos para esta diana en este momento.",
                          icon: "🔥"
                        })}
                        className="px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400 border border-orange-500/40 text-[10px] uppercase tracking-wider font-black animate-pulse shadow-[0_0_10px_rgba(249,115,22,0.3)] hover:scale-105 transition-all hover:bg-orange-500/30"
                      >
                        🔥 Hot Target
                      </button>
                    )}

                    {selected.organism && (
                      <button
                        onClick={() => setSelectedBiologicalLabel({
                          title: "Organismo de Origen",
                          desc: "Fuente biológica de la estructura proteica utilizada para el docking computacional.",
                          icon: "🧬"
                        })}
                        className="px-2 py-0.5 rounded-full bg-surface-800 text-surface-400 border border-surface-700 text-[10px] tracking-tighter uppercase hover:bg-surface-700 hover:scale-105 transition-all"
                      >
                        🧬 {selected.organism}
                      </button>
                    )}

                    {selected.resolution && (
                      <button
                        onClick={() => setSelectedBiologicalLabel({
                          title: "Resolución Cristalográfica",
                          desc: "Es la 'calidad de imagen' de la estructura 3D obtenida por Cristalografía de Rayos X o Cryo-EM. Valores menores a 2.5 Å indican una altísima resolución geométrica, lo que garantiza simulaciones de docking muy precisas y confiables.",
                          icon: "✨"
                        })}
                        className="px-2 py-0.5 rounded-full bg-surface-800 text-surface-300 border border-surface-700 text-[10px] tracking-tighter uppercase font-mono hover:bg-surface-700 hover:scale-105 transition-all"
                      >
                        ✨ {selected.resolution.toFixed(2)} Å
                      </button>
                    )}
                  </div>
                );
              })()}
            </div>

            <div className="flex items-center gap-2 rounded-xl border border-surface-700 bg-surface-950/50 px-4 py-2">
              <input
                id="isControl"
                type="checkbox"
                checked={isControl}
                onChange={(e) => setIsControl(e.target.checked)}
                disabled={!!taskId && !isTerminal}
                className="h-4 w-4 rounded border-surface-700 bg-surface-800 text-brand-600 focus:ring-brand-500"
              />
              <label htmlFor="isControl" className="text-xs font-medium text-surface-300">
                Molécula de control / endógena
              </label>
            </div>

            {isSaved && (
              <div className="mt-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-4 text-center">
                <p className="text-sm font-bold text-emerald-400 mb-3">¡Molécula guardada con éxito en tu Moldex!</p>
                <button
                  onClick={() => router.push("/moldex")}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-500 transition-colors"
                >
                  IR A MOLDEX
                </button>
              </div>
            )}

            <div className="space-y-2">
              <button
                onClick={handleValidate}
                disabled={busy || (!!taskId && !isTerminal) || !smiles.trim()}
                className="w-full rounded-xl border border-surface-700 bg-surface-800 px-4 py-2.5 text-sm font-semibold text-surface-300 transition-colors hover:bg-surface-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                1. Validar estructura
              </button>
              
              <div className="space-y-1">
                <button
                  onClick={() => handleSubmit()}
                  disabled={busy || !canEvaluate || (!!taskId && !isTerminal)}
                  className="w-full rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  2. Evaluar molécula
                </button>
              </div>

              {isTerminal && (
                <button
                  onClick={handleReset}
                  className="w-full rounded-xl border border-surface-600 px-4 py-2.5 text-sm font-medium text-surface-300 transition-colors hover:bg-surface-800"
                >
                  Nueva evaluación
                </button>
              )}
            </div>
          </div>
        </div>
      </section>

      {error && (
        <section className="rounded-2xl border border-red-900/50 bg-red-950/30 p-4">
          <h3 className="mb-1 text-sm font-bold text-red-400">Error</h3>
          <pre className="whitespace-pre-wrap text-xs text-red-300">{error}</pre>
        </section>
      )}

      {validation && (
        <section className="space-y-3 rounded-2xl border border-surface-800 bg-surface-900 p-4">
          <h3 className="text-sm font-bold text-white">Validación química</h3>
          <div className="flex flex-wrap gap-3 text-xs">
            <span>
              Estado:{" "}
              <strong className={validation.is_valid ? "text-green-400" : "text-red-400"}>
                {validation.is_valid ? "✓ Válida" : "✗ Inválida"}
              </strong>
            </span>
            {validation.canonical_smiles && (
              <span className="text-surface-400">
                Canónico: <code className="rounded bg-surface-800 px-1.5 py-0.5 font-mono">{validation.canonical_smiles}</code>
              </span>
            )}
            {validation.molecular_formula && (
              <span className="text-surface-400">Fórmula: {validation.molecular_formula}</span>
            )}
            {validation.heavy_atom_count !== null && (
              <span className="text-surface-400">Átomos pesados: {validation.heavy_atom_count}</span>
            )}
          </div>
        </section>
      )}

      {status && !isTerminal && (
        <ProgressBar progress={status.progress} status={status.status} />
      )}

      {status?.result && (
        <div className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-2">
            <ScoreCard
              totalScore={status.result.total_score}
              affinity={status.result.affinity_score}
              affinityKcal={status.result.affinity_kcal}
              adme={status.result.adme_score}
              druglikeness={status.result.druglikeness_score}
              ligandEfficiency={status.result.ligand_efficiency}
              onCertify={user ? () => handleCertify() : undefined}
              onSave={user ? handleSave : undefined}
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
            
            <div className="flex flex-col gap-5">
              <MoleculeViewer3D
                poseData={poseData ?? undefined}
                proteinData={proteinData ?? undefined}
                height={320}
                hotspots={status.result.target_hotspots?.map(h => h.name) || []}
                hotspotsHit={status.result.hotspots_hit || []}
              />
            </div>
          </div>

          <ScientificWarnings warnings={status.result.scientific_warnings} />
          <MolecularInsight result={status.result} />
          <PropertiesPanel result={status.result} />

          {/* (loadingAiReport || aiReport !== null) && (
            <section className="rounded-2xl border border-brand-800/20 bg-surface-900 p-5">
              <h3 className="mb-1 text-sm font-bold text-white">Interpretación Científica AI</h3>
              {loadingAiReport ? (
                <p>Generando interpretación...</p>
              ) : (
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-surface-300">
                  {displayedReport || "Esperando respuesta de IA..."}
                </p>
              )}
            </section>
          ) */}

          <ReproducibilityInfo result={status.result} />
          <MethodDisclaimer />
        </div>
      )}

      {status?.status === "FAILURE" && !status.result && (
        <section className="rounded-2xl border border-red-900/50 bg-red-950/30 p-4">
          <h3 className="mb-1 text-sm font-bold text-red-400">Job fallido</h3>
          <pre className="whitespace-pre-wrap text-xs text-red-300">{status.error ?? "Error desconocido"}</pre>
        </section>
      )}
      </div>
      {/* END CONTENIDO PRINCIPAL */}

      {/* Modal Pipeline Step */}
      {selectedPipelineStep && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in"
          onClick={() => setSelectedPipelineStep(null)}
        >
          <div 
            className="bg-surface-900 border border-indigo-500/50 rounded-2xl p-6 max-w-md w-full shadow-2xl relative animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setSelectedPipelineStep(null)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white transition-colors"
            >
              ✕
            </button>
            <div className="flex items-center gap-4 mb-5">
              <span className="text-4xl">{selectedPipelineStep.icon}</span>
              <div>
                <span className="text-[10px] font-mono font-bold text-indigo-400 uppercase tracking-widest">{selectedPipelineStep.step}</span>
                <h3 className="text-xl font-bold text-white leading-tight">{selectedPipelineStep.title}</h3>
              </div>
            </div>
            <div className="bg-surface-950/80 rounded-xl p-3 mb-4 border border-surface-800">
              <span className="text-xs font-mono text-indigo-300"><strong className="text-white">Motor:</strong> {selectedPipelineStep.tech}</span>
            </div>
            <p className="text-sm text-surface-300 leading-relaxed">
              {selectedPipelineStep.desc}
            </p>
            <div className="mt-6 flex justify-end">
              <button 
                onClick={() => setSelectedPipelineStep(null)}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold rounded-xl transition-colors shadow-lg shadow-indigo-500/20"
              >
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Etiqueta Biológica */}
      {selectedBiologicalLabel && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in"
          onClick={() => setSelectedBiologicalLabel(null)}
        >
          <div 
            className="bg-surface-900 border border-indigo-500/50 rounded-2xl p-6 max-w-md w-full shadow-2xl relative animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setSelectedBiologicalLabel(null)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white transition-colors"
            >
              ✕
            </button>
            <div className="flex items-center gap-4 mb-4">
              {selectedBiologicalLabel.icon && <span className="text-3xl">{selectedBiologicalLabel.icon}</span>}
              <h3 className="text-xl font-bold text-white leading-tight">{selectedBiologicalLabel.title}</h3>
            </div>
            <p className="text-sm text-surface-300 leading-relaxed">
              {selectedBiologicalLabel.desc}
            </p>
            <div className="mt-6 flex justify-end">
              <button 
                onClick={() => setSelectedBiologicalLabel(null)}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold rounded-xl transition-colors shadow-lg shadow-indigo-500/20"
              >
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Tutorial */}
      {selectedTutorialStep && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in"
          onClick={() => setSelectedTutorialStep(null)}
        >
          <div 
            className="bg-surface-900 border border-indigo-500/50 rounded-2xl p-6 max-w-md w-full shadow-2xl relative animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setSelectedTutorialStep(null)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white transition-colors"
            >
              ✕
            </button>
            <div className="flex items-center gap-4 mb-4">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-400 font-bold font-mono text-lg">{selectedTutorialStep.step}</span>
              <h3 className="text-xl font-bold text-white leading-tight">{selectedTutorialStep.title}</h3>
            </div>
            <p className="text-sm text-surface-300 leading-relaxed">
              {selectedTutorialStep.desc}
            </p>
            <div className="mt-6 flex justify-end">
              <button 
                onClick={() => setSelectedTutorialStep(null)}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold rounded-xl transition-colors shadow-lg shadow-indigo-500/20"
              >
                Entendido
              </button>
            </div>
          </div>
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

    </main>
  );
}
