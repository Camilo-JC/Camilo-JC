#!/usr/bin/env python3
"""Generate innovative Crimson Noir & Obsidian Graphite telemetry SVGs for Camilo-JC (CabDevX)."""

from __future__ import annotations

import json
import math
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = os.environ.get("GITHUB_USERNAME", "Camilo-JC")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
CACHE_FILE = ROOT_DIR / "scripts" / "metrics_cache.json"

LANG_COLORS = {
    "TypeScript": "#C50337",
    "Python": "#F4F4F5",
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
            "current_range": "Sin racha",
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
        "current_range": f"{fmt(current_start)} – {fmt(current_end)}" if current_streak else "Listo para commit",
        "active_days": active_days,
        "range_label": f"{fmt(days[0][0])} – Hoy",
    }


def collect_metrics() -> dict:
    total_contribs, days = fetch_contributions(USERNAME)
    streaks = compute_streaks(days)

    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    public_repos = cache.get("public_repos", 12)
    lang_bytes: dict[str, int] = dict(cache.get("lang_bytes", {}))

    try:
        user = fetch_json(f"https://api.github.com/users/{USERNAME}")
        repos = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&sort=updated")
        public_repos = user.get("public_repos", len(repos))
        fresh_bytes: dict[str, int] = {}
        for repo in repos:
            if repo.get("fork"):
                continue
            langs = fetch_json(repo["languages_url"])
            for lang, b in langs.items():
                fresh_bytes[lang] = fresh_bytes.get(lang, 0) + int(b)
        if fresh_bytes:
            lang_bytes = fresh_bytes
            CACHE_FILE.write_text(
                json.dumps({"public_repos": public_repos, "lang_bytes": lang_bytes}, indent=2),
                encoding="utf-8",
            )
    except urllib.error.HTTPError as exc:
        if exc.code != 403 or not lang_bytes:
            raise

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

    f0 = round(frontend_bytes / focus_total * 100)
    f1 = round(backend_api_bytes / focus_total * 100)
    f2 = max(100 - f0 - f1, 1)
    focus_pct = [
        ("Frontend", f0, "#C50337"),
        ("Backend", f1, "#F4F4F5"),
        ("Data & ML", f2, "#666666"),
    ]

    # 5-axis normalized radar scores (0.28..0.96) reflecting actual engineering stack balance
    ts_ratio = lang_bytes.get("TypeScript", 0) / total_bytes
    py_ratio = lang_bytes.get("Python", 0) / total_bytes
    ui_ratio = (lang_bytes.get("HTML", 0) + lang_bytes.get("CSS", 0) + lang_bytes.get("TypeScript", 0)) / total_bytes
    radar_axes = [
        ("Frontend", min(0.95, 0.45 + ui_ratio * 0.72), f"{f0}%"),
        ("TypeScript", min(0.95, 0.35 + ts_ratio * 1.35), f"{round(ts_ratio * 100)}%"),
        ("Python", min(0.95, 0.35 + py_ratio * 1.55), f"{round(py_ratio * 100)}%"),
        ("APIs / DB", min(0.90, 0.52 + py_ratio * 0.9), "SQL"),
        ("Data & ML", min(0.85, 0.40 + py_ratio * 1.05), f"{f2}%"),
    ]

    return {
        "public_repos": public_repos,
        "total_contribs": total_contribs,
        "days": days,
        "streaks": streaks,
        "top_langs": top_langs_pct,
        "focus": focus_pct,
        "radar_axes": radar_axes,
    }


