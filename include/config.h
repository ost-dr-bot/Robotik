/**
 * @file config.c
 * @brief Configuration constants for the robot system.
 * @author Jonas Frei
 * @date 01.09.2026
 * @version 1.0
 *
 * @warning DO NOT add any other content besides #define statements to this file.
 * This file is intended to be included only in main.c to provide configuration constants.
 * DO NOT include this file in other source files besides main.c.
 *
 * @todo Replace these constants to match your specific robot.
 */

#pragma once

// Safety system configuration constants
#define SAFETY_SYSTEM_TASK_PERIOD_MS 1     /**< Safety system task period [ms] */
#define SAFETY_SYSTEM_EVENT_QUEUE_LENGTH 3 /**< Safety system event queue length [-] */

// I2C master configuration constants
#define I2C_MASTER_SCL_IO 33 /**< GPIO pin for I2C master SCL */
#define I2C_MASTER_SDA_IO 32 /**< GPIO pin for I2C master SDA */

// UPD interface configuration constants
#define UPD_INTERFACE_HOSTNAME "Robi"     /**< Hostname for the ESP32 on the network */
#define UPD_INTERFACE_UDP_PORT 3333          /**< UDP port for communication */
#define UPD_INTERFACE_TASK_PERIOD_MS 20      /**< Network task period [ms] */
#define UPD_INTERFACE_TELEMETRY_QUEUE_LEN 64 /**< Length of the telemetry queue [-] */

// Encoder driver configuration constants
#define ENCODER_DRIVER_ENC_A_PPR 16.0f /**< Encoder A pulses per revolution */
#define ENCODER_DRIVER_ENC_B_PPR 16.0f /**< Encoder B pulses per revolution */

// Motor driver configuration constants
#define MOTOR_DRIVER_BUS_VOLTAGE_UPDATE_PERIOD_MS 10000 /**< Bus voltage update period [ms] */
#define MOTOR_DRIVER_MIN_BUS_VOLTAGE 5.0f               /**< Minimum bus voltage [V] */
#define MOTOR_DRIVER_MOTOR_A_FREE_SPIN false            /**< Motor A free spin configuration */
#define MOTOR_DRIVER_MOTOR_B_FREE_SPIN false            /**< Motor B free spin configuration */

// Control system configuration constants
#define CONTROL_SYSTEM_TASK_PERIOD_MS 5                                               /**< Control system task period [ms] */
#define CONTROL_SYSTEM_TASK_PERIOD_S ((float)CONTROL_SYSTEM_TASK_PERIOD_MS / 1000.0f) /**< Control system task period [s] */
#define CONTROL_SYSTEM_TELEMETRY_PERIOD_MS 100 /**< Control system telemetry period [ms] */

// Sequencer configuration constants
#define SEQUENCER_TASK_PERIOD_MS 100 /**< Sequencer task period [ms] */
