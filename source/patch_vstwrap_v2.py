import sys, struct, pefile, hashlib
# usage: patch_vstwrap_v2.py original_SfVstWrap.dll original_vegas220.exe out.dll [cap_MB]
# VEGAS Pro 22 build 250.
#  1) Freeze fix (same as v1): SfVstWrap's two "am I the main thread?" helpers walk a system-wide Toolhelp32
#     snapshot on every VST call; cache the main thread id after the first walk.
#  2) VRAM cap: vegas220.exe is integrity/license-checked on disk, so instead of patching it, a routine in a new
#     section of this DLL patches vegas220's in-memory SetBudget (rva 0xa58430) once, at the first VST host call,
#     to clamp the GPU frame-texture pool budget to cap_MB. It verifies the exact original bytes first and does
#     nothing if they differ (other build / other host process).
src, exe, dst = sys.argv[1], sys.argv[2], sys.argv[3]
cap_mb = int(sys.argv[4]) if len(sys.argv) > 4 else 5120
data = bytearray(open(src, 'rb').read())
assert hashlib.sha256(data).hexdigest() == 'd1e6e50e7c826596b84c0d4938eafbba070101ff62c81ce831736da00a65d9a4', 'unexpected SfVstWrap.dll'
exe_data = open(exe, 'rb').read()
assert hashlib.sha256(exe_data).hexdigest() == '46f0b64d9bea16087596b78d4f2dd71decea762c03e599c989d9b717c7002ed3', 'unexpected vegas220.exe'
vpe = pefile.PE(data=exe_data, fast_load=True)
SB_SITE, SB_BACK = 0xa5843f, 0xa5844e                 # 15 bytes: mov rsi,rdx / mov rdi,rcx / lea rbx,[rcx+8] / mov [rsp+30h],rbx
site_orig = vpe.get_data(SB_SITE, 15)
assert site_orig == bytes.fromhex('488bf2488bf9488d590848895c2430'), site_orig.hex()

