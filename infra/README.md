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
                    dns_dnssec.tf  DNSSEC signing only; delegation is not
                                   Terraform's to do - see below
                    dns_mail.tf    DMARC, MTA-STS, TLS-RPT
```

The `dns_*.tf` files are why the Cloudflare stack matters even though this site
sends no mail: DNS is the layer every other control rests on, and CAA and DMARC
are themselves just DNS records - forge the answer and you strip both. See
[SECURITY.md -> DNS & Email Security](../SECURITY.md#dns--email-security) for
what each record buys and how to verify the chain end to end.

**`dns_dnssec.tf` is only half the control, and the other half was never
Terraform's to do.** `cloudflare_zone_dnssec` signs the zone: `dig DNSKEY
csoh.org` returns a KSK and a ZSK (alg 13) and `dig +dnssec csoh.org A` returns
RRSIGs. Delegation is the separate half, done at the registry, and it is now
live too: `dig +short DS csoh.org` returns `2371 13 2 ...`, `whois csoh.org`
reports `DNSSEC: signedDelegation`, and both Google and Cloudflare DNS-over-HTTPS
answer with `AD=true`. Verified 2026-08-09.

**Do not submit a DS record.** One is already published, and submitting a second
one (or one for a key that is not the current KSK) is the DNSSEC failure that
makes a domain disappear for every validating resolver.

The reason this file used to say otherwise is worth keeping: **Cloudflare being
the registrar did not make DS submission automatic.** Believing it did left the
zone signed but undelegated for two weeks, hidden behind a check
(`dig +dnssec ... | grep flags:`) that returns no `ad` flag on some network paths
even for known-good domains. Verify with a resolver that reports validation over
HTTPS, and against a control domain, per
[SECURITY.md -> DNS & Email Security](../SECURITY.md#dns--email-security).

`prevent_destroy` on the resource is about not silently unsigning a zone the
parent is delegating to - which, now that the DS is live, would break resolution
rather than merely drop protection. Runbook:
[`MANUAL_SECURITY_STEPS.md`](MANUAL_SECURITY_STEPS.md) section 4.

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

`publish-gcp` is the only origin that ships a container, and it is the only one
with an admission control in front of it. **Binary Authorization is enforcing**
at the project level (`infra/terraform/gcp/binary_authorization.tf`): an
allowlist of `us-central1-docker.pkg.dev/csoh-org-495800/csoh-containers/**`
plus a default `ALWAYS_DENY`, opted into by both `csoh-site` and `csoh-site-qa`
with `binary_authorization { use_default = true }`. Cloud Run will not start an
image that did not come out of that repository. Three things about it are easy
to get wrong:

- **It checks provenance, not signatures.** A project has exactly one default
  policy and Cloud Run accepts only that one, so requiring an attestation would
  require it on QA too, where images are born before anything has approved them.
- **`**` is not `*`.** In an allowlist pattern `*` stops at `/`, so
  `csoh-containers/*` silently stops covering anything at a nested path. Getting
  this wrong over-denies, which surfaces as a failed deploy rather than as a
  control that quietly is not there.
- **`ignore_changes` does not apply on create.** Both services are declared with
  the `hello` placeholder image, which this policy denies, so the policy resource
  carries a `depends_on` naming both services. The same trap returns if either
  service is ever force-replaced while the policy is enforcing.

A denied deploy does not fail cleanly: the revision is created and fails,
traffic stays on the previous revision (so the site stays up), and the service
spec is still updated to the rejected image, leaving the service `Ready: False`
until the next passing deploy. `terraform apply` will not repair it either,
because `ignore_changes` covers the image. **Verify both directions** when you
touch the policy - a correctly scoped allowlist and one that denies everything
produce identical evidence if the only thing you try is a bad image.

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
| `AWS_ORIGIN_HOST` | `aws  cloudfront_domain` |
| `AZURE_ORIGIN_HOST` | `azure static_website_host` |
| `GCP_ORIGIN_HOST` | `gcp  cloud_run_service_url` (a scheme is tolerated and stripped) |

The last three are the per-origin verification targets, and they are required
even though nothing publishes through them. `deploy.yml`'s SRI and robots.txt
gates used to ask `https://csoh.org/` only, which the load balancer routes to
one origin of three, so a file missing from a single origin had roughly a
2-in-3 chance of passing. That is the `/.well-known/security.txt` failure
CLAUDE.md records. Both gates now sweep the edge plus all three origins by
name and assert they reached all four.

They are Variables rather than a runtime lookup because two of the three
deploy identities cannot look themselves up: the AWS role holds only
`cloudfront:CreateInvalidation`, and the Azure identity holds only Storage
Blob Data Contributor, a data-plane role. Widening either one to discover a
public hostname would trade a credential boundary for a lookup. An unset
Variable names itself and exits 1, so a sweep that narrows fails loudly rather
than reporting clean over fewer origins.

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
stack spans four phases plus DNS, load balancing, zone settings, and Zero Trust
Access. Miss one group and only the resources it covers fail, so the missing
permissions surface a couple at a time across several runs. The complete set:

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
| **Zone** → Origin Rules | Edit | the `http_request_origin` ruleset (rules.tf: the Host rewrite that routes qa.csoh.org to the QA Cloud Run service) |
| **Account** → Access: Apps and Policies | Edit | `cloudflare_zero_trust_access_application`, `cloudflare_zero_trust_access_policy` (qa.tf: the login in front of qa.csoh.org) |

The last two were added by the QA pipeline and each failed in the misleading way
this section warns about, so they are worth a note.

**Origin Rules.** `http_request_origin` was a phase this stack had never used,
so the token had no group covering it. Terraform reported `request is not
authorized` against the ruleset resource, with every other resource in the same
apply succeeding. Confirm the group is present before re-running an apply, which
is faster than reading a partial apply's output:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $CLOUDFLARE_TF_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$TF_VAR_zone_id/rulesets/phases/http_request_origin/entrypoint"
```

`200` means the group is there, `403` means it is not. Swap the phase name to
check any of the other three.

**Access is ACCOUNT-scoped, not zone-scoped.** An Access application protecting
one hostname inside this zone reads like a zone-scoped object, and the provider
accepts `zone_id`, but Zero Trust is an account-level product in current
Cloudflare and the zone Access API is legacy. A token holding the account group
above gets `Authentication error (10000)` on the zone endpoint - the classic
"looks like a bad credential, is actually the wrong endpoint" shape. The tell:

```bash
# succeeds                                    # fails with 10000
.../accounts/$TF_VAR_account_id/access/apps   .../zones/$TF_VAR_zone_id/access/apps
```

**Read the `error` field, not the `message` field.** Cloudflare returns three
different codes for what is ultimately the same problem, and one of them looks
nothing like a scope error:

| Code | What it actually means |
|---|---|
| `10000 Authentication error` | token cannot reach that endpoint at all |
| `9109 Unauthorized to access requested resource` | token reaches it but not that object |
| `1010` with an **empty message** | the group is present but set to Read, not Edit |

That last one cost real time here. `terraform apply` prints ` (1010)` with
nothing after it, and the API's `errors[].message` is genuinely empty - but the
response body carries a separate `error` field reading `auth.forbidden`. A raw
POST is the only way to see it, because the provider surfaces `message` only:

```sh
curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/$TF_VAR_account_id/access/apps" \
  -H "Authorization: Bearer $CLOUDFLARE_TF_API_TOKEN" -H "Content-Type: application/json" \
  --data '{"name":"probe","domain":"probe.csoh.org","type":"self_hosted"}' | python3 -m json.tool
```

So a token that passes a GET probe is **not** proven able to apply. Read access
is not evidence of Edit access, and every group in the table above needs Edit.

Set Zone Resources to `csoh.org` only. Keep this token **separate** from the
cache-purge secret and out of CI: the deploy path should never hold a credential
that can rewrite the security headers. Do not fall back to the Global API Key -
it authenticates as the whole account and sidesteps every one of these limits.

The seven required `-var` values are not secrets, but they are tedious to
re-derive (see the apply command in the bootstrap section below). Keeping them
as `TF_VAR_account_id`, `TF_VAR_zone_id`, `TF_VAR_aws_origin_host`,
`TF_VAR_gcp_origin_host`, `TF_VAR_azure_origin_host`,
`TF_VAR_gcp_qa_origin_host` and `TF_VAR_qa_allowed_emails` in the gitignored
`.env` lets Terraform pick them up with no flags at all.

Two cautions on that file, both learned the hard way. `qa_allowed_emails` is a
**list**, so its environment form has to carry JSON, and it is worth
single-quoting so the brackets are never exposed to globbing:

```sh
TF_VAR_qa_allowed_emails='["you@example.com"]'
```

And `.env` is *sourced*, not parsed, so a shell metacharacter in any value
breaks every variable after it rather than just its own line. Pasting a literal
placeholder like `<host-from-step-2>` is the easy way to do this: `<` and `>`
are redirection operators, so the file dies with `parse error near '\n'` and
every later value - including `CLOUDFLARE_TF_API_TOKEN` - silently reads as
empty. That presents as an authentication failure, several steps away from the
actual typo. Check the whole file loads before blaming a credential:

```sh
set -a; . ./.env; set +a && echo "env OK"
```

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

**Applied 2026-07-25, re-verified 2026-07-26.** The live provider carries both
halves of the condition; confirm with:

```bash
terraform -chdir=infra/terraform/gcp state show \
  google_iam_workload_identity_pool_provider.github | grep attribute_condition
terraform -chdir=infra/terraform/gcp state show \
  google_service_account_iam_member.deployer_wif_binding | grep member
```

Both must name `repo:CloudSecurityOfficeHours/csoh.org:environment:production`.
Read the live state, not the `.tf` file - the whole point of this section is
that the two can disagree.

## Security headers are declared in three places

Header values now live in three files, and they must stay in step **by hand** -
no tool compares them. Change a header in one, change it in all three:

| File | Applies to | Checked by CI? |
|---|---|---|
| `infra/terraform/cloudflare/rules.tf` | every response, all origins (the `csoh-security-headers` ruleset) | yes - `check_edge_headers.py` asserts the live edge against this file |
| `infra/terraform/aws/cloudfront.tf` | the CloudFront origin (`aws_cloudfront_response_headers_policy.security`) | no |
| `nginx-security-headers.conf` | the GCP Cloud Run origin, baked into the container image | no |

The CI column is the part that surprises people: the gate reads `rules.tf` as
its expected values and the **edge** as its actual values. The other two files
are neither the source nor the target of any assertion, so a header tightened in
`rules.tf` alone will pass CI while both origins still serve the old value to
anyone who reaches their public hostnames directly.

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
resource). **Applied 2026-07-25, re-verified 2026-07-26** - a request straight to
the distribution's `*.cloudfront.net` hostname now returns all eight:

```bash
python3 tools/check_edge_headers.py --samples 1 \
  --url "https://$(terraform -chdir=infra/terraform/aws output -raw cloudfront_domain)/"
```

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
python3 tools/check_edge_headers.py                              # 40 samples of https://csoh.org/
python3 tools/check_edge_headers.py --url <origin-url> --samples 1   # one origin directly
```

**Why it samples.** The apex is a load balancer over three origins, and two of
them (AWS via the CloudFront policy, GCP via `nginx-security-headers.conf`) now
set these headers themselves. A response from either looks correct even if the
Cloudflare ruleset were deleted outright, so only an Azure-served response
actually tests the thing this script exists to test. One request gives you no
say in which origin answers. It therefore makes 40 cache-busted requests by
default - each with a unique query string, because a cached response would just
re-confirm whichever origin replied first - prints the origin mix it saw, and
warns if it never reached Azure. The default is measured, not guessed: on
2026-07-26 two consecutive 25-sample runs reached Azure zero times, while five
consecutive 40-sample runs all reached it. Pass `--samples 1` when checking a
single origin hostname.

**Scope: this checks the edge, and only the edge.** Neither
`aws/cloudfront.tf`'s policy nor `nginx-security-headers.conf` is asserted by CI
against anything, and the script never compares the three files to each other.
Keeping them in step is manual (see the table above); check an origin by hand
after editing its headers.

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

## The 2026-07 security-remediation applies - done

Three Terraform changes landed in the repo on 2026-07-25. **All three were
applied that day and re-verified against production on 2026-07-26**; nothing
here is outstanding work. They were independent of each other - each touches a
different provider and a different state prefix - so they went in one at a time,
and each needed the usual admin session for that cloud plus GCS
application-default credentials for the state backend.

| Stack | Change | Live check |
|---|---|---|
| `gcp/` | WIF trust narrowed to `environment:production` | `attribute_condition` and the IAM member both pin the subject |
| `cloudflare/` | `www` redirect no longer derived from the request | `http://www.csoh.org/about.html` → `https://csoh.org/about.html` |
| `aws/` | CloudFront response-headers policy | all 8 headers present on `*.cloudfront.net` |

Kept below because the *verification* is the reusable part: each entry says what
to run and what a regression would look like. The blow-by-blow of the applies
themselves, including the local toolchain traps that ate an afternoon, is
[`MANUAL_SECURITY_STEPS.md`](MANUAL_SECURITY_STEPS.md) section 1.

**1. GCP - narrow the WIF trust to the production environment**
(`gcp/wif.tf`, `gcp/variables.tf`; see *OIDC trust* above)

```bash
terraform -chdir=infra/terraform/gcp state show \
  google_iam_workload_identity_pool_provider.github | grep attribute_condition
# want: assertion.repository == '...' && assertion.sub == 'repo:...:environment:production'
```

The end-to-end check is the deploy workflow: if `publish-gcp` fails at the
`google-github-actions/auth` step, the job is not entering the `production`
environment - fix the workflow, do not widen the trust back to
`attribute.repository`.

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
curl -sI http://www.csoh.org/about.html | grep -i -E 'HTTP/|^location'
#   want: 301 with `location: https://csoh.org/about.html`   <- what it returns now
#   bug:  301 with `Location: http://www.csoh.org/about.html` (points at itself)
```

Test it over **plaintext `http://`**, not `https://`. The `https://` case worked
throughout; the loop only ever existed on the scheme the redirect derived its
target from. A future edit to `cloudflare/rules.tf` that reintroduces
`wildcard_replace` on `full_uri` would look fine over HTTPS and be broken again.

**3. AWS - CloudFront emits its own security headers** (`aws/cloudfront.tf`;
see *Security headers are declared in three places* above)

```bash
# check the origin directly, bypassing the Cloudflare edge:
python3 tools/check_edge_headers.py --samples 1 \
  --url "https://$(terraform -chdir=infra/terraform/aws output -raw cloudfront_domain)/"
```

`--samples 1` because a single origin hostname has nothing to sample - the
multi-request default exists for the apex, which load-balances. Before the apply
this reported the headers as missing, which is exactly the gap that was closed.
Pointed at the Azure origin it will keep reporting them missing forever - Azure
Blob cannot set them, and the edge is the only thing that adds them there.

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
#   Defaults to 40 cache-busted samples of the apex, because only the Azure
#   origin depends on the edge ruleset and one request may never reach it.
#   Read the "origins reached:" line - a run that never saw Azure proved little.
python3 tools/check_edge_headers.py
python3 tools/check_edge_headers.py --url https://csoh.org/about.html

# Same check against one origin (nothing to sample - it is not load-balanced)
python3 tools/check_edge_headers.py --samples 1 \
  --url "https://$(terraform -chdir=infra/terraform/aws output -raw cloudfront_domain)/"
```

## Cost

These are **billing-API figures, not estimates.** The table this replaced read
"~$8-12/mo total" with Azure and Cloud Run at "~$0-1" each. Every one of those
was a guess that nobody had checked against a bill, and they were wrong by one
to two orders of magnitude. Keep the `Source` column, and keep the word
`measured` honest: an estimate in this table is a to-do, not a rounding.

| Component | Per month | Source |
|---|---|---|
| GCP Cloud Run (production origin) | $47.64 | measured |
| Azure Blob static website | $20.06 | measured |
| GCP Artifact Registry | $19.60 | measured, and rising |
| Cloudflare Load Balancing add-on (Free plan + LB) | $10.00 | billed |
| AWS S3 + CloudFront | $0.00 | measured - $28.33 of usage, exactly offset by credits |
| Terraform state (GCS) + GCP logging | $0.00 | measured - inside the free tier |
| Staging origin (qa.csoh.org): Cloud Run, Worker, Access | $0.00 | measured |
| **Total** | **~$97/mo** | ~$126 when the AWS credits lapse |

**Almost none of that is traffic.** The top three lines are dominated by the
load-balancer health probe, which runs from every Cloudflare data center rather
than once per interval: ~1.02M probes per origin per day at `interval = 60`.
Cloud Run booked 25.6M requests and 1.18M CPU-seconds over 25 days against three
cents of minimum-instance CPU, meaning it genuinely scales to zero and simply
never gets the chance; Azure bills the same probes as read operations, and its
bill is essentially all transactions with no meaningful storage line. Artifact
Registry is the only line with a slope, growing ~2.4 GB/day because its DELETE
policy targets a state the repository can never enter.

Two fixes for this are **committed and not yet applied** (`73f884db`,
2026-08-25): `interval = 300`, worth ~$50/month across Cloud Run and Azure at
the cost of failover detection going from 180s to 900s worst case; and a
tagged-image retention rule, worth ~$13/month, whose first apply deletes 726
images (~145 GB) irreversibly. Until `terraform apply` runs, the table above is
still what you are paying. Re-measure rather than editing these numbers by hand
- CLAUDE.md carries the Cost Management API call for Azure, and note that
`az consumption usage list` returns rows with every cost field null.

The bulk of the *old* cost, before the Cloudflare cutover, was the GCP Global
HTTPS Load Balancer (two forwarding rules) + Cloud Armor - redundant with
Cloudflare's edge. That saving was real; it is the ~$100/mo this stack replaced,
not evidence that the current stack is cheap.

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
