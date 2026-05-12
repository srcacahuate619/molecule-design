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
import { getAiReport, getJobStatus, getPoseFile, getProteinFile, getSuggestions, submitEvaluation, validateSmiles, certifyMolecule, downloadCertificate, saveMolecule } from "../../lib/api";
import type { JobStatus, MolecularSuggestion, ValidationResult } from "../../lib/types";

const POLL_INTERVAL_MS = 2000;

export default function EvaluationPage() {
  // --- Input state ---
  const [smiles, setSmiles] = useState("CC(=O)Oc1ccccc1C(=O)O");
  const [target, setTarget] = useState("7E2Y");

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
  const isTerminal = status?.status === "SUCCESS" || status?.status === "FAILURE";
  const canEvaluate = !!validation?.is_valid;

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

  const handleCertify = useCallback(async () => {
    if (!status?.result?.molecule_id) return;

    let wallet: string | undefined = undefined;
    const hasWallet = window.confirm(
      "¿Deseas registrar este descubrimiento a nombre de tu Wallet de Solana (Phantom/Solflare)?\n\n" +
      "• Aceptar: Ingresar tu propia Wallet.\n" +
      "• Cancelar: Certificar gratis bajo tu correo electrónico."
    );
    
    if (hasWallet) {
      const input = window.prompt("Pega la dirección pública de tu Wallet de Solana:");
      if (input === null) return; // User cancelled the prompt
      if (input.trim().length >= 32) {
        wallet = input.trim();
      } else {
        alert("La dirección ingresada parece inválida. Procediendo con certificación por correo.");
      }
    }

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
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
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
      setError((e as Error).message);
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

  const handleUseSuggestion = (sug: MolecularSuggestion) => {
    setSmiles(sug.smiles);
    handleReset();
  };

  return (
    <main className="space-y-6 pb-12">
      {/* ── Header ── */}
      <section>
        <h1 className="text-2xl font-bold text-white">Evaluación molecular</h1>
        <p className="mt-1 text-sm text-surface-400">
          Pipeline: validación (RDKit) → propiedades → conformer 3D → docking (Vina) → scoring → interpretación IA (en construcción)
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
              <input
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                disabled={!!taskId && !isTerminal}
                className="w-full rounded-xl border border-surface-700 bg-surface-950 px-4 py-3 font-mono text-sm text-gray-200 placeholder-surface-500 transition-colors focus:border-brand-500 focus:outline-none disabled:opacity-50"
                placeholder="Ej: 7E2Y"
              />
              <p className="mt-1 text-xs text-surface-500">
                5-HT1A (7E2Y) · cryo-EM 3.0 Å · Xu et al. 2021
              </p>
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
              <button
                onClick={handleSubmit}
                disabled={busy || !canEvaluate || (!!taskId && !isTerminal)}
                className="w-full rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                2. Evaluar molécula
              </button>
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
              onCertify={handleCertify}
              onSave={handleSave}
              isSaved={isSaved}
              solanaSignature={status.result.blockchain_tx_id}
              onDownloadCertificate={handleDownloadCertificate}
            />
            <MoleculeViewer3D
              poseData={poseData ?? undefined}
              proteinData={proteinData ?? undefined}
              height={320}
            />          </div>

          {/* Scientific warnings */}
          <ScientificWarnings warnings={status.result.scientific_warnings} />

          {/* Properties */}
          <PropertiesPanel result={status.result} />

          {/* AI Report - async, shown when ready */}
          {(loadingAiReport || aiReport) && (
            <section className="rounded-2xl border border-surface-800 bg-surface-900 p-5">
              <h3 className="mb-1 text-sm font-bold text-white">Interpretación IA (Próximamente)</h3>
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
                        <span className="rounded bg-surface-800 px-1.5 py-0.5 text-[10px] font-medium text-surface-400">
                          {sug.confidence}
                        </span>
                      </div>
                      <p className="text-xs leading-relaxed text-surface-400">{sug.description}</p>
                      <code className="block truncate rounded bg-surface-800 px-2 py-1 font-mono text-[10px] text-surface-300">
                        {sug.smiles}
                      </code>
                      {sug.warnings.length > 0 && (
                        <div className="text-[10px] text-yellow-400">
                          {sug.warnings.map((w, wi) => (
                            <div key={wi}>⚠ {w}</div>
                          ))}
                        </div>
                      )}
                      <button
                        onClick={() => handleUseSuggestion(sug)}
                        className="w-full rounded-lg border border-brand-600/30 bg-brand-600/10 py-1.5 text-xs font-medium text-brand-400 transition-colors hover:bg-brand-600/20"
                      >
                        Usar esta molécula
                      </button>
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
