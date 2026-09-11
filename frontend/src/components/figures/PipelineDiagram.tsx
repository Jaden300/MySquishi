/**
 * A chain of stages, drawn.
 *
 * Used twice at two lengths: five signal stages on the front page, where it
 * answers what the app does, and seven wiring links on the hardware tab, where
 * it answers what plugs into what. Both used to be an ordered list of
 * sentences.
 *
 * The connectors carry a travelling dash, so the signal is visibly moving
 * through the chain rather than sitting in it. That is decoration and stops
 * under reduced motion along with every other CSS animation.
 */

import type { ReactNode } from "react";

import type { ChainNode } from "../../lib/hardware";
import { GlyphTile } from "./Glyph";

interface PipelineDiagramProps {
  nodes: ChainNode[];
  /** Rendered inside the node it belongs to. Used for the live envelope trace. */
  slot?: Record<string, ReactNode>;
}

export function PipelineDiagram({ nodes, slot }: PipelineDiagramProps) {
  return (
    /*
      A list rather than a picture: a screen reader gets the chain in order
      with each node's detail, which is exactly what the prose version gave,
      and the visual arrangement is layout on top of that.
    */
    <ol className="flex flex-col items-stretch lg:flex-row">
      {nodes.map((node, i) => (
        <li
          key={node.label}
          className="flex flex-1 flex-col items-center lg:flex-row"
        >
          <div
            title={node.detail}
            className="flex w-full flex-1 flex-col items-center justify-center gap-2 rounded-card border border-squish-100 bg-squish-50 px-3 py-4 text-center"
          >
            <GlyphTile id={node.glyph} size={24} />
            <span className="text-label text-squish-700">{node.label}</span>
            {slot?.[node.label] ?? null}
            {node.detail ? (
              <span className="sr-only">{node.detail}</span>
            ) : null}
          </div>

          {i < nodes.length - 1 ? <Connector /> : null}
        </li>
      ))}
    </ol>
  );
}

/** The travelling dash between two nodes. Horizontal on wide, vertical below. */
function Connector() {
  return (
    <span aria-hidden="true" className="shrink-0">
      {/* Two orientations rather than a rotation, so the dash always travels
          in reading order for the layout it is in. */}
      <svg
        width="12"
        height="26"
        viewBox="0 0 12 26"
        className="lg:hidden"
        fill="none"
      >
        <path
          d="M6 1v24"
          stroke="var(--squish-300)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="4 6"
          className="flow"
        />
      </svg>
      <svg
        width="26"
        height="12"
        viewBox="0 0 26 12"
        className="hidden lg:block"
        fill="none"
      >
        <path
          d="M1 6h24"
          stroke="var(--squish-300)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="4 6"
          className="flow"
        />
      </svg>
    </span>
  );
}
