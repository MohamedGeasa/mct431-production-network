#include "mct_node.h"
#include "design_parameters.h"
#include "driver/uart.h"
#include "esp_random.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static uint32_t sequence;
static void serial_send(const mct_message_t *message,void *context) {
    (void)context;
    uint8_t payload[MCT_MESSAGE_SIZE],record[MCT_ATR_MAX],wire[2*MCT_ATR_MAX+2];
    mct_pack(message,payload);
    size_t count=mct_atr_pack(payload,sizeof payload,sequence++,record);
    count=mct_slip_encode(record,count,wire);
    uart_write_bytes(UART_NUM_0,wire,count);
}
void app_main(void) {
    /* UART0 uses the board's USB-to-UART bridge: GPIO1 TX, GPIO3 RX.
     * SDK console logging is disabled so no text contaminates SLIP frames. */
    uart_config_t config={.baud_rate=MCT_BAUD_RATE,.data_bits=UART_DATA_8_BITS,
        .parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,.flow_ctrl=UART_HW_FLOWCTRL_DISABLE,
        .source_clk=UART_SCLK_DEFAULT};
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_0,&config));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_0,1,3,UART_PIN_NO_CHANGE,UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0,MCT_UART_BUFFER_SIZE,MCT_UART_BUFFER_SIZE,0,NULL,0));
    mct_node_t node; mct_slip_t decoder={0};
    mct_node_init(&node,1,esp_random(),serial_send,NULL);
    while(true) {
        uint8_t input[128];
        int count=uart_read_bytes(UART_NUM_0,input,sizeof input,pdMS_TO_TICKS(MCT_LOOP_MS));
        for(int i=0;i<count;i++) {
            mct_message_t message;
            if(mct_slip_feed(&decoder,input[i],&message)) mct_node_receive(&node,&message,esp_timer_get_time()/1000);
        }
        if(!mct_node_tick(&node,esp_timer_get_time()/1000)) esp_restart();
    }
}
