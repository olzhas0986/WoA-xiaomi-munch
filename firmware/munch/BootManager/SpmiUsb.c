// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <Uefi.h>
#include <Protocol/LoadedImage.h>
#include <Library/UefiLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/UefiBootServicesTableLib.h>
VOID MunchSpmiUsbSnapshot(EFI_LOADED_IMAGE_PROTOCOL *Image) {
 typedef UINT32 (EFIAPI *READ_LONG)(VOID *,UINT32,UINT32,UINT32,UINT8 *,UINT32,UINT32 *);
 EFI_GUID Guid={0xfa5f306b,0xf47d,0x4ac4,{0xa4,0x7d,0x88,0x2f,0x82,0x04,0xec,0x30}};
 STATIC CONST UINT16 Registers[]={0x1506,0x1508,0x150b,0x1544,0x1140};
 UINT8 *Base,*Protocol,Value;
 UINT64 Revision;
 UINT32 Crc,Result,Read;
 UINTN I;
 READ_LONG ReadLong;
 EFI_STATUS Status;
 if (Image==NULL || Image->ImageSize!=0xb000) { Print(L"SPMI USB: expected module unavailable\n");return; }
 Base=Image->ImageBase;
 Status=gBS->LocateProtocol(&Guid,NULL,(VOID **)&Protocol);
 if (EFI_ERROR(Status)) { Print(L"SPMI USB lookup: %r\n",Status);return; }
 CopyMem(&Revision,Protocol,8);CopyMem(&ReadLong,Protocol+8,8);
 if (Revision!=0x10001 || (UINTN)ReadLong!=(UINTN)Base+0x13dc) { Print(L"SPMI USB: read ABI mismatch revision=%lx\n",Revision);return; }
 Status=gBS->CalculateCrc32(Base+0x13dc,0xb8,&Crc);
 if (EFI_ERROR(Status) || Crc!=0xe72b1d9a) { Print(L"SPMI USB: read code mismatch\n");return; }
 // PM8150B USID2 from captured stock/mainline board evidence. Only stable
 // identity/configuration/status bytes are read; no interrupt-latch clearing.
 for (I=0;I<ARRAY_SIZE(Registers);I++) {
  Value=0xff;Read=0;
  Result=ReadLong(Protocol,2,0,Registers[I],&Value,1,&Read);
  if (Result==0 && Read==1) Print(L"SPMI sid2 reg=%04x value=%02x\n",Registers[I],Value);
  else Print(L"SPMI sid2 reg=%04x error=%x bytes=%u\n",Registers[I],Result,Read);
 }
}

