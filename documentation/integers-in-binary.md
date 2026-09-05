# Integers in binary, and the lowest-set-bit trick

Prerequisite for entry 4 of [`order-flow-to-order-book.md`](order-flow-to-order-book.md),
where `BitmapBook` and `TickArrayBook` find the best price on a side with three operations on
a single integer. Those operations are standard and they are not obvious; this note derives
them, proves them, measures them, and stops.

**Notation.** Formulas below use the logic symbols on the left; code snippets use Python's own
operators on the right.

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

In C the set is capped at the width of a machine word, and a wide price range means an array of
words with the index arithmetic done by hand. Python's integers are unbounded, so the set is as
wide as the market and needs no declared band — which is why `BitmapBook`, unlike
`TickArrayBook`, has no upper edge to fall off.

## 2. Bit sequences, two ways

Let $S = \{0,1\}^{\mathbb{N}}$, the infinite $0/1$ sequences indexed from $0$. For $f \in S$
write $\pi_d(f)$ for its truncation to positions $0,\dots,d$, and let $\sim, \wedge, \vee,
\oplus$ act pointwise on $S$ — the operators of §1, now acting on the whole sequence rather
than on a fixed-width pattern.

For $d \in \mathbb{N}$ let $R_d := \mathbb{Z}/2^{d+1}\mathbb{Z}$, the remainders of the division
by $2^{d+1}$, and let $\mathrm{mod}_d : \mathbb{Z} \to R_d$ be the reduction map, taking the
least non-negative representative. Notice $\mathbb{F}_2 = R_0$. Let $P_d$ be the tuples
$(f_0,\dots,f_d) \in \mathbb{F}_2^{d+1}$, interpreted as polynomials over $\mathbb{F}_2$ of
degree at most $d$; for $f \ne 0$, $\deg(f)$ is the largest $k$ with $f_k \ne 0$, and
$\deg(0) := -1$ by convention. Coordinatewise XOR makes $P_d$ an abelian group,
$(\mathbb{F}_2^{d+1}, \oplus) \cong (\mathbb{Z}/2)^{d+1}$.

**Proposition 1.** The map $\iota_d : R_d \to P_d$ sending $x \in \{0,\dots,2^{d+1}-1\}$ to its
binary digits is a bijection.

This is standard base-2 digit uniqueness, and it is a bijection of *sets only*: transporting
$R_d$'s addition through $\iota_d$ gives $P_d$ the cyclic group $\mathbb{Z}/2^{d+1}\mathbb{Z}$,
which is not the XOR structure once $d \ge 1$.

Let $P := \bigcup_d P_d \subset S$ be the *eventually-zero* sequences: $f \in P$ iff $f_k = 0$
for all $k > L$, for some $L$, and $\deg(f)$ is the least such $L$. Let
$\bar{B} : P \to \mathbb{N}$, $\bar B(f) = \sum_k f_k 2^k$.

**Proposition 2.** $\bar B$ is a bijection; write $B$ for its inverse, the binary
representation of $\mathbb{N}$.

*Proof.* Injectivity is uniqueness of binary digits. Surjectivity is existence, by strong
induction on $n$: $n = 0$ is $\bar B(0)$; for $n > 0$ write $n = 2q + r$ with $r = n \bmod 2$,
and prepend $r$ to the expansion of $q$. $\blacksquare$

$B$ does not extend $\iota_d$ — $\mathbb{N}$ is not $R_d$, and only one of the two is a group.
What holds instead is that the two commute with truncation.

**Proposition 3.** $\pi_d \circ B = \iota_d \circ \mathrm{mod}_d$ on $\mathbb{N}$.

*Proof.* Write $B(n) = (f_k)_k$ and split the digit sum at $d$:
$n = \sum_{k \le d} f_k 2^k + \sum_{k > d} f_k 2^k$. The second sum is divisible by $2^{d+1}$
and the first lies in $\{0,\dots,2^{d+1}-1\}$, so the first *is* $\mathrm{mod}_d(n)$, and its
digits are $\pi_d(B(n))$. $\blacksquare$

## 3. Two's complement

Let $c_d : R_d \to R_d$, $c_d(x) = -x-1$.

