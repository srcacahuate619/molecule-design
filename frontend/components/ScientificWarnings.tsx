type Props = {
  warnings: string[] | null;
};

export function ScientificWarnings({ warnings }: Props) {
  if (!warnings || warnings.length === 0) return null;

  return (
    <section className="rounded-xl border border-yellow-600/30 bg-yellow-950/20 p-5">
      <h3 className="mb-2 font-bold text-yellow-400">⚠ Advertencias científicas</h3>
      <p className="mb-3 text-xs text-surface-400">
        Limitaciones detectadas en esta evaluación. Considerar antes de interpretar resultados.
      </p>
      <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed text-yellow-200/80">
        {warnings.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </section>
  );
}
