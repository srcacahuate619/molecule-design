"use client";

import { useEffect, useRef, useState } from "react";
import { Box, HelpCircle, Crosshair } from "lucide-react";

type Props = {
  poseData?: string;     // SDF - Ligando
  proteinData?: string;  // PDB - Receptor
  height?: number;
  hotspots?: string[];
  hotspotsHit?: string[];
  onOpenTargetSelector?: () => void;
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
    script.onerror = () => {
      script.remove();
      reject(new Error(`Failed to load script ${src}`));
    };
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
    link.onerror = () => {
      link.remove();
      reject(new Error(`Failed to load style ${href}`));
    };
    document.head.appendChild(link);
  });
};

// --- HELPER PARSERS ---

const cleanPdb = (pdbStr: string): string => {
  const standardResidues = new Set(["MSE", "SEP", "TPO", "PTR", "CSX", "CSD", "CSO", "CME"]);
  return pdbStr
    .split("\n")
    .filter((line) => {
      const record = line.slice(0, 6).trim();
      if (record === "HETATM") {
        const resName = line.slice(17, 20).trim();
        return standardResidues.has(resName);
      }
      return true;
    })
    .join("\n");
};

const crystallizationHelpers = new Set([
  // Common Crystallization Helpers & Ions
  "SO4", "PO4", "CL", "NA", "K", "MG", "CA", "ZN", "FE", "NI", "CU", "CO", "MN", "NH4", "LI", "BR", "I",
  "GOL", "EDO", "DMS", "ACT", "PEG", "PG4", "PGE", "IPA", "EOH", "MOH", "TRS", "FMT", "BU3", "MPD", "AZI", 
  "UNX", "DTT", "BME", "CIT", "DIO", "MLI", "PE8", "P33", "P4C"
]);

const extractReferenceLigand = (pdbStr: string): string | null => {
  const standardResidues = new Set(["MSE", "SEP", "TPO", "PTR", "CSX", "CSD", "CSO", "CME"]);
  const lines = pdbStr.split("\n").filter((line) => {
    const record = line.slice(0, 6).trim();
    if (record === "HETATM") {
      const resName = line.slice(17, 20).trim();
      const isWater = ["HOH", "WAT", "DOD", "SOL", "TIP"].includes(resName);
      return !standardResidues.has(resName) && !isWater && !crystallizationHelpers.has(resName);
    }
    return false;
  });
  if (lines.length === 0) return null;
  return lines.join("\n") + "\nEND\n";
};

const patchSdfTitle = (sdfStr: string): string => {
  const lines = sdfStr.split("\n");
  if (lines.length > 0) {
    // Forcefully overwrite the SDF title to ensure Molstar reads it
    lines[0] = "Candidato_Ligando_MolDesign";
  }
  return lines.join("\n");
};

const getResidueCoordinates = (pdbStr: string, residueName: string, residueSeq: number, chainId: string = "A") => {
  const lines = pdbStr.split("\n");
  for (const line of lines) {
    const record = line.slice(0, 6).trim();
    if (record === "ATOM" || record === "HETATM") {
      const atomName = line.slice(12, 16).trim();
      const resName = line.slice(17, 20).trim();
      const chain = line.slice(21, 22).trim() || "A";
      const seq = parseInt(line.slice(22, 26).trim());
      if (atomName === "CA" && resName === residueName && seq === residueSeq && chain === chainId) {
        const x = parseFloat(line.slice(30, 38).trim());
        const y = parseFloat(line.slice(38, 46).trim());
        const z = parseFloat(line.slice(46, 54).trim());
        return { x, y, z };
      }
    }
  }
  return null;
};

