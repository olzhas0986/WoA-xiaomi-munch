#Requires -RunAsAdministrator
param([ValidateSet('install','report','rollback')][string]$Phase='install')
$ErrorActionPreference='Stop'
$LogRoot='C:\munch-gpu-pep-core'
New-Item -ItemType Directory -Force $LogRoot | Out-Null
$Manifest=Get-Content -Raw (Join-Path $PSScriptRoot 'manifest.json') | ConvertFrom-Json
foreach($f in $Manifest.files){
 if($f.path -notmatch '^[A-Za-z0-9_./-]+$' -or $f.path.Contains('..')){throw 'Invalid manifest path'}
 if((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot $f.path)).Hash -ne $f.sha256){throw "Package checksum mismatch: $($f.path)"}
}
if((Get-CimInstance Win32_ComputerSystem).Model.Trim() -ne 'POCO F4'){throw 'Only POCO F4'}
if(@(Get-CimInstance Win32_Processor | Where-Object {$_.Architecture -eq 12}).Count -eq 0){throw 'ARM64 Windows required'}
$StatePath=Join-Path $LogRoot 'state.json'
$Policy=Get-Content -Raw (Join-Path $PSScriptRoot 'policy.json') | ConvertFrom-Json
$ParamRoot='HKLM:\SYSTEM\CurrentControlSet\Services\qcpep\Parameters'
$PowerRoot='HKLM:\SYSTEM\CurrentControlSet\Control\Power'
$Provision=Join-Path $env:SystemRoot 'Provisioning\Packages\PPMSettings-8250Profiles.wd.ppkg'
function Devices {
 # Get-PnpDevice includes unbound/no-class ACPI nodes missing from some WMI views.
 # Read numeric problem/service properties directly; do not parse localized labels.
 Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -match '^ACPI\\(?:QCOM250B|QCOM2533|QCOM250C|QCOM252E|QCOM2519)\\'} | ForEach-Object {
  $id=$_.InstanceId
  $problem=Get-PnpDeviceProperty -InstanceId $id -KeyName 'DEVPKEY_Device_ProblemCode' -ErrorAction Stop
  $service=Get-PnpDeviceProperty -InstanceId $id -KeyName 'DEVPKEY_Device_Service' -ErrorAction SilentlyContinue
  [pscustomobject]@{Name=$_.FriendlyName;PNPDeviceID=$id;Service=$(if($service){[string]$service.Data}else{''});Status=$_.Status;ConfigManagerErrorCode=[int]$problem.Data}
 }
}
function Pep { @(Devices | Where-Object {$_.PNPDeviceID -match '^ACPI\\QCOM2519\\'}) }
function Save-State { $script:state | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $StatePath }
function Native([string]$exe,[string[]]$arguments,[string]$log){
 $o=& $exe @arguments 2>&1;$result=$LASTEXITCODE
 $o | Out-File -Encoding UTF8 (Join-Path $LogRoot $log)
 $o | ForEach-Object {Write-Host $_}
 if($result -notin @(0,3010)){throw "$exe failed ($result); log $log"}
 return @($o)
}
function Optional-RegistryValue([string]$key,[string]$name) {
 # Get-ItemPropertyValue -Name can throw for an absent value even with
 # SilentlyContinue. Query the existing key, then look up its property.
 if(-not(Test-Path -LiteralPath $key -ErrorAction Stop)){return $null}
 $item=Get-ItemProperty -LiteralPath $key -ErrorAction Stop
 $property=$item.PSObject.Properties[$name]
 if($null -eq $property){return $null}
 return $property.Value
}
# Exercise the missing-value path before installation or policy writes.
$probeName='MunchReadProbe_'+[guid]::NewGuid().ToString('N')
if($null -ne (Optional-RegistryValue $PowerRoot $probeName)){throw 'Optional registry lookup self-check failed'}
function Settings {
 @(foreach($setting in $Policy.settings){
  $key=$ParamRoot
  if($setting.subkey){$key=Join-Path $key $setting.subkey}
  $got=Optional-RegistryValue $key $setting.name
  [pscustomobject]@{key=$key;name=$setting.name;expected=$setting.value;actual=$got;ok=($null -ne $got -and $got -eq $setting.value)}
 })
}
function Report {
 $devices=@(Devices | Select-Object Name,PNPDeviceID,Service,Status,ConfigManagerErrorCode)
 $settings=Settings
 [ordered]@{stage='PEP core experiment; CPU management and system low power disabled';time=(Get-Date).ToString('o');bsp_commit=$Manifest.bsp_commit;devices=$devices;settings=$settings;driver=@(Get-CimInstance Win32_SystemDriver -Filter "Name='qcpep'" | Select-Object Name,State,StartMode,PathName)} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $LogRoot 'report.json')
 $devices | Format-Table Service,Status,ConfigManagerErrorCode -AutoSize
 Write-Host 'Report: C:\munch-gpu-pep-core\report.json'
}
if($Phase -eq 'report'){Report;exit 0}
if($Phase -eq 'rollback'){
 if(-not(Test-Path $StatePath)){throw 'No saved installation state'}
 $state=Get-Content -Raw $StatePath | ConvertFrom-Json
 if($state.bsp_commit -ne $Manifest.bsp_commit -or -not $state.owned -or $state.published_inf -notmatch '^oem[0-9]+\.inf$'){throw 'No owned PEP package recorded; refusing removal'}
 $bound=@(Get-CimInstance Win32_PnPSignedDriver | Where-Object {$_.InfName -eq $state.published_inf})
 if(@($bound | Where-Object {$_.DeviceID -notmatch '^ACPI\\QCOM2519\\'}).Count){throw 'Other devices use the PEP package'}
 $p=@(Pep)
 if($p.Count -eq 1){$null=Native 'pnputil.exe' @('/disable-device',$p[0].PNPDeviceID) 'disable-rollback.log'}
 $null=Native 'sc.exe' @('config','qcpep','start=','disabled') 'service-disable.log'
 $null=Native 'pnputil.exe' @('/delete-driver',$state.published_inf,'/uninstall') 'rollback.log'
 if($state.provision_existed){Copy-Item -LiteralPath (Join-Path $LogRoot 'provision-before.ppkg') -Destination $Provision -Force}
 elseif(Test-Path $Provision){
  if((Get-FileHash -LiteralPath $Provision).Hash -eq $Manifest.provision_sha256){Remove-Item -LiteralPath $Provision}
  else{Write-Host 'Provisioning file changed after this test; retained'}
 }
 if($state.power_value_existed){New-ItemProperty -Path $PowerRoot -Name PoFxSystemIrpWaitForReportDevicePowered -PropertyType DWord -Value $state.power_value -Force | Out-Null}
 else{Remove-ItemProperty -Path $PowerRoot -Name PoFxSystemIrpWaitForReportDevicePowered -ErrorAction SilentlyContinue}
 if($state.autologger_existed){$null=Native 'reg.exe' @('import',(Join-Path $LogRoot 'autologger-before.reg')) 'restore-autologger.log'}
 else{Remove-Item -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\WMI\Autologger\qcpep-rpmh' -Recurse -ErrorAction SilentlyContinue}
 Write-Host 'PEP removed. Boot the make stable image. Existing four drivers and signing policy retained.'
 exit 0
}
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class PepCI {
 [StructLayout(LayoutKind.Sequential)] public struct CI { public uint Length; public uint Options; }
 [DllImport("ntdll.dll")] public static extern int NtQuerySystemInformation(int cls,ref CI info,uint length,out uint returned);
 public static bool Active(){CI ci=new CI();ci.Length=8;uint returned;int s=NtQuerySystemInformation(103,ref ci,8,out returned);if(s<0)throw new InvalidOperationException("Cannot query signing policy");return (ci.Options&2)!=0;}
}
'@
if(-not ([PepCI]::Active())){throw 'Active test signing required'}
if(-not(Test-Path "Cert:\LocalMachine\TrustedPublisher\$($Manifest.certificate_thumbprint)")){throw 'Missing existing WOA publisher certificate'}
$devices=@(Devices)
$expected=@{'QCOM250B'='qcscm';'QCOM2533'='QCRPEN';'QCOM250C'='qcspmi';'QCOM252E'='qcpmic'}
foreach($id in $expected.Keys){
 $d=@($devices | Where-Object {$_.PNPDeviceID -match ('^ACPI\\'+$id+'\\')})
 if($d.Count -ne 1 -or $d[0].Service -ine $expected[$id] -or $d[0].ConfigManagerErrorCode -ne 0){throw "Working $id required"}
}
$p=@(Pep)
if($p.Count -ne 1){Report;throw "Expected one present PEP device, found $($p.Count). See report.json"}
$resumeBeforeDisable=$false
if(Test-Path $StatePath){
 $state=Get-Content -Raw $StatePath | ConvertFrom-Json
 if($state.bsp_commit -ne $Manifest.bsp_commit){throw 'State belongs to another BSP'}
 if($p[0].Service -ieq 'qcpep' -and $p[0].ConfigManagerErrorCode -eq 0){Report;if(@(Settings | Where-Object {-not $_.ok}).Count){throw 'PEP policy differs from the verified test settings'};Write-Host 'PEP already started with the test policy.';exit 0}
 # Resume only a saved pre-install phase; keep its original snapshots.
 $installed=Get-CimInstance Win32_SystemDriver -Filter "Name='qcpep'"
 if($state.phase -in @('before-disable','waiting-disable-reboot') -and -not $state.published_inf -and -not $state.owned -and -not $p[0].Service -and $p[0].ConfigManagerErrorCode -in @(0,28,22) -and $null -eq $installed){
  $resumeBeforeDisable=$true
 }else{throw 'A previous attempt exists. Run setup.cmd report and collect logs before retrying.'}
}
if($p[0].Service -or $p[0].ConfigManagerErrorCode -notin @(0,28,22)){throw 'Expected an unbound PEP device, fresh or disabled'}
if($p[0].ConfigManagerErrorCode -eq 22 -and -not $resumeBeforeDisable){throw 'Disabled PEP has no matching saved pre-install state; refusing to replace the baseline'}
$existing=& pnputil.exe /enum-drivers 2>&1
if($LASTEXITCODE -ne 0){throw 'Cannot enumerate existing driver packages'}
$existingNames=@([regex]::Matches(($existing -join "`n"),'(?i)\boem[0-9]+\.inf\b') | ForEach-Object {$_.Value.ToLowerInvariant()} | Select-Object -Unique)
if(-not $resumeBeforeDisable){
$powerValue=Optional-RegistryValue $PowerRoot 'PoFxSystemIrpWaitForReportDevicePowered'
$auto='HKLM:\SYSTEM\CurrentControlSet\Control\WMI\Autologger\qcpep-rpmh'
$state=[ordered]@{bsp_commit=$Manifest.bsp_commit;published_inf='';owned=$false;provision_existed=(Test-Path $Provision);power_value_existed=($null -ne $powerValue);power_value=$powerValue;autologger_existed=(Test-Path $auto);phase='before-disable'}
if($state.provision_existed){Copy-Item -LiteralPath $Provision -Destination (Join-Path $LogRoot 'provision-before.ppkg')}
if($state.autologger_existed){$null=Native 'reg.exe' @('export','HKLM\SYSTEM\CurrentControlSet\Control\WMI\Autologger\qcpep-rpmh',(Join-Path $LogRoot 'autologger-before.reg')) 'backup-autologger.log'}
Save-State
}
# A completed disable is retained across reboot; do not disable it again.
if($p[0].ConfigManagerErrorCode -ne 22){
 $null=Native 'pnputil.exe' @('/disable-device',$p[0].PNPDeviceID,'/force') 'disable-before-install.log'
 $p=@(Pep)
 if($p.Count -eq 1 -and -not $p[0].Service -and $p[0].ConfigManagerErrorCode -in @(0,28,14)){
  $state.phase='waiting-disable-reboot';Save-State
  Report
  Write-Host 'Disable needs a reboot. Boot the same make pep image, then rerun this setup.cmd.'
  exit 0
 }
}
if($p.Count -ne 1 -or $p[0].ConfigManagerErrorCode -ne 22){throw 'PEP was not confirmed disabled; refusing installation'}
$output=Native 'pnputil.exe' @('/add-driver',(Join-Path $PSScriptRoot 'Drivers\PEP\qcpep.wd8250.inf'),'/install') 'install.log'
$names=@([regex]::Matches(($output -join "`n"),'(?i)\boem[0-9]+\.inf\b') | ForEach-Object {$_.Value.ToLowerInvariant()} | Select-Object -Unique)
if($names.Count -eq 1){$state.published_inf=$names[0];$state.owned=($names[0] -notin $existingNames)}
$state.phase='installed-disabled';Save-State
$p=@(Pep)
$driver=Get-CimInstance Win32_SystemDriver -Filter "Name='qcpep'"
if($p.Count -ne 1 -or $p[0].ConfigManagerErrorCode -ne 22 -or $null -eq $driver -or $driver.State -ne 'Stopped'){Report;throw 'PEP driver was not confirmed stopped; it will not be enabled'}
if(-not(Test-Path $ParamRoot)){throw 'Native PEP service parameters missing; device remains disabled'}
$before=@(foreach($setting in $Policy.settings){
 $key=$ParamRoot;if($setting.subkey){$key=Join-Path $key $setting.subkey}
 $value=Optional-RegistryValue $key $setting.name
 [pscustomobject]@{key=$key;name=$setting.name;existed=($null -ne $value);value=$value}
})
$before | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $LogRoot 'native-policy-before.json')
foreach($setting in $Policy.settings){
 $key=$ParamRoot;if($setting.subkey){$key=Join-Path $key $setting.subkey}
 if(-not(Test-Path -LiteralPath $key)){New-Item -Path $key -Force | Out-Null}
 New-ItemProperty -LiteralPath $key -Name $setting.name -PropertyType DWord -Value $setting.value -Force | Out-Null
}
if(@(Settings | Where-Object {-not $_.ok}).Count){Report;throw 'Policy readback failed; PEP remains disabled'}
$state.phase='policy-verified';Save-State
$null=Native 'pnputil.exe' @('/enable-device',$p[0].PNPDeviceID) 'enable.log'
$state.phase='enabled';Save-State
Report
$p=@(Pep)
if($p.Count -eq 1 -and $p[0].Service -ieq 'qcpep' -and $p[0].ConfigManagerErrorCode -eq 0){Write-Host 'PEP core started: code 0. CPU management and system low power remain disabled.'}
else{Write-Host 'PEP core did not start. Send the status table; report saved.'}
