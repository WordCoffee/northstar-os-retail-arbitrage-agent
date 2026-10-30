export interface Job {
  id: string;
  payload: unknown;
}

export interface JobResult {
  id: string;
  ok: boolean;
  value?: unknown;
  error?: string;
}

export interface QueueOptions {
  capacity: number;
}

export interface BackoffOptions {
  baseMs: number;
  maxMs: number;
  maxAttempts: number;
}

export interface BreakerOptions {
  failureThreshold: number;
  cooldownMs: number;
}

export interface TelemetryEvent {
  name: string;
  timestamp: number;
  data?: Record<string, unknown>;
}