const createHotspotsPdb = (pdbStr: string, hotspots: string[], hotspotsHit: string[]) => {
  let pdbContent = "";
  let atomIndex = 1;
  for (const hs of hotspots) {
    const match = hs.match(/(?:([A-Z]):)?([A-Z]{3})\s*(\d+)/i);
    if (!match) continue;
    const chain = match[1] || "A";
    const resn = match[2].toUpperCase();
    const resi = parseInt(match[3]);

    const coords = getResidueCoordinates(pdbStr, resn, resi, chain);
    if (coords) {
      const x = coords.x.toFixed(3).padStart(8);
      const y = coords.y.toFixed(3).padStart(8);
      const z = coords.z.toFixed(3).padStart(8);

      const isHit = hotspotsHit.includes(hs);
      const element = isHit ? "MG" : "O";
      const atomName = isHit ? "MG " : "O  ";
      const resName = isHit ? "MG " : "HOH";
      pdbContent += `HETATM${atomIndex.toString().padStart(5)}  ${atomName} ${resName} ${chain}${resi.toString().padStart(4)}    ${x}${y}${z}  1.00 20.00          ${element.padStart(2)}\n`;
      atomIndex++;
    }
  }
  if (pdbContent === "") return null;
  return pdbContent + "END\n";
};

