#include "tcp_link.h"
#include "design_parameters.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "lwip/tcp.h"
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

static int client=-1;
static void drop_client(void) {if(client>=0) {shutdown(client,SHUT_RDWR);close(client);client=-1;}}
void tcp_link_send(const mct_message_t *message,void *context) {
    (void)context;if(client<0) return;
    uint8_t wire[MCT_MESSAGE_SIZE+2]={0,MCT_MESSAGE_SIZE};mct_pack(message,wire+2);
    size_t sent=0;int64_t deadline=esp_timer_get_time()/1000+MCT_TCP_SEND_TIMEOUT_MS;
    while(sent<sizeof wire) {
        int count=send(client,wire+sent,sizeof wire-sent,0);
        if(count>0) sent+=(size_t)count;
        else if(count<0 && (errno==EAGAIN || errno==EWOULDBLOCK || errno==EINTR) && esp_timer_get_time()/1000<deadline)
            vTaskDelay(pdMS_TO_TICKS(1));
        else {drop_client();return;}
    }
    ESP_LOGI("MCT431","TX kind=%u cmd=%lu part=%lu result=%lu",message->kind,
             (unsigned long)message->command,(unsigned long)message->part,(unsigned long)message->arg0);
}
void tcp_link_run(mct_node_t *node) {
    int server=socket(AF_INET,SOCK_STREAM,IPPROTO_IP);
    if(server<0) {esp_restart();return;}
    int yes=1;setsockopt(server,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof yes);
    struct sockaddr_in address={.sin_family=AF_INET,.sin_port=htons(MCT_TCP_PORT),.sin_addr.s_addr=htonl(INADDR_ANY)};
    if(bind(server,(struct sockaddr *)&address,sizeof address)<0 || listen(server,1)<0) {close(server);esp_restart();return;}
    fcntl(server,F_SETFL,O_NONBLOCK);
    uint8_t frame[MCT_MESSAGE_SIZE+2];size_t used=0;
    ESP_LOGI("MCT431","Inspection TCP server on port %d",MCT_TCP_PORT);
    while(true) {
        if(client<0) {
            client=accept(server,NULL,NULL);used=0;
            if(client>=0) {fcntl(client,F_SETFL,O_NONBLOCK);setsockopt(client,IPPROTO_TCP,TCP_NODELAY,&yes,sizeof yes);node->next_hello_ms=0;}
        }
        if(client>=0) {
            int count=recv(client,frame+used,sizeof frame-used,0);
            if(count>0) {
                used+=(size_t)count;
                if(used>=2 && (frame[0]!=0 || frame[1]!=MCT_MESSAGE_SIZE)) {drop_client();used=0;}
                else if(used==sizeof frame) {
                    mct_message_t message;
                    if(mct_unpack(frame+2,MCT_MESSAGE_SIZE,&message)) {
                        ESP_LOGI("MCT431","RX cmd=%lu part=%lu",(unsigned long)message.command,(unsigned long)message.part);
                        mct_node_receive(node,&message,esp_timer_get_time()/1000);
                    }
                    used=0;
                }
            } else if(count==0 || (count<0 && errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR)) drop_client();
        }
        if(!mct_node_tick(node,esp_timer_get_time()/1000)) {drop_client();esp_restart();}
        vTaskDelay(pdMS_TO_TICKS(MCT_LOOP_MS));
    }
}
