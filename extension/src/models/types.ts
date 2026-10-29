// Aliases over the generated API types (api.d.ts, built from the backend OpenAPI schema by
// `npm run gen:api`). Do not hand-write response shapes here: regenerate instead.
import type { components } from './api.js';

type Schemas = components['schemas'];

export type Evidence = Schemas['EvidenceItem'];
export type InsufficiencySignal = Schemas['InsufficiencySignal'];
export type ClaimResult = Schemas['ClaimResult'];
export type AnalyzeResponse = Schemas['AnalyzeResponse'];
