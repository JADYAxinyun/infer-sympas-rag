int shared_value;

int read_global(void) {
    return shared_value;
}

int call_global(void) {
    return read_global();
}
