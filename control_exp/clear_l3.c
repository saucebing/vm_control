#include<stdio.h>
#include<stdlib.h>
#include<memory.h>
#define SIZE 72000000
int main() {
    char *a = malloc(SIZE);
    char *b = malloc(SIZE);
    int i = 0;
    for(i = 0 ; i < SIZE ; i ++) {
        a[i] = rand() % 128;
    }
    for(i = 0 ; i < 1 ; i ++) {
        memcpy(b, a, SIZE);
    }
    return 0;
}
