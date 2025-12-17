param(
    [int64]$RunId = 20292462582,
    [string]$Repo = 'atpx4869/Multi-source-downloader',
    [int]$MaxChecks = 120,
    [int]$IntervalSec = 10
)

for($i=1; $i -le $MaxChecks; $i++){
    $status = gh run view $RunId --repo $Repo --json status,conclusion --jq '.status' 2>$null
    Write-Host "[poll $i] status=$status"
    if($status -ne 'in_progress' -and $status -ne 'queued'){
        break
    }
    Start-Sleep -Seconds $IntervalSec
}

# show final summary
gh run view $RunId --repo $Repo --json status,conclusion,workflowName,createdAt --jq '. | {status:.status,conclusion:.conclusion,workflow:.workflowName,created:.createdAt}'
