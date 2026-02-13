---
name: ask-opencode
description: Use this skill when you need to delegate work to other AI models via OpenCode, get feedback from multiple models, or orchestrate collaborative multi-agent workflows. Claude Code stays in control and decides what to ask, which models to use, and how to use their responses.
version: 1.0.0
---

# Ask OpenCode

A simple bridge between Claude Code and other AI models via OpenCode CLI.

## What This Does

**Lets Claude Code communicate with other AI models** (Gemini, Codex, GPT-5, etc.) through OpenCode.

**You (Claude Code) control:**
- What to ask
- Which models to use
- How to use responses
- Whether to iterate

## Setup

**Install OpenCode:**
```bash
curl -fsSL https://raw.githubusercontent.com/opencode-ai/opencode/refs/heads/main/install | bash
```

**Configure:**
```bash
opencode /connect  # Add your API keys
```

**Test:**
```bash
opencode run "Hello"
```

## How to Use

### Send to One Model

```bash
opencode run -m "github-copilot/gpt-5.1-codex" "Your prompt here"
```

### Send to Multiple Models

```bash
# Ask Gemini
opencode run -m "github-copilot/gemini-2.5-pro" "Your prompt"

# Ask Codex
opencode run -m "github-copilot/gpt-5.1-codex" "Your prompt"

# Ask Claude
opencode run -m "github-copilot/claude-sonnet-4.5" "Your prompt"
```

### View Available Models

```bash
opencode models
```

**Note:** Requires GitHub Copilot access with OpenCode integration.

## Common Patterns

### Pattern: Delegate Work
```
You: "I need tests for this function"
→ opencode run -m "github-copilot/gpt-5.1-codex" "Write tests for: [code]"
← Review response
You: Use the tests
```

### Pattern: Get Feedback
```
You: "I wrote this code"
→ opencode run -m "github-copilot/claude-opus-4.6" "Review: [code]"
← Review response
You: Fix issues
```

### Pattern: Multiple Opinions
```
You: "Which approach is better?"
→ Ask model 1
→ Ask model 2
→ Ask model 3
← Read all responses
You: Decide based on consensus
```

### Pattern: Specialized Help
```
You: "Need algorithm + API"
→ opencode run -m "github-copilot/gemini-2.5-pro" "Design algorithm"
→ opencode run -m "github-copilot/gpt-5.1-codex" "Build API"
← Review both
You: Combine them
```

### Pattern: Iterative Refinement
```
You: "Initial solution"
→ Ask for feedback
← Get feedback
You: Improve solution
→ Ask again
← Get validation
You: Done
```

## Tips

1. **Be specific** - Clear prompts get better responses
2. **Include context** - Paste relevant code/specs
3. **Validate responses** - Other models can be wrong
4. **Iterate** - Refine based on feedback
5. **Stay in control** - You decide what to use

## Model Quick Reference

**Available GitHub Copilot Models:**

| Model | Best For |
|-------|----------|
| `github-copilot/gpt-5.1-codex` | Code generation, refactoring |
| `github-copilot/gpt-5.1-codex-max` | Complex code tasks |
| `github-copilot/gpt-5.2-codex` | Advanced code analysis |
| `github-copilot/claude-sonnet-4.5` | Balanced reasoning & code |
| `github-copilot/claude-opus-4.6` | Deep analysis, security review |
| `github-copilot/gemini-2.5-pro` | Complex reasoning |
| `github-copilot/gpt-5.2` | General purpose |
| `github-copilot/gpt-5.1` | Fast responses |

Run `opencode models` to see all available models.

## Example Workflow

**Collaborative Spec Writing:**
1. You write initial spec
2. `opencode run -m "github-copilot/claude-sonnet-4.5" "Review this spec: [spec]"`
3. Review feedback
4. Refine spec
5. `opencode run -m "github-copilot/gpt-5.1-codex" "Is this implementable: [spec]"`
6. Review feedback
7. Finalize spec

**That's it.** Simple orchestration, you control everything.
