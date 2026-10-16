# Nabla — demonstração científica reproduzível

Versão: 1.0.0. 69 operações executadas com referências independentes e notebook reexecutado.

Campanha finita: 176 casos. Controles negativos rejeitados: 9.

Lei sintética y=1+2x recuperada em 8 pontos de treino e verificada em 8 pontos reservados; uma lei errada foi rejeitada.

| Operação | Referência | Resultado |
|---|---|---|
| `analysis_extrema` | independent-identity-or-enclosure | passou |
| `analysis_integral` | closed-form/finite-reference | passou |
| `analysis_interval` | independent-identity-or-enclosure | passou |
| `analysis_pade` | closed-form/finite-reference | passou |
| `analysis_root` | independent-identity-or-enclosure | passou |
| `approximate` | independent-identity-or-enclosure | passou |
| `bayes` | closed-form/finite-reference | passou |
| `binomial` | closed-form/finite-reference | passou |
| `certified_function` | independent-identity-or-enclosure | passou |
| `certified_integral` | closed-form/finite-reference | passou |
| `condition` | closed-form/finite-reference | passou |
| `conic` | closed-form/finite-reference | passou |
| `differentiate` | independent-identity-or-enclosure | passou |
| `distribution` | closed-form/finite-reference | passou |
| `evaluate` | closed-form/finite-reference | passou |
| `factor` | closed-form/finite-reference | passou |
| `ff_extension` | closed-form/finite-reference | passou |
| `ff_irreducible` | closed-form/finite-reference | passou |
| `geometry` | closed-form/finite-reference | passou |
| `graph_apsp` | closed-form/finite-reference | passou |
| `graph_assignment` | closed-form/finite-reference | passou |
| `graph_bellman_ford` | closed-form/finite-reference | passou |
| `graph_matching` | closed-form/finite-reference | passou |
| `graph_max_flow` | closed-form/finite-reference | passou |
| `graph_mst` | closed-form/finite-reference | passou |
| `graph_scc` | closed-form/finite-reference | passou |
| `integrate` | independent-identity-or-enclosure | passou |
| `least_squares` | closed-form/finite-reference | passou |
| `limit` | closed-form/finite-reference | passou |
| `linear_regression` | closed-form/finite-reference | passou |
| `lu` | independent-identity-or-enclosure | passou |
| `markov` | closed-form/finite-reference | passou |
| `markov_hitting` | closed-form/finite-reference | passou |
| `markov_rewards` | closed-form/finite-reference | passou |
| `markov_stationary` | closed-form/finite-reference | passou |
| `matrix_inverse` | closed-form/finite-reference | passou |
| `matrix_properties` | closed-form/finite-reference | passou |
| `maximum_flow` | closed-form/finite-reference | passou |
| `nt_discrete_log` | closed-form/finite-reference | passou |
| `nt_factorization` | closed-form/finite-reference | passou |
| `nt_modular_roots` | closed-form/finite-reference | passou |
| `nt_pell` | closed-form/finite-reference | passou |
| `nt_primality` | closed-form/finite-reference | passou |
| `nt_primitive_root` | closed-form/finite-reference | passou |
| `ode` | analytic-reference | passou |
| `ode_adaptive` | analytic-reference | passou |
| `optimize` | closed-form/finite-reference | passou |
| `orthogonal_basis` | independent-identity-or-enclosure | passou |
| `polynomial_range` | closed-form/finite-reference | passou |
| `prob_binomial` | closed-form/finite-reference | passou |
| `prob_convolution` | closed-form/finite-reference | passou |
| `prob_dirichlet` | closed-form/finite-reference | passou |
| `prob_distribution` | closed-form/finite-reference | passou |
| `prob_hypergeometric` | closed-form/finite-reference | passou |
| `prob_joint` | closed-form/finite-reference | passou |
| `prob_poisson_binomial` | closed-form/finite-reference | passou |
| `prob_propagate` | closed-form/finite-reference | passou |
| `prob_stationary` | closed-form/finite-reference | passou |
| `quadratic_optimize` | closed-form/finite-reference | passou |
| `rational_compare` | closed-form/finite-reference | passou |
| `rational_limit` | closed-form/finite-reference | passou |
| `sat` | closed-form/finite-reference | passou |
| `series` | closed-form/finite-reference | passou |
| `shortest_paths` | closed-form/finite-reference | passou |
| `simplify` | independent-identity-or-enclosure | passou |
| `solve_linear` | closed-form/finite-reference | passou |
| `statistics` | closed-form/finite-reference | passou |
| `time_series` | closed-form/finite-reference | passou |
| `topological_sort` | closed-form/finite-reference | passou |

## Limites

- Finite examples do not prove correctness for all possible inputs.
- Synthetic data; no empirical physical validation or novel discovery.
- Floating ODE references have explicit tolerances; they are not exact proofs.
- Formal compilation and kernel axiom audit are separate evidence.
- No GPU, external services, public federation or Windows execution in this experiment.
