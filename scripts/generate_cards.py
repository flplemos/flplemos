"""Generates the README stat cards (assets/stats.svg and assets/languages.svg).

Runs on GitHub Actions (see .github/workflows/cards.yml) with GITHUB_TOKEN, so it
doesn't depend on any third-party service like github-readme-stats.
No dependencies: Python standard library only.

Cards are drawn at 1200px wide and shown at 100% width in the README (~830px on
github.com), so every font size here is ~1.45x the size it will appear on screen.

Local usage:  GITHUB_TOKEN=xxx python scripts/generate_cards.py flplemos
"""

import json
import os
import sys
import urllib.request
from datetime import date
from html import escape
from pathlib import Path

USER = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_USER", "flplemos")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = Path(__file__).resolve().parent.parent / "assets"

# Portfolio palette (fl-portfolio/design-system/fl-portfolio/MASTER.md)
BG, CARD, BORDER = "#020617", "#0E1223", "#334155"
FG, SOFT, MUTED = "#F8FAFC", "#CBD5E1", "#94A3B8"  # MUTED on BG ≈ 7:1
GREEN, SKY = "#22C55E", "#38BDF8"
LANG_COLORS = [GREEN, SKY, "#A78BFA", "#F59E0B", "#F472B6", "#94A3B8"]
MONO = "'JetBrains Mono',ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',monospace"
SANS = "'IBM Plex Sans',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
W = 1200

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch():
    if not TOKEN:
        sys.exit("GITHUB_TOKEN is not set")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        sys.exit(f"GraphQL: {payload['errors']}")
    return payload["data"]["user"]


def streaks(days):
    """days: [(iso_date, count)] in order. Returns (current, longest)."""
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    current = 0
    # today may not have a contribution yet: that doesn't break the streak
    seq = days[:-1] if days and days[-1][1] == 0 else days
    for _, c in reversed(seq):
        if c == 0:
            break
        current += 1
    return current, longest


