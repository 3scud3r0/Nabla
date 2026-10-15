import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum

set_option autoImplicit false
set_option maxHeartbeats 200000
-- AST statement sha256: e30ca9ac75e30576d0dff1bb1482bd225c17301638f4edbebb9bfe51ff979526
theorem nabla_generated (nabla_x : ℚ)  : (nabla_x * (nabla_x + (1 : ℚ))) = ((nabla_x * nabla_x) + nabla_x) := by
  ring

#print axioms nabla_generated
