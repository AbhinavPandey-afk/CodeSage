import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Repository } from "../api/types";

const TERMINAL_STATUSES = new Set(["ready", "failed"]);
const POLL_INTERVAL_MS = 2000;

/** Polls a repository's status until it reaches a terminal state (ready/failed). */
export function useRepositoryPolling(repoId: string | null) {
  const [repository, setRepository] = useState<Repository | null>(null);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (!repoId) return;

    const poll = async () => {
      const repo = await api.getRepository(repoId);
      setRepository(repo);
      if (TERMINAL_STATUSES.has(repo.status) && intervalRef.current) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };

    poll();
    intervalRef.current = window.setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current);
    };
  }, [repoId]);

  return repository;
}
