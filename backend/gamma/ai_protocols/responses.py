"""The Responses API — shared by OpenAI's platform /v1/responses (the wire
an OpenAI entry switches to for tool calls) and the ChatGPT subscription
backend (chatgpt.py)."""

import json
from urllib.request import Request as URLRequest

from .base import (OPENAI_PICTURE_TOKENS, TOOL_IMAGES_NOTE, Protocol, as_int, attach_target, key_headers, note_speed,
                   parse_tool_args, tool_image_turns, turn_attachments)


def _image_part(media_type: str, data: str) -> dict:
    return {"type": "input_image", "image_url": f"data:{media_type};base64,{data}"}


def _user_content(message, pdf_b64s=(), images=()) -> list:
    """A user turn's parts: its own PDFs, then the request's, its pictures,
    then the request's, and the text last."""
    files, pictures = turn_attachments(message, pdf_b64s, images)
    return [
        # The Codex backend answers a part without its filename with a
        # 400 ("Missing required parameter: 'input[0].content[0]'").
        *[{"type": "input_file", "filename": f"document-{index + 1}.pdf",
           "file_data": f"data:application/pdf;base64,{data}"}
          for index, data in enumerate(files)],
        *[_image_part(media_type, data) for media_type, data in pictures],
        {"type": "input_text", "text": message["content"]},
    ]


def responses_input(messages, pdf_b64s=None, images=None) -> list:
    """Map the common turn list to Responses API input items."""
    items = []
    image_turn = lambda imgs: {"type": "message", "role": "user", "content": [  # noqa: E731
        {"type": "input_text", "text": TOOL_IMAGES_NOTE},
        *[_image_part(media_type, data) for media_type, data in imgs]]}
    target = attach_target(messages, pdf_b64s, images)
    for message, is_image_turn in tool_image_turns(messages, image_turn):
        if is_image_turn:
            items.append(message)
        elif message["role"] == "tool":
            items.append({"type": "function_call_output", "call_id": message["call_id"],
                          "output": message["content"]})
        elif message["role"] == "assistant":
            if message.get("content") or not message.get("tool_calls"):
                content = [{"type": "output_text", "text": message["content"]}]
                items.append({"type": "message", "role": "assistant", "content": content})
            for call in message.get("tool_calls") or []:
                items.append({"type": "function_call", "call_id": call["id"],
                              "name": call["name"], "arguments": json.dumps(call["arguments"])})
        else:
            content = (_user_content(message, pdf_b64s, images) if message is target
                       else _user_content(message))
            items.append({"type": "message", "role": "user", "content": content})
    return items


def responses_tools(tools) -> list:
    # Responses API uses a flattened function-tool shape (no "function" nesting);
    # a hosted tool (the provider's web search) goes out as it is.
    return [t["hosted"] if t.get("hosted") else
            {"type": "function", "name": t["name"], "description": t["description"],
             "parameters": t["parameters"], "strict": False} for t in (tools or [])]


def _web_sources(item) -> list:
    """The pages a finished output item names: a web search call's sources
    (when the request asked for them) or a message's URL citations."""
    if item.get("type") == "web_search_call":
        found = ((item.get("action") or {}).get("sources")) or []
        return [{"url": s["url"], "title": s.get("title") or ""}
                for s in found if isinstance(s, dict) and s.get("url")]
    if item.get("type") == "message":
        return [{"url": a["url"], "title": a.get("title") or ""}
                for part in item.get("content") or [] if isinstance(part, dict)
                for a in part.get("annotations") or []
                if isinstance(a, dict) and a.get("type") == "url_citation" and a.get("url")]
    return []


def responses_body(messages, model, pdf_b64s, images, tools, effort, cache_key="",
                   service_tier="") -> dict:
    """The request body both Responses backends share. ``store`` stays off
    — the conversation is Gamma's to keep, not the provider's — and
    ``prompt_cache_key`` (one id per chat) is what makes the re-sent prefix
    a cache hit instead. ``service_tier`` is the wire value of the speed the
    call asked for (``Protocol.speed_value``), left out when there is none."""
    body = {
        "model": model,
        "input": responses_input(messages, pdf_b64s, images),
        "tools": responses_tools(tools),
        "tool_choice": "auto",
        # Batched calls (e.g. renaming a whole folder in one round) — a call
        # per round-trip would eat the tool-round budget one page at a time.
        "parallel_tool_calls": bool(tools),
        "store": False,
        "stream": True,
    }
    if effort:
        body["reasoning"] = {"effort": effort}
    if cache_key:
        body["prompt_cache_key"] = cache_key
    if service_tier:
        body["service_tier"] = service_tier
    return body


