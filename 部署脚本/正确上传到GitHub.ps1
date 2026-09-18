param(
    [string]$Owner = "buganbugan6215-gif",
    [string]$Repository = "yinli-smart-delivery",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$SharedCodeFolder = ([char[]](21151,33021,32452,20214,95,39029,38754,20849,29992,20195,30721) -join "")
$DataFolder = ([char[]](32593,31449,25968,25454,95,39029,38754,35835,21462,30340,25351,26631) -join "")
$ImageFolder = ([char[]](23637,31034,22270,29255,95,22320,22270,21644,31572,36777,22270) -join "")

# Upload only files required by the public Streamlit app.
$RootFiles = @("app.py", "README.md", "requirements.txt", ".gitignore")
$Folders = @(
    "pages",
    $SharedCodeFolder,
    $DataFolder,
    $ImageFolder,
    ".streamlit"
)

Write-Host "Uploading to: https://github.com/$Owner/$Repository" -ForegroundColor Cyan
Write-Host "Correct folder paths will be preserved. Existing flat files will not be deleted." -ForegroundColor Yellow

$SecureToken = Read-Host "Paste GitHub Fine-grained Personal Access Token" -AsSecureString
$Token = [System.Net.NetworkCredential]::new("", $SecureToken).Password
if ([string]::IsNullOrWhiteSpace($Token)) {
    throw "No GitHub token was entered. Upload stopped."
}

$Files = [System.Collections.Generic.List[System.IO.FileInfo]]::new()
foreach ($Name in $RootFiles) {
    $Path = Join-Path $ProjectRoot $Name
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $Files.Add((Get-Item -LiteralPath $Path))
    }
}
foreach ($Folder in $Folders) {
    $Path = Join-Path $ProjectRoot $Folder
    if (Test-Path -LiteralPath $Path -PathType Container) {
        Get-ChildItem -LiteralPath $Path -Recurse -Force -File | ForEach-Object { $Files.Add($_) }
    }
}

if ($Files.Count -eq 0) {
    throw "No website files were found to upload."
}

$Headers = @{
    Authorization = "Bearer $Token"
    Accept = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
    "User-Agent" = "yinli-smart-delivery-uploader"
}

function Convert-ToGitHubPath([string]$LocalPath) {
    $RootPath = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\') + '\'
    $FullPath = [System.IO.Path]::GetFullPath($LocalPath)
    if (-not $FullPath.StartsWith($RootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "File path is outside the project root: $LocalPath"
    }
    $Relative = $FullPath.Substring($RootPath.Length)
    return (($Relative -split '[\\/]') | ForEach-Object { [Uri]::EscapeDataString($_) }) -join "/"
}

for ($Index = 0; $Index -lt $Files.Count; $Index++) {
    $File = $Files[$Index]
    $GitHubPath = Convert-ToGitHubPath $File.FullName
    $ApiUrl = "https://api.github.com/repos/$Owner/$Repository/contents/$GitHubPath"
    $EncodedContent = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($File.FullName))
    $Action = "Add"
    try {
        $Existing = Invoke-RestMethod -Method Get -Uri "$ApiUrl`?ref=$Branch" -Headers $Headers
        $Action = "Update"
    } catch {
        $Existing = $null
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode.value__ -ne 404) { throw }
    }
    $Payload = @{
        message = "$Action website file: $([System.IO.Path]::GetFileName($File.Name))"
        content = $EncodedContent
        branch = $Branch
    }
    if ($Existing -and $Existing.sha) { $Payload.sha = $Existing.sha }
    Write-Progress -Activity "Uploading website files" -Status "$($Index + 1)/$($Files.Count): $GitHubPath" -PercentComplete ((($Index + 1) / $Files.Count) * 100)
    Invoke-RestMethod -Method Put -Uri $ApiUrl -Headers $Headers -ContentType "application/json; charset=utf-8" -Body ($Payload | ConvertTo-Json -Depth 5 -Compress) | Out-Null
}

Write-Progress -Activity "Uploading website files" -Completed
Write-Host "Upload finished. Refresh GitHub and confirm that pages, shared code, data, images, and .streamlit folders exist." -ForegroundColor Green
