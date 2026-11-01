"""Anthropic Messages API — Anthropic itself, and the services that speak it
(Kimi, GLM, … behind their own base URL)."""

import json
import urllib.parse
from urllib.request import Request as URLRequest

from .base import (Protocol, as_int, attach_target, key_headers, note_speed, parse_tool_args, served_speed_name,
                   turn_attachments)

API_VERSION = "2023-06-01"
# Fast mode is a beta: the flag rides with the ``speed`` parameter. Only some
# models take it (the Opus line); the listing says nothing about speed, so an
# unsupported one is refused upstream with the provider's own message.
FAST_MODE_BETA = "fast-mode-2026-02-01"
_CACHE = {"type": "ephemeral"}


def _image_part(media_type: str, data: str) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def is_anthropic_platform(base_url: str) -> bool:
    host = urllib.parse.urlparse(base_url or "").hostname or ""
    return host == "anthropic.com" or host.endswith(".anthropic.com")


def _mark_cached(message: dict) -> None:
    """Put a cache breakpoint on a turn's last content block (a string
    content becomes a one-block list first)."""
    content = message["content"]
    if isinstance(content, str):
        content = message["content"] = [{"type": "text", "text": content}]
    if content:
        content[-1] = {**content[-1], "cache_control": _CACHE}


def _with_breakpoints(body: dict) -> dict:
    """Anthropic's prompt cache is opt-in, at most four breakpoints: the
    last tool spec (the specs never change within a chat), the system
    prompt, and the last two user turns — the prefix up to the previous
    turn is what the next request shares, and a breakpoint one turn back
    keeps the lookup within reach when a reply's tool rounds add many
    blocks after it. Everything before a breakpoint is cached, so the
    conversation's stable head (the document context on the oldest user
    turn) is read from the cache from the second message on."""
    if body.get("tools"):
        body["tools"][-1] = {**body["tools"][-1], "cache_control": _CACHE}
    if body.get("system"):
        body["system"] = [{"type": "text", "text": body["system"], "cache_control": _CACHE}]
    user_turns = [m for m in body["messages"] if m["role"] == "user"]
    for message in user_turns[-2:]:
        _mark_cached(message)
    return body


def _user_content(message, pdf_b64s=(), images=()):
    """A user turn's content: its own PDFs, then the request's, its
    pictures, then the request's, and the text last — the plain text when
    there is nothing else."""
    files, pictures = turn_attachments(message, pdf_b64s, images)
    if not files and not pictures:
        return message["content"]
    return [
        *[{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}
          for data in files],
        *[_image_part(media_type, data) for media_type, data in pictures],
        {"type": "text", "text": message["content"]},
    ]


def _messages(messages, target=None, pdf_b64s=None, images=None) -> list:
    """Map the common turn list to Anthropic content blocks: tool results are
    tool_result blocks in a user turn (consecutive ones coalesced — they must
    directly follow the assistant's tool_use turn), tool calls become tool_use
    blocks after the assistant's text. The request's own attachments go on
    ``target``, the turn attach_target names."""
    out = []
    for m in messages:
        if m["role"] == "tool":
            block = {"type": "tool_result", "tool_use_id": m["call_id"], "content": m["content"]}
            if m.get("images"):
                block["content"] = [{"type": "text", "text": m["content"]}] + [
                    _image_part(media_type, data) for media_type, data in m["images"]]
            prev = out[-1] if out else None
            if (prev and prev["role"] == "user" and isinstance(prev["content"], list)
                    and prev["content"] and prev["content"][0].get("type") == "tool_result"):
                prev["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        elif m["role"] == "assistant" and m.get("tool_calls"):
            content = [{"type": "text", "text": m["content"]}] if (m.get("content") or "").strip() else []
            content += [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["arguments"]}
                        for c in m["tool_calls"]]
            out.append({"role": "assistant", "content": content})
        else:
            content = m["content"]
            if m["role"] == "user":
                content = _user_content(m, pdf_b64s, images) if m is target else _user_content(m)
            prev = out[-1] if out else None
            if (m["role"] == "user" and prev and prev["role"] == "user"
                    and isinstance(prev["content"], list)
                    and prev["content"] and prev["content"][0].get("type") == "tool_result"):
                # A tool-only assistant reply leaves its results as the last
                # user turn; fold the next real user message into it so roles
                # keep alternating. Attachment turns already carry block lists.
                prev["content"].extend(
                    content if isinstance(content, list)
                    else [{"type": "text", "text": content}])
            else:
                out.append({"role": m["role"], "content": content})
    return out


