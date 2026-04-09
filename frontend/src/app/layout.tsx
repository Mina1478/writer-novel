import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { TaskSidebar } from "@/components/layout/TaskSidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TiniX Story - AI Novel Creator",
  description: "Create amazing stories with AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} antialiased dark`}
    >
      <body className="flex min-h-screen text-foreground selection:bg-brand-primary/30">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
        <TaskSidebar />
      </body>
    </html>
  );
}
