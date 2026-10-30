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
    return (
        pd.read_csv(DATA / "shows.csv"),
        pd.read_csv(DATA / "releases.csv"),
    )


def load_google_sheet(sheet_id, credentials_json):
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    creds = Credentials.from_service_account_file(
        credentials_json,
        scopes=scopes,
    )

    gc = gspread.authorize(creds)
    book = gc.open_by_key(sheet_id)

    shows = pd.DataFrame(
        book.worksheet("Shows").get_all_records()
    )

    releases = pd.DataFrame(
        book.worksheet("Releases").get_all_records()
    )

    return shows, releases


def resolve_week(cfg, explicit_week=None):
    if explicit_week:
        start = pd.Timestamp(explicit_week).normalize()

    else:
        current = pd.Timestamp(date.today()).normalize()

        target = int(
            cfg["schedule"].get("week_start_weekday", 4)
        )

        upcoming = bool(
            cfg["schedule"].get(
                "upcoming_before_start_day",
                True,
            )
        )

        wd = current.weekday()

        if wd == target:
            delta = 0

        elif upcoming and wd < target:
            delta = target - wd

        else:
            delta = -((wd - target) % 7)

        start = current + pd.Timedelta(days=delta)

    week_length = int(
        cfg["schedule"].get("week_length_days", 7)
    )

    end = start + pd.Timedelta(days=week_length - 1)

    return start, end


def filter_week(df, date_col, start, end):
    if df.empty:
        return df.copy()

    out = df.copy()

    out[date_col] = pd.to_datetime(
        out[date_col],
        errors="coerce",
    ).dt.normalize()

    out = out[out[date_col].notna()]

    out = out[
        (out[date_col] >= start)
        & (out[date_col] <= end)
    ]

    if "include" in out.columns:
        out = out[out["include"].map(truthy)]

    return out


def prep_shows(df):
    if df.empty:
        return []

    df = df.sort_values(["date", "venue"])

    groups = []

    for show_date, day_df in df.groupby(
        "date",
        sort=True,
    ):
        events = []

        for _, row in day_df.iterrows():
            bands = [
                x.strip()
                for x in str(row["bands"]).split("|")
                if x.strip()
            ]

            notation = ""

            if (
                "Notations" in row.index
                and pd.notna(row["Notations"])
            ):
                notation = str(
                    row["Notations"]
                ).strip()

            events.append(
                {
                    "venue": str(
                        row["venue"]
                    ).strip(),
                    "bands_display": " • ".join(bands),
                    "notation": notation,
                }
            )

        groups.append(
            {
                "date": show_date,
                "day": show_date.strftime(
                    "%a"
                ).upper(),
                "short_date": (
                    f"{show_date.month}/"
                    f"{show_date.day}"
                ),
                "events": events,
            }
        )

    return groups


def prep_releases(df, types):
    if df.empty:
        return []

    allowed = {
        t.lower()
        for t in types
    }

    df = df[
        df["type"]
        .astype(str)
        .str.lower()
        .isin(allowed)
    ]

    df = df.sort_values(
        ["artist", "title"]
    )

    return [
        {
            "artist": str(
                row["artist"]
            ).strip(),
            "title": str(
                row["title"]
            ).strip(),
        }
        for _, row in df.iterrows()
    ]


def estimate_show_lines(groups):
    lines = 0.0

    for group in groups:
        lines += 0.55

        for event in group["events"]:
            chars = len(
                event["bands_display"]
            )

            lines += (
                1.0
                + max(
                    0,
                    math.ceil(chars / 46) - 1,
                )
                * 0.85
            )

            lines += 0.55

    return max(lines, 1)


def choose_show_sizes(groups, cfg):
    density = estimate_show_lines(groups)

    mx = cfg["layout"][
        "show_max_font_px"
    ]

    mn = cfg["layout"][
        "show_min_font_px"
    ]

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

    return (
        max(mn, font),
        max(20, int(font * 0.70)),
    )


