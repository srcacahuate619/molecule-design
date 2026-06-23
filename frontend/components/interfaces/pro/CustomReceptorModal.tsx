import React, { useState, useRef } from "react";
import { X, Upload, Info, FileText, CheckCircle2, Zap } from "lucide-react";
import { uploadCustomTarget } from "@/lib/api";

interface CustomReceptorModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export function CustomReceptorModal({ onClose, onSuccess }: CustomReceptorModalProps) {
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [chainId, setChainId] = useState("A");
  
  // Manual coords
  const [gridX, setGridX] = useState("");
  const [gridY, setGridY] = useState("");
  const [gridZ, setGridZ] = useState("");
  
  // Cofactors
  const [cofactors, setCofactors] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Por favor, selecciona un archivo.");
      return;
    }
    if (!name.trim()) {
      setError("Por favor, dale un nombre a tu receptor.");
      return;
    }
    if (mode === "manual" && (!gridX || !gridY || !gridZ)) {
      setError("En modo manual debes proveer las coordenadas (X, Y, Z) del centro del sitio activo.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("name", name);
      formData.append("is_curated", mode === "manual" ? "true" : "false");
      formData.append("chain_id", chainId);
      
      if (gridX && gridY && gridZ) {
        formData.append("grid_center_x", gridX);
        formData.append("grid_center_y", gridY);
        formData.append("grid_center_z", gridZ);
      }
      
      if (cofactors) {
        formData.append("cofactors_whitelist", cofactors);
      }

      await uploadCustomTarget(formData);
      onSuccess();
    } catch (err: any) {
      setError(err.message || "Ocurrió un error inesperado al subir el receptor.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
      <div className="relative w-full max-w-2xl bg-zinc-900 border border-zinc-700/50 rounded-2xl shadow-2xl overflow-hidden shadow-cyan-900/20">
        
        {/* Glow Effects */}
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-500" />
        <div className="absolute -top-32 -right-32 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 -left-32 w-64 h-64 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="relative flex items-center justify-between p-6 border-b border-zinc-800">
          <div>
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <Upload className="w-6 h-6 text-cyan-400" />
              Subir Receptor Personalizado
            </h2>
            <p className="text-zinc-400 text-sm mt-1">
              Integra tus propias proteínas a la base de datos privada de MolDesign.
            </p>
          </div>
          <button 
            onClick={onClose}
            className="p-2 text-zinc-400 hover:text-white bg-zinc-800/50 hover:bg-zinc-700 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="relative p-6 space-y-6">
          
          {/* Mode Selector */}
          <div className="flex bg-zinc-800/50 p-1 rounded-xl">
            <button
              type="button"
              onClick={() => setMode("auto")}
              className={`flex-1 py-3 px-4 rounded-lg flex items-center justify-center gap-2 font-medium transition-all ${
                mode === "auto" 
                  ? "bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-lg" 
                  : "text-zinc-400 hover:text-white hover:bg-zinc-700/50"
              }`}
            >
              <Zap className={`w-5 h-5 ${mode === "auto" ? "text-yellow-300" : ""}`} />
              Modo Automático (PDB crudo)
            </button>
            <button
              type="button"
              onClick={() => setMode("manual")}
              className={`flex-1 py-3 px-4 rounded-lg flex items-center justify-center gap-2 font-medium transition-all ${
                mode === "manual" 
                  ? "bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg" 
                  : "text-zinc-400 hover:text-white hover:bg-zinc-700/50"
              }`}
            >
              <CheckCircle2 className={`w-5 h-5 ${mode === "manual" ? "text-green-300" : ""}`} />
              Modo Manual (PDBQT Curado)
            </button>
          </div>

          {/* Mode Instructions */}
          <div className="bg-blue-900/20 border border-blue-500/20 p-4 rounded-xl flex gap-3 text-blue-200 text-sm leading-relaxed">
            <Info className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
            <div>
              {mode === "auto" ? (
                <ul className="list-disc pl-4 space-y-1">
                  <li>Sube un archivo <b>.pdb</b> (por ejemplo, extraído del RCSB).</li>
                  <li>Nuestro pipeline MGLTools/Meeko se encargará de curarlo, remover agua y optimizar puentes de hidrógeno.</li>
                  <li>Autodescubriremos el <b>Sitio Activo</b> basándonos en el ligando cocristalizado de referencia.</li>
                </ul>
              ) : (
                <ul className="list-disc pl-4 space-y-1">
                  <li>Sube un archivo <b>.pdbqt</b> que ya hayas curado en tu laboratorio.</li>
                  <li>No modificaremos la estructura, se inyectará directamente al motor Vina.</li>
                  <li>Es <b>obligatorio</b> que proveas las coordenadas (X, Y, Z) del centro de la caja de búsqueda.</li>
                </ul>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* General Settings */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1">Nombre del Receptor</label>
                <input 
                  type="text" 
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Ej. Mi Quinasa Mutante"
                  className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1">Cadena a evaluar</label>
                <input 
                  type="text" 
                  value={chainId}
                  onChange={e => setChainId(e.target.value)}
                  placeholder="A"
                  maxLength={1}
                  className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all uppercase"
                />
              </div>

              {mode === "auto" && (
                <div>
                  <label className="block text-sm font-medium text-zinc-300 mb-1">Cofactores a mantener (Opcional)</label>
                  <input 
                    type="text" 
                    value={cofactors}
                    onChange={e => setCofactors(e.target.value)}
                    placeholder="Ej. HEM, ZN, MG"
                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                  />
                  <p className="text-xs text-zinc-500 mt-1">Nombres HETATM separados por coma.</p>
                </div>
              )}
            </div>

            {/* File & Coords */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1">Archivo de Estructura</label>
                <div 
                  onClick={() => fileInputRef.current?.click()}
                  className={`w-full h-24 border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-colors ${
                    file ? 'border-cyan-500 bg-cyan-500/5' : 'border-zinc-700 hover:border-zinc-500 bg-zinc-800/50'
                  }`}
                >
                  <input 
                    type="file" 
                    ref={fileInputRef}
                    accept={mode === "auto" ? ".pdb" : ".pdbqt"} 
                    onChange={handleFileChange}
                    className="hidden" 
                  />
                  {file ? (
                    <div className="flex items-center gap-2 text-cyan-400 font-medium">
                      <FileText className="w-6 h-6" />
                      <span className="truncate max-w-[200px]">{file.name}</span>
                    </div>
                  ) : (
                    <>
                      <Upload className="w-6 h-6 text-zinc-500 mb-2" />
                      <span className="text-sm text-zinc-400">Clic para subir ({mode === "auto" ? ".pdb" : ".pdbqt"})</span>
                    </>
                  )}
                </div>
              </div>

              {(mode === "manual" || (mode === "auto" && !file)) && (
                <div>
                  <label className="block text-sm font-medium text-zinc-300 mb-1">Centro del Sitio Activo (Grid Box)</label>
                  <div className="flex gap-2">
                    <input type="number" step="0.1" placeholder="X" value={gridX} onChange={e => setGridX(e.target.value)} className="w-1/3 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 text-center" />
                    <input type="number" step="0.1" placeholder="Y" value={gridY} onChange={e => setGridY(e.target.value)} className="w-1/3 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 text-center" />
                    <input type="number" step="0.1" placeholder="Z" value={gridZ} onChange={e => setGridZ(e.target.value)} className="w-1/3 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:border-cyan-500 text-center" />
                  </div>
                  {mode === "auto" && <p className="text-xs text-zinc-500 mt-1">Opcional. Si lo omites, intentaremos auto-detectarlo.</p>}
                </div>
              )}
            </div>

          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-500/30 text-red-300 p-3 rounded-lg text-sm flex items-center gap-2">
              <Info className="w-5 h-5 shrink-0" />
              {error}
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-zinc-800">
            <button 
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-6 py-2.5 rounded-lg font-medium text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors"
            >
              Cancelar
            </button>
            <button 
              type="submit"
              disabled={loading}
              className="relative px-6 py-2.5 rounded-lg font-medium text-white overflow-hidden group transition-all"
            >
              <div className={`absolute inset-0 bg-gradient-to-r ${mode === "auto" ? "from-cyan-600 to-blue-600" : "from-purple-600 to-pink-600"} opacity-90 group-hover:opacity-100 transition-opacity`} />
              <span className="relative flex items-center gap-2">
                {loading ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Procesando...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Subir y Procesar Receptor
                  </>
                )}
              </span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
