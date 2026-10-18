#!/usr/bin/env python3
"""The list driver behind mk/uvmt/isim.mk: drive iSim over THIS checkout's own
file lists, cut where the makefile asks.

    isim_build.py --checkout <this core-v-verif checkout> --stage analyse|elaborate \
                  --upto <SECTION> --isim-vlog <path> --work <dir> [--cv-core <dir>]

isim.mk's targets call it (ISIM_BUILD defaults to this file).  The bench
ships the file list, so this reads it rather than retyping it into a make
variable where nobody would ever look at it again.  Every hard part of the
list is recorded below rather than quietly handled.  Until 2026-10-16 this
script lived in the iSim tree (test_piles/integration/bin/
core_v_verif_build.py); it moved here because what it knows -- the section
headers, the declared skips, the ISS flist, the defines every upstream flow
passes -- is knowledge about THIS bench, and belongs beside isim.mk.

WHAT IT READS FROM UPSTREAM, AND WHY EACH ONE IS READ RATHER THAN RETYPED
------------------------------------------------------------------------

  cv32e40p/tb/uvmt/uvmt_cv32e40p.flist
        The list itself.  It is a TREE, not a flat file: it pulls in ten more
        flists with `-f`, one per UVM library / agent / environment.  We
        expand that tree, so an agent upstream adds appears in the next run.

  mk/uvmt/uvmt.mk
        Every path in every one of those flists is written as `${DV_UVMA_...}`
        and friends.  Those variables are defined -- and exported -- by
        upstream's own makefile, so we PARSE THEM OUT OF IT.  Retyping the
        table here would fork their build in the one place nobody diffs.

  cv32e40p/sim/ExternalRepos.mk
        Names the CV32E40P RTL revision core-v-verif itself wants
        (CV_CORE_HASH).  The RTL we hand it comes from the sibling `cv32e40p`
        pin, which tracks a different revision for the RTL-only entries.  We
        do not silently reconcile that: `--cv-core` makes the script PRINT
        both, so the skew is in the log of every run.

  the `//` section headers inside uvmt_cv32e40p.flist
        `--upto` cuts the list at one of upstream's OWN section comments
        (Libraries / Agents / Environments).  The ladder of entries in
        isim.mk is built out of the list's own structure, not a
        selection of files found convenient.  A header that disappears is
        refused by name rather than silently yielding a shorter list.

WHAT THIS SCRIPT STILL DOES TO THE LIST, AND WHY
------------------------------------------------

Upstream's flist tree is handed to `isim-vlog -f` AS UPSTREAM WROTE IT.
`+incdir+` and nested `-f` inside a command file (SW-3990, 2026-08-14) and
`$VAR` / `${VAR}` paths (2026-10-14, integ_red_dashf_envvar) are the
analyser's own job, with upstream's DV_* table EXPORTED into its environment
exactly as `make SIMULATOR=...` exports it.  Two things remain ours, and both
are about WHICH lines, never about reading them:

  * the CUT.  `--upto` stops at one of upstream's own section headers in the
    top flist, so the copy handed to -f ends there.

  * the DECLARED SKIPS.  A line naming a file in MISSING_BY_DESIGN or
    EXCLUDED_BY_DESIGN is dropped from the copy and printed by name.  Those
    live in NESTED flists too (svlib_pkg.sv), so the copy is the tree
    FLATTENED: upstream's lines verbatim, `${VAR}` untouched, nested `-f`
    inlined, nothing else changed.

The walk that builds the copy also counts what it kept; that census is what
the entries pin ("N sources, M incdirs"), and iSim then reads the same lines.

Until 2026-10-14 this header blamed two defects (`-f` not honouring options,
`+define+` swallowed by the one-step driver) that had been fixed in August,
and the script went on expanding the tree by hand for two months after the
reason was gone.  What STILL stopped the hand-over was a third thing nobody
had measured: `${VAR}` in a command file (dvlcom expands it; isim-vlog did
not).  Fixed with the reduction above.

The script prints the command it runs and forwards the tool's exit status, so
the `.test` grades the TOOL, not the script.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


# The CV32E40P RTL's own manifest, parameterised by ${DESIGN_RTL_DIR} (its
# header says the caller sets it).  Translated to a copy under --work that is
# otherwise byte-for-byte upstream's, and handed to `isim-vlog -f`.
CV_CORE_MANIFEST = "cv32e40p_manifest.flist"


def translate_cv_core_manifest(checkout):
    """(translated_text, sources, incdir_count) from the RTL's manifest."""
    mf = Path(checkout) / CV_CORE_MANIFEST
    if not mf.is_file():
        red(f"RTL manifest missing: {mf}")
    text = mf.read_text().replace("${DESIGN_RTL_DIR}", str(Path(checkout) / "rtl"))
    sources, incdirs = [], 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("+incdir+"):
            incdirs += 1
        elif line.startswith(("+", "-")):
            pass  # another option: isim-vlog's own -f reader decides
        else:
            sources.append(os.path.normpath(line))
    missing = [x for x in sources if not Path(x).is_file()]
    if missing:
        red("the RTL manifest names files that are not in the checkout:\n  "
            + "\n  ".join(missing[:5]))
    if not sources:
        red(f"{CV_CORE_MANIFEST} yielded no sources")
    return text, sources, incdirs

