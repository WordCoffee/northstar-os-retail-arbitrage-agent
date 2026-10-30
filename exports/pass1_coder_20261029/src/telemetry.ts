import { TelemetryEvent } from './types';

export class Telemetry {
  private events: TelemetryEvent[] = [];

  record(event: TelemetryEvent): void {
    this.events.push(event);
  }

  snapshot(): Record<string, number> {
    const counts: Record<string, number> = {};
    for (const e of this.events) {
      counts[e.name] = (counts[e.name] ?? 0) + 1;
    }
    return counts;
  }

  clear(): void {
    this.events = [];
  }
}
