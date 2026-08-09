# Manual security steps - things the repo cannot do for itself

Companion to the 2026-07-25 security remediation. Everything in this file needs a
credential, a dashboard, or a registrar login, so it cannot be committed and CI cannot
apply it. The sections are ordered by real risk reduction, not by effort.

> ## Status as of 2026-08-09: nothing here is outstanding
>
> | Section | State |
> |---|---|
> | 1. Three Terraform applies | done 2026-07-25 |
> | 2. DMARC enforcement | done 2026-07-25, now `p=quarantine` |
> | 3. CAA records | done 2026-07-25, eleven live and imported into state |
> | 4. DNSSEC | done. Zone signed AND delegated; DS 2371 live at `.org`, both Google and Cloudflare DoH report `AD=true` |
> | 5. Cloudflare managed robots.txt | done 2026-07-26, injection disabled and CI now gates on parity |
> | 6. MTA-STS and TLS-RPT | done 2026-07-26, live in `mode: testing` |
> | 7. Origin exposure | a standing decision, not a task |
>
> Two follow-ups remain scheduled rather than outstanding, and both are gated on reading
> reports first rather than on a date: DMARC `p=reject` (2b) and MTA-STS `mode: enforce`
> (6, after a clean seven-day TLS-RPT window). Both windows have now passed, so they are
> ready to action once the reports look clean.

The sections that are done are kept as the record of what was changed and how each was
checked, because that is the part that decays. Re-run the verification commands rather than
trusting this file: several of these fail silently if a record is malformed, and a runbook
is only as true as its last check.

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
| **AWS** (1c) | done | `check_edge_headers.py --url https://<dist>.cloudfront.net/ --samples 1` returns all 8 matching |

The AWS stack used to carry a caveat here: it never planned clean, because one inert
argument kept three resources permanently in the diff. That argument has since been
removed (`288fcec3`) and all four stacks now plan clean. See 1c for what it was and why it
mattered.

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

The diff was exactly two attributes: `attribute_condition` on
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

### 1b. Cloudflare - fix the www redirect loop (DONE 2026-07-25)

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

**Verified 2026-07-25, re-checked 2026-07-26.** Before the fix this returned
`Location: http://www.csoh.org/about.html`, a loop back to the URL just requested:

```bash
curl -sI http://www.csoh.org/about.html | grep -i '^location:'
```

It now returns `Location: https://csoh.org/about.html`. Anything still starting `http://`
means the rule has been reverted or overridden at the edge.

### 1c. AWS - give the CloudFront origin its own security headers (DONE 2026-07-25)

```bash
terraform -chdir=infra/terraform/aws apply
```

The apply reported **1 to add, 3 to change, 0 to destroy**. Two of those changes were the
intended ones; the other two were not drift, and that is worth knowing before reading a
diff like it again:

- `aws_cloudfront_response_headers_policy.security` - created (intended)
- `aws_cloudfront_distribution.site` - attaches the policy (intended)
- `aws_iam_role_policy.publisher` and `aws_s3_bucket_policy.site` - both showed as updating
  with their `policy` "known after apply", and **zero concretely changed fields**. Their
  `aws_iam_policy_document` data sources reference the distribution, so Terraform defers
  re-rendering them whenever the distribution changes. They come back identical. Confirm
  with `terraform show -json <plan>` if you want to check rather than trust.

The plan also showed `viewer_certificate.minimum_protocol_version` moving from `TLSv1` to
`TLSv1.2_2021`, and that change never stuck. With `cloudfront_default_certificate = true`,
CloudFront pins the viewer protocol to `TLSv1` and ignores the argument. It was never a TLS
weakness: Cloudflare terminates the TLS that visitors actually negotiate, and this
distribution is only ever reached by Cloudflare. Do not "fix" it by requesting an ACM
certificate for a hostname nothing uses.

**That argument is also why this stack used to plan dirty forever, and it has since been
removed.** For a while after the apply the plan sat permanently at `0 to add, 3 to change`,
all three tracing back to it: the distribution carried a `viewer_certificate` diff that
could not converge, and the two policy resources then deferred because their
`aws_iam_policy_document` data sources depend on the distribution.

