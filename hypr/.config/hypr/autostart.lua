-- Extra autostart processes.
-- o.launch_on_start("my-service")

-- EasyEffects audio DSP (speaker/headphone EQ + compression, mic denoise).
-- Runs headless; presets autoload per output route.
o.launch_on_start("easyeffects --service-mode --hide-window")
