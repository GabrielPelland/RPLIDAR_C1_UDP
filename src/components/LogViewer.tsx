"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardHeader, CardBody, ScrollShadow, Divider, Tabs, Tab, Button } from "@heroui/react";
import { Terminal, Trash2, ChevronRight } from "lucide-react";

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
                newLogs[key] = data[key].logs || [];
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

    const clearLogs = () => {
        setLogs(prev => ({ ...prev, [selectedScript]: [] }));
    };

    const currentLogs = logs[selectedScript] || [];

    return (
        <Card className="bg-white border-zinc-200 shadow-sm h-[500px]">
            <CardHeader className="flex flex-row items-center justify-between px-6 pt-5">
                <div className="flex flex-col">
                    <h2 className="text-base font-bold text-zinc-800 flex items-center gap-2">
                        <Terminal size={16} /> Console Système
                    </h2>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-widest">Logs en direct</p>
                </div>
                <Button
                    size="sm"
                    variant="flat"
                    isIconOnly
                    onPress={clearLogs}
                    className="hover:bg-red-50 hover:text-red-500 transition-colors"
                >
                    <Trash2 size={14} />
                </Button>
            </CardHeader>

            <div className="px-6">
                <Tabs
                    variant="underlined"
                    selectedKey={selectedScript}
                    onSelectionChange={(key) => setSelectedScript(key as string)}
                    className="w-full"
                    classNames={{
                        tabList: "gap-4 border-b border-zinc-100 p-0 h-10",
                        cursor: "bg-zinc-800",
                        tab: "px-0 h-10",
                        tabContent: "text-zinc-400 group-data-[selected=true]:text-zinc-800 text-xs font-bold"
                    }}
                >
                    <Tab key="boot" title="BOOT" />
                    <Tab key="stop" title="STOP" />
                    <Tab key="toTouch" title="TOUCH" />
                </Tabs>
            </div>

            <CardBody className="p-0 bg-zinc-50/50">
                <ScrollShadow ref={scrollRef} className="flex-1 p-4 font-mono text-[11px] h-full overflow-y-auto">
                    {currentLogs.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-zinc-300 gap-2">
                            <Terminal size={32} strokeWidth={1} />
                            <span className="italic text-xs">Aucun log en attente...</span>
                        </div>
                    ) : (
                        <div className="flex flex-col">
                            {currentLogs.map((log, i) => (
                                <div key={i} className="flex gap-3 mb-1 group">
                                    <span className="text-zinc-400 shrink-0 w-8 text-right select-none">{i + 1}</span>
                                    <div className="flex items-start gap-1">
                                        <ChevronRight size={10} className="mt-0.5 text-zinc-400 opacity-0 group-hover:opacity-100" />
                                        <span className="text-zinc-700 break-all leading-relaxed">{log}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </ScrollShadow>
            </CardBody>
        </Card>
    );
}
