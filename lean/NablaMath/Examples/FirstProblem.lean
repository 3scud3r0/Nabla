import NablaMath.Algebra.Rules
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum

namespace NablaMath

/- A generated numeric instance is separate from a general theorem. -/
example : ((3 : ℚ) + 3) / 3 = 2 := by norm_num

example (x : ℚ) (hx : x ≠ 0) : (x + x) / x = 2 := by
  field_simp
  ring

end NablaMath
