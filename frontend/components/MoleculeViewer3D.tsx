"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  poseData?: string;     // SDF — ligando con enlaces correctos
  proteinData?: string;  // PDB — receptor
  height?: number;
  hotspots?: string[]; // ej. ["MET99", "TYR100"]
};

type ViewMode = "standard" | "surface" | "charges";

export function MoleculeViewer3D({ poseData, proteinData, height = 450 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef    = useRef<any>(null);

  // Estados para los controles visuales (Toggles)
  const [viewMode, setViewMode] = useState<ViewMode>("standard");
  const [showInteractions, setShowInteractions] = useState(false);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [showHotspots, setShowHotspots] = useState(true);

  console.log("MoleculeViewer3D Hotspots Prop:", hotspots);

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
        // Extraemos solo la primera pose (mejor afinidad)
        const singlePoseData = poseData!.split('$$$$')[0] + '\n$$$$\n';
        v.addModel(singlePoseData, "sdf");
      }
      
      setModelsLoaded(true);
    }
  }, [poseData, proteinData]);

  // 3. Renderizado dinámico de estilos, superficies e interacciones
  useEffect(() => {
    if (!modelsLoaded || !viewerRef.current) return;
    const v = viewerRef.current;
    const $3d = (window as any).$3Dmol;
    
    const hasProtein = !!proteinData && proteinData.trim().length > 10;
    const hasLigand  = !!poseData    && poseData.trim().length    > 10;
    const ligIdx = hasProtein ? 1 : 0;

    // Limpiamos capas previas (rápido, no recarga modelos)
    v.removeAllSurfaces();
    v.removeAllShapes();

    // Estilos base
    if (hasProtein) {
      v.setStyle(
        { model: 0 },
        { cartoon: { color: "spectrum", opacity: 0.50, thickness: 0.30 } }
      );
    }
    if (hasLigand) {
      v.setStyle(
        { model: ligIdx },
        {
          stick:  { colorscheme: "greenCarbon", radius: 0.22 },
          sphere: { colorscheme: "greenCarbon", radius: 0.20 },
        }
      );
    }

    // Cálculos de sitio activo e interacciones
    if (hasProtein && hasLigand) {
      const m0 = v.getModel(0);
      const m1 = v.getModel(ligIdx);
      
      if (m0 && m1) {
        const protAtoms = m0.selectedAtoms({});
        const ligAtoms = m1.selectedAtoms({});
        
        const pocketResis = new Set<string>();
        const pocketSelArray: any[] = [];

        // Coloreado manual de átomos para el mapa de cargas electrostáticas
        if (viewMode === "charges") {
          for (const p of protAtoms) {
            if (p.resn === "ASP" || p.resn === "GLU") p.color = "red";
            else if (p.resn === "ARG" || p.resn === "LYS" || p.resn === "HIS") p.color = "blue";
            else p.color = "white";
          }
        }

        // Detección de bolsillo y puentes de hidrógeno
        for (const p of protAtoms) {
          if (p.hetflag) continue; // Ignorar ligandos originales y agua
          
          for (const l of ligAtoms) {
            const dx = p.x - l.x, dy = p.y - l.y, dz = p.z - l.z;
            const dist2 = dx*dx + dy*dy + dz*dz;
            
            if (dist2 <= 25) { // < 5Å (Bolsillo)
              const key = `${p.chain}:${p.resi}`;
              if (!pocketResis.has(key)) {
                pocketResis.add(key);
                pocketSelArray.push({ chain: p.chain, resi: p.resi });
              }

              // Interacciones (Puentes de hidrógeno heurísticos < 3.5Å)
              if (showInteractions && dist2 <= 12.25) {
                // Para evitar fallos por espacios o mayúsculas en el formato PDB/SDF
                const lElem = l.elem ? l.elem.trim().toUpperCase() : "";
                const pElem = p.elem ? p.elem.trim().toUpperCase() : "";
                
                const isLigPolar = lElem === "O" || lElem === "N" || lElem === "F" || lElem === "S";
                const isProtPolar = pElem === "O" || pElem === "N" || pElem === "F" || pElem === "S";
                
                if (isLigPolar && isProtPolar) {
                  v.addCylinder({
                    start: { x: l.x, y: l.y, z: l.z },
                    end: { x: p.x, y: p.y, z: p.z },
                    radius: 0.05,
                    color: "yellow",
                    dashed: true,
                  });
                }
              }
            }
          }
        }

        // Aplicar estilos a los residuos del bolsillo
        if (pocketSelArray.length > 0) {
          for (const sel of pocketSelArray) {
            v.addStyle(
              { model: 0, ...sel },
              {
                stick: {
                  colorscheme: "lightgreyCarbon",
                  radius: 0.14,
                  opacity: 0.99,
                },
                cartoon: {
                  color: "spectrum",
                  opacity: 0.99,
                  thickness: 0.35,
                },
              }
            );
          }
        }

        // --- [NUEVO] Resaltar Hotspots ---
        if (showHotspots && hotspots && hotspots.length > 0) {
          console.log("Rendering hotspots for model 0:", hotspots);
          for (const hs of hotspots) {
            const match = hs.match(/([A-Z]{1,3})\s*(\d+)/i);
            if (match) {
              const resn = match[1].toUpperCase();
              const resi = parseInt(match[2]);
              
              // Intentar seleccionar en el modelo 0 (Receptor)
              const selector = { model: 0, resn, resi };
              
              v.addStyle(
                selector,
                {
                  stick: {
                    color: "#ff00ff", 
                    radius: 0.35,
                    opacity: 1.0,
                  },
                  sphere: {
                    color: "#ff00ff",
                    radius: 0.6, // Más grandes para que se noten
                  }
                }
              );
              
              v.addLabel(hs, {
                fontSize: 14,
                fontColor: "#ffffff",
                backgroundColor: "#ff00ff",
                backgroundOpacity: 1.0,
                selection: selector,
                inFront: true,
              });
            }
          }
        }

        // Aplicar Capas de Superficie (View Modes)
        if (viewMode === "surface") {
          v.addSurface(
            $3d.SurfaceType.VDW,
            { opacity: 0.5, color: "white" },
            { model: 0 }
          );
        } else if (viewMode === "charges") {
          v.addSurface(
            $3d.SurfaceType.VDW,
            { opacity: 0.65 }, // Usa los p.color modificados arriba
            { model: 0 }
          );
        }
      }
    }

    // Cámara: centrar y enfocar
    // Solo centrar si es la primera carga o si no se ha movido
    if (hasLigand) {
      v.zoomTo({ model: ligIdx });
      v.zoom(0.85);
    } else {
      v.zoomTo();
    }

    v.render();
  }, [modelsLoaded, viewMode, showInteractions, showHotspots, poseData, proteinData, hotspots]);

  const hasData = !!(poseData || proteinData);

  return (
    <div
      style={{
        width:     "100%",
        height:    `${height}px`,
        minHeight: `${height}px`,
        position:  "relative",
        background: "#0b1220",
        borderRadius: "12px",
        overflow: "hidden",
        border: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      <div
        ref={containerRef}
        style={{ width: "100%", height: "100%", position: "absolute", top: 0, left: 0 }}
        id="mol3d-viewer"
      />

      {!hasData && (
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          color: "#4b5563", fontSize: "13px", gap: "8px",
          pointerEvents: "none",
        }}>
          <span style={{ fontSize: "32px", opacity: 0.4 }}>🔬</span>
          <span>La visualización 3D aparecerá tras completar el docking</span>
        </div>
      )}

      {hasData && (
        <>
          {/* Toggles Superiores */}
          <div style={{ position: "absolute", top: "12px", right: "12px", zIndex: 10, display: "flex", flexWrap: "wrap", justifyContent: "flex-end", gap: "8px", maxWidth: "90%" }}>
            
            <div className="flex bg-surface-950/80 rounded-lg p-1 border border-surface-700 backdrop-blur-md">
              <button 
                onClick={() => setViewMode('standard')}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${viewMode === 'standard' ? 'bg-brand-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
              >
                Bolsillo
              </button>
              <button 
                onClick={() => setViewMode('surface')}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${viewMode === 'surface' ? 'bg-brand-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
              >
                Superficie
              </button>
              <button 
                onClick={() => setViewMode('charges')}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${viewMode === 'charges' ? 'bg-brand-600 text-white shadow-md' : 'text-surface-400 hover:text-white'}`}
              >
                Cargas
              </button>
            </div>

            <button
              onClick={() => setShowInteractions(!showInteractions)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg border backdrop-blur-md transition-all ${
                showInteractions 
                  ? 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400 shadow-[0_0_10px_rgba(234,179,8,0.2)]' 
                  : 'bg-surface-950/80 border-surface-700 text-surface-400 hover:text-white'
              }`}
            >
              {showInteractions ? "Ocultar Interacciones" : "Ver Interacciones"}
            </button>

            <button
              onClick={() => setShowHotspots(!showHotspots)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg border backdrop-blur-md transition-all ${
                showHotspots 
                  ? 'bg-pink-500/20 border-pink-500/50 text-pink-400 shadow-[0_0_10px_rgba(255,0,255,0.2)]' 
                  : 'bg-surface-950/80 border-surface-700 text-surface-400 hover:text-white'
              }`}
              style={showHotspots ? { borderColor: '#ff00ff', color: '#ff00ff' } : {}}
            >
              {showHotspots ? "Ocultar Hotspots" : "Ver Hotspots"}
            </button>
          </div>

          {/* Leyenda Inferior */}
          <div style={{
            position: "absolute", bottom: "10px", right: "10px",
            background: "rgba(11,18,32,0.85)", padding: "6px 10px",
            borderRadius: "8px", fontSize: "10px", color: "#94a3b8",
            display: "flex", flexDirection: "column", gap: "3px",
            backdropFilter: "blur(4px)", pointerEvents: "none",
          }}>
            <span><span style={{ color: "#60a5fa" }}>■</span> Receptor (cinta + bolsillo)</span>
            <span><span style={{ color: "#4ade80" }}>■</span> Ligando docking (pose)</span>
            {showInteractions && (
              <span><span style={{ color: "#facc15" }}>■</span> Interacciones polares (H-bonds)</span>
            )}
            {showHotspots && (
              <span><span style={{ color: "#ff00ff" }}>■</span> Hotspots Biológicos</span>
            )}
            <span style={{ color: "#6b7280", fontSize: "9px", marginTop: "2px" }}>
              Arrastra para rotar · Scroll para zoom
            </span>
          </div>
        </>
      )}
    </div>
  );
}
