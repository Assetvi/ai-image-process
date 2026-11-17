import Std.Tactic

set_option autoImplicit false

namespace FrameCrop

/-- One axis of auto_box's padding after Pillow has found a nonempty foreground. -/
def padAxis (extent left right padding : Nat) : Nat × Nat :=
  (left - padding, min extent (right + padding))

theorem axis_safety (extent left right padding : Nat)
    (nonempty : left < right) (inside : right ≤ extent) :
    let result := padAxis extent left right padding
    result.1 ≤ left ∧ right ≤ result.2 ∧
      result.1 < result.2 ∧ result.2 ≤ extent := by
  dsimp [padAxis]
  omega

theorem foreground_retained (extent left right padding pixel : Nat)
    (inside : right ≤ extent) (low : left ≤ pixel) (high : pixel < right) :
    let result := padAxis extent left right padding
    result.1 ≤ pixel ∧ pixel < result.2 := by
  dsimp [padAxis]
  omega

theorem zero_padding (extent left right : Nat) (inside : right ≤ extent) :
    padAxis extent left right 0 = (left, right) := by
  simp [padAxis, Nat.min_eq_right inside]

theorem padding_monotone (extent left right small large : Nat)
    (ordered : small ≤ large) :
    (padAxis extent left right large).1 ≤ (padAxis extent left right small).1 ∧
    (padAxis extent left right small).2 ≤ (padAxis extent left right large).2 := by
  dsimp [padAxis]
  omega

theorem rectangle_foreground_retained
    (width height left top right bottom padding x y : Nat)
    (rightInside : right ≤ width) (bottomInside : bottom ≤ height)
    (xLow : left ≤ x) (xHigh : x < right)
    (yLow : top ≤ y) (yHigh : y < bottom) :
    (padAxis width left right padding).1 ≤ x ∧
    x < (padAxis width left right padding).2 ∧
    (padAxis height top bottom padding).1 ≤ y ∧
    y < (padAxis height top bottom padding).2 := by
  have hx := foreground_retained width left right padding x rightInside xLow xHigh
  have hy := foreground_retained height top bottom padding y bottomInside yLow yHigh
  exact ⟨hx.1, hx.2, hy.1, hy.2⟩

#print axioms axis_safety
#print axioms foreground_retained
#print axioms zero_padding
#print axioms padding_monotone
#print axioms rectangle_foreground_retained

end FrameCrop

/-- Finite cross-language fixtures; these supplement the universal theorems. -/
def main : IO Unit := do
  for extent in [1:13] do
    for left in [:extent] do
      for right in [left + 1:extent + 1] do
        for padding in [:21] do
          let result := FrameCrop.padAxis extent left right padding
          IO.println s!"CASE,{extent},{left},{right},{padding},{result.1},{result.2}"
