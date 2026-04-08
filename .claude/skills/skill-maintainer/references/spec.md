# Agent Skills Specification (mirror)

Source: https://agentskills.io/specification (fetched 2026-04)

This file mirrors the key rules so you don't need to re-fetch the spec
every time. If the upstream spec changes, update this file.

## Directory structure

A skill is a directory containing, at minimum, a `SKILL.md` file:

```
skill-name/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
├── assets/           # Optional: templates, resources
└── ...               # Any additional files or directories
```

The directory name MUST match the `name` field in the frontmatter.

## Frontmatter fields

| Field | Required | Constraints |
|---|---|---|
| `name` | Yes | 1-64 chars, lowercase alphanumerics + hyphens, no leading/trailing/consecutive hyphens, must match parent directory |
| `description` | Yes | 1-1024 chars, non-empty, describes both what the skill does and when to use it |
| `license` | No | License name or reference to a bundled license file |
| `compatibility` | No | 1-500 chars, environment requirements (product, system packages, network) |
| `metadata` | No | Arbitrary key-value map for properties outside the spec |
| `allowed-tools` | No | Space-delimited list of pre-approved tools (experimental, implementation-dependent) |

### `name` — detailed rules

- 1-64 characters
- Only unicode lowercase alphanumerics (`a-z`, `0-9`) and hyphens (`-`)
- Must NOT start or end with a hyphen
- Must NOT contain consecutive hyphens (`--`)
- Must match the parent directory name exactly

Valid: `pdf-processing`, `data-analysis`, `code-review`, `skill-maintainer`
Invalid: `PDF-Processing` (uppercase), `-pdf` (leading hyphen), `pdf--processing` (double hyphen)

### `description` — detailed rules

- 1-1024 characters
- Describes BOTH what the skill does AND when to use it
- Should include specific keywords that help agents identify relevant tasks
- Multi-line YAML is fine; use folded (`>`) form unless you need preserved newlines

Good:

```yaml
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.
```

Bad:

```yaml
description: Helps with PDFs.
```

### `compatibility` — when to include

Most skills do NOT need this field. Include only for real env requirements:

```yaml
compatibility: Requires DDEV, docker, composer, and network access to drupal.org
compatibility: Requires Python 3.14+ and uv
compatibility: Designed for Claude Code (or similar products)
```

### `metadata` — house style for this workspace

Use `metadata.author` and `metadata.version` when editing workspace skills:

```yaml
metadata:
  author: ajv009
  version: "1.1.0"
```

Bump the version string when you make a non-trivial change.

### `allowed-tools` — experimental, generally skip

Spec marks this as experimental. Support varies between agent
implementations. In this workspace only `agent-browser` uses it (to
pre-approve `Bash(agent-browser:*)`). Do not add to other skills unless
the user explicitly asks.

## Body content

The Markdown body after the frontmatter contains the skill instructions.
There are no format restrictions, but the spec recommends:

- Step-by-step instructions
- Examples of inputs and outputs
- Common edge cases

**The entire body loads into context when the skill activates.** This is
the critical constraint that drives everything else in this file.

## Length recommendations

From the spec's "Progressive disclosure" section:

1. **Metadata (~100 tokens)**: `name` and `description` loaded for all
   skills at startup.
2. **Instructions (<5,000 tokens recommended)**: Full SKILL.md body loaded
   when skill activates.
3. **Resources (as needed)**: Files in `scripts/`, `references/`, `assets/`
   loaded only when the agent decides to open them.

**Hard recommendation: SKILL.md under 500 lines.** Move detailed reference
material to separate files in `references/`.

Enforcement in this workspace:

- **Workflow skills** (`drupal-contribute-fix`, `drupal-issue`,
  `drupal-issue-review`, `drupal-issue-comment`, `skill-maintainer`): stay
  under 500 lines. If you're approaching the limit, look for duplication,
  historical narration, or content that belongs in `references/`.
- **Tool reference skills** (`agent-browser`): can exceed 500 lines when
  the length reflects the tool's actual surface area. Document why in the
  skill itself so a future session knows it's intentional.

## File references

When referencing other files in your skill, use relative paths from the
skill root:

```markdown
See [the reference guide](references/REFERENCE.md) for details.

Run the extraction script:
scripts/extract.py
```

**Keep file references one level deep from SKILL.md.** Avoid deeply
nested reference chains. Exception: when a taxonomy is conceptually
load-bearing (e.g., `drupal-coding-standards/assets/standards/php/coding.md`
where `php` is a conceptual category the agent navigates).

## Progressive disclosure — how the agent decides what to load

From the spec's "How skills work":

1. **Discovery**: Agent scans skill directories at session start, reads
   ONLY `name` and `description` for each skill.
2. **Activation**: When a user request matches a skill's description, the
   agent loads the full SKILL.md body.
3. **Execution**: The agent follows SKILL.md instructions and opens
   `references/`, `scripts/`, `assets/` files only when SKILL.md tells it
   to.

This means:

- Your `description` is the ENTIRE trigger surface. It must contain the
  keywords agents will match against user requests. Be specific.
- Your SKILL.md body competes for context against everything else in the
  session. Every token matters.
- Your reference files are free (loaded on demand) IF SKILL.md has clear
  triggers for when to load them. A generic "see references/ for details"
  wastes the reference file because the agent doesn't know when to open it.

## Validation

This workspace has a validator at
`.claude/skills/skill-maintainer/scripts/validate.py` that checks every
skill for:

- Frontmatter parses as YAML
- `name` format valid, matches directory, ≤64 chars
- `description` non-empty, ≤1024 chars
- `compatibility` ≤500 chars (if present)
- `metadata` is a mapping (if present)
- SKILL.md line count ≤500 (warning, not error; tool-reference skills may
  accept the warning)

Run after every non-trivial edit:

```bash
python3 .claude/skills/skill-maintainer/scripts/validate.py
```

The upstream reference validator is at
https://github.com/agentskills/agentskills/tree/main/skills-ref (not
installed by default in this workspace; the local Python validator covers
the same rules).
