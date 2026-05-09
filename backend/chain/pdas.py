"""PDA derivation helpers — must match programs/agentvault/src/instructions/."""
from __future__ import annotations

from solders.pubkey import Pubkey


def find_config_pda(program_id: Pubkey) -> tuple[Pubkey, int]:
    return Pubkey.find_program_address([b"config"], program_id)


def find_listing_pda(
    seller: Pubkey, content_hash: bytes, program_id: Pubkey
) -> tuple[Pubkey, int]:
    if len(content_hash) != 32:
        raise ValueError("content_hash must be 32 bytes")
    return Pubkey.find_program_address(
        [b"listing", bytes(seller), content_hash], program_id
    )


def find_license_pda(
    buyer: Pubkey, listing: Pubkey, program_id: Pubkey
) -> tuple[Pubkey, int]:
    return Pubkey.find_program_address(
        [b"license", bytes(buyer), bytes(listing)], program_id
    )


def find_sandbox_pda(
    buyer: Pubkey, listing: Pubkey, program_id: Pubkey
) -> tuple[Pubkey, int]:
    return Pubkey.find_program_address(
        [b"sandbox", bytes(buyer), bytes(listing)], program_id
    )


def find_decision_pda(
    agent_id: Pubkey, timestamp: int, program_id: Pubkey
) -> tuple[Pubkey, int]:
    return Pubkey.find_program_address(
        [b"decision", bytes(agent_id), timestamp.to_bytes(8, "little", signed=True)],
        program_id,
    )
