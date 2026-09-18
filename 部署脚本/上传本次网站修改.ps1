$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$repo = 'buganbugan6215-gif/yinli-smart-delivery'
$token = Read-Host 'Paste GitHub Personal Access Token' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
try { $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
$plainToken = $plainToken -replace '[^A-Za-z0-9_]', ''

$headers = @{
    Authorization = "Bearer $plainToken"
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
    'User-Agent' = 'yinli-smart-delivery-uploader'
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

$PageOrder = ([char[]](23458,25143,19979,21333) -join '')
$PageTracking = ([char[]](35746,21333,36861,36394) -join '')
$PageOverview = ([char[]](26041,26696,39550,39542,33329) -join '')
$PageMap = ([char[]](37197,36865,32593,32476,22320,22270) -join '')
$PageReceipt = ([char[]](30005,23376,31614,25910) -join '')
$SharedFolder = ([char[]](21151,33021,32452,20214,95,39029,38754,20849,29992,20195,30721) -join '')
$DataFolder = ([char[]](32593,31449,25968,25454,95,39029,38754,35835,21462,30340,25351,26631) -join '')
$PrepFolder = ([char[]](25968,25454,25972,29702,33050,26412,95,29983,25104,32593,31449,25968,25454) -join '')
$files = @(
    'app.py',
    "pages/0_$PageOrder.py",
    "pages/0_$PageTracking.py",
    "pages/1_$PageOverview.py",
    "pages/3_$PageMap.py",
    "pages/8_$PageReceipt.py",
    "$SharedFolder/maps.py",
    "$SharedFolder/order_state.py",
    "$SharedFolder/ui.py",
    "$DataFolder/road_major.geojson",
    "$DataFolder/road_minor.geojson",
    "$DataFolder/manifest.json",
    "$PrepFolder/export_road_network.py"
)

foreach ($relative in $files) {
    $local = Join-Path $PSScriptRoot ($relative -replace '/', '\')
    if (-not (Test-Path -LiteralPath $local -PathType Leaf)) { throw "Missing file: $relative" }
    $encodedPath = (($relative -split '/') | ForEach-Object { [Uri]::EscapeDataString($_) }) -join '/'
    $uri = "https://api.github.com/repos/$repo/contents/$encodedPath"
    $previous = $null
    try { $previous = Invoke-GitHubRequest -Method Get -Uri $uri -Headers $headers }
    catch { if (-not $_.Exception.Response -or $_.Exception.Response.StatusCode.value__ -ne 404) { throw } }
    $payload = @{
        message = "Update customer platform: $relative"
        content = [Convert]::ToBase64String([IO.File]::ReadAllBytes($local))
        branch = 'main'
    }
    if ($previous) { $payload.sha = $previous.sha }
    Invoke-GitHubRequest -Method Put -Uri $uri -Headers $headers -Body ($payload | ConvertTo-Json -Compress) | Out-Null
    Write-Host "Uploaded: $relative" -ForegroundColor Green
}

Write-Host 'All changes uploaded. Streamlit Cloud will redeploy automatically.' -ForegroundColor Cyan
