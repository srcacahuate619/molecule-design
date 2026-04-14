import Link from "next/link";

const PIPELINE_STEPS = [
  { step: 1, icon: "🧪", title: "Validación química", desc: "RDKit valida estructura SMILES, fórmula molecular y restricciones." },
  { step: 2, icon: "📊", title: "Propiedades fisicoquímicas", desc: "MW, LogP, TPSA, HBD, HBA, QED — todo calculado con RDKit." },
  { step: 3, icon: "🔬", title: "Conformer 3D", desc: "Generación de estructura tridimensional con ETKDG." },
  { step: 4, icon: "🎯", title: "Docking molecular", desc: "AutoDock Vina contra target real + DiffDock (deep learning)." },
  { step: 5, icon: "📈", title: "Score compuesto", desc: "Afinidad (45%) + ADME (30%) + Drug-likeness (25%) auditable." },
  { step: 6, icon: "🤖", title: "Interpretación IA", desc: "Claude interpreta resultados sin inventar ni modificar cifras." },
];

const TECHNOLOGIES = [
  { name: "RDKit", desc: "Validación y propiedades", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" },
  { name: "AutoDock Vina", desc: "Docking clásico", color: "bg-blue-500/10 text-blue-400 border-blue-500/30" },
  { name: "DiffDock", desc: "Docking deep learning", color: "bg-purple-500/10 text-purple-400 border-purple-500/30" },
  { name: "AlphaFold DB", desc: "Estructuras predichas", color: "bg-amber-500/10 text-amber-400 border-amber-500/30" },
  { name: "3Dmol.js", desc: "Visualización 3D", color: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30" },
  { name: "Ketcher", desc: "Editor molecular", color: "bg-rose-500/10 text-rose-400 border-rose-500/30" },
];

export default function HomePage() {
  return (
    <div className="space-y-12">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-2xl border border-surface-800 bg-gradient-to-br from-surface-900 via-surface-900 to-brand-900/20 p-8 md:p-12">
        <div className="relative z-10">
          <div className="mb-2 inline-block rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs font-semibold text-brand-400">
            Pipeline Científico Real
          </div>
          <h1 className="mb-4 text-4xl font-bold tracking-tight text-white md:text-5xl">
            Mol<span className="text-brand-400">Design</span>
          </h1>
          <p className="mb-8 max-w-2xl text-lg leading-relaxed text-surface-400">
            Plataforma de diseño molecular asistido por IA con validez científica real.
            Cada número proviene de módulos científicos explícitos. La IA interpreta,
            nunca inventa.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/evaluation"
              className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-brand-600/20 transition-all hover:bg-brand-700 hover:shadow-brand-600/30"
            >
              Iniciar evaluación
              <span aria-hidden="true">→</span>
            </Link>
            <Link
              href="/history"
              className="inline-flex items-center gap-2 rounded-xl border border-surface-700 px-6 py-3 text-sm font-semibold text-surface-300 transition-all hover:border-surface-600 hover:bg-surface-800"
            >
              Ver historial
            </Link>
          </div>
        </div>
        {/* Background decoration */}
        <div className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-brand-500/5 blur-3xl" />
      </section>

      {/* Pipeline Steps */}
      <section>
        <h2 className="mb-6 text-2xl font-bold text-white">Pipeline científico</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {PIPELINE_STEPS.map((s) => (
            <div
              key={s.step}
              className="group rounded-xl border border-surface-800 bg-surface-900 p-5 transition-all hover:border-surface-700 hover:bg-surface-900/80"
            >
              <div className="mb-3 flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600/20 text-sm font-bold text-brand-400">
                  {s.step}
                </span>
                <span className="text-xl">{s.icon}</span>
              </div>
              <h3 className="mb-1 font-semibold text-gray-200">{s.title}</h3>
              <p className="text-sm leading-relaxed text-surface-400">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Technologies */}
      <section>
        <h2 className="mb-6 text-2xl font-bold text-white">Tecnologías</h2>
        <div className="flex flex-wrap gap-3">
          {TECHNOLOGIES.map((t) => (
            <div
              key={t.name}
              className={`rounded-lg border px-4 py-2.5 ${t.color}`}
            >
              <div className="text-sm font-semibold">{t.name}</div>
              <div className="text-xs opacity-70">{t.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Scientific Principles */}
      <section className="rounded-2xl border border-surface-800 bg-surface-900 p-6">
        <h2 className="mb-4 text-lg font-bold text-white">Principios científicos</h2>
        <ul className="space-y-2 text-sm leading-relaxed text-surface-400">
          <li className="flex items-start gap-2">
            <span className="mt-0.5 text-emerald-400">✓</span>
            Todos los valores provienen de módulos científicos explícitos (RDKit, Vina)
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 text-emerald-400">✓</span>
            La IA interpreta resultados — nunca inventa ni modifica cifras
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 text-emerald-400">✓</span>
            Cada resultado incluye trazabilidad completa para reproducibilidad
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 text-emerald-400">✓</span>
            Warnings y limitaciones se muestran siempre, no se ocultan
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 text-emerald-400">✓</span>
            El score es una heurística de priorización, no una verdad biológica
          </li>
        </ul>
      </section>
    </div>
  );
}