That mattered more than it looked. A stack that always reports changes trains whoever runs
it to skim the diff, which is precisely how genuine drift goes unnoticed - the same failure
shape as the Cloudflare `ignore_changes` trap, arrived at from the other direction. Commit
`288fcec3` deleted the argument, letting the provider fall back to its own `TLSv1` default,
which is what CloudFront enforces anyway; the plan now returns "No changes" and all four
stacks plan clean. `infra/terraform/aws/cloudfront.tf` keeps the full reasoning in a comment
where the argument used to be, including the one condition that would make it load-bearing:
if this distribution ever moves to an ACM certificate on a real hostname, add
`minimum_protocol_version = "TLSv1.2_2021"` back in the same change.

CloudFront distribution updates take a few minutes to propagate.

**Verified 2026-07-25** against the distribution hostname directly (get it from
`terraform -chdir=infra/terraform/aws output cloudfront_domain`), and again after the
`minimum_protocol_version` removal:

```bash
python3 tools/check_edge_headers.py --url https://<dist>.cloudfront.net/ --samples 1
```

returned `OK: all 8 headers match the repo across 1 request(s) to
https://<dist>.cloudfront.net/.` and, above it, `origins reached: aws=1`. Re-confirmed
2026-07-26. Pass `--samples 1` when pointing at a
single origin: the default is 40 cache-busted requests, which only earns its cost against
the apex, where there are three origins to land on.

> **What CI does and does not check.** The `purge-cloudflare` job runs
> `check_edge_headers.py` against `https://csoh.org/` only, so it asserts the *edge*
> ruleset. It does not read `aws_cloudfront_response_headers_policy.security` or
> `nginx-security-headers.conf`, so those two copies of the header values are kept in step
> with the edge by hand. Change one, change all three.
>
> Against the apex the checker samples 40 requests precisely because only Azure-served
> responses actually exercise the Cloudflare ruleset (AWS and GCP now set the headers
> themselves), and Cloudflare's steering arrives in bursts rather than evenly. It prints
> which origins it reached and warns when Azure never came up, because a pass that never
> reached Azure did not test the thing it claims to.
>
> The Azure origin cannot pass the check on its own hostname, and that is expected and
> unavoidable: Azure Blob static websites cannot emit custom response headers at all, so
> Azure depends entirely on the edge. See step 7 if you want to close that gap.

---

## 2. DMARC - move off `p=none` (DONE 2026-07-25)

**Current state**, verified 2026-07-26 with `dig +short TXT _dmarc.csoh.org` and
`dig +short TXT csoh.org`:

```
_dmarc.csoh.org   "v=DMARC1; p=quarantine; sp=quarantine; pct=100; rua=mailto:325e7f2d0aeb4bf097745889b5b2dd23@dmarc-reports.cloudflare.net"
csoh.org          "v=spf1 include:_spf.google.com ~all"
```

Exactly one `_dmarc` TXT record is returned, which is the thing to check (see the import
note below for why two would be worse than none).

The record it replaced was `v=DMARC1; p=none; rua=...`. SPF and DKIM were both published
correctly, and then `p=none` told every receiving mail server to deliver failures anyway.
Anyone could send mail as `admin@csoh.org` and have it land in inboxes. That address is the
RFC 9116 contact in `/.well-known/security.txt`, so a forged "send the PoC here instead"
reply to a vulnerability reporter was entirely plausible, and the site publishes a mailing
list to a large practitioner audience.

### Who actually sends as csoh.org

**Two** DKIM selectors are published, not one:

```bash
dig +short TXT google._domainkey.csoh.org    # Google Workspace
dig +short TXT default._domainkey.csoh.org   # a second sender, signs as csoh.org
```

That second selector matters, and an earlier draft of this file got it wrong by claiming
no such record existed. DMARC passes if **either** SPF or DKIM aligns and passes - not
both. So a sender that signs with a valid DKIM signature for `csoh.org` survives
enforcement even though the SPF record lists only Google. That is what made the move to
quarantine low-risk here rather than a gamble on the newsletter.

Read the aggregate reports before going further to `reject` (Cloudflare dashboard →
**Email Security → DMARC Management**). They are the only source that shows what is
*actually* sending and whether it authenticates; everything above is inference from DNS.

### 2a. Move to quarantine (DONE 2026-07-25)

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

