"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { getGlobalStats } from "../lib/api";
import { GlobalStats } from "../lib/types";
import { useInterface } from "../context/InterfaceContext";

const PIPELINE_STEPS = [
  { step: "01", title: "Validación Química", descPro: "Verificación de valencias, quiralidad y filtros de reactividad sub-segundo vía RDKit.", descEdu: "El primer filtro de nuestra plataforma. Aquí usamos RDKit para asegurar que la molécula dibujada existe según las leyes de la química. Verificamos que los enlaces sean correctos (valencia), determinamos cómo se orientan los átomos en el espacio (quiralidad) y aplicamos filtros de reactividad. Si una estructura es químicamente imposible o inestable, es descartada para no desperdiciar poder de cálculo." },
  { step: "02", title: "Propiedades", descPro: "Cálculo de descriptores físico-químicos: MW, LogP, TPSA, QED y Accesibilidad Sintética.", descEdu: "En este paso, calculamos descriptores clave como el Peso Molecular (MW), solubilidad (LogP) y área superficial polar (TPSA). También evaluamos la 'Accesibilidad Sintética' (qué tan difícil sería fabricar la molécula en la vida real) y el índice QED (cuánto se parece a un fármaco oral), asegurando que el cuerpo humano podría absorberlo." },
  { step: "03", title: "Conformer 3D", descPro: "Generación de geometrías de baja energía mediante algoritmo ETKDG.", descEdu: "Las moléculas no son planas como en los dibujos 2D, son flexibles y tridimensionales. Utilizamos el algoritmo ETKDG para predecir la forma en 3D (conformación) que requiere la menor cantidad de energía. Esto es vital porque el fármaco debe doblarse y adoptar la forma correcta para encajar dentro del receptor de la enfermedad." },
  { step: "04", title: "Docking Físico", descPro: "Simulación de acoplamiento Multi-Target utilizando AutoDock Vina.", descEdu: "¡El acoplamiento! Simulamos cómo la molécula tridimensional se une físicamente al receptor (la proteína). Usando AutoDock Vina, probamos miles de posiciones para encontrar la orientación perfecta, resultando en un puntaje de afinidad termodinámica que nos indica qué tan fuerte es la unión." },
  { step: "05", title: "Rescoring ML (L1)", descPro: "Corrección estadística de afinidad vía XGBoost entrenado con PDBbind.", descEdu: "Los motores físicos tienen sesgos. Para corregirlos, pasamos los resultados por XGBoost, un modelo de Machine Learning entrenado con miles de complejos proteína-ligando reales. Este modelo aprende de los errores históricos y ajusta el puntaje de afinidad, acercándolo con gran precisión a la realidad biológica." },
  { step: "06", title: "Topología GNN (L2)", descPro: "Evaluación interatómica profunda utilizando RTMScore GNN.", descEdu: "La Inteligencia Artificial profunda entra en acción usando Redes Neuronales de Grafos (RTMScore) para evaluar la estructura completa. La red analiza la interacción de cada átomo en 3D, descartando 'falsos positivos': moléculas que tenían buen puntaje, pero que biológicamente chocarían y fracasarían." },
  { step: "07", title: "Refinamiento Físico (L3)", descPro: "Relajación cuántica y alivio estérico mediante OpenMM/AMBER.", descEdu: "Aplicamos relajación termodinámica utilizando el motor OpenMM con campos de fuerza cuánticos. Esto 'agita' suavemente la proteína y el fármaco acoplados para disipar tensión acumulada. Ajusta microscópicamente los enlaces y optimiza los puentes de hidrógeno, garantizando máxima estabilidad." },
  { step: "08", title: "Reporte Científico", descPro: "Generación automática de documentación clínica con hotspots y ADME.", descEdu: "Finalizada la simulación, el sistema recopila todo. Genera un reporte dinámico mostrando el mapeo de interacciones críticas (hotspots) y el perfil ADME (Absorción, Distribución, Metabolismo y Excreción), presentándolo visualmente para el rápido entendimiento del investigador." },
  { step: "09", title: "Registro Solana", descPro: "Certificación inmutable en blockchain mediante hash SHA-256.", descEdu: "Para proteger la ciencia abierta, creamos una firma criptográfica (Hash SHA-256) de tu molécula y la registramos inmutablemente en la red blockchain de Solana. Obtienes un certificado digital permanente demostrando que diseñaste esa molécula en ese instante exacto." },
];

const TECHNOLOGIES = [
  { name: "AutoDock Vina", role: "Physics Engine", desc: "Motor de docking molecular que realiza predicciones termodinámicas de la energía de unión (binding affinity) y encuentra las conformaciones más estables del ligando dentro del receptor." },
  { name: "XGBoost", role: "ML Rescoring", desc: "Algoritmo de Gradient Boosting optimizado. Entrenado con complejos de PDBbind, aplica correcciones estadísticas a los scores físicos para mejorar radicalmente la precisión predictiva." },
  { name: "RTMScore", role: "GNN Topology", desc: "Modelo profundo basado en Redes Neuronales de Grafos. Analiza las interacciones 3D a nivel atómico para inferir patrones ocultos y descartar falsos positivos que engañan a los motores físicos." },
  { name: "OpenMM", role: "MD Refinement", desc: "Motor de dinámica molecular avanzado. Minimiza la energía del complejo proteína-ligando resolviendo choques estéricos y relajando la estructura con campos de fuerza AMBER." },
  { name: "RDKit", role: "Cheminformatics", desc: "El estándar en quimioinformática. Genera conformadores 3D, evalúa valencias, calcula propiedades moleculares clave (LogP, TPSA, QED) y filtra la viabilidad sintética." },
  { name: "Solana", role: "Layer-1 Ledger", desc: "Blockchain descentralizada. Registra inmutablemente los hashes criptográficos de las moléculas descubiertas, creando un certificado criptográfico permanente de la autoría científica." },
];

