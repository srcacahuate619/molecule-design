import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Microscope, Activity, ShieldCheck, Zap } from 'lucide-react';
import { API_URL } from '../lib/config';

interface MoldexCardProps {
  molecule: any;
  onClick: (id: string) => void;
  isSelected: boolean;
  onCompareToggle: () => void;
  isComparing: boolean;
}

const MoldexCard: React.FC<MoldexCardProps> = ({ molecule, onClick, isSelected, onCompareToggle, isComparing }) => {
  const [imgSrc, setImgSrc] = useState<string | undefined>(undefined);
  
  useEffect(() => {
    fetch(`${API_URL}/chem/render/${molecule.id}`, {
      headers: { "ngrok-skip-browser-warning": "true" }
    })
    .then(res => {
      if (!res.ok) throw new Error("Image fetch failed");
      return res.blob();
    })
    .then(blob => setImgSrc(URL.createObjectURL(blob)))
    .catch(() => setImgSrc(""));
  }, [molecule.id]);

  const getQualityColor = (score: number) => {
    if (score >= 95) return 'text-yellow-400 border-yellow-500/50 bg-yellow-500/20 shadow-[0_0_10px_rgba(234,179,8,0.3)] font-black italic'; // DORADO (Legendary)
    if (score >= 80) return 'text-fuchsia-400 border-fuchsia-500/30 bg-fuchsia-500/10'; // MORADO (Exceptional)
    if (score >= 60) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'; // VERDE (High Quality)
    if (score >= 40) return 'text-amber-400 border-amber-500/30 bg-amber-500/10'; // AMARILLO (Medium)
    return 'text-rose-400 border-rose-500/30 bg-rose-500/10'; // ROJO (Low)
  };

  const targetBasedName = `MDX-${molecule.target?.pdb_id || "UKN"}-${molecule.smiles_hash.substring(0,4).toUpperCase()}`;
  const isDefaultName = !molecule.name || molecule.name.startsWith("Ligando ");
  const displayName = isDefaultName ? targetBasedName : molecule.name;

  return (
    <motion.div
      whileHover={{ y: -5, scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={() => onClick(molecule.id)}
      className={`relative cursor-pointer rounded-2xl border p-4 transition-all duration-300 ${
        isSelected 
          ? 'border-indigo-500 bg-indigo-500/20 shadow-[0_0_20px_rgba(99,102,241,0.3)]' 
          : 'border-slate-800 bg-slate-900/50 hover:bg-slate-800/80'
      }`}
    >
      {/* Badge de Tier (Gamer Rank) */}
      {molecule.metrics?.score !== undefined && (
        <div className={`absolute top-3 left-3 flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-black tracking-widest border ${
          molecule.metrics.score >= 85 ? 'text-amber-400 border-amber-500/50 bg-amber-500/10 shadow-[0_0_8px_rgba(245,158,11,0.2)]' :
          molecule.metrics.score >= 70 ? 'text-fuchsia-400 border-fuchsia-500/30 bg-fuchsia-500/10' :
          molecule.metrics.score >= 55 ? 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10' :
          molecule.metrics.score >= 40 ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' :
          'text-rose-400 border-rose-500/30 bg-rose-500/10'
        }`}>
          {molecule.metrics.score >= 85 ? 'S-Tier' :
           molecule.metrics.score >= 70 ? 'A-Tier' :
           molecule.metrics.score >= 55 ? 'B-Tier' :
           molecule.metrics.score >= 40 ? 'C-Tier' :
           'D-Tier'}
        </div>
      )}

      {/* Badge de Target */}
      <div className="absolute top-3 right-3 flex items-center gap-1 rounded-full bg-slate-950/80 px-2 py-0.5 text-[10px] font-bold tracking-wider text-slate-400 border border-slate-700">
        <Microscope size={10} />
        {molecule.target?.pdb_id || "N/A"}
      </div>

      <div className="mb-4 flex h-32 items-center justify-center rounded-xl bg-white p-4 shadow-inner relative overflow-hidden group/img">
        {/* Render 2D de la molécula real */}
        <img 
          src={imgSrc || `${API_URL}/chem/render/${molecule.id}`}
          alt={molecule.name}
          className="h-full w-auto object-contain transition-transform duration-500 group-hover/img:scale-110"
          loading="lazy"
          onError={(e) => {
            // Fallback en caso de error de renderizado
            (e.target as any).style.display = 'none';
          }}
        />
        
        <div className="absolute bottom-2 right-2 bg-slate-900/80 backdrop-blur-md px-2 py-1 rounded text-[9px] font-mono font-bold text-slate-300 border border-slate-700/50 shadow-sm">
          {targetBasedName}
        </div>
      </div>

      <div className="space-y-2">
        <h3 className="truncate text-sm font-bold text-slate-100">{displayName}</h3>
        
        <div className="flex items-center justify-between">
          <div className={`flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-bold ${getQualityColor(molecule.metrics?.score || 0)}`}>
            <Zap size={12} fill="currentColor" />
            {molecule.metrics?.score?.toFixed(1) || "0.0"}
          </div>
          
          {molecule.blockchain?.certified && (
            <div className="flex items-center gap-1 text-[10px] font-bold text-indigo-400">
              <ShieldCheck size={12} />
              CERTIFIED
            </div>
          )}
        </div>

        <button 
          onClick={(e) => { e.stopPropagation(); onCompareToggle(); }}
          className={`w-full mt-2 py-1 rounded-lg border text-[9px] font-black tracking-widest transition-all ${
            isComparing 
              ? 'bg-indigo-500 border-indigo-400 text-white' 
              : 'border-slate-800 text-slate-500 hover:border-slate-700 hover:text-slate-300'
          }`}
        >
          {isComparing ? 'SELECCIONADO PARA COMPARAR' : 'COMPARAR'}
        </button>
      </div>

      {isSelected && (
        <motion.div 
          layoutId="moldex-active-glow"
          className="absolute -inset-1 rounded-2xl bg-indigo-500/10 blur-xl -z-10"
        />
      )}
    </motion.div>
  );
};

export default MoldexCard;
