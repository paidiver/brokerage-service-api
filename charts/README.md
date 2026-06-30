# PAIDIVER Brokerage Service API deployment

## Introduction

Brokerage Service API provides a federated api access to multiple annotations apis. It is deployed to JASMIN using Helm and Helmfile.

The application source code and Helm charts are hosted under
https://github.com/paidiver/brokerage-service-api

These instructions guide you through deploying the application to JASMIN using Helm and Helmfile. They assume a Kubernetes cluster is already available and accessible.

Run the commands below from the `charts/` directory.

---

## Contents

- [Prerequisites](#prerequisites)
- [Environments](#environments)
- [Initial Setup](#initial-setup)
- [Deploy](#deploy)
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

The main deployment entrypoint is [helmfile.yaml.gotmpl](helmfile.yaml.gotmpl).

The configured JASMIN environments include:

- `dev`
- `live`

Environment-specific values live under `env/<environment>/values.yaml`.

For `dev`, Helmfile deploys into the configured namespace with `-dev` appended. For example, `paidiver-st3` becomes `paidiver-st3-dev`. The ClusterIssuer name also gets the same suffix.

For `live`, Helmfile uses the namespace and ClusterIssuer name exactly as configured in [helmfile.yaml.gotmpl](helmfile.yaml.gotmpl).

---

## Initial Setup

### 1. Configure Environment Variables

Copy the example environment file in the `/charts` path and edit the values:

```bash
cp .env.example .env
```

Set the values required by [helmfile.yaml.gotmpl](helmfile.yaml.gotmpl):

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

Helmfile creates or updates the namespace, GHCR pull secret, and ClusterIssuer during the `presync` hook. If an old GHCR secret exists with an incompatible Kubernetes secret type, Helmfile recreates it. You do not need to apply [utils/ghcr-pull-secret.yaml](utils/ghcr-pull-secret.yaml) or [utils/cluster-issuer.yaml](utils/cluster-issuer.yaml) manually.

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

## Check The Deployment

For dev:

```bash
kubectl get pods -n paidiver-st3-dev
kubectl get ingress -n paidiver-st3-dev
```

For live:

```bash
kubectl get pods -n paidiver-st3
kubectl get ingress -n paidiver-st3
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
