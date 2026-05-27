"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  poseData?: string;     // SDF — ligando con enlaces correctos
  proteinData?: string;  // PDB — receptor
  height?: number;
  hotspots?: string[]; // ej. ["MET99", "TYR100"]
  hotspotsHit?: string[]; // ej. ["MET99"]
  hideLegend?: boolean;
};

type ViewMode = "standard" | "surface" | "charges";

export function MoleculeViewer3D({ poseData, proteinData, height = 450, hotspots = [], hotspotsHit = [], hideLegend = false }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef    = useRef<any>(null);

  // Estados para los controles visuales (Toggles)
  const [viewMode, setViewMode] = useState<ViewMode>("standard");
  const [showInteractions, setShowInteractions] = useState(false);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [showHotspots, setShowHotspots] = useState(true);
  const [selectedHotspot, setSelectedHotspot] = useState<string | null>(null);

  // 1. Carga inicial de modelos (Solo se ejecuta al recibir datos nuevos)
  useEffect(() => {
    const hasProtein = !!proteinData && proteinData.trim().length > 10;
    const hasLigand  = !!poseData    && poseData.trim().length    > 10;
    
    if (!hasProtein && !hasLigand) {
      setModelsLoaded(false);
      return;
    }

    const $3d = (window as any).$3Dmol;
    if (!$3d) {
      const t = setTimeout(() => {
        const v2 = (window as any).$3Dmol;
        if (v2 && containerRef.current) loadModels(v2);
      }, 600);
      return () => clearTimeout(t);
    }
    
    loadModels($3d);

    function loadModels($3dmol: any) {
      if (!containerRef.current) return;

      if (!viewerRef.current) {
        viewerRef.current = $3dmol.createViewer(containerRef.current, {
          backgroundColor: "#0b1220",
          antialias: true,
        });
      }
      const v = viewerRef.current;
      v.clear();

      if (hasProtein) {
        v.addModel(proteinData, "pdb");
      }

      if (hasLigand) {
        const singlePoseData = poseData!.split('$$$$')[0] + '\n$$$$\n';
        v.addModel(singlePoseData, "sdf");
      }
      
      setModelsLoaded(true);
    }
  }, [poseData, proteinData]);

  // 2. Renderizado dinámico de estilos, superficies e interacciones
  useEffect(() => {
    if (!modelsLoaded || !viewerRef.current) return;
    const v = viewerRef.current;
    const $3d = (window as any).$3Dmol;
    
    const hasProtein = !!proteinData && proteinData.trim().length > 10;
    const hasLigand  = !!poseData    && poseData.trim().length    > 10;
    const ligIdx = hasProtein ? 1 : 0;

    v.removeAllSurfaces();
    v.removeAllShapes();

    if (hasProtein) {
      v.setStyle({ model: 0 }, { cartoon: { color: "spectrum", opacity: 0.50, thickness: 0.30 } });
    }
    if (hasLigand) {
      v.setStyle({ model: ligIdx }, { stick: { colorscheme: "greenCarbon", radius: 0.22 } });
    }

    if (hasProtein && hasLigand) {
      const m0 = v.getModel(0);
      const m1 = v.getModel(ligIdx);
      if (m0 && m1) {
        const protAtoms = m0.selectedAtoms({});
        const ligAtoms = m1.selectedAtoms({});
        const resisWithLines = new Set<string>();
        const pocketResis = new Set<string>();
        const pocketSelArray: any[] = [];

        for (const p of protAtoms) {
          if (p.hetflag) continue;
          for (const l of ligAtoms) {
            const dx = p.x - l.x, dy = p.y - l.y, dz = p.z - l.z;
            const dist2 = dx*dx + dy*dy + dz*dz;
            if (dist2 <= 25) {
              const key = `${p.chain}:${p.resi}`;
              if (!pocketResis.has(key)) {
                pocketResis.add(key);
                pocketSelArray.push({ chain: p.chain, resi: p.resi });
              }
              if (showInteractions && dist2 <= 12.25) {
                const lElem = l.elem?.trim().toUpperCase();
                const pElem = p.elem?.trim().toUpperCase();
                if (["O","N","F","S"].includes(lElem) && ["O","N","F","S"].includes(pElem)) {
                  resisWithLines.add(`${p.resn}${p.resi}`);
                  v.addCylinder({ start: l, end: p, radius: 0.05, color: "yellow", dashed: true });
                }
              }
            }
          }
        }

        pocketSelArray.forEach(sel => {
          v.addStyle({ model: 0, ...sel }, { stick: { colorscheme: "lightgreyCarbon", radius: 0.14, opacity: 0.99 } });
        });

        if (showHotspots) {
          hotspots.forEach(hs => {
            const match = hs.match(/(?:([A-Z]):)?([A-Z]{1,3})\s*(\d+)/i);
            if (match) {
              const chain = match[1]; // Opcional
              const resn = match[2].toUpperCase();
              const resi = parseInt(match[3]);
              const isHit = hotspotsHit.includes(hs);
              const hasLine = resisWithLines.has(`${resn}${resi}`);
              const color = isHit ? (hasLine ? "#00ff00" : "#10b981") : "#ff00ff";
              const opacity = (isHit && !hasLine) ? 0.45 : 1.0;
              const radius = hasLine ? 0.75 : 0.6;
              const selector: any = { model: 0, resn, resi };
              if (chain) selector.chain = chain; // Solo aplicar si se especifica cadena
              v.addStyle(selector, { sphere: { color, radius, opacity } });
              v.setClickable(selector, true, () => setSelectedHotspot(`${chain ? chain + ':' : ''}${resn}${resi}`));
            }
          });
        }

        if (viewMode === "surface") v.addSurface($3d.SurfaceType.VDW, { opacity: 0.5, color: "white" }, { model: 0 });
        else if (viewMode === "charges") {
          protAtoms.forEach((p: any) => {
            if (["ASP", "GLU"].includes(p.resn)) p.color = "red";
            else if (["ARG", "LYS", "HIS"].includes(p.resn)) p.color = "blue";
            else p.color = "white";
          });
          v.addSurface($3d.SurfaceType.VDW, { opacity: 0.65 }, { model: 0 });
        }
      }
    }

    if (hasLigand) { v.zoomTo({ model: ligIdx }); v.zoom(0.85); } else v.zoomTo();
    v.render();
  }, [modelsLoaded, viewMode, showInteractions, showHotspots, poseData, proteinData, hotspots, hotspotsHit]);

  const hasData = !!(poseData || proteinData);

  return (
    <>
      <div className="relative overflow-hidden rounded-2xl border border-surface-800 bg-surface-950 shadow-2xl" style={{ height, width: "100%", position: "relative" }}>
        <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
        
        {!modelsLoaded && hasData && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-surface-950/50 backdrop-blur-sm">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
          </div>
        )}

        {!hasData && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-surface-500 bg-surface-950/80">
            <span className="text-4xl opacity-30">🔬</span>
            <p className="text-sm font-medium">La visualización aparecerá tras completar el docking</p>
          </div>
        )}

        {hasData && (
          <>
            <div style={{ position: "absolute", top: "12px", right: "12px", zIndex: 10, display: "flex", flexWrap: "wrap", justifyContent: "flex-end", gap: "8px", maxWidth: "90%" }}>
              <div className="flex bg-surface-950/80 rounded-lg p-1 border border-surface-700 backdrop-blur-md">
                {["standard", "surface", "charges"].map((m: any) => (
                  <button key={m} onClick={() => setViewMode(m)} className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${viewMode === m ? 'bg-brand-600 text-white' : 'text-surface-400 hover:text-white'}`}>
                    {m === "standard" ? "Bolsillo" : m === "surface" ? "Superficie" : "Cargas"}
                  </button>
                ))}
              </div>
              <button onClick={() => setShowInteractions(!showInteractions)} className={`px-3 py-1.5 text-xs font-semibold rounded-lg border backdrop-blur-md transition-all ${showInteractions ? 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400' : 'bg-surface-950/80 border-surface-700 text-surface-400'}`}>
                Interacciones
              </button>
              <button onClick={() => setShowHotspots(!showHotspots)} className={`px-3 py-1.5 text-xs font-semibold rounded-lg border backdrop-blur-md transition-all ${showHotspots ? 'bg-pink-500/20 border-pink-500/50 text-pink-400' : 'bg-surface-950/80 border-surface-700 text-surface-400'}`} style={showHotspots ? { borderColor: '#ff00ff', color: '#ff00ff' } : {}}>
                Hotspots
              </button>
            </div>

            {selectedHotspot && (
              <div style={{ position: "absolute", bottom: "12px", left: "12px", zIndex: 20, background: "rgba(255, 0, 255, 0.15)", border: "1px solid rgba(255, 0, 255, 0.4)", padding: "6px 12px", borderRadius: "10px", backdropFilter: "blur(8px)", color: "#ff80ff", fontSize: "12px", fontWeight: "bold", display: "flex", alignItems: "center", gap: "8px" }}>
                <span>🎯 Hotspot: {selectedHotspot}</span>
                <button onClick={() => setSelectedHotspot(null)} className="ml-2 opacity-60">✕</button>
              </div>
            )}
          </>
        )}
      </div>

      {!hideLegend && (
        <div className="mt-4 flex flex-wrap items-center justify-center gap-6 px-4 py-3 bg-surface-950/40 rounded-xl border border-surface-800/50 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-[#00ff00] shadow-[0_0_8px_#00ff00]" />
            <span className="text-[10px] font-bold text-surface-200 uppercase tracking-wider">Impacto Crítico (&lt; 3.5Å + Polar)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-[#10b981] opacity-60" />
            <span className="text-[10px] font-bold text-surface-400 uppercase tracking-wider">Contacto Proximidad (&lt; 5.0Å)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-[#ff00ff]" />
            <span className="text-[10px] font-bold text-surface-400 uppercase tracking-wider">Sin Interacción (&gt; 5.0Å)</span>
          </div>
        </div>
      )}
    </>
  );
}
