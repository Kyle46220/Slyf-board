import { createContext, useContext } from "react";

export const BoardContext = createContext({ origin: "", embedded: false });
export const useBoardContext = () => useContext(BoardContext);

export function boardUrl(path: string, origin: string) {
  return origin ? new URL(path, origin).href : path;
}
