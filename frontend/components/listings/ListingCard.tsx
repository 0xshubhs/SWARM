"use client";
import Link from "next/link";
import { Sparkles, ShoppingCart } from "lucide-react";
import { Card, CardHeader, CardContent, CardFooter } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatUsdc } from "@/lib/format";
import type { ListingDTO } from "@agentvault/types";

export function ListingCard({ listing }: { listing: ListingDTO }) {
  const compressedMB = (listing.seq_len * 0.05).toFixed(0); // rough estimate
  return (
    <Card className="hover:border-zinc-700 group">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between text-xs">
          <Badge variant="outline" className="font-mono">{listing.model_id}</Badge>
          <span className="text-zinc-500 font-mono">{listing.purchases} sold</span>
        </div>
        <Link href={`/listing/${listing.id}`}>
          <h3 className="text-lg font-semibold leading-snug mt-2 group-hover:text-white transition-colors">
            {listing.title}
          </h3>
        </Link>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-3 gap-2">
          <Stat label="tokens" value={listing.seq_len.toLocaleString()} />
          <Stat label="precision" value={`${(listing.bits_per_channel / 10).toFixed(1)}b`} />
          <Stat label="size" value={`~${compressedMB}MB`} />
        </div>
        <div className="flex flex-wrap gap-1">
          {listing.tags.slice(0, 4).map((t) => (
            <Badge key={t} variant="secondary">{t}</Badge>
          ))}
          {listing.tags.length > 4 && (
            <Badge variant="secondary">+{listing.tags.length - 4}</Badge>
          )}
        </div>
      </CardContent>
      <CardFooter className="gap-2">
        <Button variant="outline" size="sm" className="flex-1">
          <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Try · {formatUsdc(listing.sandbox_price_usdc)}
        </Button>
        <Button size="sm" className="flex-1">
          <ShoppingCart className="w-3.5 h-3.5 mr-1.5" /> Buy · {formatUsdc(listing.price_usdc)}
        </Button>
      </CardFooter>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-mono text-sm">{value}</div>
      <div className="text-xs text-zinc-500">{label}</div>
    </div>
  );
}
