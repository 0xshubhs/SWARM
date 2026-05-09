use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};

use crate::constants::{SANDBOX_QUERIES, SANDBOX_WINDOW_SECS};
use crate::errors::AgentVaultError;
use crate::events::SandboxAccessGranted;
use crate::state::{MemoryListing, PlatformConfig, SandboxAccess};

#[derive(Accounts)]
pub struct BuySandboxAccess<'info> {
    #[account(mut)]
    pub buyer: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump = config.bump,
        constraint = !config.paused @ AgentVaultError::PlatformPaused,
    )]
    pub config: Account<'info, PlatformConfig>,

    #[account(
        constraint = listing.active @ AgentVaultError::ListingInactive,
    )]
    pub listing: Account<'info, MemoryListing>,

    #[account(
        init_if_needed,
        payer = buyer,
        space = SandboxAccess::SPACE,
        seeds = [b"sandbox", buyer.key().as_ref(), listing.key().as_ref()],
        bump,
    )]
    pub sandbox: Account<'info, SandboxAccess>,

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

pub fn handler(ctx: Context<BuySandboxAccess>) -> Result<()> {
    let price = ctx.accounts.listing.sandbox_price_usdc;
    let fee_bps = ctx.accounts.config.platform_fee_bps;

    require!(price > 0, AgentVaultError::InvalidPrice);
    require!(
        ctx.accounts.buyer_usdc_ata.amount >= price,
        AgentVaultError::InsufficientFunds
    );

    let platform_cut: u64 = (price as u128)
        .checked_mul(fee_bps as u128)
        .ok_or(AgentVaultError::MathOverflow)?
        .checked_div(10_000)
        .ok_or(AgentVaultError::MathOverflow)? as u64;
    let seller_cut = price
        .checked_sub(platform_cut)
        .ok_or(AgentVaultError::MathOverflow)?;

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
    let sandbox = &mut ctx.accounts.sandbox;
    sandbox.buyer = ctx.accounts.buyer.key();
    sandbox.listing = ctx.accounts.listing.key();
    sandbox.expires_at = now
        .checked_add(SANDBOX_WINDOW_SECS)
        .ok_or(AgentVaultError::MathOverflow)?;
    sandbox.queries_remaining = SANDBOX_QUERIES;
    sandbox.bump = ctx.bumps.sandbox;

    emit!(SandboxAccessGranted {
        buyer: sandbox.buyer,
        listing: sandbox.listing,
        expires_at: sandbox.expires_at,
    });

    Ok(())
}
