# 01 — Solana Anchor Program

**Where:** `programs/agentvault/`
**Stack:** Rust + Anchor 0.30+
**Deploy target:** Solana devnet → mainnet
**Build first:** Yes — everything else depends on the program ID and IDL

---

## 1. Responsibilities

The program is **the trust layer**. It owns:
- Asset registry (who lists what memory)
- Atomic payments (USDC transfer + license issuance in one tx)
- Sandbox access tokens (time-bounded, query-bounded)
- Decision audit anchoring (Use Case 1 — DAO governance)

The program does **not**:
- Store blobs (Arweave does)
- Run inference (RunPod Qwen does)
- Index history (backend indexer does)

---

## 2. Account structures

### `MemoryListing` (PDA)

```rust
#[account]
pub struct MemoryListing {
    // Identity
    pub seller: Pubkey,                    // 32
    pub bump: u8,                          // 1

    // Storage pointer
    pub arweave_tx: String,                // 4 + 43 (Arweave TX IDs are 43 chars)
    pub content_hash: [u8; 32],            // 32 — SHA-256 of compressed blob

    // Memory metadata (for decompression)
    pub model_id: String,                  // 4 + 64 — e.g. "qwen2.5-7b-instruct"
    pub quant_seed: u64,                   // 8 — for deterministic decompression
    pub bits_per_channel: u8,              // 1 — encoded: 25=2.5, 35=3.5, 40=4.0
    pub seq_len: u32,                      // 4 — token count

    // Marketplace
    pub price_usdc: u64,                   // 8 — USDC micro-units (e.g. 25_000_000 = $25)
    pub sandbox_price_usdc: u64,           // 8
    pub title: String,                     // 4 + 128
    pub tags: Vec<String>,                 // 4 + 10*(4+32) = 364

    // State
    pub created_at: i64,                   // 8
    pub active: bool,                      // 1
    pub purchases: u64,                    // 8 — running counter
}
```

PDA seeds: `["listing", seller.key(), content_hash]`
Account size: ~750 bytes including discriminator

### `MemoryLicense` (PDA)

```rust
#[account]
pub struct MemoryLicense {
    pub buyer: Pubkey,                     // 32
    pub listing: Pubkey,                   // 32
    pub purchased_at: i64,                 // 8
    pub bump: u8,                          // 1
}
```

PDA seeds: `["license", buyer.key(), listing.key()]`
Account size: ~80 bytes

### `SandboxAccess` (PDA)

```rust
#[account]
pub struct SandboxAccess {
    pub buyer: Pubkey,                     // 32
    pub listing: Pubkey,                   // 32
    pub expires_at: i64,                   // 8 — unix timestamp
    pub queries_remaining: u8,             // 1
    pub bump: u8,                          // 1
}
```

PDA seeds: `["sandbox", buyer.key(), listing.key()]`
Note: this PDA is reset/overwritten on each new sandbox purchase. Buyer can extend access by re-paying.

### `DecisionRecord` (PDA) — The audit trail primitive

```rust
#[account]
pub struct DecisionRecord {
    pub agent_id: Pubkey,                  // 32 — agent's identity (could be SAID-derived)
    pub decision_type: String,             // 4 + 32 — "trade" | "vote" | "rebalance" | "..."
    pub context_hash: [u8; 32],            // 32 — SHA-256 of compressed context at decision time
    pub arweave_tx: String,                // 4 + 43 — where the context blob lives
    pub decision_data: Vec<u8>,            // 4 + 256 — compact decision summary (JSON encoded)
    pub timestamp: i64,                    // 8
    pub slot: u64,                         // 8
    pub bump: u8,                          // 1
}
```

PDA seeds: `["decision", agent_id, timestamp.to_le_bytes()]`
Account size: ~430 bytes

### `PlatformConfig` (singleton PDA)

