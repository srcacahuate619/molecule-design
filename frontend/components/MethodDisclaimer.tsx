export function MethodDisclaimer() {
  return (
    <section className="rounded-xl border border-blue-800/40 bg-blue-950/20 p-5 text-xs">
      <h3 className="mb-2 text-sm font-bold text-blue-300">
        ℹ Limitaciones del método
      </h3>
      <ul className="list-disc space-y-1 pl-4 leading-relaxed text-surface-400">
        <li>
          El docking computacional (AutoDock Vina) <strong className="text-gray-300">no equivale</strong> a validación experimental
          in vitro, in vivo o clínica.
        </li>
        <li>
          Las propiedades ADME se estiman por descriptores moleculares (RDKit), no por ensayo de absorción/metabolismo real.
        </li>
        <li>
          El score compuesto es una <strong className="text-gray-300">heurística de priorización</strong>, no una predicción de eficacia terapéutica.
        </li>
        <li>
          El reporte de IA interpreta resultados ya calculados; no genera ni modifica valores numéricos.
        </li>
        <li>
          Un buen score no garantiza actividad biológica; un mal score no la descarta completamente.
        </li>
      </ul>
    </section>
  );
}
