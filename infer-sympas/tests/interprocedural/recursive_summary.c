int recursive_value(int x) {
    if (x <= 0)
        return 0;
    return recursive_value(x - 1) + x;
}
