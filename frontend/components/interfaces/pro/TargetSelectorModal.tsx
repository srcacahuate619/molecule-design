"use client";

import React, { useState, useMemo } from "react";
import { X, Search, Database, Fingerprint, Activity, Crosshair } from "lucide-react";
import type { Target } from "../../../lib/api";
import { shareCustomTarget } from "../../../lib/api";
import { CustomReceptorModal } from "./CustomReceptorModal";

interface TargetSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  targets: Target[];
  onSelect: (pdbId: string) => void;
  selectedTargetId: string | null;
  onTargetUploadSuccess?: () => void;
}

export default function TargetSelectorModal({
  isOpen,
  onClose,
  targets,
  onSelect,
  selectedTargetId,
  onTargetUploadSuccess
}: TargetSelectorModalProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [showCustomModal, setShowCustomModal] = useState(false);
  const [activeTab, setActiveTab] = useState<"oficiales" | "propios" | "comunidad">("oficiales");

  const handleShareTarget = async (id: string) => {
    try {
      const res = await shareCustomTarget(id);
      if (res.success && onTargetUploadSuccess) {
        onTargetUploadSuccess();
        alert("¡Receptor compartido con la comunidad exitosamente!");
      }
    } catch (err: any) {
      alert("Error al compartir receptor: " + (err.message || err));
    }
  };

  // Categorize targets by structural_family and filter by search term and tab
  const groupedTargets = useMemo(() => {
    const term = searchTerm.toLowerCase();
    
    // Obtener los IDs de targets propios del localStorage
    const ownTargetIds: string[] = [];
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("moldesign_custom_targets");
        if (stored) {
          const parsed = JSON.parse(stored);
          if (Array.isArray(parsed)) {
            ownTargetIds.push(...parsed.map((id: string) => id.toLowerCase()));
          }
        }
      } catch {}
    }

    // Filter by active tab
    let tabTargets = targets;
    if (activeTab === "oficiales") {
      tabTargets = targets.filter(t => !t.is_private && !t.is_community);
    } else if (activeTab === "propios") {
      tabTargets = targets.filter(t => t.is_private || (t.id && ownTargetIds.includes(t.id.toLowerCase())) || (t.pdb_id && ownTargetIds.includes(t.pdb_id.toLowerCase())));
    } else if (activeTab === "comunidad") {
      tabTargets = targets.filter(t => t.is_community);
    }

    const filtered = tabTargets.filter(t => 
      (t.name || "").toLowerCase().includes(term) || 
      (t.pdb_id || "").toLowerCase().includes(term) || 
      (t.organism && t.organism.toLowerCase().includes(term))
    );

    const groups: Record<string, Target[]> = {};
    filtered.forEach(t => {
      const family = t.structural_family || "Otra / No Clasificada";
      if (!groups[family]) groups[family] = [];
      groups[family].push(t);
    });

    return groups;
  }, [targets, searchTerm, activeTab]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 lg:p-8 animate-in fade-in duration-200">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/30 backdrop-blur-md"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div className="relative w-full max-w-5xl h-[85vh] bg-slate-950 border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        
        {/* Header */}
        <div className="flex-none px-6 py-5 border-b border-white/10 bg-slate-900/50 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-black text-white uppercase tracking-wider flex items-center gap-2">
                <Database className="text-indigo-400" size={20} />
                Catálogo de Receptores
              </h2>
              <p className="text-[11px] text-slate-500 font-medium uppercase tracking-widest mt-1">
                Selecciona una estructura biológica para la simulación de acoplamiento molecular
              </p>
            </div>
            <button 
              onClick={onClose}
              className="p-2 bg-white/5 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 rounded-xl transition-colors duration-200"
            >
              <X size={20} />
            </button>
          </div>

          {/* Search Bar & Actions */}
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 w-full">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
              <input
                type="text"
                placeholder="Buscar por PDB ID, nombre de la proteína, o familia..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-[#03060c] border border-white/10 rounded-xl py-3 pl-10 pr-4 text-sm text-white placeholder-slate-600 outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/50 transition-all duration-200"
              />
            </div>
            <button 
              onClick={() => setShowCustomModal(true)}
              className="w-full sm:w-auto px-6 py-3 rounded-xl font-bold bg-gradient-to-r from-purple-600 to-indigo-850 hover:shadow-[0_0_15px_rgba(168,85,247,0.4)] text-white transition-all flex items-center justify-center gap-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              Subir Receptor
            </button>
          </div>

          {/* Tabs Navigation (LM Studio Style) */}
          <div className="flex border-b border-white/5 pt-1">
            <button
              onClick={() => setActiveTab("oficiales")}
              className={`pb-3 px-4 text-xs font-black uppercase tracking-wider border-b-2 transition-all ${
                activeTab === "oficiales"
                  ? "border-indigo-500 text-indigo-400"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              🌐 Receptores Oficiales
            </button>
            <button
              onClick={() => setActiveTab("propios")}
              className={`pb-3 px-4 text-xs font-black uppercase tracking-wider border-b-2 transition-all ${
                activeTab === "propios"
                  ? "border-purple-500 text-purple-400"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              💾 Mis Receptores
            </button>
            <button
              onClick={() => setActiveTab("comunidad")}
              className={`pb-3 px-4 text-xs font-black uppercase tracking-wider border-b-2 transition-all ${
                activeTab === "comunidad"
                  ? "border-purple-500 text-purple-400"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              👥 Comunidad Científica
            </button>
          </div>
        </div>

        {/* Content (Scrollable list of categories and cards) */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8 scrollbar-thin scrollbar-thumb-indigo-500/20 scrollbar-track-transparent">
          {Object.keys(groupedTargets).length === 0 ? (
            <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 space-y-3 py-10">
              <Crosshair size={40} className="opacity-20" />
              <p className="text-sm font-semibold uppercase tracking-wider">No se encontraron receptores en esta sección</p>
            </div>
          ) : (
            Object.keys(groupedTargets).sort().map(family => (
              <div key={family} className="space-y-4">
                <div className="flex items-center gap-3">
                  <h3 className="text-xs font-black text-indigo-400 uppercase tracking-[0.2em]">
                    {family}
                  </h3>
                  <div className="flex-1 h-px bg-gradient-to-r from-indigo-500/20 to-transparent" />
                  <span className="text-[10px] font-bold text-slate-600 uppercase">
                    {groupedTargets[family].length} OBJETIVOS
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {groupedTargets[family].map(target => {
                    const isSelected = 
                      (target.pdb_id && selectedTargetId && target.pdb_id.toLowerCase() === selectedTargetId.toLowerCase()) ||
                      (target.id && selectedTargetId && target.id.toLowerCase() === selectedTargetId.toLowerCase());
                    return (
                      <div 
                        key={target.pdb_id || target.id}
                        onClick={() => {
                          onSelect(target.pdb_id || target.id || "");
                          onClose();
                        }}
                        className={`group relative flex flex-col p-4 rounded-xl border cursor-pointer transition-all duration-300 ${
                          isSelected 
                            ? "bg-indigo-600/10 border-indigo-500 shadow-[0_0_20px_rgba(99,102,241,0.15)]" 
                            : "bg-black/40 border-white/5 hover:border-indigo-500/30 hover:bg-indigo-950/20"
                        }`}
                      >
                        {isSelected && (
                          <div className="absolute top-0 right-0 p-1">
                            <div className="bg-indigo-500 text-[8px] font-black uppercase px-2 py-0.5 rounded-bl-lg rounded-tr-lg text-white">
                              Activo
                            </div>
                          </div>
                        )}
                        <div className="flex justify-between items-start mb-1 gap-2">
                          <h4 className="text-sm font-bold text-white tracking-wide line-clamp-2 h-10 flex-1 leading-snug">
                            {target.name}
                          </h4>
                          <span className="text-[9px] px-2 py-1 bg-white/5 rounded-md font-bold text-slate-400 uppercase whitespace-nowrap shrink-0">
                            {target.organism || "Desconocido"}
                          </span>
                        </div>
                        
                        <div className="flex items-center gap-2 mb-4">
                          <span className="text-[10px] font-mono text-slate-500 font-bold bg-white/5 px-1.5 py-0.5 rounded">
                            {target.pdb_id}
                          </span>
                          {target.structural_family && (
                            <span className="text-[9px] font-black text-indigo-400/80 uppercase tracking-wider">
                              {target.structural_family}
                            </span>
                          )}
                        </div>

                        <div className="mt-auto grid grid-cols-2 gap-2">
                          <div className="flex items-center gap-1.5 p-2 rounded-lg bg-black/40 border border-white/5">
                            <Activity size={12} className="text-emerald-400" />
                            <div className="flex flex-col">
                              <span className="text-[8px] text-slate-500 uppercase font-bold">Spearman ρ</span>
                              <span className="text-[10px] text-white font-mono font-black">
                                {target.spearman_rho != null ? target.spearman_rho.toFixed(3) : "N/A"}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 p-2 rounded-lg bg-black/40 border border-white/5">
                            <Fingerprint size={12} className="text-cyan-400" />
                            <div className="flex flex-col">
                              <span className="text-[8px] text-slate-500 uppercase font-bold">Resolución</span>
                              <span className="text-[10px] text-white font-mono font-black">
                                {target.resolution ? `${target.resolution.toFixed(2)} Å` : "N/A"}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Credits for author / Share button */}
                        {activeTab === "propios" && !target.is_community ? (
                          <div className="mt-3 pt-2 border-t border-white/5 flex items-center justify-between text-[9px] font-bold uppercase tracking-wider">
                            <span className="text-slate-500">Privado</span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleShareTarget(target.id || target.pdb_id);
                              }}
                              className="px-2 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-black text-[8px] uppercase tracking-widest transition-colors cursor-pointer"
                            >
                              Compartir con Comunidad
                            </button>
                          </div>
                        ) : target.creator_username ? (
                          <div className="mt-3 pt-2 border-t border-white/5 flex items-center justify-between text-[9px] text-slate-500 font-bold uppercase tracking-wider">
                            <span>Colaborador:</span>
                            <span className="text-cyan-400">@{target.creator_username}</span>
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
      
      {showCustomModal && (
        <CustomReceptorModal 
          onClose={() => setShowCustomModal(false)} 
          onSuccess={() => {
            setShowCustomModal(false);
            if (onTargetUploadSuccess) onTargetUploadSuccess();
          }} 
        />
      )}
    </div>
  );
}
