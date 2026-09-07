import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Self hosted rather than linked from a font CDN. The app must stay demoable
// with no network, and render.yaml serves the API and this bundle from one
// origin, so a third party stylesheet would be the only cross origin request
// on the critical path.
import '@fontsource-variable/fraunces'
import '@fontsource-variable/plus-jakarta-sans'

import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
