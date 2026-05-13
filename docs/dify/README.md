# Dify Chatflow Notes

This folder contains the current Dify Chatflow setup notes and test inputs for Earth Online.

## Current NPC coverage

Only one NPC is wired in the backend right now:

- `mother`

The backend profile is defined in [npc_profiles.py](/C:/Users/admin/Desktop/个人资料/online/earthMockServer/app/services/npc_profiles.py:12).

## Files

- [mother_chatflow_setup.md](/C:/Users/admin/Desktop/个人资料/online/earthMockServer/docs/dify/mother_chatflow_setup.md): copy-paste setup guide for the mother NPC Chatflow
- [test_inputs/mother_inputs_object.json](/C:/Users/admin/Desktop/个人资料/online/earthMockServer/docs/dify/test_inputs/mother_inputs_object.json): raw player context object
- [test_inputs/mother_chat_messages_payload.json](/C:/Users/admin/Desktop/个人资料/online/earthMockServer/docs/dify/test_inputs/mother_chat_messages_payload.json): full `/chat-messages` request body sample

## Recommended convention

- Keep `query` for the current trigger or player message
- Keep `inputs.raw_inputs` as the single JSON string consumed by the Dify start node
- Let the final Chatflow output be a JSON string with `title`, `content`, `should_notify`, and `emotion`

## Trigger types in use

- `morning_greeting`
- `late_night_check`
- `job_follow_up`
- `money_concern`
- `weather_care`
- `holiday_check_in`
- `player_reply`

## Notes

- The backend now sends both `raw_inputs` and the flattened fields, but Dify can be configured with only `raw_inputs`.
- If more NPCs are added later, create one `*_chatflow_setup.md` file per NPC under this folder.
