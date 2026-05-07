param(
  [switch]$StopOnly,
  [switch]$SkipPortCleanup,
  [switch]$SafePortCleanup,
  [switch]$NoBrowser,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Resolve-Path (Join-Path $scriptDir "..\..")
$rootText = [string]$rootDir
$ports = @(
  5173,
  5174
) + (8000..8020)

function Write-Step($message) {
  Write-Host ""
  Write-Host "==> $message" -ForegroundColor Cyan
}

function Get-CommandLine($processId) {
  try {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId"
    return [string]$process.CommandLine
  } catch {
    return ""
  }
}

function Test-RepoProcess($processId) {
  $commandLine = Get-CommandLine $processId
  if ([string]::IsNullOrWhiteSpace($commandLine)) {
    return $false
  }

  if ($commandLine.Contains($rootText)) {
    return $true
  }

  return $commandLine -match "scripts[\\/]dev\.mjs|uvicorn app\.main:app|celery .*app\.celery_app|vite.*--port 5173"
}

function Stop-ProcessId($processId, $reason) {
  $processId = [int]$processId
  if ($processId -eq $PID) {
    return
  }

  $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
  if ($null -eq $process) {
    return
  }

  Write-Host "Stopping PID $processId ($($process.ProcessName)): $reason" -ForegroundColor Yellow
  if (-not $DryRun) {
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
  }
}

function Stop-RepoDevProcesses {
  Write-Step "Stopping old project dev processes"
  $patterns = @(
    "scripts[\\/]dev\.mjs",
    "npm.*run dev",
    "vite.*--port 5173",
    "uvicorn app\.main:app",
    "celery .*app\.celery_app"
  )

  $candidates = Get-CimInstance Win32_Process |
    Where-Object {
      $commandLine = [string]$_.CommandLine
      if ([string]::IsNullOrWhiteSpace($commandLine)) {
        return $false
      }
      if (-not $commandLine.Contains($rootText)) {
        return $false
      }
      foreach ($pattern in $patterns) {
        if ($commandLine -match $pattern) {
          return $true
        }
      }
      return $false
    } |
    Select-Object -ExpandProperty ProcessId -Unique

  foreach ($processId in $candidates) {
    Stop-ProcessId $processId "old project process"
  }
}

function Stop-ListeningPorts {
  if ($SkipPortCleanup) {
    Write-Step "Port cleanup skipped"
    return
  }

  Write-Step "Freeing project ports"
  foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
      $processId = [int]$connection.OwningProcess
      if ($processId -le 0) {
        continue
      }

      if ($SafePortCleanup -and -not (Test-RepoProcess $processId)) {
        $commandLine = Get-CommandLine $processId
        Write-Host "Port $port is busy by PID $processId, but it is not repo-scoped. Skipping. Command: $commandLine" -ForegroundColor DarkYellow
        continue
      }

      Stop-ProcessId $processId "port $port"
    }
  }
}

function Start-BrowserWatcher {
  if ($NoBrowser -or $DryRun -or $StopOnly) {
    return
  }

  $watcherCommand = @"
for (`$i = 0; `$i -lt 60; `$i += 1) {
  try {
    `$response = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 2
    if (`$response.StatusCode -ge 200 -and `$response.StatusCode -lt 500) {
      Start-Process 'http://127.0.0.1:5173'
      break
    }
  } catch {
    Start-Sleep -Seconds 2
  }
}
"@

  Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-WindowStyle",
    "Hidden",
    "-Command",
    $watcherCommand
  ) -WindowStyle Hidden | Out-Null
}

Set-Location $rootDir

Write-Host "SEO Audit local launcher" -ForegroundColor Green
Write-Host "Project: $rootDir"

Stop-RepoDevProcesses
Start-Sleep -Milliseconds 500
Stop-ListeningPorts

if ($StopOnly) {
  Write-Step "Stopped. You can close this window."
  if (-not $DryRun) {
    Read-Host "Press Enter to close"
  }
  exit 0
}

Write-Step "Starting Docker/SearXNG, backend, frontend and Celery workers"
Write-Host "Frontend will open at http://127.0.0.1:5173 when it becomes ready." -ForegroundColor Green
Write-Host "Keep this window open while you use the site. Press Ctrl+C to stop the stack." -ForegroundColor Green

Start-BrowserWatcher

if ($DryRun) {
  Write-Host "Dry run: npm run dev:full"
  exit 0
}

npm run dev:full
