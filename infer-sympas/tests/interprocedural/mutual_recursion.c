int odd(int x);

int even(int x) {
    if (x == 0) return 0;
    return odd(x - 1);
}

int odd(int x) {
    if (x == 0) return 1;
    return even(x - 1);
}

int entry(int value) {
    return even(value);
}
