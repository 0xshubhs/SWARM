import { BACKEND_URL } from "./constants";
import type {
  ListingDTO,
  ListingsPage,
  ListingsQuery,
  FeeBreakdown,
  UploadInitRequest,
  UploadInitResponse,
  UploadFinalizeRequest,
  UploadFinalizeResponse,
  VerifyHashResponse,
  DecisionDTO,
} from "@agentvault/types";

async function jfetch<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`${r.status} ${r.statusText}: ${text}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  pricing(sizeBytes: number): Promise<FeeBreakdown> {
    return jfetch<FeeBreakdown>(`/v1/pricing?size_bytes=${sizeBytes}`);
  },

  listListings(q: ListingsQuery = {}): Promise<ListingsPage> {
    const p = new URLSearchParams();
    if (q.tags?.length) p.set("tags", q.tags.join(","));
    if (q.model) p.set("model", q.model);
    if (q.minPrice !== undefined) p.set("min_price", String(q.minPrice));
    if (q.maxPrice !== undefined) p.set("max_price", String(q.maxPrice));
    if (q.seller) p.set("seller", q.seller);
    if (q.active !== undefined) p.set("active", String(q.active));
    if (q.sort) p.set("sort", q.sort);
    if (q.limit) p.set("limit", String(q.limit));
    if (q.cursor) p.set("cursor", q.cursor);
    return jfetch<ListingsPage>(`/v1/listings?${p.toString()}`);
  },

  getListing(id: string): Promise<ListingDTO> {
    return jfetch<ListingDTO>(`/v1/listings/${id}`);
  },

  initUpload(body: UploadInitRequest): Promise<UploadInitResponse> {
    return jfetch<UploadInitResponse>("/v1/upload/init", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  finalizeUpload(body: UploadFinalizeRequest): Promise<UploadFinalizeResponse> {
    return jfetch<UploadFinalizeResponse>("/v1/upload/finalize", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  verify(contentHashHex: string): Promise<VerifyHashResponse> {
    return jfetch<VerifyHashResponse>(`/v1/verify/${contentHashHex}`);
  },

  decisions(agentId: string): Promise<{ items: DecisionDTO[]; nextCursor: string | null }> {
    return jfetch(`/v1/decisions/${agentId}`);
  },
};
