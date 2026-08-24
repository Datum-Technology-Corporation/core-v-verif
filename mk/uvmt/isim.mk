###############################################################################
#
# Copyright 2026 True North Silicon
#
# Licensed under the Solderpad Hardware Licence, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://solderpad.org/licenses/
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0 WITH SHL-2.0
#
###############################################################################
#
# iSim-specific Makefile.
# iSim is True North Silicon's SystemVerilog + VHDL simulator (https://tn-si.com)
#
###############################################################################
#
# WHAT THIS SIMULATOR TARGET REACHES TODAY, AND WHAT IT DOES NOT.
#
# iSim ANALYSES the CV32E40P UVM verification environment: the five uvml_*
# library packages, the four uvma_* agents, uvme_cv32e40p_pkg and, above it,
# uvmt_cv32e40p_pkg, uvmt_cv32e40p_dut_wrap.sv and both _assert.sv files
# (analyse_uvmt).  It does NOT yet build an image of uvmt_cv32e40p_tb -- the
# Imperas OVPsim wrapper it instantiates is licensed and not fetchable -- and
# `comp` below refuses rather than pretending -- see the target for the list
# of what is missing.  Each `analyse_*` target names exactly the section of
# uvmt_cv32e40p.flist it covers, so a green target cannot be read as a claim
# about the section above it.
#
# TWO iSim DEFECTS SHAPE THIS FILE, and both are why the file list is not
# simply handed to the analyser with `-f`:
#
#   * `isim-vlog -f` does not honour OPTIONS inside a command file.  It strips
#     `//` comments and treats every other line as a source path, so a
#     `+incdir+` line is opened as a file and a `-f` line is not followed at
#     all.  uvmt_cv32e40p.flist is ten `-f` lines and twenty-seven `+incdir+`
#     lines, so it cannot be passed as-is.  $(ISIM_BUILD) expands the tree and
#     lifts the options onto the command line, where they work.
#
#   * `+define+` on the ONE-STEP `isim` driver is silently swallowed as a
#     runtime plusarg and the macro is never defined -- with exit status 0.
#     Everything here therefore goes through `isim-vlog`, the two-step
#     analyser, where `+define+` is real.
#
# When those are fixed this file gets shorter: $(ISIM_BUILD) collapses to
# `-f $(DV_UVMT_PATH)/uvmt_$(CV_CORE_LC).flist`.
#
###############################################################################

ISIM_VLOG              ?= isim-vlog
ISIM_ELAB              ?= isim-elab
ISIM_UVM_VERSION       ?= 1.2

# iSim ships a PRE-COMPILED UVM.  `-uvm <version>` maps it into the caller's
# work library, so -- unlike every other simulator in this directory -- there
# is no UVM_HOME here, no +incdir+ into a UVM source tree, and no uvm_pkg.sv
# on the command line.
ISIM_WORK              ?= $(SIM_CFG_RESULTS)/isim_work

# The flist expander described above.  It lives in the iSim tree, not here,
# because it exists only to work around iSim defects and must disappear with
# them.  There is no default: a wrong guess would produce a confusing failure
# a long way from its cause.
ISIM_BUILD             ?=

# A checkout of the CV32E40P RTL.  The UVM environment is not RTL-free --
# uvme_cv32e40p's debug coverage model names cv32e40p_pkg::RESET and three
# PULP FSM states by scope resolution -- so `analyse_uvme` needs the core's
# packages in the library first.  Defaults to the tree ExternalRepos.mk
# clones; override it to point at an existing checkout and no clone is
# attempted.
ISIM_CV_CORE           ?= $(CV_CORE_PKG)

no_rule:
	@echo 'makefile: SIMULATOR is set to $(SIMULATOR), but no rule/target specified.'
	@echo 'try "make SIMULATOR=isim analyse_uvme".'

help:
	@echo 'iSim targets, shallowest first. Each names the section of'
	@echo 'uvmt_$(CV_CORE_LC).flist it covers and claims nothing above it:'
	@echo '  analyse_uvml   the uvml_* UVM library packages   (flist "Libraries")'
	@echo '  analyse_uvma   the above + the uvma_* agents     (flist "Agents")'
	@echo '  analyse_uvme   the above + uvme_$(CV_CORE_LC)_pkg  (flist "Environments")'
	@echo '  analyse_uvmt   the above + uvmt_$(CV_CORE_LC)_pkg, dut_wrap.sv and both'
	@echo '                 _assert.sv files -- EXCLUDING uvmt_$(CV_CORE_LC)_tb.sv'
	@echo '                 (needs the Imperas OVPsim wrapper, not fetchable)'
	@echo '  comp           NOT REACHED YET -- see the target for what is missing'
	$(ISIM_VLOG) -help

