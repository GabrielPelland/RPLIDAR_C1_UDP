"use client";
//
import { useState } from "react";
import { Card, CardHeader, CardBody, Input, Button, Divider, Slider } from "@heroui/react";
import { Settings2, Save, RefreshCw } from "lucide-react";

export function LidarConfig() {
    const [config, setConfig] = useState({
        ROI_WIDTH: 1000,
        ROI_DEPTH: 1000,
        ANGLE_OFFSET: 0.0,
        WINDOW_MS: 70,
        MIN_HITS: 2,
        MAX_DIST: 3000
    });
    const [loading, setLoading] = useState(false);

    const updateConfig = (key: string, value: number) => {
        const newConfig = { ...config, [key]: value };
        setConfig(newConfig);
        sendUpdate({ [key]: value });
    };

    const sendUpdate = async (payload: any) => {
        setLoading(true);
        try {
            await fetch("/api/udp", {
                method: "POST",
                body: JSON.stringify({
                    message: JSON.stringify(payload),
                    targetIP: "127.0.0.1",
                    targetPort: 5006, // Command port in python script
                }),
            });
        } catch (e) {
            console.error("Failed to update lidar config", e);
        } finally {
            setTimeout(() => setLoading(false), 300);
        }
    };

    return (
        <Card className="bg-white border-zinc-200 shadow-sm">
            <CardHeader className="flex flex-col items-start px-6 pt-5">
                <h2 className="text-base font-bold text-zinc-800 flex items-center gap-2">
                    <Settings2 size={16} /> Paramètres Lidar
                </h2>
                <p className="text-xs text-zinc-500">Ajustement en temps réel</p>
            </CardHeader>
            <Divider className="my-2 bg-zinc-100" />
            <CardBody className="gap-6 px-6 pb-6">
                <div className="space-y-4">
                    <Slider
                        label="Largeur ROI (mm)"
                        step={50}
                        minValue={200}
                        maxValue={3000}
                        value={config.ROI_WIDTH}
                        onChange={(v) => updateConfig("ROI_WIDTH", v as number)}
                        className="max-w-md"
                    />
                    <Slider
                        label="Profondeur ROI (mm)"
                        step={50}
                        minValue={200}
                        maxValue={3000}
                        value={config.ROI_DEPTH}
                        onChange={(v) => updateConfig("ROI_DEPTH", v as number)}
                        className="max-w-md"
                    />
                    <div className="grid grid-cols-2 gap-4">
                        <Input
                            label="Angle Offset (°)"
                            size="sm"
                            type="number"
                            value={config.ANGLE_OFFSET.toString()}
                            onValueChange={(v) => updateConfig("ANGLE_OFFSET", parseFloat(v) || 0)}
                        />
                        <Input
                            label="Max Dist (mm)"
                            size="sm"
                            type="number"
                            value={config.MAX_DIST.toString()}
                            onValueChange={(v) => updateConfig("MAX_DIST", parseInt(v) || 0)}
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <Input
                            label="Window (ms)"
                            size="sm"
                            type="number"
                            value={config.WINDOW_MS.toString()}
                            onValueChange={(v) => updateConfig("WINDOW_MS", parseInt(v) || 0)}
                        />
                        <Input
                            label="Min Hits"
                            size="sm"
                            type="number"
                            value={config.MIN_HITS.toString()}
                            onValueChange={(v) => updateConfig("MIN_HITS", parseInt(v) || 0)}
                        />
                    </div>
                </div>

                <Button
                    variant="flat"
                    color="primary"
                    size="sm"
                    className="w-full font-bold"
                    isLoading={loading}
                    onPress={() => sendUpdate(config)}
                    startContent={!loading && <RefreshCw size={14} />}
                >
                    SYNCHRONISER TOUT
                </Button>
            </CardBody>
        </Card>
    );
}
