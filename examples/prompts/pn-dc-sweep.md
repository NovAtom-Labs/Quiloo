# Silicon PN forward-bias sweep

Using the local DEVSIM backend, simulate a one-dimensional silicon PN junction
at 300 K.

The p-type region extends from 0 to 0.5 um and is uniformly acceptor doped at
1e17 cm^-3. The n-type region extends from 0.5 to 1.0 um and is uniformly donor
doped at 1e16 cm^-3. Use a mesh spacing of 0.01 um in both regions.

Place an ohmic anode at the left endpoint and an ohmic cathode at the right
endpoint. Use Poisson, electron continuity, and hole continuity equations with
Boltzmann statistics, constant mobility, and SRH recombination.

Sweep the anode from 0 V to 0.2 V in 0.1 V steps while holding the cathode at
the reference potential. Return terminal current, electrostatic potential,
electron density, and hole density.

