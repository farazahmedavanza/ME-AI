---
name: supabase-agent-skills
description: Installs and applies official Supabase Agent Skills from the supabase/agent-skills GitHub repo using the Vercel skills CLI. Use when the user wants Supabase-specific agent guidance, asks to add or update Supabase skills, or works with Supabase Database, Auth, RLS, Edge Functions, Realtime, migrations, or Postgres performance in Cursor.
---

# Supabase Agent Skills (npx skills)

Official instructions live in the [supabase/agent-skills](https://github.com/supabase/agent-skills) repo and [Supabase AI Skills docs](https://supabase.com/docs/guides/getting-started/ai-skills). This skill tells you **when and how to install** those bundles so the agent can rely on them.

## When to use this

- The user asks to add Supabase skills, or references `npx skills add supabase/agent-skills`.
- Work touches Supabase products (DB, Auth, Edge Functions, Realtime, Storage, vectors, CLI, MCP) and you want the repo’s packaged `SKILL.md` sets instead of re-deriving everything from memory.
- You need only Postgres tuning: consider installing the postgres skill alone (see below).

## Install (project)

From the project root (where `.skills.json` / lockfile should live if the team uses the CLI):

```bash
npx skills add supabase/agent-skills
```

Use `-y` so the skills CLI does not stop at the interactive “select skills” prompt (separate from `npx --yes`):

```bash
npx skills@latest add supabase/agent-skills -y
```

Prefer `@latest` when the CLI’s behavior or install paths change between releases.

## Install (single skill)

```bash
npx skills add supabase/agent-skills --skill supabase
npx skills add supabase/agent-skills --skill supabase-postgres-best-practices
```

| Skill | Use when |
|--------|----------|
| `supabase` | Any Supabase product, client/SSR, Auth/RLS, CLI, migrations, extensions. |
| `supabase-postgres-best-practices` | SQL, indexes, performance, RLS, pooling, schema review. |

## User-wide (optional)

If the user wants skills available in every workspace, use the CLI’s global install flags (e.g. `-g`) and target Cursor if the installed `skills` version supports `--agent cursor`. After install, confirm where files landed with `npx skills list` and that **Cursor** is loading from its documented skill directory (commonly `~/.cursor/skills` for user skills and `.cursor/skills` in the repo for project skills).

## After install

- The skills CLI usually materializes each bundle under **`.agents/skills/<skill-name>`** in the project (e.g. `supabase`, `supabase-postgres-best-practices`) and may also sync copies for Cursor and other agents. Run `npx skills list` to confirm.
- The agent should **read** the installed `SKILL.md` and any `references/` when the task matches that skill’s description.
- For more community skills: `npx skills find <query>` and [skills.sh](https://skills.sh/).

## Not in scope here

- **Claude Code** plugin path (`/plugin install …`) is separate; use the `bash` commands above for the skills CLI in terminal workflows.
