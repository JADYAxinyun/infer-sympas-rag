#include <stddef.h>

extern int open_config(const char *path);
extern void continue_running(void);

int process_config(const char *path) {
    int ret = open_config(path);
    continue_running();
    return ret;
}
