#!/usr/bin/env python3
"""Generate a self-hosted SVG card from GitHub's API."""

from __future__ import annotations

import html
import json
import os
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


LOGIN = os.environ.get("PROFILE_LOGIN", "yazzy01")
TOKEN = os.environ["GH_TOKEN"]
API = "https://api.github.com"
OUTPUT = Path("assets/profile-metrics.svg")

LANGUAGE_COLORS = {
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Python": "#3572A5",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Java": "#b07219",
    "Shell": "#89e051",
    "Go": "#00ADD8",
    "PHP": "#4F5D95",
    "C++": "#f34b7d",
    "C": "#555555",
    "Jupyter Notebook": "#DA5B0B",
    "Vue": "#41b883",
    "Dart": "#00B4AB",
    "Rust": "#dea584",
}


def api_json(path: str, payload: dict | None = None) -> object:
    url = f"{API}{path}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "User-Agent": "yazzy01-profile-metrics",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def contribution_stats() -> dict:
    now = datetime.now(ZoneInfo("Africa/Casablanca"))
    start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { totalContributions }
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
        }
      }
    }
    """
    result = api_json(
        "/graphql",
        {
            "query": query,
            "variables": {
                "login": LOGIN,
                "from": start.isoformat(),
                "to": now.isoformat(),
            },
        },
    )
    return result["data"]["user"]["contributionsCollection"]


def repository_stats() -> tuple[dict, Counter]:
    profile = api_json(f"/users/{LOGIN}")
    languages: Counter = Counter()
    page = 1
    stars = 0

    while True:
        repos = api_json(
            f"/users/{LOGIN}/repos?type=owner&sort=updated&per_page=100&page={page}"
        )
        if not repos:
            break
        for repo in repos:
            if repo["fork"]:
                continue
            stars += repo["stargazers_count"]
            repo_languages = api_json(f"/repos/{LOGIN}/{repo['name']}/languages")
            languages.update(repo_languages)
        if len(repos) < 100:
            break
        page += 1

    profile["stars"] = stars
    return profile, languages


def text(x: int, y: int, value: object, css_class: str, anchor: str = "start") -> str:
    safe = html.escape(str(value))
    return (
        f'<text x="{x}" y="{y}" class="{css_class}" '
        f'text-anchor="{anchor}">{safe}</text>'
    )


def render(stats: dict, profile: dict, languages: Counter) -> str:
    width = 900
    height = 318
    year = datetime.now(ZoneInfo("Africa/Casablanca")).year
    updated = datetime.now(ZoneInfo("Africa/Casablanca")).strftime("%Y-%m-%d")
    contributions = stats["contributionCalendar"]["totalContributions"]

    values = [
        ("Contributions", contributions),
        ("Commits", stats["totalCommitContributions"]),
        ("Pull requests", stats["totalPullRequestContributions"]),
        ("Public repos", profile["public_repos"]),
        ("Stars earned", profile["stars"]),
    ]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Yassir Rzigui GitHub metrics</title>',
        f'<desc id="desc">Public GitHub activity and language statistics for {year}</desc>',
        "<style>",
        "text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }",
        ".title { fill: #f0f6fc; font-size: 24px; font-weight: 700; }",
        ".subtitle { fill: #8b949e; font-size: 13px; }",
        ".number { fill: #2dd4bf; font-size: 25px; font-weight: 700; }",
        ".label { fill: #8b949e; font-size: 12px; }",
        ".section { fill: #f0f6fc; font-size: 16px; font-weight: 600; }",
        ".language { fill: #c9d1d9; font-size: 12px; }",
        "</style>",
        '<rect x="1" y="1" width="898" height="316" rx="14" fill="#0d1117" stroke="#30363d" stroke-width="2"/>',
        text(32, 42, "GitHub Activity", "title"),
        text(868, 40, f"Updated {updated}", "subtitle", "end"),
        text(32, 64, f"Public profile metrics for {year}", "subtitle"),
    ]

    card_width = 156
    gap = 16
    start_x = 32
    for index, (label, value) in enumerate(values):
        x = start_x + index * (card_width + gap)
        parts.append(
            f'<rect x="{x}" y="86" width="{card_width}" height="78" rx="10" '
            'fill="#161b22" stroke="#30363d"/>'
        )
        parts.append(text(x + 16, 121, value, "number"))
        parts.append(text(x + 16, 145, label, "label"))

    parts.append(text(32, 198, "Most-used languages", "section"))
    top_languages = languages.most_common(6)
    total = sum(value for _, value in top_languages) or 1
    bar_x = 32
    bar_y = 216
    bar_width = 836
    cursor = bar_x

    if top_languages:
        for index, (language, value) in enumerate(top_languages):
            segment = bar_width * value / total
            color = LANGUAGE_COLORS.get(language, "#8b949e")
            radius = 6 if index in (0, len(top_languages) - 1) else 0
            parts.append(
                f'<rect x="{cursor:.2f}" y="{bar_y}" width="{segment:.2f}" '
                f'height="12" rx="{radius}" fill="{color}"/>'
            )
            cursor += segment

        legend_y = 260
        for index, (language, value) in enumerate(top_languages):
            column = index % 3
            row = index // 3
            x = 32 + column * 278
            y = legend_y + row * 28
            percent = value * 100 / total
            color = LANGUAGE_COLORS.get(language, "#8b949e")
            parts.append(
                f'<circle cx="{x + 6}" cy="{y - 4}" r="6" fill="{color}"/>'
            )
            parts.append(text(x + 20, y, f"{language} {percent:.1f}%", "language"))
    else:
        parts.append(text(32, 252, "No public language data available.", "subtitle"))

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    stats = contribution_stats()
    profile, languages = repository_stats()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(stats, profile, languages), encoding="utf-8")
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    main()
