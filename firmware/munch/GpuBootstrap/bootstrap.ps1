#Requires -RunAsAdministrator
param([ValidateSet('configure','install','report','rollback')][string]$Phase='configure')
$ErrorActionPreference='Stop'
$LogRoot='C:\munch-gpu'
New-Item -ItemType Directory -Force $LogRoot | Out-Null
$Manifest=Get-Content -Raw (Join-Path $PSScriptRoot 'manifest.json') | ConvertFrom-Json
foreach($f in $Manifest.files){
    if($f.path -notmatch '^[A-Za-z0-9_./-]+$' -or $f.path.Contains('..')){throw 'Invalid manifest path'}
    $file=Join-Path $PSScriptRoot $f.path
    if((Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash -ne $f.sha256){throw "Package checksum mismatch: $($f.path)"}
}
$Machine=Get-CimInstance Win32_ComputerSystem
if($Machine.Model.Trim() -ne 'POCO F4'){throw "Wrong device model: $($Machine.Model)"}
if(@(Get-CimInstance Win32_Processor | Where-Object {$_.Architecture -eq 12}).Count -eq 0){throw 'ARM64 Windows required'}
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MunchCI {
 [StructLayout(LayoutKind.Sequential)] public struct CI { public uint Length; public uint Options; }
 [DllImport("ntdll.dll")] public static extern int NtQuerySystemInformation(int cls, ref CI info, uint length, out uint returned);
 public static bool TestSigning() { CI ci=new CI();ci.Length=8;uint returned;int s=NtQuerySystemInformation(103,ref ci,8,out returned);if(s<0)throw new InvalidOperationException("Cannot query active code integrity policy");return (ci.Options&2)!=0; }
}
'@
$Cert=New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 (Join-Path $PSScriptRoot 'woa-kmci.cer')
if($Cert.Thumbprint -ne $Manifest.certificate_thumbprint){throw 'Unexpected driver signing certificate'}
$StatePath=Join-Path $LogRoot 'state.json'
function Save-State($s){$s | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $StatePath}
function Native-Checked([string]$exe,[string[]]$arguments,[string]$log){
    $output=& $exe @arguments 2>&1
    $result=$LASTEXITCODE
    $output | Out-File -Encoding UTF8 $log
    $output | ForEach-Object {Write-Host $_}
    if($result -ne 0 -and $result -ne 3010){throw "$exe failed with exit code $result; see $log"}
}
function Capture-Report {
    $entities=@(Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPDeviceID -match '^ACPI\\(?:QCOM|VEN_QCOM)'} | Select-Object Name,PNPDeviceID,Service,Status,ConfigManagerErrorCode)
    $drivers=@(Get-CimInstance Win32_PnPSignedDriver | Where-Object {$_.DeviceID -match '^ACPI\\(?:QCOM|VEN_QCOM)'} | Select-Object DeviceID,DeviceName,DriverVersion,InfName,IsSigned,Signer)
    $report=[ordered]@{stage='SCM foundation; GPU not enabled';time=(Get-Date).ToString('o');model=$Machine.Model;testsigning_active=[MunchCI]::TestSigning();bsp_commit=$Manifest.bsp_commit;devices=$entities;drivers=$drivers;video=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,PNPDeviceID)}
    $report | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $LogRoot 'report.json')
    $entities | Format-Table -AutoSize | Out-String -Width 240 | Set-Content -Encoding UTF8 (Join-Path $LogRoot 'pnp.txt')
    $entities | Where-Object {$_.PNPDeviceID -match 'QCOM250B'} | Format-List
    Write-Host 'Report saved to C:\munch-gpu\report.json'
}
if($Phase -eq 'report'){Capture-Report;exit 0}
if($Phase -eq 'configure'){
    if(-not(Test-Path $StatePath)){
        $state=[ordered]@{testsigning_before=[MunchCI]::TestSigning();root_existed=(Test-Path "Cert:\LocalMachine\Root\$($Cert.Thumbprint)");publisher_existed=(Test-Path "Cert:\LocalMachine\TrustedPublisher\$($Cert.Thumbprint)");certificate_thumbprint=$Cert.Thumbprint;published_inf='';bsp_commit=$Manifest.bsp_commit}
        Native-Checked 'bcdedit.exe' @('/export',(Join-Path $LogRoot 'bcd-before')) (Join-Path $LogRoot 'bcd-export.log')
        Save-State $state
    }
    Import-Certificate -FilePath (Join-Path $PSScriptRoot 'woa-kmci.cer') -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
    Import-Certificate -FilePath (Join-Path $PSScriptRoot 'woa-kmci.cer') -CertStoreLocation Cert:\LocalMachine\TrustedPublisher | Out-Null
    Native-Checked 'bcdedit.exe' @('/set','{current}','testsigning','on') (Join-Path $LogRoot 'signing-configure.log')
    Capture-Report
    Write-Host 'Configured test signing for the included WOA catalog. No driver installed.'
    Write-Host 'Boot Windows23 once more, then run setup.cmd install as administrator.'
    exit 0
}
if(-not(Test-Path $StatePath)){throw 'Run setup.cmd configure first'}
$state=Get-Content -Raw $StatePath | ConvertFrom-Json
if($state.bsp_commit -ne $Manifest.bsp_commit -or $state.certificate_thumbprint -ne $Cert.Thumbprint){throw 'State belongs to a different package'}
if($Phase -eq 'install'){
    if(-not ([MunchCI]::TestSigning())){throw 'Test signing is not active yet. Boot Windows23 again before installation.'}
    $device=@(Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPDeviceID -match '^ACPI\\QCOM250B\\'})
    if($device.Count -ne 1){throw 'Expected one SCM ACPI device. Boot the Windows23 foundation image.'}
    Native-Checked 'pnputil.exe' @('/add-driver',(Join-Path $PSScriptRoot 'Drivers\SCM\qcscm8250.inf'),'/install') (Join-Path $LogRoot 'install.log')
    $driver=Get-CimInstance Win32_PnPSignedDriver | Where-Object {$_.DeviceID -eq $device[0].PNPDeviceID} | Select-Object -First 1
    if($driver -and $driver.InfName -match '^oem[0-9]+\.inf$'){$state.published_inf=$driver.InfName;Save-State $state}
    Capture-Report
    Write-Host 'SCM test finished. GPU, PEP and SMMU drivers were not installed.'
    exit 0
}
if($Phase -eq 'rollback'){
    if($state.published_inf -match '^oem[0-9]+\.inf$'){
        $bound=@(Get-CimInstance Win32_PnPSignedDriver | Where-Object {$_.InfName -eq $state.published_inf})
        if(@($bound | Where-Object {$_.DeviceID -notmatch '^ACPI\\QCOM250B\\'}).Count -gt 0){throw 'Published INF also binds an unexpected device; refusing automatic removal'}
        Native-Checked 'pnputil.exe' @('/delete-driver',$state.published_inf,'/uninstall') (Join-Path $LogRoot 'rollback.log')
    }
    if(-not $state.testsigning_before){Native-Checked 'bcdedit.exe' @('/set','{current}','testsigning','off') (Join-Path $LogRoot 'signing-rollback.log')}
    if(-not $state.root_existed){Remove-Item -LiteralPath "Cert:\LocalMachine\Root\$($Cert.Thumbprint)" -ErrorAction SilentlyContinue}
    if(-not $state.publisher_existed){Remove-Item -LiteralPath "Cert:\LocalMachine\TrustedPublisher\$($Cert.Thumbprint)" -ErrorAction SilentlyContinue}
    Write-Host 'Rollback completed. Boot Windows22 for the previous ACPI namespace.'
}
