// Renders the Strava cycling and running widgets.
//
// Both sports share one set of markup (components/cycling.html and
// components/running.html) and differ only in the middle summary stat: cycling
// shows average speed, running shows average pace. Each widget root carries a
// data-strava-sport attribute naming which of the two it is.
//
// Each data file holds one or more *groups*. Cycling has two — rides and
// commutes, which Strava distinguishes with a boolean `commute` flag on every
// activity — and running has one. The tab bar is hidden when there is only one
// group, which is why running looks unchanged.
//
// The summary stats are sport-level and sit above the tabs, so they stay put
// while the tabs filter the activity list below. That is a constraint of the
// source, not a preference: Strava's year panel reports one total for all rides
// with no commute breakdown, so per-tab year totals cannot be obtained without
// aggregating every activity of the year.
//
// The JSON files hold raw Strava values — metres, seconds, local ISO timestamps —
// and every displayed number is derived here. That keeps a single source of
// truth for each fact, so distance and speed can never disagree.

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const METRES_PER_KILOMETRE = 1000;

const ACTIVE_TAB_CLASS = "strava-tab-active";

// Per-sport rendering rules. `secondary` describes the middle summary stat and
// the matching per-activity metric. Count labels come from the group, not here,
// because cycling's two groups need different words ("Rides" vs "Commutes").
const SPORTS = {
  cycling: {
    dataPath: "/data/strava/cycling.json",
    secondary: {
      label: "Avg Speed",
      unit: "km/h",
      format: (distanceMetres, movingTimeSeconds) =>
        formatSpeedKmh(distanceMetres, movingTimeSeconds),
    },
  },
  running: {
    dataPath: "/data/strava/running.json",
    secondary: {
      label: "Avg Pace",
      unit: "/km",
      format: (distanceMetres, movingTimeSeconds) =>
        formatPacePerKm(distanceMetres, movingTimeSeconds),
    },
  },
};

// --- Formatting -------------------------------------------------------------

// Headline summary figure: thousands separated, and trims a pointless ".0" so
// 3240000 m reads as "3,240" while 31800 m still reads as "31.8".
const formatSummaryDistanceKm = (distanceMetres) => {
  const kilometres = Number((distanceMetres / METRES_PER_KILOMETRE).toFixed(1));
  return kilometres.toLocaleString("en-US");
};

// Per-activity figure: always one decimal, so the distance column stays aligned
// down the list ("5.0 km" rather than "5 km" beside "12.1 km").
const formatActivityDistanceKm = (distanceMetres) =>
  (distanceMetres / METRES_PER_KILOMETRE).toFixed(1);

const formatSpeedKmh = (distanceMetres, movingTimeSeconds) => {
  if (!movingTimeSeconds) return "–";
  const kilometresPerHour =
    (distanceMetres / METRES_PER_KILOMETRE) / (movingTimeSeconds / SECONDS_PER_HOUR);
  return kilometresPerHour.toFixed(1);
};

const formatPacePerKm = (distanceMetres, movingTimeSeconds) => {
  if (!distanceMetres) return "–";
  const secondsPerKm = movingTimeSeconds / (distanceMetres / METRES_PER_KILOMETRE);
  const minutes = Math.floor(secondsPerKm / SECONDS_PER_MINUTE);
  const seconds = Math.round(secondsPerKm % SECONDS_PER_MINUTE);

  // Rounding 59.6s up must roll over into the next minute, not print "5:60".
  if (seconds === SECONDS_PER_MINUTE) return `${minutes + 1}:00`;
  return `${minutes}:${padTwoDigits(seconds)}`;
};

