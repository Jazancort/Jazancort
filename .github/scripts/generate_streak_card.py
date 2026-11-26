#!/usr/bin/env python3
"""Generate profile-summary-card-output/streak.svg from GitHub GraphQL API."""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER = os.environ.get("GITHUB_USER", "Jazancort")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_PATH = Path("profile-summary-card-output/streak.svg")


def graphql(query: str, variables: dict | None = None) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Jazancort-Profile-Cards",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request("https://api.github.com/graphql", data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    return data["data"]


def fetch_all_days(username: str) -> tuple[int, list[tuple[str, int]]]:
    info = graphql(
        """
        query($login: String!) {
          user(login: $login) {
            createdAt
            contributionsCollection {
              contributionYears
            }
          }
        }
        """,
        {"login": username},
    )["user"]
    years = sorted(info["contributionsCollection"]["contributionYears"])
    all_days: dict[str, int] = {}
    for yr in years:
        res = graphql(
            """
            query($login: String!, $from: DateTime!, $to: DateTime!) {
              user(login: $login) {
                contributionsCollection(from: $from, to: $to) {
                  contributionCalendar {
                    weeks {
                      contributionDays {
                        date
                        contributionCount
                      }
                    }
                  }
                }
              }
            }
            """,
            {"login": username, "from": f"{yr}-01-01T00:00:00Z", "to": f"{yr}-12-31T23:59:59Z"},
        )
        for wk in res["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in wk["contributionDays"]:
                all_days[d["date"]] = int(d["contributionCount"])
    sorted_days = sorted(all_days.items())
    total = sum(c for _, c in sorted_days)
    return total, sorted_days


def compute_streaks(days: list[tuple[str, int]]) -> tuple[int, str, str, int, str, str]:
    if not days:
        return 0, "", "", 0, "", ""
    # Longest streak
    longest = 0
    l_start = l_end = ""
    cur = 0
    c_start = ""
    for dt, cnt in days:
        if cnt > 0:
            if cur == 0:
                c_start = dt
            cur += 1
            if cur >= longest:
                longest = cur
                l_start, l_end = c_start, dt
        else:
            cur = 0

    # Current streak (as of today or yesterday UTC-3)
    by_date = dict(days)
    today_dt = (datetime.now(timezone.utc) - timedelta(hours=3)).date()
    d = today_dt
    if by_date.get(d.isoformat(), 0) == 0:
        d = d - timedelta(days=1)
    curr = 0
    curr_end = d.isoformat()
    curr_start = curr_end
    while by_date.get(d.isoformat(), 0) > 0:
        curr += 1
        curr_start = d.isoformat()
        d = d - timedelta(days=1)

    def fmt(iso: str) -> str:
        if not iso:
            return ""
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %d, %Y")

    first_day = fmt(days[0][0])
    curr_range = f"{fmt(curr_start)} - {fmt(curr_end)}" if curr > 1 else (fmt(curr_end) if curr == 1 else fmt(today_dt.isoformat()))
    long_range = f"{fmt(l_start)} - {fmt(l_end)}" if longest > 0 else ""
    return longest, long_range, f"{first_day} - Present", curr, curr_range, fmt(today_dt.isoformat())


def render_svg(total: int, curr: int, curr_range: str, longest: int, long_range: str, total_range: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195">
  <rect x="0.5" y="0.5" width="494" height="194" rx="4.5" fill="#09090b" stroke="#27272a" />
  <line x1="165" y1="28" x2="165" y2="170" stroke="#27272a" stroke-width="1" />
  <line x1="330" y1="28" x2="330" y2="170" stroke="#27272a" stroke-width="1" />

  <text x="82.5" y="84" text-anchor="middle" fill="#f4f4f5" font-family="Segoe UI, Ubuntu, sans-serif" font-size="28" font-weight="700">{total:,}</text>
  <text x="82.5" y="114" text-anchor="middle" fill="#a1a1aa" font-family="Segoe UI, Ubuntu, sans-serif" font-size="13" font-weight="400">Total Contributions</text>
  <text x="82.5" y="138" text-anchor="middle" fill="#71717a" font-family="Segoe UI, Ubuntu, sans-serif" font-size="11">{total_range}</text>

  <circle cx="247.5" cy="70" r="36" fill="none" stroke="#34d399" stroke-width="5" />
  <text x="247.5" y="80" text-anchor="middle" fill="#f4f4f5" font-family="Segoe UI, Ubuntu, sans-serif" font-size="28" font-weight="700">{curr}</text>
  <text x="247.5" y="132" text-anchor="middle" fill="#34d399" font-family="Segoe UI, Ubuntu, sans-serif" font-size="14" font-weight="700">Current Streak</text>
  <text x="247.5" y="155" text-anchor="middle" fill="#71717a" font-family="Segoe UI, Ubuntu, sans-serif" font-size="11">{curr_range}</text>

  <text x="412.5" y="84" text-anchor="middle" fill="#f4f4f5" font-family="Segoe UI, Ubuntu, sans-serif" font-size="28" font-weight="700">{longest}</text>
  <text x="412.5" y="114" text-anchor="middle" fill="#a1a1aa" font-family="Segoe UI, Ubuntu, sans-serif" font-size="13" font-weight="400">Longest Streak</text>
  <text x="412.5" y="138" text-anchor="middle" fill="#71717a" font-family="Segoe UI, Ubuntu, sans-serif" font-size="11">{long_range}</text>
</svg>
"""


def main() -> None:
    total, days = fetch_all_days(USER)
    longest, long_range, total_range, curr, curr_range, _ = compute_streaks(days)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render_svg(total, curr, curr_range, longest, long_range, total_range), encoding="utf-8")
    print(f"Generated {OUT_PATH}: total={total}, curr={curr}, longest={longest}")


if __name__ == "__main__":
    main()
