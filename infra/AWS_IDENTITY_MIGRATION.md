# Migrating local AWS access off the root user

Companion to [MANUAL_SECURITY_STEPS.md](MANUAL_SECURITY_STEPS.md). Everything here needs
the AWS Console, a browser, and a human. None of it can be committed, and CI cannot run
it, which is exactly why it has sat undone.

## The problem, stated plainly

`~/.aws/config` currently reads:

```ini
[default]
login_session = arn:aws:iam::038416307420:root
region = us-east-1
```

and `aws sts get-caller-identity` confirms what that means:

```json
{"UserId":"038416307420","Account":"038416307420","Arn":"arn:aws:iam::038416307420:root"}
```

Every local `terraform plan` and `terraform apply` against `infra/terraform/aws/` runs as
the **account root user**.

Three properties make the root user different in kind, not just in degree, from an
over-privileged IAM user:

1. **It cannot be scoped.** There is no policy you can attach that reduces what root may
   do. Deny statements in identity policies do not apply to it, and Service Control
   Policies in Organizations do not apply to the management account's root.
2. **It cannot be bounded.** A permissions boundary is an IAM feature; root is not an IAM
   principal in that sense, so the mechanism has nothing to attach to.
3. **Its compromise is unrecoverable from inside the account.** Root can change the
   account email and phone number, remove its own MFA, close the account, and act on
   billing. There is no higher authority in the account to undo any of that.

CIS AWS Foundations Benchmark and the AWS Well-Architected security pillar both say the
same thing: use root exactly twice, to set up an administrative identity and for the small
set of tasks that genuinely require it, then lock it away.

**The contrast worth drawing is internal to this repo.** The CI deploy path already does
the right thing. `infra/terraform/aws/oidc.tf` registers GitHub as an OIDC provider and
creates one role, `csoh-site-publisher`, whose trust policy pins the token's `sub` claim
with `StringEquals` to exactly
`repo:CloudSecurityOfficeHours/csoh.org:environment:production`, and whose permissions
policy grants exactly `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` on the one site
bucket plus `cloudfront:CreateInvalidation` on the one distribution. No static key exists,
the credential lives for minutes, and a leak would cost this site's bucket and nothing
else in the account.

So the machine that publishes the site holds a keyless, minute-lived, four-action
credential, and the laptop that changes the infrastructure holds the keys to the kingdom.
The local path is the weak link, and it is the only one left.

## What this migration does and does not change

**No Terraform in this repo changes.** Not one line, not one resource, not one state
entry. This is purely about which credential the local CLI and provider pick up. Do not
write Terraform for IAM Identity Center either, and see the warning below for why.

> ### Do not bootstrap Identity Center with Terraform
>
> It is technically possible: there are `aws_ssoadmin_*` resources. Do not.
>
> The only credential available to run that apply is the one you are trying to retire. You
> would be using root to build the identity system that replaces root, in a stack whose
> state lives in a GCS bucket, with a provider that would then need re-authenticating
> halfway through. If the apply half-succeeds (instance enabled, user created, assignment
> not yet made) you have an Identity Center you cannot log into, and the recovery path is
> the root user you were mid-way through abandoning.
>
> Identity Center is bootstrap infrastructure. Click it once in the Console, by hand, with
> your eyes on it. Then manage everything downstream of it however you like.

## 1. Pre-flight: check the root user itself

Do this first, while you still have root credentials loaded, because two of these
questions can only be answered as root and one of them may be an emergency.

```bash
aws iam get-account-summary --query 'SummaryMap.{MFA:AccountMFAEnabled,Keys:AccountAccessKeysPresent,Certs:AccountSigningCertificatesPresent}'
```

What you want to see:

| Field | Want | Meaning |
|---|---|---|
| `AccountMFAEnabled` | `1` | The root user has MFA. If this is `0`, stop and fix it now: Console, top-right account menu, Security credentials, Assign MFA device. |
| `AccountAccessKeysPresent` | `0` | There is no long-lived root access key. |
| `AccountSigningCertificatesPresent` | `0` | Legacy X.509 signing certs, essentially never wanted. |

