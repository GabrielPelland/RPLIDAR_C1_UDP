"use client";

import { useState, useEffect } from "react";
import { Card, CardHeader, CardBody, Input, Button, Divider, ScrollShadow, Chip } from "@nextui-org/react";
import { Send, Radio, MessageSquare } from "lucide-react";

export function UDPController() {
    const [messages, setMessages] = useState<any[]>([]);
    const [targetIP, setTargetIP] = useState("192.168.0.12");
    const [targetPort, setTargetPort] = useState("5005");
    const [message, setMessage] = useState("");
    const [loading, setLoading] = useState(false);

    const fetchMessages = async () => {
        try {
            const res = await fetch("/api/udp");
            const data = await res.json();
            setMessages(data);
        } catch (e) {
            console.error("Failed to fetch UDP messages", e);
        }
    };

    useEffect(() => {
        fetchMessages();
        const interval = setInterval(fetchMessages, 2000);
        return () => clearInterval(interval);
    }, []);

    const handleSend = async () => {
        if (!message) return;
        setLoading(true);
        try {
            await fetch("/api/udp", {
                method: "POST",
                body: JSON.stringify({
                    message,
                    targetIP,
                    targetPort: parseInt(targetPort),
                }),
            });
            setMessage("");
        } catch (e) {
            console.error("Failed to send UDP message", e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 h-full">
            <Card className="bg-zinc-900/50 border-zinc-800 shadow-xl backdrop-blur-md">
                <CardHeader className="flex flex-col items-start px-6 pt-6">
                    <div className="flex items-center gap-2">
                        <Send size={20} className="text-purple-400" />
                        <h2 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
                            Envoyer UDP
                        </h2>
                    </div>
                    <p className="text-sm text-zinc-400">Envoyez des commandes aux périphériques réseau</p>
                </CardHeader>
                <Divider className="my-2 bg-zinc-800" />
                <CardBody className="gap-4 px-6 pb-6">
                    <div className="grid grid-cols-2 gap-4">
                        <Input
                            label="IP Cible"
                            size="sm"
                            value={targetIP}
                            onValueChange={setTargetIP}
                            variant="bordered"
                            classNames={{ inputWrapper: "border-zinc-700 bg-zinc-800/20" }}
                        />
                        <Input
                            label="Port"
                            size="sm"
                            value={targetPort}
                            onValueChange={setTargetPort}
                            variant="bordered"
                            classNames={{ inputWrapper: "border-zinc-700 bg-zinc-800/20" }}
                        />
                    </div>
                    <Input
                        label="Message (JSON ou string)"
                        placeholder='{"cmd": "start"}'
                        value={message}
                        onValueChange={setMessage}
                        variant="bordered"
                        classNames={{ inputWrapper: "border-zinc-700 bg-zinc-800/20" }}
                    />
                    <Button
                        color="secondary"
                        variant="shadow"
                        fullWidth
                        onPress={handleSend}
                        isLoading={loading}
                        startContent={!loading && <Send size={16} />}
                    >
                        Envoyer
                    </Button>
                </CardBody>
            </Card>

            <Card className="bg-zinc-900/50 border-zinc-800 shadow-xl backdrop-blur-md">
                <CardHeader className="flex flex-col items-start px-6 pt-6">
                    <div className="flex items-center gap-2">
                        <Radio size={20} className="text-emerald-400" />
                        <h2 className="text-xl font-bold bg-gradient-to-r from-emerald-400 to-teal-500 bg-clip-text text-transparent">
                            Flux UDP Entrant
                        </h2>
                    </div>
                    <p className="text-sm text-zinc-400">Monitorez les paquets reçus sur le port 5005</p>
                </CardHeader>
                <Divider className="my-2 bg-zinc-800" />
                <CardBody className="p-0">
                    <ScrollShadow className="h-full max-h-[300px] p-6">
                        {messages.length === 0 ? (
                            <div className="text-zinc-600 italic">En attente de paquets...</div>
                        ) : (
                            <div className="flex flex-col gap-3">
                                {[...messages].reverse().map((msg, i) => (
                                    <div key={i} className="p-3 rounded-lg bg-zinc-800/40 border border-zinc-700/30 text-xs">
                                        <div className="flex items-center justify-between mb-2">
                                            <Chip size="sm" variant="dot" color="success" className="border-none text-[10px]">
                                                {msg.address}
                                            </Chip>
                                            <span className="text-zinc-500 text-[10px]">
                                                {new Date(msg.timestamp).toLocaleTimeString()}
                                            </span>
                                        </div>
                                        <pre className="text-emerald-500 font-mono overflow-x-auto">
                                            {JSON.stringify(msg, null, 2)}
                                        </pre>
                                    </div>
                                ))}
                            </div>
                        )}
                    </ScrollShadow>
                </CardBody>
            </Card>
        </div>
    );
}
