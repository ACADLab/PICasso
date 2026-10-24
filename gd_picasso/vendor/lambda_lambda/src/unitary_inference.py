# optical_unitary_infer.py
# ------------------------------------------------------------
# Scalable symbolic inference of a unitary matrix from linear
# output specifications: "output(j) = <linear combo of input(i)>".
#
# Core idea:
#   1) Build constraint matrix R (k x n) symbolically.
#   2) Check S = I - R R^H (Hermitian PSD). If nonzero, construct
#      minimal ancilla block A with A A^H = S via eigen-decomposition.
#   3) Form K orthonormal  [R | A].
#   4) Complete to an N x N unitary using a nullspace + Cholesky
#      orthonormalization trick (avoids iterative Gram–Schmidt):
#         Z = nullspace([R|A]) rows  # N x (N-K), columns
#         G = Z^H Z = L L^H      # Cholesky
#         Z_orth = Z L^{-H}
#         rows_perp = Z_orth^H   # (N-K) x N orthonormal rows
#   5) Place constrained rows at requested output indices; fill rest
#      with rows_perp to get U (unitary).
#
# This keeps expressions symbolic (rationals, sqrt, exp(I*pi*k/q), ...).
# ------------------------------------------------------------

from __future__ import annotations
import re
import itertools
from typing import List, Tuple, Dict, Any, Optional, Literal, Sequence

import sympy as sp
import os

from optical_compiler import ast as oc_ast

I = sp.I
_VERBOSE = os.getenv("UNITARY_INFERENCE_VERBOSE", "0") != "0"


def _debug(message: str) -> None:
    if _VERBOSE:
        print(message)

# ---------- Parsing the spec into a symbolic R ----------

def _basis_vec(n: int, k1: int) -> sp.Matrix:
    """1-based index -> length-n column basis vector."""
    v = [sp.Integer(0)] * n
    v[k1-1] = sp.Integer(1)
    return sp.Matrix(v)

def _parse_rhs_sympy_eval(rhs: str, n_inputs: int) -> sp.Matrix:
    """
    Parse/evaluate RHS as a length-n column vector using a restricted environment.
    Supports: input(k), + - * /, parentheses, sqrt, pi, I/j, exp(I*theta).
    Only linear forms in input(k) are accepted.
    """
    rhs = rhs.replace('^', '**').replace('√', 'sqrt')
    def input_fn(k):
        return _basis_vec(n_inputs, int(k))
    env = {
        'input': input_fn,
        'sqrt': sp.sqrt,
        'pi': sp.pi,
        'I': sp.I,
        'j': sp.I,
        'exp': sp.exp,
    }
    expr = sp.sympify(rhs, locals=env)  # evaluated to allow scalar*Matrix
    # Coerce to column vector (n x 1), linear-only
    if isinstance(expr, sp.MatrixBase):
        v = expr
    else:
        v = sp.zeros(n_inputs, 1)
        for term in sp.Add.make_args(sp.expand(expr)):
            if isinstance(term, sp.MatrixBase):
                v += term
            elif isinstance(term, sp.Mul):
                scal = sp.Integer(1)
                vec = None
                for f in term.args:
                    if isinstance(f, sp.MatrixBase):
                        if vec is not None:
                            raise ValueError(f"Nonlinear term with multiple vectors: {term}")
                        vec = f
                    else:
                        scal *= f
                if vec is None:
                    raise ValueError(f"RHS term is not linear in inputs: {term}")
                v += sp.simplify(scal) * vec
            else:
                if term != 0:
                    raise ValueError(f"Scalar term without input(): {term}")
    if v.shape != (n_inputs, 1):
        raise ValueError(f"RHS did not evaluate to a length-{n_inputs} column vector, got {v.shape}")
    return sp.simplify(v)

def parse_spec_sympy_eval(lines: List[str], n_inputs: int) -> Tuple[List[int], sp.Matrix]:
    """
    Returns:
      out_indices : list of output indices (1-based)
      R           : k x n symbolic matrix of constrained rows
    """
    out_inds, rows = [], []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if '=' not in s:
            raise ValueError(f"Missing '=': {raw}")
        lhs, rhs = s.split('=', 1)
        lhs, rhs = lhs.strip(), rhs.strip()
        m = re.match(r'output\s*\(\s*(\d+)\s*\)\s*$', lhs, flags=re.IGNORECASE)
        if not m:
            raise ValueError(f"LHS must be output(k): {lhs}")
        j = int(m.group(1))
        _debug(rhs)
        v = _parse_rhs_sympy_eval(rhs, n_inputs)  # n x 1
        out_inds.append(j)
        rows.append(v.T)  # 1 x n
    R = sp.Matrix.vstack(*rows) if rows else sp.Matrix.zeros(0, n_inputs)
    return out_inds, sp.simplify(R)

