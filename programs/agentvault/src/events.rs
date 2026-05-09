use anchor_lang::prelude::*;

#[event]
pub struct MemoryListed {
    pub listing: Pubkey,
    pub seller: Pubkey,
    pub content_hash: [u8; 32],
    pub price_usdc: u64,
    pub model_id: String,
}

#[event]
pub struct MemoryPurchased {
    pub buyer: Pubkey,
    pub listing: Pubkey,
    pub arweave_tx: String,
    pub price_usdc: u64,
    pub timestamp: i64,
}

#[event]
pub struct SandboxAccessGranted {
    pub buyer: Pubkey,
    pub listing: Pubkey,
    pub expires_at: i64,
}

#[event]
pub struct DecisionAnchored {
    pub agent_id: Pubkey,
    pub decision_type: String,
    pub context_hash: [u8; 32],
    pub slot: u64,
    pub timestamp: i64,
}

#[event]
pub struct ListingDelisted {
    pub listing: Pubkey,
    pub seller: Pubkey,
}

#[event]
pub struct ListingPriceUpdated {
    pub listing: Pubkey,
    pub seller: Pubkey,
    pub new_price_usdc: u64,
    pub new_sandbox_price_usdc: u64,
}
