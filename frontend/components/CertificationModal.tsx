"use client";

import React, { useState } from "react";
import { ShieldCheck, Wallet, Loader2, Server, CheckCircle2, AlertCircle } from "lucide-react";
import { useWallet, useConnection } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { prepareCertification, linkCertification, certifyMolecule } from "../lib/api";
import { Transaction, SystemProgram, PublicKey, TransactionInstruction } from "@solana/web3.js";

// The Memo Program ID used by MolDesign
const MEMO_PROGRAM_ID = new PublicKey("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr");

interface CertificationModalProps {
  moleculeId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function CertificationModal({ moleculeId, onClose, onSuccess }: CertificationModalProps) {
  const { publicKey, sendTransaction } = useWallet();
  const { connection } = useConnection();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleInstitutional = async () => {
    setLoading(true);
    setError(null);
    try {
      await certifyMolecule(moleculeId, "");
      onSuccess();
    } catch (err: any) {
      setError(err.message || "Error al certificar institucionalmente.");
    } finally {
      setLoading(false);
    }
  };

  const handleWeb3 = async () => {
    if (!publicKey) {
      setError("Conecta tu billetera primero para usar esta opción.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      // 1. Prepare memo from backend
      const { already_certified, memo, signature: existingSignature } = await prepareCertification(moleculeId, publicKey.toBase58());
      
      if (already_certified && existingSignature) {
        await linkCertification(moleculeId, existingSignature);
        onSuccess();
        return;
      }

      if (!memo) throw new Error("No se pudo generar el memo de certificación.");

      // 2. Build Transaction
      const tx = new Transaction().add(
        new TransactionInstruction({
          keys: [],
          programId: MEMO_PROGRAM_ID,
          data: Buffer.from(memo, "utf-8"),
        })
      );

      // 3. Send and Sign using Wallet Adapter
      const signature = await sendTransaction(tx, connection);
      
      // 4. Confirm transaction on network
      const latestBlockhash = await connection.getLatestBlockhash();
      await connection.confirmTransaction({
        signature,
        blockhash: latestBlockhash.blockhash,
        lastValidBlockHeight: latestBlockhash.lastValidBlockHeight
      }, "confirmed");

      // 5. Link in backend
      await linkCertification(moleculeId, signature);
      onSuccess();

    } catch (err: any) {
      setError(err.message || "Error al firmar transacción Web3.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-surface-900 border border-surface-800 shadow-2xl rounded-xl w-full max-w-lg overflow-hidden flex flex-col">
        <div className="p-6 border-b border-surface-800 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 bg-brand-500/10 blur-3xl rounded-full" />
          <h3 className="text-xl font-bold text-white flex items-center gap-2 relative z-10">
            <ShieldCheck className="w-6 h-6 text-brand-400" />
            Certificación en Solana
          </h3>
          <p className="text-surface-400 text-sm mt-2 relative z-10">
            Elige cómo deseas registrar tu molécula en la blockchain (Devnet).
          </p>
        </div>

        <div className="p-6 flex flex-col gap-4">
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded text-red-400 text-sm flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Option 1: Institutional */}
          <button
            onClick={handleInstitutional}
            disabled={loading}
            className="flex items-start gap-4 p-4 rounded-lg border border-surface-700 bg-surface-800 hover:bg-surface-800/80 hover:border-brand-500/50 transition-all text-left group"
          >
            <div className="w-10 h-10 rounded-full bg-surface-700 flex items-center justify-center shrink-0 group-hover:bg-brand-500/20 group-hover:text-brand-400 transition-colors">
              <Server className="w-5 h-5" />
            </div>
            <div>
              <h4 className="font-bold text-surface-200 group-hover:text-white transition-colors flex items-center gap-2">
                Certificación Institucional
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-brand-500/20 text-brand-400">Gratis</span>
              </h4>
              <p className="text-sm text-surface-400 mt-1">
                MolDesign asume el costo de gas y firma la transacción en tu nombre usando tu email como referencia de autoría. Ideal para uso rápido.
              </p>
            </div>
          </button>

          {/* Option 2: Web3 Personal */}
          <div className="flex flex-col gap-3 p-4 rounded-lg border border-surface-700 bg-surface-800 relative overflow-hidden">
            <div className="flex items-start gap-4 relative z-10">
              <div className="w-10 h-10 rounded-full bg-surface-700 flex items-center justify-center shrink-0 text-surface-300">
                <Wallet className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <h4 className="font-bold text-surface-200 flex items-center gap-2">
                  Certificación Soberana (Web3)
                </h4>
                <p className="text-sm text-surface-400 mt-1">
                  Usa tu propia billetera (Phantom) para firmar criptográficamente el descubrimiento. Tú pagas el gas (red Devnet).
                </p>
                
                <div className="mt-4 flex flex-col gap-2">
                  <WalletMultiButton className="!bg-purple-600 hover:!bg-purple-700 !h-10 !text-sm !font-bold !rounded" />
                  
                  {publicKey && (
                    <button
                      onClick={handleWeb3}
                      disabled={loading}
                      className="mt-2 w-full flex items-center justify-center gap-2 py-2 px-4 bg-surface-900 border border-surface-700 hover:border-purple-500 hover:text-purple-400 rounded text-sm font-bold transition-all disabled:opacity-50"
                    >
                      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                      {loading ? "Firmando..." : "Firmar Transacción"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-surface-800 bg-surface-950 flex justify-end">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 text-surface-400 hover:text-white text-sm font-medium transition-colors"
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
