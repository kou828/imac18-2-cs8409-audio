#!/usr/bin/env python3
"""
Verify that every struct this module shares with the kernel has the SAME
memory layout as the target kernel.

Why this exists
---------------
The module vendors private copies of the kernel's sound/hda headers. If one of
those copies disagrees with the kernel by even a single field, every later
field of the enclosing struct sits at the wrong offset. The kernel then reads
garbage - and because these structs drive array indices (autocfg.num_inputs),
the result is an out-of-bounds walk and a hard lockup, with NO compile error
and NO unresolved symbol to warn you.

A mismatch can make the module interpret kernel-owned memory with incorrect offsets and may cause a hard lockup when loaded.

Ground truth is the kernel's own BTF, not any source tree:
  * running kernel      -> /sys/kernel/btf/*
  * any other kernel    -> BTF read out of /lib/modules/<kver>/**.ko, using the
                           vmlinux extracted from /boot/vmlinuz-<kver> as the
                           base BTF (needs root; /boot/vmlinuz is mode 0600)

Usage:
    python3 verify-abi.py [--kver KVER]

Exit codes:
    0  all comparable layouts agree; review any skipped types before use
    1  MISMATCH - do not load, this risks a hard lockup
    2  could not verify (missing pahole/BTF) - do not load the module
"""
import argparse, glob, os, re, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.abspath(__file__))
RUNNING = os.uname().release
SND_MODULES = ["snd-hda-codec-generic", "snd-hda-codec", "snd-hda-core", "snd"]
CFLAGS = ("-g -DAPPLE_PINSENSE_FIXUP -DAPPLE_CODECS -DCONFIG_SND_HDA_RECONFIG=1 "
          "-Wno-unused-variable -Wno-unused-function")


def sh(cmd, timeout=180):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)


# ---------------------------------------------------------------- BTF sources
def extract_vmlinux(kver, tmp):
    """Pull an ELF vmlinux (with .BTF) out of the packed boot image."""
    img = f"/boot/vmlinuz-{kver}"
    if not os.path.exists(img):
        return None
    if not os.access(img, os.R_OK):
        print(f"  note: {img} is not readable (needs root)")
        return None
    script = None
    for c in (f"/usr/src/linux-headers-{kver}/scripts/extract-vmlinux",
              f"/lib/modules/{kver}/build/scripts/extract-vmlinux"):
        if os.path.exists(c):
            script = c
            break
    if not script:
        return None
    out = os.path.join(tmp, "vmlinux")
    r = subprocess.run(["bash", script, img], capture_output=True, timeout=300)
    if not r.stdout:
        return None
    open(out, "wb").write(r.stdout)
    if b".BTF" not in sh(f"readelf -S {out}").stdout.encode(errors="replace"):
        return None
    return out


def btf_sources(kver, tmp):
    """-> list of (btf_file, base_btf_or_None), highest-value source first."""
    if kver == RUNNING:
        srcs = [(f"/sys/kernel/btf/{m.replace('-', '_')}", None) for m in SND_MODULES]
        srcs.append(("/sys/kernel/btf/vmlinux", None))
        return [(p, b) for p, b in srcs if os.path.exists(p)]

    # A kernel that is not running: reconstruct its BTF from what is on disk.
    base = extract_vmlinux(kver, tmp)
    if not base:
        return []
    out = []
    for m in SND_MODULES:
        hits = glob.glob(f"/lib/modules/{kver}/kernel/**/{m}.ko*", recursive=True)
        if not hits:
            continue
        src, dst = hits[0], os.path.join(tmp, m + ".ko")
        if src.endswith(".zst"):
            if sh(f"zstd -dqf {src} -o {dst}").returncode != 0:
                continue
        elif src.endswith(".xz"):
            if sh(f"xz -dcf {src} > {dst}").returncode != 0:
                continue
        else:
            shutil.copy(src, dst)
        out.append((dst, base))
    out.append((base, None))
    return out


# ------------------------------------------------------------- module layouts
def candidates(kver):
    files = [os.path.join(REPO, f) for f in
             ("hda_local.h", "hda_generic.h", "hda_jack.h", "hda_auto_parser.h")]
    files.append(f"/usr/src/linux-headers-{kver}/include/sound/hda_codec.h")
    names = []
    for f in files:
        if not os.path.exists(f):
            continue
        for m in re.finditer(r"^struct\s+(\w+)\s*\{", open(f, errors="replace").read(), re.M):
            if m.group(1) not in names:
                names.append(m.group(1))
    return names


