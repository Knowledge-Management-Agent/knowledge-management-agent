# Deployment Guide — AWS EKS + MCP Server

**Target:** AWS EKS (per `requirements.md` §7, DEPLOY-1..10) | **Manifest style:** plain Kubernetes YAML (`k8s/`) — a Helm chart can replace these later without changing what's deployed | **MCP transport:** local stdio only — the MCP server is not containerized/deployed to the cluster; it runs on your machine and calls the deployed REST API over HTTPS.

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
- `aws` CLI v2, authenticated (`aws sts get-caller-identity` should work)
- `kubectl`
- `eksctl`
- `docker`
- `helm` (only needed to install the AWS Load Balancer Controller add-on, not for the app itself)

You need:
- An existing EKS cluster, **or** create one (§2)
- An AWS account with permission to create ECR repos, IAM roles, and EKS add-ons
- A domain you control (for Ingress + TLS) — or skip TLS and test via the ALB's own hostname (§6 has both paths)

Set these once, reuse everywhere below:

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export CLUSTER_NAME=km-agent-poc
export ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
export IMAGE_TAG=$(git rev-parse --short HEAD)
```

---

## 2. Create the EKS cluster (skip if you already have one)

```bash
eksctl create cluster \
  --name "$CLUSTER_NAME" \
  --region "$AWS_REGION" \
  --nodegroup-name km-agent-workers \
  --node-type t3.medium \
  --nodes 2 \
  --nodes-min 2 \
  --nodes-max 3 \
  --managed
```

This provisions VPC, subnets, and a managed node group. Takes ~15-20 minutes. `eksctl` also writes your `kubectl` context automatically; verify with:

```bash
kubectl get nodes
```

---

## 3. Cluster add-ons (one-time per cluster)

### 3a. Amazon EBS CSI driver (required for the Chroma PVC, DEPLOY-4)

```bash
eksctl create iamserviceaccount \
  --cluster "$CLUSTER_NAME" --region "$AWS_REGION" \
  --namespace kube-system --name ebs-csi-controller-sa \
  --role-name AmazonEKS_EBS_CSI_DriverRole \
  --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy \
  --approve --role-only

eksctl create addon \
  --cluster "$CLUSTER_NAME" --region "$AWS_REGION" \
  --name aws-ebs-csi-driver \
  --service-account-role-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:role/AmazonEKS_EBS_CSI_DriverRole" \
  --force
```

### 3b. AWS Load Balancer Controller (required for the Ingress → ALB, DEPLOY-6)

```bash
eksctl utils associate-iam-oidc-provider --cluster "$CLUSTER_NAME" --region "$AWS_REGION" --approve

curl -sO https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/main/docs/install/iam_policy.json
aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file://iam_policy.json

eksctl create iamserviceaccount \
  --cluster "$CLUSTER_NAME" --region "$AWS_REGION" \
  --namespace kube-system --name aws-load-balancer-controller \
  --attach-policy-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy" \
  --approve

helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName="$CLUSTER_NAME" \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller
```

Verify: `kubectl get deployment -n kube-system aws-load-balancer-controller`.

### 3c. ACM certificate (only if you're doing TLS with a real domain — see §6 for the no-domain alternative)

```bash
aws acm request-certificate \
  --domain-name "*.REPLACE_WITH_DOMAIN" \
  --validation-method DNS \
  --region "$AWS_REGION"
```

Complete DNS validation in Route53 (or your DNS provider), then note the certificate ARN for `k8s/30-ingress.yaml`.

---

## 4. Build and push images to ECR

```bash
aws ecr create-repository --repository-name km-agent-backend --region "$AWS_REGION" || true
aws ecr create-repository --repository-name km-agent-frontend --region "$AWS_REGION" || true

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker build -t "$ECR_REGISTRY/km-agent-backend:$IMAGE_TAG" ./backend
docker push "$ECR_REGISTRY/km-agent-backend:$IMAGE_TAG"

docker build -t "$ECR_REGISTRY/km-agent-frontend:$IMAGE_TAG" \
  --build-arg VITE_API_BASE_URL="https://api.REPLACE_WITH_DOMAIN" \
  ./frontend
