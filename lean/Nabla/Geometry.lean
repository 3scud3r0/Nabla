import Mathlib.Tactic.Ring
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum

namespace Nabla

structure Point where
  x : ℚ
  y : ℚ

def squaredDistance (a b : Point) : ℚ := (a.x-b.x)^2 + (a.y-b.y)^2

def midpoint (a b : Point) : Point := ⟨(a.x+b.x)/2, (a.y+b.y)/2⟩

theorem midpoint_equal_distance (a b : Point) :
    squaredDistance (midpoint a b) a = squaredDistance (midpoint a b) b := by
  simp only [squaredDistance, midpoint]
  ring

theorem pythagorean (ux uy vx vy : ℚ) (h : ux*vx + uy*vy = 0) :
    (ux-vx)^2 + (uy-vy)^2 = (ux^2+uy^2) + (vx^2+vy^2) := by
  nlinarith

theorem right_triangle_circumcircle (u v : ℚ) :
    squaredDistance ⟨u/2, v/2⟩ ⟨0, 0⟩ = squaredDistance ⟨u/2, v/2⟩ ⟨u, 0⟩ := by
  simp only [squaredDistance]
  ring

end Nabla
