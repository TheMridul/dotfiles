---
name: cloudflare
description: Cloudflare work of any kind (choosing products, Workers, Wrangler or the cf CLI, Durable Objects, Agents SDK, Sandbox, frameworks and Next.js on Workers, app setup, Email, Turnstile, Zero Trust and Cloudflare One, Gateway Workers, K2, Basin, profiling). Also Cloudflare error pages, 52x and 1xxx errors. Pick the matching guide from this skill's table and read only that one.
---

# Cloudflare guides

Each Cloudflare area has its own guide under this folder. Pick the one row that
matches the task, read `cloudflare/<guide>/GUIDE.md`, and follow it. Read a
second guide only when the task crosses into its area. When the Cloudflare MCP
server is connected, prefer its tools for docs lookups and API calls.

The guides were written as standalone skills from Cloudflare's skills repository.
Where one says `SKILL.md`, it means its own `GUIDE.md`, and "the X skill" means
the X guide in this table. `web-perf` is the exception: it stays a separate
top-level skill. Paths such as `references/` resolve from the guide's own folder.

| Guide | Use for |
| --- | --- |
| `products` | Picking Cloudflare products for a need, architecture, choosing between `cf` and Wrangler, Cloudflare error pages (52x, 1xxx, Cloudflare 403) |
| `cf-cli` | The `cf` CLI: sign-in, profiles, `cf deploy/dev/build`, DNS, zones, D1, KV, R2 from the terminal |
| `wrangler` | Wrangler commands in projects that have a `wrangler.jsonc`, `wrangler.json` or `wrangler.toml` |
| `workers-best-practices` | Writing, reviewing or configuring production Workers |
| `workers-development` | Running and debugging Workers locally with `cf dev`, `wrangler dev` or the Vite plugin; routes production debugging |
| `workers-profiling` | CPU and memory profiling of deployed Workers and Durable Objects |
| `cloudflare-app-bootstrap` | Getting an existing Workers app to a working local request: bindings, secrets, seed data |
| `frameworks-on-cloudflare` | Astro, SvelteKit, React Router, TanStack Start, Nuxt, Hono, React or Vue SPAs on Workers |
| `nextjs-on-cloudflare` | Next.js on Workers with vinext, or moving off OpenNext |
| `durable-objects` | Durable Objects for persistent state and coordination |
| `agents-sdk` | Apps built on the Cloudflare Agents SDK (`agents` package) |
| `sandbox-stable` | Apps on the stable `@cloudflare/sandbox` package |
| `sandbox-next` | Apps on `@cloudflare/sandbox@next` (SDK 1.0 preview) |
| `sandbox-migrate-to-next` | Porting a stable Sandbox app to `@cloudflare/sandbox@next` |
| `cloudflare-email-service` | Email Sending and Email Routing integrations and delivery setup |
| `turnstile-spin` | Adding or fixing Turnstile bot checks, including server-side Siteverify |
| `cloudflare-one` | Zero Trust and SASE: Access, Gateway, tunnels; reaching an Access-protected site from a script or agent |
| `cloudflare-one-migrations` | Planning a move from another VPN, SWG or SASE vendor to Cloudflare One |
| `gateway-workers` | Workers called by the Forward action in Gateway HTTP policies |
| `k2` | K2 and K2 Streams durable logs: streams, producers, retention, subscriptions |
| `basin` | Basin Pipelines, Catalog and SQL; R2 Iceberg tables (formerly Pipelines, R2 Data Catalog, R2 SQL) |
