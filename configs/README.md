# List of model configurations
Scratchpad for recording how different models should be configured for PvP.

### OpenAI Family

GPT 5 Mini
```yaml
  - agent: mini
    name: openai/gpt-5-mini
    config:
      agent: !include mini/default.yaml
      model:
        model_class: "portkey"
        model_name: openai/gpt-5-mini
```

GPT 5 High Thinking
```yaml
  - agent: mini
    name: openai/gpt-5
    config:
      agent: !include mini/default.yaml
      model:
        model_class: "portkey"
        model_name: openai/gpt-5
        model_kwargs:
          drop_params: true
          reasoning_effort: "high"
          verbosity: "medium"
```

o3
```yaml
  - agent: mini
    name: openai/o3
    config:
      agent: !include mini/default.yaml
      model:
        model_class: "portkey"
        model_name: openai/o3
```

### Anthropic Family

Claude Sonnet 4
```yaml
  - agent: mini
    name: anthropic/claude-sonnet-4-20250514
    config:
      agent: !include mini/default.yaml
      model:
        model_class: "portkey"
        model_name: anthropic/claude-sonnet-4-20250514
```

Claude Sonnet 3.7
```yaml
  - agent: mini
    name: anthropic/claude-sonnet-3-7
    config:
      agent: !include mini/default.yaml
      model:
        model_class: "portkey"
        model_name: anthropic/claude-sonnet-3-7
```

### Qwen

Qwen 3 Coder
```yaml
  - agent: mini
    name: qwen/qwen-3-coder
    config:
      agent: !include mini/default.yaml
      model:
        model_class: "portkey"
        model_name: qwen/qwen-3-coder
```
