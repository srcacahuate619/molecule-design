"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";

/**
 * Dynamically imported Ketcher editor (no SSR).
 * Ketcher uses WASM (Indigo) and browser-only APIs.
 */
const KetcherEditorInner = dynamic(() => import("./KetcherEditorInner"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center rounded-xl border border-dashed border-surface-700 bg-surface-950"
      style={{ height: 450 }}
    >
      <div className="flex items-center gap-2 text-sm text-surface-400">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
        Cargando editor molecular...
      </div>
    </div>
  ),
});

type Props = {
  onSmilesChange?: (smiles: string) => void;
  initialSmiles?: string;
};

/**
 * Ketcher molecular editor component.
 *
 * Offers two modes:
 * - Text mode: simple SMILES input with molecule presets
 * - Visual mode: full Ketcher 2D structure editor (EPAM, Apache 2.0)
 *
 * https://github.com/epam/ketcher
 */
export function KetcherEditor({ onSmilesChange, initialSmiles }: Props) {
  const [mode, setMode] = useState<"text" | "ketcher">("text");
  const [textSmiles, setTextSmiles] = useState(initialSmiles || "");
  const [ketcherError, setKetcherError] = useState<string | null>(null);

  const handleTextChange = useCallback(
    (value: string) => {
      setTextSmiles(value);
      onSmilesChange?.(value);
    },
    [onSmilesChange],
  );

  const handleKetcherSmiles = useCallback(
    (smiles: string) => {
      setTextSmiles(smiles);
      onSmilesChange?.(smiles);
    },
    [onSmilesChange],
  );

  return (
    <div className="space-y-3">
      {/* Mode toggle */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setMode("text")}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            mode === "text"
              ? "bg-brand-600/20 text-brand-400"
              : "text-surface-400 hover:bg-surface-800"
          }`}
        >
          SMILES texto
        </button>
        <button
          onClick={() => {
            setKetcherError(null);
            setMode("ketcher");
          }}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            mode === "ketcher"
              ? "bg-brand-600/20 text-brand-400"
              : "text-surface-400 hover:bg-surface-800"
          }`}
        >
          Editor visual
        </button>
      </div>

      {mode === "text" ? (
        <div className="space-y-2">
          <textarea
            rows={3}
            value={textSmiles}
            onChange={(e) => handleTextChange(e.target.value)}
            placeholder="Introduce SMILES, ej: CC(=O)Oc1ccccc1C(=O)O (Aspirina)"
            className="w-full rounded-xl border border-surface-700 bg-surface-950 px-4 py-3 font-mono text-sm text-gray-200 placeholder-surface-500 transition-colors focus:border-brand-500 focus:outline-none"
          />
          <div className="flex flex-wrap gap-2">
            {[
              { label: "Aspirina", smiles: "CC(=O)Oc1ccccc1C(=O)O" },
              { label: "Cafeína", smiles: "Cn1c(=O)c2c(ncn2C)n(C)c1=O" },
              { label: "Ibuprofeno", smiles: "CC(C)Cc1ccc(cc1)C(C)C(=O)O" },
              { label: "Serotonina", smiles: "NCCc1c[nH]c2ccc(O)cc12" },
            ].map((ex) => (
              <button
                key={ex.label}
                onClick={() => handleTextChange(ex.smiles)}
                className="rounded-lg border border-surface-700 bg-surface-800 px-2.5 py-1 text-xs text-surface-400 transition-colors hover:border-brand-500/50 hover:text-brand-400"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {ketcherError ? (
            <div className="flex items-center justify-center rounded-xl border border-dashed border-surface-700 bg-surface-950 p-12">
              <div className="text-center">
                <div className="mb-3 text-4xl">⚠️</div>
                <p className="text-sm font-medium text-surface-400">
                  No se pudo cargar el editor visual
                </p>
                <p className="mt-1 text-xs text-surface-500">{ketcherError}</p>
                <button
                  onClick={() => setMode("text")}
                  className="mt-4 rounded-lg bg-brand-600 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-brand-700"
                >
                  Cambiar a modo texto
                </button>
              </div>
            </div>
          ) : (
            <KetcherEditorInner
              initialSmiles={textSmiles}
              onSmilesChange={handleKetcherSmiles}
            />
          )}
          {/* SMILES output mirror for Ketcher mode */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-surface-400">SMILES:</label>
            <input
              type="text"
              value={textSmiles}
              readOnly
              className="flex-1 rounded-lg border border-surface-700 bg-surface-950 px-3 py-1.5 font-mono text-xs text-gray-300 focus:border-brand-500 focus:outline-none"
            />
          </div>
        </div>
      )}
    </div>
  );
}
