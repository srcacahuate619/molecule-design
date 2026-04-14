import "./globals.css";
import type { ReactNode } from "react";
import Script from "next/script";
import { AuthProvider } from "@/lib/auth";
import { Navigation } from "@/components/Navigation";

export const metadata = {
  title: "MolDesign — Diseño Molecular Asistido por IA",
  description:
    "Pipeline científico reproducible: RDKit → AutoDock Vina → DiffDock → AlphaFold → Scoring Compuesto",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        {/* 3Dmol.js: carga anticipada para viewer 3D */}
        <Script
          src="https://3dmol.org/build/3Dmol-min.js"
          strategy="beforeInteractive"
        />
      </head>
      <body>
        <AuthProvider>
          <Navigation />
          <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
