"use client";

/**
 * Inner Ketcher Editor component.
 *
 * This is loaded dynamically (no SSR) by KetcherEditor.tsx because:
 * - Ketcher uses browser-only APIs (DOM, Web Workers, WASM)
 * - The Indigo WASM module cannot run in Node.js
 *
 * Ketcher is developed by EPAM Systems under Apache 2.0 License.
 * https://github.com/epam/ketcher
 */

import { useEffect, useRef, useState } from "react";

import { Editor } from "ketcher-react";
import { StandaloneStructServiceProvider } from "ketcher-standalone";
import type { Ketcher } from "ketcher-core";

// Ketcher CSS — required for correct rendering
import "ketcher-react/dist/index.css";

type Props = {
  initialSmiles?: string;
  onSmilesChange?: (smiles: string) => void;
};

// Singleton service provider — reused across remounts
let structServiceProvider: StandaloneStructServiceProvider | null = null;

function getStructServiceProvider() {
  if (!structServiceProvider) {
    structServiceProvider = new StandaloneStructServiceProvider();
  }
  return structServiceProvider;
}

export default function KetcherEditorInner({
  initialSmiles,
  onSmilesChange,
}: Props) {
  const ketcherRef = useRef<Ketcher | null>(null);
  const [ready, setReady] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // When Ketcher initializes, store the instance and load initial SMILES
  const handleInit = async (ketcher: Ketcher) => {
    ketcherRef.current = ketcher;
    setReady(true);

    if (initialSmiles) {
      try {
        await ketcher.setMolecule(initialSmiles);
      } catch (e) {
        console.warn("Ketcher: could not load initial SMILES", e);
      }
    }
  };

  // Periodically sync SMILES from Ketcher to parent (debounced)
  useEffect(() => {
    if (!ready || !ketcherRef.current || !onSmilesChange) return;

    const interval = setInterval(async () => {
      try {
        const smiles = await ketcherRef.current!.getSmiles();
        if (smiles) {
          onSmilesChange(smiles);
        }
      } catch {
        // Ketcher may throw if canvas is empty
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [ready, onSmilesChange]);

  return (
    <div
      className="ketcher-wrapper overflow-hidden rounded-xl border border-surface-700"
      style={{ height: 450, position: "relative" }}
    >
      <Editor
        staticResourcesUrl=""
        structServiceProvider={getStructServiceProvider()}
        onInit={handleInit}
        errorHandler={(message: string) => {
          console.warn("Ketcher error:", message);
        }}
      />
    </div>
  );
}
