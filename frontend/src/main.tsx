import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Self hosted rather than linked from a font CDN. The app must stay demoable
// with no network, and render.yaml serves the API and this bundle from one
// origin, so a third party stylesheet would be the only cross origin request
// on the critical path.
//
// full.css rather than the bare package. Fraunces exposes ital, opsz, wght,
// SOFT and WONK, but the default import ships the wght only file, so the
// font-variation-settings in index.css had no axes to move and every heading
// rendered at SOFT 0: hard terminals, against a mascot built entirely of round
// ones.
//
// Not soft.css plus wonk.css, which looks like the cheaper pick and is not.
// Each subset declares its own @font-face under the same family name and the
// same unicode-range, so the later import shadows the earlier one outright:
// that pairing ships 98KB of Latin to end up with WONK and no SOFT. One file
// carrying both axes is the only version of this that works.
import '@fontsource-variable/fraunces/full.css'
import '@fontsource-variable/plus-jakarta-sans'

import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
