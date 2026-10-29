"""Build the SRHD overlay and lossless GI assets. Requires Pillow."""
from pathlib import Path
import struct
from PIL import Image, ImageOps, ImageDraw
from compile_srhd_dat import build_bp, build_cache

S=Path(__file__).resolve().parent
R=S.parent

def write_gi(image,path):
    image=image.convert('RGBA');w,h=image.size
    header=struct.pack('<16I',26983,1,0,0,w,h,0xff0000,0xff00,0xff,0xff000000,0,1,0,0,0,0)
    payload=image.tobytes('raw','BGRA')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(header+struct.pack('<8I',96,len(payload),0,0,w,h,0,0)+payload)

def build_frame():
    original=Image.open(S/'assets/FrameOriginal.png').convert('RGBA')
    frame=ImageOps.mirror(original)
    # The perimeter and attachment face right. The inner panels, portrait hole,
    # skill symbols and their original left-to-right order stay readable.
    mask=Image.new('L',original.size,0);draw=ImageDraw.Draw(mask)
    draw.rounded_rectangle((65,8,310,374),radius=28,fill=255)
    draw.rounded_rectangle((65,374,310,572),radius=24,fill=255)
    shifted=Image.new('RGBA',original.size);shifted.paste(original,(-43,0))
    shifted_mask=Image.new('L',original.size);shifted_mask.paste(mask,(-43,0))
    frame=Image.composite(shifted,frame,shifted_mask)
    # The supplied reference is authoritative for the opaque decorative rim.
    # Sample only static rim pixels; no portrait, labels, buttons or scene
    # background enters the game texture. Native alpha and attachments remain.
    reference=Image.open(S/'assets/ReferenceFrameRGB.png').convert('RGB')
    for y in range(frame.height):
        for x in range(278):
            rim=x<30 or x>=255 or y<13 or 369<=y<=378 or y>=565
            button=(54<=x<122 and y>=560) or (134<=x<203 and y>=561)
            if rim and not button and frame.getpixel((x,y))[3]==255:
                frame.putpixel((x,y),reference.getpixel((x,y))+(255,))
    return frame

def main():
    build_bp(S/'CFG/Main.txt',R/'CFG/Main.dat')
    build_cache(S/'CFG/CacheData.txt',R/'CFG/CacheData.dat')
    for language in ['Rus','Eng']:build_bp(S/'CFG'/language/'Lang.txt',R/'CFG'/language/'Lang.dat')
    frame=build_frame();write_gi(frame,R/'DATA/Image/Frame.gi');frame.save(S/'assets/FrameLeft.png')
    for kind in ['Close','Hold']:
        for state in ['N','A','D']:
            image=ImageOps.mirror(Image.open(S/f'assets/{kind}{state}Original.png'))
            write_gi(image,R/f'DATA/Image/{kind}{state}.gi')
    print('Built Main.dat, CacheData.dat, Rus/Eng Lang.dat, seven GI resources')

if __name__=='__main__':main()
