/** The one API object every component imports: the real client or the demo fake. */

import { httpApi } from './httpApi'
import { demoApi } from './demoApi'

// Build-time constant, so the bundler drops the unused branch.
export const isDemo = import.meta.env.VITE_DEMO === 'true'

export const api = import.meta.env.VITE_DEMO === 'true' ? demoApi : httpApi
