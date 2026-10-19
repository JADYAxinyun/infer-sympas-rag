int point_value(int value, int unrelated) {
    int selected = value;
    int ignored = unrelated;
    int observed = selected + 1;
    selected = unrelated;
    return observed;
}

int point_control(int flag, int value) {
    int selected = value;
    if (flag) {
        return selected;
    }
    return 0;
}
