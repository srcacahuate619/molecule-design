"use client";

import { useEffect, useRef, useState } from "react";
import { Box, HelpCircle } from "lucide-react";

// Molstar is loaded dynamically inside useEffect (client-only).
// Static imports of molstar cause webpack "Critical dependency" errors
// that break ALL pages that transitively import this component.

type Props = {
  poseData?: string;     // SDF - Ligando
  proteinData?: string;  // PDB - Receptor
  height?: number;
  hotspots?: string[];
  hotspotsHit?: string[];
};

const loadScript = (src: string, id: string): Promise<void> => {
  if (typeof document === "undefined") return Promise.resolve();
  return new Promise((resolve, reject) => {
    if (document.getElementById(id)) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.id = id;
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load script ${src}`));
    document.head.appendChild(script);
  });
};

const loadStyle = (href: string, id: string): Promise<void> => {
  if (typeof document === "undefined") return Promise.resolve();
  return new Promise((resolve, reject) => {
    if (document.getElementById(id)) {
      resolve();
      return;
    }
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = href;
    link.onload = () => resolve();
    link.onerror = () => reject(new Error(`Failed to load style ${href}`));
    document.head.appendChild(link);
  });
};

export default function AdvancedMolstarViewer({ poseData, proteinData, height = 500, hotspots = [], hotspotsHit = [] }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let viewer: any = null;
    let cancelled = false;

    const initMolstar = async () => {
      if (!containerRef.current) return;
      setLoading(true);
      setError(null);

      try {
        // Load CSS (prefer CDN first for reliable HTTPS and compression headers on production)
        try {
          await loadStyle("https://cdn.jsdelivr.net/npm/molstar@5.9.0/build/viewer/molstar.css", "molstar-css");
        } catch (cdnErr) {
          console.warn("CDN molstar.css failed, trying local:", cdnErr);
          await loadStyle("/molstar.css", "molstar-css");
        }

        // Load JS (prefer CDN first for reliable HTTPS and compression headers on production)
        try {
          await loadScript("https://cdn.jsdelivr.net/npm/molstar@5.9.0/build/viewer/molstar.js", "molstar-js");
        } catch (cdnErr) {
          console.warn("CDN molstar.js failed, trying local:", cdnErr);
          await loadScript("/molstar.js", "molstar-js");
        }

        const molstarGlobal = (window as any).molstar;
        if (!molstarGlobal) {
          throw new Error("Global 'molstar' not found.");
        }
        const Viewer = molstarGlobal.Viewer;
        if (!Viewer) {
          throw new Error("Viewer object not found in global 'molstar'.");
        }
        if (typeof Viewer.create !== "function") {
          throw new Error("Viewer.create is not a function.");
        }

        if (cancelled || !containerRef.current) return;

        // Clean container before rendering
        containerRef.current.innerHTML = "";

        viewer = await Viewer.create(containerRef.current, {
          layoutIsExpanded: false,
          layoutShowControls: false,
          layoutShowRemoteState: false,
          layoutShowSequence: false,
          layoutShowLog: false,
          viewportShowExpand: false,
          viewportShowSelectionMode: false,
          viewportShowSettings: false,
        });

        viewerRef.current = viewer;

        const hasProtein = !!proteinData && proteinData.trim().length > 10;
        const hasLigand = !!poseData && poseData.trim().length > 10;

        if (hasProtein) {
          await viewer.loadStructureFromData(proteinData, "pdb", { dataLabel: "Receptor" });
        }

        if (hasLigand) {
          const singlePoseData = poseData!.split("$$$$")[0] + "\n$$$$\n";
          await viewer.loadStructureFromData(singlePoseData, "sdf", { dataLabel: "Ligando" });
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Error al inicializar Molstar:", err);
          setError("No se pudo cargar el visor 3D científico (Mol*).");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    initMolstar();

    return () => {
      cancelled = true;
      if (viewer) {
        try { viewer.dispose(); } catch (e) { /* ignore */ }
      }
    };
  }, [poseData, proteinData]);

  const hasData = !!(poseData || proteinData);

  return (
    <div className="relative overflow-hidden rounded-3xl border border-indigo-500/10 bg-[#060a13] shadow-2xl" style={{ height, width: "100%", position: "relative" }}>
      {/* Canvas container - explicitly position and constrain parent dimensions, forcing canvas children to fill */}
      <div 
        ref={containerRef} 
        className="w-full h-full [&_canvas]:!w-full [&_canvas]:!h-full [&_.msp-plugin]:!w-full [&_.msp-plugin]:!h-full [&_.msp-plugin-container]:!w-full [&_.msp-plugin-container]:!h-full" 
        style={{ position: "relative", width: "100%", height: "100%", minHeight: `${height}px` }} 
      />

      {/* Loading HUD */}
      {loading && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#05080f]/70 backdrop-blur-sm gap-3">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-indigo-400 animate-pulse">Inicializando Mol* (WebGL2)...</span>
        </div>
      )}

      {/* Error HUD */}
      {error && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#05080f]/90 gap-2 p-4 text-center">
          <span className="text-2xl text-rose-500">⚠️</span>
          <p className="text-xs text-rose-400 font-bold">{error}</p>
        </div>
      )}

      {/* No Data HUD */}
      {!hasData && !loading && !error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-slate-600 bg-[#05080f]/80">
          <Box size={40} className="opacity-30 text-indigo-400" />
          <p className="text-xs font-black uppercase tracking-widest text-slate-500">Esperando coordenadas estructurales...</p>
        </div>
      )}

      {/* Floating Info Badge */}
      {hasData && !loading && !error && (
        <div className="absolute bottom-4 left-4 z-10 flex items-center gap-2 rounded-xl bg-black/60 border border-white/10 px-3 py-1.5 backdrop-blur-md">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping" />
          <span className="text-[8px] font-black text-slate-300 uppercase tracking-widest flex items-center gap-1">
            Motor: Molstar WebGL2 <HelpCircle size={10} className="text-slate-500" />
          </span>
        </div>
      )}
    </div>
  );
}