**If `AccountAccessKeysPresent` is `1`, delete the key outright.** Do not rotate it, do not
deactivate it and leave it, delete it. A root access key is a permanent, unscoped,
unexpiring credential to the whole account sitting in a file somewhere; there is no
legitimate use for one and AWS has recommended against them for over a decade. Console:
account menu, Security credentials, Access keys, Delete. It is under "Root access keys",
distinct from the IAM users page.

Note that MFA on root does **not** protect the current local session. `login_session`
already produced credentials; MFA gates obtaining new ones. Deleting keys and enabling MFA
are necessary, not sufficient. The goal is still to stop using root.

## 2. Enable IAM Identity Center

This is Console-only, and it is the step with a decision you cannot take back.

**It needs AWS Organizations.** Identity Center's multi-account permissions (permission
sets assigned to accounts) are a feature of an *organization instance*, which requires the
account to be part of an AWS Organization. If this account is standalone, the Console will
offer to create an organization with this account as the management account, as part of
enabling Identity Center. That is fine and is the normal path for a single-account setup.
It costs nothing and adds no obligations you do not opt into.

There is also an *account instance* of Identity Center that does not require Organizations.
Do not use it here: account instances support application assignments only, not permission
sets, so it cannot give you the role this migration is about.

**The region choice is effectively permanent.** Identity Center is enabled in exactly one
region, and that region holds the identity store, the users, the groups, the permission
sets, and every assignment. Changing it means deleting the instance and rebuilding all of
that from scratch, which also invalidates every profile on every machine. Pick
**us-east-1**, matching `var.aws_region` in `infra/terraform/aws/variables.tf` and the rest
of this project, and do not think about it again.

Steps, in the Console, signed in as root:

1. IAM Identity Center console, confirm the region selector says the region you want.
2. **Enable**. If prompted, allow it to create the organization.
3. Note the **AWS access portal URL** it gives you. It looks like
   `https://d-xxxxxxxxxx.awsapps.com/start`. You need it in step 4. You can set a custom
   subdomain instead, but the `d-` URL works and is one less thing to get wrong.

## 3. Create the user, the group, and the permission set

Still in the Console. All three, in this order, because assignments are made group-to-
permission-set and you want the pieces to exist first.

**User.** Identity Center, Users, Add user. Use a real mailbox you control: the invitation
and any password reset go there, and this is now your way into the account. Turn on MFA
for this user (Identity Center, Settings, Authentication, or per-user under Multi-factor
authentication). A passkey or an authenticator app is fine. The whole point of this
exercise is defeated if the replacement identity is a password alone.

**Group.** Identity Center, Groups, Create group, e.g. `csoh-admins`. Add the user to it.

Why bother with a group for one user: permission-set assignments are the thing you will
later want to change, and changing group membership is reversible in a way that hunting
down direct user assignments is not. It costs one click now.

**Permission set.** Identity Center, Permission sets, Create.

- **Start from the AWS managed policy `AdministratorAccess`.** Being honest about why: you
  are about to run Terraform that manages IAM itself, and diagnosing a `terraform apply`
  that fails halfway through on an unexpected `AccessDenied` is far worse than starting
  broad and narrowing with evidence. Name it something that tells the truth, like
  `CSOHAdminBootstrap`.
- Set the **session duration** to `PT1H` (the default) or `PT4H` if re-login during long
  sessions annoys you. This is the lifetime of the credentials the profile hands to
  Terraform.
- Assign the permission set to the account (`038416307420`) for the group `csoh-admins`.

**`AdministratorAccess` is a stepping stone, not the destination.** What this workflow
actually needs is bounded and knowable: the Terraform in `infra/terraform/aws/` manages an
S3 bucket and its sub-resources (`s3.tf`), a CloudFront distribution, an Origin Access
Control and a response-headers policy (`cloudfront.tf`), and IAM objects (`oidc.tf`: an
OIDC provider, one role, one inline role policy). That is S3 + CloudFront + IAM and nothing
else. A scoped customer-managed policy for it is entirely achievable.

