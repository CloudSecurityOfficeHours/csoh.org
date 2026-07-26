# csoh.org Infrastructure - multi-cloud static hosting

csoh.org is a static site served **active/active from three cloud origins**
behind Cloudflare. Cloudflare is the single edge (TLS, caching, security
headers, legacy redirects, WAF, and a Load Balancer with health-check
failover); each cloud hosts an interchangeable copy of the site:

```
                 ┌─────────────────────────────────────────────┐
  csoh.org  ───► │  Cloudflare (Free) - proxied                 │
  www.csoh.org   │   • Universal SSL (edge TLS, Full strict)    │
                 │   • Load Balancer (active/active + health)   │
                 │   • Transform Rules  → security headers      │
                 │   • Redirect Rules   → legacy /conc8, /csoh  │
                 │   • Cache Rules      → edge + browser TTLs    │
                 │   • Free Managed Ruleset (WAF)               │
                 └──────┬───────────┬───────────┬──────────────┘
        Full (strict)   │           │           │   (each origin valid HTTPS)
                 ┌───────▼──┐   ┌────▼─────┐   ┌─▼───────────────┐
                 │ AWS      │   │ GCP      │   │ Azure           │
                 │ S3(priv) │   │ Cloud Run│   │ Blob static     │
                 │ +CloudFr.│   │ (min=0,  │   │ website ($web)  │
                 │ (OAC)    │   │  no LB)  │   │                 │
                 └──────────┘   └──────────┘   └─────────────────┘
```

