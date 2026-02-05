"use client";

import { ScriptControl } from "@/components/ScriptControl";
import { LogViewer } from "@/components/LogViewer";
import { UDPController } from "@/components/UDPController";
import { RadarView } from "@/components/RadarView";
import { LidarConfig } from "@/components/LidarConfig";
import { useEffect, useState } from "react";

export default function Dashboard() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-900 p-4 md:p-8">
      <header className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 pb-6 border-b border-zinc-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900">
            Interface RPLidar C1
          </h1>
          <p className="text-zinc-500 text-sm">Contrôle Tactile — Raspberry Pi 5</p>
        </div>

        <div className="flex items-center gap-6 text-sm font-medium">
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-zinc-400 uppercase tracking-wider">Temps Réel</span>
            <span className="font-mono text-zinc-700">{time.toLocaleTimeString()}</span>
          </div>
          <div className="w-px h-8 bg-zinc-200" />
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[11px] font-bold uppercase tracking-tighter">System Ready</span>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column - Visualization & Config */}
        <div className="lg:col-span-12 xl:col-span-8 flex flex-col gap-6">
          <section className="h-[500px]">
            <RadarView />
          </section>

          <section>
            <UDPController />
          </section>
        </div>

        {/* Right Column - Controls & Logs */}
        <div className="lg:col-span-12 xl:col-span-4 flex flex-col gap-6">
          <section>
            <ScriptControl />
          </section>

          <section>
            <LidarConfig />
          </section>

          <section className="flex-1 min-h-[400px]">
            <LogViewer />
          </section>
        </div>
      </div>

      <footer className="max-w-7xl mx-auto mt-12 pb-8 pt-6 border-t border-zinc-200 flex justify-between items-center text-zinc-400 text-[10px] font-medium uppercase tracking-widest">
        <div>RP-C1-UDP-01 // PRODUCTION</div>
        <div className="flex gap-4">
          <span>v2.0.0</span>
          <span>Support Tactile</span>
        </div>
      </footer>
    </main>
  );
}
