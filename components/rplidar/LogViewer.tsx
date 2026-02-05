"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardHeader, CardBody, ScrollShadow, Divider, Tabs, Tab } from "@heroui/react";
import { Terminal } from "lucide-react";

export function LogViewer() {
    const [logs, setLogs] = useState<Record<string, string[]>>({});
    const [selectedScript, setSelectedScript] = useState("boot");
    const scrollRef = useRef<HTMLDivElement>(null);

    const fetchLogs = async () => {
        try {
            const res = await fetch("/api/scripts");
            const data = await res.json();
            const newLogs: Record<string, string[]> = {};
            Object.keys(data).forEach((key) => {
                newLogs[key] = data[key].logs;
            });
            setLogs(newLogs);
        } catch (e) {
            console.error("Failed to fetch logs", e);
        }
    };

    useEffect(() => {
        fetchLogs();
        const interval = setInterval(fetchLogs, 2000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs, selectedScript]);

    const currentLogs = logs[selectedScript] || [];

    return (
        <Card className="bg-zinc-900/50 border-zinc-800 shadow-xl backdrop-blur-md h-[500px]">
            <CardHeader className="flex flex-col items-start px-6 pt-6">
                <div className="flex items-center gap-2">
                    <Terminal size={20} className="text-cyan-400" />
                    <h2 className="text-xl font-bold bg-linear-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
                        Logs Console
                    </h2>
                </div>
                <p className="text-sm text-zinc-400">Sortie en direct des processus</p>
            </CardHeader>
            <Divider className="my-2 bg-zinc-800" />
            <CardBody className="p-0">
                <Tabs
                    variant="underlined"
                    aria-label="Script logs"
                    selectedKey={selectedScript}
                    onSelectionChange={(key) => setSelectedScript(key as string)}
                    className="px-6"
                    classNames={{
                        tabList: "gap-6 w-full relative rounded-none p-0 border-b border-divider",
                        cursor: "w-full bg-cyan-400",
                        tab: "max-w-fit px-0 h-12",
                        tabContent: "group-data-[selected=true]:text-cyan-400"
                    }}
                >
                    <Tab key="boot" title="Boot" />
                    <Tab key="stop" title="Stop" />
                    <Tab key="toTouch" title="Touch" />
                </Tabs>
                <ScrollShadow ref={scrollRef} className="flex-1 p-6 font-mono text-xs bg-black/40 h-full overflow-y-auto">
                    {currentLogs.length === 0 ? (
                        <div className="text-zinc-600 italic">Aucun log disponible pour ce script...</div>
                    ) : (
                        currentLogs.map((log, i) => (
                            <div key={i} className="mb-1 text-zinc-300 whitespace-pre-wrap">
                                <span className="text-zinc-600 mr-2">[{i}]</span>
                                {log}
                            </div>
                        ))
                    )}
                </ScrollShadow>
            </CardBody>
        </Card>
    );
}
