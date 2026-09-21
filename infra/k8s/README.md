# DynaFare Kubernetes Deployment Guide

## Prerequisites
- A running Kubernetes cluster (GKE, EKS, or local k3s/minikube)
- `kubectl` configured against your cluster
- Docker images built and pushed to GHCR (the CI/CD pipeline handles this on merge to `main`)

## Quick Deploy (dev)

```bash
# 1. Apply all manifests in order
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/secrets.yaml
kubectl apply -f infra/k8s/configmaps.yaml
kubectl apply -f infra/k8s/infrastructure.yaml
kubectl apply -f infra/k8s/kafka.yaml

# 2. Wait for stateful services to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n dynafare-dev --timeout=120s
kubectl wait --for=condition=ready pod -l app=redis -n dynafare-dev --timeout=60s
kubectl wait --for=condition=ready pod -l app=kafka -n dynafare-dev --timeout=120s

# 3. Deploy application services
kubectl apply -f infra/k8s/api-service.yaml
kubectl apply -f infra/k8s/ml-service.yaml
kubectl apply -f infra/k8s/nginx.yaml

# 4. Check rollout
kubectl rollout status deployment/api-service -n dynafare-dev
kubectl rollout status deployment/ml-service -n dynafare-dev
```

## Replace Secrets for Production

Before deploying to production, replace the base64-encoded placeholder values in `secrets.yaml` with real values, or use an external secrets manager:

```bash
# Example: update JWT_SECRET
kubectl create secret generic dynafare-secrets \
  --from-literal=JWT_SECRET='<real-secret>' \
  --from-literal=SPRING_DATASOURCE_PASSWORD='<real-db-password>' \
  --namespace dynafare-prod \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Rollback

```bash
kubectl rollout undo deployment/api-service -n dynafare-dev
kubectl rollout undo deployment/ml-service -n dynafare-dev
```
