# The QA pipeline

A staging copy of the site at `qa.csoh.org`, and a one-button promotion from
there to production. Built 2026-08-16.

```
push to qa ──► deploy-qa.yml ──► csoh-site-qa (Cloud Run) ──► qa.csoh.org
                                                                   │
                                                          you look at it
                                                                   │
                                          Actions ► Promote QA to production
                                                                   │
                                                    fast-forwards main
                                                                   │
                                  deploy.yml ──► AWS + GCP + Azure ──► csoh.org
```

## Working in it

`/Users/shawn/csoh-qa` is a git worktree permanently on `qa`; the main checkout
stays on `main`. That separation is not cosmetic - several Claude sessions share
the main checkout, and `git switch qa` there moves all of them mid-task.

```sh
cd ../csoh-qa
git fetch origin && git merge origin/main   # main moves on its own; see below
# edit, commit
git push
```

Every push to `qa` deploys. Watch **Deploy QA** in the Actions tab, then load
`qa.csoh.org`. Iterate freely; nothing here touches production.

To ship: **Actions → Promote QA to production → Run workflow**.

### Keep `qa` ahead of `main`, or promotion refuses

`main` moves without you. `site-update-deploy.yml` pushes housekeeping commits
directly to it, and `update-news.yml` merges PRs several times a day - it gained
11 commits during the afternoon this pipeline was built. Housekeeping commits
carry CI-skip markers, so they produce no workflow run at all and are easy to
miss.

`promote-qa.yml` requires `main` to be an ancestor of `qa`, because a
non-fast-forward push would silently discard those commits. When it refuses it
prints exactly which commits are missing. The fix is always to bring `main` into
`qa`, never to force the promotion.

## Why promotion ships the bytes you tested

`deploy-qa.yml` builds `csoh-site:<short-sha>` and pushes it to the **same**
Artifact Registry repo production uses, and `publish-gcp` skips the push when
the tag already exists. So when a tested commit reaches `main`, production
derives the identical tag, finds the image present, resolves it to a sha256
digest, and deploys that digest - no rebuild, no artifact-passing machinery
between the two workflows. The digest matters: the repo no longer sets
`immutable_tags`, because Artifact Registry cannot delete tagged artifacts while
it does and retention was worth more than the tag guarantee.

This only holds while the two workflows produce identical images. **Do not add
QA-only container settings.** Anything QA-specific belongs at the Cloudflare
edge, not in the image. Terraform keeps the two Cloud Run services
configuration-identical for the same reason.

## Decisions that look wrong and are not

**`deploy-qa.yml` has no `paths:` filter.** Deliberate. This repo has twice
shipped changes that never deployed because a filter was narrower than what
`stage_site.sh` publishes - `'*.html'` does not match `breaches/`, so commit
`874a813c` fixed per-breach pages and silently did not publish. A third filter
to keep in step would be a third chance to repeat that. A redundant QA deploy
costs almost nothing; a QA change that silently does not deploy costs the
confidence the environment exists to provide.

**`promote-qa.yml` depends on that.** Its second gate requires a successful
`Deploy QA` run for the exact commit being promoted, which is only reliable
because every push to `qa` produces one. Adding a paths filter to `deploy-qa.yml`
would make filtered-out commits unpromotable. The two files are coupled; both
say so.

**`cancel-in-progress: true` in QA, `false` in production.** Production cannot
be cancelled mid-flight: its publish jobs upload assets first and HTML second
across three origins, and a cancel between those passes leaves an origin serving
new CSS beside HTML naming the old hash, which SRI then blocks. None of that
exists in QA - a Cloud Run rollout is one atomic revision switch, a
half-finished push cannot corrupt a tag because a push publishes atomically, and
`qa.csoh.org` bypasses the edge cache. While iterating you want the newest push
to win.

**QA is not in the Cloudflare load balancer pool.** Pool members are
health-checked from every Cloudflare data center - roughly 1.09M probes per
origin per day, which is what produced a $119.77 Azure bandwidth bill in July
2026. A QA origin inside the pool would be probed around the clock and could
never scale to zero. It is a plain proxied DNS record plus a Worker instead.

## What exists

