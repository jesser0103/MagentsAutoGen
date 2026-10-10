import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { Toaster } from 'sonner';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'Magent Control Plane',
  description: 'Approval-Gated Multi-Agent Cloud Infrastructure Automation',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans selection:bg-cyan-400/20`}>
        {children}
        <Toaster
          theme="dark"
          position="bottom-right"
          richColors
          toastOptions={{
            style: {
              background: 'hsl(217 33% 12%)',
              border: '1px solid rgba(255,255,255,0.08)',
              color: 'hsl(210 40% 98%)',
            },
          }}
        />
      </body>
    </html>
  );
}
