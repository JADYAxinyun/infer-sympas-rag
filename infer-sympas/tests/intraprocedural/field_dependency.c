struct Box {
    int value;
};

int read_box(struct Box *box, int x) {
    box->value = x;
    return box->value;
}
