---
name: image-gen
description: "Generate raster images (illustrations, photos, art, mockup images, non-trivial icons) by delegating to Codex with gpt-6.1-sol. Use whenever a task needs a generated image instead of drawing one yourself. Not for diagrams or charts built from structured data; draw those as SVG."
---

# Image generation through Codex

Claude does not draw images itself. Codex has a built-in image generation tool
(GPT-Image-2), so hand the job to `codex exec` and read the file it writes.

Codex agents already have this tool. If you are Codex, call it directly and skip
the command below.

## Command

Run from the directory the image should land in:

```bash
cd <output dir> && codex exec --skip-git-repo-check -s workspace-write -m gpt-6.1-sol \
  "Generate an image with your image generation tool: <prompt>. Save it as <name>.png in the current directory. Reply with the saved file path only."
```

- Always pass `-m gpt-6.1-sol`. The Codex default is `gpt-6-astra`, which costs
  five times as much per token and gives no better image, because the image
  itself comes from GPT-Image-2 either way.
- `-s workspace-write` lets Codex copy the image into the current directory.
- One image takes a few minutes. Give the Bash call a timeout of at least
  400000 ms.
- Codex keeps the original under `~/.codex/generated_images/<session>/`.

## Prompt

Write the prompt as a full scene: subject, setting, lighting, composition and
style ("soft painterly", "watercolor", "flat vector", "product photo"). Name
the aspect ratio or size if it matters. For several images, run one
`codex exec` per image so each file name is predictable.

## Check the result

Open the PNG with the Read tool and look at it before reporting. If it misses
the brief, rerun with a sharper prompt instead of editing it yourself.

## Cost

Codex credits per million tokens (standard speed): gpt-6.1-sol 50 input,
2.5 cached, 250 output; gpt-6-astra 250, 25, 1,250. GPT-Image-2 is billed
on top, the same whichever model drives Codex. Image generation draws from
the plan's included Codex limits first, then credits. Source:
https://learn.chatgpt.com/docs/pricing

The "tokens used" figure that `codex exec` prints leaves out cached input. For
a real count, read the last `token_count` event in the session log under
`~/.codex/sessions/`.
