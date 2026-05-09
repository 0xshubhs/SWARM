use anchor_lang::prelude::*;

use crate::constants::*;

/// Marketplace listing for a compressed memory blob.
/// PDA seeds: ["listing", seller, content_hash]
#[account]
pub struct MemoryListing {
    pub seller: Pubkey,                    // 32
    pub bump: u8,                          // 1

    pub arweave_tx: String,                // 4 + 43
    pub content_hash: [u8; 32],            // 32

    pub model_id: String,                  // 4 + 64
    pub quant_seed: u64,                   // 8
    pub bits_per_channel: u8,              // 1   25/35/40
    pub seq_len: u32,                      // 4

    pub price_usdc: u64,                   // 8
    pub sandbox_price_usdc: u64,           // 8
    pub title: String,                     // 4 + 128
    pub tags: Vec<String>,                 // 4 + 10*(4+32)

    pub created_at: i64,                   // 8
    pub active: bool,                      // 1
    pub purchases: u64,                    // 8
}

impl MemoryListing {
    /// Anchor adds an 8-byte discriminator to every account.
    pub const SPACE: usize = 8                            // discriminator
        + 32 + 1                                          // seller, bump
        + 4 + ARWEAVE_TX_LEN                              // arweave_tx
        + 32                                              // content_hash
        + 4 + MAX_MODEL_ID_LEN                            // model_id
        + 8 + 1 + 4                                       // quant_seed, bits, seq_len
        + 8 + 8                                           // prices
        + 4 + MAX_TITLE_LEN                               // title
        + 4 + MAX_TAGS * (4 + MAX_TAG_LEN)                // tags
        + 8 + 1 + 8;                                      // created_at, active, purchases
}

/// Proof a buyer paid for the full memory.
/// PDA seeds: ["license", buyer, listing]
#[account]
pub struct MemoryLicense {
    pub buyer: Pubkey,
    pub listing: Pubkey,
    pub purchased_at: i64,
    pub bump: u8,
}

impl MemoryLicense {
    pub const SPACE: usize = 8 + 32 + 32 + 8 + 1;
}

/// Time-bounded preview access. Overwritten on re-purchase.
/// PDA seeds: ["sandbox", buyer, listing]
#[account]
pub struct SandboxAccess {
    pub buyer: Pubkey,
    pub listing: Pubkey,
    pub expires_at: i64,
    pub queries_remaining: u8,
    pub bump: u8,
}

impl SandboxAccess {
    pub const SPACE: usize = 8 + 32 + 32 + 8 + 1 + 1;
}

/// On-chain audit record anchoring an agent decision to its context.
/// PDA seeds: ["decision", agent_id, timestamp_le_bytes]
#[account]
pub struct DecisionRecord {
    pub agent_id: Pubkey,
    pub decision_type: String,
    pub context_hash: [u8; 32],
    pub arweave_tx: String,
    pub decision_data: Vec<u8>,
    pub timestamp: i64,
    pub slot: u64,
    pub bump: u8,
}

impl DecisionRecord {
    pub const SPACE: usize = 8
        + 32                                            // agent_id
        + 4 + MAX_DECISION_TYPE_LEN                     // decision_type
        + 32                                            // context_hash
        + 4 + ARWEAVE_TX_LEN                            // arweave_tx
        + 4 + MAX_DECISION_DATA_LEN                     // decision_data
        + 8 + 8 + 1;                                    // timestamp, slot, bump
}

/// Singleton config. PDA seeds: ["config"]
#[account]
pub struct PlatformConfig {
    pub authority: Pubkey,
    pub treasury: Pubkey,
    pub usdc_mint: Pubkey,
    pub platform_fee_bps: u16,
    pub paused: bool,
    pub total_listings: u64,
    pub total_volume_usdc: u64,
    pub bump: u8,
}

impl PlatformConfig {
    pub const SPACE: usize = 8 + 32 + 32 + 32 + 2 + 1 + 8 + 8 + 1;
}
