"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardHeader, CardBody, Chip } from "@heroui/react";
import { Radar, Maximize2, RotateCcw } from "lucide-react";

export function RadarView() {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [points, setPoints] = useState<any[]>([]);
    const [roi, setRoi] = useState({ w: 1000, d: 1000 });
    const [lastUpdate, setLastUpdate] = useState<string>("");

    const fetchPoints = async () => {
        try {
            const res = await fetch("/api/udp");
            const data = await res.json();

            // Find the latest lidar_points message
            const lidarMsg = [...data].reverse().find(m => m.type === "lidar_points");
            if (lidarMsg) {
                setPoints(lidarMsg.points || []);
                setRoi(lidarMsg.roi || { w: 1000, d: 1000 });
                setLastUpdate(new Date(lidarMsg.timestamp).toLocaleTimeString());
            }
        } catch (e) {
            console.error("Failed to fetch radar points", e);
        }
    };

    useEffect(() => {
        const interval = setInterval(fetchPoints, 100); // 10Hz UI update
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        // Clear canvas
        ctx.fillStyle = "#fafafa";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const padding = 40;
        const drawW = canvas.width - padding * 2;
        const drawH = canvas.height - padding * 2;

        // Draw Grid
        ctx.strokeStyle = "#e5e7eb";
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);

        // Vertical lines
        for (let i = 0; i <= 4; i++) {
            const x = padding + (drawW * i) / 4;
            ctx.beginPath();
            ctx.moveTo(x, padding);
            ctx.lineTo(x, padding + drawH);
            ctx.stroke();
        }

        // Horizontal lines
        for (let i = 0; i <= 4; i++) {
            const y = padding + (drawH * i) / 4;
            ctx.beginPath();
            ctx.moveTo(padding, y);
            ctx.lineTo(padding + drawW, y);
            ctx.stroke();
        }
        ctx.setLineDash([]);

        // Draw ROI Border
        ctx.strokeStyle = "#0ea5e9";
        ctx.lineWidth = 2;
        ctx.strokeRect(padding, padding, drawW, drawH);

        // Draw Lidar Origin (0,0) - centered at top
        ctx.fillStyle = "#ef4444";
        ctx.beginPath();
        const originX = padding + drawW / 2;
        const originY = padding;
        ctx.arc(originX, originY, 6, 0, Math.PI * 2);
        ctx.fill();

        // Draw Field of View (visual help)
        ctx.strokeStyle = "rgba(14, 165, 233, 0.1)";
        ctx.beginPath();
        ctx.moveTo(originX, originY);
        ctx.lineTo(padding, padding + drawH);
        ctx.lineTo(padding + drawW, padding + drawH);
        ctx.closePath();
        ctx.fill();

        // Draw Points
        // points[i] are {x: 0..1, y: 0..1}
        // x=0 is left, x=1 is right
        // y=0 is lidar, y=1 is max depth
        ctx.fillStyle = "#18181b";
        points.forEach(p => {
            const px = padding + p.x * drawW;
            const py = padding + p.y * drawH;
            ctx.beginPath();
            ctx.arc(px, py, 3, 0, Math.PI * 2);
            ctx.fill();
        });

        // Label
        ctx.fillStyle = "#94a3b8";
        ctx.font = "10px monospace";
        ctx.fillText(`${roi.w}mm`, padding + drawW / 2 - 20, padding + drawH + 20);
        ctx.save();
        ctx.translate(padding - 20, padding + drawH / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText(`${roi.d}mm`, -20, 0);
        ctx.restore();

    }, [points, roi]);

    return (
        <Card className="bg-white border-zinc-200 shadow-sm overflow-hidden h-full">
            <CardHeader className="flex flex-row items-center justify-between px-6 pt-5">
                <div className="flex flex-col">
                    <h2 className="text-base font-bold text-zinc-800 flex items-center gap-2">
                        <Radar size={18} className="text-sky-500" /> Visualisation Radar
                    </h2>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-widest">
                        RPLidar ROI View {lastUpdate && `— ${lastUpdate}`}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Chip size="sm" variant="flat" color="primary" className="font-mono text-[10px]">
                        {points.length} PTS
                    </Chip>
                </div>
            </CardHeader>
            <CardBody className="p-0 flex items-center justify-center bg-zinc-50/50">
                <canvas
                    ref={canvasRef}
                    width={600}
                    height={400}
                    className="w-full h-auto max-w-full aspect-video touch-none"
                />
            </CardBody>
        </Card>
    );
}
