# =============================================================================
# Binary Authorization: deploy-time admission control for Cloud Run
# -----------------------------------------------------------------------------
# WHAT THIS STOPS. Every identity that can deploy Cloud Run can, by default,
# deploy ANY image it can name - including one pulled from Docker Hub, or one
# built by hand on a laptop and pushed somewhere public. `roles/run.admin`
# grants "create revisions", not "create revisions from approved images". This
# policy adds the missing half: Cloud Run refuses to start a revision whose
# image did not come out of our own Artifact Registry repository.
#
# WHY NOW, AND NOT BEFORE. This project used to have one Cloud Run service and
# one deploy identity, and the honest answer was that Trivy plus a WIF-pinned
# pusher already covered the realistic risk. The QA pipeline
# changed the arithmetic: there are now two services (csoh-site, csoh-site-qa)
# and two deploy service accounts, and `csoh-deployer-qa` can create revisions
# without holding project-wide run.admin. More identities that can deploy means
# the set of things "a deploy" could mean got wider, and this narrows it back.
#
# WHAT THIS IS NOT. It is admission control on image PROVENANCE, not signature
# verification. Nothing here checks a cryptographic attestation, because with
# `evaluation_mode = REQUIRE_ATTESTATION` we would also have to decide WHO is
# allowed to sign - and the answer for this pipeline is genuinely awkward. QA
# builds the image that production later runs (see deploy-qa.yml: production
# recomputes the same tag, finds it present, and skips the rebuild), so the
# textbook policy of "production only runs what the production pipeline signed"
# would reject exactly the artifact we deliberately promote. Signing is still
# worth adding; it is just a bigger change than this one, and it needs the
# attestor to trust both pipelines. See cloud-deployment.html, "What we didn't
# do", which says so in those words.
#
# HOW THIS FAILS. Deploy-time, loudly, and without touching the live site. Cloud
# Run evaluates the policy when a revision is CREATED, not when a request is
# served, so a policy that is wrong breaks the next deploy and leaves the
# currently-serving revision running. That is the reason this ships enforcing
# rather than in dry-run: the blast radius of getting it wrong is a failed
# workflow run with an explicit error, not an outage.
# =============================================================================

# A project has exactly ONE Binary Authorization policy, and it always exists -
# an unmanaged project has an implicit one that allows everything. So this
# resource does not really "create" an object the way most resources do; on
# `apply` it overwrites that singleton, and on `destroy` it resets it to the
# permissive default rather than deleting anything. There is no name or ID to
# choose, which is why the resource takes a project and nothing else to identify
# itself.
resource "google_binary_authorization_policy" "default" {
  # Which project's policy this is. See variables.tf; defaults to
  # csoh-org-495800.
  project = var.project_id

  # ---------------------------------------------------------------------------
  # The allowlist: images matching any pattern here are admitted outright,
  # without being evaluated against the admission rules below. This is the whole
  # control. Everything our pipelines actually push lands inside this one
  # repository, so allowlisting the repository and denying the rest is the exact
  # shape of "only run what our CI built".
  # ---------------------------------------------------------------------------
  admission_whitelist_patterns {
    # Derived rather than typed, so it cannot drift from the repository it is
    # supposed to describe: if artifact_registry.tf is ever renamed or moved to
    # another region, this follows it. The literal value today is
    # us-central1-docker.pkg.dev/csoh-org-495800/csoh-containers/**
    #
    # The trailing `**` is deliberate and is not interchangeable with `*`. A
    # single `*` matches any number of characters EXCEPT `/`, so it would cover
    # `.../csoh-containers/csoh-site` but silently stop covering anything at a
    # nested path. `**` matches across `/` as well, so the boundary this
    # allowlists is "the repository", which is the boundary we actually mean.
    # Getting this wrong does not weaken the policy, it over-denies - which
    # surfaces as a deploy that fails rather than as a control that is quietly
    # not there.
    name_pattern = "${google_artifact_registry_repository.containers.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}/**"
  }

  # ---------------------------------------------------------------------------
  # Everything that did NOT match the allowlist above hits this rule.
  # ---------------------------------------------------------------------------
  default_admission_rule {
    # ALWAYS_DENY is the strictest of the three modes (the others being
    # ALWAYS_ALLOW, which is the permissive default a project starts with, and
    # REQUIRE_ATTESTATION, which is the signature-checking mode discussed in the
    # header). Combined with the allowlist above it reads as: our repository, or
    # nothing.
    evaluation_mode = "ALWAYS_DENY"

    # ENFORCED_BLOCK_AND_AUDIT_LOG actually blocks the deploy and writes the
    # decision to Cloud Audit Logs. The alternative, DRYRUN_AUDIT_LOG_ONLY,
    # logs the violation and admits the image anyway - useful for measuring what
    # a policy WOULD block before turning it on, and worth reaching for if you
    # are retrofitting this onto a project with deploys you do not fully know.
    # We know both of ours, and a dry-run policy is another instrument that
    # reports success while enforcing nothing, so it does not stay here.
    enforcement_mode = "ENFORCED_BLOCK_AND_AUDIT_LOG"
  }

  # Google maintains its own allowlist of system images that its managed
  # products need to run (sidecars, agents, and similar). ENABLE evaluates that
  # global policy first and admits anything on it, so a Google-injected
  # container cannot be blocked by our rule. DISABLE would make this policy the
  # only word on the subject, which sounds tighter and mostly just means a
  # future managed feature breaks in a way that looks like our bug.
  global_policy_evaluation_mode = "ENABLE"

  # The binaryauthorization.googleapis.com API (apis.tf) has to be on before the
  # policy can be written. Nothing in the arguments above references that
  # resource, so Terraform cannot infer the ordering on its own.
  #
  # The two Cloud Run services in that list are a BOOTSTRAP ordering fix, and
  # they are the non-obvious half of this file. Both services are declared with
  # Google's placeholder image, us-docker.pkg.dev/cloudrun/container/hello, with
  # the real image excluded from Terraform's diff by `ignore_changes` so CI owns
  # it (cloud_run.tf). `ignore_changes` does not apply on CREATE - a create
  # always uses the value written in the config - so on a from-scratch apply the
  # services would be created with an image this policy denies, and the apply
  # would fail. Creating them BEFORE the policy is written means they are
  # admitted under the permissive policy every project starts with, and the
  # first CI deploy replaces the placeholder with a real image from our own
  # repository. Every apply after that sends the real image, because by then it
  # is what sits in state.
  #
  # The alternative was to allowlist the placeholder path alongside our
  # repository. That works and is one line shorter, and it is rejected here on
  # purpose: it would make "our repository, or nothing" no longer literally
  # true, and a policy you have to add an asterisk to when describing it is a
  # policy someone will eventually describe without the asterisk.
  #
  # THE CAVEAT THIS LEAVES. Ordering only helps the first create. If either
  # service is ever FORCE-REPLACED while the policy is enforcing (changing its
  # name or location does that), the replacement create uses the placeholder
  # again and is denied - an apply that fails naming an image nobody in the diff
  # asked for. The remedy is to comment out that service's `binary_authorization`
  # block for the replacing apply and put it back afterwards, or to let the
  # replacement land and deploy through CI before re-enforcing.
  depends_on = [
    google_project_service.apis,
    google_cloud_run_v2_service.site,
    google_cloud_run_v2_service.site_qa,
  ]
}
