#Requires -RunAsAdministrator
param([ValidateSet('install','report','rollback')][string]$Phase='install')
$ErrorActionPreference='Stop'
$LogRoot='C:\munch-gpu-pmic'
New-Item -ItemType Directory -Force $LogRoot | Out-Null
$Manifest=Get-Content -Raw (Join-Path $PSScriptRoot 'manifest.json') | ConvertFrom-Json
foreach($f in $Manifest.files){
    if($f.path -notmatch '^[A-Za-z0-9_./-]+$' -or $f.path.Contains('..')){throw 'Invalid manifest path'}
    if((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot $f.path)).Hash -ne $f.sha256){throw "Package checksum mismatch: $($f.path)"}
}
if((Get-CimInstance Win32_ComputerSystem).Model.Trim() -ne 'POCO F4'){throw 'Only POCO F4'}
if(@(Get-CimInstance Win32_Processor | Where-Object {$_.Architecture -eq 12}).Count -eq 0){throw 'ARM64 Windows required'}
$StatePath=Join-Path $LogRoot 'state.json'
function Save-State($s){$s | ConvertTo-Json | Set-Content -Encoding UTF8 $StatePath}
function Devices { @(Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPDeviceID -match '^ACPI\\(?:QCOM250B|QCOM2533|QCOM250C|QCOM252E)\\'}) }
function Report {
    $devices=Devices | Select-Object Name,PNPDeviceID,Service,Status,ConfigManagerErrorCode
    [ordered]@{stage='SCM + RPEN + SPMI + core PMIC; GPU not enabled';time=(Get-Date).ToString('o');bsp_commit=$Manifest.bsp_commit;devices=@($devices);drivers=@(Get-CimInstance Win32_PnPSignedDriver | Where-Object {$_.DeviceID -match '^ACPI\\(?:QCOM250B|QCOM2533|QCOM250C|QCOM252E)\\'} | Select-Object DeviceID,InfName,DriverVersion,IsSigned)} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $LogRoot 'report.json')
    $devices | Format-Table Service,Status,ConfigManagerErrorCode -AutoSize
    Write-Host 'Report: C:\munch-gpu-pmic\report.json'
}
if($Phase -eq 'report'){Report;exit 0}
if($Phase -eq 'rollback'){
    if(-not(Test-Path $StatePath)){throw 'No saved PMIC installation state'}
    $state=Get-Content -Raw $StatePath | ConvertFrom-Json
    if($state.bsp_commit -ne $Manifest.bsp_commit){throw 'State belongs to another BSP'}
    if(-not $state.owned){throw 'PMIC package existed before this test; automatic removal refused'}
    if($state.published_inf -notmatch '^oem[0-9]+\.inf$'){throw 'No verified published INF recorded'}
    $bound=@(Get-CimInstance Win32_PnPSignedDriver | Where-Object {$_.InfName -eq $state.published_inf})
    if(@($bound | Where-Object {$_.DeviceID -notmatch '^ACPI\\QCOM252E\\'}).Count -gt 0){throw 'Unexpected device uses this INF'}
    & pnputil.exe /delete-driver $state.published_inf /uninstall
    if($LASTEXITCODE -notin @(0,3010)){throw 'PMIC removal failed'}
    Write-Host 'PMIC removed. SCM, RPEN, SPMI and signing settings retained. Boot Windows25.'
    exit 0
}
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class PmicCI {
 [StructLayout(LayoutKind.Sequential)] public struct CI { public uint Length; public uint Options; }
 [DllImport("ntdll.dll")] public static extern int NtQuerySystemInformation(int cls, ref CI info, uint length, out uint returned);
 public static bool TestSigning() { CI ci=new CI();ci.Length=8;uint returned;int s=NtQuerySystemInformation(103,ref ci,8,out returned);if(s<0)throw new InvalidOperationException("Cannot query active code integrity policy");return (ci.Options&2)!=0; }
}
'@
if(-not ([PmicCI]::TestSigning())){throw 'Active test signing required; complete the Windows23 configure step and boot again'}
$thumb=$Manifest.certificate_thumbprint
if(-not(Test-Path "Cert:\LocalMachine\TrustedPublisher\$thumb")){throw 'Missing WOA publisher certificate; complete Windows23 configure'}
$devices=Devices
$scm=@($devices | Where-Object {$_.PNPDeviceID -match '^ACPI\\QCOM250B\\'})
$pmic=@($devices | Where-Object {$_.PNPDeviceID -match '^ACPI\\QCOM252E\\'})
if($scm.Count -ne 1 -or $scm[0].Service -ine 'qcscm' -or $scm[0].ConfigManagerErrorCode -ne 0){throw 'Working SCM required'}
$rpen=@($devices | Where-Object {$_.PNPDeviceID -match '^ACPI\\QCOM2533\\'})
if($rpen.Count -ne 1 -or $rpen[0].Service -ine 'QCRPEN' -or $rpen[0].ConfigManagerErrorCode -ne 0){throw 'Working RPEN required'}
$spmi=@($devices | Where-Object {$_.PNPDeviceID -match '^ACPI\\QCOM250C\\'})
if($spmi.Count -ne 1 -or $spmi[0].Service -ine 'qcspmi' -or $spmi[0].ConfigManagerErrorCode -ne 0){throw 'Working SPMI required'}
if($pmic.Count -ne 1){throw 'PMIC node missing; boot the Windows26 image'}
# Record all existing published INF names before adding our one package.
$existing=& pnputil.exe /enum-drivers 2>&1
if($LASTEXITCODE -ne 0){throw 'Cannot enumerate existing driver packages'}
$existingNames=@([regex]::Matches(($existing -join "`n"),'(?i)\boem[0-9]+\.inf\b') | ForEach-Object {$_.Value.ToLowerInvariant()} | Select-Object -Unique)
$output=& pnputil.exe /add-driver (Join-Path $PSScriptRoot 'Drivers\PMIC\qcpmic8250.inf') /install 2>&1
$exitCode=$LASTEXITCODE
$output | Out-File -Encoding UTF8 (Join-Path $LogRoot 'install.log')
$output | ForEach-Object {Write-Host $_}
$names=@([regex]::Matches(($output -join "`n"),'(?i)\boem[0-9]+\.inf\b') | ForEach-Object {$_.Value.ToLowerInvariant()} | Select-Object -Unique)
if($names.Count -eq 1 -and -not(Test-Path $StatePath)){
    Save-State ([ordered]@{bsp_commit=$Manifest.bsp_commit;published_inf=$names[0];owned=($names[0] -notin $existingNames)})
}
Report
if($exitCode -notin @(0,3010)){throw "Driver installation failed: $exitCode"}
$device=@(Devices | Where-Object {$_.PNPDeviceID -match '^ACPI\\QCOM252E\\'})
if($device.Count -eq 1 -and $device[0].Service -ieq 'qcpmic' -and $device[0].ConfigManagerErrorCode -eq 0){
    Write-Host 'PMIC started: code 0. GPU is not enabled yet.'
}else{Write-Host 'PMIC is not confirmed started. Send the status shown above.'}
