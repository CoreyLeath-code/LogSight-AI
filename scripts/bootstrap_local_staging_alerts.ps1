# Windows-native, dry-run-by-default kind staging bootstrap.
# This script only creates a new local kind cluster with an in-memory test receiver.
[CmdletBinding()]
param(
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
$cluster = 'logsight-staging-alerts'
$context = "kind-$cluster"
$namespace = 'logsight-staging'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not $Execute) {
    Write-Output "PLAN ONLY: create a NEW local kind cluster '$cluster' with an internal-only test Alertmanager and memory-only webhook receiver."
    Write-Output 'Prerequisites: Docker Desktop (Linux containers), kind, kubectl.'
    Write-Output 'This does NOT send an alert, use cloud Kubernetes, or create a human acknowledgment.'
    Write-Output 'To create it explicitly: .\scripts\bootstrap_local_staging_alerts.ps1 -Execute'
    exit 0
}

foreach ($tool in @('docker', 'kind', 'kubectl')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $tool"
    }
}

& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker engine is unavailable. Start Docker Desktop in Linux containers mode.'
}

$existing = @(& kind get clusters)
if ($LASTEXITCODE -ne 0) {
    throw 'Cannot list kind clusters; refusing to create staging.'
}
if ($existing -contains $cluster) {
    throw "Cluster '$cluster' already exists. Refusing to alter or recreate it."
}

$config = Join-Path $repoRoot 'deploy/staging/kind-config.yaml'
$manifest = Join-Path $repoRoot 'deploy/staging/kind-alerts.yaml'
$receiver = Join-Path $repoRoot 'scripts/staging_test_receiver.py'
foreach ($file in @($config, $manifest, $receiver)) {
    if (-not (Test-Path -PathType Leaf $file)) {
        throw "Missing repository file: $file"
    }
}

& kind create cluster --name $cluster --config $config
if ($LASTEXITCODE -ne 0) {
    throw 'Could not create isolated local kind cluster.'
}

& kubectl --context $context apply -f $manifest
if ($LASTEXITCODE -ne 0) {
    throw 'Staging manifests failed. Inspect the newly created local cluster.'
}

& kubectl --context $context -n $namespace create configmap staging-receiver-code "--from-file=staging_test_receiver.py=$receiver"
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to create local synthetic receiver code ConfigMap.'
}

foreach ($deployment in @('staging-receiver', 'staging-alertmanager')) {
    & kubectl --context $context -n $namespace rollout status "deployment/$deployment" --timeout=180s
    if ($LASTEXITCODE -ne 0) {
        throw "Staging deployment '$deployment' did not become ready."
    }
}

Write-Output 'Local kind rehearsal resources are ready for operator verification.'
Write-Output "kubectl --context $context -n $namespace get pods"
Write-Output "kubectl --context $context -n $namespace port-forward --address 127.0.0.1 svc/staging-alertmanager 9093:9093"
Write-Output "kubectl --context $context -n $namespace port-forward --address 127.0.0.1 svc/staging-receiver 8080:8080"
Write-Output 'No real alert sent, no actual on-call recipient contacted, no human acknowledgment recorded.'
