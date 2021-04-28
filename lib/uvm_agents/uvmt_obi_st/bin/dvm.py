## 
## Copyright 2021 OpenHW Group
## Copyright 2021 Datum Technology Corporation
## SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
## 
## Licensed under the Solderpad Hardware License v 2.1 (the "License"); you may
## not use this file except in compliance with the License, or, at your option,
## the Apache License version 2.0. You may obtain a copy of the License at
## 
##     https://solderpad.org/licenses/SHL-2.1/
## 
## Unless required by applicable law or agreed to in writing, any work
## distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
## WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
## License for the specific language governing permissions and limitations
## under the License.
## 



"""Design Verification \'Makefile\'.

Usage:
  dvm.py all  <target>  [-t <test_name>]  [-s <seed>]  [-g | --gui]  [-d | --debug]  [-w | --waves] [-q | --noclean]
  dvm.py cmp  <target>
  dvm.py elab <target>  [-d | --debug]
  dvm.py cpel <target>
  dvm.py sim  <target>  [-t <test_name>]  [-s <seed>]  [-g | --gui]  [-w | --waves]
  dvm.py clean
  dvm.py (-h | --help)
  dvm.py --version

Options:
  -h --help     Show this screen.
  --version     Show version.

"""



from docopt     import docopt
import os
import subprocess
import shutil

dbg = False
pwd             = os.getcwd()
vivado_path     = "/tools/Xilinx/Vivado/2020.2/bin/"
uvm_dpi_so      = "uvm_dpi"
project_dir     = pwd + "/.."
rtl_path        = project_dir + "/rtl"
rtl_libs_path   = rtl_path + "/.imports"
dv_path         = project_dir + "/dv"
dv_imports_path = dv_path + "/.imports"
sim_debug       = True#False
sim_gui         = True
sim_waves       = False



def do_dispatch(args):
    glb_args = args
    
    if (dbg):
        print("Call to do_dispatch()")
    do_paths()
    
    if not args['<seed>']:
        args['<seed>'] = 1
    
    if args['update']:
        args['clean'] = False
        args['cmp'  ] = False
        args['elab' ] = False
        args['sim'  ] = False
    
    if args['all']:
        args['cmp'  ] = True
        args['elab' ] = True
        args['sim'  ] = True
        if (args['-q'] or args['--noclean']):
            args['clean'] = False
        else:
            args['clean'] = True
    
    if args['cpel']:
        args['clean'] = True
        args['cmp'  ] = True
        args['elab' ] = True
        args['sim'  ] = False
    
    if (args['-d'] or args['--debug']):
        sim_debug = True
    else:
        sim_debug = False
    
    if (args['-w'] or args['--waves']):
        sim_waves = True
        sim_debug = True
    else:
        sim_waves = False
    
    if (args['-g'] or args['--gui']):
        sim_debug = True
        sim_gui   = True
    else:
        sim_gui   = False
    
    if args['clean']:
        do_clean()
    if args['cmp']:
        out_path = pwd + "/out"
        if not os.path.exists(out_path):
            os.mkdir(out_path)
        do_cmp_rtl(args['<target>'])
        do_cmp_dv (dv_path + "/" + args['<target>'] + "/src/" + args['<target>'] + "_pkg.flist.xsim", args['<target>'])
    if args['elab']:
        do_elab_rtl(args['<target>'])
        do_elab_dv (args['<target>'], args['<target>'] + "_tb")
    if args['sim']:
        do_sim(args['<target>'] + "_tb", args['<target>'] + "_" + args['<test_name>'] + "_test", args['<seed>'], [])



def do_paths():
    if (dbg):
        print("Call to do_paths()")
    
    ### RTL ###
    set_env_var("RTL_PKT_SNF_PATH", rtl_path + "/pkt_snf")
    
    ### DV ###
    # Libraries
    set_env_var("UVM_HOME"                 , dv_imports_path + "/uvm"                   )
    set_env_var("DV_UVM_SRC_PATH"          , dv_imports_path + "/uvm"           + "/src")
    set_env_var("DV_UVML_HRTBT_SRC_PATH"   , dv_imports_path + "/uvml_hrtbt"    + "/src")
    set_env_var("DV_UVML_TRN_SRC_PATH"     , dv_imports_path + "/uvml_trn"      + "/src")
    set_env_var("DV_UVML_LOGS_SRC_PATH"    , dv_imports_path + "/uvml_logs"     + "/src")
    set_env_var("DV_UVML_IO_SRC_PATH"      , dv_imports_path + "/uvml_io"       + "/src")
    set_env_var("DV_UVML_SB_SRC_PATH"      , dv_imports_path + "/uvml_sb"       + "/src")
    set_env_var("DV_UVML_RAL_SRC_PATH"     , dv_imports_path + "/uvml_ral"      + "/src")
    set_env_var("DV_UVMA_RESET_SRC_PATH"   , dv_imports_path + "/uvma_reset"    + "/src")
    set_env_var("DV_UVME_RESET_ST_SRC_PATH", dv_imports_path + "/uvme_reset_st" + "/src")
    set_env_var("DV_UVMT_RESET_ST_SRC_PATH", dv_imports_path + "/uvmt_reset_st" + "/src")
    set_env_var("DV_UVMA_CLK_SRC_PATH"     , dv_imports_path + "/uvma_clk"      + "/src")
    set_env_var("DV_UVME_CLK_ST_SRC_PATH"  , dv_imports_path + "/uvme_clk_st"   + "/src")
    set_env_var("DV_UVMT_CLK_ST_SRC_PATH"  , dv_imports_path + "/uvmt_clk_st"   + "/src")
    set_env_var("DV_UVMA_AXIL_SRC_PATH"    , dv_imports_path + "/uvma_axil"     + "/src")
    set_env_var("DV_UVME_AXIL_ST_SRC_PATH" , dv_imports_path + "/uvme_axil_st"  + "/src")
    set_env_var("DV_UVMT_AXIL_ST_SRC_PATH" , dv_imports_path + "/uvmt_axil_st"  + "/src")
    
    # Source
    set_env_var("DV_UVMA_OBI_SRC_PATH"   , dv_path + "/uvma_obi"    + "/src")
    set_env_var("DV_UVME_OBI_ST_SRC_PATH", dv_path + "/uvme_obi_st" + "/src")
    set_env_var("DV_UVMT_OBI_ST_SRC_PATH", dv_path + "/uvmt_obi_st" + "/src")


