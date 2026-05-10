/**
 * Anchor IDL for the AgentVault program — hand-mirrored from
 * `programs/agentvault/src/`. Run `anchor build && anchor idl init`
 * post-deploy to refresh `idl.json` from the on-chain source of truth.
 */

export const AGENTVAULT_IDL = {
  // Anchor 0.30 reads `address` here directly; `metadata.address` retained for
  // older tooling that may still look there.
  address: "HvWGEDbnRCVThyCNwUVpFRfWsHx2aqT9Ttotr4QovGCF",
  version: "0.1.0",
  name: "agentvault",
  instructions: [
    {
      name: "initializePlatform",
      accounts: [
        { name: "authority", isMut: true, isSigner: true },
        { name: "config", isMut: true, isSigner: false },
        { name: "systemProgram", isMut: false, isSigner: false },
      ],
      args: [
        { name: "treasury", type: "publicKey" },
        { name: "usdcMint", type: "publicKey" },
        { name: "platformFeeBps", type: "u16" },
      ],
    },
    {
      name: "listMemory",
      accounts: [
        { name: "seller", isMut: true, isSigner: true },
        { name: "config", isMut: true, isSigner: false },
        { name: "listing", isMut: true, isSigner: false },
        { name: "systemProgram", isMut: false, isSigner: false },
      ],
      args: [
        { name: "arweaveTx", type: "string" },
        { name: "contentHash", type: { array: ["u8", 32] } },
        { name: "modelId", type: "string" },
        { name: "quantSeed", type: "u64" },
        { name: "bitsPerChannel", type: "u8" },
        { name: "seqLen", type: "u32" },
        { name: "priceUsdc", type: "u64" },
        { name: "sandboxPriceUsdc", type: "u64" },
        { name: "title", type: "string" },
        { name: "tags", type: { vec: "string" } },
      ],
    },
    {
      name: "buyMemory",
      accounts: [
        { name: "buyer", isMut: true, isSigner: true },
        { name: "config", isMut: true, isSigner: false },
        { name: "listing", isMut: true, isSigner: false },
        { name: "license", isMut: true, isSigner: false },
        { name: "usdcMint", isMut: false, isSigner: false },
        { name: "buyerUsdcAta", isMut: true, isSigner: false },
        { name: "sellerUsdcAta", isMut: true, isSigner: false },
        { name: "treasuryUsdcAta", isMut: true, isSigner: false },
        { name: "tokenProgram", isMut: false, isSigner: false },
        { name: "systemProgram", isMut: false, isSigner: false },
      ],
      args: [],
    },
    {
      name: "buySandboxAccess",
      accounts: [
        { name: "buyer", isMut: true, isSigner: true },
        { name: "config", isMut: false, isSigner: false },
        { name: "listing", isMut: false, isSigner: false },
        { name: "sandbox", isMut: true, isSigner: false },
        { name: "usdcMint", isMut: false, isSigner: false },
        { name: "buyerUsdcAta", isMut: true, isSigner: false },
        { name: "sellerUsdcAta", isMut: true, isSigner: false },
        { name: "treasuryUsdcAta", isMut: true, isSigner: false },
        { name: "tokenProgram", isMut: false, isSigner: false },
        { name: "systemProgram", isMut: false, isSigner: false },
      ],
      args: [],
    },
    {
      name: "delistMemory",
      accounts: [
        { name: "seller", isMut: false, isSigner: true },
        { name: "listing", isMut: true, isSigner: false },
      ],
      args: [],
    },
    {
      name: "updateListingPrice",
      accounts: [
        { name: "seller", isMut: false, isSigner: true },
        { name: "listing", isMut: true, isSigner: false },
      ],
      args: [
        { name: "newPriceUsdc", type: "u64" },
        { name: "newSandboxPriceUsdc", type: "u64" },
      ],
    },
    {
      name: "anchorDecision",
      accounts: [
        { name: "signer", isMut: true, isSigner: true },
        { name: "decision", isMut: true, isSigner: false },
        { name: "systemProgram", isMut: false, isSigner: false },
      ],
      args: [
        { name: "agentId", type: "publicKey" },
        { name: "decisionType", type: "string" },
        { name: "contextHash", type: { array: ["u8", 32] } },
        { name: "arweaveTx", type: "string" },
        { name: "decisionData", type: "bytes" },
        { name: "timestamp", type: "i64" },
      ],
    },
  ],
  accounts: [
    {
      name: "MemoryListing",
      type: {
        kind: "struct",
        fields: [
          { name: "seller", type: "publicKey" },
          { name: "bump", type: "u8" },
          { name: "arweaveTx", type: "string" },
          { name: "contentHash", type: { array: ["u8", 32] } },
          { name: "modelId", type: "string" },
          { name: "quantSeed", type: "u64" },
          { name: "bitsPerChannel", type: "u8" },
          { name: "seqLen", type: "u32" },
          { name: "priceUsdc", type: "u64" },
          { name: "sandboxPriceUsdc", type: "u64" },
          { name: "title", type: "string" },
          { name: "tags", type: { vec: "string" } },
          { name: "createdAt", type: "i64" },
          { name: "active", type: "bool" },
          { name: "purchases", type: "u64" },
        ],
      },
    },
    {
      name: "MemoryLicense",
      type: {
        kind: "struct",
        fields: [
          { name: "buyer", type: "publicKey" },
          { name: "listing", type: "publicKey" },
          { name: "purchasedAt", type: "i64" },
          { name: "bump", type: "u8" },
        ],
      },
    },
    {
      name: "SandboxAccess",
      type: {
        kind: "struct",
        fields: [
          { name: "buyer", type: "publicKey" },
          { name: "listing", type: "publicKey" },
          { name: "expiresAt", type: "i64" },
          { name: "queriesRemaining", type: "u8" },
          { name: "bump", type: "u8" },
        ],
      },
    },
    {
      name: "DecisionRecord",
      type: {
        kind: "struct",
        fields: [
          { name: "agentId", type: "publicKey" },
          { name: "decisionType", type: "string" },
          { name: "contextHash", type: { array: ["u8", 32] } },
          { name: "arweaveTx", type: "string" },
          { name: "decisionData", type: "bytes" },
          { name: "timestamp", type: "i64" },
          { name: "slot", type: "u64" },
          { name: "bump", type: "u8" },
        ],
      },
    },
    {
      name: "PlatformConfig",
      type: {
        kind: "struct",
        fields: [
          { name: "authority", type: "publicKey" },
          { name: "treasury", type: "publicKey" },
          { name: "usdcMint", type: "publicKey" },
          { name: "platformFeeBps", type: "u16" },
          { name: "paused", type: "bool" },
          { name: "totalListings", type: "u64" },
          { name: "totalVolumeUsdc", type: "u64" },
          { name: "bump", type: "u8" },
        ],
      },
    },
  ],
  events: [
    {
      name: "MemoryListed",
      fields: [
        { name: "listing", type: "publicKey", index: false },
        { name: "seller", type: "publicKey", index: false },
        { name: "contentHash", type: { array: ["u8", 32] }, index: false },
        { name: "priceUsdc", type: "u64", index: false },
        { name: "modelId", type: "string", index: false },
      ],
    },
    {
      name: "MemoryPurchased",
      fields: [
        { name: "buyer", type: "publicKey", index: false },
        { name: "listing", type: "publicKey", index: false },
        { name: "arweaveTx", type: "string", index: false },
        { name: "priceUsdc", type: "u64", index: false },
        { name: "timestamp", type: "i64", index: false },
      ],
    },
    {
      name: "SandboxAccessGranted",
      fields: [
        { name: "buyer", type: "publicKey", index: false },
        { name: "listing", type: "publicKey", index: false },
        { name: "expiresAt", type: "i64", index: false },
      ],
    },
    {
      name: "DecisionAnchored",
      fields: [
        { name: "agentId", type: "publicKey", index: false },
        { name: "decisionType", type: "string", index: false },
        { name: "contextHash", type: { array: ["u8", 32] }, index: false },
        { name: "slot", type: "u64", index: false },
        { name: "timestamp", type: "i64", index: false },
      ],
    },
    {
      name: "ListingDelisted",
      fields: [
        { name: "listing", type: "publicKey", index: false },
        { name: "seller", type: "publicKey", index: false },
      ],
    },
    {
      name: "ListingPriceUpdated",
      fields: [
        { name: "listing", type: "publicKey", index: false },
        { name: "seller", type: "publicKey", index: false },
        { name: "newPriceUsdc", type: "u64", index: false },
        { name: "newSandboxPriceUsdc", type: "u64", index: false },
      ],
    },
  ],
  errors: [
    { code: 6000, name: "ListingInactive", msg: "Listing is not active" },
    { code: 6001, name: "InsufficientFunds", msg: "Insufficient USDC balance" },
    { code: 6002, name: "InvalidHash", msg: "Hash format is invalid" },
    { code: 6003, name: "SandboxExpired", msg: "Sandbox access has expired" },
    { code: 6004, name: "NoQueriesRemaining", msg: "No sandbox queries remaining" },
    { code: 6005, name: "Unauthorized", msg: "Caller is not authorized for this action" },
    { code: 6006, name: "TitleTooLong", msg: "Title exceeds maximum length (128)" },
    { code: 6007, name: "TooManyTags", msg: "Tags array exceeds maximum size (10)" },
    { code: 6008, name: "TagTooLong", msg: "A tag exceeds the maximum length (32)" },
    { code: 6009, name: "ModelIdTooLong", msg: "Model id exceeds maximum length (64)" },
    { code: 6010, name: "InvalidArweaveTx", msg: "Arweave TX must be exactly 43 characters" },
    { code: 6011, name: "DecisionDataTooLarge", msg: "Decision data exceeds 256 bytes" },
    { code: 6012, name: "DecisionTypeTooLong", msg: "Decision type exceeds 32 characters" },
    { code: 6013, name: "PlatformPaused", msg: "Platform is currently paused" },
    { code: 6014, name: "InvalidPrice", msg: "Price must be greater than zero" },
    { code: 6015, name: "InvalidQuantization", msg: "Bits per channel must be 25, 35, or 40" },
    { code: 6016, name: "MathOverflow", msg: "Math overflow" },
    { code: 6017, name: "UsdcMintMismatch", msg: "USDC mint mismatch" },
    { code: 6018, name: "TreasuryMismatch", msg: "Treasury account mismatch" },
    { code: 6019, name: "InvalidFeeBps", msg: "Fee bps must be <= 10000" },
  ],
  metadata: {
    address: "HvWGEDbnRCVThyCNwUVpFRfWsHx2aqT9Ttotr4QovGCF",
  },
} as const;

export type AgentVaultIDL = typeof AGENTVAULT_IDL;
