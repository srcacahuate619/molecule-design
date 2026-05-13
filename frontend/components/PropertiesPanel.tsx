import type { EvaluationResult } from "../lib/types";

type Props = {
  result: EvaluationResult;
};

function Pill({ ok, label }: { ok: boolean | null; label: string }) {
  if (ok === null || ok === undefined) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold ${
        ok
          ? "border-emerald-600/40 bg-emerald-900/30 text-emerald-400"
          : "border-red-600/40 bg-red-900/30 text-red-400"
      }`}
    >
      {ok ? "✓" : "✗"} {label}
    </span>
  );
}

function Row({ label, value, unit }: { label: string; value: number | null | undefined; unit?: string }) {
  if (value === null || value === undefined) return null;
  const display = typeof value === "number" ? (Number.isInteger(value) ? String(value) : value.toFixed(2)) : String(value);
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-surface-400">{label}</span>
      <span className="tabular-nums text-gray-300">
        {display}
        {unit && <span className="ml-1 text-surface-500">{unit}</span>}
      </span>
    </div>
  );
}

export function PropertiesPanel({ result }: Props) {
  const hasProps =
    result.molecular_weight !== null ||
    result.log_p !== null ||
    result.tpsa !== null;

  if (!hasProps) return null;

  return (
    <section className="space-y-3 rounded-xl border border-surface-800 bg-surface-900 p-5">
      <h3 className="font-bold text-white">Propiedades fisicoquímicas</h3>
      <p className="text-xs text-surface-400">
        Calculadas con RDKit. Valores reales, no estimaciones de IA.
      </p>

      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
        <Row label="Peso molecular" value={result.molecular_weight} unit="Da" />
        <Row label="LogP" value={result.log_p} />
        <Row label="TPSA" value={result.tpsa} unit="Å²" />
        <Row label="HBD" value={result.hbd} />
        <Row label="HBA" value={result.hba} />
        <Row label="Rot. bonds" value={result.rotatable_bonds} />
        <Row label="Átomos pesados" value={result.heavy_atom_count} />
        <Row label="Anillos" value={result.ring_count} />
        <Row label="QED" value={result.qed} />
        <Row label="SA Score" value={result.sa_score} />
      </div>

      {result.sa_reasons && result.sa_reasons.length > 0 && (
        <div className="mt-2 space-y-1 rounded-lg border border-yellow-900/30 bg-yellow-950/20 p-2.5">
          <p className="text-[10px] font-bold uppercase tracking-wider text-yellow-500/80">Alertas de Accesibilidad (SA)</p>
          <ul className="list-inside list-disc space-y-0.5">
            {result.sa_reasons.map((reason, idx) => (
              <li key={idx} className="text-[11px] text-yellow-200/70">{reason}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        <Pill ok={result.lipinski_pass} label="Lipinski" />
        <Pill ok={result.veber_pass} label="Veber" />
      </div>
    </section>
  );
}
