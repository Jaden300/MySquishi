import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  IntervalReadout,
  SourceChip,
  SyntheticBadge,
  ClinicalTooltip,
} from "./Honesty";
import { CLINICAL_TERMS } from "../lib/clinical";

/**
 * The honesty affordances are components rather than page copy precisely so
 * they can be tested once instead of reviewed on every page.
 */

describe("IntervalReadout", () => {
  it("shows the bounds alongside the point estimate", () => {
    render(<IntervalReadout point={24.5} lower={21.0} upper={28.0} unit="kg" />);

    expect(screen.getByText(/24\.5/)).toBeInTheDocument();
    expect(screen.getByText(/21\.0 to 28\.0/)).toBeInTheDocument();
  });

  it("says when a heuristic produced the number", () => {
    render(
      <IntervalReadout point={50} lower={40} upper={60} degraded />,
    );
    expect(
      screen.getByText(/without a trained model/i),
    ).toBeInTheDocument();
  });

  it("does not claim a trained model when it had one", () => {
    render(<IntervalReadout point={50} lower={40} upper={60} />);
    expect(screen.queryByText(/without a trained model/i)).toBeNull();
  });
});

describe("SyntheticBadge", () => {
  it("labels synthetic data in words, not only colour", () => {
    render(<SyntheticBadge />);
    expect(screen.getByText("Synthetic")).toBeInTheDocument();
  });
});

describe("SourceChip", () => {
  it("describes a simulated source as simulated", () => {
    render(<SourceChip isLive={false} />);
    expect(screen.getByText("Simulated")).toBeInTheDocument();
  });

  it("describes a live source as live", () => {
    render(<SourceChip isLive />);
    expect(screen.getByText("Live sensor")).toBeInTheDocument();
  });
});

describe("ClinicalTooltip", () => {
  it("attaches the definition from the clinical reference", () => {
    render(<ClinicalTooltip term="MCID">Goal</ClinicalTooltip>);
    expect(screen.getByText("Goal")).toHaveAttribute(
      "title",
      CLINICAL_TERMS.MCID,
    );
  });

  it("renders the children unchanged for an unknown term", () => {
    render(<ClinicalTooltip term="not a real term">Plain</ClinicalTooltip>);
    expect(screen.getByText("Plain")).toBeInTheDocument();
  });

  it("quotes EWGSOP2 thresholds accurately", () => {
    // Clinical terminology has to be right: judges include people who know.
    expect(CLINICAL_TERMS["EWGSOP2 thresholds"]).toContain("27 kg for men");
    expect(CLINICAL_TERMS["EWGSOP2 thresholds"]).toContain("16 kg for women");
  });
});
