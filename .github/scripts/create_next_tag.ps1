param(
    [string]$remote = 'origin'
)

Write-Output "Fetching tags from $remote..."
git fetch --tags $remote

$latest = git tag --sort=-v:refname | Select-String '^v' | Select-Object -First 1
if ($latest) { $latest = $latest.ToString().Trim() } else { $latest='v0.0.0' }

if ($latest -match '^v(\d+)\.(\d+)\.(\d+)$') {
    $major=[int]$matches[1]; $minor=[int]$matches[2]; $patch=[int]$matches[3]+1
    $new = "v$major.$minor.$patch"
} else { $new='v1.0.0' }

Write-Output "Latest: $latest -> New: $new"

git tag -a $new -m "Release $new"
Write-Output "Pushing tag $new to $remote..."
git push $remote $new
Write-Output "Done: pushed $new"