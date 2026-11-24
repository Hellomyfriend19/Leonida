# Leonida Legacy - install missing build prerequisites on Windows (Python, .NET 8, Vulkan SDK, VS C++, llvm-mc).
# Does not download game files. Re-open the terminal after installs so PATH and VULKAN_SDK refresh.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install_prerequisites.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install_prerequisites.ps1 -Auto
#   powershell -ExecutionPolicy Bypass -File scripts\install_prerequisites.ps1 -CheckOnly
#
param(
    [switch]$Auto,
    [switch]$DryRun,
    [switch]$CheckOnly,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

function Write-Status([string]$Message) {
    if (-not $Quiet) { Write-Host $Message }
}

function Write-Note([string]$Message) {
    Write-Host $Message
}

function Test-Winget {
    return [bool](Get-Command winget -ErrorAction SilentlyContinue)
}

function Invoke-WingetInstall([string]$Id, [string]$Label, [string[]]$ExtraArgs = @()) {
    if (-not (Test-Winget)) {
        Write-Note "winget is not available; install $Label manually."
        return $false
    }
    $base = @("install", "--id", $Id, "-e", "--accept-package-agreements", "--accept-source-agreements")
    if ($Auto) { $base += "--silent" }
    $cmd = @("winget") + $base + $ExtraArgs
    $pretty = $cmd -join " "
    if ($DryRun) {
        Write-Note "[dry run] would run: $pretty"
        return $true
    }
    Write-Status "Installing $Label with winget ..."
    & winget @base @ExtraArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Note "winget install $Id failed (exit $LASTEXITCODE)."
        return $false
    }
    return $true
}