**Proposition 4.** For every $x \in R_d$, $\iota_d(c_d(x)) = \pi_d\big(\sim \iota_d(x)\big)$:
complementing the bit pattern within its own $d+1$-bit window computes $c_d$ — equivalently
$\sim\! x + 1 = -x$, which is all "invert and add one" means.

*Proof.* Write $f = \iota_d(x)$, so $x = \sum_{k=0}^d f_k 2^k$. Flipping every one of the $d+1$
coordinates and reading off the value gives $\sum_k (1-f_k)2^k = (2^{d+1}-1) - x$, which is
exactly $c_d(x) = -x-1 \bmod 2^{d+1}$. $\blacksquare$

```python
for d in range(10):
    m = 2 ** (d + 1)
    for x in range(m):
        assert (-x - 1) % m == (~x) % m == (m - 1) - x
```

## 4. The embedding of $\mathbb{Z}$ into $S$

Write $\sim\!P$ for the eventually-*one* sequences, the complements of the elements of $P$, and
$\bar P := P \cup \sim\!P$ for the eventually-constant ones.

**Definition.** $\Phi : \mathbb{Z} \to S$, $\Phi(x) = B(x)$ if $x \ge 0$, and
$\Phi(x) = \sim\! B(-1-x)$ if $x < 0$. (Note $\sim\! B(-x) = \Phi(x-1)$, not $\Phi(x)$.)

**Theorem.** $\Phi$ is injective with image $\bar P$, and extends Proposition 3 from
$\mathbb{N}$ to $\mathbb{Z}$: for every $d$,

$$\pi_d(\Phi(x)) = \iota_d(\mathrm{mod}_d(x)).$$

*Proof.* For $x \ge 0$, $\Phi(x) = B(x) \in P$; for $x < 0$, $-1-x \ge 0$, so $B(-1-x)$ is
eventually zero and $\Phi(x)$ eventually one. No sequence is both, so the two cases have
disjoint images; each is injective, and together they give $P \sqcup \sim\!P = \bar P$.

The identity is Proposition 3 for $x \ge 0$. For $x < 0$ put $n = -1-x$; truncating
$\sim\! B(n)$ complements the truncation of $B(n)$, giving
$(2^{d+1}-1) - (n \bmod 2^{d+1}) \equiv -1-n = x \pmod{2^{d+1}}$, and a $(d+1)$-bit value
congruent to $x$ is $\mathrm{mod}_d(x)$. $\blacksquare$

$\Phi$ is not onto: the alternating sequence $0,1,0,1,\dots$ is not eventually constant.

**Closure.** $\bar P$ is closed under $\sim, \wedge, \vee, \oplus$, since past the point where
both arguments have gone constant each of them returns a fixed bit. So a bitwise operator
applied to integers never leaves $\mathbb{Z}$, and CPython computes it in one pass over the
stored digits — nothing infinite is materialised. The case the book runs, `bits &= ~bit`, ANDs
leading zeros against leading ones, so the tail is zeros and the result is non-negative.

```python
import random

for _ in range(1000):
    x = random.randint(-(2**64), 2**64)
    assert ~x == -x - 1
    assert all((x >> k & 1) == (x // 2**k) % 2 for k in range(70))
```

Bit $k$ of an integer is `x >> k & 1`, for negative $x$ too, because Python's `>>` floors: this
is $\Phi$, computed, and it is where the represented value parts company with CPython's
sign-and-magnitude storage. For $b = 360$:

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

Both columns reach a fixed point — $0$ on the left, $-1$ on the right, whose every bit is $1$ —
so the infinite tail is generated, not declared:

$$b = \dots0000\,101101000, \qquad -b = \dots1111\,010011000.$$

Position $k = 3$ is the only one where both columns show a $1$. §5 proves that in general, and
it is what makes `b & -b` equal $2^3$.

## 5. Degree and `bit_length`

**Lemma.** For $b \in \mathbb{N}$, `bit_length`$(b) = \deg(B(b)) + 1$.

*Proof.* For $b > 0$, `bit_length` returns one more than the index of the highest set bit, which
is $\deg(B(b))$ by definition. For $b = 0$, `bit_length`$(0) = 0 = \deg(0) + 1$ by the
convention of §2. $\blacksquare$

