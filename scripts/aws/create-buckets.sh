#!/usr/bin/env bash
#
# Creates the two S3 buckets this project uses, locks them down, applies the
# lifecycle rules, and makes the IAM user the app authenticates as.
#
# Read it before running it. It creates billable AWS resources and prints an
# access key secret to the terminal.
#
# Needs an identity that can create buckets and IAM users. A narrowly-scoped
# user cannot do this - use an admin profile, then never use that profile again
# from the app.
#
#   AWS_PROFILE=admin ./scripts/aws/create-buckets.sh
#
# Everything is overridable:
#
#   REGION=ap-southeast-2 MEDIA_BUCKET=rightway-media \
#   PRIVATE_BUCKET=rightway-private IAM_USER=rightway-app \
#   AWS_PROFILE=admin ./scripts/aws/create-buckets.sh
#
# Safe to re-run: each step reports and skips whatever already exists.

set -euo pipefail

PROFILE="${AWS_PROFILE:-default}"
REGION="${REGION:-ap-southeast-2}"
MEDIA_BUCKET="${MEDIA_BUCKET:-rightway-media}"
PRIVATE_BUCKET="${PRIVATE_BUCKET:-rightway-private}"
IAM_USER="${IAM_USER:-rightway-app}"

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

aws_() { command aws --profile "$PROFILE" --region "$REGION" "$@"; }
say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mok\033[0m %s\n' "$*"; }
skip() { printf '  -- %s\n' "$*"; }

# --- confirm ----------------------------------------------------------------

IDENTITY="$(aws_ sts get-caller-identity --query Arn --output text)"

cat <<SUMMARY

  profile        $PROFILE
  identity       $IDENTITY
  region         $REGION
  media bucket   $MEDIA_BUCKET      (public images)
  private bucket $PRIVATE_BUCKET    (resumes - never served by URL)
  iam user       $IAM_USER

SUMMARY

if [ "${CONFIRM:-}" != "yes" ]; then
  read -r -p "Create these? [y/N] " reply
  case "$reply" in [yY]*) ;; *) echo "Nothing done."; exit 1 ;; esac
fi

# Bucket names are global across all of AWS, so a collision here is someone
# else's bucket rather than a mistake in this script.
bucket_exists() { aws_ s3api head-bucket --bucket "$1" >/dev/null 2>&1; }

make_bucket() {
  local bucket="$1"
  if bucket_exists "$bucket"; then
    skip "$bucket already exists"
  else
    aws_ s3api create-bucket --bucket "$bucket" \
      --create-bucket-configuration "LocationConstraint=$REGION" >/dev/null
    ok "created $bucket"
  fi

  # SSE-S3 rather than SSE-KMS: it satisfies "encrypted at rest" and is free,
  # where KMS bills monthly for the key plus a charge on every request.
  aws_ s3api put-bucket-encryption --bucket "$bucket" \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
  ok "$bucket encrypted with SSE-S3"
}

say "1. Buckets"
make_bucket "$MEDIA_BUCKET"
make_bucket "$PRIVATE_BUCKET"

# --- public access ----------------------------------------------------------

say "2. Public access"

# The resume bucket blocks everything, permanently. Nothing in this project
# ever needs a public URL for one - they are handed out signed and expiring.
aws_ s3api put-public-access-block --bucket "$PRIVATE_BUCKET" \
  --public-access-block-configuration \
  'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'
ok "$PRIVATE_BUCKET fully blocked"

# The media bucket is read straight from S3 for now, which needs public bucket
# policies allowed. Public ACLs stay blocked - the policy is the only way in.
# Putting CloudFront in front later lets all four of these go back to true.
aws_ s3api put-public-access-block --bucket "$MEDIA_BUCKET" \
  --public-access-block-configuration \
  'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false'
ok "$MEDIA_BUCKET allows a public read policy, blocks public ACLs"

sed "s/rightway-media/$MEDIA_BUCKET/g" \
  "$HERE/bucket-policy-media-public.json" > "$WORK/media-policy.json"
aws_ s3api put-bucket-policy --bucket "$MEDIA_BUCKET" \
  --policy "file://$WORK/media-policy.json"
ok "$MEDIA_BUCKET readable on the media/ prefix only"

# --- lifecycle --------------------------------------------------------------

say "3. Lifecycle rules"

aws_ s3api put-bucket-lifecycle-configuration --bucket "$MEDIA_BUCKET" \
  --lifecycle-configuration "file://$HERE/lifecycle-media.json"
ok "$MEDIA_BUCKET aborts incomplete uploads after 7 days"

aws_ s3api put-bucket-lifecycle-configuration --bucket "$PRIVATE_BUCKET" \
  --lifecycle-configuration "file://$HERE/lifecycle-private.json"
ok "$PRIVATE_BUCKET cools at 30 days, deletes resumes at 12 months"

# --- iam --------------------------------------------------------------------

say "4. IAM user for the app"

if aws_ iam get-user --user-name "$IAM_USER" >/dev/null 2>&1; then
  skip "$IAM_USER already exists"
else
  aws_ iam create-user --user-name "$IAM_USER" >/dev/null
  ok "created $IAM_USER"
fi

sed -e "s/rightway-media/$MEDIA_BUCKET/g" -e "s/rightway-private/$PRIVATE_BUCKET/g" \
  "$HERE/iam-policy.json" > "$WORK/iam-policy.json"
aws_ iam put-user-policy --user-name "$IAM_USER" \
  --policy-name rightway-s3 --policy-document "file://$WORK/iam-policy.json"
ok "$IAM_USER scoped to those two buckets and nothing else"

say "5. Access key"

EXISTING="$(aws_ iam list-access-keys --user-name "$IAM_USER" \
  --query 'length(AccessKeyMetadata)' --output text)"

if [ "$EXISTING" != "0" ]; then
  skip "$IAM_USER already has $EXISTING key(s); not creating another"
  skip "delete the old one first if you need a fresh pair"
  KEY_ID="(existing)"
  KEY_SECRET="(existing - not retrievable, create a new key if lost)"
else
  read -r KEY_ID KEY_SECRET <<<"$(aws_ iam create-access-key --user-name "$IAM_USER" \
    --query '[AccessKey.AccessKeyId,AccessKey.SecretAccessKey]' --output text)"
  ok "created an access key"
fi

cat <<ENV

Put these in .env locally, and in the hosting panel for production. The secret
is shown once and cannot be retrieved again.

USE_S3=True
AWS_STORAGE_BUCKET_NAME=$MEDIA_BUCKET
AWS_PRIVATE_STORAGE_BUCKET_NAME=$PRIVATE_BUCKET
AWS_S3_REGION_NAME=$REGION
AWS_ACCESS_KEY_ID=$KEY_ID
AWS_SECRET_ACCESS_KEY=$KEY_SECRET

Then move the files that are already on disk - in this order, from wherever
they actually live:

  python manage.py optimize_images --dry-run
  python manage.py optimize_images
  USE_S3=True python manage.py sync_media_to_s3 --dry-run
  USE_S3=True python manage.py sync_media_to_s3

Docs/s3-storage.md has the rest, including what to check afterwards.
ENV
