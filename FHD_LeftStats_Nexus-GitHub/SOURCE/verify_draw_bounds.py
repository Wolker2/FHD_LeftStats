"""Check the actual frame against each clipping ancestor at the target video mode."""
from pathlib import Path
from compile_srhd_dat import parse_blockpar,parse_bp_raw,unpack_dat_bytes
from verify import merge,named,prop

S=Path(__file__).resolve().parent
R=S.parent
def optional(b,key,default):
    return next((e.value for e in b.elems if e.name==key and e.child is None),default)
def ancestors(b,target,path=()):
    if b is target:return path
    for e in b.elems:
        if e.child is not None:
            found=ancestors(e.child,target,path+(b,))
            if found is not None:return found

def main():
    original=parse_blockpar(S/'fixtures/vanilla_ship.txt')
    overlay=parse_bp_raw(unpack_dat_bytes((R/'CFG/Main.dat').read_bytes(),0xB1E8C689))
    tree=merge(original,overlay);stats=named(tree,'FHD_LeftStatsPanel')
    path=ancestors(tree,stats);assert path
    width,height=1920,1080
    x,y=map(int,prop(stats,'Pos').split(',')[:2]);right=x+328;bottom=y+598
    if optional(stats,'PosAutoCorrection','False')=='True':
        dx=round((width-1024)*float(prop(stats,'PosAutoCorrectionXCoef')))
        dy=round((height-768)*float(prop(stats,'PosAutoCorrectionYCoef')))
        x+=dx;right+=dx;y+=dy;bottom+=dy
    for parent in reversed(path):
        name=optional(parent,'Name','(anonymous)')
        size=optional(parent,'Size',None)
        if size:
            pw,ph=map(int,size.split(',')[:2])
            # Native TFormShip initialization at 0x6d4a1f sets MainPanel.Size
            # to the actual VM width/height, rather than the CFG's 1024x768.
            if name=='MainPanel':pw,ph=width,height
            assert 0<=x and 0<=y and right<=pw and bottom<=ph, f'Frame clipped by {name}: frame={(x,y,right,bottom)}, parent={(pw,ph)}'
        pos=optional(parent,'Pos','0,0').split(',')
        px,py=int(pos[0]),int(pos[1]);x+=px;right+=px;y+=py;bottom+=py
    assert (x,y,right,bottom)==(355,208,683,806),'Frame no longer matches the supplied reference'
    assert path[-1] is named(tree,'MainPanel'),'Statistics are no longer direct children of fullscreen MainPanel'
    assert optional(stats,'Active','True')=='True','Statistics are hidden by default'
    for p in [S/'CFG/Main.txt',S/'CFG/Rus/Lang.txt',S/'CFG/Eng/Lang.txt']:
        assert "InterfaceState('Ship','FHD_LeftStatsPanel',0)" not in p.read_text(),'Startup/leave handler still hides the real panel'
    print('PASS: full 328x598 frame lies inside all clipping ancestors at 1920x1080; exact reference position; visible by default; no startup hide override')

if __name__=='__main__':main()
