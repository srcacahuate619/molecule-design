"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Menu, X, LogOut, User as UserIcon } from "lucide-react";
import { useState } from "react";
import Image from "next/image";
import { useInterface } from "@/context/InterfaceContext";

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
            <span className={`text-[9px] font-black uppercase tracking-widest px-2.5 py-1 z-10 select-none transition-colors leading-none flex items-center justify-center ${interfaceMode === 'GAMIFIED' ? 'text-white' : 'text-surface-500'}`}>🕹️ Gamer</span>
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

      {/* Mobile Menu Dropdown */}
      {isOpen && (
        <div className="md:hidden border-t border-surface-800 bg-surface-950 px-4 py-4 space-y-3 animate-in slide-in-from-top-4 duration-200">
          {/* Conmutador de Interfaz Móvil */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-surface-800 pb-3">
            <span className="text-[10px] font-black text-surface-400 uppercase tracking-widest">Modo de Vista</span>
            <div className="flex items-center bg-surface-900 border border-surface-800 rounded-full p-0.5 relative cursor-pointer h-7 select-none w-[155px]" onClick={toggleInterfaceMode}>
              <div className={`absolute top-0.5 bottom-0.5 rounded-full bg-brand-600/80 transition-all duration-300 ease-out ${interfaceMode === 'GAMIFIED' ? 'left-0.5 w-[85px]' : 'left-[88px] w-[65px]'}`} />
              <span className={`text-[9px] font-black uppercase tracking-widest px-2.5 py-1 z-10 select-none transition-colors leading-none flex items-center justify-center h-full ${interfaceMode === 'GAMIFIED' ? 'text-white' : 'text-surface-500'}`}>🕹️ Gamer</span>
              <span className={`text-[9px] font-black uppercase tracking-widest px-2.5 py-1 z-10 select-none transition-colors leading-none flex items-center justify-center h-full ${interfaceMode === 'PRO' ? 'text-white' : 'text-surface-500'}`}>🔬 Pro</span>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setIsOpen(false)}
                  className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-bold transition-all ${
                    isActive
                      ? "bg-brand-600 text-white shadow-lg shadow-brand-600/20"
                      : "text-surface-400 bg-surface-900/50"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
          
          <div className="pt-4 border-t border-surface-800">
            {user ? (
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-3 px-4 py-2">
                  <div className="h-8 w-8 rounded-full bg-surface-800 flex items-center justify-center text-brand-400">
                    <UserIcon size={16} />
                  </div>
                  <span className="text-sm font-bold text-white">{user.username}</span>
                </div>
                <button
                  onClick={() => { logout(); setIsOpen(false); }}
                  className="flex items-center justify-center gap-2 w-full rounded-xl bg-red-950/30 border border-red-900/50 py-3 text-sm font-bold text-red-400"
                >
                  <LogOut size={16} /> Salir
                </button>
              </div>
            ) : (
              <Link
                href="/login"
                onClick={() => setIsOpen(false)}
                className="flex items-center justify-center w-full rounded-xl bg-brand-600 py-4 text-sm font-bold text-white shadow-lg shadow-brand-600/20"
              >
                Entrar a la Plataforma
              </Link>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}

