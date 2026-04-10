#!/usr/bin/env python3
"""
Resonance scorer for drupal.org issues.

Given the artifacts of a freshly-fetched issue (issue.json, comments.json,
mr-*-diff.patch, optionally related-issues.json), find other issues — in bd
or on d.o — that look like duplicates, scope expansions, or close relatives.
Emits a JSON report consumed by the drupal-resonance-checker agent.

Architecture:
  Layer A — bd local queries (module label, description, notes matches)
  Layer B — d.o remote queries via `./scripts/fetch-issue --mode search`

Silent degrade: if Layer B fails (network, subprocess error, JSON parse),
continue with Layer A only and note the failure in the report's layer_b
section. Never crashes on network trouble; the hands-free flow keeps moving.

Scoring (deterministic, documented in score_candidate):
  +25 direct cross-reference in issue text (candidate nid mentioned in body/comments)
  +10 same module (bd label match)
  +15 per title keyword overlap (up to 3 keywords, caps at +45)
  +5  time proximity (<30 days)
  +5  per bd desc/notes match reason

Buckets:
  <40  NONE
  40-60 RELATED_TO           (informational, no flow change)
  60-80 SCOPE_EXPANSION_CANDIDATE
  >80  DUPLICATE_OF          (triggers classification category J as top candidate)

The scorer is intentionally conservative: false positives (closing a real bug
as duplicate) are much more costly than false negatives. Nothing in this
module ever auto-closes anything. The report is advisory; the controller
always runs classification after reading it.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
# resonance_search.py lives in .claude/skills/drupal-issue/scripts/
# so workbench root is 4 levels up
WORKBENCH_ROOT = SCRIPT_DIR.parent.parent.parent.parent


# ============================================================================
# Signal extraction from artifacts
# ============================================================================

# Common English stopwords + Drupal-generic noise words that would match
# everything in a drupal project if kept.
STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "when", "where",
    "what", "which", "should", "would", "could", "have", "been", "will",
    "does", "doesn", "not", "add", "fix", "use", "can", "has", "its", "all",
    "are", "was", "were", "but", "into", "over", "any", "per", "you", "your",
    "their", "them", "some", "more", "than", "only", "just", "also", "then",
    "because", "how", "who", "why", "get", "got", "let", "set", "new", "old",
    "bug", "issue", "error", "drupal", "module", "need", "needs", "make",
    "test", "tests", "file", "files", "show", "run", "using", "used",
}


def extract_signals(artifacts_dir: Path) -> Dict:
    """
    Pull scoring signals from the fetched artifacts. Returns a dict with
    everything the scorer needs to compare candidates against this issue.
    """
    issue = {}
    keywords = []
    files: Set[str] = set()
    symbols: Set[str] = set()
    error_messages: Set[str] = set()
    referenced: List[int] = []

    issue_path = artifacts_dir / "issue.json"
    if issue_path.exists():
        d = json.loads(issue_path.read_text(encoding="utf-8"))
        issue = {
            "nid": _to_int(d.get("nid")),
            "title": d.get("title", ""),
            "component": d.get("component", ""),
            "project": d.get("project", ""),
            "version": d.get("version", ""),
            "body_html": d.get("body_html", ""),
        }
        # Module and project are the same thing in this workbench's usage
        issue["module"] = issue["project"]

        keywords = _extract_keywords(issue["title"])
        body = issue["body_html"] or ""
        symbols.update(_extract_symbols(body))
        error_messages.update(_extract_error_messages(body))
        referenced.extend(_extract_issue_refs(body))

    comments_path = artifacts_dir / "comments.json"
    if comments_path.exists():
        d = json.loads(comments_path.read_text(encoding="utf-8"))
        for c in d.get("comments", []):
            body = c.get("body_html", "") or ""
            symbols.update(_extract_symbols(body))
            error_messages.update(_extract_error_messages(body))
            referenced.extend(_extract_issue_refs(body))

    # MR diffs — extract touched file paths and added-code symbols
    for diff_file in artifacts_dir.glob("mr-*-diff.patch"):
        try:
            content = diff_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        files.update(_extract_diff_files(content))
        symbols.update(_extract_diff_symbols(content))

    # Keep only the exclusion-self nid
    current_nid = issue.get("nid")
    referenced = [r for r in referenced if r != current_nid]

    return {
        "issue": issue,
        "keywords": keywords,
        "files": sorted(files),
        "symbols": sorted(symbols),
        "error_messages": sorted(error_messages),
        "referenced_issues": sorted(set(referenced)),
    }


def _to_int(value) -> Optional[int]:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _extract_keywords(text: str) -> List[str]:
    """Extract salient keywords from a title/body string, top ~10."""
    if not text:
        return []
    words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{3,}\b", text.lower())
    seen: Set[str] = set()
    out = []
    for w in words:
        if w in STOPWORDS or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= 10:
            break
    return out


def _extract_symbols(html_or_text: str) -> Set[str]:
    """Extract likely class/function names heuristically."""
    if not html_or_text:
        return set()
    classes = set(re.findall(
        r"\b([A-Z][a-zA-Z0-9_]*[a-z][a-zA-Z0-9_]*(?:[A-Z][a-zA-Z0-9_]*){1,})\b",
        html_or_text,
    ))
    funcs = set(re.findall(
        r"\b([a-z_][a-zA-Z0-9_]{3,})\s*\(",
        html_or_text,
    ))
    # Trim noise
    noise = {"span", "div", "class", "style", "href", "title", "type", "value"}
    return (classes | funcs) - noise


def _extract_error_messages(text: str) -> Set[str]:
    """Extract error-like substrings from HTML or plain text."""
    if not text:
        return set()
    errors = set()
    for m in re.finditer(
        r"(?:Error|Exception|TypeError|Fatal|Warning):\s*([^\n<]{10,120})",
        text,
    ):
        errors.add(m.group(1).strip())
    # Double-quoted capitalized messages (common in issue descriptions)
    for m in re.finditer(r'"([A-Z][^"]{20,120})"', text):
        errors.add(m.group(1).strip())
    return errors


def _extract_issue_refs(text: str) -> List[int]:
    """Extract referenced 7-digit issue NIDs."""
    if not text:
        return []
    refs = []
    for m in re.finditer(r"(?:#|/node/|/issues/)(\d{7})", text):
        refs.append(int(m.group(1)))
    return refs


def _extract_diff_files(diff_content: str) -> Set[str]:
    """Extract new-file-side paths from a unified diff."""
    files = set()
    for m in re.finditer(r"^\+\+\+ b/(.+)$", diff_content, re.MULTILINE):
        path = m.group(1).strip()
        if path and path != "/dev/null":
            files.add(path)
    return files


def _extract_diff_symbols(diff_content: str) -> Set[str]:
    """Extract class/function names from added lines of a diff."""
    symbols = set()
    for line in diff_content.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for m in re.finditer(
            r"\b(?:class|function|interface|trait)\s+([A-Za-z_][A-Za-z0-9_]{3,})",
            line,
        ):
            symbols.add(m.group(1))
    return symbols


# ============================================================================
# Layer A — bd queries
# ============================================================================

def query_bd(signals: Dict) -> List[Dict]:
    """
    Query bd for candidate issues. Returns a list of normalized candidates.

    Each candidate has: bd_id, drupal_id, title, status, labels, source,
    match_reasons.
    """
    candidates: Dict[str, Dict] = {}
    module = signals["issue"].get("module", "")

    def _upsert(item: Dict, reason: str):
        bd_id = item.get("id") or item.get("issue_id") or item.get("ID")
        if not bd_id:
            return
        if bd_id not in candidates:
            candidates[bd_id] = {
                "bd_id": bd_id,
                "drupal_id": _extract_drupal_id(item),
                "title": item.get("title", ""),
                "status": item.get("status", ""),
                "labels": item.get("labels", []),
                "source": "bd-local",
                "match_reasons": [reason],
            }
        else:
            if reason not in candidates[bd_id]["match_reasons"]:
                candidates[bd_id]["match_reasons"].append(reason)

    def _bd_list(args: List[str], reason: str):
        try:
            cmd = ["bd", "list"] + args + ["--format", "json"]
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False, timeout=30
            )
        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
            return
        if result.returncode != 0:
            return
        try:
            data = json.loads(result.stdout) if result.stdout.strip() else []
        except json.JSONDecodeError:
            return
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("issues") or data.get("items") or []
        else:
            return
        for item in items:
            if isinstance(item, dict):
                _upsert(item, reason)

    # Module-label match
    if module:
        _bd_list(["--label", f"module-{module}"], f"label:module-{module}")

    # Description / notes contains for each top keyword
    for kw in signals.get("keywords", [])[:5]:
        _bd_list(["--desc-contains", kw], f"desc:{kw}")
        _bd_list(["--notes-contains", kw], f"notes:{kw}")

    # Drupal ID labels for referenced issues
    for ref in signals.get("referenced_issues", [])[:10]:
        _bd_list(["--label", f"drupal-{ref}"], f"drupal-ref:{ref}")

    return list(candidates.values())


def _extract_drupal_id(bd_item: Dict) -> Optional[int]:
    """Pull drupal issue id from bd item's external_ref or labels."""
    ext = bd_item.get("external_ref", "") or ""
    m = re.search(r"drupal[:\-](\d+)", ext)
    if m:
        return int(m.group(1))
    labels = bd_item.get("labels") or []
    if isinstance(labels, list):
        for label in labels:
            if not isinstance(label, str):
                continue
            m = re.match(r"drupal-(\d+)", label)
            if m:
                return int(m.group(1))
    return None