# ---------- Build ancilla block from PSD remainder ----------

def build_A_from_psd_eig(S: sp.Matrix) -> sp.Matrix:
    """
    Given Hermitian PSD S (k x k), construct A (k x m) s.t. A A^H = S.
    Uses symbolic eigen-decomposition and normalizes eigenvectors.
    """
    if S.is_zero_matrix:
        return sp.zeros(S.shape[0], 0)
    # Ensure Hermitian
    if not (S - S.H).applyfunc(sp.simplify).is_zero_matrix:
        raise ValueError("S is not Hermitian symbolically")
    ev = S.eigenvects()  # list of (lambda, multiplicity, [eigenvectors])
    cols = []
    lam_list = []
    for lam, mult, vecs in ev:
        lam_s = sp.simplify(lam)
        _debug("eigvec norm computation")
        if lam_s.equals(0):
            continue
        for v in vecs:
            v = sp.Matrix(v)
            # Normalize eigenvector for stability
            nrm2 = (v.H * v)[0,0]
            _debug(f"eigvec norm^2={nrm2}")
            if nrm2 == 0:
                continue
            cols.append(v / sp.sqrt(nrm2))
            lam_list.append(lam_s)
    if not cols:
        return sp.zeros(S.shape[0], 0)
    Vpos = sp.Matrix.hstack(*cols)  # k x m
    Dsqrt = sp.diag(*[sp.sqrt(l) for l in lam_list])  # m x m
    A = sp.simplify(Vpos * Dsqrt)  # k x m so that A A^H = S
    return A

# ---------- Complete to a unitary via nullspace + Cholesky ----------

def orthonormal_rows_via_nullspace_chol(rows_ext: sp.Matrix) -> sp.Matrix:
    """
    Given rows_ext (K x N) with orthonormal rows, produce (N-K) orthonormal
    rows forming an orthonormal basis of its orthogonal complement.
      1) Z = nullspace(rows_ext) as columns (N x (N-K))
      2) G = Z^H Z = L L^H  (Cholesky)
      3) Z_orth = Z L^{-H}
      4) rows_perp = Z_orth^H
    Returns rows_perp ( (N-K) x N ).
    """
    K, N = rows_ext.shape
    cols = rows_ext.nullspace()
    if len(cols) != N - K:
        # If SymPy returns fewer, try simplifying rows first
        raise ValueError(f"Unexpected nullspace dimension {len(cols)} vs expected {N-K}. Try simplify inputs.")
    Z = sp.Matrix.hstack(*cols)  # N x (N-K)
    G = sp.simplify(Z.H * Z)
    # For independent columns, G is Hermitian positive definite
    L = G.cholesky()  # G = L L^H
    C = L.inv().H     # L^{-H}
    Z_orth = sp.simplify(Z * C)
    rows_perp = sp.simplify(Z_orth.H)
    # print("E Shape")
    # print(rows_perp.shape)
    return rows_perp

# ---------- Main inference API ----------

def infer_unitary_from_spec_symbolic_scalable(spec_lines: List[str], n_inputs: int) -> Dict[str, Any]:
    """
    End-to-end: infer a symbolic unitary U from linear output specs.
    Returns dict with:
      - 'U'          : SymPy Matrix (N x N)
      - 'N'          : dimension (n + ancillas)
      - 'ancillas'   : number of ancilla vacuum ports used
      - 'out_indices': list of outputs constrained
      - 'R'          : the k x n constrained row matrix
    """
    out_indices, R = parse_spec_sympy_eval(spec_lines, n_inputs)
    k, n = R.shape
    _debug("R is computed as")
    if _VERBOSE:
        print(R)
    # PSD remainder
    S = sp.simplify(sp.eye(k) - R * R.H)
    # Ancilla block A
    A = build_A_from_psd_eig(S)  # k x m
    m = A.shape[1]
    N = n + m
    _debug("Found A")
    # Constrained orthonormal rows [R | A]
    rows_ext = R if m == 0 else sp.Matrix.hstack(R, A)
    # Complement rows via nullspace + Cholesky
    _debug("rows_ext is computed as")
    if _VERBOSE:
        print(rows_ext)
    rows_perp = orthonormal_rows_via_nullspace_chol(rows_ext)
    # Assemble U with specified rows placed at requested output indices
    U = sp.Matrix.zeros(N, N)
    used = set()
    for i in range(k):
        t = out_indices[i] - 1
        if t in used:
            raise ValueError(f"Duplicate output index: output({out_indices[i]})")
        used.add(t)
        U[t, :] = rows_ext[i, :]
    rem_rows = [r for r in range(N) if r not in used]
    for r_idx, t in enumerate(rem_rows):
        U[t, :] = rows_perp[r_idx, :]
    U = sp.simplify(U)
    return {'U': U, 'N': N, 'ancillas': m, 'out_indices': out_indices, 'R': R}

