// Renders the Strava cycling and running widgets.
//
// Both sports share one set of markup (components/cycling.html and
// components/running.html) and differ only in the middle summary stat: cycling
// shows average speed, running shows average pace. Each widget root carries a
// data-strava-sport attribute naming which of the two it is.
//
// The JSON files hold raw Strava values — metres, seconds, local ISO timestamps —
// and every displayed number is derived here. That keeps a single source of
// truth for each fact, so distance and speed can never disagree.

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const METRES_PER_KILOMETRE = 1000;

// Per-sport rendering rules. `secondary` describes the middle summary stat and
// the matching per-activity metric.
const SPORTS = {
  cycling: {
    dataPath: "/data/strava/cycling.json",
    countLabel: "Rides",
    secondary: {
      label: "Avg Speed",
      unit: "km/h",
      format: (distanceMetres, movingTimeSeconds) =>
        formatSpeedKmh(distanceMetres, movingTimeSeconds),
    },
  },
  running: {
    dataPath: "/data/strava/running.json",
    countLabel: "Runs",
    secondary: {
      label: "Avg Pace",
      unit: "/km",
      format: (distanceMetres, movingTimeSeconds) =>
        formatPacePerKm(distanceMetres, movingTimeSeconds),
    },
  },
};

// --- Formatting -------------------------------------------------------------

// Headline summary figure: trims a pointless ".0" so 248000 m reads as "248"
// while 31800 m still reads as "31.8".
const formatSummaryDistanceKm = (distanceMetres) => {
  const kilometres = distanceMetres / METRES_PER_KILOMETRE;
  return Number(kilometres.toFixed(1)).toString();
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
  const { summary, period } = stravaData;

  setText(widgetEl, "[data-strava-period]", period);
  setText(widgetEl, "[data-strava-distance]", formatSummaryDistanceKm(summary.distanceMetres));
  setText(widgetEl, "[data-strava-count]", summary.activityCount);
  setText(widgetEl, "[data-strava-count-label]", sport.countLabel);

  setText(
    widgetEl,
    "[data-strava-secondary-value]",
    sport.secondary.format(summary.distanceMetres, summary.movingTimeSeconds),
  );
  setText(widgetEl, "[data-strava-secondary-unit]", sport.secondary.unit);
  setText(widgetEl, "[data-strava-secondary-label]", sport.secondary.label);
};

const renderActivities = (widgetEl, sport, activities) => {
  const templateEl = widgetEl.querySelector("[data-strava-activity-template]");

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

    templateEl.parentNode.appendChild(clone);
  });
};

const setText = (rootEl, selector, value) => {
  const targetEl = rootEl.querySelector(selector);
  if (targetEl) targetEl.innerText = value;
};

const initStravaWidget = async (widgetEl) => {
  const sportName = widgetEl.dataset.stravaSport;
  const sport = SPORTS[sportName];

  if (!sport) {
    console.error(`Unknown Strava sport: ${sportName}`);
    return;
  }

  const stravaData = await fetchJsonData(sport.dataPath);

  // fetchJsonData returns [] on failure, so bail rather than throw on .summary.
  if (!stravaData || !stravaData.summary) {
    console.error(`No Strava data for ${sportName}`);
    return;
  }

  renderSummary(widgetEl, sport, stravaData);
  renderActivities(widgetEl, sport, stravaData.activities || []);
};

export const StravaData = {
  init: async () => {
    const widgetEls = document.querySelectorAll("[data-strava-widget]");
    await Promise.all([...widgetEls].map(initStravaWidget));
  },
};