class Anthropic(Protocol):
    id = "anthropic"
    label = "Anthropic Messages API"
    key_placeholder = "sk-ant-…"
    key_url = "https://console.anthropic.com/settings/keys"
    speeds = {"fast": "fast"}  # no cheaper tier here; standard is the default

    def speed_tiers(self, conf):
        # Fast mode is Anthropic's own preview — a service speaking its API
        # behind another host has nothing to do with it.
        return super().speed_tiers(conf) if is_anthropic_platform(conf.get("base_url", "")) else []

    def request(self, conf, messages, system, model, pdf_b64s=None, effort="",
                max_tokens=8192, images=None, stream=False, tools=None, cache_key="", speed=""):
        target = attach_target(messages, pdf_b64s, images)
        body = {"model": model, "max_tokens": max_tokens, "system": system,
                "messages": _messages(messages, target, pdf_b64s, images)}
        if tools:
            body["tools"] = [t["hosted"] if t.get("hosted") else
                             {"name": t["name"], "description": t["description"],
                              "input_schema": t["parameters"]} for t in tools]
        if effort and effort != "none":
            # "none"/"minimal" are OpenAI's lowest levels; Anthropic's is
            # "low" ("none" means no preference here: the parameter goes).
            body["output_config"] = {"effort": "low" if effort == "minimal" else effort}
        if stream:
            body["stream"] = True
        platform = is_anthropic_platform(conf.get("base_url", ""))
        speed_value = self.speed_value(speed) if platform else ""
        if speed_value:
            body["speed"] = speed_value
        if platform:
            # Only Anthropic itself is known to take the markers; a service
            # speaking its API behind another host may reject the field.
            _with_breakpoints(body)
        headers = {
            **key_headers(conf["api_key"], "x-api-key", ""),
            "anthropic-version": API_VERSION,
            "Content-Type": "application/json",
        }
        if speed_value:
            headers["anthropic-beta"] = FAST_MODE_BETA
        return URLRequest(f"{conf['base_url']}/v1/messages", data=json.dumps(body).encode(), headers=headers)

    def hosted_web_search(self, conf):
        # Anthropic's server tool; a service speaking this API elsewhere
        # is not known to run it.
        if not is_anthropic_platform(conf.get("base_url", "")):
            return None
        return {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}

    def reply_text(self, data):
        text = "".join(item.get("text", "") for item in data.get("content", []) if item.get("type") == "text")
        if not text.strip():
            raise RuntimeError(f"empty response (stop_reason={data.get('stop_reason', 'unknown')})")
        return text

    def stop_reason(self, data):
        return str(data.get("stop_reason") or "")

    def usage(self, raw):
        # Cached and freshly written prompt parts are reported beside the
        # uncached ones; summed, the way OpenAI's prompt_tokens includes them.
        if not isinstance(raw, dict):
            return None
        cache_read = as_int(raw.get("cache_read_input_tokens"))
        cache_write = as_int(raw.get("cache_creation_input_tokens"))
        usage = {"input": as_int(raw.get("input_tokens")) + cache_read + cache_write,
                 "output": as_int(raw.get("output_tokens")),
                 "cache_read": cache_read, "cache_write": cache_write}
        return usage if (usage["input"] or usage["output"]) else None

    def served_speed(self, data):
        # ``usage.speed`` ("fast" / "standard") says which speed served the
        # turn once one was asked for; without a request it is absent.
        return served_speed_name((data.get("usage") or {}).get("speed"))

    def stream_event(self, event, state):
        kind = event.get("type")
        if kind == "message_start":
            # Input counts arrive up front; the output count comes with the
            # final message_delta (cumulative, so the last one wins). The
            # served speed rides on either usage object.
            raw_usage = (event.get("message") or {}).get("usage")
            state["usage"] = self.usage(raw_usage)
            if isinstance(raw_usage, dict):
                note_speed(state, raw_usage.get("speed"))
        elif kind == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                state["tool"] = {"id": block.get("id") or "", "name": block.get("name") or "", "json": ""}
            elif block.get("type") == "web_search_tool_result" and isinstance(block.get("content"), list):
                # The hosted search's results arrive whole with the block.
                found = [{"url": r["url"], "title": r.get("title") or ""} for r in block["content"]
                         if isinstance(r, dict) and r.get("type") == "web_search_result" and r.get("url")]
                if found:
                    yield ("web_sources", found)
        elif kind == "content_block_delta":
            delta = event.get("delta") or {}
            tool = state.get("tool")
            if delta.get("type") == "input_json_delta" and tool is not None:
                tool["json"] += delta.get("partial_json") or ""
                yield ("tool_delta", dict(tool))
            elif delta.get("type") == "citations_delta":
                cite = delta.get("citation") or {}
                if cite.get("url"):
                    yield ("web_sources", [{"url": cite["url"], "title": cite.get("title") or ""}])
            elif delta.get("text"):
                yield ("text", delta["text"])
        elif kind == "content_block_stop":
            tool = state.pop("tool", None)
            if tool is not None:
                yield ("tool", {"id": tool["id"], "name": tool["name"],
                                "arguments": parse_tool_args(tool["json"])})
        elif kind == "message_delta":
            state["stop"] = (event.get("delta") or {}).get("stop_reason") or state["stop"]
            if isinstance(event.get("usage"), dict):
                note_speed(state, event["usage"].get("speed"))
            delta_usage = self.usage(event.get("usage"))
            if delta_usage:
                usage = state["usage"] or {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
                usage["output"] = delta_usage["output"]
                if delta_usage["input"] and not usage["input"]:
                    usage.update(input=delta_usage["input"], cache_read=delta_usage["cache_read"],
                                 cache_write=delta_usage["cache_write"])
                state["usage"] = usage
        elif kind == "error":
            raise RuntimeError((event.get("error") or {}).get("message") or "stream error")

    def models_request(self, conf):
        return URLRequest(f"{conf['base_url']}/v1/models?limit=100", headers={
            **key_headers(conf["api_key"], "x-api-key", ""),
            "anthropic-version": API_VERSION,
            "Accept": "application/json",
            "User-Agent": "Gamma/model-catalog",
        })