def set_env_var(name, value):
    if (dbg):
        print("Setting env var '" + name + "' to value '" + value + "'")
    os.environ[name] = value



def do_clean():
    if (dbg):
        print("Call to do_clean()")
    print("********")
    print("Cleaning")
    print("********")
    if os.path.exists("./xsim.dir"):
        shutil.rmtree("./xsim.dir")
    if os.path.exists("./out"):
        shutil.rmtree("./out")



def do_cmp_rtl(target_design):
    if (dbg):
        print("Call to do_cmp_rtl(target_design='" + target_design + "'")
    
    



def do_cmp_dv(filelist_path, lib_name):
    if (dbg):
        print("Call to do_cmp_dv(filelist_path='" + filelist_path + "', lib_name='" + lib_name + "')")
    print("************")
    print("Compiling DV")
    print("************")
    
    run_xsim_bin("xvlog", "--incr -sv -f " + filelist_path + " -L uvm --work " + lib_name + "=out/" + lib_name + " --log ./out/compilation.log")



def do_elab_rtl(target_design):
    if (dbg):
        print("Call to do_elab_rtl(target_design='" + target_design + "')")
    
    


def do_elab_dv(lib_name, design_unit):
    
    debug_str = ""
    
    if (dbg):
        print("Call to do_elab_dv(lib_name='" + lib_name + "', design_unit='" + design_unit + "')")
    print("**************")
    print("Elaborating DV")
    print("**************")
    
    if (sim_debug):
        debug_str = " --debug all "
    else:
        debug_str = ""
    
    run_xsim_bin("xelab", lib_name + "." + design_unit + debug_str + " --incr -relax --O0 -v 0 -s " + design_unit + " -timescale 1ns/1ps -L " + lib_name + "=./out/" + lib_name + " --log ./out/elaboration.log")
    



def do_sim(snapshot, test_name, seed, args):
    
    waves_str = ""
    gui_str   = ""
    runall_str   = ""
    
    args.append("SIM_DIR_RESULTS=" + pwd + "/results")
    args.append("UVM_TESTNAME=" + test_name + "_c")
    
    act_args = ""
    for arg in args:
        act_args = act_args + " -testplusarg \"" + arg + "\""
    
    tests_results_path = pwd + "/results/" + test_name + "_" + str(seed)
    if not os.path.exists(tests_results_path):
        os.mkdir(tests_results_path)

    
    if (dbg):
        print("Call to do_sim(snapshot='" + snapshot + "', test_name='" + test_name + "', seed='" + str(seed) + "', args='" + act_args + "')")
    
    print("**********")
    print("Simulating")
    print("**********")
    
    if (sim_waves):
        if not os.path.exists(tests_results_path + "/waves_cfg.tcl"):
            f = open(tests_results_path + "/waves_cfg.tcl", "w")
            f.write("log_wave -recursive *")
            f.write("\n")
            f.write("run -all")
            f.write("\n")
            f.write("quit")
            f.close()
        waves_str = " --wdb " + tests_results_path + "/waves.wdb --tclbatch " + tests_results_path + "/waves_cfg.tcl"
    else:
        waves_str = ""
    
    if (sim_gui):
        gui_str = " --gui "
        runall_str = ""
    else:
        gui_str = ""
        if (sim_waves):
            runall_str = ""
        else:
            runall_str = " --runall --onerror quit"
    
    run_xsim_bin("xsim", snapshot + gui_str + waves_str + runall_str + " " + act_args + " --stats --log " + tests_results_path + "/sim.log")



def run_xsim_bin(name, args):
    bin_path = vivado_path + name
    if (dbg):
        print("Call to run_xsim_bin(name='" + name + "', args='"  + args + "')")
        print("System call is " + bin_path + " " + args)
    subprocess.call(bin_path + " " + args, shell=True)



if __name__ == '__main__':
    args = docopt(__doc__, version='DVMake 0.1')
    if (dbg):
        print(args)
    do_dispatch(args)
