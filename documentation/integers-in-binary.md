# Integers in binary, and the lowest-set-bit trick

Prerequisite for entry 4 of [`order-flow-to-order-book.md`](order-flow-to-order-book.md),
where `BitmapBook` and `TickArrayBook` find the best price on a side with three operations on
a single integer. Those operations are standard and they are not obvious; this note derives
them, measures them, and stops.

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

## 2. Negative numbers, and why two's complement is forced

### A counting argument

Fix a width $n$. There are $2^n$ patterns, so a signed reading is a map
$\{0,1\}^n \to \mathbb{Z}$, and the first question to ask of one is whether it is injective.
Enumerating all 256 patterns at $n = 8$ under the three classical readings:

| reading | distinct values | range | one-to-one |
| --- | --- | --- | --- |
| two's complement | 256 | $[-128, 127]$ | yes |
| ones' complement | 255 | $[-127, 127]$ | no |
| sign-magnitude | 255 | $[-127, 127]$ | no |

The two losers are symmetric about zero, which sounds like a virtue and is precisely the
defect: a symmetric range of integers has odd cardinality, $2^n$ is even, so one pattern is
left over and both schemes spend it on a second zero.

Two's complement is not merely the survivor, and the reason is worth stating on its own. Binary
addition with the carry off the top discarded **is** addition in $\mathbb{Z}/2^n\mathbb{Z}$ —
that is what the adder computes, before anyone has decided what a pattern means. A signed
reading is therefore a choice of *representatives* for the residue classes, and any complete
set of representatives is a bijection automatically. Two's complement takes
$\{-2^{n-1}, \dots, 2^{n-1}-1\}$, one per class; the other two readings take sets that are not
complete residue systems, which is the paragraph above counted a second way. The practical
form of the same fact: one adder serves the signed and the unsigned reading at once, and only
this scheme has that property.

Two consequences, both used below.

- $-m$ is not a minus sign attached to $m$. It is the additive inverse **in the ring**, namely
  $2^n - m$ — so "invert and add one" is a theorem and not a recipe: writing $\overline m$ for
  the complement of the low $n$ bits, $m + \overline m = 2^n - 1$ by construction, hence
  $\overline m + 1 = 2^n - m$.
- Being exact leaves a fingerprint: $-2^{n-1}$ has no positive counterpart, which is why
  `abs()` overflows at `INT_MIN` in C. One-to-one and symmetric cannot both hold.

### Removing the width

Now the property Python needs, and the one the losing schemes lack. Truncating an $n$-bit
two's-complement number to its low $m$ bits gives the $m$-bit two's complement of the same
value, both being the reduction mod $2^m$ of one residue class. For $-360$:

```
low  5 bits                            11000
low  9 bits                        010011000
low 13 bits                    1111010011000
low 20 bits             11111111111010011000
```

each the suffix of the next. Sign-magnitude cannot do this, its sign bit sitting at the top:
$-3$ in eight bits is `10000011`, whose low four bits read `0011`, which is $+3$.

Because the widths agree with one another they have a limit, and $n$ leaves the statement
altogether:

$$\mathbb{Z} \;\longleftrightarrow\; \{\text{eventually-constant bit sequences}\},$$

eventually-zero for $x \ge 0$ and eventually-one for $x < 0$. Injectivity is one line: if
$x \equiv y \pmod{2^n}$ for every $n$, then $2^n$ divides $x - y$ for every $n$, so $x = y$.
Surjectivity onto the eventually-constant sequences is two cases: an eventually-zero sequence
is the finite sum $\sum_k b_k 2^k$, and one whose ones begin at $N$ is
$\sum_{k<N} b_k 2^k - 2^N$. In particular $-1 = \dots1111$ is a computation rather than a
convention, $2^n - 1$ being $n$ ones for every $n$. For the reader who wants the general
theory, this is the embedding of $\mathbb{Z}$ into the 2-adic integers
$\varprojlim \mathbb{Z}/2^n\mathbb{Z}$.

### The image, computed

Bit $k$ of an integer is `x >> k & 1` — one formula for every integer, negative ones included,
because Python's `>>` floors. CPython stores sign and magnitude, so this is the single place
where the image and the storage part company: `-b` prints as `-0b101101000`, the digits of `b`
unchanged, and yet the operators see something else. For $b = 360$:

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

On this $b$ the identity of the previous subsection reads $\sim 360 = -361 = -b - 1$, and §3
writes those bits out. Read off the table too that $k = 3$ is the only position where both
columns show a $1$: that is what §3 proves in general, and it is what makes `b & -b` equal
$2^3$.

