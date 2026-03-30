$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bunPath = Join-Path $repoRoot '.agents\tools\bun\bin\bun.exe'
$gstackRoot = Join-Path $repoRoot '.agents\skills\gstack'
$nestedGitPath = Join-Path $gstackRoot '.git'
$requiredSkills = @(
  '.agents\skills\gstack-office-hours\SKILL.md',
  '.agents\skills\gstack-plan-ceo-review\SKILL.md',
  '.agents\skills\gstack-plan-eng-review\SKILL.md',
  '.agents\skills\gstack-plan-design-review\SKILL.md',
  '.agents\skills\gstack-review\SKILL.md',
  '.agents\skills\gstack-qa\SKILL.md',
  '.agents\skills\gstack-ship\SKILL.md',
  '.agents\skills\gstack-retro\SKILL.md',
  '.agents\skills\gstack-codex\SKILL.md'
)

$errors = 0

Write-Host '== gstack doctor ==' -ForegroundColor Cyan

if (Test-Path $bunPath) {
  $bunVersion = & $bunPath --version
  Write-Host "bun: $bunVersion ($bunPath)" -ForegroundColor Green
} else {
  Write-Host "bun missing: $bunPath" -ForegroundColor Red
  $errors++
}

if (Test-Path $gstackRoot) {
  Write-Host "gstack source: OK ($gstackRoot)" -ForegroundColor Green
} else {
  Write-Host "gstack source missing: $gstackRoot" -ForegroundColor Red
  $errors++
}

if (Test-Path $nestedGitPath) {
  Write-Host "nested git metadata still present: $nestedGitPath" -ForegroundColor Yellow
} else {
  Write-Host 'nested git metadata: removed' -ForegroundColor Green
}

foreach ($skill in $requiredSkills) {
  $absolute = Join-Path $repoRoot $skill
  if (Test-Path $absolute) {
    Write-Host "skill: OK ($skill)" -ForegroundColor Green
  } else {
    Write-Host "skill missing: $skill" -ForegroundColor Red
    $errors++
  }
}

if ($errors -eq 0) {
  Write-Host 'gstack repo-local install looks ready for Codex-oriented workflows.' -ForegroundColor Green
} else {
  Write-Host "gstack doctor found $errors issue(s)." -ForegroundColor Red
}

exit $errors
