"use client";

import { ScriptControl } from "@/components/ScriptControl";
import { LogViewer } from "@/components/LogViewer";
import { UDPController } from "@/components/UDPController";
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
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            Système de contrôle
          </h1>
          <p className="text-zinc-500 text-sm">Monitoring & Pilotage RPLidar / Raspberry Pi 5</p>
        </div>

        <div className="flex items-center gap-6 text-sm font-medium">
          <div className="flex flex-col items-end">
            <span className="text-[10px] text-zinc-400 uppercase tracking-wider">Heure Système</span>
            <span className="font-mono text-zinc-700">{time.toLocaleTimeString()}</span>
          </div>
          <div className="w-px h-8 bg-zinc-200" />
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-emerald-500" />
              <span>Port 5005 ON</span>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column - Controls & Telemetry */}
        <div className="lg:col-span-12 xl:col-span-8 flex flex-col gap-6">
          <section>
            <UDPController />
          </section>

          <section className="bg-white border border-zinc-200 rounded-xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-zinc-800">Visualisation Télémétrie</h3>
              <span className="text-xs text-zinc-400 px-2 py-0.5 border border-zinc-200 rounded-full">Radar View</span>
            </div>
            <div className="aspect-video bg-zinc-50 rounded-lg border border-zinc-100 flex items-center justify-center">
              <p className="text-zinc-400 font-mono text-sm uppercase tracking-widest">Initialisation du flux...</p>
            </div>
          </section>
        </div>

        {/* Right Column - Status & Logs */}
        <div className="lg:col-span-12 xl:col-span-4 flex flex-col gap-6">
          <section>
            <ScriptControl />
          </section>
          <section className="flex-1">
            <LogViewer />
          </section>
        </div>
      </div>

      <footer className="max-w-7xl mx-auto mt-12 pb-8 pt-6 border-t border-zinc-200 flex justify-between items-center text-zinc-400 text-[10px] font-medium uppercase tracking-widest">
        <div>RP-C1-UDP-01 // PRODUCTION</div>
        <div className="flex gap-4">
          <span>Documentation</span>
          <span>Support</span>
        </div>
      </footer>
    </main>
  );
}
