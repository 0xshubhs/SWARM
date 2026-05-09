//! AgentVault Anchor program. Build out per docs/01_SOLANA_PROGRAM.md.
use anchor_lang::prelude::*;

declare_id!("AgntV1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX");

#[program]
pub mod agentvault {
    use super::*;

    pub fn initialize(_ctx: Context<Initialize>) -> Result<()> {
        // TODO: program-state init. See docs/01_SOLANA_PROGRAM.md §3.
        Ok(())
    }

    // TODO: list_memory, buy_memory, sandbox_grant, anchor_decision, withdraw_royalties
    // — see docs/01_SOLANA_PROGRAM.md §2 (accounts) and §4 (instructions).
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}
