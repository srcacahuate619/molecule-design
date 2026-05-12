"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "../../lib/auth";
import { getEvaluationHistory, getUserStats, downloadCertificate } from "../../lib/api";
import type { EvaluationSummary, HistoryResponse, UserStats } from "../../lib/types";

export default function HistoryPage() {
  const { user, isLoading: authLoading } = useAuth();
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("created_at");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch history
  useEffect(() => {
    if (!user) return;
    setLoading(true);
    setError(null);
    getEvaluationHistory(page, 20, sortBy, "desc")
      .then(setHistory)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [user, page, sortBy]);

  // Fetch stats
  useEffect(() => {
    if (!user) return;
    getUserStats()
      .then(setStats)
      .catch(() => {}); // stats are nice-to-have
  }, [user]);

  if (authLoading) {
    return (
      <main className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </main>
    );
  }

  if (!user) {
    return (
      <main className="flex flex-col items-center justify-center gap-4 py-20 text-center">
        <div className="text-4xl">🔐</div>
        <h1 className="text-xl font-bold text-white">Autenticación requerida</h1>
        <p className="text-sm text-surface-400">
          Inicia sesión para ver tus moléculas guardadas.
        </p>
        <Link
          href="/login"
          className="rounded-xl bg-brand-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700"
        >
          Iniciar sesión
        </Link>
      </main>
    );
  }

  return (
    <main className="space-y-6 pb-12">
      {/* ── Header ── */}
      <section>
        <h1 className="text-2xl font-bold text-white">Moléculas Guardadas</h1>
        <p className="mt-1 text-sm text-surface-400">
          Evaluaciones moleculares que has decidido conservar.
        </p>
      </section>

      {/* ── Stats ── */}
      {stats && (
        <section className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <StatCard label="Total" value={stats.total_evaluations} />
          <StatCard label="Completadas" value={stats.completed_evaluations} color="text-green-400" />
          <StatCard label="Fallidas" value={stats.failed_evaluations} color="text-red-400" />
          <StatCard
            label="Mejor score"
            value={stats.best_score != null ? stats.best_score.toFixed(1) : "—"}
            color="text-brand-400"
          />
          <StatCard
            label="Promedio"
            value={stats.avg_score != null ? stats.avg_score.toFixed(1) : "—"}
          />
          <StatCard label="Targets únicos" value={stats.unique_targets} />
        </section>
      )}

      {/* ── Controls ── */}
      <section className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-surface-400">Ordenar por:</label>
        {[
          { key: "created_at", label: "Fecha" },
          { key: "total_score", label: "Score total" },
          { key: "affinity_kcal", label: "Afinidad" },
        ].map((opt) => (
          <button
            key={opt.key}
            onClick={() => { setSortBy(opt.key); setPage(1); }}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              sortBy === opt.key
                ? "bg-brand-600/20 text-brand-400"
                : "text-surface-400 hover:bg-surface-800"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </section>

      {/* ── Error ── */}
      {error && (
        <section className="rounded-2xl border border-red-900/50 bg-red-950/30 p-4">
          <pre className="text-xs text-red-300">{error}</pre>
        </section>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div className="flex items-center gap-2 py-8 text-sm text-surface-400">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
          Cargando evaluaciones...
        </div>
      )}

      {/* ── Table ── */}
      {history && !loading && (
        <>
          {history.items.length === 0 ? (
            <section className="flex flex-col items-center gap-3 py-20 text-center">
              <div className="text-4xl">🧬</div>
              <p className="text-sm text-surface-400">No hay evaluaciones aún.</p>
              <Link
                href="/evaluation"
                className="rounded-xl bg-brand-600 px-5 py-2 text-sm font-semibold text-white hover:bg-brand-700"
              >
                Evaluar molécula
              </Link>
            </section>
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-surface-800">
              <table className="w-full text-xs">
                <thead className="border-b border-surface-800 bg-surface-900">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-surface-400">SMILES</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Target</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Estado</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Score</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Afinidad</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">MW</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Lipinski</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">QED</th>
                    <th className="px-3 py-3 text-center font-semibold text-surface-400">Certificado</th>
                    <th className="px-3 py-3 text-right font-semibold text-surface-400">Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {history.items.map((item: EvaluationSummary, i: number) => (
                    <tr
                      key={item.molecule_id + i}
                      className="border-b border-surface-800/50 transition-colors hover:bg-surface-900/50"
                    >
                      <td className="max-w-[200px] truncate px-4 py-3 font-mono text-surface-300">
                        {item.smiles}
                      </td>
                      <td className="px-3 py-3 text-center text-surface-400">{item.target_pdb_id}</td>
                      <td className="px-3 py-3 text-center">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-3 py-3 text-center font-semibold text-brand-400">
                        {item.total_score != null ? item.total_score.toFixed(1) : "—"}
                      </td>
                      <td className="px-3 py-3 text-center text-surface-300">
                        {item.affinity_kcal != null ? `${item.affinity_kcal.toFixed(1)} kcal/mol` : "—"}
                      </td>
                      <td className="px-3 py-3 text-center text-surface-400">
                        {item.molecular_weight != null ? item.molecular_weight.toFixed(0) : "—"}
                      </td>
                      <td className="px-3 py-3 text-center">
                        {item.lipinski_pass != null ? (
                          item.lipinski_pass ? (
                            <span className="text-green-400">✓</span>
                          ) : (
                            <span className="text-red-400">✗</span>
                          )
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-3 py-3 text-center text-surface-400">
                        {item.qed != null ? item.qed.toFixed(2) : "—"}
                      </td>
                      <td className="px-3 py-3 text-center">
                        {item.blockchain_tx_id ? (
                          <button
                            onClick={() => downloadCertificate(item.molecule_id)}
                            className="inline-flex items-center gap-1.5 rounded-md bg-brand-500/10 px-2 py-1 text-[10px] font-bold text-brand-400 transition-colors hover:bg-brand-500/20"
                            title="Descargar Certificado PDF"
                          >
                            📥 PDF
                          </button>
                        ) : (
                          <span className="text-[10px] text-surface-600">No cert.</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-right text-surface-500">
                        {item.created_at ? new Date(item.created_at).toLocaleDateString("es-MX", {
                          day: "2-digit",
                          month: "short",
                          year: "numeric",
                        }) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Pagination ── */}
          {history.total > history.page_size && (
            <div className="flex items-center justify-center gap-3">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-lg border border-surface-700 px-3 py-1.5 text-xs text-surface-300 transition-colors hover:bg-surface-800 disabled:opacity-40"
              >
                ← Anterior
              </button>
              <span className="text-xs text-surface-400">
                Página {history.page} de {Math.ceil(history.total / history.page_size)}
              </span>
              <button
                disabled={!history.has_next}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-surface-700 px-3 py-1.5 text-xs text-surface-300 transition-colors hover:bg-surface-800 disabled:opacity-40"
              >
                Siguiente →
              </button>
            </div>
          )}
        </>
      )}

      {/* ── Disclaimer ── */}
      <p className="text-center text-xs text-surface-500">
        Los scores son heurísticas computacionales para priorización, no evidencia clínica.
        Todos los resultados son reproducibles mediante los parámetros registrados.
      </p>
    </main>
  );
}

// ── Sub-components ──

function StatCard({
  label,
  value,
  color = "text-white",
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="rounded-xl border border-surface-800 bg-surface-900 p-3 text-center">
      <div className={`text-lg font-bold ${color}`}>{value}</div>
      <div className="text-xs text-surface-500">{label}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    completed: { bg: "bg-green-900/30", text: "text-green-400", label: "Completada" },
    SUCCESS: { bg: "bg-green-900/30", text: "text-green-400", label: "Completada" },
    failed: { bg: "bg-red-900/30", text: "text-red-400", label: "Fallida" },
    FAILURE: { bg: "bg-red-900/30", text: "text-red-400", label: "Fallida" },
    running: { bg: "bg-blue-900/30", text: "text-blue-400", label: "En curso" },
    PENDING: { bg: "bg-yellow-900/30", text: "text-yellow-400", label: "Pendiente" },
  };
  const c = config[status] ?? { bg: "bg-surface-800", text: "text-surface-400", label: status };
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[10px] font-semibold ${c.bg} ${c.text}`}>
      {c.label}
    </span>
  );
}
