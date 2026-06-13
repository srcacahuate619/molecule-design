"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../lib/auth";
import { Menu, X, LogOut, User as UserIcon } from "lucide-react";
import { useState } from "react";
import Image from "next/image";
import { useInterface } from "../context/InterfaceContext";

const NAV_ITEMS = [
  { href: "/", label: "Inicio" },
  { href: "/evaluation", label: "Evaluación" },
  { href: "/moldex", label: "Moldex" },
];

export function Navigation() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const { interfaceMode, toggleInterfaceMode } = useInterface();

  return (
    <nav className="sticky top-0 z-[100] border-b border-surface-800 bg-surface-950/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 text-lg font-bold text-white">
          <Image src="/logo.png" alt="MolDesign AI Logo" width={32} height={32} className="rounded-lg object-contain" />
          MolDesign AI
        </Link>

        {/* Mobile Menu Button */}
        <button 
          className="md:hidden p-2 text-surface-400 hover:text-white"
          onClick={() => setIsOpen(!isOpen)}
        >
          {isOpen ? <X size={24} /> : <Menu size={24} />}
        </button>

        {/* Desktop Nav Links + Switch */}
        <div className="hidden md:flex items-center gap-6">
          <div className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-brand-600/20 text-brand-400"
                      : "text-surface-400 hover:bg-surface-800 hover:text-gray-200"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>

          {/* Interface Switch (Gamer vs Pro) */}
          <div className="flex items-center bg-surface-900/60 border border-surface-800 rounded-full p-0.5 relative cursor-pointer h-7 select-none" onClick={toggleInterfaceMode}>
            <div className={`absolute top-0.5 bottom-0.5 rounded-full bg-brand-600/80 transition-all duration-300 ease-out ${interfaceMode === 'GAMIFIED' ? 'left-0.5 w-[85px]' : 'left-[88px] w-[65px]'}`} />
            <span className={`text-[9px] font-black uppercase tracking-widest px-2.5 py-1 z-10 select-none transition-colors leading-none flex items-center justify-center ${interfaceMode === 'GAMIFIED' ? 'text-white' : 'text-surface-500'}`}>📚 Edu</span>
            <span className={`text-[9px] font-black uppercase tracking-widest px-2.5 py-1 z-10 select-none transition-colors leading-none flex items-center justify-center ${interfaceMode === 'PRO' ? 'text-white' : 'text-surface-500'}`}>🔬 Pro</span>
          </div>
        </div>

        {/* Desktop Auth */}
        <div className="hidden md:flex items-center gap-3">
          {user ? (
            <>
              <span className="text-sm text-surface-400">
                {user.username}
              </span>
              <button
                onClick={logout}
                className="rounded-lg border border-surface-700 px-3 py-1.5 text-sm text-surface-400 transition-colors hover:border-red-700 hover:text-red-400"
              >
                Salir
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-700"
            >
              Entrar
            </Link>
          )}
        </div>
      </div>

      {/* Mobile Menu Modal */}
      {isOpen && (
        <div className="fixed inset-0 z-[200] md:hidden animate-in fade-in duration-200">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={() => setIsOpen(false)} />
          
          {/* Modal Centrado Absoluto */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[90vw] max-w-sm bg-[#05080f] border border-white/10 rounded-3xl shadow-2xl flex flex-col animate-in zoom-in-95 duration-300">
            
            <div className="flex items-center justify-between px-6 py-5 border-b border-white/5 bg-black/40">
              <span className="text-xs font-black text-white tracking-[0.2em] uppercase flex items-center gap-2">
                <Menu size={16} className="text-brand-500" /> Navegación
              </span>
              <button onClick={() => setIsOpen(false)} className="p-2 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white rounded-xl transition-all">
                <X size={18} />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Conmutador de Interfaz Móvil */}
              <div className="flex items-center justify-between border-b border-surface-800/50 pb-4">
                <span className="text-[10px] font-black text-surface-400 uppercase tracking-widest">Modo de Vista</span>
                <div className="flex items-center bg-surface-900 border border-surface-800 rounded-full p-0.5 relative cursor-pointer h-8 select-none w-[160px]" onClick={toggleInterfaceMode}>
                  <div className={`absolute top-0.5 bottom-0.5 rounded-full bg-brand-600/80 transition-all duration-300 ease-out ${interfaceMode === 'GAMIFIED' ? 'left-0.5 w-[85px]' : 'left-[88px] w-[68px]'}`} />
                  <span className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-1 z-10 select-none transition-colors leading-none flex items-center justify-center h-full ${interfaceMode === 'GAMIFIED' ? 'text-white' : 'text-surface-500'}`}>📚 Edu</span>
                  <span className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-1 z-10 select-none transition-colors leading-none flex items-center justify-center h-full ${interfaceMode === 'PRO' ? 'text-white' : 'text-surface-500'}`}>🔬 Pro</span>
                </div>
              </div>

              <div className="flex flex-col gap-3">
                {NAV_ITEMS.map((item) => {
                  const isActive = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setIsOpen(false)}
                      className={`flex items-center gap-3 rounded-2xl px-5 py-4 text-sm font-bold transition-all ${
                        isActive
                          ? "bg-brand-600 text-white shadow-[0_0_20px_rgba(79,70,229,0.3)] border border-brand-500/50"
                          : "text-surface-300 bg-surface-900/50 border border-white/5 hover:bg-surface-800"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
              
              <div className="pt-4 border-t border-surface-800/50">
                {user ? (
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center justify-center gap-3 px-4 py-3 bg-black/40 rounded-2xl border border-white/5">
                      <div className="h-10 w-10 rounded-full bg-surface-800 flex items-center justify-center text-brand-400 border border-white/5">
                        <UserIcon size={20} />
                      </div>
                      <span className="text-sm font-black text-white tracking-widest uppercase">{user.username}</span>
                    </div>
                    <button
                      onClick={() => { logout(); setIsOpen(false); }}
                      className="flex items-center justify-center gap-2 w-full rounded-2xl bg-red-950/30 border border-red-900/50 py-4 text-xs font-black tracking-widest uppercase text-red-400 hover:bg-red-900/40 transition-all"
                    >
                      <LogOut size={16} /> Salir de Sesión
                    </button>
                  </div>
                ) : (
                  <Link
                    href="/login"
                    onClick={() => setIsOpen(false)}
                    className="flex items-center justify-center w-full rounded-2xl bg-brand-600 py-4 text-xs font-black uppercase tracking-widest text-white shadow-lg shadow-brand-600/20 hover:bg-brand-500 transition-all"
                  >
                    Entrar a la Plataforma
                  </Link>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}

