import { spawn, ChildProcess } from "child_process";
import path from "path";

interface ScriptInstance {
    process: ChildProcess;
    name: string;
    logs: string[];
    status: "running" | "stopped" | "error";
}

class ScriptManager {
    private static instance: ScriptManager;
    private instances: Map<string, ScriptInstance> = new Map();

    private constructor() { }

    public static getInstance(): ScriptManager {
        if (!ScriptManager.instance) {
            ScriptManager.instance = new ScriptManager();
        }
        return ScriptManager.instance;
    }

    public startScript(scriptName: string, scriptPath: string) {
        if (this.instances.has(scriptName)) {
            const instance = this.instances.get(scriptName);
            if (instance?.status === "running") {
                console.log(`Script ${scriptName} is already running.`);
                return;
            }
        }

        const fullPath = path.resolve(process.cwd(), "rplidar_control", scriptPath);
        console.log(`Starting script: python3 ${fullPath}`);

        const child = spawn("python3", [fullPath]);

        const instance: ScriptInstance = {
            process: child,
            name: scriptName,
            logs: [],
            status: "running",
        };

        child.stdout.on("data", (data) => {
            const log = data.toString();
            instance.logs.push(log);
            if (instance.logs.length > 1000) instance.logs.shift();
            console.log(`[${scriptName}] STDOUT: ${log}`);
            // In a real app, broadcast via socket.io here
        });

        child.stderr.on("data", (data) => {
            const log = data.toString();
            instance.logs.push(log);
            console.error(`[${scriptName}] STDERR: ${log}`);
        });

        child.on("close", (code) => {
            console.log(`Script ${scriptName} exited with code ${code}`);
            instance.status = code === 0 ? "stopped" : "error";
        });

        this.instances.set(scriptName, instance);
    }

    public stopScript(scriptName: string) {
        const instance = this.instances.get(scriptName);
        if (instance && instance.status === "running") {
            instance.process.kill();
            instance.status = "stopped";
        }
    }

    public getStatus(scriptName: string) {
        const instance = this.instances.get(scriptName);
        return instance ? { status: instance.status, logs: instance.logs } : null;
    }

    public getAllStatuses() {
        const statuses: Record<string, any> = {};
        this.instances.forEach((instance, name) => {
            statuses[name] = { status: instance.status, logs: instance.logs.slice(-50) };
        });
        return statuses;
    }
}

export const scriptManager = ScriptManager.getInstance();
