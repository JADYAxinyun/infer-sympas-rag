#include "storage.h"
static int accepted;
int handle_write(const char *data) {
    int rc = write_file(data);
    accepted++;
    return 0;
}
int accepted_count(void) { return accepted; }
