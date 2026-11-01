"""OpenAI Chat Completions — OpenAI itself and every compatible server
(DeepSeek, Kimi, Qwen, GLM, OpenRouter, vLLM, Ollama, llama.cpp, LiteLLM,
…). The wire follows the endpoint: only OpenAI gets max_completion_tokens,
the Responses API for tool calls, and the gpt-/o-family filter on its model
listing; only a compatible server gets its reported thinking echoed back."""

import json
import re
from urllib.request import Request as URLRequest

from .base import (EMPTY_REPLY_HINT, OPENAI_PICTURE_TOKENS, TOOL_IMAGES_NOTE, Protocol, api_url, as_int,
                   attach_target, key_headers, multipart_body, note_speed, parse_tool_args, served_speed_name, tool_image_turns,
                   turn_attachments)
from .responses import OPENAI_RESPONSES
from .services import service_of

# Listings include models the chat endpoint can't use.
_NOT_CHAT = re.compile(r"embed|whisper|tts|audio|image|dall-e|moderation|transcribe|realtime|search")
_OPENAI_CHAT_FAMILIES = re.compile(r"^(gpt-|o\d|chatgpt-)")


def _image_part(media_type: str, data: str) -> dict:
    return {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}}


def _user_content(message, pdf_b64s=(), images=()):
    """A user turn's content: its own PDFs, then the request's, its
    pictures, then the request's, and the text last — the plain text when
    there is nothing else."""
    files, pictures = turn_attachments(message, pdf_b64s, images)
    if not files and not pictures:
        return message["content"]
    return [
        *[{"type": "file", "file": {"filename": f"document-{index + 1}.pdf",
                                    "file_data": f"data:application/pdf;base64,{data}"}}
          for index, data in enumerate(files)],
        *[_image_part(media_type, data) for media_type, data in pictures],
        {"type": "text", "text": message["content"]},
    ]


# How compatible servers report a model's thinking beside the reply: as
# text (``reasoning_content``: DeepSeek, Kimi, Qwen, GLM, vLLM, llama.cpp;
# ``reasoning``: OpenRouter, Ollama, newer vLLM) and as OpenRouter's
# structured, possibly signed ``reasoning_details``. A thinking model wants
# them back on its earlier assistant turns (DeepSeek refuses a request with
# tools without them), echoed under the name they arrived by.
REASONING_FIELDS = ("reasoning_content", "reasoning")
REASONING_DETAILS = "reasoning_details"


def _merge_details(kept: list, chunk: list) -> None:
    """Fold one streamed ``reasoning_details`` chunk into the reply's list:
    a piece of an item already begun (same ``index`` and ``type``) extends
    its text, any other item is appended as it came."""
    for item in chunk:
        if not isinstance(item, dict):
            continue
        same = next((k for k in kept if "index" in item and k.get("index") == item.get("index")
                     and k.get("type") == item.get("type")), None)
        if same is None:
            kept.append(dict(item))
            continue
        for key, value in item.items():
            if key in ("text", "summary", "data") and isinstance(value, str):
                same[key] = (same.get(key) or "") + value
            elif value is not None:
                same[key] = value


def is_openai_platform(base_url: str) -> bool:
    """Whether an entry talks to OpenAI itself rather than a compatible
    server (DeepSeek, a gateway, a local model)."""
    return (base_url or "").startswith("https://api.openai.com")


