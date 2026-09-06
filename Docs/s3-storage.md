# Uploads on S3

Set `USE_S3=True` and uploaded files go to Amazon S3 instead of the local disk.
Everything else - the dashboard, the forms, the permission checks - is
unchanged. This document covers the AWS side, the cutover, and the handful of
settings that are the difference between a bill of a few cents and a bill of a
few dollars.

With `USE_S3` off, which is the default, none of this applies: uploads go to
`MEDIA_ROOT` and `PRIVATE_MEDIA_ROOT` exactly as before, which is what local
development and the test suite want.

---

## Two buckets, never one

| | `rightway-media` | `rightway-private` |
|---|---|---|
| Holds | Service images, team photos, logo, favicon | Applicants' resumes |
| Read by | Everyone, on every page view | Staff with `pages.view_application` |
| URLs | Unsigned and permanent | Signed and expiring, minted per download |
| In front of it | Optionally CloudFront | Nothing, ever |
| Storage class | Standard, always | Standard, cooling with age |

Resumes are personal information. Everything in the media bucket is
world-readable by design, so keeping the two apart means no single edit to a
bucket policy can ever confuse one for the other. Buckets are free; this
separation costs nothing.

The app enforces the same split independently: `STORAGES["private"]` is a
separate backend pointed at a separate bucket, and
`dashboard.careers_views.application_resume` is still the only code path that
can produce a URL for a resume.

---

## What actually drives the bill

Storage is not the expensive part. For this site it is fractions of a cent a
month either way. Two things matter, in this order:

**1. How many bytes leave the bucket.** Egress is roughly four times the price
of storage per GB, and it is paid again on every page view. This is why
`pages.imaging` shrinks uploads before they are ever stored: the service photos
that shipped with this project were 2.2 MB PNGs, and at around 90 KB of WebP
each the same traffic moves 25x fewer bytes. That saving is larger than
anything else in this document.

**2. Whether those bytes get cached.** Images are written with
`Cache-Control: public, max-age=31536000, immutable` and served from unsigned,
permanent URLs, so a browser or a CDN can hold onto them indefinitely. Signing
image URLs would put an expiring query string on every `<img src>`, defeat every
cache in between, and turn each page view back into a billed request. The app
deliberately does not do that.

The rest is guardrails against charges that are easy to accrue without noticing:

- **Abort incomplete multipart uploads after 7 days.** An upload that dies
  part-way leaves parts behind that are billed as storage and do not appear in
  the console's object list. This is the classic invisible S3 charge.
- **Versioning stays off.** With it on, every replaced file is kept and paid for
  indefinitely. If you do want it, pair it with a rule that expires noncurrent
  versions, or the bucket only ever grows.
- **Encryption is SSE-S3, not SSE-KMS.** SSE-S3 is free and satisfies
  "encrypted at rest". KMS bills for the key every month plus a charge per
  request.
- **Resume transitions are gated on object size.** Standard-IA and Glacier bill
  a minimum of 128 KB per object, so moving a 20 KB text resume into them costs
  *more* than leaving it in Standard. The lifecycle rules use
  `ObjectSizeGreaterThan: 131072` so only objects big enough to benefit move.

Expect well under a dollar a month at this site's scale, and effectively zero
while the AWS free tier's monthly egress allowance covers it. Prices move;
check the current ones for your region rather than trusting a number here.

---

## Setting up AWS

[`scripts/aws/create-buckets.sh`](../scripts/aws/create-buckets.sh) does all of
this in one go and prints the environment variables at the end:

    AWS_PROFILE=admin ./scripts/aws/create-buckets.sh

It needs an identity that can create buckets and IAM users, which a
narrowly-scoped user cannot do - use an admin profile for setup, and never from
the app. It is safe to re-run; each step skips whatever already exists.

To do it through the console instead, one screen at a time, follow
[s3-console-setup.md](s3-console-setup.md).

