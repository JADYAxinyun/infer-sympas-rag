int ctrl_early(int flag, int value) {
    if (flag < 0) return -1;
    return value;
}

int ctrl_switch(int key, int value) {
    switch (key) {
    case 0: return value;
    case 1: return value + 1;
    default: return -1;
    }
}

int ctrl_helper(int value) { return value; }
int ctrl_conditional_call(int flag, int value) {
    if (flag) return ctrl_helper(value);
    return 0;
}

int ctrl_unrelated(int flag, int value) {
    int ignored = 0;
    if (flag) ignored = flag + 1;
    (void)ignored;
    return value;
}
