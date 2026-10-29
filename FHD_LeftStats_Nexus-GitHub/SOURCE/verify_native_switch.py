"""Run the actual native tab switch with stubbed UI object methods (not a game run)."""
import sys,struct,argparse,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
from compile_srhd_dat import parse_blockpar,parse_bp_raw,unpack_dat_bytes
from verify import merge,named,prop
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--exe',type=Path,required=True)
parser.add_argument('--vanilla',action='store_true')
args=parser.parse_args()
expected='83300344af802bc51e64389c58f047e5afdf195c133048098be3881fae29ed98'
if hashlib.sha256(args.exe.read_bytes()).hexdigest()!=expected:raise SystemExit('This probe supports only the documented reference executable SHA256 '+expected)
root=Path(__file__).resolve().parent.parent
b=parse_blockpar(root/'SOURCE/fixtures/vanilla_ship.txt')
if not args.vanilla:b=merge(b,parse_bp_raw(unpack_dat_bytes((root/'CFG/Main.dat').read_bytes(),0xB1E8C689)))
pe=pefile.PE(str(args.exe))
u=Uc(UC_ARCH_X86,UC_MODE_32);base=pe.OPTIONAL_HEADER.ImageBase;payload=pe.get_memory_mapped_image()
u.mem_map(base,(len(payload)+4095)&~4095);u.mem_write(base,payload)
u.mem_map(0x1800000,0x10000);u.mem_map(0x2000000,0x800000);u.mem_map(0x3000000,0x10000)
def put(addr,v):u.mem_write(addr,struct.pack('<I',v&0xffffffff))
def get(addr):return struct.unpack('<I',u.mem_read(addr,4))[0]
VMT=0x2000000;FORM=0x2100000;STOP=0x1800800;SETPOS=0x1800100;SETACTIVE=0x1800200
put(VMT+12,SETPOS);put(VMT+40,SETACTIVE)
objects={};addresses={};states={};parents={};nodes={};counter=0

def visit(node,parent=None):
 global counter
 key=id(node);parents[key]=parent;nodes[key]=node
 name=next((e.value for e in node.elems if e.name=='Name'),None)
 active=next((e.value for e in node.elems if e.name=='Active'),'True')!='False'
 states[key]=active
 if name:
  assert name not in objects,'duplicate name '+name
  addr=0x2200000+counter*0x200;counter+=1
  objects[name]=(addr,key);addresses[addr]=name;put(addr,VMT)
  pos=next((e.value for e in node.elems if e.name=='Pos'),'0,0').split(',')
  put(addr+0x20,int(pos[0]));put(addr+0x24,int(pos[1]) if len(pos)>1 else 0)
 for e in node.elems:
  if e.child is not None:visit(e.child,key)
visit(b)

def visible(name):
 key=objects[name][1]
 while key is not None:
  if not states[key]:return False
  key=parents[key]
 return True

def ret():
 sp=u.reg_read(UC_X86_REG_ESP);pc=get(sp);u.reg_write(UC_X86_REG_ESP,sp+4);u.reg_write(UC_X86_REG_EIP,pc)

def hook(uc,addr,size,user):
 if addr==STOP:uc.emu_stop();return
 if addr==0x4cefc8:
  ptr=uc.reg_read(UC_X86_REG_EDX);raw=bytearray()
  while (c:=bytes(uc.mem_read(ptr,2)))!=b'\0\0':raw.extend(c);ptr+=2
  name=raw.decode('utf-16le');assert name in objects,'native name not found: '+name
  uc.reg_write(UC_X86_REG_EAX,objects[name][0]);ret()
 elif addr==0x414ea0:
  ptr=uc.reg_read(UC_X86_REG_ECX);put(ptr,uc.reg_read(UC_X86_REG_EAX));put(ptr+4,uc.reg_read(UC_X86_REG_EDX));ret()
 elif addr==SETPOS:
  obj=uc.reg_read(UC_X86_REG_EAX);p=uc.reg_read(UC_X86_REG_EDX);put(obj+0x20,get(p));put(obj+0x24,get(p+4));ret()
 elif addr==SETACTIVE:
  obj=uc.reg_read(UC_X86_REG_EAX);states[objects[addresses[obj]][1]]=bool(uc.reg_read(UC_X86_REG_EDX)&255);ret()
 elif addr==0x7a568c:ret()
 elif addr==0x78c078:uc.reg_write(UC_X86_REG_EAX,0x2600000);ret()
 elif addr==0x70e5e0:uc.reg_write(UC_X86_REG_EAX,0x2610000);ret()
u.hook_add(UC_HOOK_CODE,hook)
put(FORM,VMT);put(FORM+0x378,410);put(0x87bbd8,0x2600000);u.mem_write(0x2610070,b'\1')
# Use the actual serialized default visibility, without faking an entry callback.
# In the old design the same name belonged to the mutually exclusive native tab.
real='FHD_LeftStatsPanel' if 'FHD_LeftStatsPanel' in objects else 'PanelRight'
u.mem_write(FORM+0x4a4,b'\0')
sp=0x300f000;put(sp,STOP);u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_EAX,FORM)
u.emu_start(0x6f50e8,STOP,count=5000)
print('Executed native x86 handler 0x6f50e8; real statistics visible:',visible(real),'; hold visible:',visible('PanelRH'))
assert visible(real) and visible('PanelRH'),'Native switching hid a required panel'
print('PASS: native open-hold operation preserves the independent real statistics panel')