The rest of this section is what that script does, for when you would rather do
it by hand or need to change one piece. The JSON is in
[`scripts/aws/`](../scripts/aws/); replace the bucket names if yours differ -
they appear inside the policy files too, and the script substitutes them for you.

### 1. Buckets

    REGION=ap-southeast-2

    for BUCKET in rightway-media rightway-private; do
      aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
        --create-bucket-configuration LocationConstraint="$REGION"

      aws s3api put-bucket-encryption --bucket "$BUCKET" \
        --server-side-encryption-configuration \
        '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
    done

Sydney because it is closest to the people using the site, and because
applicants' personal information is better kept onshore.

Leave versioning off. It is off for a new bucket unless you turn it on.

### 2. Block public access

The private bucket is locked down completely and stays that way:

    aws s3api put-public-access-block --bucket rightway-private \
      --public-access-block-configuration \
      BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

The media bucket depends on how you serve it. Serving straight from S3 needs
public bucket policies allowed:

    aws s3api put-public-access-block --bucket rightway-media \
      --public-access-block-configuration \
      BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false

    aws s3api put-bucket-policy --bucket rightway-media \
      --policy file://scripts/aws/bucket-policy-media-public.json

That policy grants read on `media/*` only - the prefix the app writes under -
rather than on the whole bucket.

If you put CloudFront in front instead (see below), all four block settings stay
`true` and the bucket policy names the distribution rather than `*`. That is
both cheaper and tighter, so it is worth doing once there is real traffic.

### 3. Lifecycle rules

    aws s3api put-bucket-lifecycle-configuration --bucket rightway-media \
      --lifecycle-configuration file://scripts/aws/lifecycle-media.json

    aws s3api put-bucket-lifecycle-configuration --bucket rightway-private \
      --lifecycle-configuration file://scripts/aws/lifecycle-private.json

The media bucket only gets the incomplete-upload cleanup. Its objects are small
and read constantly, so they stay in Standard - moving them anywhere else would
cost more, not less.

The private bucket also cools resumes as they age - Standard for the first 30
days while the role is being filled, then Standard-IA - and deletes them at 12
months.

Be clear-eyed about the scale here: at 500 resumes a year the entire archive
costs about four cents a year, and the transition rule saves well under one of
them. It is there because it scales correctly if the volume ever grows, not
because it changes this year's bill. Glacier was deliberately left out for the
same reason in reverse: at a 12-month retention it would save a fraction of a
cent per resume while adding a per-GB retrieval charge every time someone opens
an older one.

### 4. An IAM user for the app

Railway has no instance roles, so the app authenticates with a key pair. The
policy grants read, write and delete on those two buckets, plus `ses:SendEmail`
so the same user can send mail (see [email.md](email.md)) - and nothing else. No
`s3:*`, and no ability to change a bucket policy.

    aws iam create-user --user-name rightway-app
    aws iam put-user-policy --user-name rightway-app \
      --policy-name rightway-s3 --policy-document file://scripts/aws/iam-policy.json
    aws iam create-access-key --user-name rightway-app

Keep the secret from that last command; it is not shown again.

---

## Settings

See `.env.example` for the full annotated list. The minimum:

    USE_S3=True
    AWS_STORAGE_BUCKET_NAME=rightway-media
    AWS_PRIVATE_STORAGE_BUCKET_NAME=rightway-private
    AWS_S3_REGION_NAME=ap-southeast-2
    AWS_ACCESS_KEY_ID=...
    AWS_SECRET_ACCESS_KEY=...

`SERVE_MEDIA` turns itself off when `USE_S3` is on - there is nothing left for
Django to serve - so it does not need setting.

Static files stay where they are. WhiteNoise already serves them from the app
process under hashed, far-future-cacheable names, so moving them into a bucket
would add cost and a deploy step to buy nothing.

---

## The cutover

Do this from wherever the files currently are - your own machine, or a shell on
the box with the volume mounted.

