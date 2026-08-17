"use client";

import { useEffect, useState } from "react";
import type { Screen } from "./types";

const SESSION_KEY = "dasibom-active-scan";
const RECOVERABLE_SCREENS: Screen[] = [
  "preview",
  "analysis",
  "action",
  "after-camera",
  "after-preview",
  "after-analysis",
];

export function useOnlineStatus() {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    const timer = window.setTimeout(update, 0);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  return online;
}

export function useScanRecovery(screen: Screen, nickname: string) {
  const [resumeScreen, setResumeScreen] = useState<Screen | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const saved = window.localStorage.getItem(SESSION_KEY);
      if (!saved) return;
      try {
        const parsed = JSON.parse(saved) as { screen: Screen; savedAt: number };
        const isFresh = Date.now() - parsed.savedAt < 30 * 60 * 1000;
        if (isFresh && RECOVERABLE_SCREENS.includes(parsed.screen)) {
          setResumeScreen(parsed.screen);
        } else {
          window.localStorage.removeItem(SESSION_KEY);
        }
      } catch {
        window.localStorage.removeItem(SESSION_KEY);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (RECOVERABLE_SCREENS.includes(screen)) {
      window.localStorage.setItem(
        SESSION_KEY,
        JSON.stringify({ screen, nickname, savedAt: Date.now() }),
      );
    }
    if (screen === "reward") {
      window.localStorage.removeItem(SESSION_KEY);
      const timer = window.setTimeout(() => setResumeScreen(null), 0);
      return () => window.clearTimeout(timer);
    }
  }, [nickname, screen]);

  const clear = () => {
    window.localStorage.removeItem(SESSION_KEY);
    setResumeScreen(null);
  };

  return { resumeScreen, clear };
}

export function useServiceWorker() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const register = () => void navigator.serviceWorker.register("/sw.js");
    window.addEventListener("load", register, { once: true });
    return () => window.removeEventListener("load", register);
  }, []);
}
