/**
 * Phase 23 / B3 — Presets & Queue.
 *
 * Pure client-side scheduler: jobs are captured as parameter snapshots and
 * consumed in serial order against the Lab's runner callback. No backend
 * job system; refreshing the page preserves the queue (for resume after
 * accidental navigation) but does not auto-start a new run.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// Phase 25 / D3 — provider + model override are accepted on every job kind.
// Both are optional and when absent the server picks the default provider.
type EngineOverrides = {
  engine_provider?: string;
  engine_model?: string;
};

export type QuickCopyJobPayload = EngineOverrides & {
  kind: 'quick_copy';
  project_id: string;
  region_id: string;
  platform_id: string;
  angle_id: string;
  engine: string;
  output_mode: string;
  compliance_suggest: boolean;
  quantity: number;
  tones: string[];
  locales: string[];
  region_ids: string[];
};

export type FullSopJobPayload = EngineOverrides & {
  kind: 'full_sop';
  project_id: string;
  region_id: string;
  platform_id: string;
  angle_id: string;
  engine: string;
  output_mode: string;
  compliance_suggest: boolean;
  mode: 'auto' | 'draft' | 'director';
};

export type RefreshCopyJobPayload = EngineOverrides & {
  kind: 'refresh_copy';
  project_id: string;
  base_script_id: string;
  engine: string;
  output_mode: string;
  compliance_suggest: boolean;
  quantity: number;
  tones: string[];
  locales: string[];
};

export type QueueJobPayload =
  | QuickCopyJobPayload
  | FullSopJobPayload
  | RefreshCopyJobPayload;

export type QueueJobStatus = 'pending' | 'running' | 'ok' | 'failed' | 'skipped';

export type QueueJob = {
  id: string;
  label: string;
  createdAt: number;
  status: QueueJobStatus;
  payload: QueueJobPayload;
  scriptId?: string;
  error?: string;
  startedAt?: number;
  finishedAt?: number;
};

export type PresetSlot = {
  id: string;
  name: string;
  pinned?: boolean;
  createdAt: number;
  payload: QueueJobPayload;
};

const QUEUE_KEY = 'sop_queue';
const PRESETS_KEY = 'sop_presets';
const MAX_PRESETS = 10;

const safeRead = <T,>(key: string, fallback: T): T => {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
};

const safeWrite = (key: string, value: unknown) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore quota / private mode failures
  }
};

const shortId = () => Math.random().toString(36).slice(2, 10);

export type QueueRunner = (
  payload: QueueJobPayload,
) => Promise<{ scriptId?: string; [key: string]: unknown } | undefined>;

export function useLabQueue(runner: QueueRunner) {
  const [queue, setQueue] = useState<QueueJob[]>(() => safeRead<QueueJob[]>(QUEUE_KEY, []));
  const [presets, setPresets] = useState<PresetSlot[]>(() =>
    safeRead<PresetSlot[]>(PRESETS_KEY, []),
  );
  const [isRunning, setIsRunning] = useState(false);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const cancelRef = useRef(false);

  // Rolling average run time (ms) across completed jobs; seeds the ETA label.
  const [avgJobMs, setAvgJobMs] = useState<number>(() => {
    const raw = Number(localStorage.getItem('sop_queue_avg_ms') || '45000');
    return Number.isFinite(raw) && raw > 0 ? raw : 45000;
  });

  useEffect(() => safeWrite(QUEUE_KEY, queue), [queue]);
  useEffect(() => safeWrite(PRESETS_KEY, presets), [presets]);
  useEffect(() => {
    try {
      localStorage.setItem('sop_queue_avg_ms', String(Math.round(avgJobMs)));
    } catch {
      // ignore
    }
  }, [avgJobMs]);

  const pendingCount = useMemo(
    () => queue.filter((j) => j.status === 'pending' || j.status === 'running').length,
    [queue],
  );
  const runnerIndex = useMemo(() => {
    if (!currentId) return -1;
    return queue.findIndex((j) => j.id === currentId);
  }, [queue, currentId]);
  const etaMs = useMemo(() => pendingCount * Math.max(4000, avgJobMs), [pendingCount, avgJobMs]);

  const addJob = useCallback((payload: QueueJobPayload, label?: string) => {
    const job: QueueJob = {
      id: shortId(),
      label: label || describePayload(payload),
      createdAt: Date.now(),
      status: 'pending',
      payload,
    };
    setQueue((prev) => [...prev, job]);
    return job.id;
  }, []);

  const removeJob = useCallback((id: string) => {
    setQueue((prev) => prev.filter((j) => j.id !== id));
  }, []);

  const clearQueue = useCallback((onlyFinished = false) => {
    setQueue((prev) =>
      onlyFinished
        ? prev.filter((j) => j.status === 'pending' || j.status === 'running')
        : [],
    );
  }, []);

  const cancelRun = useCallback(() => {
    cancelRef.current = true;
  }, []);

  const runAll = useCallback(async () => {
    if (isRunning) return;
    setIsRunning(true);
    cancelRef.current = false;
    try {
      // Take a snapshot of pending jobs; we walk the snapshot to avoid races.
      const snapshotIds = queue.filter((j) => j.status === 'pending').map((j) => j.id);
      for (const id of snapshotIds) {
        if (cancelRef.current) {
          break;
        }
        setCurrentId(id);
        const startedAt = Date.now();
        setQueue((prev) =>
          prev.map((j) => (j.id === id ? { ...j, status: 'running', startedAt } : j)),
        );
        const jobFromQueue = await new Promise<QueueJob | undefined>((resolve) => {
          setQueue((prev) => {
            const found = prev.find((j) => j.id === id);
            resolve(found);
            return prev;
          });
        });
        if (!jobFromQueue) continue;
        try {
          const result = await runner(jobFromQueue.payload);
          const finishedAt = Date.now();
          const dur = Math.max(1000, finishedAt - startedAt);
          setAvgJobMs((prev) => (prev <= 0 ? dur : Math.round(prev * 0.7 + dur * 0.3)));
          setQueue((prev) =>
            prev.map((j) =>
              j.id === id
                ? {
                    ...j,
                    status: 'ok',
                    finishedAt,
                    scriptId:
                      (result && typeof (result as any).script_id === 'string'
                        ? (result as any).script_id
                        : (result as any)?.scriptId) || undefined,
                  }
                : j,
            ),
          );
        } catch (err: any) {
          const finishedAt = Date.now();
          setQueue((prev) =>
            prev.map((j) =>
              j.id === id
                ? {
                    ...j,
                    status: 'failed',
                    finishedAt,
                    error: err?.message || String(err),
                  }
                : j,
            ),
          );
        }
      }
    } finally {
      setCurrentId(null);
      setIsRunning(false);
      cancelRef.current = false;
    }
  }, [isRunning, queue, runner]);

  // Presets -----------------------------------------------------------------
  const savePreset = useCallback((name: string, payload: QueueJobPayload) => {
    setPresets((prev) => {
      const clean = (name || '').trim() || `Preset ${prev.length + 1}`;
      const slot: PresetSlot = {
        id: shortId(),
        name: clean,
        createdAt: Date.now(),
        payload,
      };
      const next = [slot, ...prev];
      if (next.length > MAX_PRESETS) next.length = MAX_PRESETS;
      return next;
    });
  }, []);

  const deletePreset = useCallback((id: string) => {
    setPresets((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const renamePreset = useCallback((id: string, name: string) => {
    setPresets((prev) => prev.map((p) => (p.id === id ? { ...p, name } : p)));
  }, []);

  const togglePinPreset = useCallback((id: string) => {
    setPresets((prev) => {
      const next = prev.map((p) => (p.id === id ? { ...p, pinned: !p.pinned } : p));
      next.sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)));
      return next;
    });
  }, []);

  return {
    queue,
    presets,
    isRunning,
    currentId,
    runnerIndex,
    pendingCount,
    etaMs,
    avgJobMs,
    addJob,
    removeJob,
    clearQueue,
    runAll,
    cancelRun,
    savePreset,
    deletePreset,
    renamePreset,
    togglePinPreset,
  };
}

function describePayload(p: QueueJobPayload): string {
  if (p.kind === 'full_sop') {
    return `SOP · ${p.region_id} · ${p.platform_id} · ${p.angle_id}`;
  }
  if (p.kind === 'quick_copy') {
    const rs = (p.region_ids || []).join(',') || p.region_id;
    return `Copy · ${rs} · q${p.quantity}`;
  }
  return `Refresh · ${p.base_script_id}`;
}
