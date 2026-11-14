#Requires -RunAsAdministrator
param([ValidateSet('prepare','status','start')][string]$Phase='prepare')
$ErrorActionPreference='Stop'
if((Get-CimInstance Win32_ComputerSystem).Model.Trim() -ne 'POCO F4'){throw 'Only POCO F4'}
$Store='C:\munch-gpu-pep-late'
if(-not(Test-Path $Store)){New-Item -ItemType Directory $Store | Out-Null}
$PepServiceKey='HKLM:\SYSTEM\CurrentControlSet\Services\qcpep'
$Id='ACPI\QCOM2519\0'
function Value($key,$name){
 if(-not(Test-Path -LiteralPath $key)){return $null}
 $item=Get-ItemProperty -LiteralPath $key
 $p=$item.PSObject.Properties[$name]
 if($null -ne $p){return $p.Value}
 return $null
}
function Problem { [int](Get-PnpDeviceProperty -InstanceId $Id -KeyName DEVPKEY_Device_ProblemCode).Data }
function Logged($exe,[string[]]$arguments,$name){
 $o=& $exe @arguments 2>&1;$code=$LASTEXITCODE
 $o | Out-File -Encoding UTF8 (Join-Path $Store $name)
 $o | ForEach-Object {Write-Host $_}
 return $code
}
function Status {
 Write-Host ('Service Start: '+(Value $PepServiceKey 'Start')+' (4 = disabled)')
 Write-Host ('PEP problem: '+(Problem)+' (22 = disabled device)')
 Get-CimInstance Win32_SystemDriver -Filter "Name='qcpep'" | Format-Table Name,State,StartMode
}
if($Phase -eq 'status'){Status;exit 0}
if((Value $PepServiceKey 'Start') -ne 4){throw 'Keep qcpep startup disabled before this operation'}
if($Phase -eq 'prepare'){
 $before=Problem
 if($before -ne 22){
  $code=Logged 'pnputil.exe' @('/disable-device',$Id,'/force') 'disable-device.txt'
  if($code -notin @(0,3010)){throw 'Device disable failed; no driver startup changes were made'}
 }
 Status
 Write-Host 'Boot Windows29 with service still disabled, then run status. Expect problem 22.'
 exit 0
}
# Start phase is a separate explicit operation after the disabled-device boot.
if((Problem) -ne 22){throw 'Late start requires PEP problem 22 after reboot; run prepare first'}
$driver=Get-CimInstance Win32_SystemDriver -Filter "Name='qcpep'"
if($driver.State -ne 'Stopped'){throw 'The PEP driver must be stopped before the late-load test'}
$pages=@(Get-CimInstance Win32_PageFileUsage)
if(@($pages | Where-Object {$_.AllocatedBaseSize -gt 0}).Count -eq 0){throw 'No active pagefile reported; refusing a test that may not produce a dump'}
$crash='HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl'
if((Value $crash 'CrashDumpEnabled') -notin @(1,2,3,7)){throw 'Crash dump recording is not enabled; inspect CrashControl first'}
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class LatePepFirmware {
 [DllImport("kernel32.dll")] static extern uint GetSystemFirmwareTable(uint p,uint id,[Out]byte[] b,uint n);
 public static string Ssdt(){uint n=GetSystemFirmwareTable(0x41435049,0x54445353,null,0);if(n<36||n>2097152)throw new InvalidOperationException("Cannot read SSDT");byte[] b=new byte[n];if(GetSystemFirmwareTable(0x41435049,0x54445353,b,n)!=n)throw new InvalidOperationException("Cannot read SSDT");return System.Text.Encoding.ASCII.GetString(b);}
}
'@
$table=[LatePepFirmware]::Ssdt()
if(-not $table.Contains('PEPH') -or -not $table.Contains('QCOM2519')){throw 'Boot Windows29; its PEPH contract is required'}
$policy=Get-Content -Raw (Join-Path $PSScriptRoot 'policy.json') | ConvertFrom-Json
foreach($setting in $policy.settings){
 $key=Join-Path $PepServiceKey 'Parameters';if($setting.subkey){$key=Join-Path $key $setting.subkey}
 if((Value $key $setting.name) -ne $setting.value){throw ('PEP test policy differs: '+$setting.name)}
}
$expected=@{'QCOM250B'='qcscm';'QCOM2533'='QCRPEN';'QCOM250C'='qcspmi';'QCOM252E'='qcpmic'}
foreach($hid in $expected.Keys){
 $dev=@(Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -match ('^ACPI\\'+$hid+'\\')})
 if($dev.Count -ne 1){throw ('Missing required device '+$hid)}
 $problem=Get-PnpDeviceProperty -InstanceId $dev[0].InstanceId -KeyName DEVPKEY_Device_ProblemCode
 $serviceProperty=Get-PnpDeviceProperty -InstanceId $dev[0].InstanceId -KeyName DEVPKEY_Device_Service
 if([int]$problem.Data -ne 0 -or $serviceProperty.Data -ine $expected[$hid]){throw ('Required service is not ready: '+$hid)}
}
$Tag=[guid]::NewGuid().ToString('N').Substring(0,8)
$Session='MunchPepLate-'+$Tag
$Trace=Join-Path $env:SystemRoot ('System32\LogFiles\WMI\'+$Session+'.etl')
$Providers=Join-Path $PSScriptRoot 'providers.txt'
$code=Logged 'logman.exe' @('create','trace',$Session,'-o',$Trace,'-pf',$Providers,'-f','bin','-max','32','-bs','64','-nb','4','32','-ft','00:00:01','-ets') 'trace-start.txt'
if($code -ne 0){throw 'Fresh live tracing failed; PEP remains disabled'}
$active=$true
try{
 $code=Logged 'logman.exe' @('query',$Session,'-ets') 'trace-query.txt'
 if($code -ne 0){throw 'Cannot confirm live trace'}
 [ordered]@{time=(Get-Date).ToString('o');session=$Session;trace=$Trace;crash_dump_enabled=(Value $crash 'CrashDumpEnabled');pagefiles=@($pages | Select-Object Name,AllocatedBaseSize);phase='before-demand-start'} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $Store 'attempt.json')
 $code=Logged 'sc.exe' @('config','qcpep','start=','demand') 'set-demand.txt'
 if($code -ne 0 -or (Value $PepServiceKey 'Start') -ne 3){throw 'Cannot set demand start'}
 Write-Host 'Live trace is recording. Enabling the already-installed PEP now.'
 $code=Logged 'pnputil.exe' @('/enable-device',$Id) 'enable-device.txt'
 if($code -notin @(0,3010)){throw 'PEP enable returned an error; trace retained'}
 Status
 if($code -eq 3010){Write-Host 'Enable requested reboot. Do not repeat the early-boot test; collect these logs.'}
}finally{
 # This executes only if Windows remains running. Recovery instructions apply
 # if the kernel crashes or hangs before this block can execute.
 $restore=Logged 'sc.exe' @('config','qcpep','start=','disabled') 'restore-disabled.txt'
 if($restore -ne 0){Write-Host 'Startup restore failed; set qcpep disabled before rebooting.'}
 if($active){$null=Logged 'logman.exe' @('stop',$Session,'-ets') 'trace-stop.txt'}
}
Write-Host 'Late test returned. PEP boot startup was restored to disabled; collect logs.'