def build_probe(tmp, names, kver):
    """Instantiate each struct, drop the ones that cannot compile, build with -g."""
    for hdr in glob.glob(os.path.join(REPO, "*.h")):
        dst = os.path.join(tmp, os.path.basename(hdr))
        if not os.path.exists(dst):
            os.symlink(hdr, dst)
    open(os.path.join(tmp, "Makefile"), "w").write(
        f"obj-m += probe.o\nccflags-y += {CFLAGS}\n"
        f"all:\n\tmake -C /lib/modules/{kver}/build M={tmp} modules\n")
    keep = list(names)
    for _ in range(40):
        src = ['#include <linux/module.h>', '#include "patch_cs8409.h"']
        src += [f"struct {n} probe_{n};" for n in keep]
        src.append('MODULE_LICENSE("GPL");')
        open(os.path.join(tmp, "probe.c"), "w").write("\n".join(src) + "\n")
        if os.path.exists(os.path.join(tmp, "probe.o")):
            os.remove(os.path.join(tmp, "probe.o"))
        r = sh(f"make -C {tmp}")
        if os.path.exists(os.path.join(tmp, "probe.o")):
            return keep
        # gcc uses typographic quotes depending on locale - accept both
        log = r.stdout + r.stderr
        bad = set(re.findall(r"probe_(\w+)['\u2018\u2019] has incomplete type", log))
        bad |= set(re.findall(r"storage size of ['\u2018\u2019]probe_(\w+)['\u2018\u2019] isn"
                             r"['\u2018\u2019]?t known", log))
        if not bad:
            print((r.stdout + r.stderr)[-2500:])
            return None
        keep = [n for n in keep if n not in bad]
    return None


def layout(src, struct, base=None):
    """-> (size, [(member, offset, size)]) or None."""
    cmd = f"pahole {'--btf_base=' + base + ' ' if base else ''}-C {struct} {src}"
    try:
        out = sh(cmd, timeout=90).stdout
    except subprocess.TimeoutExpired:
        return None
    if "size:" not in out:
        return None
    size = re.search(r"/\* size: (\d+)", out)
    members = re.findall(r"^\s+.*?\b(\w+)(?:\[[^\]]*\])?;\s*/\*\s*(\d+)\s+(\d+)", out, re.M)
    return (int(size.group(1)) if size else None,
            [(m, int(o), int(s)) for m, o, s in members])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kver", default=RUNNING, help="kernel to verify against")
    kver = ap.parse_args().kver
    if not re.fullmatch(r"[0-9][A-Za-z0-9.+_-]*", kver):
        ap.error("invalid kernel release string")

    print(f"module source : {REPO}")
    print(f"target kernel : {kver}" + ("  (running)" if kver == RUNNING else "  (NOT running)"))

    if not shutil.which("pahole"):
        print("\nCANNOT VERIFY: pahole is not installed  (apt install dwarves)")
        return 2
    if not os.path.isdir(f"/lib/modules/{kver}/build"):
        print(f"\nCANNOT VERIFY: no build tree for {kver}")
        return 2

    with tempfile.TemporaryDirectory(prefix="cs8409-abi-") as tmp:
        srcs = btf_sources(kver, tmp)
        if not srcs:
            print(f"\nCANNOT VERIFY: no usable BTF for {kver}.")
            print("  The running kernel exposes /sys/kernel/btf; another kernel needs")
            print("  /boot/vmlinuz-<kver> readable (root) plus its scripts/extract-vmlinux.")
            return 2
        print(f"BTF sources   : {len(srcs)}")

        keep = build_probe(tmp, candidates(kver), kver)
        if keep is None:
            print("\nCANNOT VERIFY: the layout probe would not build")
            return 2
        obj = os.path.join(tmp, "probe.o")

        checked = skipped = 0
        skipped_names = []
        problems = []
        for n in keep:
            mine = layout(obj, n)
            if mine is None:
                continue
            theirs = None
            for path, base in srcs:
                theirs = layout(path, n, base)
                if theirs:
                    break
            if theirs is None:
                skipped += 1
                skipped_names.append(n)
                continue
            checked += 1
            mo = {m: o for m, o, _ in mine[1]}
            to = {m: o for m, o, _ in theirs[1]}
            if mine[0] != theirs[0]:
                problems.append(f"  {n}: size {mine[0]} (module) != {theirs[0]} (kernel)")
                for m in to:
                    if m in mo and mo[m] != to[m]:
                        problems.append(f"      first shifted field: {m} at {mo[m]} vs {to[m]}")
                        break
                for m in to:
                    if m not in mo:
                        problems.append(f"      kernel has a field the module lacks: {m}")
                        break
            else:
                bad = [m for m in to if m in mo and mo[m] != to[m]]
                if bad:
                    problems.append(f"  {n}: same size but {len(bad)} field(s) misplaced, e.g. {bad[0]}")

        print(f"structs compared: {checked}   (not in BTF, skipped: {skipped})")
        if skipped_names:
            print("not in BTF: " + ", ".join(skipped_names))
        if checked == 0:
            print("\nCANNOT VERIFY: no struct could be compared")
            return 2
        if problems:
            print(f"\nLAYOUT MISMATCH - DO NOT LOAD THIS MODULE:\n")
            print("\n".join(problems))
            print("\nLoading it risks a hard lockup. Fix the vendored headers to match.")
            return 1
        print("\nOK: every shared struct matches this kernel's layout.")
        return 0


sys.exit(main())