def render_github_stats_svg(m: dict) -> str:
    s = m["streaks"]
    top = m["top_langs"]
    axes = m["radar_axes"]

    # Left Reactor Gauge calculations
    rcx, rcy = 186, 174
    outer_r = 76
    inner_r = 60
    inner_circ = 2 * math.pi * inner_r
    active_ratio = min(max(s["active_days"] / 90.0, 0.35), 0.92)
    inner_dash = active_ratio * inner_circ

    # Center 5-Axis Radar Chart (cx=585, cy=205, max_r=92)
    cx, cy, max_r = 585, 206, 86
    n_axes = len(axes)
    web_rings = []
    for scale in (0.33, 0.66, 1.0):
        pts = []
        for i in range(n_axes):
            ang = -math.pi / 2 + (2 * math.pi * i / n_axes)
            px = cx + max_r * scale * math.cos(ang)
            py = cy + max_r * scale * math.sin(ang)
            pts.append(f"{px:.1f},{py:.1f}")
        stroke_col = "#2A2A30" if scale == 1.0 else "#1B1B20"
        web_rings.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="{stroke_col}" stroke-width="1"/>')

    axis_lines = []
    radar_pts = []
    vertex_dots = []
    axis_labels = []
    for i, (label, val, tag) in enumerate(axes):
        ang = -math.pi / 2 + (2 * math.pi * i / n_axes)
        ex = cx + max_r * math.cos(ang)
        ey = cy + max_r * math.sin(ang)
        axis_lines.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#222228" stroke-width="1"/>')

        vx = cx + max_r * val * math.cos(ang)
        vy = cy + max_r * val * math.sin(ang)
        radar_pts.append(f"{vx:.1f},{vy:.1f}")
        delay = round(i * 0.35, 2)
        vertex_dots.append(
            f'<circle cx="{vx:.1f}" cy="{vy:.1f}" r="4.2" fill="#FF3366" stroke="#090909" stroke-width="1.5">'
            f'<animate attributeName="r" values="3.8;5.4;3.8" dur="2.2s" begin="{delay}s" repeatCount="indefinite"/>'
            f'</circle>'
        )

        lx = cx + (max_r + 22) * math.cos(ang)
        ly = cy + (max_r + 18) * math.sin(ang)
        anchor = "middle"
        if math.cos(ang) > 0.3:
            anchor = "start"
        elif math.cos(ang) < -0.3:
            anchor = "end"
        axis_labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" fill="#D4D4D8" font-size="11" font-weight="600" class="mono">{escape(label)}</text>'
        )

    # Right Panel: Language Spectrum DNA Bar + List (width 328 at x=824)
    dna_x, dna_w = 824, 326
    dna_segs = []
    cur_x = dna_x
    for idx, (name, _, pct, color) in enumerate(top):
        w = max(8, int(dna_w * pct / 100)) if idx < len(top) - 1 else max(8, dna_x + dna_w - cur_x)
        dna_segs.append(f'<rect x="{cur_x}" y="128" width="{max(w - 3, 4)}" height="12" rx="4" fill="{color}"/>')
        cur_x += w

    lang_rows = []
    for idx, (name, _, pct, color) in enumerate(top):
        y = 172 + idx * 36
        bar_w = max(10, int(pct * 2.1))
        lang_rows.append(
            f'<g transform="translate(824, {y})">'
            f'<rect x="0" y="-10" width="3" height="16" rx="1.5" fill="{color}"/>'
            f'<text x="12" y="2" fill="#F4F4F5" font-size="12.5" font-weight="600" class="mono">{escape(name)}</text>'
            f'<text x="326" y="2" text-anchor="end" fill="#A3A3A3" font-size="12" class="mono">{pct}%</text>'
            f'<rect x="12" y="10" width="314" height="4" rx="2" fill="#17171B"/>'
            f'<rect x="12" y="10" width="{bar_w}" height="4" rx="2" fill="{color}" opacity="0.9"/>'
            f'</g>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 380" width="100%" height="100%" role="img" aria-label="CabDevX GitHub Telemetry HUD">
  <defs>
    <linearGradient id="gsBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#02060E"/>
      <stop offset="52%" stop-color="#090909"/>
      <stop offset="100%" stop-color="#19030B"/>
    </linearGradient>
    <linearGradient id="gsCard" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#0B0B0F"/>
      <stop offset="100%" stop-color="#05070B"/>
    </linearGradient>
    <linearGradient id="gsBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#C50337" stop-opacity="0.55"/>
      <stop offset="50%" stop-color="#262626"/>
      <stop offset="100%" stop-color="#666666" stop-opacity="0.55"/>
    </linearGradient>
    <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FF3366"/>
      <stop offset="60%" stop-color="#C50337"/>
      <stop offset="100%" stop-color="#666666"/>
    </linearGradient>
    <radialGradient id="radarFill" cx="50%" cy="50%" r="55%">
      <stop offset="0%" stop-color="#C50337" stop-opacity="0.48"/>
      <stop offset="100%" stop-color="#C50337" stop-opacity="0.14"/>
    </radialGradient>
    <filter id="glowCrimson" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <style>
      .sans {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace; }}
      .orbit-spin {{ animation: spinOrbit 18s linear infinite; transform-box: fill-box; transform-origin: center; }}
      .orbit-rev {{ animation: spinRev 11s linear infinite; transform-box: fill-box; transform-origin: center; }}
      .pulse-dot {{ animation: pulseDot 1.6s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }}
      .radar-breath {{ animation: radarBreath 3.5s ease-in-out infinite; }}
      @keyframes spinOrbit {{
        from {{ transform: rotate(0deg); }}
        to {{ transform: rotate(360deg); }}
      }}
      @keyframes spinRev {{
        from {{ transform: rotate(360deg); }}
        to {{ transform: rotate(0deg); }}
      }}
      @keyframes pulseDot {{
        0%, 100% {{ opacity: 1; transform: scale(1); }}
        50% {{ opacity: 0.4; transform: scale(0.8); }}
      }}
      @keyframes radarBreath {{
        0%, 100% {{ opacity: 0.85; }}
        50% {{ opacity: 1; }}
      }}
    </style>
    <clipPath id="dnaClip">
      <rect x="{dna_x}" y="128" width="{dna_w}" height="12" rx="4"/>
    </clipPath>
    <linearGradient id="dnaSheen" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0"/>
      <stop offset="50%" stop-color="#FFFFFF" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="sweepGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FF3366" stop-opacity="0.65"/>
      <stop offset="100%" stop-color="#C50337" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <rect x="1.5" y="1.5" width="1197" height="377" rx="18" fill="url(#gsBg)" stroke="url(#gsBorder)" stroke-width="1.5"/>

  <!-- Top HUD Header -->
  <text x="32" y="40" fill="#F4F4F5" font-size="20" font-weight="700" class="sans">GitHub Telemetry</text>
  <text x="206" y="40" fill="#666666" font-size="12" class="mono">:: {escape(USERNAME)} · LIVE REPO METRICS</text>
  <rect x="1004" y="21" width="164" height="24" rx="12" fill="#090909" stroke="#262626"/>
  <circle cx="1020" cy="33" r="3.5" fill="#C50337" class="pulse-dot"/>
  <text x="1032" y="37" fill="#A3A3A3" font-size="10.5" class="mono">AUTO-SYNC 24H</text>

  <!-- Panel 1: Velocity & Streak Reactor (x=30..382) -->
  <rect x="30" y="62" width="352" height="292" rx="14" fill="url(#gsCard)" stroke="#222226" stroke-width="1.2"/>
  <text x="50" y="88" fill="#888888" font-size="11.5" font-weight="600" letter-spacing="1" class="mono">CONTRIBUTION REACTOR</text>

  <!-- Dual Counter-Rotating Orbital Rings -->
  <circle cx="{rcx}" cy="{rcy}" r="{outer_r}" fill="none" stroke="#2E2E36" stroke-width="1.5" stroke-dasharray="6 10" class="orbit-spin"/>
  <circle cx="{rcx}" cy="{rcy}" r="{outer_r - 7}" fill="none" stroke="#C50337" stroke-opacity="0.45" stroke-width="1.5" stroke-dasharray="28 110" class="orbit-rev"/>
  <circle cx="{rcx}" cy="{rcy}" r="{inner_r}" fill="none" stroke="#16161A" stroke-width="9"/>
  <circle cx="{rcx}" cy="{rcy}" r="{inner_r}" fill="none" stroke="url(#ringGrad)" stroke-width="9" stroke-dasharray="{inner_dash:.1f} {inner_circ:.1f}" stroke-linecap="round" transform="rotate(-90 {rcx} {rcy})" filter="url(#glowCrimson)">
    <animate attributeName="stroke-opacity" values="0.78;1;0.78" dur="2.8s" repeatCount="indefinite"/>
  </circle>

  <text x="{rcx}" y="{rcy + 6}" text-anchor="middle" fill="#F4F4F5" font-size="34" font-weight="800" class="sans">{m["total_contribs"]}</text>
  <text x="{rcx}" y="{rcy + 24}" text-anchor="middle" fill="#888888" font-size="9.5" letter-spacing="1" class="mono">CONTRIBS / AÑO</text>

  <!-- 4 Micro KPI Tiles inside Panel 1 -->
  <rect x="48" y="266" width="150" height="36" rx="8" fill="#090909" stroke="#1E1E22"/>
  <text x="58" y="281" fill="#666666" font-size="9.5" class="mono">RACHA ACTUAL</text>
  <text x="58" y="295" fill="#FF3366" font-size="12.5" font-weight="700" class="mono">{s["current"]:02d}d</text>
  <text x="188" y="295" text-anchor="end" fill="#666666" font-size="9.5" class="mono">{s["active_days"]} act.</text>

  <rect x="208" y="266" width="154" height="36" rx="8" fill="#090909" stroke="#1E1E22"/>
  <text x="218" y="281" fill="#666666" font-size="9.5" class="mono">MEJOR RACHA</text>
  <text x="218" y="295" fill="#F4F4F5" font-size="12.5" font-weight="700" class="mono">{s["longest"]:02d}d</text>
  <text x="352" y="295" text-anchor="end" fill="#666666" font-size="9" class="mono">{s["longest_range"]}</text>

  <text x="206" y="332" text-anchor="middle" fill="#666666" font-size="10.5" class="mono">{m["public_repos"]} repositorios públicos · {s["range_label"]}</text>

  <!-- Panel 2: 5-Axis Stack Radar (x=400..780) -->
  <rect x="400" y="62" width="380" height="292" rx="14" fill="url(#gsCard)" stroke="#222226" stroke-width="1.2"/>
  <text x="422" y="88" fill="#888888" font-size="11.5" font-weight="600" letter-spacing="1" class="mono">ENGINEERING RADAR</text>
  {"".join(web_rings)}
  {"".join(axis_lines)}
  <!-- Live Rotating Sonar Sweep -->
  <g>
    <path d="M {cx} {cy} L {cx} {cy - max_r} A {max_r} {max_r} 0 0 1 {cx + max_r * 0.55:.1f} {cy - max_r * 0.83:.1f} Z" fill="url(#sweepGrad)" opacity="0.42">
      <animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="5.5s" repeatCount="indefinite"/>
    </path>
  </g>
  <polygon points="{" ".join(radar_pts)}" fill="url(#radarFill)" stroke="#C50337" stroke-width="2" class="radar-breath" filter="url(#glowCrimson)"/>
  {"".join(vertex_dots)}
  {"".join(axis_labels)}

  <!-- Panel 3: Language DNA Spectrum (x=798..1170) -->
  <rect x="798" y="62" width="372" height="292" rx="14" fill="url(#gsCard)" stroke="#222226" stroke-width="1.2"/>
  <text x="824" y="88" fill="#888888" font-size="11.5" font-weight="600" letter-spacing="1" class="mono">CODE DNA SPECTRUM</text>
  <text x="824" y="114" fill="#666666" font-size="10.5" class="mono">Distribución real por bytes</text>
  {"".join(dna_segs)}
  <g clip-path="url(#dnaClip)">
    <rect x="{dna_x - 60}" y="126" width="56" height="16" fill="url(#dnaSheen)">
      <animate attributeName="x" values="{dna_x - 60};{dna_x + dna_w + 40};{dna_x + dna_w + 40}" keyTimes="0;0.55;1" dur="3.6s" repeatCount="indefinite"/>
    </rect>
  </g>
  {"".join(lang_rows)}
