# PAIDIVER Brokerage Service API deployment

## Introduction

Brokerage Service API provides a federated api access to multiple services.

The application source code and Helm charts are hosted under
https://github.com/paidiver/brokerage-service-api

These instructions guide you through deploying the application using Helm and Helmfile. They assume a Kubernetes cluster is already available and accessible.

---

## Contents

- [Prerequisites](#prerequisites)
- [Environments](#environments)
- [Initial Setup](#initial-setup)
- [Deploy](#deploy)
- [Check The Deployment](#check-the-deployment)
- [Upgrade](#upgrade)
- [Chart Releases](#chart-releases)

---

## Prerequisites

Install these tools before deploying:

- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)
- [Helmfile](https://github.com/helmfile/helmfile)
- [helm-diff](https://github.com/databus23/helm-diff)
- Git Bash, Linux shell, or another shell that can run the commands below

Docker is only required if you are building images locally. Normal deployments pull published images from GHCR.

---

## Environments

The main deployment entrypoint is [helmfile.yaml.gotmpl](helmfile.yaml.gotmpl).

The configured environments include:

- `dev`
- `live`

Environment-specific values live under `env/<environment>/values/values.yaml`.

---

## Initial Setup

### 1. Configure Environment Variables

Copy the example environment file and edit the values:

```bash
cp .env.example .env
```

The secret values are stored in 1Password:

- `GHCR_TOKEN`: `DSG_BODC_EXTERNAL_TOOLS`, "GitHub Container Registry access for Paidiver Worms Cache API"
- `POSTGRES_PASSWORD`: `DSG_BODC_GENERIC`, "PAIDIVER Postgres worms-cache user password"
- `POSTGRES_SUPERUSER_PASSWORD`: `DSG_BODC_GENERIC`, "PAIDIVER Postgres worms-cache admin user password"
- `DJANGO_SECRET_KEY`: `DSG_BODC_GENERIC`, "PAIDIVER Django secret key"
- `CACHED_WORMS_API_TOKEN`: `DSG_BODC_GENERIC`, "PAIDIVER WORMS API Cache Token"


Load the variables into your shell:

```bash
set -a
source .env
set +a
```

### 2. Select The Kubernetes Context

When deploying to the BODC clusters, you will need two contexts to be stored in KUBECONFIG. First, store your two kubeconfigs in seperate files (e.g. livhydra-staging-1-kubeconfig and livkraken-staging-1-kubeconfig).

Next, export the kubeconfigs with:

```bash
export KUBECONFIG="./kube_config_path.yaml"
```

Check that your shell is pointing at the intended cluster:

```bash
kubectl config get-contexts
```

On the BODC clusters, this should return two lines.

Check that the namespace is reachable:

```bash
kubectl get pods -n "$NAMESPACE"
```

**For local deployments only**, create the namespace if it does not already exist:

```bash
kubectl create namespace "$NAMESPACE"
```

BODC cluster namespaces and quotas are managed outside this repository within OpenTofu.

### 3. Create Required Secrets

Check the existing secrets first:

```bash
kubectl get secrets -n "$NAMESPACE"
```

Create the GHCR pull secret:

```bash
ghcr_secret_template=$(sed -e "s/{{NAMESPACE}}/$NAMESPACE/g" -e "s/{{GHCR_SECRET_NAME}}/$GHCR_SECRET_NAME/g" -e "s/{{GHCR_USERNAME}}/$GHCR_USERNAME/g" -e "s/{{GHCR_TOKEN}}/$GHCR_TOKEN/g" utils/ghcr-pull-secret.yaml)

echo "$ghcr_secret_template" | kubectl apply -f -
```

Confirm the required secrets exist:

```bash
kubectl get secrets -n "$NAMESPACE"
```

### 4. Create The JASMIN Cluster Issuer

**This step is required ONLY for JASMIN deployments that use TLS via cert-manager.**

```bash
cluster_issuer_template=$(sed -e "s/{{NAMESPACE}}/$NAMESPACE/g" -e "s/{{CLUSTER_ISSUER_NAME}}/$CLUSTER_ISSUER_NAME/g" utils/cluster-issuer.yaml)

echo "$cluster_issuer_template" | kubectl apply -f -
```

Check it:

```bash
kubectl get clusterissuer
```

### 5. Update Helm Repositories


```bash
helm repo add brokerage-service-api https://paidiver.github.io/brokerage-service-api
helm repo update
```

To list available chart versions:

```bash
helm search repo -l brokerage-service-api
```

Set the required `chartVersion` in [helmfile.yaml.gotmpl](helmfile.yaml.gotmpl).

---

## Deploy

Preview the changes:

```bash
helmfile -e <environment> diff
```

For example:

```bash
helmfile -e jasmin diff
```

### Deploy to JASMIN

For JASMIN, deploy PostgreSQL first and wait for it to become ready. The API release has init containers and migration hooks that wait for PostgreSQL.

```bash
helmfile -e jasmin apply --selector name=postgres-annotations-api
```

Then deploy the remaining releases:

```bash
helmfile -e jasmin apply
```

### Deploy to BODC clusters

To deploy to the BODC clusters, you need to deploy to Kraken and Hydra separately. Kraken holds the PostgreSQL and the FRPC tunnel which connects PostgreSQL to the INT servers. Deploy to Kraken with:
```bash
helmfile -e livkraken-staging-1 apply
```

Confirm that the FRPC tunnel is connected properly and that PostgreSQL has started through the logs.

Once FRPC and PostgreSQL are working, you can deploy the WORMS Cache API to Hydra by running:

```bash
helmfile -e livhydra-staging-1 apply
```

---

## Check The Deployment

Check all pods:

```bash
kubectl get pods -n "$NAMESPACE"
```
You should see the pods related to the environment you deployed, including the PostgreSQL pod and the API pods.

---

## Connect To Postgres

Forward the PostgreSQL service to your local machine:

```bash
kubectl port-forward -n "$NAMESPACE" svc/postgres-postgresql 5432:5432
```

Keep that terminal open while you connect with DBeaver, or `psql`.

Use:

- Host: `localhost` or `livbodcinttst.bodc.me`
- Port: `5433`
- Database: value of `POSTGRES_DB`
- Username: value of `POSTGRES_USER`
- Password: value of `POSTGRES_PASSWORD`

To inspect the generated PostgreSQL Secret:

```bash
kubectl get secret -n "$NAMESPACE" postgres-postgresql -o yaml
```

To decode the normal user password:

```bash
kubectl get secret -n "$NAMESPACE" postgres-postgresql -o jsonpath='{.data.password}' | base64 --decode
```

To decode the admin password:

```bash
kubectl get secret -n "$NAMESPACE" postgres-postgresql -o jsonpath='{.data.postgres-password}' | base64 --decode
```

---

## Chart Releases

The API chart is released from the application repository via Git tags.

To release a new chart, create a tag in this format:

```text
vMAJOR.MINOR.PATCH[-PRERELEASE]
```

Examples:

- `v1.2.3`
- `v1.3.0-alpha.1`

The release workflow:

- Reads the version from the Git tag
- Patches `charts/api/Chart.yaml` during packaging
- Packages the chart
- Publishes it via `helm/chart-releaser-action`

The source chart can keep a development version such as `0.0.0-dev`; published chart versions are derived from Git tags.

---
