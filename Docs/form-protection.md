# Form protection

What guards the three public forms — the contact enquiry, the consultation
request and the job application — and in what order.

| Layer | Applies to | What happens when it trips |
|---|---|---|
| Daily rate limit | All three | Refused, with the phone number offered |
| Server-side validation | All three | Field errors, form redisplayed |
| Turnstile | All three | Form error, widget offers a retry |
| Honeypot | Contact only | Accepted and quarantined; the sender is not told |
| Secure email sending | All three | — |

Order matters. The cheapest check runs first, so a flood is turned away with
one cache read rather than a database write, a file upload and a call to
Cloudflare.

---

## 1. Daily rate limit

`pages/ratelimit.py`. **Three accepted submissions per day**, counted against
the visitor's IP address and against the email address they gave. Either
bucket filling blocks the next submission until the window expires.

The window runs for 24 hours **from the first submission**, not the last — the
counter is created with `cache.add` and then incremented, so three messages in
quick succession do not extend the lockout to a day after the third.

### The quota is per form

Three enquiries, three consultation requests and three job applications, each
counted separately. Not three submissions in total.

This is deliberate. Someone applying for three advertised roles and then asking
a question about a fourth is doing something entirely ordinary, and a shared
counter would stop them. The cost is that a determined sender gets nine
submissions a day across all three forms rather than three — acceptable,
because Turnstile is the actual bot defence and this is the backstop.

### What counts

- **Only submissions that passed validation.** Someone mistyping their email
  four times has not used up their allowance.
- **Spam counts.** A tripped honeypot burns quota exactly like a real message,
  so repeatedly hitting the trap is not a free way to hammer the endpoint.

### Known limitation: shared addresses

A limit of three per IP per day is aggressive for this particular site. A
support coordinator's office, a group home, a school, a public library, or any
mobile network using CGNAT can put many unrelated people behind one address.
The fourth genuine enquirer on that network is refused for 24 hours.

Two things soften it, neither of which removes it:

- The refusal always carries the phone number, and the contact and consultation
  pages both show it beside the form.
- The email bucket is separate, so this only bites when several people share
  both a network and a day.

If office enquiries start going missing, raising `SUBMISSION_LIMIT` — or
raising only the IP limit while leaving the email limit at three — is the first
thing to try. Both are one constant in `pages/ratelimit.py`.

### Where the counters live

`CACHES` uses Django's database backend, so the counters are rows in
`django_cache`. Migration `pages/0015_cache_table.py` creates that table,
because nothing on a deploy runs `manage.py createcachetable` and all three
forms check the limit before doing anything else — a missing table means all
three return 500.

> **If the cache is ever moved to Redis**, note that the test suite currently
> relies on `DatabaseCache` writes rolling back with each test's transaction.
> On Redis, counters would leak between tests and cause confusing failures.
> `pages/tests_ratelimit.py` clears the cache in `setUp`; other test modules do
> not.

---

## 2. Server-side validation

`pages/forms.py`. Every rule is enforced on the server, never only in the
browser: `accept` on a file input, `min` on a date, and `required` are all
hints a client can ignore.

- **Contact** — a real email address, and a message of at least 10 characters.
- **Application** — résumé extension and size checked against
  `RESUME_ALLOWED_EXTENSIONS` and `RESUME_MAX_BYTES`, not just the `accept`
  attribute.
- **Consultation** — weekdays only, at least one business day's notice, a
  suburb when a home visit is asked for, and a participant name when the
  enquiry is on someone else's behalf.

---

## 3. Turnstile

[Docs/turnstile.md](turnstile.md) has the detail. In short: the widget's token
is verified server-side against Cloudflare on every submission, and `success`,
`action` and `hostname` are all checked.

---

## 4. Honeypot — contact form only

A hidden field, `hp_reference`, that people never see and bots tend to fill.

**A tripped honeypot does not reject the message.** It is saved as an `Enquiry`
with `status=SPAM`, no notification email goes out, and the sender sees the
ordinary success message.

Three reasons for that shape:

- The trap can misfire. A browser autofilling a hidden field is not a bot, and
  a dropped message from someone asking about disability support is not
  recoverable.
- Telling a bot it was caught teaches it to avoid the trap.
- Staff can review what was caught. The dashboard hides spam from the enquiry
  list and the counts, and shows a spam count on the overview.

The field name is deliberately meaningless. Names like `website`, `url` or
`company` are standard autofill tokens that Chrome fills even off-screen with
`autocomplete="off"`.

---

## 5. Secure email sending

[Docs/email.md](email.md) has the detail. Amazon SES over its API via boto3 —
TLS throughout, credentials from the environment, never in the repo. Recipients
are derived from dashboard permissions rather than a hardcoded list.

---

## Reviewing what was caught

| Where | What it shows |
|---|---|
| Dashboard → Enquiries | Spam is excluded from the list and the counts |
| Dashboard overview | A spam count, so quarantined messages are visible |
| Application log, `WARNING` | Every rate-limit refusal and every Turnstile rejection, with the reason |

A refusal never explains itself to the visitor beyond one plain sentence — a
bot would learn from the detail. The log is where the causes are told apart.
