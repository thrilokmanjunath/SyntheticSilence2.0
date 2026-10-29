# Cross-platform relative path resolution for Windows PowerPoint automation
$BaseDir = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
param(
    [string]$Src = (Join-Path $PSScriptRoot "..\SyntheticSilence_RI_Review1.pptx"),
    [string]$Out = (Join-Path $PSScriptRoot "render"),
    [string]$Pdf = (Join-Path $PSScriptRoot "..\SyntheticSilence_RI_Review1.pdf")
)

$Src = [System.IO.Path]::GetFullPath($Src)
$Out = [System.IO.Path]::GetFullPath($Out)
$Pdf = [System.IO.Path]::GetFullPath($Pdf)

if (Test-Path $Out) { Remove-Item $Out -Recurse -Force }
New-Item -ItemType Directory $Out | Out-Null

try {
    $app = New-Object -ComObject PowerPoint.Application
    $p = $app.Presentations.Open($Src, $true, $false, $false)
    $p.Export($Out, "PNG", 1600, 900)
    $p.SaveAs($Pdf, 32)
    $p.Close()
    $app.Quit()
    Write-Output ("Rendered " + (Get-ChildItem $Out).Count + " slides to " + $Out)
} catch {
    Write-Warning "PowerPoint COM automation requires Microsoft PowerPoint on Windows: $_"
}
