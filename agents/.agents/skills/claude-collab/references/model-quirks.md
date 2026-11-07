# Model quirks for skill and worker prompts

Checked against provider guidance on 2026-10-17. These notes adapt existing workflows; they do not select a model, grant tool access, or override the user's instructions. Read only the relevant model section. Recheck the source before changing a model ID, API setting, or effort default. Effort levels are not comparable across models or products.

## GPT-6 Astra

It can ask for clarification or approval before useful work is complete, follow conflicting skill rules too literally, format answers heavily, delegate less than expected, and test small edits too broadly. State the requested outcome, real approval boundary, useful delegation conditions, and proportionate completion checks. Continue authorized work through completion; preserve explicit review checkpoints.

Source: [OpenAI prompting guidance](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices).

## GPT-6.1 Sol

OpenAI offers the family prompting guidance as a starting point, based on Astra observations. Validate those mitigations on Sol rather than claiming identical quirks. Preserve an explicit Sol choice. For direct API integrations, supported effort is low, medium (default), high, xhigh, or max; none and minimal are unsupported, and tool calling requires Responses. These are API constraints, not parameters to insert into a skill brief.

Sources: [family guidance](https://developers.openai.com/api/docs/guides/latest-model), [Sol model](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

## Claude Opus 5.5

Start effort comparisons at medium; higher levels can spend much longer thinking. Thinking is always on. Request concise reasons or action summaries rather than private reasoning in visible text. In unattended runs, a text-only update or end_turn does not prove completion: check the stated done condition and remaining work, and continue only within the existing authorization, deadline, and retry boundary. For dense visual input, crop or zoom when needed.

Source: [Opus 5.5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5).

## Claude Sonnet 5.5

For specified coding tasks, start effort comparisons at medium; harder work may need high. The Claude API default is high, while Claude Code defaults to medium. Low or medium can check in early; define completion and continue authorized work. Higher effort can add supporting files or review rounds beyond the task, so state the scope and stop after relevant checks. Low effort can skip verification: require a check that exercises the change. For research, explicitly retrieve changing facts. With JSON reasoning tasks, use adaptive thinking and schema support where available; between_tools has no up-front thinking without tools.

Source: [Sonnet 5.5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5).

## Claude Haiku 5.5

Medium is the default starting point; low is useful for short tasks but can skip searches, checks, or completion in long prompts. Include the current date for retrieval and specify which changing facts require search. Give agents a short brief, concrete completion condition, and real verification command. Adaptive thinking helps when JSON output and custom tools are combined; disabling thinking can suppress a needed tool call. Effort replaces the old thinking budget. Check for an empty visible answer on xhigh before accepting a result.

Source: [Haiku 5.5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-haiku-5-5).

## Claude Code invocation

Use the installed CLI's supported --model and --effort flags only when a deliberate override is warranted. Verify alias resolution and account availability; an alias is not a permanent version pin. Claude Code starts Opus 5.5, Sonnet 5.5, and Haiku 5.5 at medium. Keep API defaults separate from CLI defaults and preserve the user's chosen model.

Source: [Claude Code model configuration](https://code.claude.com/docs/en/model-config).
