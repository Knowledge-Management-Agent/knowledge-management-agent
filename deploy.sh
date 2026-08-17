#!/usr/bin/env bash
# Idempotent end-to-end deploy: terraform apply -> build/push images -> apply
# k8s manifests -> wait for rollout -> re-ingest the eval corpus.
#
# Meant to run somewhere with a clean network path to AWS/ECR/GitHub -- the
# bastion, a GitHub Actions runner, or any machine without a TLS-intercepting
# corporate proxy in the way. It intentionally does none of the Zscaler CA
# bundle workarounds this project needed on the original authoring laptop;
# see step.md's "Device-specific workarounds" section if you need those.
#
# Required env vars (set before running, not stored in this repo):
#   GROQ_API_KEY   - from console.groq.com
# Optional:
#   AWS_REGION     (default us-east-1)
#   CLUSTER_NAME   (default km-agent-poc)
#   IMAGE_TAG      (default: current git short SHA)
#
# Usage:
#   export GROQ_API_KEY=gsk_...
#   ./deploy.sh
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER_NAME="${CLUSTER_NAME:-km-agent-poc}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
NAMESPACE=km-agent

if [ -z "${GROQ_API_KEY:-}" ]; then
  echo "ERROR: GROQ_API_KEY is not set. export GROQ_API_KEY=... and re-run." >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "=== 1/8: terraform apply ==="
cd terraform
if [ ! -f backend.hcl ]; then
  echo "ERROR: terraform/backend.hcl missing." >&2
  echo "Run 'cd terraform/bootstrap && terraform init && terraform apply' once first," >&2
  echo "then cp backend.hcl.example backend.hcl and fill in the bootstrap outputs (see step.md 2a/2b)." >&2
  exit 1
fi
terraform init -backend-config=backend.hcl -input=false
terraform apply -auto-approve -input=false
AWS_ACCOUNT_ID="$(terraform output -raw account_id 2>/dev/null || aws sts get-caller-identity --query Account --output text)"
ECR_BACKEND_URL="$(terraform output -json ecr_repository_urls | python3 -c "import sys,json;print(json.load(sys.stdin)['km-agent-backend'])")"
ECR_FRONTEND_URL="$(terraform output -json ecr_repository_urls | python3 -c "import sys,json;print(json.load(sys.stdin)['km-agent-frontend'])")"
cd "$REPO_ROOT"

echo "=== 2/8: point kubectl at the cluster ==="
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$AWS_REGION"
kubectl get nodes

echo "=== 3/8: build + push backend image ($IMAGE_TAG) ==="
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
docker build -t "${ECR_BACKEND_URL}:${IMAGE_TAG}" ./backend
docker push "${ECR_BACKEND_URL}:${IMAGE_TAG}"

echo "=== 4/8: apply namespace, config, storage, secret, backend ==="
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml
kubectl patch configmap km-backend-config -n "$NAMESPACE" --type merge -p \
  '{"data":{"LLM_PROVIDER":"groq","EMBEDDING_PROVIDER":"local"}}'
kubectl apply -f k8s/03-storageclass.yaml
kubectl apply -f k8s/04-pvc.yaml

JWT_SECRET="$(openssl rand -hex 32)"
DEMO_VIEWER_PASSWORD="$(openssl rand -hex 8)"
DEMO_AUTHOR_PASSWORD="$(openssl rand -hex 8)"
kubectl create secret generic km-backend-secret -n "$NAMESPACE" \
  --from-literal=GROQ_API_KEY="$GROQ_API_KEY" \
  --from-literal=OPENAI_API_KEY="" \
  --from-literal=AZURE_OPENAI_API_KEY="" \
  --from-literal=AZURE_OPENAI_ENDPOINT="" \
  --from-literal=AZURE_OPENAI_CHAT_DEPLOYMENT="" \
  --from-literal=AZURE_OPENAI_EMBEDDING_DEPLOYMENT="" \
  --from-literal=ANTHROPIC_API_KEY="" \
  --from-literal=GEMINI_API_KEY="" \
  --from-literal=JWT_SECRET="$JWT_SECRET" \
  --from-literal=DEMO_VIEWER_PASSWORD="$DEMO_VIEWER_PASSWORD" \
  --from-literal=DEMO_AUTHOR_PASSWORD="$DEMO_AUTHOR_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

