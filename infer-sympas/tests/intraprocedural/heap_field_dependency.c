#include <stdlib.h>

struct Item {
    int value;
};

int heap_value(int x) {
    struct Item *item = malloc(sizeof(struct Item));
    item->value = x;
    int result = item->value;
    free(item);
    return result;
}
