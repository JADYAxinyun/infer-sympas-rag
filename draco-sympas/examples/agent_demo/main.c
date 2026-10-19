int open_config(const char *path);

int process_config(const char *path) {
    int ret = open_config(path);
    return ret;
}
