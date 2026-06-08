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

export default function EvaluationPage() {
  const { interfaceMode } = useInterface();

  // --- Input state ---
  const [smiles, setSmiles] = useState("CC(=O)Oc1ccccc1C(=O)O");
  const [target, setTarget] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<"HUMANOS" | "PATOGENOS" | "">("");
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [activeSubcategory, setActiveSubcategory] = useState<string>("");
  const [targets, setTargets] = useState<Target[]>([]);
  const [loadingTargets, setLoadingTargets] = useState(true);

  useEffect(() => {
    getTargets()
      .then((data) => {
        setTargets(data);
      })
      .catch((err) => console.error("Error loading targets:", err))
      .finally(() => setLoadingTargets(false));
  }, []);

  // --- Pipeline state ---
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isControl, setIsControl] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [showWalletInput, setShowWalletInput] = useState(false);
  const [customWallet, setCustomWallet] = useState("");
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
  const isTerminal = status?.status === "SUCCESS" || status?.status === "FAILURE";
  const canEvaluate = !!validation?.is_valid && target.length >= 4;

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

  const handleCertify = useCallback(async (walletOverride?: string) => {
    if (!status?.result?.molecule_id) return;

    if (!showWalletInput) {
      setShowWalletInput(true);
      return;
    }

    const wallet = customWallet.trim().length >= 32 ? customWallet.trim() : undefined;

    try {
      setBusy(true);
      const res = await certifyMolecule(status.result.molecule_id, wallet);
      setStatus((prev) => {
        if (!prev || !prev.result) return prev;
        return {
          ...prev,
          result: { ...prev.result, blockchain_tx_id: res.signature },
        };
      });
      setIsSaved(true);
      setShowWalletInput(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }, [status, showWalletInput, customWallet]);

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
        showWalletInput={showWalletInput}
        setShowWalletInput={setShowWalletInput}
        customWallet={customWallet}
        setCustomWallet={setCustomWallet}
      />
    );
  }

  return (
    <main className="space-y-6 pb-12">
      <section>
        <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
          🕹️ Laboratorio Virtual MolDesign AI
        </h1>
        <p className="mt-1 text-sm text-surface-400">
          Pipeline Científico de 3 Niveles: Validación (RDKit) → Screening (Vina+XGBoost Nivel 1) → Análisis Topológico (GNN Nivel 2) → Refinamiento Físico (OpenMM Nivel 3) → Blockchain (Solana).
        </p>
      </section>

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
                          { id: "endocrinologia", name: "Endocrinología", icon: "🩸" }
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
                                  // Los 8 targets de cáncer de mama
                                  const breastCancerPdbIds = ["3ERT", "5L2I", "2W96", "4JPS", "3O96", "3PP0", "4ZZZ", "1HVY"];
                                  filteredTargets = targets.filter(t => breastCancerPdbIds.includes(t.pdb_id));
                                } else if (activeSubcategory === "inmunoterapia") {
                                  filteredTargets = targets.filter(t => t.pdb_id === "3OSK");
                                }
                              } else if (activeCategory === "cardiologia") {
                                filteredTargets = targets.filter(t => t.pdb_id === "2P4E" || t.pdb_id === "6U26");
                              } else if (activeCategory === "endocrinologia") {
                                filteredTargets = targets.filter(t => t.name.toUpperCase().includes("GLP"));
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
                              
                              // Subtítulo clínico en el botón para guiar al usuario
                              let breastSubtype = "";
                              if (t.pdb_id === "3ERT") breastSubtype = "Receptor Hormonal (ER-α)";
                              else if (t.pdb_id === "5L2I") breastSubtype = "Ciclo Celular (CDK6)";
                              else if (t.pdb_id === "2W96") breastSubtype = "Ciclo Celular (CDK4)";
                              else if (t.pdb_id === "4JPS") breastSubtype = "Vía PI3K (PIK3CA WT)";
                              else if (t.pdb_id === "3O96") breastSubtype = "Vía AKT (AKT1)";
                              else if (t.pdb_id === "3PP0") breastSubtype = "Receptor RTK (HER2)";
                              else if (t.pdb_id === "4ZZZ") breastSubtype = "Reparación ADN (PARP1)";
                              else if (t.pdb_id === "1HVY") breastSubtype = "Quimioterapia (TS)";

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
                                    {breastSubtype && (
                                      <span className="text-[10px] text-surface-400 font-medium mt-0.5">{breastSubtype}</span>
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
                    <div className="group relative">
                      <span className="px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/20 text-[10px] uppercase tracking-tighter font-semibold cursor-help">
                        {selected.structural_family || "Other"}
                      </span>
                      <div className="absolute bottom-full left-0 mb-2 hidden w-48 rounded-lg bg-surface-800/95 backdrop-blur-md border border-surface-700 p-2 text-[10px] leading-tight text-surface-200 shadow-xl group-hover:block z-50">
                        <p className="font-bold text-brand-400 mb-1">Familia Estructural</p>
                        Clasificación biológica de la proteína. Determina los parámetros del modelo de scoring ML v4.0.
                      </div>
                    </div>
                    <div className="group relative">
                      <span className={`px-2 py-0.5 rounded-full border text-[10px] tracking-tighter uppercase font-semibold cursor-help ${
                        selected.requires_cns ? "bg-purple-500/10 text-purple-400 border-purple-500/20" : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                      }`}>
                        {selected.requires_cns ? "🧠 CNS Active" : "🛡️ Peripheral"}
                      </span>
                      <div className="absolute bottom-full left-0 mb-2 hidden w-48 rounded-lg bg-surface-800/95 backdrop-blur-md border border-surface-700 p-2 text-[10px] leading-tight text-surface-200 shadow-xl group-hover:block z-50">
                        <p className="font-bold text-purple-400 mb-1">Requerimiento CNS</p>
                        {selected.requires_cns 
                          ? "Este target reside en el cerebro. El sistema aplicará penalizaciones si la molécula no cruza la barrera hematoencefálica (BBB)."
                          : "Target periférico. No requiere cruzar la barrera hematoencefálica para su efectividad."}
                      </div>
                    </div>
                    {selected.is_hot && (
                      <div className="group relative">
                        <span className="px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400 border border-orange-500/40 text-[10px] uppercase tracking-wider font-black animate-pulse shadow-[0_0_10px_rgba(249,115,22,0.3)]">
                          🔥 Hot Target
                        </span>
                        <div className="absolute bottom-full left-0 mb-2 hidden w-40 rounded-lg bg-surface-800/95 backdrop-blur-md border border-surface-700 p-2 text-[10px] leading-tight text-surface-200 shadow-xl group-hover:block z-50">
                          Proteína de alta relevancia farmacéutica actual (Trending).
                        </div>
                      </div>
                    )}
                    {selected.organism && (
                      <div className="group relative">
                        <span className="px-2 py-0.5 rounded-full bg-surface-800 text-surface-400 border border-surface-700 text-[10px] tracking-tighter uppercase cursor-help">
                          🧬 {selected.organism}
                        </span>
                        <div className="absolute bottom-full left-0 mb-2 hidden w-40 rounded-lg bg-surface-800/95 backdrop-blur-md border border-surface-700 p-2 text-[10px] leading-tight text-surface-200 shadow-xl group-hover:block z-50">
                          <p className="font-bold text-surface-100 mb-1">Organismo</p>
                          Fuente biológica de la estructura proteica utilizada para el docking.
                        </div>
                      </div>
                    )}
                    {selected.resolution && (
                      <div className="group relative">
                        <span className="px-2 py-0.5 rounded-full bg-surface-800 text-surface-300 border border-surface-700 text-[10px] tracking-tighter uppercase font-mono cursor-help">
                          ✨ {selected.resolution.toFixed(2)} Å
                        </span>
                        <div className="absolute bottom-full left-0 mb-2 hidden w-44 rounded-lg bg-surface-800/95 backdrop-blur-md border border-surface-700 p-2 text-[10px] leading-tight text-surface-200 shadow-xl group-hover:block z-50">
                          <p className="font-bold text-yellow-500 mb-1">Resolución Cristalográfica</p>
                          Calidad de la estructura. Valores menores a 2.5 Å indican alta fiabilidad para docking preciso.
                        </div>
                      </div>
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
    </main>
  );
}