docker push "$ECR_REGISTRY/km-agent-frontend:$IMAGE_TAG"
```

`VITE_API_BASE_URL` is baked into the frontend at build time (see `frontend/Dockerfile`) — it must match whatever hostname you'll expose the backend on in §6. If you don't have a domain yet, rebuild the frontend image once you know the ALB hostname (or your real domain) rather than guessing now.

---

## 5. Apply base manifests (namespace, config, storage)

Edit placeholders first:
- `k8s/01-configmap.yaml` — set `LLM_PROVIDER` / `EMBEDDING_PROVIDER` to a real provider (not `mock`) if you want real answers, and set `CORS_ORIGINS` to your actual frontend origin.
- `k8s/10-backend-deployment.yaml` and `k8s/20-frontend-deployment.yaml` — replace `REPLACE_WITH_ECR_URI` / `REPLACE_WITH_TAG` with `$ECR_REGISTRY` / `$IMAGE_TAG` from above.
- `k8s/30-ingress.yaml` — replace `REPLACE_WITH_DOMAIN` and `REPLACE_WITH_ACM_CERTIFICATE_ARN` (or see §6 for the no-domain path).

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

**If you have a domain + ACM cert (recommended, matches DEPLOY-6's TLS requirement):**

```bash
kubectl apply -f k8s/30-ingress.yaml
kubectl get ingress -n km-agent   # wait for ADDRESS to populate (a few minutes)
```

Point `app.<domain>` and `api.<domain>` (Route53 CNAME/ALIAS) at the ALB hostname shown in `ADDRESS`.

**If you don't have a domain yet (quick PoC test, no TLS):** skip the Ingress and reach the services directly:

```bash
kubectl port-forward -n km-agent svc/km-backend 8000:8000 &
kubectl port-forward -n km-agent svc/km-frontend 8080:80 &
```

Then open `http://localhost:8080` and `curl http://localhost:8000/health`.

---

## 7. Verify

```bash
kubectl get pods -n km-agent -w        # wait for Running/Ready
kubectl rollout status deployment/km-backend -n km-agent
kubectl rollout status deployment/km-frontend -n km-agent

curl -s https://api.REPLACE_WITH_DOMAIN/health | python -m json.tool
# expect: {"status": "ok", "llm_provider": "...", "embedding_provider": "...", "indexed_chunks": 0}
```

Log in and run one query end-to-end:

```bash
TOKEN=$(curl -s -X POST https://api.REPLACE_WITH_DOMAIN/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"author","password":"<DEMO_AUTHOR_PASSWORD from step 5>"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST https://api.REPLACE_WITH_DOMAIN/query \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"question":"test question"}'
```

If it returns an answer (mock text if `LLM_PROVIDER=mock`), the pipeline is live end-to-end on EKS.

**Before trusting the corpus is populated:** the PVC starts empty — ingest documents through the frontend's Ingest tab, the `/ingest` API, or the MCP `ingest_document` tool (§8) before expecting real query results.

---

## 8. Run the MCP server locally

The MCP server is not deployed — you run it on your own machine, and it talks to the cluster over the same HTTPS endpoint you just verified.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Create `backend/app/mcp/.env` (copy from `backend/app/mcp/.env.example`, already gitignored) and set:

```
KM_API_BASE_URL=https://api.REPLACE_WITH_DOMAIN
KM_MCP_USERNAME=author
KM_MCP_PASSWORD=<DEMO_AUTHOR_PASSWORD from step 5>
```

Load it into the shell and run the server directly to confirm it starts (it will block, waiting on stdio — Ctrl+C to stop):

```bash
export $(grep -v '^#' app/mcp/.env | xargs)
python -m app.mcp.server
```

### Register it with Claude Code

```bash
claude mcp add km-agent \
  --env KM_API_BASE_URL=https://api.REPLACE_WITH_DOMAIN \
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
        "KM_API_BASE_URL": "https://api.REPLACE_WITH_DOMAIN",
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
docker build -t "$ECR_REGISTRY/km-agent-backend:$IMAGE_TAG" ./backend
docker push "$ECR_REGISTRY/km-agent-backend:$IMAGE_TAG"
kubectl set image deployment/km-backend backend="$ECR_REGISTRY/km-agent-backend:$IMAGE_TAG" -n km-agent
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

# only if you created the cluster in step 2 and nothing else uses it:
eksctl delete cluster --name "$CLUSTER_NAME" --region "$AWS_REGION"
```

---

## 11. Known limitations (carried over from report.md, not fixed by this deployment work)

- **Single backend replica only.** ChromaDB's `PersistentClient` is a single-writer local store; scaling `km-backend` beyond 1 replica requires migrating to a managed/clustered vector DB first (DEPLOY-4).
- **MCP server isn't deployed or containerized** by design (confirmed choice: stdio-only, local). This satisfies MCP-1..4 but not the "independently containerized" framing in MCP-5/DEPLOY-1 as originally written in `requirements.md` — worth a note back to whoever owns that doc if a remote/always-on MCP endpoint is needed later (that would mean adding HTTP transport + a Deployment, which the code is structured to support without a rewrite: `mcp.run(transport="streamable-http")` instead of the default stdio call in `backend/app/mcp/server.py`).
- **Eval hasn't been run against a real LLM provider and recorded** (NFR-1/2/3 in `report.md` §3) — do this before treating the `≥85%`/`≥90%`/`≤8s` targets as met, independent of this deployment work.
- **Secrets are plain K8s Secrets**, not AWS Secrets Manager / External Secrets Operator — acceptable for this PoC's non-production security posture (SEC-3), revisit if this ever handles real data.
