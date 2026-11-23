# Read-only local kind staging verification; makes no cluster mutations or alerts.
[CmdletBinding()]
param(
    [ValidatePattern('^[a-z0-9][a-z0-9-]{5,39}$')]
    [string]$DrillId = ''
)

$ErrorActionPreference = 'Stop'
$cluster = 'logsight-staging-alerts'
$context = "kind-$cluster"
$namespace = 'logsight-staging'

function Read-KubectlJson {
    param([string[]]$KubectlArgs)
    $raw = & kubectl --context $context -n $namespace @KubectlArgs -o json
    if ($LASTEXITCODE -ne 0) {
        throw "kubectl read failed (context=$context). Check local cluster status."
    }
    return ($raw | Out-String | ConvertFrom-Json)
}

foreach ($name in @('kind', 'kubectl')) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $name"
    }
}

$clusters = @(& kind get clusters)
if ($LASTEXITCODE -ne 0 -or $clusters -notcontains $cluster) {
    throw "Dedicated local kind cluster '$cluster' is unavailable. No alternate context will be inspected."
}

$deployments = @('staging-alertmanager', 'staging-receiver')
$services = @('staging-alertmanager', 'staging-receiver')
$results = @()

foreach ($name in $deployments) {
    $deployment = Read-KubectlJson -KubectlArgs @('get', 'deployment', $name)
    $desired = [int]$deployment.spec.replicas
    $ready = [int]$deployment.status.readyReplicas
    $updated = [int]$deployment.status.updatedReplicas
    $observed = [int]$deployment.status.observedGeneration
    $generation = [int]$deployment.metadata.generation
    $healthy = ($desired -eq 1 -and $ready -eq 1 -and $updated -eq 1 -and $observed -ge $generation)
    $results += [pscustomobject]@{
        resource = "deployment/$name"
        healthy = $healthy
        desired = $desired
        ready = $ready
        updated = $updated
    }
}

foreach ($name in $services) {
    $service = Read-KubectlJson -KubectlArgs @('get', 'service', $name)
    $internal = ($service.spec.type -eq 'ClusterIP' -and [string]::IsNullOrEmpty($service.spec.externalName))
    $results += [pscustomobject]@{
        resource = "service/$name"
        healthy = $internal
        desired = $null
        ready = $null
        updated = $null
    }
}

$allHealthy = @($results | Where-Object { -not $_.healthy }).Count -eq 0
$receiptObserved = $false

if ($DrillId) {
    # Only inspect a localhost port-forward that the operator started separately.
    # This is a memory-only webhook receipt, NOT a human acknowledgment.
    try {
        $reply = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/receipts' -Method Get -TimeoutSec 5
        $receiptObserved = @($reply.receipts | Where-Object { $_.drill_id -eq $DrillId }).Count -gt 0
    }
    catch {
        throw 'Local receiver is unavailable. Start the localhost-only port-forward first.'
    }
}

[pscustomobject]@{
    context = $context
    namespace = $namespace
    status = $(if ($allHealthy) { 'pass' } else { 'fail' })
    resources = $results
    receipt_checked = [bool]$DrillId
    receipt_observed = $receiptObserved
    external_delivery_verified = $false
    human_acknowledgment_verified = $false
} | ConvertTo-Json -Depth 6

if (-not $allHealthy -or ($DrillId -and -not $receiptObserved)) {
    exit 1
}
exit 0
