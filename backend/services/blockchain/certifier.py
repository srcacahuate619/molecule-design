"""
Blockchain certification service for MolDesign.

Uses Solana devnet to certify molecular discoveries with CC0 license.
"""

import asyncio
from typing import Optional
from datetime import datetime

from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey as PublicKey
from solders.transaction import Transaction
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
from solders.message import Message
from solders.transaction import VersionedTransaction

from core.config import get_settings
settings = get_settings()
from core.exceptions import TransactionFailedError
from core.models import BlockchainRecord


class SolanaCertifier:
    """
    Handles certification of molecular discoveries on Solana devnet.

    Uses the Memo Program to store immutable records of scientific contributions.
    """

    MEMO_PROGRAM_ID = PublicKey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")

    def __init__(self):
        self.client = AsyncClient(settings.solana_rpc_url)
        # Load keypair from config (in production, use secure key management)
        if settings.solana_private_key:
            self.keypair = Keypair.from_bytes(bytes.fromhex(settings.solana_private_key))
        else:
            self.keypair = None

    async def certify_molecule(
        self,
        record: BlockchainRecord,
        user_wallet: Optional[str] = None
    ) -> str:
        """
        Certify a molecular discovery on Solana devnet.

        Args:
            record: The blockchain record to certify
            user_wallet: Optional user wallet for attribution

        Returns:
            Transaction signature

        Raises:
            TransactionFailedError: If certification fails
        """
        try:
            # Create memo data
            memo_data = self._create_memo_data(record, user_wallet)

            # Create memo instruction
            memo_ix = Instruction(
                program_id=self.MEMO_PROGRAM_ID,
                accounts=[],  # Memo program doesn't need accounts
                data=memo_data.encode('utf-8')
            )

            # Get recent blockhash
            recent_blockhash = await self.client.get_latest_blockhash()

            # Create transaction
            if not self.keypair:
                raise TransactionFailedError(
                    smiles_hash=record.smiles_hash,
                    reason="Solana private key not configured"
                )

            message = Message([memo_ix], self.keypair.pubkey())
            txn = Transaction([self.keypair], message, recent_blockhash.value.blockhash)

            # Send transaction
            result = await self.client.send_transaction(txn)

            if result.value is None:
                raise TransactionFailedError(
                    smiles_hash=record.smiles_hash,
                    reason="Transaction failed to send"
                )

            return str(result.value)

        except Exception as e:
            error_str = str(e)
            if "Attempt to debit an account but found no record of a prior credit" in error_str or "AccountNotFound" in error_str:
                raise TransactionFailedError(
                    smiles_hash=record.smiles_hash,
                    reason="Ups! Fondos insuficientes en el servidor para pagar la certificación en Solana. Por favor recarga la wallet del servidor (Devnet).",
                    detail="InsufficientFunds"
                )
            raise TransactionFailedError(
                smiles_hash=record.smiles_hash,
                reason=f"Certification failed: {error_str}",
                detail=str(type(e).__name__)
            )

    def _create_memo_data(self, record: BlockchainRecord, user_wallet: Optional[str]) -> str:
        """Create the memo string for the transaction."""
        timestamp_iso = record.timestamp.isoformat()

        memo = f"MolDesign-CC0|{record.smiles_hash}|{record.total_score:.2f}|{record.target_pdb_id}|{timestamp_iso}"

        if user_wallet:
            memo += f"|{user_wallet}"

        return memo

    async def verify_certification(self, signature: str) -> Optional[BlockchainRecord]:
        """
        Verify a certification transaction on the blockchain.

        Args:
            signature: Transaction signature

        Returns:
            BlockchainRecord if found and valid, None otherwise
        """
        try:
            # Get transaction details
            tx_info = await self.client.get_transaction(signature)

            if tx_info.value is None:
                return None

            # Parse memo from transaction
            memo_data = self._extract_memo_from_tx(tx_info.value)

            if not memo_data:
                return None

            return self._parse_memo_to_record(memo_data)

        except Exception:
            return None

    def _extract_memo_from_tx(self, tx) -> Optional[str]:
        """Extract memo data from transaction."""
        try:
            # Parse transaction to find memo instruction
            if hasattr(tx, 'transaction') and hasattr(tx.transaction, 'message'):
                message = tx.transaction.message
                
                # Check instructions for memo program
                for instruction in message.instructions:
                    if str(instruction.program_id) == str(self.MEMO_PROGRAM_ID):
                        # Decode memo data (skip the first byte which is instruction discriminator)
                        memo_bytes = instruction.data[1:] if len(instruction.data) > 1 else instruction.data
                        return memo_bytes.decode('utf-8')
            
            return None
        except Exception:
            return None

    def _parse_memo_to_record(self, memo: str) -> Optional[BlockchainRecord]:
        """Parse memo string back to BlockchainRecord."""
        try:
            parts = memo.split('|')
            if len(parts) < 5 or not parts[0] == "MolDesign-CC0":
                return None

            smiles_hash = parts[1]
            total_score = float(parts[2])
            target_pdb_id = parts[3]
            timestamp_str = parts[4]
            user_wallet = parts[5] if len(parts) > 5 else None

            timestamp = datetime.fromisoformat(timestamp_str)

            return BlockchainRecord(
                smiles_hash=smiles_hash,
                total_score=total_score,
                target_pdb_id=target_pdb_id,
                user_wallet=user_wallet or "",
                timestamp=timestamp
            )

        except (ValueError, IndexError):
            return None

    async def close(self):
        """Close the RPC client."""
        await self.client.close()


# Global instance
certifier = SolanaCertifier()


async def certify_molecule_async(record: BlockchainRecord, user_wallet: Optional[str] = None) -> str:
    """Async wrapper for molecule certification."""
    return await certifier.certify_molecule(record, user_wallet)


def certify_molecule_sync(record: BlockchainRecord, user_wallet: Optional[str] = None) -> str:
    """Synchronous wrapper for molecule certification."""
    return asyncio.run(certify_molecule_async(record, user_wallet))