</svg>
'''


def render_dev_telemetry_svg(m: dict) -> str:
    days = m["days"]
    focus = m["focus"]

    recent = days[-168:] if len(days) >= 168 else days
    pad_count = max(0, 168 - len(recent))
    grid_days = [("pad", 0)] * pad_count + recent

    # Compute 24 weekly activity intensities for smooth waveform
    weekly_totals = []
    for w in range(24):
        chunk = grid_days[w * 7 : (w + 1) * 7]
        weekly_totals.append(sum(lvl for _, lvl in chunk))
    max_week = max(weekly_totals) or 1

    # Waveform area chart coordinates: x=578..1142 (w=564), y=102..168 (h=66)
    wx0, wx1 = 578, 1142
    wy_base, wy_top = 166, 102
    wave_pts = []
    for i, val in enumerate(weekly_totals):
        px = wx0 + (wx1 - wx0) * (i / 23.0)
        py = wy_base - ((val / max_week) * (wy_base - wy_top))
        wave_pts.append((px, py, val))

    # Build smooth quadratic/cubic Bezier path through wave_pts
    line_d = f"M {wave_pts[0][0]:.1f} {wave_pts[0][1]:.1f}"
    for i in range(1, len(wave_pts)):
        x_prev, y_prev, _ = wave_pts[i - 1]
        x_cur, y_cur, _ = wave_pts[i]
        cx_mid = (x_prev + x_cur) / 2
        line_d += f" C {cx_mid:.1f} {y_prev:.1f}, {cx_mid:.1f} {y_cur:.1f}, {x_cur:.1f} {y_cur:.1f}"
    area_d = f"{line_d} L {wx1} {wy_base} L {wx0} {wy_base} Z"

    peak_x, peak_y, _ = max(wave_pts, key=lambda t: t[2])

    # Circular micro-dot matrix for 24 weeks (below waveform: y=184..286)
    level_colors = {
        0: "#151519",
        1: "#450718",
        2: "#7A0424",
        3: "#A80330",
        4: "#E11D48",
    }
    dots = []
    start_x, start_y = 582, 180
    step_x, step_y = 24.1, 13.0
    for idx, (_, lvl) in enumerate(grid_days):
        col = idx // 7
        row = idx % 7
        cx_dot = start_x + col * step_x
        cy_dot = start_y + row * step_y
        color = level_colors.get(lvl, "#151519")
        r = 4.0 if lvl == 0 else 4.6
        if lvl >= 2:
            delay = round((col * 0.11 + row * 0.08) % 2.4, 2)
            dots.append(
                f'<circle cx="{cx_dot:.1f}" cy="{cy_dot:.1f}" r="{r}" fill="{color}">'
                f'<animate attributeName="opacity" values="0.55;1;0.55" dur="2.2s" begin="{delay}s" repeatCount="indefinite"/>'
                f'</circle>'
            )
        else:
            dots.append(f'<circle cx="{cx_dot:.1f}" cy="{cy_dot:.1f}" r="{r}" fill="{color}"/>')

    # Focus segmented bar
    f0, f1, f2 = focus[0], focus[1], focus[2]
    bar_x, bar_w_total = 578, 564
    seg_parts = []
    cur_x = bar_x
    for idx, (_, pct, color) in enumerate(focus):
        w = int(bar_w_total * pct / 100) if idx < len(focus) - 1 else (bar_x + bar_w_total - cur_x)
        seg_parts.append(f'<rect x="{cur_x}" y="302" width="{max(w - 4, 6)}" height="7" rx="3.5" fill="{color}"/>')
        cur_x += w

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 340" width="100%" height="100%" role="img" aria-label="CabDevX Builder Activity">
  <defs>
    <linearGradient id="dtBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#02060E"/>
      <stop offset="52%" stop-color="#090909"/>
      <stop offset="100%" stop-color="#19030B"/>
    </linearGradient>
    <linearGradient id="dtCard" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#0B0B0F"/>
      <stop offset="100%" stop-color="#05070B"/>
    </linearGradient>
    <linearGradient id="dtBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#C50337" stop-opacity="0.55"/>
      <stop offset="50%" stop-color="#262626"/>
      <stop offset="100%" stop-color="#666666" stop-opacity="0.55"/>
    </linearGradient>
    <linearGradient id="waveArea" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#C50337" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#C50337" stop-opacity="0.02"/>
    </linearGradient>
    <filter id="waveGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <style>
      .sans {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace; }}
      .pipe-flow {{
        stroke-dasharray: 18 96;
        animation: pipeMove 2.2s linear infinite;
      }}
      .pipe-flow-alt {{
        stroke-dasharray: 10 104;
        animation: pipeMove 2.2s linear -1.1s infinite;
      }}
      .blink-cur {{ animation: blinkCur 0.9s steps(2, start) infinite; }}
      @keyframes pipeMove {{
        from {{ stroke-dashoffset: 114; }}
        to {{ stroke-dashoffset: 0; }}
      }}
      @keyframes blinkCur {{
        0%, 49% {{ opacity: 1; }}
        50%, 100% {{ opacity: 0; }}
      }}
    </style>
  </defs>

  <rect x="1.5" y="1.5" width="1197" height="337" rx="18" fill="url(#dtBg)" stroke="url(#dtBorder)" stroke-width="1.5"/>

  <!-- Header -->
  <text x="32" y="40" fill="#F4F4F5" font-size="20" font-weight="700" class="sans">Builder Activity</text>
  <text x="192" y="40" fill="#666666" font-size="12" class="mono">:: ARCHITECTURE PIPELINE &amp; VELOCITY WAVEFORM</text>

  <!-- Left Panel: Animated Architecture Pipeline (x=30..532) -->
  <rect x="30" y="60" width="502" height="256" rx="14" fill="url(#dtCard)" stroke="#222226" stroke-width="1.2"/>
  <circle cx="52" cy="82" r="4" fill="#C50337"/>
  <circle cx="66" cy="82" r="4" fill="#666666"/>
  <circle cx="80" cy="82" r="4" fill="#E5E5E5" opacity="0.7"/>
  <text x="281" y="86" text-anchor="middle" fill="#666666" font-size="11" class="mono">cabdevx :: production-flow</text>
  <line x1="30" y1="98" x2="532" y2="98" stroke="#1D1D22" stroke-width="1"/>

  <!-- Pipeline Connector Line + Dual Traveling Pulses -->
  <line x1="92" y1="158" x2="468" y2="158" stroke="#262626" stroke-width="2.5"/>
  <line x1="92" y1="158" x2="468" y2="158" stroke="#C50337" stroke-width="2.8" class="pipe-flow" filter="url(#waveGlow)"/>
  <line x1="92" y1="158" x2="468" y2="158" stroke="#F4F4F5" stroke-width="2" class="pipe-flow-alt"/>

  <!-- 4 Sequentially Pulsing Pipeline Stage Nodes -->
  <g transform="translate(56, 126)">
    <rect x="0" y="0" width="84" height="64" rx="10" fill="#090909" stroke="#C50337" stroke-width="1.2">
      <animate attributeName="stroke-opacity" values="0.35;1;0.35" dur="3.2s" begin="0s" repeatCount="indefinite"/>
    </rect>
    <circle cx="42" cy="18" r="5" fill="#C50337">
      <animate attributeName="r" values="4;6.2;4" dur="3.2s" begin="0s" repeatCount="indefinite"/>
    </circle>
    <text x="42" y="39" text-anchor="middle" fill="#F4F4F5" font-size="11.5" font-weight="700" class="mono">UI</text>
    <text x="42" y="54" text-anchor="middle" fill="#888888" font-size="9.5" class="mono">Next.js</text>
  </g>

  <g transform="translate(172, 126)">
    <rect x="0" y="0" width="84" height="64" rx="10" fill="#090909" stroke="#C50337" stroke-width="1.2">
      <animate attributeName="stroke-opacity" values="0.35;1;0.35" dur="3.2s" begin="0.8s" repeatCount="indefinite"/>
    </rect>
    <circle cx="42" cy="18" r="5" fill="#F4F4F5">
      <animate attributeName="r" values="4;6.2;4" dur="3.2s" begin="0.8s" repeatCount="indefinite"/>
    </circle>
    <text x="42" y="39" text-anchor="middle" fill="#F4F4F5" font-size="11.5" font-weight="700" class="mono">API</text>
    <text x="42" y="54" text-anchor="middle" fill="#888888" font-size="9.5" class="mono">Django/Fast</text>
  </g>

  <g transform="translate(288, 126)">
    <rect x="0" y="0" width="84" height="64" rx="10" fill="#090909" stroke="#C50337" stroke-width="1.2">
      <animate attributeName="stroke-opacity" values="0.35;1;0.35" dur="3.2s" begin="1.6s" repeatCount="indefinite"/>
    </rect>
    <circle cx="42" cy="18" r="5" fill="#FF3366">
      <animate attributeName="r" values="4;6.2;4" dur="3.2s" begin="1.6s" repeatCount="indefinite"/>
    </circle>
    <text x="42" y="39" text-anchor="middle" fill="#F4F4F5" font-size="11.5" font-weight="700" class="mono">DATA</text>
    <text x="42" y="54" text-anchor="middle" fill="#888888" font-size="9.5" class="mono">SQL · ML</text>
  </g>

  <g transform="translate(404, 126)">
    <rect x="0" y="0" width="92" height="64" rx="10" fill="#090909" stroke="#C50337" stroke-width="1.2">
      <animate attributeName="stroke-opacity" values="0.35;1;0.35" dur="3.2s" begin="2.4s" repeatCount="indefinite"/>
    </rect>
    <circle cx="46" cy="18" r="5" fill="#C50337" filter="url(#waveGlow)">
      <animate attributeName="r" values="4;6.2;4" dur="3.2s" begin="2.4s" repeatCount="indefinite"/>
    </circle>
    <text x="46" y="39" text-anchor="middle" fill="#F4F4F5" font-size="11.5" font-weight="700" class="mono">DEPLOY</text>
    <text x="46" y="54" text-anchor="middle" fill="#888888" font-size="9.5" class="mono">Docker</text>
  </g>

  <!-- Concise Terminal Output inside Left Panel -->
  <rect x="52" y="212" width="458" height="84" rx="10" fill="#02060E" stroke="#1E1E24"/>
  <text x="68" y="236" fill="#C50337" font-size="11.5" class="mono">❯ <tspan fill="#D4D4D8">status:</tspan> <tspan fill="#F4F4F5">building full-stack &amp; ML products</tspan></text>
  <text x="68" y="258" fill="#666666" font-size="11.5" class="mono">  stack:  <tspan fill="#A3A3A3">TypeScript · Python · PostgreSQL · Docker</tspan></text>
  <text x="68" y="280" fill="#666666" font-size="11.5" class="mono">  goal:   <tspan fill="#FF4D79">clean UI + solid APIs + real impact</tspan></text>
  <rect x="382" y="269" width="7" height="13" rx="1" fill="#C50337" class="blink-cur"/>

  <!-- Right Panel: Weekly Velocity Waveform + Micro-Dot Matrix (x=552..1170) -->
  <rect x="552" y="60" width="618" height="256" rx="14" fill="url(#dtCard)" stroke="#222226" stroke-width="1.2"/>
  <text x="578" y="86" fill="#E5E5E5" font-size="12.5" font-weight="700" class="sans">Pulso semanal (24 semanas)</text>
  <text x="1142" y="86" text-anchor="end" fill="#888888" font-size="11" class="mono">{m["total_contribs"]} contribs / año</text>

  <!-- Baseline & Animated Waveform -->
  <line x1="578" y1="166" x2="1142" y2="166" stroke="#1E1E24" stroke-width="1"/>
  <path d="{area_d}" fill="url(#waveArea)"/>
  <path d="{line_d}" fill="none" stroke="#C50337" stroke-width="2.4" stroke-linecap="round" filter="url(#waveGlow)"/>

  <!-- Peak Sonar Ripple Beacon -->
  <circle cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="4.5" fill="none" stroke="#FF3366" stroke-width="1.5">
    <animate attributeName="r" values="4;15" dur="2.2s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.85;0" dur="2.2s" repeatCount="indefinite"/>
  </circle>
  <circle cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="4.5" fill="#F4F4F5" stroke="#C50337" stroke-width="2"/>

  <!-- Live Tracer Orb Riding the Waveform -->
  <circle r="4.2" fill="#FFFFFF" stroke="#C50337" stroke-width="2" filter="url(#waveGlow)">
    <animateMotion path="{line_d}" dur="4.5s" repeatCount="indefinite"/>
  </circle>

  <!-- Micro-Dot Contribution Matrix -->
  {"".join(dots)}

  <!-- Stack Focus Legend + Segmented Bar -->
  <text x="578" y="294" fill="#888888" font-size="10.5" class="mono">
    <tspan fill="#FF3366">{escape(f0[0])} {f0[1]}%</tspan>  ·  <tspan fill="#F4F4F5">{escape(f1[0])} {f1[1]}%</tspan>  ·  <tspan fill="#888888">{escape(f2[0])} {f2[1]}%</tspan>
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
