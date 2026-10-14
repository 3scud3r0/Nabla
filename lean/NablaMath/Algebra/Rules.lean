import NablaMath.Prelude
import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum

namespace NablaMath
theorem add_zero (x : ℚ) : x + 0 = x := by ring
theorem zero_add (x : ℚ) : 0 + x = x := by ring
theorem mul_one (x : ℚ) : x * 1 = x := by ring
theorem one_mul (x : ℚ) : 1 * x = x := by ring
theorem div_one (x : ℚ) : x / 1 = x := by ring
theorem pow_one (x : ℚ) : x ^ (1 : ℕ) = x := by simp
theorem add_self (x : ℚ) : x + x = 2 * x := by ring
theorem div_self (x : ℚ) (hx : x ≠ 0) : x / x = 1 := by field_simp
theorem cancel_mul_div (x y : ℚ) (hy : y ≠ 0) : (x * y) / y = x := by field_simp
theorem subtract_self (x : ℚ) : x - x = 0 := by ring

theorem add_comm_rule (x y : ℚ) : x + y = y + x := by ring

theorem mul_comm_rule (x y : ℚ) : x * y = y * x := by ring

theorem add_assoc_rule (x y z : ℚ) : (x + y) + z = x + (y + z) := by ring

theorem mul_assoc_rule (x y z : ℚ) : (x * y) * z = x * (y * z) := by ring

theorem add_zero_rule (x : ℚ) : x + 0 = x := by ring

theorem mul_one_rule (x : ℚ) : x * 1 = x := by ring

theorem div_one_rule (x : ℚ) : x / 1 = x := by norm_num

theorem pow_one_rule (x : ℚ) : x ^ 1 = x := by ring

theorem factor_common_left (a b c : ℚ) : a * b + a * c = a * (b + c) := by ring

theorem quotient_rule_identity (f f' g g' : ℚ) (hg : g ≠ 0) :
    (f' * g - f * g') / (g ^ 2) = f' / g - f * g' / (g ^ 2) := by
  field_simp

end NablaMath
