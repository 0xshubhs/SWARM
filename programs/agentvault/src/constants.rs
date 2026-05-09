//! Program-wide constants. Treasury and USDC mint are set in PlatformConfig
//! at runtime (via initialize_platform), not hard-coded here.

/// Devnet USDC mint. Mainnet uses `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`.
/// Stored on PlatformConfig and validated against incoming token accounts.
pub const USDC_DEVNET: &str = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU";

/// Default platform fee in basis points (10% = 1000).
pub const DEFAULT_FEE_BPS: u16 = 1000;

/// Sandbox access window after purchase, in seconds.
pub const SANDBOX_WINDOW_SECS: i64 = 600;

/// Default sandbox query allowance per purchase.
pub const SANDBOX_QUERIES: u8 = 5;

// Length budgets (bytes excluding the 4-byte length prefix that anchor adds).
pub const MAX_TITLE_LEN: usize = 128;
pub const MAX_MODEL_ID_LEN: usize = 64;
pub const MAX_TAG_LEN: usize = 32;
pub const MAX_TAGS: usize = 10;
pub const ARWEAVE_TX_LEN: usize = 43;
pub const MAX_DECISION_TYPE_LEN: usize = 32;
pub const MAX_DECISION_DATA_LEN: usize = 256;
