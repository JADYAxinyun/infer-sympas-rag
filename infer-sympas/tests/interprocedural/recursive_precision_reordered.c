int rec_first(int a, int unused, int n);
int rec_left(int a, int b, int n);
int rec_right(int a, int b, int n);

int rec_entry(int value, int unrelated, int n) {
    return rec_left(value, unrelated, n);
}
int rec_right(int a, int b, int n) {
    if (n <= 0) return b;
    return rec_left(b, a, n - 1);
}
int rec_left(int a, int b, int n) {
    if (n <= 0) return a;
    return rec_right(b, a, n - 1);
}
int rec_first(int a, int unused, int n) {
    if (n <= 0) return a;
    return rec_first(a, unused, n - 1);
}
