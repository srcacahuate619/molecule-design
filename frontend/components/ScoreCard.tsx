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
  ligandEfficiency?: number | null;
  onCertify?: () => void;
  onSave?: () => void;
  isSaved?: boolean;
  solanaSignature?: string | null;
  onDownloadCertificate?: () => void;
  isControl?: boolean;
  saScore?: number | null;
  saReasons?: string[] | null;
};

export function ScoreCard({
  totalScore,
  affinity,
  affinityKcal,
  adme,
  druglikeness,
  ligandEfficiency,
  onCertify,
  onSave,
  isSaved = false,
  solanaSignature,
  onDownloadCertificate,
  isControl = false,
  saScore,
  saReasons,
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

      <div className="flex gap-3 pt-2">
        {onSave && (
          <button
            onClick={onSave}
            disabled={isSaved}
            className={`flex-1 rounded-lg py-3 font-semibold transition-all ${
              isSaved
                ? "cursor-not-allowed bg-surface-800 text-surface-500"
                : "bg-surface-800 text-surface-300 hover:bg-surface-700 hover:text-white"
            }`}
          >
            {isSaved ? "✓ Guardada en tu cuenta" : "💾 Guardar molécula"}
          </button>
        )}
        
        {solanaSignature ? (
          <div className="flex-1 flex gap-2">
            <a
              href={`https://explorer.solana.com/tx/${solanaSignature}?cluster=devnet`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-[#14F195]/10 text-[#14F195] py-3 font-semibold text-center transition-all hover:bg-[#14F195]/20"
              title="Ver en Solana Explorer"
            >
              ✓ Certificada en Solana
            </a>
            {onDownloadCertificate && (
              <button
                onClick={onDownloadCertificate}
                className="flex-[0.5] rounded-lg bg-surface-800 text-surface-300 py-3 font-semibold transition-all hover:bg-surface-700 hover:text-white"
                title="Descargar Certificado PDF"
              >
                📥 PDF
              </button>
            )}
          </div>
        ) : onCertify ? (
          <button
            onClick={onCertify}
            className="flex-1 text-center rounded-lg bg-gradient-to-r from-[#9945FF] to-[#14F195] py-3 font-bold text-white shadow-lg transition-all hover:opacity-90 active:scale-95"
          >
            Certificar en Solana
          </button>
        ) : null}
      </div>

      <ScoreBar label="Afinidad" value={affinity} weight="45%" color="#3b82f6" />
      
      {!isControl ? (
        <>
          <ScoreBar label="ADME" value={adme} weight="30%" color="#8b5cf6" />
          <ScoreBar label="Drug-likeness" value={druglikeness} weight="25%" color="#06b6d4" />
        </>
      ) : (
        <div className="rounded-lg border border-brand-500/30 bg-brand-500/10 p-3 text-center">
          <div className="text-xs font-bold text-brand-400 uppercase tracking-wider mb-1">Modo Molécula de Control</div>
          <p className="text-[10px] text-brand-300 leading-tight">
            Penalizaciones ADME/Drug-likeness desactivadas. Puntaje basado 100% en afinidad molecular.
          </p>
        </div>
      )}

      {affinityKcal !== null && affinityKcal !== undefined && (
        <div className="text-xs text-surface-400">
          Afinidad (Vina + XGBoost): <strong className="text-gray-300">{affinityKcal.toFixed(3)} kcal/mol</strong>
        </div>
      )}

      {ligandEfficiency !== null && ligandEfficiency !== undefined && (
        <div className="text-xs text-surface-400">
          Ligand Efficiency (LE):{" "}
          <strong className="text-brand-400">
            {ligandEfficiency.toFixed(3)} kcal/mol/atom
          </strong>
        </div>
      )}
      {saScore !== null && saScore !== undefined && (
        <div className="space-y-2">
          <div className="text-xs text-surface-400">
            Accesibilidad Sintética (SA):{" "}
            <strong className={saScore > 6.0 ? "text-red-400" : saScore > 4.5 ? "text-yellow-400" : "text-emerald-400"}>
              {saScore.toFixed(2)} {saScore > 6.0 ? "(Inviable)" : saScore > 4.5 ? "(Difícil)" : "(Fácil)"}
            </strong>
          </div>
          
          {saScore > 6.0 && saReasons && saReasons.length > 0 && (
            <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-2.5">
              <div className="flex items-center gap-1.5 mb-1 text-[10px] font-bold text-red-400 uppercase tracking-wider">
                <span className="text-sm">🧪</span> Motivos de Inviabilidad
              </div>
              <ul className="space-y-1">
                {saReasons.map((reason, idx) => (
                  <li key={idx} className="text-[11px] text-red-300/80 leading-tight">• {reason}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
