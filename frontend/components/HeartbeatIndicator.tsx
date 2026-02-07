'use client';

import { useEffect, useState } from 'react';
import { ConnectionState } from '@/types/engine';
import { useEngineSocket } from '@/hooks/useEngineSocket';

export function HeartbeatIndicator() {
  const { connectionState, lastHeartbeat, error, reconnect } = useEngineSocket();
  const [isPulsing, setIsPulsing] = useState(false);

  useEffect(() => {
    if (lastHeartbeat) {
      setIsPulsing(true);
      const timeout = setTimeout(() => setIsPulsing(false), 1000);
      return () => clearTimeout(timeout);
    }
  }, [lastHeartbeat]);

  const getStatusColor = () => {
    switch (connectionState) {
      case ConnectionState.CONNECTED:
        return isPulsing ? 'bg-green-500' : 'bg-green-400';
      case ConnectionState.CONNECTING:
        return 'bg-yellow-400';
      case ConnectionState.ERROR:
        return 'bg-red-500';
      case ConnectionState.DISCONNECTED:
        return 'bg-gray-400';
      default:
        return 'bg-gray-400';
    }
  };

  const getStatusText = () => {
    switch (connectionState) {
      case ConnectionState.CONNECTED:
        return 'Connected';
      case ConnectionState.CONNECTING:
        return 'Connecting...';
      case ConnectionState.ERROR:
        return error || 'Error';
      case ConnectionState.DISCONNECTED:
        return 'Disconnected';
      default:
        return 'Unknown';
    }
  };

  return (
    <div className="fixed top-4 right-4 z-50 flex items-center gap-2 bg-white/90 backdrop-blur-sm border border-gray-200 rounded-lg px-3 py-2 shadow-lg">
      <div className="relative">
        {/* Pulsing glow effect */}
        {isPulsing && connectionState === ConnectionState.CONNECTED && (
          <div className="absolute inset-0 animate-ping">
            <div className={`w-3 h-3 rounded-full ${getStatusColor()} opacity-75`}></div>
          </div>
        )}
        {/* Main indicator */}
        <div
          className={`w-3 h-3 rounded-full ${getStatusColor()} transition-all duration-300 ${
            isPulsing ? 'scale-110' : 'scale-100'
          }`}
        ></div>
      </div>

      <div className="flex flex-col">
        <span className="text-xs font-medium text-gray-700">{getStatusText()}</span>
        {lastHeartbeat && connectionState === ConnectionState.CONNECTED && (
          <span className="text-[10px] text-gray-500">
            {new Date(lastHeartbeat).toLocaleTimeString()}
          </span>
        )}
      </div>

      {(connectionState === ConnectionState.ERROR || connectionState === ConnectionState.DISCONNECTED) && (
        <button
          onClick={reconnect}
          className="ml-2 text-xs text-blue-600 hover:text-blue-800 font-medium"
        >
          Retry
        </button>
      )}
    </div>
  );
}