mk_results:
	$(MKDIR_P) $(SIM_CFG_RESULTS)
	$(MKDIR_P) $(ISIM_WORK)

check_isim_build:
	@if [ -z "$(ISIM_BUILD)" ]; then \
	    echo "SIMULATOR=isim needs ISIM_BUILD set to core_v_verif_build.py"; \
	    echo "  (test_piles/integration/bin/ in the iSim tree). See the"; \
	    echo "  comment at the top of mk/uvmt/isim.mk for why it exists."; \
	    exit 1; \
	fi

################################################################################
# Analysis targets.  THE SPLIT IS UPSTREAM'S, NOT OURS: --upto names a section
# comment inside uvmt_$(CV_CORE_LC).flist, and the expander refuses if that
# header is no longer there rather than silently analysing a different set.

analyse_uvml: mk_results check_isim_build
	$(ISIM_BUILD) --root $(abspath $(CORE_V_VERIF)/..) --stage analyse \
		--upto Libraries --uvm $(ISIM_UVM_VERSION) \
		--isim-vlog $(ISIM_VLOG) --work $(ISIM_WORK)

analyse_uvma: mk_results check_isim_build
	$(ISIM_BUILD) --root $(abspath $(CORE_V_VERIF)/..) --stage analyse \
		--upto Agents --uvm $(ISIM_UVM_VERSION) \
		--isim-vlog $(ISIM_VLOG) --work $(ISIM_WORK)

analyse_uvme: mk_results check_isim_build
	$(ISIM_BUILD) --root $(abspath $(CORE_V_VERIF)/..) --stage analyse \
		--upto Environments --uvm $(ISIM_UVM_VERSION) \
		--isim-vlog $(ISIM_VLOG) --work $(ISIM_WORK) \
		--cv-core $(ISIM_CV_CORE)

# analyse_uvmt is the above PLUS uvmt_$(CV_CORE_LC)_pkg.sv, dut_wrap.sv and
# both _assert.sv files -- upstream's own "CV32E40P tests" / "CV32E40P test
# bench files" / "FIXME:STR:Find a better location" flist sections.  It
# EXPLICITLY STOPS SHORT of uvmt_$(CV_CORE_LC)_tb.sv: $(ISIM_BUILD) excludes
# it by name (declared, printed, not silently dropped) because it
# instantiates the Imperas OVPsim wrapper, which is licensed and not
# fetchable.  See github#25.
analyse_uvmt: mk_results check_isim_build
	$(ISIM_BUILD) --root $(abspath $(CORE_V_VERIF)/..) --stage analyse \
		--upto "FIXME:STR:Find a better location" --uvm $(ISIM_UVM_VERSION) \
		--isim-vlog $(ISIM_VLOG) --work $(ISIM_WORK) \
		--cv-core $(ISIM_CV_CORE)

################################################################################
# `comp` -- the target every other simulator in this directory implements.
#
# It REFUSES, by name and with the list, rather than running something smaller
# and reporting success.  A simulator target that quietly builds less than
# `comp` means is how "core-v-verif runs on iSim" gets said out loud when it
# is not true.
comp:
	@echo "SIMULATOR=isim does not reach the comp target yet. Missing, in order:"
	@echo "  1. uvmt_$(CV_CORE_LC)_debug_assert.sv needs SVA sequence ALGEBRA"
	@echo "     (and/or/intersect/throughout/within, first_match, a mid-chain"
	@echo "     [*0:n]) that the V2 engine's single linear step vector does not"
	@echo "     carry yet -- see SVA_RUNTIME_PLAN.md Break #8 in the iSim tree."
	@echo "     uvmt_$(CV_CORE_LC)_interrupt_assert.sv analyses clean today."
	@echo "  2. imperas_iss.flist -- the Imperas OVPsim reference model. It"
	@echo "     is licensed and not fetchable, and uvmt_$(CV_CORE_LC)_tb"
	@echo "     instantiates its wrapper."
	@echo "  3. elaboration of the core itself: iSim does not yet elaborate"
	@echo "     cv32e40p_top. See integ_cv32e40p_elab in the iSim tree."
	@exit 1

test: comp

clean:
	rm -rf $(ISIM_WORK)
	rm -rf $(SIM_RESULTS)
