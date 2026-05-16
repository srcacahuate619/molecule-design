import React from 'react';
import { motion } from 'framer-motion';
// import { MoleculeMetadata } from '../lib/types';
import { Microscope, Activity, ShieldCheck, Zap } from 'lucide-react';

interface PokedexCardProps {
  molecule: any;
  onClick: (id: string) => void;
  isSelected: boolean;
  onCompareToggle: () => void;
  isComparing: boolean;
}

const PokedexCard: React.FC<PokedexCardProps> = ({ molecule, onClick, isSelected, onCompareToggle, isComparing }) => {
  const getQualityColor = (score: number) => {
    if (score >= 95) return 'text-yellow-400 border-yellow-500/50 bg-yellow-500/20 shadow-[0_0_10px_rgba(234,179,8,0.3)] font-black italic'; // DORADO (Legendary)
    if (score >= 80) return 'text-fuchsia-400 border-fuchsia-500/30 bg-fuchsia-500/10'; // MORADO (Exceptional)
    if (score >= 60) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'; // VERDE (High Quality)
    if (score >= 40) return 'text-amber-400 border-amber-500/30 bg-amber-500/10'; // AMARILLO (Medium)
    return 'text-rose-400 border-rose-500/30 bg-rose-500/10'; // ROJO (Low)
  };

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
      {/* Badge de Target */}
      <div className="absolute top-3 right-3 flex items-center gap-1 rounded-full bg-slate-950/80 px-2 py-0.5 text-[10px] font-bold tracking-wider text-slate-400 border border-slate-700">
        <Microscope size={10} />
        {molecule.target.pdb_id}
      </div>

      <div className="mb-4 flex h-32 items-center justify-center rounded-xl bg-gradient-to-br from-slate-950 to-slate-900 p-2 shadow-inner">
        {/* Placeholder para la imagen 2D (SMILES render) */}
        <div className="text-center opacity-30">
          <Activity size={40} className="mx-auto mb-2 text-indigo-400" />
          <span className="text-[10px] font-mono">{molecule.smiles_hash.substring(0, 8)}</span>
        </div>
      </div>

      <div className="space-y-2">
        <h3 className="truncate text-sm font-bold text-slate-100">{molecule.name}</h3>
        
        <div className="flex items-center justify-between">
          <div className={`flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-bold ${getQualityColor(molecule.metrics.score)}`}>
            <Zap size={12} fill="currentColor" />
            {molecule.metrics.score.toFixed(1)}
          </div>
          
          {molecule.blockchain.certified && (
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
          layoutId="pokedex-active-glow"
          className="absolute -inset-1 rounded-2xl bg-indigo-500/10 blur-xl -z-10"
        />
      )}
    </motion.div>
  );
};

export default PokedexCard;
