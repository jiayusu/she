import Foundation

let supportedContractVersion = "1.0"

protocol VersionedContract {
    var contractVersion: String { get }
}

enum MasteryState: String, Codable, CaseIterable, Sendable {
    case unseen = "UNSEEN"
    case heard = "HEARD"
    case comprehended = "COMPREHENDED"
    case imitated = "IMITATED"
    case promptedOutput = "PROMPTED_OUTPUT"
    case spontaneousOutput = "SPONTANEOUS_OUTPUT"
    case transferred = "TRANSFERRED"
}

enum EvidenceKind: String, Codable, Sendable {
    case prompted
    case spontaneous
    case transferred
    case comprehension
}

enum TeachingPressure: String, Codable, CaseIterable, Sendable {
    case low
    case normal
}

struct PetSummary: Codable, Equatable, Sendable {
    let name: String
    let mood: String
    let accessibilityLabel: String

    enum CodingKeys: String, CodingKey {
        case name, mood
        case accessibilityLabel = "accessibility_label"
    }
}

struct HighlightSummary: Codable, Equatable, Sendable {
    let text: String
    let evidenceID: String

    enum CodingKeys: String, CodingKey {
        case text
        case evidenceID = "evidence_id"
    }
}

struct TodayTask: Codable, Equatable, Sendable {
    let title: String
    let subtitle: String
    let progress: Double
    let actionLabel: String

    enum CodingKeys: String, CodingKey {
        case title, subtitle, progress
        case actionLabel = "action_label"
    }
}

struct DashboardMetrics: Codable, Equatable, Sendable {
    let spontaneousSpeakingCount: Int
    let unpromptedOutputCount: Int
    let newWords: [String]

    enum CodingKeys: String, CodingKey {
        case spontaneousSpeakingCount = "spontaneous_speaking_count"
        case unpromptedOutputCount = "unprompted_output_count"
        case newWords = "new_words"
    }
}

struct DeviceSummary: Codable, Equatable, Sendable {
    let deviceID: String
    let name: String
    let online: Bool
    let batteryPercent: Int?

    enum CodingKeys: String, CodingKey {
        case deviceID = "device_id"
        case name, online
        case batteryPercent = "battery_percent"
    }
}

struct DashboardSnapshot: Codable, Equatable, Sendable, VersionedContract {
    let contractVersion: String
    let generatedAt: String
    let greeting: String
    let pet: PetSummary
    let highlight: HighlightSummary
    let task: TodayTask
    let metrics: DashboardMetrics
    let device: DeviceSummary
    let mock: Bool

    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version"
        case generatedAt = "generated_at"
        case greeting, pet, highlight, task, metrics, device, mock
    }
}

struct LearningEvidence: Codable, Equatable, Identifiable, Sendable {
    let evidenceID: String
    let kind: EvidenceKind
    let expression: String
    let occurredAt: String
    let confidence: Double

    var id: String { evidenceID }

    enum CodingKeys: String, CodingKey {
        case evidenceID = "evidence_id"
        case kind, expression
        case occurredAt = "occurred_at"
        case confidence
    }
}

struct MasteryUpdate: Codable, Equatable, Sendable {
    let expression: String
    let from: MasteryState
    let to: MasteryState
    let evidenceIDs: [String]

    enum CodingKeys: String, CodingKey {
        case expression, from, to
        case evidenceIDs = "evidence_ids"
    }
}

struct WeeklyReport: Codable, Equatable, Sendable, VersionedContract {
    let contractVersion: String
    let periodStart: String
    let periodEnd: String
    let spontaneousSpeakingCount: Int
    let promptedSpeakingCount: Int
    let newSpontaneousWords: [String]
    let transferredWords: [String]
    let currentFocus: String
    let scaffoldTrend: String
    let evidence: [LearningEvidence]
    let masteryUpdates: [MasteryUpdate]
    let mock: Bool

    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version"
        case periodStart = "period_start"
        case periodEnd = "period_end"
        case spontaneousSpeakingCount = "spontaneous_speaking_count"
        case promptedSpeakingCount = "prompted_speaking_count"
        case newSpontaneousWords = "new_spontaneous_words"
        case transferredWords = "transferred_words"
        case currentFocus = "current_focus"
        case scaffoldTrend = "scaffold_trend"
        case evidence
        case masteryUpdates = "mastery_updates"
        case mock
    }
}

struct DeviceSettings: Codable, Equatable, Sendable, VersionedContract {
    let contractVersion: String
    let deviceID: String
    let name: String
    let online: Bool
    let batteryPercent: Int?
    var volume: Int
    var ledEnabled: Bool
    var cameraEnabled: Bool
    var rawAudioUploadEnabled: Bool
    let firmwareVersion: String
    let lastSeenAt: String
    let mock: Bool

    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version"
        case deviceID = "device_id"
        case name, online
        case batteryPercent = "battery_percent"
        case volume
        case ledEnabled = "led_enabled"
        case cameraEnabled = "camera_enabled"
        case rawAudioUploadEnabled = "raw_audio_upload_enabled"
        case firmwareVersion = "firmware_version"
        case lastSeenAt = "last_seen_at"
        case mock
    }
}

struct DeviceSettingsPatch: Codable, Equatable, Sendable {
    var volume: Int?
    var ledEnabled: Bool?
    var cameraEnabled: Bool?
    var rawAudioUploadEnabled: Bool?

    init(
        volume: Int? = nil,
        ledEnabled: Bool? = nil,
        cameraEnabled: Bool? = nil,
        rawAudioUploadEnabled: Bool? = nil
    ) {
        self.volume = volume
        self.ledEnabled = ledEnabled
        self.cameraEnabled = cameraEnabled
        self.rawAudioUploadEnabled = rawAudioUploadEnabled
    }

    enum CodingKeys: String, CodingKey {
        case volume
        case ledEnabled = "led_enabled"
        case cameraEnabled = "camera_enabled"
        case rawAudioUploadEnabled = "raw_audio_upload_enabled"
    }
}

struct ParentConstraints: Codable, Equatable, Sendable, VersionedContract {
    let contractVersion: String
    var sessionBudgetSeconds: Int
    var preferredTopics: [String]
    var avoidTopics: [String]
    var nextDayContext: String
    var teachingPressure: TeachingPressure
    let updatedAt: String
    let mock: Bool

    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version"
        case sessionBudgetSeconds = "session_budget_seconds"
        case preferredTopics = "preferred_topics"
        case avoidTopics = "avoid_topics"
        case nextDayContext = "next_day_context"
        case teachingPressure = "teaching_pressure"
        case updatedAt = "updated_at"
        case mock
    }
}

struct ParentConstraintsUpdate: Codable, Equatable, Sendable {
    let sessionBudgetSeconds: Int
    let preferredTopics: [String]
    let avoidTopics: [String]
    let nextDayContext: String
    let teachingPressure: TeachingPressure

    enum CodingKeys: String, CodingKey {
        case sessionBudgetSeconds = "session_budget_seconds"
        case preferredTopics = "preferred_topics"
        case avoidTopics = "avoid_topics"
        case nextDayContext = "next_day_context"
        case teachingPressure = "teaching_pressure"
    }
}

struct PrivacyOperation: Codable, Equatable, Sendable, VersionedContract {
    let contractVersion: String
    let operation: String
    let status: String
    let mock: Bool
    let storeMutated: Bool

    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version"
        case operation, status, mock
        case storeMutated = "store_mutated"
    }
}
