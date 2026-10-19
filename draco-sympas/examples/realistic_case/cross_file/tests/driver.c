#include <stddef.h>
#include "../storage.h"
int main(void) {
    if (handle_write(NULL) != -3) return 1;
    if (accepted_count() != 0) return 2;
    if (handle_write("valid") != 0) return 3;
    return accepted_count() == 1 ? 0 : 4;
}
