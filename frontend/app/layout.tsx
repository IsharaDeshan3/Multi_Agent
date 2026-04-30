import "./globals.css";

import type { Metadata } from "next";
import { Newsreader, Space_Grotesk } from "next/font/google";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space",
  display: "swap",
});

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-news",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Research Review Dashboard",
  description: "Monitor backend health and workflow progress.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${newsreader.variable}`}>
      <body>{children}</body>
    </html>
  );
}
