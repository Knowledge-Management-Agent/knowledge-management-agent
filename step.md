# Deployment Guide — AWS EKS + MCP Server

**Target:** AWS EKS (per `requirements.md` §7, DEPLOY-1..10) | **Infra provisioning:** Terraform (`terraform/`) — VPC, EKS cluster/node group, IRSA roles, EBS CSI driver, AWS Load Balancer Controller, ECR | **App manifests:** plain Kubernetes YAML (`k8s/`) — a Helm chart can replace these later without changing what's deployed | **MCP transport:** local stdio only — the MCP server is not containerized/deployed to the cluster; it runs on your machine and calls the deployed REST API over HTTPS.

This closes the two gaps identified in `report.md` §7–8 (MCP-1..6, DEPLOY-1..10). It does not change anything about the existing RAG pipeline, RBAC, or generation logic — only how the app is packaged, exposed, and additionally reachable via MCP.

---

## 0. What you're deploying

| Component | Where it runs | Image |
|---|---|---|
| `km-backend` (FastAPI + ChromaDB) | EKS, 1 replica (single-writer vector store — see §5) | `backend/Dockerfile` |
| `km-frontend` (React, nginx) | EKS, 2 replicas | `frontend/Dockerfile` |
| MCP server | **Your machine**, stdio, launched by Claude Desktop/Code | `backend/app/mcp/server.py` (no image — runs from your local Python env) |

The MCP server is a thin REST client (`backend/app/mcp/client.py`) — it logs into the deployed backend the same way the web UI does and is bound by the same viewer/author RBAC. It has no direct access to Chroma, the LLM provider, or any secret other than its own login credentials.

---

## 1. Prerequisites

