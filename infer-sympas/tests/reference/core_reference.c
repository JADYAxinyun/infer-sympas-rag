#include <stdlib.h>

int ref_assign(int x, int noise) {
    int a = x + 1;                      /*S:A_ASSIGN*/
    int ignored = noise * 2;             /*S:A_IGNORED*/
    return a;                           /*S:A_RETURN*/
}

int ref_overwrite(int x, int y) {
    int a = x;                          /*S:O_FIRST*/
    a = y;                              /*S:O_LAST*/
    return a;                           /*S:O_RETURN*/
}

int ref_branch(int flag, int x) {
    int a = 0;                          /*S:B_INITIAL*/
    if (flag) {                         /*S:B_CONDITION*/
        a = x;                          /*S:B_WRITE*/
    }
    return a;                           /*S:B_RETURN*/
}

int ref_identity(int x) {
    return x;                           /*S:I_RETURN*/
}
int ref_calls(int x, int unrelated) {
    int a = ref_identity(x);             /*S:C_RELEVANT*/
    int b = ref_identity(unrelated);     /*S:C_UNRELATED*/
    return a;                           /*S:C_RETURN*/
}

int ref_loop(int x, int n) {
    int a = x;                          /*S:L_INITIAL*/
    while (n-- > 0) {                   /*S:L_CONDITION*/
        a++;                            /*S:L_UPDATE*/
    }
    return a;                           /*S:L_RETURN*/
}

int ref_local_pointer(int x) {
    int a = 0;                          /*S:P_INITIAL*/
    int *p = &a;                        /*S:P_ALIAS*/
    *p = x;                             /*S:P_WRITE*/
    return a;                           /*S:P_RETURN*/
}

int ref_array(int x) {
    int a[2] = {0, 0};                  /*S:R_INITIAL*/
    a[0] = x;                           /*S:R_WRITE*/
    return a[0];                        /*S:R_RETURN*/
}

int ref_heap(int x) {
    int *p = malloc(sizeof(int));        /*S:H_ALLOC*/
    *p = x;                             /*S:H_WRITE*/
    return *p;                          /*S:H_RETURN*/
}

int ref_two_heaps(int x, int unrelated) {
    int *p = malloc(sizeof(int));        /*S:T_ALLOC_P*/
    int *q = malloc(sizeof(int));        /*S:T_ALLOC_Q*/
    *p = x;                             /*S:T_WRITE_P*/
    *q = unrelated;                     /*S:T_WRITE_Q*/
    return *p;                          /*S:T_RETURN*/
}

/* Heap lifetime is deliberately outside the slicing criterion. These functions
 * are analyzed statically, never executed; they are not memory-safety examples.
 */
