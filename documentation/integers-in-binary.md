# Integers in binary, and the lowest-set-bit trick

Prerequisite for entry 4 of [`order-flow-to-order-book.md`](order-flow-to-order-book.md),
where `BitmapBook` and `TickArrayBook` find the best price on a side with three operations on
a single integer. Those operations are standard and they are not obvious; this note derives
them, proves them, measures them, and stops.

**Notation.** Formulas below use the logic symbols on the left; code snippets use Python's own
operators on the right. The two never mix.

| logic | meaning | Python |
| --- | --- | --- |
| $\sim$ | complement / NOT | `~` |
| $\wedge$ | AND | `&` |
| $\vee$ | OR | `\|` |
| $\oplus$ | XOR | `^` |

---

## 1. A number as a set

Read an integer by its binary digits rather than by its magnitude, and it is a **set of
positions**: bit $k$ of $B$ is set exactly when $k$ belongs to the set. Prices already live on
an integer grid, so with an origin $p_0$ the position $k = p - p_0$ is a price and one integer
is the occupancy of a whole side of the book.

| operation | meaning |
| --- | --- |
| `bit = 1 << k` | the singleton $\{k\}$ |
| `B \|= bit` | add $k$ — occupy the level |
| `B &= ~bit` | remove $k$ — vacate the level |
| `B & bit` | test membership |
| `B.bit_count()` | the size of the set, so the number of occupied levels |

Removal is `&= ~bit` and not `^= bit`: exclusive-or *toggles*, so it removes a level that is
there and creates one that is not. Only one of the two is idempotent, and the book calls it on
every write.

In C the set is capped at the width of a machine word, and a wide price range means an array of
words with the index arithmetic done by hand. Python's integers are unbounded, so the set is as
wide as the market and needs no declared band — which is why `BitmapBook`, unlike
`TickArrayBook`, has no upper edge to fall off.

## 2. Bit sequences, two ways

Let $S = \{0,1\}^{\mathbb{N}}$, the infinite $0/1$ sequences indexed from $0$. For $f \in S$
write $\pi_d(f)$ for its truncation to positions $0,\dots,d$, and let $\sim, \wedge, \vee,
\oplus$ act pointwise on $S$ — the operators of §1, now acting on the whole sequence rather
than on a fixed-width pattern.

For $d \in \mathbb{N}$ let $R_d := \mathbb{Z}/2^{d+1}\mathbb{Z}$, with $\mathrm{mod}_d : \mathbb{Z}
\to R_d$ the reduction map, and let $\mathbb{F}_2 := R_0$. Let $P_d$ be the tuples
$(f_0,\dots,f_d) \in \mathbb{F}_2^{d+1}$, read as polynomials over $\mathbb{F}_2$ of degree at
most $d$; for $f \in P_d$ nonzero, $\deg(f)$ is the largest $k$ with $f_k \ne 0$, and
$\deg(0) := -1$ (this convention pays for itself twice below). Coordinatewise XOR makes $P_d$
an abelian group, $(\mathbb{F}_2^{d+1}, \oplus) \cong (\mathbb{Z}/2)^{d+1}$.

**Proposition 1.** The map $\iota_d : R_d \to P_d$ sending $x \in \{0,\dots,2^{d+1}-1\}$ to its
binary digits is a bijection.

This is standard base-2 digit uniqueness, and it is a bijection of *sets only*. Transporting
$R_d$'s addition through $\iota_d$ gives $P_d$ a second abelian-group structure, the one with
carries, isomorphic to the *cyclic* group $\mathbb{Z}/2^{d+1}\mathbb{Z}$ — genuinely different
from the XOR structure once $d \ge 1$: $\mathbb{Z}/4\mathbb{Z}$ has an element of additive order
$4$, while every element of $(\mathbb{Z}/2)^2$ has order at most $2$, so the two groups on $P_1$
are not isomorphic. Both live on the same four bit patterns, and the rest of this note is largely
about not confusing them: XOR is carry-free, integer addition is not. Neither structure is
extended to a ring here — ordinary $\mathbb{F}_2$-polynomial multiplication does not even close
on $P_d$ (two degree-$d$ factors can have a degree-$2d$ product) — and nothing below multiplies
two bit patterns, only adds them, two different ways.

