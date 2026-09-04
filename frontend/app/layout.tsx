import type { Metadata } from "next";

import Providers from "./providers";
import "./globals.css";

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
    <html lang="en">
      <body className="min-h-screen antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
