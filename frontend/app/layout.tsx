import "./globals.css";
import type { Metadata, Viewport } from "next";
import Shell from "@/components/Shell";
import { Providers } from "@/components/Providers";

export const metadata: Metadata = {
  title: "Brandwright | Brand governance",
  description: "Pre-publication brand governance. AI explains and suggests. Humans decide.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" data-scroll-behavior="smooth"><body><Providers><Shell>{children}</Shell></Providers></body></html>;
}
