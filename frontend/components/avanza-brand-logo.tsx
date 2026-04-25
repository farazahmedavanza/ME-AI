"use client";

import Image from "next/image";
import { cn } from "@/lib/cn";

const heights = { sm: 32, md: 40, lg: 48 } as const;
const AVANZA_LOGO_SRC = "/Avanza-logo.png?v=20260425";

export function AvanzaBrandLogo({
  className,
  size = "md",
  priority = false,
  centered = false,
}: {
  className?: string;
  size?: keyof typeof heights;
  priority?: boolean;
  centered?: boolean;
}) {
  const h = heights[size];
  return (
    <Image
      src={AVANZA_LOGO_SRC}
      alt="Avanza Solutions"
      width={220}
      height={h}
      className={cn(
        "h-auto w-auto max-w-full object-contain",
        centered ? "object-center mx-auto" : "object-left",
        className
      )}
      style={{ height: h, width: "auto" }}
      priority={priority}
    />
  );
}
