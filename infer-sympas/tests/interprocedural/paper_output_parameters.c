/* Adapted from SymPas Fig.4 (JCST 2021, p.403).
 * Bounded wrapper avoids the example's I/O and selects the final sum.
 * Expected: paper_entry return depends on formal[0] and formal[1].
 * A returned-value-only call summary cannot model these void calls.
 */
static void paper_add(int *a, int *b) {
    *a = *a + *b;
}

static void paper_inc(int *z) {
    int one = 1;
    paper_add(z, &one);
}

static void paper_A(int *x, int *y) {
    paper_add(x, y);
    paper_inc(y);
}

int paper_entry(int initial_sum, int initial_i) {
    int sum = initial_sum;
    int i = initial_i;
    paper_A(&sum, &i);
    return sum;
}