CORE = "cv32e40p"
FLIST = f"{CORE}/tb/uvmt/uvmt_{CORE}.flist"
UVMT_MK = "mk/uvmt/uvmt.mk"
EXTERNAL_REPOS = f"{CORE}/sim/ExternalRepos.mk"

# Upstream's own section comments inside uvmt_cv32e40p.flist, in their order.
# `--upto` names one of these.  They are upstream's words, and if upstream
# renames one the script refuses rather than quietly analysing a different set.
SECTIONS = [
    "Libraries",
    "Agents",
    "Environments",
    "CV32E40P test bench Directories",
    "CV32E40P tests (includes constants/macros/types meant for test bench)",
    "CV32E40P test bench files",
    "FIXME:STR:Find a better location",
]

# Files upstream's list names that are NOT IN THE CHECKOUT BY DESIGN, by
# basename, with the reason.  svlib is cloned from bitbucket by
# ExternalRepos.mk at build time -- a `src/master` web URL, not a pinnable git
# commit -- so the checkout carries its flist and its .so but not its source.
#
# The set is DECLARED, and everything outside it is a hard failure, so that a
# file which goes missing for any other reason -- a rename upstream, a bad
# variable expansion, a half-finished provision -- still stops the run instead
# of shrinking the list.
MISSING_BY_DESIGN = {
    "svlib_pkg.sv":
        "verilab svlib; cloned from bitbucket by ExternalRepos.mk at build "
        "time, not a pinned commit. Nothing in the cv32e40p UVM environment "
        "imports svlib_pkg -- upstream's flist line is its only reference.",
}

# Files upstream's list names that ARE in the checkout but are deliberately
# left out of THIS stage, by basename, with the reason -- distinct from
# MISSING_BY_DESIGN above, which is for files the checkout never had at all.
# A file here is real, present, and simply not what this rung claims.
EXCLUDED_BY_DESIGN = {
    "uvmt_cv32e40p_tb.sv":
        "instantiates uvmt_cv32e40p_iss_wrap, the wrapper around the "
        "Imperas OVPsim reference model (imperas_iss.flist) -- licensed, "
        "third-party, not fetchable. Excluded from the analyse_uvmt rung by "
        "design: the analyse ladder stops short of the tb; `comp` adds it "
        "together with the vendored OVPM SV layer (--with-iss-sv).",
}


ISS_FLIST = f"{CORE}/tb/uvmt/imperas_iss.flist"

