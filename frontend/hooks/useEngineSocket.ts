'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { ConnectionState, EngineMessage, WorldState } from '@/types/engine';

interface UseEngineSocketReturn {
  state: WorldState | null;
  connectionState: ConnectionState;
  lastHeartbeat: number | null;
  error: string | null;
  reconnect: () => void;
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/api/v1/hass/ws';
const MAX_RECONNECT_DELAY = 16000; // 16 seconds
const INITIAL_RECONNECT_DELAY = 1000; // 1 second

export function useEngineSocket(): UseEngineSocketReturn {
  const [state, setState] = useState<WorldState | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>(ConnectionState.DISCONNECTED);
  const [lastHeartbeat, setLastHeartbeat] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectDelayRef = useRef<number>(INITIAL_RECONNECT_DELAY);
  const shouldReconnectRef = useRef<boolean>(true);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    setConnectionState(ConnectionState.CONNECTING);
    setError(null);

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionState(ConnectionState.CONNECTED);
        reconnectDelayRef.current = INITIAL_RECONNECT_DELAY; // Reset delay on successful connection
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const message: EngineMessage = JSON.parse(event.data);

          if (message.type === 'heartbeat') {
            setLastHeartbeat(Date.now());
          } else if (message.type === 'state') {
            setState(message.data);
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (event) => {
        console.error('WebSocket error:', event);
        setConnectionState(ConnectionState.ERROR);
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        setConnectionState(ConnectionState.DISCONNECTED);
        wsRef.current = null;

        // Attempt reconnection with exponential backoff
        if (shouldReconnectRef.current) {
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, MAX_RECONNECT_DELAY);
            connect();
          }, reconnectDelayRef.current);
        }
      };
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setConnectionState(ConnectionState.ERROR);
      setError('Failed to create WebSocket connection');
    }
  }, []);

  const reconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    reconnectDelayRef.current = INITIAL_RECONNECT_DELAY;
    connect();
  }, [connect]);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();

    return () => {
      shouldReconnectRef.current = false;

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return {
    state,
    connectionState,
    lastHeartbeat,
    error,
    reconnect,
  };
}
