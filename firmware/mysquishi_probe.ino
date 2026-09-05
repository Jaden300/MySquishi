/*
 * MySquishi Phase 2 bring up probe.
 *
 * Reads one analog pin at a fixed rate and prints "millis,value" over serial.
 * That is the whole job. There is deliberately no filtering, no thresholding,
 * no rep detection and no state on the microcontroller: every one of those
 * lives in Python, where it is version controlled and covered by tests. A
 * board that only reports what the ADC saw cannot lie to the analysis about
 * what the sensor did.
 *
 * ---------------------------------------------------------------------------
 * BEFORE YOU RUN THIS: set the MyoWare 2.0 output selector to RAW.
 * ---------------------------------------------------------------------------
 * ENV is the factory default and it is the wrong mode for this pipeline. The
 * analysis bandpasses 20-450 Hz, and an envelope has already been rectified
 * and smoothed, so almost none of it survives that filter. tools/probe.py
 * detects this and will tell you, but it costs a 60 second recording to find
 * out. Check the switch first.
 *
 * Wiring, for a MyoWare 2.0 with the Link Shield:
 *
 *   Sensor -> Link Shield -> 3.5 mm TRS cable -> Arduino Shield -> A0
 *
 * Upload with the Arduino IDE, then close the Serial Monitor before running
 * the probe. The monitor holds the port exclusively and probe.py will not be
 * able to open it.
 */

// The analog pin the Arduino Shield routes the sensor to.
const uint8_t SENSOR_PIN = A0;

// 500 Hz, not the 1000 Hz the app's simulated pipeline uses.
//
// The limit is the serial link, not the ADC. A "millis,value" line is 10 to
// 12 bytes, and 8N1 framing costs 10 bits per byte, so 115200 baud carries
// only about 960 to 1150 lines per second. That is at or below 1000 Hz with
// no headroom at all, which turns every scheduling hiccup into a dropped
// sample. At 230400 baud and 500 Hz there is roughly 4x headroom, so a
// dropout in the recording means a real problem rather than an arithmetic
// certainty.
//
// The cost is honest and documented: Nyquist falls to 250 Hz, so the 250-450
// Hz part of the sEMG band is not observed and spectral fatigue is measured
// over a truncated spectrum. The Python bandpass clamps its upper edge to
// just under Nyquist automatically, so nothing breaks. See
// docs/HARDWARE_CHECKLIST.md.
const unsigned long SAMPLE_HZ = 500UL;
const unsigned long PERIOD_US = 1000000UL / SAMPLE_HZ;
const unsigned long BAUD = 230400UL;

// Bytes that must be free in the TX buffer before a sample is printed. A full
// line plus its newline fits comfortably in 16.
const int TX_HEADROOM = 16;

unsigned long nextSampleUs = 0;

void setup() {
  Serial.begin(BAUD);
  while (!Serial) {
    ; // Boards with native USB need a moment. The Uno falls straight through.
  }

  // Header lines are prefixed with '#' so the parser in probe.py skips them.
  // They travel with the recording into the CSV, so a trace found on disk
  // later still says what produced it.
  Serial.println("# mysquishi_probe v1");
  Serial.print("# sample_hz=");
  Serial.println(SAMPLE_HZ);
  Serial.print("# baud=");
  Serial.println(BAUD);
  Serial.println("# adc_bits=10");
  Serial.println("# set the MyoWare 2.0 output selector to RAW, not ENV");
  Serial.println("# columns: millis,adc_counts");

  nextSampleUs = micros();
}

void loop() {
  // Pace on an accumulating deadline rather than delay(). delay() waits a
  // fixed time *after* the work, so the true period is the delay plus the
  // cost of analogRead and print, and the sample rate drifts below the
  // configured one. Advancing a deadline instead makes the average rate
  // exact: a slow iteration is absorbed by the next one rather than pushing
  // every future sample later.
  nextSampleUs += PERIOD_US;

  // The subtraction is compared as a signed value on purpose. micros() rolls
  // over roughly every 70 minutes, and a plain "micros() < nextSampleUs"
  // comparison would stall here for the rest of that period when it happens.
  // Signed difference wraps correctly and the rollover passes unnoticed.
  while ((long)(micros() - nextSampleUs) < 0) {
    ; // Spin until the deadline. Nothing else needs doing.
  }

  int value = analogRead(SENSOR_PIN);

  // Never block on a full TX buffer. Serial.print stalls when the buffer is
  // full, and stalling here would delay the *next* sample too, turning one
  // late byte into a growing timing error. Skipping keeps the clock honest,
  // and the gap is visible to the analysis anyway: probe.py recovers dropouts
  // from the millis column, which is why the timestamp is printed rather than
  // assumed. Do not print a counter here, it would corrupt the two column
  // format that the parser depends on.
  if (Serial.availableForWrite() < TX_HEADROOM) {
    return;
  }

  Serial.print(millis());
  Serial.print(',');
  Serial.println(value);
}
