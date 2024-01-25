# Burrow
Burrow is thermostat written in python. It uses Home Assistant to display information and facilitate changes. Burrow supports a daily schedule with presets, home proximity via ping, and zones. It uses weighted averages to set the home temperature.

The HVAC unit needs to be connected to something that can communicate over MQTT. The HVAC python script is designed to run on a raspberry pi with some relays attached, this is not documented.

Temperature sensors are BLE devices that HA can see, an automation is needed to publish updates over MQTT included and works 

# Home Assistant conifg
- name: "Burrow"
    unique_id: "Burrow"
    current_temperature_topic: "burrow/temperature/f"
    max_temp: 80
    min_temp: 60
    precision: 0.5
    preset_modes:
      - "day"
      - "night"
      - "morning"
      - "away"
    preset_mode_state_topic: "burrow/burrow/mode"
    preset_mode_command_topic: "burrow/burrow/setpreset"
    swing_modes: ["Home", "Out", "Off", "More", "Fan"]
    swing_mode_command_topic: "burrow/burrow/set"
    swing_mode_state_topic: "burrow/burrow/get"

    mode_state_topic: "burrow/system/get"
    mode_command_topic: "burrow/system/set"
    modes: ["off", "heat", "cool", "fan_only", "auto"]
    temperature_state_topic: "burrow/system/target/get"
    temperature_command_topic: "burrow/system/target/setf"

