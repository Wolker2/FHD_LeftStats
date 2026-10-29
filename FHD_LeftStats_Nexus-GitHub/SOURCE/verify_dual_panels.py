"""Verify that native tab switching cannot hide the real statistics container."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
from compile_srhd_dat import parse_blockpar,parse_bp_raw,unpack_dat_bytes,ser_bp_block
from verify import named,prop,merge

S=Path(__file__).resolve().parent
R=S.parent

def names(b):
    result=[]
    for e in b.elems:
        if e.child is not None:result.extend(names(e.child))
        elif e.name=='Name':result.append(e.value)
    return result

def main():
    original=parse_blockpar(S/'fixtures/vanilla_ship.txt')
    overlay=parse_bp_raw(unpack_dat_bytes((R/'CFG/Main.dat').read_bytes(),0xB1E8C689))
    combined=merge(original,overlay)
    stats=named(combined,'FHD_LeftStatsPanel')
    assert stats is not None,'Statistics still use the native mutually exclusive PanelRight container'
    native_tab=named(combined,'PanelRight')
    assert named(native_tab,'CaptainI') is None,'Native tab switching still owns the portrait'
    assert named(stats,'CaptainI') is not None and named(stats,'Skills') is not None
    assert prop(stats,'Pos')=='-93,52,7','Root panel does not match the measured reference'
    assert prop(stats,'Size')=='328,598' and prop(stats,'Active')=='True'
    for key in ['ToRH','FromRH']:
        hidden=named(native_tab,key)
        assert hidden is not None and prop(hidden,'Active')=='False','Native switch must remain bound to a hidden compatible button'
    for key in ['FHD_StatsKeepOpen','FHD_HoldKeepOpen']:
        button=named(combined,key)
        assert button is not None
        assert any(e.name=='OnPressCode' and e.child is not None for e in button.elems)
    count=Counter(names(combined))
    for n in ['PanelRight','PanelRH','ToRH','FromRH','CaptainA','CaptainI','RewardsImg','Skills','PanelAddInfo','ShipName','CharName']:
        assert count[n]==1,f'Broken native binding: {n} occurs {count[n]} times'
    cargo=deepcopy(named(combined,'PanelRH'))
    visible_button=named(cargo,'FHD_HoldKeepOpen')
    for e in visible_button.elems:
        if e.name=='Name':e.value='FromRH'
        if e.name=='Help':e.value='FormShip.CloseHold'
    visible_button.elems=[e for e in visible_button.elems if e.name!='OnPressCode']
    assert ser_bp_block(cargo)==ser_bp_block(named(original,'PanelRH')),'Cargo geometry, art or item controls changed'
    assert ser_bp_block(named(combined,'Left'))==ser_bp_block(named(original,'Left')),'Equipment changed'
    handler=(S/'CFG/Rus/Lang.txt').read_text()
    assert "InterfaceState('Ship','PanelRight',1)" not in handler
    assert "InterfaceState('Ship','PanelRH',1)" not in handler
    assert "InterfacePos('Ship','PanelRight',-688" not in handler
    assert "InterfaceState('Ship','FHD_LeftStatsPanel',1)" in handler
    assert "if(UICheckElement('Ship','PanelRight','IsActive')) ButtonClick('Ship','ToRH');" in handler
    print('PASS: independent statistics parent; hidden native tab bindings; both visible box buttons preserve hold mode; unique native control bindings; unchanged cargo geometry and equipment')
    print('Game execution remains unverified; this checks the serialized configuration and handler contracts.')

if __name__=='__main__':main()
