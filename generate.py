
from pathlib import Path
from datetime import date
import argparse
import math
import yaml
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
import base64

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUT = ROOT / "output"

def truthy(v):
    return str(v).strip().lower() in {"true", "1", "yes", "y", "x"}

def load_config():
    with open(ROOT / "config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    active = cfg["theme"]["active"]
    cfg["colors"] = cfg["theme"]["palettes"][active]
    return cfg

def load_local_csv():
    return pd.read_csv(DATA / "shows.csv"), pd.read_csv(DATA / "releases.csv")

def load_google_sheet(sheet_id, credentials_json):
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_file(credentials_json, scopes=scopes)
    gc = gspread.authorize(creds)
    book = gc.open_by_key(sheet_id)

    shows = pd.DataFrame(book.worksheet("Shows").get_all_records())
    releases = pd.DataFrame(book.worksheet("Releases").get_all_records())
    return shows, releases

def resolve_week(cfg, explicit_week=None):
    if explicit_week:
        start = pd.Timestamp(explicit_week).normalize()
    else:
        current = pd.Timestamp(date.today()).normalize()
        target = int(cfg["schedule"].get("week_start_weekday", 4))
        upcoming = bool(cfg["schedule"].get("upcoming_before_start_day", True))

        wd = current.weekday()
        if wd == target:
            delta = 0
        elif upcoming and wd < target:
            delta = target - wd
        else:
            delta = -((wd - target) % 7)

        start = current + pd.Timedelta(days=delta)

    end = start + pd.Timedelta(days=int(cfg["schedule"].get("week_length_days", 7)) - 1)
    return start, end

def filter_week(df, date_col, start, end):
    if df.empty:
        return df.copy()

    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce").dt.normalize()
    out = out[out[date_col].notna()]
    out = out[(out[date_col] >= start) & (out[date_col] <= end)]

    if "include" in out.columns:
        out = out[out["include"].map(truthy)]

    return out

def prep_shows(df):
    if df.empty:
        return []

    df = df.sort_values(["date", "venue"])
    groups = []

    for show_date, day_df in df.groupby("date", sort=True):
        events = []
        for _, row in day_df.iterrows():
            bands = [x.strip() for x in str(row["bands"]).split("|") if x.strip()]
            events.append({
                "venue": str(row["venue"]).strip(),
                "bands_display": " • ".join(bands),
            })

        groups.append({
            "date": show_date,
            "day": show_date.strftime("%a").upper(),
            "short_date": f"{show_date.month}/{show_date.day}",
            "events": events,
        })
    return groups

def prep_releases(df, types):
    if df.empty:
        return []

    allowed = {t.lower() for t in types}
    df = df[df["type"].astype(str).str.lower().isin(allowed)]
    df = df.sort_values(["artist", "title"])

    return [
        {"artist": str(row["artist"]).strip(), "title": str(row["title"]).strip()}
        for _, row in df.iterrows()
    ]

def estimate_show_lines(groups):
    lines = 0.0
    for group in groups:
        lines += 0.55
        for event in group["events"]:
            chars = len(event["bands_display"])
            lines += 1.0 + max(0, math.ceil(chars / 46) - 1) * 0.85
            lines += 0.55
    return max(lines, 1)

def choose_show_sizes(groups, cfg):
    density = estimate_show_lines(groups)
    mx = cfg["layout"]["show_max_font_px"]
    mn = cfg["layout"]["show_min_font_px"]

    if density <= 12:
        font = mx
    elif density <= 16:
        font = mx - 3
    elif density <= 20:
        font = mx - 6
    elif density <= 24:
        font = mx - 8
    else:
        font = mn

    return max(mn, font), max(20, int(font * 0.70))

def choose_release_sizes(items, cfg):
    n = len(items)
    mx = cfg["layout"]["release_max_font_px"]
    mn = cfg["layout"]["release_min_font_px"]

    if n <= 8:
        font, cols = mx, 1
    elif n <= 12:
        font, cols = mx - 3, 2
    elif n <= 18:
        font, cols = mx - 6, 2
    else:
        font, cols = mn, 2

    return max(mn, font), max(18, int(font * 0.72)), cols

def resolve_font_file(filename):
    if not filename:
        return ""

    path = STATIC / "fonts" / filename

    if not path.exists():
        print(f"WARNING: Font not found: {path}")
        return ""

    suffix = path.suffix.lower()

    mime_types = {
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
    }

    mime = mime_types.get(
        suffix,
        "application/octet-stream"
    )

    encoded = base64.b64encode(
        path.read_bytes()
    ).decode("ascii")

    print(f"Loaded font: {filename}")

    return f"data:{mime};base64,{encoded}"

def resolve_background(cfg):
    filename = cfg["images"].get("okc_background", "").strip()
    if not filename:
        return ""
    p = (STATIC / "images" / filename).resolve()
    return p.as_uri() if p.exists() else ""

def week_label(start, end):
    if start.month == end.month:
        line1 = f"{start.strftime('%b').upper()} {start.day}–{end.day}"
    else:
        line1 = f"{start.strftime('%b').upper()} {start.day}–{end.strftime('%b').upper()} {end.day}"
    return line1, str(start.year)

def render_html(env, cfg, **kwargs):
    return env.get_template("slide.html").render(**cfg, **kwargs)

def png_from_html(browser, html, html_path, png_path, width, height):
    html_path.write_text(html, encoding="utf-8")
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
    page.goto(html_path.resolve().as_uri(), wait_until="load")
    # Wait until all @font-face resources have actually loaded
    page.wait_for_function(
        "document.fonts.status === 'loaded'"
    )

    loaded = page.evaluate("""
        document.fonts.check('100px "OMW Display"')
    """)

    print(f"OMW Display loaded: {loaded}")
    
    page.screenshot(
        path=str(png_path),
        full_page=False
    )
    page.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet-id", help="Google Sheet ID")
    ap.add_argument("--credentials", help="Service-account JSON path")
    ap.add_argument("--week", help="Edition start date YYYY-MM-DD")
    args = ap.parse_args()

    cfg = load_config()

    if args.sheet_id and args.credentials:
        shows_raw, releases_raw = load_google_sheet(args.sheet_id, args.credentials)
        source = "Google Sheets"
    else:
        shows_raw, releases_raw = load_local_csv()
        source = "CSV"

    start, end = resolve_week(cfg, args.week)
    shows_df = filter_week(shows_raw, "date", start, end)
    releases_df = filter_week(releases_raw, "release_date", start, end)

    day_groups = prep_shows(shows_df)
    albums = prep_releases(releases_df, ["Album", "EP"])
    singles = prep_releases(releases_df, ["Single"])

    show_font, venue_font = choose_show_sizes(day_groups, cfg)
    album_font, album_title_font, album_cols = choose_release_sizes(albums, cfg)
    single_font, single_title_font, single_cols = choose_release_sizes(singles, cfg)

    week_line_1, week_line_2 = week_label(start, end)

    font_files = {
        "display": resolve_font_file(cfg["typography"].get("display_file", "")),
        "condensed": resolve_font_file(cfg["typography"].get("condensed_file", "")),
        "body": resolve_font_file(cfg["typography"].get("body_file", "")),
    }
    background_image = resolve_background(cfg)

    slides = [
        dict(kind="shows", slide_class="shows-1", watermark="", kicker="OKC METAL WEEKLY", heading="LIVE NOISE",
             day_groups=day_groups, items=[],
             footer="YOUR WEEKLY GUIDE TO HEAVY MUSIC IN OKC", page_num=1,
             release_columns=1, release_font_px=30, release_title_font_px=22),
        dict(kind="releases", slide_class="releases-2", watermark="02", kicker="NEW NOISE", heading="ALBUMS + EPS",
             day_groups=[], items=albums, footer="FULL LIST • NO FILLER", page_num=2,
             release_columns=album_cols, release_font_px=album_font,
             release_title_font_px=album_title_font),
        dict(kind="releases", slide_class="releases-3", watermark="03", kicker="NEW NOISE", heading="SINGLES",
             day_groups=[], items=singles, footer="WHAT ARE YOU LISTENING TO?", page_num=3,
             release_columns=single_cols, release_font_px=single_font,
             release_title_font_px=single_title_font),
        dict(kind="support", slide_class="support-4", watermark="", kicker="SUPPORT THE SCENE", heading="KEEP IT HEAVY",
             day_groups=[], items=[],
             footer="SUPPORT LOCAL • SHOW UP • BRING PEOPLE WITH YOU", page_num=4,
             release_columns=1, release_font_px=30, release_title_font_px=22),
    ]

    edition_dir = OUT / f"{start:%Y-%m-%d}_to_{end:%Y-%m-%d}"
    edition_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)

    print(f"Source: {source}")
    print(f"Edition: {start:%Y-%m-%d} through {end:%Y-%m-%d}")
    print(f"Show rows: {len(shows_df)} | Albums/EPs: {len(albums)} | Singles: {len(singles)}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for slide in slides:
            html = render_html(
                env, cfg, **slide, page_total=4,
                week_line_1=week_line_1, week_line_2=week_line_2,
                show_font_px=show_font, show_venue_font_px=venue_font,
                font_files=font_files,
                background_image=background_image if slide["kind"] in {"shows", "support"} else "",
            )
            stem = f"{slide['page_num']:02d}"
            png_from_html(
                browser, html,
                edition_dir / f"{stem}.html",
                edition_dir / f"{stem}.png",
                cfg["canvas"]["width"], cfg["canvas"]["height"]
            )
            print(f"Wrote {edition_dir / f'{stem}.png'}")
        browser.close()

    print(f"Done: {edition_dir}")

if __name__ == "__main__":
    main()
