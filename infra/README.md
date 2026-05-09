# csoh.org GCP Infrastructure

Terraform + GitHub Actions deployment of csoh.org to Google Cloud Run, with the
load balancer / WAF / CDN / TLS / logging stack wrapped around it as a security
showcase.

## Architecture

```
Cloudflare (DNS only, gray cloud)
        │
        ▼
Global External HTTPS Load Balancer  (anycast IP)
   ├─ Cloud Armor (OWASP CRS WAF + per-IP rate limit + adaptive DDoS)
   ├─ Cloud CDN  (edge cache for static assets)
   └─ Modern TLS policy (TLS 1.2+ only)
        │
        ▼
Serverless NEG → Cloud Run (csoh-site)
   - nginx:1.27-alpine, digest-pinned (Dockerfile)
   - Custom CSP / HSTS / COOP / CORP headers (nginx.conf)
   - Runs as csoh-run-runtime SA (zero IAM roles)
   - Ingress restricted: only LB + internal traffic
        │
        ▼
Container image stored in Artifact Registry (immutable tags)
   - Built by GitHub Actions
   - Trivy-scanned (fails build on HIGH/CRITICAL)
   - Pushed via WIF — no service account keys

Logging:
   - Cloud Armor decisions, LB 4xx/5xx, IAM changes, audit logs
     → 400-day retention bucket
```

## File layout

```
infra/terraform/
  versions.tf            providers + GCS backend
  variables.tf           project, region, domain, GitHub repo
  apis.tf                google_project_service for required APIs
  service_accounts.tf    csoh-run-runtime (zero roles), csoh-deployer
  artifact_registry.tf   csoh-containers repo, immutable tags, cleanup policy
  wif.tf                 GitHub Actions WIF pool + provider, repo-scoped
  cloud_run.tf           Cloud Run v2 service, ingress=LB-only
  cloud_armor.tf         WAF rules + rate limit + adaptive protection
  load_balancer.tf       LB, NEG, backend, URL maps, TLS policy, managed cert
  logging.tf             400-day retention bucket + security log sink
  outputs.tf             LB IP, WIF provider, etc.
```

## One-time bootstrap

Run on a workstation authenticated as a project Owner.

```bash
# 1. Set the active project
gcloud config set project csoh-org-495800

# 2. Application-default credentials for Terraform
gcloud auth application-default login

# 3. Enable APIs needed before Terraform runs (rest are managed by Terraform)
gcloud services enable cloudresourcemanager.googleapis.com \
                       iam.googleapis.com \
                       serviceusage.googleapis.com

# 4. Create the GCS bucket that holds Terraform state.
#    Versioning + uniform IAM are non-negotiable for state buckets.
gcloud storage buckets create gs://csoh-org-495800-tfstate \
    --location=us-central1 \
    --uniform-bucket-level-access \
    --public-access-prevention

gcloud storage buckets update gs://csoh-org-495800-tfstate --versioning

# 5. Initialize and apply
cd infra/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Expect ~15–20 minutes for the managed SSL cert to provision once you've
pointed DNS at the LB IP. Until the cert is `ACTIVE`, HTTPS will fail — `gcloud
compute ssl-certificates describe csoh-cert --global` to watch status.

## DNS (Cloudflare)

After `terraform apply`, grab the LB IP:

```bash
terraform output -raw load_balancer_ip
```

In Cloudflare, with **gray cloud (DNS only)** so Cloud Armor sees real client IPs:

| Type | Name             | Value                   |
|------|------------------|-------------------------|
| A    | gcp              | `<LB IP>`               |  ← staging, verify here first
| A    | csoh.org         | `<LB IP>`               |  ← cut over after staging looks good
| A    | www              | `<LB IP>`               |

Keep TTLs short (300s) during cutover so you can roll back fast.

## GitHub Actions

The `.github/workflows/gcp-deploy.yml` workflow is wired to the WIF pool created
by Terraform. Required inputs are baked in (project, region, deployer SA, WIF
provider) — no GitHub Secrets needed.

It runs on every push to `main` that touches site files (mirroring the existing
FTP deploy's path filter) plus manual `workflow_dispatch`. The two pipelines run
in parallel until you cut DNS over.

## Common operations

```bash
# Force a redeploy (rebuilds latest image)
gh workflow run "GCP — Build, Scan, and Deploy"

# Roll back to a previous Cloud Run revision
gcloud run services update-traffic csoh-site \
    --region us-central1 \
    --to-revisions <REVISION_NAME>=100

# Watch Cloud Armor block events
gcloud logging read \
    'resource.type="http_load_balancer"
     AND jsonPayload.enforcedSecurityPolicy.outcome="DENY"' \
    --limit 20 --format json

# Watch managed cert status
gcloud compute ssl-certificates describe csoh-cert --global \
    --format='value(managed.status,managed.domainStatus)'
```

## Cost on $300 free credit

| Component                  | Approx. monthly |
|---------------------------|-----------------|
| LB forwarding rule (×2)    | ~$18            |
| Cloud Armor policy         | ~$5 + $0.75/rule|
| Cloud Run (scale to zero)  | ~$0–2           |
| Artifact Registry storage  | <$1             |
| Cloud Logging (low volume) | <$2             |
| Egress + CDN               | varies, ~$1–3   |
| **Total**                  | **~$30/mo**     |

Credit lasts ~10 months at this footprint.
