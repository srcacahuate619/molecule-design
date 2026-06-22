import "./globals.css";
import type { ReactNode } from "react";
import Script from "next/script";
import { AuthProvider } from "../lib/auth";
import { Navigation } from "../components/Navigation";
import { InterfaceProvider } from "../context/InterfaceContext";
import { WalletProvider } from "../components/WalletProvider";

export const metadata = {
  title: "MolDesign AI — Diseño Molecular Gamificado y Avanzado",
  description:
    "Pipeline científico avanzado de 3 niveles: Screening Vina+XGBoost (Nivel 1), Redes de Grafos RTMScore GNN (Nivel 2) y Refinamiento Físico OpenMM/AMBER (Nivel 3). Certificación Solana.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&family=Space+Grotesk:wght@400;600;700&display=swap"
          rel="stylesheet"
        />
        {/* 3Dmol.js: carga anticipada para viewer 3D */}
        <Script
          src="https://3dmol.org/build/3Dmol-min.js"
          strategy="beforeInteractive"
        />
        {/* GEO Optimization: JSON-LD Schema para buscadores y LLMs */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "SoftwareApplication",
              "name": "MolDesign AI",
              "applicationCategory": "ScienceApplication",
              "operatingSystem": "Web",
              "description": "Plataforma de descubrimiento de fármacos asistida por IA con validación química RDKit, docking AutoDock Vina, rescoring XGBoost y topología GNN RTMScore.",
              "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "USD"
              }
            })
          }}
        />
      </head>
      <body>
        <WalletProvider>
          <AuthProvider>
            <InterfaceProvider>
              <Navigation />
              <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
            </InterfaceProvider>
          </AuthProvider>
        </WalletProvider>
      </body>
    </html>
  );
}
