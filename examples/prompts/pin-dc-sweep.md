# Silicon PIN forward-bias sweep

Using the local DEVSIM backend, simulate a one-dimensional silicon PIN
structure at 300 K.

Use a 0.25 um p-type region uniformly acceptor doped at 5e16 cm^-3, followed by
a 0.50 um nominally intrinsic region with a residual donor concentration of
1e10 cm^-3, followed by a 0.25 um n-type region uniformly donor doped at
5e16 cm^-3. Use 0.01 um mesh spacing in the doped regions and 0.02 um in the
intrinsic region.

Use ohmic contacts at both endpoints. Apply Poisson, electron continuity, and
hole continuity equations with Boltzmann statistics, constant mobility, and
SRH recombination.

Sweep the left contact from 0 V to 0.2 V in 0.1 V steps. Return terminal
current, electrostatic potential, electric field, electron density, and hole
density.

