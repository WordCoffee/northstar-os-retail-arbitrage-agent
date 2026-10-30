import { QueueOptions } from './types';

const HEADER_SIZE = 8;

export class RingQueue {
  private readonly sab: SharedArrayBuffer;
  private readonly view: Int32Array;
  private readonly capacity: number;
  private readonly head: number;
  private readonly tail: number;
  private readonly count: number;

  constructor(options: QueueOptions) {
    const cap = Math.max(1, Math.floor(options.capacity));
    this.capacity = cap;
    this.sab = new SharedArrayBuffer(HEADER_SIZE + cap * 4);
    this.view = new Int32Array(this.sab);
    this.head = 0;
    this.tail = 1;
    this.count = 2;
  }

  get sharedBuffer(): SharedArrayBuffer {
    return this.sab;
  }

  static fromSharedBuffer(sab: SharedArrayBuffer, capacity: number): RingQueue {
    const q = new RingQueue({ capacity });
    q.view.set(new Int32Array(sab));
    q.head = q.view[0];
    q.tail = q.view[1];
    q.count = q.view[2];
    return q;
  }

  tryPush(item: number): boolean {
    const cap = this.capacity;
    const curCount = Atomics.load(this.view, this.count);
    if (curCount >= cap) {
      return false;
    }
    const curTail = Atomics.load(this.view, this.tail);
    const slot = curTail % cap;
    Atomics.store(this.view, slot, item);
    Atomics.store(this.view, this.tail, curTail + 1);
    Atomics.store(this.view, this.count, curCount + 1);
    return true;
  }

  tryPop(): number | null {
    const cap = this.capacity;
    const curCount = Atomics.load(this.view, this.count);
    if (curCount <= 0) {
      return null;
    }
    const curHead = Atomics.load(this.view, this.head);
    const slot = curHead % cap;
    const item = Atomics.load(this.view, slot);
    Atomics.store(this.view, this.head, curHead + 1);
    Atomics.store(this.view, this.count, curCount - 1);
    return item;
  }

  async push(item: number): Promise<void> {
    while (!this.tryPush(item)) {
      await new Promise<void>((resolve) => setTimeout(resolve, 1));
    }
  }

  async pop(): Promise<number> {
    while (true) {
      const item = this.tryPop();
      if (item !== null) {
        return item;
      }
      await new Promise<void>((resolve) => setTimeout(resolve, 1));
    }
  }

  size(): number {
    return Atomics.load(this.view, this.count);
  }

  isFull(): boolean {
    return Atomics.load(this.view, this.count) >= this.capacity;
  }

  isEmpty(): boolean {
    return Atomics.load(this.view, this.count) <= 0;
  }
}