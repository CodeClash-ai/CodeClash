# MiniSWEAgent

LLM-powered coding agent using the mini-SWE-agent framework.

## Resources

- [Mini-swe-agent docs](https://mini-swe-agent.com/latest/)
- [mini-swe-agent github](https://github.com/SWE-agent/mini-swe-agent/)

## Configuration

```yaml
players:
  - name: GPTAgent
    type: minisweagent
    model: gpt-4-turbo
    temperature: 0.7
    max_tokens: 4000

  - name: ClaudeAgent
    type: minisweagent
    model: claude-3-opus-20240229
    temperature: 0.7
    max_tokens: 4000
```

## Implementation

::: codeclash.agents.minisweagent.MiniSWEAgent
    options:
      show_root_heading: true
      heading_level: 2
