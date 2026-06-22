"use client";

import React, { useEffect, useState, useRef } from "react";
import { fetchCertificateBlobUrl, downloadCertificate } from "../lib/api";
import { Download, Maximize, FileText, Loader2, ShieldCheck, AlertCircle } from "lucide-react";
import { CertificationModal } from "./CertificationModal";

interface PDFReportViewerProps {
  moleculeId: string;
  isCertified: boolean;
  onCertify?: () => void;
  isCertifying?: boolean;
}

export function PDFReportViewer({ moleculeId, isCertified, onCertify, isCertifying = false }: PDFReportViewerProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    let url = "";

    async function loadPdf() {
      setIsLoading(true);
      setError(null);
      try {
        url = await fetchCertificateBlobUrl(moleculeId);
        if (active) {
          setBlobUrl(url);
          setIsLoading(false);
        }
      } catch (err: any) {
        if (active) {
          setError(err.message || "Error al cargar el reporte");
          setIsLoading(false);
        }
      }
    }

    loadPdf();

    return () => {
      active = false;
      if (url) {
        URL.revokeObjectURL(url);
      }
    };
  }, [moleculeId, isCertified]);

  if (isLoading) {
    return (
      <div className="w-full h-full min-h-[400px] flex flex-col items-center justify-center bg-surface-900 border border-surface-800 rounded-lg">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-4" />
        <div className="text-surface-400 font-mono text-xs uppercase tracking-wider">Desencriptando Blob...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-full min-h-[400px] flex flex-col items-center justify-center bg-red-500/5 border border-red-500/20 rounded-lg p-6 text-center">
        <AlertCircle className="w-10 h-10 text-red-400 mb-4" />
        <div className="text-red-400 font-bold mb-2">Error de Carga</div>
        <div className="text-surface-400 text-sm max-w-md">{error}</div>
      </div>
    );
  }

  return (
    <>
      <div ref={containerRef} className="flex flex-col w-full h-full min-h-[500px] bg-surface-950 border border-surface-800 rounded-lg overflow-hidden relative">
        {/* Premium Toolbar */}
        <div className="flex items-center justify-between px-4 py-3 bg-surface-900 border-b border-surface-800 z-10 shadow-sm relative">
          <div className="flex items-center gap-3">
            <FileText className="w-4 h-4 text-brand-400" />
            <span className="font-mono text-xs text-surface-300 tracking-wider">MD_{moleculeId.split('-')[0].toUpperCase()}.PDF</span>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (containerRef.current) {
                  if (document.fullscreenElement) {
                    document.exitFullscreen();
                  } else {
                    containerRef.current.requestFullscreen();
                  }
                }
              }}
              className="p-1.5 text-surface-400 hover:text-white hover:bg-surface-800 rounded transition-colors"
              title="Pantalla Completa"
            >
              <Maximize className="w-4 h-4" />
            </button>
            
            <div className="w-px h-4 bg-surface-700 mx-1" />
            
            <button
              onClick={() => downloadCertificate(moleculeId)}
              className="flex items-center gap-2 px-3 py-1.5 bg-surface-800 hover:bg-brand-500 hover:text-surface-950 text-surface-300 transition-all rounded font-mono text-xs font-bold shadow-sm"
            >
              <Download className="w-3 h-3" />
              <span className="hidden sm:inline">DESCARGAR</span>
            </button>
          </div>
        </div>

        {/* PDF Viewer Canvas Area */}
        <div className="flex-1 overflow-hidden relative bg-[#0f1015]">
          {!isCertified && (
            <div className="absolute top-0 inset-x-0 z-20 bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 flex items-center justify-between backdrop-blur-md">
              <div className="flex items-center gap-2 text-amber-500 text-sm font-medium">
                <AlertCircle className="w-4 h-4" />
                <span>Molécula sin certificación blockchain</span>
              </div>
              {onCertify && (
                <button
                  onClick={() => setShowModal(true)}
                  disabled={isCertifying}
                  className="flex items-center gap-2 px-3 py-1.5 bg-amber-500 text-surface-950 font-bold font-mono text-xs uppercase hover:bg-amber-400 transition-all rounded shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ShieldCheck className="w-3 h-3" />
                  Certificar Ahora
                </button>
              )}
            </div>
          )}
          
          <div className="absolute inset-0 z-10 pt-[40px]">
            {blobUrl && (
              <iframe 
                src={`${blobUrl}#toolbar=0`} 
                className="w-full h-full border-none bg-transparent"
                title="Visor PDF"
              />
            )}
          </div>
        </div>
      </div>
      
      {showModal && (
        <CertificationModal 
          moleculeId={moleculeId} 
          onClose={() => setShowModal(false)}
          onSuccess={() => {
            setShowModal(false);
            if (onCertify) onCertify();
          }}
        />
      )}
    </>
  );
}
