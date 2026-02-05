"use client";

import { ScriptControl } from "@/components/ScriptControl";
import { LogViewer } from "@/components/LogViewer";
import { UDPController } from "@/components/UDPController";
import { Chip } from "@heroui/react";
import { Cpu, Wifi, Activity } from "lucide-react";
import { useEffect, useState } from "react";

export default function Dashboard() {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <main className="min-h-screen bg-black text-zinc-100 p-4 md:p-8 selection:bg-cyan-500/30">
      {/* Header section */}
      <header className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-end justify-between gap-4 mb-12">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-linear-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Activity className="text-white" size={24} />
            </div>
            <h1 className="text-3xl font-black tracking-tight uppercase italic underline decoration-cyan-500 underline-offset-8">
              RPLidar <span className="text-cyan-500">Monitor</span>
            </h1>
          </div>
          <p className="text-zinc-500 font-medium">Raspberry Pi 5 Dashboard • Expérience Interactive</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Chip
            startContent={<Cpu size={14} />}
            variant="flat"
            className="bg-zinc-900 border-zinc-800 text-zinc-400"
          >
            RPi 5 Online
          </Chip>
          <Chip
            startContent={<Wifi size={14} />}
            variant="flat"
            color="success"
            className="bg-zinc-900 border-zinc-800"
          >
            UDP: 5005
          </Chip>
          <div className="px-4 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-xs font-mono text-cyan-500 shadow-inner">
            {now.toLocaleTimeString()}
          </div>
        </div>
      </header>

      {/* Grid Layout */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column - Controls & UDP */}
        <div className="lg:col-span-12 xl:col-span-8 flex flex-col gap-8">
          <section>
            <UDPController />
          </section>

          <section className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <ScriptControl />
            {/* Placeholder for future telemetry or stats */}
            <div className="rounded-3xl border-2 border-dashed border-zinc-800 flex items-center justify-center p-8 bg-zinc-900/20">
              <div className="text-center">
                <Activity size={48} className="mx-auto text-zinc-800 mb-4" />
                <p className="text-zinc-600 font-medium italic">Telemetry Visualization Coming Soon</p>
              </div>
            </div>
          </section>
        </div>

        {/* Right Column - Logs */}
        <div className="lg:col-span-12 xl:col-span-4">
          <section className="sticky top-8">
            <LogViewer />
          </section>
        </div>
      </div>

      {/* Background decoration */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none -z-10 overflow-hidden">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-cyan-500/10 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/10 blur-[120px] rounded-full" />
      </div>
    </main>
  );
}
