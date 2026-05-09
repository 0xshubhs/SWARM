use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};

use crate::errors::AgentVaultError;
use crate::events::MemoryPurchased;
use crate::state::{MemoryLicense, MemoryListing, PlatformConfig};

#[derive(Accounts)]
pub struct BuyMemory<'info> {
    #[account(mut)]
    pub buyer: Signer<'info>,

    #[account(
        mut,
        seeds = [b"config"],
        bump = config.bump,
        constraint = !config.paused @ AgentVaultError::PlatformPaused,
    )]
    pub config: Account<'info, PlatformConfig>,

    #[account(
        mut,
        constraint = listing.active @ AgentVaultError::ListingInactive,
    )]
    pub listing: Account<'info, MemoryListing>,

    #[account(
        init,
        payer = buyer,
        space = MemoryLicense::SPACE,
        seeds = [b"license", buyer.key().as_ref(), listing.key().as_ref()],
        bump,
    )]
    pub license: Account<'info, MemoryLicense>,

    #[account(
        constraint = usdc_mint.key() == config.usdc_mint @ AgentVaultError::UsdcMintMismatch,
    )]
    pub usdc_mint: Account<'info, Mint>,

    #[account(
        mut,
        constraint = buyer_usdc_ata.mint == usdc_mint.key() @ AgentVaultError::UsdcMintMismatch,
        constraint = buyer_usdc_ata.owner == buyer.key() @ AgentVaultError::Unauthorized,
    )]
    pub buyer_usdc_ata: Account<'info, TokenAccount>,

    #[account(
        mut,
        constraint = seller_usdc_ata.mint == usdc_mint.key() @ AgentVaultError::UsdcMintMismatch,
        constraint = seller_usdc_ata.owner == listing.seller @ AgentVaultError::Unauthorized,
    )]
    pub seller_usdc_ata: Account<'info, TokenAccount>,

    #[account(
        mut,
        constraint = treasury_usdc_ata.mint == usdc_mint.key() @ AgentVaultError::UsdcMintMismatch,
        constraint = treasury_usdc_ata.owner == config.treasury @ AgentVaultError::TreasuryMismatch,
    )]
    pub treasury_usdc_ata: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

pub fn handler(ctx: Context<BuyMemory>) -> Result<()> {
    let listing = &mut ctx.accounts.listing;
    let cfg = &mut ctx.accounts.config;

    let price = listing.price_usdc;
    require!(price > 0, AgentVaultError::InvalidPrice);
    require!(
        ctx.accounts.buyer_usdc_ata.amount >= price,
        AgentVaultError::InsufficientFunds
    );

    let platform_cut: u64 = (price as u128)
        .checked_mul(cfg.platform_fee_bps as u128)
        .ok_or(AgentVaultError::MathOverflow)?
        .checked_div(10_000)
        .ok_or(AgentVaultError::MathOverflow)? as u64;
    let seller_cut = price
        .checked_sub(platform_cut)
        .ok_or(AgentVaultError::MathOverflow)?;

    // buyer -> seller
    token::transfer(
        CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.buyer_usdc_ata.to_account_info(),
                to: ctx.accounts.seller_usdc_ata.to_account_info(),
                authority: ctx.accounts.buyer.to_account_info(),
            },
        ),
        seller_cut,
    )?;

    // buyer -> treasury
    if platform_cut > 0 {
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.buyer_usdc_ata.to_account_info(),
                    to: ctx.accounts.treasury_usdc_ata.to_account_info(),
                    authority: ctx.accounts.buyer.to_account_info(),
                },
            ),
            platform_cut,
        )?;
    }

    let now = Clock::get()?.unix_timestamp;
    let license = &mut ctx.accounts.license;
    license.buyer = ctx.accounts.buyer.key();
    license.listing = listing.key();
    license.purchased_at = now;
    license.bump = ctx.bumps.license;

    listing.purchases = listing
        .purchases
        .checked_add(1)
        .ok_or(AgentVaultError::MathOverflow)?;
    cfg.total_volume_usdc = cfg
        .total_volume_usdc
        .checked_add(price)
        .ok_or(AgentVaultError::MathOverflow)?;

    emit!(MemoryPurchased {
        buyer: license.buyer,
        listing: license.listing,
        arweave_tx: listing.arweave_tx.clone(),
        price_usdc: price,
        timestamp: now,
    });

    Ok(())
}
