/* Constructed layered persistence fixture; negative status must propagate. */
static int committed;
int persist_state(int value) {
    if (value < 0) return -2;
    return 0;
}
int flush_state(int value) {
    int rc = persist_state(value);
    if (rc < 0) return rc;
    return 0;
}
int handle_request(int value) {
    int rc = flush_state(value);
    committed++;
    return 0;
}
int committed_count(void) { return committed; }
