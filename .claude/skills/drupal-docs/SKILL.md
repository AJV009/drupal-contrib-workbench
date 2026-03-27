---
name: drupal-docs
description: Search and fetch Drupal documentation from drupal.org, api.drupal.org, and drupalatyourfingertips.com. Matches natural language queries against a curated URL catalog covering official docs and community reference guides, then retrieves relevant pages. Use when you need authoritative Drupal documentation or practical code examples.
---

# Drupal Documentation

**Announce at start:** "I'm using the drupal-docs skill to find documentation on [topic]."

Fetch and return Drupal documentation relevant to a query. This skill searches a curated catalog of drupal.org, api.drupal.org, and drupalatyourfingertips.com URLs, identifies the most relevant pages, fetches their full content, and returns it for the calling agent to use.

## Arguments

- `$1` - **Query** (required). A natural language description of what you need to know. Examples:
  - `"entity API field definitions"`
  - `"how to create a custom module"`
  - `"form API validation and submission"`
  - `"routing and controllers"`
  - `"services and dependency injection"`
  - `"configuration management export import"`
  - `"caching strategies and cache tags"`
  - `"Twig theming and templates"`
  - `"hook system event subscribers"`
  - `"automated testing PHPUnit"`
  - `"batch and queue processing"`
  - `"paragraphs module patterns"`
  - `"drush custom commands"`

## Execution

You are a fast research agent. Your job is to find and fetch documentation, not to analyze or act on it. Return the raw content so the calling agent can use it.

### Step 1: Load the URL catalog

Read the URL catalog file at `references/drupal-docs-urls.md` (in this skill's directory). This contains all curated Drupal documentation URLs organized by category, each with a brief description of its content. The catalog includes official drupal.org docs, api.drupal.org references, and community guides from drupalatyourfingertips.com.

### Step 2: Match URLs to the query

From the catalog, identify **all pages relevant** to the query. Match by:

- URL path segments (e.g., query "entity API" matches URLs containing `/entity-api`, `/entity`, `/entities`)
- Description keywords (e.g., query "dependency injection" matches entries described as "Services and dependency injection container")
- Semantic relevance (e.g., query "custom module" matches `/creating-modules`, `/module-file`, `/info-yml`, `/hooks`, `/routing-system`, and also `/modules` from the community catalog)
- Category context (e.g., query "testing" should match entries under the Testing category, plus related entries like coding standards and DTT)

Be generous with matching. It is better to fetch an extra page than to miss a relevant one. But stay focused: do not fetch unrelated categories unless the query is broad.

**Matching guidelines:**
- For API queries, include both the official drupal.org overview and the drupalatyourfingertips.com practical guide
- For "how to" queries, include tutorial/guide pages, the relevant API reference, and the community guide
- For troubleshooting queries, include security pages, change records, and relevant API docs
- Always include the most specific match first, then broaden to related topics
- When a topic exists in both official docs and community guides, include both for completeness

### Step 3: Fetch matched pages

For each matched URL, fetch the URL content to retrieve the page. Fetch pages in parallel where possible for speed.

When fetching, extract the complete content of each page. Return all text, code examples, tables, steps, warnings, and notes. Do not summarize. Return everything.

If a URL redirects, follow the redirect and note the final URL in the output.

### Step 4: Return results

Return all fetched content organized by page, with clear headers:

```
## <Page Title> - <URL>

<full page content>

---

## <Next Page Title> - <URL>

<full page content>
```

If a page fails to load (404, 503, timeout), note the failure and continue with remaining pages. Suggest the user check whether the URL has moved by searching drupal.org directly.

## Tips for effective queries

- **Be specific**: "Form API AJAX callbacks" will yield better results than just "forms"
- **Use Drupal terminology**: "render arrays" not "page rendering", "entity bundles" not "content types API"
- **Combine concepts**: "routing access control" will match both routing and permissions pages
- **Ask about versions**: If you need version-specific docs, mention "Drupal 10" or "Drupal 11" in your query
- **Broader catalog**: The catalog includes both official drupal.org documentation and practical community guides from drupalatyourfingertips.com, so queries will often return complementary perspectives on the same topic

## Catalog maintenance

The URL catalog at `references/drupal-docs-urls.md` is a manually curated list. To maintain it:

- Periodically verify URLs still resolve (drupal.org restructures docs occasionally)
- Add new URLs when major documentation pages are published
- Remove URLs that consistently 404 or redirect to unrelated content
- When Drupal releases a new major version, update api.drupal.org URLs to reference the latest version
- Check drupalatyourfingertips.com for new chapters and add them to the community reference section
