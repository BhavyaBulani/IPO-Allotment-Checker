param(
    [string]$envPath = "..\.env",
    [string]$backupDir = ".\backups"
)

# Read environment variables
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)\s*=\s*(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
} else {
    Write-Warning "Could not find .env file at $envPath. Continuing, assuming environment variables are set."
}

$user = $env:MYSQL_USER
if (-not $user) { $user = "ipo_user" }

$password = $env:MYSQL_PASSWORD
if (-not $password) { $password = "ipo_password" }

$host_name = $env:MYSQL_HOST
if (-not $host_name) { $host_name = "localhost" }

$port = $env:MYSQL_PORT
if (-not $port) { $port = "3306" }

$database = $env:MYSQL_DATABASE
if (-not $database) { $database = "ipo_checker" }

if (-not (Test-Path -Path $backupDir)) {
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path -Path $backupDir -ChildPath "$($database)_$timestamp.sql"

Write-Host "Starting backup of database $database to $backupFile..."

# Run mysqldump
try {
    $command = "mysqldump --host=$host_name --port=$port --user=$user --password=$password --databases $database --result-file=$backupFile"
    Invoke-Expression $command
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Backup completed successfully!"
    } else {
        Write-Error "mysqldump failed with exit code $LASTEXITCODE."
    }
} catch {
    Write-Error "Failed to execute backup: $_"
}
