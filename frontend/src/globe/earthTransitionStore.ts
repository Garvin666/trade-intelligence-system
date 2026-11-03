import { create } from "zustand";

export type EarthTransitionStatus = "idle" | "leaving";

interface EarthTransitionState {
  status: EarthTransitionStatus;
  begin: () => void;
  reset: () => void;
}

export const useEarthTransitionStore = create<EarthTransitionState>((set) => ({
  status: "idle",
  begin: () => set({ status: "leaving" }),
  reset: () => set({ status: "idle" }),
}));