The honest caveat, so you narrow it with your eyes open: **IAM write access is
escalation-equivalent to administrator** unless it is constrained. A principal that can
create a role and attach `AdministratorAccess` to it is an administrator by a slightly
longer route. So `AmazonS3FullAccess` + `CloudFrontFullAccess` + `IAMFullAccess` is a
cosmetic improvement, not a real one. Real narrowing means either scoping the IAM
statements to the specific role and provider ARNs this stack owns, or attaching a
permissions boundary to anything the permission set is allowed to create. Neither is hard,
both need care, and neither should be attempted in the same sitting as the migration
itself. Do the migration, live on it, then narrow it as a separate change with a
`terraform plan` to prove nothing broke.

## 4. Configure the local CLI

The AWS CLI here is v2 (`aws --version` reports `aws-cli/2.36.8` at the time of writing;
the `sso-session` format below needs 2.13 or newer, so any current v2 is fine).

```bash
aws configure sso
```

What it asks, and what to answer:

| Prompt | Answer |
|---|---|
| `SSO session name` | `csoh` (any label; it names the reusable login block) |
| `SSO start URL` | the `https://d-xxxxxxxxxx.awsapps.com/start` from step 2 |
| `SSO region` | `us-east-1` (the region Identity Center was enabled in, not necessarily your resource region) |
| `SSO registration scopes` | accept the default `sso:account:access` |

A browser opens for the device-authorization approval. Approve it, and the CLI lists the
accounts and roles your user can reach. Pick account `038416307420` and the
`CSOHAdminBootstrap` permission set, then:

| Prompt | Answer |
|---|---|
| `CLI default client Region` | `us-east-1` |
| `CLI default output format` | `json` |
| `CLI profile name` | `csoh-admin` |

The result in `~/.aws/config`:

```ini
[sso-session csoh]
sso_start_url = https://d-xxxxxxxxxx.awsapps.com/start
sso_region = us-east-1
sso_registration_scopes = sso:account:access

[profile csoh-admin]
sso_session = csoh
sso_account_id = 038416307420
sso_role_name = CSOHAdminBootstrap
region = us-east-1
output = json
```

**How this differs from the `login_session` block it replaces.** Superficially they look
alike: both are a pointer, and neither stores a secret on disk. The differences that
matter:

- `login_session = arn:aws:iam::038416307420:root` names a **principal** and resolves to
  root's own permissions, which are unbounded by construction. The SSO profile names an
  **account plus a permission set**, and resolves to an assumed role whose permissions are
  whatever that permission set says today.
- The SSO profile's credentials arrive as an STS assumed-role session with an expiry, and
  the resulting ARN is `arn:aws:sts::038416307420:assumed-role/AWSReservedSSO_.../<user>`.
  That ARN appears in CloudTrail, so actions are attributable to a person and a role rather
  than to "root".
- `login_session` is an AWS CLI mechanism that the Terraform AWS provider does not
  implement, which is why `aws configure export-credentials` is currently required to
  bridge it. The SSO profile is understood by the provider directly. That is the subject of
  the next section, and it is the real payoff.

Do not delete the old `[default]` block yet. Step 8.

## 5. The Terraform compatibility question

This is where most migration guides are vague or wrong, and getting it wrong mid-migration
is how people end up back on root "just for now" and never leave.

**Verified for this repo:** `infra/terraform/aws/.terraform.lock.hcl` pins
`registry.terraform.io/hashicorp/aws` at **5.100.0** (constraint `~> 5.0` in
`versions.tf`), and the build installed under `.terraform/providers/` is
`darwin_arm64` (a `darwin_amd64` copy sits alongside it; the lock file itself records only
`h1:`/`zh:` hashes and names no platform). The 5.x provider is built on
the AWS SDK for Go v2, whose shared-config loader resolves SSO profiles natively;
inspecting the installed 5.100.0 `darwin_arm64` binary confirms it carries the `sso_session`,
`sso_start_url`, `sso_account_id` and `sso_role_name` config keys and the `ssocreds`
credential provider. Local Terraform is 1.15.7 `darwin_arm64`, comfortably above the
`required_version = ">= 1.6.0"` floor.

So: **the provider consumes the SSO profile directly. No bridging step is needed.**

### Path A: the profile, directly (use this one)

