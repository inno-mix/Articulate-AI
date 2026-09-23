// Copies channel 0 of each render quantum to the main thread (voice-and-pronunciation.md §1).
// Downsampling and chunking happen on the main thread (src/lib/audio/pcm.ts) — this stays tiny
// so it never blocks the audio render thread.
class PcmCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel) {
      this.port.postMessage(channel.slice());
    }
    return true;
  }
}

registerProcessor("pcm-capture-processor", PcmCaptureProcessor);
