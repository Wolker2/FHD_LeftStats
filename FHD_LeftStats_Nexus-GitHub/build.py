#!/usr/bin/env python3
"""Rebuild the supplied LeftStats ALPHA from its original text and PNG sources."""
import argparse,hashlib,json,platform,shutil,subprocess,sys,tempfile,zipfile,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PREFIX='Mods/FHD_MODS/FHD_LeftStats/'
EXPECTED_EXE='83300344af802bc51e64389c58f047e5afdf195c133048098be3881fae29ed98'
def sha(data):return hashlib.sha256(data).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def rebuild(verify=False,exe=None):
    logs={}
    with tempfile.TemporaryDirectory(prefix='leftstats-source-build-') as td:
        root=Path(td);shutil.copytree(ROOT/'SOURCE',root/'SOURCE',ignore=shutil.ignore_patterns('__pycache__','*.pyc','FrameLeft.png'))
        (root/'ModuleInfo.txt').write_bytes((root/'SOURCE/ModuleInfo.txt').read_bytes().decode('utf-8').encode('cp1251'))
        def run(name,args):
            p=subprocess.run(args,cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            logs[name]=p.stdout
            if p.returncode:
                print(p.stdout);raise RuntimeError(name+' failed, exit '+str(p.returncode))
            print('PASS:',name,flush=True)
        run('original_source_build',[sys.executable,str(root/'SOURCE/build.py')])
        expected=load(ROOT/'SOURCE/RUNTIME_SHA256.json')
        files={name:(root/name).read_bytes() for name in expected}
        if verify:
            for name in ('verify.py','verify_draw_bounds.py','verify_dual_panels.py'):
                run(name,[sys.executable,str(root/'SOURCE'/name)])
        if exe:
            exe=Path(exe).resolve();assert sha(exe.read_bytes())==EXPECTED_EXE,'Unsupported game EXE fixture'
            for name in ('verify_native_switch.py','verify_native_lifecycle.py'):
                run(name,[sys.executable,str(root/'SOURCE'/name),'--exe',str(exe)])
        # Match the editable cache to compiled bytes and check all local image paths.
        sys.path.insert(0,str(root/'SOURCE'))
        from compile_srhd_dat import parse_blockpar,ser_cache_block,unpack_dat_bytes
        tree=parse_blockpar(root/'SOURCE/CFG/CacheData.txt')
        assert ser_cache_block(tree)==unpack_dat_bytes(files['CFG/CacheData.dat'],0xea8f3f37)
        refs=[]
        def walk(node):
            for e in node.elems:
                if e.child is not None:walk(e.child)
                elif e.value.lower().endswith('.gi'):
                    path=e.value.replace('\\','/');assert path.startswith(PREFIX),path
                    relative=path[len(PREFIX):];assert relative in files,'Missing image '+relative
                    refs.append(path)
        walk(tree)
        assert len(refs)==7
        digest={name:sha(data) for name,data in files.items()};changed=[n for n in files if digest[n]!=expected[n]]
        from PIL import __version__ as pillow_version
        report={'status':'PASS' if not changed else 'BUILT: modified runtime differs from original','mod_version':'0.5 FirstOpenFix ALPHA','runtime_files':len(files),'dat_files':4,'gi_files':7,'metadata_files':1,'byte_identical_files':len(files)-len(changed),'different_files':changed,'sha256':digest,'prebuilt_runtime_inputs_used':False,'game_required_for_build':False,'resource_references_checked':len(refs),'resource_references_missing':[],'standalone_verification_suites':3 if verify else 0,'native_verification_suites':2 if exe else 0,'native_fixture_sha256':EXPECTED_EXE if exe else None,'full_game_executed':False,'full_rscript_vm_executed':False,'actual_game_rendering_tested':False,'github_workflow_executed':False,'python':platform.python_version(),'pillow':pillow_version,'zlib':zlib.ZLIB_RUNTIME_VERSION,'logs':logs}
        return files,report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify-original',action='store_true');p.add_argument('--verify',action='store_true');p.add_argument('--exe',type=Path);p.add_argument('--output-dir',type=Path,default=ROOT/'dist');a=p.parse_args()
    files,report=rebuild(a.verify or bool(a.exe),a.exe)
    if a.verify_original and report['different_files']:raise SystemExit('Original hash mismatch: '+repr(report['different_files']))
    out=a.output_dir;out.mkdir(parents=True,exist_ok=True);target=out/'FHD_LeftStats_0.5_FirstOpenFix_ALPHA_FROM_SOURCE.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted({**{PREFIX+n:b for n,b in files.items()},'README_RU.txt':(ROOT/'README_RU.txt').read_bytes()}.items()):
            info=zipfile.ZipInfo(name,(2026,10,29,0,0,0));info.external_attr=0o100644<<16;z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    report['output_sha256']=sha(target.read_bytes());report['distribution_readme_files']=1
    (out/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','runtime_files','byte_identical_files','resource_references_checked','standalone_verification_suites','native_verification_suites')}))
if __name__=='__main__':main()