Let $P := \bigcup_d P_d \subset S$: exactly the *eventually-zero* sequences, $f \in P$ iff there
is $L$ with $f_k = 0$ for all $k > L$, and $L = \deg(f)$ always works (including $\deg(0)=-1$,
covering $f=0$). Let $\bar{B} : P \to \mathbb{N}$, $\bar B(f) = \sum_k f_k 2^k$.

**Proposition 2.** $\bar B$ is a bijection; write $B$ for its inverse, the binary
representation of $\mathbb{N}$.

Injectivity is uniqueness of binary digits. Surjectivity is existence, by strong induction on
$n$: $n=0$ is $\bar B(0)$; for $n>0$ write $n = 2q+r$ with $r = n \bmod 2$, and prepend $r$ to
the (inductively given) expansion of $q$.

## 3. Two's complement, forced

### A counting argument

Fix a width $n$ bits — equivalently, set $d = n-1$ and work in $R_d = \mathbb{Z}/2^n\mathbb{Z}$.
There are $2^n$ patterns, so a signed reading is a map $\{0,1\}^n \to \mathbb{Z}$, and the first
question to ask of one is whether it is injective. Enumerating all 256 patterns at $n = 8$
under the three classical readings:

| reading | distinct values | range | one-to-one |
| --- | --- | --- | --- |
| two's complement | 256 | $[-128, 127]$ | yes |
| ones' complement | 255 | $[-127, 127]$ | no |
| sign-magnitude | 255 | $[-127, 127]$ | no |

The two losers are symmetric about zero, which sounds like a virtue and is precisely the
defect: a symmetric range of integers has odd cardinality, $2^n$ is even, so one pattern is
left over and both schemes spend it on a second zero.

Two's complement is not merely the survivor, and the reason is worth stating on its own. Binary
addition with the carry off the top discarded **is** addition in $R_d$ — that is what the adder
computes, before anyone has decided what a pattern means. A signed reading is therefore a choice
of *representatives* for $R_d$'s residue classes, and any complete set of representatives is a
bijection automatically — the same freedom Proposition 1 exercises to build $\iota_d$, aimed at
a different window of representatives. Two's complement takes $\{-2^{n-1}, \dots, 2^{n-1}-1\}$,
one per class; the other two readings take sets that are not complete residue systems, which is
the paragraph above counted a second time. The practical form of the same fact: one adder serves
the signed and the unsigned reading at once, and only this scheme has that property.

Two consequences, both used below.

- $-m$ is not a minus sign attached to $m$. It is the additive inverse **in the ring**, namely
  $2^n - m$ — so "invert and add one" is a theorem and not a recipe: writing $\overline m$ for
  the complement of the low $n$ bits, $m + \overline m = 2^n - 1$ by construction, hence
  $\overline m + 1 = 2^n - m$.
- Being exact leaves a fingerprint: $-2^{n-1}$ has no positive counterpart, which is why
  `abs()` overflows at `INT_MIN` in C. One-to-one and symmetric cannot both hold.

The first consequence is worth proving outright rather than leaving as an identity checked by
construction. Let $c_d : R_d \to R_d$, $c_d(x) = -x-1$.

**Proposition 3.** For every $x \in R_d$, $\iota_d(c_d(x)) = \pi_d\big(\sim \iota_d(x)\big)$:
complementing the bit pattern within its own $d+1$-bit window computes $c_d$.

*Proof.* Write $f = \iota_d(x)$, so $x = \sum_{k=0}^d f_k 2^k$. Flipping every one of the $d+1$
coordinates of $f$ and reading off the value gives $\sum_k (1-f_k)2^k = (2^{d+1}-1) - x$, which
is exactly $c_d(x) = -x-1 \bmod 2^{d+1}$. $\blacksquare$

So $c_d(x) + 1 = -x$: complementing a fixed-width pattern and adding one negates it — the first
bullet above, proved.

## 4. The embedding of $\mathbb{Z}$ into $S$

$P \subset S$ is the eventually-zero sequences; write $\sim\!P$ for the eventually-*one*
sequences (the complements of elements of $P$), and $\bar P := P \cup \sim\!P$, the
eventually-constant sequences.

**Definition.** $\Phi : \mathbb{Z} \to S$, $\Phi(x) = B(x)$ if $x \ge 0$, and
$\Phi(x) = \sim\! B(-1-x)$ if $x < 0$.

