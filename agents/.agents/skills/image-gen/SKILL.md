---
name: image-gen
description: "Generate or edit raster images using an available image-generation tool. When Claude needs Codex to provide that tool, delegate with gpt-6.1-sol. Use code or vector tools for structured charts, diagrams, and existing SVG assets."
---

# Image generation

Use the current environment's image-generation tool directly when available. When running in Claude without such a tool, delegate to Codex with gpt-6.1-sol as the coordinating model. The image-generation tool produces the image; choosing a stronger text coordinator does not by itself establish better image quality.

## Delegate when needed

In T3 Code, read [T3 execution](../claude-collab/references/t3-code.md) and use `delegate_task` targeting the available Codex instance with model `gpt-6.1-sol`. Give it the visual brief, accessible reference paths, and output requirements; require the actual image-generation tool, not a text description or a code-drawn substitute. Follow the returned completion instructions rather than polling. Do not run the shell command below inside T3. If Codex or its image tool is unavailable, report the limitation without silently changing providers or generating a substitute.

For an image the user wants to save, post, or use elsewhere, require a saved PNG and its absolute path. Verify the returned artifact before presenting it. If the image tool only returns an inline artifact, do not invent a local path; report the export limitation. Claude remains responsible for returning the result to the user.

Outside T3 Code, use the CLI route below.

Create a task-specific prompt file with the file-editing tool. Include the visual brief, exact output path, and any reference image paths. Keep untrusted prompt text out of shell command interpolation. From the intended output directory, run:

```text
codex exec --skip-git-repo-check -s workspace-write -m gpt-6.1-sol - < /tmp/<task>/image-brief.md
```

Use an authorized writable output directory. Preserve the explicit Sol choice; if unavailable, report the limitation rather than silently switching models. For edits, inspect the reference and use the image tool's reference mechanism. If a required image is inaccessible, request it again instead of inventing it.

Specify subject, setting, lighting, composition, style, and any required dimensions or transparency. Ask Codex to save the result at the named path and return that path. For multiple images, give every output a distinct name. Allow several minutes for generation while monitoring the process and keeping the user informed.

## Verify

Confirm the file exists and inspect it with an available image viewer. Check the brief, dimensions, and transparency where relevant. Refine the prompt or edit through the image tool when needed. Return the image or link the saved artifact; do not treat a worker's claimed path as proof that a file was saved.

## Model quirks and cost

Keep the delegation brief focused on producing and saving the image. Use [model quirks](../claude-collab/references/model-quirks.md) only when the coordinator needs tuning. Check [current pricing](https://learn.chatgpt.com/docs/pricing) when cost matters rather than relying on a fixed token-price ratio or assuming the user's configured default. Do not report usage telemetry as proof of a separate charge.