// "1:11:23" when it ran over an hour, "42:38" when it did not.
const formatDuration = (totalSeconds) => {
  const hours = Math.floor(totalSeconds / SECONDS_PER_HOUR);
  const minutes = Math.floor((totalSeconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
  const seconds = Math.round(totalSeconds % SECONDS_PER_MINUTE);

  if (hours > 0) return `${hours}:${padTwoDigits(minutes)}:${padTwoDigits(seconds)}`;
  return `${minutes}:${padTwoDigits(seconds)}`;
};

// Timestamps are stored without a timezone suffix so they parse as local time,
// which keeps a late-evening activity from drifting onto the next day.
const formatShortDate = (localIsoTimestamp) => {
  const date = new Date(localIsoTimestamp);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.toLocaleString("en-US", { month: "short" })} ${date.getDate()}`;
};

const padTwoDigits = (value) => String(value).padStart(2, "0");

// --- Rendering --------------------------------------------------------------

const renderSummary = (widgetEl, sport, stravaData) => {
  const { summary } = stravaData;

  setText(widgetEl, "[data-strava-period]", stravaData.period);
  setText(widgetEl, "[data-strava-distance]", formatSummaryDistanceKm(summary.distanceMetres));
  // The count is absent when Strava's totals panel did not show one. Render a
  // dash rather than "null".
  setText(widgetEl, "[data-strava-count]", summary.activityCount ?? "–");
  setText(widgetEl, "[data-strava-count-label]", stravaData.countLabel || "");

  setText(
    widgetEl,
    "[data-strava-secondary-value]",
    sport.secondary.format(summary.distanceMetres, summary.movingTimeSeconds),
  );
  setText(widgetEl, "[data-strava-secondary-unit]", sport.secondary.unit);
  setText(widgetEl, "[data-strava-secondary-label]", sport.secondary.label);
};

// The lifetime totals strip. Optional in the payload, so the whole block stays
// hidden rather than showing an empty row when a scrape could not read it.
const renderAllTime = (widgetEl, stravaData) => {
  const stripEl = widgetEl.querySelector("[data-strava-alltime]");
  if (!stripEl) return;

  const allTime = stravaData.allTime;
  if (!allTime || !allTime.distanceMetres) {
    stripEl.hidden = true;
    return;
  }

  const parts = [`${formatSummaryDistanceKm(allTime.distanceMetres)} km`];
  if (allTime.activityCount) {
    const label = (stravaData.countLabel || "").toLowerCase();
    parts.push(`${allTime.activityCount.toLocaleString("en-US")} ${label}`.trim());
  }

  setText(widgetEl, "[data-strava-alltime-summary]", parts.join(" · "));
  stripEl.hidden = false;
};

const renderActivities = (widgetEl, sport, activities) => {
  const templateEl = widgetEl.querySelector("[data-strava-activity-template]");
  const containerEl = templateEl.parentNode;

  clearRenderedRows(containerEl);

  activities.forEach((activity, index) => {
    const clone = document.importNode(templateEl.content, true);

    setText(clone, ".strava-activity-title", activity.name);
    setText(clone, ".strava-activity-date", formatShortDate(activity.startDateLocal));
    setText(
      clone,
      "[data-strava-activity-distance]",
      `${formatActivityDistanceKm(activity.distanceMetres)} km`,
    );
    setText(
      clone,
      "[data-strava-activity-secondary]",
      sport.secondary.format(activity.distanceMetres, activity.movingTimeSeconds),
    );
    setText(clone, "[data-strava-activity-secondary-label]", sport.secondary.unit);
    setText(clone, "[data-strava-activity-time]", formatDuration(activity.movingTimeSeconds));

    // The list's bottom border is the widget's own, so the last row drops its divider.
    if (index === activities.length - 1) {
      const rowEl = clone.querySelector(".strava-activity-row-bordered");
      rowEl.className = "strava-activity-row";
    }

    containerEl.appendChild(clone);
  });
};

// Switching tabs re-renders the list, so previously appended rows must go. The
// <template> itself is the source of those rows and has to survive.
const clearRenderedRows = (containerEl) => {
  [...containerEl.children]
    .filter((child) => child.tagName !== "TEMPLATE")
    .forEach((child) => child.remove());
};

const renderTabs = (widgetEl, groups, onSelect) => {
  const tabsEl = widgetEl.querySelector("[data-strava-tabs]");

  // A single group needs no switch — this is what keeps running looking untouched.
  if (groups.length < 2) return;

  const templateEl = tabsEl.querySelector("[data-strava-tab-template]");

  groups.forEach((group, index) => {
    const clone = document.importNode(templateEl.content, true);
    const tabEl = clone.querySelector(".strava-tab");

    tabEl.innerText = group.label;
    tabEl.dataset.stravaTabIndex = index;
    tabEl.addEventListener("click", () => onSelect(index));

    tabsEl.appendChild(clone);
  });

  tabsEl.hidden = false;
};

const highlightActiveTab = (widgetEl, activeIndex) => {
  widgetEl.querySelectorAll(".strava-tab").forEach((tabEl) => {
    const isActive = Number(tabEl.dataset.stravaTabIndex) === activeIndex;
    tabEl.classList.toggle(ACTIVE_TAB_CLASS, isActive);
    tabEl.setAttribute("aria-selected", String(isActive));
  });
};

const initStravaWidget = async (widgetEl) => {
  const sportName = widgetEl.dataset.stravaSport;
  const sport = SPORTS[sportName];

  if (!sport) {
    console.error(`Unknown Strava sport: ${sportName}`);
    return;
  }

  const stravaData = await fetchJsonData(sport.dataPath);
  const groups = stravaData && stravaData.groups;

  // fetchJsonData returns [] on failure, so bail rather than throw below.
  if (!groups || groups.length === 0 || !stravaData.summary) {
    console.error(`No Strava data for ${sportName}`);
    return;
  }

  // Summary and lifetime totals are sport-level, so both are rendered once
  // rather than per tab.
  renderSummary(widgetEl, sport, stravaData);
  renderAllTime(widgetEl, stravaData);

  const selectGroup = (index) => {
    renderActivities(widgetEl, sport, groups[index].activities || []);
    highlightActiveTab(widgetEl, index);
  };

  renderTabs(widgetEl, groups, selectGroup);
  selectGroup(0);
};

const setText = (rootEl, selector, value) => {
  const targetEl = rootEl.querySelector(selector);
  if (targetEl) targetEl.innerText = value;
};

export const StravaData = {
  init: async () => {
    const widgetEls = document.querySelectorAll("[data-strava-widget]");
    await Promise.all([...widgetEls].map(initStravaWidget));
  },
};
