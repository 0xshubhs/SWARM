use anchor_lang::prelude::*;

use crate::errors::AgentVaultError;
use crate::state::PlatformConfig;

#[derive(Accounts)]
pub struct InitializePlatform<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        init,
        payer = authority,
        space = PlatformConfig::SPACE,
        seeds = [b"config"],
        bump,
    )]
    pub config: Account<'info, PlatformConfig>,

    pub system_program: Program<'info, System>,
}

pub fn handler(
    ctx: Context<InitializePlatform>,
    treasury: Pubkey,
    usdc_mint: Pubkey,
    platform_fee_bps: u16,
) -> Result<()> {
    require!(platform_fee_bps <= 10_000, AgentVaultError::InvalidFeeBps);

    let cfg = &mut ctx.accounts.config;
    cfg.authority = ctx.accounts.authority.key();
    cfg.treasury = treasury;
    cfg.usdc_mint = usdc_mint;
    cfg.platform_fee_bps = platform_fee_bps;
    cfg.paused = false;
    cfg.total_listings = 0;
    cfg.total_volume_usdc = 0;
    cfg.bump = ctx.bumps.config;
    Ok(())
}