| Where | What |
|---|---|
| `infra/terraform/gcp/cloud_run.tf` | `csoh-site-qa` service, scales to zero |
| `infra/terraform/gcp/service_accounts.tf` | `csoh-deployer-qa`, scoped to that one service |
| `infra/terraform/gcp/wif.tf` | trust for `environment:qa`, bound to the QA deployer only |
| `infra/terraform/cloudflare/qa.tf` | DNS record, Access app + policy, the Host-rewrite Worker |
| `infra/terraform/cloudflare/rules.tf` | cache bypass for `qa.csoh.org` |
| `.github/workflows/deploy-qa.yml` | build, scan, deploy to the QA service |
| `.github/workflows/promote-qa.yml` | gated fast-forward of `main` |

The `qa` GitHub Environment is branch-restricted to `qa`, mirroring how
`production` is restricted to `main`. **A job that calls
`google-github-actions/auth` must declare `environment: qa`** or the WIF trust
rejects its token, with an error that names the token exchange rather than the
missing environment.

Cost: nothing. Cloud Run scales to zero, the image is shared with production so
registry storage does not grow, there are no health-check probes, Workers' free
tier is 100k requests/day, and Zero Trust is free to 50 users.

## Traps, all of which cost real time on 2026-08-16

**Cloudflare Free cannot rewrite the Host header.** Cloud Run picks a service by
`Host`, and this project runs two, so `qa.csoh.org` must be rewritten to the
`*.run.app` hostname or every request 404s after DNS, TLS, and the Access login
all succeed. An Origin Rule is the natural tool, but Host Header Override is a
paid-plan feature. The trap is the timing: entitlement is checked only when the
ruleset is written, so the config validates and `terraform plan` shows a clean
create right up until apply returns `not entitled to use the HostHeader
override`. **Plan success is not evidence that a Cloudflare feature is available
on your plan.** A ten-line Worker does the rewrite instead.

**The Worker route needs the trailing `/*`.** Without it only the bare hostname
matches, so the home page proxies and every asset under it 404s - presenting as
a broken stylesheet rather than a routing mistake.

**Access is account-scoped, not zone-scoped.** An app protecting one hostname
inside the zone reads like a zone object and the provider accepts `zone_id`, but
Zero Trust is account-level now and the zone Access API is legacy. A token with
the account permission gets `Authentication error (10000)` on the zone endpoint.

**One-Time PIN must be explicitly enabled.** An email allowlist is unsatisfiable
without an email login method: the Access page offers only "Cloudflare" account
sign-in, and any visitor whose Cloudflare account address is not on the list is
refused with "That account does not have access". That points at the policy,
which is correct. The tell is the login page offering exactly one method and it
not being email.

**`auto_redirect_to_identity` needs exactly one identity provider.** Enabling
OTP gave the account two, which retroactively invalidated a flag set when there
were zero - so a later update failed naming a field nobody had touched. It is
not set now.

**Dashboard edits to Access become drift that reverts.** Opening the policy by
hand to escape a lockout works, and the next `terraform apply` silently undoes
it and locks you out again - confusing precisely because the first fix appeared
to work. Change `qa.tf` as well, or instead.

**Policies created in the dashboard are "reusable" account-level objects.** They
cannot be deleted from the app's policy endpoint, and cannot be deleted at all
while attached, so they have to be detached by updating the app first. They also
collide on `precedence` with the Terraform-managed policy.

**The registry race.** `deploy-qa.yml` and `publish-gcp` build the same commit
into the same tag, so pushing a commit to `main` and `qa` at once makes them
race. Production lost once: it checked the registry (empty), spent two minutes
building and scanning, and by the time it pushed, the QA run had published the
tag. Tags were immutable then, so the push was rejected, `Deploy to Cloud Run`
was skipped, and GCP sat a commit behind AWS and Azure with `purge-cloudflare`
skipped - the split-origin state where about one request in three serves stale
content, from a workflow that looked like it had simply failed. `publish-gcp`
now re-checks immediately before pushing and treats an existing tag as success.
**Re-running the failed job is the repair**, and it takes the promotion path.

Tags are no longer immutable, so that same race now ends in a silent overwrite
rather than a rejection - the louder failure was the friendlier one. Two things
bound it: both workflows still check before pushing, and both deploy the digest
the tag resolves to rather than the tag, so whatever wins the race cannot change
the bytes a running revision was built from.

## The Cloudflare token

