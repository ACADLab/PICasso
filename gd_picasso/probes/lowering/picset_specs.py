"""Step 1 probe: which PIC-Set tasks are expressible as lambda-lambda linear specs?"""
from psd_gate import infer_guarded as infer_unitary_from_spec
import traceback

TASKS = {
 # ---- C1 ----
 "MZI (balanced, 3dB)": (2, [
    "output(1) = (input(1) + input(2))/sqrt(2)",
    "output(2) = (input(1) - input(2))/sqrt(2)"]),
 "MMI 1x2 splitter": (1, [
    "output(1) = input(1)/sqrt(2)",
    "output(2) = input(1)/sqrt(2)"]),
 "2x2 optical switch (cross)": (2, [
    "output(1) = input(2)",
    "output(2) = input(1)"]),
 "MZM (push-pull, bar state)": (2, [
    "output(1) = input(1)",
    "output(2) = input(2)"]),
 # ---- C2 ----
 "90 deg optical hybrid (4x4)": (4, [
    "output(1) = (input(1) + input(2))/2",
    "output(2) = (input(1) - input(2))/2",
    "output(3) = (input(1) + I*input(2))/2",
    "output(4) = (input(1) - I*input(2))/2"]),
 "Tunable 1x4 switch (uniform)": (1, [
    "output(1) = input(1)/2", "output(2) = input(1)/2",
    "output(3) = input(1)/2", "output(4) = input(1)/2"]),
 "Ring add-drop (single wavelength pt)": (2, [
    "output(1) = 0.1*input(1)",
    "output(2) = 0.99*input(2)"]),
 # ---- C3 ----
 "4x4 crossbar (permutation)": (4, [
    "output(1) = input(3)", "output(2) = input(4)",
    "output(3) = input(1)", "output(4) = input(2)"]),
 "Clements 4x4 mesh (Hadamard-4)": (4, [
    "output(1) = (input(1)+input(2)+input(3)+input(4))/2",
    "output(2) = (input(1)-input(2)+input(3)-input(4))/2",
    "output(3) = (input(1)+input(2)-input(3)-input(4))/2",
    "output(4) = (input(1)-input(2)-input(3)+input(4))/2"]),
 "4-ch DFT / AWG-like (4-point)": (4, [
    "output(1) = (input(1)+input(2)+input(3)+input(4))/2",
    "output(2) = (input(1)+I*input(2)-input(3)-I*input(4))/2",
    "output(3) = (input(1)-input(2)+input(3)-input(4))/2",
    "output(4) = (input(1)-I*input(2)-input(3)+I*input(4))/2"]),
 # ---- deliberately infeasible: demands gain ----
 "INFEASIBLE PROBE (gain 2x)": (1, ["output(1) = 2*input(1)"]),
 # ---- lossy tap: sub-unitary, needs ancilla ----
 "Directional coupler 90:10 tap": (1, [
    "output(1) = sqrt(0.9)*input(1)"]),
}

print(f"{'task':40s} {'N':>3} {'anc':>4}  status")
print("-"*78)
ok=0
for name,(nin,spec) in TASKS.items():
    try:
        r = infer_unitary_from_spec(spec, nin)
        print(f"{name:40s} {r['N']:>3} {r['ancillas']:>4}  OK")
        ok+=1
    except Exception as e:
        msg=str(e).split("\n")[0][:38]
        print(f"{name:40s} {'-':>3} {'-':>4}  REJECT: {msg}")
print("-"*78)
print(f"expressible: {ok}/{len(TASKS)}")
