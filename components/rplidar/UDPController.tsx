"use client";

import { useState, useEffect } from "react";
import { Card, CardHeader, CardBody, Input, Button, Divider, ScrollShadow, Chip } from "@heroui/react";
import { Send, Terminal } from "lucide-react";

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
            <Card className="bg-white border-zinc-200 shadow-sm">
                <CardHeader className="flex flex-col items-start px-6 pt-5">
                    <h2 className="text-base font-bold text-zinc-800">
                        Envoi UDP
                    </h2>
                    <p className="text-xs text-zinc-500">Commandes vers le réseau</p>
                </CardHeader>
                <Divider className="my-2 bg-zinc-100" />
                <CardBody className="gap-4 px-6 pb-6">
                    <div className="grid grid-cols-2 gap-3">
                        <Input
                            label="IP"
                            size="sm"
                            value={targetIP}
                            onValueChange={setTargetIP}
                            variant="flat"
                            classNames={{ inputWrapper: "bg-zinc-50 border-zinc-100" }}
                        />
                        <Input
                            label="Port"
                            size="sm"
                            value={targetPort}
                            onValueChange={setTargetPort}
                            variant="flat"
                            classNames={{ inputWrapper: "bg-zinc-50 border-zinc-100" }}
                        />
                    </div>
                    <Input
                        label="Message"
                        placeholder='Envoyer JSON/Texte'
                        value={message}
                        onValueChange={setMessage}
                        variant="flat"
                        size="sm"
                        classNames={{ inputWrapper: "bg-zinc-50 border-zinc-100" }}
                    />
                    <Button
                        color="primary"
                        variant="solid"
                        size="sm"
                        className="w-full font-bold"
                        onPress={handleSend}
                        isLoading={loading}
                        startContent={!loading && <Send size={14} />}
                    >
                        ENVOYER
                    </Button>
                </CardBody>
            </Card>

            <Card className="bg-white border-zinc-200 shadow-sm">
                <CardHeader className="flex flex-col items-start px-6 pt-5">
                    <h2 className="text-base font-bold text-zinc-800">
                        Flux Entrant
                    </h2>
                    <p className="text-xs text-zinc-500">Monitor port 5005</p>
                </CardHeader>
                <Divider className="my-2 bg-zinc-100" />
                <CardBody className="p-0">
                    <ScrollShadow className="h-[220px] p-4 bg-zinc-50/50">
                        {messages.length === 0 ? (
                            <div className="text-zinc-400 text-xs italic">Aucun paquet reçu...</div>
                        ) : (
                            <div className="flex flex-col gap-2">
                                {[...messages].reverse().map((msg, i) => (
                                    <div key={i} className="p-2.5 rounded border border-zinc-100 bg-white text-[11px] font-mono">
                                        <div className="flex items-center justify-between mb-1 opacity-60">
                                            <span className="font-bold">{msg.address}</span>
                                            <span>{new Date(msg.timestamp).toLocaleTimeString()}</span>
                                        </div>
                                        <div className="text-zinc-600">
                                            {JSON.stringify(msg, null, 1)}
                                        </div>
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
