// Renders the Strava cycling and running widgets.
//
// Both sports share one set of markup (components/cycling.html and
// components/running.html). Each widget root carries a data-strava-sport
// attribute naming which of the two it is; that selects the per-sport formatting
// below, where cycling shows per-activity speed and running per-activity pace.
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
//
// Each activity also carries a routeImage: a small photograph of its route on a
// map, captured at scrape time and committed as a static asset. Five rows named
// "Evening Ride" are indistinguishable as text, which is what the pictures are
// there to fix. It is null for anything recorded without GPS.

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const METRES_PER_KILOMETRE = 1000;

const ACTIVE_TAB_CLASS = "strava-tab-active";
const LINKED_ROW_CLASS = "strava-activity-row-linked";

// Per-sport rendering rules.
//
// `summary` and `activity` are separate on purpose. The middle summary stat used
// to be an average speed derived from the year's distance and time, but Strava's
// yearly figure is elapsed time — including every stop — so that average came out
// well below the real riding pace. Total time is the same data reported without
// the misleading division. Per-activity speed and pace stay, because there the
// time behaves like moving time.
//
// Count labels come from the payload, since cycling's groups need different
// words ("Rides" vs "Commutes").
const SPORTS = {
  cycling: {
    dataPath: "/data/strava/cycling.json",
    summary: {
      label: "Time",
      unit: "",
      format: (distanceMetres, movingTimeSeconds) => formatHoursMinutes(movingTimeSeconds),
    },
    activity: {
      label: "km/h",
      format: (distanceMetres, movingTimeSeconds) =>
        formatSpeedKmh(distanceMetres, movingTimeSeconds),
    },
  },
  running: {
    dataPath: "/data/strava/running.json",
    summary: {
      label: "Time",
      unit: "",
      format: (distanceMetres, movingTimeSeconds) => formatHoursMinutes(movingTimeSeconds),
    },
    activity: {
      label: "/km",
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

// Totals rather than a single activity: "136h 11m", or "44m" under an hour.
const formatHoursMinutes = (totalSeconds) => {
  const hours = Math.floor(totalSeconds / SECONDS_PER_HOUR);
  const minutes = Math.round((totalSeconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);

  if (hours === 0) return `${minutes}m`;
  return `${hours.toLocaleString("en-US")}h ${minutes}m`;
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
    sport.summary.format(summary.distanceMetres, summary.movingTimeSeconds),
  );
  setText(widgetEl, "[data-strava-secondary-unit]", sport.summary.unit);
  setText(widgetEl, "[data-strava-secondary-label]", sport.summary.label);
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
      sport.activity.format(activity.distanceMetres, activity.movingTimeSeconds),
    );
    setText(clone, "[data-strava-activity-secondary-label]", sport.activity.label);
    setText(clone, "[data-strava-activity-time]", formatDuration(activity.movingTimeSeconds));
    renderRouteMap(clone, activity);
    renderActivityLink(clone, activity);

    // The list's bottom border is the widget's own, so the last row drops its divider.
    //
    // classList.replace, not an assignment to className: the row may already carry
    // the linked-row class by this point, and overwriting className would silently
    // strip it and leave the last activity without its pointer cursor.
    if (index === activities.length - 1) {
      const rowEl = clone.querySelector(".strava-activity-row-bordered");
      rowEl.classList.replace("strava-activity-row-bordered", "strava-activity-row");
    }

    containerEl.appendChild(clone);
  });
};

// Points a row at its activity on Strava.
//
// The href is only set when the payload has a URL, because an <a> without one is
// not focusable and not announced as a link — which is the correct outcome for a
// row that has nowhere to go, and better than a link that looks live and does
// nothing. The class marking a row as linked drives the affordance in CSS, so an
// inert row does not get a pointer cursor.
//
// Not run through `prefix`: unlike the route images this is an absolute URL to
// strava.com, not a path within this site.
const renderActivityLink = (rowEl, activity) => {
  const linkEl = rowEl.querySelector("[data-strava-activity-link]");
  if (!linkEl || !activity.stravaUrl) return;

  linkEl.href = activity.stravaUrl;
  linkEl.target = "_blank";
  // noopener because the opened page must not get a handle on this window;
  // noreferrer keeps the referrer off the request.
  linkEl.rel = "noopener noreferrer";
  linkEl.classList.add(LINKED_ROW_CLASS);
};

// The route thumbnail, and the dot it replaces.
//
// Every row ships both, and exactly one is shown: an activity recorded without
// GPS — an indoor ride, a treadmill run — has no route to draw, and a row that
// silently lost its left-hand element would sit out of line with its neighbours.
//
// The alt text names the activity rather than describing the picture. A route
// shape cannot be usefully described in words, and the title is already in the
// row beside it, so a screen reader gets the useful fact and no duplication.
const renderRouteMap = (rowEl, activity) => {
  const figureEl = rowEl.querySelector("[data-strava-activity-map]");
  const imageEl = rowEl.querySelector("[data-strava-activity-map-image]");
  const dotEl = rowEl.querySelector("[data-strava-activity-dot]");

  if (!figureEl || !imageEl) return;

  if (!activity.routeImage) {
    figureEl.hidden = true;
    return;
  }

  // Through the same `prefix` as fetchJsonData and hifi.js: GitHub Pages serves
  // the site from a subpath, so the stored root-relative path would resolve
  // outside the site and 404.
  //
  // Cache-busted because a re-scrape rewrites these images *under the same file
  // name* — the name is the activity id, which does not change when the picture
  // does. Fixing a bad capture would otherwise leave the old one on screen.
  imageEl.src = bustCache(prefix + activity.routeImage);
  imageEl.alt = `Route of ${activity.name}`;
  figureEl.hidden = false;
  if (dotEl) dotEl.hidden = true;
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
