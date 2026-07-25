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
infra/terraform/
  aws/          S3 (private) + CloudFront/OAC + GitHub OIDC role
  azure/        Storage account + $web static website + Entra federated cred
  gcp/          Cloud Run + Artifact Registry + WIF (LB/Armor/CDN removed)
  cloudflare/   Load Balancer + pool/monitor + header/redirect/cache rules
```

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

The AWS account ID, Azure subscription ID, and Azure tenant ID are fixed
accounts hardcoded in the Terraform (`infra/terraform/aws`, `.../azure`) and
the deploy workflow - they're identifiers, not secrets, so they're committed
rather than configured as Variables.

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
