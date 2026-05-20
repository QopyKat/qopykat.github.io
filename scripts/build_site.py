#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path

import markdown
from jinja2 import Environment


ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "tokyo-trip-plans"
SITE_DIR = ROOT / "site"
DAY_DIR = SITE_DIR / "day"
ROOT_INDEX = ROOT / "index.html"
PHOTO_DATA_PATH = ROOT / "scripts" / "day_photos.json"

PICO_SOURCE = ROOT / "vendor" / "pico.min.css"
PICO_OUTPUT = SITE_DIR / "vendor" / "pico.min.css"

DAY_TYPE_RANGES = {
    "tokyo-city": range(1, 21),
    "day-trip": range(21, 28),
    "holiday": range(28, 32),
    "fandom": range(32, 36),
    "unusual": range(36, 39),
}

SPECIAL_DAY_TYPES = {
    39: "tokyo-city",
    40: "tokyo-city",
    41: "day-trip",
}

DAY_TYPE_LABELS = {
    "tokyo-city": "Tokyo city day",
    "day-trip": "Regional day trip",
    "holiday": "Holiday / special date",
    "fandom": "Fandom / anime / gaming",
    "unusual": "Unusual / experimental",
}

WEATHER_OPTIONS = {
    "mixed": "Mixed weather",
    "rain-friendly": "Rain-friendly",
    "clear-day": "Best on a clear day",
    "snow-beautiful": "Snow-beautiful",
}

ENERGY_OPTIONS = {
    "light": "Light day",
    "moderate": "Moderate day",
    "packed": "Packed day",
}

RESERVATION_OPTIONS = {
    "none": "No special booking pressure",
    "recommended": "Booking recommended",
    "essential": "Book early / essential",
}

STATUS_LABELS = {
    "book-early": "Book early",
    "weather-sensitive": "Weather-sensitive",
    "cash-useful": "Cash useful",
    "holiday-risk": "Holiday risk",
    "shopping-heavy": "Shopping-heavy",
    "late-night-friendly": "Late-night friendly",
}

BODY_LABELS = {
    "Suggested flow:": "Suggested flow",
    "Opening-time considerations:": "Opening-time considerations",
    "Why this is a fit:": "Why this is a fit",
}

MARKDOWN_EXTENSIONS = ["extra", "sane_lists"]

SCRIPT_ASSET_DIR = ROOT / "scripts" / "assets"
STYLES_CSS_PATH = SCRIPT_ASSET_DIR / "styles.css"
APP_JS_PATH = SCRIPT_ASSET_DIR / "app.js"
BASE_TEMPLATE_PATH = SCRIPT_ASSET_DIR / "base.html"


def read_script_asset(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() + "\n"


BASE_ENV = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)
BASE_TMPL = BASE_ENV.from_string(read_script_asset(BASE_TEMPLATE_PATH))


@dataclass
class DayPlan:
    number: int
    slug: str
    filename: str
    title: str
    short_title: str
    summary: str
    tag: str
    total_cost: str
    transit_time: str
    cost_breakdown: list[str]
    transit_breakdown: list[str]
    map_links: list[tuple[str, str]]
    body_md: str
    day_type: str
    day_type_label: str
    cost_band: str
    weather: str
    weather_label: str
    energy: str
    energy_label: str
    reservation: str
    reservation_label: str
    status_flags: list[str]
    photos: list[dict[str, str]]

    @property
    def output_name(self) -> str:
        return f"{self.slug}.html"

    @property
    def output_path(self) -> Path:
        return DAY_DIR / self.output_name

    @property
    def display_id(self) -> str:
        return f"{self.number:02d}"

    @property
    def tag_slug(self) -> str:
        return self.tag.lower().replace(" ", "-")


