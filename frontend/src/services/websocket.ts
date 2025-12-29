type MessageHandler = (data: unknown) => void;

interface WebSocketMessage {
  type: string;
  data?: unknown;
}

class WebSocketService {
  private ws: WebSocket | null = null;
  private handlers: Map<string, MessageHandler[]> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private pingInterval: number | null = null;

  connect(): void {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.emit('connection', { status: 'connected' });
        this.startPing();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.emit(message.type, message.data);
        } catch (e) {
          console.error('Failed to parse WebSocket message', e);
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.emit('connection', { status: 'disconnected' });
        this.stopPing();
        this.attemptReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error', error);
        this.emit('connection', { status: 'error' });
      };
    } catch (error) {
      console.error('Failed to create WebSocket', error);
      this.attemptReconnect();
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
      setTimeout(() => this.connect(), delay);
    } else {
      console.error('Max reconnection attempts reached');
      this.emit('connection', { status: 'failed' });
    }
  }

  private startPing(): void {
    this.pingInterval = window.setInterval(() => {
      this.send({ type: 'ping' });
    }, 30000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  subscribe(type: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, []);
    }
    this.handlers.get(type)!.push(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.handlers.get(type);
      if (handlers) {
        const index = handlers.indexOf(handler);
        if (index > -1) {
          handlers.splice(index, 1);
        }
      }
    };
  }

  private emit(type: string, data: unknown): void {
    const handlers = this.handlers.get(type);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(data);
        } catch (e) {
          console.error('Error in WebSocket handler', e);
        }
      });
    }
  }

  send(message: WebSocketMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  disconnect(): void {
    this.stopPing();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const wsService = new WebSocketService();
