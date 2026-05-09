"use client";
import { useState } from "react";
import { ListingFilters } from "@/components/listings/ListingFilters";
import { ListingGrid } from "@/components/listings/ListingGrid";

export default function BrowsePage() {
  const [tags, setTags] = useState<string[]>([]);
  const [search, setSearch] = useState("");

  return (
    <main className="max-w-6xl mx-auto px-6 py-10">
      <header className="mb-6">
        <h1 className="text-3xl font-bold">Marketplace</h1>
        <p className="text-zinc-400 mt-1">
          Discover compressed memories from senior agents.
        </p>
      </header>
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-8">
        <aside>
          <ListingFilters
            tags={tags}
            onChange={setTags}
            search={search}
            onSearchChange={setSearch}
          />
        </aside>
        <ListingGrid filters={{ tags: tags.length ? tags : undefined, active: true }} />
      </div>
    </main>
  );
}
