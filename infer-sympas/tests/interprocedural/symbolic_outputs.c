/* Rule-based symbolic summary regression; no paper benchmark claims. */
int sym_first(int a, int b) { (void)b; return a; }
int sym_swap(int a, int b) { return sym_first(b, a); }
int sym_nested(int a, int b) { return sym_first(sym_first(a, b), b); }
int sym_two_calls(int a, int b) {
    int first = sym_first(a, b);
    int unused = sym_first(b, a);
    (void)unused;
    return first;
}
int sym_expression(int a, int b) { return sym_swap(a, b) + a; }
int sym_leaf(int x) { return x + 1; }
int sym_middle(int x) { return sym_leaf(x); }
int sym_top(int a, int b) { (void)b; return sym_middle(a); }

void sym_set(int *out, int value) { *out = value; }
int sym_pointer(int initial, int value) {
    int result = initial;
    sym_set(&result, value);
    return result;
}
int sym_alias(int value) {
    int result = 0;
    int *p = &result;
    int *q = p;
    *q = value;
    return *p;
}
int sym_alias_writes(int a, int b) {
    int result = 0;
    int *p = &result;
    int *q = p;
    *p = a;
    *q = b;
    return result;
}
int sym_may_alias(int flag, int a, int b) {
    int x = a, y = b;
    int *p;
    if (flag) p = &x; else p = &y;
    return *p;
}

int sym_global;
void sym_write_global(int value) { sym_global = value; }
int sym_global_entry(int value) { sym_write_global(value); return sym_global; }
int sym_read_global(void) { return sym_global; }

struct sym_box { int value; int other; };
int sym_field(int value) { struct sym_box b; b.value = value; return b.value; }
int sym_array(int value) { int a[2]; a[0] = value; return a[0]; }
int sym_loop(int value, int n) { int x = value; while (n-- > 0) x++; return x; }
int sym_returns(int flag, int a, int b) { if (flag) return a; return b; }
int sym_recursive(int value, int n) {
    if (n <= 0) return value;
    return sym_recursive(value, n - 1);
}
int sym_odd(int value, int n);
int sym_even(int value, int n) {
    if (n <= 0) return value;
    return sym_odd(value, n - 1);
}
int sym_odd(int value, int n) {
    if (n <= 0) return value;
    return sym_even(value, n - 1);
}
extern int sym_external(int value);
int sym_unknown(int value) { return sym_external(value); }
int sym_unchecked(int value) { sym_external(value); return value; }
int sym_indirect(int value, int (*fn)(int)) { return fn(value); }
int sym_unrelated_flag(int flag, int value) {
    int unrelated = 0;
    if (flag) unrelated = flag + 1;
    (void)unrelated;
    return value;
}
int *sym_identity_pointer(int *p) { return p; }
int sym_pointer_return(int value) {
    int x = 0;
    int *p = sym_identity_pointer(&x);
    *p = value;
    return x;
}
struct sym_box *sym_box_pointer(struct sym_box *p) { return p; }
int sym_struct_pointer_return(int value) {
    struct sym_box box;
    struct sym_box *p = sym_box_pointer(&box);
    p->value = value;
    return box.value;
}
int sym_aggregate_merge(int a, int b) {
    struct sym_box box;
    box.value = a;
    box.other = b;
    return box.value;
}
int sym_formal_alias(int *p, int *q, int value) {
    *p = value;
    return *q;
}
extern int *sym_unknown_pointer(int *p);
int sym_unresolved_pointer(int value) {
    int x = 0;
    int *p = sym_unknown_pointer(&x);
    *p = value;
    return x;
}
int sym_array_pointer_alias(int value) {
    int array[2] = {0, 0};
    int *p = array;
    p[0] = value;
    return array[0];
}
