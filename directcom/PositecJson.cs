using System.Collections.Generic;
using System.Runtime.Serialization;

namespace WorxMqttInterface.Json // Angepasster Namespace
{
    #region Enums
    public enum ErrorCode
    {
        UNK = -1,
        NONE = 0,
        TRAPPED = 1,
        LIFTED = 2,
        WIRE_MISSING = 3,
        OUTSIDE_WIRE = 4,
        RAINING = 5,
        CLOSE_DOOR_TO_CUT_GRASS = 6,
        CLOSE_DOOR_GO_HOME = 7,
        MOTOR_BLADE_FAULT = 8,
        MOTOR_WHEELS_FAULT = 9,
        TRAPPED_TIMEOUT_FAULT = 10,
        UPSIDE_DOWN = 11,
        BATTERY_LOW = 12,
        REVERSE_WIRE = 13,
        BATTERY_CHARGE = 14,
        FIND_TIMEOUT = 15,
        LOCK = 16,
        BATTERY_TEMP = 17,
        DUMMY_MODEL = 18,
        BATTERY_TRUNK = 19,
        WIRE_SYNC = 20,
        NUM = 21,
        RTK_Charging_station_docking = 100,
        RTK_HBI = 101,
        RTK_OTA = 102,
        RTK_Map = 103,
        RTK_Excessive_slope = 104,
        RTK_Unreachable_zone = 105,
        RTK_Unreachable_chargingstation = 106,
        RTK_Insufficient_sensor_data = 108,
        RTK_Training_start_disallowed = 109,
        VISION_CAMERA = 110,
        VISION_mapping_exploration_required = 111,
        VISION_mapping_exploration_failed = 112,
        VISION_RFID_reader_error = 113,
        VISION_Headlight_error = 114,
        RTK_Missing_charging_station = 115,
        RV_Blade_height_adjustment_blocked = 116
    }
    public enum StatusCode
    {
        UNK = -1,
        IDLE = 0,
        HOME = 1,
        START_SEQUENCE = 2,
        LEAVE_HOUSE = 3,
        FOLLOW_WIRE = 4,
        SEARCHING_HOME = 5,
        SEARCHING_WIRE = 6,
        GRASS_CUTTING = 7,
        LIFT_RECOVERY = 8,
        TRAPPED_RECOVERY = 9,
        BLADE_BLOCKED_RECOVERY = 10,
        DEBUG = 11,
        REMOTE_CONTROL = 12,
        OFF_LIMITS_ESCAPE = 13,
        GOING_HOME = 30,
        AREA_TRAINING = 31,
        BORDER_CUT = 32,
        AREA_SEARCH = 33,
        PAUSE = 34,
        RTK_MOVE_TO_ZONE = 103, // Moving to zone - The mower is reaching a zone without cutting
        RTK_GOING_HOME = 104,   // Going home - The mower is returning to the charging station
        VISION_border_crossing = 110,
        VISION_exploring_lawn = 111
    }
    public enum ChargeCode // Angepasster Name, um Konflikt mit 'System' zu vermeiden
    {
        CHARGED = 0,
        CHARGING = 1,
        ERROR_CHARGING = 2
    }
    public enum Command
    {
        PING = 0,
        START = 1,
        STOP = 2,
        HOME = 3,
        ZONE_SEARCH_REQ = 4,
        LOCK = 5,
        UNLOCK = 6,
        RESET_LOG = 7,
        PAUSE_OVER_WIRE,
        SAFE_HOMING
    }
    #endregion

    [DataContract]
    public struct ApiEntry
    {
        [DataMember(Name = "Login")] public string? Login;
        [DataMember(Name = "WebApi")] public string? WebApi;
        [DataMember(Name = "CliId")] public string? ClientId;
    }

    #region AWS IoT
    [DataContract]
    public struct OneTimeScheduler
    {
        [DataMember(Name = "bc")] public int BorderCut;
        [DataMember(Name = "wtm")] public int WorkTime;
    }

    [DataContract]
    public struct Schedule
    {
        [DataMember(Name = "m")] public int Mode;
        [DataMember(Name = "distm", EmitDefaultValue = false)] public int? Party;
        [DataMember(Name = "ots", EmitDefaultValue = false)] public OneTimeScheduler? Ots;
        [DataMember(Name = "p")] public int Perc;
        [DataMember(Name = "d")] public List<List<object>> Days;
        [DataMember(Name = "dd", EmitDefaultValue = false)] public List<List<object>> DDays;
    }

    [DataContract]
    public class ModuleConfig
    {
        [DataMember(Name = "enabled")] public int Enabled;
    }

    [DataContract]
    public class ModuleConfigDF
    {
        [DataMember(Name = "cut")] public int Cutting;
        [DataMember(Name = "fh")] public int FastHome;
    }

    [DataContract]
    public class ModuleConfigs
    {
        [DataMember(Name = "US")] public ModuleConfig? US;
        [DataMember(Name = "4G")] public ModuleConfig? G4;
        [DataMember(Name = "DF")] public ModuleConfigDF? DF;
    }

