param(
  [string]$VercelUrl = "https://seo-audit-diplom.vercel.app",
  [string]$Alias = "seo-audit-diplom.vercel.app",
  [int]$BackendPort = 8000,
  [switch]$NoBrowser,
  [switch]$NoPause,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Resolve-Path (Join-Path $scriptDir "..\..")
$frontendDir = Join-Path $rootDir "frontend"
$outputDir = Join-Path $rootDir "output"
$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$stackOut = Join-Path $outputDir "public-stack-$runId.out.log"
$stackErr = Join-Path $outputDir "public-stack-$runId.err.log"
$tunnelOut = Join-Path $outputDir "public-tunnel-$runId.out.log"
$tunnelErr = Join-Path $outputDir "public-tunnel-$runId.err.log"

function Write-Step($message) {
  Write-Host ""
  Write-Host "==> $message" -ForegroundColor Cyan
}

function Wait-HttpReady($url, $label, $attempts = 90) {
  for ($i = 0; $i -lt $attempts; $i += 1) {
    try {
      $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        Write-Host "$label ready: $url" -ForegroundColor Green
        return
      }
    } catch {
      Start-Sleep -Seconds 2
    }
  }
  throw "$label did not become ready: $url"
}

function Wait-TunnelUrl($path, $attempts = 45) {
  for ($i = 0; $i -lt $attempts; $i += 1) {
    if (Test-Path $path) {
      $content = [string](Get-Content -Path $path -Raw -ErrorAction SilentlyContinue)
      $match = [regex]::Match($content, "https://[a-zA-Z0-9.-]+\.(?:lhr\.life|loca\.lt)")
      if ($match.Success) {
        return $match.Value
      }
    }
    Start-Sleep -Seconds 2
  }
  throw "Tunnel URL was not found in $path"
}

