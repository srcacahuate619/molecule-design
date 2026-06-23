"use client";

import React, { useMemo } from "react";
import { ConnectionProvider, WalletProvider as SolanaWalletProvider } from "@solana/wallet-adapter-react";
import { WalletModalProvider } from "@solana/wallet-adapter-react-ui";
import { clusterApiUrl } from "@solana/web3.js";
import "@solana/wallet-adapter-react-ui/styles.css";

export function WalletProvider({ children }: { children: React.ReactNode }) {
  // Use Devnet for certification
  const network = clusterApiUrl("devnet");
  
  // Wallets are auto-detected by standard, but we can explicitly add more if needed
  const wallets = useMemo(() => [], []);

  const ConnectionProviderAny = ConnectionProvider as any;
  const SolanaWalletProviderAny = SolanaWalletProvider as any;
  const WalletModalProviderAny = WalletModalProvider as any;

  return (
    <ConnectionProviderAny endpoint={network}>
      <SolanaWalletProviderAny wallets={wallets} autoConnect>
        <WalletModalProviderAny>{children}</WalletModalProviderAny>
      </SolanaWalletProviderAny>
    </ConnectionProviderAny>
  );
}
