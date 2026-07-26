# Manual security steps - things the repo cannot do for itself

Companion to the 2026-07-25 security remediation. Everything in this file needs a
credential, a dashboard, or a registrar login, so it cannot be committed and CI cannot
apply it. Work top to bottom: the list is ordered by real risk reduction, not by effort.

Every step includes a verification command. Run it and confirm the expected output before
ticking the step off - several of these fail silently if a record is malformed.

> ## Lesson learned: apply Terraform BEFORE you push
>
> This did not happen in the right order on 2026-07-25, so record it for next time.
>
> The documentation in this changeset (`how-csoh-org-is-secured.html`,
> `cloud-deployment.html`, `terraform.html`, `SECURITY.md`) describes the new posture in
> the present tense: that the AWS origin sets its own security headers, and that all three
> clouds pin the OIDC subject to the `production` environment. Those became true of the
> repository the moment they were committed, and true of production only when the
> corresponding `terraform apply` ran.
>
> Pushing to `main` triggers a deploy that publishes those pages. Push first and the site
> is briefly asserting a security claim that does not yet hold, on pages whose entire
> premise is that a reader can verify them with `curl`. Apply first, then push.

---

## 1. Apply the three Terraform changes

The code changes are committed but **inert until applied**, and they are independent of
each other. Status as of 2026-07-25:

| Stack | State | Effect while un-applied |
|---|---|---|
| **GCP** (1a) | **done and verified live** | - |
| **Cloudflare** (1b) | outstanding | `www.csoh.org` still redirect-loops on plain HTTP |
| **AWS** (1c) | outstanding | the CloudFront origin still serves no security headers of its own |

#### Before you start: two local traps that waste hours

Both of these cost real time on 2026-07-25, and neither produces an error that points at
its cause.

**1. Terraform must be a native arm64 build.** Check first:

```bash
file "$(which terraform)" && terraform version
```

Both must say `arm64` / `darwin_arm64`. If Terraform is an x86_64 binary on Apple Silicon
(which is what Intel Homebrew at `/usr/local` installs, as opposed to native Homebrew at
`/opt/homebrew`), it downloads x86_64 *providers* too, and every provider then runs under
Rosetta translation. The AWS provider binary is ~725 MB, and translating it exceeds
Terraform's plugin-start handshake timeout. The symptoms are a provider process pegged at
100% CPU with **zero network connections**, and intermittent
`timeout while waiting for plugin to start` - roughly half the time, so it looks flaky
rather than broken. Only the AWS stack is really affected; the Google and Cloudflare
providers are small enough to translate in time.

The fix is a native Terraform (`terraform_<version>_darwin_arm64.zip` from
`releases.hashicorp.com`, checksum-verified) followed by `terraform init` in **all four**
stack directories, including `azure/`, which is otherwise easy to forget until
`terraform output` fails with `Required plugins are not installed`. Pin the same version
that wrote the current state; a newer Terraform can bump the state format irreversibly.

**2. Set `AWS_EC2_METADATA_DISABLED=true` in your shell profile.**

```bash
export AWS_EC2_METADATA_DISABLED=true
```

Local AWS auth here is `aws login` with a `login_session` in `~/.aws/config`, and that
session expires. When it does, the AWS provider falls through the credential chain to EC2
instance metadata, which does not exist on a laptop, and hangs for minutes before failing
with `No valid credential sources found` plus `no EC2 IMDS role found`. That message names
IMDS, not the expired session, so it sends you looking in the wrong place. With this set,
the same situation fails in about a second. Ask the CLI directly what it thinks:

```bash
aws sts get-caller-identity
```

`Your session has expired` means run `aws login`. Note also that
`aws configure export-credentials --format env` is what bridges an `aws login` session
into the environment variables the Terraform provider understands - the provider does not
implement `login_session` itself.

