.

[Client commands](#/api_cmds?id=client-commands)
================================================

[Server level commands](#/api_cmds?id=server-level-commands)
------------------------------------------------------------

### [Start listening to events](#/api_cmds?id=start-listening-to-events)

    interface {
        messageId: string;
        command: "start_listening";
    }

### [Set API schema version](#/api_cmds?id=set-api-schema-version)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "set_api_schema";
        schemaVersion: number;
    }

[Driver level commands](#/api_cmds?id=driver-level-commands)
------------------------------------------------------------

### [Set 2FA verify code](#/api_cmds?id=set-2fa-verify-code)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "driver.set_verify_code";
        verifyCode: string;
    }

Returns:

    interface {
        result: boolean;
    }

### [Set captcha](#/api_cmds?id=set-captcha)

\[compatible with schema version: 7+\]

    interface {
        messageId: string;
        command: "driver.set_captcha";
        captchaId?: string;
        captcha: string;
    }

Returns:

    interface {
        result: boolean;
    }

### [Update the station and device informations](#/api_cmds?id=update-the-station-and-device-informations)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "driver.poll_refresh";
    }

### [Get cloud connection status](#/api_cmds?id=get-cloud-connection-status)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "driver.is_connected";
    }

Returns:

    interface {
        connected: boolean;
    }

### [Get push notification connection status](#/api_cmds?id=get-push-notification-connection-status)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "driver.is_push_connected";
    }

Returns:

    interface {
        connected: boolean;
    }

### [Connect to cloud and push notifications](#/api_cmds?id=connect-to-cloud-and-push-notifications)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "driver.connect";
    }

Returns:

    interface {
        result: boolean;
    }

### [Disconnect from cloud and push notifications](#/api_cmds?id=disconnect-from-cloud-and-push-notifications)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "driver.disconnect";
    }

### [Get Video Events](#/api_cmds?id=get-video-events)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "driver.get_video_events";
        startTimestampMs?: number;
        endTimestampMs?: number;
        filter?: EventFilterType;
        maxResults?: number;
    }

Returns:

    interface {
        events: Array<EventRecordResponse>
    }

### [Get Alarm Events](#/api_cmds?id=get-alarm-events)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "driver.get_alarm_events";
        startTimestampMs?: number;
        endTimestampMs?: number;
        filter?: EventFilterType;
        maxResults?: number;
    }

Returns:

    interface {
        events: Array<EventRecordResponse>
    }

### [Get History Events](#/api_cmds?id=get-history-events)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "driver.get_history_events";
        startTimestampMs?: number;
        endTimestampMs?: number;
        filter?: EventFilterType;
        maxResults?: number;
    }

Returns:

    interface {
        events: Array<EventRecordResponse>
    }

### [Get MQTT notification connection status](#/api_cmds?id=get-mqtt-notification-connection-status)

\[compatible with schema version: 9+\]

    interface {
        messageId: string;
        command: "driver.is_mqtt_connected";
    }

Returns:

    interface {
        connected: boolean;
    }

### [Set log level](#/api_cmds?id=set-log-level)

\[compatible with schema version: 9+\]

    interface {
        messageId: string;
        command: "driver.set_log_level";
        level: "silly" | "trace" | "debug" | "info" | "warn" | "error" | "fatal";
    }

### [Get log level](#/api_cmds?id=get-log-level)

\[compatible with schema version: 9+\]

    interface {
        messageId: string;
        command: "driver.get_log_level";
    }

Returns:

    interface {
        level: "silly" | "trace" | "debug" | "info" | "warn" | "error" | "fatal";
    }

### [Start listening logs](#/api_cmds?id=start-listening-logs)

\[compatible with schema version: 9+\]

    interface {
        messageId: string;
        command: "driver.start_listening_logs";
    }

### [Stop listening logs](#/api_cmds?id=stop-listening-logs)

\[compatible with schema version: 9+\]

    interface {
        messageId: string;
        command: "driver.stop_listening_logs";
    }

### [Get if listening logs was started](#/api_cmds?id=get-if-listening-logs-was-started)

\[compatible with schema version: 21+\]

    interface {
        messageId: string;
        command: "driver.is_listening_logs";
    }

Returns:

    interface {
        started: boolean;
    }

[Station level commands](#/api_cmds?id=station-level-commands)
--------------------------------------------------------------

### [Reboot station](#/api_cmds?id=reboot-station)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "station.reboot";
        serialNumber: string;
    }

### [Get station connection status](#/api_cmds?id=get-station-connection-status)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "station.is_connected";
        serialNumber: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        connected: boolean;
    }

### [Connect to station](#/api_cmds?id=connect-to-station)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "station.connect";
        serialNumber: string;
    }

