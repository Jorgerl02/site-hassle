"use client";

import createCache from "@emotion/cache";
import { CacheProvider } from "@emotion/react";
import { useServerInsertedHTML } from "next/navigation";
import { useState, type ReactNode } from "react";

/**
 * Emotion SSR registry for the App Router (Chakra UI v3 docs, «Next.js App»).
 * Without it Emotion renders its `<style data-emotion>` tags inline next to the
 * components during SSR, so the server HTML has nodes the client tree does not
 * and React throws a hydration mismatch (#418) and re-renders the whole page.
 * Here every style inserted while rendering is collected and flushed into the
 * document head through `useServerInsertedHTML`, before the markup that uses it.
 */
export function EmotionRegistry({ children }: { children: ReactNode }) {
  const [{ cache, flush }] = useState(() => {
    const cache = createCache({ key: "css" });
    cache.compat = true;
    const previousInsert = cache.insert;
    let inserted: string[] = [];
    cache.insert = (...args) => {
      const serialized = args[1];
      if (cache.inserted[serialized.name] === undefined) inserted.push(serialized.name);
      return previousInsert(...args);
    };
    const flush = () => {
      const previouslyInserted = inserted;
      inserted = [];
      return previouslyInserted;
    };
    return { cache, flush };
  });

  useServerInsertedHTML(() => {
    const names = flush();
    if (names.length === 0) return null;
    const styles = names.map((name) => cache.inserted[name]).join("");
    return <style data-emotion={`${cache.key} ${names.join(" ")}`} dangerouslySetInnerHTML={{ __html: styles }} />;
  });

  return <CacheProvider value={cache}>{children}</CacheProvider>;
}