**A wedged run leaves a state lock behind.** If Terraform dies without releasing it,
`force-unlock` with the ID from the error is safe *only* once you have confirmed no
terraform process is alive (`ps aux | grep terraform`; a plugin whose parent is `PPID 1`
is an orphan and can be killed). Never reach for `-lock=false` - on 2026-07-25 that
started a second concurrent apply against the same state, which is exactly the corruption
the lock exists to prevent.

### 1a. GCP - close the Workload Identity trust (DONE 2026-07-25)

This was the highest-value apply: before it, any workflow in the repo, on any branch, could
mint credentials for `csoh-deployer` (`roles/run.admin` + `roles/artifactregistry.writer`).

```bash
terraform -chdir=infra/terraform/gcp apply
```

Expect a diff on exactly two attributes: `attribute_condition` on
`google_iam_workload_identity_pool_provider.github`, and `member` on
`google_service_account_iam_member.deployer_wif_binding`.

**Verified 2026-07-25**, two ways. The live config carries both claims:

```bash
gcloud iam workload-identity-pools providers describe github-provider \
  --project=csoh-org-495800 --location=global \
  --workload-identity-pool=github-pool --format="value(attributeCondition)"
```

returns

```
assertion.repository == 'CloudSecurityOfficeHours/csoh.org' && assertion.sub == 'repo:CloudSecurityOfficeHours/csoh.org:environment:production'
```

and the service-account binding is now a single `principal://.../subject/repo:...:environment:production`
rather than a `principalSet://.../attribute.repository/...` matching the whole repo:

```bash
gcloud iam service-accounts get-iam-policy \
  csoh-deployer@csoh-org-495800.iam.gserviceaccount.com --project=csoh-org-495800
```

More usefully, the deploy that ran afterward authenticated normally, so the tightened
trust is confirmed not to break the real publish path. To confirm the gate actually
*bites*, add a throwaway workflow with `id-token: write` and no `environment:`, attempt
the same auth, watch it be rejected, and delete it.

> If a future workflow genuinely needs GCP credentials, it **must** declare
> `environment: production`. That is now a hard requirement on all three clouds, and it is
> deliberate.

### 1b. Cloudflare - fix the www redirect loop

This stack needs two things that the others do not: a broader API token than the one in
`.env`, and five `-var` values.

