/**
 * DartWebSocket: WebSocket client with auto-reconnect.
 */
class DartWebSocket {
    constructor() {
        this.ws = null;
        this.handlers = {};
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.currentDelay = this.reconnectDelay;
        this.intentionalClose = false;
    }

    connect() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${protocol}//${window.location.host}/ws`;

        try {
            this.ws = new WebSocket(url);
        } catch (e) {
            console.error("WebSocket creation failed:", e);
            this._scheduleReconnect();
            return;
        }

        this.ws.onopen = () => {
            console.log("WebSocket connected");
            this.currentDelay = this.reconnectDelay;
            this._emit("connected", {});
        };

        this.ws.onclose = (event) => {
            console.log("WebSocket closed:", event.code, event.reason);
            this._emit("disconnected", {});
            if (!this.intentionalClose) {
                this._scheduleReconnect();
            }
        };

        this.ws.onerror = (error) => {
            const errorType = error?.type || "unbekannt";
            console.error(`WebSocket Fehler (Typ: ${errorType}):`, error);
        };

        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                const type = message.type;
                const data = message.data;
                this._emit(type, data);
            } catch (e) {
                console.error("WebSocket message parse error:", e);
            }
        };
    }

    _scheduleReconnect() {
        console.log(`Reconnecting in ${this.currentDelay}ms...`);
        setTimeout(() => {
            this.connect();
        }, this.currentDelay);
        this.currentDelay = Math.min(this.currentDelay * 2, this.maxReconnectDelay);
    }

    send(command, data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ command, ...data }));
        }
    }

    on(eventType, handler) {
        if (!this.handlers[eventType]) {
            this.handlers[eventType] = [];
        }
        this.handlers[eventType].push(handler);
    }

    off(eventType, handler) {
        if (this.handlers[eventType]) {
            this.handlers[eventType] = this.handlers[eventType].filter(h => h !== handler);
        }
    }

    _emit(eventType, data) {
        const handlers = this.handlers[eventType];
        if (handlers) {
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (e) {
                    console.error(`Handler error for ${eventType}:`, e);
                }
            });
        }
    }

    disconnect() {
        this.intentionalClose = true;
        if (this.ws) {
            this.ws.close();
        }
    }
}