### [Disconnect from station](#/api_cmds?id=disconnect-from-station)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "station.disconnect";
    }

### [Get properties metadata](#/api_cmds?id=get-properties-metadata)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "station.get_properties_metadata";
        serialNumber: string;
    }

Returns:

    interface {
        properties: {
            [index: string]: PropertyMetadataAny;
        }
    }

### [Get property values](#/api_cmds?id=get-property-values)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "station.get_properties";
        serialNumber: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        properties: {
            [index: string]: PropertyValue;
        }
    }

### [Set property value](#/api_cmds?id=set-property-value)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "station.set_property";
        serialNumber: string;
        name: string;
        value: unknown;
    }

### [Trigger alarm sound](#/api_cmds?id=trigger-alarm-sound)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "station.trigger_alarm";
        serialNumber: string;
        seconds: number;
    }

### [Reset alarm sound](#/api_cmds?id=reset-alarm-sound)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "station.reset_alarm";
        serialNumber: string;
    }

### [Get supported commands](#/api_cmds?id=get-supported-commands)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "station.get_commands";
        serialNumber: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        commands: Array<CommandName>;
    }

### [Check command name](#/api_cmds?id=check-command-name)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "station.has_command";
        serialNumber: string;
        commandName: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        exists: boolean;
    }

### [Check property name](#/api_cmds?id=check-property-name)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "station.has_property";
        serialNumber: string;
        propertyName: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        exists: boolean;
    }

### [Set guard mode](#/api_cmds?id=set-guard-mode)

\[compatible with schema version: 0-12\]

_Deprecated: Removed since schema version 13. Use the set/get property commands instead._

    interface {
        messageId: string;
        command: "station.set_guard_mode";
        serialNumber: string;
        mode: number;
    }

### [Chime](#/api_cmds?id=chime)

\[compatible with schema version: 15+\]

Only supported if no doorbell device is registered at the station where the chime is to be performed.

    interface {
        messageId: string;
        command: "station.chime";
        serialNumber: string;
        ringtone?: number;
    }

### [Download image](#/api_cmds?id=download-image)

\[compatible with schema version: 17+\]

    interface {
        messageId: string;
        command: "station.download_image";
        serialNumber: string;
        file: string;
    }

### [Database Query Latest Info](#/api_cmds?id=database-query-latest-info)

\[compatible with schema version: 18+\]

    interface {
        messageId: string;
        command: "station.database_query_latest_info";
        serialNumber: string;
    }

### [Database Query Local](#/api_cmds?id=database-query-local)

\[compatible with schema version: 18+\]

    interface {
        messageId: string;
        command: "station.database_query_local";
        serialNumber: string;
        startDate: Date;
        endDate: Date;
        eventType?: FilterEventType;
        detectionType?: FilterDetectType;
        storageType?: FilterStorageType;
    }

### [Database Count By Date](#/api_cmds?id=database-count-by-date)

\[compatible with schema version: 18+\]

    interface {
        messageId: string;
        command: "station.database_count_by_date";
        serialNumber: string;
        startDate: Date;
        endDate: Date;
    }

### [Database Delete](#/api_cmds?id=database-delete)

\[compatible with schema version: 18+\]

    interface {
        messageId: string;
        command: "station.database_delete";
        serialNumber: string;
        ids: Array<number>;
    }

[Device level commands](#/api_cmds?id=device-level-commands)
------------------------------------------------------------

### [Get properties metadata](#/api_cmds?id=get-properties-metadata-1)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "device.get_properties_metadata";
        serialNumber: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        properties: {
            [index: string]: PropertyMetadataAny;
        }
    }

### [Get property values](#/api_cmds?id=get-property-values-1)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "device.get_properties";
        serialNumber: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        properties: {
            [index: string]: PropertyValue;
        }
    }

### [Set property value](#/api_cmds?id=set-property-value-1)

\[compatible with schema version: 0+\]

    interface {
        messageId: string;
        command: "device.set_property";
        serialNumber: string;
        name: string;
        value: unknown;
    }

### [Start live stream](#/api_cmds?id=start-live-stream)

\[compatible with schema version: 2+\]

    interface {
      messageId: string;
      command: "device.start_livestream";
      serialNumber: string;
    }

### [Stop live stream](#/api_cmds?id=stop-live-stream)

\[compatible with schema version: 2+\]

    interface {
      messageId: string;
      command: "device.stop_livestream";
      serialNumber: string;
    }

### [Get live stream status](#/api_cmds?id=get-live-stream-status)

\[compatible with schema version: 2+\]

    interface {
      messageId: string;
      command: "device.is_livestreaming";
      serialNumber: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        livestreaming: boolean;
    }

