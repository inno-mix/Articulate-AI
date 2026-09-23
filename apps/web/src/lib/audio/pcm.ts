/**
 * Pure PCM helpers (voice-and-pronunciation.md §1). No DOM APIs — safe to unit test directly.
 */

export function downsample(input: Float32Array, inRate: number, outRate: number): Float32Array {
  if (inRate === outRate) return input.slice();

  const ratio = inRate / outRate;
  const outLength = Math.floor(input.length / ratio);
  const output = new Float32Array(outLength);

  for (let i = 0; i < outLength; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.floor((i + 1) * ratio);
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    output[i] = sum / (end - start);
  }

  return output;
}

export function floatToInt16(input: Float32Array): Int16Array {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const clamped = Math.max(-1, Math.min(1, input[i]));
    output[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
  }
  return output;
}

export function int16ToFloat32(input: Int16Array): Float32Array<ArrayBuffer> {
  const output = new Float32Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const value = input[i];
    output[i] = value < 0 ? value / 32768 : value / 32767;
  }
  return output;
}

export function rms(input: Float32Array): number {
  if (input.length === 0) return 0;
  let sumOfSquares = 0;
  for (let i = 0; i < input.length; i++) sumOfSquares += input[i] * input[i];
  return Math.sqrt(sumOfSquares / input.length);
}

/** Downsamples pushed frames and emits fixed-size `chunkSamples` Int16 chunks. */
export class PcmChunker {
  private readonly inRate: number;
  private readonly outRate: number;
  private readonly chunkSamples: number;
  private readonly onChunk: (chunk: Int16Array) => void;
  private buffer: number[] = [];

  constructor(opts: {
    inRate: number;
    outRate?: number;
    chunkSamples?: number;
    onChunk: (chunk: Int16Array) => void;
  }) {
    this.inRate = opts.inRate;
    this.outRate = opts.outRate ?? 16000;
    this.chunkSamples = opts.chunkSamples ?? 1600;
    this.onChunk = opts.onChunk;
  }

  push(frame: Float32Array): void {
    const downsampled = downsample(frame, this.inRate, this.outRate);
    for (let i = 0; i < downsampled.length; i++) this.buffer.push(downsampled[i]);

    while (this.buffer.length >= this.chunkSamples) {
      const chunk = this.buffer.splice(0, this.chunkSamples);
      this.onChunk(floatToInt16(Float32Array.from(chunk)));
    }
  }

  flush(): void {
    if (this.buffer.length === 0) return;
    const remainder = Float32Array.from(this.buffer);
    this.buffer = [];
    this.onChunk(floatToInt16(remainder));
  }
}