export default function AdvancedMolstarViewer({ poseData, proteinData, height = 500, hotspots = [], hotspotsHit = [], onOpenTargetSelector }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewerReady, setViewerReady] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const handleFocusCandidate = () => {
    const viewer = viewerRef.current;
    if (viewer && viewerReady) {
      try {
        const structures = viewer.plugin.managers.structure.hierarchy.current.structures;
        console.log("Molstar structures in hierarchy:", structures);
        
        let candidate = structures.find((s: any) => {
          const label1 = (s.cell?.obj?.label || "").toLowerCase();
          const label2 = (s.cell?.obj?.data?.label || "").toLowerCase();
          return label1.includes("candidato") || label1.includes("diseño") || label1.includes("ligando") || label1.includes("sdf") || label1.includes("unknown") ||
                 label2.includes("candidato") || label2.includes("diseño") || label2.includes("ligando") || label2.includes("sdf") || label2.includes("unknown");
        });

        if (!candidate && poseData && structures.length > 1) {
          console.warn("Candidate not found by label. Falling back to the last loaded structure.");
          candidate = structures[structures.length - 1];
        }

        if (candidate && candidate.cell?.obj?.data) {
          const data = candidate.cell.obj.data;
          console.log("Candidate structure data for focus:", data);
          
          if (data.boundary && data.boundary.sphere) {
            console.log("Focusing using boundary sphere:", data.boundary.sphere);
            // Focus on the sphere with a slight zoom out for context
            viewer.plugin.managers.camera.focusSphere(data.boundary.sphere);
            
            // Try to highlight it if possible
            if (data.representativeLoci) {
              try {
                viewer.plugin.managers.interactivity.lociHighlights.highlightOnly({ loci: data.representativeLoci });
              } catch (e) { /* ignore highlight error */ }
            }
          } else if (data.representativeLoci) {
            console.log("Focusing using representativeLoci");
            viewer.plugin.managers.camera.focusLoci(data.representativeLoci);
          } else {
            console.warn("No boundary or loci found on candidate data.");
            viewer.plugin.managers.camera.reset();
          }
        } else {
          console.warn("No candidate data object found.");
          viewer.plugin.managers.camera.reset();
        }
      } catch (e) {
        console.error("Error focusing on candidate molecule:", e);
      }
    }
  };

  // 1. Initial Load of Scripts and Molstar Instance (Only once on unmount)
  useEffect(() => {
    let viewer: any = null;
    let cancelled = false;
    let sub: any = null;

    const initMolstar = async () => {
      if (!containerRef.current) return;
      setLoading(true);
      setError(null);

      try {
        // Load CSS (prefer CDN first, fallback to local)
        try {
          await loadStyle("https://cdn.jsdelivr.net/npm/molstar@5.9.0/build/viewer/molstar.css", "molstar-css");
        } catch (cdnErr) {
          console.warn("CDN molstar.css failed, trying local:", cdnErr);
          await loadStyle("/molstar.css", "molstar-css");
        }

        // Load JS (prefer CDN first, fallback to local)
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

        containerRef.current.innerHTML = "";

        // Create the viewer instance with default controls enabled (settings, selection, expand)
        viewer = await Viewer.create(containerRef.current, {
          layoutIsExpanded: false,
          layoutShowControls: false,
          layoutShowRemoteState: false,
          layoutShowSequence: false,
          layoutShowLog: false,
          viewportShowExpand: true,         // Enable default expand button
          viewportShowSelectionMode: true,  // Enable default selection controls
          viewportShowSettings: true,       // Enable default settings button
        });

        // Subscribe to layout changes to reactively update the outer container's size
        sub = viewer.plugin.layout.events.updated.subscribe(() => {
          if (viewer.plugin && viewer.plugin.layout) {
            setIsExpanded(!!viewer.plugin.layout.state.isExpanded);
          }
        });

        viewerRef.current = viewer;
        setViewerReady(true);
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
      setViewerReady(false);
      if (sub) {
        try { sub.unsubscribe(); } catch (e) { /* ignore */ }
      }
      if (viewer) {
        try { viewer.dispose(); } catch (e) { /* ignore */ }
      }
    };
  }, []);

  // 2. Dynamic Reload of Models when Data changes (Fast reload without WebGL flashing)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !viewerReady) return;

    let cancelled = false;

    const loadStructures = async () => {
      try {
        setLoading(true);

        // Clear previous structures
        await viewer.plugin.clear();

        const hasProtein = !!proteinData && proteinData.trim().length > 10;
        const hasLigand = !!poseData && poseData.trim().length > 10;

        if (cancelled) return;

        if (hasProtein) {
          // Load cleaned protein receptor structure (no overlapping HETATMs)
          const cleanProt = cleanPdb(proteinData!);
          await viewer.loadStructureFromData(cleanProt, "pdb", { dataLabel: "Receptor" });

          if (cancelled) return;

          // Always load crystallographic reference ligand as a separate named structure
          const refLig = extractReferenceLigand(proteinData!);
          if (refLig) {
            await viewer.loadStructureFromData(refLig, "pdb", { dataLabel: "Referencia (Cristalografía)" });
          }

          if (cancelled) return;

          // Always load pocket hotspots as a separate named structure
          if (hotspots.length > 0) {
            const hotspotsPdb = createHotspotsPdb(proteinData!, hotspots, hotspotsHit);
            if (hotspotsPdb) {
              await viewer.loadStructureFromData(hotspotsPdb, "pdb", { dataLabel: "Hotspots (Puntos Clave)" });
            }
          }
        }

        if (cancelled) return;

        if (hasLigand) {
          // Load candidate ligand (patched to avoid "unknown" label in tooltip)
          const singlePoseData = poseData!.split("$$$$")[0] + "\n$$$$\n";
          const patchedSdf = patchSdfTitle(singlePoseData);
          await viewer.loadStructureFromData(patchedSdf, "sdf", { dataLabel: "Mi Diseño MolDesign (Candidato)" });
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Error al cargar estructuras en Molstar:", err);
          setError("Error al cargar coordenadas en el visualizador.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadStructures();

    return () => {
      cancelled = true;
    };
  }, [viewerReady, proteinData, poseData, hotspots, hotspotsHit]);

  const prevExpandedRef = useRef<boolean>(isExpanded);

  // 3. Reactively Resize Molstar WebGL canvas when layout expanded state changes
  useEffect(() => {
    const viewer = viewerRef.current;
    if (viewer && viewerReady) {
      // Only execute resize logic if expanded state has actually changed (prevents 0x0 canvas collapse on mount)
      if (prevExpandedRef.current !== isExpanded) {
        prevExpandedRef.current = isExpanded;

        const resize = () => {
          try {
            const container = containerRef.current;
            if (container && container.clientWidth > 0 && container.clientHeight > 0) {
              // Trigger layout event
              if (typeof viewer.handleResize === "function") {
                viewer.handleResize();
              }
              // Force WebGL canvas resize and aspect ratio correction
              if (viewer.plugin && viewer.plugin.canvas3d && typeof viewer.plugin.canvas3d.handleResize === "function") {
                viewer.plugin.canvas3d.handleResize();
              }
              // Dispatch window resize event to trigger internal observers in Molstar
              window.dispatchEvent(new Event("resize"));
            }
          } catch (e) {
            console.warn("Resize error on expand state change:", e);
          }
        };

        // Run multiple times with slight delays to ensure CSS transition and layout reflow are complete
        const t1 = setTimeout(resize, 50);
        const t2 = setTimeout(resize, 150);
        const t3 = setTimeout(resize, 300);

        return () => {
          clearTimeout(t1);
          clearTimeout(t2);
          clearTimeout(t3);
        };
      }
    }
  }, [isExpanded, viewerReady]);

  const hasData = !!(poseData || proteinData);

  // Stacking context breakout styles when viewport is expanded
  const wrapperStyle = isExpanded
    ? { position: "fixed" as const, inset: 0, width: "100vw", height: "100vh", zIndex: 9999 }
    : { height, width: "100%", position: "relative" as const };

  const canvasStyle = isExpanded
    ? { position: "relative" as const, width: "100vw", height: "100vh" }
    : { position: "relative" as const, width: "100%", height: "100%", minHeight: `${height}px` };

  return (
    <div 
      className={
        isExpanded
          ? "bg-[#060a13] w-screen h-screen flex items-center justify-center z-[9999]"
          : "relative overflow-hidden rounded-3xl border border-indigo-500/10 bg-[#060a13] shadow-2xl"
      }
      style={wrapperStyle}
    >
      <style>{`
        .msp-plugin,
        .msp-plugin-container,
        .msp-viewport {
          width: 100% !important;
          height: 100% !important;
        }
        .msp-viewport canvas {
          width: 100% !important;
          height: 100% !important;
        }
      `}</style>

      {/* Floating Controls Bar */}
      {hasData && !loading && !error && !isExpanded && (
        <div className="absolute top-4 left-4 z-[100] flex items-center gap-2 pointer-events-auto">
          {/* Identify Candidate Ligand Button */}
          {poseData && (
            <button
              onClick={handleFocusCandidate}
              className="flex items-center gap-2 rounded-xl bg-[#090e1a]/90 border border-white/10 px-3 py-1.5 backdrop-blur-md text-[10px] font-black uppercase tracking-wider text-slate-300 hover:text-white hover:bg-indigo-600/30 hover:border-indigo-500/50 transition-all duration-200 shadow-xl"
            >
              <Crosshair size={12} className="text-indigo-400" />
              <span>Identificar Mi Diseño</span>
            </button>
          )}
        </div>
      )}

      {/* Canvas container - forces the WebGL canvas to span full boundaries */}
      <div 
        ref={containerRef} 
        className="w-full h-full [&_canvas]:!w-full [&_canvas]:!h-full [&_.msp-plugin]:!w-full [&_.msp-plugin]:!h-full [&_.msp-plugin-container]:!w-full [&_.msp-plugin-container]:!h-full [&_.msp-viewport]:!w-full [&_.msp-viewport]:!h-full" 
        style={canvasStyle} 
      />

      {/* Loading HUD */}
      {loading && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#05080f]/70 backdrop-blur-sm gap-3">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-indigo-400 animate-pulse">Cargando Mol* (WebGL2)...</span>
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

      {/* Floating Info / Legend Badge */}
      {hasData && !loading && !error && !isExpanded && (
        <div className="absolute bottom-4 left-4 z-10 flex flex-col gap-1.5 rounded-xl bg-black/60 border border-white/10 p-2.5 backdrop-blur-md max-w-[280px]">
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping" />
            <span className="text-[8px] font-black text-slate-300 uppercase tracking-widest flex items-center gap-1">
              Motor: Molstar WebGL2 <HelpCircle size={10} className="text-slate-500" />
            </span>
          </div>
          {hotspots.length > 0 && (
            <div className="flex items-center gap-3 mt-1 border-t border-white/5 pt-1 text-[8px] font-bold text-slate-400 uppercase tracking-wider">
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#10b981] inline-block shadow-[0_0_6px_#10b981]" /> Contacto</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#ef4444] inline-block shadow-[0_0_6px_#ef4444]" /> Omitido</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
