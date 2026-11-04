"""Gera os cards de stats do README (assets/stats.svg e assets/languages.svg).

Roda no GitHub Actions (ver .github/workflows/cards.yml) usando o GITHUB_TOKEN,
então não depende de nenhum serviço externo tipo github-readme-stats.
Sem dependências: só a biblioteca padrão do Python.

Uso local:  GITHUB_TOKEN=xxx python scripts/generate_cards.py flplemos
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

# Paleta do portfolio (design-system/fl-portfolio/MASTER.md)
BG, CARD, BORDER = "#020617", "#0E1223", "#334155"
FG, SOFT, MUTED = "#F8FAFC", "#CBD5E1", "#94A3B8"
GREEN, SKY = "#22C55E", "#38BDF8"
LANG_COLORS = [GREEN, SKY, "#A78BFA", "#F59E0B", "#F472B6", "#94A3B8"]
MONO = "'JetBrains Mono',ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',monospace"
SANS = "'IBM Plex Sans',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"

QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
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
        sys.exit("GITHUB_TOKEN não definido")
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
    """days: lista [(date, count)] em ordem. Retorna (atual, maior)."""
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    current = 0
    # hoje pode ainda não ter contribuição: não quebra a sequência
    seq = days[:-1] if days and days[-1][1] == 0 else days
    for _, c in reversed(seq):
        if c == 0:
            break
        current += 1
    return current, longest


def fmt(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def frame(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">
  <defs>
    <radialGradient id="g" cx="1" cy="0" r="0.9">
      <stop offset="0" stop-color="{GREEN}" stop-opacity="0.12"/><stop offset="1" stop-color="{GREEN}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="16" fill="{BG}" stroke="{FG}" stroke-opacity="0.1"/>
  <rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="16" fill="url(#g)"/>
  <text x="28" y="40" font-family="{MONO}" font-size="15" fill="{MUTED}"><tspan fill="{GREEN}">❯</tspan> {escape(title)}</text>
{body}
</svg>
"""


def stats_card(u):
    repos = u["repositories"]
    cc = u["contributionsCollection"]
    cal = cc["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    cur, best = streaks(days)
    stars = sum(n["stargazerCount"] for n in repos["nodes"])

    items = [
        ("contribuições (12m)", fmt(cal["totalContributions"]), GREEN),
        ("commits (12m)", fmt(cc["totalCommitContributions"] + cc["restrictedContributionsCount"]), FG),
        ("repositórios", fmt(repos["totalCount"]), FG),
        ("pull requests", fmt(u["pullRequests"]["totalCount"]), FG),
        ("streak atual", f"{cur}d", SKY),
        ("maior streak", f"{best}d", FG),
        ("estrelas", fmt(stars), FG),
        ("seguidores", fmt(u["followers"]["totalCount"]), FG),
    ]
    W, H = 600, 300
    body = []
    for i, (label, value, color) in enumerate(items):
        col, row = i % 4, i // 4
        x, y = 28 + col * 138, 92 + row * 70
        body.append(
            f'  <text x="{x}" y="{y}" font-family="{MONO}" font-size="26" font-weight="700" fill="{color}">{escape(value)}</text>\n'
            f'  <text x="{x}" y="{y + 22}" font-family="{SANS}" font-size="12" fill="{MUTED}">{escape(label)}</text>'
        )

    # sparkline: contribuições por semana nas últimas 52 semanas
    weekly = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in cal["weeks"]][-52:]
    peak = max(weekly) or 1
    bx, by, bh = 28, 272, 70
    bw = (W - 56) / max(len(weekly), 1)
    body.append(f'  <line x1="{bx}" y1="{by}" x2="{W - 28}" y2="{by}" stroke="{BORDER}" stroke-opacity="0.7"/>')
    for i, v in enumerate(weekly):
        hgt = max(2, v / peak * bh) if v else 2
        op = 0.25 + 0.75 * (v / peak) if v else 0.15
        body.append(
            f'  <rect x="{bx + i * bw + 1:.1f}" y="{by - hgt:.1f}" width="{bw - 2:.1f}" height="{hgt:.1f}" rx="1.5" fill="{GREEN}" fill-opacity="{op:.2f}"/>'
        )
    body.append(
        f'  <text x="{W - 28}" y="40" text-anchor="end" font-family="{MONO}" font-size="11" fill="{BORDER}">atualizado {date.today():%d/%m/%Y}</text>'
    )
    return frame(W, H, "github --stats", "\n".join(body))


def languages_card(u):
    totals = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            totals[e["node"]["name"]] = totals.get(e["node"]["name"], 0) + e["size"]
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    if len(top) > 6:
        top = top[:5] + [("Outras", sum(v for _, v in top[5:]))]
    total = sum(v for _, v in top) or 1

    W, H = 600, 300
    body = []
    x0, bar_w, y0 = 28, W - 56, 72
    body.append(f'  <clipPath id="bar"><rect x="{x0}" y="{y0}" width="{bar_w}" height="12" rx="6"/></clipPath>')
    body.append(f'  <g clip-path="url(#bar)"><rect x="{x0}" y="{y0}" width="{bar_w}" height="12" fill="{CARD}"/>')
    x = x0
    for i, (_, v) in enumerate(top):
        w = v / total * bar_w
        body.append(f'    <rect x="{x:.1f}" y="{y0}" width="{w + 0.5:.1f}" height="12" fill="{LANG_COLORS[i]}"/>')
        x += w
    body.append("  </g>")

    for i, (name, v) in enumerate(top):
        col, row = i % 2, i // 2
        x, y = 28 + col * 280, 130 + row * 54
        pct = v / total * 100
        body.append(
            f'  <circle cx="{x + 6}" cy="{y - 5}" r="6" fill="{LANG_COLORS[i]}"/>\n'
            f'  <text x="{x + 22}" y="{y}" font-family="{SANS}" font-size="15" fill="{SOFT}">{escape(name)}</text>\n'
            f'  <text x="{x + 252}" y="{y}" text-anchor="end" font-family="{MONO}" font-size="15" font-weight="600" fill="{FG}">{pct:.1f}%</text>\n'
            f'  <rect x="{x + 22}" y="{y + 10}" width="230" height="3" rx="1.5" fill="{CARD}"/>\n'
            f'  <rect x="{x + 22}" y="{y + 10}" width="{max(3, 230 * pct / 100):.1f}" height="3" rx="1.5" fill="{LANG_COLORS[i]}" fill-opacity="0.8"/>'
        )
    return frame(W, H, "linguagens --top", "\n".join(body))


def main():
    u = fetch()
    OUT.mkdir(exist_ok=True)
    (OUT / "stats.svg").write_text(stats_card(u), encoding="utf-8")
    (OUT / "languages.svg").write_text(languages_card(u), encoding="utf-8")
    print("ok:", OUT / "stats.svg", OUT / "languages.svg")


if __name__ == "__main__":
    main()
