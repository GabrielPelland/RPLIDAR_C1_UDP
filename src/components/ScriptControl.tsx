"use client";

import { useState, useEffect } from "react";
import { Card, CardHeader, CardBody, Button, Chip, Divider } from "@nextui-org/react";
import { Play, Square, Loader2 } from "lucide-react";

const SCRIPTS = [
    { name: "RPLidar Boot", path: "rplidar_boot.py", id: "boot" },
    { name: "RPLidar Stop", path: "rplidar_stop.py", id: "stop" },
    { name: "Lidar to Touch", path: "rplidar_toTouch.py", id: "toTouch" },
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
        <Card className="bg-zinc-900/50 border-zinc-800 shadow-xl backdrop-blur-md">
            <CardHeader className="flex flex-col items-start px-6 pt-6">
                <h2 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
                    Contrôle des Scripts
                </h2>
                <p className="text-sm text-zinc-400">Gérez les processus Python sur le Raspberry Pi</p>
            </CardHeader>
            <Divider className="my-2 bg-zinc-800" />
            <CardBody className="gap-4 px-6 pb-6">
                {SCRIPTS.map((script) => {
                    const status = statuses[script.id]?.status || "stopped";
                    const isRunning = status === "running";

                    return (
                        <div key={script.id} className="flex items-center justify-between p-3 rounded-xl bg-zinc-800/30 border border-zinc-700/50">
                            <div className="flex flex-col">
                                <span className="font-semibold text-zinc-100">{script.name}</span>
                                <span className="text-xs text-zinc-500 font-mono">{script.path}</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <Chip
                                    color={isRunning ? "success" : status === "error" ? "danger" : "default"}
                                    variant="flat"
                                    size="sm"
                                    className="capitalize"
                                >
                                    {status}
                                </Chip>
                                <Button
                                    isIconOnly
                                    size="sm"
                                    variant="shadow"
                                    color={isRunning ? "danger" : "success"}
                                    isLoading={loading === script.id}
                                    onPress={() => handleAction(script.id, script.path, isRunning ? "stop" : "start")}
                                >
                                    {isRunning ? <Square size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" />}
                                </Button>
                            </div>
                        </div>
                    );
                })}
            </CardBody>
        </Card>
    );
}
