import { PublicKey } from "@solana/web3.js";

export function findConfigPda(programId: PublicKey): [PublicKey, number] {
  return PublicKey.findProgramAddressSync([Buffer.from("config")], programId);
}

export function findListingPda(
  seller: PublicKey,
  contentHash: Buffer,
  programId: PublicKey,
): [PublicKey, number] {
  return PublicKey.findProgramAddressSync(
    [Buffer.from("listing"), seller.toBuffer(), contentHash],
    programId,
  );
}

export function findLicensePda(
  buyer: PublicKey,
  listing: PublicKey,
  programId: PublicKey,
): [PublicKey, number] {
  return PublicKey.findProgramAddressSync(
    [Buffer.from("license"), buyer.toBuffer(), listing.toBuffer()],
    programId,
  );
}

export function findSandboxPda(
  buyer: PublicKey,
  listing: PublicKey,
  programId: PublicKey,
): [PublicKey, number] {
  return PublicKey.findProgramAddressSync(
    [Buffer.from("sandbox"), buyer.toBuffer(), listing.toBuffer()],
    programId,
  );
}
