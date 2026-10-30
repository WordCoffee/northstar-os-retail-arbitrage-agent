import { Task } from './types';

export class Queue {
  private view: Task[];

  constructor(initial: Task[] = []) {
    this.view = [...initial];
  }

  push(task: Task): void {
    this.view.push(task);
  }

  pop(): Task | undefined {
    return this.view.shift();
  }

  size(): number {
    return this.view.length;
  }
}
