import { useEffect, useSyncExternalStore } from "react";

import { AppModel, initialAppState, type AppState } from "./appModel";

export function useAppModel(model: AppModel): AppState {
  useEffect(() => {
    void model.load();
  }, [model]);

  return useSyncExternalStore(
    (listener) => model.subscribe(listener),
    () => model.getState(),
    () => initialAppState,
  );
}
