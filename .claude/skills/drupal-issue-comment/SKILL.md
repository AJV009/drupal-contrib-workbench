---
name: drupal-issue-comment
description: >
  Draft a drupal.org issue comment after reproducing or investigating a bug.
  Use when the user has finished reproducing an issue and wants to write up
  findings as a comment on the d.o issue queue. Covers screenshot capture,
  HTML formatting for the d.o comment box, and conversational tone.
license: GPL-2.0-or-later
metadata:
  author: ajv009
  version: "1.0.0"
---

# drupal-issue-comment

**Announce at start:** "I'm using the drupal-issue-comment skill to draft the d.o comment."

> **IRON LAW:** NO SELF-CONGRATULATORY FILLER IN COMMENTS. Never mention passing tests, PHPCS results, or how clean your code is. Let the MR speak for itself.

> **IRON LAW:** NO EM DASHES, EN DASHES, OR DOUBLE HYPHENS. They look AI-generated. Use commas, colons, semicolons, or periods instead.

## Gotchas

- **drupal.org accepts Filtered HTML only.** Supported tags: `<h2>-<h6>`,
  `<em>`, `<strong>`, `<pre>`, `<code>`, `<del>`, `<img>`, `<blockquote>`,
  `<q>`, `<a>`, `<ul>/<ol>/<li>`, `<dl>/<dt>/<dd>`. No `<style>`, `<head>`,
  `<script>`, `<!DOCTYPE>`. Unknown tags are silently stripped.
- **`[#NNNNNN]` auto-links to the issue.** `#NNNNNN` on its own does not.
  Use the brackets every time.
- **Screenshot paths include the upload date.** After uploading to d.o,
  the file lives at `/files/issues/YYYY-MM-DD/filename.png` where the date
  is the day you uploaded (today), not the issue creation date.
- **Never add `Co-Authored-By: Claude ...` to drupal.org commits.** Different
  norms than GitHub. The transparency note in the comment body is the
  correct disclosure on d.o.
- **`tui.json` entry is pre-created.** `drupal-issue.sh` creates the
  numeric-issue entry with an `issue-page` action. Only APPEND the comment
  action — never overwrite or remove the pre-existing entries.
- **Author comment #9 pattern ≠ humility.** "Happy to change X if you want"
  on incomplete work defers scoping to the reviewer. Finish mechanical
  follow-throughs (tests, standards, naming) before drafting, not after.

## Called From

This skill is invoked as the final step by:
- `/drupal-issue` (category F: reply with context, category I: re-review)
- `/drupal-issue-review` (step 5: draft a comment after reproduction)
- `/drupal-contribute-fix` (after pushing, to document changes on the issue)

It is a terminal skill with no handoff to a next skill. Its output is the `.html` comment file at `DRUPAL_ISSUES/{issue_number}/issue-comment-{issue_number}.html`.

Write a drupal.org issue queue comment after reproducing or investigating a bug.

## When to use

- After reproducing a d.o issue locally
- When the user says "write up the findings", "comment on the issue", "draft a reply"
- When test results, screenshots, or analysis need to be packaged for d.o

## Comment style

The comment goes into a Drupal.org issue comment box which accepts **Filtered HTML**.
It is NOT a report, NOT a README, NOT documentation. It is a conversation with other
contributors on the issue.

### Tone

- **Conversational.** Write as if you're a contributor replying to another contributor.
- Address people by their d.o username with `@username`.
- Say "Hey @person, I tried X and here's what I found" not "Section 1: Findings".
- When someone couldn't reproduce or got different results, don't say "why they failed".
  Instead say "could you try this?" or "this is what worked for me".
- Be helpful, not authoritative. Suggest, don't lecture.
- Keep it concise. Contributors are busy.

### Humility over showmanship

- **Never write sentences that prove your work is superior or correct.** Let the
  diff speak for itself. Don't say "this does exactly what X suggested" or
  "this is the right approach". Just state what you did.
- **No self-congratulatory filler.** Lines like "Minimal diff, easy to read,
  does the job" or "Clean, simple, works perfectly" are garbage. Cut them.
- **Don't advertise your own quality checks.** Never mention that tests pass,
  PHPCS is clean, or that you ran linting. The MR pipeline shows that. Lines
  like "Existing tests still pass, PHPCS clean" read as boasting. If you wrote
  tests, say you added them. Don't narrate that they pass.
