import { useState } from "react";

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
  onSave?: (customName?: string) => void;
  isSaved?: boolean;
  solanaSignature?: string | null;
  onDownloadCertificate?: () => void;
  isControl?: boolean;
  saScore?: number | null;
  saReasons?: string[] | null;
  rawVinaKcal?: number | null;
  rawXgboostKcal?: number | null;
  lipophilicEfficiency?: number | null;
  specificity?: number | null;
  affinityMultiplier?: number | null;
  specificityMultiplier?: number | null;
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
  lipophilicEfficiency,
  specificity,
  affinityMultiplier,
  specificityMultiplier,
}: ScoreCardProps) {
  const [isSavingPrompt, setIsSavingPrompt] = useState(false);
  const [customName, setCustomName] = useState("");

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

      <div className="flex flex-col gap-3 pt-2">
        {isSavingPrompt ? (
          <div className="rounded-lg border border-brand-500/30 bg-surface-950 p-4 shadow-xl">
            <p className="mb-2 text-xs font-semibold text-surface-200">Asigna un nombre a este candidato (Opcional)</p>
            <input 
              type="text" 
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              placeholder="Ej. MDX-7E2Y-51D1"
              className="w-full rounded bg-surface-900 px-3 py-2 text-sm text-white border border-surface-700 focus:border-brand-500 focus:outline-none mb-3"
            />
            <div className="flex gap-2">
              <button 
                onClick={() => setIsSavingPrompt(false)}
                className="flex-1 rounded py-2 text-xs font-bold text-surface-400 bg-surface-800 hover:text-white"
              >
                Cancelar
              </button>
              <button 
                onClick={() => {
                  if (onSave) onSave(customName.trim() || undefined);
                  setIsSavingPrompt(false);
                }}
                className="flex-1 rounded bg-brand-600 py-2 text-xs font-bold text-white hover:bg-brand-500"
              >
                Confirmar y Guardar
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {(onSave || onCertify || solanaSignature) && (
              <div className="flex gap-3">
                {onSave && (
                  <button
                    onClick={() => setIsSavingPrompt(true)}
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
                  <a
                    href={`https://explorer.solana.com/tx/${solanaSignature}?cluster=devnet`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-[#14F195]/10 text-[#14F195] py-3 font-semibold text-center transition-all hover:bg-[#14F195]/20"
                    title="Ver en Solana Explorer"
                  >
                    ✓ Certificada en Solana
                  </a>
                ) : onCertify ? (
                  <button
                    onClick={onCertify}
                    className="flex-1 text-center rounded-lg bg-gradient-to-r from-[#9945FF] to-[#14F195] py-3 font-bold text-white shadow-lg transition-all hover:opacity-90 active:scale-95"
                  >
                    Certificar en Solana
                  </button>
                ) : null}
              </div>
            )}

            {onDownloadCertificate && (
              <button
                onClick={onDownloadCertificate}
                className="w-full flex items-center justify-center gap-2 rounded-lg border border-brand-500/30 bg-brand-500/10 text-brand-400 py-3 px-4 font-bold text-sm tracking-wide transition-all hover:bg-brand-500/20 active:scale-[0.98]"
              >
                📥 {solanaSignature ? "Descargar Certificado PDF (On-Chain)" : "Descargar Reporte Científico (PDF)"}
              </button>
            )}
          </div>
        )}
        

        
        {!onSave && !onCertify && !solanaSignature && (
          <div className="w-full text-center rounded-lg border border-brand-500/20 bg-surface-950/50 p-3 shadow-inner">
            <p className="text-xs text-surface-300">
              Para <strong className="text-white">guardar</strong> el diseño y <strong className="text-brand-400">certificarlo en Solana</strong>, necesitas <a href="/login" className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2 font-bold">iniciar sesión</a>.
            </p>
          </div>
        )}
      </div>

      <ScoreBar label="Afinidad" value={affinity} weight="45%" color="#3b82f6" />
      
      {!isControl ? (
        <>
          <ScoreBar label="ADME" value={adme} weight="30%" color="#8b5cf6" />
          <ScoreBar label="Drug-likeness" value={druglikeness} weight="25%" color="#06b6d4" />
          {specificity !== null && specificity !== undefined && (
            <ScoreBar label="Especificidad" value={specificity} color="#f59e0b" />
          )}
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

      {lipophilicEfficiency !== null && lipophilicEfficiency !== undefined && (
        <div className="group relative text-xs text-surface-400">
          <div className="flex cursor-help items-center gap-1 w-max">
            <span>Lipophilic Efficiency (LLE):</span>
            <strong className="text-emerald-400 border-b border-dashed border-emerald-500/50 pb-0.5">
              {lipophilicEfficiency.toFixed(3)}
            </strong>
          </div>
          
          {/* Tooltip Hover */}
          <div className="pointer-events-none absolute bottom-full left-0 z-10 mb-2 w-max max-w-xs scale-95 opacity-0 transition-all group-hover:scale-100 group-hover:opacity-100">
            <div className="rounded-lg border border-brand-500/30 bg-surface-950 p-3 shadow-xl">
              <h4 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-emerald-400">Lipophilic Efficiency (LLE)</h4>
              <div className="mt-1 space-y-1.5 text-[11px] text-surface-300">
                <p>
                  Mide la "calidad" de la afinidad. Evita que la molécula sea potente solo por ser demasiado grasa.
                </p>
                <div className="mt-2 rounded bg-surface-900 p-2 text-center font-mono text-[10px] text-emerald-300 border border-surface-800">
                  LLE = (-Afinidad / 1.36) - LogP
                </div>
                <p className="mt-2 text-[9px] text-surface-500">
                  Calculado con escala termodinámica (factor de conversión de 1.36 kcal/mol a pKd). Se busca un LLE {">"} 3 o incluso {">"} 5.
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

      {/* Relleno matemático para auditabilidad [NUEVO] */}
      <div className="mt-6 border-t border-surface-800/50 pt-4">
        <details className="group cursor-pointer">
          <summary className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-surface-500 transition-colors hover:text-surface-300">
            <span className="text-xs transition-transform group-open:rotate-90">▶</span>
            Rigor Científico y Auditoría Matemática
          </summary>
          <div className="mt-4 space-y-3 rounded-lg bg-surface-950/50 p-4 font-mono text-[11px] text-surface-400">
            {isControl ? (
              <div className="flex justify-between border-b border-surface-800/30 pb-2">
                <span>Fórmula del Score Compuesto:</span>
                <span className="text-surface-500">Métrica de Afinidad Pura (Control)</span>
              </div>
            ) : (
              <div className="flex justify-between border-b border-surface-800/30 pb-2">
                <span>Fórmula del Score Compuesto:</span>
                <span className="text-surface-500">[(A·0.45) + (P·M_a)] · M_s</span>
              </div>
            )}
            
            <div className="grid grid-cols-2 gap-4 pt-1">
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span>(A) Afin. Score:</span>
                  <span className="text-blue-400">{(affinity || 0).toFixed(2)}</span>
                </div>
                {!isControl && (
                  <div className="flex justify-between">
                    <span>(P) Phys. Score:</span>
                    <span className="text-purple-400">
                      {((adme || 0) * 0.30 + (druglikeness || 0) * 0.25).toFixed(2)}
                    </span>
                  </div>
                )}
              </div>
              
              <div className="space-y-1">
                {!isControl && (
                  <div className="flex justify-between">
                    <span>(M_a) Multipl. A:</span>
                    <span className={affinityMultiplier && affinityMultiplier < 1.0 ? "text-red-400" : "text-emerald-400"}>
                      {(affinityMultiplier ?? 1.0).toFixed(3)}
                    </span>
                  </div>
                )}
                {!isControl && (
                  <div className="flex justify-between">
                    <span>(M_s) Multipl. S:</span>
                    <span className={specificityMultiplier && specificityMultiplier < 1.0 ? "text-orange-400" : "text-emerald-400"}>
                      {(specificityMultiplier ?? 1.0).toFixed(3)}
                    </span>
                  </div>
                )}
              </div>
              
              <div className="col-span-2 pt-2 border-t border-surface-800/30">
                {!isControl && (
                  <p className="text-[10px] text-surface-500 mb-2">
                    * Nota: El "Phys. Score" es la suma ponderada de ADME (30%) y Drug-likeness (25%). 
                    M_a penaliza si la afinidad es baja, y M_s penaliza la falta de interacción con hotspots.
                  </p>
                )}
                <div className="flex justify-between text-xs font-bold text-gray-200 bg-surface-800/30 p-2 rounded">
                  <span>Resultado Final:</span>
                  <strong className={scoreColor}>{totalDisplay}</strong>
                </div>
              </div>
            </div>
          </div>
        </details>
      </div>
    </section>
  );
}
