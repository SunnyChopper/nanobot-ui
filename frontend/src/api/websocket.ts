/**
 * WebSocket connection manager for the nanobot server.
 *
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Typed JSON frame parsing
 * - Event-based API with typed callbacks
 * - Keepalive ping every 30 s
 */

import type { WsClientFrame, WsConnectionStatus, WsServerFrame } from './types'

export type WsEventHandler = (frame: WsServerFrame) => void
export type WsStatusHandler = (status: WsConnectionStatus) => void

const WS_URL =
  window.location.protocol === 'https:'
    ? `wss://${window.location.host}/ws/chat`
    : `ws://${window.location.host}/ws/chat`

const PING_INTERVAL_MS = 30_000
const BASE_RECONNECT_MS = 1_000
const MAX_RECONNECT_MS = 30_000

export class NanobotWebSocket {
  private ws: WebSocket | null = null
  private sessionId: string
  private onFrame: WsEventHandler
  private onStatus: WsStatusHandler
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private reconnectDelay = BASE_RECONNECT_MS
  private closed = false

  constructor(opts: {
    sessionId: string
    onFrame: WsEventHandler
    onStatus: WsStatusHandler
  }) {
    this.sessionId = opts.sessionId
    this.onFrame = opts.onFrame
    this.onStatus = opts.onStatus
  }

  connect(): void {
    if (this.closed) return
    this.onStatus('connecting')

    const ws = new WebSocket(WS_URL)
    this.ws = ws

    ws.onopen = () => {
      this.reconnectDelay = BASE_RECONNECT_MS
      this.onStatus('connected')
      this._startPing()
      // Send session identifier so the server can route messages correctly
      this._send({ type: 'session_init', session_id: this.sessionId })
    }

    ws.onmessage = (event: MessageEvent<string>) => {
      try {
        const frame = JSON.parse(event.data) as WsServerFrame
        this.onFrame(frame)
      } catch {
        // Ignore malformed frames
      }
    }

    ws.onclose = () => {
      this.ws = null
      this._stopPing()
      if (!this.closed) {
        this.onStatus('disconnected')
        this._scheduleReconnect()
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }

  send(frame: WsClientFrame): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(frame))
    }
  }

  close(): void {
    this.closed = true
    this._stopPing()
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.ws?.close()
    this.ws = null
  }

  private _send(frame: WsClientFrame): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(frame))
    }
  }

  private _startPing(): void {
    this._stopPing()
    this.pingTimer = setInterval(() => {
      this._send({ type: 'ping' })
    }, PING_INTERVAL_MS)
  }

  private _stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  private _scheduleReconnect(): void {
    if (this.closed) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, MAX_RECONNECT_MS)
      this.connect()
    }, this.reconnectDelay)
  }
}