- **Offer to revert completed work. Do NOT defer incomplete work.**
  There is a sharp line between these two patterns, and only one is
  legitimate humility:
  - **OK** (reverting completed work): "happy to revert this if you
    prefer the previous approach". You did the work, reviewed it,
    pushed it, and are offering to undo it if the reviewer disagrees.
    This respects the reviewer's authority over the final shape.
  - **NOT OK** (deferring incomplete work): "did not add a kernel test,
    happy to add one if you want", "didn't nest the new fields to match
    the upstream convention, say the word if you'd rather have
    consistency", "will open an MR if preferred". This turns the
    reviewer into your PM and asks them to do the scoping work you
    should have done before posting.

  Rule of thumb for deciding: if the work is within the scope of the
  already-touched files, is mechanical (no new design decisions), or
  is a standard follow-through (tests, standards compliance, naming
  consistency with existing conventions), DO IT before posting. If the
  work genuinely needs a policy choice from the maintainer (a magic
  number, an API shape, a user-visible name), state the choice you
  made and the reasoning as a FACT ("picked 2 as one nudge, one retry,
  then release") rather than framing it as an open question. If the
  reviewer disagrees, they will say so; that is what the review is
  for.

- **No "separate follow-up" language without a linked issue AND a
  completed pre-follow-up search.** Saying "I'll file a separate issue
  for X" without a link is a smell: either it should already be filed
  (paste the link), or X belongs in this MR. Before mentioning any
  follow-up in a comment, run the three-part pre-follow-up search from
  `drupal-issue` Q10 (issue queue, existing MRs, existing code pattern
  in the same codebase) and state what was searched so the reviewer
  knows the check was done.

- **State facts, not opinions about your own work.** "Added strtolower to the
  array_map chains" is a fact. "This is much cleaner" is self-promotion.

### What NOT to do

- No `<style>` tags, no CSS, no `<head>`, no `<!DOCTYPE>`.
- No section headers like "## Root Cause Analysis". This isn't a paper.
- No summary tables or status badges.
- No over-engineering. It's a comment box, not a landing page.
- Don't repeat the entire issue description back. People can read the thread.
- **Never use em dashes (—), en dashes (–), or double hyphens (--).**
  They look AI-generated. Restructure the sentence instead: use commas,
  colons, semicolons, periods, or parentheses. Write like a normal person.
- **Don't glorify or over-praise other people's work.** A one-liner like
  "looks good" is fine. Don't write paragraphs listing everything they did
  right. If someone already reviewed it, don't repeat their review.
- **Don't repeat yourself.** If you mention a caveat or dependency earlier
  in the comment, don't restate it at the end as a "summary" or "note".
  Say it once, in the right place. No recap paragraphs.
- **Don't pad with filler.** If your actual content is three sentences,
  the comment should be three sentences. Don't stretch it to look thorough.
- **Don't narrate implementation details nobody asked for.** If you pushed
  a commit, the diff shows what changed. Don't write paragraphs explaining
  which method you called or why you chose one cache tag over another. One
  sentence per change is enough: "Split the NULL/disabled branches in
  blockAccess()" not a 200-word essay about addCacheableDependency behavior.
  If a reviewer needs to understand the change, they will read the diff.
- **Contribute substance, not commentary.** Instead of writing prose about
  what someone else's code does, contribute something concrete: a test that
  was missing, a reproduction script, a screenshot, a CI artifact link.
  Marcus's comment "Added a functional js test" with video/screenshot links
  moved the issue forward more than 2000 characters of cache tag analysis.
  Ask yourself: "Does this comment move the issue closer to being committed,
  or does it just show that I understood the code?" If the latter, cut it.

## Allowed HTML tags

Drupal.org Filtered HTML supports:

```
<h2> <h3> <h4> <h5> <h6> <em> <strong> <pre> <code> <del>
<img> <blockquote> <q> <a> <ul> <ol> <li> <dl> <dt> <dd>
```

Issue references auto-link: `[#1234567]` becomes a clickable link to that issue.

## Screenshots

### Capturing

Use `agent-browser` (installed at `~/.cargo/bin/agent-browser`, headless, no npm/node needed).
For the full command reference, see the `agent-browser` skill at `.claude/skills/agent-browser/SKILL.md`.

```bash
# Login to DDEV site
ULI=$(ddev drush uli --no-browser 2>/dev/null)
agent-browser open "$ULI"
agent-browser wait --load networkidle

# Navigate and screenshot each relevant page
agent-browser open "https://d{issue_id}.ddev.site/path/to/page"
agent-browser wait --load networkidle
agent-browser screenshot --full "DRUPAL_ISSUES/{issue_number}/screenshots/01-page-name.png"

# For before/after comparisons
agent-browser screenshot "DRUPAL_ISSUES/{issue_number}/screenshots/before.png"
# ... apply fix, reload ...
agent-browser reload && agent-browser wait --load networkidle
agent-browser screenshot "DRUPAL_ISSUES/{issue_number}/screenshots/after.png"

# Always close when done
agent-browser close
```

Name screenshots with numbered prefixes and descriptive slugs:
```
01-form-display.png
02-widget-settings.png
03-error-triggered.png
04-watchdog-detail.png
```

### Where to save

Store screenshots under the issue working directory:

```
DRUPAL_ISSUES/{issue_number}/screenshots/
```

### Embedding in the comment

Screenshots get uploaded to the d.o issue as file attachments. Once uploaded,
they live at a predictable path. Embed them in the comment HTML like:

```html
<img src="/files/issues/YYYY-MM-DD/03-error-triggered.png" alt="AJAX error after clicking the automator button" />
```

- Use the **date the files were uploaded** (today's date) in the path.
- Always include meaningful `alt` text describing what the screenshot shows.
- Add a short line of context before each image so people know what they're looking at:

```html
<p>Error after clicking the automator button:</p>
<img src="/files/issues/2026-03-21/03-error-triggered.png" alt="AJAX error after clicking automator button" />
```

Don't dump all screenshots at the end in a "Screenshots" section. Inline them
where they're relevant in the flow of the comment.

## Linking related issues

Drupal.org auto-links issue numbers in square brackets. Use this format:

```
[#3558728]
```

When mentioning a related issue, briefly say what it covers so people don't have
to click through:

```
(related to [#3558728] which covers the same calculateDependencies() crash for $field_name)
```

Search drupal.org before drafting to find related/duplicate issues. Check if
the problems you discovered during reproduction already have open issues.

## Structure of a good comment

A typical comment flows like this (but don't use these as literal headers):

1. **Greeting + context** - "Hey @person, I reproduced this on X environment..."
2. **Confirmation** - "I can confirm the error" + the error message in `<pre>`
3. **Relevant screenshots** - inlined where they make sense
4. **Analysis** - what you found, confirming or adding to existing analysis
5. **Response to previous commenter** - if someone had trouble, help them out
6. **Reproduction steps** - what worked for you, as an `<ol>`
7. **Recommendation** - what should happen next with the issue/MR

## Transparency note

If the reproduction and comment drafting were done with AI assistance, add a
brief italic+bold note at the end disclosing this. Be honest, humble, and make
it clear this is not AI slop. Keep it to 2-3 lines max:

```html
<em><strong>Transparency note:</strong> This research and comment were drafted
with highly supervised usage of Claude Code. Not here to waste anyone's efforts
or demean the work being done, and definitely not posting AI slop. I verified
everything personally. If I'm not doing something right process-wise, please
flag it, would be more than happy to course correct.</em>
```

## No Co-Authored-By on drupal.org

**Never** add `Co-Authored-By: Claude ...` (or any AI co-author tag) to commit
messages or MR descriptions on drupal.org. The transparency note in the comment
is sufficient disclosure. The co-author tag is fine on GitHub and other forges,
but d.o is a different community with different norms.

## Output

The final output is a single `.html` file saved at:

```
DRUPAL_ISSUES/{issue_number}/issue-comment-{issue_number}.html
```

This file contains ONLY the comment body HTML, no wrapper, no doctype, no head.
Ready to copy-paste into the d.o comment box.

## TUI Browser Integration (MANDATORY)

After writing the comment HTML file, append a comment action to the issue's
entry in `CONTRIB_WORKBENCH/tui.json`. The entry is pre-created by
`drupal-issue.sh`; only append, never overwrite existing actions like
`issue-page`.

Action format (append to the `actions` array of the numeric issue key):

```json
{ "id": "comment", "label": "Comment", "icon": "comment", "type": "file-open", "path": "/absolute/path/to/DRUPAL_ISSUES/{issue_number}/issue-comment-{issue_number}.html" }
```

Rules: `type` must be `file-open`, `path` must be absolute (not relative),
issue key is the numeric ID (e.g., `"3508503"`). Skipping this step means
the contributor loses one-click access to the comment from TUI Browser's
terminal toolbar.
