use anchor_lang::prelude::*;

#[error_code]
pub enum AgentVaultError {
    #[msg("Listing is not active")]
    ListingInactive,
    #[msg("Insufficient USDC balance")]
    InsufficientFunds,
    #[msg("Hash format is invalid")]
    InvalidHash,
    #[msg("Sandbox access has expired")]
    SandboxExpired,
    #[msg("No sandbox queries remaining")]
    NoQueriesRemaining,
    #[msg("Caller is not authorized for this action")]
    Unauthorized,
    #[msg("Title exceeds maximum length (128)")]
    TitleTooLong,
    #[msg("Tags array exceeds maximum size (10)")]
    TooManyTags,
    #[msg("A tag exceeds the maximum length (32)")]
    TagTooLong,
    #[msg("Model id exceeds maximum length (64)")]
    ModelIdTooLong,
    #[msg("Arweave TX must be exactly 43 characters")]
    InvalidArweaveTx,
    #[msg("Decision data exceeds 256 bytes")]
    DecisionDataTooLarge,
    #[msg("Decision type exceeds 32 characters")]
    DecisionTypeTooLong,
    #[msg("Platform is currently paused")]
    PlatformPaused,
    #[msg("Price must be greater than zero")]
    InvalidPrice,
    #[msg("Bits per channel must be 25, 35, or 40")]
    InvalidQuantization,
    #[msg("Math overflow")]
    MathOverflow,
    #[msg("USDC mint mismatch")]
    UsdcMintMismatch,
    #[msg("Treasury account mismatch")]
    TreasuryMismatch,
    #[msg("Fee bps must be <= 10000")]
    InvalidFeeBps,
}