```bash
aws sso login --sso-session csoh
AWS_PROFILE=csoh-admin terraform -chdir=infra/terraform/aws plan
```

Or export it for the shell session:

```bash
export AWS_PROFILE=csoh-admin
aws sso login --sso-session csoh
terraform -chdir=infra/terraform/aws plan
```

The provider reads `~/.aws/config`, follows `sso_session` to the `[sso-session csoh]`
block, finds the cached SSO token under `~/.aws/sso/cache/`, and exchanges it for
short-lived role credentials. When the token expires it fails with a message that names SSO
and tells you to re-run `aws sso login`, which, unlike the IMDS red herring documented in
MANUAL_SECURITY_STEPS.md, actually points at the cause.

Note that `AWS_PROFILE` has no effect on the **backend**. `versions.tf` puts this stack's
state in the GCS bucket `csoh-org-495800-tfstate` under prefix `csoh/aws`, so Google
application-default credentials still have to be present. That is unchanged by this
migration and is called out in `infra/README.md`.

### Path B: export-credentials, still viable as a fallback

`aws configure export-credentials` works against an SSO profile just as it does against a
`login_session` one. It resolves whatever the profile says and prints concrete credentials:

```bash
aws sso login --sso-session csoh
eval "$(aws configure export-credentials --profile csoh-admin --format env)"
terraform -chdir=infra/terraform/aws plan
```

That sets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` and
`AWS_CREDENTIAL_EXPIRATION` in the shell.

Keep this in your pocket for a tool that predates SDK v2 SSO support, but prefer Path A,
for a specific reason: **environment variables beat profiles in the credential chain.**
Exported credentials persist in the shell after they expire and after you re-run
`aws sso login`, and they silently shadow the profile. The failure looks like "I logged in
and it still says expired". If you have used Path B in a shell and want to go back to Path
A in the same shell:

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_CREDENTIAL_EXPIRATION
```

Keep `AWS_EC2_METADATA_DISABLED=true` exported either way, for the reason documented in
MANUAL_SECURITY_STEPS.md: without it, an expired session falls through the chain to EC2
instance metadata that does not exist on a laptop and hangs for minutes before failing with
a message that blames IMDS.

## 6. Verification

Two checks, in order. Do not skip the first because the second passed.

**Check 1: the identity is no longer root.**

```bash
aws sts get-caller-identity --profile csoh-admin
```

The `Arn` must look like:

```
arn:aws:sts::038416307420:assumed-role/AWSReservedSSO_CSOHAdminBootstrap_xxxxxxxx/nunley@gmail.com
```

If it ends in `:root`, you are still on the old credentials. Most likely causes: `--profile`
omitted and `AWS_PROFILE` not set, or stale `AWS_*` environment variables shadowing the
profile (see the `unset` above).

**Check 2: Terraform still works.**

```bash
export AWS_PROFILE=csoh-admin
aws sso login --sso-session csoh
terraform -chdir=infra/terraform/aws plan
```

Expect a clean plan. `cloudfront.tf` deliberately omits `minimum_protocol_version` (the
reasoning is written out at length around line 160 of that file), which is what made this
stack converge; if you instead see the permanent `0 to add, 3 to change` churn described in
MANUAL_SECURITY_STEPS.md section 1c, you are on an older checkout, not looking at a
credentials problem.

**The safety net, and its limit.** `versions.tf` sets
`allowed_account_ids = [var.aws_account_id]`, defaulting to `038416307420`
(`variables.tf`). If the credentials in play belong to any *other* AWS account, Terraform
aborts before it touches anything, with an explicit account-mismatch error. That is a real
guardrail during a credential migration, when it is genuinely easy to have the wrong
profile active, and it is worth knowing it is there.

Its limit is equally worth knowing: it checks the **account**, not the **principal**. Root
and the SSO role are the same account, so `allowed_account_ids` will happily let a root
apply through. Check 1 is what tells you which identity you are, and there is no automated
substitute for reading its output.

## 7. Cutover and rollback

The cutover is not a switch, it is a period of using the new identity and finding out what
it cannot do. Plan for that rather than being surprised by it.