```rust
#[account]
pub struct PlatformConfig {
    pub authority: Pubkey,                 // 32 — admin
    pub treasury: Pubkey,                  // 32 — receives 10% platform fee
    pub usdc_mint: Pubkey,                 // 32
    pub platform_fee_bps: u16,             // 2 — basis points (1000 = 10%)
    pub paused: bool,                      // 1
    pub total_listings: u64,               // 8
    pub total_volume_usdc: u64,            // 8
    pub bump: u8,                          // 1
}
```

PDA seeds: `["config"]`
Initialized once via `initialize_platform`.

---

## 3. Instructions

### 3.1 `initialize_platform` (one-time setup)

```rust
pub fn initialize_platform(
    ctx: Context<InitializePlatform>,
    treasury: Pubkey,
    usdc_mint: Pubkey,
    platform_fee_bps: u16,  // 1000 = 10%
) -> Result<()>
```

Called once by the program deployer to set up the singleton config.

### 3.2 `list_memory`

```rust
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
) -> Result<()>
```

Validates: `tags.len() <= 10`, `title.len() <= 128`, `arweave_tx.len() == 43`, prices > 0.
Increments `PlatformConfig.total_listings`.
Emits `MemoryListed` event.

### 3.3 `buy_memory`

```rust
pub fn buy_memory(ctx: Context<BuyMemory>) -> Result<()>
```

Atomic operation:
1. Validate `listing.active == true`
2. Calculate split: `platform_cut = price * fee_bps / 10000`, `seller_cut = price - platform_cut`
3. Transfer USDC from buyer's ATA → seller's ATA (90%)
4. Transfer USDC from buyer's ATA → treasury ATA (10%)
5. Initialize `MemoryLicense` PDA owned by buyer
6. Increment `listing.purchases`
7. Add to `PlatformConfig.total_volume_usdc`
8. Emit `MemoryPurchased { buyer, listing, arweave_tx }` event

Required accounts:
- `buyer` (signer)
- `listing` (mut)
- `license` (init, mut, PDA)
- `seller_usdc_ata` (mut)
- `buyer_usdc_ata` (mut)
- `treasury_usdc_ata` (mut)
- `usdc_mint`
- `token_program`
- `platform_config` (mut)
- `system_program`

### 3.4 `buy_sandbox_access`

```rust
pub fn buy_sandbox_access(
    ctx: Context<BuySandboxAccess>,
) -> Result<()>
```

Same payment flow as `buy_memory` but:
- Pays `listing.sandbox_price_usdc` instead
- Creates/overwrites `SandboxAccess` PDA with `expires_at = now + 600` (10 min) and `queries_remaining = 5`
- Does NOT increment `listing.purchases` (separate counter if needed)

### 3.5 `delist_memory`

```rust
pub fn delist_memory(ctx: Context<DelistMemory>) -> Result<()>
```

Only `listing.seller` can call. Sets `listing.active = false`. Doesn't close the account (preserves audit history).

### 3.6 `update_listing_price`

```rust
pub fn update_listing_price(
    ctx: Context<UpdateListingPrice>,
    new_price_usdc: u64,
    new_sandbox_price_usdc: u64,
) -> Result<()>
```

Only `listing.seller`. Lets sellers respond to demand.

### 3.7 `anchor_decision` — The audit primitive

```rust
pub fn anchor_decision(
    ctx: Context<AnchorDecision>,
    agent_id: Pubkey,           // Could be == ctx.accounts.signer.key for self-anchored
    decision_type: String,
    context_hash: [u8; 32],
    arweave_tx: String,
    decision_data: Vec<u8>,
) -> Result<()>
```

Anyone can call (the agent itself, or a privileged "audit oracle" service).
Validates: `decision_type.len() <= 32`, `decision_data.len() <= 256`.
Creates `DecisionRecord` PDA. Emits `DecisionAnchored` event.

This is the SECOND product — DAOs use this *without* needing the marketplace.

---

## 4. Events

