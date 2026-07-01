# PAIDIVER Brokerage Service API deployment

## Introduction

Brokerage Service API provides federated API access to multiple annotations APIs. It can be deployed to JASMIN or a local Kubernetes cluster using Helmfile.

The application source code and Helm charts are hosted under
https://github.com/paidiver/brokerage-service-api

These instructions guide you through deploying the application using Helm and Helmfile. They assume a Kubernetes cluster is already available and accessible.

Run the Helmfile commands below from the `deployment/helmfile/` directory.

---

## Contents

- [Prerequisites](#prerequisites)
- [Environments](#environments)
- [Initial Setup](#initial-setup)
- [Deploy](#deploy)
- [Deploy Locally](#deploy-locally)
- [Check The Deployment](#check-the-deployment)
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

The main deployment entrypoint is [helmfile/helmfile.yaml.gotmpl](helmfile/helmfile.yaml.gotmpl).

The configured JASMIN environments include:

- `dev`
- `live`

The local Kubernetes environment is:

- `local`

Environment-specific values live under `env/<environment>/values.yaml`.

For `dev`, Helmfile deploys into the configured namespace with `-dev` appended. For example, `paidiver-st3` becomes `paidiver-st3-dev`. The ClusterIssuer name also gets the same suffix.

For `live`, Helmfile uses the namespace and ClusterIssuer name exactly as configured in [helmfile/helmfile.yaml.gotmpl](helmfile/helmfile.yaml.gotmpl).

For `local`, Helmfile deploys to `brokerage-service-api-local`, disables ingress and image pull secrets, and skips the JASMIN secret and ClusterIssuer hooks.

---

## Initial Setup

### 1. Configure Environment Variables

Copy the example environment file in `deployment/helmfile/` and edit the values:

```bash
cp .env.example .env
```

Set the values required by [helmfile/helmfile.yaml.gotmpl](helmfile/helmfile.yaml.gotmpl) for JASMIN `dev` and `live` deployments:

- `RELEASE_NAME`: Helm release name, for example `brokerage-service-api`
- `CLUSTER_ISSUER_NAME`: base JASMIN ClusterIssuer name, for example `letsencrypt-brokerage-service-api`
- `GHCR_SECRET_NAME`: Kubernetes pull secret name, for example `brokerage-service-api-ghcr-pull-secret`
- `GHCR_USERNAME`: GitHub username or service account with GHCR access
- `GHCR_TOKEN`: GitHub token with permission to pull the GHCR image

Load the variables into your shell:

```bash
set -a
source .env
set +a
```

### 2. Select The Kubernetes Context

Export the JASMIN kubeconfig:

```bash
export KUBECONFIG="./kube_config_path.yaml"
```

Check that your shell is pointing at the intended cluster:

```bash
kubectl config get-contexts
```

Helmfile creates or updates the namespace, GHCR pull secret, and ClusterIssuer during the `presync` hook. If an old GHCR secret exists with an incompatible Kubernetes secret type, Helmfile recreates it. You do not need to apply [helmfile/utils/ghcr-pull-secret.yaml](helmfile/utils/ghcr-pull-secret.yaml) or [helmfile/utils/cluster-issuer.yaml](helmfile/utils/cluster-issuer.yaml) manually.

The local environment does not require these variables.

### 3. Update Helm Repositories and Docker Image Tag

```bash
helm repo add brokerage-service-api https://paidiver.github.io/brokerage-service-api
helm repo update
```

To list available chart versions:

```bash
helm search repo -l brokerage-service-api
```

Set the required `chartVersion` in [helmfile.yaml.gotmpl](helmfile.yaml.gotmpl).

Also set the `image.tag` in the releases values to the correct version.

---

## Deploy

Preview the changes:

```bash
helmfile -e <environment> diff
```

For example:

```bash
helmfile -e dev diff
```

Apply the selected environment:

```bash
helmfile -e dev apply
```

For live:

```bash
helmfile -e live diff
helmfile -e live apply
```

The `presync` hook runs as part of `apply`. It ensures the namespace exists, creates or updates the GHCR pull secret from your environment variables, recreates GHCR secrets when needed, and applies the JASMIN ClusterIssuer.

---

## Deploy Locally

Use this path for a local Kubernetes cluster such as kind or Minikube.

The local values file [helmfile/env/local/values.yaml](helmfile/env/local/values.yaml) uses a local image named `brokerage-service-api:local`, disables ingress, and does not configure an image pull secret.

- Build The Local Image

From `deployment/helmfile/`, build the image using the repository root as the Docker context:

```bash
docker build -f ../../docker/Dockerfile -t brokerage-service-api:local ../..
```

- Copy the image into your local Kubernetes cluster:

```bash
kind load docker-image brokerage-service-api:local
```

- Apply The Local Environment

```bash
helmfile -e local apply
```

- Check And Connect

```bash
kubectl get pods -n "$NAMESPACE"
kubectl get svc -n "$NAMESPACE"
kubectl port-forward -n "$NAMESPACE" svc/brokerage-service-api-service 8080:80
```

Health endpoint:

```text
http://localhost:8080/health/
```

API schema and documentation:

```text
http://localhost:8080/docs/
```

- Remove the local release:

```bash
helmfile -e local destroy
```

---

## Check The Deployment

For local:

```bash
kubectl get pods -n "$NAMESPACE"
kubectl get svc -n "$NAMESPACE"
```

For dev:

```bash
kubectl get pods -n "$NAMESPACE"-dev
kubectl get ingress -n "$NAMESPACE"-dev
```

For live:

```bash
kubectl get pods -n "$NAMESPACE"
kubectl get ingress -n "$NAMESPACE"
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
- Patches `deployment/charts/api/Chart.yaml` during packaging
- Packages the chart
- Publishes it via `helm/chart-releaser-action`

The source chart can keep a development version such as `0.0.0-dev`; published chart versions are derived from Git tags.

---
