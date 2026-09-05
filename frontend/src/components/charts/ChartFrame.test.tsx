import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChartFrame } from "./ChartFrame";

/**
 * ChartFrame is what makes the states pass mechanical rather than bespoke per
 * chart. If these hold, no chart can ship without its three states, because
 * every chart is this component plus a Recharts body.
 */

describe("ChartFrame", () => {
  it("renders its chart when there is data", () => {
    render(
      <ChartFrame title="Strength">
        <div>chart body</div>
      </ChartFrame>,
    );
    expect(screen.getByText("chart body")).toBeInTheDocument();
  });

  it("shows a loading state instead of the chart", () => {
    render(
      <ChartFrame title="Strength" loading>
        <div>chart body</div>
      </ChartFrame>,
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("chart body")).toBeNull();
  });

  it("shows an error with a way to recover", async () => {
    const onRetry = vi.fn();
    render(
      <ChartFrame title="Strength" error="Could not reach the server." onRetry={onRetry}>
        <div>chart body</div>
      </ChartFrame>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Could not reach the server.",
    );
    expect(screen.queryByText("chart body")).toBeNull();

    screen.getByRole("button", { name: /try again/i }).click();
    expect(onRetry).toHaveBeenCalled();
  });

  it("invites action when empty rather than reporting absence", () => {
    render(
      <ChartFrame
        title="Strength"
        isEmpty
        emptyMessage="Complete a session and your progress appears here."
      >
        <div>chart body</div>
      </ChartFrame>,
    );

    expect(
      screen.getByText("Complete a session and your progress appears here."),
    ).toBeInTheDocument();
    expect(screen.queryByText("chart body")).toBeNull();
  });

  it("carries the synthetic badge when the data is synthetic", () => {
    render(
      <ChartFrame title="Cohort" isSynthetic>
        <div>chart body</div>
      </ChartFrame>,
    );
    expect(screen.getByText("Synthetic")).toBeInTheDocument();
  });

  it("defines a clinical term in its heading when given one", () => {
    render(
      <ChartFrame title="Fatigue" tooltipTerm="MDF slope">
        <div>chart body</div>
      </ChartFrame>,
    );
    expect(screen.getByText("Fatigue")).toHaveAttribute("title");
  });

  it("prefers the error state over the empty state", () => {
    // A failed request is not the same as no data, and saying "nothing yet"
    // when the server is down would be wrong.
    render(
      <ChartFrame title="Strength" error="Server unreachable" isEmpty>
        <div>chart body</div>
      </ChartFrame>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
