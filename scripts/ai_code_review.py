#!/usr/bin/env python3
"""
AI Code Review Script

Cross-model code review:
- Claude code → o1-preview reviews
- OpenAI code → Claude 4.6 Opus reviews
- Human code → Dual review (both)

Usage:
    python scripts/ai_code_review.py --diff pr.diff --author Claude --pr-number 42
    python scripts/ai_code_review.py --diff pr.diff --author Human --pr-number 42 --dual
"""

import os
import sys
import argparse
from typing import Dict, Optional
import anthropic
import openai
from github import Github


# Model configurations
MODELS = {
    "claude-opus": "claude-opus-4-6",
    "claude-sonnet": "claude-sonnet-4-5-20250929",
    "o1-preview": "o1-preview",
    "o1-mini": "o1-mini",
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
}


def review_with_claude(diff: str, model: str = "claude-opus") -> str:
    """
    OpenAI код → Claude ревьюит

    Args:
        diff: Git diff текст
        model: claude-opus или claude-sonnet

    Returns:
        Review text в Markdown
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""You are reviewing code written by another AI (OpenAI o1/gpt-4o).

**Review Focus Areas:**

1. **Architecture & Design Patterns**
   - SOLID principles violations
   - Coupling/cohesion issues
   - Design pattern misuse

2. **Security (Critical!)**
   - OWASP Top 10 vulnerabilities
   - SQL injection, XSS, CSRF
   - Secrets hardcoded in code
   - 152-ФЗ compliance (Russian data privacy law)

3. **Performance**
   - N+1 database queries
   - Inefficient algorithms (O(n²) where O(n) possible)
   - Missing database indexes
   - Memory leaks (unclosed connections, file handles)

4. **Error Handling**
   - Missing try/catch blocks
   - Swallowed exceptions
   - Unclear error messages
   - No fallback for external API failures

5. **AgentIQ-Specific Rules** (check docs/GUARDRAILS.md, CLAUDE.md)
   - Guardrails rules must NOT be hardcoded
   - Banned phrases must NOT appear in AI-generated responses
   - Quality score formula must be percentage-based (not absolute)
   - WB API pagination must handle duplicates (dedup by fb_id)
   - CLAUDE.md must NEVER be committed

6. **Code Maintainability**
   - Functions >50 lines (consider splitting)
   - Poor naming (unclear variable/function names)
   - Missing docstrings for complex logic
   - Magic numbers (use named constants)

**Code Diff:**
```diff
{diff}
```

**Format Your Review:**

## ✅ Strengths
- [List positive aspects, what's well done]

## ⚠️ Issues Found

### [CRITICAL/HIGH/MEDIUM/LOW] Issue Title
- **Location:** `file.py:42-45`
- **Problem:** [What's wrong]
- **Impact:** [What could go wrong in production]
- **Fix:** [Concrete suggestion with code example if possible]

## 🔒 Security Concerns
- [Any security vulnerabilities - this section is CRITICAL]

## 🚀 Performance
- [Performance issues if any]

## 🎯 AgentIQ Guidelines
- [Violations of project-specific rules from GUARDRAILS.md or CLAUDE.md]

## Overall Decision
[APPROVE / REQUEST_CHANGES / COMMENT]

**Reasoning:** [Brief explanation of decision]
"""

    try:
        response = client.messages.create(
            model=MODELS[model],
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"❌ Claude review failed: {str(e)}"


def review_with_openai(diff: str, use_reasoning: bool = True) -> str:
    """
    Claude код → OpenAI ревьюит

    Args:
        diff: Git diff текст
        use_reasoning: True = o1-preview (reasoning), False = gpt-4o (fast)

    Returns:
        Review text в Markdown
    """
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    model = MODELS["o1-preview"] if use_reasoning else MODELS["gpt-4o"]

    system_prompt = """You are an expert code reviewer focusing on correctness and reliability.

**Your Mission:** Find bugs, edge cases, and potential runtime errors that could break production.

**Review Priorities:**
1. Bugs and edge cases (off-by-one, null pointers, race conditions)
2. Type safety issues (wrong types, missing type checks)
3. Best practices violations (antipatterns)
4. Test coverage gaps (untested edge cases)
5. Security vulnerabilities (injection, auth bypass)
6. Performance issues (N+1 queries, inefficient loops)

**Be Specific:**
- Point to exact line numbers
- Explain WHY it's a problem
- Suggest HOW to fix it (with code if possible)
"""

    user_prompt = f"""Review this code diff:

```diff
{diff}
```

**Review Checklist:**

☐ **Bugs & Edge Cases**
   - Null/undefined handling
   - Array bounds checking
   - Division by zero
   - Race conditions (async code)

☐ **Security**
   - SQL injection (string concatenation in queries)
   - XSS (unsanitized user input)
   - Authentication bypass
   - Sensitive data exposure

☐ **Performance**
   - N+1 database queries
   - Inefficient algorithms
   - Missing indexes
   - Resource leaks

☐ **Error Handling**
   - Unhandled exceptions
   - Missing try/catch
   - Poor error messages

☐ **Testing**
   - Critical paths not tested
   - Missing edge case tests
   - No integration tests for DB changes

☐ **Breaking Changes**
   - API contract changes
   - Database schema changes
   - Removed/renamed functions

**Format:**

## Issues

### [Priority: CRITICAL/HIGH/MEDIUM/LOW] Issue Title
- **Location:** `file.py:42`
- **Problem:** [description]
- **Suggestion:** [how to fix]

## Recommendations
- [General improvements]

## Decision
[APPROVE / REQUEST_CHANGES / COMMENT]
"""

    try:
        if use_reasoning:
            # o1-preview не поддерживает system message
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": user_prompt}]
            )
        else:
            # gpt-4o поддерживает system
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

        return response.choices[0].message.content

    except Exception as e:
        return f"❌ OpenAI review failed: {str(e)}"


