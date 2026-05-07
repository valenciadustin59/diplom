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
      $content = Get-Content -Path $path -Raw -ErrorAction SilentlyContinue
      $match = [regex]::Match($content, "https://[a-zA-Z0-9.-]+\.(?:lhr\.life|loca\.lt)")
      if ($match.Success) {
        return $match.Value
      }
    }
    Start-Sleep -Seconds 2
  }
  throw "Tunnel URL was not found in $path"
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

Set-Location $rootDir
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

Write-Host "SEO Audit public Vercel launcher" -ForegroundColor Green
Write-Host "Project: $rootDir"
Write-Host "Public URL: $VercelUrl"

Write-Step "Stopping old local stack and old tunnel"
if (-not $DryRun) {
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $scriptDir "start-site.ps1") -StopOnly -SafePortCleanup -NoPause
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
Start-Process -FilePath "npx.cmd" -ArgumentList @(
  "-y",
  "localtunnel",
  "--port",
  "$actualBackendPort",
  "--local-host",
  "127.0.0.1"
) -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr -WindowStyle Hidden | Out-Null

$tunnelUrl = Wait-TunnelUrl $tunnelOut
Wait-HttpReady "$tunnelUrl/health/ready" "Tunnel"

Write-Step "Checking tunnel CORS"
$corsHeaders = @{
  Origin = $VercelUrl
  "Access-Control-Request-Method" = "POST"
  "Access-Control-Request-Headers" = "content-type"
}
$cors = Invoke-WebRequest -Uri "$tunnelUrl/audits" -Method OPTIONS -Headers $corsHeaders -UseBasicParsing -TimeoutSec 20
if ($cors.StatusCode -ne 200 -or $cors.Headers["Access-Control-Allow-Origin"] -ne $VercelUrl) {
  throw "Tunnel is reachable, but CORS is not configured for $VercelUrl"
}

Write-Step "Updating Vercel VITE_API_URL"
Set-Location $frontendDir
npx vercel env rm VITE_API_URL production --yes
if ($LASTEXITCODE -ne 0) {
  Write-Host "VITE_API_URL was not removed. Continuing; it may not have existed." -ForegroundColor DarkYellow
}
$tunnelUrl | npx vercel env add VITE_API_URL production
if ($LASTEXITCODE -ne 0) {
  throw "Could not add VITE_API_URL to Vercel."
}

Write-Step "Deploying frontend to Vercel production"
$deployOutput = npx vercel --prod --yes 2>&1
Write-Host $deployOutput
$deploymentMatch = [regex]::Match(($deployOutput -join "`n"), "https://frontend-[a-zA-Z0-9-]+\.vercel\.app")
if (-not $deploymentMatch.Success) {
  throw "Could not find deployment URL in Vercel output."
}
$deploymentUrl = $deploymentMatch.Value

Write-Step "Assigning stable alias"
npx vercel alias set $deploymentUrl $Alias
if ($LASTEXITCODE -ne 0) {
  throw "Could not assign alias $Alias."
}

Write-Step "Public site is ready"
Write-Host "Frontend: $VercelUrl" -ForegroundColor Green
Write-Host "Backend tunnel: $tunnelUrl" -ForegroundColor Green
Write-Host "Local frontend: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host ""
Write-Host "Do not close this computer/session while people use Vercel: the backend runs here." -ForegroundColor Yellow
Write-Host "Use Stop SEO Audit.cmd to stop local stack and tunnel." -ForegroundColor Yellow

if (-not $NoBrowser) {
  Start-Process $VercelUrl
}

if (-not $NoPause) {
  Read-Host "Press Enter to close this launcher window"
}
