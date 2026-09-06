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

## Every email the site sends

| # | Trigger | Where it fires | To | Message |
|---|---|---|---|---|
| 1 | Contact form submitted | `pages.views.contact` → `notifications.enquiry_received` | Staff with `pages.view_enquiry` + office inbox | `New enquiry: {name}` |
| 2 | Contact form submitted | same | The sender | "We've received your message" |
| 3 | Job application submitted | `pages.views._application_page` → `notifications.application_received` | Staff with `pages.view_application` + office inbox | `Job application: {role}` (résumé not attached) |
| 4 | Job application submitted | same | The applicant | "We've received your application for {role}" |
| 5 | Consultation requested | `pages.views.consultation` → `consultation_mail.acknowledge` | The participant | "We've received your consultation request ({ref})" |
| 6 | Consultation requested | `pages.views.consultation` → `notifications.consultation_requested` | Staff with `pages.view_consultation` + office inbox | `Consultation request: {name} ({ref})` |
| 7 | Staff confirm a time in the dashboard, with "send confirmation" ticked | `dashboard.careers_views` → `consultation_mail.confirm` | The participant | "Your consultation is confirmed - {day}" |
| 8 | Staff use "Forgot password" | `dashboard.views.DashboardPasswordResetView` | The staff account's address | Django's reset link, from `templates/dashboard/auth/password_reset_email.txt` |
| 9 | `manage.py test_notifications --send` | the management command | The address given | A sample confirmation and a sample notification |

A contact form that trips the spam honeypot sends nothing (the enquiry is
quarantined in the dashboard instead). `ADMIN_NOTIFICATION_EMAILS` is copied on
1, 3 and 6. With `EMAIL_REDIRECT_TO` set, all nine go there instead.

Messages 1-7 are logged and swallowed on failure so a mail outage never shows
the visitor an error page; 7 additionally tells the staff member to phone the
participant. Message 8 is Django's own view and raises on failure.

---

## Making mail actually deliver

The default backend prints to the terminal and sends nothing, which keeps the
forms working before any credentials exist. Production sends through **Amazon
SES**; any SMTP server also works.

### Amazon SES

The app talks to the SES API directly with boto3
([config/ses_backend.py](../config/ses_backend.py)), using the same IAM key
pair it already has for S3. No SMTP credentials, no extra secret. One line in
`.env`:

```ini
EMAIL_BACKEND=config.ses_backend.SESEmailBackend
DEFAULT_FROM_EMAIL=no-reply@rightwaysupportservices.com.au
```

On the AWS side, in the **same region as the buckets** (`ap-southeast-2` unless
`AWS_SES_REGION_NAME` says otherwise — SES identities are regional, and the
wrong region fails with "Email address is not verified" even though it is):

1. **Verify the domain.** SES → Identities → Create identity → Domain →
   `rightwaysupportservices.com.au`. Leave **Easy DKIM** on and add the three
   CNAME records it gives you to DNS. Verifying the whole domain covers
   `no-reply@`, the office address, and anything else `@` it.
2. **Set a custom MAIL FROM domain** on that identity, e.g.
   `mail.rightwaysupportservices.com.au`, and add its MX and TXT records. This is
   what makes SPF align, which Gmail and Outlook now require for delivery to the
   inbox rather than spam.
3. **Add a DMARC record** at `_dmarc.rightwaysupportservices.com.au`:
   `v=DMARC1; p=none; rua=mailto:arshdeep@rightwaysupportservices.com.au`.
   Tighten `p=` to `quarantine` once the reports show only legitimate mail.
4. **Request production access.** A new SES account is in the *sandbox*: it can
   only send to addresses you have verified individually, and 200 a day. Every
   confirmation to a member of the public will be refused until this is lifted.
   SES → Account dashboard → Request production access. Say it is transactional
   mail (enquiry confirmations, booking confirmations, password resets) for a
   single business website with no marketing list.
5. **Give the IAM user permission.** `scripts/aws/iam-policy.json` now includes
   `ses:SendEmail`. Re-running `scripts/aws/create-buckets.sh` re-applies it, or
   by hand:

   ```bash
   aws iam put-user-policy --user-name rightway-app \
     --policy-name rightway-s3 --policy-document file://scripts/aws/iam-policy.json
   ```

Then check it from a machine with the production `.env`:

```bash
python manage.py test_notifications --send you@example.com
```

`Configuration` at the top of that output shows the SES region and which key is
in use. A refusal is logged with SES's own reason — the usual ones are the
sandbox (recipient not verified), the region, and the IAM policy not yet
re-applied.

Optional settings, all in `.env.example`: `AWS_SES_REGION_NAME`,
`AWS_SES_ACCESS_KEY_ID` / `AWS_SES_SECRET_ACCESS_KEY` if mail should use a
different identity from the buckets, and `AWS_SES_CONFIGURATION_SET` to attach a
configuration set for bounce and complaint events.

**Bounces and complaints matter to SES.** It suspends accounts whose bounce rate
passes 5% or complaint rate passes 0.1%. This site only sends to addresses
people typed into a form moments earlier, so the natural rate is low, but keep
an eye on the SES reputation dashboard after go-live.

### Any SMTP server

```ini
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-username
EMAIL_HOST_PASSWORD=your-password
DEFAULT_FROM_EMAIL=no-reply@rightwaysupportservices.com.au
```

Use a transactional provider — Postmark, SendGrid, Mailgun, or SES's own SMTP
endpoint. Consumer Gmail rate-limits and will eventually block this.

**Set up SPF and DKIM for the domain** whichever route you take. Mail claiming
to be from `rightwaysupportservices.com.au` without them lands in spam or is
rejected outright, and confirmations that silently fail are worse than none —
the sender assumes their enquiry never arrived.

---

## How it fits together

| File | What it does |
|---|---|
| [pages/notifications.py](../pages/notifications.py) | Recipients, notifications, confirmations |
| [pages/consultation_mail.py](../pages/consultation_mail.py) | The consultation acknowledgement and "time confirmed" message |
| [config/ses_backend.py](../config/ses_backend.py) | Amazon SES transport |
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
python manage.py test pages.tests_notifications config.tests_ses_backend
```
