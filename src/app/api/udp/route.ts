import { NextRequest, NextResponse } from "next/server";
import { udpServer } from "@/lib/udp-server";

export async function GET() {
    const messages = udpServer.getMessages();
    return NextResponse.json(messages);
}

export async function POST(req: NextRequest) {
    const { message, targetIP, targetPort } = await req.json();

    if (!message || !targetIP || !targetPort) {
        return NextResponse.json({ error: "Missing parameters" }, { status: 400 });
    }

    udpServer.sendMessage(message, targetIP, targetPort);
    return NextResponse.json({ message: "Sent UDP packet" });
}
