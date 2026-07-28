<#
.SYNOPSIS
    JARVIS AI Assistant - Backend Launcher Script
.DESCRIPTION
    Launches the Python FastAPI backend completely silently (no windows).
    Monitors the backend health and auto-restarts on crash.
    Designed for production use and Windows startup integration.
.NOTES
    Version: 1.0.0
    Author: JARVIS Team
#>

param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$NoMonitor,
    [switch]$NoGreeting,
    [string]$LogLevel = "INFO"
)

# ─── Configuration ──────────────────────────────────────────────────────────

$JarvisRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = "python"
$BackendScript = Join-Path $JarvisRoot "backend" "main.py"
$HealthUrl = "http://${Host}:${Port}/api/health"
$CheckInterval = 5
$StartupTimeout = 30
$RestartDelay = 3
$MaxRestarts = 5

# ─── Helper Functions ───────────────────────────────────────────────────────

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    Write-Host "[$timestamp] [$Level] $Message"
}

function Test-Health {
    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 3 -ErrorAction SilentlyContinue
        return $response.status -eq "healthy"
    } catch {
        return $false
    }
}

function Get-Greeting {
    param([string]$UserName = "Maxsad")
    # Russian greeting as configured
    return "Добро пожаловать, ${UserName}. Чем могу помочь?"
}

function Speak-Greeting {
    param([string]$Text)
    try {
        Add-Type -AssemblyName System.Speech
        $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
        # Try to select Russian voice
        $voices = $speak.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture -like 'ru-*' }
        if ($voices) {
            $speak.SelectVoice($voices[0].VoiceInfo.Name)
        }
        $speak.Speak($Text)
        Write-Log "Spoke greeting: $($Text.Substring(0, [Math]::Min(50, $Text.Length)))..."
    } catch {
        Write-Log "Failed to speak greeting: $_" "WARN"
    }
}

function Start-Backend {
    param([bool]$Initial = $true)
    
    Write-Log "Starting JARVIS backend..."
    Write-Log "  Root: $JarvisRoot"
    Write-Log "  Script: $BackendScript"
    Write-Log "  Host: $Host`:$Port"
    
    # Start Python process completely hidden
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $PythonExe
    $startInfo.Arguments = "`"$BackendScript`" --host=$Host --port=$Port"
    $startInfo.WorkingDirectory = $JarvisRoot
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    
    try {
        $process = [System.Diagnostics.Process]::Start($startInfo)
        Write-Log "Backend started (PID: $($process.Id))"
        
        # Wait for it to become healthy
        $startTime = Get-Date
        while ($true) {
            $elapsed = ((Get-Date) - $startTime).TotalSeconds
            if ($elapsed -gt $StartupTimeout) {
                Write-Log "Backend failed to become healthy within ${StartupTimeout}s" "ERROR"
                
                # Capture any output
                if (-not $process.HasExited) {
                    $stdout = $process.StandardOutput.ReadToEnd()
                    $stderr = $process.StandardError.ReadToEnd()
                    if ($stdout) { Write-Log "STDOUT: $stdout" "DEBUG" }
                    if ($stderr) { Write-Log "STDERR: $stderr" "DEBUG" }
                }
                return $null
            }
            
            if (Test-Health) {
                Write-Log "✓ Backend is healthy and ready (${elapsed}s)"
                return $process
            }
            
            # Check if process died
            if ($process.HasExited) {
                Write-Log "Backend exited with code $($process.ExitCode)" "ERROR"
                $stderr = $process.StandardError.ReadToEnd()
                if ($stderr) { Write-Log "STDERR: $stderr" "ERROR" }
                return $null
            }
            
            Start-Sleep -Seconds 1
        }
    } catch {
        Write-Log "Failed to start backend: $_" "ERROR"
        return $null
    }
}

# ─── Main ───────────────────────────────────────────────────────────────────

Write-Log "="*50
Write-Log "JARVIS AI Assistant v0.1.0"
Write-Log "="*50
Write-Log "Starting backend service..."

# Check for Python
try {
    $pythonVersion = & $PythonExe --version 2>&1
    Write-Log "Python: $pythonVersion"
} catch {
    Write-Log "Python not found! Please install Python 3.10+" "ERROR"
    exit 1
}

# Startup greeting
if (-not $NoGreeting) {
    $greeting = Get-Greeting
    Start-Job -ScriptBlock { param($t) Speak-Greeting $t } -ArgumentList $greeting | Out-Null
}

# Start backend with monitoring
$restartCount = 0
$restartWindow = (Get-Date)

while ($true) {
    $process = Start-Backend
    
    if ($process -eq $null) {
        # Failed to start
        $restartCount++
        $elapsedSinceWindow = ((Get-Date) - $restartWindow).TotalMinutes
        
        if ($elapsedSinceWindow -gt 5) {
            $restartCount = 1
            $restartWindow = Get-Date
        }
        
        if ($restartCount -gt $MaxRestarts) {
            Write-Log "Backend crashed $MaxRestarts times. Giving up." "CRITICAL"
            exit 1
        }
        
        Write-Log "Restarting in ${RestartDelay}s (attempt ${restartCount}/${MaxRestarts})..."
        Start-Sleep -Seconds $RestartDelay
        continue
    }
    
    # Reset restart counter on successful start
    $restartCount = 0
    
    # If monitoring is disabled, wait for process exit
    if ($NoMonitor) {
        $process.WaitForExit()
        Write-Log "Backend process exited" "INFO"
        exit $process.ExitCode
    }
    
    # Monitor health
    Write-Log "Monitoring backend health (every ${CheckInterval}s)..."
    
    $monitor = $true
    while ($monitor) {
        Start-Sleep -Seconds $CheckInterval
        
        if ($process.HasExited) {
            Write-Log "Backend process exited with code $($process.ExitCode)" "WARN"
            $monitor = $false
            break
        }
        
        $healthy = Test-Health
        if (-not $healthy) {
            Write-Log "Health check failed" "WARN"
            $monitor = $false
            break
        }
    }
    
    # Auto-restart
    if (-not $process.HasExited) {
        Write-Log "Stopping unresponsive backend..."
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    
    Write-Log "Restarting backend..."
    Start-Sleep -Seconds $RestartDelay
}
