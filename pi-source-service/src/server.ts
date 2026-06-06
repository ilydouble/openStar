import { mkdirSync } from "fs";
import express, { type Request, type Response } from "express";
import { Agent, type AgentMessage } from "@earendil-works/pi-agent-core";
import { createReadOnlyTools } from "@earendil-works/pi-coding-agent";
import {
	getModel,
	getEnvApiKey,
	registerBuiltInApiProviders,
	streamSimple,
	type KnownProvider,
} from "@earendil-works/pi-ai";

registerBuiltInApiProviders();

const PORT = parseInt(process.env.PI_SERVICE_PORT ?? "11002");
const PROVIDER = (process.env.PI_PROVIDER ?? "anthropic") as KnownProvider;
const MODEL_ID = process.env.PI_MODEL_ID ?? "claude-sonnet-4-6";
// PI_BASE_URL: ZAI/OpenAI-compatible providers üçün URL override.
// Claude, GPT, Gemini kimi provayderlərdə ignore edilir.
const ZAI_PROVIDERS = new Set(["zai", "zai-coding-cn"]);
const PI_BASE_URL = ZAI_PROVIDERS.has(PROVIDER) ? (process.env.PI_BASE_URL ?? null) : null;
const MAX_TOKENS = parseInt(process.env.PI_MAX_TOKENS ?? "8192");
const WORKSPACE = process.env.PI_WORKSPACE ?? "/workspace";
// Max concurrent sessions — evicts oldest when limit is reached
const MAX_SESSIONS = parseInt(process.env.PI_MAX_SESSIONS ?? "500");
// Session idle TTL in ms — sessions unused longer than this are garbage collected
const SESSION_TTL_MS = parseInt(process.env.PI_SESSION_TTL_MS ?? String(30 * 60 * 1000));

// Ensure workspace directory exists at startup
mkdirSync(WORKSPACE, { recursive: true });

// Session store: session_id → { agent, lastUsed }
interface SessionEntry {
	agent: Agent;
	lastUsed: number;
}
const sessions = new Map<string, SessionEntry>();

// Periodic GC: remove sessions idle longer than SESSION_TTL_MS
setInterval(() => {
	const now = Date.now();
	let removed = 0;
	for (const [id, entry] of sessions) {
		if (now - entry.lastUsed > SESSION_TTL_MS) {
			entry.agent.abort();
			sessions.delete(id);
			removed++;
		}
	}
	if (removed > 0) {
		console.log(`[pi-src] gc: removed ${removed} idle sessions, active=${sessions.size}`);
	}
}, 5 * 60 * 1000);

const app = express();
app.use(express.json({ limit: "10mb" }));

app.get("/health", (_req: Request, res: Response) => {
	res.json({ status: "ok", provider: PROVIDER, model: MODEL_ID, sessions: sessions.size });
});

interface ChatRequest {
	session_id: string;
	message: string;
	system_prompt?: string;
	history?: Array<{ role: "user" | "assistant"; content: string }>;
}

app.post("/v1/chat", async (req: Request, res: Response) => {
	const { session_id, message, system_prompt, history } = req.body as ChatRequest;
	console.log(`[pi-src] chat session=${session_id} msg=${String(message).slice(0, 80)}`);

	if (!session_id || !message) {
		res.status(400).json({ error: "session_id and message are required" });
		return;
	}

	res.setHeader("Content-Type", "text/event-stream");
	res.setHeader("Cache-Control", "no-cache");
	res.setHeader("Connection", "keep-alive");
	res.flushHeaders();

	const sendEvent = (data: object) => {
		if (!res.writableEnded) {
			res.write(`data: ${JSON.stringify(data)}\n\n`);
		}
	};

	let entry = sessions.get(session_id);

	if (!entry) {
		// Evict oldest session when at capacity
		if (sessions.size >= MAX_SESSIONS) {
			let oldestId = "";
			let oldestTime = Infinity;
			for (const [id, e] of sessions) {
				if (e.lastUsed < oldestTime) {
					oldestTime = e.lastUsed;
					oldestId = id;
				}
			}
			if (oldestId) {
				sessions.get(oldestId)?.agent.abort();
				sessions.delete(oldestId);
				console.log(`[pi-src] evicted oldest session=${oldestId}, active=${sessions.size}`);
			}
		}

		const apiKey = process.env.PI_API_KEY ?? getEnvApiKey(PROVIDER) ?? undefined;
		const modelBase = getModel(PROVIDER, MODEL_ID as never);
		const model = PI_BASE_URL ? { ...modelBase, baseUrl: PI_BASE_URL } : modelBase;

		const agent = new Agent({
			initialState: {
				systemPrompt: system_prompt ?? "",
				model,
				thinkingLevel: "off",
				tools: createReadOnlyTools(WORKSPACE),
			},
			streamFn: (m, context, opts) =>
				streamSimple(m, context, {
					...opts,
					apiKey,
					maxTokens: MAX_TOKENS,
				}),
		});

		if (history?.length) {
			agent.state.messages = history.flatMap<AgentMessage>((msg) => {
				if (msg.role === "user") {
					return [{ role: "user", content: [{ type: "text", text: msg.content }], timestamp: Date.now() }];
				}
				return [
					{
						role: "assistant",
						content: [{ type: "text", text: msg.content }],
						api: "anthropic-messages",
						provider: PROVIDER,
						model: MODEL_ID,
						usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
						stopReason: "end_turn",
						timestamp: Date.now(),
					},
				];
			});
		}

		entry = { agent, lastUsed: Date.now() };
		sessions.set(session_id, entry);
	} else {
		entry.lastUsed = Date.now();
	}

	const { agent } = entry;

	const unsubscribe = agent.subscribe((event) => {
		switch (event.type) {
			case "message_update":
				if (event.assistantMessageEvent.type === "text_delta") {
					sendEvent({ type: "token", text: event.assistantMessageEvent.delta });
				}
				break;
			case "tool_execution_start":
				sendEvent({ type: "tool_start", name: event.toolName, args: event.args });
				break;
			case "tool_execution_end":
				sendEvent({ type: "tool_end", name: event.toolName, is_error: event.isError });
				break;
			case "agent_end":
				unsubscribe();
				sendEvent({ type: "done" });
				if (!res.writableEnded) res.end();
				break;
		}
	});

	try {
		await agent.prompt(message);
	} catch (err: unknown) {
		unsubscribe();
		const msg = err instanceof Error ? err.message : String(err);
		sendEvent({ type: "error", message: msg });
		if (!res.writableEnded) res.end();
	}
});

app.delete("/v1/session/:id", (req: Request, res: Response) => {
	const entry = sessions.get(req.params.id);
	if (entry) {
		entry.agent.abort();
		sessions.delete(req.params.id);
	}
	res.json({ ok: true });
});

// Client disconnect → abort the running agent
app.use((req: Request, res: Response) => {
	res.on("close", () => {
		const sessionId = (req.body as ChatRequest | undefined)?.session_id;
		if (sessionId) {
			sessions.get(sessionId)?.agent.abort();
		}
	});
});

app.listen(PORT, () => {
	console.log(`pi-source-service running on port ${PORT} (${PROVIDER}/${MODEL_ID})`);
	console.log(`[pi-src] workspace=${WORKSPACE} max_sessions=${MAX_SESSIONS} ttl=${SESSION_TTL_MS}ms`);
});