### [Trigger alarm sound](#/api_cmds?id=trigger-alarm-sound-1)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "device.trigger_alarm";
        serialNumber: string;
        seconds: number;
    }

### [Reset alarm sound](#/api_cmds?id=reset-alarm-sound-1)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "device.reset_alarm";
        serialNumber: string;
    }

### [Start video download](#/api_cmds?id=start-video-download)

\[compatible with schema version: 3+\]

    interface {
      messageId: string;
      command: "device.start_download";
      serialNumber: string;
      path: string;
      cipherId: number;
    }

### [Cancel video download](#/api_cmds?id=cancel-video-download)

\[compatible with schema version: 3+\]

    interface {
      messageId: string;
      command: "device.cancel_download";
      serialNumber: string;
    }

### [Get download status](#/api_cmds?id=get-download-status)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.is_downloading";
      serialNumber: string;
    }

Returns:

    interface {
        serialNumber: string;
        downloading: boolean;
    }

### [Pan and tilt camera](#/api_cmds?id=pan-and-tilt-camera)

\[compatible with schema version: 3+\]

    interface {
      messageId: string;
      command: "device.pan_and_tilt";
      serialNumber: string;
      direction: PanTiltDirection;
    }

### [Calibrate pan and tilt camera](#/api_cmds?id=calibrate-pan-and-tilt-camera)

\[compatible with schema version: 10+\]

    interface {
      messageId: string;
      command: "device.calibrate";
      serialNumber: string;
    }

### [Doorbell quick response](#/api_cmds?id=doorbell-quick-response)

\[compatible with schema version: 3+\]

    interface {
      messageId: string;
      command: "device.quick_response";
      serialNumber: string;
      voiceId: number;
    }

### [Get doorbell quick response voices](#/api_cmds?id=get-doorbell-quick-response-voices)

\[compatible with schema version: 3+\]

    interface {
      messageId: string;
      command: "device.get_voices";
      serialNumber: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        voices: Voices
    }

### [Get supported commands](#/api_cmds?id=get-supported-commands-1)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "device.get_commands";
        serialNumber: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        commands: Array<CommandName>;
    }

### [Check command name](#/api_cmds?id=check-command-name-1)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "device.has_command";
        serialNumber: string;
        commandName: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        exists: boolean;
    }

### [Check property name](#/api_cmds?id=check-property-name-1)

\[compatible with schema version: 3+\]

    interface {
        messageId: string;
        command: "device.has_property";
        serialNumber: string;
        propertyName: string;
    }

Returns:

    interface {
        serialNumber: string;  // [added with schema version: 4+]
        exists: boolean;
    }

### [Start RTSP live stream](#/api_cmds?id=start-rtsp-live-stream)

\[compatible with schema version: 6+\]

    interface {
      messageId: string;
      command: "device.start_rtsp_livestream";
      serialNumber: string;
    }

### [Stop RTSP live stream](#/api_cmds?id=stop-rtsp-live-stream)

\[compatible with schema version: 6+\]

    interface {
      messageId: string;
      command: "device.stop_rtsp_livestream";
      serialNumber: string;
    }

### [Get RTSP live stream status](#/api_cmds?id=get-rtsp-live-stream-status)

\[compatible with schema version: 6+\]

    interface {
      messageId: string;
      command: "device.is_rtsp_livestreaming";
      serialNumber: string;
    }

Returns:

    interface {
        serialNumber: string;
        livestreaming: boolean;
    }

### [Calibrate lock](#/api_cmds?id=calibrate-lock)

\[compatible with schema version: 9+\]

    interface {
      messageId: string;
      command: "device.calibrate_lock";
      serialNumber: string;
    }

### [Unlock](#/api_cmds?id=unlock)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.unlock";
      serialNumber: string;
    }

### [Start talkback](#/api_cmds?id=start-talkback)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.start_talkback";
      serialNumber: string;
    }

### [Stop talkback](#/api_cmds?id=stop-talkback)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.stop_talkback";
      serialNumber: string;
    }

### [Get talkback status](#/api_cmds?id=get-talkback-status)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.is_talkback_ongoing";
      serialNumber: string;
    }

Returns:

    interface {
        serialNumber: string;
        talkbackOngoing: boolean;
    }

### [Send talkback audio data](#/api_cmds?id=send-talkback-audio-data)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.talkback_audio_data";
      serialNumber: string;
      buffer: Buffer;
    }

### [Snooze](#/api_cmds?id=snooze)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.snooze";
      serialNumber: string;
      snoozeTime: number;
      snoozeChime?: boolean;
      snoozeMotion?: boolean;
      snoozeHomebase?: boolean;
    }