# THE DEFINES UPSTREAM'S OWN uvmt FLOW PASSES, mirrored -- not invented:
# mk/uvmt/uvmt.mk's SV_CMP_FLAGS carries +define+CV32E40P_ASSERT_ON for
# EVERY simulator, and each per-simulator mk (dsim.mk:39, vcs.mk:170,
# riviera.mk:79) adds +define+CV32E40P_TRACE_EXECUTION -- without it the
# wrapper's `ifdef-gated cv32e40p_tracer never exists and every
# step_compare / iss_wrap cross-module reference into tracer_i fails to
# bind at elaboration (measured: the "Unable to bind ...tracer_i.*"
# family).  SW-517200.
UPSTREAM_DEFINES = [
    "+define+CV32E40P_ASSERT_ON",
    "+define+CV32E40P_TRACE_EXECUTION",
    # Every upstream flow also compiles with -timescale "1ns/1ps"
    # (vsim.mk:89/119, riviera.mk:69, vcs.mk TIMESCALE).  Without it the
    # tool default 1ns/1ns folds every bare `* 1ps` literal to ZERO --
    # MEASURED: uvme_cv32e40p_reset_vseq started the clock with period
    # `cfg.sys_clk_period * 1ps` == 0 and the core never executed a
    # single instruction (identically degenerate under dsim without the
    # flag, which is why the early differential quietly matched).
    # Spelled as a list so both the vlog and elab command lines share it:
    # the elaborate stage re-parses stored bodies and must fold time the
    # same way (SW-520100).
    # Every upstream UVM flow also defines UVM (xrun.mk:178, vsim.mk:149,
    # vcs.mk:56).  imperas_CV32.sv gates on it: without it the wrapper's
    # `ifndef UVM` arm calls $finish right after svimp_entry() -- MEASURED,
    # the whole uvmt TB stopped at 1ns with "$finish called at 1 (1ns)"
    # from imperas_CV32.sv:735 the moment the OBI agents went active.
    "+define+UVM",
]

UPSTREAM_TIMESCALE = ["-timescale", "1ns/1ps"]


def expand_iss_flist(checkout, table):
    """imperas_iss.flist -> (incdirs, sources), the same ${VAR} expansion the
    main flist gets.  Every named file must exist: the OVPM SV layer is
    VENDORED (vendor_lib/imperas), so a missing file is a provision failure,
    never a licensing gap -- the licensed piece is the OVPsim runtime .so
    behind imperas_CV32.sv's DPI-C imports, which no analyse/elaborate stage
    touches."""
    fl = checkout / ISS_FLIST
    if not fl.is_file():
        red(f"ISS flist missing: {fl}")
    incdirs, sources = [], []
    for raw in fl.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        line = _expand(line, table)
        if line.startswith("+incdir+"):
            d = line[len("+incdir+"):]
            if Path(d).is_dir():
                incdirs.append(d)
        elif line.startswith(("+", "-")):
            pass
        else:
            if not Path(line).is_file():
                red(f"{ISS_FLIST} names a file not in the checkout: {line}")
            sources.append(line)
    if not sources:
        red(f"{ISS_FLIST} yielded no sources")
    return incdirs, sources


def red(msg):
    sys.exit(f"INTEGRATION RED: {msg}")


def upstream_vars(checkout):
    """The DV_* / TBSRC_HOME path table, PARSED OUT OF upstream's own uvmt.mk."""
    mk = checkout / UVMT_MK
    if not mk.is_file():
        red(f"upstream makefile missing: {mk}\n"
            f"  -- is this a core-v-verif checkout?")
    table = {"CORE_V_VERIF": str(checkout), "CV_CORE_LC": CORE, "CV_CORE": CORE}
    pat = re.compile(r"^\s*export\s+(DV_\w+|TBSRC_HOME)\s*=\s*(\S+)\s*$", re.M)
    found = pat.findall(mk.read_text())
    if not found:
        red(f"{UVMT_MK} yielded no `export DV_... =` path variables -- "
            f"upstream changed how the flists are parameterised, and this "
            f"script must be taught the new shape rather than guess.")
    table.update(found)
    for k in list(table):
        table[k] = _expand(table[k], table)
    return table


def _expand(s, table):
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\$\((\w+)\)|\$\{(\w+)\}",
                   lambda m: table.get(m.group(1) or m.group(2), m.group(0)), s)
    return s


