"use client";

import { ScriptControl } from "@/components/rplidar/ScriptControl";
import { LogViewer } from "@/components/rplidar/LogViewer";
import { UDPController } from "@/components/rplidar/UDPController";
import { Chip } from "@heroui/react";
import { Cpu, Wifi, Activity, Radar } from "lucide-react";
import { useEffect, useState } from "react";

export default function Dashboard() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <main className="min-h-screen bg-black text-zinc-100 p-4 md:p-8 selection:bg-cyan-500/30">
      {/* Background Decor */}
      <div className="fixed inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(24,24,27,1)_0%,rgba(0,0,0,1)_100%)] -z-10" />
      <div className="fixed top-0 left-0 w-full h-full bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none -z-10" />

      <header className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-end justify-between gap-4 mb-12">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-linear-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Activity className="text-white" size={24} />
            </div>
            <h1 className="text-3xl font-black tracking-tight uppercase italic underline decoration-cyan-500 underline-offset-8">
              RPLidar <span className="text-cyan-500">Dash</span>
            </h1>
          </div>
          <p className="text-zinc-500 font-medium tracking-wide">SYSTEM MONITORING & CONTROL / RASPBERRY PI 5</p>
        </div>

        <div className="flex items-center gap-4 bg-zinc-900/40 backdrop-blur-xl p-4 rounded-2xl border border-zinc-800/50">
          <div className="flex flex-col items-end">
            <span className="text-xs text-zinc-500 font-bold uppercase tracking-tighter">System Time</span>
            <span className="text-xl font-mono font-bold text-zinc-100 tabular-nums">
              {time.toLocaleTimeString()}
            </span>
          </div>
          <div className="w-[1px] h-10 bg-zinc-800" />
          <div className="flex gap-2">
            <Chip startContent={<Cpu size={14} />} variant="flat" color="primary" className="bg-blue-500/10 text-blue-400 border-none font-bold">87% CPU</Chip>
            <Chip startContent={<Wifi size={14} />} variant="flat" color="success" className="bg-emerald-500/10 text-emerald-400 border-none font-bold">5005 ON</Chip>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 h-full">
        {/* Left Column - Controls & Telemetry */}
        <div className="lg:col-span-12 xl:col-span-8 flex flex-col gap-8">
          <section className="flex-1">
            <UDPController />
          </section>

          <section className="bg-zinc-900/30 border border-zinc-800/50 rounded-3xl p-8 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-cyan-500 shadow-[0_0_10px_rgba(6,182,212,0.5)]" />
                Visualisation Télémétrie
              </h3>
              <Chip size="sm" variant="bordered" className="border-zinc-700 text-zinc-400">Placeholder Radar</Chip>
            </div>
            <div className="aspect-video bg-zinc-950 rounded-2xl border border-zinc-800 flex items-center justify-center relative overflow-hidden group">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(6,182,212,0.05)_0%,transparent_70%)]" />
              <div className="flex flex-col items-center gap-4 text-zinc-700 group-hover:text-zinc-500 transition-colors">
                <Radar className="animate-pulse" size={48} />
                <p className="font-mono text-sm tracking-widest uppercase">Initializing Radar View...</p>
              </div>
            </div>
          </section>
        </div>

        {/* Right Column - Status & Logs */}
        <div className="lg:col-span-12 xl:col-span-4 flex flex-col gap-8">
          <section>
            <ScriptControl />
          </section>
          <section className="flex-1">
            <LogViewer />
          </section>
        </div>
      </div>

      <footer className="max-w-7xl mx-auto mt-12 pb-8 border-t border-zinc-900 pt-8 flex justify-between items-center text-zinc-600 text-xs font-medium uppercase tracking-widest">
        <div>RP-C1-UDP-01 // PRODUCTION READY</div>
        <div className="flex gap-4">
          <span className="hover:text-cyan-500 cursor-pointer transition-colors">Documentation</span>
          <span className="hover:text-cyan-500 cursor-pointer transition-colors">Support</span>
        </div>
      </footer>
    </main>
  );
}
