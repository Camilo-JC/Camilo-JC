#!/usr/bin/env python3
"""Generate cohesive Crimson Noir & Obsidian Graphite telemetry SVGs for Camilo-JC (CabDevX)."""

from __future__ import annotations

import json
import math
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = os.environ.get("GITHUB_USERNAME", "Camilo-JC")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

LANG_COLORS = {
    "TypeScript": "#C50337",
    "Python": "#E5E5E5",
    "HTML": "#FF4D79",
    "CSS": "#888888",
    "JavaScript": "#666666",
    "PLpgSQL": "#9E032C",
    "Dockerfile": "#A3A3A3",
    "Shell": "#4D4D4D",
}


def fetch_json(url: str) -> dict | list:
    headers = {"User-Agent": "CabDevX-Profile-Generator"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_contributions(username: str) -> tuple[int, list[tuple[str, int]]]:
    req = urllib.request.Request(
        f"https://github.com/users/{username}/contributions",
        headers={"User-Agent": "CabDevX-Profile-Generator"},
    )
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
    total_match = re.search(r"([\d,]+)\s+contributions?\s+in\s+the\s+last\s+year", html)
    total = int(total_match.group(1).replace(",", "")) if total_match else 0
    days = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*data-level="(\d+)"', html)
    days.sort(key=lambda x: x[0])
    return total, [(d, int(lvl)) for d, lvl in days]


def compute_streaks(days: list[tuple[str, int]]) -> dict:
    if not days:
        return {
            "longest": 0,
            "longest_range": "—",
            "current": 0,
            "current_range": "Sin racha activa",
            "active_days": 0,
            "range_label": "",
        }

    longest = 0
    longest_start = longest_end = days[0][0]
    cur = 0
    cur_start = days[0][0]

    for date_str, lvl in days:
        if lvl > 0:
            if cur == 0:
                cur_start = date_str
            cur += 1
            if cur > longest:
                longest = cur
                longest_start = cur_start
                longest_end = date_str
        else:
            cur = 0

    current_streak = 0
    current_end = days[-1][0]
    current_start = days[-1][0]
    for i in range(len(days) - 1, -1, -1):
        date_str, lvl = days[i]
        if lvl > 0:
            if current_streak == 0:
                current_end = date_str
            current_streak += 1
            current_start = date_str
        elif i == len(days) - 1:
            continue
        else:
            break

    def fmt(d: str) -> str:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%b %d")

    active_days = sum(1 for _, lvl in days if lvl > 0)
    return {
        "longest": longest,
        "longest_range": f"{fmt(longest_start)} – {fmt(longest_end)}" if longest else "—",
        "current": current_streak,
        "current_range": f"{fmt(current_start)} – {fmt(current_end)}" if current_streak else "Listo para el próximo commit",
        "active_days": active_days,
        "range_label": f"{fmt(days[0][0])} – Presente",
    }


def collect_metrics() -> dict:
    user = fetch_json(f"https://api.github.com/users/{USERNAME}")
    repos = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&sort=updated")
    total_contribs, days = fetch_contributions(USERNAME)
    streaks = compute_streaks(days)

    lang_bytes: dict[str, int] = {}
    repo_langs: dict[str, int] = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        primary = repo.get("language")
        if primary:
            repo_langs[primary] = repo_langs.get(primary, 0) + 1
        langs = fetch_json(repo["languages_url"])
        for lang, b in langs.items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + int(b)

    total_bytes = sum(lang_bytes.values()) or 1
    top_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)[:5]
    top_langs_pct = [
        (name, val, round((val / total_bytes) * 100, 1), LANG_COLORS.get(name, "#888888"))
        for name, val in top_langs
    ]

    frontend_bytes = sum(lang_bytes.get(k, 0) for k in ("TypeScript", "JavaScript", "HTML", "CSS"))
    backend_bytes = sum(lang_bytes.get(k, 0) for k in ("Python", "PLpgSQL", "Dockerfile", "Shell"))
    data_ml_bytes = int(lang_bytes.get("Python", 0) * 0.42)
    backend_api_bytes = max(backend_bytes - data_ml_bytes, 1)
    focus_total = frontend_bytes + backend_api_bytes + data_ml_bytes or 1

    focus_pct = [
        ("Frontend & UI", round(frontend_bytes / focus_total * 100), "#C50337"),
        ("Backend & APIs", round(backend_api_bytes / focus_total * 100), "#E5E5E5"),
        ("Data & ML", max(100 - round(frontend_bytes / focus_total * 100) - round(backend_api_bytes / focus_total * 100), 1), "#666666"),
    ]

    total_repo_count = sum(repo_langs.values()) or 1
    top_repo_langs = sorted(repo_langs.items(), key=lambda x: x[1], reverse=True)[:4]
    repo_lang_pct = [
        (name, cnt, round((cnt / total_repo_count) * 100), LANG_COLORS.get(name, "#888888"))
        for name, cnt in top_repo_langs
    ]

    return {
        "public_repos": user.get("public_repos", len(repos)),
        "total_contribs": total_contribs,
        "days": days,
        "streaks": streaks,
        "top_langs": top_langs_pct,
        "repo_langs": repo_lang_pct,
        "focus": focus_pct,
    }


