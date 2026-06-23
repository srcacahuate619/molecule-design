import { useState } from "react";

type ScoreBarProps = {
  label: string;
  value: number | null;
  weight?: string;
  color: string;
  onClick?: () => void;
};

function ScoreBar({ label, value, weight, color, onClick }: ScoreBarProps) {
  const display = value !== null && value !== undefined ? value.toFixed(1) : "—";
  const pct = value !== null && value !== undefined ? Math.max(0, Math.min(100, value)) : 0;

  const content = (
    <div className="space-y-1.5 w-full text-left">
      <div className="flex items-center justify-between text-sm">
        <span>
          <span className="font-semibold text-gray-200">{label}</span>
          {weight && <span className="ml-1 text-surface-400">({weight})</span>}
        </span>
        <span className="tabular-nums text-gray-300">{display}/100</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-800">
        <div
          className="score-bar-fill h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );

  if (onClick) {
    return (
      <button 
        type="button" 
        onClick={onClick} 
        className="block w-full hover:scale-[1.02] hover:bg-surface-800/30 p-2 -mx-2 rounded-lg transition-all"
      >
        {content}
      </button>
    );
  }

  return content;
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
  onViewCertificate?: () => void;
  onDownloadComplex?: () => void;
  isControl?: boolean;
  saScore?: number | null;
  saReasons?: string[] | null;
  rawVinaKcal?: number | null;
  rawXgboostKcal?: number | null;
  lipophilicEfficiency?: number | null;
  specificity?: number | null;
  affinityMultiplier?: number | null;
  specificityMultiplier?: number | null;
  gnnScore?: number | null;
  bloodViabilityScore?: number | null;
  bloodSystemicReactivity?: string[] | null;
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
  onViewCertificate,
  onDownloadComplex,
  isControl = false,
  saScore,
  saReasons,
  rawVinaKcal,
  rawXgboostKcal,
  lipophilicEfficiency,
  specificity,
  affinityMultiplier,
  specificityMultiplier,
  gnnScore,
  bloodViabilityScore,
  bloodSystemicReactivity,
}: ScoreCardProps) {
  const [isSavingPrompt, setIsSavingPrompt] = useState(false);
  const [customName, setCustomName] = useState("");
  const [selectedEducationalMetric, setSelectedEducationalMetric] = useState<{title: string, desc: React.ReactNode, icon?: string, math?: React.ReactNode} | null>(null);

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

  let tier = "D-Tier";
  let tierColor = "bg-rose-500/10 text-rose-400 border-rose-500/25";
  let tierGlow = "";
  
  if (totalScore !== null) {
    if (totalScore >= 85) {
      tier = "S-Tier";
      tierColor = "bg-amber-500/10 text-amber-400 border-amber-500/30 font-black animate-pulse";
      tierGlow = "shadow-[0_0_15px_rgba(245,158,11,0.2)]";
    } else if (totalScore >= 70) {
      tier = "A-Tier";
      tierColor = "bg-fuchsia-500/10 text-fuchsia-400 border-fuchsia-500/25";
      tierGlow = "shadow-[0_0_10px_rgba(217,70,239,0.15)]";
    } else if (totalScore >= 55) {
      tier = "B-Tier";
      tierColor = "bg-cyan-500/10 text-cyan-400 border-cyan-500/25";
      tierGlow = "shadow-[0_0_10px_rgba(6,182,212,0.15)]";
    } else if (totalScore >= 40) {
      tier = "C-Tier";
      tierColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/25";
      tierGlow = "shadow-[0_0_10px_rgba(16,185,129,0.1)]";
    }
  }

  return (
    <section className="space-y-4 rounded-xl border border-surface-800 bg-surface-900 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-bold text-white">Score compuesto</h3>
          {totalScore !== null && (
            <span className={`px-2 py-0.5 rounded-full border text-[9px] font-black uppercase tracking-widest ${tierColor} ${tierGlow}`}>
              {tier}
            </span>
          )}
        </div>
        <span className={`text-3xl font-black tracking-tighter tabular-nums ${scoreColor}`}>
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
              <div className="flex flex-col sm:flex-row gap-3">
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
              <div className="flex gap-2 w-full mt-2">
                {onViewCertificate && (
                  <button
                    onClick={onViewCertificate}
                    className="flex-1 flex items-center justify-center gap-2 rounded-lg border border-brand-500/50 bg-brand-500/20 text-brand-300 py-3 px-4 font-bold text-sm tracking-wide transition-all hover:bg-brand-500/30 active:scale-[0.98]"
                  >
                    👁 Ver Reporte
                  </button>
                )}
                <button
                  onClick={onDownloadCertificate}
                  className={`${onViewCertificate ? "flex-[0.4]" : "w-full"} flex items-center justify-center gap-2 rounded-lg border border-surface-600 bg-surface-800 text-surface-300 py-3 px-4 font-bold text-sm tracking-wide transition-all hover:bg-surface-700 active:scale-[0.98]`}
                  title="Descargar PDF"
                >
                  📥 {onViewCertificate ? "Descargar" : (solanaSignature ? "Descargar Certificado PDF (On-Chain)" : "Descargar Reporte Científico (PDF)")}
                </button>
              </div>
            )}

            {onDownloadComplex && (
              <button
                onClick={onDownloadComplex}
                className="w-full flex items-center justify-center gap-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 py-3 px-4 font-bold text-sm tracking-wide transition-all hover:bg-indigo-500/20 active:scale-[0.98] mt-2"
              >
                🧬 Descargar Complejo 3D (PDB)
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

      <ScoreBar 
        label="Afinidad" 
        value={affinity} 
        weight="45%" 
        color="#3b82f6" 
        onClick={() => setSelectedEducationalMetric({
          title: "Afinidad (Energía de Unión)",
          icon: "🧲",
          desc: "La afinidad mide qué tan fuerte se 'pega' tu molécula a la proteína diana. En el mundo físico, esto se representa mediante la Energía Libre de Gibbs (ΔG). Mientras más negativo sea el valor de kcal/mol, más fuerte es la unión (como imanes más potentes).",
          math: "Un ΔG de -9.0 kcal/mol es típicamente un billón de veces más afín que un ΔG de -1.0 kcal/mol."
        })}
      />
      
      {!isControl ? (
        <>
          {bloodViabilityScore !== undefined && (
            <ScoreBar 
              label="Viabilidad Sanguínea" 
              value={bloodViabilityScore} 
              color="#ef4444" 
              onClick={() => setSelectedEducationalMetric({
                title: "Viabilidad Sanguínea (ADMET)",
                icon: "🩸",
                desc: "Representa qué tan probable es que tu molécula sobreviva en la sangre y órganos sin causar toxicidad fatal. Un score bajo aquí destruirá tu Score Compuesto sin importar qué tan buena sea la afinidad, ya que una molécula tóxica nunca podría ser un fármaco aprobado."
              })}
            />
          )}
          <ScoreBar 
            label="ADME" 
            value={adme} 
            weight="30%" 
            color="#8b5cf6" 
            onClick={() => setSelectedEducationalMetric({
              title: "Perfil ADME",
              icon: "🩸",
              desc: "ADME significa Absorción, Distribución, Metabolismo y Excreción. Este score evalúa cómo el cuerpo humano procesaría tu fármaco. Si es muy bajo, tu molécula podría ser destruida por el hígado antes de llegar a la proteína diana o ser expulsada inmediatamente por los riñones."
            })}
          />
          <ScoreBar 
            label="Drug-likeness" 
            value={druglikeness} 
            weight="25%" 
            color="#06b6d4" 
            onClick={() => setSelectedEducationalMetric({
              title: "Similitud a Fármaco (Drug-likeness)",
              icon: "💊",
              desc: "Evalúa si tu molécula cumple las reglas históricas (como la Regla de los 5 de Lipinski) para ser una buena pastilla oral. Las moléculas gigantes o súper grasosas suelen ser malos fármacos porque no pueden atravesar las paredes celulares del intestino.",
              math: "Penalizaciones comunes: Peso > 500 Da, LogP > 5, más de 10 rotaciones."
            })}
          />
          {specificity !== null && specificity !== undefined && (
            <ScoreBar 
              label="Especificidad" 
              value={specificity} 
              color="#f59e0b" 
              onClick={() => setSelectedEducationalMetric({
                title: "Especificidad de Diana",
                icon: "🎯",
                desc: "Mide qué tan enfocada está la molécula en los 'Puntos Calientes' (Hotspots) de la proteína. Un fármaco muy grande que toca todo el exterior pero no entra al bolsillo activo tendrá una baja especificidad, lo que causa efectos secundarios severos en la vida real."
              })}
            />
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
        <div className="text-xs text-surface-400 mt-2">
          <button 
            onClick={() => setSelectedEducationalMetric({
              title: "Desglose de Afinidad (Motores de IA)",
              icon: "🤖",
              desc: "Tu puntaje final de afinidad no viene de un solo algoritmo, sino de dos que se supervisan mutuamente para evitar 'alucinaciones' o falsos positivos.",
              math: (
                <div className="space-y-2 mt-2">
                  <div className="flex justify-between border-b border-surface-700 pb-1">
                    <span>1. AutoDock Vina (Física Pura):</span>
                    <strong className="text-white">{rawVinaKcal !== null && rawVinaKcal !== undefined ? `${rawVinaKcal.toFixed(3)} kcal/mol` : "N/A"}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>2. XGBoost (Inteligencia Espacial):</span>
                    <strong className="text-brand-300">{rawXgboostKcal !== null && rawXgboostKcal !== undefined ? `${rawXgboostKcal.toFixed(3)} kcal/mol` : "N/A"}</strong>
                  </div>
                </div>
              )
            })}
            className="flex items-center gap-1 w-max hover:text-white transition-colors"
          >
            <span>Afinidad combinada (Vina + XGBoost):</span>
            <strong className="text-gray-300 border-b border-dashed border-gray-500 pb-0.5">
              {affinityKcal.toFixed(3)} kcal/mol
            </strong>
          </button>
        </div>
      )}

      {ligandEfficiency !== null && ligandEfficiency !== undefined && (
        <div className="text-xs text-surface-400 mt-2">
          <button 
            onClick={() => setSelectedEducationalMetric({
              title: "Eficiencia del Ligando (LE)",
              icon: "⚖️",
              desc: "A veces, moléculas gigantes se unen fuerte solo por ser grandes (como velcro enorme), pero son pésimos fármacos. El 'LE' mide qué tan eficiente es CADA átomo de tu molécula generando afinidad. Fármacos inteligentes logran alta afinidad con pocos átomos.",
              math: "LE = Afinidad / Número de Átomos Pesados. Un valor típico para fármacos orales ronda los -0.3 kcal/mol/átomo. ¡A menor valor, mejor!"
            })}
            className="flex items-center gap-1 w-max hover:text-brand-300 transition-colors"
          >
            <span>Ligand Efficiency (LE):</span>
            <strong className="text-brand-400 border-b border-dashed border-brand-500/50 pb-0.5">
              {ligandEfficiency.toFixed(3)} kcal/mol/atom
            </strong>
          </button>
        </div>
      )}

      {lipophilicEfficiency !== null && lipophilicEfficiency !== undefined && (
        <div className="text-xs text-surface-400 mt-2">
          <button 
            onClick={() => setSelectedEducationalMetric({
              title: "Eficiencia Lipofílica (LLE)",
              icon: "🧼",
              desc: "Mide la 'calidad' de tu afinidad en relación con cuánta grasa tiene tu molécula. Evita que crees moléculas súper potentes pero que sean solo manchas de grasa que el hígado no puede procesar.",
              math: "LLE = (-Afinidad / 1.36) - LogP. Valores mayores a 5 indican un candidato clínico fantástico."
            })}
            className="flex items-center gap-1 w-max hover:text-emerald-300 transition-colors"
          >
            <span>Lipophilic Efficiency (LLE):</span>
            <strong className="text-emerald-400 border-b border-dashed border-emerald-500/50 pb-0.5">
              {lipophilicEfficiency.toFixed(3)}
            </strong>
          </button>
        </div>
      )}

      {gnnScore !== null && gnnScore !== undefined && (
        <div className="text-xs text-surface-400 mt-2">
          <button 
            onClick={() => setSelectedEducationalMetric({
              title: "Evaluación de Red Neuronal de Grafos (GNN)",
              icon: "🧠",
              desc: "MolDesign usa una IA especializada llamada RTMScore (Red Neuronal de Grafos) que funciona como un inspector 3D. Revisa átomo por átomo cómo encaja tu molécula en el receptor y castiga duramente si hay 'choques estéricos' (átomos atravesándose entre sí).",
              math: "Multiplicador de Calidad: Valores mayores a 20.0 aumentan tu score general. Valores menores lo reducen drásticamente."
            })}
            className="flex items-center gap-1 w-max hover:text-purple-300 transition-colors"
          >
            <span>Inteligencia GNN (Nivel 2):</span>
            <strong className="text-purple-400 border-b border-dashed border-purple-500/50 pb-0.5">
              {gnnScore.toFixed(2)} (x{((() => {
                const rawFactor = 1.0 / (1.0 + Math.exp(-0.05 * (gnnScore - 20.0)));
                return 0.7 + (rawFactor * 0.45);
              })()).toFixed(3)})
            </strong>
          </button>
        </div>
      )}
      
      {saScore !== null && saScore !== undefined && (
        <div className="space-y-2 mt-2">
          <div className="text-xs text-surface-400">
            <button 
              onClick={() => setSelectedEducationalMetric({
                title: "Accesibilidad Sintética (SA Score)",
                icon: "🧪",
                desc: "No sirve de nada diseñar el fármaco perfecto en la computadora si los químicos en la vida real no pueden fabricarlo. El SA Score analiza la complejidad de tus anillos, puentes y quiralidad para saber si tu molécula es viable para ser sintetizada en un laboratorio.",
                math: (
                  <div className="mt-2 flex justify-between border-t border-surface-800 pt-2 text-xs font-bold w-full">
                    <span className="text-emerald-400">1.0 = Muy Fácil</span>
                    <span className="text-yellow-400">4.5+ = Difícil</span>
                    <span className="text-red-400">6.0+ = Imposible</span>
                  </div>
                )
              })}
              className="flex items-center gap-1 w-max hover:text-white transition-colors"
            >
              <span>Accesibilidad Sintética (SA):</span>
              <strong className={`border-b border-dashed pb-0.5 ${saScore > 6.0 ? "text-red-400 border-red-500/50" : saScore > 4.5 ? "text-yellow-400 border-yellow-500/50" : "text-emerald-400 border-emerald-500/50"}`}>
                {saScore.toFixed(2)} {saScore > 6.0 ? "(Inviable)" : saScore > 4.5 ? "(Difícil)" : "(Fácil)"}
              </strong>
            </button>
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
          
          {bloodSystemicReactivity && bloodSystemicReactivity.length > 0 && (
            <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-2.5 animate-pulse">
              <div className="flex items-center gap-1.5 mb-1 text-[10px] font-black text-red-500 uppercase tracking-wider">
                <span className="text-sm">☠️</span> Peligro Toxicológico
              </div>
              <ul className="space-y-1">
                {bloodSystemicReactivity.map((reason, idx) => (
                  <li key={idx} className="text-[11px] font-bold text-red-400/90 leading-tight">• {reason}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {bloodViabilityScore !== null && bloodViabilityScore !== undefined && (
        <div className="text-xs text-surface-400 mt-2">
          <button 
            onClick={() => setSelectedEducationalMetric({
              title: "Viabilidad Sanguínea (M_v)",
              icon: "🩸",
              desc: "Mide la probabilidad de que la molécula sea viable en sangre sin causar toxicidades sistémicas fatales. Un valor de 100% significa sin toxicidad conocida. Valores menores reducen directamente el score final como multiplicador agresivo (M_v = Score / 100).",
              math: `Multiplicador M_v: ${(bloodViabilityScore / 100).toFixed(3)}`
            })}
            className="flex items-center gap-1 w-max hover:text-red-300 transition-colors"
          >
            <span>Viabilidad en Sangre:</span>
            <strong className={`border-b border-dashed pb-0.5 ${bloodViabilityScore < 100 ? "text-red-400 border-red-500/50" : "text-emerald-400 border-emerald-500/50"}`}>
              {bloodViabilityScore.toFixed(1)}% (x{(bloodViabilityScore / 100).toFixed(3)})
            </strong>
          </button>
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
                <span className="text-surface-500">
                  {gnnScore !== null && gnnScore !== undefined 
                    ? "[(A·M_g·0.45) + (P·M_a)] · M_s · M_sa · M_v" 
                    : "[(A·0.45) + (P·M_a)] · M_s · M_sa · M_v"}
                </span>
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
                {!isControl && gnnScore !== null && gnnScore !== undefined && (
                  <div className="flex justify-between">
                    <span>(M_g) Multipl. G:</span>
                    <span className={((0.7 + (1.0 / (1.0 + Math.exp(-0.05 * (gnnScore - 20.0)))) * 0.45)) < 1.0 ? "text-red-400" : "text-purple-400 font-bold"}>
                      {((0.7 + (1.0 / (1.0 + Math.exp(-0.05 * (gnnScore - 20.0)))) * 0.45)).toFixed(3)}
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
                {!isControl && (
                  <div className="flex justify-between">
                    <span>(M_sa) Penaliz. SA:</span>
                    <span className={(saScore ?? 0) > 6.0 ? "text-red-400" : "text-emerald-400"}>
                      {(saScore ?? 0) > 6.0 ? ((saScore ?? 0) > 7.0 ? 0.0 : ((7.0 - (saScore ?? 0)) / 1.0)).toFixed(3) : "1.000"}
                    </span>
                  </div>
                )}
                {!isControl && (
                  <div className="flex justify-between">
                    <span>(M_v) Viab. Sangre:</span>
                    <span className={bloodViabilityScore && bloodViabilityScore < 100 ? "text-red-400" : "text-emerald-400"}>
                      {bloodViabilityScore !== undefined && bloodViabilityScore !== null ? (bloodViabilityScore / 100).toFixed(3) : "1.000"}
                    </span>
                  </div>
                )}
              </div>
              
              <div className="col-span-2 pt-2 border-t border-surface-800/30">
                {!isControl && (
                  <p className="text-[10px] text-surface-500 mb-2 font-sans">
                    * Nota: El "Phys. Score" es la suma ponderada de ADME y Drug-likeness. 
                    M_g aplica sólo sobre Afinidad (A). M_a penaliza afinidad general baja. M_s penaliza hotspots. M_sa y M_v (Viabilidad Sanguínea) son factores finales agresivos.
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

      {/* Modal Métrica Educativa */}
      {selectedEducationalMetric && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in"
          onClick={() => setSelectedEducationalMetric(null)}
        >
          <div 
            className="bg-surface-900 border border-indigo-500/50 rounded-2xl p-6 max-w-md w-full shadow-2xl relative animate-in zoom-in-95 text-left"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setSelectedEducationalMetric(null)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white transition-colors"
            >
              ✕
            </button>
            <div className="flex items-center gap-4 mb-4">
              {selectedEducationalMetric.icon && <span className="text-3xl">{selectedEducationalMetric.icon}</span>}
              <h3 className="text-xl font-bold text-white leading-tight">{selectedEducationalMetric.title}</h3>
            </div>
            <p className="text-sm text-surface-300 leading-relaxed">
              {selectedEducationalMetric.desc}
            </p>
            {selectedEducationalMetric.math && (
              <div className="mt-4 bg-surface-950/80 rounded-xl p-3 border border-surface-800 text-xs font-mono text-indigo-300">
                {selectedEducationalMetric.math}
              </div>
            )}
            <div className="mt-6 flex justify-end">
              <button 
                onClick={() => setSelectedEducationalMetric(null)}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold rounded-xl transition-colors shadow-lg shadow-indigo-500/20"
              >
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}

    </section>
  );
}
