/**
 * The voice preference.
 *
 * Mirrors demo.test.ts, including the storage throws case: localStorage does
 * not merely return null in a private window, it raises, and a preference read
 * that throws would take the app down on load.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { useVoiceStore, VOICE_STORAGE_KEY, speechAvailable } from "./voice";

describe("the voice preference", () => {
  beforeEach(() => {
    localStorage.clear();
    useVoiceStore.setState({ voiceOn: false });
  });

  it("defaults to off", () => {
    expect(useVoiceStore.getState().voiceOn).toBe(false);
  });

  it("persists a change", () => {
    useVoiceStore.getState().setVoiceOn(true);

    expect(useVoiceStore.getState().voiceOn).toBe(true);
    expect(localStorage.getItem(VOICE_STORAGE_KEY)).toBe("true");
  });

  it("turns back off", () => {
    useVoiceStore.getState().setVoiceOn(true);
    useVoiceStore.getState().setVoiceOn(false);

    expect(useVoiceStore.getState().voiceOn).toBe(false);
    expect(localStorage.getItem(VOICE_STORAGE_KEY)).toBe("false");
  });

  it("survives storage that throws on write", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("site data blocked");
    });

    expect(() => useVoiceStore.getState().setVoiceOn(true)).not.toThrow();
    expect(useVoiceStore.getState().voiceOn).toBe(true);

    spy.mockRestore();
  });
});

describe("speech availability", () => {
  it("is false when the browser has no speechSynthesis", () => {
    // jsdom implements none, which is the case a real old browser presents.
    expect(speechAvailable()).toBe(false);
  });

  it("is true once the api is present", () => {
    vi.stubGlobal("speechSynthesis", { speak() {}, cancel() {}, speaking: false });

    expect(speechAvailable()).toBe(true);

    vi.unstubAllGlobals();
  });
});