def donut_segments(items: list[tuple], cx: float, cy: float, r: float) -> str:
    circ = 2 * math.pi * r
    offset = 0.0
    parts = []
    total = sum(x[2] for x in items) or 100
    for item in items:
        pct = item[2]
        color = item[3] if len(item) > 3 else item[2]
        seg = (pct / total) * circ
        gap = max(seg - 2.5, 1.0)
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="11" '
            f'stroke-dasharray="{gap:.2f} {circ:.2f}" stroke-dashoffset="{-offset:.2f}" '
            f'stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += seg
    return "\n      ".join(parts)


def render_github_stats_svg(m: dict) -> str:
    s = m["streaks"]
    top = m["top_langs"]
    focus = m["focus"]

    lang_rows = []
    for idx, (name, _, pct, color) in enumerate(top):
        y = 266 + idx * 21
        bar_w = max(8, int(pct * 1.45))
        lang_rows.append(
            f'<g transform="translate(54, {y})">'
            f'<circle cx="5" cy="-4" r="4" fill="{color}"/>'
            f'<text x="16" y="0" fill="#E5E5E5" font-size="12" class="mono">{escape(name)}</text>'
            f'<rect x="122" y="-9" width="150" height="7" rx="3.5" fill="#17171A"/>'
            f'<rect x="122" y="-9" width="{bar_w}" height="7" rx="3.5" fill="{color}"/>'
            f'<text x="284" y="0" fill="#888888" font-size="11.5" class="mono">{pct}%</text>'
            f'</g>'
        )

    focus_items_for_donut = [(n, p, p, c) for n, p, c in focus]
    focus_rows = []
    for idx, (name, pct, color) in enumerate(focus):
        y = 272 + idx * 28
        bar_w = max(12, int(pct * 1.5))
        focus_rows.append(
            f'<g transform="translate(636, {y})">'
            f'<circle cx="5" cy="-4" r="4.5" fill="{color}"/>'
            f'<text x="18" y="0" fill="#E5E5E5" font-size="12.5" class="sans">{escape(name)}</text>'
            f'<rect x="132" y="-9" width="155" height="8" rx="4" fill="#17171A"/>'
            f'<rect x="132" y="-9" width="{bar_w}" height="8" rx="4" fill="{color}"/>'
            f'<text x="298" y="0" fill="#D4D4D8" font-size="12" font-weight="600" class="mono">{pct}%</text>'
            f'</g>'
        )

    lang_donut = donut_segments(top, 476, 304, 42)
    focus_donut = donut_segments(focus_items_for_donut, 1068, 304, 42)

    ring_circ = 2 * math.pi * 34
    streak_pct = min(max(s["current"] / max(s["longest"], 1), 0.14 if s["current"] > 0 else 0.06), 1.0)
    streak_dash = streak_pct * ring_circ

    top_name, _, top_pct, _ = top[0]
    lead_focus_name, lead_focus_pct, _ = max(focus, key=lambda x: x[1])
    streak_unit = "día seguido" if s["current"] == 1 else "días seguidos"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 390" width="100%" height="100%" role="img" aria-label="CabDevX GitHub Stats">
  <defs>
    <linearGradient id="gsBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#02060E"/>
      <stop offset="55%" stop-color="#090909"/>
      <stop offset="100%" stop-color="#19030B"/>
    </linearGradient>
    <linearGradient id="gsCard" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#0B0B0E"/>
      <stop offset="100%" stop-color="#05070B"/>
    </linearGradient>
    <linearGradient id="gsAccent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#C50337"/>
      <stop offset="65%" stop-color="#FF3366"/>
      <stop offset="100%" stop-color="#666666"/>
    </linearGradient>
    <linearGradient id="gsBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#C50337" stop-opacity="0.45"/>
      <stop offset="50%" stop-color="#262626"/>
      <stop offset="100%" stop-color="#666666" stop-opacity="0.45"/>
    </linearGradient>
    <style>
      .sans {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace; }}
    </style>
  </defs>

  <rect x="1.5" y="1.5" width="1197" height="387" rx="18" fill="url(#gsBg)" stroke="url(#gsBorder)" stroke-width="1.5"/>

  <!-- Header -->
  <text x="34" y="42" fill="#F4F4F5" font-size="22" font-weight="700" class="sans">GitHub Stats</text>
  <text x="34" y="62" fill="#666666" font-size="12" class="mono">cabdevx · {m["public_repos"]} repositorios públicos · datos reales</text>
  <rect x="1004" y="26" width="164" height="26" rx="13" fill="#090909" stroke="#262626"/>
  <circle cx="1020" cy="39" r="3.5" fill="#C50337"/>
  <text x="1032" y="43" fill="#A3A3A3" font-size="11" class="mono">AUTO-UPDATED</text>

  <!-- Row 1: 3 KPI Bento Cards -->
  <rect x="32" y="82" width="366" height="122" rx="14" fill="url(#gsCard)" stroke="#222226" stroke-width="1.2"/>
  <text x="54" y="108" fill="#888888" font-size="12.5" font-weight="600" class="sans">Contribuciones (último año)</text>
  <text x="54" y="160" fill="#F4F4F5" font-size="44" font-weight="800" class="sans">{m["total_contribs"]}</text>
  <text x="54" y="186" fill="#666666" font-size="11.5" class="mono">{s["range_label"]} · {s["active_days"]} días activos</text>

  <rect x="417" y="82" width="366" height="122" rx="14" fill="url(#gsCard)" stroke="#222226" stroke-width="1.2"/>
  <circle cx="484" cy="143" r="34" fill="none" stroke="#1A1A1F" stroke-width="6"/>
  <circle cx="484" cy="143" r="34" fill="none" stroke="url(#gsAccent)" stroke-width="6" stroke-dasharray="{streak_dash:.1f} {ring_circ:.1f}" stroke-linecap="round" transform="rotate(-90 484 143)"/>
  <text x="484" y="150" text-anchor="middle" fill="#F4F4F5" font-size="22" font-weight="800" class="sans">{s["current"]:02d}</text>
  <text x="540" y="124" fill="#E5E5E5" font-size="14" font-weight="700" class="sans">Racha actual</text>
  <text x="540" y="146" fill="#FF3366" font-size="12" class="mono">{s["current"]} {streak_unit}</text>
  <text x="540" y="168" fill="#666666" font-size="11.5" class="mono">{s["current_range"]}</text>

  <rect x="802" y="82" width="366" height="122" rx="14" fill="url(#gsCard)" stroke="#222226" stroke-width="1.2"/>
  <text x="824" y="108" fill="#888888" font-size="12.5" font-weight="600" class="sans">Mejor racha</text>
  <text x="824" y="160" fill="#F4F4F5" font-size="44" font-weight="800" class="sans">{s["longest"]:02d}<tspan fill="#C50337" font-size="16" font-weight="600"> días</tspan></text>
  <text x="824" y="186" fill="#666666" font-size="11.5" class="mono">Pico: {s["longest_range"]}</text>

  <!-- Row 2: 2 Language / Focus Donut Cards -->
  <rect x="32" y="218" width="558" height="148" rx="14" fill="url(#gsCard)" stroke="#222226" stroke-width="1.2"/>
  <text x="54" y="244" fill="#E5E5E5" font-size="14" font-weight="700" class="sans">Lenguajes principales (código)</text>
  {"".join(lang_rows)}
  <g>
    <circle cx="476" cy="304" r="42" fill="none" stroke="#17171A" stroke-width="11"/>
    {lang_donut}
    <text x="476" y="302" text-anchor="middle" fill="#F4F4F5" font-size="17" font-weight="800" class="sans">{int(round(top_pct))}%</text>
    <text x="476" y="318" text-anchor="middle" fill="#888888" font-size="10" class="mono">{escape(top_name)}</text>
  </g>

  <rect x="610" y="218" width="558" height="148" rx="14" fill="url(#gsCard)" stroke="#222226" stroke-width="1.2"/>
  <text x="636" y="244" fill="#E5E5E5" font-size="14" font-weight="700" class="sans">Enfoque de desarrollo</text>
  {"".join(focus_rows)}
  <g>
    <circle cx="1068" cy="304" r="42" fill="none" stroke="#17171A" stroke-width="11"/>
    {focus_donut}
    <text x="1068" y="302" text-anchor="middle" fill="#F4F4F5" font-size="17" font-weight="800" class="sans">{lead_focus_pct}%</text>
    <text x="1068" y="318" text-anchor="middle" fill="#888888" font-size="9.5" class="mono">{escape(lead_focus_name.split()[0])}</text>
  </g>
