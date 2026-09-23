import { describe, expect, it } from "vitest";

import { PcmChunker, downsample, floatToInt16, int16ToFloat32, rms } from "@/lib/audio/pcm";

describe("downsample", () => {
  it("averages groups of samples when going from 48k to 16k", () => {
    const input = new Float32Array([0, 0, 0, 1, 1, 1, 2, 2, 2]);

    const output = downsample(input, 48000, 16000);

    expect(output).toEqual(new Float32Array([0, 1, 2]));
  });

  it("returns the input unchanged when rates are equal", () => {
    const input = new Float32Array([0.1, -0.2, 0.3]);

    expect(downsample(input, 16000, 16000)).toEqual(input);
  });
});

describe("floatToInt16", () => {
  it("scales 1.0 to 32767 and -1.0 to -32768", () => {
    const output = floatToInt16(new Float32Array([1, -1]));

    expect(output).toEqual(new Int16Array([32767, -32768]));
  });

  it("clamps values outside [-1, 1]", () => {
    const output = floatToInt16(new Float32Array([1.5, -1.5]));

    expect(output).toEqual(new Int16Array([32767, -32768]));
  });
});

describe("int16ToFloat32", () => {
  it("scales back to the [-1, 1] range", () => {
    const output = int16ToFloat32(new Int16Array([32767, -32768, 0]));

    expect(output).toEqual(new Float32Array([1, -1, 0]));
  });
});

describe("rms", () => {
  it("computes the root-mean-square of the samples", () => {
    expect(rms(new Float32Array([1, -1, 1, -1]))).toBe(1);
  });

  it("returns 0 for silence", () => {
    expect(rms(new Float32Array([0, 0, 0]))).toBe(0);
  });
});

describe("PcmChunker", () => {
  it("emits exact 1600-sample chunks across uneven pushes, then flushes the remainder", () => {
    const chunks: Int16Array[] = [];
    const chunker = new PcmChunker({ inRate: 16000, onChunk: (c) => chunks.push(c) });

    chunker.push(new Float32Array(500));
    chunker.push(new Float32Array(1300)); // buffer 1800 -> one 1600 chunk, 200 left
    chunker.push(new Float32Array(2000)); // buffer 2200 -> one 1600 chunk, 600 left

    expect(chunks).toHaveLength(2);
    expect(chunks[0]).toHaveLength(1600);
    expect(chunks[1]).toHaveLength(1600);

    chunker.flush();

    expect(chunks).toHaveLength(3);
    expect(chunks[2]).toHaveLength(600);
  });

  it("does not emit an empty chunk when flushed with nothing buffered", () => {
    const chunks: Int16Array[] = [];
    const chunker = new PcmChunker({ inRate: 16000, onChunk: (c) => chunks.push(c) });

    chunker.push(new Float32Array(1600));
    expect(chunks).toHaveLength(1);

    chunker.flush();

    expect(chunks).toHaveLength(1);
  });
});
