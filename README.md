# VEGAS Pro 22 Lag Fix

**Instant splices and drags, and much lower VRAM use, for VEGAS Pro 22 (build 250).**

If VEGAS Pro 22 does any of these, this is for you:

- You split a clip (**S**) and it takes **4–10 seconds** to actually happen, sometimes with **"Not Responding"**.
- You click and drag a clip and it doesn't move for several seconds, then **teleports** into place.
- VEGAS eats **13–20+ GB of VRAM**, even on a simple one-track timeline, and playback starts dropping frames.

---

## Before you start

1. Open VEGAS → **Help → About VEGAS Pro**. It must say **Version 22.0 (Build 250)**.
   Any other version: the installer will tell you it can't be applied and **won't change anything**.
2. Windows 10 or 11 (64-bit).

## Install (about 1 minute)

1. Click the green **Code** button at the top of this page → **Download ZIP**.
2. Right-click the downloaded ZIP → **Extract All…**
3. **Close VEGAS Pro 22.**
4. Open the extracted folder and double-click **`Install.bat`**.
5. Windows asks *"Do you want to allow this app to make changes?"* → click **Yes**.
6. You should see **`[OK] Installed!`** Press Enter to close the window. That's it. Open VEGAS and edit like normal.

> If Windows shows **"Windows protected your PC"**, click **More info → Run anyway**.
> The scripts are plain text. Open `installer.ps1` in Notepad if you want to see exactly what they do.

## Uninstall

Close VEGAS, then double-click **`Uninstall.bat`** → **Yes**. Your original file is put back.
(Reinstalling or "Repair"-ing VEGAS Pro 22 also undoes the fix.)

---

## What it changes

- **Only one file:** `SfVstWrap.dll` in your VEGAS Pro 22 folder. The original is saved next to it as `SfVstWrap.dll.original-backup`.
- `vegas220.exe` is **never touched**. VEGAS checks that file at startup and won't run if it has been changed.
- The installer only patches your file if it is the **exact** original build 250 file, and only saves the result if it's **byte-for-byte identical** to the tested version.
- No VEGAS files are included in this download. The installer edits your own copy.
- Your plug-ins (VST, OFX, Sapphire, Universe, etc.), projects, and settings are not affected.

## Results (one test PC, 24 GB GPU, 4K + 1080p project)

| | Before | After |
|---|---|---|
| Split / drag a clip | 7–11 s freeze, "Not Responding" | Instant |
| VEGAS VRAM use | ~14 GB (17–21 GB for the whole GPU) | ~9 GB (~12.5 GB for the whole GPU) |

---

## Why this happens (for the curious)

### 1. The splice/drag freeze
Whenever VEGAS talks to a **VST audio plug-in** (for example the bundled MAGIX *Analogue Modelling Suite* on a track), its plug-in host (`SfVstWrap.dll`) asks *"am I running on the main thread?"*.
To answer, it takes a snapshot of **every thread of every program running on your PC** and walks through the list. With lots of programs open (browsers, launchers, overlays…) that's often 10,000–15,000+ threads, so each check takes ~0.15 s. And one splice triggers dozens of checks.

That's why it's worse the more apps you have open, and why older VEGAS versions on less busy PCs didn't seem to do it.
**Fix:** do the check once, remember the answer (the main thread never changes), and compare instantly after that.

### 2. The VRAM hog
VEGAS keeps decoded video frames on the GPU as a cache. At startup it sets that cache's size limit to roughly **half of your free VRAM** (~10 GB on a 24 GB card), on top of everything else it uses, and it fills it up fast (timeline thumbnails alone can create thousands of frames).
**Fix:** cap that cache at **5 GB**. Because VEGAS refuses to start if `vegas220.exe` is modified, the cap is applied in memory after VEGAS starts, from `SfVstWrap.dll`, and only after checking that the code it changes is exactly what's expected.

---

## Notes

- Not affiliated with VEGAS Creative Software, MAGIX, or Boris FX. Use at your own risk. Tested on one PC.
- VEGAS Pro 2026/2027 appear to have the same plug-in thread-scan issue. This fix does **not** support those versions.
- `source/patch_vstwrap_v2.py` is the script that produced the patch, for anyone who wants to check or rebuild it.
