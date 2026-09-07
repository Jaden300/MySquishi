import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Tabs } from "./Tabs";

/**
 * The tabs carry what used to be separate routes, so a keyboard user has to be
 * able to reach every section. These pin the roving tabindex pattern down.
 */

const TABS = [
  { id: "strength", label: "Strength" },
  { id: "consistency", label: "Consistency" },
  { id: "insights", label: "Insights" },
];

function setup(value = "strength") {
  const onChange = vi.fn();
  render(
    <Tabs tabs={TABS} value={value} onChange={onChange} name="progress" />,
  );
  return { onChange };
}

describe("Tabs", () => {
  it("marks only the active tab as selected", () => {
    setup("consistency");
    expect(screen.getByRole("tab", { name: "Consistency" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Strength" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("keeps one stop in the tab order", () => {
    setup("strength");
    expect(screen.getByRole("tab", { name: "Strength" })).toHaveAttribute(
      "tabindex",
      "0",
    );
    expect(screen.getByRole("tab", { name: "Insights" })).toHaveAttribute(
      "tabindex",
      "-1",
    );
  });

  it("moves to the next tab on arrow right", async () => {
    const { onChange } = setup("strength");
    await userEvent.click(screen.getByRole("tab", { name: "Strength" }));
    await userEvent.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenLastCalledWith("consistency");
  });

  it("wraps around from the first tab on arrow left", async () => {
    const { onChange } = setup("strength");
    await userEvent.click(screen.getByRole("tab", { name: "Strength" }));
    await userEvent.keyboard("{ArrowLeft}");
    expect(onChange).toHaveBeenLastCalledWith("insights");
  });

  it("jumps to the last tab on End", async () => {
    const { onChange } = setup("strength");
    await userEvent.click(screen.getByRole("tab", { name: "Strength" }));
    await userEvent.keyboard("{End}");
    expect(onChange).toHaveBeenLastCalledWith("insights");
  });

  it("points each tab at its panel", () => {
    setup();
    expect(screen.getByRole("tab", { name: "Strength" })).toHaveAttribute(
      "aria-controls",
      "progress-panel-strength",
    );
  });
});
