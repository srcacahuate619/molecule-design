import React from 'react';
import { motion } from 'framer-motion';
import { Microscope, ArrowLeftRight, Zap, Info } from 'lucide-react';

interface ComparisonProps {
  molA: any;
  molB: any;
  onClose: () => void;
}

const MolecularComparison: React.FC<ComparisonProps> = ({ molA, molB, onClose }) => {
  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/90 backdrop-blur-md p-8"
    >
      <div className="relative w-full max-w-6xl rounded-3xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
        <button 
          onClick={onClose}
          className="absolute top-6 right-6 rounded-full bg-slate-800 p-2 text-slate-400 hover:text-white transition-colors"
        >
          <Microscope size={20} className="rotate-45" />
        </button>

        <h2 className="text-3xl font-black text-white mb-8 flex items-center gap-4">
          <ArrowLeftRight className="text-indigo-500" /> COMPARADOR DE LIGANDOS
        </h2>

        <div className="grid grid-cols-2 gap-12">
          {/* Molécula A */}
          <div className="space-y-6">
            <div className="h-64 rounded-2xl bg-slate-950 border border-slate-800 p-4">
               {/* Visor 3D A placeholder */}
               <div className="flex h-full items-center justify-center text-slate-700 font-bold uppercase tracking-widest text-xs">
                 [ Visor 3D: {molA.name} ]
               </div>
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-bold text-white">{molA.name}</h3>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1 text-indigo-400 font-black">
                  <Zap size={14} fill="currentColor" /> {molA.metrics.affinity.toFixed(2)}
                </div>
                <div className="text-xs text-slate-500 font-bold uppercase">{molA.target.pdb_id}</div>
              </div>
            </div>
          </div>

          {/* Molécula B */}
          <div className="space-y-6">
            <div className="h-64 rounded-2xl bg-slate-950 border border-slate-800 p-4">
               {/* Visor 3D B placeholder */}
               <div className="flex h-full items-center justify-center text-slate-700 font-bold uppercase tracking-widest text-xs">
                 [ Visor 3D: {molB.name} ]
               </div>
            </div>
            <div className="space-y-2 text-right">
              <h3 className="text-xl font-bold text-white">{molB.name}</h3>
              <div className="flex items-center gap-4 justify-end">
                <div className="text-xs text-slate-500 font-bold uppercase">{molB.target.pdb_id}</div>
                <div className="flex items-center gap-1 text-emerald-400 font-black">
                  <Zap size={14} fill="currentColor" /> {molB.metrics.affinity.toFixed(2)}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Tabla Comparativa */}
        <div className="mt-12 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/50">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-800/50 text-[10px] font-bold uppercase tracking-widest text-slate-500">
              <tr>
                <th className="px-6 py-3">PROPIEDAD</th>
                <th className="px-6 py-3 text-center">{molA.smiles_hash.substring(0,8)}</th>
                <th className="px-6 py-3 text-center">DIFERENCIA</th>
                <th className="px-6 py-3 text-center">{molB.smiles_hash.substring(0,8)}</th>
              </tr>
            </thead>
            <tbody className="text-slate-300 font-mono text-xs">
              {[
                { label: "LOG P", valA: molA.metrics.log_p, valB: molB.metrics.log_p },
                { label: "PESO MOL.", valA: molA.metrics.mw, valB: molB.metrics.mw },
                { label: "TPSA", valA: molA.metrics.tpsa, valB: molB.metrics.tpsa },
                { label: "SCORE", valA: molA.metrics.score, valB: molB.metrics.score },
              ].map(row => (
                <tr key={row.label} className="border-t border-slate-800/50 hover:bg-slate-800/20 transition-colors">
                  <td className="px-6 py-4 font-bold text-slate-500 font-sans">{row.label}</td>
                  <td className="px-6 py-4 text-center">{row.valA.toFixed(2)}</td>
                  <td className="px-6 py-4 text-center font-bold">
                    <span className={row.valB > row.valA ? 'text-emerald-400' : 'text-rose-400'}>
                      {row.valB > row.valA ? '+' : ''}{(row.valB - row.valA).toFixed(2)}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-center">{row.valB.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  );
};

export default MolecularComparison;
