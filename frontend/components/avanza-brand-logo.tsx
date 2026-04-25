"use client";

import Image from "next/image";
import { cn } from "@/lib/cn";

const heights = { sm: 32, md: 40, lg: 48 } as const;

export function AvanzaBrandLogo({
  className,
  size = "md",
  priority = false,
}: {
  className?: string;
  size?: keyof typeof heights;
  priority?: boolean;
}) {
  const h = heights[size];
  return (
    <Image
      src="/Avanza-logo.png"
      alt="Avanza Solutions"
      width={220}
      height={h}
      className={cn("h-auto w-auto max-w-full object-contain object-left", className)}
      style={{ height: h, width: "auto" }}
      priority={priority}
    />
  );
}
