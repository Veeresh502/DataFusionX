import React from 'react';
import { Sidebar } from '../components/Sidebar';
import { Navbar } from '../components/Navbar';

interface MainLayoutProps {
  children: React.ReactNode;
  onRefresh?: () => void;
  lastChecked?: Date | null;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  children,
  onRefresh,
  lastChecked,
}) => {
  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Navbar onRefresh={onRefresh} lastChecked={lastChecked} />
        <main className="flex-1 p-6 md:p-8 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
};
