import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Providers from "./providers";
import Sidebar from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Agentic SDLC System Dashboard",
  description: "Real-time visualization and management of the AI SDLC pipeline",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full bg-zinc-950 text-zinc-100">
      <body className={`${inter.className} h-full flex overflow-hidden`}>
        <Providers>
          <Sidebar />
          <main className="flex-1 flex flex-col h-full overflow-hidden bg-zinc-950">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