// Narrow temporary policy: only PM8150B USID2 TYPEC_MODE_CFG is writable.
// Called after USBIN is verified absent and the OTG command bit is clear.
typedef UINT32 (EFIAPI *MODE_READ)(VOID *,UINT32,UINT32,UINT32,UINT8 *,UINT32,UINT32 *);
typedef UINT32 (EFIAPI *MODE_WRITE)(VOID *,UINT32,UINT32,UINT32,UINT8 *,UINT32);
STATIC VOID *ModeProtocol;
STATIC MODE_READ ModeRead;
STATIC MODE_WRITE ModeWrite;
STATIC UINT8 SavedMode;
STATIC BOOLEAN RestoreMode;
STATIC EFI_STATUS WriteMode (UINT8 Value) {
 UINT8 Actual=0xff;
 UINT32 Count=0,Result;
 Result=ModeWrite(ModeProtocol,2,0,0x1544,&Value,1);
 Print(L"TypeC mode write=%02x status=%x\n",Value,Result);
 if(Result!=0) return EFI_DEVICE_ERROR;
 Result=ModeRead(ModeProtocol,2,0,0x1544,&Actual,1,&Count);
 Print(L"TypeC mode readback=%02x status=%x bytes=%u\n",Actual,Result,Count);
 return Result==0 && Count==1 && Actual==Value ? EFI_SUCCESS : EFI_DEVICE_ERROR;
}
// PM8150B TYPEC_MODE_CFG: disable=bit0, sink=bit1, source=bit2,
// try-source=bit3 and try-sink=bit4 (Linux qcom_pmic_typec_port.c).
// Accept explicit supported policies, never reserved/contradictory bit patterns.
STATIC EFI_STATUS BeginSourceMode (VOID) {
 UINT32 Count=0;
 EFI_STATUS Status;
 if(RestoreMode) return EFI_ALREADY_STARTED;
 if(ModeRead(ModeProtocol,2,0,0x1544,&SavedMode,1,&Count)!=0 || Count!=1) return EFI_DEVICE_ERROR;
 Print(L"TypeC original mode=%02x\n",SavedMode);
 switch(SavedMode) {
  case 0x00: // DRP without try preference
  case 0x01: // disabled
  case 0x02: // sink only
  case 0x04: // source only
  case 0x08: // try source
  case 0x10: // try sink (mainline default)
  case 0x12: // vendor try-sink/sink-only
   break;
  default:
   Print(L"TypeC mode rejected: unknown/reserved policy %02x\n",SavedMode);
   return EFI_UNSUPPORTED;
 }
 Print(L"TypeC saved mode=%02x; temporary source-only\n",SavedMode);
 RestoreMode=TRUE; // Also undo a partially completed/failed write.
 Status=WriteMode(0x01); // Linux TCPM sequence: disable, then set role.
 if(EFI_ERROR(Status)) return Status;
 gBS->Stall(10000);
 return WriteMode(0x04);
}
EFI_STATUS MunchSpmiUsbSource (EFI_LOADED_IMAGE_PROTOCOL *Image) {
 EFI_GUID Guid={0xfa5f306b,0xf47d,0x4ac4,{0xa4,0x7d,0x88,0x2f,0x82,0x04,0xec,0x30}};
 UINT8 *Base,*Protocol;
 UINT64 Revision;
 UINT32 Crc;
 EFI_STATUS Status;
 if(RestoreMode) return EFI_ALREADY_STARTED;
 if(Image==NULL || Image->ImageBase==NULL || Image->ImageSize!=0xb000) return EFI_UNSUPPORTED;
 Base=Image->ImageBase;
 Status=gBS->LocateProtocol(&Guid,NULL,(VOID **)&Protocol);
 if(EFI_ERROR(Status)) return Status;
 CopyMem(&Revision,Protocol,8);
 CopyMem(&ModeRead,Protocol+8,8);CopyMem(&ModeWrite,Protocol+16,8);
 Print(L"SPMI source ABI: rev=%lx read-rva=%lx write-rva=%lx\n",Revision,
       (UINTN)ModeRead-(UINTN)Base,(UINTN)ModeWrite-(UINTN)Base);
 if(Revision!=0x10001 || (UINTN)ModeRead!=(UINTN)Base+0x13dc ||
    (UINTN)ModeWrite!=(UINTN)Base+0x1494) {
  Print(L"SPMI source ABI rejected\n");return EFI_UNSUPPORTED;
 }
 if(EFI_ERROR(gBS->CalculateCrc32(Base+0x13dc,0xb8,&Crc)) || Crc!=0xe72b1d9a ||
    EFI_ERROR(gBS->CalculateCrc32(Base+0x1494,0x98,&Crc)) || Crc!=0x7034a44d) return EFI_COMPROMISED_DATA;
 ModeProtocol=Protocol;
 return BeginSourceMode ();
}
EFI_STATUS MunchSpmiUsbRestore (VOID) {
 EFI_STATUS Status;
 if(!RestoreMode) return EFI_SUCCESS;
 Status=WriteMode(SavedMode);
 if(!EFI_ERROR(Status)) RestoreMode=FALSE;
 Print(L"TypeC original mode restore: %r\n",Status);
 return Status;
}

// Read the actual OTG command bit. GetOtg reports the boost FSM state,
// which need not change immediately when the command is cleared.
EFI_STATUS MunchSpmiUsbOtgCommand (EFI_LOADED_IMAGE_PROTOCOL *Image, BOOLEAN *Enabled) {
 EFI_GUID Guid={0xfa5f306b,0xf47d,0x4ac4,{0xa4,0x7d,0x88,0x2f,0x82,0x04,0xec,0x30}};
 UINT8 *Base,*Protocol,Value=0xff;
 MODE_READ Read;
 UINT64 Revision;
 UINT32 Crc,Count=0;
 EFI_STATUS Status;
 if(Enabled==NULL) return EFI_INVALID_PARAMETER;
 *Enabled=TRUE;
 if(Image==NULL || Image->ImageBase==NULL || Image->ImageSize!=0xb000) return EFI_UNSUPPORTED;
 Base=Image->ImageBase;
 Status=gBS->LocateProtocol(&Guid,NULL,(VOID **)&Protocol);
 if(EFI_ERROR(Status)) return Status;
 CopyMem(&Revision,Protocol,8);CopyMem(&Read,Protocol+8,8);
 if(Revision!=0x10001 || (UINTN)Read!=(UINTN)Base+0x13dc) return EFI_UNSUPPORTED;
 if(EFI_ERROR(gBS->CalculateCrc32(Base+0x13dc,0xb8,&Crc)) || Crc!=0xe72b1d9a) return EFI_COMPROMISED_DATA;
 if(Read(Protocol,2,0,0x1140,&Value,1,&Count)!=0 || Count!=1) return EFI_DEVICE_ERROR;
 *Enabled=(Value & 1)!=0;
 Print(L"PMIC OTG command sid2 reg1140=%02x enabled=%u\n",Value,*Enabled);
 return EFI_SUCCESS;
}