function ProHome({ stats, error }: { stats: GlobalStats | null, error: boolean }) {
  const [selectedOrchestratorNode, setSelectedOrchestratorNode] = useState<{title: string, engine: string, desc: string} | null>(null);
  const [selectedPipelineStep, setSelectedPipelineStep] = useState<typeof PIPELINE_STEPS[0] | null>(null);
  const [selectedTech, setSelectedTech] = useState<typeof TECHNOLOGIES[0] | null>(null);
  const [selectedPillar, setSelectedPillar] = useState<{tag: string, title: string, desc: string} | null>(null);
  if (!stats && !error) {
    return (
      <div className="flex min-h-[80vh] items-center justify-center font-mono">
        <div className="text-center">
          <div className="mb-4 text-brand-500 text-xs">INITIALIZING SYSTEM...</div>
          <div className="mx-auto h-px w-32 bg-surface-800 overflow-hidden relative">
             <div className="absolute top-0 left-0 h-full bg-brand-500 w-1/3 animate-[score-fill_1s_ease-in-out_infinite]" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="border-x border-surface-800 bg-surface-950 min-h-[80vh]">
      {/* HEADER / HERO AREA */}
      <section className="grid grid-cols-1 lg:grid-cols-2 border-b border-surface-800">
        <div className="p-8 md:p-12 flex flex-col justify-center border-b lg:border-b-0 lg:border-r border-surface-800">
          <div className="mb-6 font-mono text-[10px] text-brand-500 tracking-widest uppercase">
            [ MolDesign AI // Next-Gen Pipeline ]
          </div>
          <h1 className="mb-6 font-display text-4xl md:text-5xl font-bold tracking-tight text-white uppercase">
            Industrial Grade<br />Molecular Discovery
          </h1>
          <p className="mb-10 font-sans text-sm text-surface-400 max-w-md leading-relaxed">
            Plataforma de quimioinformática de alta precisión. Integración de docking físico, machine learning y certificación blockchain para acelerar la investigación farmacológica.
          </p>
          <div className="flex flex-wrap gap-4 font-mono text-xs">
            <Link
              href="/evaluation"
              className="inline-flex items-center justify-center bg-brand-500 text-surface-950 px-6 py-3 font-bold hover:bg-brand-400 transition-colors"
            >
              INICIAR SIMULACIÓN
            </Link>
            <a
              href="https://github.com/srcacahuate619/molecule-design"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center border border-surface-700 px-6 py-3 text-surface-300 hover:text-white hover:border-surface-500 transition-colors"
            >
              EXPLORAR REPOSITORIO
            </a>
          </div>
        </div>

        {/* SIGNATURE ELEMENT & MONITOR */}
        <div className="flex flex-col">
          <div className="flex-1 relative border-b border-surface-800 p-8 flex items-center justify-center overflow-hidden">
            {/* Logo from original design */}
            <div className="relative w-full flex items-center justify-center p-4 lg:p-8">
              <Image
                src="/logo-full.png"
                alt="MolDesign AI Logo"
                width={700}
                height={233}
                className="w-full max-w-[600px] object-contain drop-shadow-[0_0_15px_rgba(var(--brand-500-rgb),0.2)] hover:scale-105 transition-transform duration-500"
                priority
              />
            </div>
            <div className="absolute bottom-4 right-4 font-mono text-[9px] text-surface-500 tracking-widest uppercase">
              Simulación de Interacciones // Activo
            </div>
          </div>
          
          {/* SYSTEM MONITOR */}
          <div className="p-6 font-mono text-xs bg-surface-950">
            <div className="mb-4 flex items-center justify-between text-surface-500 border-b border-surface-800 pb-2">
              <span className="tracking-widest">SYSTEM MONITOR</span>
              <span className="flex gap-1">
                <span className="w-2 h-2 bg-brand-500" />
              </span>
            </div>
            <div className="space-y-2 text-[10px]">
              {[
                { name: "Vina Physics Engine", status: "ONLINE", val: "OK" },
                { name: "XGBoost ML Rescoring", status: "ONLINE", val: "OK" },
                { name: "RTMScore GNN Engine", status: "ONLINE", val: "OK" },
                { name: "Solana Node (Devnet)", status: "SYNCED", val: "OK" }
              ].map((sys) => (
                <div key={sys.name} className="flex justify-between items-center text-surface-400">
                  <span>{sys.name}</span>
                  <div className="flex gap-4">
                    <span>[{sys.val}]</span>
                    <span className={sys.status === "ONLINE" || sys.status === "SYNCED" ? "text-brand-500" : "text-surface-600"}>
                      {sys.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {error && (
        <div className="p-4 bg-red-950/20 border-b border-red-900/50 font-mono text-xs text-red-400">
          [ERROR] No se pudo conectar con el motor de estadísticas. El sistema principal sigue operativo.
        </div>
      )}

      {/* STATS DASHBOARD */}
      <section className="grid grid-cols-2 lg:grid-cols-4 border-b border-surface-800 divide-x divide-y lg:divide-y-0 divide-surface-800">
        {[
          { label: "Moléculas Evaluadas", value: stats?.total_molecules?.toLocaleString() ?? "..." },
          { label: "Certificaciones", value: stats?.total_certifications?.toLocaleString() ?? "..." },
          { label: "Mejor Puntuación", value: stats?.best_score?.toFixed(1) ?? "...", unit: "pts" },
          { label: "Estado Global", value: stats?.community_status ?? "Global" },
        ].map((stat, i) => (
          <div key={i} className="p-6 flex flex-col justify-between group">
            <div className="font-mono text-[9px] text-surface-500 tracking-widest uppercase mb-4">
              {stat.label}
            </div>
            <div className="font-display text-2xl md:text-3xl font-bold text-white flex items-baseline gap-1">
              {stat.value}
              {stat.unit && <span className="font-mono text-[10px] text-surface-500 font-normal">{stat.unit}</span>}
            </div>
            {stat.label === "Mejor Puntuación" && stats?.best_molecule_name && (
              <div className="mt-4 pt-4 border-t border-surface-800 hidden group-hover:block transition-all">
                <div className="font-mono text-[9px] text-brand-500 mb-1">RÉCORD MUNDIAL // {stats.best_target_pdb}</div>
                <div className="font-mono text-[9px] text-surface-400 break-all">{stats.best_molecule_name}</div>
              </div>
            )}
          </div>
        ))}
      </section>

      {/* TARGET SPOTLIGHT */}
      <section className="p-8 md:p-12 border-b border-surface-800 bg-surface-900">
        <div className="max-w-3xl">
          <div className="font-mono text-[10px] text-brand-500 mb-4 tracking-widest">
            [ TARGET ACTIVO: {stats?.hot_target?.pdb_id || "----"} ]
          </div>
          <h2 className="font-display text-xl md:text-2xl font-bold text-white mb-4 uppercase">
            {stats?.hot_target?.spearman_rho && stats.hot_target.spearman_rho > 0 
              ? `Precisión Calibrada (ρ = ${stats.hot_target.spearman_rho.toFixed(3)})` 
              : "Física y Geometría de Alta Precisión"}
          </h2>
          <p className="font-sans text-surface-400 text-sm leading-relaxed mb-6">
            {stats?.hot_target?.spearman_rho && stats.hot_target.spearman_rho > 0 
              ? `Motor validado contra ${stats.hot_target.name}, logrando una correlación de Spearman de ${stats.hot_target.spearman_rho.toFixed(3)} en pruebas blindadas.`
              : `Optimizado para el receptor ${stats?.hot_target?.name || "----"}, mapeando fuerzas químicas y hotspots tridimensionales. Validación blindada en planificación.`}
          </p>
          <div className="font-mono text-[10px] text-surface-500">
            STATUS: <span className="text-brand-500">MULTI-TARGET SUPPORT ENABLED</span>
          </div>
        </div>
      </section>

      {/* SCIENTIFIC ARCHITECTURE PILLARS */}
      <section className="p-8 md:p-12 border-b border-surface-800 bg-surface-950">
        <div className="font-mono text-[10px] text-brand-500 mb-12 tracking-widest uppercase text-center">
          [ Core Architecture // Scientific Foundation ]
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16 gap-y-12 max-w-6xl mx-auto">
          
          <button 
            onClick={() => setSelectedPillar({
              tag: "L1-L4",
              title: "Arquitectura de Rescoring en Cascada",
              desc: "Ningún modelo resuelve todo. Al derivar fragmentos pequeños a Vina, péptidos a DiffPepDock/ColabFold, y centros metálicos a xtb/AutoDock4, hemos creado un 'cerebro' orquestador que entiende las limitaciones físicas de sus propias herramientas."
            })}
            className="space-y-4 text-left p-4 -m-4 rounded hover:bg-surface-900/50 transition-colors cursor-pointer group"
          >
            <div className="flex items-center gap-3 mb-2">
              <span className="text-brand-500 font-mono text-xs border border-brand-500/30 bg-brand-500/10 px-2 py-1 group-hover:bg-brand-500 group-hover:text-surface-950 transition-colors">[L1-L4]</span>
              <h3 className="font-display font-bold text-white text-lg uppercase tracking-wide group-hover:text-brand-400 transition-colors">Arquitectura de Rescoring en Cascada</h3>
            </div>
            <p className="font-sans text-sm text-surface-400 leading-relaxed line-clamp-2 group-hover:line-clamp-none">
              Ningún modelo resuelve todo. Al derivar fragmentos pequeños a Vina, péptidos a DiffPepDock/ColabFold, y centros metálicos a xtb/AutoDock4, hemos creado un "cerebro" orquestador que entiende las limitaciones físicas de sus propias herramientas.
            </p>
          </button>

          <button 
            onClick={() => setSelectedPillar({
              tag: "PHYS",
              title: "Guardrails y Prevención de Alucinación",
              desc: "A diferencia de plataformas genéricas de Deep Learning que inventan afinidades mágicas, MolDesign impone física dura: Potency Floors, castigos por tensión de anillos (Cubano) y filtros de Accesibilidad Sintética (SA Score) para evitar estructuras imposibles."
            })}
            className="space-y-4 text-left p-4 -m-4 rounded hover:bg-surface-900/50 transition-colors cursor-pointer group"
          >
            <div className="flex items-center gap-3 mb-2">
              <span className="text-brand-500 font-mono text-xs border border-brand-500/30 bg-brand-500/10 px-2 py-1 group-hover:bg-brand-500 group-hover:text-surface-950 transition-colors">[PHYS]</span>
              <h3 className="font-display font-bold text-white text-lg uppercase tracking-wide group-hover:text-brand-400 transition-colors">Guardrails y Prevención de "Alucinación"</h3>
            </div>
            <p className="font-sans text-sm text-surface-400 leading-relaxed line-clamp-2 group-hover:line-clamp-none">
              A diferencia de plataformas genéricas de Deep Learning que inventan afinidades mágicas, MolDesign impone física dura: Potency Floors, castigos por tensión de anillos (Cubano) y filtros de Accesibilidad Sintética (SA Score).
            </p>
          </button>

          <button 
            onClick={() => setSelectedPillar({
              tag: "S-LE",
              title: "Eficiencia Dinámica de Ligando (Size-Adaptive LE)",
              desc: "Muchos competidores fallan al sobredimensionar moléculas gigantes (efecto bola de nieve de Vina). Nuestro umbral dinámico que interpola penalizaciones energéticas entre fragmentos y macromoléculas corrige este sesgo sistémico."
            })}
            className="space-y-4 text-left p-4 -m-4 rounded hover:bg-surface-900/50 transition-colors cursor-pointer group"
          >
            <div className="flex items-center gap-3 mb-2">
              <span className="text-brand-500 font-mono text-xs border border-brand-500/30 bg-brand-500/10 px-2 py-1 group-hover:bg-brand-500 group-hover:text-surface-950 transition-colors">[S-LE]</span>
              <h3 className="font-display font-bold text-white text-lg uppercase tracking-wide group-hover:text-brand-400 transition-colors">Eficiencia Dinámica de Ligando (Size-Adaptive LE)</h3>
            </div>
            <p className="font-sans text-sm text-surface-400 leading-relaxed line-clamp-2 group-hover:line-clamp-none">
              Muchos competidores fallan al sobredimensionar moléculas gigantes (efecto bola de nieve de Vina). Nuestro umbral dinámico que interpola entre fragmentos y macromoléculas corrige este sesgo sistémico (avance de nivel doctoral).
            </p>
          </button>

          <button 
            onClick={() => setSelectedPillar({
              tag: "MDIM",
              title: "Validación Multidimensional",
              desc: "Al cruzar el score puramente termodinámico (Vina) con un mapa geométrico tridimensional (RTMScore) y perfiles de contactos químicos (ProLIF), el sistema no se deja engañar por moléculas que 'caben' físicamente pero no interactúan químicamente de la forma correcta."
            })}
            className="space-y-4 text-left p-4 -m-4 rounded hover:bg-surface-900/50 transition-colors cursor-pointer group"
          >
            <div className="flex items-center gap-3 mb-2">
              <span className="text-brand-500 font-mono text-xs border border-brand-500/30 bg-brand-500/10 px-2 py-1 group-hover:bg-brand-500 group-hover:text-surface-950 transition-colors">[MDIM]</span>
              <h3 className="font-display font-bold text-white text-lg uppercase tracking-wide group-hover:text-brand-400 transition-colors">Validación Multidimensional</h3>
            </div>
            <p className="font-sans text-sm text-surface-400 leading-relaxed line-clamp-2 group-hover:line-clamp-none">
              Al cruzar el score puramente termodinámico (Vina) con un mapa geométrico tridimensional (RTMScore) y contactos químicos (ProLIF), el sistema no se deja engañar por moléculas que "caben" pero no interactúan químicamente de la forma correcta.
            </p>
          </button>

        </div>
      </section>

      {/* PIPELINE & TECH STACK */}
      <section className="grid grid-cols-1 lg:grid-cols-3">
        <div className="lg:col-span-2 border-b lg:border-b-0 lg:border-r border-surface-800 p-8 md:p-12">
          <div className="font-mono text-[10px] text-surface-500 tracking-widest uppercase mb-8">
            Flujo de Ejecución (Pipeline)
          </div>
          <div className="space-y-6">
            {PIPELINE_STEPS.map((s) => (
              <button 
                key={s.step} 
                onClick={() => setSelectedPipelineStep(s)}
                className="flex gap-4 group text-left cursor-pointer hover:bg-surface-900 p-2 rounded transition-colors -ml-2 w-full"
              >
                <div className="font-mono text-sm text-surface-600 group-hover:text-brand-500 transition-colors mt-0.5">
                  {s.step}
                </div>
                <div>
                  <h3 className="font-display font-bold text-white text-sm uppercase mb-1 group-hover:text-brand-400 transition-colors">{s.title}</h3>
                  <p className="font-sans text-xs text-surface-400 leading-relaxed max-w-md line-clamp-2 group-hover:line-clamp-none">{s.descPro}</p>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="p-8 md:p-12 flex flex-col">
          <div className="font-mono text-[10px] text-surface-500 tracking-widest uppercase mb-8">
            Stack Tecnológico
          </div>
          <div className="flex-1">
            <ul className="space-y-2 font-mono text-xs">
              {TECHNOLOGIES.map((t, i) => (
                <li key={i}>
                  <button 
                    onClick={() => setSelectedTech(t)}
                    className="w-full flex justify-between items-baseline border-b border-surface-800 pb-2 p-2 -ml-2 rounded hover:bg-surface-900 transition-colors text-left group cursor-pointer"
                  >
                    <span className="text-white group-hover:text-brand-400 transition-colors">{t.name}</span>
                    <span className="text-surface-500 text-[10px] bg-surface-800 px-2 py-0.5 rounded group-hover:bg-brand-500/20 group-hover:text-brand-400 transition-colors">{t.role}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <div className="mt-12 pt-8 border-t border-surface-800">
            <h3 className="font-display font-bold text-white text-sm uppercase mb-2">Ciencia Abierta</h3>
            <p className="font-sans text-xs text-surface-400 leading-relaxed">
              Registros bajo licencia CC0 (Dominio Público). La autoría queda certificada inmutablemente en Solana.
            </p>
          </div>
        </div>
      </section>

      {/* ORCHESTRATOR FLOWCHART */}
      <section className="p-8 md:p-12 border-b border-surface-800 bg-surface-950">
        <div className="max-w-6xl mx-auto">
          <div className="font-mono text-[10px] text-brand-500 mb-10 tracking-widest uppercase text-center">
            [ Decision Engine // Orchestrator Flow ]
          </div>
          
          <div className="flex flex-col items-center font-mono text-xs max-w-4xl mx-auto">
            
            {/* Input Node */}
            <div className="w-full max-w-sm px-6 py-4 border border-surface-600 bg-surface-900 text-white text-center rounded mb-4">
              <div className="font-bold text-sm mb-1">INPUT</div>
              <div className="text-surface-400 text-[10px]">Estructura Molecular (SMILES/SDF)</div>
            </div>
            
            <div className="text-surface-600 mb-4">↓</div>
            
            {/* Validation Node */}
            <div className="w-full max-w-sm px-6 py-4 border border-brand-500 bg-brand-500/10 text-brand-400 font-bold text-center rounded mb-4 relative">
              1. Validación Química (RDKit)
              <div className="absolute top-[90%] right-[-100px] flex flex-col items-center">
                <svg width="24" height="24" className="text-surface-600 mb-1 ml-[-20px]" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                   <path d="M4 4 L20 20" />
                   <path d="M10 20 L20 20 L20 10" />
                </svg>
                <div className="px-2 py-1 border border-red-500 text-red-500 text-[9px] rounded">RECHAZO (Falla SA Score / QED)</div>
              </div>
            </div>

            <div className="text-surface-600 mb-4">↓</div>

            {/* Orchestrator Node */}
            <div className="w-full px-8 py-5 border-2 border-purple-500 bg-purple-500/10 text-white font-bold tracking-widest rounded-lg text-center mb-8">
              🧠 CEREBRO ORQUESTADOR
              <div className="text-[10px] text-purple-400 mt-2 font-normal uppercase">Enrutamiento según propiedades fisicoquímicas</div>
            </div>

            {/* Branches Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 w-full mb-8">
              
              {/* Branch 1 */}
              <button 
                onClick={() => setSelectedOrchestratorNode({
                  title: "Fragmentos",
                  engine: "AutoDock Vina",
                  desc: "Para moléculas muy pequeñas (Peso Molecular < 250), el sistema prioriza AutoDock Vina, permitiendo una búsqueda exhaustiva de alta resolución geométrica. Dado su pequeño tamaño, la simulación física pura es sumamente precisa."
                })}
                className="flex flex-col p-5 border border-surface-700 bg-surface-900 rounded hover:border-brand-500/50 hover:bg-surface-800 transition-all cursor-pointer text-left group"
              >
                <div className="text-[10px] text-surface-500 mb-3 font-bold uppercase tracking-widest border-b border-surface-800 pb-2 text-center w-full group-hover:text-brand-500 transition-colors">Fragmentos</div>
                <div className="text-white text-xs mb-3 text-center w-full">MW &lt; 250</div>
                <div className="text-brand-500 font-bold mb-2 text-center w-full">AutoDock Vina</div>
                <div className="text-[10px] text-surface-400 text-center leading-relaxed w-full line-clamp-2 group-hover:line-clamp-none">Búsqueda exhaustiva de alta resolución geométrica</div>
              </button>

              {/* Branch 2 */}
              <button 
                onClick={() => setSelectedOrchestratorNode({
                  title: "Drug-Like",
                  engine: "Vina + XGBoost L1",
                  desc: "Para moléculas medianas tipo fármaco (MW 250 - 800), el sistema acopla termodinámicamente con Vina, pero aplica un modelo estadístico XGBoost L1 para corregir las deficiencias del motor físico utilizando datos del PDBbind."
                })}
                className="flex flex-col p-5 border border-surface-700 bg-surface-900 rounded hover:border-brand-500/50 hover:bg-surface-800 transition-all cursor-pointer text-left group"
              >
                <div className="text-[10px] text-surface-500 mb-3 font-bold uppercase tracking-widest border-b border-surface-800 pb-2 text-center w-full group-hover:text-brand-500 transition-colors">Drug-Like</div>
                <div className="text-white text-xs mb-3 text-center w-full">MW 250 - 800</div>
                <div className="text-brand-500 font-bold mb-2 text-center w-full">Vina + XGBoost L1</div>
                <div className="text-[10px] text-surface-400 text-center leading-relaxed w-full line-clamp-2 group-hover:line-clamp-none">Corrección estadística de funciones de scoring termodinámicas</div>
              </button>

              {/* Branch 3 */}
              <button 
                onClick={() => setSelectedOrchestratorNode({
                  title: "Péptidos / Macros",
                  engine: "ColabFold / DiffPep",
                  desc: "Para cadenas de aminoácidos grandes o macromoléculas, los motores de docking tradicionales fallan. El orquestador las desvía hacia modelos híbridos de deep learning estructural para predecir acoplamientos complejos de novo."
                })}
                className="flex flex-col p-5 border border-surface-700 bg-surface-900 rounded hover:border-brand-500/50 hover:bg-surface-800 transition-all cursor-pointer text-left group"
              >
                <div className="text-[10px] text-surface-500 mb-3 font-bold uppercase tracking-widest border-b border-surface-800 pb-2 text-center w-full group-hover:text-brand-500 transition-colors">Péptidos / Macros</div>
                <div className="text-white text-xs mb-3 text-center w-full">Cadenas AA grandes</div>
                <div className="text-brand-500 font-bold mb-2 text-center w-full">ColabFold / DiffPep</div>
                <div className="text-[10px] text-surface-400 text-center leading-relaxed w-full line-clamp-2 group-hover:line-clamp-none">Predicción de estructuras híbridas de novo y acoplamiento</div>
              </button>

              {/* Branch 4 */}
              <button 
                onClick={() => setSelectedOrchestratorNode({
                  title: "Metales",
                  engine: "xtb / AutoDock4",
                  desc: "Las metaloproteínas requieren mecánica cuántica. El sistema detecta centros metálicos y parametriza los estados electrónicos usando xTB, resolviendo choques estéricos y geometrías de coordinación que Vina no soporta."
                })}
                className="flex flex-col p-5 border border-surface-700 bg-surface-900 rounded hover:border-brand-500/50 hover:bg-surface-800 transition-all cursor-pointer text-left group"
              >
                <div className="text-[10px] text-surface-500 mb-3 font-bold uppercase tracking-widest border-b border-surface-800 pb-2 text-center w-full group-hover:text-brand-500 transition-colors">Metales</div>
                <div className="text-white text-xs mb-3 text-center w-full">Centros Metálicos</div>
                <div className="text-brand-500 font-bold mb-2 text-center w-full">xtb / AutoDock4</div>
                <div className="text-[10px] text-surface-400 text-center leading-relaxed w-full line-clamp-2 group-hover:line-clamp-none">Parametrización cuántica y alivio estérico localizado</div>
              </button>

            </div>

            <div className="text-surface-600 mb-4 text-center text-[10px] uppercase tracking-widest">↓ Convergencia ↓</div>

            {/* Validation Node */}
            <div className="w-full px-8 py-4 border border-blue-500 bg-blue-500/10 text-blue-400 font-bold text-center rounded mb-4">
              2. Validación Multidimensional L2-L3
              <div className="text-[10px] font-normal text-blue-300/80 mt-2">
                RTMScore GNN (Topología) + ProLIF (Contactos 3D) + OpenMM
              </div>
            </div>

            <div className="text-surface-600 mb-4">↓</div>

            {/* Output Node */}
            <div className="w-full max-w-sm px-6 py-4 border border-emerald-500 bg-emerald-500/10 text-emerald-400 text-center rounded font-bold">
              💎 Solana Blockchain Certification
            </div>

          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="p-8 md:p-12 border-t border-surface-800 flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="font-display font-bold text-white uppercase tracking-wider text-sm">
          MolDesign AI <span className="text-surface-600 font-mono text-[10px] ml-2">v6.5</span>
        </div>
        <div className="font-mono text-[10px] text-surface-500 text-center md:text-right leading-relaxed">
          <span className="block text-white mb-1">Johan Amezcua</span>
          26000885@es.uveg.edu.mx<br />
          UVEG Software Engineering
        </div>
      </footer>

      {/* Modal Interactivo del Orquestador */}
      {selectedOrchestratorNode && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in"
          onClick={() => setSelectedOrchestratorNode(null)}
        >
          <div 
            className="bg-surface-900 border border-brand-500/50 rounded-lg p-8 max-w-lg w-full shadow-2xl relative animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setSelectedOrchestratorNode(null)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white transition-colors text-xl font-bold"
            >
              ✕
            </button>
            
            <div className="font-mono text-[10px] text-surface-500 tracking-widest uppercase border-b border-surface-800 pb-2 mb-6">
              Ruta de Ejecución // {selectedOrchestratorNode.title}
            </div>

            <div className="mb-6">
              <span className="inline-block px-3 py-1 bg-brand-500/10 border border-brand-500/50 text-brand-400 text-xs font-bold font-mono rounded mb-4">
                ENGINE: {selectedOrchestratorNode.engine}
              </span>
              <p className="text-base text-surface-300 font-sans leading-relaxed">
                {selectedOrchestratorNode.desc}
              </p>
            </div>

            <div className="flex justify-end pt-4 border-t border-surface-800">
              <button 
                onClick={() => setSelectedOrchestratorNode(null)}
                className="px-6 py-2 bg-brand-500 text-surface-950 hover:bg-brand-400 font-mono font-bold text-sm transition-colors"
              >
                CERRAR
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Interactivo del Pipeline Pro */}
      {selectedPipelineStep && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in"
          onClick={() => setSelectedPipelineStep(null)}
        >
          <div 
            className="bg-surface-900 border border-brand-500/50 rounded-lg p-8 max-w-md w-full shadow-2xl relative animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setSelectedPipelineStep(null)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white transition-colors text-xl font-bold"
            >
              ✕
            </button>
            
            <div className="font-mono text-[10px] text-brand-500 tracking-widest uppercase border-b border-surface-800 pb-2 mb-6">
              Pipeline // Step {selectedPipelineStep.step}
            </div>

            <div className="mb-6">
              <h3 className="text-xl font-display font-bold text-white uppercase mb-4">
                {selectedPipelineStep.title}
              </h3>
              <p className="text-base text-surface-300 font-sans leading-relaxed">
                {selectedPipelineStep.descPro}
              </p>
            </div>

            <div className="flex justify-end pt-4 border-t border-surface-800">
              <button 
                onClick={() => setSelectedPipelineStep(null)}
                className="px-6 py-2 border border-surface-700 text-surface-400 hover:text-white hover:bg-surface-800 font-mono text-sm transition-colors rounded"
              >
                CERRAR
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Interactivo: Tech Stack */}
      {selectedTech && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in"
          onClick={() => setSelectedTech(null)}
        >
          <div 
            className="bg-surface-900 border border-brand-500/50 rounded-lg p-8 max-w-md w-full shadow-2xl relative animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setSelectedTech(null)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white transition-colors text-xl font-bold"
            >
              ✕
            </button>
            
            <div className="font-mono text-[10px] text-brand-500 tracking-widest uppercase border-b border-surface-800 pb-2 mb-6">
              Stack Tecnológico // Component
            </div>

            <div className="mb-6">
              <h3 className="text-2xl font-display font-bold text-white mb-2">
                {selectedTech.name}
              </h3>
              <span className="inline-block px-2 py-1 bg-surface-800 text-brand-400 text-[10px] font-mono rounded mb-4">
                ROLE: {selectedTech.role}
              </span>
              <p className="text-base text-surface-300 font-sans leading-relaxed">
                {selectedTech.desc}
              </p>
            </div>

            <div className="flex justify-end pt-4 border-t border-surface-800">
              <button 
                onClick={() => setSelectedTech(null)}
                className="px-6 py-2 border border-surface-700 text-surface-400 hover:text-white hover:bg-surface-800 font-mono text-sm transition-colors rounded"
              >
                CERRAR
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Interactivo: Arquitectura Científica */}
      {selectedPillar && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in"
          onClick={() => setSelectedPillar(null)}
        >
          <div 
            className="bg-surface-900 border border-brand-500/50 rounded-lg p-8 max-w-lg w-full shadow-2xl relative animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setSelectedPillar(null)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white transition-colors text-xl font-bold"
            >
              ✕
            </button>
            
            <div className="font-mono text-[10px] text-brand-500 tracking-widest uppercase border-b border-surface-800 pb-2 mb-6">
              Scientific Architecture // Pillar
            </div>

            <div className="mb-6">
              <div className="flex items-center gap-3 mb-4">
                <span className="text-brand-500 font-mono text-xs border border-brand-500/30 bg-brand-500/10 px-2 py-1">[{selectedPillar.tag}]</span>
                <h3 className="text-xl font-display font-bold text-white uppercase">
                  {selectedPillar.title}
                </h3>
              </div>
              <p className="text-base text-surface-300 font-sans leading-relaxed">
                {selectedPillar.desc}
              </p>
            </div>

            <div className="flex justify-end pt-4 border-t border-surface-800">
              <button 
                onClick={() => setSelectedPillar(null)}
                className="px-6 py-2 border border-surface-700 text-surface-400 hover:text-white hover:bg-surface-800 font-mono text-sm transition-colors rounded"
              >
                CERRAR
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

function AcademyHome({ stats, error }: { stats: GlobalStats | null, error: boolean }) {
  const [selectedPipelineStep, setSelectedPipelineStep] = useState<typeof PIPELINE_STEPS[0] | null>(null);
  if (!stats && !error) {
    return (
      <div className="flex min-h-[80vh] items-center justify-center font-mono bg-surface-950">
        <div className="text-center">
          <div className="mb-4 text-indigo-400 text-xl font-bold animate-pulse">CARGANDO DATOS DEL CAMPUS...</div>
          <div className="mx-auto h-2 w-48 bg-surface-800 border border-indigo-500/30 relative rounded-full overflow-hidden">
             <div className="absolute top-0 left-0 h-full bg-indigo-500 w-1/3 animate-[score-fill_1.5s_ease-in-out_infinite]" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[#0b0f19] min-h-screen text-white font-mono relative overflow-hidden -mt-8 pt-8 rounded-xl border border-indigo-900/30 shadow-2xl">
      {/* Subtle Dot Grid Background (Academic) */}
      <div className="absolute inset-0 pointer-events-none opacity-20" style={{ backgroundImage: 'radial-gradient(#4f46e5 1px, transparent 1px)', backgroundSize: '30px 30px' }}></div>
      
      <div className="relative z-10 max-w-6xl mx-auto px-4 md:px-8 space-y-16 pb-20">
        
        {/* HERO */}
        <section className="flex flex-col lg:flex-row items-center gap-12 mt-10">
          <div className="flex-1 space-y-8">
            <div className="inline-block px-4 py-1 bg-indigo-500/10 border border-indigo-500/50 text-indigo-300 font-bold tracking-widest text-sm rounded-full">
              [ ENTORNO ACADÉMICO ]
            </div>
            <h1 className="text-5xl md:text-7xl font-display font-black uppercase text-white leading-tight">
              MolDesign <span className="text-indigo-400">Campus</span>
            </h1>
            <p className="text-lg text-slate-400 max-w-md leading-relaxed">
              Plataforma de aprendizaje y descubrimiento de fármacos. Supera las prácticas de laboratorio y clasifica en la tabla de méritos de tu universidad.
            </p>
            <div className="flex gap-6 mt-8">
              <Link
                href="/evaluation"
                className="group relative inline-flex items-center justify-center px-8 py-4 font-bold text-lg text-white bg-indigo-600 rounded-lg hover:bg-indigo-500 transition-all shadow-lg"
              >
                INICIAR PRÁCTICA
              </Link>
            </div>
          </div>

          <div className="flex-1 w-full max-w-md relative p-8 border border-surface-800 bg-surface-900/50 backdrop-blur-md rounded-2xl shadow-xl hover:border-indigo-500/30 transition-all group">
            <div className="relative w-full aspect-[3/1] flex items-center justify-center">
              {/* Se mantiene el glow alrededor del logo a petición del usuario */}
              <Image
                src="/logo-full.png"
                alt="MolDesign AI Logo"
                width={700}
                height={233}
                className="w-full object-contain filter drop-shadow-[0_0_20px_rgba(0,255,255,0.6)] group-hover:drop-shadow-[0_0_30px_rgba(0,255,255,0.8)] transition-all duration-700"
                priority
              />
            </div>
            <div className="mt-6 border-t border-surface-700 pt-4 flex justify-between items-center text-indigo-400">
              <span className="font-bold">STATUS: ACTIVO</span>
              <span className="text-sm">V6.5 Edu</span>
            </div>
          </div>
        </section>

        {error && (
          <div className="p-4 bg-red-950/50 border border-red-900 text-red-400 font-medium text-center rounded-lg">
            SISTEMA DESCONECTADO - MODO OFFLINE
          </div>
        )}

        {/* LEADERBOARD (STATS) */}
        <section className="mt-20 border border-surface-700 bg-surface-900/40 rounded-2xl p-8 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-600 to-purple-600"></div>
          <h2 className="text-2xl font-bold text-white mb-8 flex items-center gap-3">
            <span className="text-indigo-400">📊</span> TABLA DE MÉRITOS
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { label: "MOLÉCULAS SINTETIZADAS", value: stats?.total_molecules?.toLocaleString() ?? "...", icon: "🧪" },
              { label: "CERTIFICADOS EMITIDOS", value: stats?.total_certifications?.toLocaleString() ?? "...", icon: "📜" },
              { label: "PUNTUACIÓN MÁXIMA", value: stats?.best_score?.toFixed(1) ?? "...", unit: "PTS", icon: "⭐" },
              { label: "RED ACADÉMICA", value: stats?.community_status ?? "Global", icon: "🎓" },
            ].map((stat, i) => (
              <div key={i} className="flex flex-col p-6 bg-surface-950/50 border border-surface-800 rounded-xl hover:border-indigo-500/50 transition-colors group">
                <div className="text-3xl mb-3 opacity-80 group-hover:opacity-100 group-hover:scale-110 transition-all">{stat.icon}</div>
                <div className="text-2xl font-bold text-white flex items-baseline gap-2 mb-1">
                  {stat.value} {stat.unit && <span className="text-sm text-indigo-400">{stat.unit}</span>}
                </div>
                <div className="text-[10px] font-bold text-surface-400 uppercase tracking-wider">{stat.label}</div>
              </div>
            ))}
          </div>

          {stats?.best_molecule_name && (
            <div className="mt-8 p-5 bg-indigo-950/30 border border-indigo-900/50 rounded-xl flex justify-between items-center flex-wrap gap-4">
               <div>
                  <div className="text-indigo-300 font-bold tracking-widest text-sm uppercase">Mejor Proyecto // {stats.best_user_name ?? "Anónimo"}</div>
                  <div className="text-xs text-surface-400 mt-1">OBJETIVO: {stats.best_target_pdb}</div>
               </div>
               <div className="text-xs font-mono text-white bg-surface-950 px-4 py-2 border border-surface-700 rounded-lg break-all max-w-lg">
                  {stats.best_molecule_name}
               </div>
            </div>
          )}
        </section>

        {/* QUEST PIPELINE */}
        <section className="mt-20">
           <h2 className="text-2xl font-bold text-white mb-8 flex items-center gap-3">
             <span className="text-indigo-400">📚</span> RUTA DE PRÁCTICAS
           </h2>
           <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {PIPELINE_STEPS.map((s, idx) => (
                <button 
                  key={idx} 
                  onClick={() => setSelectedPipelineStep(s)}
                  className="relative text-left bg-surface-900/40 border border-surface-800 p-6 rounded-xl hover:border-indigo-500/50 hover:bg-surface-800/50 transition-all group overflow-hidden cursor-pointer"
                >
                   <div className="absolute top-0 left-0 w-1 h-full bg-surface-700 group-hover:bg-indigo-500 transition-colors"></div>
                   <div className="absolute top-4 right-4 text-3xl opacity-5 group-hover:opacity-10 font-bold transition-all">P{s.step}</div>
                   <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                     {s.title}
                   </h3>
                   <p className="text-xs text-surface-400 font-sans leading-relaxed line-clamp-2">{s.descEdu}</p>
                   
                   <div className="mt-5 h-1.5 w-full bg-surface-950 rounded-full overflow-hidden relative">
                     <div className="absolute top-0 bottom-0 bg-indigo-500 w-0 group-hover:w-full transition-all duration-1000 ease-out" />
                   </div>
                </button>
              ))}
           </div>
        </section>

      </div>

      {/* Modal Interactivo: Ruta de Prácticas */}
      {selectedPipelineStep && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in"
          onClick={() => setSelectedPipelineStep(null)}
        >
          <div 
            className="bg-surface-900 border border-indigo-500/50 rounded-2xl p-6 max-w-md w-full shadow-2xl relative animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              onClick={() => setSelectedPipelineStep(null)}
              className="absolute top-4 right-4 text-surface-400 hover:text-white transition-colors"
            >
              ✕
            </button>
            <div className="mb-6">
              <h3 className="text-2xl font-display font-bold text-white uppercase mb-4 flex items-center gap-2">
                <span className="text-indigo-500">P{selectedPipelineStep.step}</span> {selectedPipelineStep.title}
              </h3>
              <p className="text-base text-surface-300 font-sans leading-relaxed">
                {selectedPipelineStep.descEdu}
              </p>
            </div>
            
            <div className="flex justify-end">
              <button 
                onClick={() => setSelectedPipelineStep(null)}
                className="px-6 py-2 bg-indigo-600/20 text-indigo-400 hover:bg-indigo-600/40 hover:text-white font-bold rounded-lg transition-colors"
              >
                ¡Entendido!
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function HomePage() {
  const { interfaceMode } = useInterface();
  const [stats, setStats] = useState<GlobalStats | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getGlobalStats()
      .then(setStats)
      .catch((err) => {
        console.error("Error loading stats:", err);
        setError(true);
      });
  }, []);

  if (interfaceMode === "GAMIFIED") {
    return <AcademyHome stats={stats} error={error} />;
  }

  return <ProHome stats={stats} error={error} />;
}
