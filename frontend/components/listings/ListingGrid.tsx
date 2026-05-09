"use client";
import { ListingCard } from "./ListingCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/shared/EmptyState";
import { useListings } from "@/lib/hooks/useListings";
import { Database } from "lucide-react";
import type { ListingsQuery } from "@agentvault/types";

export function ListingGrid({ filters }: { filters: ListingsQuery }) {
  const { data, isLoading, error } = useListings(filters);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-64" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        icon={Database}
        title="Failed to load listings"
        description={String(error)}
      />
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <EmptyState
        icon={Database}
        title="No listings yet"
        description="Be the first to list a memory and earn when others use your trained context."
      />
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {data.items.map((l) => (
        <ListingCard key={l.id} listing={l} />
      ))}
    </div>
  );
}