# ============================================================================
# Layer B — d.o search via fetch-issue
# ============================================================================

def _fetch_issue_search(project: str, keywords: List[str], max_issues: int) -> Tuple[List[Dict], Optional[str]]:
    """One attempt at `fetch-issue --mode search`. Returns (matches, error)."""
    wrapper = WORKBENCH_ROOT / "scripts" / "fetch-issue"
    cmd = [
        str(wrapper),
        "--mode", "search",
        "--project", project,
        "--keywords",
    ] + keywords + [
        "--max-issues", str(max_issues),
        "--out", "-",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=90
        )
    except subprocess.TimeoutExpired:
        return [], "fetch-issue search timed out after 90s"
    except FileNotFoundError:
        return [], f"fetch-issue wrapper not found at {wrapper}"
    except Exception as e:
        return [], f"fetch-issue search failed: {e}"

    if result.returncode != 0:
        return [], (
            f"fetch-issue search exited {result.returncode}: "
            f"{result.stderr.strip()[:200]}"
        )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return [], f"fetch-issue search output is not valid JSON: {e}"
    return data.get("matches", []), None


def _fetch_issue_lookup(project: str, nid: int) -> Optional[Dict]:
    """One attempt at `fetch-issue --mode issue-lookup` for a referenced nid."""
    wrapper = WORKBENCH_ROOT / "scripts" / "fetch-issue"
    cmd = [
        str(wrapper),
        "--mode", "issue-lookup",
        "--issue", str(nid),
        "--project", project,
        "--out", "-",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=30
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def query_drupal_org(
    signals: Dict, max_issues: int = 100
) -> Tuple[List[Dict], Optional[str]]:
    """
    Query d.o for candidate issues via multiple strategies:

    1. Title search with decreasing keyword counts (3 → 2 → 1) until a non-zero
       result set is found or we run out of keywords.
    2. Direct issue-lookup for every referenced issue nid in the current issue
       (comments + body). Referenced issues get a high-confidence tag because
       the author literally cited them.

    Silent degrade: returns (candidates, error_message). If both strategies
    fail, the caller still emits a report with Layer B marked degraded.
    """
    project = signals["issue"].get("project", "")
    if not project:
        return [], "no project name in issue signals"

    current_nid = signals["issue"].get("nid")
    seen_nids: Set[int] = set()
    candidates: List[Dict] = []
    errors: List[str] = []

    # Strategy 1: explicit referenced-issue lookups (strongest signal)
    for ref_nid in signals.get("referenced_issues", []):
        if ref_nid == current_nid or ref_nid in seen_nids:
            continue
        lookup = _fetch_issue_lookup(project, ref_nid)
        if not lookup:
            continue
        seen_nids.add(ref_nid)
        candidates.append({
            "bd_id": None,
            "drupal_id": ref_nid,
            "title": lookup.get("title", ""),
            "status": lookup.get("status", {}).get("label", "") if isinstance(lookup.get("status"), dict) else "",
            "changed": lookup.get("changed", ""),
            "source": "drupal-org",
            "match_reasons": ["explicit-reference-lookup"],
            "url": lookup.get("url", ""),
        })

    # Strategy 2: title search with keyword-count fallback
    keywords = signals.get("keywords", [])
    if not keywords:
        return candidates, None if candidates else "no keywords extracted from issue title"

    matches: List[Dict] = []
    used_keywords: List[str] = []
    last_error: Optional[str] = None

    for k in (3, 2, 1):
        attempt_keywords = keywords[:k]
        if not attempt_keywords:
            continue
        result, err = _fetch_issue_search(project, attempt_keywords, max_issues)
        if err:
            last_error = err
            continue
        if result:
            matches = result
            used_keywords = attempt_keywords
            break

    if last_error and not matches:
        errors.append(last_error)

    for match in matches:
        nid = match.get("nid")
        if not nid:
            continue
        if current_nid and nid == current_nid:
            continue
        if nid in seen_nids:
            continue
        seen_nids.add(nid)
        candidates.append({
            "bd_id": None,
            "drupal_id": nid,
            "title": match.get("title", ""),
            "status": match.get("status_label", ""),
            "changed": match.get("changed", ""),
            "source": "drupal-org",
            "match_reasons": [f"title:{'+'.join(used_keywords)}"],
            "url": match.get("url", ""),
        })

    error_msg = "; ".join(errors) if errors else None
    return candidates, error_msg


# ============================================================================
# Scoring + bucketing
# ============================================================================

def score_candidate(candidate: Dict, signals: Dict) -> Tuple[int, List[str]]:
    """
    Compute a confidence score and list of scoring reasons for a candidate.

    See module docstring for the signal weights. The scorer is deterministic
    and does not call any LLM.
    """
    score = 0
    reasons = []

    cand_drupal = candidate.get("drupal_id")
    referenced = signals.get("referenced_issues", [])
    if cand_drupal and cand_drupal in referenced:
        score += 25
        reasons.append("direct cross-reference in issue text")

    match_reasons = candidate.get("match_reasons", [])
    if any(r.startswith("label:module-") for r in match_reasons):
        score += 10
        reasons.append("same module (bd label match)")

    # Title keyword overlap (especially valuable for d.o candidates where
    # the match_reason is already title-based but we want to weight the
    # number of overlapping keywords).
    cand_title_kw = set(_extract_keywords(candidate.get("title", "")))
    our_kw = set(signals.get("keywords", []))
    overlap = cand_title_kw & our_kw
    if overlap:
        score += 15 * min(len(overlap), 3)  # cap at +45
        reasons.append(
            f"title keyword overlap ({len(overlap)}): {', '.join(sorted(overlap)[:5])}"
        )

    # Time proximity (<30 days)
    changed_str = candidate.get("changed", "")
    if changed_str:
        try:
            changed_dt = datetime.fromisoformat(changed_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            days_ago = (now - changed_dt).days
            if 0 <= days_ago <= 30:
                score += 5
                reasons.append(f"recent activity ({days_ago}d ago)")
        except (ValueError, TypeError):
            pass

    # bd desc/notes contains — each adds a small bump
    for r in match_reasons:
        if r.startswith("desc:") or r.startswith("notes:"):
            score += 5
            reasons.append(f"bd {r}")

    return score, reasons


def bucket_for_score(score: int) -> str:
    if score >= 80:
        return "DUPLICATE_OF"
    if score >= 60:
        return "SCOPE_EXPANSION_CANDIDATE"
    if score >= 40:
        return "RELATED_TO"
    return "NONE"


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Resonance scorer for drupal.org issues — ticket 029",
    )
    parser.add_argument(
        "--artifacts-dir",
        required=True,
        help="Path to DRUPAL_ISSUES/{id}/artifacts/",
    )
    parser.add_argument(
        "--out",
        default="-",
        help="Output path or '-' for stdout JSON (default: stdout)",
    )
    parser.add_argument(
        "--max-do-candidates",
        type=int,
        default=100,
        help="Max d.o candidates to scan in Layer B (default: 100)",
    )
    args = parser.parse_args()

    artifacts = Path(args.artifacts_dir)
    if not artifacts.is_dir():
        print(f"ERROR: artifacts dir not found: {artifacts}", file=sys.stderr)
        sys.exit(2)

    signals = extract_signals(artifacts)

    layer_a_candidates = query_bd(signals)
    layer_b_candidates, layer_b_error = query_drupal_org(
        signals, max_issues=args.max_do_candidates
    )

    # Merge + dedupe by drupal_id (bd-local takes precedence when both exist)
    seen_drupal: Set[int] = set()
    merged: List[Dict] = []
    for c in layer_a_candidates:
        merged.append(c)
        if c.get("drupal_id"):
            seen_drupal.add(c["drupal_id"])
    for c in layer_b_candidates:
        if c.get("drupal_id") and c["drupal_id"] in seen_drupal:
            continue
        merged.append(c)

    # Score each candidate
    scored: List[Dict] = []
    for c in merged:
        score, reasons = score_candidate(c, signals)
        c["confidence"] = score
        c["bucket"] = bucket_for_score(score)
        c["score_reasons"] = reasons
        scored.append(c)

    scored.sort(key=lambda x: (-x["confidence"], x.get("drupal_id") or 0))

    buckets = {
        "DUPLICATE_OF": [],
        "SCOPE_EXPANSION_CANDIDATE": [],
        "RELATED_TO": [],
        "NONE": [],
    }
    for c in scored:
        buckets[c["bucket"]].append(c)

    report = {
        "issue": {
            "drupal_id": signals["issue"].get("nid"),
            "project": signals["issue"].get("project"),
            "title": signals["issue"].get("title"),
            "component": signals["issue"].get("component"),
            "version": signals["issue"].get("version"),
        },
        "signals_used": {
            "keywords": signals["keywords"],
            "files": signals["files"][:10],
            "symbols": signals["symbols"][:10],
            "error_messages": signals["error_messages"][:5],
            "referenced_issues": signals["referenced_issues"],
        },
        "layer_a": {
            "source": "bd-local",
            "candidate_count": len(layer_a_candidates),
            "status": "ok",
        },
        "layer_b": {
            "source": "drupal-org",
            "candidate_count": len(layer_b_candidates),
            "status": "degraded" if layer_b_error else "ok",
            "error": layer_b_error,
        },
        "total_candidates": len(merged),
        "bucket_counts": {k: len(v) for k, v in buckets.items()},
        "candidates": scored,
    }

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out == "-":
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
    else:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")

    # Summary line to stderr so callers see a quick status
    print(
        f"RESONANCE: bd={len(layer_a_candidates)} do={len(layer_b_candidates)} "
        f"total={len(merged)} "
        f"dup={len(buckets['DUPLICATE_OF'])} "
        f"sec={len(buckets['SCOPE_EXPANSION_CANDIDATE'])} "
        f"rel={len(buckets['RELATED_TO'])} "
        f"layer_b={'ok' if not layer_b_error else 'degraded'}",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