def main() -> None:
    day_photos = load_day_photos()
    day_plans = [
        parse_day_plan(path, day_photos)
        for path in sorted(SRC_DIR.glob("[0-9][0-9]-*.md"))
        if path.name != "00-overview.md"
    ]
    overview_md = (SRC_DIR / "00-overview.md").read_text()

    if SITE_DIR.exists():
      shutil.rmtree(SITE_DIR)
    DAY_DIR.mkdir(parents=True, exist_ok=True)
    PICO_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(PICO_SOURCE, PICO_OUTPUT)
    (SITE_DIR / "styles.css").write_text(read_script_asset(STYLES_CSS_PATH), encoding="utf-8")
    (SITE_DIR / "app.js").write_text(read_script_asset(APP_JS_PATH), encoding="utf-8")

    build_overview_page(overview_md, day_plans)
    build_day_pages(day_plans)


def load_day_photos() -> dict[str, list[dict[str, str]]]:
    if not PHOTO_DATA_PATH.exists():
        return {}
    data = json.loads(PHOTO_DATA_PATH.read_text())
    return {slug: [dict(item) for item in items] for slug, items in data.items()}


def parse_day_plan(path: Path, day_photos: dict[str, list[dict[str, str]]]) -> DayPlan:
    lines = path.read_text().splitlines()

    title = lines[0].removeprefix("#").strip()
    short_title = re.sub(r"^\d+\.\s*", "", title).strip()
    summary = extract_value(lines, "Short summary:")
    tag = strip_inline_code(extract_value(lines, "Tag:"))
    total_cost = extract_value(lines, "- Estimated total cost per person:")
    transit_time = extract_value(lines, "- Estimated transit time from central Tokyo base:")
    cost_breakdown = extract_nested_list(lines, "- Cost breakdown:")
    transit_breakdown = extract_nested_list(lines, "- Transit breakdown:")
    map_links = extract_markdown_links(extract_nested_list(lines, "- Map links:"))
    body_md = normalize_body(extract_body_markdown(lines))
    day_number = int(path.name.split("-", 1)[0])

    return DayPlan(
        number=day_number,
        slug=path.stem,
        filename=path.name,
        title=title,
        short_title=short_title,
        summary=summary,
        tag=tag,
        total_cost=total_cost,
        transit_time=transit_time,
        cost_breakdown=cost_breakdown,
        transit_breakdown=transit_breakdown,
        map_links=map_links,
        body_md=body_md,
        day_type=infer_day_type(day_number),
        day_type_label=DAY_TYPE_LABELS[infer_day_type(day_number)],
        cost_band=infer_cost_band(total_cost),
        weather=infer_weather(day_number),
        weather_label=WEATHER_OPTIONS[infer_weather(day_number)],
        energy=infer_energy(day_number),
        energy_label=ENERGY_OPTIONS[infer_energy(day_number)],
        reservation=infer_reservation(day_number),
        reservation_label=RESERVATION_OPTIONS[infer_reservation(day_number)],
        status_flags=infer_status_flags(day_number),
        photos=day_photos.get(path.stem, []),
    )


def extract_value(lines: list[str], prefix: str) -> str:
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    raise ValueError(f"Could not find line starting with {prefix!r}")


def extract_nested_list(lines: list[str], marker: str) -> list[str]:
    for index, line in enumerate(lines):
        if line.startswith(marker):
            items: list[str] = []
            for inner in lines[index + 1 :]:
                if inner.startswith("  - "):
                    items.append(inner[4:].strip())
                elif inner.strip() == "":
                    if items:
                        break
                else:
                    if items:
                        break
            return items
    return []


def extract_markdown_links(items: list[str]) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for item in items:
        match = re.match(r"\[(.+?)\]\((.+?)\)", item)
        if match:
            links.append((match.group(1), match.group(2)))
        else:
            links.append((item, "#"))
    return links


def strip_inline_code(value: str) -> str:
    return value.replace("`", "").strip()