def split_show_pages(browser, env, cfg, groups, common):
    """
    Paginate shows using Chromium's actual rendered layout.

    - Keep complete events together when possible.
    - Keep consecutive festival days together when they fit.
    - Split oversized events between individual bands.
    """
    import re

    def festival_key(group):
        if len(group["events"]) != 1:
            return None

        note = group["events"][0].get("notation", "")
        match = re.match(
            r"^(.*?)\s+DAY\s+\d+\b",
            note,
            re.I,
        )

        return (
            match.group(1).strip().casefold()
            if match else None
        )

    page = browser.new_page(
        viewport={
            "width": cfg["canvas"]["width"],
            "height": cfg["canvas"]["height"],
        }
    )

    template = env.get_template("slide.html")

    def fits(groups_on_page):
        html = template.render(
            **cfg,
            **common,
            kind="shows",
            slide_class="shows-1",
            kicker="OKC METAL WEEKLY",
            heading="LIVE NOISE",
            day_groups=groups_on_page,
            items=[],
            watermark="",
            footer="",
            release_columns=1,
            release_font_px=30,
            release_title_font_px=22,
            page_num=1,
            page_total=1,
        )

        page.set_content(html, wait_until="load")
        page.evaluate("() => document.fonts.ready")

        return page.evaluate("""() => {
            const root = document.querySelector('.slide');
            const content = document.querySelector('.shows');
            const nodes = [
                ...document.querySelectorAll(
                    '.day-group, .event, .bands, .event-meta'
                )
            ];

            const rect = root.getBoundingClientRect();
            const bottom = rect.bottom - 55;

            return (
                content.getBoundingClientRect().bottom <= bottom &&
                nodes.every(n => {
                    const r = n.getBoundingClientRect();
                    return (
                        r.bottom <= bottom &&
                        r.right <= rect.right - 45
                    );
                })
            );
        }""")

    def split_event(group, event):
        """Split an oversized lineup at band boundaries."""
        bands = event["bands_display"].split(" • ")
        chunks = []
        current = []

        for band in bands:
            candidate = current + [band]
            trial_event = {
                **event,
                "bands_display": " • ".join(candidate),
            }
            trial_group = {
                **group,
                "events": [trial_event],
            }

            if current and not fits([trial_group]):
                chunks.append(current)
                current = [band]
            else:
                current = candidate

        if current:
            chunks.append(current)

        results = []

        for index, chunk in enumerate(chunks):
            notation = event.get("notation", "")

            if index > 0:
                notation = (
                    f"{notation} CONT."
                    if notation else "CONT."
                )

            piece = {
                **event,
                "bands_display": " • ".join(chunk),
                "notation": notation,
            }

            result = {
                **group,
                "events": [piece],
            }

            if not fits([result]):
                raise ValueError(
                    "Show entry cannot fit on an empty slide: "
                    + piece["bands_display"]
                )

            results.append(result)

        return results

    # Build atomic units: one complete event per unit.
    units = []

    for group in groups:
        for event in group["events"]:
            single = {
                **group,
                "events": [event],
            }

            if fits([single]):
                units.append(single)
            else:
                units.extend(split_event(group, event))

    # Detect adjacent festival days by notation.
    # Example: FLYOVER FEST DAY 1 / FLYOVER FEST DAY 2
    bundles = []
    i = 0

    while i < len(units):
        current = units[i]
        key = festival_key(current)

        if key and i + 1 < len(units):
            following = units[i + 1]

            if (
                festival_key(following) == key
                and fits([current, following])
            ):
                bundles.append([current, following])
                i += 2
                continue

        bundles.append([current])
        i += 1

    pages = []
    current_page = []

    for bundle in bundles:
        if fits(current_page + bundle):
            current_page.extend(bundle)
            continue

        if current_page:
            pages.append(current_page)
            current_page = []

        if fits(bundle):
            current_page.extend(bundle)
        else:
            for unit in bundle:
                if not fits(current_page + [unit]):
                    if current_page:
                        pages.append(current_page)
                    current_page = []

                current_page.append(unit)

    if current_page:
        pages.append(current_page)

    page.close()

    # Recombine adjacent entries sharing a date so the
    # template preserves its existing same-day styling.
    merged_pages = []

    for show_page in pages:
        merged = []

        for group in show_page:
            if (
                merged
                and merged[-1]["date"] == group["date"]
            ):
                merged[-1]["events"].extend(group["events"])
            else:
                merged.append({
                    **group,
                    "events": list(group["events"]),
                })

        merged_pages.append(merged)

    return merged_pages or [[]]



