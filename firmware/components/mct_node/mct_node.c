#include "mct_node.h"
#include "design_parameters.h"
#include <string.h>

static void reply(mct_node_t *n,const mct_message_t *m,uint8_t kind,uint32_t result) {
    mct_message_t r=*m;r.kind=kind;
    if(kind==MCT_COMPLETED || kind==MCT_REJECTED) r.arg0=result;
    n->send(&r,n->context);
}
static void complete(mct_node_t *n,uint32_t result) {
    n->result=n->last;n->result.kind=MCT_COMPLETED;n->result.arg0=result;
    n->busy=false;n->has_result=true;n->send(&n->result,n->context);
}
void mct_node_init(mct_node_t *n,uint8_t station,uint32_t boot,mct_send_fn send,void *context) {
    memset(n,0,sizeof *n);n->station=station;n->boot=boot?boot:1;n->send=send;n->context=context;
}
void mct_node_receive(mct_node_t *n,const mct_message_t *m,int64_t now) {
    if(m->kind==MCT_PING) {
        if(n->session && m->session==n->session && m->boot==n->boot && m->station==n->station)
            n->last_gateway_ms=now;
        return;
    }
    if(m->kind!=MCT_COMMAND) return;
    reply(n,m,MCT_DELIVERED,0);
    bool can_bind=!n->session && m->op==MCT_BIND;
    if(!m->session || !m->command || m->boot!=n->boot || m->station!=n->station ||
       (!can_bind && m->session!=n->session)) {reply(n,m,MCT_REJECTED,MCT_BAD_BINDING);return;}
    n->last_gateway_ms=now;
    if(n->has_last && m->command<=n->last.command) {
        if(mct_equal(m,&n->last)) {
            reply(n,m,MCT_ACCEPTED,0);
            if(n->has_result) n->send(&n->result,n->context);
        } else reply(n,m,MCT_REJECTED,MCT_OLD_ID);
        return;
    }
    if(n->busy) {reply(n,m,MCT_REJECTED,MCT_BUSY);return;}
    bool valid=false;
    if(m->op==MCT_BIND) valid=true;
    else if(m->op==MCT_CONFIG)
        valid=m->arg0>=MCT_MIN_DURATION_MS && m->arg0<=MCT_MAX_DURATION_MS &&
              (n->station==1 || (m->arg1>=1 && m->arg1<=MCT_MAX_RULE_PARAMETER && m->arg2<=MCT_MAX_RULE_PARAMETER));
    else valid=n->configured && m->part>0 && m->op==(n->station==1?MCT_PRODUCE:MCT_INSPECT);
    if(!valid) {reply(n,m,MCT_REJECTED,MCT_BAD_COMMAND);return;}
    n->session=m->session;n->last=*m;n->has_last=true;n->has_result=false;
    reply(n,m,MCT_ACCEPTED,0);
    if(m->op==MCT_BIND) complete(n,MCT_OK);
    else if(m->op==MCT_CONFIG) {
        n->duration_ms=m->arg0;n->modulus=m->arg1;n->offset=m->arg2;n->configured=true;
        complete(n,MCT_OK);
    } else {
        n->busy=true;n->deadline_ms=now+n->duration_ms;
    }
}
bool mct_node_tick(mct_node_t *n,int64_t now) {
    if(n->session && now-n->last_gateway_ms>MCT_GATEWAY_WATCHDOG_MS) return false;
    if(n->busy && now>=n->deadline_ms) {
        uint32_t verdict=MCT_OK;
        if(n->station==2) verdict=(((uint64_t)n->last.part+n->offset)%n->modulus)==0?MCT_FAIL:MCT_PASS;
        complete(n,verdict);
    }
    if(now>=n->next_hello_ms) {
        mct_message_t hello={.kind=MCT_HELLO,.station=n->station,.session=n->session,
            .boot=n->boot,.arg0=n->busy,.arg1=n->has_last?n->last.command:0};
        n->send(&hello,n->context);n->next_hello_ms=now+MCT_HEARTBEAT_MS;
    }
    return true;
}
