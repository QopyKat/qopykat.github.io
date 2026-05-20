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
