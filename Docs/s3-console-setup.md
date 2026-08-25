# Creating the buckets by hand

The click-by-click version of [`scripts/aws/create-buckets.sh`](../scripts/aws/create-buckets.sh).
Same result, and worth doing this way once if you want to see what each setting
actually is.

Roughly 20 minutes. You need to be signed in as root, or as a user with
administrator access - a narrowly-scoped user cannot create buckets or IAM
users. The `ashesh-admin` identity on this account cannot do it.

AWS moves labels around between redesigns. Where the wording here does not match
what you see, the setting is almost always in the same place under a slightly
different name.

---

## Before you start: set the region

Top right of the console, next to your account name. Choose
**Asia Pacific (Sydney) ap-southeast-2**.

Do this first and check it on every screen. **This account defaults to
ap-south-1 (Mumbai)**, and a bucket cannot be moved between regions afterwards -
the only fix is to create a new one and copy everything across.

Sydney because it is closest to the people using the site, and because
applicants' resumes are personal information that is better kept onshore.

---

## 1. The media bucket

This one holds service images, team photos, the logo and the favicon. Everyone
reads it, on every page view.

**S3 → Buckets → Create bucket**

| Setting | Value |
|---|---|
| Bucket type | General purpose |
| Bucket name | `rightway-media` |
| AWS Region | Asia Pacific (Sydney) ap-southeast-2 |
| Object Ownership | **ACLs disabled (recommended)** |

Leave "Copy settings from existing bucket" alone.

### Block Public Access

This is the one screen worth slowing down for. **Untick "Block all public
access"**, then set the four boxes underneath individually:

| Box | Set to |
|---|---|
| Block public access granted through *new* ACLs | ✅ ticked |
| Block public access granted through *any* ACLs | ✅ ticked |
| Block public access granted through *new* public bucket or access point policies | ⬜ unticked |
| Block public and cross-account access through *any* public bucket policies | ⬜ unticked |

Then tick the acknowledgement box that appears.

The two ACL boxes stay ticked because ACLs are the old, per-object way of making
things public and this project never uses them. The two policy boxes come off
because a bucket policy is how the images get served - and that policy, added in
step 3, only opens the `media/` prefix.

### The rest

| Setting | Value |
|---|---|
| Bucket Versioning | **Disable** |
| Default encryption | Server-side encryption with Amazon S3 managed keys (SSE-S3) |
| Object Lock | Disable |

Versioning off matters for cost: with it on, every replaced image is kept and
billed indefinitely. SSE-S3 rather than the KMS option because it is free and
still counts as encrypted at rest - KMS bills monthly for the key plus a charge
on every request.

**Create bucket.**

---

## 2. The private bucket

This one holds resumes. Nothing about it is public, ever.

**Create bucket** again, with the same region and encryption settings, and these
differences:

| Setting | Value |
|---|---|
| Bucket name | `rightway-private` |
| Block Public Access | **Leave "Block all public access" ticked** - all four boxes |
| Bucket Versioning | Disable |
| Default encryption | SSE-S3 |

No bucket policy is ever added to this one. The app reaches it with IAM
credentials and hands out short-lived signed URLs, one download at a time, after
checking that the staff member has `pages.view_application`.

---

## 3. The media bucket policy

**S3 → rightway-media → Permissions → Bucket policy → Edit**

Paste this and save:

    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "PublicReadUploadedImages",
          "Effect": "Allow",
          "Principal": "*",
          "Action": "s3:GetObject",
          "Resource": "arn:aws:s3:::rightway-media/media/*"
        }
      ]
    }

Note the `/media/*` on the end. That is the prefix the app writes under, so the
policy grants read on uploaded images and on nothing else - not on the bucket
listing, and not on anything that gets put there later outside that prefix.

The bucket will now show a red **Publicly accessible** badge in the console.
That is expected and correct for this bucket. If `rightway-private` ever shows
it, something is wrong - go back to step 2.

---

## 4. Lifecycle rule on the media bucket

**S3 → rightway-media → Management → Lifecycle rules → Create lifecycle rule**

| Field | Value |
|---|---|
| Rule name | `abort-incomplete-uploads` |
| Rule scope | Apply to **all objects** in the bucket (tick the acknowledgement) |
| Action | Delete expired object delete markers or incomplete multipart uploads |
| ↳ | Tick **Delete incomplete multipart uploads**, set **7** days |

That is the only rule this bucket gets. Its objects are small and read
constantly, so they stay in Standard - moving them to a colder class would cost
more, not less.

The rule matters more than it looks. An upload that dies part-way leaves parts
behind which are billed as storage and **do not show up in the object list**, so
without this they accumulate invisibly. It is the classic surprise on an S3
bill.

---

## 5. Lifecycle rules on the private bucket

Three rules on `rightway-private`. Create them one at a time.

### 5a. Same cleanup as above

| Field | Value |
|---|---|
| Rule name | `abort-incomplete-uploads` |
| Rule scope | All objects (tick the acknowledgement) |
| Action | Delete incomplete multipart uploads, **7** days |

### 5b. Cool resumes once the role is filled