# ---------- Fast numeric backend ----------

def _sympy_matrix_to_numpy(M: sp.Matrix, eval_prec: int = 50):
    try:
        import numpy as np
    except ImportError as exc:
        raise ImportError("numpy is required for the fast inference backend.") from exc
    rows = [[complex(val.evalf(eval_prec)) for val in row] for row in M.tolist()]
    return np.array(rows, dtype=complex)


def _unitary_inference_fast_from_R(
    R, target_indices: List[int], tol: float = 1e-12
):
    try:
        import numpy as np
        from scipy.linalg import null_space, cholesky
    except ImportError as exc:
        raise ImportError("scipy is required for the fast inference backend.") from exc

    R = np.array(R, dtype=complex)
    k, n = R.shape

    # --- Step 1: Defect Analysis ---
    S = np.eye(k, dtype=complex) - R @ R.conj().T
    eigvals, eigvecs = np.linalg.eigh(S)
    if np.any(eigvals < -tol):
        raise ValueError(
            "Specification R is not a contraction (S is not PSD). "
            f"Smallest eigenvalue: {np.min(eigvals)}"
        )

    mask = eigvals > tol
    m = int(np.sum(mask))
    if m > 0:
        V_plus = eigvecs[:, mask]
        Lambda_plus_sqrt = np.diag(np.sqrt(eigvals[mask]))
        A = V_plus @ Lambda_plus_sqrt
    else:
        A = np.zeros((k, 0), dtype=complex)

    E = np.hstack([R, A])
    N = n + m

    # --- Step 2: Orthonormal Complement ---
    if N == k:
        F = np.zeros((0, N), dtype=complex)
    else:
        Z = null_space(E, rcond=tol)
        G = Z.conj().T @ Z
        L = cholesky(G, lower=True)
        Z_orth = Z @ np.linalg.inv(L.conj().T)
        F = Z_orth.conj().T

    # --- Step 3: Synthesis & Permutation ---
    target_zero = [i - 1 for i in target_indices]
    if len(set(target_zero)) != len(target_zero):
        raise ValueError(f"Duplicate output index: {target_indices}")
    if any(i < 0 or i >= N for i in target_zero):
        raise ValueError(f"Output index out of range for N={N}: {target_indices}")

    U = np.zeros((N, N), dtype=complex)
    remaining = [i for i in range(N) if i not in set(target_zero)]
    for i, target_idx in enumerate(target_zero):
        U[target_idx, :] = E[i, :]
    for i, remain_idx in enumerate(remaining):
        U[remain_idx, :] = F[i, :]

    return U, m


def infer_unitary_from_spec_fast(
    spec_lines: List[str],
    n_inputs: int,
    tol: float = 1e-12,
    eval_prec: int = 50,
) -> Dict[str, Any]:
    out_indices, R = parse_spec_sympy_eval(spec_lines, n_inputs)
    R_np = _sympy_matrix_to_numpy(R, eval_prec=eval_prec)
    U_np, m = _unitary_inference_fast_from_R(R_np, out_indices, tol=tol)
    U = sp.Matrix(U_np)
    return {'U': U, 'N': int(U.shape[0]), 'ancillas': m, 'out_indices': out_indices, 'R': R}