pe = pefile.PE(data=bytes(data), fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_SECURITY']])
sec = {s.Name.rstrip(b'\0').decode(): s for s in pe.sections}
foff = pe.get_offset_from_rva
def r32(frm_next, to): return struct.pack('<i', to - frm_next)

IAT_GCTID, IAT_GMHW, IAT_GPA = 0x5d7378, 0x5d7348, 0x5d7370
CACHE = 0x76be40
txt, dsec = sec['.text'], sec['.data']

# ---------- new section layout (code + data, RWX) ----------
reloc = sec['.reloc']
NEW_VA = (reloc.VirtualAddress + reloc.Misc_VirtualSize + 0xfff) & ~0xfff
APPLY = NEW_VA                      # ApplyVramCap()
# data offsets inside the new section
D_FLAG, D_VP, D_RET, D_WK32, D_AVP, D_WV22 = 0x180, 0x188, 0x190, 0x1a0, 0x1c0, 0x1e0
FLAG, VPSLOT, RETSLOT, WK32, AVP, WV22 = (NEW_VA + o for o in (D_FLAG, D_VP, D_RET, D_WK32, D_AVP, D_WV22))

c = bytearray()
fix = {}                            # label -> list of (pos_of_rel32, kind)
def here(): return NEW_VA + len(c)
def rip(op, target):                # op bytes followed by rip-relative disp32 (no trailing imm)
    c.extend(op); c.extend(r32(here() + 4, target))
done_jumps = []
def jcc_done(op):                   # 0f 85 / 0f 84 rel32 -> done
    c.extend(op); done_jumps.append(len(c)); c.extend(b'\0\0\0\0')

c += b'\x53'                                         # push rbx
c += b'\x48\x83\xec\x30'                             # sub rsp,30h
c += b'\xb0\x01'                                     # mov al,1
rip(b'\x86\x05', FLAG)                               # xchg [FLAG],al   (run once)
c += b'\x84\xc0'                                     # test al,al
jcc_done(b'\x0f\x85')                                # jnz done
rip(b'\x48\x8d\x0d', WV22)                           # lea rcx,L"vegas220.exe"
rip(b'\xff\x15', IAT_GMHW)                           # call GetModuleHandleW -> vegas220 base, or NULL in any other host
c += b'\x48\x85\xc0'; jcc_done(b'\x0f\x84')          # test rax,rax / jz done
c += b'\x48\x89\xc3'                                 # mov rbx,rax
for off in (0, 7):                                   # verify the 15 original bytes (two overlapping qwords)
    c += b'\x48\x8b\x83' + struct.pack('<i', SB_SITE + off)          # mov rax,[rbx+site+off]
    c += b'\x48\xb9' + site_orig[off:off + 8] if off == 0 else b'\x48\xb9' + exe_data[vpe.get_offset_from_rva(SB_SITE + 7):vpe.get_offset_from_rva(SB_SITE + 7) + 8]
    c += b'\x48\x39\xc8'                             # cmp rax,rcx
    jcc_done(b'\x0f\x85')                            # jne done
rip(b'\x48\x8d\x0d', WK32)                           # lea rcx,L"kernel32.dll"
rip(b'\xff\x15', IAT_GMHW)                           # call GetModuleHandleW
c += b'\x48\x85\xc0'; jcc_done(b'\x0f\x84')          # test rax,rax / jz done
c += b'\x48\x89\xc1'                                 # mov rcx,rax
rip(b'\x48\x8d\x15', AVP)                            # lea rdx,"VirtualProtect"
rip(b'\xff\x15', IAT_GPA)                            # call GetProcAddress
c += b'\x48\x85\xc0'; jcc_done(b'\x0f\x84')          # test rax,rax / jz done
rip(b'\x48\x89\x05', VPSLOT)                         # mov [VPSLOT],rax
c += b'\x48\x8d\x8b' + struct.pack('<i', SB_SITE)    # lea rcx,[rbx+site]
c += b'\xba\x0f\x00\x00\x00'                         # mov edx,15
c += b'\x41\xb8\x40\x00\x00\x00'                     # mov r8d,PAGE_EXECUTE_READWRITE
c += b'\x4c\x8d\x4c\x24\x28'                         # lea r9,[rsp+28h]
c += b'\xff\xd0'                                     # call rax (VirtualProtect)
c += b'\x85\xc0'; jcc_done(b'\x0f\x84')              # test eax,eax / jz done
c += b'\x48\x8d\x83' + struct.pack('<i', SB_BACK)    # lea rax,[rbx+back]
rip(b'\x48\x89\x05', RETSLOT)                        # mov [RETSLOT],rax
CLAMP_LEA_AT = len(c)
c += b'\x48\x8d\x05\0\0\0\0'                         # lea rax,[CLAMP]  (patched below)
c += b'\x48\x89\x83' + struct.pack('<i', SB_SITE + 6)              # mov [site+6],rax      (abs target)
c += b'\xc6\x83' + struct.pack('<i', SB_SITE + 14) + b'\x90'      # mov byte [site+14],90h (nop)
c += b'\xc7\x83' + struct.pack('<i', SB_SITE + 2) + b'\0\0\0\0'   # mov dword [site+2],0   (rip+0)
c += b'\x66\xc7\x83' + struct.pack('<i', SB_SITE) + b'\xff\x25'   # mov word [site],25FFh  (jmp [rip+0]) - last
c += b'\x48\x8d\x8b' + struct.pack('<i', SB_SITE)    # lea rcx,[rbx+site]
c += b'\xba\x0f\x00\x00\x00'                         # mov edx,15
c += b'\x44\x8b\x44\x24\x28'                         # mov r8d,[rsp+28h]  (old protection)
c += b'\x4c\x8d\x4c\x24\x2c'                         # lea r9,[rsp+2Ch]
rip(b'\xff\x15', VPSLOT)                             # call [VPSLOT]  (restore protection)
DONE = len(c)
c += b'\x48\x83\xc4\x30'                             # add rsp,30h
c += b'\x5b'                                         # pop rbx
c += b'\xc3'                                         # ret
for p in done_jumps:
    c[p:p + 4] = struct.pack('<i', DONE - (p + 4))
# clamp cave (vegas220 SetBudget jumps here)
while len(c) % 16: c += b'\xcc'
CLAMP = here()
c[CLAMP_LEA_AT + 3:CLAMP_LEA_AT + 7] = r32(NEW_VA + CLAMP_LEA_AT + 7, CLAMP)
c += b'\x48\x8b\xf2'                                 # mov rsi,rdx      (new budget)
c += b'\x48\x8b\xf9'                                 # mov rdi,rcx
c += b'\x48\xb8' + struct.pack('<Q', cap_mb * 1048576)  # mov rax,cap
c += b'\x48\x3b\xf0'                                 # cmp rsi,rax
c += b'\x48\x0f\x47\xf0'                             # cmova rsi,rax
c += b'\x48\x8d\x59\x08'                             # lea rbx,[rcx+8]
c += b'\x48\x89\x5c\x24\x30'                         # mov [rsp+30h],rbx
rip(b'\xff\x25', RETSLOT)                            # jmp [RETSLOT]
assert len(c) <= D_FLAG
sect = bytearray(0x200)
sect[:len(c)] = c
sect[D_WK32:D_WK32 + 26] = 'kernel32.dll\0'.encode('utf-16le')
sect[D_AVP:D_AVP + 15] = b'VirtualProtect\0'
sect[D_WV22:D_WV22 + 26] = 'vegas220.exe\0'.encode('utf-16le')

# ---------- freeze fix caves in .text slack (as v1, slow paths now call APPLY first) ----------
ORIG_SNAP = (b'\x31\xd2\xb9\x04\x00\x00\x00', b'\x33\xd2\xb9\x04\x00\x00\x00')
patches = [
    dict(snap=0x51fc36, back=0x51fc3d, fast_out=0x51fd28, sete=b'\x40\x0f\x94\xc5',
         found=0x51fce9, found_tail=b'\x3b\x44\x24\x50\x40\x0f\x94\xc5', tid_load=b'\x8b\x44\x24\x50', found_out=0x51fcf7),
    dict(snap=0x51fdcd, back=0x51fdd4, fast_out=0x51feb8, sete=b'\x41\x0f\x94\xc6',
         found=0x51fe7a, found_tail=b'\x3b\x45\xff\x41\x0f\x94\xc6', tid_load=b'\x8b\x45\xff', found_out=0x51fe87),
]
cave = (txt.VirtualAddress + txt.Misc_VirtualSize + 15) & ~15
CAVE_END = txt.VirtualAddress + txt.SizeOfRawData
def put(rva, blob):
    assert all(x == 0 for x in data[foff(rva):foff(rva) + len(blob)]), 'cave not empty'
    data[foff(rva):foff(rva) + len(blob)] = blob
for p in patches:
    snap_orig = bytes(data[foff(p['snap']):foff(p['snap']) + 7]); assert snap_orig in ORIG_SNAP
    flen = 6 + len(p['found_tail'])
    fo = bytes(data[foff(p['found']):foff(p['found']) + flen])
    assert fo[:2] == b'\xff\x15' and struct.unpack('<i', fo[2:6])[0] + p['found'] + 6 == IAT_GCTID and fo[6:] == p['found_tail']
    A = cave; a = bytearray()
    a += b'\x8b\x05' + r32(A + len(a) + 6, CACHE); a += b'\x85\xc0'
    jz = len(a); a += b'\x74\x00'
    a += b'\xff\x15' + r32(A + len(a) + 6, IAT_GCTID)
    a += b'\x3b\x05' + r32(A + len(a) + 6, CACHE)
    a += p['sete']; a += b'\xe9' + r32(A + len(a) + 5, p['fast_out'])
    a[jz + 1] = len(a) - (jz + 2)
    a += b'\xe8' + r32(A + len(a) + 5, APPLY)        # slow path: apply VRAM cap once
    a += snap_orig; a += b'\xe9' + r32(A + len(a) + 5, p['back'])
    put(A, a); cave = A + len(a)
    B = cave; b = bytearray()
    b += p['tid_load']; b += b'\x89\x05' + r32(B + len(b) + 6, CACHE)
    b += b'\xff\x15' + r32(B + len(b) + 6, IAT_GCTID); b += p['found_tail']
    b += b'\xe9' + r32(B + len(b) + 5, p['found_out'])
    put(B, b); cave = B + len(b)
    data[foff(p['snap']):foff(p['snap']) + 7] = b'\xe9' + r32(p['snap'] + 5, A) + b'\x90\x90'
    data[foff(p['found']):foff(p['found']) + flen] = b'\xe9' + r32(p['found'] + 5, B) + b'\x90' * (flen - 5)
assert cave <= CAVE_END
struct.pack_into('<I', data, txt.get_file_offset() + 8, cave - txt.VirtualAddress)
struct.pack_into('<I', data, dsec.get_file_offset() + 8, max(dsec.Misc_VirtualSize, CACHE + 4 - dsec.VirtualAddress))

# ---------- append the new section; move the (now invalid) certificate after it ----------
e_lfanew = struct.unpack_from('<I', data, 0x3c)[0]
nsec = struct.unpack_from('<H', data, e_lfanew + 6)[0]
optsz = struct.unpack_from('<H', data, e_lfanew + 20)[0]
opt = e_lfanew + 24
hdr_end = opt + optsz + 40 * nsec
size_of_headers = struct.unpack_from('<I', data, opt + 60)[0]
assert hdr_end + 40 <= size_of_headers and all(x == 0 for x in data[hdr_end:hdr_end + 40]), 'no room for a section header'
sec_dir = opt + 112 + 4 * 8                           # IMAGE_DIRECTORY_ENTRY_SECURITY (PE32+)
cert_off, cert_size = struct.unpack_from('<II', data, sec_dir)
raw_end = reloc.PointerToRawData + reloc.SizeOfRawData
assert cert_off == raw_end and cert_off + cert_size == len(data)
cert = bytes(data[cert_off:])
new_raw = raw_end
del data[cert_off:]
data += sect
struct.pack_into('<8sIIIIIIHHI', data, hdr_end, b'.vfix\0\0\0', len(sect), NEW_VA, len(sect), new_raw, 0, 0, 0, 0, 0xE0000020)
struct.pack_into('<H', data, e_lfanew + 6, nsec + 1)
struct.pack_into('<I', data, opt + 56, NEW_VA + 0x1000)  # SizeOfImage
struct.pack_into('<II', data, sec_dir, len(data), cert_size)
data += cert
open(dst, 'wb').write(data)
print('ApplyVramCap 0x%x, clamp 0x%x, cap %d MB, freeze caves end 0x%x (limit 0x%x)' % (APPLY, CLAMP, cap_mb, cave, CAVE_END))
print('patched sha256', hashlib.sha256(data).hexdigest())
