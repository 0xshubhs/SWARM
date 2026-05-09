import type { Narrator } from "../types.js";

export function createTeeNarrator(...narrators: Narrator[]): Narrator {
  return new Proxy({} as Narrator, {
    get(_, prop: string) {
      return (...args: any[]) =>
        narrators.forEach((n) => {
          const fn = (n as any)[prop];
          if (typeof fn === "function") fn.apply(n, args);
        });
    },
  });
}
