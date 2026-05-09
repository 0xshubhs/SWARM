use anchor_lang::prelude::*;

use crate::errors::AgentVaultError;
use crate::events::ListingPriceUpdated;
use crate::state::MemoryListing;

#[derive(Accounts)]
pub struct UpdateListingPrice<'info> {
    pub seller: Signer<'info>,

    #[account(
        mut,
        constraint = listing.seller == seller.key() @ AgentVaultError::Unauthorized,
    )]
    pub listing: Account<'info, MemoryListing>,
}

pub fn handler(
    ctx: Context<UpdateListingPrice>,
    new_price_usdc: u64,
    new_sandbox_price_usdc: u64,
) -> Result<()> {
    require!(new_price_usdc > 0, AgentVaultError::InvalidPrice);
    require!(new_sandbox_price_usdc > 0, AgentVaultError::InvalidPrice);

    let listing = &mut ctx.accounts.listing;
    listing.price_usdc = new_price_usdc;
    listing.sandbox_price_usdc = new_sandbox_price_usdc;

    emit!(ListingPriceUpdated {
        listing: listing.key(),
        seller: listing.seller,
        new_price_usdc,
        new_sandbox_price_usdc,
    });

    Ok(())
}