> #### The import that made this safe, and the rule it leaves behind
>
> The `_dmarc` record already existed in Cloudflare, created through the dashboard.
> Terraform did not know that, so a plain `apply` would have **created a second one**.
> Cloudflare will happily hold two TXT records at the same name, and a domain publishing
> two DMARC records is treated by every receiver as publishing **none at all** - RFC 7489
> says to ignore the domain's policy entirely rather than guess. That would have been
> strictly worse than `p=none`, with no error anywhere and a plan that looked like it
> worked.
>
> It was imported first, on 2026-07-25, so it never happened. The step was: resolve the
> existing record's ID (needs the Terraform token from
> [README.md](README.md#there-are-two-cloudflare-tokens-and-they-are-not-interchangeable),
> which has DNS Edit),
>
> ```bash
> curl -s -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" "https://api.cloudflare.com/client/v4/zones/9bba25b9d72c820bda69e692e8f9a41d/dns_records?type=TXT&name=_dmarc.csoh.org" | python3 -c "import json,sys; r=json.load(sys.stdin)['result']; print(r[0]['id'] if len(r)==1 else f'EXPECTED 1 RECORD, FOUND {len(r)} - fix that first')"
> ```
>
> then import it (this needs the same `-var` values as any other command in this stack),
>
> ```bash
> terraform -chdir=infra/terraform/cloudflare import cloudflare_record.dmarc 9bba25b9d72c820bda69e692e8f9a41d/<record-id>
> ```
>
> and confirm `plan` showed **1 to change, 0 to add** before applying.
>
> **The rule generalises, and section 3 needed it too:** any record in this zone that was
> created by hand must be imported before the first `apply` that touches it, and a `plan`
> proposing *add* for something that already exists is the signal to stop.

**Verified 2026-07-26**, after the apply:

```bash
dig +short TXT _dmarc.csoh.org
```

returns exactly one line, containing `p=quarantine`. Two lines would mean an import was
skipped and DMARC is switched off entirely - delete the duplicate in the dashboard
immediately.

### 2b. After a clean reporting period (2 to 4 weeks), move to reject - NOT YET DONE

This is the one part of section 2 still outstanding, and deliberately so: quarantine has
only been live since 2026-07-25, so the earliest sensible date is around 2026-08-08. Change
`p` and `sp` to `reject` in `dns_mail.tf` and apply. The record is Terraform-managed and in
state now, so this is a one-line diff and a normal review, with no import step.

**SPF is a separate decision, not part of this step.** The apex is
`v=spf1 include:_spf.google.com ~all`, and tightening `~all` to `-all` carries a different
risk than the DMARC change: the second DKIM signer is not in the SPF record, and some
receivers weight an SPF hard fail on its own, independently of DMARC. Identify that sender
from the aggregate reports first. If it is the Kit newsletter sending as `@csoh.org`, the
right fix is to add its SPF include, not to leave `~all` in place forever.

---

## 3. CAA records - constrain who may issue certificates for csoh.org (DONE 2026-07-25)

**DONE 2026-07-25**, via the Cloudflare dashboard's "add recommended CAA records" helper
rather than Terraform. Before that there was no CAA record at all, meaning every publicly
trusted CA - roughly fifty - could issue for this domain. HSTS preload does not help:
a preloaded domain still trusts any publicly trusted chain.

Eleven records are now live, Cloudflare's full supported-CA set:

| Tag | Values |
| --- | --- |
| `issue` | comodoca.com, digicert.com, letsencrypt.org, pki.goog, ssl.com |
| `issuewild` | the same five |
| `iodef` | mailto:admin@csoh.org |

That set is correct and safe. In particular `letsencrypt.org` appears under **`issuewild`**,
which is what matters: Universal SSL issues a wildcard here (`*.csoh.org`, `csoh.org`), and
once any `issuewild` record exists it governs wildcard issuance completely, with the
`issue` records no longer applying to wildcards. An `issuewild` set omitting the real
issuer would forbid the certificate the site runs on, and nothing would break until a
renewal was silently refused weeks later.

Five CAs is more permissive than a minimal pin naming only Let's Encrypt, deliberately.
Cloudflare chooses and rotates the issuing CA itself and on the Free plan there is no
setting to fix it, so a narrow pin fails at renewal time rather than at apply time. Five
instead of fifty is where nearly all the benefit is.

