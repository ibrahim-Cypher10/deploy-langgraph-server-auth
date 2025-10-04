import { useCallback, useEffect, useMemo, useState } from "react";
import { Client, type Assistant, type Message } from "@langchain/langgraph-sdk";
import { useStream } from "@langchain/langgraph-sdk/react";
import clsx from "clsx";

type ConnectionState = {
  apiUrl: string;
  apiKey: string;
};

type ActiveConfig = ConnectionState & {
  applied: boolean;
};

const DEFAULT_API_URL = "http://localhost:8000";

function renderMessageContent(message: Message): string {
  if (typeof message.content === "string") {
    return message.content;
  }

  return message.content
    .map((part) => {
      if (part.type === "text") {
        return part.text;
      }

      if (part.type === "image_url") {
        const value = typeof part.image_url === "string" ? part.image_url : part.image_url.url;
        return `[image: ${value}]`;
      }

      return JSON.stringify(part);
    })
    .join("\n");
}

type StreamTesterProps = {
  client: Client;
  assistantId: string;
  threadId: string | null;
  onThreadIdChange: (threadId: string | null) => void;
};

function StreamTester({ client, assistantId, threadId, onThreadIdChange }: StreamTesterProps) {
  const [messageInput, setMessageInput] = useState("Briefly introduce yourself and offer to help me.");
  const [configurableInput, setConfigurableInput] = useState("{}");
  const [formError, setFormError] = useState<string | null>(null);

  const stream = useStream({
    client,
    assistantId,
    threadId: threadId ?? undefined,
    onThreadId: (id) => onThreadIdChange(id),
    fetchStateHistory: false,
  });

  useEffect(() => {
    setFormError(null);
    setMessageInput("Briefly introduce yourself and offer to help me.");
  }, [assistantId]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    const trimmed = messageInput.trim();
    if (!trimmed) {
      setFormError("Enter a message before streaming.");
      return;
    }

    let configurable: Record<string, unknown> | undefined;
    const configText = configurableInput.trim();
    if (configText.length > 0 && configText !== "{}") {
      try {
        configurable = JSON.parse(configText);
      } catch (error) {
        setFormError("Configurable values must be valid JSON.");
        return;
      }
    }

    try {
      await stream.submit(
        { messages: [trimmed] },
        configurable
          ? {
              config: {
                configurable,
              },
            }
          : undefined,
      );
      setMessageInput("");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setFormError(message);
    }
  };

  const handleResetThread = () => {
    onThreadIdChange(null);
  };

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-slate-800 bg-slate-900/70 p-4 shadow">
        <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">Stream playground</h2>
            <p className="text-sm text-slate-400">
              Assistant <span className="font-mono text-slate-200">{assistantId}</span> · Thread
              <span className="font-mono text-slate-200"> {threadId ?? "(auto)"}</span>
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-slate-300">
            {threadId && (
              <button
                type="button"
                onClick={handleResetThread}
                className="rounded border border-slate-700 bg-slate-800 px-3 py-1 font-medium text-slate-200 hover:bg-slate-700"
              >
                New thread
              </button>
            )}
            <span
              className={clsx(
                "rounded-full px-2 py-1 text-xs font-semibold",
                stream.isLoading ? "bg-emerald-500/20 text-emerald-300" : "bg-slate-700 text-slate-200",
              )}
            >
              {stream.isLoading ? "Streaming" : "Idle"}
            </span>
          </div>
        </header>

        <form onSubmit={handleSubmit} className="space-y-3">
          <label className="block text-sm font-medium text-slate-300">
            Message
            <textarea
              value={messageInput}
              onChange={(event) => setMessageInput(event.target.value)}
              rows={3}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950/80 p-3 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
              placeholder="Ask the Rocket assistant something"
            />
          </label>

          <label className="block text-sm font-medium text-slate-300">
            Configurable overrides (JSON)
            <textarea
              value={configurableInput}
              onChange={(event) => setConfigurableInput(event.target.value)}
              rows={2}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950/80 p-2 text-xs text-slate-200 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
              placeholder='e.g. {"thread_id": "..."}'
            />
          </label>

          {formError && (
            <p className="rounded border border-rose-500/40 bg-rose-900/40 p-2 text-sm text-rose-200">{formError}</p>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={stream.isLoading}
              className="rounded bg-emerald-500 px-4 py-2 font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-emerald-600/50"
            >
              {stream.isLoading ? "Streaming…" : "Send"}
            </button>
            <button
              type="button"
              onClick={() => void stream.stop()}
              className="rounded border border-slate-700 bg-slate-800 px-4 py-2 font-semibold text-slate-200 hover:bg-slate-700"
            >
              Stop
            </button>
          </div>
        </form>
      </section>

      <section className="space-y-3">
        <header className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-100">Streamed messages</h3>
          <div className="text-xs text-slate-400">
            {stream.error
              ? `Error: ${String(stream.error)}`
              : stream.messages.length
                ? `${stream.messages.length} message${stream.messages.length === 1 ? "" : "s"}`
                : "Waiting for output"}
          </div>
        </header>

        <div className="space-y-2">
          {stream.messages.map((message, index) => (
            <article
              key={message.id ?? `${message.type}-${index}`}
              className={clsx(
                "rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-sm shadow",
                message.type === "human"
                  ? "border-emerald-600/40"
                  : message.type === "ai"
                    ? "border-sky-500/40"
                    : "border-slate-700",
              )}
            >
              <header className="mb-1 flex items-center justify-between text-xs uppercase tracking-wide text-slate-400">
                <span>{message.type === "human" ? "You" : message.type === "ai" ? "Rocket" : message.type}</span>
                <span className="font-mono text-[10px] text-slate-500">{message.id ?? `#${index}`}</span>
              </header>
              <p className="whitespace-pre-wrap text-slate-200">{renderMessageContent(message)}</p>
            </article>
          ))}

          {!stream.messages.length && (
            <p className="rounded border border-dashed border-slate-700 bg-slate-900/40 p-4 text-center text-sm text-slate-400">
              Send a prompt to see streaming updates.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

function App() {
  const [connection, setConnection] = useState<ConnectionState>({
    apiUrl: DEFAULT_API_URL,
    apiKey: "",
  });
  const [activeConfig, setActiveConfig] = useState<ActiveConfig>({
    apiUrl: DEFAULT_API_URL,
    apiKey: "",
    applied: false,
  });
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [assistantsError, setAssistantsError] = useState<string | null>(null);
  const [isLoadingAssistants, setIsLoadingAssistants] = useState(false);
  const [selectedAssistantId, setSelectedAssistantId] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);

  const client = useMemo(() => {
    return new Client({
      apiUrl: activeConfig.apiUrl || undefined,
      apiKey: activeConfig.apiKey || undefined,
    });
  }, [activeConfig.apiKey, activeConfig.apiUrl]);

  const applyConnection = () => {
    setActiveConfig({ ...connection, applied: true });
    setThreadId(null);
    setAssistants([]);
    setSelectedAssistantId(null);
    setAssistantsError(null);
  };

  const loadAssistants = useCallback(async () => {
    setIsLoadingAssistants(true);
    setAssistantsError(null);
    try {
      const results = await client.assistants.search({ limit: 20, offset: 0 });
      setAssistants(results);
      setSelectedAssistantId((current) => current ?? results[0]?.assistant_id ?? null);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setAssistantsError(message);
    } finally {
      setIsLoadingAssistants(false);
    }
  }, [client]);

  useEffect(() => {
    if (activeConfig.applied) {
      void loadAssistants();
    }
  }, [activeConfig.applied, loadAssistants]);

  const showStreamTester = activeConfig.applied && selectedAssistantId;

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-8 px-4 py-10">
      <header className="space-y-2 text-center">
        <h1 className="text-3xl font-bold text-slate-100">LangGraph Proxy Stream Tester</h1>
        <p className="text-sm text-slate-400">
          Connect to your authenticated proxy and verify the <code className="rounded bg-slate-800 px-1">useStream</code> hook works end-to-end.
        </p>
      </header>

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 shadow">
        <h2 className="text-lg font-semibold text-slate-100">1. Connect to the proxy</h2>
        <p className="mb-4 text-sm text-slate-400">
          Provide the base URL of your LangGraph proxy and (if required) an API key.
        </p>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            applyConnection();
          }}
          className="grid gap-4 md:grid-cols-2"
        >
          <label className="text-sm font-medium text-slate-300">
            Proxy URL
            <input
              type="url"
              required
              value={connection.apiUrl}
              onChange={(event) => setConnection((prev) => ({ ...prev, apiUrl: event.target.value }))}
              placeholder="http://localhost:8000"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950/80 p-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
            />
          </label>

          <label className="text-sm font-medium text-slate-300">
            API key
            <input
              type="text"
              value={connection.apiKey}
              onChange={(event) => setConnection((prev) => ({ ...prev, apiKey: event.target.value }))}
              placeholder="Optional"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950/80 p-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
            />
          </label>

          <div className="md:col-span-2 flex flex-wrap items-center gap-3">
            <button
              type="submit"
              className="rounded bg-emerald-500 px-4 py-2 font-semibold text-emerald-950 transition hover:bg-emerald-400"
            >
              {activeConfig.applied ? "Reconnect" : "Connect"}
            </button>
            {activeConfig.applied && <span className="text-xs text-emerald-300">Connected to {activeConfig.apiUrl}</span>}
          </div>
        </form>
      </section>

      {activeConfig.applied && (
        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-6 shadow">
          <h2 className="text-lg font-semibold text-slate-100">2. Choose an assistant</h2>
          <p className="mb-4 text-sm text-slate-400">
            We will automatically list assistants from the LangGraph server behind your proxy. Pick one to start streaming.
          </p>

          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void loadAssistants()}
                className="rounded border border-slate-700 bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-700"
              >
                {isLoadingAssistants ? "Refreshing…" : "Refresh assistants"}
              </button>
              {assistantsError && <span className="text-sm text-rose-300">{assistantsError}</span>}
              {!assistants.length && !assistantsError && !isLoadingAssistants && (
                <span className="text-xs text-slate-400">No assistants returned yet.</span>
              )}
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              {assistants.map((assistant) => (
                <label
                  key={assistant.assistant_id}
                  className={clsx(
                    "flex cursor-pointer flex-col rounded border p-3 transition",
                    selectedAssistantId === assistant.assistant_id
                      ? "border-emerald-500/60 bg-emerald-500/10"
                      : "border-slate-800 bg-slate-900/70 hover:border-emerald-500/40",
                  )}
                >
                  <input
                    type="radio"
                    name="assistant"
                    value={assistant.assistant_id}
                    checked={selectedAssistantId === assistant.assistant_id}
                    onChange={() => {
                      setSelectedAssistantId(assistant.assistant_id);
                      setThreadId(null);
                    }}
                    className="sr-only"
                  />
                  <span className="text-sm font-semibold text-slate-100">{assistant.name ?? assistant.assistant_id}</span>
                  <span className="text-xs text-slate-400">{assistant.assistant_id}</span>
                  {assistant.description && <span className="mt-1 text-xs text-slate-400">{assistant.description}</span>}
                </label>
              ))}
            </div>
          </div>
        </section>
      )}

      {showStreamTester && selectedAssistantId && (
        <StreamTester client={client} assistantId={selectedAssistantId} threadId={threadId} onThreadIdChange={setThreadId} />
      )}
    </main>
  );
}

export default App;
