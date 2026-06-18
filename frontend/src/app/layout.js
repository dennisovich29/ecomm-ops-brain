import './globals.css'

export const metadata = {
  title: 'Ops Brain — AI E-commerce Operations',
  description: 'AI-powered multi-agent operations intelligence for e-commerce',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
