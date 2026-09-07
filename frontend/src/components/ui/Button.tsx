/**
 * The one button.
 *
 * Before this existed the primary button's utility string was copy pasted
 * fourteen times and the secondary's about eight, which is how a hover colour
 * ends up different on two pages. Anything that looks like a button in this
 * app renders through here.
 *
 * It resolves to a router Link, an anchor or a real button depending on which
 * of to and href is set, so a link never has to be dressed up as a button by
 * hand.
 */

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "md" | "lg";

interface CommonProps {
  variant?: Variant;
  size?: Size;
  className?: string;
  children: ReactNode;
}

interface ButtonAsButton
  extends CommonProps,
    Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children"> {
  to?: never;
  href?: never;
}

interface ButtonAsLink extends CommonProps {
  /** Renders a react-router Link. */
  to: string;
  href?: never;
  onClick?: () => void;
}

interface ButtonAsAnchor extends CommonProps {
  /** Renders a plain anchor. Used for the CSV export endpoints. */
  href: string;
  to?: never;
  download?: boolean | string;
}

type ButtonProps = ButtonAsButton | ButtonAsLink | ButtonAsAnchor;

const VARIANT: Record<Variant, string> = {
  primary:
    "bg-squish-500 text-mist shadow-soft hover:bg-squish-700 disabled:bg-squish-300",
  secondary:
    "border border-squish-300 text-squish-700 bg-mist hover:bg-squish-50 disabled:text-ink/40",
  ghost: "text-squish-700 hover:bg-squish-50 disabled:text-ink/40",
  danger: "border border-alert text-alert bg-mist hover:bg-alert hover:text-mist",
};

const SIZE: Record<Size, string> = {
  md: "px-5 py-2.5 text-label",
  lg: "px-7 py-3.5 text-lead",
};

/*
  active:scale is the cheapest motion in the app and the one users feel most
  directly. It is a transform transition, so the reduced motion block in
  index.css already neutralises it.
*/
const BASE =
  "inline-flex items-center justify-center gap-2 rounded-pill font-medium " +
  "transition-transform duration-150 active:scale-[0.98] " +
  "disabled:cursor-not-allowed disabled:active:scale-100";

export function Button(props: ButtonProps) {
  const { variant = "primary", size = "md", className = "", children } = props;
  const classes = `${BASE} ${VARIANT[variant]} ${SIZE[size]} ${className}`;

  if ("to" in props && props.to !== undefined) {
    const { to, onClick } = props;
    return (
      <Link to={to} onClick={onClick} className={classes}>
        {children}
      </Link>
    );
  }

  if ("href" in props && props.href !== undefined) {
    const { href, download } = props;
    return (
      <a href={href} download={download} className={classes}>
        {children}
      </a>
    );
  }

  const { variant: _v, size: _s, className: _c, children: _ch, ...rest } =
    props as ButtonAsButton;

  return (
    // type defaults to button so a control inside a form cannot submit it by
    // accident, but an explicit type in rest still wins.
    <button type="button" {...rest} className={classes}>
      {children}
    </button>
  );
}
