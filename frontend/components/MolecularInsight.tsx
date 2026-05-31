import type { EvaluationResult } from "../lib/types";

type Props = {
  result: EvaluationResult;
};

export function MolecularInsight({ result }: Props) {
  const insights: { type: "warning" | "success" | "info"; message: string; title: string }[] = [];

  // 1. Lógica de "Grease Ball" (Lipofilicidad vs Afinidad)
  if (result.log_p !== null && result.log_p > 5 && result.affinity_kcal !== null && result.affinity_kcal < -7.5) {
    insights.push({
      type: "warning",
      title: "Riesgo de 'Grease Ball'",
      message: "Tu molécula tiene alta afinidad pero es extremadamente lipofílica. Esto suele indicar baja solubilidad y posibles efectos tóxicos inespecíficos. Considera añadir grupos polares (OH, NH2)."
    });
  }

  // 2. Lógica de Tensión de Anillo / SA Score
  if (result.sa_score !== null && result.sa_score > 6.0) {
    insights.push({
      type: "warning",
      title: "Dificultad Sintética Crítica",
      message: `El SA Score de ${result.sa_score.toFixed(2)} indica que esta estructura es muy difícil de sintetizar. ${result.sa_reasons?.length ? "Causa principal: " + result.sa_reasons.join(", ") : "Considera simplificar el scaffold."}`
    });
  }

  // 3. Consistencia Vina vs ML v4.2 + Suelo de Afinidad
  if (result.affinity_kcal !== null) {
    const threshold = result.affinity_threshold ?? -7.5;
    const isWeak = result.affinity_kcal > threshold; // e.g., -6.2 > -7.5 is True (Weak)

    if (isWeak) {
      insights.push({
        type: "warning",
        title: "Potencia Insuficiente",
        message: `Aunque tu molécula es eficiente, su afinidad absoluta de ${result.affinity_kcal.toFixed(2)} kcal/mol es demasiado débil. Para este target, necesitamos al menos ${threshold.toFixed(2)} kcal/mol para considerar la molécula como un candidato viable.`
      });
    }

    if (result.total_score !== null && result.total_score > 35) {
      insights.push({
        type: "success",
        title: "Validación Científica",
        message: result.target_spearman_rho != null && result.target_spearman_rho !== 0
          ? `Los descriptores de interacción (ProLIF) y el modelo ML confirman una señal biológica prometedora para el target ${result.target_name || "seleccionado"} (Spearman ρ=${result.target_spearman_rho.toFixed(3)} — validado en benchmark ciego).`
          : `Los descriptores de interacción (ProLIF) y el modelo ML confirman una señal biológica prometedora para el target ${result.target_name || "seleccionado"}. La correlación Spearman de este receptor está pendiente de recálculo con la geometría de sitio activo corrigida.`
      });
    } else if (!isWeak) {
      insights.push({
        type: "info",
        title: "Señal Biológica Débil",
        message: "El modelo ML v4.2 no detecta suficientes interacciones clave. La molécula podría no tener la orientación adecuada en el bolsillo de unión."
      });
    }
  }

  // 4. Eficiencia de Ligando y Alerta de Fragmento
  if (result.ligand_efficiency !== null) {
    const isFragment = (result.heavy_atom_count ?? 0) < 15;
    
    if (result.ligand_efficiency < -0.3) {
      if (isFragment) {
        insights.push({
          type: "info",
          title: "Potencial de Fragmento",
          message: `Tu molécula es pequeña pero extremadamente eficiente (LE: ${Math.abs(result.ligand_efficiency).toFixed(3)}). Ojo: No es un fármaco aún, sino un 'semilla' ideal. Necesitas hacerla crecer para que bloquee el target de forma competitiva.`
        });
      } else if (result.total_score !== null && result.total_score > 30) {
        insights.push({
          type: "success",
          title: "Alta Eficiencia de Ligando",
          message: `Con un LE de ${Math.abs(result.ligand_efficiency).toFixed(3)}, cada átomo pesado está contribuyendo significativamente a la unión. Es un excelente punto de partida para optimización.`
        });
      }
    } else if (isFragment) {
       insights.push({
        type: "warning",
        title: "Tamaño Insuficiente",
        message: "La molécula es demasiado pequeña para este target y no tiene la eficiencia necesaria para compensarlo. Considera expandir el scaffold."
      });
    }
  }

  // 5. Análisis de Hotspots
  if (result.hotspots_hit && result.hotspots_hit.length > 0) {
    insights.push({
      type: "success",
      title: "Especificidad Biológica Lograda",
      message: `¡Excelente! Tu molécula ha logrado interactuar con los siguientes hotspots críticos: ${result.hotspots_hit.join(", ")}. Esto valida que el diseño está atacando el sitio funcional correcto.`
    });
  } else if (result.target_hotspots && result.target_hotspots.length > 0) {
    insights.push({
      type: "info",
      title: "Falta de Especificidad",
      message: "La molécula está en el sitio activo, pero no está impactando los hotspots críticos. Considera reorientar la molécula hacia estos residuos para mejorar la potencia biológica."
    });
  }

  return (
    <section className="space-y-3">
      <h3 className="text-sm font-bold uppercase tracking-widest text-surface-500">
        Análisis de Diseño Molecular
      </h3>
      <div className="grid gap-3">
        {insights.map((insight, idx) => (
          <div 
            key={idx}
            className={`rounded-xl border p-4 shadow-lg transition-all hover:scale-[1.01] ${
              insight.type === "warning" 
                ? "border-yellow-600/30 bg-yellow-950/20" 
                : insight.type === "success"
                ? "border-emerald-600/30 bg-emerald-950/20"
                : "border-blue-600/30 bg-blue-950/20"
            }`}
          >
            <div className="flex items-start gap-3">
              <div className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${
                insight.type === "warning" ? "bg-yellow-500" : insight.type === "success" ? "bg-emerald-500" : "bg-blue-500"
              }`} />
              <div>
                <h4 className={`text-sm font-bold ${
                  insight.type === "warning" ? "text-yellow-400" : insight.type === "success" ? "text-emerald-400" : "text-blue-400"
                }`}>
                  {insight.title}
                </h4>
                <p className="mt-1 text-xs leading-relaxed text-surface-300">
                  {insight.message}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
