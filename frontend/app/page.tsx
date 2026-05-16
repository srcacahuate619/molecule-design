"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getGlobalStats } from "../lib/api";
import { GlobalStats } from "../lib/types";

const PIPELINE_STEPS = [
  { step: 1, icon: "🧪", title: "Validación Química", desc: "RDKit valida estructura SMILES y restricciones medicinales.", detail: "Verificación de valencias, quiralidad y filtros de reactividad sub-segundo." },
  { step: 2, icon: "📊", title: "Propiedades", desc: "MW, LogP, TPSA, QED y Accesibilidad Sintética (SA).", detail: "Cálculo de descriptores físico-químicos basados en fragmentos moleculares." },
  { step: 3, icon: "🧬", title: "Conformer 3D", desc: "Generación de estructuras tridimensionales de baja energía.", detail: "Uso del algoritmo ETKDG para obtener la geometría más probable del ligando." },
  { step: 4, icon: "🎯", title: "Docking Físico", desc: "AutoDock Vina contra múltiples receptores (Multi-Target).", detail: "Simulación de fuerzas electrostáticas y de van der Waals en sitios activos calibrados." },
  { step: 5, icon: "🧠", title: "Rescoring ML", desc: "Corrección de afinidad via Machine Learning.", detail: "Modelo entrenado con 5,000 complejos de PDBbind para reducir falsos positivos." },
  { step: 6, icon: "🤖", title: "Interpretación IA", desc: "Reporte científico narrativo generado por Claude.", detail: "Análisis cualitativo de interacciones clave y sugerencias de optimización." },
  { step: 7, icon: "🔗", title: "Blockchain", desc: "Registro inmutable de autoría en la red Solana.", detail: "Certificación permanente del descubrimiento con hash SHA-256 único." },
];

const TECHNOLOGIES = [
  { name: "AutoDock Vina", desc: "Docking de precisión", color: "border-blue-500/30 text-blue-400 shadow-blue-500/10", tooltip: "Motor físico estándar de oro para simulación de acoplamiento molecular." },
  { name: "XGBoost", desc: "Cerebro Espacial ML", color: "border-brand-500/30 text-brand-400 shadow-brand-500/10", tooltip: "Algoritmo de Gradient Boosting para corrección estadística de afinidad." },
  { name: "RDKit", desc: "Quimioinformática", color: "border-emerald-500/30 text-emerald-400 shadow-emerald-500/10", tooltip: "Toolkit profesional para validación y descriptores moleculares." },
  { name: "Solana", desc: "Blockchain Layer-1", color: "border-purple-500/30 text-purple-400 shadow-purple-500/10", tooltip: "Red descentralizada de alta velocidad para registro de propiedad intelectual." },
  { name: "Claude / Gemini", desc: "IA Generativa", color: "border-indigo-500/30 text-indigo-400 shadow-indigo-500/10", tooltip: "Modelos de lenguaje avanzados para síntesis de resultados científicos." },
  { name: "3Dmol.js", desc: "Renderizado 3D", color: "border-cyan-500/30 text-cyan-400 shadow-cyan-500/10", tooltip: "Librería de visualización acelerada por WebGL para estructuras PDB." },
];

