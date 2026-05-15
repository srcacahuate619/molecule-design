import type { EvaluationResult } from "../lib/types";

type Props = {
  result: EvaluationResult;
};

export function ReproducibilityInfo({ result }: Props) {
  const hasInfo = result.vina_version || result.vina_random_seed !== null || result.parsing_source;

  if (!hasInfo) return null;

  return (
    <section className="space-y-2 rounded-xl border border-surface-800 bg-surface-900 p-5">
      <h3 className="font-bold text-white">Reproducibilidad</h3>
      <p className="text-xs text-surface-400">
        Parámetros clave para reproducir este resultado.
      </p>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
        <span className="text-surface-400">ML Rescore</span>
        <span className="text-brand-400 font-semibold">v4.0 (Spearman 0.512)</span>
        
        {result.vina_version && (
          <>
            <span className="text-surface-400">AutoDock Vina</span>
            <span className="text-gray-300">{result.vina_version}</span>
          </>
        )}
        {result.vina_random_seed !== null && result.vina_random_seed !== undefined && (
          <>
            <span className="text-surface-400">Random seed</span>
            <span className="text-gray-300">{result.vina_random_seed}</span>
          </>
        )}
        {result.evaluated_at && (
          <>
            <span className="text-surface-400">Evaluado</span>
            <span className="text-gray-300">{new Date(result.evaluated_at).toLocaleString()}</span>
          </>
        )}
      </div>
    </section>
  );
}
