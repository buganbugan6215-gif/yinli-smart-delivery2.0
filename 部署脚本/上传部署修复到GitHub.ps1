$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$repo = 'buganbugan6215-gif/yinli-smart-delivery'
$token = Read-Host 'Paste GitHub Personal Access Token' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
try {
$plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
$plainToken = $plainToken -replace '[^A-Za-z0-9_]', ''

$headers = @{
    Authorization = "Bearer $plainToken"
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
}

function Invoke-GitHubRequest {
    param([string]$Method, [string]$Uri, [hashtable]$Headers, [string]$Body = $null)
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            if ([string]::IsNullOrEmpty($Body)) { return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $Headers }
            return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $Headers -ContentType 'application/json' -Body $Body
        }
        catch {
            if ($attempt -eq 3) { throw }
            Write-Host "Network retry $attempt/3..." -ForegroundColor Yellow
            Start-Sleep -Seconds (2 * $attempt)
        }
    }
}

foreach ($name in @('requirements.txt')) {
    $path = Join-Path $PSScriptRoot $name
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing file: $name" }

    $uri = "https://api.github.com/repos/$repo/contents/$name"
    $previous = $null
    try {
        $previous = Invoke-GitHubRequest -Method Get -Uri $uri -Headers $headers
    }
    catch {
        if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
    }
    $content = [Convert]::ToBase64String([IO.File]::ReadAllBytes($path))
    $body = @{
        message = "Fix Streamlit Cloud dependencies: $name"
        content = $content
        branch = 'main'
    }
    if ($previous) { $body.sha = $previous.sha }
    $body = $body | ConvertTo-Json
    Invoke-GitHubRequest -Method Put -Uri $uri -Headers $headers -Body $body | Out-Null
    Write-Host "Uploaded: $name" -ForegroundColor Green
}

Write-Host 'Return to Streamlit Cloud and click Reboot app.' -ForegroundColor Cyan
