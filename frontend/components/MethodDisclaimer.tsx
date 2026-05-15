export function MethodDisclaimer() {
  return (
    <section className="rounded-xl border border-blue-800/40 bg-blue-950/20 p-5 text-xs">
      <h3 className="mb-2 text-sm font-bold text-blue-300">
        ℹ Limitaciones del método
      </h3>
      <ul className="list-disc space-y-1 pl-4 leading-relaxed text-surface-400">
        <li>
          El docking computacional (AutoDock Vina) <strong className="text-gray-300">no equivale</strong> a validación experimental
          in vitro o clínica.
        </li>
        <li>
          Se aplica un modelo de <strong className="text-gray-300">re-scoring ML v4.2</strong> (Spearman ρ=0.512) para reducir el ruido de Vina y rescatar la señal biológica del target seleccionado.
        </li>
        <li>
          Las propiedades ADME y de accesibilidad sintética (SA) son estimaciones teóricas; un SA {">"} 6.0 indica alta complejidad estructural.
        </li>
        <li>
          El reporte de IA interpreta resultados ya calculados; no genera ni modifica valores numéricos.
        </li>
        <li>
          Un buen score compuesto es una <strong className="text-gray-300">heurística de priorización</strong> basada en afinidad y drug-likeness.
        </li>
      </ul>
    </section>
  );
}
