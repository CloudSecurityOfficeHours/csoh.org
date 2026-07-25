# Manual security steps - things the repo cannot do for itself

Companion to the 2026-07-25 security remediation. Everything in this file needs a
credential, a dashboard, or a registrar login, so it cannot be committed and CI cannot
apply it. Work top to bottom: the list is ordered by real risk reduction, not by effort.

Every step includes a verification command. Run it and confirm the expected output before
ticking the step off - several of these fail silently if a record is malformed.

> ## Ordering matters: apply Terraform BEFORE you push
>
> The documentation in this changeset (`how-csoh-org-is-secured.html`,
> `cloud-deployment.html`, `terraform.html`, `SECURITY.md`) describes the new posture in
> the present tense: that the AWS origin sets its own security headers, and that all three
> clouds pin the OIDC subject to the `production` environment. Both statements are true of
> the repository and **not yet true of production** until step 1 below has run.
>
> Pushing to `main` triggers a deploy, which publishes those pages. So run **step 1 first**,
> then push. Otherwise the site publishes a verifiable security claim that does not yet
> hold - on pages whose entire premise is that a reader can check them with `curl`.

---

## 1. Apply the three Terraform changes

The code changes are committed but **inert until applied**. Until you run these, the WIF
trust is still repository-scoped, the `www` redirect still loops on HTTP, and the AWS
origin still serves no security headers.

They are independent of each other and can be applied in any order.

### 1a. GCP - close the Workload Identity trust (do this one first)

This is the highest-value apply. Right now any workflow in the repo, on any branch, can
mint credentials for `csoh-deployer` (`roles/run.admin` + `roles/artifactregistry.writer`).

```bash
terraform -chdir=infra/terraform/gcp apply
```

Expect a diff on exactly two attributes: `attribute_condition` on
`google_iam_workload_identity_pool_provider.github`, and `member` on
`google_service_account_iam_member.deployer_wif_binding`.

**Verify** - the next `deploy.yml` run must still authenticate. Watch the `publish-gcp`
job's "Authenticate to Google Cloud" step. It should succeed, because that job declares
`environment: production`. If you want to confirm the gate actually bites, temporarily
add a throwaway workflow with `id-token: write` and no `environment:`, attempt the same
auth, and confirm it is now rejected. Delete it afterward.

> If a future workflow genuinely needs GCP credentials, it **must** declare
> `environment: production`. That is now a hard requirement on all three clouds, and it is
> deliberate.

### 1b. Cloudflare - fix the www redirect loop

```bash
terraform -chdir=infra/terraform/cloudflare apply
```

**Verify** (currently returns `Location: http://www.csoh.org/about.html`, a loop):

```bash
curl -sI http://www.csoh.org/about.html | grep -i '^location:'
```

Expected after apply: `location: https://csoh.org/about.html`

### 1c. AWS - give the CloudFront origin its own security headers

```bash
terraform -chdir=infra/terraform/aws apply
```

Expect a new `aws_cloudfront_response_headers_policy.security` plus an in-place update to
the distribution. CloudFront distribution updates take a few minutes to propagate.

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