def choose_release_sizes(items, cfg):
    n = len(items)

    mx = cfg["layout"][
        "release_max_font_px"
    ]

    mn = cfg["layout"][
        "release_min_font_px"
    ]

    if n <= 8:
        font, cols = mx, 1

    elif n <= 12:
        font, cols = mx - 3, 2

    elif n <= 18:
        font, cols = mx - 6, 2

    else:
        font, cols = mn, 2

    return (
        max(mn, font),
        max(18, int(font * 0.72)),
        cols,
    )


def split_release_pages(
    items,
    max_per_page=26,
):
    """
    Split releases into balanced pages.

    Examples:
        20 -> [20]
        26 -> [26]
        27 -> [14, 13]
        34 -> [17, 17]
        53 -> [18, 18, 17]
    """

    if not items:
        return [[]]

    page_count = math.ceil(
        len(items) / max_per_page
    )

    base_size = (
        len(items) // page_count
    )

    remainder = (
        len(items) % page_count
    )

    pages = []
    start = 0

    for i in range(page_count):
        size = base_size + (
            1 if i < remainder else 0
        )

        pages.append(
            items[start:start + size]
        )

        start += size

    return pages


def resolve_font_file(filename):
    if not filename:
        return ""

    path = STATIC / "fonts" / filename

    if not path.exists():
        print(
            f"WARNING: Font not found: {path}"
        )
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
        "application/octet-stream",
    )

    encoded = base64.b64encode(
        path.read_bytes()
    ).decode("ascii")

    print(
        f"Loaded font: {filename}"
    )

    return (
        f"data:{mime};base64,{encoded}"
    )


def resolve_background(cfg):
    filename = (
        cfg["images"]
        .get("okc_background", "")
        .strip()
    )

    if not filename:
        return ""

    path = (
        STATIC
        / "images"
        / filename
    ).resolve()

    return (
        path.as_uri()
        if path.exists()
        else ""
    )


def week_label(start, end):
    if start.month == end.month:
        line1 = (
            f"{start.strftime('%b').upper()} "
            f"{start.day}–{end.day}"
        )

    else:
        line1 = (
            f"{start.strftime('%b').upper()} "
            f"{start.day}–"
            f"{end.strftime('%b').upper()} "
            f"{end.day}"
        )

    return line1, str(start.year)


def render_html(
    env,
    cfg,
    **kwargs,
):
    return (
        env
        .get_template("slide.html")
        .render(**cfg, **kwargs)
    )


