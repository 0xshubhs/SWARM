"use client";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";

interface Props {
  tags: string[];
  onChange: (tags: string[]) => void;
  search: string;
  onSearchChange: (v: string) => void;
}

const SUGGESTED = [
  "anchor",
  "solana",
  "rust",
  "defi",
  "drift",
  "jupiter",
  "dao",
  "governance",
];

export function ListingFilters({ tags, onChange, search, onSearchChange }: Props) {
  const toggle = (t: string) =>
    onChange(tags.includes(t) ? tags.filter((x) => x !== t) : [...tags, t]);

  return (
    <div className="space-y-3">
      <Input
        placeholder="Search listings..."
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
      />
      <div className="flex flex-wrap gap-1.5">
        {SUGGESTED.map((t) => (
          <button key={t} onClick={() => toggle(t)} className="cursor-pointer">
            <Badge variant={tags.includes(t) ? "default" : "outline"}>{t}</Badge>
          </button>
        ))}
      </div>
    </div>
  );
}
