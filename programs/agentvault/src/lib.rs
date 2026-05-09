//! AgentVault — on-chain registry, atomic USDC payments, and audit anchoring.
//! Spec: docs/01_SOLANA_PROGRAM.md
use anchor_lang::prelude::*;

pub mod constants;
pub mod errors;
pub mod events;
pub mod instructions;
pub mod state;

use instructions::*;

// Placeholder until first deploy. Replace via:
//   solana address -k target/deploy/agentvault-keypair.json
declare_id!("AgntVau1tVau1tVau1tVau1tVau1tVau1tVau1tVau1");

#[program]
pub mod agentvault {
    use super::*;

    pub fn initialize_platform(
        ctx: Context<InitializePlatform>,
        treasury: Pubkey,
        usdc_mint: Pubkey,
        platform_fee_bps: u16,
    ) -> Result<()> {
        instructions::initialize_platform::handler(ctx, treasury, usdc_mint, platform_fee_bps)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn list_memory(
        ctx: Context<ListMemory>,
        arweave_tx: String,
        content_hash: [u8; 32],
        model_id: String,
        quant_seed: u64,
        bits_per_channel: u8,
        seq_len: u32,
        price_usdc: u64,
        sandbox_price_usdc: u64,
        title: String,
        tags: Vec<String>,
    ) -> Result<()> {
        instructions::list_memory::handler(
            ctx,
            arweave_tx,
            content_hash,
            model_id,
            quant_seed,
            bits_per_channel,
            seq_len,
            price_usdc,
            sandbox_price_usdc,
            title,
            tags,
        )
    }

    pub fn buy_memory(ctx: Context<BuyMemory>) -> Result<()> {
        instructions::buy_memory::handler(ctx)
    }

    pub fn buy_sandbox_access(ctx: Context<BuySandboxAccess>) -> Result<()> {
        instructions::buy_sandbox_access::handler(ctx)
    }

    pub fn delist_memory(ctx: Context<DelistMemory>) -> Result<()> {
        instructions::delist_memory::handler(ctx)
    }

    pub fn update_listing_price(
        ctx: Context<UpdateListingPrice>,
        new_price_usdc: u64,
        new_sandbox_price_usdc: u64,
    ) -> Result<()> {
        instructions::update_listing_price::handler(ctx, new_price_usdc, new_sandbox_price_usdc)
    }

    pub fn anchor_decision(
        ctx: Context<AnchorDecision>,
        agent_id: Pubkey,
        decision_type: String,
        context_hash: [u8; 32],
        arweave_tx: String,
        decision_data: Vec<u8>,
        timestamp: i64,
    ) -> Result<()> {
        instructions::anchor_decision::handler(
            ctx,
            agent_id,
            decision_type,
            context_hash,
            arweave_tx,
            decision_data,
            timestamp,
        )
    }
}
