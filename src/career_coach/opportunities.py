"""Curated source discovery, not a live listing search or eligibility checker."""

import re

SOURCES = [
    (
        "jobs",
        "USAJOBS",
        "https://www.usajobs.gov/",
        {"government", "research", "engineering", "data", "software"},
    ),
    (
        "internships",
        "NASA internships",
        "https://www.nasa.gov/learning-resources/internship-programs/",
        {"research", "engineering", "science", "data", "internship"},
    ),
    (
        "research",
        "NSF REU",
        "https://www.nsf.gov/funding/initiatives/reu",
        {"research", "science", "undergraduate", "engineering"},
    ),
    (
        "entrepreneurial",
        "Y Combinator apply",
        "https://www.ycombinator.com/apply",
        {"startup", "founder", "entrepreneur", "business", "software"},
    ),
]


def discover(profile):
    text = " ".join(profile.values()).lower()
    tokens = set(re.findall(r"[a-z]+", text))
    ranked = sorted(SOURCES, key=lambda s: len(tokens & s[3]), reverse=True)
    lines = [
        "Curated public source suggestions — NOT verified open opportunities.",
        "Match uses profile/description keywords (self-reported); no eligibility or readiness inference.",
        "Open each source to check current listings, deadlines, location and eligibility.",
    ]
    for kind, name, url, keywords in ranked:
        matches = sorted(tokens & keywords)
        lines.append(
            f"- {kind}: {name}\n  {url}\n  Keyword overlap: {', '.join(matches) or 'none; general discovery source'}"
        )
    return "\n".join(lines)


SKILL_TERMS = {
    "python": {"python"},
    "java": {"java"},
    "sql": {"sql", "postgresql"},
    "algorithms": {"algorithms", "algorithm", "structures"},
    "cloud": {"cloud", "aws"},
    "systems": {"systems", "scalable", "distributed"},
    "communication": {"communication", "collaborate", "collaboration"},
    "ownership": {"ownership", "own"},
    "research": {"research"},
    "customer-discovery": {"customer", "customers", "discovery"},
}


def skills_in(text):
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    return {skill for skill, terms in SKILL_TERMS.items() if tokens & terms}


def match_opportunity(description, profile, results):
    required = skills_in(description)
    reported = skills_in(profile.get("background", ""))
    demonstrated = {r.question.skill.lower() for r in results if r.evaluation.score >= 2}

    def show(values):
        return ", ".join(sorted(values)) or "none identified"

    return "\n".join(
        [
            "Pasted opportunity match — keyword baseline, not an eligibility or readiness judgment.",
            f"Recognized requirement topics: {show(required)}",
            f"Self-reported overlap (unverified): {show(required & reported)}",
            f"Demonstrated overlap (score 2+ in this short sample): {show(required & demonstrated)}",
            f"Topics without demonstrated evidence: {show(required - demonstrated)}",
            "Missing evidence does not mean missing ability. This small vocabulary misses synonyms, "
            "qualifications and context. Verify the full listing, deadlines and eligibility yourself.",
        ]
    )
