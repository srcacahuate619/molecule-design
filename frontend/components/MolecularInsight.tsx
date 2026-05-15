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
      message: `El SA Score de ${result.sa_score} indica que esta estructura es muy difícil de sintetizar. ${result.sa_reasons?.length ? "Causa principal: " + result.sa_reasons.join(", ") : "Considera simplificar el scaffold."}`
    });
  }

  // 3. Consistencia Vina vs ML v4.0 (Ajustado por honestidad científica)
  if (result.affinity_kcal !== null) {
    if (result.total_score !== null && result.total_score > 35) {
      insights.push({
        type: "success",
        title: "Validación Científica v4.0",
        message: "Los descriptores de interacción (ProLIF) y el modelo ML confirman una señal biológica prometedora para el target seleccionado (Spearman ρ=0.512)."
      });
    } else {
      insights.push({
        type: "info",
        title: "Señal Biológica Débil",
        message: "El modelo ML v4.0 no detecta suficientes interacciones clave. La molécula podría no tener la orientación adecuada en el bolsillo de unión."
      });
    }
  }

  // 4. Eficiencia de Ligando (Ajustado para evitar falsos positivos en moléculas junk)
  if (result.ligand_efficiency !== null && result.ligand_efficiency < -0.3) {
    if (result.total_score !== null && result.total_score > 30) {
      insights.push({
        type: "success",
        title: "Alta Eficiencia de Ligando",
        message: `Con un LE de ${result.ligand_efficiency.toFixed(3)}, cada átomo pesado está contribuyendo significativamente a la unión. Es un excelente punto de partida para optimización.`
      });
    } else {
      insights.push({
        type: "info",
        title: "Aprovechamiento de Fragmento",
        message: `Aunque la molécula es pequeña y eficiente (LE: ${result.ligand_efficiency.toFixed(3)}), su tamaño actual no es suficiente para generar una afinidad competitiva.`
      });
    }
  }

  if (insights.length === 0) return null;

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
