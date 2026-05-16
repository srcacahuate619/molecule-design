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

const POLL_INTERVAL_MS = 2000;

export default function EvaluationPage() {
  // --- Input state ---
  const [smiles, setSmiles] = useState("CC(=O)Oc1ccccc1C(=O)O");
  const [target, setTarget] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<"HUMANOS" | "PATOGENOS" | "">("");
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

  const handleSave = useCallback(async () => {
    if (!status?.result?.molecule_id) return;
    try {
      setBusy(true);
      await saveMolecule(status.result.molecule_id);
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
    const moleculeId = status?.result?.molecule_id;
    if (!moleculeId) return;
    setAiReport(null);
    setLoadingAiReport(true);
    getAiReport(moleculeId)
      .then((report) => setAiReport(report))
      .catch(() => setAiReport(null))
      .finally(() => setLoadingAiReport(false));
  }, [status?.result?.molecule_id]);

  useEffect(() => {
    if (!aiReport) {
      setDisplayedReport("");
      return;
    }
    let i = 0;
    const interval = setInterval(() => {
      setDisplayedReport(aiReport.slice(0, i));
      i += 3;
      if (i > aiReport.length) clearInterval(interval);
    }, 20);
    return () => clearInterval(interval);
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

  const handleSubmit = async () => {
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

      const result = await submitEvaluation(smiles, target, isControl);
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

  return (
    <main className="space-y-6 pb-12">
      <section>
        <h1 className="text-2xl font-bold text-white">Evaluación molecular</h1>
        <p className="mt-1 text-sm text-surface-400">
          Pipeline: validación (RDKit) → propiedades (SA) → conformer 3D → docking (Vina) → rescoring (ML v4.0) → interpretación IA → certificación On-Chain (Solana) | Correlación ρ=0.512
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
                  <select
                    value={selectedCategory}
                    onChange={(e) => {
                      setSelectedCategory(e.target.value as any);
                      setTarget("");
                    }}
                    disabled={!!taskId && !isTerminal}
                    className="w-full rounded-xl border border-surface-700 bg-surface-950 px-4 py-3 font-mono text-sm text-gray-200 transition-colors focus:border-brand-500 focus:outline-none disabled:opacity-50 appearance-none"
                  >
                    <option value="">Seleccionar Origen del Target...</option>
                    <option value="HUMANOS">🧬 Organismo: Humano (H. sapiens)</option>
                    <option value="PATOGENOS">🦠 Organismo: Patógenos / Microorganismos</option>
                  </select>

                  {selectedCategory && (
                    <select
                      value={target}
                      onChange={(e) => setTarget(e.target.value)}
                      disabled={!!taskId && !isTerminal}
                      className="w-full animate-in fade-in slide-in-from-top-2 rounded-xl border border-brand-500/30 bg-surface-950 px-4 py-3 font-mono text-sm text-brand-300 transition-colors focus:border-brand-500 focus:outline-none disabled:opacity-50 appearance-none shadow-[0_0_15px_rgba(20,241,149,0.1)]"
                    >
                      <option value="">Seleccionar Receptor Específico...</option>
                      {selectedCategory === "HUMANOS" ? (
                        <>
                          <optgroup label="🧠 Neurología / Psiquiatría">
                            {targets.filter(t => t.pdb_id === '7E2Y').map(t => (
                              <option key={t.pdb_id} value={t.pdb_id}>
                                {t.pdb_id} - {t.name}
                              </option>
                            ))}
                          </optgroup>
                          <optgroup label="🧬 Oncología / Inmunoterapia">
                            {targets.filter(t => t.pdb_id === '3OSK' || t.pdb_id === 'EGFR' || t.pdb_id === 'MET').map(t => (
                              <option key={t.pdb_id} value={t.pdb_id}>
                                {t.pdb_id} - {t.name}
                              </option>
                            ))}
                          </optgroup>
                          <optgroup label="❤️ Cardiología">
                            {targets.filter(t => t.pdb_id === '2P4E' || t.pdb_id === '6U26').map(t => (
                              <option key={t.pdb_id} value={t.pdb_id}>
                                {t.pdb_id} - {t.name} {t.is_hot ? "🔥" : ""}
                              </option>
                            ))}
                            {targets.filter(t => t.pdb_id === '2P4E' || t.pdb_id === '6U26').length === 0 && (
                              <option disabled>Próximamente: Receptores Hipertensión</option>
                            )}
                          </optgroup>
                          <optgroup label="🩸 Endocrinología">
                            {targets.filter(t => t.name.toUpperCase().includes('GLP')).map(t => (
                              <option key={t.pdb_id} value={t.pdb_id}>
                                {t.pdb_id} - {t.name} {t.is_hot ? "🔥" : ""}
                              </option>
                            ))}
                            {targets.filter(t => t.name.toUpperCase().includes('GLP')).length === 0 && (
                              <option disabled>Próximamente: Insulina / Diabetes</option>
                            )}
                          </optgroup>
                        </>
                      ) : (
                        <>
                          <optgroup label="🦠 Bacterias - Pared Celular">
                            {targets.filter(t => t.pdb_id.includes('PBP')).map(t => (
                              <option key={t.pdb_id} value={t.pdb_id}>
                                {t.pdb_id} - {t.name}
                              </option>
                            ))}
                          </optgroup>
                          <optgroup label="🧬 Bacterias - Replicación ADN">
                            {targets.filter(t => t.name.toLowerCase().includes('girasa')).map(t => (
                              <option key={t.pdb_id} value={t.pdb_id}>
                                {t.pdb_id} - {t.name}
                              </option>
                            ))}
                          </optgroup>
                          <optgroup label="🛡️ Bacterias - Resistencia">
                            {targets.filter(t => t.name.toLowerCase().includes('lactamasa')).map(t => (
                              <option key={t.pdb_id} value={t.pdb_id}>
                                {t.pdb_id} - {t.name}
                              </option>
                            ))}
                          </optgroup>
                          <optgroup label="🧫 Virus">
                            <option disabled>Próximamente: Proteasas Virales</option>
                          </optgroup>
                        </>
                      )}
                    </select>
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
                  onClick={handleSubmit}
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
              onCertify={() => handleCertify()}
              onSave={user ? handleSave : undefined}
              isSaved={isSaved}
              solanaSignature={status.result.blockchain_tx_id}
              onDownloadCertificate={handleDownloadCertificate}
              isControl={status.result.is_control}
              saScore={status.result.sa_score}
              saReasons={status.result.sa_reasons}
              rawVinaKcal={(status.result.docking_poses?.[0] as any)?.affinity ?? null}
              rawXgboostKcal={status.result.affinity_kcal}
              lipophilicEfficiency={status.result.ligand_lipophilicity_efficiency}
              specificity={status.result.specificity_score}
              affinityMultiplier={status.result.affinity_multiplier}
              specificityMultiplier={status.result.specificity_multiplier}
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

          {(loadingAiReport || aiReport) && (
            <section className="rounded-2xl border border-brand-800/20 bg-surface-900 p-5">
              <h3 className="mb-1 text-sm font-bold text-white">Interpretación Científica AI</h3>
              {loadingAiReport ? (
                <p>Generando interpretación...</p>
              ) : (
                <p className="text-sm leading-relaxed text-surface-300">{displayedReport}</p>
              )}
            </section>
          )}

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
