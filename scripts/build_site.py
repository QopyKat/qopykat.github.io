#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
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

PICO_SOURCE = ROOT / "vendor" / "pico.min.css"
PICO_OUTPUT = SITE_DIR / "vendor" / "pico.min.css"

DAY_TYPE_RANGES = {
    "tokyo-city": range(1, 21),
    "day-trip": range(21, 28),
    "holiday": range(28, 32),
    "fandom": range(32, 36),
    "unusual": range(36, 39),
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

STYLES_CSS = r"""
:root {
  color-scheme: light;
  --pico-font-family: "IBM Plex Sans", "Avenir Next", Avenir, "Segoe UI", sans-serif;
  --pico-primary: #b2412e;
  --pico-primary-background: #b2412e;
  --pico-primary-hover: #923424;
  --pico-primary-hover-background: #923424;
  --pico-primary-focus: rgba(178, 65, 46, 0.2);
}

html[data-theme="light"] {
  color-scheme: light;
  --pico-background-color: #fffaf1;
  --pico-color: #1f1c18;
  --pico-muted-color: #6a6a63;
  --pico-secondary: #4a5f57;
  --pico-card-background-color: rgba(255, 255, 255, 0.9);
  --pico-form-element-background-color: rgba(255, 255, 255, 0.96);
  --pico-form-element-border-color: rgba(90, 72, 55, 0.2);
  --pico-form-element-color: #1f1c18;
  --pico-form-element-placeholder-color: #7d7266;
  --pico-contrast-background: #201c18;
  --pico-contrast-foreground: #fff9f2;
  --page-ink: #1f1c18;
  --page-soft: #f7f1e5;
  --page-soft-2: #fffaf1;
  --surface-1: rgba(255, 252, 246, 0.92);
  --surface-2: rgba(255, 255, 255, 0.9);
  --surface-3: rgba(255, 255, 255, 0.78);
  --surface-4: rgba(247, 241, 229, 0.85);
  --line-soft: rgba(90, 72, 55, 0.14);
  --shadow-soft: rgba(53, 38, 26, 0.07);
  --shadow-soft-2: rgba(53, 38, 26, 0.06);
  --shadow-soft-3: rgba(53, 38, 26, 0.05);
}

html[data-theme="dark"] {
  color-scheme: dark;
  --pico-background-color: #12100e;
  --pico-color: #efe5d7;
  --pico-muted-color: #c1b4a2;
  --pico-secondary: #9bb8ae;
  --pico-card-background-color: rgba(35, 28, 24, 0.92);
  --pico-form-element-background-color: rgba(34, 27, 23, 0.96);
  --pico-form-element-border-color: rgba(205, 183, 156, 0.24);
  --pico-form-element-color: #f3eadf;
  --pico-form-element-placeholder-color: #a99a89;
  --pico-contrast-background: #f4eadc;
  --pico-contrast-foreground: #1c1714;
  --page-ink: #efe5d7;
  --page-soft: #171310;
  --page-soft-2: #12100e;
  --surface-1: rgba(30, 24, 20, 0.92);
  --surface-2: rgba(35, 28, 24, 0.9);
  --surface-3: rgba(28, 23, 20, 0.82);
  --surface-4: rgba(48, 38, 31, 0.82);
  --line-soft: rgba(214, 193, 169, 0.14);
  --shadow-soft: rgba(0, 0, 0, 0.26);
  --shadow-soft-2: rgba(0, 0, 0, 0.22);
  --shadow-soft-3: rgba(0, 0, 0, 0.18);
}

html[data-theme="light"],
html[data-theme="dark"] {
  --badge-strong: #245f4b;
  --badge-experimental: #8a4f17;
  --badge-weather: #305d8e;
  --badge-type: #5d4b73;
  --badge-energy-light: #4f6b46;
  --badge-energy-moderate: #7d5a2a;
  --badge-energy-packed: #8f3f3f;
  --badge-reservation-none: #4f6b46;
  --badge-reservation-recommended: #8a4f17;
  --badge-reservation-essential: #923424;
  --badge-status: #5f5f72;
}

html {
  scroll-behavior: smooth;
}

body {
  color: var(--page-ink);
  background:
    radial-gradient(circle at top left, rgba(178, 65, 46, 0.12), transparent 24rem),
    radial-gradient(circle at top right, rgba(74, 95, 87, 0.12), transparent 28rem),
    linear-gradient(180deg, var(--page-soft), var(--page-soft-2));
}

main.container {
  padding-top: 2rem;
  padding-bottom: 4rem;
}

.site-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: var(--surface-1);
  box-shadow: 0 0.8rem 1.5rem var(--shadow-soft-3);
}

.site-toolbar a {
  text-decoration: none;
  color: inherit;
  font-weight: 700;
}

.toolbar-brand {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.toolbar-brand small {
  color: var(--pico-muted-color);
  font-weight: 500;
}

.theme-switch {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  white-space: nowrap;
}

.theme-switch label {
  margin: 0;
  font-size: 0.9rem;
  color: var(--pico-muted-color);
}

.theme-switch input[type="checkbox"][role="switch"] {
  margin: 0;
}

.toolbar-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.site-hero,
.page-hero {
  border: 1px solid var(--line-soft);
  border-radius: 1.5rem;
  padding: 2rem 1.5rem;
  background: var(--surface-1);
  box-shadow: 0 1rem 2rem var(--shadow-soft);
}

.hero-kicker {
  display: inline-block;
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--pico-secondary);
}

.site-subtitle,
.page-subtitle {
  max-width: 70ch;
  color: var(--pico-muted-color);
  margin-bottom: 0;
}

.compact-day-bar {
  position: fixed;
  top: 0.75rem;
  left: 50%;
  z-index: 60;
  width: min(72rem, calc(100vw - 2rem));
  opacity: 0;
  pointer-events: none;
  transform: translate(-50%, -0.9rem);
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.compact-day-bar.is-visible {
  opacity: 1;
  pointer-events: auto;
  transform: translate(-50%, 0);
}

.compact-day-bar__inner {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.45rem 0.9rem;
  padding: 0.55rem 0.8rem;
  border: 1px solid var(--line-soft);
  border-radius: 1rem;
  background: var(--surface-1);
  box-shadow: 0 1rem 2rem var(--shadow-soft);
  backdrop-filter: blur(10px);
}

.compact-day-bar__title-group {
  min-width: 0;
}

.compact-day-bar__kicker {
  display: block;
  margin-bottom: 0.2rem;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--pico-secondary);
}

.compact-day-bar__title {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.98rem;
  font-weight: 700;
}

.compact-day-bar__meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-content: center;
  gap: 0.32rem;
  max-width: 100%;
}

.compact-day-bar .badge {
  padding: 0.16rem 0.52rem;
  font-size: 0.7rem;
}

.overview-actions,
.day-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
  margin-top: 1.5rem;
}

.day-nav a[role="button"] {
  margin-bottom: 0;
}

.browser-shell {
  margin: 1.5rem 0 2rem;
  padding: 1rem;
  border: 1px solid var(--line-soft);
  border-radius: 1.25rem;
  background: var(--surface-3);
}

.browser-shell h3 {
  margin-bottom: 0.25rem;
}

.browser-shell > p {
  color: var(--pico-muted-color);
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.85rem;
  margin: 1rem 0 1.25rem;
}

.filter-grid label {
  font-size: 0.85rem;
  color: var(--pico-muted-color);
  margin-bottom: 0.35rem;
}

.filter-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.filter-count {
  color: var(--pico-muted-color);
  font-size: 0.95rem;
}

.plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr));
  gap: 1rem;
}

.plan-card {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  height: 100%;
  padding: 1rem;
  border: 1px solid var(--line-soft);
  border-radius: 1.15rem;
  background: var(--surface-2);
  box-shadow: 0 0.6rem 1.4rem var(--shadow-soft-2);
}

.plan-card[hidden] {
  display: none;
}

.plan-card h4,
.plan-card h5 {
  margin: 0;
}

.plan-card p {
  margin: 0;
}

.card-summary {
  color: var(--pico-muted-color);
  font-size: 0.97rem;
}

.card-badge-stack {
  display: grid;
  gap: 0.45rem;
}

.badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.22rem 0.7rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: white;
}

.badge-strong-fit {
  background: var(--badge-strong);
}

.badge-experimental {
  background: var(--badge-experimental);
}

.badge-weather-dependent {
  background: var(--badge-weather);
}

.badge-type {
  background: var(--badge-type);
}

.badge-weather-mixed,
.badge-weather-rain-friendly,
.badge-weather-clear-day,
.badge-weather-snow-beautiful {
  background: var(--badge-weather);
}

.badge-energy-light {
  background: var(--badge-energy-light);
}

.badge-energy-moderate {
  background: var(--badge-energy-moderate);
}

.badge-energy-packed {
  background: var(--badge-energy-packed);
}

.badge-reservation-none {
  background: var(--badge-reservation-none);
}

.badge-reservation-recommended {
  background: var(--badge-reservation-recommended);
}

.badge-reservation-essential {
  background: var(--badge-reservation-essential);
}

.badge-status {
  background: var(--badge-status);
}

.meta-grid,
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.75rem;
}

.meta-item,
.detail-item {
  padding: 0.8rem 0.9rem;
  border-radius: 1rem;
  background: var(--surface-4);
  border: 1px solid rgba(90, 72, 55, 0.08);
}

.meta-item strong,
.detail-item strong {
  display: block;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.2rem;
  color: var(--pico-secondary);
}

.detail-list {
  margin: 0;
  padding-left: 1.1rem;
}

.detail-list li {
  margin: 0.3rem 0;
}

.status-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.article-shell,
.page-shell {
  display: grid;
  gap: 1.5rem;
}

.page-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 21rem);
  gap: 1.5rem;
  align-items: start;
}

.sticky-panel {
  position: sticky;
  top: 1rem;
}

.page-panel,
.page-content,
.overview-prose {
  border: 1px solid var(--line-soft);
  border-radius: 1.25rem;
  background: var(--surface-2);
  box-shadow: 0 0.8rem 1.6rem var(--shadow-soft-3);
}

.page-panel {
  padding: 1rem;
}

.page-content,
.overview-prose {
  padding: 1.25rem 1.3rem;
}

.page-content h2:first-child,
.overview-prose h2:first-child {
  margin-top: 0;
}

.page-panel h2,
.page-panel h3 {
  margin-top: 0;
}

.map-list {
  margin: 0;
  padding-left: 1.2rem;
}

.map-list li {
  margin: 0.35rem 0;
}

.map-embed-wrap {
  display: grid;
  gap: 0.85rem;
}

.map-embed-box {
  position: relative;
  border: 1px solid var(--line-soft);
  border-radius: 1rem;
  overflow: hidden;
  background: var(--surface-4);
  box-shadow: 0 0.6rem 1.2rem var(--shadow-soft-3);
}

.map-embed-box iframe {
  display: block;
  width: 100%;
  min-height: 22rem;
  border: 0;
}

.map-embed-status {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  gap: 0.5rem;
  padding: 1.25rem;
  text-align: center;
  background: var(--surface-4);
  color: var(--pico-muted-color);
}

.map-embed-box.is-loaded .map-embed-status {
  display: none;
}

.map-embed-status[hidden] {
  display: none;
}

.map-loading-indicator {
  width: 1.25rem;
  height: 1.25rem;
  border: 0.18rem solid rgba(127, 87, 58, 0.2);
  border-top-color: var(--pico-primary);
  border-radius: 50%;
  animation: map-spin 0.8s linear infinite;
}

.map-embed-error {
  font-weight: 600;
  color: var(--pico-primary);
}

@keyframes map-spin {
  to {
    transform: rotate(360deg);
  }
}

.card-footer {
  margin-top: auto;
}

.muted-note {
  font-size: 0.9rem;
  color: var(--pico-muted-color);
}

code {
  background: rgba(127, 87, 58, 0.12);
  color: inherit;
  padding: 0.1rem 0.35rem;
  border-radius: 0.35rem;
}

html[data-theme="dark"] code {
  background: rgba(255, 232, 205, 0.12);
}

@media (max-width: 900px) {
  .page-layout {
    grid-template-columns: 1fr;
  }

  .sticky-panel {
    position: static;
  }

  .compact-day-bar {
    width: calc(100vw - 1rem);
    top: 0.5rem;
  }

  .compact-day-bar__inner {
    align-items: flex-start;
    grid-template-columns: 1fr;
  }

  .compact-day-bar__meta {
    justify-content: flex-start;
  }

  .compact-day-bar__title {
    white-space: normal;
  }
}
"""

APP_JS = r"""
(function () {
  const THEME_KEY = "tokyo-trip-theme";
  const JPY_PER_EUR = 184.92;
  const themeSwitches = Array.from(document.querySelectorAll("[data-theme-switch]"));
  const themeLabelNodes = Array.from(document.querySelectorAll("[data-theme-label]"));
  let currentTheme = null;

  function getThemeFromUrl() {
    try {
      const theme = new URLSearchParams(window.location.search).get("theme");
      return theme === "dark" || theme === "light" ? theme : null;
    } catch (error) {
      return null;
    }
  }

  function getSystemTheme() {
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return "dark";
    }
    return "light";
  }

  function getStoredTheme() {
    try {
      return localStorage.getItem(THEME_KEY);
    } catch (error) {
      return null;
    }
  }

  function isSameSiteLink(url) {
    if (url.protocol === "file:" && window.location.protocol === "file:") {
      return true;
    }
    return url.origin === window.location.origin;
  }

  function syncThemeLinks(theme) {
    document.querySelectorAll("a[href]").forEach((link) => {
      const rawHref = link.getAttribute("href");
      if (!rawHref || rawHref.startsWith("#")) {
        return;
      }
      try {
        const url = new URL(rawHref, window.location.href);
        if (!isSameSiteLink(url) || url.protocol === "mailto:" || url.protocol === "tel:") {
          return;
        }
        url.searchParams.set("theme", theme);
        const nextHref = url.protocol === "file:"
          ? `${url.pathname}${url.search}${url.hash}`
          : `${url.pathname}${url.search}${url.hash}`;
        link.setAttribute("href", nextHref);
      } catch (error) {
        // Ignore malformed URLs.
      }
    });
  }

  function syncThemeUrl(theme) {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("theme", theme);
      window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    } catch (error) {
      // Ignore history failures.
    }
  }

  function setTheme(theme, persist) {
    currentTheme = theme;
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;

    themeSwitches.forEach((input) => {
      input.checked = theme === "dark";
    });

    themeLabelNodes.forEach((node) => {
      node.textContent = theme === "dark" ? "Dark mode" : "Light mode";
    });

    if (persist) {
      try {
        localStorage.setItem(THEME_KEY, theme);
      } catch (error) {
        // Ignore storage failures in file:// mode.
      }
    }

    syncThemeUrl(theme);
    syncThemeLinks(theme);
  }

  const initialTheme = getThemeFromUrl() || getStoredTheme() || getSystemTheme() || "dark";
  setTheme(initialTheme, false);

  document.querySelectorAll("[data-map-embed-box]").forEach((box) => {
    const iframe = box.querySelector("iframe");
    const loadingState = box.querySelector("[data-map-loading]");
    const errorState = box.querySelector("[data-map-error]");
    if (!iframe || !loadingState || !errorState) {
      return;
    }

    const failTimer = window.setTimeout(() => {
      loadingState.hidden = true;
      errorState.hidden = false;
    }, 12000);

    iframe.addEventListener("load", () => {
      window.clearTimeout(failTimer);
      box.classList.add("is-loaded");
      loadingState.hidden = true;
      errorState.hidden = true;
    });
  });

  function formatEuro(value) {
    return new Intl.NumberFormat("en-IE", {
      style: "currency",
      currency: "EUR",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }

  function formatJpy(value) {
    return `JPY ${new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 0,
    }).format(value)}`;
  }

  function convertJpyToEur(value) {
    return value / JPY_PER_EUR;
  }

  function renderCurrencyRange(node) {
    const minJpy = Number(node.dataset.jpyMin || "0");
    const maxJpy = node.dataset.jpyMax ? Number(node.dataset.jpyMax) : null;
    const minPlus = node.dataset.jpyMinPlus === "true";
    const maxPlus = node.dataset.jpyMaxPlus === "true";
    const minEur = `${formatEuro(convertJpyToEur(minJpy))}${minPlus ? "+" : ""}`;
    const minJpyText = `${formatJpy(minJpy)}${minPlus ? "+" : ""}`;

    if (maxJpy !== null && !Number.isNaN(maxJpy)) {
      const maxEur = `${formatEuro(convertJpyToEur(maxJpy))}${maxPlus ? "+" : ""}`;
      const maxJpyText = `${formatJpy(maxJpy)}${maxPlus ? "+" : ""}`;
      node.textContent = `${minEur} to ${maxEur} (${minJpyText} to ${maxJpyText})`;
      return;
    }

    node.textContent = `${minEur} (${minJpyText})`;
  }

  document.querySelectorAll("[data-currency-range]").forEach(renderCurrencyRange);

  document.querySelectorAll("[data-day-page]").forEach((page) => {
    const hero = page.querySelector("[data-page-hero]");
    const compactBar = page.querySelector("[data-compact-day-bar]");
    if (!hero || !compactBar) {
      return;
    }

    const setCompactBarVisible = (visible) => {
      compactBar.classList.toggle("is-visible", visible);
      compactBar.setAttribute("aria-hidden", visible ? "false" : "true");
    };

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver((entries) => {
        const entry = entries[0];
        const shouldShow = entry.intersectionRatio < 0.35 && entry.boundingClientRect.top < 0;
        setCompactBarVisible(shouldShow);
      }, {
        threshold: [0, 0.35, 0.7, 1],
      });
      observer.observe(hero);
    } else {
      const onScroll = () => {
        const rect = hero.getBoundingClientRect();
        setCompactBarVisible(rect.bottom < 120);
      };
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }
  });

  themeSwitches.forEach((input) => {
    input.addEventListener("change", function () {
      setTheme(input.checked ? "dark" : "light", true);
    });
  });

  if (window.matchMedia) {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = function () {
      if (!getThemeFromUrl() && !getStoredTheme()) {
        setTheme(media.matches ? "dark" : "light", false);
      }
    };
    if (media.addEventListener) {
      media.addEventListener("change", listener);
    } else if (media.addListener) {
      media.addListener(listener);
    }
  }

  const root = document.querySelector("[data-plan-browser]");
  if (!root) return;

  const searchInput = root.querySelector("[data-filter='search']");
  const tagSelect = root.querySelector("[data-filter='tag']");
  const typeSelect = root.querySelector("[data-filter='type']");
  const costSelect = root.querySelector("[data-filter='cost']");
  const weatherSelect = root.querySelector("[data-filter='weather']");
  const energySelect = root.querySelector("[data-filter='energy']");
  const reservationSelect = root.querySelector("[data-filter='reservation']");
  const resetButton = root.querySelector("[data-reset-filters]");
  const countNode = root.querySelector("[data-result-count]");
  const cards = Array.from(root.querySelectorAll("[data-plan-card]"));

  const normalize = (value) => (value || "").toLowerCase().trim();

  function applyFilters() {
    const search = normalize(searchInput.value);
    const tag = normalize(tagSelect.value);
    const type = normalize(typeSelect.value);
    const cost = normalize(costSelect.value);
    const weather = normalize(weatherSelect.value);
    const energy = normalize(energySelect.value);
    const reservation = normalize(reservationSelect.value);

    let visible = 0;

    cards.forEach((card) => {
      const haystack = normalize(card.dataset.search);
      const cardTag = normalize(card.dataset.tag);
      const cardType = normalize(card.dataset.type);
      const cardCost = normalize(card.dataset.cost);
      const cardWeather = normalize(card.dataset.weather);
      const cardEnergy = normalize(card.dataset.energy);
      const cardReservation = normalize(card.dataset.reservation);

      const matchesSearch = !search || haystack.includes(search);
      const matchesTag = !tag || cardTag === tag;
      const matchesType = !type || cardType === type;
      const matchesCost = !cost || cardCost === cost;
      const matchesWeather = !weather || cardWeather === weather;
      const matchesEnergy = !energy || cardEnergy === energy;
      const matchesReservation = !reservation || cardReservation === reservation;

      const show = matchesSearch && matchesTag && matchesType && matchesCost && matchesWeather && matchesEnergy && matchesReservation;
      card.hidden = !show;
      if (show) visible += 1;
    });

    countNode.textContent = `${visible} day plan${visible === 1 ? "" : "s"} shown`;
  }

  [searchInput, tagSelect, typeSelect, costSelect, weatherSelect, energySelect, reservationSelect].forEach((el) => {
    el.addEventListener("input", applyFilters);
    el.addEventListener("change", applyFilters);
  });

  resetButton.addEventListener("click", function () {
    searchInput.value = "";
    tagSelect.value = "";
    typeSelect.value = "";
    costSelect.value = "";
    weatherSelect.value = "";
    energySelect.value = "";
    reservationSelect.value = "";
    applyFilters();
  });

  applyFilters();
})();
"""

BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }}</title>
    <script>
      (function () {
        var theme = "dark";
        try {
          var urlTheme = new URLSearchParams(window.location.search).get("theme");
          if (urlTheme === "dark" || urlTheme === "light") {
            theme = urlTheme;
          } else {
            theme = localStorage.getItem("tokyo-trip-theme") || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
          }
        } catch (error) {}
        document.documentElement.dataset.theme = theme || "dark";
        document.documentElement.style.colorScheme = document.documentElement.dataset.theme;
      })();
    </script>
    <link rel="stylesheet" href="{{ pico_css_url }}">
    <link rel="stylesheet" href="{{ styles_href }}">
  </head>
  <body>
    <main class="container">
      <header class="site-toolbar">
        <a href="{{ home_href }}" class="toolbar-brand">
          <span>Tokyo Trip Plans</span>
          <small>Local travel site</small>
        </a>
        <div class="toolbar-controls">
          {{ toolbar_extra | safe }}
          <div class="theme-switch">
            <label for="theme-switch">Theme</label>
            <input id="theme-switch" type="checkbox" role="switch" data-theme-switch aria-label="Toggle dark mode">
            <span data-theme-label>Dark mode</span>
          </div>
        </div>
      </header>
      {{ content | safe }}
    </main>
    {% if script_href %}
    <script src="{{ script_href }}"></script>
    {% endif %}
  </body>
 </html>
"""

BASE_ENV = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)
BASE_TMPL = BASE_ENV.from_string(BASE_TEMPLATE)


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
    day_plans = [parse_day_plan(path) for path in sorted(SRC_DIR.glob("[0-9][0-9]-*.md")) if path.name != "00-overview.md"]
    overview_md = (SRC_DIR / "00-overview.md").read_text()

    if SITE_DIR.exists():
      shutil.rmtree(SITE_DIR)
    DAY_DIR.mkdir(parents=True, exist_ok=True)
    PICO_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(PICO_SOURCE, PICO_OUTPUT)
    (SITE_DIR / "styles.css").write_text(STYLES_CSS.strip() + "\n")
    (SITE_DIR / "app.js").write_text(APP_JS.strip() + "\n")

    build_overview_page(overview_md, day_plans)
    build_day_pages(day_plans)


def parse_day_plan(path: Path) -> DayPlan:
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
    if number in {7, 8, 9, 19, 23, 24, 25, 28, 29, 38}:
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
    if number in {20, 21, 22, 23, 25, 26, 27, 31}:
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
