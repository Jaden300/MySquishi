/**
 * The branded select.
 *
 * A native select cannot have its popup styled: the browser draws the arrow,
 * the list and every row, so five controls in this app were rendering as
 * system chrome dropped into a violet page. This is the listbox pattern
 * instead, which is the only way to own that popup.
 *
 * Written once here rather than per call site because the keyboard behaviour
 * is the part a native select gives away for free, and reimplementing it five
 * times is how four of them end up subtly broken. Arrow keys move, Enter and
 * Space commit, Escape closes and restores focus, Home and End jump, and
 * typing a letter jumps to the next option starting with it.
 */

import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

export interface SelectOption {
  value: string;
  label: string;
  /** Rendered dimmed and skipped by the keyboard, as a native select does. */
  disabled?: boolean;
}

interface SelectProps {
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  /** Wired to the trigger, so a visible label can point at this control. */
  id?: string;
  disabled?: boolean;
  /** Shown when no option matches the current value. */
  placeholder?: string;
  title?: string;
  className?: string;
  "aria-label"?: string;
}

export function Select({
  options,
  value,
  onChange,
  id,
  disabled = false,
  placeholder = "Select",
  title,
  className = "",
  "aria-label": ariaLabel,
}: SelectProps) {
  const reduced = useReducedMotion();
  const generatedId = useId();
  const triggerId = id ?? `select-${generatedId}`;
  const listId = `${triggerId}-listbox`;

  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<(HTMLLIElement | null)[]>([]);
  /* Accumulated printable keys, for type ahead. */
  const typed = useRef({ buffer: "", at: 0 });

  const selectedIndex = options.findIndex((option) => option.value === value);
  const selected = selectedIndex >= 0 ? options[selectedIndex] : undefined;

  const firstEnabled = () => options.findIndex((option) => !option.disabled);

  /* Opening lands on the current value, or on the first option a keyboard is
     allowed to reach if nothing is selected yet. */
  const openList = () => {
    if (disabled) return;
    setActive(selectedIndex >= 0 ? selectedIndex : Math.max(firstEnabled(), 0));
    setOpen(true);
  };

  const close = (refocus: boolean) => {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  };

  const commit = (index: number) => {
    const option = options[index];
    if (!option || option.disabled) return;
    onChange(option.value);
    close(true);
  };

  /* Skips disabled options rather than landing on them and refusing to commit,
     which is what a native select does. Stops at the ends instead of wrapping
     past a run of disabled entries forever. */
  const step = (from: number, delta: number) => {
    let next = from;
    for (let i = 0; i < options.length; i += 1) {
      next += delta;
      if (next < 0 || next >= options.length) return;
      if (!options[next].disabled) {
        setActive(next);
        return;
      }
    }
  };

  const edge = (delta: 1 | -1) => {
    const order = delta === 1 ? [...options.keys()] : [...options.keys()].reverse();
    const found = order.find((i) => !options[i].disabled);
    if (found !== undefined) setActive(found);
  };

  /* Type ahead. Keys within a second extend the search rather than restarting
     it, so "st" reaches "Stopwatch" and not the first word beginning with t. */
  const typeAhead = (key: string) => {
    const now = Date.now();
    typed.current.buffer =
      now - typed.current.at > 1000 ? key : typed.current.buffer + key;
    typed.current.at = now;

    const query = typed.current.buffer.toLowerCase();
    const match = options.findIndex(
      (option) => !option.disabled && option.label.toLowerCase().startsWith(query),
    );
    if (match >= 0) {
      setActive(match);
      if (!open) commit(match);
    }
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (disabled) return;

    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        if (!open) openList();
        else step(active, 1);
        return;
      case "ArrowUp":
        event.preventDefault();
        if (!open) openList();
        else step(active, -1);
        return;
      case "Home":
        if (!open) return;
        event.preventDefault();
        edge(1);
        return;
      case "End":
        if (!open) return;
        event.preventDefault();
        edge(-1);
        return;
      case "Enter":
        event.preventDefault();
        if (open) commit(active);
        else openList();
        return;
      case " ":
        /* Space commits an open list, but has to stay available for type ahead
           once a query is running, or a two word label cannot be reached. */
        if (open && typed.current.buffer === "") {
          event.preventDefault();
          commit(active);
          return;
        }
        break;
      case "Escape":
        if (open) {
          event.preventDefault();
          close(true);
        }
        return;
      case "Tab":
        /* Let focus leave, but do not leave a popup hanging behind it. */
        if (open) setOpen(false);
        return;
      default:
        break;
    }

    if (event.key.length === 1 && !event.metaKey && !event.ctrlKey && !event.altKey) {
      event.preventDefault();
      typeAhead(event.key);
    }
  };

  /* Close on a click that lands outside. pointerdown rather than click so the
     list is gone before the outside control reacts. */
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  /* Keep the active option in view when the arrows walk past the fold. Guarded
     because scrollIntoView is a browser affordance jsdom does not implement,
     and scrolling is not worth taking a render down for. */
  useEffect(() => {
    if (!open) return;
    const el = optionRefs.current[active];
    if (typeof el?.scrollIntoView === "function") {
      el.scrollIntoView({ block: "nearest" });
    }
  }, [open, active]);

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        id={triggerId}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-haspopup="listbox"
        aria-activedescendant={open ? `${listId}-${active}` : undefined}
        aria-label={ariaLabel}
        disabled={disabled}
        title={title}
        onClick={() => (open ? close(false) : openList())}
        onKeyDown={onKeyDown}
        className="flex w-full items-center justify-between gap-3 rounded-card border border-squish-100 bg-mist px-3.5 py-2.5 text-left text-label text-ink transition-colors hover:border-squish-300 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className={selected ? "" : "text-ink/70"}>
          {selected?.label ?? placeholder}
        </span>
        <Chevron open={open} />
      </button>

      <AnimatePresence>
        {open ? (
          <motion.ul
            id={listId}
            role="listbox"
            aria-label={ariaLabel}
            initial={reduced ? false : { opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? { opacity: 0 } : { opacity: 0, y: -4 }}
            transition={reduced ? { duration: 0 } : { duration: 0.12 }}
            className="absolute z-40 mt-2 max-h-64 w-full overflow-auto rounded-card border border-squish-100 bg-mist p-1.5 shadow-soft"
          >
            {options.map((option, i) => {
              const isSelected = option.value === value;
              const isActive = i === active;
              return (
                <li
                  key={option.value}
                  ref={(el) => {
                    optionRefs.current[i] = el;
                  }}
                  id={`${listId}-${i}`}
                  role="option"
                  aria-selected={isSelected}
                  aria-disabled={option.disabled || undefined}
                  onPointerDown={(event) => {
                    /* Keep focus on the trigger, so closing can restore it
                       without the browser having moved it to the list. */
                    event.preventDefault();
                    commit(i);
                  }}
                  onPointerEnter={() => !option.disabled && setActive(i)}
                  className={`flex cursor-pointer items-center justify-between gap-3 rounded-[10px] px-3 py-2 text-label transition-colors ${
                    option.disabled
                      ? "cursor-not-allowed text-ink/70 line-through"
                      : isSelected
                        ? "text-squish-700"
                        : "text-ink"
                  } ${isActive && !option.disabled ? "bg-squish-50" : ""}`}
                >
                  <span>{option.label}</span>
                  {isSelected ? <Check /> : null}
                </li>
              );
            })}
          </motion.ul>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={`shrink-0 text-squish-500 transition-transform duration-200 ${
        open ? "rotate-180" : ""
      }`}
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function Check() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className="shrink-0 text-squish-500"
    >
      <path d="m5 13 4 4L19 7" />
    </svg>
  );
}
