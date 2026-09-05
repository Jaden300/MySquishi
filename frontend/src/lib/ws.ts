/**
 * The live session socket.
 *
 * The client sends only start, stop and pause. Everything else in the app is
 * REST: the socket carries frames, not queries. See docs/ARCHITECTURE.md.
 */

import { useLiveStore } from "../store/live";
import type { LiveMessage } from "../types/api";

export interface LiveOptions {
  source?: string;
  patientId?: string;
  /** Signal quality dial, so a demo can show the SQI badge reacting. */
  junkiness?: number;
}

export class LiveConnection {
  private socket: WebSocket | null = null;

  connect(options: LiveOptions = {}): void {
    const {
      source = "simulated",
      patientId = "demo",
      junkiness = 0,
    } = options;

    const store = useLiveStore.getState();
    store.reset();
    store.setStatus("connecting");

    // Same origin, so the Vite proxy forwards the upgrade in development and
    // there is nothing to configure in production.
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url =
      `${protocol}//${window.location.host}/api/signal/live` +
      `?source=${encodeURIComponent(source)}` +
      `&patient_id=${encodeURIComponent(patientId)}` +
      `&junkiness=${junkiness}`;

    const socket = new WebSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      useLiveStore.getState().setStatus("running");
      socket.send(JSON.stringify({ type: "start" }));
    };

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as LiveMessage;
      const state = useLiveStore.getState();

      if (message.type === "frame") {
        state.applyFrame(message);
      } else if (message.type === "summary") {
        state.applySummary(message);
      } else if (message.type === "error") {
        state.setError(message.message);
      }
    };

    socket.onerror = () => {
      useLiveStore
        .getState()
        .setError("Lost contact with the signal source.");
    };

    socket.onclose = () => {
      const { status, setStatus } = useLiveStore.getState();
      // An ended session closed on purpose. Anything else stopped early.
      if (status === "running" || status === "paused") setStatus("idle");
      this.socket = null;
    };
  }

  private send(type: "start" | "stop" | "pause"): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type }));
    }
  }

  start(): void {
    this.send("start");
    useLiveStore.getState().setStatus("running");
  }

  pause(): void {
    this.send("pause");
    useLiveStore.getState().setStatus("paused");
  }

  /** Asks the server to persist and send its summary frame. */
  stop(): void {
    this.send("stop");
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = null;
  }
}

export const liveConnection = new LiveConnection();
