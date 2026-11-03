import { useEffect, useReducer } from "react";
import { DEMO_STAGES } from "./DEMO_STAGES";

interface DemoPlaybackOptions {
  stageCount?: number;
  intervalMs?: number;
  autoStart?: boolean;
  loop?: boolean;
}

export function useDemoPlayback({
  stageCount = DEMO_STAGES.length,
  intervalMs = 1200,
  autoStart = false,
  loop = true,
}: DemoPlaybackOptions = {}) {
  interface PlaybackState {
    tick: number;
    playing: boolean;
    loop: boolean;
  }

  type PlaybackAction =
    | { type: "tick" }
    | { type: "play" }
    | { type: "pause" }
    | { type: "reset" }
    | { type: "toggle-loop" };

  const [state, dispatch] = useReducer(
    (current: PlaybackState, action: PlaybackAction): PlaybackState => {
      if (action.type === "tick") {
        if (!current.playing) return current;
        const next = current.tick + 1;
        return {
          tick: next,
          loop: current.loop,
          playing: current.loop || next < stageCount,
        };
      }
      if (action.type === "play") return { ...current, playing: true };
      if (action.type === "pause") return { ...current, playing: false };
      if (action.type === "reset") return { ...current, tick: 0, playing: false };
      return { ...current, loop: !current.loop };
    },
    undefined,
    (): PlaybackState => ({ tick: 0, playing: autoStart, loop }),
  );

  useEffect(() => {
    if (!state.playing) return;
    const timer = window.setInterval(() => {
      dispatch({ type: "tick" });
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [state.playing, intervalMs]);

  const stageIndex = state.loop
    ? state.tick % stageCount
    : Math.min(state.tick, stageCount - 1);

  return {
    playing: state.playing,
    tick: state.tick,
    stageIndex,
    loop: state.loop,
    play: () => dispatch({ type: "play" }),
    pause: () => dispatch({ type: "pause" }),
    reset: () => dispatch({ type: "reset" }),
    setLoop: () => dispatch({ type: "toggle-loop" }),
  };
}
