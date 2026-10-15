# Local simulated laboratory campaign

`frontier-lab-951017/` contains the final fixed-seed campaign artifacts, including
192 synthetic tasks, fitted nearest-neighbor models, six reserved-set evaluations,
independent solver measurements, scientific publications, domain results, logs,
protocol/source hashes, journal, JUnit and byte-integrity manifests.

This is **simulated usage**, not adoption by a frontier laboratory or a gain in
frontier model capability. Both learned baselines score zero on the two reserved
family groups. The exact solver reference scores 48/48 in each group and is not a
trained model. All negative controls pass; none of these facts establishes 95%
completion of the scientific vision.

The four role labels are local workflow responsibilities, not authenticated
people. Stored signing keys are public; ephemeral private signing keys were not
persisted. Disciplinary outputs are idealized synthetic examples. The NIST
numerical check retains the provenance of the existing published reference.
Generated synthetic task data are labeled CC0-1.0 in their records; implementation
and other generated examples follow the repository license. Bibliographic
metadata do not license any associated full text.

`frontier-lab-development-951017.json` preserves the successful development run
before the final source/protocol metadata were implemented. It used the same
data seed. It was not discarded based on model accuracy.

`frontier-lab-pre-control-fix-951017.json` preserves the subsequent rehearsal before
the final control fix. `frontier-lab-control-failure-23117.json` records the failed
isolated-wheel smoke that exposed an incorrect assumption about sorted split
order. The final version explicitly selects the training endpoint, and includes
a regression using that same failing seed.

Use [the reproduction guide](../../docs/FRONTIER_LAB_SIMULATION.md) and
[the audited results](../../docs/audits/FRONTIER_LAB_SIMULATION_2026_10_15.md).
The top-level manifest inventories byte integrity. Reproduce semantic results
with the individual verifiers; timings, PDFs, ephemeral signatures and SQLite
storage need not be byte-identical in a new run.
