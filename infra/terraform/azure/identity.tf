# This whole file sets up "keyless" deploys to Azure: GitHub Actions proves who
# it is using a short-lived, signed token (OIDC) instead of a stored password or
# secret. It's the Azure counterpart to GCP WIF and the AWS OIDC role — an Entra
# ID app registration trusts GitHub's OIDC issuer via a federated credential, and
# the workflow's token is exchanged for an Azure access token. No client secret
# is ever created or stored. Background concepts used throughout:
#   - "resource" = a real cloud object Terraform CREATES and manages. "data"
#     (just below) = something Terraform only READS or looks up, never creates.
#   - OIDC (OpenID Connect) = a standard login protocol. GitHub acts as an
#     "identity provider": for each workflow run it issues a signed token (a JWT)
#     describing that run, which Azure can be configured to trust.
#   - Entra ID = Microsoft's identity directory (the service formerly called
#     Azure AD). It holds users, groups, and the app identities below. The
#     `azuread` provider in versions.tf talks to it; the `azurerm` provider
#     manages the actual Azure resources (storage, etc.).
# A "data" source READS existing info instead of creating anything. This one
# returns details about the identity Terraform itself is currently logged in as
# (the operator running `terraform apply`) — notably its object ID and tenant
# ID, reused below as the owner of the app objects and exported as an output.
data "azuread_client_config" "current" {}

# Two Entra objects together form an app identity, and beginners trip on the
# distinction:
#   - an "application" (a.k.a. app registration) is the GLOBAL definition/
#     blueprint of the app — its name, its client_id, and which external tokens
#     it trusts (the federated credential is attached to it).
#   - a "service principal" (next resource) is the LOCAL instance of that app
#     inside THIS tenant — the actual identity that can be granted Azure
#     permissions and that signs in.
# You need both: the application to define and be trusted, the service principal
# to receive roles and act. This resource is the application half.
resource "azuread_application" "github" {
  # Human-readable name shown in the Entra portal; identifies this as the
  # site's GitHub publisher identity.
  display_name = "csoh-site-github-publisher"
  # Who may administer this app object in Entra. We set the operator (read from
  # the data source above) as owner. The "[ ]" make this a list — `owners`
  # accepts multiple object IDs even though there's one here.
  owners = [data.azuread_client_config.current.object_id]
}

# The service principal: the in-tenant identity for the application above. This
# is the "principal" that the role assignment at the bottom grants permissions
# to, and what GitHub Actions effectively becomes after the token exchange.
resource "azuread_service_principal" "github" {
  # Links this service principal back to its application by client_id (the app's
  # public identifier). Referencing `azuread_application.github` also tells
  # Terraform to create the application first, then this principal.
  client_id = azuread_application.github.client_id
  # Same operator set as owner here, mirroring the application above.
  owners = [data.azuread_client_config.current.object_id]
}

# A "federated identity credential" is the heart of keyless auth: instead of a
# password or client secret, it tells Entra "trust an OIDC token from THIS
# external issuer, addressed to THIS audience, describing THIS exact subject —
# and treat it as proof of identity for this app." When all three match, Entra
# hands back a short-lived Azure access token. It's the Azure analogue of the
# AWS trust policy and GCP's WIF provider mapping.
# The federated credential locks the trust to this repo's `production` GitHub
# Environment. The deploy jobs declare `environment: production`, so the OIDC
# sub claim is `repo:OWNER/REPO:environment:production` (not the
# `ref:refs/heads/...` form) — `subject` must match that. The branch
# restriction is enforced by the GitHub Environment itself (main-only).
resource "azuread_application_federated_identity_credential" "github" {
  # Which app registration this credential is attached to. `.id` references the
  # application resource above, so Terraform creates the app first. Note this is
  # the application's directory object ID, distinct from its client_id.
  application_id = azuread_application.github.id
  # A human-readable label for this credential in the Entra portal; cosmetic.
  display_name = "github-production"
  # Free-text note shown alongside it. The "${...}" is Terraform interpolation —
  # it splices variable values into the string. With the variables.tf defaults
  # this reads "...for CloudSecurityOfficeHours/csoh.org".
  description = "GitHub Actions OIDC (production environment) for ${var.github_owner}/${var.github_repo}"
  # The "audiences" the incoming token must be addressed to (its "aud" claim).
  # This fixed value is the standard audience for Entra's token-exchange
  # endpoint; it's what GitHub's azure/login step requests. Requiring it stops a
  # token minted for some other service from being replayed against Azure.
  audiences = ["api://AzureADTokenExchange"]
  # The "issuer": the exact URL whose signature the token must carry. Entra
  # fetches GitHub's public signing keys from here to verify the token is
  # genuinely from GitHub Actions and untampered.
  issuer = "https://token.actions.githubusercontent.com"
  # The "subject" is the security gate. GitHub stamps every OIDC token with a
  # "sub" claim describing the workflow context that produced it; this value
  # must match it exactly or Entra rejects the exchange. With the defaults it
  # resolves to "repo:CloudSecurityOfficeHours/csoh.org:environment:production",
  # so ONLY a job in this repo running in the GitHub "production" Environment is
  # trusted — any other repo, fork, branch, or environment is refused.
  subject = "repo:${var.github_owner}/${var.github_repo}:environment:production"
}

# An Azure "role assignment" is the three-part grant that actually gives an
# identity permissions: WHO (a principal) gets WHAT role (a bundle of allowed
# actions) over WHICH scope (a subscription, resource group, or single
# resource). This is Azure's RBAC (Role-Based Access Control) system — the
# rough equivalent of attaching an IAM policy to a role in AWS, except the role
# (the permission set) and the assignment (granting it here) are separate
# concepts. Nothing the service principal created above can DO anything until a
# role is assigned to it; this resource is what wires that up.
# "Least privilege" is the security rule of granting only the exact permissions
# a job needs and nothing more, so a leaked credential can't be used to roam.
# Here that means the publisher can read/write blob data in THIS storage account
# only: "Storage Blob Data Contributor" is the data-plane role needed to upload
# into $web, and it grants no control-plane (account management) rights.
resource "azurerm_role_assignment" "github_blob_writer" {
  # "scope" pins the grant to a single object: this site's storage account, and
  # nothing else in the subscription. `azurerm_storage_account.site.id` is a
  # REFERENCE to the storage account defined in storage.tf (its full Azure
  # resource ID). Because this resource reads that value, Terraform knows to
  # create the storage account first, then this assignment. Scoping here (rather
  # than at the whole subscription) is the "WHICH" half of least privilege.
  scope = azurerm_storage_account.site.id
  # "role_definition_name" is the named permission bundle to grant. Azure ships
  # hundreds of built-in roles; this one is deliberately narrow. The "Data"
  # roles act on the DATA PLANE (the bytes inside blobs) — exactly what's needed
  # to upload the site's files into the $web container. It grants NO control
  # plane rights (creating/deleting/reconfiguring the account itself), so even
  # if this credential leaked it couldn't tear down or repoint the account.
  role_definition_name = "Storage Blob Data Contributor"
  # "principal_id" is WHO receives the role: the service principal created
  # above. `.object_id` is that principal's unique ID in the Entra directory
  # (every directory object — app, service principal, user — has one). This
  # reference also orders creation: the service principal exists before the
  # grant that targets it.
  principal_id = azuread_service_principal.github.object_id
}