class OpenAIChat(Protocol):
    id = "openai"
    picture_tokens = OPENAI_PICTURE_TOKENS
    label = "OpenAI Chat Completions API"
    key_placeholder = "sk-proj-…"
    key_url = "https://platform.openai.com/api-keys"
    # The same tiers as its Responses wire: "priority" is fast mode (it also
    # answers to "fast"), "flex" the cheaper, slower one.
    speeds = OPENAI_RESPONSES.speeds

    def speed_tiers(self, conf):
        # A compatible server bills and routes however it likes; only
        # OpenAI itself is known to take the field.
        return super().speed_tiers(conf) if is_openai_platform(conf["base_url"]) else []

    def wire(self, conf, tools=None):
        # Tool calls to OpenAI itself go over the Responses API (reasoning
        # models reject tools on chat completions); a compatible gateway may
        # not implement /v1/responses, and chat-completions tools work there.
        return OPENAI_RESPONSES if tools and is_openai_platform(conf["base_url"]) else self

    def request(self, conf, messages, system, model, pdf_b64s=None, effort="",
                max_tokens=8192, images=None, stream=False, tools=None, cache_key="", speed=""):
        target = attach_target(messages, pdf_b64s, images)
        # The thinking each assistant turn echoes back (never to OpenAI
        # itself, which reports none this way). A field one turn carries is
        # sent on every assistant turn, empty where none was kept, so a
        # server that wants it on each earlier turn finds it there.
        echo = not is_openai_platform(conf["base_url"])
        fields = {f for m in messages if echo and m["role"] == "assistant"
                  for f in (m.get("reasoning") or {}) if f in REASONING_FIELDS}

        def thinking(m):
            kept = m.get("reasoning") if isinstance(m.get("reasoning"), dict) else {}
            out = {f: "" for f in fields}
            out.update({f: v for f, v in kept.items() if f in fields and isinstance(v, str)})
            if echo and isinstance(kept.get(REASONING_DETAILS), list) and kept[REASONING_DETAILS]:
                out[REASONING_DETAILS] = kept[REASONING_DETAILS]
            return out

        wire = [{"role": "system", "content": system}] if system else []
        image_turn = lambda imgs: {"role": "user", "content": [  # noqa: E731
            {"type": "text", "text": TOOL_IMAGES_NOTE},
            *[_image_part(media_type, data) for media_type, data in imgs]]}
        for m, is_image_turn in tool_image_turns(messages, image_turn):
            if is_image_turn:
                wire.append(m)
            elif m["role"] == "tool":
                wire.append({"role": "tool", "tool_call_id": m["call_id"], "content": m["content"]})
            elif m["role"] == "assistant" and m.get("tool_calls"):
                wire.append({"role": "assistant", "content": m.get("content") or None,
                             "tool_calls": [{"id": c["id"], "type": "function",
                                             "function": {"name": c["name"],
                                                          "arguments": json.dumps(c["arguments"])}}
                                            for c in m["tool_calls"]], **thinking(m)})
            elif m["role"] == "assistant":
                wire.append({"role": "assistant", "content": m["content"], **thinking(m)})
            elif m["role"] == "user":
                wire.append({"role": "user", "content": (_user_content(m, pdf_b64s, images) if m is target
                                                         else _user_content(m))})
            else:
                wire.append({"role": m["role"], "content": m["content"]})
        body = {
            "model": model,
            # Current OpenAI models take max_completion_tokens (the cap includes
            # hidden reasoning tokens, so leave a generous default); compatible
            # servers take the classic max_tokens.
            ("max_completion_tokens" if is_openai_platform(conf["base_url"]) else "max_tokens"): max_tokens,
            "messages": wire,
        }
        functions = [t for t in tools or [] if not t.get("hosted")]  # this wire hosts no tools
        if functions:
            body["tools"] = [{"type": "function",
                              "function": {"name": t["name"], "description": t["description"],
                                           "parameters": t["parameters"]}} for t in functions]
        if effort:
            body["reasoning_effort"] = effort
        service_tier = self.speed_value(speed) if is_openai_platform(conf["base_url"]) else ""
        if service_tier:
            body["service_tier"] = service_tier
        if cache_key and (is_openai_platform(conf["base_url"]) or (service_of(conf) or {}).get("cache_key")):
            # Routes every turn of one conversation to the same cache; a
            # compatible server may reject fields it doesn't know, so only a
            # named service that takes it (Kimi) gets it too.
            body["prompt_cache_key"] = cache_key
        if stream:
            body["stream"] = True
            # The final chunk then carries the token counts (OpenAI and the
            # common compatible servers: vLLM, Ollama, llama.cpp, LiteLLM).
            body["stream_options"] = {"include_usage": True}
        return URLRequest(api_url(conf["base_url"], "/chat/completions"), data=json.dumps(body).encode(), headers={
            **key_headers(conf["api_key"]),
            "Content-Type": "application/json",
        })

    def reply_text(self, data):
        choices = data.get("choices") or [{}]
        text = (choices[0].get("message") or {}).get("content") or ""
        if not text.strip():
            reason = choices[0].get("finish_reason", "unknown")
            raise RuntimeError(f"empty response (finish_reason={reason} — {EMPTY_REPLY_HINT})")
        return text

    def stop_reason(self, data):
        return str(((data.get("choices") or [{}])[0] or {}).get("finish_reason") or "")

    def usage(self, raw):
        if not isinstance(raw, dict):
            return None
        usage = {"input": as_int(raw.get("prompt_tokens")), "output": as_int(raw.get("completion_tokens")),
                 "cache_read": as_int((raw.get("prompt_tokens_details") or {}).get("cached_tokens")),
                 "cache_write": 0}
        return usage if (usage["input"] or usage["output"]) else None

    def served_speed(self, data):
        # The completion says which tier served it ("default", "flex",
        # "priority", "scale") — what was asked for may have been routed
        # elsewhere; a compatible server leaves the field out.
        return served_speed_name(data.get("service_tier"))

    def stream_event(self, event, state):
        if event.get("error"):
            raise RuntimeError((event["error"] or {}).get("message") or "stream error")
        if event.get("usage"):
            state["usage"] = self.usage(event["usage"]) or state["usage"]
        note_speed(state, event.get("service_tier"))  # every chunk carries the served tier
        choice = (event.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}
        if delta.get("content"):
            yield ("text", delta["content"])
        for field in REASONING_FIELDS:
            if isinstance(delta.get(field), str) and delta[field]:
                kept = state.setdefault("reasoning", {})
                kept[field] = kept.get(field, "") + delta[field]
        if isinstance(delta.get(REASONING_DETAILS), list):
            _merge_details(state.setdefault("reasoning", {}).setdefault(REASONING_DETAILS, []),
                           delta[REASONING_DETAILS])
        pending = state.setdefault("pending", {})  # index -> {id, name, args} across deltas
        for tc in delta.get("tool_calls") or []:
            slot = pending.setdefault(tc.get("index", 0), {"id": "", "name": "", "args": ""})
            if tc.get("id"):
                slot["id"] = tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                slot["name"] = fn["name"]
            if fn.get("arguments"):
                slot["args"] += fn["arguments"]
                yield ("tool_delta", {"id": slot["id"], "name": slot["name"], "json": slot["args"]})
        state["stop"] = choice.get("finish_reason") or state["stop"]

    def stream_end(self, state):
        # The thinking arrived piecewise too: whole, ahead of the calls it led to.
        if state.get("reasoning"):
            yield ("reasoning", state["reasoning"])
        # Tool calls are announced piecewise; emit them once the stream ends.
        for _, slot in sorted(state.get("pending", {}).items()):
            yield ("tool", {"id": slot["id"], "name": slot["name"],
                            "arguments": parse_tool_args(slot["args"])})

    def models(self, data, conf):
        platform = is_openai_platform(conf["base_url"])
        # OpenAI's own listing is narrowed to its conversational families; a
        # compatible server names its models however it likes.
        return [m for m in super().models(data, conf)
                if not _NOT_CHAT.search(m["id"]) and (not platform or _OPENAI_CHAT_FAMILIES.match(m["id"]))]

    def transcription(self, conf):
        # OpenAI surely transcribes; a compatible server (DeepSeek) may not.
        return 2 if is_openai_platform(conf["base_url"]) else 1

    def transcription_request(self, conf, model, language, filename, content_type, audio, *, timestamps=False):
        fields = {"model": model, **({"language": language} if language else {})}
        if timestamps and model.endswith("-diarize"):
            # the diarizing model times its segments in its own format, and
            # takes audio past 30 s only in chunks
            fields.update({"response_format": "diarized_json", "chunking_strategy": "auto"})
        elif timestamps:
            # whisper-1's; gpt-4o-transcribe answers json or text only (a 400)
            fields.update({"response_format": "verbose_json", "timestamp_granularities[]": "segment"})
        body, multipart_type = multipart_body(fields, filename, content_type, audio)
        return URLRequest(api_url(conf["base_url"], "/audio/transcriptions"), data=body, headers={
            **key_headers(conf["api_key"]),
            "Content-Type": multipart_type,
        })

    def transcript(self, data):
        return (data.get("text") or "").strip()

    def transcript_segments(self, data):
        # verbose_json's and diarized_json's segments: {start, end, text, …} in seconds
        def seconds(value):
            return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

        segments = [{"start": seconds(s.get("start")) or 0.0, "end": seconds(s.get("end")),
                     "text": str(s.get("text") or "").strip()}
                    for s in data.get("segments") or [] if isinstance(s, dict)]
        return [s for s in segments if s["text"]] or super().transcript_segments(data)
