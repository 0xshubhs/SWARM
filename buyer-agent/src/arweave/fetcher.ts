export async function fetchFromArweave(
  arweaveTx: string,
  onProgress?: (bytes: number) => void,
): Promise<Buffer> {
  const r = await fetch(`https://arweave.net/${arweaveTx}`);
  if (!r.ok) throw new Error(`Arweave fetch failed: ${r.status}`);
  const reader = r.body!.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value) {
      chunks.push(value);
      total += value.length;
      onProgress?.(total);
    }
  }
  return Buffer.concat(chunks.map((c) => Buffer.from(c)));
}
