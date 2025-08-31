"""
llm_prompt.py

Refactored Prompt utility for delivering prompts to various LLM backends.
- Replaces kwargs templating with an explicit promptStrategy callable.
- Removes modelPromptStrategyMap; callers choose a strategy.
- Adds safer defaults, optional system prompt, temperature control,
  improved transformers generation, and structured error handling.

Usage example:

    from llm_prompt import Prompt

    # Choose a strategy explicitly
    p = Prompt(
        modelName="llama3",
        message="Hello world",
        promptStrategy=Prompt.deliverOllamaPrompt,
    )
    print(p.deliver())

    # OpenAI-compatible API:
    p = Prompt(
        modelName="gpt-4o",
        message="Say hi",
        promptStrategy=Prompt.deliverAPIPrompt,
        temperature=0.2,
        systemPrompt="You are helpful.",
    )
    print(p.deliver())

    # LiteLLM (e.g., OpenRouter; set env OPENROUTER_API_KEY):
    p = Prompt(
        modelName="openrouter/google/palm-2-chat-bison",
        message="Hello, how are you?",
        promptStrategy=Prompt.deliverLiteLLMPrompt,
    )
    print(p.deliver())

    # Local HF Transformers:
    p = Prompt(
        modelName="microsoft/Phi-3.5-mini-instruct",
        message="Write a limerick",
        promptStrategy=Prompt.deliverTransformersTokenizerPrompt,
    )
    print(p.deliver())

    # Instructor (structured output):
    from pydantic import BaseModel
    class MyOut(BaseModel):
        greeting: str
    p = Prompt(
        modelName="phi3",
        message="Return {\"greeting\": \"hi\"}",
        promptStrategy=Prompt.deliverPromptInstructor,
    )
    print(p.deliver(structuredOutputClass=MyOut))
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

# Optional deps
try:
    import instructor  # type: ignore
except Exception:  # pragma: no cover
    instructor = None  # type: ignore

try:
    import ollama  # type: ignore
except Exception:  # pragma: no cover
    ollama = None  # type: ignore

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

# liteLLM (optional)
try:
    from litellm import completion as litellm_completion  # type: ignore
except Exception:  # pragma: no cover
    litellm_completion = None  # type: ignore

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
except Exception:  # pragma: no cover
    AutoModelForCausalLM = None  # type: ignore
    AutoTokenizer = None  # type: ignore

try:
    from icecream import ic  # type: ignore
except Exception:  # pragma: no cover
    def ic(*args, **kwargs):  # fallback no-op
        return None

# Config fallback
try:
    from core.utils import config as CONFIG  # type: ignore
except Exception:  # pragma: no cover
    CONFIG = {
        "prompt_template": "",
        "baseurl": None,
        "api_key": None,
        "default_ollama_server": "http://localhost:11434",
    }


@dataclass
class _TransformersCache:
    model: Any = None
    tokenizer: Any = None
    model_name: Optional[str] = None

    def get_or_create(self, model_name: str) -> Tuple[Any, Any]:
        if AutoModelForCausalLM is None or AutoTokenizer is None:
            raise RuntimeError("transformers not installed")
        if self.model is None or self.model_name != model_name:
            # Load once; rely on accelerate for device placement
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name, device_map="auto"
            )
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model_name = model_name
        return self.model, self.tokenizer


_TRANSFORMERS_CACHE = _TransformersCache()

# A PromptStrategy is an instance method (bound) that returns a string or structured output
PromptStrategy = Callable[["Prompt"], Any]


class Prompt:
    def __init__(
        self,
        modelName: str,
        message: Optional[str] = None,
        promptTemplate: str = CONFIG.get("prompt_template", ""),
        isInstructor: bool = False,
        promptStrategy: Optional[PromptStrategy] = None,
        temperature: float = 0.3,
        systemPrompt: Optional[str] = None,
        max_new_tokens: int = 1024,
        top_p: float = 0.95,
        seed: Optional[int] = None,
    ) -> None:
        self.modelName = modelName
        self.messageContent = message if message is not None else promptTemplate
        self.isInstructor = isInstructor
        self.temperature = float(temperature)
        self.systemPrompt = systemPrompt
        self.max_new_tokens = int(max_new_tokens)
        self.top_p = float(top_p)
        self.seed = seed

        # Strategy: bind caller-provided strategy to this instance, or default to Ollama
        if promptStrategy is None:
            self.promptStrategy: PromptStrategy = self.deliverOllamaPrompt
        else:
            try:
                # Bind unbound function (e.g., Prompt.deliverAPIPrompt) to this instance
                self.promptStrategy = promptStrategy.__get__(self, Prompt)  # type: ignore[attr-defined]
            except Exception:
                # Fallback: assume already bound/callable
                self.promptStrategy = promptStrategy  # type: ignore[assignment]

        self.baseurl, self.apiKey = self._getBaseUrlAndKey()
        self._transformerModel = None
        self._tokenizer = None

    def deliver(self, **kwargs) -> Any:
        return self.promptStrategy(**kwargs) if hasattr(self.promptStrategy, "__call__") else None

    # ----- Common helpers -----
    def _getBaseUrlAndKey(self) -> Tuple[Optional[str], Optional[str]]:
        # For OpenAI-native models, let the OpenAI SDK defaults apply (env vars)
        if self.modelName in {"gpt-4o", "gpt-4o-mini"}:
            return None, None
        return CONFIG.get("baseurl", None), CONFIG.get("api_key", None)

    def _setupClient(self):
        if self.isInstructor:
            return self._setupInstructorClient()
        if OpenAI is None:
            raise RuntimeError("openai SDK not installed")
        return OpenAI(base_url=self.baseurl, api_key=self.apiKey)

    def _setupInstructorClient(self):
        if instructor is None or OpenAI is None:
            raise RuntimeError("instructor or openai not installed")
        client = instructor.from_openai(
            OpenAI(
                base_url=CONFIG.get("default_ollama_server", "http://localhost:11434"),
                api_key="ollama",
            ),
            mode=instructor.Mode.JSON,
        )
        return client

    # ----- Strategies -----
    def deliverPromptInstructor(self, structuredOutputClass: Any) -> Any:
        client = self._setupInstructorClient()
        messages = self._build_messages()
        response = client.chat.completions.create(
            model=self.modelName,
            messages=messages,
            response_model=structuredOutputClass,
            temperature=self.temperature,
        )
        return response

    def deliverAPIPrompt(self) -> str:
        client = self._setupClient()
        if not self.messageContent:
            return ""
        messages = self._build_messages()
        ic({"model": self.modelName, "len": len(self.messageContent)})
        resp = client.chat.completions.create(
            model=self.modelName,
            messages=messages,
            temperature=self.temperature,
        )
        if resp is None or not getattr(resp, "choices", None):
            return ""
        return resp.choices[0].message.content

    def deliverOllamaPrompt(self) -> str:
        if ollama is None:
            raise RuntimeError("ollama library not installed")
        if not self.messageContent:
            return ""
        ic({"model": self.modelName, "len": len(self.messageContent)})
        out = ollama.generate(model=self.modelName, prompt=self.messageContent)
        return out.get("response", "") if isinstance(out, dict) else str(out)

    def deliverTransformersTokenizerPrompt(self) -> str:
        model, tok = _TRANSFORMERS_CACHE.get_or_create(self.modelName)
        text = self._chat_template(tok, self.messageContent or "")

        # Tokenize (keep on CPU and let accelerate handle device placement)
        model_inputs = tok([text], return_tensors="pt")

        gen_kwargs = {
            "max_new_tokens": self.max_new_tokens,
            "do_sample": True,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        if self.seed is not None:
            try:
                import torch  # type: ignore
                torch.manual_seed(int(self.seed))
            except Exception:
                pass

        generated_ids = model.generate(**model_inputs, **gen_kwargs)
        # strip prompt tokens
        trimmed = [out_ids[len(inp_ids):] for inp_ids, out_ids in zip(model_inputs.input_ids, generated_ids)]
        response = tok.batch_decode(trimmed, skip_special_tokens=True)[0]
        return response

    def deliverLiteLLMPrompt(self, **extra) -> str:
        """Deliver via LiteLLM. Set provider API keys via env vars (e.g., OPENROUTER_API_KEY).
        Usage:
            Prompt(modelName="openrouter/google/palm-2-chat-bison",
                   message="Hello",
                   promptStrategy=Prompt.deliverLiteLLMPrompt)
        """
        if litellm_completion is None:
            raise RuntimeError("litellm not installed: pip install litellm")
        if not self.messageContent:
            return ""
        messages = self._build_messages()
        params = {
            "model": self.modelName,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_new_tokens,
            "top_p": self.top_p,
        }
        params.update(extra or {})
        resp = litellm_completion(**params)  # openai-like response
        # Extract text robustly
        try:
            if hasattr(resp, "choices"):
                choices = resp.choices
                if choices:
                    msg = getattr(choices[0], "message", None)
                    if msg is not None and hasattr(msg, "content"):
                        return msg.content
            if isinstance(resp, dict):
                choices = resp.get("choices")
                if choices:
                    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
                    if isinstance(msg, dict):
                        return msg.get("content", "")
        except Exception:
            pass
        return str(resp)

    # ----- Utilities -----
    def _build_messages(self) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        if self.systemPrompt:
            msgs.append({"role": "system", "content": str(self.systemPrompt)})
        msgs.append({"role": "user", "content": self.messageContent or ""})
        return msgs

    @staticmethod
    def _chat_template(tokenizer: Any, content: str) -> str:
        messages = [{"role": "user", "content": content}]
        try:
            # Not all tokenizers implement this; fallback to raw
            return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            return content

