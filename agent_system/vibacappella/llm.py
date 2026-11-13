"""Small OpenAI-compatible Chat Completions transport, with a text-JSON fallback.

No vendor SDK, provider-specific URL, credential persistence or audio uploads.
"""
import json
import time
import urllib.error
import urllib.request

from .config import endpoint_config, provider_values


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an API credential to a redirected host.
        return None


class Client:
    def __init__(self, cfg, store, opener=None):
        self.cfg, self.store = cfg["llm"], store
        self.url, self.model, self.key = endpoint_config(cfg)
        store.secrets = tuple(set(store.secrets+(self.key,)))
        self.team_id = provider_values(cfg).get(self.cfg.get("team_id_env", ""), "")
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def complete(self, messages, schemas):
        c = self.cfg
        payload = {"model": self.model, "messages": messages,
                   c["max_tokens_field"]: c["max_output_tokens"]}
        if c.get("include_usage", False):
            payload["usage"] = {"include": True}
        if c["tool_mode"] == "native":
            payload.update(tools=schemas, tool_choice="auto")
        else:
            # Works with models that can produce JSON but lack native tool calling.
            payload["messages"] = self.json_messages(messages, schemas)
        encoded = json.dumps(payload, ensure_ascii=False).encode()
        estimate = (len(encoded)+2)//3 + c["max_output_tokens"]
        for attempt in range(c["retries"]+1):
            budget = self.store.read("budget.json") if self.store.path("budget.json").exists() else {"calls": 0, "tokens": 0, "estimated": False}
            if budget["calls"] >= c["max_calls"] or budget["tokens"]+estimate > c["max_total_tokens"]:
                raise RuntimeError("LLM budget exhausted; checkpoints are saved. Increase the explicit budget before resuming.")
            # Reserve before the request so a crash/failure does not reset usage.
            budget.update(calls=budget["calls"]+1, tokens=budget["tokens"]+estimate)
            self.store.write("budget.json", budget)
            request = urllib.request.Request(self.url, encoded, headers={
                "Content-Type": "application/json", c["auth_header"]: c["auth_prefix"]+self.key})
            if self.team_id:
                request.add_header("X-Prime-Team-ID", self.team_id)
            try:
                with self.opener.open(request, timeout=c["timeout_seconds"]) as response:
                    raw = response.read(4*1024*1024+1)
                    cost_usd = getattr(response, "headers", {}).get("x-parley-v1-cost")
                if len(raw) > 4*1024*1024:
                    raise RuntimeError("LLM response exceeded 4 MiB")
                result = json.loads(raw)
                usage = result.get("usage", {}).get("total_tokens")
                if isinstance(usage, int) and usage >= 0:
                    budget["tokens"] += usage-estimate
                else:
                    budget["estimated"] = True
                self.store.write("budget.json", budget)
                choices = result.get("choices", [])
                if not choices or choices[0].get("finish_reason") in ("length", "content_filter"):
                    raise RuntimeError("LLM returned an empty, truncated or filtered response; use a smaller window or larger output limit")
                message = choices[0]["message"]
                if c["tool_mode"] == "json":
                    text = message.get("content") or ""
                    if text.startswith("```"):
                        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
                    action = json.loads(text)
                    message = {"role": "assistant", "content": None, "tool_calls": [{
                        "id": f"json_{budget['calls']}", "type": "function",
                        "function": {"name": action["tool"], "arguments": json.dumps(action["arguments"])}}]}
                else:
                    message = {k: message[k] for k in ("role", "content", "tool_calls") if k in message}
                    calls = message.get("tool_calls", [])
                    if not isinstance(calls, list) or len(calls) > 64:
                        raise RuntimeError("Invalid or excessive tool calls from provider")
                    seen = set()
                    for call in calls:
                        if (not isinstance(call, dict) or not isinstance(call.get("id"), str) or
                            call["id"] in seen or not isinstance(call.get("function"), dict) or
                            not isinstance(call["function"].get("name"), str) or
                            not isinstance(call["function"].get("arguments"), str)):
                            raise RuntimeError("Malformed tool call from provider; no tools executed")
                        seen.add(call["id"])
                message["role"] = "assistant"
                self.store.log("llm_response", model=self.model, usage=result.get("usage"), call=budget["calls"], cost_usd=cost_usd)
                return self.store.redact(message)
            except urllib.error.HTTPError as exc:
                code = exc.code
                exc.close()
                self.store.log("llm_http_error", status=code, attempt=attempt+1)
                if code not in (429, 500, 502, 503, 504) or attempt == c["retries"]:
                    raise RuntimeError(f"LLM HTTP {code}; check endpoint, model and account configuration (response body omitted)") from None
                time.sleep(min(5, 2**attempt))
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == c["retries"]:
                    raise RuntimeError(f"LLM network failure: {type(exc).__name__}; run is resumable") from None
                time.sleep(min(5, 2**attempt))
        raise RuntimeError("LLM request failed")

    @staticmethod
    def json_messages(messages, schemas):
        out = [{"role": "system", "content":
                "Return exactly one JSON object: {\"tool\": <name>, \"arguments\": {...}}. "
                "No prose. Available tools: "+json.dumps(schemas, ensure_ascii=False)}]
        for msg in messages:
            if msg["role"] == "tool":
                out.append({"role": "user", "content": "Tool result: "+msg["content"]})
            elif msg.get("tool_calls"):
                out.append({"role": "assistant", "content": json.dumps(msg["tool_calls"], ensure_ascii=False)})
            else:
                out.append(msg)
        return out