| Field | Value |
|---|---|
| Rule name | `cool-resumes-after-the-role-is-filled` |
| Rule scope | Limit the scope using filters |
| ↳ Prefix | `resumes/` |
| ↳ Object size | **Specify minimum object size**: `131072` bytes |
| Action | Move current versions of objects between storage classes |
| ↳ | **Standard-IA**, after **30** days |

The size filter is the part people leave out. Standard-IA bills a **minimum of
128 KB per object**, so moving a 40 KB text resume into it costs *more* than
leaving it alone. 131072 bytes is that 128 KB threshold, so only objects big
enough to actually benefit are moved.

### 5c. Delete after 12 months

| Field | Value |
|---|---|
| Rule name | `delete-resumes-after-12-months` |
| Rule scope | Limit the scope using filters |
| ↳ Prefix | `resumes/` |
| Action | Expire current versions of objects |
| ↳ | After **365** days |

Australian Privacy Principle 11.2 requires destroying personal information once
it is no longer needed for what it was collected for, and 12 months is a
defensible reading of that for unsuccessful applicants.

**S3 deletes the file; the application record stays.** A record older than a
year will still list a resume, and the download will 404. That is deliberate -
the hiring history stays readable - but tell whoever handles applications, or it
will look like a bug.

---

## 6. The IAM user

The app needs credentials. Railway has no instance roles, so it is a key pair.

**IAM → Users → Create user**

| Field | Value |
|---|---|
| User name | `rightway-app` |
| Provide user access to the console | **Leave unticked** |

Next, on the permissions screen choose **Attach policies directly**, then
**Create policy** (it opens a new tab). In that tab switch to the **JSON** tab
and replace what is there with:

    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "ListOnlyTheseTwoBuckets",
          "Effect": "Allow",
          "Action": "s3:ListBucket",
          "Resource": [
            "arn:aws:s3:::rightway-media",
            "arn:aws:s3:::rightway-private"
          ]
        },
        {
          "Sid": "ReadWriteObjects",
          "Effect": "Allow",
          "Action": [
            "s3:GetObject",
            "s3:PutObject",
            "s3:DeleteObject"
          ],
          "Resource": [
            "arn:aws:s3:::rightway-media/*",
            "arn:aws:s3:::rightway-private/*"
          ]
        }
      ]
    }

Name it `rightway-s3` and create it. Back on the first tab, refresh the policy
list, tick `rightway-s3`, and finish creating the user.

Read, write and delete on those two buckets and nothing else. No `s3:*`, no
ability to change a bucket policy, no access to anything else in the account. If
these credentials ever leak, that is the whole blast radius.

---

## 7. The access key

**IAM → Users → rightway-app → Security credentials → Access keys → Create
access key**

Pick **Application running outside AWS**. Skip the description tag. Create.

Copy both values now, or download the `.csv`. **The secret is shown once and
cannot be retrieved afterwards** - if you lose it, delete the key and make a new
one.

---

## 8. Point the app at it

`.env` locally, and the hosting panel for production:

    USE_S3=True
    AWS_STORAGE_BUCKET_NAME=rightway-media
    AWS_PRIVATE_STORAGE_BUCKET_NAME=rightway-private
    AWS_S3_REGION_NAME=ap-southeast-2
    AWS_ACCESS_KEY_ID=AKIA...
    AWS_SECRET_ACCESS_KEY=...

`SERVE_MEDIA` turns itself off when `USE_S3` is on, so it does not need setting.

Never commit `.env`. It is gitignored, and it should stay that way.

---

## 9. Check it before moving any files

    python manage.py check

That fails loudly if a variable is missing, rather than quietly falling back to
the filesystem.

Then confirm the credentials actually reach the buckets. The dry run asks S3
whether each file is already there, so it exercises the real credentials against
both buckets without writing anything:

    USE_S3=True python manage.py sync_media_to_s3 --dry-run

A clean listing means everything is wired up. If not:

| Error | Cause |
|---|---|
| `InvalidAccessKeyId` / `SignatureDoesNotMatch` | Key pair wrong or partly copied |
| `AccessDenied` | The `rightway-s3` policy did not attach to the user |
| `NoSuchBucket` / `404` | Bucket name or region wrong - check step 0 |
| `USE_S3 is off...` | The variable did not reach the process |

---

## 10. Move the existing files

Order matters. Shrinking first means the oversized originals never reach the
bucket at all - on this project's media directory that is 18 MB against 565 KB.

    python manage.py optimize_images --dry-run
    python manage.py optimize_images

    USE_S3=True python manage.py sync_media_to_s3 --dry-run
    USE_S3=True python manage.py sync_media_to_s3

Run these against the database the files belong to. For production that means a
shell on the host with the volume mounted, not your own machine.

Back up `media/` and `private-media/` first - on a volume they are the only copy.

---

## Afterwards

Open the site. A service image's URL should read
`rightway-media.s3.ap-southeast-2.amazonaws.com/media/services/...`. If it says
`s3.amazonaws.com` with no region in it, something has dropped the addressing
style setting and every request is paying a redirect.

Open an application in the dashboard and download the resume. You should be
redirected to a long signed URL, and the file should save under the applicant's
name rather than as `resume.pdf`.

Then leave the Railway volume attached for a fortnight before detaching it.

[s3-storage.md](s3-storage.md) has the cost reasoning, the CloudFront upgrade,
and what to check when something looks wrong.
