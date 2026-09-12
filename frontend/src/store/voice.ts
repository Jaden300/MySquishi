/**
 * Voice coaching preference.
 *
 * Structurally the same as the demo mode store next door, including the
 * try/catch around storage: it throws outright in a private window or with
 * site data blocked, rather than merely returning null, and a failure to read
 * a preference must not take the session down.
 *
 * Defaults **off**, which is the opposite of demo mode and deliberate. An app
 * that starts talking without being asked is the wrong first impression in a
 * shared room, and browsers block speech before a user gesture anyway, so a
 * default of on would appear broken on first load and work on the second.
 * Demo mode defaults on because a cold visit needs a populated app; there is
 * no equivalent argument for sound.
 */

import { create } from "zustand";

const STORAGE_KEY = "mysquishi.voice";

function readStored(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function writeStored(on: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(on));
  } catch {
    /* Preference is not persisted. The session still works. */
  }
}

interface VoiceState {
  voiceOn: boolean;
  setVoiceOn: (on: boolean) => void;
}

export const useVoiceStore = create<VoiceState>((set) => ({
  voiceOn: readStored(),
  setVoiceOn: (on) => {
    writeStored(on);
    set({ voiceOn: on });
  },
}));

/**
 * Whether speech is available at all in this browser.
 *
 * Kept as a plain function so a component can hide the toggle rather than
 * offering a switch that does nothing. jsdom has no speechSynthesis, so this
 * is false under test unless a test stubs one.
 */
export function speechAvailable(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export { STORAGE_KEY as VOICE_STORAGE_KEY };
