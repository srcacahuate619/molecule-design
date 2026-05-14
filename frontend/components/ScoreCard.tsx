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
  rawVinaKcal?: number | null;
  rawXgboostKcal?: number | null;
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
  rawVinaKcal,
  rawXgboostKcal,
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
        <div className="group relative text-xs text-surface-400">
          <div className="flex cursor-help items-center gap-1 w-max">
            <span>Afinidad (Vina + XGBoost):</span>
            <strong className="text-gray-300 border-b border-dashed border-gray-500 pb-0.5">
              {affinityKcal.toFixed(3)} kcal/mol
            </strong>
          </div>
          
          {/* Tooltip Hover */}
          <div className="pointer-events-none absolute bottom-full left-0 z-10 mb-2 w-max max-w-xs scale-95 opacity-0 transition-all group-hover:scale-100 group-hover:opacity-100">
            <div className="rounded-lg border border-brand-500/30 bg-surface-950 p-3 shadow-xl">
              <h4 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-brand-400">Desglose del Motor Físico y de IA</h4>
              <div className="space-y-1.5 text-[11px]">
                <div className="flex justify-between gap-4">
                  <span className="text-surface-400">1. Motor Físico (AutoDock Vina):</span>
                  <strong className="text-white">{rawVinaKcal !== null && rawVinaKcal !== undefined ? `${rawVinaKcal.toFixed(3)} kcal/mol` : "N/A"}</strong>
                </div>
                <div className="flex justify-between gap-4">
                  <span className="text-surface-400">2. Cerebro Espacial (XGBoost):</span>
                  <strong className="text-brand-300">{rawXgboostKcal !== null && rawXgboostKcal !== undefined ? `${rawXgboostKcal.toFixed(3)} kcal/mol` : "N/A (Fallback)"}</strong>
                </div>
              </div>
              <div className="mt-2 border-t border-surface-800 pt-2 text-[9px] leading-tight text-surface-500">
                XGBoost ajusta el puntaje de Vina utilizando patrones de interacción 3D aprendidos de PDBbind (5,000 complejos experimentales).
              </div>
            </div>
            {/* Tooltip Arrow */}
            <div className="absolute left-8 top-full h-2 w-2 -translate-y-1/2 rotate-45 border-b border-r border-brand-500/30 bg-surface-950"></div>
          </div>
        </div>
      )}

      {ligandEfficiency !== null && ligandEfficiency !== undefined && (
        <div className="group relative text-xs text-surface-400">
          <div className="flex cursor-help items-center gap-1 w-max">
            <span>Ligand Efficiency (LE):</span>
            <strong className="text-brand-400 border-b border-dashed border-brand-500/50 pb-0.5">
              {ligandEfficiency.toFixed(3)} kcal/mol/atom
            </strong>
          </div>
          
          {/* Tooltip Hover */}
          <div className="pointer-events-none absolute bottom-full left-0 z-10 mb-2 w-max max-w-xs scale-95 opacity-0 transition-all group-hover:scale-100 group-hover:opacity-100">
            <div className="rounded-lg border border-brand-500/30 bg-surface-950 p-3 shadow-xl">
              <h4 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-brand-400">Ligand Efficiency (Eficiencia del Ligando)</h4>
              <div className="mt-1 space-y-1.5 text-[11px] text-surface-300">
                <p>
                  Mide qué tan eficiente es cada átomo de la molécula para generar afinidad por la proteína.
                </p>
                <div className="mt-2 rounded bg-surface-900 p-2 text-center font-mono text-[10px] text-brand-300 border border-surface-800">
                  LE = Afinidad / Número de Átomos Pesados
                </div>
                <p className="mt-2 text-[9px] text-surface-500">
                  Un valor más negativo es mejor. Valores típicos para fármacos orales rondan los -0.3 kcal/mol/átomo.
                </p>
              </div>
            </div>
            {/* Tooltip Arrow */}
            <div className="absolute left-8 top-full h-2 w-2 -translate-y-1/2 rotate-45 border-b border-r border-brand-500/30 bg-surface-950"></div>
          </div>
        </div>
      )}
      
      {saScore !== null && saScore !== undefined && (
        <div className="space-y-2">
          <div className="group relative text-xs text-surface-400">
            <div className="flex cursor-help items-center gap-1 w-max">
              <span>Accesibilidad Sintética (SA):</span>
              <strong className={`border-b border-dashed pb-0.5 ${saScore > 6.0 ? "text-red-400 border-red-500/50" : saScore > 4.5 ? "text-yellow-400 border-yellow-500/50" : "text-emerald-400 border-emerald-500/50"}`}>
                {saScore.toFixed(2)} {saScore > 6.0 ? "(Inviable)" : saScore > 4.5 ? "(Difícil)" : "(Fácil)"}
              </strong>
            </div>

            {/* Tooltip Hover */}
            <div className="pointer-events-none absolute bottom-full left-0 z-10 mb-2 w-max max-w-xs scale-95 opacity-0 transition-all group-hover:scale-100 group-hover:opacity-100">
              <div className="rounded-lg border border-brand-500/30 bg-surface-950 p-3 shadow-xl">
                <h4 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-brand-400">Accesibilidad Sintética (SA Score)</h4>
                <div className="mt-1 space-y-1.5 text-[11px] text-surface-300">
                  <p>
                    Estima qué tan difícil será sintetizar esta molécula en un laboratorio real.
                  </p>
                  <p className="text-[10px] text-surface-400">
                    Se basa en la complejidad estructural (anillos, estereocentros) y fragmentos inusuales comparados con catálogos químicos (RDKit).
                  </p>
                  <div className="mt-2 flex justify-between border-t border-surface-800 pt-2 text-[9px] font-bold">
                    <span className="text-emerald-400">1.0 = Muy Fácil</span>
                    <span className="text-yellow-400">4.5+ = Difícil</span>
                    <span className="text-red-400">6.0+ = Inviable</span>
                  </div>
                </div>
              </div>
              {/* Tooltip Arrow */}
              <div className="absolute left-8 top-full h-2 w-2 -translate-y-1/2 rotate-45 border-b border-r border-brand-500/30 bg-surface-950"></div>
            </div>
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
