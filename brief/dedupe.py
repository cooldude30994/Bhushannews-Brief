"""
Deduplication, three layers:

  1. Canonical URL hash  — strips tracking params, catches exact re-shares.
  2. Normalised title hash — catches syndicated copies with different URLs.
  3. Fuzzy title clustering — catches near-identical headlines across outlets
     (rapidfuzz token_set_ratio >= FUZZY_THRESHOLD).

Also cross-checks against `state["seen"]` so a story already sent in a
previous run (within the retention window) isn't repeated even if today's
feed still lists it.

Within each cluster, the "representative" item is chosen by:
  - primary/government/regulator sources first (see PRIMARY_SOURCE_HINTS)
  - otherwise the earliest published item
The rest are recorded as `also_covered_by`.
"""
import hashlib
import re
import urllib.parse

from rapidfuzz import fuzz

FUZZY_THRESHOLD = 88

PRIMARY_SOURCE_HINTS = [
    "oecd.org", "incometax.gov.in", "cbic.gov.in", "pib.gov.in",
    "gst.gov.in", "mca.gov.in", "sebi.gov.in", "rbi.org.in",
    "egazette", "gazette",
]

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                    "utm_content", "ref", "cid", "src"}


def canonical_url(url):
    try:
        parts = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parts.query)
        query = [(k, v) for k, v in query if k.lower() not in TRACKING_PARAMS]
        path = parts.path.rstrip("/")
        clean = urllib.parse.urlunsplit((parts.scheme, parts.netloc, path,
                                          urllib.parse.urlencode(query), ""))
        return clean.lower()
    except Exception:  # noqa: BLE001
        return url.lower()


def normalise_title(title):
    t = title.lower()
    t = re.sub(r"[\u2013\u2014-]\s*[a-z0-9 .]+$", "", t)  # strip " - Outlet Name" suffix
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def fingerprint(item):
    curl = canonical_url(item["link"])
    return hashlib.sha1(curl.encode("utf-8")).hexdigest()


def is_primary_source(item):
    link = item["link"].lower()
    source = (item.get("source") or "").lower()
    return any(h in link or h in source for h in PRIMARY_SOURCE_HINTS)


def dedupe(items, seen_fingerprints):
    """Returns a list of representative items, each with an added
    'also_covered_by' list of other outlet names, and a set of new
    fingerprints to merge into state['seen']."""
    # Drop anything whose canonical URL was already sent in a prior run.
    fresh = []
    new_fps = set()
    for it in items:
        fp = fingerprint(it)
        if fp in seen_fingerprints:
            continue
        it["_fp"] = fp
        it["_norm_title"] = normalise_title(it["title"])
        fresh.append(it)

    # Exact URL dedupe within this run (same story, same link, multiple feeds)
    by_fp = {}
    for it in fresh:
        by_fp.setdefault(it["_fp"], []).append(it)
    stage1 = [group[0] for group in by_fp.values()]
    for group in by_fp.values():
        stage1_item = group[0]
        others = {g["source"] for g in group[1:] if g.get("source")}
        stage1_item.setdefault("also_covered_by", set()).update(others)

    # Exact normalised-title dedupe
    by_title = {}
    for it in stage1:
        by_title.setdefault(it["_norm_title"], []).append(it)
    stage2 = []
    for group in by_title.values():
        rep = _pick_representative(group)
        others = {g["source"] for g in group if g is not rep and g.get("source")}
        rep.setdefault("also_covered_by", set()).update(others)
        stage2.append(rep)

    # Fuzzy clustering across remaining items (within same bucket only)
    clusters = []
    used = [False] * len(stage2)
    for i, it in enumerate(stage2):
        if used[i]:
            continue
        cluster = [it]
        used[i] = True
        for j in range(i + 1, len(stage2)):
            if used[j] or stage2[j]["bucket"] != it["bucket"]:
                continue
            score = fuzz.token_set_ratio(it["_norm_title"], stage2[j]["_norm_title"])
            if score >= FUZZY_THRESHOLD:
                cluster.append(stage2[j])
                used[j] = True
        clusters.append(cluster)

    final = []
    for cluster in clusters:
        rep = _pick_representative(cluster)
        others = {c["source"] for c in cluster if c is not rep and c.get("source")}
        rep.setdefault("also_covered_by", set()).update(others)
        rep["also_covered_by"] = sorted(x for x in rep["also_covered_by"] if x)
        final.append(rep)
        new_fps.add(rep["_fp"])

    return final, new_fps


def _pick_representative(group):
    primary = [g for g in group if is_primary_source(g)]
    pool = primary if primary else group
    return min(pool, key=lambda g: g["published"])
