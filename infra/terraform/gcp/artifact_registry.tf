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
    # Make image tags IMMUTABLE: once a tag (e.g. ":abc123") points at an
    # image, it can never be moved to a different image or overwritten. This is
    # a security/integrity guarantee -- it prevents "tag hijacking" where a tag
    # silently changes underneath you, and guarantees that what CI tested is
    # byte-for-byte what Cloud Run later runs. Because of this, CI must push a
    # NEW unique tag for every deploy (typically the git commit SHA) rather
    # than reusing one like ":latest".
    immutable_tags = true
  }

  # Cleanup policies are automatic housekeeping rules that delete (or protect)
  # old images so the repository -- and your storage bill -- doesn't grow
  # forever. A repo can have several policies; they are evaluated together, and
  # a KEEP rule wins over a DELETE rule when both match the same image (KEEP is
  # a safety net that protects images a DELETE rule might otherwise remove).
  # You can declare a block like this more than once on the same resource;
  # Terraform treats each "cleanup_policies { ... }" as a separate policy.
  #
  # Policy 1: always KEEP the 30 most recent image versions, so the current
  # deploy plus a healthy window of previous ones stay available for instant
  # rollback even if the DELETE policy below would otherwise sweep them.
  cleanup_policies {
    # A unique label for this policy (free text). Just names the rule.
    id = "keep-recent-30"
    # KEEP = protect matching images from deletion (an allow/retain rule).
    action = "KEEP"
    # Match the N newest versions in the repo and keep them.
    most_recent_versions {
      # Retain the 30 most recently pushed image versions.
      keep_count = 30
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
      # string in seconds; 604800s = 7 days (the trailing "# 7d" is the
      # original author's own note spelling that out). So untagged leftovers
      # get a one-week grace period before being purged.
      older_than = "604800s" # 7d
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
