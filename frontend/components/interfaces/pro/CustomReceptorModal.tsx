import React, { useState, useRef, useEffect } from "react";
import { X, Upload, Info, FileText, CheckCircle2, Zap } from "lucide-react";
import { uploadCustomTarget } from "../../../lib/api";

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
  
  // Manual size
  const [gridSizeX, setGridSizeX] = useState("20.0");
  const [gridSizeY, setGridSizeY] = useState("20.0");
  const [gridSizeZ, setGridSizeZ] = useState("20.0");
  
  // Cofactors
  const [cofactors, setCofactors] = useState("");
  const [isCommunity, setIsCommunity] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      // Validación de tipo de archivo en cliente
      const ext = selected.name.split(".").pop()?.toLowerCase();
      const allowed = mode === "manual" ? ["pdbqt"] : ["pdb"];
      if (!allowed.includes(ext || "")) {
        setError(`Archivo inválido. Se esperaba .${allowed.join(" o .")} para el modo seleccionado.`);
        e.target.value = "";
        return;
      }
      setError(null);
      setFile(selected);
    }
  };

  // [FIX] Auto-enviar cuando el archivo es seleccionado (evita el doble click)
  // Cuando el file picker cierra y file cambia de null -> File, se re-ejecuta handleSubmit
  const pendingSubmitRef = useRef(false);

  useEffect(() => {
    if (pendingSubmitRef.current && file) {
      pendingSubmitRef.current = false;
      // Crear un evento sintético para reutilizar la lógica de handleSubmit
      const syntheticEvent = { preventDefault: () => {} } as React.FormEvent;
      handleSubmit(syntheticEvent);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      // Marcar que, cuando el usuario seleccione un archivo, se re-envíe el form
      pendingSubmitRef.current = true;
      fileInputRef.current?.click();
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
      
      if (mode === "manual" && gridSizeX && gridSizeY && gridSizeZ) {
        formData.append("grid_size_x", gridSizeX);
        formData.append("grid_size_y", gridSizeY);
        formData.append("grid_size_z", gridSizeZ);
      }
      
      if (cofactors) {
        formData.append("cofactors_whitelist", cofactors);
      }
      formData.append("is_community", isCommunity ? "true" : "false");

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
      <div className="relative w-full max-w-2xl bg-zinc-900 border border-zinc-700/50 rounded-2xl shadow-2xl overflow-y-auto max-h-[95vh] sm:max-h-[90vh] shadow-purple-900/20">
        
        {/* Glow Effects */}
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500" />
        <div className="absolute -top-32 -right-32 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 -left-32 w-64 h-64 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="relative flex items-center justify-between p-4 sm:p-6 border-b border-zinc-800">
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2">
              <Upload className="w-5 h-5 sm:w-6 sm:h-6 text-purple-400" />
              Subir Receptor Personalizado
            </h2>
            <p className="text-zinc-400 text-xs sm:text-sm mt-1">
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
        <form onSubmit={handleSubmit} className="relative p-4 sm:p-6 space-y-4 sm:space-y-6">
          
          {/* Mode Selector */}
          <div className="flex flex-col sm:flex-row bg-zinc-800/50 p-1 rounded-xl gap-1">
            <button
              type="button"
              onClick={() => setMode("auto")}
              className={`flex-1 py-2 sm:py-3 px-4 rounded-lg flex items-center justify-center gap-2 font-medium transition-all text-sm ${
                mode === "auto" 
                  ? "bg-gradient-to-r from-purple-600 to-indigo-800 text-white shadow-lg shadow-purple-900/40" 
                  : "text-zinc-400 hover:text-white hover:bg-zinc-700/50"
              }`}
            >
              <Zap className={`w-4 h-4 sm:w-5 sm:h-5 ${mode === "auto" ? "text-yellow-300" : ""}`} />
              Modo Automático (PDB crudo)
            </button>
            <button
              type="button"
              onClick={() => setMode("manual")}
              className={`flex-1 py-2 sm:py-3 px-4 rounded-lg flex items-center justify-center gap-2 font-medium transition-all text-sm ${
                mode === "manual" 
                  ? "bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg shadow-purple-900/40" 
                  : "text-zinc-400 hover:text-white hover:bg-zinc-700/50"
              }`}
            >
              <CheckCircle2 className={`w-4 h-4 sm:w-5 sm:h-5 ${mode === "manual" ? "text-green-300" : ""}`} />
              Modo Manual (PDBQT Curado)
            </button>
          </div>

          {/* Mode Instructions */}
          <div className="bg-purple-950/20 border border-purple-500/20 p-4 rounded-xl flex gap-3 text-purple-200 text-sm leading-relaxed">
            <Info className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
            <div>
              {mode === "auto" ? (
                <ul className="list-disc pl-4 space-y-1 text-xs sm:text-sm">
                  <li>Sube un archivo <b>.pdb</b> (por ejemplo, extraído del RCSB).</li>
                  <li>Nuestro pipeline MGLTools/Meeko se encargará de curarlo, remover agua y optimizar puentes de hidrógeno.</li>
                  <li>Autodescubriremos el <b>Sitio Activo</b> basándonos en el ligando cocristalizado de referencia.</li>
                </ul>
              ) : (
                <ul className="list-disc pl-4 space-y-1 text-xs sm:text-sm">
                  <li>Sube un archivo <b>.pdbqt</b> que ya hayas curado en tu laboratorio.</li>
                  <li>No modificaremos la estructura, se inyectará directamente al motor Vina.</li>
                  <li>Es <b>obligatorio</b> que proveas las coordenadas (X, Y, Z) del centro de la caja de búsqueda.</li>
                </ul>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
            
            {/* General Settings */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1">Nombre del Receptor</label>
                <input 
                  type="text" 
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Ej. Mi Quinasa Mutante"
                  className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all"
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
                  className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all uppercase"
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
                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all"
                  />
                  <p className="text-xs text-zinc-500 mt-1">Nombres HETATM separados por coma.</p>
                </div>
              )}

              <div className="flex items-center gap-3 bg-zinc-950/40 p-3 rounded-lg border border-zinc-800/80 mt-2">
                <input 
                  type="checkbox" 
                  id="share_community"
                  checked={isCommunity}
                  onChange={e => setIsCommunity(e.target.checked)}
                  className="w-4 h-4 text-purple-500 bg-zinc-950 border-zinc-700 rounded focus:ring-purple-500 cursor-pointer"
                />
                <div className="cursor-pointer select-none">
                  <label htmlFor="share_community" className="block text-xs font-semibold text-zinc-200 cursor-pointer">
                    Compartir con la comunidad científica
                  </label>
                  <p className="text-[10px] text-zinc-500 leading-tight">
                    Cualquier investigador de MolDesign podrá ver y usar este receptor. Se incluirá mención de tu usuario.
                  </p>
                </div>
              </div>
            </div>

            {/* Grid Box Settings */}
            <div className="space-y-4">
              <input 
                type="file" 
                ref={fileInputRef}
                accept={mode === "auto" ? ".pdb" : ".pdbqt"} 
                onChange={handleFileChange}
                className="hidden" 
              />
              
              {mode === "manual" ? (
                <>
                  <div>
                    <label className="block text-sm font-medium text-zinc-300 mb-1">Coordenadas del Centro (Grid Box)</label>
                    <div className="flex gap-2">
                      <input type="number" step="0.1" placeholder="X" value={gridX} onChange={e => setGridX(e.target.value)} className="w-1/3 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:border-purple-500 text-center" />
                      <input type="number" step="0.1" placeholder="Y" value={gridY} onChange={e => setGridY(e.target.value)} className="w-1/3 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:border-purple-500 text-center" />
                      <input type="number" step="0.1" placeholder="Z" value={gridZ} onChange={e => setGridZ(e.target.value)} className="w-1/3 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:border-purple-500 text-center" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-300 mb-1">Tamaño de la Caja (Grid Size)</label>
                    <div className="flex gap-2">
                      <input type="number" step="0.1" placeholder="SX" value={gridSizeX} onChange={e => setGridSizeX(e.target.value)} className="w-1/3 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:border-purple-500 text-center" />
                      <input type="number" step="0.1" placeholder="SY" value={gridSizeY} onChange={e => setGridSizeY(e.target.value)} className="w-1/3 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:border-purple-500 text-center" />
                      <input type="number" step="0.1" placeholder="SZ" value={gridSizeZ} onChange={e => setGridSizeZ(e.target.value)} className="w-1/3 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:border-purple-500 text-center" />
                    </div>
                    <p className="text-xs text-zinc-500 mt-1">Valores recomendados: 20.0 x 20.0 x 20.0 Ångströms.</p>
                  </div>
                </>
              ) : (
                <div className="h-full flex flex-col justify-center bg-zinc-900/50 border border-zinc-800 rounded-xl p-4 space-y-2">
                  <h4 className="text-sm font-semibold text-purple-400">Automatización Inteligente</h4>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    Al no especificar coordenadas, nuestro servidor rastreará la estructura PDB y computará un centro espacial anclado al ligando con mayor relevancia farmacológica. El tamaño de búsqueda (Grid Size) se auto-ajustará dinámicamente a <span className="font-mono text-purple-300">25.0 Å</span> para proveer flexibilidad computacional a Vina.
                  </p>
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
          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 sm:gap-3 pt-4 border-t border-zinc-800">
            <button 
              type="button"
              onClick={onClose}
              disabled={loading}
              className="w-full sm:w-auto px-6 py-2.5 rounded-lg font-medium text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors text-sm"
            >
              Cancelar
            </button>
            <button 
              type="submit"
              disabled={loading}
              className="w-full sm:w-auto relative px-6 py-2.5 rounded-lg font-medium text-white overflow-hidden group transition-all text-sm"
            >
              <div className={`absolute inset-0 bg-gradient-to-r ${mode === "auto" ? "from-purple-600 to-indigo-800" : "from-purple-600 to-pink-600"} opacity-90 group-hover:opacity-100 transition-opacity`} />
              <span className="relative flex items-center justify-center gap-2">
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
                    {file ? <CheckCircle2 className="w-4 h-4" /> : <Upload className="w-4 h-4" />}
                    {file ? `Procesar y Subir: ${file.name.substring(0, 15)}...` : "Seleccionar Archivo y Continuar"}
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
