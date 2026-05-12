"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getGlobalStats } from "@/lib/api";
import { GlobalStats } from "@/lib/types";

const PIPELINE_STEPS = [
  { step: 1, icon: "🧪", title: "Validación química", desc: "RDKit valida estructura SMILES, fórmula molecular y restricciones estricta." },
  { step: 2, icon: "📊", title: "Propiedades fisicoquímicas", desc: "MW, LogP, TPSA, HBD, HBA, QED — todo calculado con RDKit." },
  { step: 3, icon: "🔬", title: "Conformer 3D", desc: "Generación de estructura tridimensional con ETKDG." },
  { step: 4, icon: "🎯", title: "Docking molecular", desc: "AutoDock Vina contra target real (7E2Y) + DiffDock (deep learning)." },
  { step: 5, icon: "📈", title: "Score compuesto", desc: "Afinidad (45%) + ADME (30%) + Drug-likeness (25%) con umbral LE industrial." },
  { step: 6, icon: "🤖", title: "Interpretación IA", desc: "Claude y Gemini interpretan resultados sin inventar ni modificar cifras." },
  { step: 7, icon: "🔗", title: "Certificación Blockchain", desc: "Registro inmutable en Solana devnet para el reconocimiento permanente del creador in silico." },
];

const TECHNOLOGIES = [
  { name: "RDKit", desc: "Validación y propiedades", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" },
  { name: "AutoDock Vina", desc: "Docking clásico", color: "bg-blue-500/10 text-blue-400 border-blue-500/30" },
  { name: "Solana", desc: "Certificación inmutable", color: "bg-purple-500/10 text-purple-400 border-purple-500/30" },
  { name: "Claude / Gemini", desc: "Interpretación científica", color: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30" },
  { name: "3Dmol.js", desc: "Visualización 3D", color: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30" },
  { name: "Ketcher", desc: "Editor molecular", color: "bg-rose-500/10 text-rose-400 border-rose-500/30" },
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
    { label: "Mejor Afinidad", value: stats?.best_affinity?.toFixed(1) ?? "...", unit: "kcal/mol", icon: "🏆" },
    { label: "Comunidad", value: stats?.community_status ?? "Global", icon: "🌍" },
  ];

  return (
    <div className="space-y-12">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-2xl border border-surface-800 bg-gradient-to-br from-surface-900 via-surface-900 to-brand-900/20 p-8 md:p-12">
        <div className="relative z-10">
          <div className="mb-2 inline-block rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs font-semibold text-brand-400">
            Pipeline Científico Real
          </div>
          <h1 className="mb-4 text-4xl font-bold tracking-tight text-white md:text-5xl">
            Mol<span className="text-brand-400">Design</span> AI
          </h1>
          <p className="mb-8 max-w-2xl text-lg leading-relaxed text-surface-400">
            Diseño molecular con rigor industrial. Pipeline científico basado en
            Ligand Efficiency y Docking de precisión, con reconocimiento permanente al 
            creador in silico mediante Blockchain.
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
              Ver guardadas
            </Link>
          </div>
        </div>
        <div className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-brand-500/5 blur-3xl" />
      </section>

      {/* Stats Section */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statsDisplay.map((stat) => (
          <div key={stat.label} className="rounded-xl border border-surface-800 bg-surface-900/50 p-4 text-center">
            <div className="mb-1 text-2xl">{stat.icon}</div>
            <div className="text-2xl font-bold text-white">
              {stat.value}
              {stat.unit && <span className="ml-1 text-xs font-medium text-surface-500">{stat.unit}</span>}
            </div>
            <div className="text-xs font-medium text-surface-400 uppercase tracking-wider">{stat.label}</div>
          </div>
        ))}
      </section>

      {/* Target Spotlight */}
      <section className="relative overflow-hidden rounded-2xl border border-brand-500/20 bg-surface-900 p-8">
        <div className="flex flex-col gap-6 md:flex-row md:items-center">
          <div className="flex-1 space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-400">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75"></span>
                <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500"></span>
              </span>
              Target Activo
            </div>
            <h2 className="text-3xl font-bold text-white">Receptor 5-HT1A <span className="text-surface-500 font-mono text-xl">(7E2Y)</span></h2>
            <p className="text-surface-400 leading-relaxed">
              Actualmente centramos nuestra potencia de cálculo en el receptor de serotonina 1A, 
              crucial para el tratamiento de la ansiedad, depresión y enfermedades neurodegenerativas. 
            </p>
            <div className="flex items-center gap-4 text-sm font-medium text-brand-400">
              <span>✓ Estructura Cryo-EM</span>
              <span>✓ Resolución 3.0 Å</span>
              <span className="text-surface-500">• Próximamente: Multi-target a demanda</span>
            </div>
          </div>
          <div className="flex-shrink-0 rounded-xl bg-surface-800/50 p-4 border border-surface-700">
             <div className="text-xs text-surface-500 mb-2 uppercase font-bold tracking-widest">Estado del Motor</div>
             <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm text-surface-300">
                   <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> 
                   Vina 1.2.5: Online
                </div>
                <div className="flex items-center gap-2 text-sm text-surface-300">
                   <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> 
                   RDKit Engine: Online
                </div>
                <div className="flex items-center gap-2 text-sm text-surface-300 opacity-50">
                   <div className="h-1.5 w-1.5 rounded-full bg-surface-600" /> 
                   Custom PDB Upload: Pending
                </div>
             </div>
          </div>
        </div>
      </section>

      {/* Pipeline Steps */}
      <section>
        <h2 className="mb-6 text-2xl font-bold text-white">Pipeline científico</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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

      {/* Open Science & Technologies */}
      <div className="grid gap-8 lg:grid-cols-3">
        <section className="lg:col-span-2">
          <h2 className="mb-6 text-2xl font-bold text-white">Tecnologías</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {TECHNOLOGIES.map((t) => (
              <div
                key={t.name}
                className={`rounded-lg border px-4 py-3 ${t.color}`}
              >
                <div className="text-sm font-bold">{t.name}</div>
                <div className="text-xs opacity-70">{t.desc}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-6">
          <div className="mb-4 text-2xl">🔓</div>
          <h2 className="mb-2 text-xl font-bold text-emerald-400">Ciencia Abierta (CC0)</h2>
          <p className="text-sm leading-relaxed text-emerald-100/60">
            MolDesign promueve la democratización del descubrimiento de fármacos. 
            Todos los hallazgos certificados se registran bajo licencia de Dominio Público, 
            garantizando que el conocimiento sea libre mientras tu autoría queda 
            grabada para siempre en la blockchain.
          </p>
        </section>
      </div>

      {/* Scientific Principles */}
      <section className="rounded-2xl border border-surface-800 bg-surface-900 p-6">
        <h2 className="mb-4 text-lg font-bold text-white">Principios científicos</h2>
        <ul className="grid gap-3 text-sm leading-relaxed text-surface-400 md:grid-cols-2">
          <li className="flex items-start gap-2">
            <span className="mt-0.5 text-emerald-400">✓</span>
            Valores de módulos científicos explícitos (RDKit, Vina)
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 text-emerald-400">✓</span>
            Interpretación IA basada en datos, sin invención
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 text-emerald-400">✓</span>
            Trazabilidad completa para reproducibilidad
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 text-emerald-400">✓</span>
            Certificación en Solana para reconocimiento de autor
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 text-emerald-400">✓</span>
            Umbral LE de -0.30 kcal/mol/at para eliminación de ruido
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 text-emerald-400">✓</span>
            Heurística de priorización, no verdad biológica absoluta
          </li>
        </ul>
      </section>

      {/* Creator Info Footer */}
      <footer className="border-t border-surface-800 pt-8 pb-12">
        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <div className="text-center md:text-left">
            <div className="text-sm font-semibold text-white">Johan Amezcua</div>
            <div className="text-xs text-surface-500">Fundador y desarrollador de MolDesign</div>
          </div>
          <div className="flex items-center gap-2 text-xs text-surface-400">
            <span>📧</span>
            <a href="mailto:26000885@es.uveg.edu.mx" className="hover:text-brand-400 transition-colors">
              26000885@es.uveg.edu.mx
            </a>
          </div>
          <div className="text-[10px] uppercase tracking-widest text-surface-600">
            UVEG • Ingeniería en Software
          </div>
        </div>
      </footer>
    </div>
  );
}
