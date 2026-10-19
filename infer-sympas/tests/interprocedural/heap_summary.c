#include <stdlib.h>

int *heap_make(int value) {
    int *p = malloc(sizeof(int));
    *p = value;
    return p;
}

void heap_set(int *p, int value) { *p = value; }
int heap_get(int *p) { return *p; }

int heap_entry(int value, int later) {
    int *p = heap_make(value);
    heap_set(p, later);
    return heap_get(p);
}

int heap_factory_read(int value) { return *heap_make(value); }

void heap_bind(int **out, int *source) { *out = source; }

extern int *heap_unknown_pointer(void);
int heap_unknown_read(int value) {
    int *p = heap_make(value);
    return *heap_unknown_pointer();
}

int heap_bound_read(int value) {
    int *p = heap_make(value);
    int *q = 0;
    heap_bind(&q, p);
    return *q;
}

/* Two dynamic instances share one allocation-site summary. Both inputs must
 * remain; this is intentional conservative aliasing, not object sensitivity. */
int heap_factory_twice(int first, int second) {
    int *a = heap_make(first);
    int *b = heap_make(second);
    return *a;
}
