import express, { type Request, type Response } from "express";
import { Agent, type AgentMessage } from "@earendil-works/pi-agent-core";
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
const MAX_TOKENS = parseInt(process.env.PI_MAX_TOKENS ?? "8192");

// Session store: session_id → Agent
const sessions = new Map<string, Agent>();

const app = express();
app.use(express.json({ limit: "10mb" }));

app.get("/health", (_req: Request, res: Response) => {
	res.json({ status: "ok", provider: PROVIDER, model: MODEL_ID });
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

	let agent = sessions.get(session_id);

	if (!agent) {
		const apiKey = process.env.PI_API_KEY ?? getEnvApiKey(PROVIDER) ?? undefined;
		const model = getModel(PROVIDER, MODEL_ID as never);

		agent = new Agent({
			initialState: {
				systemPrompt: system_prompt ?? "",
				model,
				thinkingLevel: "off",
				tools: [],
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

		sessions.set(session_id, agent);
	}

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
	const agent = sessions.get(req.params.id);
	if (agent) {
		agent.abort();
		sessions.delete(req.params.id);
	}
	res.json({ ok: true });
});

// Client disconnect → abort the running agent
app.use((req: Request, res: Response) => {
	res.on("close", () => {
		const sessionId = (req.body as ChatRequest | undefined)?.session_id;
		if (sessionId) {
			sessions.get(sessionId)?.abort();
		}
	});
});

app.listen(PORT, () => {
	console.log(`pi-source-service running on port ${PORT} (${PROVIDER}/${MODEL_ID})`);
});