### [Add User](#/api_cmds?id=add-user)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.add_user";
      serialNumber: string;
      username: string;
      passcode: string;
      schedule?: Schedule;
    }

### [Delete User](#/api_cmds?id=delete-user)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.delete_user";
      serialNumber: string;
      username: string;
    }

### [Get Users](#/api_cmds?id=get-users)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.get_users";
      serialNumber: string;
    }

Returns:

    interface {
        users: Array<User>;
    }

### [Update User Username](#/api_cmds?id=update-user-username)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.update_user";
      serialNumber: string;
      username: string;
      newUsername: string;
    }

### [Update User Passcode](#/api_cmds?id=update-user-passcode)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.update_user_passcode";
      serialNumber: string;
      username: string;
      passcode: string;
    }

### [Update User Schedule](#/api_cmds?id=update-user-schedule)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.update_user_schedule";
      serialNumber: string;
      username: string;
      schedule: Schedule;
    }

### [Verify PIN](#/api_cmds?id=verify-pin)

\[compatible with schema version: 13+\]

    interface {
      messageId: string;
      command: "device.verify_pin";
      serialNumber: string;
      pin: string;
    }

### [Open](#/api_cmds?id=open)

\[compatible with schema version: 21+\]

    interface {
      messageId: string;
      command: "device.open";
      serialNumber: string;
    }

### [Enable/disable status led](#/api_cmds?id=enabledisable-status-led)

\[compatible with schema version: 0-12\]

_Deprecated: Removed since schema version 13. Use the set/get property commands instead._

    interface {
      messageId: string;
      command: "device.set_status_led";
      serialNumber: string;
      value: boolean;
    }

### [Enable/disable auto nightvision](#/api_cmds?id=enabledisable-auto-nightvision)

\[compatible with schema version: 0-12\]

_Deprecated: Removed since schema version 13. Use the set/get property commands instead._

    interface {
      messageId: string;
      command: "device.set_auto_night_vision";
      serialNumber: string;
      value: boolean;
    }

### [Enable/disable motion detection](#/api_cmds?id=enabledisable-motion-detection)

\[compatible with schema version: 0-12\]

_Deprecated: Removed since schema version 13. Use the set/get property commands instead._

    interface {
      messageId: string;
      command: "device.set_motion_detection";
      serialNumber: string;
      value: boolean;
    }

### [Enable/disable sound detection](#/api_cmds?id=enabledisable-sound-detection)

\[compatible with schema version: 0-12\]

_Deprecated: Removed since schema version 13. Use the set/get property commands instead._

    interface {
      messageId: string;
      command: "device.set_sound_detection";
      serialNumber: string;
      value: boolean;
    }

### [Enable/disable pet detection](#/api_cmds?id=enabledisable-pet-detection)

\[compatible with schema version: 0-12\]

_Deprecated: Removed since schema version 13. Use the set/get property commands instead._

    interface {
      messageId: string;
      command: "device.set_pet_detection";
      serialNumber: string;
      value: boolean;
    }

### [Enable/disable RTSP stream](#/api_cmds?id=enabledisable-rtsp-stream)

\[compatible with schema version: 0-12\]

_Deprecated: Removed since schema version 13. Use the set/get property commands instead._

    interface {
      messageId: string;
      command: "device.set_rtsp_stream";
      serialNumber: string;
      value: boolean;
    }

### [Enable/disable anti theft detection](#/api_cmds?id=enabledisable-anti-theft-detection)

\[compatible with schema version: 0-12\]

_Deprecated: Removed since schema version 13. Use the set/get property commands instead._

    interface {
      messageId: string;
      command: "device.set_anti_theft_detection";
      serialNumber: string;
      value: boolean;
    }

### [Set watermark](#/api_cmds?id=set-watermark)

\[compatible with schema version: 0-12\]

_Deprecated: Removed since schema version 13. Use the set/get property commands instead._

    interface {
      messageId: string;
      command: "device.set_watermark";
      serialNumber: string;
      value: number;
    }

### [Enable/disable device](#/api_cmds?id=enabledisable-device)

\[compatible with schema version: 0-12\]

_Deprecated: Removed since schema version 13. Use the set/get property commands instead._

    interface {
      messageId: string;
      command: "device.enable_device";
      serialNumber: string;
      value: boolean;
    }

### [Lock/unlock device](#/api_cmds?id=lockunlock-device)

\[compatible with schema version: 0-12\]

_Deprecated: Removed since schema version 13. Use the set/get property commands instead._

    interface {
      messageId: string;
      command: "device.lock_device";
      serialNumber: string;
      value: boolean;
    }