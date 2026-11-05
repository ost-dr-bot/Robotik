/**
 * @file control_system.c
 * @brief Control system implementation.
 * @author Jonas Frei
 * @date 01.09.2026
 * @version 1.0
 */

#include "control_system.h"
#include "safety_system.h"
#include "udp_interface.h"
#include <freertos/FreeRTOS.h>
#include <freertos/event_groups.h>
#include <esp_log.h>
#include <math.h>

static const char *TAG = "Control System"; /**< Tag for logging purposes */

static control_system_config_t cfg = {0}; /**< Configuration for the control system */

static EventGroupHandle_t control_system_event_group = NULL; /**< Event group for control system events */
#define CONTROL_SYSTEM_INITIALIZED_BIT BIT0                  /**< Bit indicating control system is initialized in the event group */

esp_err_t control_system_init(const control_system_config_t *config)
{
    ESP_LOGI(TAG, "Initializing control system...");

    // Create control system event group if it doesn't exist
    if (control_system_event_group == NULL)
    {
        control_system_event_group = xEventGroupCreate();
        if (control_system_event_group == NULL)
        {
            ESP_LOGE(TAG, "Failed to create control system event group");
            return ESP_FAIL;
        }
    }
    else if (xEventGroupGetBits(control_system_event_group) & CONTROL_SYSTEM_INITIALIZED_BIT)
    {
        ESP_LOGW(TAG, "Control system already initialized.");
        return ESP_OK;
    }

    // Store the configuration
    if (config == NULL)
    {
        return ESP_ERR_INVALID_ARG;
    }
    cfg = *config;

    // Initialize all control system components
    ESP_ERROR_CHECK(encoder_driver_init(&cfg.encoder_config));
    ESP_ERROR_CHECK(motor_driver_init(&cfg.motor_driver_config));

    // Set the control system initialized bit in the event group
    xEventGroupSetBits(control_system_event_group, CONTROL_SYSTEM_INITIALIZED_BIT);
    ESP_LOGI(TAG, "Control system initialized.");
    return ESP_OK;
}

float triangle(float t_ms, float period_ms)
{
    float phase = fmodf(t_ms / period_ms, 1.0f);

    if (phase < 0.0f)
        phase += 1.0f;

    return phase < 0.5f
        ? -1.0f + 4.0f * phase
        : 3.0f - 4.0f * phase;
}

void control_system_task(void *arg)
{
    // Register the control system task with the safety system
    ESP_ERROR_CHECK(safety_system_register_task());

    // Wait for the control system to be initialized before starting the main loop
    xEventGroupWaitBits(control_system_event_group, CONTROL_SYSTEM_INITIALIZED_BIT, pdFALSE, pdTRUE, portMAX_DELAY);

    // Main control loop
    float shaft_angles[2] = {0.0f, 0.0f};
    float voltage[2] = {0.0f, 0.0f};
    TickType_t last_wake = xTaskGetTickCount();
    while (!safety_system_is_shutting_down())
    {

        // Read the shaft angles from the encoder
        encoder_driver_get_angles(shaft_angles);

        // Add telemetry samples to the UDP interface
        udp_interface_add_control_sample(shaft_angles[0], shaft_angles[1]);

        voltage[0] = sin(0.2f * 3.14159f * (float)xTaskGetTickCount() / 1000.0f) * 5.0f; // Example voltage for motor A
        voltage[1] = (2*triangle(0.5f * (float)xTaskGetTickCount()/ 1000.0f, 5.0f)-1) * 5.0f; // Example voltage for motor B
        //calculate the voltage to the motors
        motor_driver_set_voltage_motor_A(voltage[0]);
        motor_driver_set_voltage_motor_B(voltage[1]);

        // Wait for the next cycle
        xTaskDelayUntil(&last_wake, pdMS_TO_TICKS(cfg.task_period_ms));
    }

    // Cleanup and exit the task
    xEventGroupClearBits(control_system_event_group, CONTROL_SYSTEM_INITIALIZED_BIT);
    ESP_ERROR_CHECK(safety_system_unregister_task());
    ESP_LOGI(TAG, "Control system task finished.");
    vTaskDelete(NULL);
}


