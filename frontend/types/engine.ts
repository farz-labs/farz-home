export enum ConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  ERROR = 'error',
}

export interface HeartbeatMessage {
  type: 'heartbeat';
  tick: number;
  timestamp: number;
}

export interface StateMessage {
  type: 'state';
  data: WorldState;
  tick: number;
}

export type EngineMessage = HeartbeatMessage | StateMessage;

export interface WorldState {
  entities: Record<string, Entity>;
  global_attributes: Record<string, any>;
  timestamp?: number;
}

export interface Entity {
  id: string;
  name: string;
  tags: string[];
  attributes: Record<string, any>;
}
