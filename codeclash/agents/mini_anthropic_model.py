"""Custom mini-swe-agent model class for Claude served through a custom Anthropic-compatible
base URL, with explicit per-token cost tracking.

mini-swe-agent's default LitellmModel converts everything to the OpenAI API format. Behind
some proxies/gateways that drops the `cache_control` markers, disabling prompt caching and
making Claude calls slow and expensive. This class speaks the native Anthropic API instead
(via the `anthropic` SDK against a configurable `base_url`), so caching is preserved, and it
computes request cost from its own `cost:` block rather than relying on a litellm price registry.

To use it, point a player's `model` block at
`model_class: codeclash.agents.mini_anthropic_model.AnthropicModel` and provide the API key,
base URL, and model name (see the `*_env` config fields, which keep endpoint-specific values in
the environment rather than in committed configs). Requires the optional `anthropic` dependency
(`uv pip install -e '.[llama]'`). See configs/ladder/robotrumble_llama.yaml.
"""

import json
import logging
import os
import time
from types import SimpleNamespace
from typing import Any

import anthropic
from jinja2 import StrictUndefined, Template
from minisweagent.models import GLOBAL_MODEL_STATS
from minisweagent.models.utils.actions_toolcall import parse_toolcall_actions
from minisweagent.models.utils.retry import retry
from pydantic import BaseModel

logger = logging.getLogger("anthropic_model")

# Map Anthropic stop reasons to OpenAI-style finish_reasons so that finish_reason-based
# format_error_templates (e.g. the truncation branch) behave the same as for litellm models.
_ANTHROPIC_FINISH_REASON = {
    "max_tokens": "length",
    "tool_use": "tool_calls",
    "end_turn": "stop",
    "stop_sequence": "stop",
}


def _finish_reason_from_anthropic(stop_reason: str | None) -> str | None:
    return _ANTHROPIC_FINISH_REASON.get(stop_reason, stop_reason)


ANTHROPIC_BASH_TOOL = {
    "name": "bash",
    "description": "Execute a bash command",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute",
            }
        },
        "required": ["command"],
    },
}


class CostPerToken(BaseModel):
    """Per-token costs in USD."""

    input: float = 0.0
    output: float = 0.0
    cache_creation_input: float = 0.0
    cache_read_input: float = 0.0


class AnthropicModelConfig(BaseModel):
    model_name: str
    """Anthropic model name, e.g. `claude-sonnet-4-5-20250929`. Overridden by `model_name_env`
    if that names a set environment variable (so endpoint-specific model ids stay out of configs)."""
    model_name_env: str | None = None
    """Optional env var to read the model name from, overriding `model_name` when set."""
    model_kwargs: dict[str, Any] = {}
    """Additional arguments passed to the API."""
    drop_none_model_kwargs: bool = True
    """Drop all model_kwargs that are None.
    This is so we can easily recursively merge this config with other configs targeting litellm.
    """
    max_tokens: int = 16384
    """Maximum number of output tokens."""
    base_url: str | None = None
    """Custom base URL for the Anthropic API (e.g. for proxies). Overridden by `base_url_env`."""
    base_url_env: str | None = None
    """Optional env var to read the base URL from, overriding `base_url` when set (so endpoint
    URLs stay out of configs)."""
    api_key_env: str = "ANTHROPIC_API_KEY"
    """Environment variable name for the API key."""
    cost: CostPerToken = CostPerToken()
    """Per-token costs in USD for computing request cost from usage."""
    format_error_template: str = "{{ error }}"
    """Template used when the LM's output is not in the expected format."""
    observation_template: str = (
        "{% if output.exception_info %}<exception>{{output.exception_info}}</exception>\n{% endif %}"
        "<returncode>{{output.returncode}}</returncode>\n<output>\n{{output.output}}</output>"
    )
    """Template used to render the observation after executing an action."""


