/*
 * OVPsim DPI STUB for the core-v-verif imperas reference-model layer
 * (vendor_lib/imperas/imperas_DV_COREV/sv/imperas_CV32.sv).
 *
 * The real OVPsim runtime (.so) behind these imports is LICENSED and
 * not present on this infrastructure.  This stub satisfies the DPI
 * imports so the uvmt TB LOADS and RUNS -- the reference model simply
 * never executes, which makes the step-compare machinery inert.  That
 * is DIFFERENTIAL-VALID: dsim cannot run the reference model without
 * the licence either, so both simulators run the same stubbed bench
 * (see test_piles/integration/README.md).
 *
 * The DPI EXPORTS the real OVPsim would call back (svexp_busFetch and
 * family -- time-consuming exported tasks) are deliberately never
 * called from here, matching iSim's fail-late non-registration of
 * blocking task exports (SW-519400).
 *
 * Build:  cc -shared -fPIC -o ovpsim_dpi_stub.so ovpsim_dpi_stub.c
 */
#include <stdint.h>
#include <string.h>
#include <stdio.h>

/* C-natural layouts mirroring imperas_CV32.sv's typedefs (all-u64). */
typedef struct { uint64_t f[31]; } SVData_ioT;     /* 31 Uns64 members */
typedef struct { uint64_t f[1];  } SVData_stateT;  /* cycles */
typedef struct { uint64_t f[4];  } RMData_ioT;     /* irq_ack..DM */
typedef struct { uint64_t f[5];  } RMData_stateT;  /* retPC..trap */

void svimp_entry(const char* s1, const char* s2, const char* s3)
{
      (void)s1; (void)s2; (void)s3;
      fprintf(stderr, "ovpsim_dpi_stub: svimp_entry (reference model "
              "STUBBED -- no OVPsim licence on this host)\n");
}

void svimp_pull(RMData_ioT* io, RMData_stateT* state)
{
      if (io)    memset(io,    0, sizeof *io);
      if (state) memset(state, 0, sizeof *state);
}

void svimp_push(const SVData_ioT* io, const SVData_stateT* state)
{
      (void)io; (void)state;
}

void svimp_exit(void)       { }
void svimp_netupdate(void)  { }
