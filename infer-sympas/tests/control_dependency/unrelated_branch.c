int unrelated_branch(int x, int flag) {
    int result = x + 1;
    if (flag)
        result = 99;
    return result;
}
