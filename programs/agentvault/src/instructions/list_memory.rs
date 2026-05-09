use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::AgentVaultError;
use crate::events::MemoryListed;
use crate::state::{MemoryListing, PlatformConfig};

#[derive(Accounts)]
#[instruction(arweave_tx: String, content_hash: [u8; 32])]
pub struct ListMemory<'info> {
    #[account(mut)]
    pub seller: Signer<'info>,

    #[account(
        mut,
        seeds = [b"config"],
        bump = config.bump,
        constraint = !config.paused @ AgentVaultError::PlatformPaused,
    )]
    pub config: Account<'info, PlatformConfig>,

    #[account(
        init,
        payer = seller,
        space = MemoryListing::SPACE,
        seeds = [b"listing", seller.key().as_ref(), &content_hash],
        bump,
    )]
    pub listing: Account<'info, MemoryListing>,

    pub system_program: Program<'info, System>,
}

#[allow(clippy::too_many_arguments)]
pub fn handler(
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
    require!(
        arweave_tx.len() == ARWEAVE_TX_LEN,
        AgentVaultError::InvalidArweaveTx
    );
    require!(title.len() <= MAX_TITLE_LEN, AgentVaultError::TitleTooLong);
    require!(model_id.len() <= MAX_MODEL_ID_LEN, AgentVaultError::ModelIdTooLong);
    require!(tags.len() <= MAX_TAGS, AgentVaultError::TooManyTags);
    for t in tags.iter() {
        require!(t.len() <= MAX_TAG_LEN, AgentVaultError::TagTooLong);
    }
    require!(price_usdc > 0, AgentVaultError::InvalidPrice);
    require!(sandbox_price_usdc > 0, AgentVaultError::InvalidPrice);
    require!(
        matches!(bits_per_channel, 25 | 35 | 40),
        AgentVaultError::InvalidQuantization
    );

    let listing = &mut ctx.accounts.listing;
    listing.seller = ctx.accounts.seller.key();
    listing.bump = ctx.bumps.listing;
    listing.arweave_tx = arweave_tx;
    listing.content_hash = content_hash;
    listing.model_id = model_id.clone();
    listing.quant_seed = quant_seed;
    listing.bits_per_channel = bits_per_channel;
    listing.seq_len = seq_len;
    listing.price_usdc = price_usdc;
    listing.sandbox_price_usdc = sandbox_price_usdc;
    listing.title = title;
    listing.tags = tags;
    listing.created_at = Clock::get()?.unix_timestamp;
    listing.active = true;
    listing.purchases = 0;

    let cfg = &mut ctx.accounts.config;
    cfg.total_listings = cfg
        .total_listings
        .checked_add(1)
        .ok_or(AgentVaultError::MathOverflow)?;

    emit!(MemoryListed {
        listing: listing.key(),
        seller: listing.seller,
        content_hash,
        price_usdc,
        model_id,
    });

    Ok(())
}
