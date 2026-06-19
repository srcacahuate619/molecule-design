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
  const lastReportedSmiles = useRef<string | null>(null);

  // When Ketcher initializes, store the instance and load initial SMILES
  const handleInit = async (ketcher: Ketcher) => {
    ketcherRef.current = ketcher;
    
    // Enable valency error display and other "free" drawing settings
    ketcher.setSettings({
      "valency-error-display": true,
      "ignore-stereochemistry-errors": true,
      "smart-layout": true,
      "disable-check-on-save": true
    });

    setReady(true);

    // On mobile, Ketcher internally focuses an input after mounting which
    // triggers the virtual keyboard. We explicitly blur it away.
    setTimeout(() => {
      if (document.activeElement instanceof HTMLElement) {
        document.activeElement.blur();
      }
    }, 100);

    if (initialSmiles) {
      try {
        lastReportedSmiles.current = initialSmiles;
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
        if (ketcherRef.current) {
          const smiles = await ketcherRef.current.getSmiles();
          if (smiles !== undefined && smiles !== lastReportedSmiles.current) {
            lastReportedSmiles.current = smiles;
            onSmilesChange(smiles);
          }
        }
      } catch {
        // Ketcher may throw if canvas is empty
      }
    }, 500); // Slightly slower interval to feel less "jittery"

    return () => clearInterval(interval);
  }, [ready, onSmilesChange]);

  const isProcessing = useRef(false);
  const pendingSmiles = useRef<string | null>(null);

  // Internal function to handle the heavy lifting
  const syncToKetcher = async (smiles: string) => {
    if (!ready || !ketcherRef.current) return;
    
    if (isProcessing.current) {
      pendingSmiles.current = smiles;
      return;
    }

    try {
      // Check if SMILES is valid before attempting to set it (to avoid chaotic jumps)
      // We can use a simple check or just let ketcher fail, but a "clean" way is to 
      // only update if it's empty or doesn't have obvious syntax errors.
      const current = await ketcherRef.current.getSmiles();
      if (current !== smiles) {
        // We only proceed if it's empty or looks like a valid SMILES 
        // (simple heuristic: balanced parentheses and numbers)
        const isPotentiallyValid = smiles === "" || (
            (smiles.match(/\(/g) || []).length === (smiles.match(/\)/g) || []).length
        );

        if (isPotentiallyValid) {
            isProcessing.current = true;
            lastReportedSmiles.current = smiles;
            await ketcherRef.current.setMolecule(smiles);
        }
      }
    } catch (e) {
      // Invalid SMILES during typing - ignore
    } finally {
      isProcessing.current = false;
      // If a new request came in while we were busy, process the LATEST one now
      if (pendingSmiles.current !== null) {
        const next = pendingSmiles.current;
        pendingSmiles.current = null;
        syncToKetcher(next);
      }
    }
  };

  // Sync external SMILES changes to Ketcher (ONLY if they didn't originate from Ketcher)
  useEffect(() => {
    if (ready && ketcherRef.current && initialSmiles !== undefined) {
      if (initialSmiles === lastReportedSmiles.current) return;

      const timeout = setTimeout(() => {
        syncToKetcher(initialSmiles);
      }, 50); // Fast 50ms debounce

      return () => clearTimeout(timeout);
    }
  }, [initialSmiles, ready]);

  return (
    <div
      className="ketcher-wrapper rounded-xl border border-surface-700"
      style={{ height: 550, position: "relative", overflow: "hidden", maxWidth: "100%" }}
    >
      <Editor
        staticResourcesUrl=""
        structServiceProvider={getStructServiceProvider()}
        onInit={handleInit}
        errorHandler={(message: string) => {
          // Log but don't block
          console.debug("Ketcher notice:", message);
        }}
      />
    </div>
  );
}
