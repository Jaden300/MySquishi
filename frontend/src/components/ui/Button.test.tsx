import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";

/**
 * Button resolves to three different elements. These pin that down, because a
 * navigation rendered as a button rather than a link is a real accessibility
 * bug and an easy one to introduce by accident.
 */

describe("Button", () => {
  it("renders a real button by default", () => {
    render(<Button>Start</Button>);
    expect(screen.getByRole("button", { name: "Start" })).toBeInTheDocument();
  });

  it("renders a router link when given a route", () => {
    render(
      <MemoryRouter>
        <Button to="/train">Train</Button>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Train" })).toHaveAttribute(
      "href",
      "/train",
    );
  });

  it("renders a plain anchor when given an href", () => {
    render(<Button href="/api/export/sessions.csv">Export</Button>);
    expect(screen.getByRole("link", { name: "Export" })).toHaveAttribute(
      "href",
      "/api/export/sessions.csv",
    );
  });

  it("does not fire when disabled", () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Finish
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Finish" });
    expect(button).toBeDisabled();
    button.click();
    expect(onClick).not.toHaveBeenCalled();
  });

  it("defaults to type button so it cannot submit a form by accident", () => {
    render(<Button>Pause</Button>);
    expect(screen.getByRole("button", { name: "Pause" })).toHaveAttribute(
      "type",
      "button",
    );
  });

  it("still accepts an explicit submit type", () => {
    render(<Button type="submit">Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute(
      "type",
      "submit",
    );
  });
});