**Why this shape.** The site is 100% static, so it doesn't need a server or a
cloud load balancer - object/static hosting on each provider costs pennies.
The previous single-cloud design (GCP Cloud Run behind a Global HTTPS Load
Balancer + Cloud Armor + Cloud CDN) duplicated the edge that Cloudflare
already provides, for ~$100/mo. Spreading across three origins is *cheaper*
and turns the deploy into a working multi-cloud + keyless-OIDC lesson - see
[cloud-deployment.html](https://csoh.org/cloud-deployment.html).

Each origin must expose **HTTPS with a valid cert** so the Cloudflare→origin
leg runs at **Full (strict)**:
- **AWS** - private S3 bucket reached only via **CloudFront + OAC** (the S3
  website endpoint is HTTP-only, so we don't use it).
- **GCP** - **Cloud Run** (scale-to-zero); its `*.run.app` URL is HTTPS and
  free at idle. The GCLB / Cloud Armor / Cloud CDN were retired.
- **Azure** - Storage Account **static website** (`$web`), served on its
  built-in `*.web.core.windows.net` HTTPS endpoint.

## File layout

```
infra/
  README.md                   this file - architecture, cost, cutover runbook
  MANUAL_SECURITY_STEPS.md    steps needing a dashboard or registrar login, so
                              they cannot be committed and CI cannot run them
  AWS_IDENTITY_MIGRATION.md   root-account -> Identity Center migration runbook
  terraform/
    aws/          S3 (private) + CloudFront/OAC + response-headers policy + OIDC role
    azure/        Storage account + $web static website + Entra federated cred
    gcp/          Cloud Run + Artifact Registry + WIF (LB/Armor/CDN removed)
    cloudflare/   Load Balancer + pool/monitor + header/redirect/cache rules,
                  plus the DNS security records:
                    dns_caa.tf     CAA - which CAs may issue for this domain
                    dns_dnssec.tf  DNSSEC signing (carries prevent_destroy)
                    dns_mail.tf    DMARC, MTA-STS, TLS-RPT
```

The `dns_*.tf` files are why the Cloudflare stack matters even though this site
sends no mail: DNS is the layer every other control rests on, and CAA and DMARC
are themselves just DNS records - forge the answer and you strip both. See
[SECURITY.md -> DNS & Email Security](../SECURITY.md#dns--email-security) for
what each record buys and how to verify the chain end to end.

All four states live in the same GCS bucket (`csoh-org-495800-tfstate`) under
separate prefixes (`csoh/aws`, `csoh/azure`, `csoh/prod`, `csoh/cloudflare`).
One secured state store; storage cost is pennies. The trade-off is that
Terraform needs GCS application-default credentials present when running any
of the dirs.

## Build & publish

`tools/stage_site.sh` produces `dist/` - the exact public file set (its rsync
filter, `tools/site-publish.filter`, mirrors nginx.conf's block rules and the
Dockerfile strip list, so all three origins serve byte-identical content).
`.github/workflows/deploy.yml` builds once, then fans out:

```
build (search index + stage dist/) ─┬─► publish-aws    (s3 sync + CF invalidate) ─┐
                                    ├─► publish-azure  (blob sync to $web)        ├─► purge-cloudflare
                                    └─► publish-gcp    (container + Trivy + Run)  ┘
```

Each publish job uploads **assets first, HTML second**. A single-pass sync can
land `index.html` (asking for `/style.css?v=NEW`) before `style.css` itself; any
request in that window makes Cloudflare cache the OLD bytes under the NEW `?v=`
key, and since assets are served `immutable, max-age=31536000` that wrong answer
sticks for a year while SRI blocks the file and the site renders unstyled. That
happened on 2026-07-15. The final `purge-cloudflare` job runs only after all
three origins are current, purges the edge, then re-derives every versioned
asset's SHA-384 from what the edge actually serves and fails the deploy on a
mismatch.

Every cloud authenticates with **keyless OIDC** - no long-lived cloud secrets
in the repo. Non-secret resource IDs are read from **repo Variables**
(Settings → Secrets and variables → Actions → Variables), populated from the
Terraform outputs below:

| Repo Variable | Source (`terraform -chdir=infra/terraform/<dir> output -raw …`) |
|---|---|
| `AWS_PUBLISHER_ROLE_ARN` | `aws  publisher_role_arn` |
| `AWS_BUCKET_NAME` | `aws  bucket_name` |
| `AWS_CLOUDFRONT_DISTRIBUTION_ID` | `aws  cloudfront_distribution_id` |
| `AZURE_CLIENT_ID` | `azure github_client_id` |
| `AZURE_STORAGE_ACCOUNT` | `azure storage_account_name` |
| `CLOUDFLARE_ZONE_ID` | Cloudflare dashboard → Overview (an identifier, not a secret) |

One **Secret** is also required: `CLOUDFLARE_API_TOKEN`, used only by the
`purge-cloudflare` job. Cloudflare has no OIDC federation, so this is the one
stored credential in the deploy path. Create it as a Custom token with the
single permission **Zone → Cache Purge**, Zone Resources limited to `csoh.org`,
and nothing else. If either the secret or the variable is missing the deploy
fails by design - publishing to the origins while silently leaving a stale edge
is exactly the failure that job exists to stop.

### There are TWO Cloudflare tokens, and they are not interchangeable

The cache-purge token above is deliberately useless for anything else. Running
`terraform apply` against `infra/terraform/cloudflare/` needs a **second, broader
token**, and this is not written down anywhere else - the local `.env` holds only
the narrow CI one, so reaching for it produces a pile of
`Authentication error (10000)` and `Unauthorized to access requested resource
(9109)` failures that look like a broken config rather than a scope problem.

Cloudflare gates each *ruleset phase* behind its own permission group, and this
stack spans three phases plus DNS, load balancing, and zone settings. Miss one
group and only the resources it covers fail, so the missing permissions surface
a couple at a time across several runs. The complete set:

| Scope | Permission | Needed for |
|---|---|---|
| **Account** → Load Balancing: Monitors and Pools | Edit | `cloudflare_load_balancer_pool`, `cloudflare_load_balancer_monitor` (both account-scoped) |
| **Zone** → Zone | Read | reading the zone at all |
| **Zone** → Zone Settings | Edit | `cloudflare_zone_settings_override` (zone.tf: TLS mode, min version, HSTS-adjacent dials) |
| **Zone** → DNS | Edit | `cloudflare_record.www` |
| **Zone** → Load Balancers | Edit | `cloudflare_load_balancer` (zone-scoped) |
| **Zone** → Cache Rules | Edit | the `http_request_cache_settings` ruleset |
| **Zone** → Dynamic Redirect | Edit | the `http_request_dynamic_redirect` ruleset (www -> apex, legacy paths) |
| **Zone** → Transform Rules | Edit | the `http_response_headers_transform` ruleset (the security headers) |

Set Zone Resources to `csoh.org` only. Keep this token **separate** from the
cache-purge secret and out of CI: the deploy path should never hold a credential
that can rewrite the security headers. Do not fall back to the Global API Key -
it authenticates as the whole account and sidesteps every one of these limits.

The five required `-var` values are not secrets, but they are tedious to
re-derive (see the apply command in the bootstrap section below). Keeping them
as `TF_VAR_account_id`, `TF_VAR_zone_id`, `TF_VAR_aws_origin_host`,
`TF_VAR_gcp_origin_host` and `TF_VAR_azure_origin_host` in the gitignored `.env`
lets Terraform pick them up with no flags at all.

The AWS account ID, Azure subscription ID, and Azure tenant ID are fixed
accounts hardcoded in the Terraform (`infra/terraform/aws`, `.../azure`) and
the deploy workflow - they're identifiers, not secrets, so they're committed
rather than configured as Variables.

## OIDC trust: all three clouds pin the same subject

Keyless is not the same as scoped. What each cloud *trusts* is a claim inside
the GitHub OIDC token, and the design rule is that all three pin the identical
subject:

```
repo:CloudSecurityOfficeHours/csoh.org:environment:production
```

| Cloud | Where | How it's expressed |
|---|---|---|
| AWS | `aws/oidc.tf` | `StringEquals` on `token.actions.githubusercontent.com:sub` |
| Azure | `azure/identity.tf` | `subject = "repo:.../csoh.org:environment:production"` |
| GCP | `gcp/wif.tf` | `attribute_condition` on `assertion.sub` + a `principal://` IAM member |

**GCP used to be the outlier.** Its `attribute_condition` gated only on
`assertion.repository`, and the IAM member was
`principalSet://.../attribute.repository/<owner>/<repo>`. Together that trusted
*every* workflow in the repo, on any branch, in any (or no) environment, to
impersonate `csoh-deployer` (`roles/run.admin` + `roles/artifactregistry.writer`).
That includes scheduled jobs that read untrusted web pages and never enter an
environment at all. `var.github_branch` was declared but referenced nowhere, so
the config read as though branch enforcement existed when it did not.

`wif.tf` now requires both claims in the `attribute_condition`, and the IAM
member is a single `principal://.../subject/repo:<owner>/<repo>:environment:production`
(valid because `google.subject` is mapped from `assertion.sub`). The condition
is the hard gate; the narrowed member is defense in depth. `variables.tf`
documents that `github_branch` is deliberately *not* referenced by the trust.

**Why pin the environment rather than the ref.** A `ref:refs/heads/main` check
only proves which branch the workflow file came from - any workflow can run on
`main`. Pinning `environment:production` proves the job declared
`environment: production` and therefore passed whatever gates that environment
carries, and the `production` environment's own deployment branch policy
(exactly one entry: `main`) enforces the branch transitively. So the
environment pin is a superset of the ref pin, not an alternative to it.

Only `deploy.yml`'s `publish-gcp` job uses GCP auth, and it declares
`environment: production`. If you add a job that needs cloud credentials, it
must declare that environment or it will be rejected at the token exchange.

**This needs a `terraform apply` in `infra/terraform/gcp/` to take effect.**

## Security headers are declared in three places

Header values now live in three files, and they must stay in step:

| File | Applies to | Notes |
|---|---|---|
| `infra/terraform/cloudflare/rules.tf` | every response, all origins | the `csoh-security-headers` ruleset |
| `infra/terraform/aws/cloudfront.tf` | the CloudFront origin | `aws_cloudfront_response_headers_policy.security` |
| `nginx-security-headers.conf` | the GCP Cloud Run origin | baked into the container image |

**Azure has no fourth entry, and cannot.** Azure Blob static websites cannot
emit custom response headers at all, so that origin depends entirely on the
Cloudflare edge. That is a known, accepted gap - reaching the Azure origin
directly gets you the site with no CSP and no HSTS.

AWS used to have the same gap: there was no `response_headers_policy_id`
anywhere in the AWS config, so the distribution's public `*.cloudfront.net`
hostname served a fully functional copy of the site with no CSP, no HSTS, and
no `X-Frame-Options`. The new policy carries the same eight headers as the edge
ruleset - HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
and the CSP through `security_headers_config`, plus `Permissions-Policy`,
`Cross-Origin-Opener-Policy` and `Cross-Origin-Resource-Policy` through
`custom_headers_config` (those three have no first-class argument in the
resource). **This needs a `terraform apply` in `infra/terraform/aws/`.**

### The `ignore_changes` trap, and the CI gate that compensates

`cloudflare_ruleset.security_headers` carries `lifecycle { ignore_changes = [rules] }`,
a deliberate workaround for a cloudflare v4 provider bug that returns the
multi-header block in a non-deterministic order. `rules` is the *only*
meaningful attribute of a `cloudflare_ruleset`, so the workaround makes the
resource inert after creation: tighten the CSP in Git, run `terraform apply`,
get a clean plan, and ship nothing. The repo, the diff, and the reviewer all
believe the header changed.

Terraform cannot catch that, so CI asserts it from the outside instead.
`tools/check_edge_headers.py` parses the eight header name/value pairs out of
`rules.tf` and compares them against what the live site actually serves:

```bash
python3 tools/check_edge_headers.py                        # defaults to https://csoh.org/
python3 tools/check_edge_headers.py --url <origin-url>     # check one origin directly
```

It exits non-zero on any missing or drifted header, and `deploy.yml`'s
`purge-cloudflare` job runs it right after the existing SRI verification, so
**a deploy now fails on header drift** - whether the cause is a forgotten
apply, a dashboard edit, or someone using the Cloudflare API token to weaken a
header. Because `ignore_changes` is still there, fixing a reported drift means
editing the header in the Cloudflare dashboard to match the repo, or dropping
the `lifecycle` block for one apply.

Delete the checker when the cloudflare v5 provider upgrade lets
`ignore_changes` go away.

## One-time bootstrap

Each cloud needs an authenticated admin session for the first `apply`; after
that, deploys are keyless via the workflow.

```bash
# GCS state bucket (already exists; create only if rebuilding from scratch)
gcloud storage buckets create gs://csoh-org-495800-tfstate \
    --location=us-central1 --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://csoh-org-495800-tfstate --versioning
gcloud auth application-default login   # Terraform reads these for the GCS backend

# AWS  (admin creds in the environment, e.g. `aws sso login`)
terraform -chdir=infra/terraform/aws init
terraform -chdir=infra/terraform/aws apply

# Azure  (`az login`)
terraform -chdir=infra/terraform/azure init
terraform -chdir=infra/terraform/azure apply

# GCP
terraform -chdir=infra/terraform/gcp init
terraform -chdir=infra/terraform/gcp apply

# Cloudflare  (export CLOUDFLARE_API_TOKEN; pass the three origin hostnames)
terraform -chdir=infra/terraform/cloudflare init
terraform -chdir=infra/terraform/cloudflare apply \
  -var account_id=<CF_ACCOUNT_ID> \
  -var zone_id=<CF_ZONE_ID> \
  -var aws_origin_host="$(terraform -chdir=infra/terraform/aws   output -raw cloudfront_domain)" \
  -var gcp_origin_host="$(terraform  -chdir=infra/terraform/gcp   output -raw cloud_run_service_url | sed 's#https://##')" \
  -var azure_origin_host="$(terraform -chdir=infra/terraform/azure output -raw static_website_host)"
```

Then run the deploy workflow once (`gh workflow run "Deploy - build once, publish to AWS + GCP + Azure"`)
so all three origins have content before any DNS points at them.

## Pending applies - 2026-07 security remediation

Three Terraform changes are committed but **not yet live**. They are
independent of each other: each touches a different provider and a different
state prefix, so they can be applied in any order, one at a time, and a failure
in one does not block the others. All three need the usual admin session for
that cloud plus GCS application-default credentials for the state backend.

**1. GCP - narrow the WIF trust to the production environment**
(`gcp/wif.tf`, `gcp/variables.tf`; see *OIDC trust* above)

```bash
terraform -chdir=infra/terraform/gcp plan     # expect: provider + IAM member changes only
terraform -chdir=infra/terraform/gcp apply
```

Verify by running the deploy workflow and confirming `publish-gcp` still
authenticates. If it fails at the `google-github-actions/auth` step, the job
is not entering the `production` environment - fix the workflow, do not widen
the trust back to `attribute.repository`.

**2. Cloudflare - fix the `www` redirect loop** (`cloudflare/rules.tf`)

The redirect's `target_url` was
`wildcard_replace(http.request.full_uri, "https://www.*", "https://$${1}")`.
The rule expression (`http.host eq "www.csoh.org"`) matches plaintext HTTP too,
and the dynamic-redirect phase runs *before* "Always Use HTTPS". On an `http://`
request the `https://www.*` pattern did not match, `wildcard_replace` returned
its input unchanged, and Cloudflare 301'd the request to itself forever, in
cleartext - so the browser never reached a response carrying HSTS for the `www`
host. It is now `concat("https://csoh.org", http.request.uri.path)`: scheme and
host hardcoded, never derived from the request, with `preserve_query_string`
carrying the query.

```bash
terraform -chdir=infra/terraform/cloudflare apply   # plus the -var flags from bootstrap above
curl -sI http://www.csoh.org/about.html | grep -i -E 'HTTP/|location'
#   want: 301 with `location: https://csoh.org/about.html`
#   bug:  301 with `Location: http://www.csoh.org/about.html` (points at itself)
```

**3. AWS - CloudFront emits its own security headers** (`aws/cloudfront.tf`;
see *Security headers are declared in three places* above)

```bash
terraform -chdir=infra/terraform/aws apply
# then check the origin directly, bypassing the Cloudflare edge:
python3 tools/check_edge_headers.py \
  --url "https://$(terraform -chdir=infra/terraform/aws output -raw cloudfront_domain)/"
```

Before the apply that command reports the headers as missing, which is exactly
the gap being closed. Pointed at the Azure origin it will keep reporting them
missing forever - Azure Blob cannot set them, and the edge is the only thing
that adds them there.

## Cutover (safety-gated) & rollback

> **Historical.** This cutover completed in 2026 - csoh.org has served from all
> three origins behind the Cloudflare Load Balancer since then, and the GCP
> Global HTTPS LB / Cloud Armor / Cloud CDN are gone. The runbook is kept
> because it is the procedure to follow if an origin is ever re-provisioned or
> a fourth is added, and because it documents *why* the current shape exists.

This is production. Cut over in stages and keep the old GCP LB IP as a rollback
target until you're confident.

1. **Verify each origin directly** (bypass Cloudflare) - confirm 200s, headers,
   and that no sensitive files are reachable:
   ```bash
   curl -I "https://$(terraform -chdir=infra/terraform/aws   output -raw cloudfront_domain)/"
   curl -I "$(terraform   -chdir=infra/terraform/gcp   output -raw cloud_run_service_url)/"
   curl -I "$(terraform   -chdir=infra/terraform/azure output -raw static_website_endpoint)"
   # missing path -> custom 404; sensitive path -> not 200
   curl -sI ".../does-not-exist" | head -1
   curl -sI ".../.git/config"   | head -1
   ```
2. **Apply the Cloudflare LB** (origins added with health checks). Temporarily
   add the **old GCP LB IP as a 4th origin** in `cloudflare_load_balancer_pool`
   as a fallback while the new origins bake in.
3. **Flip DNS**: point `csoh.org` / `www` at the Load Balancer (the Terraform
   `cloudflare_load_balancer` + `cloudflare_record.www` do this). Keep TTLs
   low. Watch LB health and Cloudflare analytics.
4. **Verify through the edge**:
   ```bash
   curl -sI https://csoh.org/ | grep -i -E 'strict-transport|content-security|cf-cache'
   curl -sI "https://csoh.org/conc8/index.php/blog/" | grep -i -E 'location|HTTP/'   # -> 301 /news.html
   ```
5. **Retire**: once stable, remove the GCP-LB fallback origin, then
   `terraform -chdir=infra/terraform/gcp apply` (the LB/Armor/CDN resources are
   already gone from the config, so apply destroys the live ones). Remove the
   old `gcp.csoh.org` staging DNS record.

**Rollback at any step:** repoint the `csoh.org` Cloudflare records back to the
original GCP LB IP (kept until step 5). Because the GCP teardown is the *last*
step, the old path stays intact and reversible throughout.

## Common operations

```bash
# Force a full redeploy to all three clouds
gh workflow run "Deploy - build once, publish to AWS + GCP + Azure"

# Watch Cloudflare LB origin health (dashboard): Traffic → Load Balancing
# Pull one origin for testing: set enabled=false on it in the pool + apply

# Roll back a GCP Cloud Run revision
gcloud run services update-traffic csoh-site --region us-central1 \
    --to-revisions <REVISION_NAME>=100

# Purge Cloudflare cache after an out-of-band change
#   Normally unnecessary - deploy.yml's purge-cloudflare job does this on every
#   deploy. For a change made outside the pipeline:
#   Dashboard → Caching → Purge Everything (or scoped purge)

# Check what the edge is actually serving vs. what the HTML asks for
#   (the same SRI check deploy.yml runs; see CLAUDE.md for the one-liners)
curl -s https://csoh.org/ | grep -o 'style\.css?v=[0-9a-f]*'

# Check the live security headers against infra/terraform/cloudflare/rules.tf
#   Terraform cannot enforce that ruleset (ignore_changes = [rules]), so this
#   is the only thing that catches drift. deploy.yml runs it on every deploy.
python3 tools/check_edge_headers.py
python3 tools/check_edge_headers.py --url https://csoh.org/about.html
```

## Cost

| Component | Approx. monthly |
|---|---|
| Cloudflare Load Balancing add-on (Free plan + LB) | ~$5-7 |
| AWS S3 + CloudFront (free-tier egress) | ~$0-1 |
| GCP Cloud Run (scale-to-zero) + Artifact Registry | ~$0-1 |
| Azure Blob static website | ~$0-1 |
| GCS Terraform state | <$1 |
| **Total** | **~$8-12/mo** (down from ~$100) |

The bulk of the old cost was the GCP Global HTTPS Load Balancer (two
forwarding rules) + Cloud Armor - redundant with Cloudflare's edge.

## Trade-offs vs. the old GCP stack

- **WAF**: Cloud Armor's tunable OWASP CRS is replaced by Cloudflare's **Free
  Managed Ruleset** (lighter coverage) + one free rate-limit rule. To restore
  parity: Cloudflare paid WAF, or per-origin AWS WAF on CloudFront.
- **WebP content negotiation**: the `.htaccess`/nginx `Accept`-based `.jpg→.webp`
  rewrite has no static-hosting equivalent. Prefer `<picture>` / direct `.webp`
  references in HTML, or Cloudflare Polish (paid).
- **Origin-side request blocking** (deny dotfiles/`.json`/scripts) is replaced
  by **not uploading** those files - `tools/site-publish.filter` is the single
  source of truth for what's public.