def extract_body_markdown(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        if line == "Suggested flow:":
            return "\n".join(lines[index:])
    return "\n".join(lines)


def normalize_body(body_md: str) -> str:
    normalized: list[str] = []
    for line in body_md.splitlines():
        normalized.append(f"## {BODY_LABELS[line]}" if line in BODY_LABELS else line)
    return "\n".join(normalized).strip() + "\n"


def infer_day_type(number: int) -> str:
    if number in SPECIAL_DAY_TYPES:
        return SPECIAL_DAY_TYPES[number]
    for slug, valid_range in DAY_TYPE_RANGES.items():
        if number in valid_range:
            return slug
    raise ValueError(f"Unhandled day number {number}")


def infer_cost_band(total_cost: str) -> str:
    amounts = [int(value.replace(",", "")) for value in re.findall(r"JPY\s+([\d,]+)", total_cost)]
    maximum = max(amounts) if amounts else 0
    if maximum <= 12000:
        return "lowest-cost"
    if maximum <= 14000:
        return "lower-mid"
    if maximum <= 18000:
        return "mid-range"
    return "higher-cost"


def infer_weather(number: int) -> str:
    if number in {11, 14, 16, 17, 18, 32, 33, 34, 35, 36, 37}:
        return "rain-friendly"
    if number in {21, 22, 26, 27}:
        return "snow-beautiful"
    if number in {7, 8, 9, 19, 23, 24, 25, 28, 29, 38, 41}:
        return "clear-day"
    return "mixed"


def infer_energy(number: int) -> str:
    if number in {1, 2, 3, 8, 10, 20, 29, 31, 36, 37}:
        return "light"
    if number in {11, 13, 16, 21, 22, 23, 26, 27, 28, 30, 38}:
        return "packed"
    return "moderate"


def infer_reservation(number: int) -> str:
    if number in {16, 18, 28, 29}:
        return "essential"
    if number in {11, 30, 32, 38}:
        return "recommended"
    return "none"


def infer_status_flags(number: int) -> list[str]:
    flags: list[str] = []
    if number in {16, 18, 28, 29, 30, 32, 38}:
        flags.append("book-early")
    if number in {21, 22, 23, 24, 26, 27, 28, 38}:
        flags.append("weather-sensitive")
    if number in {20, 21, 22, 23, 25, 26, 27, 31, 41}:
        flags.append("cash-useful")
    if number in {28, 29, 30, 31}:
        flags.append("holiday-risk")
    if number in {5, 13, 14, 15, 32, 33, 34, 35}:
        flags.append("shopping-heavy")
    if number in {3, 5, 6, 7, 11, 15, 28, 30}:
        flags.append("late-night-friendly")
    return flags


def render_markdown(text: str, current_page: str) -> str:
    rewritten = rewrite_markdown_file_links(text, current_page)
    html = markdown.markdown(rewritten, extensions=MARKDOWN_EXTENSIONS)
    html = rewrite_html_file_links(html, current_page)
    return wrap_currency_mentions(html)


def rewrite_markdown_file_links(text: str, current_page: str) -> str:
    pattern = re.compile(r"\((/home/[^)]+/tokyo-trip-plans/([^)/]+\.md))\)")

    def replace(match: re.Match[str]) -> str:
        filename = match.group(2)
        return f"({resolve_md_target(filename, current_page)})"

    return pattern.sub(replace, text)


def rewrite_html_file_links(html: str, current_page: str) -> str:
    pattern = re.compile(r'href="(/home/[^"]+/tokyo-trip-plans/([^"/]+\.md))"')

    def replace(match: re.Match[str]) -> str:
        filename = match.group(2)
        return f'href="{resolve_md_target(filename, current_page)}"'

    return pattern.sub(replace, html)


def resolve_md_target(filename: str, current_page: str) -> str:
    if filename == "00-overview.md":
        return "../../index.html" if current_page == "day" else "index.html"
    stem = filename[:-3]
    return f"site/day/{stem}.html" if current_page == "overview" else f"{stem}.html"


def wrap_currency_mentions(html: str) -> str:
    pattern = re.compile(r"JPY\s+([\d,]+)(\+)?(?:\s+to\s+([\d,]+)(\+)?)?")

    def replace(match: re.Match[str]) -> str:
        min_amount = int(match.group(1).replace(",", ""))
        min_plus = "true" if match.group(2) else "false"
        max_amount = match.group(3)
        max_plus = "true" if match.group(4) else "false"
        attrs = [
            'data-currency-range="true"',
            f'data-jpy-min="{min_amount}"',
            f'data-jpy-min-plus="{min_plus}"',
        ]
        if max_amount:
            attrs.append(f'data-jpy-max="{int(max_amount.replace(",", ""))}"')
            attrs.append(f'data-jpy-max-plus="{max_plus}"')
        return f'<span class="currency-range" {" ".join(attrs)}>{escape(match.group(0))}</span>'

    return pattern.sub(replace, html)


def badge_html(text: str, css_class: str) -> str:
    return f'<span class="badge {css_class}">{escape(text)}</span>'


def build_overview_page(overview_md: str, day_plans: list[DayPlan]) -> None:
    overview_html = render_markdown(overview_md, "overview")
    browser_html = build_browser(day_plans)
    overview_html = overview_html.replace("<h2>Day-plan index</h2>", "<h2>Day-plan index</h2>" + browser_html, 1)

    content = f"""
    <div class="article-shell">
      <section class="site-hero">
        <span class="hero-kicker">Tokyo Trip Planner</span>
        <h1>Tokyo Trip Plans</h1>
        <p class="site-subtitle">A local static guide generated from your markdown planning files. Browse by mood, cost band, trip type, and weather fit, then open individual day pages for the full details.</p>
        <div class="overview-actions">
          <a href="#day-plan-browser" role="button">Browse day plans</a>
        </div>
      </section>
      <article class="overview-prose">
        {overview_html}
      </article>
    </div>
    """
    page = render_page("Tokyo Trip Plans", content, "site/vendor/pico.min.css", "site/styles.css", "site/app.js", "index.html")
    ROOT_INDEX.write_text(page)


def build_browser(day_plans: list[DayPlan]) -> str:
    cards: list[str] = []
    for day in day_plans:
        search_text = " ".join(
            [
                day.short_title,
                day.summary,
                day.tag,
                day.day_type_label,
                day.weather_label,
                day.energy_label,
                day.reservation_label,
                " ".join(STATUS_LABELS[flag] for flag in day.status_flags),
                " ".join(day.cost_breakdown),
                " ".join(day.transit_breakdown),
            ]
        ).lower()

        map_link = day.map_links[0][1] if day.map_links else "#"
        map_label = day.map_links[0][0] if day.map_links else "Map"
        status_badges = "".join(badge_html(STATUS_LABELS[flag], "badge-status") for flag in day.status_flags)

        cards.append(
            f"""
            <article
              class="plan-card"
              data-plan-card
              data-search="{escape(search_text)}"
              data-tag="{escape(day.tag.lower())}"
              data-type="{escape(day.day_type)}"
              data-cost="{escape(day.cost_band)}"
              data-weather="{escape(day.weather)}"
              data-energy="{escape(day.energy)}"
              data-reservation="{escape(day.reservation)}"
            >
              <div class="card-badge-stack">
                <div class="badge-row">
                  {badge_html(day.tag, f"badge-{day.tag_slug}")}
                  {badge_html(day.day_type_label, "badge-type")}
                </div>
                <div class="badge-row">
                  {badge_html(day.weather_label, f"badge-weather-{day.weather}")}
                  {badge_html(day.energy_label, f"badge-energy-{day.energy}")}
                  {badge_html(day.reservation_label, f"badge-reservation-{day.reservation}")}
                </div>
                {f'<div class="status-list">{status_badges}</div>' if status_badges else ""}
              </div>
              <div>
                <h4><a href="site/day/{escape(day.output_name)}">{escape(day.display_id)}. {escape(day.short_title)}</a></h4>
                <p class="card-summary">{escape(day.summary)}</p>
              </div>
                <div class="meta-grid">
                <div class="meta-item">
                  <strong>Total cost</strong>
                  <span>{render_markdown_inline(day.total_cost, "overview")}</span>
                </div>
                <div class="meta-item">
                  <strong>Transit time</strong>
                  <span>{render_markdown_inline(day.transit_time, "overview")}</span>
                </div>
              </div>
              <div class="card-footer overview-actions">
                <a href="site/day/{escape(day.output_name)}" role="button">Open day plan</a>
                <a href="{escape(map_link)}" class="secondary">Map: {escape(map_label)}</a>
              </div>
            </article>
            """
        )

    return f"""
    <section class="browser-shell" id="day-plan-browser" data-plan-browser>
      <h3>Interactive browser</h3>
      <p>Search the plans and narrow them by fit, trip type, and rough cost band.</p>
      <div class="filter-grid">
        <div>
          <label for="plan-search">Search</label>
          <input id="plan-search" type="search" placeholder="Kamakura, anime, Christmas..." data-filter="search">
        </div>
        <div>
          <label for="tag-filter">Fit tag</label>
          <select id="tag-filter" data-filter="tag">
            <option value="">All tags</option>
            <option value="strong fit">Strong fit</option>
            <option value="experimental">Experimental</option>
            <option value="weather-dependent">Weather-dependent</option>
          </select>
        </div>
        <div>
          <label for="type-filter">Trip type</label>
          <select id="type-filter" data-filter="type">
            <option value="">All trip types</option>
            <option value="tokyo-city">Tokyo city day</option>
            <option value="day-trip">Regional day trip</option>
            <option value="holiday">Holiday / special date</option>
            <option value="fandom">Fandom / anime / gaming</option>
            <option value="unusual">Unusual / experimental</option>
          </select>
        </div>
        <div>
          <label for="cost-filter">Rough cost band</label>
          <select id="cost-filter" data-filter="cost">
            <option value="">All cost bands</option>
            <option value="lowest-cost">Lowest-cost</option>
            <option value="lower-mid">Lower-mid</option>
            <option value="mid-range">Mid-range</option>
            <option value="higher-cost">Higher-cost</option>
          </select>
        </div>
        <div>
          <label for="weather-filter">Weather fit</label>
          <select id="weather-filter" data-filter="weather">
            <option value="">All weather fits</option>
            <option value="mixed">Mixed weather</option>
            <option value="rain-friendly">Rain-friendly</option>
            <option value="clear-day">Best on a clear day</option>
            <option value="snow-beautiful">Snow-beautiful</option>
          </select>
        </div>
        <div>
          <label for="energy-filter">Energy level</label>
          <select id="energy-filter" data-filter="energy">
            <option value="">All energy levels</option>
            <option value="light">Light day</option>
            <option value="moderate">Moderate day</option>
            <option value="packed">Packed day</option>
          </select>
        </div>
        <div>
          <label for="reservation-filter">Reservation pressure</label>
          <select id="reservation-filter" data-filter="reservation">
            <option value="">All reservation levels</option>
            <option value="none">No special booking pressure</option>
            <option value="recommended">Booking recommended</option>
            <option value="essential">Book early / essential</option>
          </select>
        </div>
      </div>
      <div class="filter-actions">
        <span class="filter-count" data-result-count></span>
        <button type="button" class="secondary" data-reset-filters>Reset filters</button>
      </div>
      <div class="plan-grid">
        {"".join(cards)}
      </div>
    </section>
    """


def build_day_pages(day_plans: list[DayPlan]) -> None:
    for index, day in enumerate(day_plans):
        prev_day = day_plans[index - 1] if index > 0 else None
        next_day = day_plans[index + 1] if index + 1 < len(day_plans) else None
        status_badges = "".join(badge_html(STATUS_LABELS[flag], "badge-status") for flag in day.status_flags)
        map_embed_html = build_map_embed(day)
        compact_bar_meta = "".join(
            [
                badge_html(day.tag, f"badge-{day.tag_slug}"),
                badge_html(day.day_type_label, "badge-type"),
                badge_html(day.weather_label, f"badge-weather-{day.weather}"),
                badge_html(day.energy_label, f"badge-energy-{day.energy}"),
                badge_html(day.reservation_label, f"badge-reservation-{day.reservation}"),
                status_badges,
            ]
        )

        photo_gallery_html = render_photo_gallery(day.photos)

        content = f"""
        <div class="page-shell" data-day-page>
          <div class="compact-day-bar" data-compact-day-bar aria-hidden="true">
            <div class="compact-day-bar__inner">
              <div class="compact-day-bar__title-group">
                <span class="compact-day-bar__kicker">{escape(day.display_id)} / {escape(day.day_type_label)}</span>
                <span class="compact-day-bar__title">{escape(day.short_title)}</span>
              </div>
              <div class="compact-day-bar__meta">
                {compact_bar_meta}
              </div>
            </div>
          </div>
          <section class="page-hero" data-page-hero>
            <span class="hero-kicker">{escape(day.display_id)} / {escape(day.day_type_label)}</span>
            <h1>{escape(day.short_title)}</h1>
            <p class="page-subtitle">{escape(day.summary)}</p>
            <div class="card-badge-stack">
              <div class="badge-row">
                {badge_html(day.tag, f"badge-{day.tag_slug}")}
                {badge_html(day.day_type_label, "badge-type")}
              </div>
              <div class="badge-row">
                {badge_html(day.weather_label, f"badge-weather-{day.weather}")}
                {badge_html(day.energy_label, f"badge-energy-{day.energy}")}
                {badge_html(day.reservation_label, f"badge-reservation-{day.reservation}")}
              </div>
              {f'<div class="status-list">{status_badges}</div>' if status_badges else ""}
            </div>
            {build_day_nav(prev_day, next_day)}
          </section>

          <div class="page-layout">
            <article class="page-content">
              {photo_gallery_html}
              {render_markdown(day.body_md, "day")}
              {map_embed_html}
              {build_day_nav(prev_day, next_day)}
            </article>

            <aside class="sticky-panel">
              <section class="page-panel">
                <h2>Day snapshot</h2>
                <div class="detail-grid">
                  <div class="detail-item">
                    <strong>Total cost</strong>
                    <span>{render_markdown_inline(day.total_cost, "day")}</span>
                  </div>
                  <div class="detail-item">
                    <strong>Transit time</strong>
                    <span>{render_markdown_inline(day.transit_time, "day")}</span>
                  </div>
                  <div class="detail-item">
                    <strong>Weather fit</strong>
                    <span>{escape(day.weather_label)}</span>
                  </div>
                  <div class="detail-item">
                    <strong>Energy level</strong>
                    <span>{escape(day.energy_label)}</span>
                  </div>
                  <div class="detail-item">
                    <strong>Reservations</strong>
                    <span>{escape(day.reservation_label)}</span>
                  </div>
                </div>
                <h3>Status badges</h3>
                <div class="status-list">
                  {status_badges}
                </div>
                <h3>Cost breakdown</h3>
                {render_detail_list(day.cost_breakdown)}
                <h3>Transit breakdown</h3>
                {render_detail_list(day.transit_breakdown)}
                <h3>Map links</h3>
                <ul class="map-list">
                  {"".join(f'<li><a href=\"{escape(url)}\">{escape(label)}</a></li>' for label, url in day.map_links)}
                </ul>
                <p class="muted-note">All estimates are per person and assume a flexible Tokyo base rather than a fixed hotel district.</p>
              </section>
            </aside>
          </div>
        </div>
        """

        page = render_page(
            day.title,
            content,
            "../vendor/pico.min.css",
            "../styles.css",
            "../app.js",
            "../../index.html",
        )
        day.output_path.write_text(page)


def render_detail_list(items: list[str]) -> str:
    html_items = []
    for item in items:
        html_items.append(f"<li>{render_markdown_inline(item, 'day')}</li>")
    return f'<ul class="detail-list">{"".join(html_items)}</ul>'


def render_photo_gallery(photos: list[dict[str, str]]) -> str:
    if not photos:
        return ""

    figures: list[str] = []
    for photo in photos:
        src = escape(photo["src"])
        href = escape(photo["href"])
        caption = escape(photo["caption"])
        figures.append(
            f"""
            <figure class="photo-card">
              <a href="{href}" class="photo-card__link">
                <img src="{src}" alt="{caption}" loading="lazy" referrerpolicy="no-referrer">
                <figcaption>{caption}</figcaption>
              </a>
            </figure>
            """
        )

    return f"""
    <section class="photo-gallery" aria-labelledby="photo-gallery-title">
      <div class="photo-gallery__header">
        <h2 id="photo-gallery-title">Photo highlights</h2>
      </div>
      <div class="photo-gallery__grid">
        {"".join(figures)}
      </div>
    </section>
    """


def render_markdown_inline(text: str, current_page: str) -> str:
    html = render_markdown(text, current_page)
    if html.startswith("<p>") and html.endswith("</p>"):
        return html[3:-4]
    return html


def build_day_nav(prev_day: DayPlan | None, next_day: DayPlan | None) -> str:
    parts = ['<nav class="day-nav">', '<a href="../../index.html" class="secondary">Back to overview</a>']
    if prev_day:
        parts.append(f'<a href="{escape(prev_day.output_name)}">Previous: {escape(prev_day.display_id)}</a>')
    if next_day:
        parts.append(f'<a href="{escape(next_day.output_name)}">Next: {escape(next_day.display_id)}</a>')
    parts.append("</nav>")
    return "".join(parts)


def render_page(
    title: str,
    content: str,
    pico_href: str,
    styles_href: str,
    script_href: str | None,
    home_href: str,
    toolbar_extra: str = "",
) -> str:
    return BASE_TMPL.render(
        title=title,
        content=content,
        pico_css_url=pico_href,
        styles_href=styles_href,
        script_href=script_href,
        home_href=home_href,
        toolbar_extra=toolbar_extra,
    )


def build_map_embed(day: DayPlan) -> str:
    embed_url = derive_embed_url(day)
    if not embed_url:
        return ""
    return f"""
    <div class="map-embed-wrap">
      <h3>Embedded map</h3>
      <div class="map-embed-box" data-map-embed-box>
        <div class="map-embed-status" data-map-loading>
          <div class="map-loading-indicator" aria-hidden="true"></div>
          <p>Loading map...</p>
        </div>
        <div class="map-embed-status" data-map-error hidden>
          <p class="map-embed-error">Failed to load embedded map.</p>
          <p>The plain map links are still available on the right.</p>
        </div>
        <iframe
          src="{escape(embed_url)}"
          loading="lazy"
          referrerpolicy="no-referrer-when-downgrade"
          allowfullscreen
          title="{escape(day.short_title)} map"
        ></iframe>
      </div>
      <p class="muted-note">The plain map links on the right always stay available. The embedded map loads from the web.</p>
    </div>
    """


def derive_embed_url(day: DayPlan) -> str | None:
    if not day.map_links:
        return None

    label, url = day.map_links[0]
    match = re.search(r"[?&]q=([^&]+)", url)
    query = match.group(1) if match else label.replace(" ", "+")
    query = query.strip()
    if not query:
        return None
    return f"https://www.google.com/maps?q={query}&output=embed"


if __name__ == "__main__":
    main()
