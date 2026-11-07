import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'DetectivePM | India Product Management Jobs',
  description: 'Verified Product Management internships and early-career roles in India, from legitimate sources.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#090d16] text-slate-100 antialiased selection:bg-indigo-500 selection:text-white">
        {children}
      </body>
    </html>
  )
}
