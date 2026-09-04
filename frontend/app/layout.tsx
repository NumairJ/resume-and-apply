import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Navbar } from "@/components/Navbar";
import Providers from "./providers";
import "./globals.css";

// Self-hosted at build time by next/font, so the app has no runtime dependency on
// Google's CDN — which matters for something meant to run locally. The variable is
// consumed by --font-sans in globals.css.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Resume and Apply",
  description: "Resume tailoring using AI and Job Tracking",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen font-sans antialiased">
        <Providers>
          <Navbar />
          {children}
        </Providers>
      </body>
    </html>
  );
}
