"""Schema.org structured data, as plain dictionaries.

Search engines read this to understand what a page *is* rather than guessing
from the prose, which is what produces the richer results: the business panel
with a phone number and opening hours, expandable FAQ entries, and job listings
in Google's jobs experience.

Built in Python rather than written into templates by hand because a stray
apostrophe in a service description would silently break hand-written JSON, and
a broken block is ignored in full.
"""

import re

from django.urls import reverse

# Suburb, state and postcode are stored as one free-text line ("Toowoomba, QLD
# 4350") because that is how a person writes an address. Schema.org wants the
# parts separately, so they are split back out here, conservatively: anything
# unrecognised is left in the street field rather than guessed at.
DEFAULT_LOCALITY = "Toowoomba"
DEFAULT_REGION = "QLD"
DEFAULT_POSTCODE = "4350"
DEFAULT_COUNTRY = "AU"


def _absolute(request, path):
    """Make a site-relative path absolute, which structured data requires."""
    if not path:
        return None
    return request.build_absolute_uri(path)


def postal_address(site):
    address = (site.address or "").strip()
    locality, region, postcode = DEFAULT_LOCALITY, DEFAULT_REGION, DEFAULT_POSTCODE

    parts = [part.strip() for part in address.split(",") if part.strip()]
    if len(parts) >= 2:
        locality = parts[-2]
        tail = parts[-1].rsplit(" ", 1)
        if len(tail) == 2 and tail[1].isdigit():
            region, postcode = tail[0], tail[1]
        else:
            region = parts[-1]

    return {
        "@type": "PostalAddress",
        "addressLocality": locality,
        "addressRegion": region,
        "postalCode": postcode,
        "addressCountry": DEFAULT_COUNTRY,
    }


DAYS = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}
DAY_ORDER = list(DAYS.values())

HOURS_PATTERN = re.compile(
    r"(?P<from>[A-Za-z]{3})[A-Za-z]*\s*[-–]\s*(?P<to>[A-Za-z]{3})[A-Za-z]*"
    r".*?(?P<open>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
    r"\s*[-–]\s*(?P<close>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
    re.IGNORECASE | re.DOTALL,
)


def _to_24h(value):
    """"8:00 AM" -> "08:00". Returns None if it cannot be read confidently."""
    match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", value.strip(), re.IGNORECASE)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower()

    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0

    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def opening_hours(hours):
    """Parse "Mon - Fri, 8:00 AM - 5:00 PM" into a schema.org specification.

    Opening hours are stored as free text because that is what belongs on the
    page. This reads the common shape and gives up quietly on anything else -
    omitting the property is fine, publishing wrong hours is not.
    """
    if not hours:
        return None

    match = HOURS_PATTERN.search(hours)
    if not match:
        return None

    start = DAYS.get(match.group("from")[:3].lower())
    end = DAYS.get(match.group("to")[:3].lower())
    opens = _to_24h(match.group("open"))
    closes = _to_24h(match.group("close"))
    if not (start and end and opens and closes):
        return None

    first, last = DAY_ORDER.index(start), DAY_ORDER.index(end)
    days = DAY_ORDER[first : last + 1] if first <= last else DAY_ORDER[first:] + DAY_ORDER[: last + 1]

    return [
        {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": days,
            "opens": opens,
            "closes": closes,
        }
    ]


def organization(request, site):
    """The business itself, attached to every page.

    Typed as LocalBusiness rather than Organization because the searches that
    matter here are local - someone looking for disability support near
    Toowoomba, not the company by name.
    """
    home = _absolute(request, reverse("home"))

    data = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "@id": f"{home}#organization",
        "name": site.name,
        "url": home,
        "description": site.footer_description or site.tagline or "",
        "address": postal_address(site),
        "areaServed": {"@type": "City", "name": DEFAULT_LOCALITY},
    }

    hours = opening_hours(site.hours)
    if hours:
        data["openingHoursSpecification"] = hours

    if site.logo_url:
        data["logo"] = _absolute(request, site.logo_url)
        data["image"] = data["logo"]
    if site.phone:
        data["telephone"] = site.phone_href.replace("tel:", "")
    if site.email:
        data["email"] = site.email
    if site.abn:
        # Australian Business Number - the local equivalent of a tax ID.
        data["taxID"] = site.abn

    profiles = [
        _absolute(request, link.url)
        for link in getattr(site, "_social_links", [])
        if link.url
    ]
    if profiles:
        data["sameAs"] = profiles

    return data


