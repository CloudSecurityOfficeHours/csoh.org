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

**All three were applied and verified on 2026-07-25.** This section is kept as the record
of what was done and how each was checked, not as outstanding work.

| Stack | State | Verified by |
|---|---|---|
| **GCP** (1a) | done | `plan` clean; live `attributeCondition` pins `environment:production`; the deploy afterward still authenticated |
| **Cloudflare** (1b) | done | `curl -sI http://www.csoh.org/about.html` returns `Location: https://csoh.org/about.html` |
| **AWS** (1c) | done | `check_edge_headers.py --url https://<dist>.cloudfront.net/` returns all 8 matching |

One caveat carried forward: the AWS stack does **not** plan clean, and by design it cannot.
See 1c below - one inert argument keeps three resources permanently in the diff.

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
CloudFront pins the viewer protocol to `TLSv1` and ignores the argument. It is not a TLS
weakness: Cloudflare terminates the TLS that visitors actually negotiate, and this
distribution is only ever reached by Cloudflare. Do not "fix" it by requesting an ACM
certificate for a hostname nothing uses.

**It is, however, why this stack never plans clean.** Confirmed after the apply: the plan
is permanently `0 to add, 3 to change`, and all three trace to that one argument. The
distribution shows a `viewer_certificate` diff that cannot converge; the two policy
resources then defer because their `aws_iam_policy_document` data sources depend on the
distribution, and show `policy` as unknown-after-apply with zero concrete field changes.

That matters more than it looks. A stack that always reports changes trains whoever runs
it to skim the diff, which is precisely how genuine drift goes unnoticed - the same
failure shape as the Cloudflare `ignore_changes` trap, arrived at from the other
direction. The clean fix is to delete the `minimum_protocol_version` argument entirely:
the provider's default is `TLSv1`, which is what CloudFront enforces anyway, so the plan
converges and all three diffs disappear. Re-add it only if this distribution ever moves to
an ACM certificate on a real hostname, at which point the argument starts doing something.

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

### Who actually sends as csoh.org

**Two** DKIM selectors are published, not one:

```bash
dig +short TXT google._domainkey.csoh.org    # Google Workspace
dig +short TXT default._domainkey.csoh.org   # a second sender, signs as csoh.org
```

That second selector matters, and an earlier draft of this file got it wrong by claiming
no such record existed. DMARC passes if **either** SPF or DKIM aligns and passes - not
both. So a sender that signs with a valid DKIM signature for `csoh.org` survives
enforcement even though the SPF record lists only Google. That is what makes the move to
quarantine low-risk here rather than a gamble on the newsletter.

Still read the aggregate reports before going further (Cloudflare dashboard → **Email
Security → DMARC Management**). They are the only source that shows what is *actually*
sending and whether it authenticates; everything above is inference from DNS.

### 2a. Move to quarantine

The record is now managed in Terraform, in
[`terraform/cloudflare/dns_mail.tf`](terraform/cloudflare/dns_mail.tf), with the reasoning
for each tag inline. It sets:

```
v=DMARC1; p=quarantine; sp=quarantine; pct=100; rua=mailto:325e7f2d0aeb4bf097745889b5b2dd23@dmarc-reports.cloudflare.net
```

Deliberately *not* included, though an earlier draft of this file suggested them:
`adkim=s` / `aspf=s` (strict alignment is a separate tightening and should not ride along
with an enforcement change), and `ruf=` (forensic reports are ignored by most receivers
and can carry recipient PII).

> #### IMPORT BEFORE YOU APPLY. This one bites silently.
>
> The `_dmarc` record already exists in Cloudflare. Terraform does not know that, so a
> plain `apply` **creates a second one**. Cloudflare will happily hold two TXT records at
> the same name, and a domain publishing two DMARC records is treated by every receiver as
> publishing **none at all** - RFC 7489 says to ignore the domain's policy entirely rather
> than guess. You would end up strictly worse off than `p=none`, with no error anywhere
> and a plan that looked like it worked.
>
> Find the existing record's ID (needs the Terraform token from
> [README.md](README.md#there-are-two-cloudflare-tokens-and-they-are-not-interchangeable),
> which has DNS Edit):
>
> ```bash
> curl -s -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" "https://api.cloudflare.com/client/v4/zones/9bba25b9d72c820bda69e692e8f9a41d/dns_records?type=TXT&name=_dmarc.csoh.org" | python3 -c "import json,sys; r=json.load(sys.stdin)['result']; print(r[0]['id'] if len(r)==1 else f'EXPECTED 1 RECORD, FOUND {len(r)} - fix that first')"
> ```
>
> Then import it (this needs the same `-var` values as any other command in this stack):
>
> ```bash
> terraform -chdir=infra/terraform/cloudflare import cloudflare_record.dmarc 9bba25b9d72c820bda69e692e8f9a41d/<record-id>
> ```
>
> Now `plan` must show **1 to change, 0 to add**. If it says *add*, the import did not
> take: stop, do not apply.