</svg>
'''


def render_dev_telemetry_svg(m: dict) -> str:
    days = m["days"]
    focus = m["focus"]

    recent = days[-168:] if len(days) >= 168 else days
    pad_count = max(0, 168 - len(recent))
    grid_days = [("pad", 0)] * pad_count + recent

    level_colors = {
        0: "#121216",
        1: "#3B0615",
        2: "#6E0421",
        3: "#9C032C",
        4: "#C50337",
    }

    cells = []
    start_x = 588
    start_y = 114
    step = 23
    for idx, (_, lvl) in enumerate(grid_days):
        col = idx // 7
        row = idx % 7
        x = start_x + col * step
        y = start_y + row * 17
        color = level_colors.get(lvl, "#121216")
        cells.append(f'<rect x="{x}" y="{y}" width="13" height="13" rx="3" fill="{color}"/>')

    bar_x = 588
    bar_w_total = 540
    seg_parts = []
    cur_x = bar_x
    for idx, (_, pct, color) in enumerate(focus):
        w = int(bar_w_total * pct / 100) if idx < len(focus) - 1 else (bar_x + bar_w_total - cur_x)
        seg_parts.append(f'<rect x="{cur_x}" y="294" width="{max(w - 3, 6)}" height="9" rx="4.5" fill="{color}"/>')
        cur_x += w

    f0, f1, f2 = focus[0], focus[1], focus[2]

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 336" width="100%" height="100%" role="img" aria-label="CabDevX Developer Telemetry">
  <defs>
    <linearGradient id="dtBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#02060E"/>
      <stop offset="55%" stop-color="#090909"/>
      <stop offset="100%" stop-color="#19030B"/>
    </linearGradient>
    <linearGradient id="dtBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#C50337" stop-opacity="0.45"/>
      <stop offset="50%" stop-color="#262626"/>
      <stop offset="100%" stop-color="#666666" stop-opacity="0.45"/>
    </linearGradient>
    <style>
      .sans {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace; }}
      .cursor-blink {{ animation: blink 1s steps(2, start) infinite; }}
      @keyframes blink {{
        0%, 49% {{ opacity: 1; }}
        50%, 100% {{ opacity: 0; }}
      }}
    </style>
  </defs>

  <rect x="1.5" y="1.5" width="1197" height="333" rx="18" fill="url(#dtBg)" stroke="url(#dtBorder)" stroke-width="1.5"/>

  <text x="34" y="42" fill="#F4F4F5" font-size="22" font-weight="700" class="sans">Builder Activity</text>
  <text x="34" y="62" fill="#888888" font-size="12.5" class="sans">Interfaces limpias, APIs sólidas y analítica aplicada a problemas reales.</text>

  <g transform="translate(780, 36)" class="mono" font-size="11.5">
    <circle cx="0" cy="-4" r="4" fill="#C50337"/><text x="10" y="0" fill="#D4D4D8">Frontend</text>
    <circle cx="98" cy="-4" r="4" fill="#E5E5E5"/><text x="108" y="0" fill="#D4D4D8">Backend</text>
    <circle cx="192" cy="-4" r="4" fill="#666666"/><text x="202" y="0" fill="#D4D4D8">Data &amp; ML</text>
  </g>

  <!-- Left Subcard: Dark Code Editor -->
  <rect x="32" y="82" width="520" height="228" rx="14" fill="#05070B" stroke="#222226" stroke-width="1.2"/>
  <circle cx="54" cy="103" r="4.5" fill="#C50337"/>
  <circle cx="70" cy="103" r="4.5" fill="#666666"/>
  <circle cx="86" cy="103" r="4.5" fill="#E5E5E5" opacity="0.75"/>
  <text x="292" y="107" text-anchor="middle" fill="#666666" font-size="11.5" class="mono">cabdevx_architecture.py</text>
  <line x1="32" y1="120" x2="552" y2="120" stroke="#1E1E22" stroke-width="1"/>

  <g class="mono" font-size="12.5">
    <text x="52" y="148" fill="#4D4D54">1</text>
    <text x="74" y="148" fill="#C50337">class <tspan fill="#F4F4F5">CabDevX</tspan><tspan fill="#888888">:</tspan></text>

    <text x="52" y="172" fill="#4D4D54">2</text>
    <text x="92" y="172" fill="#888888">frontend <tspan fill="#C50337">=</tspan> <tspan fill="#FDA4AF">["Next.js", "React", "TypeScript"]</tspan></text>

    <text x="52" y="196" fill="#4D4D54">3</text>
    <text x="92" y="196" fill="#888888">backend  <tspan fill="#C50337">=</tspan> <tspan fill="#E5E5E5">["Django", "FastAPI", "PostgreSQL"]</tspan></text>

    <text x="52" y="220" fill="#4D4D54">4</text>
    <text x="92" y="220" fill="#888888">devops   <tspan fill="#C50337">=</tspan> <tspan fill="#A3A3A3">["Docker", "Vercel", "GitHub Actions"]</tspan></text>

    <text x="52" y="252" fill="#4D4D54">5</text>
    <text x="92" y="252" fill="#C50337">def <tspan fill="#F4F4F5">ship</tspan><tspan fill="#888888">(idea):</tspan></text>

    <text x="52" y="276" fill="#4D4D54">6</text>
    <text x="110" y="276" fill="#C50337">return <tspan fill="#F4F4F5">clean_ui(idea) </tspan><tspan fill="#FF3366">+</tspan><tspan fill="#F4F4F5"> solid_api()</tspan></text>
    <rect x="466" y="264" width="7" height="14" rx="1" fill="#C50337" class="cursor-blink"/>
  </g>

  <!-- Right Subcard: Heatmap & Focus -->
  <rect x="570" y="82" width="596" height="228" rx="14" fill="#05070B" stroke="#222226" stroke-width="1.2"/>
  <text x="588" y="103" fill="#E5E5E5" font-size="12.5" font-weight="600" class="sans">Actividad reciente (últimas 24 semanas)</text>
  <text x="1148" y="103" text-anchor="end" fill="#666666" font-size="11" class="mono">{m["total_contribs"]} contribs / año</text>

  {"".join(cells)}

  <text x="588" y="254" fill="#E5E5E5" font-size="12.5" font-weight="600" class="sans">Distribución de stack</text>
  <text x="588" y="282" fill="#888888" font-size="11.5" class="mono">
    <tspan fill="#FF3366">{escape(f0[0])} {f0[1]}%</tspan>  ·  <tspan fill="#E5E5E5">{escape(f1[0])} {f1[1]}%</tspan>  ·  <tspan fill="#888888">{escape(f2[0])} {f2[1]}%</tspan>
  </text>

  {"".join(seg_parts)}
</svg>
'''


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    metrics = collect_metrics()
    (ASSETS_DIR / "github-stats.svg").write_text(render_github_stats_svg(metrics), encoding="utf-8")
    (ASSETS_DIR / "dev-telemetry.svg").write_text(render_dev_telemetry_svg(metrics), encoding="utf-8")
    print(f"Generated SVGs for {USERNAME}: {metrics['total_contribs']} contribs, {metrics['public_repos']} repos")


if __name__ == "__main__":
    main()
