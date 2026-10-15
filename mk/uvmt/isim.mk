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
# WHAT THIS SIMULATOR TARGET REACHES, AND WHAT STANDS IN.
#
# iSim ANALYSES, ELABORATES and RUNS the CV32E40P UVM verification environment:
# the five uvml_* library packages, the four uvma_* agents, uvme_cv32e40p_pkg,
# uvmt_cv32e40p_pkg, uvmt_cv32e40p_tb and both _assert.sv files, against the
# CV32E40P RTL this tree's ExternalRepos.mk names.  `comp` builds the image;
# `test` runs a firmware test in it.  In the iSim tree, the integration pile
# runs hello_world, fibonacci, csr_instructions and illegal through this
# bench to SIMULATION PASSED on every build (test/integration/
# integ_core_v_verif_uvmt_run.test), so a green `test` here means the same
# thing it means for every other simulator in this directory.
#
# ONE THING STANDS IN.  uvmt_cv32e40p_tb instantiates the Imperas OVPsim
# reference model behind imperas_CV32.sv's DPI-C imports.  Its SV layer is
# vendored (vendor_lib/imperas) and compiles; the OVPsim runtime .so is
# licensed and not fetchable here.  $(ISIM_OVP_MODEL_DPI) is whatever .so
# satisfies those imports: the real model where it is licensed, or the stub
# the iSim tree ships (test_piles/integration/support/ovpsim_dpi_stub.c),
# which announces itself in the log as "reference model STUBBED" and compares
# nothing.  There is no default, so a run cannot quietly compare against
# nothing without the log saying so.
#
# HOW THE FILE LIST REACHES iSim.  uvmt_cv32e40p.flist is handed to
# `isim-vlog -f` as written: nested `-f`, `+incdir+` and the `${DV_*}` paths
# are read by the analyser, with this makefile's exported variables in its
# environment -- exactly as for dsim.  $(ISIM_BUILD), a script in the iSim
# tree, still exists for two things that are about WHICH lines, not about
# reading them: cutting the list at one of the `//` section headers below
# (the analyse_* ladder), and dropping the files it declares skipped by name
# (svlib_pkg.sv, cloned at build time rather than pinned).  Earlier versions
# of this header blamed two iSim defects for the script's existence; both
# were fixed in August 2026 and the last gap (`${VAR}` in a command file) in
# October 2026.
#
###############################################################################

ISIM                   ?= isim
ISIM_VLOG              ?= isim-vlog
ISIM_ELAB              ?= isim-elab
ISIM_UVM_VERSION       ?= 1.2

# iSim ships a PRE-COMPILED UVM.  `-uvm <version>` maps it into the caller's
# work library, so -- unlike every other simulator in this directory -- there
# is no UVM_HOME here, no +incdir+ into a UVM source tree, no uvm_pkg.sv on the
# command line, and no libuvm_dpi.so to load at run time.
ISIM_WORK              ?= $(SIM_CFG_RESULTS)/isim_work
ISIM_IMAGE             ?= $(ISIM_WORK)/a.out.so

# The list driver described above.  It lives in the iSim tree
# (test_piles/integration/bin/core_v_verif_build.py).  There is no default: a
# wrong guess would produce a confusing failure a long way from its cause.
ISIM_BUILD             ?=

# The .so behind imperas_CV32.sv's DPI-C imports: the licensed OVPsim model,
# or the iSim tree's stub.  Required by `test`; see the header.
ISIM_OVP_MODEL_DPI     ?=

# A checkout of the CV32E40P RTL.  Defaults to the tree ExternalRepos.mk
# clones; override it to point at an existing checkout and no clone is
# attempted.
ISIM_CV_CORE           ?= $(CV_CORE_PKG)

# Run-time flags of your own, after the bench's (`+UVM_VERBOSITY=...`).
ISIM_USER_RUN_FLAGS    ?=

no_rule:
	@echo 'makefile: SIMULATOR is set to $(SIMULATOR), but no rule/target specified.'
	@echo 'try "make SIMULATOR=isim test TEST=hello-world".'

help:
	@echo 'iSim targets, shallowest first. Each analyse_* target names the section'
	@echo 'of uvmt_$(CV_CORE_LC).flist it covers and claims nothing above it:'
	@echo '  analyse_uvml   the uvml_* UVM library packages   (flist "Libraries")'
	@echo '  analyse_uvma   the above + the uvma_* agents     (flist "Agents")'
	@echo '  analyse_uvme   the above + uvme_$(CV_CORE_LC)_pkg  (flist "Environments")'
	@echo '  analyse_uvmt   the above + uvmt_$(CV_CORE_LC)_pkg, dut_wrap.sv and both'
	@echo '                 _assert.sv files, EXCLUDING uvmt_$(CV_CORE_LC)_tb.sv'
	@echo '  comp           the whole bench, uvmt_$(CV_CORE_LC)_tb elaborated to an image'
	@echo '  test           run TEST=<name> in that image (needs ISIM_OVP_MODEL_DPI)'
	$(ISIM_VLOG) -help

