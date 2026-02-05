"use client";

import { useState, useEffect } from "react";
import { Card, CardHeader, CardBody, Button, Chip, Divider } from "@heroui/react";
import { Play, Square } from "lucide-react";

const SCRIPTS = [
    { name: "Lidar Touch", path: "rplidar_toTouch.py", id: "toTouch" },
];

export function ScriptControl() {
    const [statuses, setStatuses] = useState<Record<string, any>>({});
    const [loading, setLoading] = useState<string | null>(null);

    const fetchStatuses = async () => {
        try {
            const res = await fetch("/api/scripts");
            const data = await res.json();
            setStatuses(data);
        } catch (e) {
            console.error("Failed to fetch script statuses", e);
        }
    };

    useEffect(() => {
        fetchStatuses();
        const interval = setInterval(fetchStatuses, 2000);
        return () => clearInterval(interval);
    }, []);

    const handleAction = async (scriptId: string, scriptPath: string, action: "start" | "stop") => {
        setLoading(scriptId);
        try {
            await fetch("/api/scripts", {
                method: "POST",
                body: JSON.stringify({ action, scriptName: scriptId, scriptPath }),
            });
            fetchStatuses();
        } catch (e) {
            console.error(`Failed to ${action} script`, e);
        } finally {
            setLoading(null);
        }
    };

    return (
        <Card className="bg-white border-zinc-200 shadow-sm">
            <CardHeader className="flex flex-col items-start px-6 pt-5">
                <h2 className="text-base font-bold text-zinc-800">
                    Scripts Python
                </h2>
                <p className="text-xs text-zinc-500">Gestion des processus Raspberry Pi</p>
            </CardHeader>
            <Divider className="my-2 bg-zinc-100" />
            <CardBody className="gap-3 px-6 pb-6">
                {SCRIPTS.map((script) => {
                    const status = statuses[script.id]?.status || "stopped";
                    const isRunning = status === "running";

                    return (
                        <div key={script.id} className="flex items-center justify-between p-3 rounded-lg bg-zinc-50 border border-zinc-100">
                            <div className="flex flex-col">
                                <span className="text-sm font-medium text-zinc-700">{script.name}</span>
                                <span className="text-[10px] text-zinc-400 font-mono">{script.path}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <Chip
                                    color={isRunning ? "success" : status === "error" ? "danger" : "default"}
                                    variant="flat"
                                    size="sm"
                                    className="h-6 text-[10px] font-bold uppercase tracking-wider"
                                >
                                    {status}
                                </Chip>
                                <Button
                                    isIconOnly
                                    size="sm"
                                    variant="flat"
                                    color={isRunning ? "danger" : "primary"}
                                    isLoading={loading === script.id}
                                    onPress={() => handleAction(script.id, script.path, isRunning ? "stop" : "start")}
                                    className="w-8 h-8 min-w-8"
                                >
                                    {isRunning ? <Square size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
                                </Button>
                            </div>
                        </div>
                    );
                })}
            </CardBody>
        </Card>
    );
}