def breadcrumbs(request, trail):
    """`trail` is [(name, url-or-None), ...], last item being the current page.

    Gives search results a readable path instead of a bare URL, and helps a
    crawler understand how the site nests.
    """
    items = []
    for position, (name, url) in enumerate(trail, start=1):
        entry = {"@type": "ListItem", "position": position, "name": name}
        if url:
            entry["item"] = _absolute(request, url)
        items.append(entry)

    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


def service(request, obj, site):
    home = _absolute(request, reverse("home"))
    data = {
        "@context": "https://schema.org",
        "@type": "Service",
        "name": obj.title,
        "description": obj.meta_description or obj.summary,
        "url": _absolute(request, obj.get_absolute_url()),
        "serviceType": obj.title,
        "provider": {"@id": f"{home}#organization"},
        "areaServed": {"@type": "City", "name": DEFAULT_LOCALITY},
    }
    if obj.image_url:
        data["image"] = _absolute(request, obj.image_url)
    return data


def job_posting(request, vacancy, site):
    """A vacancy, in the form Google's job search expects.

    `hiringOrganization` is spelled out rather than referenced by @id: Google
    documents these as required properties and does not resolve a reference for
    them the way the general schema.org model would.
    """
    data = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": vacancy.title,
        "description": vacancy.description or vacancy.summary,
        "datePosted": vacancy.created_at.date().isoformat(),
        "employmentType": _employment_type(vacancy.employment_type),
        "hiringOrganization": {
            "@type": "Organization",
            "name": site.name,
            "sameAs": _absolute(request, reverse("home")),
        },
        "jobLocation": {
            "@type": "Place",
            "address": postal_address(site),
        },
        "directApply": True,
    }

    if vacancy.location:
        data["jobLocation"]["address"] = {
            **data["jobLocation"]["address"],
            "streetAddress": vacancy.location,
        }
    if vacancy.closing_date:
        data["validThrough"] = vacancy.closing_date.isoformat()

    return data


def _employment_type(value):
    """Map Vacancy.EmploymentType onto the vocabulary Google accepts.

    Keep this in step with the model's choices - an unrecognised value falls
    back to OTHER, which is valid but tells a job seeker nothing.
    """
    lookup = {
        "full_time": "FULL_TIME",
        "part_time": "PART_TIME",
        # Australian casual work has no exact counterpart in the vocabulary.
        # PART_TIME plus TEMPORARY is the closest honest description.
        "casual": ["PART_TIME", "TEMPORARY"],
        "casual_part_time": ["PART_TIME", "TEMPORARY"],
        "contract": "CONTRACTOR",
        "fixed_term": "TEMPORARY",
        "internship": "INTERN",
        "volunteer": "VOLUNTEER",
    }
    return lookup.get(str(value).lower().replace("-", "_"), "OTHER")


def faq_page(faqs):
    """`faqs` is an iterable of objects or dicts with question/answer."""
    entries = []
    for item in faqs:
        question = item.get("question") if isinstance(item, dict) else getattr(item, "question", None)
        answer = item.get("answer") if isinstance(item, dict) else getattr(item, "answer", None)
        if not (question and answer):
            continue
        entries.append(
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
        )

    if not entries:
        return None

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entries,
    }


def person(request, member, site):
    home = _absolute(request, reverse("home"))
    data = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": member.name,
        "jobTitle": member.role,
        "url": _absolute(request, member.get_absolute_url()),
        "worksFor": {"@id": f"{home}#organization"},
    }
    if member.photo_url:
        data["image"] = _absolute(request, member.photo_url)
    if member.bio:
        data["description"] = member.bio
    return data
