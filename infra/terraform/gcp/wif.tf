# --- What this file does ---
# This file wires up KEYLESS deploys from GitHub Actions into this GCP
# project. "Keyless" means GitHub never holds a stored Google password or a
# downloaded JSON key file (the usual things that leak and get abused).
# Instead it uses Workload Identity Federation (WIF), explained below.
#
# The cloud idea - OIDC FEDERATION: when a GitHub Actions job runs, GitHub
# itself issues a short-lived, signed proof-of-identity called an OIDC token.
# That token is like a tamper-proof badge that says "I am workflow X running
# in repo Y on branch Z." WIF lets GCP TRUST that badge: GCP verifies the
# badge came from GitHub, checks it matches rules we set, and in return hands
# back a temporary GCP access token. The temporary token expires in minutes,
# so there is no long-lived secret to steal. This trust is set up in two
# pieces - a "pool" (a container for external identities) and a "provider"
# (the specific trust rule for one external issuer, here GitHub) - then a
# permission grant connects the trusted GitHub identity to the deployer SA.
#
# Terraform reminders used throughout this file:
#   - A `resource` block describes one real cloud object Terraform should
#     create and keep in sync (vs. a `data` source, which only READS an
#     existing object - there are none here). The two quoted labels are the
#     resource TYPE (e.g. google_iam_workload_identity_pool) and a LOCAL NAME
#     we pick ("github") to refer to it from other lines.
#   - `var.NAME` reads an input variable from variables.tf (e.g. project_id).
#   - `${ ... }` is interpolation: whatever is inside is computed and spliced
#     into the surrounding string.
#   - Writing one resource's attribute inside another resource (for example
#     google_iam_workload_identity_pool.github.workload_identity_pool_id) is a
#     cross-resource REFERENCE; it also tells Terraform to build the
#     referenced object first, so ordering is automatic.

# STEP 1 - the WIF POOL. Workload Identity Federation lets GitHub Actions
# impersonate the deployer SA without long-lived JSON keys (the OIDC token
# GitHub mints for the workflow run is exchanged for a short-lived GCP access
# token). A pool is just a named container that groups external (non-Google)
# identities so they can be referenced by GCP IAM. Nothing is trusted yet;
# this only creates the bucket the GitHub trust rule (Step 2) will live in.
resource "google_iam_workload_identity_pool" "github" {
  # Which GCP project owns this pool. Reads project_id from variables.tf so
  # the value isn't hard-coded in many files.
  project = var.project_id
  # The pool's permanent ID within the project. It must be unique here and is
  # referenced later (and in outputs.tf) to build the long principal name.
  workload_identity_pool_id = "github-pool"
  # Friendly names shown in the Cloud Console; cosmetic only, no behavior.
  display_name = "GitHub Actions"
  description  = "WIF pool for GitHub Actions"

  # `depends_on` forces an explicit ordering: do not create this pool until
  # the project's APIs (apis.tf, which enables IAM/STS/etc.) are enabled.
  # Without those APIs turned on, creating WIF objects would fail. Terraform
  # usually infers order from references, but here there is no direct
  # reference, so we state the dependency by hand.
  depends_on = [google_project_service.apis]
}

