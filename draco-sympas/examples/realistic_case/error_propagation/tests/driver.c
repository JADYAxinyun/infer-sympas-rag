int handle_request(int);
int committed_count(void);
int main(void) {
    if (handle_request(-1) != -2) return 1;
    if (committed_count() != 0) return 2;
    if (handle_request(1) != 0) return 3;
    return committed_count() == 1 ? 0 : 4;
}
