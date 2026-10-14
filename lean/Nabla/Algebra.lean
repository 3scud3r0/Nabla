import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum

namespace Nabla

theorem rational_cancel (x y : ℚ) (hy : y ≠ 0) : (x * y) / y = x := by
  field_simp

theorem distributivity_certificate (a b c : ℚ) : a * b + a * c = a * (b + c) := by
  ring

theorem linear_implication (x y : ℚ) (hxy : x ≤ y) (hy : y ≤ 3) : x ≤ 3 := by
  linarith

end Nabla
