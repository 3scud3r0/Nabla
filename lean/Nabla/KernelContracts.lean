/-! Kernel-only contracts. These prove the displayed propositions over Nat and
Prop. They do not certify Python translation or a general arithmetic solver. -/
namespace Nabla.KernelContracts

theorem implication_compose (P Q R : Prop) (pq : P → Q) (qr : Q → R) : P → R := by
  intro p
  exact qr (pq p)

theorem conjunction_commutes (P Q : Prop) : (P ∧ Q) ↔ (Q ∧ P) := by
  constructor
  · intro h
    exact ⟨h.right, h.left⟩
  · intro h
    exact ⟨h.right, h.left⟩

theorem guarded_equality (P : Prop) (a b c : Nat)
    (ab : P → a = b) (bc : P → b = c) : P → a = c := by
  intro p
  exact Eq.trans (ab p) (bc p)

theorem list_map_identity (xs : List Nat) : xs.map (fun x => x) = xs := by
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    exact congrArg (List.cons x) ih

theorem natural_add_zero (n : Nat) : n + 0 = n := by
  exact Nat.add_zero n

theorem natural_add_successor (n m : Nat) : n + (m + 1) = (n + m) + 1 := by
  rfl

#print axioms implication_compose
#print axioms conjunction_commutes
#print axioms guarded_equality
#print axioms list_map_identity
#print axioms natural_add_zero
#print axioms natural_add_successor

end Nabla.KernelContracts