(The $-1$ matters: $\sim\! B(-x)$ is *not* $\Phi(x)$, it is $\Phi(x-1)$ — one step further
negative — the easiest place in this whole construction to be off by one.)

**Theorem.** $\Phi$ is injective, with image exactly $\bar P$ — $\Phi(x) \in P$ iff $x \ge 0$
and $\Phi(x) \in \sim\!P$ iff $x < 0$ — and for every $d$,
$$\pi_d(\Phi(x)) = \iota_d(\mathrm{mod}_d(x)).$$

*Proof.* For $x \ge 0$, $\Phi(x) = B(x) \in P$; for $x<0$, $-1-x \ge 0$ so $B(-1-x) \in P$ is
eventually zero, hence $\Phi(x) = \sim\! B(-1-x)$ is eventually one. A sequence cannot be both
eventually zero and eventually one, so the two cases have disjoint images; each case is
injective ($x \mapsto -1-x$, $B$, and $\sim$ are each injective), so $\Phi$ is injective with
image $P \sqcup \sim\!P = \bar P$.

For the truncation identity, $x \ge 0$ is immediate: truncating the base-2 expansion of $x$ to
$d+1$ digits computes $x \bmod 2^{d+1}$. For $x<0$, let $n = -1-x \ge 0$; truncating
$\Phi(x) = \sim\! B(n)$ to $d+1$ bits complements the truncation of $B(n)$, so its value is
$(2^{d+1}-1) - (n \bmod 2^{d+1})$, which is $\equiv -1-n = x \pmod{2^{d+1}}$; being a $(d+1)$-bit
value, it equals $x \bmod 2^{d+1}$ exactly. $\blacksquare$

$\Phi$ is not onto $S$: $S$ has cardinality $2^{\aleph_0}$ — it is, as a set, the 2-adic integers
$\mathbb{Z}_2 = \varprojlim \mathbb{Z}/2^n\mathbb{Z}$ — while $\mathbb{Z}$ is countable, so no
bijection $\mathbb{Z} \to S$ can exist. What the theorem gives instead, $\mathbb{Z}
\hookrightarrow S$ as the eventually-constant sequences, *is* the embedding of $\mathbb{Z}$ into
$\mathbb{Z}_2$, made concrete rather than named.

**Closure.** $\bar P$ is closed under $\sim, \wedge, \vee, \oplus$: if $f$ is eventually $a$ from $N_f$
and $g$ is eventually $b$ from $N_g$, then past $\max(N_f,N_g)$ every one of these operators
returns the single fixed bit $a$-op-$b$, so the result is again eventually constant. Hence
$\Phi(\mathbb{Z}) = \bar P$ is closed under all four — a bitwise operator applied to (patterns
of) integers never leaves $\mathbb{Z}$ — and CPython computes the result in one pass over
the finitely many stored digits on each side; nothing infinite is materialised. The case the
book runs is `bits &= ~bit`, a non-negative number AND a negative one, leading zeros against
leading ones: the tail is zeros and the result is non-negative.

```python
import random

for _ in range(1000):
    x = random.randint(-(2**64), 2**64)
    assert ~x == -x - 1
    assert all((x >> k & 1) == (x // 2**k) % 2 for k in range(70))
```

Bit $k$ of an integer is `x >> k & 1` — one formula for every integer, negative ones included,
because Python's `>>` floors: this is $\Phi$, computed. CPython stores sign and magnitude, so
this is the single place where the image and the storage part company: `-b` prints as
`-0b101101000`, the digits of `b` unchanged, and yet the operators see something else. For
$b = 360$:

```
 k    b>>k  bit     -b>>k  bit
 0     360   0       -360   0
 1     180   0       -180   0
 2      90   0        -90   0
 3      45   1        -45   1
 4      22   0        -23   1
 5      11   1        -12   0
 6       5   1         -6   0
 7       2   0         -3   1
 8       1   1         -2   0
 9       0   0         -1   1
10       0   0         -1   1
11       0   0         -1   1
```

Flooring the halving drives the left column to $0$ and holds it there; it drives the right
column to $-1$ — through $-180, -90, -45, -23, -12, -6, -3, -2$ — and holds it there, and the
bit of $-1$ is $1$. The infinite tail is generated, not declared:

$$b = \dots0000\,101101000, \qquad -b = \dots1111\,010011000.$$

On this $b$ the identity of §3 reads $\sim 360 = -361 = -b - 1$, and §6 writes those bits out.
Read off the table too that $k = 3$ is the only position where both columns show a $1$: §5
proves that in general, and it is what makes `b & -b` equal $2^3$.

## 5. Degree and `bit_length`

**Lemma.** For $b \in \mathbb{N}$, `bit_length`$(b) = \deg(B(b)) + 1$.

*Proof.* For $b>0$, `bit_length` returns one more than the index of the highest set bit, which
is $\deg(B(b))$ by definition. For $b=0$, `bit_length`$(0)=0=\deg(0)+1$ by the convention fixed
in §2. $\blacksquare$

So `bits.bit_length() - 1` — the highest-set-bit half of every `best_price` — literally computes
$\deg(B(\text{bits}))$: the builtin returns a degree, off by the usual one because "degree"
counts from $0$ and "length" from $1$.

**Proposition 4.** For $b \in \mathbb{N}$, $b > 0$, $\deg(b \wedge (-b)) = \nu(b)$, the number of
trailing zero bits of $b$ — equivalently, $b \wedge (-b) = 2^{\nu(b)}$.

*Proof.* Let $n = \nu(b)$, so $B(b)_k = 0$ for $k<n$ and $B(b)_n = 1$. Then $B(b-1)$ agrees with
$B(b)$ above position $n$, is $1$ at every position below $n$, and is $0$ at $n$ — subtracting
$1$ flips exactly the trailing zeros and the lowest one. By the Definition of §4,
$\Phi(-b) = \sim\! B(b-1)$, so bit $k$ of $-b$ is $0$ for $k<n$, $1$ at $n$, and the complement
of bit $k$ of $b$ for $k>n$. ANDing position by position: below $n$, $0 \wedge 0 = 0$; at $n$,
$1 \wedge 1 = 1$; above $n$, $f_k \wedge (1-f_k) = 0$. So $b \wedge (-b)$ has exactly one set
bit, at position $n$, i.e. equals $2^n$. $\blacksquare$

Combined with the Lemma, $\nu(b) = (b \wedge -b).\texttt{bit\_length()} - 1$ — the lowest-set-bit
half of `best_price`. The two branches of the code are now the same statement applied twice:
`bits.bit_length() - 1` is $\deg$ of the pattern directly, `(bits & -bits).bit_length() - 1` is
$\deg$ after isolating the lowest term.

```python
import random

def deg(b):
    return b.bit_length() - 1  # deg(0) := -1

def trailing_zeros(b):
    n = 0
    while b & 1 == 0:
        n += 1
        b >>= 1
    return n

for _ in range(1000):
    b = random.randint(1, 2**200)
    assert deg(b & -b) == trailing_zeros(b)
```

## 6. `b & -b`

By Proposition 4, $b \wedge (-b) = 2^{\nu(b)}$; concretely, for $b = 360$, with the low thirteen
bits of each value written out:

```
b       0000101101000
~b      1111010010111
-b      1111010011000     = ~b + 1
b & -b  0000000001000
```

That is the lowest occupied position, and the highest needs no trick at all: by §5's Lemma,

$$\nu(b) = \operatorname{bitlength}\big(b \wedge -b\big) - 1,
\qquad
\lfloor \log_2 b \rfloor = \operatorname{bitlength}(b) - 1$$

— the best ask and the best bid, one expression each. A third,

$$b \oplus \big(b \wedge (-b)\big),$$

clears the lowest set bit: $x \oplus x = 0$ in the $(\mathbb{Z}/2)^{d+1}$ group of §2, so XORing
against the single bit that $b \wedge -b$ isolates removes exactly that bit and nothing else.
Alternating the two walks the occupied positions from the bottom up in one step per *occupied*
level rather than one per grid position. That is `TickArrayBook.levels_map`.

These are the three questions the hardware answers in one instruction each — `ctz`, `clz` and
`popcnt`, count trailing zeros, count leading zeros, population count — asked of an integer
that has no word width to count zeros against, so the Python forms count from the bottom
instead: `(b & -b).bit_length() - 1`, `b.bit_length() - 1`, `b.bit_count()`. It is a rare case
where the interpreted language states a low-latency trick *more* clearly than C does.

