import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "API Health & SLA Monitor | Avanza",
  description: "Intelligent API operations dashboard",
  icons: {
    icon: "/Avanza-logo.png",
    apple: "/Avanza-logo.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-avbg">{children}</body>
    </html>
  );
}
