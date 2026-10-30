export class RingQueue {
  private readonly buf: Int32Array;
  private readonly head: Int32Array;
  private readonly tail: Int32Array;
  private readonly capacity: number;

  constructor(capacity: number) {
    if (!Number.isInteger(capacity) || capacity <= 0) {
      throw new Error("capacity must be a positive integer");
    }
    const sab = new SharedArrayBuffer((capacity + 2) * 4);
    this.buf = new Int32Array(sab);
    this.head = new Int32Array(sab, 0, 1);
    this.tail = new Int32Array(sab, 1, 1);
    this.capacity = capacity;
  }

  get sharedBuffer(): SharedArrayBuffer {
    return this.buf.buffer as SharedArrayBuffer;
  }

  tryPush(index: number): boolean {
    const h = Atomics.load(this.head, 0);
    const t = Atomics.load(this.tail, 0);
    const next = (t + 1) % this.capacity;
    if (next === h) return false;
    Atomics.store(this.buf, t, index);
    Atomics.store(this.tail, 0, next);
    Atomics.notify(this.tail, 1);
    return true;
  }

  tryPop(): number | null {
    const h = Atomics.load(this.head, 0);
    const t = Atomics.load(this.tail, 0);
    if (h === t) return null;
    const val = Atomics.load(this.buf, h);
    Atomics.store(this.head, 0, (h + 1) % this.capacity);
    Atomics.notify(this.head, 1);
    return val;
  }

  async push(index: number): Promise<void> {
    while (!this.tryPush(index)) {
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    }
  }

  async pop(): Promise<number> {
    while (true) {
      const v = this.tryPop();
      if (v !== null) return v;
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    }
  }

  size(): number {
    const h = Atomics.load(this.head, 0);
    const t = Atomics.load(this.tail, 0);
    return (t - h + this.capacity) % this.capacity;
  }

  isFull(): boolean {
    return this.size() === this.capacity;
  }

  isEmpty(): boolean {
    return this.size() === 0;
  }
}