def cv_core_hash(checkout):
    """The CV32E40P revision core-v-verif itself asks for."""
    er = checkout / EXTERNAL_REPOS
    if not er.is_file():
        return None
    m = re.search(r"^\s*CV_CORE_HASH\s*\??=\s*(\S+)", er.read_text(), re.M)
    return m.group(1) if m else None


def expand_flist(checkout, table, upto):
    """Walk upstream's flist TREE, cut at one of THEIR section headers.

    Returns (incdirs, sources, copy_lines): the census of what the cut keeps
    (paths expanded, for the counts and the existence checks) and the LINES
    to hand to `-f` -- upstream's own, verbatim, `${VAR}` untouched, nested
    `-f` inlined, declared skips and duplicate mentions removed.  Anything
    else beginning with `+` or `-` is refused rather than dropped, because
    silently ignoring a flag upstream added is how a run stops being the run
    upstream described.
    """
    if upto not in SECTIONS:
        red(f"--upto {upto!r} is not one of upstream's section headers: {SECTIONS}")
    stop_after = SECTIONS.index(upto)

    top = checkout / FLIST
    if not top.is_file():
        red(f"upstream flist missing: {top}")

    incdirs, sources, seen_sections = [], [], []
    entries = []                      # (kind, raw line, expanded path), in order
    state = {"section": -1, "stopped": False}

    def walk(path, is_top):
        path = Path(path)
        if not path.is_file():
            red(f"flist named by upstream is not in the checkout: {path}")
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if line.startswith("//"):
                if is_top:
                    head = line.lstrip("/ ").strip()
                    if head in SECTIONS:
                        seen_sections.append(head)
                        state["section"] = SECTIONS.index(head)
                        state["stopped"] = state["section"] > stop_after
                continue
            if not line or state["stopped"]:
                continue
            raw = line
            line = _expand(line, table)
            if line.startswith("-f "):
                walk(line[3:].strip(), False)
            elif line.startswith("+incdir+"):
                d = os.path.normpath(line[len("+incdir+"):])
                if d not in incdirs:
                    incdirs.append(d)
                    entries.append(("inc", raw, d))
            elif line.startswith(("+", "-")):
                red(f"{path.name} carries an option this harness does not "
                    f"handle: {line!r}")
            else:
                # Upstream's top-level list names two files TWICE, once via
                # ${DV_UVMT_PATH} and once via ${TBSRC_HOME}/uvmt, which are
                # the same directory. Analysing a module twice is not what
                # upstream means, so the second mention is dropped -- here,
                # visibly, and not by editing their file.
                s = os.path.normpath(line)
                if s not in sources:
                    sources.append(s)
                    entries.append(("src", raw, s))

    walk(top, True)

    for name in SECTIONS[:stop_after + 1]:
        if name not in seen_sections:
            red(f"upstream's {FLIST} no longer has the section header "
                f"'// {name}' that --upto cuts on. The list may still be "
                f"fine, but the CUT is no longer upstream's -- re-read their "
                f"file and re-teach SECTIONS rather than grading a guess.")
    kept = []
    for s in sources:
        name = Path(s).name
        if name in EXCLUDED_BY_DESIGN:
            print(f"== EXCLUDED (by design): {name} -- "
                  f"{EXCLUDED_BY_DESIGN[name]}")
        elif Path(s).is_file():
            kept.append(s)
        elif name in MISSING_BY_DESIGN:
            print(f"== SKIPPED (declared): {name} -- "
                  f"{MISSING_BY_DESIGN[name]}")
        else:
            red("upstream's flist names a source that is not in the "
                f"checkout: {s}")
    for d in [d for d in incdirs if not Path(d).is_dir()]:
        print(f"== SKIPPED (declared) incdir: {d} -- belongs to a source "
              f"skipped above")
    incdirs = [d for d in incdirs if Path(d).is_dir()]
    if not kept:
        red(f"{FLIST} up to '{upto}' yielded no sources")
    copy_lines = [raw for kind, raw, path in entries
                  if (kind == "inc" and path in incdirs) or
                     (kind == "src" and path in kept)]
    return incdirs, kept, copy_lines