function Stop-PublicTunnelProcesses {
  $candidates = Get-CimInstance Win32_Process |
    Where-Object {
      $commandLine = [string]$_.CommandLine
      $commandLine -match "localtunnel|lt\.js|lt --port|localhost\.run"
    } |
    Select-Object -ExpandProperty ProcessId -Unique

  foreach ($processId in $candidates) {
    if ([int]$processId -ne $PID) {
      Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
  }
}

function Start-LocalTunnel($port, $attempts = 4) {
  for ($attempt = 1; $attempt -le $attempts; $attempt += 1) {
    Write-Host "Tunnel attempt $attempt/$attempts" -ForegroundColor DarkCyan
    Stop-PublicTunnelProcesses
    Start-Sleep -Seconds 1

    $attemptOut = $tunnelOut.Replace(".out.log", "-attempt$attempt.out.log")
    $attemptErr = $tunnelErr.Replace(".err.log", "-attempt$attempt.err.log")
    Start-Process -FilePath "npx.cmd" -ArgumentList @(
      "-y",
      "localtunnel",
      "--port",
      "$port",
      "--local-host",
      "127.0.0.1"
    ) -RedirectStandardOutput $attemptOut -RedirectStandardError $attemptErr -WindowStyle Hidden | Out-Null

    try {
      $candidateUrl = Wait-TunnelUrl $attemptOut 30
      Wait-HttpReady "$candidateUrl/health/live" "Tunnel" 45
      Wait-HttpReady "$candidateUrl/audits" "Tunnel API" 12
      return $candidateUrl
    } catch {
      Write-Host "Tunnel attempt failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
  }

  throw "Could not start a stable public tunnel after $attempts attempts."
}

function Wait-BackendPort($stdoutPath, $stderrPath, $fallbackPort, $attempts = 60) {
  for ($i = 0; $i -lt $attempts; $i += 1) {
    $content = ""
    foreach ($path in @($stdoutPath, $stderrPath)) {
      if (Test-Path $path) {
        $content += "`n" + (Get-Content -Path $path -Raw -ErrorAction SilentlyContinue)
      }
    }

    if (-not [string]::IsNullOrWhiteSpace($content)) {
      $match = [regex]::Match($content, "Backend API:\s+http://127\.0\.0\.1:(\d+)")
      if ($match.Success) {
        return [int]$match.Groups[1].Value
      }
      $uvicornMatch = [regex]::Match($content, "Uvicorn running on http://127\.0\.0\.1:(\d+)")
      if ($uvicornMatch.Success) {
        return [int]$uvicornMatch.Groups[1].Value
      }
    }

    try {
      $response = Invoke-WebRequest -Uri "http://127.0.0.1:$fallbackPort/health/ready" -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $fallbackPort
      }
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  throw "Could not detect backend port from $stdoutPath / $stderrPath"
}

function Invoke-CmdChecked($command, $label, [switch]$AllowFailure) {
  Push-Location $frontendDir
  $previousErrorActionPreference = $ErrorActionPreference
  try {
    Write-Host $command -ForegroundColor DarkGray
    $ErrorActionPreference = "Continue"
    $output = & cmd.exe /d /s /c $command 2>&1
    $exitCode = $LASTEXITCODE
    if ($output) {
      $output | ForEach-Object { Write-Host $_ }
    }
    if ($exitCode -ne 0 -and -not $AllowFailure) {
      throw "$label failed with exit code $exitCode"
    }
    return ($output -join "`n")
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Pop-Location
  }
}

Set-Location $rootDir
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

Write-Host "SEO Audit public Vercel launcher" -ForegroundColor Green
Write-Host "Project: $rootDir"
Write-Host "Public URL: $VercelUrl"

Write-Step "Stopping old local stack and old tunnel"
if (-not $DryRun) {
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $scriptDir "start-site.ps1") -StopOnly -NoPause
}

Write-Step "Starting local stack with Vercel CORS"

if (-not $DryRun) {
  $stackEnv = "Set-Location '$rootDir'; `$env:CORS_ALLOW_ORIGINS='$VercelUrl'; npm run dev:full"
  Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    $stackEnv
  ) -RedirectStandardOutput $stackOut -RedirectStandardError $stackErr -WindowStyle Hidden | Out-Null
}

if ($DryRun) {
  Write-Host "Dry run: would start stack with CORS_ALLOW_ORIGINS=$VercelUrl"
  Write-Host "Dry run: would create localtunnel tunnel to port $BackendPort"
  Write-Host "Dry run: would update Vercel VITE_API_URL and deploy production"
  exit 0
}

$actualBackendPort = Wait-BackendPort $stackOut $stackErr $BackendPort
Wait-HttpReady "http://127.0.0.1:$actualBackendPort/health/ready" "Backend"
Write-Host "Backend port: $actualBackendPort" -ForegroundColor Green

Write-Step "Opening public tunnel to backend"
$tunnelUrl = Start-LocalTunnel $actualBackendPort
Set-Content -Path (Join-Path $outputDir "vercel-api-url.txt") -Value $tunnelUrl -Encoding UTF8

Write-Step "Checking tunnel CORS"
$corsHeaders = @{
  Origin = $VercelUrl
  "Access-Control-Request-Method" = "POST"
  "Access-Control-Request-Headers" = "accept,bypass-tunnel-reminder,content-type,ngrok-skip-browser-warning"
}
$cors = Invoke-WebRequest -Uri "$tunnelUrl/audits" -Method OPTIONS -Headers $corsHeaders -UseBasicParsing -TimeoutSec 20
if ($cors.StatusCode -ne 200 -or $cors.Headers["Access-Control-Allow-Origin"] -ne $VercelUrl) {
  throw "Tunnel is reachable, but CORS is not configured for $VercelUrl"
}

Write-Step "Updating Vercel VITE_API_URL"
Invoke-CmdChecked "npx vercel env rm VITE_API_URL production --yes" "Remove VITE_API_URL" -AllowFailure | Out-Null
Invoke-CmdChecked "powershell -NoProfile -Command `"Write-Output '$tunnelUrl'`" | npx vercel env add VITE_API_URL production" "Add VITE_API_URL" | Out-Null

Write-Step "Deploying frontend to Vercel production"
$deployOutput = Invoke-CmdChecked "npx vercel --prod --yes" "Vercel production deploy"
$deploymentMatch = [regex]::Match($deployOutput, "https://frontend-[a-zA-Z0-9-]+\.vercel\.app")
if (-not $deploymentMatch.Success) {
  throw "Could not find deployment URL in Vercel output."
}
$deploymentUrl = $deploymentMatch.Value

Write-Step "Assigning stable alias"
Invoke-CmdChecked "npx vercel alias set $deploymentUrl $Alias" "Assign Vercel alias" | Out-Null

Write-Step "Public site is ready"
Write-Host "Frontend: $VercelUrl" -ForegroundColor Green
Write-Host "Backend tunnel: $tunnelUrl" -ForegroundColor Green
Write-Host "Local frontend: http://127.0.0.1:5173" -ForegroundColor Green

Write-Step "Verifying deployed frontend uses the current backend"
try {
  $html = Invoke-WebRequest -Uri $VercelUrl -UseBasicParsing -TimeoutSec 30
  $assetMatch = [regex]::Match($html.Content, "/assets/index-[^`"`']+\.js")
  if ($assetMatch.Success) {
    $assetUrl = "$VercelUrl$($assetMatch.Value)"
    $bundle = Invoke-WebRequest -Uri $assetUrl -UseBasicParsing -TimeoutSec 30
    if ($bundle.Content.Contains($tunnelUrl)) {
      Write-Host "Verified: Vercel bundle points to $tunnelUrl" -ForegroundColor Green
    } else {
      Write-Host "Warning: Vercel opened, but the JS bundle does not contain $tunnelUrl yet. Wait a minute and refresh." -ForegroundColor Yellow
    }
  } else {
    Write-Host "Warning: could not find frontend JS bundle for verification." -ForegroundColor Yellow
  }
} catch {
  Write-Host "Warning: public frontend verification failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Do not close this computer/session while people use Vercel: the backend runs here." -ForegroundColor Yellow
Write-Host "Use Stop SEO Audit.cmd to stop local stack and tunnel." -ForegroundColor Yellow

if (-not $NoBrowser) {
  Start-Process $VercelUrl
}

if (-not $NoPause) {
  Read-Host "Press Enter to close this launcher window"
}