```rust
#[event]
pub struct MemoryListed {
    pub listing: Pubkey,
    pub seller: Pubkey,
    pub content_hash: [u8; 32],
    pub price_usdc: u64,
    pub model_id: String,
}

#[event]
pub struct MemoryPurchased {
    pub buyer: Pubkey,
    pub listing: Pubkey,
    pub arweave_tx: String,
    pub price_usdc: u64,
    pub timestamp: i64,
}

#[event]
pub struct SandboxAccessGranted {
    pub buyer: Pubkey,
    pub listing: Pubkey,
    pub expires_at: i64,
}

#[event]
pub struct DecisionAnchored {
    pub agent_id: Pubkey,
    pub decision_type: String,
    pub context_hash: [u8; 32],
    pub slot: u64,
    pub timestamp: i64,
}

#[event]
pub struct ListingDelisted {
    pub listing: Pubkey,
    pub seller: Pubkey,
}
```

The backend indexer subscribes to these events to keep Supabase in sync.

---

## 5. Errors

```rust
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
    #[msg("Arweave TX must be exactly 43 characters")]
    InvalidArweaveTx,
    #[msg("Decision data exceeds 256 bytes")]
    DecisionDataTooLarge,
    #[msg("Platform is currently paused")]
    PlatformPaused,
    #[msg("Price must be greater than zero")]
    InvalidPrice,
    #[msg("Bits per channel must be 25, 35, or 40")]
    InvalidQuantization,
}
```

---

## 6. File structure

```
programs/agentvault/
├── Cargo.toml
├── Xargo.toml
└── src/
    ├── lib.rs                       # Entry, instruction routing, declare_id!
    ├── constants.rs                 # USDC mint, treasury, fee_bps
    ├── errors.rs                    # AgentVaultError enum
    ├── events.rs                    # Event structs
    ├── state.rs                     # All #[account] structs
    └── instructions/
        ├── mod.rs                   # pub use ...
        ├── initialize_platform.rs
        ├── list_memory.rs
        ├── buy_memory.rs
        ├── buy_sandbox_access.rs
        ├── delist_memory.rs
        ├── update_listing_price.rs
        └── anchor_decision.rs
```

---

## 7. Cargo.toml

```toml
[package]
name = "agentvault"
version = "0.1.0"
description = "AgentVault: Solana program for AI agent memory marketplace and audit trail"
edition = "2021"

[lib]
crate-type = ["cdylib", "lib"]
name = "agentvault"

[features]
no-entrypoint = []
no-idl = []
no-log-ix-name = []
cpi = ["no-entrypoint"]
default = []

[dependencies]
anchor-lang = "0.30.1"
anchor-spl = "0.30.1"
solana-program = "1.18"
```

---

## 8. Tests

`tests/agentvault.ts` — written in TypeScript using anchor-bankrun for speed.

Required test cases:
1. Initialize platform succeeds, second init fails
2. List memory: success, validation failures (long title, too many tags, invalid hash length, invalid bits)
3. Buy memory: USDC transfers correctly split 90/10, license PDA created, listing.purchases incremented
4. Buy memory: fails when listing inactive
5. Buy memory: fails on insufficient USDC
6. Sandbox access: creates correct expiry/queries fields
7. Sandbox access: re-purchase replaces old PDA cleanly
8. Delist: only seller can delist
9. Delist: existing licenses still valid (decoupled)
10. Anchor decision: DecisionRecord PDA correctly populated
11. Anchor decision: enforces decision_data size limit
12. Update price: only seller can update
13. Pause: blocks all paid actions when paused

Use `anchor-bankrun` and `solana-bankrun` for fast in-process tests:

```bash
yarn add -D anchor-bankrun solana-bankrun chai mocha ts-mocha @types/mocha @types/chai
```

---

## 9. Deployment