### Bringing them under Terraform (DONE 2026-07-25, before the DNSSEC apply)

[`terraform/cloudflare/dns_caa.tf`](terraform/cloudflare/dns_caa.tf) declares all eleven,
mirroring the live values exactly, and all eleven were imported into state on 2026-07-25.

The order was the whole point. Until they were in state, any `terraform apply` in this
stack would have created a duplicate of all eleven, and the DNSSEC change in section 4
needed an apply. That apply has since run, and `dig +short CAA csoh.org` still returns
eleven lines rather than twenty-two, which is the empirical confirmation that the imports
took.

**The general rule stands even though this instance is finished:** anything in this zone
that was created through the dashboard has to be imported before the first `apply` that
touches the stack. That applies to any CAA record added by hand from here on, and the
generator below is kept for exactly that case.

Generate the import commands (needs the Terraform token, which has DNS Read):

```bash
curl -s -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" "https://api.cloudflare.com/client/v4/zones/9bba25b9d72c820bda69e692e8f9a41d/dns_records?type=CAA&per_page=100" | python3 -c '
import json,sys
ZONE="9bba25b9d72c820bda69e692e8f9a41d"
KEYS={"comodoca.com":"comodoca","digicert.com; cansignhttpexchanges=yes":"digicert","letsencrypt.org":"letsencrypt","pki.goog; cansignhttpexchanges=yes":"pkigoog","ssl.com":"sslcom"}
d=json.load(sys.stdin)
if not d.get("success"): sys.exit("API error: %s" % d.get("errors"))
n=0
for r in d["result"]:
    tag=r["data"]["tag"]; val=str(r["data"]["value"])
    if tag=="iodef": addr="cloudflare_record.caa_iodef"
    else:
        k=KEYS.get(val)
        if not k: print("# UNMAPPED, add to locals first: %s %s" % (tag,val)); continue
        addr="cloudflare_record.caa_%s[\"%s\"]" % (tag,k)
    print("terraform -chdir=infra/terraform/cloudflare import %s%s%s %s/%s" % (chr(39),addr,chr(39),ZONE,r["id"])); n+=1
print("# %d commands (expect 11)" % n, file=sys.stderr)
'
```

Review the output, then run the commands. Afterwards `terraform plan` must show **no
changes for any `caa_` resource**, which is what it showed on 2026-07-25. If it wants to
create them, the import did not take - stop, because applying then doubles every record.

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
> The live records take the other valid approach: `issuewild` exists and lists the same
> five CAs as `issue`. Under RFC 8659, once ANY `issuewild` record is present it governs
> wildcard issuance completely and the `issue` records stop applying to wildcards - so the
> two lists must be kept identical. `dns_caa.tf` builds both from one `local`, which is
> what makes that impossible to get wrong by editing only one of them.
>
> (Having no `issuewild` at all is also valid, and then `issue` covers wildcards too. What
> is never valid here is an `issuewild` list that omits the real issuer.)

**Verified 2026-07-26:**

```bash
dig +short CAA csoh.org
```

returns eleven lines: five `issue`, five `issuewild`, one `iodef`.

**Then verify again after the next renewal.** The certificate live on 2026-07-26 is a
Let's Encrypt one issued 2026-07-01 and expiring 2026-09-29, so renewal is due around late
August. CAA is enforced at issuance, so a mistake here surfaces then, not now:

```bash
openssl s_client -connect csoh.org:443 -servername csoh.org </dev/null 2>/dev/null | openssl x509 -noout -issuer -dates
```

A `notAfter` that has moved forward means renewal succeeded under the new CAA policy. If
it has not moved as expiry approaches, suspect these records first and check the issuer
against the list above.

---

## 4. DNSSEC - sign the zone AND delegate it (DONE, verified 2026-08-09)

