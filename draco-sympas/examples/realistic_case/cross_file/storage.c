#include "storage.h"
/* Documented fixture policy: negative values indicate write errors. */
int write_file(const char *data) {
    if (!data) return -3;
    return 0;
}