**The empty set is not covered by any of this.** `b = 0` gives `b & -b == 0` and
`(0).bit_length() == 0`, so both formulae return $-1$: a grid position below the origin, hence
a plausible price, returned without an exception. An empty side has to be tested for, never
computed — which is the `if not bits: return None` that opens both `best_price` methods.

## 7. What it costs

The two lookups look alike and are not the same price.

`bit_length` reads the size CPython already stores alongside the digits, so it is $O(1)$.
`b & -b` allocates a result and walks the magnitude one digit at a time, so it is $O(W)$ in the
span $W$ of the set. Over two orders of magnitude of span, on one machine:

| span $W$ (bits) | `b.bit_length()` | `b & -b` |
| --- | --- | --- |
| $10^3$ | 27 ns | 85 ns |
| $10^5$ | 27 ns | 3.0 µs |

```python
import timeit

n = 200_000
for span in (10**3, 10**5):
    b = 1 << span
    high = timeit.timeit(lambda: b.bit_length(), number=n) / n
    low = timeit.timeit(lambda: b & -b, number=n) / n
    print(f"{span:>6}  {high * 1e9:5.1f} ns  {low * 1e9:7.1f} ns")
```

So in the book the best-*bid* lookup is flat in the width of the market and the best-*ask*
lookup is not. The asymmetry belongs to Python's unbounded integers and not to the algorithm:
in C, on one word, both are a single instruction. It is worth knowing which half of a symmetric
pair of formulae is the expensive one, and the source of that asymmetry is the language.

## 8. Where the book uses it

| operation | where |
| --- | --- |
| `1 << k`, `\|= bit`, `&= ~bit` | `BitmapBook.set_volume`, `TickArrayBook.set_volume` |
| `bit_length() - 1` | the $d = +1$ branch of `best_price` in both |
| `(bits & -bits).bit_length() - 1` | the $d = -1$ branch of `best_price` in both |
| `bits ^= bits & -bits` | `TickArrayBook.levels_map` |

All in `unito26.lob.orderbook`. Entry 4 of
[`order-flow-to-order-book.md`](order-flow-to-order-book.md) puts these lookups back in
context, against the four other ways of finding a best price and with the timings of the
ladder as a whole; `notebooks/aggregate-book.ipynb` runs them.

## 9. Sources

Where the standard treatment lives, for a reader who wants more than one page of it.

- Emina Torlak and Sami Davies, **CSE 311, Lecture 12: Modular Arithmetic and Integer
  Representations**, University of Washington,
  <https://courses.cs.washington.edu/courses/cse311/20sp/doc/lecture12.pdf>. Slides 13–17 are
  §3 above in the fixed-width case: unsigned, then sign-magnitude rejected because "adding the
  representation of -18 and 99 doesn't give the representation of 81", then two's complement
  defined as the unsigned representation of $2^n - |x|$, with the key property that it "is
  equivalent to $y \bmod 2^n$, so arithmetic works $\bmod\ 2^n$" and a proof of invert-and-add-one
  from $x + \overline x = 2^n - 1$.
- Henry S. Warren, **Hacker's Delight**, §2-1, *Manipulating Rightmost Bits*. The identities of
  §6 and a page of their relatives, stated for a machine word.
- Donald E. Knuth, **The Art of Computer Programming**, Vol. 4A, §7.1.3, *Bitwise Tricks and
  Techniques*. The full treatment.
- For $S = \{0,1\}^{\mathbb{N}}$ as the 2-adic integers proper — the topology, the metric, the
  arithmetic beyond what §4 needs — Neal Koblitz, **p-adic Numbers, p-adic Analysis, and
  Zeta-Functions**, Ch. I, is the standard short entry point.

One warning attached to the second, since it is the reference a reader is most likely to act
on. Warren gives `x & (x - 1)` for clearing the lowest set bit, and it is the better expression
on a machine word; on a Python integer it is the worse one. In `TickArrayBook.levels_map`,
walking a 900-level book, `bits &= bits - 1` measures 0.41 ms against 0.28 ms for the
`bits ^= bits & -bits` the code uses — the exclusive-or is against a one-bit number, while
subtract-and-AND runs the full width twice. A word-level identity does not automatically
transfer to a bignum, which is §7's lesson arriving from the other direction.