mk_results:
	$(MKDIR_P) $(SIM_CFG_RESULTS)
	$(MKDIR_P) $(ISIM_WORK)

check_isim_build:
	@if [ -z "$(ISIM_BUILD)" ]; then \
	    echo "SIMULATOR=isim needs ISIM_BUILD set to core_v_verif_build.py"; \
	    echo "  (test_piles/integration/bin/ in the iSim tree). See the"; \
	    echo "  comment at the top of mk/uvmt/isim.mk for what it does."; \
	    exit 1; \
	fi

check_isim_ovp_model:
	@if [ -z "$(ISIM_OVP_MODEL_DPI)" ]; then \
	    echo "SIMULATOR=isim test needs ISIM_OVP_MODEL_DPI: the .so behind"; \
	    echo "  imperas_CV32.sv's DPI-C imports -- the licensed OVPsim model, or"; \
	    echo "  the stub in the iSim tree (test_piles/integration/support/"; \
	    echo "  ovpsim_dpi_stub.c, built with cc -shared -fPIC). See the header."; \
	    exit 1; \
	fi

################################################################################
# Analysis targets.  THE SPLIT IS UPSTREAM'S, NOT OURS: --upto names a section
# comment inside uvmt_$(CV_CORE_LC).flist, and the driver refuses if that
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
# bench files" / "FIXME:STR:Find a better location" flist sections -- and
# stops short of uvmt_$(CV_CORE_LC)_tb.sv, which `comp` adds together with
# the vendored OVPM SV layer (imperas_iss.flist).
analyse_uvmt: mk_results check_isim_build
	$(ISIM_BUILD) --root $(abspath $(CORE_V_VERIF)/..) --stage analyse \
		--upto "FIXME:STR:Find a better location" --uvm $(ISIM_UVM_VERSION) \
		--isim-vlog $(ISIM_VLOG) --work $(ISIM_WORK) \
		--cv-core $(ISIM_CV_CORE)

################################################################################
# `comp` -- the whole bench: the RTL, every flist section, uvmt_$(CV_CORE_LC)_tb
# and the vendored OVPM SV layer, elaborated to $(ISIM_IMAGE).
comp: mk_results check_isim_build
	$(ISIM_BUILD) --root $(abspath $(CORE_V_VERIF)/..) --stage elaborate \
		--upto "FIXME:STR:Find a better location" --with-iss-sv \
		--uvm $(ISIM_UVM_VERSION) \
		--isim-vlog $(ISIM_VLOG) --isim-elab $(ISIM_ELAB) --work $(ISIM_WORK) \
		--cv-core $(ISIM_CV_CORE)

# Skip compile if COMP is specified and negative
ifneq ($(call IS_NO,$(COMP)),NO)
ISIM_SIM_PREREQ = comp
endif

################################################################################
# `test` -- the same shape as dsim.mk's: the firmware the `hex` target built,
# the UVM test the test's YAML names, in the run directory uvmt.mk lays out.
# One image, built once by `comp`, is reused across tests.
test: $(ISIM_SIM_PREREQ) check_isim_ovp_model hex
	mkdir -p $(SIM_RUN_RESULTS) && \
	cd $(SIM_RUN_RESULTS) && \
		$(ISIM) \
			-image $(ISIM_IMAGE) \
			+sv_lib=$(abspath $(ISIM_OVP_MODEL_DPI)) \
			$(CFG_PLUSARGS) \
			$(TEST_PLUSARGS) \
			$(ISIM_USER_RUN_FLAGS) \
			+UVM_TESTNAME=$(TEST_UVM_TEST) \
			+firmware=$(SIM_TEST_PROGRAM_RESULTS)/$(TEST_PROGRAM)$(OPT_RUN_INDEX_SUFFIX).hex \
			+elf_file=$(SIM_TEST_PROGRAM_RESULTS)/$(TEST_PROGRAM)$(OPT_RUN_INDEX_SUFFIX).elf \
			2>&1 | tee isim-$(TEST_NAME).log

clean:
	rm -rf $(ISIM_WORK)
	rm -rf $(SIM_RESULTS)