> ## Both halves are live
>
> Signing AND delegation are complete. Verified 2026-08-09:
>
> | Check | Result |
> |---|---|
> | `dig DNSKEY csoh.org` | 2 keys (KSK 257 + ZSK 256, alg 13) |
> | `dig csoh.org A +dnssec` | RRSIG present - the zone is signed |
> | `dig +short DS csoh.org` | `2371 13 2 17867E31182375DA5E7C315D67552D70600A7EFB2475404F2B7414B7B097F734` |
> | `whois csoh.org` | `DNSSEC: signedDelegation` |
> | DS digest vs live KSK | recomputed SHA-256 over the DNSKEY RDATA: **matches**, key tag 2371 |
> | Google DoH / Cloudflare DoH | both return `AD=true` - the chain validates |
>
> **DO NOT SUBMIT A DS RECORD.** An earlier version of this section listed that as
> "the one outstanding action in this file" and pinned a KSK to submit. It has
> since been done. Submitting again, or submitting a DS for a key that is not the
> current KSK, is the single DNSSEC failure mode that takes a domain offline for
> every validating resolver - the domain does not slow down, it vanishes. If you
> are reading this looking for something to do, there is nothing here.
>
> **Two corrections are worth keeping, because both cost real time.**
>
> First: `cloudflare_zone_dnssec` enables **signing** only. Delegation was a
> separate manual step, and an earlier draft wrongly concluded that Cloudflare
> being the registrar made it automatic. It does not.
>
> Second, and the reason this section read as unfinished for two weeks: **the
> `ad`-flag check below is unreliable on some networks.** Running
> `dig +dnssec csoh.org A @1.1.1.1 | grep 'flags:'` returns no `ad` flag from at
> least one network path here, and it does the same for KNOWN-GOOD signed domains
> (`cloudflare.com`, `internetsociety.org`) - the AD bit is being stripped in
> transit. That false negative is what produced the "delegation never happened"
> conclusion. Do not trust it. Ask a resolver that reports validation over HTTPS
> instead:
>
> ```sh
> curl -s "https://dns.google/resolve?name=csoh.org&type=A" | grep -o '"AD":[a-z]*'
> curl -s -H 'accept: application/dns-json' \
>   "https://cloudflare-dns.com/dns-query?name=csoh.org&type=A" | grep -o '"AD":[a-z]*'
> ```
>
> Both should print `"AD":true`. A control domain is the cheap way to tell a broken
> measurement from a broken zone: if `cloudflare.com` fails your check too, the
> check is wrong, not the zone.

The web surface is largely covered by HSTS preload already, so the real value is in the
records that have no transport-layer backstop: `MX` (redirect inbound mail to an attacker
MTA), the SPF/DKIM/DMARC TXT records (forge a permissive policy so a receiver validating
a spoofed message sees a pass), and any future `_acme-challenge` TXT (satisfy a CA's
DNS-01 validation and mint a certificate).

It is also what makes steps 2 and 3 mean anything. DMARC policy and CAA restrictions are
both just DNS records; an attacker who can forge a DNS answer can replace either. A CA
checks CAA over plain DNS at issuance time, so a forged answer strips the restriction.
Both are protected now that the delegation below is live: a forged answer fails validation
rather than being accepted.

### Signing and delegation are two separate things, and both are now done

DNSSEC needs both halves, from two different systems:

1. **Signing**, at the DNS provider. Cloudflare generates the keys, publishes `DNSKEY`, and
   signs every answer with an `RRSIG`. This is what `cloudflare_zone_dnssec` in
   [`terraform/cloudflare/dns_dnssec.tf`](terraform/cloudflare/dns_dnssec.tf) turns on, and
   it is done. The resource carries `prevent_destroy = true`, so a stray
   `terraform destroy` cannot silently unsign the zone.

   ```bash
   terraform -chdir=infra/terraform/cloudflare apply
   ```

2. **Delegation**, at the registry. The `DS` record - a hash of the KSK - has to be
   published in the `.org` zone by the registrar, so that a validating resolver walking
   down from the root has a reason to trust our `DNSKEY`. **This was done separately, and
   is live:** `dig +short DS csoh.org` returns DS 2371 and `whois` reports
   `DNSSEC: signedDelegation`. Without it, `DNSKEY` and `RRSIG` would be records nobody
   had been told to check.

**Cloudflare being both registrar and DNS provider does not merge those two steps.** An
earlier draft of this section assumed it did, concluded there was no registrar action at
all, and that assumption delayed the delegation. `whois csoh.org` does report
`Registrar: Cloudflare, Inc.`, and the nameservers are Cloudflare's, but the DS submission
was still a distinct action someone had to take. `terraform apply` does not do it and
waiting does not do it. It has since been done.

