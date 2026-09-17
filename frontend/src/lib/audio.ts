/**
 * Microphone capture and low latency playback for the practice call.
 *
 * Three things here are the difference between a call that works in the room and
 * one that does not.
 *
 * SECURE CONTEXT. getUserMedia returns nothing outside a secure context, and
 * `localhost` counts while `192.168.1.x` does not. A QR code pointing a judge's
 * phone at a laptop's LAN IP over plain HTTP yields no microphone and no useful
 * error, which is the single most likely way this fails in front of people.
 *
 * USER GESTURE. An AudioContext starts suspended and only resumes inside a real
 * user gesture. On iOS it can also drop to "interrupted" when a call arrives, and
 * that state is resumable, so both are treated as recoverable rather than fatal.
 *
 * BARGE IN. Nova generates faster than real time, so audio already delivered but
 * not yet played has to be DISCARDED on an interruption rather than played out,
 * or the member keeps talking over the person who interrupted her.
 */

export const INPUT_RATE = 16000;
export const OUTPUT_RATE = 24000;

export function isSecureForMicrophone(): boolean {
  return window.isSecureContext;
}

export function microphoneBlockedReason(): string | null {
  if (!window.isSecureContext) {
    return (
      "This page is not a secure context, so the browser will not grant microphone " +
      "access. Open it over HTTPS, or on localhost. A LAN address over plain HTTP " +
      "silently yields no microphone."
    );
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    return "This browser does not expose getUserMedia.";
  }
  return null;
}

export class MicCapture {
  private ctx: AudioContext | null = null;
  private node: AudioWorkletNode | null = null;
  private stream: MediaStream | null = null;
  private source: MediaStreamAudioSourceNode | null = null;

  /** Must be called from inside a user gesture. */
  async start(onFrame: (pcm: ArrayBuffer) => void): Promise<void> {
    const blocked = microphoneBlockedReason();
    if (blocked) throw new Error(blocked);

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    this.ctx = new AudioContext();
    if (this.ctx.state !== "running") await this.ctx.resume();

    await this.ctx.audioWorklet.addModule("/mic-worklet.js");
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, "mic-processor");
    this.node.port.onmessage = (e) => onFrame(e.data as ArrayBuffer);
    this.source.connect(this.node);
    // Not connected to the destination on purpose. Routing the microphone to the
    // speakers is how a demo produces feedback howl in a room with a PA.
  }

  setMuted(muted: boolean): void {
    this.node?.port.postMessage({ muted });
  }

  get sampleRate(): number | null {
    return this.ctx?.sampleRate ?? null;
  }

  async stop(): Promise<void> {
    this.node?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    await this.ctx?.close();
    this.ctx = null;
    this.node = null;
    this.stream = null;
    this.source = null;
  }
}

export class AudioPlayer {
  private ctx: AudioContext | null = null;
  private playAt = 0;
  private sources = new Set<AudioBufferSourceNode>();

  async ensure(): Promise<void> {
    if (!this.ctx) this.ctx = new AudioContext();
    // "interrupted" is an iOS state and it is resumable. Treating it as fatal
    // means a phone call during the demo permanently kills the audio.
    if (this.ctx.state === "suspended" || (this.ctx.state as string) === "interrupted") {
      await this.ctx.resume();
    }
  }

  /** Queue one base64 chunk of 24 kHz sixteen bit mono PCM from the model. */
  async play(base64: string): Promise<void> {
    await this.ensure();
    if (!this.ctx) return;

    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const pcm = new Int16Array(bytes.buffer);

    const buffer = this.ctx.createBuffer(1, pcm.length, OUTPUT_RATE);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 0x8000;

    const node = this.ctx.createBufferSource();
    node.buffer = buffer;
    node.connect(this.ctx.destination);

    const now = this.ctx.currentTime;
    // A small lead keeps chunks butted together instead of clicking.
    this.playAt = Math.max(this.playAt, now + 0.04);
    node.start(this.playAt);
    this.playAt += buffer.duration;

    this.sources.add(node);
    node.onended = () => this.sources.delete(node);
  }

  /**
   * Barge in. Discard everything queued but not yet heard.
   *
   * Nova runs ahead of real time, so without this the member audibly keeps
   * talking for seconds after she was interrupted.
   */
  clear(): void {
    this.sources.forEach((s) => {
      try {
        s.stop();
      } catch {
        /* already finished */
      }
    });
    this.sources.clear();
    this.playAt = this.ctx?.currentTime ?? 0;
  }

  async stop(): Promise<void> {
    this.clear();
    await this.ctx?.close();
    this.ctx = null;
    this.playAt = 0;
  }
}
