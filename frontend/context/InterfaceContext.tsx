"use client";
import React, { createContext, useContext, useState, useEffect } from "react";

type InterfaceMode = "GAMIFIED" | "PRO";

interface InterfaceContextProps {
  interfaceMode: InterfaceMode;
  setInterfaceMode: (mode: InterfaceMode) => void;
  toggleInterfaceMode: () => void;
}

const InterfaceContext = createContext<InterfaceContextProps | undefined>(undefined);

export function InterfaceProvider({ children }: { children: React.ReactNode }) {
  const [interfaceMode, setInterfaceMode] = useState<InterfaceMode>("GAMIFIED");

  useEffect(() => {
    const saved = localStorage.getItem("moldesign_interface_mode");
    if (saved === "GAMIFIED" || saved === "PRO") {
      setInterfaceMode(saved);
    }
  }, []);

  const changeMode = (mode: InterfaceMode) => {
    setInterfaceMode(mode);
    localStorage.setItem("moldesign_interface_mode", mode);
  };

  const toggleInterfaceMode = () => {
    const next = interfaceMode === "GAMIFIED" ? "PRO" : "GAMIFIED";
    changeMode(next);
  };

  return (
    <InterfaceContext.Provider value={{ interfaceMode, setInterfaceMode: changeMode, toggleInterfaceMode }}>
      {children}
    </InterfaceContext.Provider>
  );
}

export function useInterface() {
  const context = useContext(InterfaceContext);
  if (!context) {
    throw new Error("useInterface must be used within an InterfaceProvider");
  }
  return context;
}