def dual_review(diff: str) -> Dict[str, str]:
    """
    Human код → оба AI ревьюят и сравниваем

    Args:
        diff: Git diff текст

    Returns:
        Dict with 'claude' and 'openai' reviews
    """
    print("Running dual review (Claude + o1-preview)...")

    claude_review = review_with_claude(diff, model="claude-sonnet")  # Быстрее Opus
    openai_review = review_with_openai(diff, use_reasoning=True)     # o1 для глубины

    return {
        "claude": claude_review,
        "openai": openai_review
    }


def post_review_to_pr(pr_number: int, reviews, code_author: str):
    """
    Post review comment to GitHub PR

    Args:
        pr_number: PR number
        reviews: String or Dict (dual review)
        code_author: "Claude" / "OpenAI" / "Human"
    """
    gh_token = os.getenv("GITHUB_TOKEN")
    gh_repo = os.getenv("GITHUB_REPOSITORY")

    if not gh_token or not gh_repo:
        print("⚠️ GITHUB_TOKEN or GITHUB_REPOSITORY not set. Skipping PR comment.")
        print("\n--- REVIEW OUTPUT ---\n")
        if isinstance(reviews, dict):
            print(f"### Claude Review:\n{reviews['claude']}\n")
            print(f"### OpenAI Review:\n{reviews['openai']}\n")
        else:
            print(reviews)
        return

    try:
        gh = Github(gh_token)
        repo = gh.get_repo(gh_repo)
        pr = repo.get_pull(pr_number)

        if isinstance(reviews, dict):  # Dual review
            reviewer_models = "Claude 4.5 Sonnet + OpenAI o1-preview"
            comment = f"""## 🤖 AI Code Review (Dual)

### 🔷 Claude 4.5 Sonnet Review
{reviews['claude']}

---

### 🔶 OpenAI o1-preview Review
{reviews['openai']}

---
**Code by:** {code_author}
**Reviewed by:** {reviewer_models}
"""
        else:  # Single review
            if "Claude" in str(reviews) or "claude" in code_author.lower():
                reviewer_model = "Claude 4.6 Opus"
            else:
                reviewer_model = "OpenAI o1-preview"

            comment = f"""## 🤖 AI Code Review

{reviews}

---
**Code by:** {code_author}
**Reviewed by:** {reviewer_model}
"""

        pr.create_issue_comment(comment)
        print(f"✅ Review posted to PR #{pr_number}")

    except Exception as e:
        print(f"❌ Failed to post to PR: {e}")
        print("\n--- REVIEW OUTPUT ---\n")
        if isinstance(reviews, dict):
            print(f"### Claude:\n{reviews['claude']}\n")
            print(f"### OpenAI:\n{reviews['openai']}\n")
        else:
            print(reviews)


def main():
    parser = argparse.ArgumentParser(description="AI Code Review Script")
    parser.add_argument("--diff", required=True, help="Path to diff file")
    parser.add_argument("--author", required=True,
                        help="Code author: Claude / OpenAI / o1 / gpt-4o / Human")
    parser.add_argument("--pr-number", type=int, required=True, help="GitHub PR number")
    parser.add_argument("--dual", action="store_true",
                        help="Use both Claude and o1 (for Human code)")

    args = parser.parse_args()

    # Read diff file
    try:
        with open(args.diff, 'r', encoding='utf-8') as f:
            diff = f.read()
    except FileNotFoundError:
        print(f"❌ Diff file not found: {args.diff}")
        sys.exit(1)

    if not diff.strip():
        print("⚠️ Empty diff. Skipping review.")
        sys.exit(0)

    # Determine review strategy
    author = args.author.lower()

    if args.dual or author == "human":
        print(f"🤖 Running DUAL review for {args.author} code...")
        reviews = dual_review(diff)

    elif "claude" in author:
        print(f"🤖 Running OpenAI o1-preview review for Claude code...")
        reviews = review_with_openai(diff, use_reasoning=True)

    elif any(x in author for x in ["openai", "o1", "gpt"]):
        print(f"🤖 Running Claude 4.6 Opus review for OpenAI code...")
        reviews = review_with_claude(diff, model="claude-opus")

    else:
        print(f"⚠️ Unknown code author: {args.author}. Defaulting to dual review.")
        reviews = dual_review(diff)

    # Post review to PR
    post_review_to_pr(args.pr_number, reviews, args.author)

    print("✅ AI Code Review completed")


if __name__ == "__main__":
    main()
