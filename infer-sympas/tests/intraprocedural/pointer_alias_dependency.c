int pointer_alias(int *ptr, int value) {
    int *alias = ptr;
    *alias = value;
    return *ptr;
}
