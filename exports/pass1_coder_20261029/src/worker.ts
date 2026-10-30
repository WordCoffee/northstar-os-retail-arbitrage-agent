import { parentPort } from 'node:worker_threads';
import { Task } from './types';

function main(): void {
  const port = parentPort;
  if (port === null) {
    throw new Error('parentPort is null; worker must run inside a Worker thread');
  }

  port.on('message', (msg: { task: Task }) => {
    const { task } = msg;
    port.postMessage({ result: task.id * 2 });
  });
}

main();
