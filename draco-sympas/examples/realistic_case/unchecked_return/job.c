/* Constructed configuration-job fixture, not a production defect. */
static int processed;
int load_config(const char *path) {
    if (!path) return -1;
    return 0;
}
int run_job(const char *path) {
    int rc = load_config(path);
    processed++;
    return 0;
}
int processed_count(void) { return processed; }