def infer_unitary_from_spec(
    spec_lines: List[str],
    n_inputs: int,
    backend: Literal["symbolic", "fast"] = "symbolic",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Unified entrypoint for unitary inference.
      backend="symbolic" -> infer_unitary_from_spec_symbolic_scalable
      backend="fast"     -> infer_unitary_from_spec_fast (numpy/scipy)
    """
    if backend == "symbolic":
        return infer_unitary_from_spec_symbolic_scalable(spec_lines, n_inputs)
    if backend == "fast":
        return infer_unitary_from_spec_fast(spec_lines, n_inputs, **kwargs)
    raise ValueError(f"Unknown backend '{backend}'. Expected 'symbolic' or 'fast'.")


def infer_unitary_program_from_spec(
    spec_lines: List[str],
    n_inputs: int,
    backend: Literal["symbolic", "fast"] = "symbolic",
    input_ports: Optional[List[int]] = None,
    output_ports: Optional[List[int]] = None,
    program_tol: float = 1e-9,
    program_backend: Literal["symbolic", "reck_numpy"] = "symbolic",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Convenience wrapper: infer a unitary and immediately synthesize a program.
    Returns the same dict as infer_unitary_from_spec plus a 'program' entry.
    """
    res = infer_unitary_from_spec(spec_lines, n_inputs, backend=backend, **kwargs)
    res["program"] = unitary_to_program(
        res["U"],
        input_ports=input_ports,
        output_ports=output_ports,
        tol=program_tol,
        backend=program_backend,
    )
    return res

# ---------- Utilities ----------

def is_unitary(U: sp.Matrix, tol: float = 1e-40) -> bool:
    """Numeric check (high precision) that U*U^H == I."""
    U_num = U.evalf(80)
    Id = (U_num * U_num.H).evalf(80)
    N = U.shape[0]
    mx = max([abs(Id[i, j] - (1 if i == j else 0)) for i in range(N) for j in range(N)])
    U_dagger = U.H

    # Multiply U by its Hermitian conjugate
    product = U * U_dagger

    # Create an identity matrix of the same size
    identity_matrix = sp.eye(U.rows)
    _debug(str(product))
    assert(product == identity_matrix)
    return mx < tol

def save_matrix_srepr(U: sp.Matrix, path: str) -> None:
    with open(path, "w") as f:
        f.write(sp.srepr(U))

def symbolic_outputs_polar(U: sp.Matrix, n_physical: int, simplify: bool = True):
    if not isinstance(U, sp.MatrixBase):
        U = sp.Matrix(U)
    N = int(U.shape[0])
    assert U.shape == (N, N), "U must be square (N x N)"
    assert 0 < n_physical <= N, "n_physical must be in 1..N"

    A = sp.symbols('A1:'+str(n_physical+1), positive=True)
    theta = sp.symbols('theta1:'+str(n_physical+1), real=True)
    z_phys = [A[i]*sp.exp(sp.I*theta[i]) for i in range(n_physical)]
    z_vec = sp.Matrix(z_phys + [sp.Integer(0)]*(N - n_physical))
    y_vec = U * z_vec
    if simplify:
        y_vec = sp.simplify(y_vec)
    return {'A': A, 'theta': theta}, z_vec, y_vec

# ---------- Clements decomposition + program synthesis ----------


def _givens_zero(a: sp.Expr, b: sp.Expr, tol: float = 1e-12) -> sp.Matrix:
    """Return 2x2 unitary G so that G @ [a, b]^T = [r, 0]^T."""
    a_s = sp.simplify(a)
    b_s = sp.simplify(b)
    if float(sp.Abs(b_s).evalf()) <= tol:
        return sp.eye(2)
    r = sp.sqrt(a_s * sp.conjugate(a_s) + b_s * sp.conjugate(b_s))
    if float(sp.Abs(r).evalf()) <= tol:
        return sp.eye(2)
    return sp.Matrix(
        [
            [sp.conjugate(a_s) / r, sp.conjugate(b_s) / r],
            [-b_s / r, a_s / r],
        ]
    )


def clements_decomposition(U: sp.Matrix, tol: float = 1e-12) -> Tuple[List[Tuple[int, int, sp.Matrix]], List[sp.Expr]]:
    """
    Factor a unitary U into a sequence of 2x2 rotations (Clements/Reck style).
    Returns (ops, phases) where:
      ops    : list of (row_top, row_bottom, G) applied from left during elimination
      phases : list of per-mode diagonal phases remaining after elimination
    """
    if not isinstance(U, sp.MatrixBase):
        U = sp.Matrix(U)
    n_rows, n_cols = U.shape
    if n_rows != n_cols:
        raise ValueError("Clements decomposition expects a square unitary.")
    N = n_rows
    work = sp.Matrix(U)
    ops: List[Tuple[int, int, sp.Matrix]] = []

    for col in range(N):
        for row in range(N - 1, col, -1):
            a = sp.simplify(work[row - 1, col])
            b = sp.simplify(work[row, col])
            if float(sp.Abs(b).evalf()) <= tol:
                continue
            G = _givens_zero(a, b, tol=tol)
            work[row - 1 : row + 1, :] = sp.simplify(G * work[row - 1 : row + 1, :])
            ops.append((row - 1, row, G))

    phases: List[sp.Expr] = []
    for i in range(N):
        val = sp.simplify(work[i, i])
        mag = float(sp.Abs(val).evalf())
        if mag <= tol:
            phases.append(sp.Integer(1))
        else:
            phases.append(sp.simplify(val / sp.Abs(val)))
    return ops, phases


def _matrix_to_py_complex(M: sp.Matrix, tol: float = 1e-12) -> List[List[complex]]:
    """Convert a 2x2 SymPy matrix to Python complex lists with small parts zeroed."""
    def _c(val: sp.Expr) -> complex:
        z = complex(val.evalf())
        re = 0.0 if abs(z.real) < tol else z.real
        im = 0.0 if abs(z.imag) < tol else z.imag
        return complex(re, im)

    rows: List[List[complex]] = []
    for r in M.tolist():
        rows.append([_c(val) for val in r])
    return rows


def _matrix_to_py_complex_np(M, tol: float = 1e-12) -> List[List[complex]]:
    rows: List[List[complex]] = []
    for row in M:
        vals: List[complex] = []
        for val in row:
            z = complex(val)
            re = 0.0 if abs(z.real) < tol else z.real
            im = 0.0 if abs(z.imag) < tol else z.imag
            vals.append(complex(re, im))
        rows.append(vals)
    return rows


def _givens_zero_np(a: complex, b: complex, tol: float = 1e-12):
    import numpy as np

    if abs(b) <= tol:
        return np.eye(2, dtype=complex)
    r = np.sqrt(abs(a) ** 2 + abs(b) ** 2)
    if r <= tol:
        return np.eye(2, dtype=complex)
    return np.array(
        [
            [np.conjugate(a) / r, np.conjugate(b) / r],
            [-b / r, a / r],
        ],
        dtype=complex,
    )


def reck_decomposition_numpy(U, tol: float = 1e-12) -> Tuple[List[Tuple[int, int, object]], List[complex]]:
    """
    Numeric Reck-style decomposition using NumPy.
    Returns (ops, phases) where ops is a list of (row_top, row_bottom, G).
    """
    import numpy as np

    work = np.array(U, dtype=complex, copy=True)
    if work.shape[0] != work.shape[1]:
        raise ValueError("Reck decomposition expects a square unitary.")
    N = work.shape[0]
    ops: List[Tuple[int, int, object]] = []

    for col in range(N):
        for row in range(N - 1, col, -1):
            a = work[row - 1, col]
            b = work[row, col]
            if abs(b) <= tol:
                continue
            G = _givens_zero_np(a, b, tol=tol)
            work[row - 1 : row + 1, :] = G @ work[row - 1 : row + 1, :]
            ops.append((row - 1, row, G))

    phases: List[complex] = []
    for i in range(N):
        val = work[i, i]
        mag = abs(val)
        phases.append(val / mag if mag > tol else 1.0 + 0.0j)
    return ops, phases


def unitary_to_program(
    U: sp.Matrix,
    input_ports: Optional[List[int]] = None,
    output_ports: Optional[List[int]] = None,
    tol: float = 1e-9,
    backend: Literal["symbolic", "reck_numpy"] = "symbolic",
) -> oc_ast.Expr:
    """
    Synthesize a program (using 2x2 unitaries) that realises the given unitary U.

    Args:
        U: NxN SymPy matrix (unitary).
        input_ports: optional list of port numbers for inputs; defaults to 1..N.
        output_ports: optional list of output port numbers; defaults to 1..N.
        tol: numerical tolerance for pruning small entries/phases.
    """
    if backend == "reck_numpy":
        return unitary_to_program_fast(U, input_ports=input_ports, output_ports=output_ports, tol=tol)

    if not isinstance(U, sp.MatrixBase):
        U = sp.Matrix(U)
    n_rows, n_cols = U.shape
    if n_rows != n_cols:
        raise ValueError("unitary_to_program expects a square matrix.")
    N = n_rows
    if input_ports is None:
        input_ports = list(range(1, N + 1))
    if output_ports is None:
        output_ports = list(range(1, N + 1))
    if len(input_ports) != N or len(output_ports) != N:
        raise ValueError("input_ports and output_ports must have length N.")

    ops, phases = clements_decomposition(U, tol=tol)
    name_counter = itertools.count()

    actions: List[Tuple[str, ...]] = []
    signals: List[str] = []
    # Bind inputs
    for port in input_ports:
        name = f"s{next(name_counter)}"
        actions.append(("let", name, oc_ast.Input(port)))
        signals.append(name)

    # Per-mode phases from the residual diagonal (applied first in the circuit).
    for idx, phase in enumerate(phases):
        phase_val = complex(phase.evalf())
        if abs(phase_val - 1.0) <= tol:
            continue
        theta = float(sp.arg(phase).evalf())
        new_name = f"s{next(name_counter)}"
        actions.append(("let", new_name, oc_ast.Phase(signal=oc_ast.Var(signals[idx]), theta=theta)))
        signals[idx] = new_name

    # Two-mode rotations: apply adjoints in reverse order to match U = G1^H...Gm^H * diag(phases).
    for top, bottom, G in reversed(ops):
        G_dag = G.conjugate().T
        matrix = _matrix_to_py_complex(G_dag)
        pair_expr = oc_ast.Pair(oc_ast.Var(signals[top]), oc_ast.Var(signals[bottom]))
        unit_expr = oc_ast.Unitary(matrix=matrix, signal=pair_expr)
        left_name = f"s{next(name_counter)}"
        right_name = f"s{next(name_counter)}"
        actions.append(("unpack", left_name, right_name, unit_expr))
        signals[top] = left_name
        signals[bottom] = right_name

    # Outputs
    for port, name in zip(output_ports, signals):
        actions.append(("output", port, oc_ast.Var(name)))

    body: oc_ast.Expr = oc_ast.UnitLiteral()
    for action in reversed(actions):
        kind = action[0]
        if kind == "let":
            _, name, expr = action
            body = oc_ast.Let(name=name, value=expr, body=body)
        elif kind == "unpack":
            _, left, right, pair_expr = action
            body = oc_ast.Unpack(pair_expr=pair_expr, left_name=left, right_name=right, body=body)
        elif kind == "output":
            _, port, expr = action
            body = oc_ast.LetOutput(port=port, value=expr, body=body)
        else:
            raise ValueError(f"Unknown action kind: {kind}")
    return body


def unitary_to_program_fast(
    U,
    input_ports: Optional[List[int]] = None,
    output_ports: Optional[List[int]] = None,
    tol: float = 1e-9,
) -> oc_ast.Expr:
    """
    Faster numeric unitary -> program synthesis using NumPy Reck decomposition.
    Accepts a NumPy array or a SymPy matrix.
    """
    import numpy as np

    if isinstance(U, sp.MatrixBase):
        U_np = np.array(U.evalf(50).tolist(), dtype=complex)
    else:
        U_np = np.array(U, dtype=complex)
    if U_np.shape[0] != U_np.shape[1]:
        raise ValueError("unitary_to_program_fast expects a square matrix.")
    N = int(U_np.shape[0])
    if input_ports is None:
        input_ports = list(range(1, N + 1))
    if output_ports is None:
        output_ports = list(range(1, N + 1))
    if len(input_ports) != N or len(output_ports) != N:
        raise ValueError("input_ports and output_ports must have length N.")

    ops, phases = reck_decomposition_numpy(U_np, tol=tol)
    name_counter = itertools.count()

    actions: List[Tuple[str, ...]] = []
    signals: List[str] = []
    for port in input_ports:
        name = f"s{next(name_counter)}"
        actions.append(("let", name, oc_ast.Input(port)))
        signals.append(name)

    for idx, phase in enumerate(phases):
        phase_val = complex(phase)
        if abs(phase_val - 1.0) <= tol:
            continue
        theta = float(np.angle(phase_val))
        new_name = f"s{next(name_counter)}"
        actions.append(("let", new_name, oc_ast.Phase(signal=oc_ast.Var(signals[idx]), theta=theta)))
        signals[idx] = new_name

    for top, bottom, G in reversed(ops):
        G_dag = np.conjugate(G).T
        matrix = _matrix_to_py_complex_np(G_dag, tol=tol)
        pair_expr = oc_ast.Pair(oc_ast.Var(signals[top]), oc_ast.Var(signals[bottom]))
        unit_expr = oc_ast.Unitary(matrix=matrix, signal=pair_expr)
        left_name = f"s{next(name_counter)}"
        right_name = f"s{next(name_counter)}"
        actions.append(("unpack", left_name, right_name, unit_expr))
        signals[top] = left_name
        signals[bottom] = right_name

    for port, name in zip(output_ports, signals):
        actions.append(("output", port, oc_ast.Var(name)))

    body: oc_ast.Expr = oc_ast.UnitLiteral()
    for action in reversed(actions):
        kind = action[0]
        if kind == "let":
            _, name, expr = action
            body = oc_ast.Let(name=name, value=expr, body=body)
        elif kind == "unpack":
            _, left, right, pair_expr = action
            body = oc_ast.Unpack(pair_expr=pair_expr, left_name=left, right_name=right, body=body)
        elif kind == "output":
            _, port, expr = action
            body = oc_ast.LetOutput(port=port, value=expr, body=body)
        else:
            raise ValueError(f"Unknown action kind: {kind}")
    return body

# ---------- Demos ----------

if __name__ == "__main__":
    # Demo A: 8-input uniform average on output(1)
    specA = ["output(1) = (input(1)+input(2)+input(3)+input(4)+input(5)+input(6)+input(7)+input(8))/sqrt(8)"]
    resA = infer_unitary_from_spec_symbolic_scalable(specA, n_inputs=8)
    UA = resA['U']
    print("Demo A: N =", resA['N'], " ancillas =", resA['ancillas'])
    print("First row:", UA[0, :])
    print("Unitary check (numeric):", is_unitary(UA))

    from sympy import pprint
    # pprint(UA)
    y = (symbolic_outputs_polar(UA, 8)[2][0])
    prog = unitary_to_program(UA)
    # print((prog))
    from optical_compiler import format_expr
    # prog is the AST returned by unitary_to_program(...)
    print(format_expr(prog))

    # Demo B: Two outputs, non-orthogonal but contractive -> needs ancilla
    specB = [
        "output(1) = (input(1) + input(2) ) / sqrt(2)",
        "output(2) = (input(1) - input(2)) / sqrt(2)"
    ]
    resB = infer_unitary_from_spec_symbolic_scalable(specB, n_inputs=2)
    UB = resB['U']
    # print("Demo B: N =", resB['N'], " ancillas =", resB['ancillas'])
    # print(UB)
    # print("Row 1 (phys):", UB[0, :4])
    # print("Row 2 (phys):", UB[1, :4])
    # print("Unitary check (numeric):", is_unitary(UB))


    # Demo A: 4-input uniform average on output(1)
    specA = ["output(1) = (input(1)+input(2)+input(3)+input(4))/(2)",
             "output(2) = (input(1)+input(2)-input(3)-input(4))/(2)",
             "output(3) = (input(1)-input(2)+input(3)-input(4))/(2)",
             "output(4) = (input(1)-input(2)-input(3)+input(4))/(2)"]
    resA = infer_unitary_from_spec_symbolic_scalable(specA, n_inputs=4)
    UA = resA['U']
    print("Demo A: N =", resA['N'], " ancillas =", resA['ancillas'])
    # print("First row:", UA[0, :])
    print("Unitary check (numeric):", is_unitary(UA))
    from sympy import pprint
    pprint(UA)
    # pprint(symbolic_outputs_polar(UA, 4)[2][1])
    prog = unitary_to_program(UA)
    # print((prog))
    from optical_compiler import format_expr
    # prog is the AST returned by unitary_to_program(...)
    print(format_expr(prog))
    from optical_compiler import format_expr  # optional
    from symbolic_executor import execute_symbolic

    res = execute_symbolic(prog)  # prog is your AST
    print(res.expressions)
    print(res.expressions[4])
    print(res.expressions[1])
    print(res.expressions[2])
    print(res.expressions[3])
    # print(res.outputs)  # port -> {input_idx: coeff}
    # print(res.matrix)   # rows = outputs (sorted ports), cols = inputs (sorted)