class ResponsesWire(Protocol):
    """The Responses stream and token report; a backend adds its request."""

    streams_only = True  # always SSE — read_reply joins the deltas
    picture_tokens = OPENAI_PICTURE_TOKENS
    # Both Responses backends route by service tier: "priority" is the fast
    # one (OpenAI's fast mode, Codex's own Fast), "flex" the cheaper, slower
    # one. The Codex backend's listing says which tiers each model has.
    speeds = {"flex": "flex", "fast": "priority"}

    def hosted_web_search(self, conf):
        return {"type": "web_search"}

    def usage(self, raw):
        if not isinstance(raw, dict):
            return None
        usage = {"input": as_int(raw.get("input_tokens")), "output": as_int(raw.get("output_tokens")),
                 "cache_read": as_int((raw.get("input_tokens_details") or {}).get("cached_tokens")),
                 "cache_write": 0}
        return usage if (usage["input"] or usage["output"]) else None

    def stream_event(self, event, state):
        kind = event.get("type") or ""
        items = state.setdefault("items", {})  # item id -> {id (call_id), name, json} being streamed
        if kind == "response.output_text.delta":
            if event.get("delta"):
                yield ("text", event["delta"])
        elif kind == "response.output_item.added":
            item = event.get("item") or {}
            if item.get("type") == "function_call":
                items[item.get("id") or ""] = {"id": item.get("call_id") or item.get("id") or "",
                                               "name": item.get("name") or "", "json": ""}
        elif kind == "response.function_call_arguments.delta":
            slot = items.get(event.get("item_id") or "")
            if slot is not None:
                slot["json"] += event.get("delta") or ""
                yield ("tool_delta", dict(slot))
        elif kind == "response.output_item.done":
            item = event.get("item") or {}
            if item.get("type") == "function_call":
                items.pop(item.get("id") or "", None)
                yield ("tool", {"id": item.get("call_id") or item.get("id") or "",
                                "name": item.get("name") or "",
                                "arguments": parse_tool_args(item.get("arguments"))})
            else:
                sources = _web_sources(item)
                if sources:
                    yield ("web_sources", sources)
        elif kind in ("response.completed", "response.incomplete"):
            # incomplete: the output cap or the window stopped it — the
            # counts still count, and the stop reason says it was cut off.
            response = event.get("response") or {}
            state["stop"] = response.get("status") or "completed"
            state["usage"] = self.usage(response.get("usage")) or state["usage"]
            # The finished response names the tier that served it (OpenAI's
            # "default" / "flex" / "priority"), whatever was asked for.
            note_speed(state, response.get("service_tier"))
        elif kind in ("response.failed", "error"):
            error = (event.get("response") or {}).get("error") or {} if kind == "response.failed" else event
            raise RuntimeError(error.get("message") or "stream error")


class OpenAIResponses(ResponsesWire):
    """OpenAI's platform /v1/responses, used instead of Chat Completions when
    a call carries function tools: reasoning models (gpt-5.x) reject tools +
    reasoning_effort on /v1/chat/completions, and OpenAI's guidance is the
    Responses API. Only against OpenAI itself — see OpenAIChat.wire."""

    id = "openai-responses"
    label = "OpenAI Responses API"
    entry = False

    def request(self, conf, messages, system, model, pdf_b64s=None, effort="",
                max_tokens=8192, images=None, stream=False, tools=None, cache_key="", speed=""):
        # No endpoint check here: OpenAIChat.wire only switches to this wire
        # against OpenAI itself.
        body = {**responses_body(messages, model, pdf_b64s, images, tools, effort, cache_key,
                                 self.speed_value(speed)),
                "max_output_tokens": max_tokens}
        if any((t.get("hosted") or {}).get("type") == "web_search" for t in tools or []):
            # The pages a search consulted, beside the ones the reply cites.
            body["include"] = ["web_search_call.action.sources"]
        if system:
            body["instructions"] = system
        return URLRequest(f"{conf['base_url']}/v1/responses", data=json.dumps(body).encode(), headers={
            **key_headers(conf["api_key"]),
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        })


OPENAI_RESPONSES = OpenAIResponses()