**1. Back up first.** `media/` and `private-media/` are the only copies.

    cp -r media private-media /somewhere/safe/

**2. Shrink the images.** Before uploading, so the oversized originals never
reach the bucket at all.

    python manage.py optimize_images --dry-run
    python manage.py optimize_images

This rewrites each image and repoints its database row, so run it against the
same database those files belong to. It is safe to re-run: anything already
optimised is left alone.

**3. Upload.**

    USE_S3=True python manage.py sync_media_to_s3 --dry-run
    USE_S3=True python manage.py sync_media_to_s3

Object keys are the paths already in the database, so nothing in the database
changes. An interrupted run can simply be repeated - objects already in the
bucket are skipped.

**4. Turn it on.** Set the variables above in the hosting panel and redeploy.

**5. Check.** Open the site and confirm a service image loads from the bucket -
its URL will be the S3 or CloudFront domain, not your own. Then open an
application in the dashboard and download the resume.

**6. Remove the volume.** Once you are confident, a week or two later. That also
lifts the single-replica limit, since a Railway volume cannot be shared between
instances.

---

## Resume retention is 12 months

`lifecycle-private.json` deletes anything under `resumes/` after 365 days.

Australian Privacy Principle 11.2 requires destroying personal information once
it is no longer needed for the purpose it was collected for, and 12 months is a
defensible reading of that for unsuccessful applicants. It is a compliance
decision that happens to also be a cost one.

**S3 deletes the object; the `Application` row stays.** A record older than a
year will still list a resume, and the download will 404. That is by design -
the application history stays readable - but staff should know to expect it.

To change the period, edit `"Days"` and re-apply. To stop deleting altogether,
set that rule's `"Status"` to `"Disabled"`.

---

## Adding CloudFront later

Worth doing when the site has real traffic, for three reasons: transfer from S3
into CloudFront is free and CloudFront has a large permanently free monthly
allowance, so egress effectively stops being billed; a warm cache means the
origin is barely read at all; and the bucket can go back to blocking all public
access, reachable only by the distribution.

Create the distribution with the media bucket as origin and an Origin Access
Control, let it rewrite the bucket policy, re-enable all four public-access
blocks, then set:

    AWS_S3_CUSTOM_DOMAIN=d111111abcdef8.cloudfront.net

**Use Price Class All.** Price Class 100 and 200 both exclude Australia and New
Zealand, so choosing one to "save money" would serve your visitors from the
other side of the world - and under the free allowance it saves nothing anyway.

The private bucket is never given a distribution. `STORAGES["private"]` sets
`custom_domain: None` explicitly, so even a misconfiguration elsewhere cannot
route a resume through a public CDN.

---

## If something looks wrong

**Images 404, or download instead of displaying.** Check the object's
Content-Type in the console. It is recorded when the object is written, and only
a re-upload changes it. `PagesConfig.ready` registers `image/webp` for exactly
this reason - Python does not know that extension on every host, and an
unrecognised one is stored as `binary/octet-stream`.

**Every image URL has a long query string.** `querystring_auth` has been turned
on for the media bucket. Turn it off: signed image URLs are uncacheable and cost
money on every view.

**Resume downloads 404 for staff who should have access.** The permission check
runs first and returns 403, not 404, so a 404 means the object is genuinely
missing from the bucket - usually a row that predates the sync.

**URLs read `bucket.s3.amazonaws.com` rather than
`bucket.s3.ap-southeast-2.amazonaws.com`.** The `addressing_style` option has
been lost. The global endpoint answers with a redirect to the regional one, so
every request pays an extra round trip.

**Going back to the filesystem.** Set `USE_S3=False`. The files stay in the
bucket and the database still holds the same relative paths, so copying the
buckets back down into `MEDIA_ROOT` and `PRIVATE_MEDIA_ROOT` restores the
previous arrangement exactly.
