use anchor_lang::prelude::*;

use crate::errors::AgentVaultError;
use crate::events::ListingDelisted;
use crate::state::MemoryListing;

#[derive(Accounts)]
pub struct DelistMemory<'info> {
    pub seller: Signer<'info>,

    #[account(
        mut,
        constraint = listing.seller == seller.key() @ AgentVaultError::Unauthorized,
    )]
    pub listing: Account<'info, MemoryListing>,
}

pub fn handler(ctx: Context<DelistMemory>) -> Result<()> {
    let listing = &mut ctx.accounts.listing;
    listing.active = false;

    emit!(ListingDelisted {
        listing: listing.key(),
        seller: listing.seller,
    });

    Ok(())
}