What owning both sides *does* remove is narrower, and worth keeping straight because it is
the reason there is no urgency to roll anything back. The classic DNSSEC outage is a
**stale DS**: the registrar publishing a DS for a key the DNS provider no longer uses, at
which point every validating resolver treats all answers as forged. The domain does not
slow down, it vanishes, and only for users behind validating resolvers, which makes it
painful to diagnose. Cloudflare managing the key material and the registrar record together
means a key rotation updates both, so that specific failure mode is off the table here. A
missing DS was the safe direction while delegation was pending; a wrong DS is the dangerous
one, and now that a DS is live that is the failure mode to protect against.

**Verify.** The `terraform output` reflects the signing half only; the `dig` and `whois`
checks are the ones that tell you whether delegation actually landed. Status as of
2026-08-09 is in the right-hand column:

```bash
terraform -chdir=infra/terraform/cloudflare output dnssec_status   # want "active"    -> active
dig +short DNSKEY csoh.org                                         # want 2 keys      -> KSK 257 + ZSK 256, alg 13
dig +short DS csoh.org                                             # want a DS record -> 2371 13 2 17867E31...B097F734
whois csoh.org | grep -i '^DNSSEC:'                                # want signed      -> DNSSEC: signedDelegation
curl -s "https://dns.google/resolve?name=csoh.org&type=A" | grep -o '"AD":[a-z]*'          # -> "AD":true
curl -s -H 'accept: application/dns-json' \
  "https://cloudflare-dns.com/dns-query?name=csoh.org&type=A" | grep -o '"AD":[a-z]*'      # -> "AD":true
```

Validation by a resolver is the check that matters: it means the signatures were verified
and they held. **Do not use `dig +dnssec csoh.org A @1.1.1.1 | grep 'flags:'` for this.**
That was the command this block used to recommend, and it returns no `ad` flag on at least
one network path here even for known-good signed zones - `cloudflare.com` and
`internetsociety.org` fail it identically, because the AD bit is stripped in transit. It
measures the path, not the zone, and reading it as a verdict is what produced the wrong
"delegation never happened" conclusion. Ask a resolver that reports its validation result
over HTTPS, use two of them, and run a control domain in the same breath: a known-good zone
that fails your check means the check is broken, not the zone. A DS present with no
validation from any resolver means signing and delegation genuinely disagree - investigate
before assuming propagation lag.

> ### If you ever transfer the domain to another registrar
>
> Disable DNSSEC **before** the transfer and re-enable it after. Otherwise the new
> registrar inherits a DS record for a key that no longer signs the zone, which is the
> stale-DS outage described above. **This is live advice now.** An earlier version of this
> box deferred it on the grounds that there was no DS to go stale; DS 2371 is published at
> `.org`, so a transfer done without this step can take the domain offline for every
> validating resolver.

---

## 5. Turn off Cloudflare's managed robots.txt injection (DONE 2026-07-26)

Cloudflare was prepending its own AI-crawler block ahead of the repo's `robots.txt`. The
served file carried a `Cloudflare Managed` section that `Disallow`ed several crawlers the
repo's own `robots.txt` and `llms.txt` explicitly allow: 2 occurrences of
`Cloudflare Managed` live, 0 in the repo file.

That was not a vulnerability, but it was the same failure class as the Terraform
`ignore_changes` trap: the edge silently overriding what is in Git, with nothing to catch
it.

**The repo's position was kept** (crawlers allowed), by disabling the managed `robots.txt`
at Cloudflare dashboard → **Security → Bots → AI Crawl Control** on 2026-07-26. The
alternative would have been to keep Cloudflare's position and delete the AI-crawler `Allow`
section from `robots.txt`, correcting the corresponding sentence in `llms.txt`; that is not
what was chosen, so `robots.txt` and `llms.txt` in the repo remain the authority.

**Verified 2026-07-26:**

```bash
python3 tools/check_robots_parity.py
```

returns `ok  99 lines match, byte-for-byte after whitespace normalization`.