def fmt(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def text(x, y, s, size, fill, font=SANS, weight=None, anchor=None):
    attrs = f'x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}"'
    if weight:
        attrs += f' font-weight="{weight}"'
    if anchor:
        attrs += f' text-anchor="{anchor}"'
    return f"  <text {attrs}>{s}</text>"


def frame(h, title, label, body, stamp=True):
    today = date.today()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{escape(label)}">
  <title>{escape(label)}</title>
  <defs>
    <radialGradient id="g" cx="1" cy="0" r="0.8">
      <stop offset="0" stop-color="{GREEN}" stop-opacity="0.10"/><stop offset="1" stop-color="{GREEN}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="20" fill="{BG}" stroke="{FG}" stroke-opacity="0.1"/>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="20" fill="url(#g)"/>
{text(48, 60, f'<tspan fill="{GREEN}">❯</tspan> {escape(title)}', 22, SOFT, MONO)}
{text(W - 48, 60, f"updated {MONTHS[today.month - 1]} {today.day:02d}, {today.year}", 18, MUTED, MONO, anchor="end") if stamp else ""}
{body}
</svg>
"""


def stats_card(u):
    repos = u["repositories"]
    cc = u["contributionsCollection"]
    cal = cc["contributionCalendar"]
    weeks = cal["weeks"][-52:]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    cur, best = streaks(days)
    weekly = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
    active = sum(1 for v in weekly if v)
    stars = sum(n["stargazerCount"] for n in repos["nodes"])

    H = 520
    b = []

    # ── hero metric (left) ──
    b.append(text(48, 170, fmt(cal["totalContributions"]), 96, GREEN, MONO, 700))
    b.append(text(48, 212, "contributions", 24, FG, SANS, 600))
    b.append(text(48, 242, "in the last 12 months", 20, MUTED))

    # ── secondary metrics (right, 4 × 2 grid) ──
    items = [
        (fmt(cc["totalCommitContributions"] + cc["restrictedContributionsCount"]), "commits"),
        (fmt(repos["totalCount"]), "repositories"),
        (fmt(u["pullRequests"]["totalCount"]), "pull requests"),
        (fmt(stars), "stars earned"),
        (plural(cur, "day"), "current streak"),
        (plural(best, "day"), "longest streak"),
        (f"{active}/52", "active weeks"),
        (fmt(u["followers"]["totalCount"]), "followers"),
    ]
    gx, col_w = 400, 190
    b.append(f'  <line x1="{gx - 32}" y1="112" x2="{gx - 32}" y2="252" stroke="{BORDER}" stroke-opacity="0.8"/>')
    for i, (value, label) in enumerate(items):
        x, y = gx + (i % 4) * col_w, 140 + (i // 4) * 84
        b.append(text(x, y, escape(value), 36, FG, MONO, 700))
        b.append(text(x, y + 30, label, 19, MUTED))

    # ── weekly activity chart ──
    top, base = 330, 450
    b.append(f'  <line x1="48" y1="290" x2="{W - 48}" y2="290" stroke="{BORDER}" stroke-opacity="0.6"/>')
    b.append(text(48, 326, "weekly contributions · last 52 weeks", 19, SOFT, SANS, 600))
    peak = max(weekly) if weekly else 0
    b.append(text(W - 48, 326, f"peak {peak}/week", 18, MUTED, MONO, anchor="end"))
    chart_h = base - top - 22
    bw = (W - 96) / max(len(weekly), 1)
    for i, v in enumerate(weekly):
        h = max(3, v / (peak or 1) * chart_h) if v else 3
        fill, op = (GREEN, 0.35 + 0.65 * v / peak) if v else (BORDER, 0.5)
        if v and v == peak:
            op = 1
        b.append(
            f'  <rect x="{48 + i * bw + 2:.1f}" y="{base - h:.1f}" width="{bw - 4:.1f}" height="{h:.1f}" rx="2" fill="{fill}" fill-opacity="{op:.2f}"/>'
        )
    # month labels on the first week of each month
    last_month = None
    for i, w in enumerate(weeks):
        m = int(w["contributionDays"][0]["date"][5:7])
        if m != last_month and i < len(weeks) - 2:
            if last_month is not None:
                b.append(text(f"{48 + i * bw + 2:.1f}", base + 30, MONTHS[m - 1], 16, MUTED, MONO))
            last_month = m

    label = f"GitHub stats for {USER}: {cal['totalContributions']} contributions in the last 12 months"
    return frame(H, "github --stats", label, "\n".join(b))


def languages_card(u):
    totals = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            totals[e["node"]["name"]] = totals.get(e["node"]["name"], 0) + e["size"]
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    if len(top) > 6:
        top = top[:5] + [("Other", sum(v for _, v in top[5:]))]
    total = sum(v for _, v in top) or 1
    biggest = top[0][1] if top else 1

    H = 330
    b = []
    x0, bar_w, y0 = 48, W - 96, 96
    b.append(f'  <clipPath id="bar"><rect x="{x0}" y="{y0}" width="{bar_w}" height="18" rx="9"/></clipPath>')
    b.append(f'  <g clip-path="url(#bar)"><rect x="{x0}" y="{y0}" width="{bar_w}" height="18" fill="{CARD}"/>')
    x = x0
    for i, (_, v) in enumerate(top):
        w = v / total * bar_w
        # 2px gaps keep adjacent segments distinguishable without relying on hue alone
        b.append(f'    <rect x="{x:.1f}" y="{y0}" width="{max(w - 2, 1):.1f}" height="18" fill="{LANG_COLORS[i]}"/>')
        x += w
    b.append("  </g>")

    col_w = (W - 96) / 3
    for i, (name, v) in enumerate(top):
        x, y = 48 + (i % 3) * col_w, 180 + (i // 3) * 82
        pct = v / total * 100
        inner = col_w - 56
        b.append(f'  <circle cx="{x + 8:.1f}" cy="{y - 7}" r="8" fill="{LANG_COLORS[i]}"/>')
        b.append(text(f"{x + 28:.1f}", y, escape(name), 22, FG, SANS, 500))
        b.append(text(f"{x + inner:.1f}", y, f"{pct:.1f}%", 22, FG, MONO, 700, "end"))
        b.append(f'  <rect x="{x + 28:.1f}" y="{y + 16}" width="{inner - 28:.1f}" height="6" rx="3" fill="{CARD}"/>')
        b.append(
            f'  <rect x="{x + 28:.1f}" y="{y + 16}" width="{max(6, (inner - 28) * v / biggest):.1f}" height="6" rx="3" fill="{LANG_COLORS[i]}"/>'
        )

    label = "Top languages: " + ", ".join(f"{n} {v / total * 100:.1f}%" for n, v in top)
    return frame(H, "languages --top", label, "\n".join(b), stamp=False)


def main():
    u = fetch()
    OUT.mkdir(exist_ok=True)
    (OUT / "stats.svg").write_text(stats_card(u), encoding="utf-8")
    (OUT / "languages.svg").write_text(languages_card(u), encoding="utf-8")
    print("ok:", OUT / "stats.svg", OUT / "languages.svg")


if __name__ == "__main__":
    main()
