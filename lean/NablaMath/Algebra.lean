import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum

namespace NablaMath

theorem add_self_rational (x : ℚ) : x + x = 2 * x := by ring

theorem cancel_nonzero_rational (x : ℚ) (hx : x ≠ 0) : (x + x) / x = 2 := by
  field_simp
  ring

end NablaMath