# STEP 2 - the WIF PROVIDER. This is the actual trust rule that says "accept
# OIDC badges issued by GitHub Actions." It also translates fields out of
# GitHub's token into GCP attributes, and sets a condition that narrows trust
# to exactly this one repository.
resource "google_iam_workload_identity_pool_provider" "github" {
  # Same owning project as the pool.
  project = var.project_id
  # Attach this provider to the pool created in Step 1. Referencing the pool's
  # ID (instead of retyping "github-pool") also makes Terraform create the
  # pool first.
  workload_identity_pool_id = google_iam_workload_identity_pool.github.workload_identity_pool_id
  # Permanent ID for this provider within the pool; reused in outputs.tf to
  # build the provider's full resource name that the deploy workflow passes to
  # the google-github-actions auth step.
  workload_identity_pool_provider_id = "github-provider"
  # Cosmetic label in the Console.
  display_name = "GitHub OIDC"

  # ATTRIBUTE MAPPING - a GitHub OIDC token carries "claims" (facts about the
  # run). `assertion.<x>` reads a claim from the incoming token; the left side
  # is the GCP attribute we store it as. These mapped attributes are what we
  # can later match on in IAM (e.g. attribute.repository is used in the
  # principalSet binding at the bottom of this file).
  attribute_mapping = {
    # google.subject is the required, unique caller identity. GitHub's `sub`
    # claim encodes which repo/branch/environment the run came from.
    "google.subject" = "assertion.sub"
    # repository = "owner/repo" of the workflow run (e.g. "CloudSecurity.../csoh.org").
    "attribute.repository" = "assertion.repository"
    # repository_owner = just the org/user that owns the repo.
    "attribute.repository_owner" = "assertion.repository_owner"
    # ref = the git ref that triggered the run (e.g. "refs/heads/main").
    "attribute.ref" = "assertion.ref"
    # workflow = the name of the workflow file that ran.
    "attribute.workflow" = "assertion.workflow"
  }

  # ATTRIBUTE CONDITION - a hard gate evaluated when a token is presented.
  # GCP rejects the token unless this expression is true. This is the critical
  # security control: without it, ANY GitHub workflow in any repo on the whole
  # platform could mint a token from this pool.
  #
  # Two claims are required, not one:
  #   * repository - the run came from this exact repo (values from variables.tf,
  #     e.g. "CloudSecurityOfficeHours/csoh.org").
  #   * sub - the run was executing in the `production` or `qa` GitHub
  #     Environment.
  #
  # The second half is what makes this equivalent to the other two clouds.
  # Checking only `repository` trusted EVERY workflow in the repo, on every
  # branch - including scheduled jobs that read untrusted web content and never
  # enter an environment - to mint credentials for the deployer SA. AWS
  # (aws/oidc.tf) and Azure (azure/identity.tf) both pin the full subject
  # `repo:<owner>/<repo>:environment:production`, and only deploy.yml's
  # `publish-gcp` job (which declares `environment: production`) needs to pass.
  # The `production` environment is itself restricted to the `main` branch, so
  # this transitively enforces the branch rule that var.github_branch describes.
  #
  # The `qa` alternative was added for deploy-qa.yml. It follows the same shape
  # deliberately: `qa` is a real GitHub Environment, restricted by its own
  # deployment branch policy to the `qa` branch, so this stays an environment
  # pin rather than a looser `assertion.ref` check. Widening it to something
  # like a `startsWith` on the subject would re-open exactly the hole the
  # production pin closed, because a workflow can enter an environment it was
  # not built for far more easily than it can forge a claim.
  #
  # PASSING THIS CONDITION IS NOT AUTHORIZATION. It only gets a token minted
  # from the pool. WHICH service account that token may then impersonate is
  # decided separately, by the `principal://` bindings in Step 3 below - and the
  # `qa` subject is bound only to the narrowly-scoped QA deployer. Both halves
  # have to name a subject for it to be able to deploy anything; editing this
  # condition alone produces a token that can do nothing, and editing only the
  # binding below produces a token that is never issued.
  attribute_condition = "assertion.repository == '${var.github_owner}/${var.github_repo}' && (assertion.sub == 'repo:${var.github_owner}/${var.github_repo}:environment:production' || assertion.sub == 'repo:${var.github_owner}/${var.github_repo}:environment:qa')"

  # OIDC settings: tell GCP who issues the tokens we trust. The issuer_uri is
  # GitHub Actions' well-known, fixed OIDC issuer URL - GCP fetches GitHub's
  # public signing keys from there to verify each token's signature is genuine.
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# STEP 3 - the PERMISSION GRANT (the link that makes WIF useful). Steps 1-2
# only establish that GCP will trust a token from this repo. They do NOT yet
# let that token DO anything. This grant says: the federated GitHub identity
# is allowed to "impersonate" (act as) the deployer service account. Once it
# can act as that SA, it inherits exactly the SA's least-privilege roles
# (push images + deploy Cloud Run revisions; see service_accounts.tf) - and
# nothing more.
resource "google_service_account_iam_member" "deployer_wif_binding" {
  # WHICH service account this grant is attached to: the "deployer" SA defined
  # in service_accounts.tf. `.name` is its full resource path, which this
  # particular IAM resource type expects. Referencing it also makes Terraform
  # create the SA before this binding.
  service_account_id = google_service_account.deployer.name
  # The role being granted on that SA. workloadIdentityUser is the specific
  # permission that allows a federated (external) identity to impersonate the
  # service account - i.e. it is what turns "trusted token" into "can act as
  # the deployer."
  role = "roles/iam.workloadIdentityUser"
  # WHO receives the role - the "member." A `principal://` member names ONE
  # federated identity by its subject, where the subject is whatever
  # `google.subject` was mapped from above (here GitHub's `sub` claim).
  # Reading the URL: it points at this project (by numeric project_number from
  # variables.tf), into the global "github-pool" (its ID pulled from the pool
  # resource), then names the exact subject
  # `repo:<owner>/<repo>:environment:production`.
  #
  # This previously used `principalSet://.../attribute.repository/<owner>/<repo>`,
  # which granted impersonation to ANY workflow run from the repo, on any
  # branch, in any (or no) environment. The attribute_condition above is the
  # hard gate and already rejects those tokens; pinning the member to the same
  # subject is defense in depth, and mirrors the StringEquals-on-sub condition
  # in aws/oidc.tf and the `subject =` line in azure/identity.tf.
  member = "principal://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/subject/repo:${var.github_owner}/${var.github_repo}:environment:production"
}

# STEP 4 - the SECOND permission grant, for QA. Identical in shape to Step 3,
# with two things changed: the subject ends `:environment:qa` instead of
# `:environment:production`, and it points at the QA deployer service account
# rather than the production one.
#
# This pairing is the whole point of splitting the identities. A token minted by
# deploy-qa.yml carries the `qa` subject, so it matches ONLY this binding, so it
# can impersonate ONLY csoh-deployer-qa - whose roles stop at the csoh-site-qa
# Cloud Run service (see service_accounts.tf). It cannot act as
# `google_service_account.deployer` and therefore cannot reach production, even
# though both tokens come from the same pool and pass the same provider
# condition.
#
# It follows that the `qa` GitHub Environment must have a deployment branch
# policy restricting it to the `qa` branch, exactly as `production` is
# restricted to `main`. Without that policy this trust still works, but it would
# accept a run of deploy-qa.yml from any branch - which is a much smaller
# problem than the production equivalent, yet the same shape, and free to avoid.
resource "google_service_account_iam_member" "deployer_qa_wif_binding" {
  service_account_id = google_service_account.deployer_qa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principal://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/subject/repo:${var.github_owner}/${var.github_repo}:environment:qa"
}
