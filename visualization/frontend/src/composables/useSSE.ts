import { ref, type Ref } from "vue";
import type { SSEEvent } from "../types/events";

/**
 * SSE 事件连接管理 composable。
 *
 * 建立到指定 URL 的 SSE 连接，监听所有自定义事件类型，
 * 将事件分发给通过 on() 注册的回调函数。
 */
export function useSSE() {
  const events = ref<SSEEvent[]>([]);
  const isConnected = ref(false);
  const error = ref<string | null>(null);

  let source: EventSource | null = null;
  const listeners = new Map<string, Set<(data: any) => void>>();

  /** 所有支持的事件类型 */
  const EVENT_TYPES = [
    "build:start",
    "build:iteration_start",
    "build:search_plan",
    "build:search_done",
    "build:entities_extracted",
    "build:merge_done",
    "build:convergence",
    "build:iteration_end",
    "build:extraction_failed",
    "build:prompts_start",
    "build:prompt_progress",
    "build:prompts_generated",
    "build:meta_generated",
    "build:complete",
    "build:error",
    "evolve:start",
    "evolve:tick_start",
    "evolve:assessment",
    "evolve:plan",
    "evolve:agent_action",
    "evolve:propagation",
    "evolve:narrative",
    "evolve:tick_end",
    "evolve:equilibrium",
    "evolve:complete",
    "evolve:error",
  ];

  function connect(url: string) {
    disconnect();
    error.value = null;

    source = new EventSource(url);

    source.onopen = () => {
      isConnected.value = true;
    };

    for (const type of EVENT_TYPES) {
      source.addEventListener(type, (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          const event: SSEEvent = {
            event: type,
            data,
            timestamp: new Date(),
          };
          events.value.push(event);
          listeners.get(type)?.forEach((cb) => cb(data));
        } catch (err) {
          console.error(`SSE 事件解析失败: ${type}`, err);
        }
      });
    }

    source.onerror = () => {
      isConnected.value = false;
      error.value = "SSE 连接断开";
      source?.close();
    };
  }

  function on(eventType: string, callback: (data: any) => void) {
    if (!listeners.has(eventType)) {
      listeners.set(eventType, new Set());
    }
    listeners.get(eventType)!.add(callback);
  }

  function off(eventType: string, callback: (data: any) => void) {
    listeners.get(eventType)?.delete(callback);
  }

  function disconnect() {
    source?.close();
    source = null;
    isConnected.value = false;
  }

  function clearEvents() {
    events.value = [];
  }

  function clearListeners() {
    listeners.clear();
  }

  return {
    events,
    isConnected,
    error,
    connect,
    on,
    off,
    disconnect,
    clearEvents,
    clearListeners,
  };
}