    [DataContract]
    public class AutoLock
    {
        [DataMember(Name = "lvl")] public int Level;
        [DataMember(Name = "t")] public int Time;
    }

    [DataContract]
    public struct ConfigP0
    {
        [DataMember(Name = "id", EmitDefaultValue = false)] public ushort? Id;
        [DataMember(Name = "lg")] public string? Language;
        [DataMember(Name = "tm")] public string? Time;
        [DataMember(Name = "dt")] public string? Date;
        [DataMember(Name = "sc")] public Schedule Schedule;
        [DataMember(Name = "cmd")] public Command Cmd;
        [DataMember(Name = "mz")] public int[] MultiZones;
        [DataMember(Name = "mzv")] public int[] MultiZonePercs;
        [DataMember(Name = "mzk", EmitDefaultValue = false)] public int? MultiZoneKeeper;
        [DataMember(Name = "rd")] public int RainDelay;
        [DataMember(Name = "sn")] public string? SerialNo;
        [DataMember(Name = "al", EmitDefaultValue = false)] public AutoLock AutoLock;
        [DataMember(Name = "tq", EmitDefaultValue = false)] public int? Torque;
        [DataMember(Name = "modules", EmitDefaultValue = false)] public ModuleConfigs ModulesC;
    }

    [DataContract]
    public struct ConfigP1
    {
        [DataMember(Name = "id", EmitDefaultValue = false)] public ushort? Id;
        [DataMember(Name = "lg")] public string? Language;
        [DataMember(Name = "cmd")] public Command Cmd;
        [DataMember(Name = "rd")] public int RainDelay;
        [DataMember(Name = "al", EmitDefaultValue = false)] public AutoLock AutoLock;
        [DataMember(Name = "tq", EmitDefaultValue = false)] public int? Torque;
    }

    [DataContract]
    public struct Battery
    {
        [DataMember(Name = "t")] public float Temp;
        [DataMember(Name = "v")] public float Volt;
        [DataMember(Name = "p")] public float Perc;
        [DataMember(Name = "nr")] public int Cycle;
        [DataMember(Name = "c")] public ChargeCode Charging;
        [DataMember(Name = "m")] public int Maintenance;
    }

    [DataContract]
    public struct Statistic
    {
        [DataMember(Name = "b")] public int Blade;
        [DataMember(Name = "d")] public int Distance;
        [DataMember(Name = "wt")] public int WorkTime;
        [DataMember(Name = "bl")] public int BorderLen;
    }

    [DataContract]
    public struct Rain
    {
        [DataMember(Name = "s")] public int State;
        [DataMember(Name = "cnt")] public int Counter;
    }

    [DataContract]
    public struct ModuleState
    {
        [DataMember(Name = "stat")] public string? State;
    }

    [DataContract]
    public class ModuleStates
    {
        [DataMember(Name = "US")] public ModuleState? US;
        [DataMember(Name = "DF")] public ModuleState? DF;
        [DataMember(Name = "RL")] public ModuleState? RL;
        [DataMember(Name = "4G")] public ModuleState? G4;
    }

    [DataContract]
    public class DataBase
    {
        [DataMember(Name = "bt")] public Battery Battery;
        [DataMember(Name = "dmp")] public float[] Orient = [0, 0, 0];
        [DataMember(Name = "st")] public Statistic Statistic;
        [DataMember(Name = "ls")] public StatusCode LastState;
        [DataMember(Name = "le")] public ErrorCode LastError;
        [DataMember(Name = "rsi")] public int RecvSignal;
        [DataMember(Name = "act", EmitDefaultValue = false)] public int? Act;
        [DataMember(Name = "tr", EmitDefaultValue = false)] public int? Tr;
        [DataMember(Name = "conn", EmitDefaultValue = false)] public string? Conn;
        [DataMember(Name = "rain", EmitDefaultValue = false)] public Rain Rain;
    }

    [DataContract]
    public class DataP0 : DataBase
    {
        [DataMember(Name = "mac")] public string? MacAdr;
        [DataMember(Name = "fw")] public double Firmware;
        [DataMember(Name = "fwb", EmitDefaultValue = false)] public int? Beta;
        [DataMember(Name = "lz")] public int LastZone;
        [DataMember(Name = "lk")] public int Lock;
        [DataMember(Name = "modules", EmitDefaultValue = false)] public ModuleStates? ModulesD;
    }

    [DataContract]
    public class DataP1 : DataBase
    {
        [DataMember(Name = "tm")] public string? Stamp = string.Empty;
        [DataMember(Name = "fw")] public string? Firmware = string.Empty;
    }

    [DataContract]
    public class MqttP0
    {
        [DataMember(Name = "cfg")]
        public ConfigP0 Cfg;
        [DataMember(Name = "dat")]
        public DataP0 Dat = new();
    }

    [DataContract]
    public class MqttP1
    {
        [DataMember(Name = "cfg")]
        public ConfigP1 Cfg;
        [DataMember(Name = "dat")]
        public DataP1 Dat = new();
    }
    #endregion

    #region Web API
    #region OAuth
    [DataContract]
    public class OError
    {
        [DataMember(Name = "error")] public string? Error;
        [DataMember(Name = "error_description")] public string? Desc;
        [DataMember(Name = "message")] public string? Message;
    }