def png_from_html(
    browser,
    html,
    html_path,
    png_path,
    width,
    height,
):
    html_path.write_text(
        html,
        encoding="utf-8",
    )

    page = browser.new_page(
        viewport={
            "width": width,
            "height": height,
        },
        device_scale_factor=1,
    )

    page.goto(
        html_path.resolve().as_uri(),
        wait_until="load",
    )

    # Wait for any configured fonts
    # before taking the screenshot.
    page.wait_for_function(
        "document.fonts.status === 'loaded'"
    )

    page.screenshot(
        path=str(png_path),
        full_page=False,
    )

    page.close()


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--sheet-id",
        help="Google Sheet ID",
    )

    ap.add_argument(
        "--credentials",
        help="Service-account JSON path",
    )

    ap.add_argument(
        "--week",
        help="Edition start date YYYY-MM-DD",
    )

    args = ap.parse_args()

    cfg = load_config()

    # ---------------------------------
    # Load data
    # ---------------------------------

    if args.sheet_id and args.credentials:
        shows_raw, releases_raw = (
            load_google_sheet(
                args.sheet_id,
                args.credentials,
            )
        )

        source = "Google Sheets"

    else:
        shows_raw, releases_raw = (
            load_local_csv()
        )

        source = "CSV"

    # ---------------------------------
    # Resolve edition dates
    # ---------------------------------

    start, end = resolve_week(
        cfg,
        args.week,
    )

    shows_df = filter_week(
        shows_raw,
        "date",
        start,
        end,
    )

    releases_df = filter_week(
        releases_raw,
        "release_date",
        start,
        end,
    )

    # ---------------------------------
    # Prepare content
    # ---------------------------------

    day_groups = prep_shows(
        shows_df
    )

    albums = prep_releases(
        releases_df,
        ["Album", "EP"],
    )

    singles = prep_releases(
        releases_df,
        ["Single"],
    )

    # ---------------------------------
    # Determine layout
    # ---------------------------------

    show_font, venue_font = (
        choose_show_sizes(
            day_groups,
            cfg,
        )
    )

    (
        album_font,
        album_title_font,
        album_cols,
    ) = choose_release_sizes(
        albums,
        cfg,
    )

    # Singles can create multiple pages.
    # Keep each page readable rather
    # than shrinking a large list.
    single_pages = split_release_pages(
        singles,
        max_per_page=26,
    )

    week_line_1, week_line_2 = (
        week_label(
            start,
            end,
        )
    )

    # ---------------------------------
    # Assets
    # ---------------------------------

    font_files = {
        "display": resolve_font_file(
            cfg["typography"].get(
                "display_file",
                "",
            )
        ),
        "condensed": resolve_font_file(
            cfg["typography"].get(
                "condensed_file",
                "",
            )
        ),
        "body": resolve_font_file(
            cfg["typography"].get(
                "body_file",
                "",
            )
        ),
    }

    background_image = (
        resolve_background(cfg)
    )

    # ---------------------------------
    # Build slides
    # ---------------------------------

    slides = []
    
    # Live shows placeholder.
    # Actual pagination happens after Chromium starts.
    slides.append(
        dict(
            kind="shows",
            slide_class="shows-1",
            watermark="",
            kicker="OKC METAL WEEKLY",
            heading="LIVE NOISE",
            day_groups=day_groups,
            items=[],
            footer=(
                "YOUR WEEKLY GUIDE TO "
                "HEAVY MUSIC IN OKC"
            ),
            release_columns=1,
            release_font_px=30,
            release_title_font_px=22,
        )
    )

    # Albums + EPs
    slides.append(
        dict(
            kind="releases",
            slide_class="releases-2",
            watermark="",
            kicker="NEW NOISE",
            heading="ALBUMS + EPS",
            day_groups=[],
            items=albums,
            footer="FULL LIST • NO FILLER",
            release_columns=album_cols,
            release_font_px=album_font,
            release_title_font_px=(
                album_title_font
            ),
        )
    )

    # Singles — one or more slides
    for i, single_page in enumerate(
        single_pages
    ):
        (
            single_font,
            single_title_font,
            single_cols,
        ) = choose_release_sizes(
            single_page,
            cfg,
        )

        slides.append(
            dict(
                kind="releases",
                slide_class="releases-3",
                watermark="",
                kicker="NEW NOISE",
                heading=(
                    "SINGLES"
                    if i == 0
                    else "SINGLES CONT."
                ),
                day_groups=[],
                items=single_page,
                footer=(
                    "WHAT ARE YOU "
                    "LISTENING TO?"
                ),
                release_columns=(
                    single_cols
                ),
                release_font_px=(
                    single_font
                ),
                release_title_font_px=(
                    single_title_font
                ),
            )
        )

    # Support slide always goes last.
    slides.append(
        dict(
            kind="support",
            slide_class="support-4",
            watermark="",
            kicker="SUPPORT THE SCENE",
            heading="KEEP IT HEAVY",
            day_groups=[],
            items=[],
            footer=(
                "SUPPORT LOCAL • SHOW UP • "
                "BRING PEOPLE WITH YOU"
            ),
            release_columns=1,
            release_font_px=30,
            release_title_font_px=22,
        )
    )

    # ---------------------------------
    # Dynamic numbering
    # ---------------------------------

    page_total = len(slides)

    for page_num, slide in enumerate(
        slides,
        start=1,
    ):
        slide["page_num"] = page_num

        if slide["kind"] == "releases":
            slide["watermark"] = (
                f"{page_num:02d}"
            )

    # ---------------------------------
    # Output directory
    # ---------------------------------

    edition_dir = (
        OUT
        / (
            f"{start:%Y-%m-%d}"
            f"_to_"
            f"{end:%Y-%m-%d}"
        )
    )

    edition_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    env = Environment(
        loader=FileSystemLoader(
            TEMPLATES
        ),
        autoescape=True,
    )

    # ---------------------------------
    # Console summary
    # ---------------------------------

    print(
        f"Source: {source}"
    )

    print(
        f"Edition: "
        f"{start:%Y-%m-%d} "
        f"through "
        f"{end:%Y-%m-%d}"
    )

    print(
        f"Show rows: {len(shows_df)} | "
        f"Albums/EPs: {len(albums)} | "
        f"Singles: {len(singles)}"
    )

    print(
        f"Slides: {page_total} | "
        f"Singles pages: "
        f"{len(single_pages)} "
        f"("
        f"{', '.join(str(len(page)) for page in single_pages)}"
        f" items)"
    )

    # ---------------------------------
    # Render
    # ---------------------------------

    
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Measure and paginate live shows.
        show_pages = split_show_pages(
            browser,
            env,
            cfg,
            day_groups,
            dict(
                week_line_1=week_line_1,
                week_line_2=week_line_2,
                show_font_px=show_font,
                show_venue_font_px=venue_font,
                font_files=font_files,
                background_image=background_image,
            ),
        )

        # Replace the placeholder with actual show pages.
        show_slide = slides[0]

        slides = [
            dict(
                show_slide,
                day_groups=groups,
                heading=(
                    "LIVE NOISE"
                    if i == 0
                    else "LIVE NOISE CONT."
                ),
            )
            for i, groups in enumerate(show_pages)
        ] + slides[1:]

        # Recalculate slide numbers and release watermarks.
        page_total = len(slides)

        for page_num, slide in enumerate(slides, start=1):
            slide["page_num"] = page_num

            if slide["kind"] == "releases":
                slide["watermark"] = f"{page_num:02d}"

        print(
            f"Show pages: {len(show_pages)} | "
            f"Total slides: {page_total}"
        )

        for slide in slides:

            html = render_html(
                env,
                cfg,
                **slide,
                page_total=page_total,
                week_line_1=week_line_1,
                week_line_2=week_line_2,
                show_font_px=show_font,
                show_venue_font_px=(
                    venue_font
                ),
                font_files=font_files,
                background_image=(
                    background_image
                    if slide["kind"]
                    in {"shows", "support"}
                    else ""
                ),
            )

            stem = (
                f"{slide['page_num']:02d}"
            )

            png_from_html(
                browser,
                html,
                edition_dir
                / f"{stem}.html",
                edition_dir
                / f"{stem}.png",
                cfg["canvas"]["width"],
                cfg["canvas"]["height"],
            )

            print(
                "Wrote "
                f"{edition_dir / f'{stem}.png'}"
            )

        browser.close()

    print(
        f"Done: {edition_dir}"
    )


if __name__ == "__main__":
    main()