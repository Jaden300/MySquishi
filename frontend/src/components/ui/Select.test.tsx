/**
 * The branded select.
 *
 * This component exists because a native select cannot have its popup styled,
 * which means reimplementing the keyboard behaviour the native control gave
 * away for free. That behaviour is the whole risk in the swap, so it is what
 * these cover: a listbox that looks right and cannot be driven from the
 * keyboard is a regression against the accessibility floor, not a redesign.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Select, type SelectOption } from "./Select";

const OPTIONS: SelectOption[] = [
  { value: "biceps", label: "Biceps" },
  { value: "forearm", label: "Forearm" },
  { value: "quadriceps", label: "Quadriceps", disabled: true },
  { value: "calf", label: "Calf" },
];

function setup(overrides: Partial<React.ComponentProps<typeof Select>> = {}) {
  const onChange = vi.fn();
  render(
    <Select
      options={OPTIONS}
      value="biceps"
      onChange={onChange}
      aria-label="Muscle"
      {...overrides}
    />,
  );
  return { onChange, trigger: screen.getByRole("combobox") };
}

describe("Select", () => {
  it("shows the selected label and no popup until opened", () => {
    const { trigger } = setup();

    expect(trigger).toHaveTextContent("Biceps");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("opens on click and lists every option", async () => {
    const user = userEvent.setup();
    const { trigger } = setup();

    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(OPTIONS.length);
  });

  it("commits the clicked option", async () => {
    const user = userEvent.setup();
    const { onChange, trigger } = setup();

    await user.click(trigger);
    await user.click(screen.getByRole("option", { name: "Forearm" }));

    expect(onChange).toHaveBeenCalledWith("forearm");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("moves with the arrow keys and commits on Enter", async () => {
    const user = userEvent.setup();
    const { onChange, trigger } = setup();

    trigger.focus();
    await user.keyboard("{ArrowDown}"); // opens, active on the current value
    await user.keyboard("{ArrowDown}"); // Forearm
    await user.keyboard("{Enter}");

    expect(onChange).toHaveBeenCalledWith("forearm");
  });

  it("skips a disabled option rather than landing on it", async () => {
    const user = userEvent.setup();
    const { onChange, trigger } = setup();

    trigger.focus();
    await user.keyboard("{ArrowDown}"); // open, on Biceps
    await user.keyboard("{ArrowDown}"); // Forearm
    await user.keyboard("{ArrowDown}"); // skips Quadriceps, lands on Calf
    await user.keyboard("{Enter}");

    expect(onChange).toHaveBeenCalledWith("calf");
    expect(onChange).not.toHaveBeenCalledWith("quadriceps");
  });

  it("marks the disabled option so assistive technology agrees", async () => {
    const user = userEvent.setup();
    const { trigger } = setup();

    await user.click(trigger);

    expect(screen.getByRole("option", { name: "Quadriceps" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("closes on Escape and returns focus to the trigger", async () => {
    const user = userEvent.setup();
    const { onChange, trigger } = setup();

    await user.click(trigger);
    await user.keyboard("{Escape}");

    /*
      aria-expanded rather than the absence of the node. The popup exits
      through AnimatePresence, which keeps it mounted for the length of the
      fade, and jsdom never advances those frames. This is the state assistive
      technology reads, so it is also the one worth asserting.
    */
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveFocus();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("jumps to an option by typing its first letter", async () => {
    const user = userEvent.setup();
    const { onChange, trigger } = setup();

    await user.click(trigger);
    await user.keyboard("c");
    await user.keyboard("{Enter}");

    expect(onChange).toHaveBeenCalledWith("calf");
  });

  it("does not open when disabled", async () => {
    const user = userEvent.setup();
    const { trigger } = setup({ disabled: true });

    await user.click(trigger);

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("falls back to the placeholder when no option matches", () => {
    const { trigger } = setup({ value: "", placeholder: "Select a muscle" });

    expect(trigger).toHaveTextContent("Select a muscle");
  });
});