```bash
# 1. Build
anchor build

# 2. Get the deployed program ID
PROGRAM_ID=$(solana address -k target/deploy/agentvault-keypair.json)
echo "Program ID: $PROGRAM_ID"

# 3. Update declare_id!() in lib.rs and Anchor.toml [programs.devnet]
sed -i "s/declare_id!(\".*\")/declare_id!(\"$PROGRAM_ID\")/" programs/agentvault/src/lib.rs
# (also update Anchor.toml)

# 4. Rebuild with correct program ID
anchor build

# 5. Deploy to devnet
anchor deploy --provider.cluster devnet

# 6. Initialize platform
anchor run initialize --provider.cluster devnet

# 7. Generate IDL exports for backend + frontend + buyer agent
anchor idl init --filepath target/idl/agentvault.json $PROGRAM_ID --provider.cluster devnet
cp target/idl/agentvault.json ../../shared/types/idl.json
cp target/types/agentvault.ts ../../shared/types/agentvault.ts
```

---

## 10. Claude Code prompt — paste this verbatim

````
You are building the AgentVault Solana Anchor program. This is the on-chain trust layer for an AI agent memory marketplace + audit trail system.

## Read the spec
The complete spec is in `docs/01_SOLANA_PROGRAM.md`. Open it. Read every section. Build exactly what's specified.

## Hard requirements
- Anchor 0.30.1 syntax
- All accounts use PDAs with seeds specified in the doc
- USDC payments use anchor-spl token program for SPL token transfers
- Every instruction validates inputs and returns appropriate AgentVaultError
- Every state-changing instruction emits the corresponding event
- 90/10 split between seller and platform treasury, configurable via PlatformConfig.platform_fee_bps

## File structure
Build files exactly as listed in section 6 of the spec. Don't merge files.

## Build steps in order
1. Cargo.toml with dependencies
2. constants.rs (with placeholder treasury — accept as parameter to initialize_platform)
3. errors.rs (full AgentVaultError enum)
4. events.rs (all five event structs)
5. state.rs (MemoryListing, MemoryLicense, SandboxAccess, DecisionRecord, PlatformConfig)
6. instructions/initialize_platform.rs
7. instructions/list_memory.rs
8. instructions/buy_memory.rs (this is the critical atomic-payment one)
9. instructions/buy_sandbox_access.rs
10. instructions/delist_memory.rs
11. instructions/update_listing_price.rs
12. instructions/anchor_decision.rs
13. instructions/mod.rs (re-exports)
14. lib.rs (declare_id!, #[program] module, instruction routing)

After each file, briefly explain what's there. After lib.rs, run `anchor build` and fix any errors iteratively.

## Tests (after program builds clean)
Write tests in `tests/agentvault.ts` using anchor-bankrun. Cover all 13 test cases listed in section 8. Use a helper fixture function to set up a fresh test environment per test.

## Common pitfalls to avoid
- Account size calculation: every Vec<T> needs `4 + len * size_of::<T>()`. Strings need `4 + max_len`. Add 8 for the discriminator.
- PDA seeds must match between init and lookup. Use the exact seeds in section 2 of the spec.
- USDC has 6 decimals. Always use micro-units (multiply human price by 1_000_000).
- `init` constraint requires `payer` and `space` and `seeds` and `bump`.
- Use `init_if_needed` for SandboxAccess since users can re-purchase.

Build. Test. Iterate until `anchor build` and `anchor test --skip-local-validator` both pass clean.
````

---

## 11. Definition of done

- [ ] All 7 instructions implemented
- [ ] All 5 account types fully defined with correct sizes
- [ ] All 5 events emit on the correct instructions
- [ ] All 13 error codes used appropriately
- [ ] `anchor build` clean (no warnings about unused vars)
- [ ] `anchor test` passes all 13 test cases
- [ ] Deployed to devnet, program ID recorded in `.env.example`
- [ ] IDL exported to `shared/types/idl.json` and `shared/types/agentvault.ts`
- [ ] Initial `initialize_platform` tx executed, treasury and config PDA exist on-chain

When this list is checked, every other component can start building against the IDL.
