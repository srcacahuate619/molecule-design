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
  const [target, setTarget] = useState("7E2Y");
  const [targets, setTargets] = useState<Target[]>([]);
  const [loadingTargets, setLoadingTargets] = useState(true);

  useEffect(() => {
    getTargets()
      .then((data) => {
        setTargets(data);
        if (data.length > 0) {
          const hasDefault = data.some((t) => t.pdb_id === "7E2Y");
          if (!hasDefault) {
            setTarget(data[0].pdb_id);
          }
        }
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
  const canEvaluate = !!validation?.is_valid;

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

    // Si el input no está visible, lo mostramos y terminamos
    if (!showWalletInput) {
      setShowWalletInput(true);
      return;
    }

    // Si ya está visible, procedemos con el valor de customWallet
    const wallet = customWallet.trim().length >= 32 ? customWallet.trim() : undefined;

    try {
      setBusy(true);
      const res = await certifyMolecule(status.result.molecule_id, wallet);
      // We update the local state to show the badge immediately
      setStatus((prev) => {
        if (!prev || !prev.result) return prev;
        return {
          ...prev,
          result: { ...prev.result, blockchain_tx_id: res.signature },
        };
      });
      // Backend now auto-saves on certify, so we update local UI state
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

  // --- Polling ---
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
          console.log(polled);
          if (polled.status === "SUCCESS" || polled.status === "FAILURE") {
            stopPolling();
          }
        } catch {
          // silently retry on next interval
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling],
  );

  useEffect(() => () => stopPolling(), [stopPolling]);


  // --- Fetch 3D file when we have results ---
  useEffect(() => {
    if (!status?.result?.molecule_id) return;
    const moleculeId = status.result.molecule_id;
    // Fetch protein PDB
    getProteinFile(moleculeId).then((protein) => {
      setProteinData(protein);
    });
    // Fetch ligand pose SDF (with explicit bonds)
    getPoseFile(moleculeId).then((pose) => {
      setPoseData(pose);
    });
  }, [status?.result?.molecule_id]);

  // --- Fetch AI report separately after SUCCESS (decoupled from Celery pipeline) ---
  useEffect(() => {
    const moleculeId = status?.result?.molecule_id;
    if (!moleculeId) return;
    // Reset on new evaluation
    setAiReport(null);
    setLoadingAiReport(true);
    getAiReport(moleculeId)
      .then((report) => setAiReport(report))
      .catch(() => setAiReport(null))
      .finally(() => setLoadingAiReport(false));
  }, [status?.result?.molecule_id]);

  // --- Typewriter effect for AI report ---
  useEffect(() => {
    if (!aiReport) {
      setDisplayedReport("");
      return;
    }
    let i = 0;
    const interval = setInterval(() => {
      setDisplayedReport(aiReport.slice(0, i));
      i += 3; // Escribir de a 3 caracteres para que sea fluido pero rápido
      if (i > aiReport.length) clearInterval(interval);
    }, 20);
    return () => clearInterval(interval);
  }, [aiReport]);

  // --- Fetch suggestions when we have results ---
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.result?.total_score]);

  // --- Handlers ---
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
      // Chequeo preventivo de límites para anónimos
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
        // Extraer mensaje amigable si viene de FastAPI
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
    
    // Disparamos validación automática
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
      {/* ── Header ── */}
      <section>
        <h1 className="text-2xl font-bold text-white">Evaluación molecular</h1>
        <p className="mt-1 text-sm text-surface-400">
          Pipeline: validación (RDKit) → propiedades (SA) → conformer 3D → docking (Vina) → rescoring (ML v4.0) → interpretación IA (sin tokens disponibles:c) → certificación On-Chain (Solana)
        </p>
      </section>

      {/* ── Input section ── */}
      <section className="space-y-4 rounded-2xl border border-surface-800 bg-surface-900 p-5">
        <div className="grid gap-5 md:grid-cols-3">
          {/* SMILES Editor */}
          <div className="md:col-span-2">
            <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-surface-400">
              Molécula (SMILES)
            </label>
            <KetcherEditor
              initialSmiles={smiles}
              onSmilesChange={(s) => setSmiles(s)}
            />
          </div>

          {/* Target + Actions */}
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-surface-400">
                Target PDB
              </label>
              {loadingTargets ? (
                <div className="w-full rounded-xl border border-surface-700 bg-surface-950 px-4 py-3 font-mono text-sm text-surface-500">
                  Cargando targets...
                </div>
              ) : (
                <select
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  disabled={!!taskId && !isTerminal}
                  className="w-full rounded-xl border border-surface-700 bg-surface-950 px-4 py-3 font-mono text-sm text-gray-200 transition-colors focus:border-brand-500 focus:outline-none disabled:opacity-50 appearance-none"
                >
                  {targets.map((t) => (
                    <option key={t.pdb_id} value={t.pdb_id}>
                      {t.pdb_id} - {t.name}
                    </option>
                  ))}
                </select>
              )}
              {(() => {
                const selected = targets.find((t) => t.pdb_id === target);
                if (!selected) return null;
                return (
                  <p className="mt-1 text-xs text-surface-500">
                    {selected.name} · {selected.resolution} Å · {selected.organism}
                  </p>
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
              <div className="group relative">
                <span className="cursor-help text-[10px] text-surface-500 underline decoration-dotted">?</span>
                <div className="absolute bottom-full left-1/2 mb-2 hidden w-48 -translate-x-1/2 rounded-lg bg-surface-800 p-2 text-[10px] leading-tight text-surface-200 shadow-xl group-hover:block">
                  Si se activa, el sistema ignorará las penalizaciones de fármacos orales (ADME) para no penalizar ligandos naturales.
                </div>
              </div>
            </div>

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
                {!user && (
                   <p className="text-center text-[10px] text-surface-500">
                     Límite para anónimos: 10 evaluaciones (propietario) / 2 (público)
                   </p>
                )}
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

      {/* ── Error ── */}
      {error && (
        <section className="rounded-2xl border border-red-900/50 bg-red-950/30 p-4">
          <h3 className="mb-1 text-sm font-bold text-red-400">Error</h3>
          <pre className="whitespace-pre-wrap text-xs text-red-300">{error}</pre>
        </section>
      )}

      {/* ── Validation result ── */}
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
          {validation.warnings.length > 0 && (
            <div className="space-y-0.5 text-xs text-yellow-400">
              {validation.warnings.map((w, i) => (
                <div key={i}>⚠ {w}</div>
              ))}
            </div>
          )}
          {validation.errors.length > 0 && (
            <div className="space-y-0.5 text-xs text-red-400">
              {validation.errors.map((e, i) => (
                <div key={i}>✗ {e}</div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* ── Progress ── */}
      {status && !isTerminal && (
        <ProgressBar progress={status.progress} status={status.status} />
      )}

      {/* ── Results ── */}
      {status?.result && (
        <div className="space-y-5">
          {/* Score + 3D View side by side on large screens */}
          <div className="grid gap-5 lg:grid-cols-2">
            <ScoreCard
              totalScore={status.result.total_score}
              affinity={status.result.affinity_score}
              affinityKcal={status.result.affinity_kcal}
              adme={status.result.adme_score}
              druglikeness={status.result.druglikeness_score}
              ligandEfficiency={status.result.ligand_efficiency}
              onCertify={() => handleCertify()}
              onSave={handleSave}
              isSaved={isSaved}
              solanaSignature={status.result.blockchain_tx_id}
              onDownloadCertificate={handleDownloadCertificate}
              isControl={status.result.is_control}
              saScore={status.result.sa_score}
              saReasons={status.result.sa_reasons}
              rawVinaKcal={(status.result.docking_poses?.[0] as any)?.affinity ?? status.result.docking_poses?.[0]?.affinity_kcal ?? null}
              rawXgboostKcal={
                ((status.result.docking_poses?.[0] as any)?.affinity ?? status.result.docking_poses?.[0]?.affinity_kcal) !== status.result.affinity_kcal
                  ? status.result.affinity_kcal
                  : null
              }
            />
            
            <div className="flex flex-col gap-5">
              {showWalletInput && !status.result.blockchain_tx_id && (
                <div className="animate-in fade-in slide-in-from-top-2 rounded-2xl border border-brand-500/30 bg-brand-500/5 p-4 shadow-lg backdrop-blur-sm">
                  <h4 className="mb-2 text-sm font-bold text-brand-400">Certificación en Solana</h4>
                  <p className="mb-3 text-[11px] text-surface-400">
                    Ingresa tu Wallet (Phantom/Solflare) para registrar la autoría. 
                    Si lo dejas vacío, se certificará bajo tu correo.
                  </p>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Dirección de tu Wallet Solana..."
                      value={customWallet}
                      onChange={(e) => setCustomWallet(e.target.value)}
                      className="flex-1 rounded-lg border border-surface-700 bg-surface-950 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none"
                    />
                    <button
                      onClick={() => handleCertify()}
                      disabled={busy}
                      className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
                    >
                      {busy ? "Procesando..." : "Confirmar"}
                    </button>
                    <button
                      onClick={() => setShowWalletInput(false)}
                      className="rounded-lg border border-surface-700 px-3 py-2 text-sm text-surface-400 hover:bg-surface-800"
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              )}
              
              <MoleculeViewer3D
                poseData={poseData ?? undefined}
                proteinData={proteinData ?? undefined}
                height={320}
              />
            </div>
          </div>

          {/* Scientific warnings */}
          <ScientificWarnings warnings={status.result.scientific_warnings} />

          {/* New Dynamic Molecular Insight */}
          <MolecularInsight result={status.result} />

          {/* Properties */}
          <PropertiesPanel result={status.result} />

          {/* AI Report - async, shown when ready */}
          {(loadingAiReport || aiReport) && (
            <section className="rounded-2xl border border-brand-800/20 bg-surface-900 p-5">
              <h3 className="mb-1 text-sm font-bold text-white">Interpretación Científica AI</h3>
              <p className="mb-3 text-xs text-surface-500">
                Generada por Claude (Anthropic). No sustituye criterio científico experto.
              </p>
              {loadingAiReport ? (
                <div className="flex items-center gap-2 py-2 text-sm text-surface-400">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
                  Generando interpretación...
                </div>
              ) : (
                <p className="text-sm leading-relaxed text-surface-300">
                  {displayedReport}
                  {displayedReport.length < (aiReport?.length || 0) && (
                    <span className="ml-1 inline-block h-4 w-1 animate-pulse bg-brand-500" />
                  )}
                </p>
              )}
            </section>
          )}

          {/* Molecular suggestions */}
          {(suggestions.length > 0 || loadingSuggestions) && (
            <section className="space-y-3 rounded-2xl border border-surface-800 bg-surface-900 p-5">
              <h3 className="text-sm font-bold text-white">Sugerencias de optimización</h3>
              <p className="text-xs text-surface-500">
                Hipótesis computacionales basadas en reglas de química medicinal. No constituyen predicciones experimentales.
              </p>
              {loadingSuggestions ? (
                <div className="flex items-center gap-2 py-4 text-sm text-surface-400">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
                  Generando sugerencias...
                </div>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {suggestions.map((sug, i) => (
                    <div
                      key={i}
                      className="space-y-2 rounded-xl border border-surface-700 bg-surface-950 p-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs font-semibold text-brand-400">{sug.name}</span>
                        <div className="flex flex-col items-end gap-1">
                          <span className="rounded bg-surface-800 px-1.5 py-0.5 text-[10px] font-medium text-surface-400">
                            {sug.confidence}
                          </span>
                          {sug.ml_score !== undefined && sug.ml_score !== null && (
                            <div className="flex items-center gap-1.5 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-bold text-emerald-400 border border-emerald-500/20">
                                <span className="relative flex h-1 w-1">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-1 w-1 bg-emerald-500"></span>
                                </span>
                                PROMETEDOR: {sug.ml_score.toFixed(2)}
                            </div>
                          )}
                        </div>
                      </div>
                      <p className="text-xs leading-relaxed text-surface-400">{sug.description}</p>
                      {sug.smiles && (
                        <code className="block truncate rounded bg-surface-800 px-2 py-1 font-mono text-[10px] text-surface-300">
                          {sug.smiles}
                        </code>
                      )}
                      {sug.warnings.length > 0 && (
                        <div className="text-[10px] text-yellow-400">
                          {sug.warnings.map((w, wi) => (
                            <div key={wi}>⚠ {w}</div>
                          ))}
                        </div>
                      )}
                      {sug.smiles && (
                        <button
                          onClick={() => handleUseSuggestion(sug)}
                          className="w-full rounded-lg border border-brand-600/30 bg-brand-600/10 py-1.5 text-xs font-medium text-brand-400 transition-colors hover:bg-brand-600/20"
                        >
                          Usar esta molécula
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Error from evaluation */}
          {status.result.error_message && (
            <section className="rounded-2xl border border-red-900/50 bg-red-950/30 p-4">
              <h3 className="mb-1 text-sm font-bold text-red-400">Error en evaluación</h3>
              <pre className="whitespace-pre-wrap text-xs text-red-300">
                {status.result.error_message}
              </pre>
            </section>
          )}

          {/* Reproducibility */}
          <ReproducibilityInfo result={status.result} />

          {/* Method disclaimer */}
          <MethodDisclaimer />
        </div>
      )}

      {/* ── Job FAILURE without result ── */}
      {status?.status === "FAILURE" && !status.result && (
        <section className="rounded-2xl border border-red-900/50 bg-red-950/30 p-4">
          <h3 className="mb-1 text-sm font-bold text-red-400">Job fallido</h3>
          <pre className="whitespace-pre-wrap text-xs text-red-300">
            {status.error ?? "Error desconocido"}
          </pre>
        </section>
      )}
    </main>
  );
}
