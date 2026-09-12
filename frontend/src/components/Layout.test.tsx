/**
 * The shell, and the two keyboard affordances that live in it.
 *
 * The accessibility floor in docs/DESIGN.md asks for visible keyboard focus on
 * every interactive element. It was missing the step before that: a way to get
 * past the header at all. Without a skip link, reaching the page content means
 * tabbing through the wordmark, the demo toggle and four nav links, on every
 * route, every time.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { Layout } from "./Layout";

function renderLayout() {
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: <Layout />,
        children: [{ index: true, element: <h1>Home</h1> }],
      },
    ],
    { initialEntries: ["/"] },
  );

  return render(<RouterProvider router={router} />);
}

describe("Layout", () => {
  it("offers a skip link as the first thing the keyboard reaches", async () => {
    const user = userEvent.setup();
    renderLayout();

    await user.tab();

    expect(screen.getByRole("link", { name: /skip to content/i })).toHaveFocus();
  });

  it("points the skip link at the main landmark", () => {
    renderLayout();

    const skip = screen.getByRole("link", { name: /skip to content/i });
    const main = document.querySelector("main");

    // A skip link that points nowhere is worse than none: it takes the focus
    // and leaves the reader where they were.
    expect(skip).toHaveAttribute("href", "#main");
    expect(main).toHaveAttribute("id", "main");
  });

  it("gives the navigation four links and no hidden menu", () => {
    renderLayout();

    // Four fit in one row at 390px, which is why there is no hamburger. If a
    // fifth ever arrives, that stops being true.
    const nav = screen.getByRole("navigation");
    expect(nav.querySelectorAll("a")).toHaveLength(4);
  });
});
