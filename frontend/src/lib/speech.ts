/**
 * Voice coaching.
 *
 * The live session already knows everything worth saying: the coach state
 * machine writes prompts in the house voice, and each repetition closes with
 * its own feedback string. Both were rendered silently. This speaks them.
 *
 * A module level singleton beside `liveConnection` rather than a component,
 * for three reasons. A component remounts on a route change and under
 * StrictMode, and each mount reruns its effect, which is exactly how a stale
 * repetition gets announced twice. There is exactly one `window.speechSynthesis`
 * so there should be exactly one owner of it. And the precedent is already
 * here: the socket is a global source pushing into the store, and this is its
 * mirror image, a global sink reading out of it.
 *
 * Nothing here writes to the store. It only subscribes.
 */

import { useLiveStore } from "../store/live";
import { useVoiceStore } from "../store/voice";
import type { Coach, SummaryFrame } from "../types/api";

/**
 * What matters most when two things want to be said at once.
 *
 * speechSynthesis keeps its own queue and naive calls pile up, so at five
 * frames a second the app would fall behind and narrate the past. Instead a
 * higher or equal priority utterance cancels whatever is speaking, and a lower
 * one that arrives mid sentence is dropped rather than queued. A repetition
 * count that lands a second late is noise, and another repetition is coming.
 */
const Priority = {
  Feedback: 1,
  RepCount: 2,
  Phase: 3,
  Summary: 4,
} as const;

type Priority = (typeof Priority)[keyof typeof Priority];

/** Minimum gap between the two chattiest kinds, so quick repetitions do not
 *  stutter over each other. */
const FLOOR_MS = 700;

const COUNT_WORDS = [
  "One",
  "Two",
  "Three",
  "Four",
  "Five",
  "Six",
  "Seven",
  "Eight",
  "Nine",
  "Ten",
];

/** Spoken rather than displayed, so a long history does not become a recital. */
function countWord(index: number): string {
  return index >= 1 && index <= COUNT_WORDS.length
    ? COUNT_WORDS[index - 1]
    : String(index);
}

/**
 * What to say when the session ends.
 *
 * Every figure spoken here generalizes to any muscle: repetition counts,
 * percent of your own maximum, and form quality. The summary frame carries no
 * kilogram figure at all, so there is nothing on it the clinical gate would
 * withhold. Anything added here that is grip only has to be gated on
 * `summary.muscle` through `allowsKilograms`, the same way the screen does it.
 * See lib/muscle.ts.
 */
export function summaryUtterance(summary: SummaryFrame): string {
  const parts = [
    `Session complete. ${summary.rep_count} repetitions`,
    `averaging ${Math.round(summary.mean_mvc)} percent of your maximum.`,
  ];

  if (summary.mean_rep_quality !== null) {
    parts.push(`Your form scored ${Math.round(summary.mean_rep_quality)}.`);
  }

  return parts.join(" ");
}

class VoiceCoach {
  private unsubscribe: (() => void) | null = null;

  /**
   * The last repetition timestamp reacted to. Starts undefined, and the first
   * observation records whatever the store already held without speaking, so
   * starting voice on a page that already has repetitions behind it does not
   * announce one that closed before the listener arrived. The same idiom as
   * RepPulse in LiveStage.
   */
  private seenRepAt: number | undefined = undefined;

  private lastPhase: Coach["phase"] | null = null;
  private lastSpokenAt = 0;
  private currentPriority = 0;

  /** Subscribe to the live store. Safe to call twice. */
  start(): void {
    if (this.unsubscribe || !this.supported()) return;

    this.unsubscribe = useLiveStore.subscribe((state, previous) => {
      try {
        this.onChange(state, previous);
      } catch {
        /* A throw here would propagate into the websocket message handler and
           take the session down with it. Silence is the correct failure. */
      }
    });
  }

  stop(): void {
    this.unsubscribe?.();
    this.unsubscribe = null;
    this.seenRepAt = undefined;
    this.lastPhase = null;
    this.currentPriority = 0;
    this.cancel();
  }

  /**
   * Speak a zero length utterance from inside a click handler.
   *
   * Browsers drop speech that was not initiated by a user gesture, and the
   * session begins with a button press, so unlocking the queue there means the
   * first real prompt is not swallowed.
   */
  prime(): void {
    if (!this.supported() || !useVoiceStore.getState().voiceOn) return;
    try {
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(""));
    } catch {
      /* Unavailable is not a failure worth surfacing. */
    }
  }

  private supported(): boolean {
    return typeof window !== "undefined" && "speechSynthesis" in window;
  }

  private cancel(): void {
    try {
      window.speechSynthesis.cancel();
    } catch {
      /* Nothing to cancel. */
    }
  }

  private onChange(
    state: ReturnType<typeof useLiveStore.getState>,
    previous: ReturnType<typeof useLiveStore.getState>,
  ): void {
    if (!useVoiceStore.getState().voiceOn) {
      // Track the repetition marker even while muted, so switching voice on
      // mid session does not immediately announce the previous repetition.
      this.seenRepAt = state.repCompletedAt;
      this.lastPhase = state.coach?.phase ?? null;
      return;
    }

    if (state.summary && state.summary !== previous.summary) {
      this.say(summaryUtterance(state.summary), Priority.Summary);
      return;
    }

    const phase = state.coach?.phase ?? null;
    if (phase && phase !== this.lastPhase) {
      this.lastPhase = phase;
      // The prompt is the copy already on screen. Speaking a different string
      // here would fork the wording between what is read and what is heard.
      if (state.coach?.prompt) this.say(state.coach.prompt, Priority.Phase);
    }

    const at = state.repCompletedAt;
    const previousAt = this.seenRepAt;
    this.seenRepAt = at;

    if (previousAt === undefined || at === previousAt || !at) return;

    const rep = state.reps[state.reps.length - 1];
    if (!rep) return;

    this.say(countWord(rep.index + 1), Priority.RepCount);
    if (rep.feedback) this.say(rep.feedback, Priority.Feedback);
  }

  private say(text: string, priority: Priority): void {
    if (!text || !this.supported()) return;

    const now = Date.now();
    const speaking = this.isSpeaking();

    // A lower priority utterance never interrupts, and never queues behind
    // what is already being said.
    if (speaking && priority < this.currentPriority) return;

    if (
      !speaking &&
      priority <= Priority.RepCount &&
      now - this.lastSpokenAt < FLOOR_MS
    ) {
      return;
    }

    try {
      if (speaking) this.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
      this.currentPriority = priority;

      // Only the chatty kinds arm the floor. A coaching prompt is not a reason
      // to swallow the repetition count that lands in the same frame.
      if (priority <= Priority.RepCount) this.lastSpokenAt = now;
    } catch {
      /* Speech is an enhancement. Losing it must not affect the session. */
    }
  }

  private isSpeaking(): boolean {
    try {
      return window.speechSynthesis.speaking;
    } catch {
      return false;
    }
  }
}

export const voiceCoach = new VoiceCoach();
