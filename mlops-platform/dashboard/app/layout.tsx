"use client";

import "./globals.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Inter } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { useState } from "react";

import Navbar from "@/components/Navbar";
import Sidebar from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"] });

/** Root layout with sidebar + top navbar, theme provider, and React Query provider. */
export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} bg-zinc-950 text-zinc-100`}>
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <QueryClientProvider client={queryClient}>
            <div className="min-h-screen w-full">
              <div className="flex min-h-screen w-full">
                <div className="w-[240px] border-r border-zinc-800 bg-zinc-950">
                  <Sidebar />
                </div>
                <div className="flex min-w-0 flex-1 flex-col">
                  <div className="border-b border-zinc-800">
                    <Navbar />
                  </div>
                  <main className="min-w-0 flex-1 p-6">{children}</main>
                </div>
              </div>
            </div>
          </QueryClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