    [DataContract]
    public class OAuth
    {
        [DataMember(Name = "token_type")]
        public string? Type;
        [DataMember(Name = "expires_in")]
        public int Expires;
        [DataMember(Name = "access_token")]
        public string? Access;
        [DataMember(Name = "refresh_token")]
        public string? Refresh;
        // Hinzugefügt für id_token, falls benötigt
        [DataMember(Name = "id_token")]
        public string? IdToken { get; set; }
    }
    #endregion

    #region User me
    [DataContract]
    public class UserMe
    {
        [DataMember(Name = "id")] public int Id;
        [DataMember(Name = "mqtt_endpoint")] public string? Endpoint;
    }
    #endregion

    #region Product item + Status
    [DataContract]
    public struct MqttTopic
    {
        [DataMember(Name = "command_in")] public string CmdIn { get; set; }
        [DataMember(Name = "command_out")] public string CmdOut { get; set; }
    }
    [DataContract]
    public class LastStatusOld
    {
        [DataMember(Name = "timestamp")]
        public string? TimeStamp;
        [DataMember(Name = "payload")]
        public MqttP0? PayLoad;
    }
    [DataContract]
    public class LastStatusNew
    {
        [DataMember(Name = "timestamp")]
        public string? TimeStamp;
        [DataMember(Name = "payload")]
        public MqttP1? PayLoad;
    }

    [DataContract]
    public class ProductItem
    {
        [DataMember(Name = "id")] public int Id { get; set; }
        [DataMember(Name = "uuid")] public string? Uuid { get; set; }
        [DataMember(Name = "user_id")] public int UserId { get; set; }
        [DataMember(Name = "product_id")] public int ProductId { get; set; }
        [DataMember(Name = "serial_number")] public string? SerialNo { get; set; }
        [DataMember(Name = "mac_address")] public string? MacAdr { get; set; }
        [DataMember(Name = "name")] public string? Name { get; set; }
        [DataMember(Name = "locked")] public bool Locked { get; set; }
        [DataMember(Name = "firmware_auto_upgrade")] public bool AutoUpgd { get; set; }
        [DataMember(Name = "mqtt_endpoint")] public string? Endpoint { get; set; } // Broker URL
        [DataMember(Name = "mqtt_port")] public int MqttPort { get; set; } = 443; // Standardport, falls nicht explizit angegeben
        [DataMember(Name = "mqtt_topics")] public MqttTopic? Topic { get; set; }
        [DataMember(Name = "online")] public bool Online { get; set; }
        [DataMember(Name = "protocol")] public int Protocol { get; set; }
        [DataMember(Name = "capabilities")] public List<string>? Capas { get; set; }
        [DataMember(Name = "blade_work_time_reset")] public int? BladeReset { get; set; }
        [DataMember(Name = "blade_work_time_reset_at")] public string? BladeResetAt { get; set; }
    }

    [DataContract]
    public class StatusOld
    {
        [DataMember(Name = "serial_number")] public string? SerialNo;
        [DataMember(Name = "name")] public string? Name;
        [DataMember(Name = "online")] public bool Online;
        [DataMember(Name = "protocol")] public int Protocol;
        [DataMember(Name = "blade_work_time_reset")] public int? BladeReset;
        [DataMember(Name = "last_status")] public LastStatusOld? Last;
    }
    [DataContract]
    public class StatusNew
    {
        [DataMember(Name = "serial_number")] public string? SerialNo;
        [DataMember(Name = "name")] public string? Name;
        [DataMember(Name = "online")] public bool Online;
        [DataMember(Name = "protocol")] public int Protocol;
        [DataMember(Name = "blade_work_time_reset")] public int? BladeReset;
        [DataMember(Name = "last_status")] public LastStatusNew? Last;
    }
    #endregion

    #region Activity log
    [DataContract]
    public struct ActivityConfig
    {
        [DataMember(Name = "dt")] public string? Date;
        [DataMember(Name = "tm")] public string? Time;
    }
    [DataContract]
    public struct ActivityBattery
    {
        [DataMember(Name = "c")] public ChargeCode Charging;
        [DataMember(Name = "m")] public int Maintenance;
    }
    [DataContract]
    public struct ActivityData
    {
        [DataMember(Name = "le")] public ErrorCode LastError;
        [DataMember(Name = "ls")] public StatusCode LastState;
        [DataMember(Name = "lz")] public int LastZone;
        [DataMember(Name = "lk")] public int Lock;
        [DataMember(Name = "bt")] public ActivityBattery Battery;
    }
    [DataContract]
    public struct ActivityPayload
    {
        [DataMember(Name = "cfg")] public ActivityConfig Cfg;
        [DataMember(Name = "dat")] public ActivityData Dat;
    }
    [DataContract]
    public struct ActivityEntry
    {
        [DataMember(Name = "_id")] public string ActId;
        [DataMember(Name = "timestamp")] public string Stamp;
        [DataMember(Name = "product_item_id")] public string? MowId;
        [DataMember(Name = "payload")] public ActivityPayload Payload;
    }
    #endregion
    #endregion
}