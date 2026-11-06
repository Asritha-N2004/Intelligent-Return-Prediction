"use client";
import {useEffect,useState} from 'react';
import {usePathname,useRouter} from 'next/navigation';
import {PackageCheck} from 'lucide-react';
export default function AuthGate({children}:{children:React.ReactNode}){
 const pathname=usePathname(),router=useRouter();
 const [verified,setVerified]=useState(false);
 useEffect(()=>{let active=true;setVerified(false);if(['/login','/create-account'].includes(pathname))return;fetch('/api/auth/me',{cache:'no-store'}).then(r=>{if(!active)return;if(r.ok)setVerified(true);else router.replace('/login')}).catch(()=>{if(active)router.replace('/login')});return()=>{active=false}},[pathname,router]);
 if(['/login','/create-account'].includes(pathname))return <>{children}</>;
 if(!verified)return <div className="auth-loading"><PackageCheck size={32}/><p>Opening your workspace…</p></div>;
 return <>{children}</>;
}