### Closure

Bitwise operators act positionally, and a positional operation on two eventually-constant
sequences is eventually constant, so the result lands back in $\mathbb{Z}$ every time and
CPython computes it in one pass over the stored digits — nothing infinite is materialised. The
case the book runs is `bits &= ~bit`, a non-negative number AND a negative one, leading zeros
against leading ones: the tail is zeros and the result is non-negative. Clearing a level on an
unbounded integer needs no mask and no declared width.

```python
import random

for _ in range(1000):
    x = random.randint(-(2**64), 2**64)
    assert ~x == -x - 1
    assert all((x >> k & 1) == (x // 2**k) % 2 for k in range(70))
```

## 3. `b & -b`

The same $b = 360$, with the low thirteen bits of each value written out:

```
b       0000101101000
~b      1111010010111
-b      1111010011000     = ~b + 1
b & -b  0000000001000
```

The middle step is the whole argument. Complementing $b$ turns its trailing zeros into trailing
ones; adding $1$ then carries through exactly those ones, resetting them to zero, and the carry
stops at the lowest set bit of $b$, which is left set. Above that position nothing else
absorbed the carry, so every bit of $-b$ is the complement of the corresponding bit of $b$.

Hence $b$ and $-b$ agree in **exactly one** position, and

$$b \wedge (-b) = 2^{\nu(b)},$$

where $\nu(b)$ is the number of trailing zeros of $b$. That is the lowest occupied position,
and the highest needs no trick at all:

$$\nu(b) = \operatorname{bitlength}\big(b \wedge (-b)\big) - 1,
\qquad
\lfloor \log_2 b \rfloor = \operatorname{bitlength}(b) - 1$$

— the best ask and the best bid, one expression each. A third,

$$b \veebar \big(b \wedge (-b)\big),$$

clears the lowest set bit, so alternating the two walks the occupied positions from the bottom
up in one step per *occupied* level rather than one per grid position. That is
`TickArrayBook.levels_map`.

These are the three questions the hardware answers in one instruction each — `ctz`, `clz` and
`popcnt`, count trailing zeros, count leading zeros, population count — asked of an integer
that has no word width to count zeros against, so the Python forms count from the bottom
instead: `(b & -b).bit_length() - 1`, `b.bit_length() - 1`, `b.bit_count()`. It is a rare case
where the interpreted language states a low-latency trick *more* clearly than C does.

**The empty set is not covered by any of this.** `b = 0` gives `b & -b == 0` and
`(0).bit_length() == 0`, so both formulae return $-1$: a grid position below the origin, hence
a plausible price, returned without an exception. An empty side has to be tested for, never
computed — which is the `if not bits: return None` that opens both `best_price` methods.

## 4. What it costs

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

## 5. Where the book uses it

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

## 6. Sources

Where the standard treatment lives, for a reader who wants more than one page of it.

- Emina Torlak and Sami Davies, **CSE 311, Lecture 12: Modular Arithmetic and Integer
  Representations**, University of Washington,
  <https://courses.cs.washington.edu/courses/cse311/20sp/doc/lecture12.pdf>. Slides 13–17 are
  §2 above in the fixed-width case: unsigned, then sign-magnitude rejected because "adding the
  representation of -18 and 99 doesn't give the representation of 81", then two's complement
  defined as the unsigned representation of $2^n - |x|$, with the key property that it "is
  equivalent to $y \bmod 2^n$, so arithmetic works $\bmod\ 2^n$" and a proof of invert-and-add-one
  from $x + \overline x = 2^n - 1$.
- Henry S. Warren, **Hacker's Delight**, §2-1, *Manipulating Rightmost Bits*. The identities of
  §3 and a page of their relatives, stated for a machine word.
- Donald E. Knuth, **The Art of Computer Programming**, Vol. 4A, §7.1.3, *Bitwise Tricks and
  Techniques*. The full treatment.

One warning attached to the second, since it is the reference a reader is most likely to act
on. Warren gives `x & (x - 1)` for clearing the lowest set bit, and it is the better expression
on a machine word; on a Python integer it is the worse one. In `TickArrayBook.levels_map`,
walking a 900-level book, `bits &= bits - 1` measures 0.41 ms against 0.28 ms for the
`bits ^= bits & -bits` the code uses — the exclusive-or is against a one-bit number, while
subtract-and-AND runs the full width twice. A word-level identity does not automatically
transfer to a bignum, which is §4's lesson arriving from the other direction.
