#Requires -RunAsAdministrator
# Diagnostic collection only: never start/enable a driver or alter policy.
$ErrorActionPreference='Stop'
if((Get-CimInstance Win32_ComputerSystem).Model.Trim() -ne 'POCO F4'){throw 'Only POCO F4'}
$Stamp=(Get-Date).ToString('yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,6)
$Work=Join-Path $env:TEMP ('munch-pep-diag-'+$Stamp)
New-Item -ItemType Directory $Work | Out-Null
$Work=(Get-Item -LiteralPath $Work).FullName
$Errors=New-Object System.Collections.Generic.List[string]
function Json($name,$value){$value | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 (Join-Path $Work $name)}
function Attempt($name,[scriptblock]$action){try{& $action}catch{$Errors.Add($name+': '+$_.Exception.Message)}}
function NativeLog($exe,[string[]]$arguments,$name){
 & $exe @arguments 2>&1 | Out-File -Encoding UTF8 (Join-Path $Work $name)
 if($LASTEXITCODE -ne 0){$Errors.Add($exe+' exit '+$LASTEXITCODE)}
}
$Budget=128MB
function CopyBounded($source,$relative){
 $dest=Join-Path $Work $relative
 New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
 $inputFile=[IO.File]::Open($source,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
 try{
  $length=$inputFile.Length
  if($length -gt 64MB -or $length -gt $script:Budget){throw 'Collection size limit reached'}
  $outputFile=[IO.File]::Open($dest,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try{
   $buffer=New-Object byte[] 65536
   $remaining=$length
   while($remaining -gt 0){
    $n=$inputFile.Read($buffer,0,[int][Math]::Min($buffer.Length,$remaining))
    if($n -eq 0){throw 'Short file read'}
    $outputFile.Write($buffer,0,$n);$remaining-=$n
   }
  }finally{$outputFile.Dispose()}
  $script:Budget-=$length
 }finally{$inputFile.Dispose()}
}
Attempt 'system' {
 Json 'system.json' ([ordered]@{time=(Get-Date).ToString('o');machine=(Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,NumberOfProcessors,NumberOfLogicalProcessors);os=(Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,LastBootUpTime);processor=@(Get-CimInstance Win32_Processor | Select-Object Name,DeviceID,Architecture,NumberOfCores,NumberOfLogicalProcessors)})
}
Attempt 'devices' {
 $rows=@(Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -match '^ACPI\\(?:QCOM250B|QCOM2533|QCOM250C|QCOM252E|QCOM2519)\\'} | ForEach-Object {
  $row=[ordered]@{instance=$_.InstanceId;name=$_.FriendlyName;status=$_.Status;properties=@()}
  $row.properties=@(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_ProblemCode,DEVPKEY_Device_ProblemStatus,DEVPKEY_Device_Service,DEVPKEY_Device_DriverInfPath,DEVPKEY_Device_DriverVersion,DEVPKEY_Device_Driver,DEVPKEY_Device_HardwareIds -ErrorAction SilentlyContinue | Select-Object KeyName,Type,Data)
  $row
 })
 Json 'devices.json' $rows
}
Attempt 'drivers' {
 $drivers=@(Get-CimInstance Win32_SystemDriver | Where-Object {$_.Name -in @('qcpep','qcscm','qcspmi','qcpmic','QCRPEN')} | Select-Object Name,State,StartMode,PathName)
 Json 'drivers.json' $drivers
 foreach($driver in $drivers){
  $file=$driver.PathName.Trim('"')
  if($file -like '\SystemRoot\*'){$file=Join-Path $env:SystemRoot $file.Substring(12)}
  if($file -like '\??\*'){$file=$file.Substring(4)}
  if(Test-Path -LiteralPath $file){(Get-FileHash -Algorithm SHA256 -LiteralPath $file | Select-Object Path,Hash) | ConvertTo-Json -Compress | Add-Content -Encoding UTF8 (Join-Path $Work 'driver-hashes.jsonl')}
 }
}
Attempt 'registry' {
 $keys=@('HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl','HKLM:\SYSTEM\CurrentControlSet\Services\qcpep','HKLM:\SYSTEM\CurrentControlSet\Services\qcpep\Parameters','HKLM:\SYSTEM\CurrentControlSet\Services\qcpep\Parameters\DirectedPState','HKLM:\SYSTEM\CurrentControlSet\Services\qcpep\Parameters\PARKSEL','HKLM:\SYSTEM\CurrentControlSet\Control\WMI\Autologger\qcpep-rpmh','HKLM:\SYSTEM\CurrentControlSet\Control\WMI\Autologger\MunchPepBoot','HKLM:\SYSTEM\CurrentControlSet\Enum\ACPI\QCOM2519\0','HKLM:\SYSTEM\CurrentControlSet\Enum\ACPI\QCOM2519\0\Device Parameters')
 $driverKey=Get-PnpDeviceProperty -InstanceId 'ACPI\QCOM2519\0' -KeyName DEVPKEY_Device_Driver -ErrorAction SilentlyContinue
 if($driverKey -and $driverKey.Data -match '^\{[0-9A-Fa-f-]+\}\\[0-9]{4}$'){
  $classKey=Join-Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Class' $driverKey.Data
  $keys+=@($classKey,(Join-Path $classKey 'Resources'),(Join-Path $classKey 'SystemLibResources'),(Join-Path $classKey 'Parameters'))
 }
 $values=@(foreach($key in $keys){if(Test-Path -LiteralPath $key){[ordered]@{key=$key;values=(Get-ItemProperty -LiteralPath $key | Select-Object -Property * -ExcludeProperty PSPath,PSParentPath,PSChildName,PSDrive,PSProvider)}}})
 Json 'registry.json' $values
}
Attempt 'PEP own logs' {
 $folder='C:\munch-gpu-pep-core'
 if(Test-Path $folder){Get-ChildItem -LiteralPath $folder -File | ForEach-Object {CopyBounded $_.FullName ('pep-core/'+$_.Name)}}
}
Attempt 'trace preparation logs' {
 $folder='C:\munch-gpu-pep-trace'
 if(Test-Path $folder){Get-ChildItem -LiteralPath $folder -File | ForEach-Object {CopyBounded $_.FullName ('trace-setup/'+$_.Name)}}
}
Attempt 'late test logs' {
 $folder='C:\munch-gpu-pep-lmh'
 if(Test-Path $folder){Get-ChildItem -LiteralPath $folder -File | ForEach-Object {CopyBounded $_.FullName ('lmh-test/'+$_.Name)}}
 $folder='C:\munch-gpu-pep-late'
 if(Test-Path $folder){Get-ChildItem -LiteralPath $folder -File | ForEach-Object {CopyBounded $_.FullName ('late-test/'+$_.Name)}}
}
Attempt 'minidumps' {
 $path=Join-Path $env:SystemRoot 'Minidump'
 if(Test-Path $path){Get-ChildItem -LiteralPath $path -File -Filter '*.dmp' | ForEach-Object {Attempt ('minidump '+$_.Name) {CopyBounded $_.FullName ('minidumps/'+$_.Name)}}}
}
Attempt 'setupapi' {CopyBounded (Join-Path $env:SystemRoot 'INF\setupapi.dev.log') 'setupapi.dev.log'}
Attempt 'System events' {NativeLog 'wevtutil.exe' @('epl','System',(Join-Path $Work 'System.evtx')) 'export-system.txt'}
Attempt 'PnP events' {NativeLog 'wevtutil.exe' @('epl','Microsoft-Windows-Kernel-PnP/Configuration',(Join-Path $Work 'Kernel-PnP.evtx')) 'export-pnp.txt'}
Attempt 'providers' {NativeLog 'logman.exe' @('query','providers') 'trace-providers.txt'}
Attempt 'PEP device stack' {NativeLog 'pnputil.exe' @('/enum-devices','/instanceid','ACPI\QCOM2519\0','/stack','/drivers') 'pep-stack.txt'}
Attempt 'existing PEP traces' {
 $path=Join-Path $env:SystemRoot 'System32\LogFiles\WMI'
 $files=@(Get-ChildItem -LiteralPath $path -File -ErrorAction SilentlyContinue | Where-Object {$_.Name -like '*pep*.etl*'})
 # Preserve all boot-counter files before timestamp-sorted live test files;
 # the device's wall clock resets and cannot reliably order different boots.
 $late=@($files | Where-Object {$_.Name -like 'MunchPepLate*.etl*'} | Sort-Object LastWriteTime -Descending)
 $boot=@($files | Where-Object {$_.Name -like 'MunchPepBoot.etl*'} | Sort-Object Name)
 $other=@($files | Where-Object {$_.Name -notlike 'MunchPepBoot.etl*' -and $_.Name -notlike 'MunchPepLate*.etl*'} | Sort-Object LastWriteTime -Descending)
 $traces=@(@($late+$boot+$other) | Select-Object -First 8)
 foreach($file in $traces){Attempt ('trace '+$file.Name) {CopyBounded $file.FullName ('traces/'+$file.Name)}}
}
Attempt 'ACPI' {
 Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class PepDiagnosticFirmware {
 [DllImport("kernel32.dll",SetLastError=true)] static extern uint GetSystemFirmwareTable(uint provider,uint id,[Out] byte[] buffer,uint size);
 public static byte[] Table(string signature){uint id=BitConverter.ToUInt32(System.Text.Encoding.ASCII.GetBytes(signature),0);uint n=GetSystemFirmwareTable(0x41435049,id,null,0);if(n==0)return null;if(n<36||n>2097152)throw new InvalidOperationException("Invalid firmware table size");byte[] data=new byte[n];if(GetSystemFirmwareTable(0x41435049,id,data,n)!=n)throw new InvalidOperationException("Firmware table read failed");return data;}
}
'@
 foreach($signature in @('DSDT','SSDT','FACP','APIC','GTDT','CSRT')){
  $data=[PepDiagnosticFirmware]::Table($signature)
  if($null -ne $data){[IO.File]::WriteAllBytes((Join-Path $Work ($signature+'.aml')),$data)}
 }
}
Json 'collection.json' ([ordered]@{purpose='Recovery-state diagnostic snapshot; PEP not started';time=(Get-Date).ToString('o');registry_modified=$false;driver_started=$false;notes='Live firmware is the current recovery boot, not necessarily the previously hung Windows29. ETL files are bounded live copies, not newly started traces.';errors=@($Errors.ToArray())})
$manifest=@(Get-ChildItem -LiteralPath $Work -Recurse -File | ForEach-Object {$hash=Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName;[ordered]@{path=$_.FullName.Substring($Work.Length+1);bytes=$_.Length;sha256=$hash.Hash}})
Json 'manifest.json' $manifest
$Desktop=[Environment]::GetFolderPath('Desktop')
$Zip=Join-Path $Desktop ('munch-pep-diag-'+$Stamp+'.zip')
Compress-Archive -Path (Join-Path $Work '*') -DestinationPath $Zip -CompressionLevel Optimal
Write-Host "Saved: $Zip"
Write-Host ('Optional collection errors: '+$Errors.Count)
