
"use client";

import { useEffect, useRef } from "react";

type Props = {
  poseData?: string;
  proteinData?: string;
};

export function MoleculeViewer3D({ poseData, proteinData }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);



  // Initialize viewer ONCE on mount, regardless of data
  useEffect(() => {
    // Aggressive telemetry: log $3Dmol presence
    if (typeof window !== "undefined") {
      console.log("3DMOL OBJECT:", (window as any).$3Dmol);
    }
    if (
      typeof window !== "undefined" &&
      (window as any).$3Dmol &&
      containerRef.current &&
      !viewerRef.current
    ) {
      viewerRef.current = new (window as any).$3Dmol.GLViewer(containerRef.current, {
        backgroundColor: "#0b1220"
      });
    }
  }, []);

  // Update models/styles on data change
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.clear();
    let hasModel = false;
    console.log("[3D DEBUG] poseData:", poseData);
    let m1 = null, m2 = null;
    // Add protein model
    if (proteinData && proteinData.trim().length > 0) {
      m1 = viewer.addModel(proteinData, "pdb");
      console.log("[3D DEBUG] Protein model:", m1);
      if (m1) {
        // Professional: classic spectrum cartoon
        viewer.setStyle({ model: 0 }, { cartoon: { color: "spectrum" } });
        hasModel = true;
      } else {
        console.warn("[3D DEBUG] Protein PDB string failed to parse.");
      }
    }
    // Add ligand/pose model
    if (poseData && poseData.trim().length > 0) {
      m2 = viewer.addModel(poseData, "sdf");
      console.log("[3D DEBUG] Pose model:", m2);
      if (m2) {
        // Professional: thick, visible green stick
        viewer.setStyle({ model: m1 ? 1 : 0 }, { stick: { colorscheme: 'greenCarbon', radius: 0.25 } });
        hasModel = true;
      } else {
        console.warn("[3D DEBUG] Pose SDF string failed to parse.");
      }
    }
    // Failsafe: if nothing, apply a global style to see if anything renders
    if (!hasModel) {
      viewer.setStyle({}, { stick: { colorscheme: 'greenCarbon', radius: 0.25 } });
    }
    // Only render if at least one model was added
    if (hasModel) {
      // Camera focus: zoom to ligand if present, else all
      if (m2) {
        viewer.zoomTo({ model: m1 ? 1 : 0 });
      } else {
        viewer.zoomTo();
      }
      viewer.render();
    }
  }, [proteinData, poseData]);

  return (
    <div style={{ width: '100%', height: '450px', minHeight: '450px', position: 'relative', background: '#0b1220' }}>
      <h1 style={{ color: 'red', position: 'absolute', zIndex: 999 }}>V2.2 - STABLE</h1>
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}
        id="mol3d-viewer"
      />
    </div>
  );
}