sed "s|REPLACE_WITH_ECR_URI/km-agent-backend:REPLACE_WITH_TAG|${ECR_BACKEND_URL}:${IMAGE_TAG}|" \
  k8s/10-backend-deployment.yaml | kubectl apply -f -
kubectl apply -f k8s/11-backend-service.yaml

echo "=== 5/8: wait for backend rollout + public NLB hostname ==="
kubectl rollout status deployment/km-backend -n "$NAMESPACE" --timeout=300s

BACKEND_HOST=""
for i in $(seq 1 60); do
  BACKEND_HOST="$(kubectl get svc km-backend -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"
  [ -n "$BACKEND_HOST" ] && break
  sleep 5
done
if [ -z "$BACKEND_HOST" ]; then
  echo "ERROR: backend LoadBalancer hostname never appeared after 5 minutes." >&2
  exit 1
fi
BACKEND_URL="http://${BACKEND_HOST}"
echo "Backend URL: $BACKEND_URL"

echo "=== 6/8: build + push frontend image (VITE_API_BASE_URL=$BACKEND_URL) ==="
docker build -t "${ECR_FRONTEND_URL}:${IMAGE_TAG}" \
  --build-arg VITE_API_BASE_URL="$BACKEND_URL" \
  ./frontend
docker push "${ECR_FRONTEND_URL}:${IMAGE_TAG}"

sed "s|REPLACE_WITH_ECR_URI/km-agent-frontend:REPLACE_WITH_TAG|${ECR_FRONTEND_URL}:${IMAGE_TAG}|" \
  k8s/20-frontend-deployment.yaml | kubectl apply -f -
kubectl apply -f k8s/21-frontend-service.yaml
kubectl rollout status deployment/km-frontend -n "$NAMESPACE" --timeout=300s

FRONTEND_HOST=""
for i in $(seq 1 60); do
  FRONTEND_HOST="$(kubectl get svc km-frontend -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"
  [ -n "$FRONTEND_HOST" ] && break
  sleep 5
done

echo "=== 7/8: smoke test ==="
# The Service's LoadBalancer hostname appears well before AWS finishes
# provisioning DNS + passing target-group health checks -- retry.
for i in $(seq 1 30); do
  if BODY=$(curl -sf --max-time 10 "${BACKEND_URL}/health"); then
    echo "$BODY" | python3 -m json.tool
    break
  fi
  echo "not ready yet (attempt $i/30), retrying in 10s..."
  sleep 10
  if [ "$i" -eq 30 ]; then
    echo "ERROR: backend never became reachable at ${BACKEND_URL}/health" >&2
    exit 1
  fi
done

echo "=== 8/8: re-ingest eval corpus ==="
LOGIN_JSON="$(printf '{"username":"author","password":"%s"}' "$DEMO_AUTHOR_PASSWORD")"
TOKEN="$(curl -sf -X POST "${BACKEND_URL}/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$LOGIN_JSON" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")"

for f in eval/corpus/*; do
  echo "  ingesting $(basename "$f")..."
  curl -sf -X POST "${BACKEND_URL}/ingest" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@${f}" > /dev/null
done

echo ""
echo "=== Done ==="
echo "Frontend: http://${FRONTEND_HOST}"
echo "Backend:  ${BACKEND_URL}"
echo "Login:    author / ${DEMO_AUTHOR_PASSWORD}"
echo "          viewer / ${DEMO_VIEWER_PASSWORD}"
echo ""
echo "Save these credentials now -- they are not stored anywhere else."
