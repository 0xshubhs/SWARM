"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { ListingsQuery } from "@agentvault/types";

export function useListings(filters: ListingsQuery = {}) {
  return useQuery({
    queryKey: ["listings", filters],
    queryFn: () => api.listListings(filters),
  });
}

export function useListing(id: string | undefined) {
  return useQuery({
    queryKey: ["listing", id],
    queryFn: () => (id ? api.getListing(id) : Promise.reject(new Error("no id"))),
    enabled: Boolean(id),
  });
}
