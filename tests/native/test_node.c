#include "mct_node.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static mct_message_t last_response;
static unsigned int completion_count;
static void capture(const mct_message_t *message, void *context) {
    (void)context;last_response=*message;
    if(message->kind==MCT_COMPLETED) completion_count++;
}
int main(void) {
    assert(mct_crc((const uint8_t *)"123456789",9)==0x29b1);
    mct_message_t vector={.kind=MCT_COMMAND,.op=MCT_INSPECT,.station=2,.session=0x0102030405060708ULL,
        .command=7,.part=8,.arg0=9,.arg1=10,.arg2=11,.boot=0x12345678};
    uint8_t packed[36];mct_pack(&vector,packed);
    const uint8_t expected[]={1,1,4,2,1,2,3,4,5,6,7,8,0,0,0,7,0,0,0,8,0,0,0,9,0,0,0,10,0,0,0,11,0x12,0x34,0x56,0x78};
    assert(memcmp(packed,expected,sizeof expected)==0);
    uint8_t record[138],wire[278];size_t len=mct_atr_pack(packed,sizeof packed,0,record);
    size_t wirelen=mct_slip_encode(record,len,wire);mct_slip_t decoder={0};mct_message_t decoded;
    unsigned int frames=0;
    for(size_t i=0;i<wirelen;i++) if(mct_slip_feed(&decoder,wire[i],&decoded)) frames++;
    assert(frames==1 && mct_equal(&decoded,&vector));
    record[10]^=1;assert(!mct_atr_unpack(record,len,&decoded));

    mct_node_t node;mct_node_init(&node,2,42,capture,NULL);
    mct_message_t cmd={.kind=MCT_COMMAND,.op=MCT_BIND,.station=2,.session=123,.command=1,.boot=42};
    mct_node_receive(&node,&cmd,0);assert(last_response.kind==MCT_COMPLETED);
    cmd.command=2;cmd.op=MCT_CONFIG;cmd.arg0=100;cmd.arg1=3;cmd.arg2=1;
    mct_node_receive(&node,&cmd,1);assert(node.configured && last_response.kind==MCT_COMPLETED);
    cmd.command=3;cmd.op=MCT_INSPECT;cmd.part=2;cmd.arg0=cmd.arg1=cmd.arg2=0;
    mct_node_receive(&node,&cmd,2);assert(node.busy && last_response.kind==MCT_ACCEPTED);
    int64_t deadline=node.deadline_ms;
    mct_node_receive(&node,&cmd,50);assert(node.deadline_ms==deadline);
    node.next_hello_ms=1000;mct_node_tick(&node,102);
    assert(last_response.kind==MCT_COMPLETED && last_response.arg0==MCT_FAIL);
    unsigned int before=completion_count;
    mct_node_receive(&node,&cmd,110);assert(!node.busy && completion_count==before+1);
    cmd.part=3;mct_node_receive(&node,&cmd,120);assert(last_response.kind==MCT_REJECTED);
    cmd.command=2;mct_node_receive(&node,&cmd,120);assert(last_response.kind==MCT_REJECTED);
    cmd.command=4;cmd.boot=99;mct_node_receive(&node,&cmd,120);assert(last_response.kind==MCT_REJECTED);
    cmd.boot=42;cmd.op=MCT_CONFIG;cmd.arg0=1;cmd.arg1=0;
    mct_node_receive(&node,&cmd,120);assert(last_response.kind==MCT_REJECTED);
    assert(!mct_node_tick(&node,7000));
    puts("Native protocol and station state-machine tests passed");
    return 0;
}
