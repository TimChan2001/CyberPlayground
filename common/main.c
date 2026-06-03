#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
int LLVMFuzzerTestOneInput(const uint8_t*, size_t);
int main(int argc, char **argv){
  if(argc<2){fprintf(stderr,"usage: %s poc\n",argv[0]);return 2;}
  FILE *f=fopen(argv[1],"rb"); if(!f){perror(argv[1]);return 2;}
  fseek(f,0,SEEK_END); long n=ftell(f); fseek(f,0,SEEK_SET);
  uint8_t *buf=(uint8_t*)malloc(n>0?n:1);
  if(n>0) fread(buf,1,n,f); fclose(f);
  int r=LLVMFuzzerTestOneInput(buf,(size_t)n);
  free(buf);
  return r;
}
