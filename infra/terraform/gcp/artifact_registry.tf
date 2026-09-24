# A "resource" block tells Terraform to CREATE and manage a real cloud object
# (as opposed to a "data" source, which only READS something that already
# exists). Here the object is a Google Artifact Registry repository: a private,
# Google-hosted store for Docker container images. Think of it as this
# project's own private Docker Hub. Our GCP origin runs the site as an nginx
# container on Cloud Run, and that container image has to live somewhere Cloud
# Run can pull it from -- this repository is that home. CI builds the image,
# pushes it here, then deploys it to Cloud Run.
#
# "google_artifact_registry_repository" is the resource TYPE (provided by the
# Google provider declared in versions.tf), and "containers" is the local NAME
# we give this instance. Elsewhere in the Terraform code you refer to it as
# google_artifact_registry_repository.containers.
resource "google_artifact_registry_repository" "containers" {
  # Which GCP project owns this repository. var.project_id reads the value of
  # the "project_id" variable (see variables.tf, default "csoh-org-495800").
  # The "var." prefix is how Terraform references an input variable; pulling it
  # from a variable instead of hard-coding it keeps the project ID in one place.
  project = var.project_id
  # The GCP region the repository lives in (var.region defaults to
  # "us-central1"). It is deliberately the SAME region as the Cloud Run service
  # (see cloud_run.tf) so image pulls stay region-local: faster cold starts and
  # no cross-region data-transfer charges.
  location = var.region
  # The repository's short name/ID. Combined with project + location it forms
  # the image path CI pushes to and Cloud Run pulls from, e.g.
  # us-central1-docker.pkg.dev/csoh-org-495800/csoh-containers/<image>:<tag>.
  repository_id = "csoh-containers"
  # Free-text human description shown in the GCP console. Purely informational.
  description = "csoh.org container images"
  # The kind of artifacts this repo holds. "DOCKER" means it stores Docker /
  # OCI container images. Artifact Registry can also host npm, Maven, etc.;
  # we only need container images for the Cloud Run origin.
  format = "DOCKER"

  # Docker-specific settings for the repository.
  docker_config {
    # Image tags are MUTABLE here, and that is a deliberate trade rather than
    # an oversight. Artifact Registry's documentation is explicit: "If a
    # repository has immutable tags enabled, tagged artifacts can't be
    # deleted." Every deploy pushes a NEW unique tag (the git commit SHA), so
    # an image is tagged at birth and stays tagged forever -- which makes
    # immutable tags and ANY deletion-based retention mutually exclusive on
    # this repository: with immutable tags, both delete rules below are inert
    # and the repository grows without bound. Do not re-enable it.
    #
    # What replaced the guarantee. Immutable tags promised that a tag could not
    # be moved after the fact. That promise now comes from digests instead:
    # deploy.yml and deploy-qa.yml resolve the tag to a sha256 digest and pass
    # THAT to `gcloud run deploy`, and Binary Authorization evaluates the
    # digest-resolved reference either way. A tag moved after a deploy cannot
    # change the bytes that are running.
    #
    # What is genuinely weaker: a lost push race is now a silent overwrite
    # rather than a loud rejection. Both deploy workflows check for the tag
    # before pushing, so they do not fight in the normal case, and the digest
    # pinning above bounds the damage when they do.
    immutable_tags = false
  }

  # Cleanup policies are automatic housekeeping rules that delete (or protect)
  # old images so the repository -- and your storage bill -- doesn't grow
  # forever. A repo can have several policies; they are evaluated together, and
  # a KEEP rule wins over a DELETE rule when both match the same image (KEEP is
  # a safety net that protects images a DELETE rule might otherwise remove).
  # You can declare a block like this more than once on the same resource;
  # Terraform treats each "cleanup_policies { ... }" as a separate policy.
  #
  # Policy 1: always KEEP the 10 most recent image versions, so the current
  # deploy plus a few previous ones stay available for a quick rollback even
  # though the DELETE policies below would otherwise sweep them.
  cleanup_policies {
    # A unique label for this policy (free text). Just names the rule.
    id = "keep-recent-10"
    # KEEP = protect matching images from deletion (an allow/retain rule).
    action = "KEEP"
    # Match the N newest versions in the repo and keep them.
    most_recent_versions {
      # Retain the 10 most recently pushed image versions. This is a floor that
      # does not depend on dates: rollback targets exist even after a quiet
      # stretch where every image has aged past the DELETE rules below. Ten is
      # deliberate: an old image has no use here beyond a quick rollback, and
      # redeploying an older commit rebuilds its image anyway. At a typical
      # push rate (~6/day) ten is a day or two of deploys.
      keep_count = 10
    }
  }

  # Policy 2: DELETE old "untagged" images. When CI pushes a new image to a
  # tag, the image the tag used to point at can become untagged (a dangling
  # leftover) -- here those orphans are garbage-collected once they age out.
  cleanup_policies {
    # Unique label for this policy.
    id = "delete-old-untagged"
    # DELETE = remove matching images (subject to any KEEP rule winning).
    action = "DELETE"
    # The "condition" block narrows which images this rule applies to.
    condition {
      # Only target images that have NO tag pointing at them. Tagged images
      # (like the live deploy) are never touched by this rule.
      tag_state = "UNTAGGED"
      # ...and only once they are older than this age. The value is a duration
      # string in seconds; 86400s = 1 day (the trailing "# 1d" spells that
      # out). A day of grace covers an image caught mid-push; nothing here needs
      # an untagged image kept any longer.
      older_than = "86400s" # 1d
    }
  }

  # Policy 3: DELETE old TAGGED images -- the rule that actually reclaims space.
  #
  # Policy 2 above looks like it does this job and cannot. Every deploy pushes a
  # NEW unique tag, so an image is tagged at birth and stays tagged forever;
  # nothing ever transitions to UNTAGGED for the rule to catch. A rule whose
  # condition can never be met reports no error, it just never fires.
  #
  # This rule depends on immutable_tags = false (see docker_config above):
  # Artifact Registry will not delete a tagged artifact under immutable tags,
  # so with that setting on, this rule cannot execute either, and still
  # reports success. The two settings are a package; re-enabling immutability
  # silently re-breaks retention. The tell is never in the policy: check that
  # the image count actually moves.
  #
  # With a one-day age and the KEEP rule above, the repository holds its newest
  # 10 images plus anything pushed in the last day: about 2 GiB on a normal day,
  # at ~0.19 GiB of unique layers per image.
  #
  # Note the interaction with promotion: promote-qa reuses the image QA built,
  # found by tag and then deployed by digest. Once that image has aged out,
  # deploy.yml finds no tag, rebuilds the commit from source, and scans what it
  # built. Nothing fails, but the promotion no longer ships the exact bytes QA
  # tested - so promote soon after QA passes, or raise keep_count above.
  cleanup_policies {
    id     = "delete-old-tagged"
    action = "DELETE"
    condition {
      tag_state  = "TAGGED"
      older_than = "86400s" # 1d
    }
  }

  # depends_on forces an explicit ordering: Terraform must finish creating
  # google_project_service.apis (the block in apis.tf that switches on the
  # required GCP service APIs) BEFORE it tries to create this repository.
  # Creating an Artifact Registry repo requires the artifactregistry.googleapis.com
  # API to be enabled first; without this dependency Terraform might attempt
  # both at once and fail with an "API not enabled" error. depends_on is needed
  # here because nothing in this resource's arguments references that API
  # resource directly, so Terraform can't infer the order on its own.
  depends_on = [google_project_service.apis]
}