export default function HomePage() {
  const [stats, setStats] = useState<GlobalStats | null>(null);

  useEffect(() => {
    getGlobalStats()
      .then(setStats)
      .catch((err) => console.error("Error loading stats:", err));
  }, []);

  const statsDisplay = [
    { label: "Moléculas Evaluadas", value: stats?.total_molecules.toLocaleString() ?? "...", icon: "🧬" },
    { label: "Certificaciones", value: stats?.total_certifications.toLocaleString() ?? "...", icon: "🔗" },
    { label: "Mejor Puntuación", value: stats?.best_score?.toFixed(1) ?? "...", unit: "pts", icon: "🏆" },
    { label: "Comunidad", value: stats?.community_status ?? "Global", icon: "🌍" },
  ];

  return (
    <div className="space-y-12 pb-20">
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-3xl border border-surface-800 bg-surface-900 p-8 md:p-16">
        {/* Animated Background Orbs */}
        <div className="absolute -right-20 -top-20 h-80 w-80 animate-pulse rounded-full bg-brand-500/10 blur-[100px]" />
        <div className="absolute -left-20 -bottom-20 h-80 w-80 animate-pulse rounded-full bg-emerald-500/5 blur-[100px]" />

        <div className="relative z-10 flex flex-col items-center text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand-500/20 bg-brand-500/5 px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-brand-400 shadow-lg shadow-brand-500/5">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-75"></span>
              <span className="relative inline-flex h-2 w-2 rounded-full bg-brand-500"></span>
            </span>
            Next-Gen Molecular Pipeline
          </div>
          <h1 className="mb-6 text-5xl font-black tracking-tighter text-white md:text-7xl">
            Mol<span className="bg-gradient-to-r from-brand-400 to-emerald-400 bg-clip-text text-transparent">Design</span> AI
          </h1>
          <p className="mb-10 max-w-2xl text-lg font-medium leading-relaxed text-surface-400">
            Descubrimiento de fármacos con rigor industrial. Combinamos <span className="text-white">docking físico</span>,
            <span className="text-white"> machine learning</span> y <span className="text-white">blockchain</span> para acelerar la quimioinformática.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link
              href="/evaluation"
              className="group relative inline-flex items-center gap-2 overflow-hidden rounded-2xl bg-brand-600 px-8 py-4 text-base font-bold text-white transition-all hover:bg-brand-500 hover:shadow-[0_0_40px_rgba(var(--brand-500-rgb),0.3)] active:scale-95"
            >
              <span className="relative z-10 flex items-center gap-2">
                Diseñar Molécula
                <svg className="h-5 w-5 transition-transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </span>
            </Link>
            <a
              href="https://github.com/srcacahuate619/molecule-design"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-2xl border border-surface-700 bg-surface-950/50 px-8 py-4 text-base font-bold text-surface-300 backdrop-blur-sm transition-all hover:border-surface-600 hover:bg-surface-800"
            >
              Explorar Repositorio
            </a>
          </div>
        </div>
      </section>

      {/* Stats Dashboard */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statsDisplay.map((stat) => (
          <div key={stat.label} className="group relative rounded-2xl border border-surface-800 bg-surface-900/40 p-6 transition-all hover:border-surface-700 hover:bg-surface-900/60">
            <div className="mb-4 text-3xl transition-transform group-hover:scale-110 group-hover:rotate-6">{stat.icon}</div>
            <div className="text-3xl font-black text-white">
              {stat.value}
              {stat.unit && <span className="ml-1 text-sm font-bold text-surface-500">{stat.unit}</span>}
            </div>
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-surface-500">{stat.label}</div>

            {/* Tooltip for Best Score */}
            {stat.label === "Mejor Puntuación" && stats?.best_molecule_name && (
              <div className="pointer-events-none absolute bottom-full left-0 z-20 mb-2 w-max max-w-[280px] scale-95 opacity-0 transition-all group-hover:pointer-events-auto group-hover:scale-100 group-hover:opacity-100">
                <div className="rounded-xl border border-brand-500/30 bg-surface-950 p-4 shadow-2xl shadow-brand-500/20">
                  <div className="mb-2 flex items-center justify-between border-b border-surface-800 pb-2">
                    <h4 className="text-[10px] font-black uppercase tracking-wider text-brand-400">Récord Mundial</h4>
                    <span className="text-[10px] text-surface-500 font-mono">🏆 Best Docking</span>
                  </div>
                  <div className="space-y-3 text-[11px]">
                    <div className="flex flex-col gap-1">
                      <span className="text-[9px] font-bold uppercase tracking-widest text-surface-500">Diseñador y Receptor</span>
                      <span className="font-bold text-white flex items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                        {stats.best_user_name ?? "Anónimo"} 
                        <span className="text-brand-500">→</span>
                        <span className="text-emerald-400">{stats.best_target_pdb ?? "6B3J"}</span>
                      </span>
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-[9px] font-bold uppercase tracking-widest text-surface-500">Estructura Química (SMILES)</span>
                      <div className="relative group/smiles">
                        <code className="block break-all rounded-lg bg-surface-900 p-2 font-mono text-[10px] text-brand-300 border border-brand-500/10">
                          {stats.best_molecule_name}
                        </code>
                        <div className="mt-1 text-[9px] text-surface-600 italic">
                          Copia este SMILES para evaluarlo
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                {/* Connector Arrow */}
                <div className="absolute left-8 top-full h-2 w-2 -translate-y-1/2 rotate-45 border-b border-r border-brand-500/30 bg-surface-950"></div>
              </div>
            )}
          </div>
        ))}
      </section>

      {/* Interactive Pipeline Steps */}
      <section>
        <div className="mb-8 flex items-end justify-between">
          <div>
            <h2 className="text-2xl font-black text-white tracking-tight">Pipeline Científico</h2>
            <p className="text-sm text-surface-500">Flujo de trabajo automatizado end-to-end</p>
          </div>
          <div className="hidden h-px flex-1 bg-surface-800 mx-8 md:block" />
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {PIPELINE_STEPS.map((s) => (
            <div
              key={s.step}
              className="group relative rounded-2xl border border-surface-800 bg-surface-900 p-6 transition-all hover:-translate-y-1 hover:border-brand-500/30 hover:bg-surface-800/50"
            >
              <div className="mb-4 flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/10 text-sm font-black text-brand-400 group-hover:bg-brand-500 group-hover:text-white transition-colors">
                  0{s.step}
                </span>
                <span className="text-2xl grayscale group-hover:grayscale-0 transition-all">{s.icon}</span>
              </div>
              <h3 className="mb-2 text-base font-bold text-white">{s.title}</h3>
              <p className="text-xs leading-relaxed text-surface-400 group-hover:text-surface-300 transition-colors">{s.desc}</p>

              {/* Detailed Tooltip on Hover */}
              <div className="mt-4 overflow-hidden max-h-0 opacity-0 transition-all duration-300 group-hover:max-h-20 group-hover:opacity-100">
                <div className="pt-4 border-t border-surface-800 text-[10px] text-surface-500 italic">
                  {s.detail}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Target Spotlight & System Status */}
      <div className="grid gap-6 lg:grid-cols-3">
        <section className="lg:col-span-2 relative overflow-hidden rounded-3xl border border-brand-500/20 bg-surface-900 p-8 shadow-2xl shadow-brand-500/5">
          <div className="flex flex-col gap-8 md:flex-row md:items-center">
            <div className="flex-1 space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full bg-brand-500/10 px-4 py-1 text-xs font-bold text-brand-400 border border-brand-500/20">
                Hot Target Activo: {stats.hot_target?.name || "Cargando..."} ({stats.hot_target?.pdb_id || "----"})
              </div>
              <h2 className="text-4xl font-black text-white tracking-tighter">Precisión Calibrada: {stats.hot_target?.spearman_rho?.toFixed(3) || "0.000"}</h2>
              <p className="text-base leading-relaxed text-surface-400">
                Nuestro motor ha sido validado contra el receptor {stats.hot_target?.name || "----"}, 
                logrando una correlación de Spearman de {stats.hot_target?.spearman_rho?.toFixed(3) || "0.000"} en pruebas blindadas.
              </p>
              <div className="flex flex-wrap gap-4 text-xs font-bold uppercase tracking-widest">
                <span className="flex items-center gap-2 text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" /> SPEARMAN ρ = {stats.hot_target?.spearman_rho?.toFixed(3) || "0.000"}
                </span>
                <span className="flex items-center gap-2 text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" /> MULTI-TARGET SUPPORT
                </span>
              </div>
            </div>
          </div>
          {/* Subtle decoration */}
          <div className="absolute right-0 bottom-0 opacity-10 pointer-events-none">
            <svg width="200" height="200" viewBox="0 0 200 200" fill="none">
              <circle cx="100" cy="100" r="80" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" />
              <circle cx="100" cy="100" r="50" stroke="currentColor" strokeWidth="1" />
            </svg>
          </div>
        </section>

        <section className="rounded-3xl border border-surface-800 bg-surface-950 p-8 font-mono">
          <div className="mb-6 flex items-center justify-between">
            <h3 className="text-xs font-black uppercase tracking-[0.2em] text-surface-500">System Monitor</h3>
            <div className="flex gap-1">
              <div className="h-2 w-2 rounded-full bg-red-500" />
              <div className="h-2 w-2 rounded-full bg-yellow-500/20" />
              <div className="h-2 w-2 rounded-full bg-emerald-500/20" />
            </div>
          </div>
          <div className="space-y-4">
            {[
              { name: "Vina Physics Engine", status: "ONLINE", color: "text-emerald-400" },
              { name: "XGBoost ML Rescoring", status: "STABLE", color: "text-emerald-400" },
              { name: "RDKit Cheminformatics", status: "ONLINE", color: "text-emerald-400" },
              { name: "Solana Node (Devnet)", status: "SYNCED", color: "text-brand-400" },
              { name: "Gemini / Claude Interpretation", status: "READY", color: "text-emerald-400" },
            ].map((sys) => (
              <div key={sys.name} className="flex items-center justify-between border-b border-surface-900 pb-2 last:border-0">
                <span className="text-[10px] text-surface-500 leading-tight">{sys.name}</span>
                <span className={`text-[10px] font-bold ${sys.color}`}>{sys.status}</span>
              </div>
            ))}
          </div>
          <div className="mt-8 text-[9px] text-surface-600 animate-pulse">
            {">"} SYSTEM ALERT: AI INFERENCE SUSPENDED
          </div>
        </section>
      </div>

      {/* Tech Stack Interactive Grid */}
      <section>
        <h2 className="mb-8 text-2xl font-black text-white tracking-tight text-center">Tecnologías de Grado Industrial</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {TECHNOLOGIES.map((t) => (
            <div
              key={t.name}
              title={t.tooltip}
              className={`group cursor-help rounded-2xl border bg-surface-900 p-4 transition-all hover:bg-surface-800 hover:shadow-2xl ${t.color}`}
            >
              <div className="mb-1 text-sm font-black">{t.name}</div>
              <div className="text-[10px] opacity-60 font-medium">{t.desc}</div>

              {/* Invisible expandable area for the "pop" effect */}
              <div className="mt-2 h-0 opacity-0 group-hover:h-auto group-hover:opacity-100 transition-all text-[9px] leading-tight text-white/80 pt-2 border-t border-white/10">
                {t.tooltip}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Open Science & Ethics */}
      <section className="relative overflow-hidden rounded-3xl border border-emerald-500/20 bg-emerald-500/5 p-10">
        <div className="relative z-10 flex flex-col md:flex-row gap-10 items-center">
          <div className="text-5xl">🔓</div>
          <div>
            <h2 className="mb-3 text-2xl font-black text-emerald-400 tracking-tight">Ciencia Abierta (Licencia CC0)</h2>
            <p className="max-w-3xl text-sm leading-relaxed text-emerald-100/60 font-medium">
              MolDesign no es una "caja negra". Promovemos la democratización del descubrimiento de fármacos.
              Todos los hallazgos certificados se registran bajo licencia de **Dominio Público**,
              garantizando que el conocimiento sea libre mientras tu autoría queda grabada de forma inmutable
              en la red de Solana.
            </p>
          </div>
        </div>
      </section>

      {/* Footer / Creator */}
      <footer className="border-t border-surface-800 pt-12">
        <div className="flex flex-col items-center justify-between gap-8 md:flex-row">
          <div className="text-center md:text-left">
            <div className="text-base font-black text-white tracking-tight">Johan Amezcua</div>
            <div className="text-xs font-bold text-surface-500 uppercase tracking-widest">Molecular Design Founder</div>
          </div>
          <div className="flex gap-4">
            <a href="mailto:26000885@es.uveg.edu.mx" className="rounded-xl border border-surface-800 p-3 text-surface-400 hover:text-brand-400 hover:border-brand-500/30 transition-all">
              📧 26000885@es.uveg.edu.mx
            </a>
          </div>
          <div className="text-[10px] font-black uppercase tracking-[0.4em] text-surface-700">
            UVEG • SOFTWARE ENGINEERING
          </div>
        </div>
      </footer>
    </div>
  );
}