**If the new identity cannot do something.** With `AdministratorAccess` this should not
happen, but if it does, the failure is loud and specific: an `AccessDenied` naming the API
action and the resource. The correct response is to **add that action to the permission
set**, not to reach for root. Every such failure is free information about what the scoped
policy in step 3 will eventually need to contain, so write it down.

**If an apply fails partway through.** Terraform state is the thing to protect, and it is
in GCS, unaffected by which AWS credential you hold. Re-authenticate (`aws sso login
--sso-session csoh`), then re-run. If the run died wedged and left a state lock, follow
MANUAL_SECURITY_STEPS.md: confirm no terraform process is alive, then `force-unlock` with
the ID from the error. Never `-lock=false`; that starts a second concurrent apply against
the same state rather than clearing anything.

**Do not run two applies with two identities at once.** During cutover the temptation is to
have a root shell open "just in case" alongside the SSO shell. Two concurrent applies
against one state is the corruption the lock exists to prevent. Close the root shell.

**Do not try to delete or disable the root user.** You cannot: every AWS account has
exactly one root user, permanently, and it is the account's ultimate recovery path. There
is no API and no console button for removing it, and attempting to lock yourself out of it
on purpose is how an account becomes unrecoverable. (AWS's centralized root access
management can remove root credentials from *member* accounts in an organization, but the
management account's root is explicitly out of scope, and this account is the management
account.)

The correct end state is not "root is gone", it is **"root is unused, MFA-protected,
key-less, and its credentials live somewhere physically safe"**. Root remains the
break-glass path for the handful of things that genuinely require it: closing the account,
changing the account name or root email, some billing and support-plan changes, and
recovering Identity Center if you ever lock yourself out of it. Those are real, they are
rare, and none of them is `terraform apply`.

## 8. Retire the `login_session` block

Once step 6 passes and you have run at least one real `terraform plan` (better: an actual
`apply`) through the SSO profile, remove the old block from `~/.aws/config`:

```ini
[default]
login_session = arn:aws:iam::038416307420:root
region = us-east-1
```

Leaving both is worse than it sounds, and not merely untidy:

- `[default]` is what every command without `--profile` and without `AWS_PROFILE`
  resolves to. Which is to say: forget the flag once, and you are back on root without any
  signal that anything is different. The commands succeed. That is the whole problem.
- It keeps a working, unscoped path to the account alive on a laptop for no benefit,
  precisely the exposure this migration exists to close.
- It makes "which identity did that action run as?" a question that has to be answered by
  archaeology instead of by reading the config.

Two ways to remove it, both fine:

- **Delete the block entirely.** Then a command with no profile has no credentials and
  fails immediately with `Unable to locate credentials`. Loud, unambiguous, and safe.
- **Replace it** so the default *is* the SSO profile:

  ```ini
  [default]
  sso_session = csoh
  sso_account_id = 038416307420
  sso_role_name = CSOHAdminBootstrap
  region = us-east-1
  output = json
  ```

  Convenient, and it means `terraform -chdir=infra/terraform/aws plan` works with no
  `AWS_PROFILE` at all. The trade-off is that it is quieter: a missing login shows up as an
  expiry error rather than as an obvious absence.

Either way, re-run the step 6 check afterwards with no profile flag at all:

```bash
aws sts get-caller-identity
```

`:root` in that output means the old block is still winning somewhere. Also check the shell
for stale exports (`env | grep '^AWS_'`) and `~/.aws/credentials`, which does not currently
exist here and should stay that way.

## What still requires the Console

For the record, since this repo's bias is to automate everything:

| Task | Why it cannot be scripted here |
|---|---|
| Enabling MFA on the root user | Root MFA assignment is a Console flow; there is no CLI/API for it |
| Deleting a root access key | Same: root credentials are managed only from the account's Security credentials page |
| Enabling IAM Identity Center (and the organization) | First-time enablement is a Console action, and doing it from Terraform means bootstrapping with the credential being retired |
| Approving the first `aws sso login` | Device-authorization flow, deliberately requires a browser and a human |

Everything downstream of those (permission sets, assignments, later scoping) has an API and
could be managed as code once a non-root identity exists to run it. That is a reasonable
follow-up. It is not this change.
