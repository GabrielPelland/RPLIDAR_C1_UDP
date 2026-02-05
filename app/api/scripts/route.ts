import { NextRequest, NextResponse } from "next/server";
import { scriptManager } from "@/lib/script-manager";

export async function GET() {
    const statuses = scriptManager.getAllStatuses();
    return NextResponse.json(statuses);
}

export async function POST(req: NextRequest) {
    const { action, scriptName, scriptPath } = await req.json();

    if (action === "start") {
        scriptManager.startScript(scriptName, scriptPath);
        return NextResponse.json({ message: `Started ${scriptName}` });
    } else if (action === "stop") {
        scriptManager.stopScript(scriptName);
        return NextResponse.json({ message: `Stopped ${scriptName}` });
    }

    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
}
