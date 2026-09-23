import { int16ToFloat32 } from "@/lib/audio/pcm";

export interface AudioSink {
  resume(): Promise<void>;
  enqueue(pcm16: ArrayBuffer): void;
  stop(): void;
  onDrained(cb: () => void): () => void;
}

/** Schedules received PCM16 chunks back-to-back (voice-and-pronunciation.md §1). */
export class PcmPlayer implements AudioSink {
  private readonly audioContext: AudioContext;
  private readonly listeners = new Set<() => void>();
  private sources: AudioBufferSourceNode[] = [];
  private nextStartTime = 0;

  constructor(sampleRate = 24000) {
    this.audioContext = new AudioContext({ sampleRate });
  }

  async resume(): Promise<void> {
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }
  }

  enqueue(pcm16: ArrayBuffer): void {
    const float32 = int16ToFloat32(new Int16Array(pcm16));
    const buffer = this.audioContext.createBuffer(1, float32.length, this.audioContext.sampleRate);
    buffer.copyToChannel(float32, 0);

    const source = this.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(this.audioContext.destination);

    const startTime = Math.max(this.nextStartTime, this.audioContext.currentTime);
    source.start(startTime);
    this.nextStartTime = startTime + buffer.duration;

    this.sources.push(source);
    source.onended = () => {
      this.sources = this.sources.filter((s) => s !== source);
      if (this.sources.length === 0) {
        for (const cb of this.listeners) cb();
      }
    };
  }

  stop(): void {
    for (const source of this.sources) {
      try {
        source.stop();
      } catch {
        // already stopped/ended — nothing to do
      }
    }
    this.sources = [];
    this.nextStartTime = 0;
  }

  onDrained(cb: () => void): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }
}
