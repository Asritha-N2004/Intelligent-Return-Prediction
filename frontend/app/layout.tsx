import AuthGate from '../components/AuthGate';
import './globals.css';
import type { Metadata } from 'next';
export const metadata: Metadata = {title:'ReturnWise AI | Returns Intelligence',description:'Predict returns. Recover value. Optimize every journey.'};
export default function RootLayout({children}:{children:React.ReactNode}) {return <html lang="en"><body><AuthGate>{children}</AuthGate></body></html>}
