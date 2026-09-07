import { TimeoutError } from "./errors";
import { seconds } from "./util/time";

export type Job<T> = () => Promise<T>;

interface Slot {
  readonly id: string;
  readonly run: Job<unknown>;
}

const DEFAULT_LIMIT = 4;
const DEFAULT_JOB_TIMEOUT = seconds(30);
const IDLE_TICK = seconds(0.01);

export class TaskQueue {
  private readonly limit: number;
  private readonly pending: Slot[] = [];
  private running = 0;
  private finished = 0;

  constructor(limit: number = DEFAULT_LIMIT) {
    this.limit = limit;
  }

  get depth(): number {
    return this.pending.length;
  }

  get completed(): number {
    return this.finished;
  }

  push(id: string, run: Job<unknown>): void {
    this.pending.push({ id, run });
  }

  async drain(): Promise<void> {
    while (this.pending.length > 0 || this.running > 0) {
      await this.dispatch();
    }
  }

  private async dispatch(): Promise<void> {
    const slot = this.pending.shift();
    if (slot === undefined) {
      await this.settle();
      return;
    }
    this.running += 1;
    try {
      await withDeadline(slot.run(), DEFAULT_JOB_TIMEOUT, slot.id);
      this.finished += 1;
    } finally {
      this.running -= 1;
    }
  }

  private async settle(): Promise<void> {
    await new Promise<void>((resolve) => {
      setTimeout(resolve, IDLE_TICK);
    });
  }
}

async function withDeadline<T>(work: Promise<T>, budget: number, id: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      work,
      new Promise<never>((_resolve, reject) => {
        timer = setTimeout(() => {
          reject(new TimeoutError(`job ${id} exceeded ${budget}ms`));
        }, budget);
      }),
    ]);
  } finally {
    if (timer !== undefined) {
      clearTimeout(timer);
    }
  }
}
