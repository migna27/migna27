#!/usr/bin/env python3
"""Generate cyberpunk HUD SVG telemetry cards for Miguel's GitHub profile."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import sys
import urllib.error
import urllib.request

LANGUAGE_COLORS = {
    "Python": "#00A8FF",
    "JavaScript": "#FF2A85",
    "TypeScript": "#2979FF",
    "HTML": "#FF1744",
    "CSS": "#38BDF8",
    "GDScript": "#00C8FF",
    "Ren'Py": "#FF4D8D",
    "C#": "#60A5FA",
    "C++": "#F43F5E",
    "C": "#E11D48",
    "Java": "#FB7185",
    "Shell": "#0EA5E9",
    "Jupyter Notebook": "#3B82F6",
    "Otros": "#64748B",
}

FALLBACK_PALETTE = [
    "#00A8FF",
    "#FF2A85",
    "#2979FF",
    "#FF1744",
    "#38BDF8",
    "#FB7185",
]


def pick_language_color(lang: str, idx: int) -> str:
    return LANGUAGE_COLORS.get(lang, FALLBACK_PALETTE[idx % len(FALLBACK_PALETTE)])


def api_get_json(url: str, token: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "migna27-profile-telemetry",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_repos(username: str, metrics_token: str, github_token: str) -> list[dict]:
    token = metrics_token or github_token
    repos: list[dict] = []
    page = 1

    while True:
        if metrics_token:
            url = (
                "https://api.github.com/user/repos"
                f"?affiliation=owner&visibility=all&per_page=100&page={page}"
            )
        else:
            url = (
                f"https://api.github.com/users/{username}/repos"
                f"?type=owner&per_page=100&page={page}"
            )

        batch = api_get_json(url, token)
        if not isinstance(batch, list) or not batch:
            break

        for repo in batch:
            owner_login = repo.get("owner", {}).get("login", "")
            if owner_login.lower() == username.lower():
                repos.append(repo)

        if len(batch) < 100:
            break
        page += 1

    return repos


def collect_github_metrics(
    username: str,
    metrics_token: str,
    github_token: str,
    include_profile_repo: bool,
) -> dict:
    token = metrics_token or github_token
    user_info = api_get_json(f"https://api.github.com/users/{username}", token)
    repos = fetch_all_repos(username, metrics_token, github_token)

    own_non_fork = [r for r in repos if not r.get("fork")]
    total_stars = sum(int(r.get("stargazers_count", 0)) for r in own_non_fork)
    total_forks = sum(int(r.get("forks_count", 0)) for r in own_non_fork)

    lang_totals: dict[str, int] = {}
    analyzed_repos = 0
    for repo in own_non_fork:
        full_name = repo.get("full_name", "")
        if not include_profile_repo and full_name.lower() == f"{username}/{username}".lower():
            continue

        langs_url = repo.get("languages_url")
        if not langs_url:
            continue

        analyzed_repos += 1
        lang_map = api_get_json(langs_url, token)
        if isinstance(lang_map, dict):
            for lang, byte_count in lang_map.items():
                if isinstance(byte_count, int) and byte_count > 0:
                    lang_totals[lang] = lang_totals.get(lang, 0) + byte_count

    return {
        "username": username,
        "followers": int(user_info.get("followers", 0)) if isinstance(user_info, dict) else 0,
        "repos_count": len(own_non_fork),
        "analyzed_repos": analyzed_repos,
        "total_stars": total_stars,
        "total_forks": total_forks,
        "lang_totals": lang_totals,
        "sync_date": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
    }


def summarize_languages(lang_totals: dict[str, int], max_items: int = 8) -> tuple[list[tuple[str, int, float, str]], int]:
    total_bytes = sum(lang_totals.values())
    if total_bytes <= 0:
        return [], 0

    sorted_langs = sorted(lang_totals.items(), key=lambda item: (-item[1], item[0]))
    if len(sorted_langs) > max_items:
        head = sorted_langs[: max_items - 1]
        tail_bytes = sum(b for _, b in sorted_langs[max_items - 1 :])
        other_label = "Otros" if "Otros" not in dict(head) else "Otros lenguajes"
        head.append((other_label, tail_bytes))
        sorted_langs = head

    summary: list[tuple[str, int, float, str]] = []
    for idx, (lang, byte_count) in enumerate(sorted_langs):
        pct = (byte_count / total_bytes) * 100.0
        summary.append((lang, byte_count, pct, pick_language_color(lang, idx)))
    return summary, total_bytes


def render_top_langs_svg(
    summary: list[tuple[str, int, float, str]],
    analyzed_repos: int,
    sync_date: str,
    placeholder: bool = False,
) -> str:
    if placeholder:
        height = 220
        subtitle = f"SYNC: {sync_date} UTC // PENDIENTE DE PRIMERA EJECUCIÓN"
        body = (
            '  <rect x="28" y="84" width="744" height="102" rx="4" fill="#101320" stroke="#00A8FF" stroke-opacity="0.45" stroke-width="1.2"/>\n'
            '  <text x="400" y="124" text-anchor="middle" fill="#F1F5F9" font-family="Consolas, \'Fira Code\', monospace" font-size="14" font-weight="bold">SINCRONIZACIÓN PENDIENTE // EJECUTA EL WORKFLOW DE GITHUB ACTIONS</text>\n'
            '  <text x="400" y="150" text-anchor="middle" fill="#94A3B8" font-family="Consolas, \'Fira Code\', monospace" font-size="11.5">Esta tarjeta calculará automáticamente el porcentaje exacto de código en tus repositorios.</text>\n'
            '  <text x="400" y="170" text-anchor="middle" fill="#00A8FF" font-family="Consolas, \'Fira Code\', monospace" font-size="10.5">Actions &gt; Update GitHub Telemetry &gt; Run workflow</text>'
        )
    elif not summary:
        height = 220
        subtitle = f"{analyzed_repos} REPOS ANALIZADOS // SYNC: {sync_date} UTC"
        body = (
            '  <rect x="28" y="84" width="744" height="102" rx="4" fill="#101320" stroke="#FF1744" stroke-opacity="0.45" stroke-width="1.2"/>\n'
            '  <text x="400" y="124" text-anchor="middle" fill="#F1F5F9" font-family="Consolas, \'Fira Code\', monospace" font-size="14" font-weight="bold">0 REPOS PÚBLICOS CON CÓDIGO DETECTADOS</text>\n'
            '  <text x="400" y="150" text-anchor="middle" fill="#94A3B8" font-family="Consolas, \'Fira Code\', monospace" font-size="11.5">Publica tus repositorios o configura el secret METRICS_TOKEN para incluir repos privados.</text>\n'
            '  <text x="400" y="170" text-anchor="middle" fill="#FF2A85" font-family="Consolas, \'Fira Code\', monospace" font-size="10.5">Settings &gt; Secrets and variables &gt; Actions &gt; METRICS_TOKEN</text>'
        )
    else:
        rows = (len(summary) + 1) // 2
        height = 122 + rows * 44 + 18

        bar_x = 28
        bar_y = 74
        bar_total_w = 744
        segments: list[str] = []
        cursor_x = float(bar_x)
        for idx, (lang, _, pct, color) in enumerate(summary):
            if idx == len(summary) - 1:
                seg_w = max(0.0, (bar_x + bar_total_w) - cursor_x)
            else:
                seg_w = (pct / 100.0) * bar_total_w
            if seg_w > 0:
                segments.append(
                    f'    <rect x="{cursor_x:.2f}" y="{bar_y}" width="{seg_w:.2f}" height="14" fill="{color}"/>'
                )
            cursor_x += seg_w

        grid_items: list[str] = []
        col_x = [28, 412]
        track_w = 356
        start_y = 118
        row_pitch = 44

        for idx, (lang, _, pct, color) in enumerate(summary):
            col = idx % 2
            row = idx // 2
            x = col_x[col]
            y = start_y + row * row_pitch
            esc_lang = html.escape(lang, quote=True)
            pct_str = f"{pct:.1f}%"
            fill_w = max(4.0, (pct / 100.0) * track_w)
            grid_items.append(
                f'  <circle cx="{x + 6}" cy="{y + 6}" r="5" fill="{color}"/>\n'
                f'  <text x="{x + 19}" y="{y + 10}" fill="#F1F5F9" font-family="Consolas, \'Fira Code\', monospace" font-size="12.5" font-weight="bold">{esc_lang}</text>\n'
                f'  <text x="{x + track_w}" y="{y + 10}" text-anchor="end" fill="{color}" font-family="Consolas, \'Fira Code\', monospace" font-size="12.5" font-weight="bold">{pct_str}</text>\n'
                f'  <rect x="{x}" y="{y + 18}" width="{track_w}" height="7" rx="2" fill="#101320" stroke="#1A1E33" stroke-width="0.8"/>\n'
                f'  <rect x="{x}" y="{y + 18}" width="{fill_w:.2f}" height="7" rx="2" fill="{color}"/>'
            )

        subtitle = f"{analyzed_repos} REPOS ANALIZADOS // SYNC: {sync_date} UTC"
        body = (
            f'  <rect x="{bar_x}" y="{bar_y}" width="{bar_total_w}" height="14" rx="3" fill="#101320" stroke="#1A1E33" stroke-width="1"/>\n'
            '  <clipPath id="barClip">\n'
            f'    <rect x="{bar_x}" y="{bar_y}" width="{bar_total_w}" height="14" rx="3"/>\n'
            '  </clipPath>\n'
            '  <g clip-path="url(#barClip)">\n'
            + "\n".join(segments)
            + "\n  </g>\n"
            + "\n".join(grid_items)
        )

    esc_subtitle = html.escape(subtitle, quote=True)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 {height}" width="800" height="{height}" fill="none">\n'
        '  <defs>\n'
        '    <pattern id="langsScan" width="4" height="4" patternUnits="userSpaceOnUse">\n'
        '      <rect width="4" height="1" fill="#00A8FF" opacity="0.045"/>\n'
        '    </pattern>\n'
        '  </defs>\n'
        f'  <polygon points="16,4 784,4 796,16 796,{height - 16} 784,{height - 4} 16,{height - 4} 4,{height - 16} 4,16" fill="#0B0D14" stroke="#1A1E33" stroke-width="1.5"/>\n'
        f'  <polygon points="16,4 784,4 796,16 796,{height - 16} 784,{height - 4} 16,{height - 4} 4,{height - 16} 4,16" fill="url(#langsScan)"/>\n'
        f'  <polygon points="14,3 782,3 794,15 794,{height - 17} 782,{height - 5} 14,{height - 5} 2,{height - 17} 2,15" stroke="#FF1744" stroke-width="1" opacity="0.3"/>\n'
        f'  <polygon points="18,5 786,5 798,17 798,{height - 15} 786,{height - 3} 18,{height - 3} 6,{height - 15} 6,17" stroke="#00A8FF" stroke-width="1" opacity="0.3"/>\n'
        '  <path d="M4 34 L4 16 L16 4 L44 4" stroke="#FF1744" stroke-width="2.5"/>\n'
        '  <path d="M756 4 L784 4 L796 16 L796 34" stroke="#00A8FF" stroke-width="2.5"/>\n'
        f'  <path d="M4 {height - 34} L4 {height - 16} L16 {height - 4} L44 {height - 4}" stroke="#00A8FF" stroke-width="2.5"/>\n'
        f'  <path d="M756 {height - 4} L784 {height - 4} L796 {height - 16} L796 {height - 34}" stroke="#FF2A85" stroke-width="2.5"/>\n'
        '  <rect x="24" y="18" width="752" height="36" fill="#101320" stroke="#1A1E33" stroke-width="1"/>\n'
        '  <rect x="24" y="18" width="5" height="36" fill="#FF1744"/>\n'
        '  <text x="38" y="41" fill="#FF1744" font-family="Consolas, \'Fira Code\', monospace" font-size="13.5" font-weight="bold" letter-spacing="1" opacity="0.45">[ TELEMETRY // LENGUAJES EN REPOSITORIOS ]</text>\n'
        '  <text x="40" y="41" fill="#00A8FF" font-family="Consolas, \'Fira Code\', monospace" font-size="13.5" font-weight="bold" letter-spacing="1" opacity="0.45">[ TELEMETRY // LENGUAJES EN REPOSITORIOS ]</text>\n'
        '  <text x="39" y="41" fill="#F1F5F9" font-family="Consolas, \'Fira Code\', monospace" font-size="13.5" font-weight="bold" letter-spacing="1">[ TELEMETRY // LENGUAJES EN REPOSITORIOS ]</text>\n'
        f'  <text x="762" y="40" text-anchor="end" fill="#94A3B8" font-family="Consolas, \'Fira Code\', monospace" font-size="10.5">{esc_subtitle}</text>\n'
        f'{body}\n'
        '</svg>\n'
    )


def render_overview_svg(metrics: dict, top_lang: str, placeholder: bool = False) -> str:
    sync_date = html.escape(str(metrics.get("sync_date", "----")), quote=True)
    if placeholder:
        vals = ["SYNC...", "SYNC...", "SYNC...", "PENDING"]
    else:
        vals = [
            str(metrics.get("repos_count", 0)),
            str(metrics.get("total_stars", 0)),
            str(metrics.get("followers", 0)),
            top_lang or "N/A",
        ]

    cards = [
        ("REPOSITORIOS", vals[0], "#00A8FF"),
        ("ESTRELLAS", vals[1], "#FF1744"),
        ("SEGUIDORES", vals[2], "#FF2A85"),
        ("LENGUAJE TOP", vals[3], "#2979FF"),
    ]

    boxes: list[str] = []
    start_x = 24
    box_w = 176
    gap = 16
    for idx, (label, val, accent) in enumerate(cards):
        x = start_x + idx * (box_w + gap)
        esc_label = html.escape(label, quote=True)
        esc_val = html.escape(val, quote=True)
        font_size = 22 if len(esc_val) <= 8 else 16
        boxes.append(
            f'  <rect x="{x}" y="68" width="{box_w}" height="82" rx="3" fill="#101320" stroke="{accent}" stroke-opacity="0.55" stroke-width="1.2"/>\n'
            f'  <rect x="{x}" y="68" width="{box_w}" height="4" fill="{accent}"/>\n'
            f'  <text x="{x + box_w // 2}" y="95" text-anchor="middle" fill="#94A3B8" font-family="Consolas, \'Fira Code\', monospace" font-size="11" font-weight="bold" letter-spacing="1">{esc_label}</text>\n'
            f'  <text x="{x + box_w // 2}" y="130" text-anchor="middle" fill="#F1F5F9" font-family="Consolas, \'Fira Code\', monospace" font-size="{font_size}" font-weight="bold">{esc_val}</text>'
        )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 175" width="800" height="175" fill="none">\n'
        '  <defs>\n'
        '    <pattern id="ovScan" width="4" height="4" patternUnits="userSpaceOnUse">\n'
        '      <rect width="4" height="1" fill="#FF1744" opacity="0.04"/>\n'
        '    </pattern>\n'
        '  </defs>\n'
        '  <polygon points="16,4 784,4 796,16 796,159 784,171 16,171 4,159 4,16" fill="#0B0D14" stroke="#1A1E33" stroke-width="1.5"/>\n'
        '  <polygon points="16,4 784,4 796,16 796,159 784,171 16,171 4,159 4,16" fill="url(#ovScan)"/>\n'
        '  <path d="M4 34 L4 16 L16 4 L44 4" stroke="#00A8FF" stroke-width="2.5"/>\n'
        '  <path d="M756 4 L784 4 L796 16 L796 34" stroke="#FF1744" stroke-width="2.5"/>\n'
        '  <path d="M4 141 L4 159 L16 171 L44 171" stroke="#FF2A85" stroke-width="2.5"/>\n'
        '  <path d="M756 171 L784 171 L796 159 L796 141" stroke="#00A8FF" stroke-width="2.5"/>\n'
        '  <rect x="24" y="18" width="752" height="34" fill="#101320" stroke="#1A1E33" stroke-width="1"/>\n'
        '  <rect x="24" y="18" width="5" height="34" fill="#00A8FF"/>\n'
        '  <text x="39" y="40" fill="#F1F5F9" font-family="Consolas, \'Fira Code\', monospace" font-size="13.5" font-weight="bold" letter-spacing="1">[ TELEMETRY // RESUMEN DE CUENTA ]</text>\n'
        f'  <text x="762" y="39" text-anchor="end" fill="#94A3B8" font-family="Consolas, \'Fira Code\', monospace" font-size="10.5">USER: {html.escape(str(metrics.get("username", "migna27")), quote=True)} // SYNC: {sync_date} UTC</text>\n'
        + "\n".join(boxes)
        + "\n</svg>\n"
    )


def write_svg(path: str, content: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update GitHub profile language & overview SVGs.")
    parser.add_argument("--username", default=os.environ.get("GITHUB_USERNAME", "migna27"))
    parser.add_argument("--langs-out", default="assets/top-langs.svg")
    parser.add_argument("--overview-out", default="assets/github-overview.svg")
    parser.add_argument("--include-profile-repo", action="store_true")
    parser.add_argument("--test-sample", action="store_true")
    parser.add_argument("--placeholder", action="store_true")
    args = parser.parse_args()

    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    if args.test_sample:
        metrics = {
            "username": args.username,
            "followers": 12,
            "repos_count": 9,
            "analyzed_repos": 8,
            "total_stars": 24,
            "total_forks": 3,
            "lang_totals": {
                "Python": 45200,
                "GDScript": 28400,
                "JavaScript": 16100,
                "HTML": 9800,
                "CSS": 7400,
                "Ren'Py": 6100,
                "C++": 3200,
            },
            "sync_date": today,
        }
        summary, _ = summarize_languages(metrics["lang_totals"])
        top_lang = summary[0][0] if summary else "N/A"
        write_svg(args.langs_out, render_top_langs_svg(summary, metrics["analyzed_repos"], today))
        write_svg(args.overview_out, render_overview_svg(metrics, top_lang))
        print(f"Sample SVGs written to {args.langs_out} and {args.overview_out}")
        return 0

    if args.placeholder:
        metrics = {
            "username": args.username,
            "followers": 0,
            "repos_count": 0,
            "analyzed_repos": 0,
            "total_stars": 0,
            "total_forks": 0,
            "lang_totals": {},
            "sync_date": today,
        }
        write_svg(args.langs_out, render_top_langs_svg([], 0, today, placeholder=True))
        write_svg(args.overview_out, render_overview_svg(metrics, "PENDING", placeholder=True))
        print(f"Placeholder SVGs written to {args.langs_out} and {args.overview_out}")
        return 0

    metrics_token = os.environ.get("METRICS_TOKEN", "").strip()
    github_token = os.environ.get("GITHUB_TOKEN", "").strip()

    try:
        metrics = collect_github_metrics(
            username=args.username,
            metrics_token=metrics_token,
            github_token=github_token,
            include_profile_repo=args.include_profile_repo,
        )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Failed to fetch GitHub telemetry for {args.username}: {exc}", file=sys.stderr)
        return 1

    summary, _ = summarize_languages(metrics["lang_totals"])
    top_lang = summary[0][0] if summary else "N/A"
    write_svg(args.langs_out, render_top_langs_svg(summary, metrics["analyzed_repos"], metrics["sync_date"]))
    write_svg(args.overview_out, render_overview_svg(metrics, top_lang))
    print(
        f"Updated telemetry for {args.username}: "
        f"{metrics['repos_count']} repos, {metrics['analyzed_repos']} analyzed, "
        f"{len(summary)} language buckets, top={top_lang}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
