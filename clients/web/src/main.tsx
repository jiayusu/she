import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { LiveAppApi } from "@/api/appApi";
import { RootApp } from "@/features/RootApp";
import { AppModel } from "@/state/appModel";
import "@/design/theme.css";

// Dev goes through the Vite proxy (same-origin); production builds read
// SHE_WEB_API_BASE at deploy time and fall back to same-origin /v1.
const embeddedBase = (globalThis as { __SHE_WEB_API_BASE__?: string }).__SHE_WEB_API_BASE__;
const api = new LiveAppApi({ baseUrl: embeddedBase ?? "" });
const rpgChildId = import.meta.env.VITE_SHE_RPG_CHILD_ID?.trim();
const rpgSessionId = import.meta.env.VITE_SHE_RPG_SESSION_ID?.trim();
const model = new AppModel(
  api,
  rpgChildId && rpgSessionId
    ? { rpgDemoIdentity: { childId: rpgChildId, sessionId: rpgSessionId } }
    : {},
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RootApp model={model} />
  </StrictMode>,
);
