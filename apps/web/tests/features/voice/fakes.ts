import { MicPermissionError } from "@/lib/audio/mic-capture";
import type { AudioSource } from "@/lib/audio/mic-capture";
import type { AudioSink } from "@/lib/audio/pcm-player";

export class FakeAudioSource implements AudioSource {
  level = 0;
  stopped = false;
  private onChunk: ((chunk: Int16Array) => void) | null = null;

  async start(onChunk: (chunk: Int16Array) => void): Promise<void> {
    this.onChunk = onChunk;
  }

  stop(): void {
    this.stopped = true;
  }

  emit(chunk: Int16Array): void {
    this.onChunk?.(chunk);
  }
}

export class DeniedAudioSource implements AudioSource {
  level = 0;
  async start(): Promise<void> {
    throw new MicPermissionError();
  }
  stop(): void {}
}

export class FakeAudioSink implements AudioSink {
  resumed = false;
  stopped = false;
  enqueued: ArrayBuffer[] = [];

  async resume(): Promise<void> {
    this.resumed = true;
  }

  enqueue(pcm16: ArrayBuffer): void {
    this.enqueued.push(pcm16);
  }

  stop(): void {
    this.stopped = true;
  }

  onDrained(): () => void {
    return () => {};
  }
}
