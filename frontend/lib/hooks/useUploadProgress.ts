"use client";
import { useState, useCallback } from "react";
import { useWebSocket } from "./useWebSocket";
import { BACKEND_WS_URL } from "../constants";

export type UploadPhase =
  | "queued"
  | "compressing"
  | "uploading"
  | "listing_pending"
  | "confirmed"
  | "error";

export interface UploadProgress {
  phase: UploadPhase;
  compressPercent: number;
  uploadPercent: number;
  contentHash?: string;
  arweaveTx?: string;
  listingPda?: string;
  txSignature?: string;
  error?: string;
}

const INITIAL: UploadProgress = {
  phase: "queued",
  compressPercent: 0,
  uploadPercent: 0,
};

export function useUploadProgress(uploadId: string | null, wsToken: string | null) {
  const [progress, setProgress] = useState<UploadProgress>(INITIAL);

  const handleMessage = useCallback((msg: any) => {
    setProgress((prev) => {
      switch (msg.type) {
        case "upload.received":
          return { ...prev, phase: "compressing" };
        case "compress.progress":
          return { ...prev, compressPercent: msg.data.percent };
        case "compress.done":
          return {
            ...prev,
            compressPercent: 100,
            contentHash: msg.data.content_hash_hex,
            phase: "uploading",
          };
        case "arweave.upload.progress":
          return { ...prev, uploadPercent: msg.data.percent };
        case "arweave.upload.done":
          return { ...prev, uploadPercent: 100, arweaveTx: msg.data.arweave_tx };
        case "listing.pending":
          return { ...prev, phase: "listing_pending" };
        case "listing.confirmed":
          return {
            ...prev,
            phase: "confirmed",
            listingPda: msg.data.listing_pda,
            txSignature: msg.data.tx_signature,
          };
        case "error":
          return { ...prev, phase: "error", error: msg.data.message };
        default:
          return prev;
      }
    });
  }, []);

  useWebSocket({
    url: uploadId ? `${BACKEND_WS_URL}/v1/ws/upload/${uploadId}` : null,
    token: wsToken,
    onMessage: handleMessage,
  });

  return progress;
}
