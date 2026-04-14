type ScoreBarProps = {
  label: string;
  value: number | null;
  weight?: string;
  color: string;
};

function ScoreBar({ label, value, weight, color }: ScoreBarProps) {
  const display = value !== null && value !== undefined ? value.toFixed(1) : "—";
  const pct = value !== null && value !== undefined ? Math.max(0, Math.min(100, value)) : 0;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span>
          <span className="font-semibold text-gray-200">{label}</span>
          {weight && <span className="ml-1 text-surface-400">({weight})</span>}
        </span>
        <span className="tabular-nums text-gray-300">{display}/100</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-800">
        <div
          className="score-bar-fill h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}

type ScoreCardProps = {
  totalScore: number | null;
  affinity: number | null;
  affinityKcal: number | null;
  adme: number | null;
  druglikeness: number | null;
};

export function ScoreCard({
  totalScore,
  affinity,
  affinityKcal,
  adme,
  druglikeness,
}: ScoreCardProps) {
  const totalDisplay =
    totalScore !== null && totalScore !== undefined
      ? totalScore.toFixed(1)
      : "—";

  const scoreColor =
    totalScore !== null && totalScore >= 70
      ? "text-emerald-400"
      : totalScore !== null && totalScore >= 40
        ? "text-yellow-400"
        : "text-red-400";

  return (
    <section className="space-y-4 rounded-xl border border-surface-800 bg-surface-900 p-5">
      <div className="flex items-baseline justify-between">
        <h3 className="text-base font-bold text-white">Score compuesto</h3>
        <span className={`text-3xl font-bold tabular-nums ${scoreColor}`}>
          {totalDisplay}
        </span>
      </div>

      <p className="text-xs text-surface-400">
        Heurística compuesta para priorización (0–100). No equivale a validación experimental.
      </p>

      <ScoreBar label="Afinidad" value={affinity} weight="45%" color="#3b82f6" />
      <ScoreBar label="ADME" value={adme} weight="30%" color="#8b5cf6" />
      <ScoreBar label="Drug-likeness" value={druglikeness} weight="25%" color="#06b6d4" />

      {affinityKcal !== null && affinityKcal !== undefined && (
        <div className="text-xs text-surface-400">
          Afinidad Vina: <strong className="text-gray-300">{affinityKcal.toFixed(3)} kcal/mol</strong>{" "}
          (normalizado a score en rango [-10, -4])
        </div>
      )}
    </section>
  );
}
