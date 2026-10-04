int multi_pointer(int **ptr, int value) {
    **ptr = value;
    return **ptr;
}
