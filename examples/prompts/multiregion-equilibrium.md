# Four-region silicon equilibrium stack

Using the local DEVSIM backend, simulate a one-dimensional p+ / p / n / n+
silicon stack at 300 K under equilibrium with no externally applied bias.

The p+ region extends from 0 to 0.2 um with constant acceptor doping of
1e18 cm^-3. The p region extends from 0.2 to 1.0 um with constant acceptor
doping of 1e16 cm^-3. The n region extends from 1.0 to 1.8 um with constant
donor doping of 1e16 cm^-3. The n+ region extends from 1.8 to 2.0 um with
constant donor doping of 1e18 cm^-3. Use 0.01 um mesh spacing in the outer
regions and 0.02 um in the inner regions.

Use ohmic endpoint contacts, Poisson, electron continuity, and hole continuity
equations with Boltzmann statistics, constant mobility, and SRH recombination.
Return terminal current, electrostatic potential, electric field, electron
density, and hole density.
