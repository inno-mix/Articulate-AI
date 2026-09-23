import { PcmChunker, rms } from "@/lib/audio/pcm";

const WORKLET_URL = "/worklets/pcm-capture-processor.js";
const WORKLET_NAME = "pcm-capture-processor";

export class MicPermissionError extends Error {
  constructor(message = "Microphone permission was denied.") {
    super(message);
    this.name = "MicPermissionError";
  }
}

export interface AudioSource {
  start(onChunk: (chunk: Int16Array) => void): Promise<void>;
  stop(): void;
  readonly level: number;
}

/** Captures the mic via an AudioWorklet, downsamples to 16 kHz PCM16 (voice-and-pronunciation.md §1). */
export class MicCapture implements AudioSource {
  private stream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private chunker: PcmChunker | null = null;
  level = 0;

  async start(onChunk: (chunk: Int16Array) => void): Promise<void> {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });
    } catch {
      throw new MicPermissionError();
    }
    this.stream = stream;

    const audioContext = new AudioContext();
    this.audioContext = audioContext;
    await audioContext.audioWorklet.addModule(WORKLET_URL);

    const sourceNode = audioContext.createMediaStreamSource(stream);
    this.sourceNode = sourceNode;
    const workletNode = new AudioWorkletNode(audioContext, WORKLET_NAME);
    this.workletNode = workletNode;

    this.chunker = new PcmChunker({ inRate: audioContext.sampleRate, onChunk });
    workletNode.port.onmessage = (event: MessageEvent<Float32Array>) => {
      this.chunker?.push(event.data);
      this.level = rms(event.data);
    };

    // Worklet writes no output samples (silence), so connecting to destination is safe — it just
    // keeps this node in the active render graph so process() keeps running.
    sourceNode.connect(workletNode);
    workletNode.connect(audioContext.destination);
  }

  stop(): void {
    this.chunker?.flush();
    this.workletNode?.disconnect();
    this.sourceNode?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    void this.audioContext?.close();

    this.chunker = null;
    this.workletNode = null;
    this.sourceNode = null;
    this.stream = null;
    this.audioContext = null;
    this.level = 0;
  }
}
