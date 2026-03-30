param(
  [ValidateSet('codex')]
  [string]$TargetHost = 'codex'
)

function Convert-ToGitBashPath {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PathValue
  )

  $resolved = (Resolve-Path $PathValue).Path
  $drive = $resolved.Substring(0, 1).ToLowerInvariant()
  $rest = $resolved.Substring(2).Replace('\', '/')
  return "/$drive$rest"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bunPath = Join-Path $repoRoot '.agents\tools\bun\bin\bun.exe'
$gstackRoot = Join-Path $repoRoot '.agents\skills\gstack'
$generatedRoot = Join-Path $gstackRoot '.agents\skills'
$publishedRoot = Join-Path $repoRoot '.agents\skills'
$gitBashCandidates = @(
  'C:\Program Files\Git\bin\bash.exe',
  'C:\Program Files\Git\usr\bin\bash.exe'
)
$gitBash = $gitBashCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not (Test-Path $bunPath)) {
  Write-Error "Repo-local bun not found at $bunPath"
  exit 1
}

if (-not (Test-Path $gstackRoot)) {
  Write-Error "Repo-local gstack not found at $gstackRoot"
  exit 1
}

if (-not $gitBash) {
  Write-Error 'Git Bash was not found. Install Git for Windows so gstack refresh can regenerate Codex skills.'
  exit 1
}

$gstackBashPath = Convert-ToGitBashPath -PathValue $gstackRoot
$bunBashPath = Convert-ToGitBashPath -PathValue $bunPath
$bashCommand = "cd '$gstackBashPath' && '$bunBashPath' run gen:skill-docs --host $TargetHost"

& $gitBash -lc $bashCommand
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

if (-not (Test-Path $generatedRoot)) {
  Write-Error "Generated skill directory not found at $generatedRoot"
  exit 1
}

Get-ChildItem -LiteralPath $generatedRoot -Directory | ForEach-Object {
  if ($_.Name -eq 'gstack') {
    Write-Host 'published skill: gstack (source checkout already lives at .agents/skills/gstack)' -ForegroundColor Yellow
    return
  }

  $destination = Join-Path $publishedRoot $_.Name
  if (Test-Path $destination) {
    Remove-Item -LiteralPath $destination -Recurse -Force
  }

  Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse
  Write-Host "published skill: $($_.Name)" -ForegroundColor Green
}

$codexSource = Join-Path $gstackRoot 'codex'
$codexAlias = Join-Path $publishedRoot 'gstack-codex'
if (Test-Path $codexSource) {
  if (Test-Path $codexAlias) {
    Remove-Item -LiteralPath $codexAlias -Recurse -Force
  }

  Copy-Item -LiteralPath $codexSource -Destination $codexAlias -Recurse
  $codexAgentsDir = Join-Path $codexAlias 'agents'
  New-Item -ItemType Directory -Path $codexAgentsDir -Force | Out-Null
  @'
interface:
  display_name: "gstack-codex"
  short_description: "Use Codex as an independent second opinion for review, challenge, or consultation."
  default_prompt: "Use gstack-codex for this task."
policy:
  allow_implicit_invocation: true
'@ | Set-Content -LiteralPath (Join-Path $codexAgentsDir 'openai.yaml')
  Write-Host 'published skill: gstack-codex' -ForegroundColor Green
}

Write-Host 'gstack Codex skills refreshed into repo-local .agents/skills.' -ForegroundColor Green
