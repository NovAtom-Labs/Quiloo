# Physics and unit notes

The study assumes an abrupt one-dimensional silicon p-n junction, complete dopant ionization, equilibrium, 300 K, and the depletion approximation. It is an analytical preflight for later numerical comparison, not a replacement for TCAD.

The built-in potential is

`V_bi = V_T ln(N_A N_D / n_i^2)`.

The total depletion width is

`W = sqrt((2 epsilon_s V_bi / q) (1/N_A + 1/N_D))`.

The peak field magnitude is

`E_max = 2 V_bi / W`.

All internal calculations and serialized fields use SI units. Doping values enter through the TOML file in `cm^-3` and must be converted to `m^-3`. Electric field output is `V/m`. A relative tolerance of `0.02` means two percent, not 0.02 percent.

At equilibrium, the net terminal current density should be zero within numerical precision.