def analyse_cv_core(cv_core, isim_vlog, work, want_hash, uvm):
    """Analyse the CV32E40P RTL using UPSTREAM'S OWN cv32e40p manifest.

    The UVM environment is not RTL-free: uvme_cv32e40p's debug coverage model
    names cv32e40p_pkg::RESET and three PULP FSM states by scope resolution,
    so the environment package cannot analyse without the core's package.
    The RTL is the checkout ExternalRepos.mk clones (or --cv-core).
    """
    checkout = Path(cv_core)
    if not checkout.is_dir():
        red(f"--cv-core {checkout} is not a directory\n"
            f"  -- clone the core (ExternalRepos.mk) or pass --cv-core")
    head = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    print(f"== RTL: {checkout}")
    print(f"   provisioned sha : {head or '(unknown)'}")
    print(f"   core-v-verif ExternalRepos.mk CV_CORE_HASH : {want_hash}")
    if want_hash and head and not head.startswith(want_hash):
        print(f"   SHA SKEW: core-v-verif names {want_hash}; the `cv32e40p` "
              f"pin provides {head[:12]}. Read the entry's header before "
              f"attributing any failure below to iSim.")
    translated_text, sources, incdir_count = translate_cv_core_manifest(checkout)
    flist_path = work / f"{Path(CV_CORE_MANIFEST).stem}.translated.f"
    flist_path.write_text(translated_text)
    # -uvm rides the RTL analyse too (SW-517200): with the upstream
    # defines on, the RTL's own sva/ and bhv/tracer files `include
    # uvm_macros.svh and emit uvm_error -- upstream compiles RTL and tb in
    # ONE compile with UVM on the search path, so this mirrors that.
    cmd = [isim_vlog, "-uvm", uvm, "-work", str(work), "-lib", "work"]
    cmd += UPSTREAM_DEFINES
    cmd += UPSTREAM_TIMESCALE
    cmd += ["-f", str(flist_path)]
    print(f"== analyse RTL: {len(sources)} sources, {incdir_count} incdirs, "
          f"from upstream {CV_CORE_MANIFEST}")
    return subprocess.run(cmd).returncode