So `bits.bit_length() - 1` computes $\deg(B(\text{bits}))$: the builtin returns a degree.

**Proposition 5.** For $b \in \mathbb{N}$, $b > 0$, $\deg(b \wedge (-b)) = \nu(b)$, the number of
trailing zero bits of $b$ — equivalently, $b \wedge (-b) = 2^{\nu(b)}$.

*Proof.* Let $n = \nu(b)$, so $B(b)_k = 0$ for $k<n$ and $B(b)_n = 1$. Then $B(b-1)$ agrees with
$B(b)$ above position $n$, is $1$ at every position below $n$, and is $0$ at $n$ — subtracting
$1$ flips exactly the trailing zeros and the lowest one. By the Definition of §4,
$\Phi(-b) = \sim\! B(b-1)$, so bit $k$ of $-b$ is $0$ for $k<n$, $1$ at $n$, and the complement
of bit $k$ of $b$ for $k>n$. ANDing position by position: below $n$, $0 \wedge 0 = 0$; at $n$,
$1 \wedge 1 = 1$; above $n$, $f_k \wedge (1-f_k) = 0$. So $b \wedge (-b)$ has exactly one set
bit, at position $n$. $\blacksquare$

Combined with the Lemma, $\nu(b) = (b \wedge -b).\texttt{bit\_length()} - 1$: the two branches of
`best_price` are the same operation, `bit_length() - 1`, applied once directly and once after
$b \wedge (-b)$ isolates the lowest term. And $b \oplus (b \wedge (-b))$ clears that term, since
$x \oplus x = 0$ — which is how `levels_map` walks the occupied levels one step each.

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

For $b = 360$, with the low thirteen bits of each value written out:

```
b       0000101101000
~b      1111010010111
-b      1111010011000     = ~b + 1
b & -b  0000000001000
```

`b = 0` is not covered: `b & -b == 0` and `(0).bit_length() == 0`, so both formulae return $-1$,
a grid position below the origin and hence a plausible price, returned without an exception. An
empty side has to be tested for, which is the `if not bits: return None` opening both
`best_price` methods.

## 6. What it costs

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
in C, on one word, both are a single instruction.

## 7. Where the book uses it

| operation | where |
| --- | --- |
| `1 << k`, `\|= bit`, `&= ~bit` | `BitmapBook.set_size`, `TickArrayBook.set_size` |
| `bit_length() - 1` | `best_price` on both sides in `TickArrayBook`, the $d = +1$ branch in `BitmapBook` |
| `(bits & -bits).bit_length() - 1` | the $d = -1$ branch of `BitmapBook.best_price` |
| `bits ^= 1 << k` | walking the occupied levels in both |

The asymmetry of section 6 is the reason `TickArrayBook` no longer appears in the third row.
Since it declares a band it has a *ceiling*, so it indexes its sell side downward from it --
bit $\mathrm{ceiling} - p$ rather than $p - \mathrm{origin}$ -- and the best price is the
highest set bit on either side. `BitmapBook` cannot: it has no upper edge, which is the whole
distinction between the two rungs, and the cost of that freedom is the scan.

**What the book stopped using.** `count_binary_gaps` and `measure_largest_binary_gap` no
longer answer `side_statistics`. Two consecutive occupied prices bound exactly one maximal
run of empty positions, of length $|p_{i+1} - p_i| - 1$, so the gaps fall out of the walk
that produced the levels, and doing that costs less than masking a window out of the
occupancy integer -- measured at about 1.4 times on the deep book. The derivations above
stand, `unito26.lob.binary_gaps` keeps its tests, and the individual `gap_count` and
`largest_gap_size_between_non_empty_levels` still go through them. What changed is which one
is on the hot path.
`notebooks/why-the-tick-array-book-is-not-faster.ipynb` has the measurement.

All in `unito26.lob.orderbook`. Entry 4 of
[`order-flow-to-order-book.md`](order-flow-to-order-book.md) puts these lookups back in
context, against the four other ways of finding a best price and with the timings of the
ladder as a whole; `notebooks/aggregate-book.ipynb` runs them.
