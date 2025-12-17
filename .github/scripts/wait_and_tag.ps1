$repoUrl='https://api.github.com/repos/atpx4869/Multi-source-downloader/releases/tags/v1.1.3'
$found=$false
for ($i=0; $i -lt 12; $i++) {
    try {
        Invoke-RestMethod -Uri $repoUrl -ErrorAction Stop | Out-Null
        Write-Output "FOUND"
        $found=$true
        break
    } catch {
        Write-Output "Not found yet ($i)"
        Start-Sleep -Seconds 15
    }
}
if (-not $found) {
    Write-Output "Timeout: release v1.1.3 not found"
    exit 2
}
Write-Output "Release exists — creating next tag"
$latestTag = git tag --sort=-v:refname | Select-String -Pattern '^v' | Select-Object -First 1
if ($latestTag) { $latestTag = $latestTag.ToString().Trim() } else { $latestTag='v0.0.0' }
if ($latestTag -match '^v(\d+)\.(\d+)\.(\d+)$') {
    $major=[int]$matches[1]; $minor=[int]$matches[2]; $patch=[int]$matches[3]+1
    $newTag="v$major.$minor.$patch"
} else { $newTag='v1.0.0' }
Write-Output "New tag: $newTag"
git tag -a $newTag -m "Release $newTag"
git push origin $newTag
