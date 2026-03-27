# TICKET-012: Use Chrome MCP Tools Instead of Playwright for Screenshots

**Status:** COMPLETED
**Priority:** P2 (Medium)
**Affects:** `.claude/skills/drupal-issue-review/SKILL.md`, `.claude/skills/drupal-issue-comment/SKILL.md`
**Type:** Enhancement

## Problem

Both `drupal-issue-review` and `drupal-issue-comment` skills suggest installing Playwright for taking screenshots:

```bash
npm init -y && npm install playwright
npx playwright install chromium
# Write script to navigate + screenshot
```

This is slow (~30-60 seconds to install), requires Node.js in the DDEV environment, and is unnecessary because Chrome MCP tools (`mcp__claude-in-chrome__*`) are already available in the session.

Chrome MCP provides:
- `mcp__claude-in-chrome__navigate` - Navigate to URL
- `mcp__claude-in-chrome__computer` - Take screenshots, click, type
- `mcp__claude-in-chrome__read_page` - Read page content
- `mcp__claude-in-chrome__gif_creator` - Record GIF of multi-step interactions

## Current Behavior

Skills instruct:
1. Install Playwright in the project directory
2. Write a Node.js script to navigate and screenshot
3. Execute the script
4. Save screenshots to `DRUPAL_ISSUES/{id}/screenshots/`

## Desired Behavior

Skills instruct:
1. Use `ddev drush uli` to get a login URL
2. Use Chrome MCP `navigate` to open the DDEV site
3. Use Chrome MCP `computer` with screenshot action to capture pages
4. Save screenshots to `DRUPAL_ISSUES/{id}/screenshots/`

## Benefits

- **Speed:** No npm install, no Playwright download (~60 seconds saved)
- **Reliability:** Chrome MCP is already loaded and available
- **Interactivity:** Can interact with the page (fill forms, click buttons, not just screenshot)
- **GIF recording:** Can record multi-step workflows as GIFs for issue comments
- **No environment pollution:** No node_modules added to the project

## Implementation Plan

### 1. Update `drupal-issue-review` screenshot section

Replace Playwright instructions with:

```markdown
## Capturing Evidence (Screenshots)

Use Chrome MCP tools for screenshots and page interaction:

1. Get login URL:
   ```bash
   ddev drush uli
   ```

2. Navigate to the site:
   - Use mcp__claude-in-chrome__navigate with the uli URL

3. Navigate to the relevant page:
   - Use mcp__claude-in-chrome__navigate to the specific route

4. Take screenshot:
   - Use mcp__claude-in-chrome__computer with action: screenshot
   - Save to DRUPAL_ISSUES/{issue_id}/screenshots/{num}-{description}.png

5. For multi-step reproduction:
   - Use mcp__claude-in-chrome__gif_creator to record the workflow
   - Save as DRUPAL_ISSUES/{issue_id}/screenshots/{description}.gif

### Fallback (if Chrome MCP unavailable)
If Chrome MCP tools are not available (no browser connected), fall back
to Playwright installation. But prefer Chrome MCP when available.
```

### 2. Update `drupal-issue-comment` screenshot section

Update the screenshot embedding instructions:

```markdown
## Screenshot Capture

Prefer Chrome MCP tools over Playwright:
1. mcp__claude-in-chrome__computer (screenshot action) for single captures
2. mcp__claude-in-chrome__gif_creator for multi-step workflows

Screenshots should still be saved to:
  DRUPAL_ISSUES/{issue_number}/screenshots/{num}-{description}.png

For embedding in comments, the format remains:
  <img src="/files/issues/YYYY-MM-DD/{filename}" alt="{description}" />
```

### 3. Keep Playwright as fallback

Don't remove Playwright instructions entirely. Some sessions may not have Chrome MCP available (e.g., running headless, no browser extension). Add a decision point:

```markdown
## Screenshot Tool Selection

1. Check if Chrome MCP is available (mcp__claude-in-chrome__tabs_context_mcp)
2. If available: use Chrome MCP (preferred)
3. If not available: install and use Playwright (fallback)
```

## Acceptance Criteria

- [ ] Skills prefer Chrome MCP over Playwright for screenshots
- [ ] Playwright remains as fallback when Chrome MCP unavailable
- [ ] Screenshot file naming convention unchanged
- [ ] GIF recording documented for multi-step reproductions
- [ ] No npm install required when Chrome MCP is available

## Files to Modify

1. `.claude/skills/drupal-issue-review/SKILL.md` - Replace Playwright with Chrome MCP (primary), Playwright (fallback)
2. `.claude/skills/drupal-issue-comment/SKILL.md` - Update screenshot capture section
