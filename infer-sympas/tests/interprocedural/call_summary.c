int callee(int x) {
    return x < 0 ? -1 : 0;
}

int caller(int a) {
    int ret = callee(a);
    return ret;
}
