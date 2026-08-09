# Email

Every public form sends two messages:

- a **notification** to the staff who can act on it, with a button through to
  the record in the dashboard;
- a **confirmation** to the person who submitted it, so they know it arrived.

| Form | Notification subject | Confirmation |
|---|---|---|
| Contact | `New enquiry: {name}` | "We've received your message" |
| Job application | `Job application: {role}` | "We've received your application for {role}" |
| Consultation | `Consultation request: {name} ({ref})` | Acknowledgement with their reference |

Consultations send a third message later, when staff confirm a time from the
dashboard.

---

## Who gets notified

Not a list in a settings file. It is worked out from the same permissions that
guard the dashboard:

| Submission | Permission required |
|---|---|
| Contact enquiry | `pages.view_enquiry` |
| Job application | `pages.view_application` |
| Consultation request | `pages.view_consultation` |

Every active staff user holding the permission, plus the office address from
the dashboard Settings page. Superusers hold every permission and always
receive everything.

This means someone in the **Enquiry Handler** group is told about enquiries but
not job applications — which is right, because the button in an application
notification would only turn them away. Add a user to a group and they start
receiving; remove them and they stop. Nothing to remember to update.

A staff account with no email address on it cannot be notified. The command
below lists any.

`ADMIN_NOTIFICATION_EMAILS` adds addresses that have no staff account — a
developer or agency watching submissions. Usually empty.

### Check it

```bash
python manage.py test_notifications
```

Prints the mail configuration, then who would be notified about each kind of
submission and why:

```
Contact enquiries  (pages.view_enquiry)
    arshdeep@rightwaysupportservices.com.au  (staff)
    priya@rightwaysupportservices.com.au  (staff)
    michael@rightwaysupportservices.com.au  (staff)

Job applications  (pages.view_application)
    arshdeep@rightwaysupportservices.com.au  (staff)
```

It warns if nobody would be notified about something, which is the failure that
otherwise goes unnoticed until someone asks why nobody replied.

Add `--send you@example.com` to send a real sample notification and
confirmation. Nothing is written to the database.

```bash
python manage.py test_notifications --send you@example.com --host your-site.up.railway.app
```

`--host` sets the domain in the button link; pass your real one to check the
link works from an inbox.

---

## Testing without emailing real people

Testing the flow means submitting real-looking forms, and those produce real
emails — to the office, to every member of staff with the permission, and to
whatever address was typed into the form. On a staging site that means the
client receives test traffic, and a mistyped address means a stranger does.

Set `EMAIL_REDIRECT_TO` and every outgoing message goes there instead:

```ini
EMAIL_REDIRECT_TO=you@example.com
```

The redirect happens at the last moment before sending, **after** the site has
worked out who would have received it, so the routing under test is still the
real thing. What arrives looks like this:

```
Subject: [TEST -> arshdeep@..., priya@..., michael@...] New enquiry: Dana Whitfield

[Redirected email]
This would have been sent to: arshdeep@..., priya@..., michael@...
```

The HTML version carries a red banner saying the same, so a redirected message
is never mistaken for a real one.

It covers password resets and consultation confirmations too — everything the
site sends.

**Remove it when you are done.** With it set, nobody receives anything.

---

## Making mail actually deliver

The default backend prints to the terminal and sends nothing, which keeps the
forms working before any credentials exist. To send for real:

```ini
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-username
EMAIL_HOST_PASSWORD=your-password
DEFAULT_FROM_EMAIL=no-reply@rightwaysupportservices.com.au
```

Use a transactional provider — Postmark, SendGrid, Mailgun, SES. Consumer Gmail
rate-limits and will eventually block this.

**Set up SPF and DKIM for the domain.** Mail claiming to be from
`rightwaysupportservices.com.au` without them lands in spam or is rejected
outright, and confirmations that silently fail are worse than none — the
sender assumes their enquiry never arrived. Every provider documents the DNS
records; do it before going live.

---

## How it fits together

| File | What it does |
|---|---|
| [pages/notifications.py](../pages/notifications.py) | Recipients, notifications, confirmations |
| [pages/consultation_mail.py](../pages/consultation_mail.py) | The consultation acknowledgement and "time confirmed" message |
| [config/email_backend.py](../config/email_backend.py) | The `EMAIL_REDIRECT_TO` safety net |
| [templates/email/notification.\*](../templates/email/) | Staff notification, HTML and text |
| [templates/email/confirmation.\*](../templates/email/) | Confirmation to the submitter, HTML and text |

Both templates are sent as HTML **with a plain-text alternative**. Some clients
refuse to render HTML, and a message nobody can read is worse than none.

Failures are logged, never raised. The submission is already in the database by
the time email is attempted, so a mail outage cannot turn a saved enquiry into
an error page for the person who sent it. The consequence is that a broken mail
server is invisible from the front end — which is what `test_notifications` is
for.

A tripped spam honeypot sends nothing at all. The enquiry is quarantined for
review in the dashboard, and the sender is not told they were flagged.

```bash
python manage.py test pages.tests_notifications
```