class AnthropicModel:
    abort_exceptions: list[type[Exception]] = [
        anthropic.BadRequestError,
        anthropic.AuthenticationError,
        anthropic.PermissionDeniedError,
        anthropic.NotFoundError,
        KeyboardInterrupt,
    ]

    def __init__(self, *, config_class: type = AnthropicModelConfig, **kwargs):
        self.config = config_class(**kwargs)
        # Resolve endpoint-specific values from the environment so they stay out of configs.
        if self.config.model_name_env:
            model_name = os.getenv(self.config.model_name_env, "")
            if not model_name:
                raise ValueError(f"Set the {self.config.model_name_env} environment variable to the model name.")
            self.config.model_name = model_name
        if self.config.base_url_env:
            base_url = os.getenv(self.config.base_url_env, "")
            if not base_url:
                raise ValueError(f"Set the {self.config.base_url_env} environment variable to the API base URL.")
            self.config.base_url = base_url
        api_key = os.getenv(self.config.api_key_env, "")
        if not api_key:
            raise ValueError(f"API key not found. Set the {self.config.api_key_env} environment variable.")
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url
        self.client = anthropic.Anthropic(**client_kwargs)

    @staticmethod
    def _set_cache_control_on_last_message(messages: list[dict]) -> list[dict]:
        """Add cache_control to the last block of the last message."""
        import copy

        messages = copy.deepcopy(messages)
        if not messages:
            return messages
        last = messages[-1]
        content = last["content"]
        if content is None:
            last["cache_control"] = {"type": "ephemeral"}
        elif isinstance(content, str):
            last["content"] = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
        else:
            content[-1]["cache_control"] = {"type": "ephemeral"}
        return messages

    @staticmethod
    def _strip_display_text(content: list[dict] | str) -> list[dict] | str:
        """Remove the 'text' key we add to non-text blocks for interactive display
        and 'caller' (None) that model_dump() emits from newer SDK versions."""
        if not isinstance(content, list):
            return content
        return [
            {
                k: v
                for k, v in block.items()
                if not (k == "text" and block.get("type") != "text") and not (k == "caller" and v is None)
            }
            for block in content
        ]

    def _query(self, messages: list[dict], **kwargs):
        assert messages[0]["role"] == "system"
        api_messages = self._set_cache_control_on_last_message(
            [{"role": m["role"], "content": self._strip_display_text(m["content"])} for m in messages[1:]]
        )
        extra_model_kwargs = self.config.model_kwargs | kwargs
        if self.config.drop_none_model_kwargs:
            extra_model_kwargs = {k: v for k, v in extra_model_kwargs.items() if v is not None}
        return self.client.messages.create(
            model=self.config.model_name,
            max_tokens=self.config.max_tokens,
            system=messages[0]["content"],
            messages=api_messages,
            tools=[ANTHROPIC_BASH_TOOL],
            **extra_model_kwargs,
        )

    def query(self, messages: list[dict[str, str]], **kwargs) -> dict:
        for attempt in retry(logger=logger, abort_exceptions=self.abort_exceptions):
            with attempt:
                response = self._query(messages, **kwargs)
        actions = self._parse_actions(response)
        cost_output = self._calculate_cost(response)
        GLOBAL_MODEL_STATS.add(cost_output["cost"])
        content = []
        for block in response.content:
            d = block.model_dump()
            if block.type == "tool_use":
                d["text"] = f"```\n{block.input.get('command', json.dumps(block.input))}\n```"
            content.append(d)
        return {
            "role": "assistant",
            "content": content,
            "extra": {
                "actions": actions,
                "response": response.model_dump(),
                **cost_output,
                "timestamp": time.time(),
            },
        }

    def _parse_actions(self, response: anthropic.types.Message) -> list[dict]:
        tool_calls = [
            SimpleNamespace(
                id=block.id,
                function=SimpleNamespace(name=block.name, arguments=json.dumps(block.input)),
            )
            for block in response.content
            if block.type == "tool_use"
        ]
        return parse_toolcall_actions(
            tool_calls,
            format_error_template=self.config.format_error_template,
            template_kwargs={"finish_reason": _finish_reason_from_anthropic(response.stop_reason)},
        )

    def _calculate_cost(self, response: anthropic.types.Message) -> dict[str, float]:
        usage = response.usage
        c = self.config.cost
        return {
            "cost": (
                usage.input_tokens * c.input
                + usage.output_tokens * c.output
                + getattr(usage, "cache_creation_input_tokens", 0) * c.cache_creation_input
                + getattr(usage, "cache_read_input_tokens", 0) * c.cache_read_input
            )
        }

    def format_message(self, **kwargs) -> dict:
        return kwargs

    def format_observation_messages(
        self, message: dict, outputs: list[dict], template_vars: dict | None = None
    ) -> list[dict]:
        """Format execution outputs as a single user message with tool_result blocks (Anthropic format)."""
        actions = message.get("extra", {}).get("actions", [])
        not_executed = {"output": "", "returncode": -1, "exception_info": "action was not executed"}
        padded_outputs = outputs + [not_executed] * (len(actions) - len(outputs))
        tool_results = []
        extras = []
        for action, output in zip(actions, padded_outputs):
            content = Template(self.config.observation_template, undefined=StrictUndefined).render(
                output=output, **(template_vars or {})
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": action["tool_call_id"],
                    "content": content,
                    "text": content,
                }
            )
            extras.append(
                {
                    "raw_output": output.get("output", ""),
                    "returncode": output.get("returncode"),
                    "timestamp": time.time(),
                    "exception_info": output.get("exception_info"),
                    **output.get("extra", {}),
                }
            )
        return [
            {
                "role": "user",
                "content": tool_results,
                "extra": {"observations": extras},
            }
        ]

    def get_template_vars(self, **kwargs) -> dict[str, Any]:
        return self.config.model_dump()

    def serialize(self) -> dict:
        return {
            "info": {
                "config": {
                    "model": self.config.model_dump(mode="json"),
                    "model_type": f"{self.__class__.__module__}.{self.__class__.__name__}",
                },
            }
        }
