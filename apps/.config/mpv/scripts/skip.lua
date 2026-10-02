-- Importing mpv module
local mpv = require('mp')
local mpv_options = require("mp.options")

local options = { -- setting default options
    op_start = 0, op_end = 0, ed_start = 0, ed_end = 0,
    toggle = false, toggle_key = "T", offset = 0,
}
mpv_options.read_options(options, "skip") --reading script-opts data

local skipped_op = false
local skipped_ed = false
local skip_enabled = true

-- Main function to check and skip if within the defined section
local function skip()
    if not skip_enabled then
        return
    end

    local current_time = mp.get_property_number("time-pos")

    if not current_time then
        return
    end

    local op_target = options.op_end - options.offset
    local ed_target = options.ed_end - options.offset

    -- Check for opening sequence
    if current_time >= options.op_start and current_time < op_target then
        if options.toggle or not skipped_op then
            mp.set_property_number("time-pos", op_target)
            skipped_op = true
        end
    end

    -- Check for ending sequence
    if current_time >= options.ed_start and current_time < ed_target then
        if options.toggle or not skipped_ed then
            mp.set_property_number("time-pos", ed_target)
            skipped_ed = true
        end
    end
end

-- Toggle skip on/off
local function toggle_skip()
    skip_enabled = not skip_enabled
    if skip_enabled then
        skipped_op = false
        skipped_ed = false
    end
    mp.osd_message("Skip: " .. (skip_enabled and "ON" or "OFF"), 2)
end

if options.toggle then
    mp.add_key_binding(options.toggle_key, "toggle-skip", toggle_skip)
end

-- Bind the function to be called whenever the time position is changed
mp.observe_property("time-pos", "number", skip)