def main():
    ap = argparse.ArgumentParser()
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--checkout",
                       help="THIS core-v-verif checkout, by any name -- what "
                            "mk/uvmt/isim.mk passes ($(CORE_V_VERIF))")
    where.add_argument("--root",
                       help="the iSim integration pile's layout: the directory "
                            "that HOLDS a checkout named core_v_verif/")
    ap.add_argument("--stage", required=True,
                    choices=("analyse", "elaborate"))
    ap.add_argument("--upto", required=True,
                    help="cut upstream's flist at this section header of THEIRS")
    ap.add_argument("--isim-vlog", required=True)
    ap.add_argument("--isim-elab")
    ap.add_argument("--top", default="uvmt_cv32e40p_tb",
                    help="elaboration top (default: %(default)s)")
    ap.add_argument("--with-iss-sv", action="store_true",
                    help="fold in the VENDORED Imperas OVPM SV layer "
                         "(imperas_iss.flist): vendor_lib/imperas ships the "
                         "full SV source under an Apache-modified licence; "
                         "only the OVPsim runtime .so behind its DPI-C "
                         "imports is licensed/unfetchable, and that boundary "
                         "is a RUN-time concern, not an analyse/elaborate "
                         "one. Implied by --stage elaborate.")
    ap.add_argument("--work", required=True)
    ap.add_argument("--uvm", default="1.2", help="the shipped UVM to map")
    ap.add_argument("--cv-core",
                    help="a provisioned cv32e40p checkout, analysed first")
    a = ap.parse_args()

    # Our own prints and the analyser's diagnostics share a pipe. Without
    # this, Python's block buffering makes them come out in an order that has
    # nothing to do with what happened, and a `.test` that CHECKs one before
    # the other grades a lie.
    sys.stdout.reconfigure(line_buffering=True)

    # MEASURED 2026-10-18 on a user's own clone (directory named `master`):
    # the driver insisted on <root>/core_v_verif/ -- the iSim integration
    # pile's layout -- and refused every checkout not named that.  isim.mk
    # now hands over the checkout itself; --root stays for the pile.
    if a.checkout is not None:
        checkout = Path(a.checkout)
        if not (checkout / FLIST).is_file():
            red(f"--checkout {checkout} is not a core-v-verif checkout: no {FLIST} in it")
    else:
        checkout = Path(a.root) / "core_v_verif"
        if not checkout.is_dir():
            red(f"no checkout at {checkout} (--root is the directory that HOLDS core_v_verif/)")

    if a.stage == "elaborate":
        # the top instantiates the ISS wrapper unconditionally in this
        # vintage; its SV closure is vendored, so elaboration folds it in.
        a.with_iss_sv = True

    if a.with_iss_sv:
        # The tb's exclusion predates the measurement that the OVPM SV
        # layer is VENDORED (vendor_lib/imperas, Apache-modified licence)
        # -- only the OVPsim runtime .so behind the DPI-C boundary is
        # licensed/unfetchable, and no analyse/elaborate touches it.
        EXCLUDED_BY_DESIGN.pop("uvmt_cv32e40p_tb.sv", None)

    table = upstream_vars(checkout)
    incdirs, sources, copy_lines = expand_flist(checkout, table, a.upto)
    if a.with_iss_sv:
        iss_inc, iss_src = expand_iss_flist(checkout, table)
        # the main flist already names step_compare/iss_wrap? it does not --
        # they live only in imperas_iss.flist; dedup defensively anyway.
        for d in iss_inc:
            if d not in incdirs:
                incdirs.append(d)
        for s in iss_src:
            if s not in sources:
                sources.append(s)
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)

    if a.cv_core:
        rc = analyse_cv_core(a.cv_core, a.isim_vlog, work, cv_core_hash(checkout), a.uvm)
        if rc != 0:
            print("== RTL analysis failed; the environment cannot be analysed "
                  "without cv32e40p_pkg")
            return rc

    # The copy: upstream's tree, cut and with the declared skips removed --
    # the `${VAR}` paths, the `+incdir+` lines, everything else is theirs and
    # the analyser reads it with their table in its environment.
    cut = work / f"{Path(FLIST).stem}.cut.f"
    cut.write_text("\n".join(
        [f"// {Path(FLIST).name} as provisioned, cut at '{a.upto}' with the",
         "// declared skips removed (core_v_verif_build.py); every path is",
         "// upstream's own, through the DV_* variables uvmt.mk exports.", ""]
        + copy_lines) + "\n")
    cmd = [a.isim_vlog, "-uvm", a.uvm, "-work", str(work), "-lib", "work"]
    cmd += UPSTREAM_DEFINES
    cmd += UPSTREAM_TIMESCALE
    cmd += ["-f", str(cut)]
    if a.with_iss_sv:
        cmd += ["-f", str(checkout / ISS_FLIST)]
    print(f"== analyse: {len(sources)} sources, {len(incdirs)} incdirs, "
          f"upstream {FLIST} up to '{a.upto}'"
          + (" + imperas_iss.flist (vendored OVPM SV layer)"
             if a.with_iss_sv else ""))
    print("+ " + " ".join(cmd)
          + f"   (env: {' '.join(k for k in sorted(table) if k.startswith('DV_'))} TBSRC_HOME)")
    rc = subprocess.run(cmd, env={**os.environ, **table}).returncode
    if rc != 0 or a.stage == "analyse":
        return rc

    if not a.isim_elab:
        red("--stage elaborate needs --isim-elab")
    ecmd = [a.isim_elab, "-uvm", a.uvm, "-work", str(work), "-lib", "work",
            "-top", a.top, "-sir"]
    ecmd += UPSTREAM_TIMESCALE
    print(f"== elaborate: -top {a.top}")
    print("+ " + " ".join(ecmd))
    return subprocess.run(ecmd).returncode


if __name__ == "__main__":
    sys.exit(main())
