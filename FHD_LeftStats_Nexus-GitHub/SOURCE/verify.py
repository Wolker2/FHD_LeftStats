from pathlib import Path
from copy import deepcopy
from collections import defaultdict
import sys
import struct
from PIL import Image,ImageOps
from compile_srhd_dat import parse_blockpar, parse_bp_raw, unpack_dat_bytes, ser_bp_block

S=Path(__file__).resolve().parent
R=S.parent
def child(b,name): return next(e.child for e in b.elems if e.name==name and e.child is not None)
def prop(b,name): return next(e.value for e in b.elems if e.name==name and e.child is None)
def named(b,name):
    if any(e.name=='Name' and e.value==name for e in b.elems): return b
    for e in b.elems:
        if e.child is not None:
            found=named(e.child,name)
            if found is not None:return found
def merge(base,overlay):
    out=deepcopy(base);seen=defaultdict(int)
    for e in overlay.elems:
        if e.child is not None:
            i=seen[e.name];seen[e.name]+=1
            slots=[j for j,x in enumerate(out.elems) if x.name==e.name and x.child is not None]
            if i<len(slots):out.elems[slots[i]].child=merge(out.elems[slots[i]].child,e.child)
            else:out.elems.append(deepcopy(e))
        else:
            out.elems=[x for x in out.elems if not(x.name==e.name and x.child is None)]
            out.elems.append(deepcopy(e))
    return out
def main():
    vanilla=parse_blockpar(S/'fixtures/vanilla_ship.txt')
    baseline='--baseline' in sys.argv
    combined=vanilla if baseline else merge(vanilla,parse_bp_raw(unpack_dat_bytes((R/'CFG/Main.dat').read_bytes(),0xB1E8C689)))
    stats=named(combined,'FHD_LeftStatsPanel');cargo=named(combined,'PanelRH')
    assert stats is not None,'Statistics still belong to the mutually exclusive native tab'
    # Match the measured reference; the hold remains at its original location.
    handler='' if baseline else (S/'CFG/Rus/Lang.txt').read_text()
    assert prop(stats,'Pos')=='-93,52,7','Root frame does not match the reference with center correction'
    assert prop(stats,'Active')=='True','Root frame must be visible without a callback'
    assert prop(cargo,'Pos')=='410,12','Original hold position changed'
    assert ser_bp_block(named(combined,'Left'))==ser_bp_block(named(vanilla,'Left')), 'Equipment layout changed'
    assert prop(named(combined,'CaptainI'),'Pos')=='46,40,4', 'Portrait must match the reference aperture'
    assert prop(named(combined,'Skills'),'Pos')=='-43,0', 'Skill controls must move with their artwork'
    assert prop(named(combined,'PanelAddInfo'),'RectBarY')=='222,399,239,542', 'Scrollbar hit region did not move'
    for filename in ['Main.dat','Rus/Lang.dat','Eng/Lang.dat']:
        expected=parse_blockpar(S/'CFG'/filename.replace('.dat','.txt'))
        actual=parse_bp_raw(unpack_dat_bytes((R/'CFG'/filename).read_bytes(),0xB1E8C689))
        assert ser_bp_block(actual)==ser_bp_block(expected),filename+' binary roundtrip failed'
    text=(S/'CFG/Rus/Lang.txt').read_text()
    for token in ['t_OnEnteringForm','t_OnReEnteringForm','t_OnLeavingForm',"InterfaceState('Ship','FHD_LeftStatsPanel',1)","if(UICheckElement('Ship','PanelRight','IsActive')) ButtonClick('Ship','ToRH');"]:
        assert token in text, 'Missing lifecycle behavior: '+token
    def read_rgba_gi(path):
        data=path.read_bytes();h=struct.unpack_from('<16I',data)
        assert h[:2]==(26983,1) and h[10:12]==(0,1)
        offset,size=struct.unpack_from('<II',data,64)
        assert size==h[4]*h[5]*4 and offset+size==len(data)
        return Image.frombytes('RGBA',(h[4],h[5]),data[offset:],'raw','BGRA')
    frame=read_rgba_gi(R/'DATA/Image/Frame.gi')
    original=Image.open(S/'assets/FrameOriginal.png').convert('RGBA')
    mirrored=ImageOps.mirror(original)
    assert frame.crop((280,0,328,598)).tobytes()==mirrored.crop((280,0,328,598)).tobytes(), 'Attachment is not mirrored'
    assert frame.crop((52,199,232,331)).tobytes()==original.crop((95,199,275,331)).tobytes(), 'Skill symbols changed direction'
    assert frame.crop((49,44,141,147)).tobytes()==original.crop((92,44,184,147)).tobytes(), 'Portrait aperture changed'
    for kind in ['Close','Hold']:
        for state in ['N','A','D']:
            sprite=read_rgba_gi(R/f'DATA/Image/{kind}{state}.gi')
            expected=ImageOps.mirror(Image.open(S/f'assets/{kind}{state}Original.png').convert('RGBA'))
            assert sprite.tobytes()==expected.tobytes()
    print('PASS: measured left geometry; original hold position and equipment; portrait, skills and scrollbar aligned; DAT roundtrips; handler declarations; exact GI pixels')
    print('NOT VERIFIED: full game execution, rendering, minimum-resolution clipping')
if __name__=='__main__':main()
