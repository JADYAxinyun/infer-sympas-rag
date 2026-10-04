int shared_value;

int update_global(int x) {
    shared_value = x;
    return shared_value;
}
