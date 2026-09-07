/**
 * The front page.
 *
 * Carries what the landing page and the about page used to carry between them,
 * with the about half rebuilt as figures. About was 135 lines of paragraphs
 * explaining things that the app already had the data to show, so each section
 * below names the paragraph it replaced.
 *
 * There is exactly one printed sentence on this page, under the headline.
 * Everything the prose used to say is either drawn or carried on a title
 * attribute with a screen reader only copy beside it. Nothing was deleted.
 */

import { useEffect, useState } from "react";

import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { SIGNAL_CHAIN } from "../lib/hardware";
import { SquishiMascot } from "../components/SquishiMascot";
import { PoseSpot } from "../components/brand/PoseSpot";
import { DataSplit } from "../components/figures/DataSplit";
import { EnvelopeCurve } from "../components/figures/EnvelopeCurve";
import { LimitationsGrid } from "../components/figures/LimitationsGrid";
import { ModelProvenance } from "../components/figures/ModelProvenance";
import { PipelineDiagram } from "../components/figures/PipelineDiagram";
import {
  Button,
  Card,
  Figure,
  Reveal,
  SectionHeader,
  StatTile,
} from "../components/ui";

export function HomePage() {
  const preview = usePreviewContraction();

  const sessions = useApi(() => api.listSessions("demo"), []);
  const cohort = useApi(() => api.cohortSummary(), []);
  const models = useApi(() => api.models(), []);

  const all = sessions.data ?? [];
  const reps = all.reduce((total, s) => total + (s.rep_count ?? 0), 0);
  const syntheticSessions = all.filter((s) => s.is_synthetic).length;

  return (
    <div className="flex flex-col gap-16 pb-8">
      {/* 1. Hero. Squishi runs off a preview loop, so the character is doing
             its one memorable thing before anything is connected. */}
      <section className="flex flex-col items-center gap-8 py-6 text-center">
        <SquishiMascot value={preview} size={200} />

        <div className="flex max-w-2xl flex-col items-center gap-4">
          {/*
            The greeting pose sits beside the headline rather than replacing
            the mascot above it: that one is driven by the preview contraction,
            and pinning it to a pose would freeze the only thing on the page
            that moves for a reason.
          */}
          <PoseSpot pose="waving" size={64} label="Squishi waves hello" motion="bob" />
          <h1 className="text-hero text-squish-700">Grip strength, made visible</h1>
          <p className="text-lead text-ink/70">
            MySquishi turns the electrical activity of your forearm into
            something you can see, so you can tell whether today went well
            without guessing.
          </p>
        </div>

        <div className="flex flex-wrap justify-center gap-3">
          <Button to="/train?stage=profile" size="lg">
            Get started
          </Button>
          <Button to="/train?stage=live" variant="secondary" size="lg">
            Try a session
          </Button>
        </div>
      </section>

      {/* 2. Three numbers about the app itself. */}
      <Reveal>
        <div className="grid gap-4 sm:grid-cols-3">
          <StatTile
            size="hero"
            label="Repetitions recorded"
            value={sessions.loading ? null : reps}
            note="Every repetition across every session on this account, live and seeded."
          />
          <StatTile
            size="hero"
            label="People in the reference group"
            value={cohort.loading ? null : (cohort.data?.n_patients ?? null)}
            note="A synthetic reference population, generated to demonstrate the app. It does not describe real people."
          />
          <StatTile
            size="hero"
            label="Models trained"
            value={models.loading ? null : (models.data?.length ?? 0)}
            note="Models currently on disk. Anything without a trained model falls back to transparent rule based scoring and says so."
          />
        </div>
      </Reveal>

      {/* 3. Replaces About's first paragraph, on what the app measures. */}
      <Reveal>
        <section className="flex flex-col gap-6">
          <SectionHeader
            title="From muscle to a number"
            pose="explaining"
            note="Your forearm muscles produce electrical activity when you grip. The signal is filtered, rectified and smoothed into an effort envelope, then a handful of features are computed for each repetition: how quickly you built up force, how steadily you held it, and how the frequency content shifted as you tired."
          />
          <Card pad="lg">
            <PipelineDiagram nodes={SIGNAL_CHAIN} />
          </Card>
        </section>
      </Reveal>

      {/* 4. New. The measured Phase 2 response, which existed only in a
             docblock and docs/HARDWARE_FINDINGS.md until now. */}
      <Reveal>
        <Figure
          title="Why the meter is not linear"
          source="measured"
          note="Measured on the bench in Phase 2. Going from rest to a quarter effort barely moves the raw envelope, while half to maximal nearly quintuples it, so the meter uses a square root scale to expand the low effort range where rehabilitation happens."
        >
          <EnvelopeCurve />
        </Figure>
      </Reveal>

      {/* 5. Replaces About's four column model table. */}
      <Reveal>
        <section className="flex flex-col gap-6">
          <SectionHeader
            title="The models"
            pose="presenting"
            note="Read from the registry rather than a hand written list, so this cannot drift away from what is actually deployed. The bar under each score is that model's training set against the largest."
          />
          <Figure
            title="What each model was trained on"
            source="model"
            loading={models.loading}
            error={models.error}
            onRetry={models.reload}
            isEmpty={!models.data?.length}
            emptyMessage="No trained models are on disk. The app falls back to transparent rule based scoring, and says so wherever that happens."
          >
            <ModelProvenance models={models.data ?? []} />
          </Figure>
        </section>
      </Reveal>

      {/* 6. Replaces About's "where the data comes from" paragraph, with the
             actual ratio rather than a claim about it. */}
      <Reveal>
        <Figure
          title="How much of this is real"
          source="synthetic"
          pose="thinking"
          loading={sessions.loading || cohort.loading}
          error={sessions.error ?? cohort.error}
          onRetry={sessions.reload}
          note="The demo account and the reference population are synthetic. They were generated to demonstrate the app and do not describe real people. Anywhere synthetic data drives something you see, it carries the synthetic badge."
        >
          <DataSplit
            liveSessions={all.length - syntheticSessions}
            syntheticSessions={syntheticSessions}
            cohortSize={cohort.data?.n_patients ?? 0}
          />
        </Figure>
      </Reveal>

      {/* 7. Replaces About's four limitation bullets. Every sentence is kept
             verbatim on the tile it belongs to. */}
      <Reveal>
        <section className="flex flex-col gap-6">
          <SectionHeader
            title="What this cannot tell you"
            note="Grip force in kilograms is an estimate calibrated to a reference you reported yourself. It is not a dynamometer measurement, and it is labeled that way everywhere it appears. Every prediction is shown with an interval rather than a single number, because a point estimate with the uncertainty stripped off is the dishonest way to report a model."
          />
          <LimitationsGrid />
        </section>
      </Reveal>

      {/* 8. Close. */}
      <Reveal>
        <Card tone="accent" pad="lg" className="relative overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-6">
            <h2 className="text-h2 text-squish-700">
              No hardware needed to try it
            </h2>
            <div className="flex flex-wrap gap-3">
              <Button to="/train?stage=live" size="lg">
                Try a session
              </Button>
              <Button to="/lab?tab=hardware" variant="secondary" size="lg">
                See the hardware
              </Button>
            </div>
          </div>
          <PoseSpot pose="winking" size={72} placement="corner-br" motion="bob" />
        </Card>
      </Reveal>
    </div>
  );
}

/** A gentle looping contraction, so Squishi is alive on the front page. */
function usePreviewContraction(): number {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => {
      const t = ((Date.now() - started) / 1000) % 6;
      // Ramp, hold, release, rest.
      const shape =
        t < 1 ? t : t < 3 ? 1 : t < 4 ? 1 - (t - 3) : 0;
      setValue(shape * 70);
    }, 60);

    return () => window.clearInterval(timer);
  }, []);

  return value;
}
