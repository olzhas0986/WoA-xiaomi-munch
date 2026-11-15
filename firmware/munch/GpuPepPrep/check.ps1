#Requires -RunAsAdministrator
$ErrorActionPreference='Stop'
$Manifest=Get-Content -Raw (Join-Path $PSScriptRoot 'manifest.json') | ConvertFrom-Json
foreach($f in $Manifest.files){
    if($f.path -notmatch '^[A-Za-z0-9_./-]+$' -or $f.path.Contains('..')){throw 'Invalid manifest path'}
    if((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot $f.path)).Hash -ne $f.sha256){throw "Package checksum mismatch: $($f.path)"}
}
if((Get-CimInstance Win32_ComputerSystem).Model.Trim() -ne 'POCO F4'){throw 'Only POCO F4'}
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MunchFirmware {
 [DllImport("kernel32.dll", SetLastError=true)] static extern uint GetSystemFirmwareTable(uint provider,uint id,[Out] byte[] buffer,uint size);
 public static byte[] Dsdt(){uint n=GetSystemFirmwareTable(0x41435049,0x54445344,null,0);if(n<36||n>65536)throw new InvalidOperationException("Cannot read DSDT size");byte[] b=new byte[n];if(GetSystemFirmwareTable(0x41435049,0x54445344,b,n)!=n)throw new InvalidOperationException("Cannot read DSDT");return b;}
}
'@
$LogRoot='C:\munch-gpu-pep'
New-Item -ItemType Directory -Force $LogRoot | Out-Null
$dsdt=[MunchFirmware]::Dsdt()
[IO.File]::WriteAllBytes((Join-Path $LogRoot 'DSDT.aml'),$dsdt)
$hash=[BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($dsdt)).Replace('-','').ToLowerInvariant()
$namespaceOK=($hash -eq $Manifest.dsdt_sha256)
$cpu=@(Get-CimInstance Win32_Processor)
$logical=($cpu | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
$devices=@(Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPDeviceID -match '^ACPI\\(?:QCOM250B|QCOM2533|QCOM250C|QCOM252E)\\'} | Select-Object Name,PNPDeviceID,Service,Status,ConfigManagerErrorCode)
$expected=@{'QCOM250B'='qcscm';'QCOM2533'='QCRPEN';'QCOM250C'='qcspmi';'QCOM252E'='qcpmic'}
$servicesOK=($devices.Count -eq 4)
foreach($id in $expected.Keys){
    $d=@($devices | Where-Object {$_.PNPDeviceID -match ('^ACPI\\'+$id+'\\')})
    if($d.Count -ne 1 -or $d[0].Service -ine $expected[$id] -or $d[0].ConfigManagerErrorCode -ne 0){$servicesOK=$false}
}
[ordered]@{stage='PEP CPU namespace preparation; PEP not installed';time=(Get-Date).ToString('o');dsdt_sha256=$hash;expected_dsdt_sha256=$Manifest.dsdt_sha256;namespace_ok=$namespaceOK;logical_processors=$logical;services_ok=$servicesOK;devices=$devices;processors=@($cpu | Select-Object Name,DeviceID,Architecture,NumberOfCores,NumberOfLogicalProcessors)} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $LogRoot 'report.json')
Write-Host "CPU: $logical / 8"
Write-Host "Preparation namespace: $namespaceOK"
Write-Host "SCM/RPEN/SPMI/PMIC: $servicesOK"
if(-not $namespaceOK -or $logical -ne 8 -or -not $servicesOK){$devices | Format-Table Service,Status,ConfigManagerErrorCode;throw 'Preparation check failed; report saved in C:\munch-gpu-pep'}
Write-Host 'Preparation OK. PEP driver not installed.'