That checker is now a deploy gate: the `purge-cloudflare` job in `deploy.yml` runs
`tools/check_robots_parity.py --url https://csoh.org/robots.txt` alongside
`check_edge_headers.py`, so a re-enabled injection fails the deploy instead of going
unnoticed. It has to be an outside-in check for the same reason the header checker does:
AI Crawl Control is a zone-level dashboard toggle that
`infra/terraform/cloudflare/` does not declare, so `terraform apply` would neither report
nor fix a regression.

---

## 6. MTA-STS and TLS-RPT (DONE 2026-07-26, in `mode: testing`)

Before this, neither `_mta-sts.csoh.org` nor `_smtp._tls.csoh.org` existed. SMTP between
mail servers uses opportunistic TLS, so an on-path attacker could strip `STARTTLS` and
inbound mail would be delivered in cleartext. Since `admin@csoh.org` is the published
security.txt contact, inbound vulnerability reports are exactly the mail you would least
like downgraded.

Google Workspace supports MTA-STS enforce mode. All three parts are live, managed in
[`terraform/cloudflare/dns_mail.tf`](terraform/cloudflare/dns_mail.tf) apart from the policy
file, which is checked into the repo:

1. DNS TXT at `_mta-sts.csoh.org`: `v=STSv1; id=2026072601`
2. DNS TXT at `_smtp._tls.csoh.org`: `v=TLSRPTv1; rua=mailto:admin@csoh.org`
3. `https://mta-sts.csoh.org/.well-known/mta-sts.txt`, served as `text/plain`:

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

   The hostname needs its own HTTPS endpoint, and an earlier draft here assumed that meant
   a Cloudflare Worker. It did not. `mta-sts` is a proxied CNAME onto the apex, so it is
   another name for the same load balancer, and the policy file rides the ordinary site
   deploy from `/.well-known/mta-sts.txt` across all three origins. Universal SSL is a
   wildcard (`*.csoh.org`), so the certificate was already valid for the hostname and
   nothing in `dns_caa.tf` had to change. `dns_mail.tf` records why the `www` redirect does
   not catch this hostname, which would have broken the policy fetch silently.

It starts at `mode: testing`, which reports failures via TLS-RPT and delivers anyway. The
move to `mode: enforce` is still to come: confirm the TLS-RPT reports are clean for at
least one full `max_age` window (7 days), then change the mode **and** bump the `id=` in
the same commit. `dns_mail.tf` carries the full checklist inline. Forgetting the id bump
means senders keep enforcing the cached old policy for up to a week, which looks like the
change took when it did not.

**Verified 2026-07-26:**

```bash
dig +short TXT _mta-sts.csoh.org      # "v=STSv1; id=2026072601"
dig +short TXT _smtp._tls.csoh.org    # "v=TLSRPTv1; rua=mailto:admin@csoh.org"
curl -sI https://mta-sts.csoh.org/.well-known/mta-sts.txt   # 200, content-type: text/plain, no redirect
curl -s  https://mta-sts.csoh.org/.well-known/mta-sts.txt   # the policy above, mode: testing
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

Re-run the whole set rather than trusting the statuses above. Everything here passed on
2026-07-26 except the DS record, which is section 4's outstanding action:

```bash
python3 tools/check_edge_headers.py        # OK, 8 headers; 40 samples, and it names the origins it reached
python3 tools/check_robots_parity.py       # OK, robots.txt matches the repo
dig +short TXT _dmarc.csoh.org             # ONE line, p=quarantine
dig +short CAA csoh.org                    # 11 lines
dig +short DS csoh.org                     # want DS 2371 ...
whois csoh.org | grep -i '^DNSSEC:'        # want signedDelegation
curl -s "https://dns.google/resolve?name=csoh.org&type=A" | grep -o '"AD":[a-z]*'   # want "AD":true
# NOT `dig +dnssec ... | grep flags` for the ad bit - see section 4, it false-negatives here
dig +short TXT _mta-sts.csoh.org           # v=STSv1; id=2026072601
curl -sI http://www.csoh.org/about.html | grep -i '^location:'   # https://csoh.org/about.html
curl -sI https://csoh.org/.well-known/security.txt | head -1     # HTTP/2 200
```

The first two are also CI gates in the `purge-cloudflare` job, so drift in the edge headers
or in `robots.txt` fails a deploy. Nothing in CI watches the DNS records: those are only
checked when someone runs this sweep.