Then apply, and confirm the result is a single record:

```bash
dig +short TXT _dmarc.csoh.org
```

Exactly one line, containing `p=quarantine`. Two lines means the import was skipped and
DMARC is now switched off entirely - delete the duplicate in the dashboard immediately.

### 2b. After a clean reporting period (2 to 4 weeks), move to reject

Change `p` and `sp` to `reject` in `dns_mail.tf` and apply. By then the record is
Terraform-managed, so this is a one-line diff and a normal review.

**SPF is a separate decision, not part of this step.** The apex is
`v=spf1 include:_spf.google.com ~all`, and tightening `~all` to `-all` carries a different
risk than the DMARC change: the second DKIM signer is not in the SPF record, and some
receivers weight an SPF hard fail on its own, independently of DMARC. Identify that sender
from the aggregate reports first. If it is the Kit newsletter sending as `@csoh.org`, the
right fix is to add its SPF include, not to leave `~all` in place forever.

---

## 3. CAA records - constrain who may issue certificates for csoh.org

There is currently **no CAA record**, so all ~50 publicly trusted CAs may issue for this
domain. CAA turns that into a two-CA surface and, with `iodef`, alerts you on attempted
mis-issuance. HSTS preload does not help here: a preloaded domain still trusts any
publicly trusted chain.

The records are defined in Terraform, in
[`terraform/cloudflare/dns_caa.tf`](terraform/cloudflare/dns_caa.tf), with the reasoning
inline. Four records on the apex:

| Tag | Value | Why |
| --- | --- | --- |
| `issue` | `letsencrypt.org` | issuer of the certificate currently served |
| `issue` | `pki.goog` | Google Trust Services, Cloudflare's other primary CA |
| `issue` | `ssl.com` | also in Cloudflare's rotation; headroom so a rotation cannot fail issuance |
| `iodef` | `mailto:admin@csoh.org` | be told when a CA refuses a request that violates the above |

These are new records, so unlike the DMARC change there is **nothing to import** - a plain
apply creates them.

> ### Do NOT add `issuewild ";"`
>
> An earlier draft of this file listed exactly that, on the reasoning that nothing here
> needs a wildcard. It would have broken certificate renewal and eventually taken TLS down.
>
> Cloudflare Universal SSL issues a **wildcard** certificate for this domain. Check for
> yourself:
>
> ```bash
> openssl s_client -connect csoh.org:443 -servername csoh.org </dev/null 2>/dev/null | openssl x509 -noout -text | grep -A2 "Subject Alternative Name"
> ```
>
> It returns `DNS:*.csoh.org, DNS:csoh.org`. Denying wildcard issuance forbids the very
> certificate the site runs on, and nothing breaks until a renewal is silently refused
> weeks later.
>
> Under RFC 8659, with no `issuewild` record present the `issue` records govern wildcards
> too. Omitting it is both correct and safe.

**Do not narrow the CA list to just the current issuer.** Cloudflare picks and rotates the
CA itself, and on the Free plan there is no setting to fix it (that is an Advanced
Certificate Manager feature). Pinning one CA works until the day Cloudflare renews with a
different one. Three CAs instead of ~50 is where nearly all the benefit is.

**Verify after apply:**

```bash
dig +short CAA csoh.org
```

Expected: four lines. Before the apply it returns nothing.

**Then verify again after the next renewal.** The certificate live at the time of writing
expires 2026-09-29, so renewal is due around late August. CAA is enforced at issuance, so
a mistake here surfaces then, not now:

```bash
openssl s_client -connect csoh.org:443 -servername csoh.org </dev/null 2>/dev/null | openssl x509 -noout -issuer -dates
```

A `notAfter` that has moved forward means renewal succeeded under the new CAA policy. If
it has not moved as expiry approaches, suspect these records first and check the issuer
against the list above.

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