function Test-PythonExe([string]$Exe) {
    if (-not ($Exe -and (Test-Path -LiteralPath $Exe))) { return $false }
    if ($Exe -match '\\WindowsApps\\') { return $false }
    $code = "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
    try {
        & $Exe -c $code 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Find-PythonExe {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in @("3.14", "3.13", "3.12", "3")) {
            cmd /c "py -$v -c `"import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)`" >nul 2>nul"
            if ($LASTEXITCODE -eq 0) { return @("py-$v") }
        }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and (Test-PythonExe $python.Source)) { return @($python.Source) }
    # Skip the Microsoft Store python.exe alias when it is the only "python" on PATH.
    $local = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $local) {
        foreach ($dir in (Get-ChildItem -LiteralPath $local -Directory -Filter "Python3*" -ErrorAction SilentlyContinue | Sort-Object Name -Descending)) {
            $exe = Join-Path $dir.FullName "python.exe"
            if (-not (Test-Path -LiteralPath $exe)) { continue }
            if (Test-PythonExe $exe) { return @($exe) }
        }
    }
    return $null
}

function Test-PythonOk { return [bool](Find-PythonExe) }

function Ensure-Python {
    if (Test-PythonOk) {
        Write-Status "OK  Python 3.12+"
        return $true
    }
    Write-Note "Missing  Python 3.12+"
    if ($CheckOnly) { return $false }
    if (-not $Auto) {
        $ans = Read-Host "Install Python 3.12 for your user (winget, no admin)? [Y/N]"
        if ($ans -notmatch '^[Yy]') { return $false }
    }
    if (-not (Invoke-WingetInstall "Python.Python.3.12" "Python 3.12" @("--scope", "user"))) {
        Write-Note "  https://www.python.org/downloads/ - tick Add python.exe to PATH"
        return $false
    }
    if (Test-PythonOk) { return $true }
    Write-Note "Python was installed; open a new terminal if the build still cannot find it."
    return (Test-PythonOk)
}

function Test-DotNetSdk8 {
    $dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
    if (-not $dotnet) { return $false }
    $lines = & dotnet --list-sdks 2>$null
    foreach ($line in $lines) {
        if ($line -match '^(\d+)\.') {
            if ([int]$Matches[1] -ge 8) { return $true }
        }
    }
    return $false
}

function Ensure-DotNetSdk {
    if (Test-DotNetSdk8) {
        Write-Status "OK  .NET 8 SDK"
        return $true
    }
    Write-Note "Missing  .NET 8 SDK"
    if ($CheckOnly) { return $false }
    if (-not $Auto) {
        $ans = Read-Host "Install .NET 8 SDK with winget? [Y/N]"
        if ($ans -notmatch '^[Yy]') { return $false }
    }
    if (-not (Invoke-WingetInstall "Microsoft.DotNet.SDK.8" ".NET 8 SDK")) {
        Write-Note "  https://dotnet.microsoft.com/download/dotnet/8.0"
        return $false
    }
    return (Test-DotNetSdk8)
}

function Test-VulkanSdk {
    if ($env:VULKAN_SDK -and (Test-Path -LiteralPath (Join-Path $env:VULKAN_SDK "Bin\spirv-as.exe"))) {
        return $true
    }
    return [bool](Get-Command spirv-as -ErrorAction SilentlyContinue)
}

function Ensure-VulkanSdk {
    if (Test-VulkanSdk) {
        Write-Status "OK  Vulkan SDK (spirv-as / spirv-val)"
        return $true
    }
    Write-Note "Missing  Vulkan SDK"
    if ($CheckOnly) { return $false }
    if (-not $Auto) {
        $ans = Read-Host "Install Vulkan SDK with winget (large download)? [Y/N]"
        if ($ans -notmatch '^[Yy]') { return $false }
    }
    foreach ($id in @("LunarGInc.VulkanSDK", "KhronosGroup.VulkanSDK")) {
        if (Invoke-WingetInstall $id "Vulkan SDK") {
            if (Test-VulkanSdk) { return $true }
        }
    }
    Write-Note "  https://vulkan.lunarg.com/ - then reopen the terminal (VULKAN_SDK)"
    return $false
}

function Test-VsCppTools {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path -LiteralPath $vswhere)) { return $false }
    $path = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
    return [bool]($path -and $path.Trim())
}

function Ensure-VsCppTools {
    if (Test-VsCppTools) {
        Write-Status "OK  Visual Studio C++ x64 tools"
        return $true
    }
    Write-Note "Missing  Visual Studio 2022 with Desktop development with C++"
    if ($CheckOnly) { return $false }
    if (-not $Auto) {
        $ans = Read-Host "Install VS 2022 Build Tools + C++ workload (large)? [Y/N]"
        if ($ans -notmatch '^[Yy]') { return $false }
    }
    $override = '--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended'
    if (-not (Invoke-WingetInstall "Microsoft.VisualStudio.2022.BuildTools" "VS 2022 Build Tools" @("--override", $override))) {
        Write-Note "  Install Visual Studio 2022 Community or Build Tools with C++ desktop workload"
        return $false
    }
    return (Test-VsCppTools)
}

function Test-Git {
    return [bool](Get-Command git -ErrorAction SilentlyContinue)
}

function Ensure-Git {
    if (Test-Git) { return $true }
    if ($CheckOnly) { return $false }
    if (-not $Auto) {
        $ans = Read-Host "Install Git (needed to build llvm-mc)? [Y/N]"
        if ($ans -notmatch '^[Yy]') { return $false }
    }
    Invoke-WingetInstall "Git.Git" "Git" | Out-Null
    return (Test-Git)
}

function Get-LlvmMcPath {
    if ($env:LLVM_MC) {
        $raw = $env:LLVM_MC.Trim()
        if ($raw -match '\s') {
            $first = ($raw -split '\s+', 2)[0]
            if (Test-Path -LiteralPath $first) { return $first }
        } elseif (Test-Path -LiteralPath $raw) {
            return $raw
        }
    }
    $default = Join-Path $env:USERPROFILE ".leonida\llvm-mc\llvm-mc.exe"
    if (Test-Path -LiteralPath $default) { return $default }
    $onPath = Get-Command llvm-mc -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    return $null
}

function Test-LlvmMc { return [bool](Get-LlvmMcPath) }

function Ensure-LlvmMc {
    if (Test-LlvmMc) {
        Write-Status "OK  llvm-mc ($(Get-LlvmMcPath))"
        return $true
    }
    Write-Note "Missing  llvm-mc (LLVM 21+ with AMDGPU; run scripts\build_llvm_mc.ps1)"
    if ($CheckOnly) { return $false }
    if (-not (Test-PythonOk -and Test-VsCppTools)) {
        Write-Note "  Install Python and Visual Studio C++ first, then run this script again or:"
        Write-Note "  powershell -ExecutionPolicy Bypass -File scripts\build_llvm_mc.ps1"
        return $false
    }
    if (-not (Ensure-Git)) {
        Write-Note "  Git is required for build_llvm_mc.ps1"
        return $false
    }
    if (-not $Auto) {
        $ans = Read-Host "Build llvm-mc now (~20-40 min, ~2 GB temp)? [Y/N]"
        if ($ans -notmatch '^[Yy]') { return $false }
    }
    $build = Join-Path $Root "scripts\build_llvm_mc.ps1"
    if ($DryRun) {
        Write-Note "[dry run] would run: $build"
        return $false
    }
    Write-Note "Building llvm-mc (this can take a while) ..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File $build
    if ($LASTEXITCODE -ne 0) {
        Write-Note "build_llvm_mc.ps1 failed."
        return $false
    }
    if (Test-LlvmMc) { return $true }
    Write-Note "Build finished; set LLVM_MC or open a new terminal."
    return $false
}

function Test-GamePackage {
    Write-Note "Note   Xbox Series package 1.0.2.1 is not installed by this script (your own legal copy)."
    return $true
}

if ($env:OS -ne "Windows_NT") {
    Write-Note "This installer is for Windows only."
    exit 2
}

Write-Note ""
Write-Note "Leonida Legacy - prerequisite check"
Write-Note "Repository: $Root"
Write-Note ""

$results = @(
    (Ensure-Python),
    (Ensure-DotNetSdk),
    (Ensure-VulkanSdk),
    (Ensure-VsCppTools),
    (Ensure-LlvmMc)
)
Test-GamePackage | Out-Null

$ok = ($results -notcontains $false)
if ($CheckOnly) {
    exit $(if ($ok) { 0 } else { 1 })
}

if (-not $ok) {
    Write-Note ""
    Write-Note "Some prerequisites are still missing. Fix the messages above and run again,"
    Write-Note "or: powershell -ExecutionPolicy Bypass -File scripts\install_prerequisites.ps1 -Auto"
    exit 1
}

Write-Note ""
Write-Note "All automated prerequisites look ready. If you just installed tools, open a new terminal."
exit 0