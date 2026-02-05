import dgram from "dgram";

class UDPServer {
    private static instance: UDPServer;
    private socket: dgram.Socket;
    private latestMessages: any[] = [];
    private port: number = 5005;

    private constructor() {
        this.socket = dgram.createSocket("udp4");

        this.socket.on("error", (err) => {
            console.error(`UDP Server error:\n${err.stack}`);
            this.socket.close();
        });

        this.socket.on("message", (msg, rinfo) => {
            try {
                const data = JSON.parse(msg.toString());
                this.latestMessages.push({
                    timestamp: new Date().toISOString(),
                    address: rinfo.address,
                    ...data,
                });
                if (this.latestMessages.length > 100) this.latestMessages.shift();
            } catch (e) {
                console.log(`UDP Server received non-JSON message from ${rinfo.address}:${rinfo.port}`);
            }
        });

        this.socket.on("listening", () => {
            const address = this.socket.address();
            console.log(`UDP Server listening on ${address.address}:${address.port}`);
        });

        this.socket.bind(this.port);
    }

    public static getInstance(): UDPServer {
        if (!UDPServer.instance) {
            UDPServer.instance = new UDPServer();
        }
        return UDPServer.instance;
    }

    public getMessages() {
        return this.latestMessages;
    }

    public sendMessage(message: string, targetIP: string, targetPort: number) {
        const data = Buffer.from(message);
        this.socket.send(data, targetPort, targetIP, (err) => {
            if (err) console.error(`UDP Send error: ${err}`);
        });
    }
}

// Global variable to keep instance across HMR in dev
const globalWithUDP = global as typeof globalThis & {
    udpServer: UDPServer | undefined;
};

export const udpServer = globalWithUDP.udpServer || UDPServer.getInstance();

if (process.env.NODE_ENV !== "production") {
    globalWithUDP.udpServer = udpServer;
}
