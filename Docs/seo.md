# SEO

What is built into the site, and what still needs doing by hand.

Most of this is automatic — add a service in the dashboard and it appears in
the sitemap with its own structured data, no extra step. The parts that need a
person are in [Still to do](#still-to-do) at the end.

---

## What the site does

### Every page

| Element | Where it comes from |
|---|---|
| `<title>` | `{% block title %}` in the page template |
| `<meta name="description">` | `{% block meta_description %}` |
| `<link rel="canonical">` | The current URL, minus any query string |
| Open Graph + Twitter tags | `{% block og_title %}` / `{% block og_description %}` |
| `LocalBusiness` structured data | Site settings, via the context processor |

**Canonicals** matter more than they look. A visitor arriving from a campaign
link lands on `/services/?utm_source=facebook`; without a canonical tag that is
a second page competing with `/services/` for the same ranking.

**Open Graph** controls the preview when a page is shared in Facebook,
LinkedIn, WhatsApp or a text message. For a disability support provider that is
often how a family first sees the site.

Titles and descriptions have length limits worth respecting: roughly **60
characters** for a title and **160** for a description before search results cut
them off mid-sentence. `Docs/seo.md` aside, the quickest check is to look at the
rendered page.

### Structured data

Schema.org data tells a search engine what a page *is*, rather than leaving it
to infer from the prose. It is what produces the richer results.

| Page | Type | What it can produce |
|---|---|---|
| Every page | `LocalBusiness` | Business panel: phone, address, opening hours |
| Service detail | `Service` + `BreadcrumbList` | Breadcrumb trail in results |
| Vacancy detail | `JobPosting` | Listing in Google's jobs experience |
| Team member | `Person` + `BreadcrumbList` | |
| FAQ | `FAQPage` | Expandable questions under the result |

Built in [pages/structured_data.py](../pages/structured_data.py) as plain
dictionaries and rendered by the `{% ld_json %}` tag, which escapes `<`, `>`
and `&`. That escaping is not cosmetic: content is administrator-editable, and
a `</script>` inside a service description would otherwise close the tag early
and inject the rest into the page as markup.

`JobPosting` is the one with real commercial value here — it puts vacancies in
front of job seekers without paying a job board. It needs `datePosted`,
`hiringOrganization` and a location, all of which are filled from the vacancy
and the site settings.

### Sitemap and robots

- `/sitemap.xml` — every public page, with last-modified dates.
  Unpublished services and closed vacancies are excluded automatically.
- `/robots.txt` — disallows `/dashboard/`, `/admin/` and the consultation
  thank-you page, and points at the sitemap.

The sitemap URL in `robots.txt` is generated from the request, so it stays
correct across the Railway domain and the final custom domain.

Definitions live in [pages/sitemaps.py](../pages/sitemaps.py). Priorities are
relative and only order this site against itself — the pages that win enquiries
sit above the legal boilerplate.

---

## Editing content well

The dashboard fields that affect search results:

**Service → Meta description.** Falls back to the summary when empty. Write one
for each service: it is the sentence that appears under the link in Google.
Around 150 characters, describing the service, not the company.

**Service → Title.** Becomes the page title and the heading. "Personal Care" is
better than "Our Personal Care Support Offering".

**Vacancy → Employment type.** Feeds `employmentType` in the job listing. It
maps onto Google's fixed vocabulary in `structured_data._employment_type`; if
you add a new choice to the model, add it there too, or it degrades to `OTHER`.

**Site settings → Address, phone, hours.** These become the `LocalBusiness`
block. The hours field is free text and is parsed for the structured data, so
keep the "Mon - Fri, 8:00 AM - 5:00 PM" shape. Anything it cannot read
confidently is left out rather than guessed at — wrong opening hours in a
search result are worse than none.

**Site settings → Follow us.** Published links with a real URL become `sameAs`,
which is how a search engine ties the site to its social profiles. Rows left
without a URL are skipped.

---

## Still to do

These need a person, not code.

**1. Verify the domain in Google Search Console.** Nothing else on this list
matters as much. Add the property, submit `/sitemap.xml`, then read the
Coverage and Enhancements reports — that is where you find out whether the
`JobPosting` and `FAQPage` data was accepted.

Also test individual pages with the
[Rich Results Test](https://search.google.com/test/rich-results).

**2. Create a Google Business Profile.** For "NDIS provider Toowoomba" and
similar searches, the map pack sits above the ordinary results. The
`LocalBusiness` data supports it but does not replace it. Keep the name,
address and phone identical to the site — inconsistency between them is what
holds local rankings back.

**3. Make a proper share image.** `og:image` currently points at
`static/images/hero-home.png`. Social platforms want **1200×630**; anything
else gets cropped unpredictably. One branded image with the logo and a short
line of text is enough, and it is what people see when the site is shared.

**4. Write real service meta descriptions.** Several fall back to the summary,
which reads as description rather than invitation.

**5. Get listed where NDIS participants actually look.** Directory listings and
local links matter more for this sector than general link building. Start with
the NDIS provider finder, local disability networks and Toowoomba business
directories.

**6. Check `TRUST_PROXY_SSL_HEADER=True` is set in production.** Without it
Django believes requests are plain HTTP and writes `http://` canonicals and
`og:url` values on an HTTPS site, which is a needless self-inflicted wound.

**7. Consider a blog or resources section.** The searches that bring in
enquiries are questions — "what can I use my NDIS funding for", "how to change
NDIS provider". The site currently has nothing aimed at those, and the FAQ page
is the only thing close. This is the largest remaining opportunity and the one
that takes the most sustained effort.

---

## Checking your work

```bash
python manage.py test pages.tests_seo
```

18 tests covering the sitemap, robots.txt, canonicals and every structured data
block. They parse the JSON rather than matching substrings, because a malformed
block is skipped in full by search engines and nothing on the page looks wrong.

To see what a crawler sees:

```bash
curl -s http://127.0.0.1:8000/robots.txt
curl -s http://127.0.0.1:8000/sitemap.xml | head -40
```
