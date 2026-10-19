#include <stddef.h>
int run_job(const char *);
int processed_count(void);
int main(void) {
    if (run_job(NULL) >= 0) return 1;
    if (processed_count() != 0) return 2;
    if (run_job("valid") != 0) return 3;
    return processed_count() == 1 ? 0 : 4;
}