**The token.** `.env` holds the cache-purge CI token, which cannot read the zone, the
rulesets, or the load balancer. Using it fails with `Authentication error (10000)` and
`Unauthorized to access requested resource (9109)`, which reads like a broken config but
is purely a scope problem. Cloudflare gates each ruleset phase behind its own permission
group, so a partially-scoped token fails a couple of resources at a time across several
runs. The complete eight-group set is tabulated in
[README.md](README.md#there-are-two-cloudflare-tokens-and-they-are-not-interchangeable).
Keep it separate from the CI secret.

**The variables.** They are identifiers rather than secrets, but re-deriving them means
pulling Terraform state and querying the GitHub API, so they are recorded here:

| Variable | Where it comes from |
|---|---|
| `account_id` | Cloudflare dashboard, or the `account_id` on any LB pool in this stack's state |
| `zone_id` | the `CLOUDFLARE_ZONE_ID` repo Variable |
| `aws_origin_host` | `terraform -chdir=../aws output -raw cloudfront_domain` |
| `gcp_origin_host` | `terraform -chdir=../gcp output -raw cloud_run_service_url`, scheme stripped |
| `azure_origin_host` | `terraform -chdir=../azure output -raw static_website_host` |

Put them in the gitignored `.env` as `TF_VAR_account_id` and friends and Terraform picks
them up with no flags. Otherwise pass each with `-var`, as in the bootstrap command in
[README.md](README.md).

```bash
CLOUDFLARE_API_TOKEN='<the-terraform-token>' terraform -chdir=infra/terraform/cloudflare apply
```

**Read this plan before confirming.** It touches `cloudflare_zone_settings_override`,
which carries live TLS dials (`ssl`, `min_tls_version`, `tls_1_3`). If the stack has not
been applied in a while, those may show changes that have nothing to do with the redirect.

**Verify** (before the fix this returns `Location: http://www.csoh.org/about.html`, a loop
back to the URL just requested):

```bash
curl -sI http://www.csoh.org/about.html | grep -i '^location:'
```

Expected after apply: `location: https://csoh.org/about.html`. Anything still starting
`http://` means the rule did not take.

### 1c. AWS - give the CloudFront origin its own security headers

```bash
terraform -chdir=infra/terraform/aws apply
```

Expect **1 to add, 3 to change, 0 to destroy**. Two of those changes are the intended
ones; the other two are not drift, and it is worth knowing that before you read the diff
and worry:

- `aws_cloudfront_response_headers_policy.security` - created (intended)
- `aws_cloudfront_distribution.site` - attaches the policy (intended)
- `aws_iam_role_policy.publisher` and `aws_s3_bucket_policy.site` - both show as updating
  with their `policy` "known after apply", and **zero concretely changed fields**. Their
  `aws_iam_policy_document` data sources reference the distribution, so Terraform defers
  re-rendering them whenever the distribution changes. They come back identical. Confirm
  with `terraform show -json <plan>` if you want to check rather than trust.

The plan will also show `viewer_certificate.minimum_protocol_version` moving from `TLSv1`
to `TLSv1.2_2021`. That change never sticks. With `cloudfront_default_certificate = true`,
CloudFront pins the viewer protocol to `TLSv1` and ignores the argument, so this is a
permanent no-op diff on every future plan. It is not a TLS weakness: Cloudflare terminates
the TLS that visitors actually negotiate, and this distribution is only ever reached by
Cloudflare. Do not "fix" it by requesting an ACM certificate for a hostname nothing uses.

CloudFront distribution updates take a few minutes to propagate.

**Verify** against the distribution hostname directly (get it from
`terraform -chdir=infra/terraform/aws output cloudfront_domain`):

```bash
python3 tools/check_edge_headers.py --url https://<dist>.cloudfront.net/
```

Expected: `OK: all 8 headers ... match the repo.`

> The Azure origin will still fail that check, and that is expected and unavoidable:
> Azure Blob static websites cannot emit custom response headers at all. Azure depends on
> the Cloudflare edge. See step 7 if you want to close that gap.

---

## 2. DMARC - move off `p=none` (highest-value non-Terraform step)

**Current state**, verified 2026-07-25:

```
_dmarc.csoh.org   "v=DMARC1; p=none; rua=mailto:325e7f2d0aeb4bf097745889b5b2dd23@dmarc-reports.cloudflare.net;"
csoh.org          "v=spf1 include:_spf.google.com ~all"
```

SPF and DKIM are both published correctly, and then `p=none` tells every receiving mail
server to deliver failures anyway. Anyone can send mail as `admin@csoh.org` and it lands
in inboxes. That address is the RFC 9116 contact in `/.well-known/security.txt`, so a
forged "send the PoC here instead" reply to a vulnerability reporter is entirely
plausible, and the site publishes a mailing list to a large practitioner audience.

### Before you enforce: read the reports

You already have `rua` reporting pointed at Cloudflare's aggregator. Check it and confirm
every legitimate sender is aligned before tightening. The known senders are Google
Workspace (`include:_spf.google.com`, plus the `google._domainkey` DKIM record, both
confirmed present) and the Kit newsletter.

**Kit needs a decision.** There is no Kit DKIM record and no Kit SPF include on this
domain, which strongly suggests Kit sends from its own domain with a reply-to rather than
as `@csoh.org`. If that is right, enforcement will not affect the newsletter. Confirm it
in the DMARC reports rather than assuming, and if Kit does send as `@csoh.org`, add its
SPF include and DKIM record **before** step 2b.

### 2a. Move to quarantine

In the Cloudflare dashboard: **DNS → Records**, edit the `_dmarc` TXT record to:

```
v=DMARC1; p=quarantine; sp=quarantine; pct=100; adkim=s; aspf=s; rua=mailto:325e7f2d0aeb4bf097745889b5b2dd23@dmarc-reports.cloudflare.net; ruf=mailto:admin@csoh.org; fo=1;
```

`sp=quarantine` covers subdomains, which currently inherit `p=none`. `adkim=s` / `aspf=s`
require strict alignment.

### 2b. After a clean reporting period (2 to 4 weeks), move to reject

Change `p` and `sp` to `reject` in the same record, and tighten SPF from softfail to
hardfail by editing the apex TXT record to:

```
v=spf1 include:_spf.google.com -all
```

**Verify:**

```bash
dig +short TXT _dmarc.csoh.org
dig +short TXT csoh.org | grep spf
```

---

## 3. CAA records - constrain who may issue certificates for csoh.org

There is currently **no CAA record**, so all ~50 publicly trusted CAs may issue for this
domain. CAA turns that into a two-CA surface and, with `iodef`, alerts you on attempted
mis-issuance. HSTS preload does not help here: a preloaded domain still trusts any
publicly trusted chain.

In the Cloudflare dashboard: **DNS → Records → Add record**, type **CAA**, four records
on the apex `csoh.org`:

| Tag | Value | Why |
| --- | --- | --- |
| `issue` | `letsencrypt.org` | Cloudflare Universal SSL issues from Let's Encrypt |
| `issue` | `pki.goog` | ...and from Google Trust Services |
| `issuewild` | `;` | Deny all wildcard issuance (nothing here needs one) |
| `iodef` | `mailto:admin@csoh.org` | Get notified on a violation |

> Add both `issue` values. Cloudflare rotates between these two CAs, and pinning only one
> can break certificate renewal.

**Verify:**

```bash
dig +short CAA csoh.org
```

Expected: four lines. Currently returns nothing.

---

## 4. DNSSEC - sign the zone

Currently **off** (no DS, no DNSKEY, no AD flag). Cloudflare is authoritative for this
zone, so this is close to one click plus one registrar paste.

The web surface is largely covered by HSTS preload already, so the real value is in the
records that have no transport-layer backstop: `MX` (redirect inbound mail to an attacker
MTA), the SPF/DKIM/DMARC TXT records (forge a permissive policy so a receiver validating
a spoofed message sees a pass), and any future `_acme-challenge` TXT (satisfy a CA's
DNS-01 validation and mint a certificate).

Do this **after** step 3, so the signed zone covers the new CAA records.

1. Cloudflare dashboard: **DNS → Settings → DNSSEC → Enable DNSSEC**.
2. Cloudflare shows a DS record. Copy it.
3. Log in to the registrar for `csoh.org` and paste the DS record into its DNSSEC section.
4. Wait for propagation (usually minutes, occasionally hours).

**Verify:**

```bash
dig +short DS csoh.org                          # expect a DS record
dig +dnssec csoh.org A @1.1.1.1 | grep 'flags:' # expect the "ad" flag
```

---

## 5. Turn off Cloudflare's managed robots.txt injection

Cloudflare is prepending its own AI-crawler block ahead of the repo's `robots.txt`. The
served file now contains a `Cloudflare Managed` section that `Disallow`s several crawlers
the repo's own `robots.txt` and `llms.txt` explicitly allow. Confirmed live: the served
file has 2 occurrences of `Cloudflare Managed`; the repo file has 0.

This is not a vulnerability, but it is the same failure class as the Terraform
`ignore_changes` trap: the edge silently overriding what is in Git, with nothing to catch
it.

**Decide which policy you actually want**, then make one place authoritative:

- **To keep the repo's position** (crawlers allowed): Cloudflare dashboard →
  **Security → Bots → AI Crawl Control**, disable the managed `robots.txt`.
- **To keep Cloudflare's position** (crawlers blocked): delete the AI-crawler `Allow`
  section from `robots.txt` and correct the corresponding sentence in `llms.txt`.

**Verify:**

```bash
curl -s https://csoh.org/robots.txt | grep -c 'Cloudflare Managed'   # want 0 for option A
```

Consider adding a CI assertion that the served `robots.txt` matches the repo copy
byte-for-byte, the same way `tools/check_edge_headers.py` now guards the headers.

---

## 6. MTA-STS and TLS-RPT (optional, lowest priority)

Neither `_mta-sts.csoh.org` nor `_smtp._tls.csoh.org` exists. SMTP between mail servers
uses opportunistic TLS, so an on-path attacker can strip `STARTTLS` and inbound mail is
delivered in cleartext. Since `admin@csoh.org` is the published security.txt contact,
inbound vulnerability reports are exactly the mail you would least like downgraded.

Google Workspace supports MTA-STS enforce mode. Three parts:

1. DNS TXT at `_mta-sts.csoh.org`: `v=STSv1; id=20260725000000`
2. DNS TXT at `_smtp._tls.csoh.org`: `v=TLSRPTv1; rua=mailto:admin@csoh.org`
3. Serve `https://mta-sts.csoh.org/.well-known/mta-sts.txt` as `text/plain`:

   ```
   version: STSv1
   mode: testing
   mx: aspmx.l.google.com
   mx: alt1.aspmx.l.google.com
   mx: alt2.aspmx.l.google.com
   mx: alt3.aspmx.l.google.com
   mx: alt4.aspmx.l.google.com
   max_age: 604800
   ```

   The hostname needs its own HTTPS endpoint. A small Cloudflare Worker on
   `mta-sts.csoh.org` returning that body is the least-effort option and avoids touching
   the three-origin publish path.

Start at `mode: testing`, confirm the TLS-RPT reports are clean for a week, then switch to
`mode: enforce` and bump the `id=`.

**Verify:**

```bash
dig +short TXT _mta-sts.csoh.org
curl -s https://mta-sts.csoh.org/.well-known/mta-sts.txt
```

---

## 7. Origin exposure - a decision, not a defect

Both non-GCP origin hostnames answer directly, bypassing the Cloudflare edge:

- `https://csohorgsite.z13.web.core.windows.net/` serves the whole site with **no
  security headers at all** (Azure Blob cannot set them).
- The Cloud Run URL is derivable in one guess from the Terraform this site publishes as
  teaching material, and answers directly.

Impact is genuinely low: the content is public, there are no cookies, no auth, and no user
data, and every page carries a canonical link. The concrete residual risks are that the
Azure copy is framable while the apex is `X-Frame-Options: DENY`, and that direct traffic
to Cloud Run bills you without the edge absorbing it.

Three options, in ascending order of effort:

1. **Accept and document it.** Reasonable for a public static site. This is already noted
   in `infra/README.md` and on the public deployment page.
2. **Shared-secret gate.** Have Cloudflare inject a header via a Transform Rule and have
   `nginx.conf` return 403 without it. Roughly ten lines, closes the Cloud Run bypass.
   Does not work for Azure Blob, which cannot evaluate rules.
3. **Drop the Azure origin.** Two origins already provide redundancy, and the GCP origin
   has full header parity. This removes the header-free mirror entirely.

Independently worth doing regardless of which you pick: set a **GCP billing budget alert**
on the project, so sustained direct traffic to Cloud Run is noticed.

---

## Verification sweep

After working through the above, re-run the whole set:

```bash
python3 tools/check_edge_headers.py
dig +short TXT _dmarc.csoh.org
dig +short CAA csoh.org
dig +short DS csoh.org
curl -sI http://www.csoh.org/about.html | grep -i '^location:'
curl -s https://csoh.org/robots.txt | grep -c 'Cloudflare Managed'
curl -sI https://csoh.org/.well-known/security.txt | head -1
```
