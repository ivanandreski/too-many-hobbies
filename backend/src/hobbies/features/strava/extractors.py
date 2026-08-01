"""
In-page extraction snippets.

These run inside the browser and do as little as possible: locate a region and
hand back its visible text. Every bit of interpretation happens in Python
(page_parser.py), which keeps the fragile, untestable part of scraping down to
"find the right box" and makes the rest ordinary unit-tested code.

Regions are found by the words Strava renders — "This Year", "All-Time", a bike
name — rather than by CSS class names, which are generated and change between
deploys.
"""

# Finds a heading whose text matches one of `headings`, then climbs to the
# nearest ancestor holding several lines of text and returns that text.
# Returns null when nothing matches, which the caller reports as a scrape failure.
SECTION_TEXT_BY_HEADING = """
(headings) => {
    const wanted = headings.map((heading) => heading.toLowerCase());
    const MAX_HEADING_LENGTH = 60;
    const MAX_CLIMB = 6;
    const MIN_LINES = 3;

    const isMatch = (text) =>
        wanted.some((heading) => text === heading || text.startsWith(heading));

    const candidates = document.querySelectorAll(
        'h1,h2,h3,h4,h5,h6,[role="heading"],dt,legend,caption,strong,b,span,div,p,button,a'
    );

    for (const element of candidates) {
        const text = (element.textContent || '').trim().toLowerCase();
        if (!text || text.length > MAX_HEADING_LENGTH || !isMatch(text)) continue;

        // Climb until an ancestor carries the heading *and* its stat lines.
        let node = element;
        for (let step = 0; step < MAX_CLIMB && node.parentElement; step++) {
            node = node.parentElement;
            const blockText = (node.innerText || '').trim();
            const lineCount = blockText.split('\\n').filter((line) => line.trim()).length;
            if (lineCount >= MIN_LINES) return blockText;
        }
    }
    return null;
}
"""

# Clicks the control that switches the totals panels to a given sport.
#
# These are icons (a bike, a running shoe), so there is no text to match on.
# Instead every candidate is scored against its identifying attributes —
# accessible name, title, data-*, class, icon reference — plus its text content
# if it happens to have any. Returns a description of what was clicked, or null
# when nothing matched, so the caller knows the panel was left untouched.
CLICK_SPORT_CONTROL = """
({ keywords, attributes }) => {
    const wanted = keywords.map((keyword) => keyword.toLowerCase());
    const CLICKABLE = 'button,a,[role="tab"],[role="button"],[role="radio"],label,li';

    const identifyingText = (element) => {
        const parts = [];
        for (const name of attributes) {
            const value = element.getAttribute && element.getAttribute(name);
            if (value) parts.push(value);
        }
        // Icons are often an <svg><use href="#icon-ride"> inside the control.
        for (const icon of element.querySelectorAll('svg, use, img, i, span')) {
            for (const name of [...attributes, 'xlink:href']) {
                const value = icon.getAttribute && icon.getAttribute(name);
                if (value) parts.push(value);
            }
        }
        const text = (element.textContent || '').trim();
        if (text && text.length <= 30) parts.push(text);
        return parts.join(' ').toLowerCase();
    };

    for (const element of document.querySelectorAll(CLICKABLE)) {
        const haystack = identifyingText(element);
        if (!haystack) continue;
        if (!wanted.some((keyword) => haystack.includes(keyword))) continue;

        // Skip anything that is plainly a navigation link away from the profile.
        const href = element.getAttribute('href') || '';
        if (href.startsWith('http') && !href.includes(location.hostname)) continue;

        element.click();
        return {
            tag: element.tagName.toLowerCase(),
            matched: haystack.slice(0, 200),
        };
    }
    return null;
}
"""

# Diagnostic: lists everything that looks like a sport switcher, with the
# attributes that identify it. Used by probe.py to work out the right keywords
# when CLICK_SPORT_CONTROL comes back null.
SPORT_CONTROL_CANDIDATES = """
(attributes) => {
    const CLICKABLE = 'button,a,[role="tab"],[role="button"],[role="radio"],label,li';
    const rows = [];

    for (const element of document.querySelectorAll(CLICKABLE)) {
        const found = {};
        for (const name of attributes) {
            const value = element.getAttribute && element.getAttribute(name);
            if (value) found[name] = value.slice(0, 120);
        }

        const icons = [];
        for (const icon of element.querySelectorAll('svg, use, img')) {
            const descriptor = {};
            for (const name of [...attributes, 'xlink:href']) {
                const value = icon.getAttribute && icon.getAttribute(name);
                if (value) descriptor[name] = value.slice(0, 120);
            }
            if (Object.keys(descriptor).length) icons.push(descriptor);
        }

        const text = (element.textContent || '').trim().slice(0, 40);
        if (!Object.keys(found).length && !icons.length && !text) continue;

        rows.push({ tag: element.tagName.toLowerCase(), text, attributes: found, icons });
    }
    return rows.slice(0, 80);
}
"""

# Returns one entry per activity row on the training page. `text` is the row's
# visible text; `commuteMarkup` flags a commute indicator found in the row's
# markup (icon class, title attribute or badge), which page_parser trusts over
# the activity name.
ACTIVITY_ROWS = """
() => {
    const MAX_MARKUP = 600;

    // Tried in order; the first selector yielding rows wins. Strava has served
    // this list as both a table and a card list.
    const rowSelectors = [
        'table tbody tr',
        '[data-testid*="activity"]',
        '[class*="activity-list"] li',
        '[class*="ActivityList"] li',
        'ul[class*="feed"] > li',
    ];

    let rows = [];
    for (const selector of rowSelectors) {
        const found = [...document.querySelectorAll(selector)];
        if (found.length > rows.length) rows = found;
        if (rows.length) break;
    }

    return rows.map((row) => {
        const markup = row.innerHTML || '';
        const link = row.querySelector('a[href*="/activities/"]');
        return {
            text: (row.innerText || '').trim(),
            commuteMarkup: /commute/i.test(markup),
            activityUrl: link ? link.getAttribute('href') : null,
            markupSample: markup.slice(0, MAX_MARKUP),
        };
    }).filter((row) => row.text);
}
"""

# Diagnostic only: used by probe.py to report what a page actually contains when
# the extractors above come back empty.
PAGE_OUTLINE = """
() => {
    const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')]
        .map((el) => (el.textContent || '').trim())
        .filter(Boolean)
        .slice(0, 60);

    const buttons = [...document.querySelectorAll('button,[role="tab"]')]
        .map((el) => (el.textContent || '').trim())
        .filter((text) => text && text.length < 30)
        .slice(0, 60);

    return { headings, buttons, url: location.href, title: document.title };
}
"""