Ten permission groups, all **Edit**, listed in `infra/README.md`. Read them
there rather than guessing; a partly-scoped token fails only the resources it
cannot reach, so missing groups surface a couple at a time over several runs.

Decode the errors, because they do not all look like scope problems:

| Code | Meaning |
|---|---|
| `10000 Authentication error` | token cannot reach that endpoint |
| `9109 Unauthorized to access requested resource` | reaches it, but not that object |
| `1010` with an **empty message** | group present but set to Read, not Edit |
| `12130 policy precedences must be unique` | a dashboard-made policy occupies the slot |
| `11010 application_already_exists` | a dashboard-made app for the same hostname |

`1010` is the mean one: `terraform apply` prints ` (1010)` and nothing else,
because the API's `message` really is empty - the reason sits in a separate
`error` field reading `auth.forbidden` that the provider does not surface. A raw
`curl` POST is the only way to see it.

**A token that passes a GET probe is not proven able to apply.** Read access is
not evidence of Edit access. To test writes, create something disposable and
delete it.

Checking a ruleset phase is reachable:

```sh
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $CLOUDFLARE_TF_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$TF_VAR_zone_id/rulesets/phases/http_request_origin/entrypoint"
```

`403` means the group is missing. `404` means you have access and the phase is
simply empty, which is the normal state for a phase with no ruleset - **404 is a
pass, not a failure.**

## Applying the Terraform

GCP first, because its `cloud_run_qa_service_url` output is the Cloudflare
stack's `gcp_qa_origin_host`.

```sh
AWS_EC2_METADATA_DISABLED=true terraform -chdir=infra/terraform/gcp apply
terraform -chdir=infra/terraform/gcp output -raw cloud_run_qa_service_url   # strip https://
```

Then Cloudflare, **`-target`ed**. An unscoped apply also picks up a pending
`check_regions` change on the load balancer pool that is unrelated to QA, and a
rejected pool apply writes bad values into state.

```sh
set -a; . ./.env; set +a
export CLOUDFLARE_API_TOKEN="$CLOUDFLARE_TF_API_TOKEN"
terraform -chdir=infra/terraform/cloudflare apply \
  -target=cloudflare_zero_trust_access_application.qa \
  -target=cloudflare_zero_trust_access_policy.qa_allow_listed_emails
terraform -chdir=infra/terraform/cloudflare apply \
  -target=cloudflare_record.qa -target=cloudflare_workers_script.qa_host_rewrite \
  -target=cloudflare_workers_route.qa -target=cloudflare_ruleset.cache
```

**Access before the hostname, deliberately.** Terraform does not order unrelated
resources, so one apply could create the DNS record and Worker before the login
gate, publishing QA unprotected for the rest of the run. Splitting it closes
that window. Verify between the two:

```sh
curl -sS -o /dev/null -D- https://qa.csoh.org/ | grep -iE '^HTTP/|^location:'
```

Want a `302` toward `cloudflareaccess.com`.

### `.env` traps

It is **sourced, not parsed**, so a shell metacharacter anywhere breaks every
variable after it. Pasting a literal placeholder like `<host-from-step-2>` is the
easy way in: `<` and `>` are redirection operators, the file dies with `parse
error near '\n'`, and every later value - including `CLOUDFLARE_TF_API_TOKEN` -
silently reads as empty. That presents as an authentication failure several
steps from the typo. Check the file loads before blaming a credential:

```sh
set -a; . ./.env; set +a && echo "env OK"
```

`TF_VAR_qa_allowed_emails` is a list, so it needs JSON, single-quoted:

```sh
TF_VAR_qa_allowed_emails='["you@example.com"]'
```

## Verifying a QA deploy

```sh
curl -sS -o /dev/null -D- https://qa.csoh.org/ | grep -iE '^HTTP/|^location:'   # 302 to Access
gcloud run services describe csoh-site-qa --project csoh-org-495800 \
  --region us-central1 --format='value(spec.template.spec.containers[0].image)'
git rev-parse --short=12 origin/qa    # must match the image tag above
```

The origin's own `*.run.app` URL bypasses Cloudflare, which is useful for
separating "the site is broken" from "the edge is broken" - and is also why
Access is not a secrecy boundary. That hostname is publicly reachable, exactly
as production's is. Do not put anything in QA that would harm you if read early.
