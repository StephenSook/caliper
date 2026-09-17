/**
 * Microphone capture for the practice call.
 *
 * AudioWorklet rather than ScriptProcessorNode. ScriptProcessorNode is
 * deprecated and handles its events on the main thread, so it drops frames the
 * moment React renders anything, which on stage looks like the model ignoring
 * you.
 *
 * The AudioContext sample rate is whatever the hardware gives us, usually 44100
 * or 48000, and it cannot be changed reliably (asking for 16000 in the
 * constructor is ignored or breaks on iOS). Nova 2 Sonic requires 16000, so the
 * downsample happens here, on the audio thread, before anything crosses to the
 * main thread.
 */

const TARGET_RATE = 16000;
const FRAME_SAMPLES = 512; // 32 ms at 16 kHz

class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    // sampleRate is a global inside an AudioWorkletGlobalScope.
    this.ratio = sampleRate / TARGET_RATE;
    this.buffer = new Float32Array(FRAME_SAMPLES);
    this.filled = 0;
    this.position = 0;
    this.muted = false;
    this.port.onmessage = (e) => {
      if (e.data && typeof e.data.muted === "boolean") this.muted = e.data.muted;
    };
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true;

    // Linear interpolation resample. Cheap, and speech at 16 kHz does not
    // reward anything more expensive.
    while (this.position < channel.length) {
      const index = Math.floor(this.position);
      const frac = this.position - index;
      const a = channel[index] ?? 0;
      const b = channel[index + 1] ?? a;
      this.buffer[this.filled++] = this.muted ? 0 : a + (b - a) * frac;

      if (this.filled === FRAME_SAMPLES) {
        // Float32 in [-1, 1] to signed sixteen bit little endian.
        const pcm = new Int16Array(FRAME_SAMPLES);
        for (let i = 0; i < FRAME_SAMPLES; i++) {
          const s = Math.max(-1, Math.min(1, this.buffer[i]));
          pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        this.port.postMessage(pcm.buffer, [pcm.buffer]);
        this.filled = 0;
      }
      this.position += this.ratio;
    }
    this.position -= channel.length;
    return true;
  }
}

registerProcessor("mic-processor", MicProcessor);
