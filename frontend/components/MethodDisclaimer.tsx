export function MethodDisclaimer() {
  return (
    <section className="rounded-xl border border-blue-800/30 bg-blue-950/20 p-5 text-xs">
      <h3 className="mb-2 text-sm font-bold text-blue-300 flex items-center gap-1.5">
        <span>ℹ️</span> Limitaciones y Metodología Científica
      </h3>
      <ul className="list-disc space-y-1.5 pl-4 leading-relaxed text-surface-400">
        <li>
          El docking computacional (AutoDock Vina) <strong className="text-gray-300">no equivale</strong> a validación experimental
          in vitro o clínica. Actúa como una heurística biofísica predictiva de afinidad termodinámica.
        </li>
        <li>
          Se aplica un modelo de <strong className="text-gray-300">re-scoring espacial con XGBoost</strong> calibrado sobre complejos experimentales de la base de datos PDBbind para ajustar los efectos del solvente y ruido entrópico.
        </li>
        <li>
          Las estimaciones de propiedades ADME y accesibilidad sintética (SA) son teóricas basadas en modelos de subestructuras. Un SA &gt; 6.0 indica que el ligando presenta alta complejidad sintética en laboratorio real.
        </li>
        <li>
          Un score compuesto elevado es un <strong className="text-gray-300">criterio de priorización de Hits</strong> que equilibra potencia absoluta, eficiencia atómica y propiedades de farmacóforo.
        </li>
      </ul>

      {/* Detalle Científico de Fórmulas y Rigor Biofísico [NUEVO] */}
      <div className="mt-5 border-t border-blue-800/30 pt-4">
        <details className="group cursor-pointer">
          <summary className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-blue-400 transition-colors hover:text-blue-300">
            <span className="text-[8px] transition-transform group-open:rotate-90">▶</span>
            🔬 Rigor Biofísico: Auditoría de Ecuaciones y Calibración (v6.1)
          </summary>
          <div className="mt-3 space-y-4 rounded-lg bg-surface-950/60 p-4 font-mono text-[11px] leading-relaxed text-surface-400 border border-blue-950/40">
            
            {/* 1. Eficiencia Dinámica de Ligando */}
            <div className="space-y-1.5">
              <h4 className="font-bold text-blue-300 border-b border-surface-800 pb-1 text-[10px] uppercase tracking-wider">
                1. Eficiencia de Ligando Adaptativa (Size-Adaptive LE)
              </h4>
              <p className="text-surface-500 text-[10px]">
                La densidad de energía de unión requerida decae fisiológicamente con el tamaño molecular debido a restricciones de empaquetamiento estérico. El punto medio de la sigmoide (LE_mid) se calcula dinámicamente:
              </p>
              <div className="bg-surface-900/80 p-2.5 rounded border border-surface-800/50 my-2 text-center text-gray-300 leading-normal">
                {`if HeavyAtoms < 15:   LE_mid = -0.38`} <br />
                {`if HeavyAtoms > 45:   LE_mid = -0.20`} <br />
                {`else: LE_mid = -0.38 + (HeavyAtoms - 15) * (0.18 / 30)`}
              </div>
              <p className="text-surface-500 text-[10px]">
                Score de Afinidad Normalizado (S_LE):
              </p>
              <div className="bg-surface-900/80 p-2 rounded border border-surface-800/50 my-2 text-center text-brand-400">
                {`S_LE = 100 / (1 + e^(15 * (LE - LE_mid)))`}
              </div>
            </div>

            {/* 2. Penalizador de Potencia Absoluta */}
            <div className="space-y-1.5">
              <h4 className="font-bold text-blue-300 border-b border-surface-800 pb-1 text-[10px] uppercase tracking-wider">
                2. Penalizador de Potencia Absoluta Suave (Soft Boundary)
              </h4>
              <p className="text-surface-500 text-[10px]">
                Si la afinidad calculada es más débil que el umbral biológico del receptor (Threshold, ej: -7.5 kcal/mol), se aplica un decaimiento sigmoideo suave. Si cumple o supera el Threshold, no hay penalización alguna:
              </p>
              <div className="bg-surface-900/80 p-2.5 rounded border border-surface-800/50 my-2 text-center text-gray-300 leading-normal">
                {`if ΔG <= Threshold: Potency_Factor = 1.0`} <br />
                {`else: Potency_Factor = min(1.0, 2.0 / (1 + e^(2.0 * (ΔG - Threshold))))`}
              </div>
            </div>

            {/* 3. Eficiencia Lipofílica */}
            <div className="space-y-1.5">
              <h4 className="font-bold text-blue-300 border-b border-surface-800 pb-1 text-[10px] uppercase tracking-wider">
                3. Eficiencia Lipofílica (Lipophilic Efficiency - LLE)
              </h4>
              <p className="text-surface-500 text-[10px]">
                Garantiza la calidad de la interacción termodinámica evitando compuestos hiper-lipofílicos inespecíficos.
              </p>
              <div className="bg-surface-900/80 p-2 rounded border border-surface-800/50 my-2 text-center text-emerald-400">
                {`LLE = (-ΔG) - LogP`}
              </div>
              <div className="bg-surface-900/80 p-2.5 rounded border border-surface-800/50 my-2 text-gray-400 text-[10px] leading-normal">
                {`• Si LLE < 3.0: Se penaliza multiplicando por max(0.4, LLE / 3.0)`} <br />
                {`• Si LLE > 7.0: Se otorga un bonus del 5% (máximo acotado a 100)`}
              </div>
            </div>

            {/* 4. Composición de Puntuación */}
            <div className="space-y-1.5">
              <h4 className="font-bold text-blue-300 border-b border-surface-800 pb-1 text-[10px] uppercase tracking-wider">
                4. Integración y Multiplicadores de Relevancia
              </h4>
              <p className="text-surface-500 text-[10px]">
                El score físico ponderado (Physico_Score = 30% ADME + 25% Drug-likeness) es modulado por la potencia. Compuestos incapaces de unir al receptor (baja afinidad) no aportan relevancia por sus propiedades estructurales:
              </p>
              <div className="bg-surface-900/80 p-2.5 rounded border border-surface-800/50 my-2 text-[10px] text-gray-300 leading-normal">
                {`if S_LE < 20:   Affinity_Multiplier = (S_LE / 20) * 0.4 + 0.1  [Rango 0.1 - 0.5]`} <br />
                {`else:           Affinity_Multiplier = ((S_LE - 20) / 80) * 0.5 + 0.5  [Rango 0.5 - 1.0]`}
              </div>
              <p className="text-surface-500 text-[10px]">
                Score Total (escala 0-100) aplicando el multiplicador de especificidad biológica según hotspots alcanzados:
              </p>
              <div className="bg-surface-900/80 p-2.5 rounded border border-surface-800/50 my-2 text-center text-gray-300 leading-normal">
                {`Base_Score = (S_LE * 0.45) + (Physico_Score * Affinity_Multiplier)`} <br />
                {`Total_Score = Base_Score * (0.5 + 0.5 * Specificity_Score / 100)`}
              </div>
            </div>
            
          </div>
        </details>
      </div>
    </section>
  );
}
