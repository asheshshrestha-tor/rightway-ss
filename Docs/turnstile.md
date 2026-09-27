# Turnstile

Cloudflare Turnstile guards the three public forms. It is one layer of several —
[Docs/form-protection.md](form-protection.md) covers the whole pipeline. This
page is the Turnstile detail.

| Form | `data-action` | Set in |
|---|---|---|
| Contact enquiry | `contact` | `ContactForm.turnstile_action` |
| Job application | `job-application` | `ApplicationForm.turnstile_action` |
| Consultation request | `consultation` | `ConsultationForm.turnstile_action` |

---

## Switching it on

Two environment variables, both required. With either one missing Turnstile
disables itself completely: no widget in the page, no check on submission.
That is deliberate — a fresh clone, the test suite and local development all
run with no Cloudflare account involved.

```
TURNSTILE_SITE_KEY=0x4AAAAAAFAluGVoc-gZgkNN
TURNSTILE_SECRET_KEY=...
```

The **sitekey is public**. It is read straight out of the page source; there is
nothing to protect.

The **secret is not**. It goes in `.env` or the hosting panel's environment and
nowhere else — not in git, not in a ticket, not pasted into a chat. Read it
from the Cloudflare dashboard under *Turnstile → this widget → Settings*, or:

```
wrangler turnstile widget get 0x4AAAAAAFAluGVoc-gZgkNN
```

(needs Wrangler 4.109 or newer, and `wrangler login` first). That prints the
secret, so pipe it nowhere and put it straight in `.env` by hand. If it is ever
exposed, rotate it in the dashboard — the sitekey stays the same, so nothing
else has to change.

The widget's domain list in Cloudflare must include every hostname the site is
served from, `www.` included. A hostname missing there fails every submission
from it.

---

## What the server checks

`pages/turnstile.py`. The widget alone protects nothing — the token it produces
is just a string, and anyone can post a made-up one straight to the form
endpoint, skipping the page entirely. So every submission is checked against
Cloudflare's siteverify API from the server, and three separate things have to
hold:

- **`success`** — Cloudflare issued this token, and it has not been spent
  before. Tokens last 300 seconds and validate exactly once; a replay comes
  back as `timeout-or-duplicate`.
- **`action`** — the token came from the form being submitted. Without this
  check, a token minted by whichever widget is cheapest to solve could be spent
  on any of the three.
- **`hostname`** — the token was issued to this site, not to a copy of the page
  hosted elsewhere under the same sitekey.

The secret is sent only in that server-to-server POST. It is never rendered
into a page, and siteverify is never called from the browser.

### Hostnames

`TURNSTILE_ALLOWED_HOSTNAMES` overrides the list; leave it unset and it is
derived from `ALLOWED_HOSTS` with wildcards dropped, which is right almost
always. If that leaves nothing — a bare `*`, or a local
`ALLOWED_HOSTS=127.0.0.1,localhost` — the hostname check turns itself off
rather than rejecting everything, so local development keeps working.

### When Cloudflare is unreachable

The submission is **refused**, with a message asking the visitor to try again.
Letting it through because the check itself broke would hand anyone who can
disrupt that one call a way straight past Turnstile. The refusal is logged at
`ERROR`; the contact and consultation pages both carry the phone number beside
the form, so there is always another way through.

---

## When something is being rejected

Every refusal is logged at `WARNING` with the reason and Cloudflare's own error
codes:

```
Turnstile rejected a contact submission: hostname 'www.example.com' is not one of ours (error-codes=none)
```

The visitor only ever sees one sentence, the same one for every cause, so a bot
learns nothing from it. The log is the only place the causes are told apart.

| In the log | Usually means |
|---|---|
| `no token in the submission` | JavaScript blocked, or a POST that never came from the page |
| `action was 'x', expected 'y'` | The template's `data-action` and the form's `turnstile_action` have drifted apart |
| `hostname '...' is not one of ours` | A hostname missing from `ALLOWED_HOSTS`, or from the widget's domain list in Cloudflare |
| `error-codes=invalid-input-secret` | Wrong or rotated secret |
| `error-codes=timeout-or-duplicate` | The token expired (over 5 minutes on the page) or was submitted twice |
| `siteverify unreachable` | Cloudflare could not be reached — see above |

The action in the template and the action on the form class are compared on
every submission, so they are changed together or not at all.

---

## Files

| File | What it does |
|---|---|
| `pages/turnstile.py` | The siteverify call and the three checks |
| `pages/forms.py` | `TurnstileFormMixin`, mixed into all three forms |
| `templates/pages/partials/turnstile.html` | The widget, included inside each `<form>` |
| `pages/context_processors.py` | Puts the sitekey in the template context |
| `pages/tests_turnstile.py` | Tests, with siteverify stubbed — nothing here calls Cloudflare |

No new dependency: the siteverify call uses `urllib` from the standard library.