Install locally:
- `aws` CLI v2, authenticated (`aws sts get-caller-identity` should work — you're using an IAM user with AdministratorAccess, which is sufficient for everything below)
- `terraform` >= 1.5 (provisions the VPC/EKS/IAM/ECR/add-ons — replaces the old `eksctl`/manual-`helm` approach)
- `kubectl`
- `docker`

You need:
- An AWS account with permission to create VPCs, EKS clusters, IAM roles, ECR repos, and EKS add-ons (AdministratorAccess covers this)
- Nothing else yet — no domain required. This guide skips Route53/ACM/TLS for now and tests via `kubectl port-forward` (§6/§7). Add a domain + ACM cert later by extending `terraform/` with an `aws_acm_certificate` and Route53 records, then filling in `k8s/30-ingress.yaml`'s placeholders — nothing else in this guide needs to change.

Set these once, reuse everywhere below:

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export CLUSTER_NAME=km-agent-poc
export IMAGE_TAG=$(git rev-parse --short HEAD)
```

---

## 2. Provision AWS infrastructure with Terraform

Two Terraform roots: `terraform/bootstrap` (state backend, applied once ever, local state) and `terraform/` (VPC, EKS, node group, IAM/IRSA, EBS CSI driver, AWS Load Balancer Controller, ECR — applied per environment, remote state in S3).

### 2a. Bootstrap the state backend (one-time, ever)

```bash
cd terraform/bootstrap
terraform init
terraform apply
```

Note the outputs (`state_bucket_name`, `lock_table_name`) — you need them next.

### 2b. Configure and apply the main infrastructure

```bash
cd ../   # back to terraform/
cp backend.hcl.example backend.hcl
```

Edit `backend.hcl`: set `bucket` and `dynamodb_table` to the bootstrap outputs, `region` to `$AWS_REGION`. (`backend.hcl` is gitignored — it's environment-specific, not secret, but there's no reason to commit it.)

```bash
terraform init -backend-config=backend.hcl
terraform plan    # review: 1 VPC, 1 EKS cluster + node group, 2 IRSA roles, 1 EKS add-on,
                  # 1 helm_release, 2 ECR repos -- roughly 40-50 resources
terraform apply
```

This takes **15-20 minutes** (EKS cluster creation dominates). When it finishes:

```bash
terraform output                       # note ecr_repository_urls
eval $(terraform output -raw configure_kubectl)   # runs `aws eks update-kubeconfig ...`
kubectl get nodes                      # should show 2 Ready nodes
kubectl get deployment -n kube-system aws-load-balancer-controller   # should show 1/1 Ready
```

```bash
export ECR_BACKEND_URL=$(terraform output -json ecr_repository_urls | python -c "import sys,json;print(json.load(sys.stdin)['km-agent-backend'])")
export ECR_FRONTEND_URL=$(terraform output -json ecr_repository_urls | python -c "import sys,json;print(json.load(sys.stdin)['km-agent-frontend'])")
```

**What Terraform owns vs. what `kubectl` owns:** Terraform provisions cloud infrastructure and cluster add-ons only (VPC, EKS, node group, IRSA roles, the EBS CSI driver add-on, the AWS Load Balancer Controller). It does **not** create the app's namespace, ConfigMap, Secret, PVC, Deployments, Services, or Ingress — those stay as plain `kubectl apply -f k8s/...` (§5–6), unchanged from before. This keeps a clean line: Terraform = cluster exists and is ready; `kubectl`/`k8s/` = what runs on it.

---

## 3. (No separate add-on step — Terraform did this in §2)

The EBS CSI driver add-on and AWS Load Balancer Controller are provisioned by `terraform/addons.tf` as part of `terraform apply` above. If either failed or you need to re-check them later:

```bash
kubectl get pods -n kube-system | grep -E "ebs-csi|aws-load-balancer"
```

---

## 4. Build and push images to ECR

```bash
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker build -t "${ECR_BACKEND_URL}:$IMAGE_TAG" ./backend
docker push "${ECR_BACKEND_URL}:$IMAGE_TAG"

docker build -t "${ECR_FRONTEND_URL}:$IMAGE_TAG" \
  --build-arg VITE_API_BASE_URL="http://localhost:8000" \
  ./frontend
docker push "${ECR_FRONTEND_URL}:$IMAGE_TAG"
```

`VITE_API_BASE_URL` is baked into the frontend at build time (see `frontend/Dockerfile`). It's set to `http://localhost:8000` here because §6/§7 test via `kubectl port-forward` (no domain yet, per §1). Once you add a real domain + Ingress, rebuild the frontend image with `VITE_API_BASE_URL=https://api.<your-domain>` instead.

---

## 5. Apply base manifests (namespace, config, storage)

Edit placeholders first:
- `k8s/01-configmap.yaml` — set `LLM_PROVIDER` / `EMBEDDING_PROVIDER` to a real provider (not `mock`) if you want real answers. `CORS_ORIGINS` can stay as-is while testing via `kubectl port-forward` (browser origin is `http://localhost:5173`/`:8080` either way).
- `k8s/10-backend-deployment.yaml` — replace `REPLACE_WITH_ECR_URI/km-agent-backend:REPLACE_WITH_TAG` with `${ECR_BACKEND_URL}:${IMAGE_TAG}`.
- `k8s/20-frontend-deployment.yaml` — replace `REPLACE_WITH_ECR_URI/km-agent-frontend:REPLACE_WITH_TAG` with `${ECR_FRONTEND_URL}:${IMAGE_TAG}`.
- `k8s/30-ingress.yaml` — leave as-is for now (not applied until §1's "add a domain later" step).

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml
kubectl apply -f k8s/03-storageclass.yaml
kubectl apply -f k8s/04-pvc.yaml
```

**Do not** `kubectl apply -f k8s/02-secret.example.yaml` — it's a template with placeholder values, not a real secret. Create the real one imperatively so secret values never sit in a file on disk:

```bash
kubectl create secret generic km-backend-secret -n km-agent \
  --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY" \
  --from-literal=AZURE_OPENAI_API_KEY="" \
  --from-literal=AZURE_OPENAI_ENDPOINT="" \
  --from-literal=AZURE_OPENAI_CHAT_DEPLOYMENT="" \
  --from-literal=AZURE_OPENAI_EMBEDDING_DEPLOYMENT="" \
  --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --from-literal=GEMINI_API_KEY="" \
  --from-literal=JWT_SECRET="$(openssl rand -hex 32)" \
  --from-literal=DEMO_VIEWER_PASSWORD="$(openssl rand -hex 8)" \
  --from-literal=DEMO_AUTHOR_PASSWORD="$(openssl rand -hex 8)"
```

Only set the API key literal(s) for the provider(s) you actually configured in the ConfigMap; leave the rest blank. **Save the generated `DEMO_AUTHOR_PASSWORD` somewhere** — you'll need it to log in and for the MCP server's `KM_MCP_PASSWORD` in §8.

---

## 6. Apply app manifests and expose it

```bash
kubectl apply -f k8s/10-backend-deployment.yaml
kubectl apply -f k8s/11-backend-service.yaml
kubectl apply -f k8s/20-frontend-deployment.yaml
kubectl apply -f k8s/21-frontend-service.yaml
```

**No domain yet (this guide's default path)** — skip the Ingress and reach the services directly:

```bash
kubectl port-forward -n km-agent svc/km-backend 8000:8000 &
kubectl port-forward -n km-agent svc/km-frontend 8080:80 &
```

Then open `http://localhost:8080` and `curl http://localhost:8000/health`.

**Once you have a domain + ACM cert** (see §1): fill in `k8s/30-ingress.yaml`'s placeholders, rebuild the frontend image with the real `VITE_API_BASE_URL` (§4), then:

```bash
kubectl apply -f k8s/30-ingress.yaml
kubectl get ingress -n km-agent   # wait for ADDRESS to populate (a few minutes)
```

Point `app.<domain>` and `api.<domain>` (Route53 CNAME/ALIAS) at the ALB hostname shown in `ADDRESS`.

---

## 7. Verify

```bash
kubectl get pods -n km-agent -w        # wait for Running/Ready
kubectl rollout status deployment/km-backend -n km-agent
kubectl rollout status deployment/km-frontend -n km-agent

curl -s http://localhost:8000/health | python -m json.tool
# expect: {"status": "ok", "llm_provider": "...", "embedding_provider": "...", "indexed_chunks": 0}
```

(Substitute `https://api.<your-domain>` for `http://localhost:8000` throughout this section once you've applied the Ingress from §6.)

Log in and run one query end-to-end:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"author","password":"<DEMO_AUTHOR_PASSWORD from step 5>"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"question":"test question"}'
```

If it returns an answer (mock text if `LLM_PROVIDER=mock`), the pipeline is live end-to-end on EKS.

**Before trusting the corpus is populated:** the PVC starts empty — ingest documents through the frontend's Ingest tab, the `/ingest` API, or the MCP `ingest_document` tool (§8) before expecting real query results.

---

## 8. Run the MCP server locally

The MCP server is not deployed — you run it on your own machine, and it talks to the cluster over the same endpoint you just verified in §7 (`localhost:8000` via port-forward, or `https://api.<your-domain>` once you have an Ingress).

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Create `backend/app/mcp/.env` (copy from `backend/app/mcp/.env.example`, already gitignored) and set:

```
KM_API_BASE_URL=http://localhost:8000
KM_MCP_USERNAME=author
KM_MCP_PASSWORD=<DEMO_AUTHOR_PASSWORD from step 5>
```

(Use `https://api.<your-domain>` instead once you've set up the Ingress. Either way, the `kubectl port-forward` from §6 needs to be running for `localhost:8000` to work.)

Load it into the shell and run the server directly to confirm it starts (it will block, waiting on stdio — Ctrl+C to stop):

```bash
export $(grep -v '^#' app/mcp/.env | xargs)
python -m app.mcp.server
```

### Register it with Claude Code

```bash
claude mcp add km-agent \
  --env KM_API_BASE_URL=http://localhost:8000 \
  --env KM_MCP_USERNAME=author \
  --env KM_MCP_PASSWORD=<DEMO_AUTHOR_PASSWORD> \
  -- python -m app.mcp.server
```

Run this from the `backend/` directory (or use `--cwd`), so `python -m app.mcp.server` resolves the `app` package.

### Register it with Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "km-agent": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/absolute/path/to/knowledge-management-agent/backend",
      "env": {
        "KM_API_BASE_URL": "http://localhost:8000",
        "KM_MCP_USERNAME": "author",
        "KM_MCP_PASSWORD": "<DEMO_AUTHOR_PASSWORD>"
      }
    }
  }
}
```

Tools exposed: `query_knowledge_base`, `generate_document`, `ingest_document` (reads a local file path on *your* machine and uploads it), `list_documents`. All four run as whatever role `KM_MCP_USERNAME` has — use `viewer` credentials instead of `author` if you want a read-only MCP identity.

---

## 9. Updating a deployment

```bash
export IMAGE_TAG=$(git rev-parse --short HEAD)
docker build -t "${ECR_BACKEND_URL}:$IMAGE_TAG" ./backend
docker push "${ECR_BACKEND_URL}:$IMAGE_TAG"
kubectl set image deployment/km-backend backend="${ECR_BACKEND_URL}:$IMAGE_TAG" -n km-agent
kubectl rollout status deployment/km-backend -n km-agent
```

Same pattern for `km-frontend`. Because the backend Deployment uses `strategy: Recreate` (required for the single ReadWriteOnce Chroma PVC), there's a brief outage during backend rollouts — acceptable for a PoC, called out in `k8s/10-backend-deployment.yaml`.

---

## 10. Teardown

```bash
kubectl delete -f k8s/30-ingress.yaml --ignore-not-found
kubectl delete -f k8s/20-frontend-deployment.yaml -f k8s/21-frontend-service.yaml
kubectl delete -f k8s/10-backend-deployment.yaml -f k8s/11-backend-service.yaml
kubectl delete -f k8s/04-pvc.yaml -f k8s/03-storageclass.yaml   # deletes the PVC -- Chroma data is lost
kubectl delete secret km-backend-secret -n km-agent
kubectl delete -f k8s/01-configmap.yaml -f k8s/00-namespace.yaml
```

Then tear down the AWS infrastructure (only if nothing else uses this cluster):

```bash
cd terraform
terraform destroy   # removes VPC, EKS cluster/node group, IRSA roles, add-ons, ECR repos
```

The state backend (`terraform/bootstrap` — S3 bucket + DynamoDB table) is meant to be long-lived; leave it unless you're permanently done with this project. If you do want to remove it: `cd terraform/bootstrap && terraform destroy` — note the S3 bucket has `prevent_destroy` set, so you'd need to remove that lifecycle block first (deliberate friction against accidentally deleting Terraform state).

---

## 11. Known limitations (carried over from report.md, not fixed by this deployment work)

- **Single backend replica only.** ChromaDB's `PersistentClient` is a single-writer local store; scaling `km-backend` beyond 1 replica requires migrating to a managed/clustered vector DB first (DEPLOY-4).
- **MCP server isn't deployed or containerized** by design (confirmed choice: stdio-only, local). This satisfies MCP-1..4 but not the "independently containerized" framing in MCP-5/DEPLOY-1 as originally written in `requirements.md` — worth a note back to whoever owns that doc if a remote/always-on MCP endpoint is needed later (that would mean adding HTTP transport + a Deployment, which the code is structured to support without a rewrite: `mcp.run(transport="streamable-http")` instead of the default stdio call in `backend/app/mcp/server.py`).
- **Eval hasn't been run against a real LLM provider and recorded** (NFR-1/2/3 in `report.md` §3) — do this before treating the `≥85%`/`≥90%`/`≤8s` targets as met, independent of this deployment work.
- **Secrets are plain K8s Secrets**, not AWS Secrets Manager / External Secrets Operator — acceptable for this PoC's non-production security posture (SEC-3), revisit if this ever handles real data.
- **`terraform/` has not been run against real AWS infrastructure yet.** It was authored and syntax-checked (`terraform fmt`) in an environment where `terraform init` couldn't reach `releases.hashicorp.com` (network policy in that sandbox, not an AWS issue) to download providers/modules, so `terraform validate`/`plan` were never run. The module sources, versions, and attribute names are correct as of `terraform-aws-modules/eks` v20.x / `vpc` v5.x / `iam` v5.x, but the first real `terraform init && terraform plan` (§2) is also this config's first real test — read the plan output carefully before `apply`.
